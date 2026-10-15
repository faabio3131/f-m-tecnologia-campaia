from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from campaia_core.subscription import ChargeStatus
from campaia_core.payment_gateway import GatewayChargeStatus, parse_refund_observations
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, with_step_up, unique_idem


class RefundObservationTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.gateway = self.charge()
        self.payment(self.gateway, 'paid-before-refund')
        self.initial_cycle = self.state.subscriptions['demo-tenant'].paid_cycle_schedule
        self.counter = 0

    def event(self, refunds=None, *, status='REFUNDED', kind='PAYMENT_REFUNDED', token='test-webhook-secret', event_id=None):
        self.counter += 1
        return self.client.post('/webhooks/asaas', headers={'asaas-access-token': token},
            json={'id': event_id or f'refund-observed-{self.counter}', 'event': kind,
                  'payment': {'id': self.gateway, 'status': status, 'value': '1.00', 'refunds': refunds}})

    def item(self, client=None):
        return (client or self.client).get('/billing/charges', headers=OWNER).json()['items'][0]

    def test_pending_cancelled_and_done_are_distinct_and_sum_all_completed_refunds(self):
        result = self.event([{'status': 'PENDING', 'value': '1.00'}], status='REFUND_IN_PROGRESS')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.item()['gateway_refund_amount'], '0.00')
        self.assertEqual(self.item()['gateway_refund_state'], 'PROCESSING')
        self.assertFalse(self.usage().json()['access_active'])
        self.event([{'status': 'CANCELLED', 'value': '1.00'}])
        self.assertEqual(self.item()['gateway_refund_state'], 'NO_COMPLETED_REFUND')
        self.event([{'status': 'DONE', 'value': '0.40'}, {'status': 'DONE', 'value': '0.60'}])
        self.assertEqual(Decimal(self.item()['gateway_refund_amount']), Decimal('1.00'))
        self.assertEqual(self.item()['gateway_refund_state'], 'FULL_DONE')
        self.assertEqual(self.state.charges[self.gateway].status, ChargeStatus.SETTLED)
        self.assertEqual(self.state.charges[self.gateway].amount, Decimal('1.00'))
        self.assertEqual(self.state.subscriptions['demo-tenant'].paid_cycle_schedule, self.initial_cycle)
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 1)
        self.assertFalse(self.usage().json()['access_active'])

    def test_partial_refund_inside_received_snapshot_cannot_be_mistaken_for_fully_paid_access(self):
        response = self.event([{'status': 'DONE', 'value': '0.40'}], status='RECEIVED', kind='PAYMENT_RECEIVED')
        self.assertFalse(response.json()['reconciled'])
        self.assertEqual(self.item()['gateway_refund_state'], 'PARTIAL_DONE')
        self.assertEqual(Decimal(self.item()['gateway_refund_amount']), Decimal('0.40'))
        self.assertFalse(self.usage().json()['access_active'])
        self.payment(self.gateway, 'stale-confirmation-after-refund')
        self.assertFalse(self.usage().json()['access_active'])
        self.assertEqual(self.item()['gateway_refund_state'], 'PARTIAL_DONE')

    def test_missing_invalid_unknown_and_over_refund_never_confirm_a_return(self):
        for refunds, expected in [(None, 'MISSING'), ({'status': 'DONE', 'value': '1.00'}, 'MISSING'),
             ([{'status': 'DONE', 'value': True}], 'INVALID'), ([{'status': 'DONE', 'value': '1.001'}], 'INVALID'),
             ([{'status': 'FUTURE_STATUS', 'value': '1.00'}], 'INVALID'),
             ([{'status': 'DONE', 'value': '1.01'}], 'AMOUNT_CONFLICT')]:
            with self.subTest(refunds=refunds):
                self.assertEqual(self.event(refunds).status_code, 200)
                self.assertEqual(self.item()['gateway_refund_state'], expected)
                self.assertIsNone(self.item()['gateway_refund_amount'])
        self.assertFalse(self.usage().json()['access_active'])

    def test_older_weaker_observations_do_not_erase_completed_refund_evidence(self):
        self.event([{'status': 'DONE', 'value': '1.00'}])
        self.event([{'status': 'PENDING', 'value': '1.00'}], status='REFUND_IN_PROGRESS')
        self.assertEqual(self.item()['gateway_refund_state'], 'OBSERVATION_CONFLICT')
        self.assertEqual(Decimal(self.item()['gateway_refund_amount']), Decimal('1.00'))
        self.assertFalse(self.usage().json()['access_active'])

    def test_authentication_dedupe_privacy_and_restart_preserve_observations(self):
        values = [{'status': 'DONE', 'value': '0.50', 'description': 'PRIVATE-PAYER', 'creditCardToken': 'NO-CARD'}]
        self.assertEqual(self.event(values, token='wrong', event_id='refund-dedupe').status_code, 401)
        self.assertIsNone(self.item()['gateway_refund_state'])
        self.event(values, event_id='refund-dedupe')
        self.event([{'status': 'DONE', 'value': '1.00'}], event_id='refund-dedupe')
        stored = self.state.idempotency.get('demo-tenant', 'billing-receipt:refund-dedupe').result
        self.assertEqual(stored['refund_observations'], (('DONE', Decimal('0.50')),))
        self.assertNotIn('PRIVATE-PAYER', str(stored))
        self.assertNotIn('NO-CARD', str(stored))
        restarted = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(restarted.app.state.campaia.db._conn.close)
        self.assertEqual(Decimal(self.item(restarted)['gateway_refund_amount']), Decimal('0.50'))
        self.assertEqual(restarted.get('/billing/charges', headers=OTHER_OWNER).json()['items'], [])

    def test_explicit_get_uses_the_same_refund_authority_and_replay_never_refunds(self):
        values = [{'status': 'DONE', 'value': '1.00'}]
        original = self.state.billing_gateway.inspect_charge
        def inspect(*args):
            self.assertFalse(self.state.db.in_transaction)
            return replace(original(*args), status=GatewayChargeStatus.CONFIRMED,
                source_status='RECEIVED', refund_observations=parse_refund_observations(values), refunds_present=True)
        headers = {**with_step_up(OWNER), **unique_idem()}
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=inspect) as read:
            response = self.client.post(f'/billing/charges/{self.gateway}/reconcile', headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(response.json()['reconciled'])
            self.assertEqual(self.client.post(f'/billing/charges/{self.gateway}/reconcile', headers=headers).json(), response.json())
        self.assertEqual(read.call_count, 1)
        self.assertEqual(self.item()['gateway_refund_state'], 'FULL_DONE')
        self.assertEqual(self.item()['status_source'], 'RECONCILIATION')
        self.assertFalse(self.usage().json()['access_active'])

    def test_refund_observation_failure_rolls_back_amount_hold_audit_and_dedupe(self):
        original = self.state.audit.append
        def append(**kwargs):
            result = original(**kwargs)
            if kwargs['action'] == 'BILLING_PAYMENT_RECONCILIATION':
                raise RuntimeError('injected receipt failure')
            return result
        values = [{'status': 'DONE', 'value': '1.00'}]
        with patch.object(self.state.audit, 'append', side_effect=append):
            with self.assertRaisesRegex(RuntimeError, 'injected receipt failure'):
                self.event(values, event_id='refund-rollback')
        self.assertIsNone(self.item()['gateway_refund_state'])
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-receipt:refund-rollback'))
        self.assertFalse(self.state.asaas_webhook.already_seen('refund-rollback'))
        self.assertTrue(self.usage().json()['access_active'])
        self.assertEqual(self.event(values, event_id='refund-rollback').status_code, 200)
        self.assertEqual(self.item()['gateway_refund_state'], 'FULL_DONE')
