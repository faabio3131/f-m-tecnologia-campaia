from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from tests_api.test_anniversary_lifecycle import clock
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, FINANCE, with_step_up, unique_idem


class BillingGuaranteeTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.gateway = self.charge()
        self.assertEqual(self.payment(self.gateway).status_code, 200)
        self.initial = self.state.subscriptions['demo-tenant']
        self.start = self.initial.paid_cycle_schedule.anchor_at
        self.quote = self.get_quote()

    def get_quote(self, client=None):
        result = (client or self.client).get('/billing/guarantee', headers=OWNER)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def request(self, client=None, headers=None, body=None):
        return (client or self.client).post('/billing/guarantee',
            headers=headers or {**with_step_up(OWNER), **unique_idem()},
            json=body if body is not None else {'fingerprint': self.quote['fingerprint'], 'accept': True})

    def test_request_preserves_paid_facts_consumption_and_ends_access_without_dispatching_a_refund(self):
        self.assertEqual(self.quote['state'], 'ELIGIBLE')
        self.assertEqual(Decimal(self.quote['paid_amount']), Decimal('1.00'))
        self.assertEqual(len(self.quote['items']), 1)
        first = self.state.idempotency.get('demo-tenant', 'billing-first-paid').result
        self.assertEqual(first['paid_at'], self.start)
        cycle = self.initial.paid_cycle_schedule.obligation_id('demo-tenant', 0)
        self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=cycle,
            operation_id='before-guarantee', action='strategy', at=datetime.now(timezone.utc))
        self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id='before-guarantee',
            kind='SETTLE', reference='delivered-before-guarantee', at=datetime.now(timezone.utc))
        with patch.object(self.state.billing_gateway, 'create_charge', side_effect=AssertionError('No new charge')):
            with patch.object(self.state.billing_gateway, 'void_charge', side_effect=AssertionError('No invoice delete')):
                response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['state'], 'REQUESTED')
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'CANCELED')
        self.assertFalse(self.usage().json()['access_active'])
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 5)
        self.assertEqual(len(self.state.charges), 1)
        self.assertEqual(self.state.charges[self.gateway].status.value, 'SETTLED')
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')
        blocked = self.client.post('/billing/subscription/reactivate', headers={**with_step_up(OWNER), **unique_idem()})
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 1)

    def test_exact_seven_day_boundary_is_inclusive(self):
        with clock(self.start + timedelta(days=7)):
            self.assertEqual(self.get_quote()['state'], 'ELIGIBLE')
            response = self.request()
        self.assertEqual(response.status_code, 200, response.text)

    def test_expired_commercial_window_does_not_silently_restart_or_register_a_request(self):
        with clock(self.start + timedelta(days=7, microseconds=1)):
            self.assertEqual(self.get_quote()['state'], 'EXPIRED')
            response = self.request()
        self.assertEqual(response.status_code, 409)
        self.assertIn('Direitos legais', response.json()['message'])
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-guarantee-request'))
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'ACTIVE')

    def test_timely_request_remains_recorded_after_deadline_restart_and_other_authorized_actor(self):
        headers = {**with_step_up(OWNER), **unique_idem()}
        response = self.request(headers=headers)
        self.assertEqual(response.status_code, 200)
        restarted = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(restarted.app.state.campaia.db._conn.close)
        with clock(self.start + timedelta(days=30)):
            self.assertEqual(self.get_quote(restarted), response.json())
            self.assertEqual(self.request(client=restarted, headers=headers).json(), response.json())
            self.assertEqual(self.request(client=restarted, headers={**with_step_up(FINANCE), **unique_idem()}).json(), response.json())
        conflict = {**with_step_up(FINANCE), 'Idempotency-Key': headers['Idempotency-Key']}
        self.assertEqual(self.request(headers=conflict).status_code, 409)
        self.assertEqual(sum(e.action == 'BILLING_GUARANTEE_REQUESTED' for e in self.state.audit.list_for_tenant('demo-tenant')), 1)

    def test_two_workers_register_one_case_and_audit_with_different_keys(self):
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda client: self.request(client=client), [self.client, other]))
        self.assertTrue(all(response.status_code == 200 for response in responses), [r.text for r in responses])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(sum(e.action == 'BILLING_GUARANTEE_REQUESTED' for e in self.state.audit.list_for_tenant('demo-tenant')), 1)

    def test_review_acceptance_auth_isolation_and_client_amount_rejected(self):
        self.assertEqual(self.client.get('/billing/guarantee', headers=OTHER_OWNER).status_code, 404)
        for body, status in [({'fingerprint': self.quote['fingerprint'], 'accept': False}, 422),
                             ({'fingerprint': self.quote['fingerprint'], 'accept': 'true'}, 422),
                             ({'fingerprint': '0' * 64, 'accept': True}, 409),
                             ({'fingerprint': self.quote['fingerprint'], 'accept': True, 'amount': '1000'}, 422)]:
            self.assertEqual(self.request(body=body).status_code, status)
        self.assertEqual(self.request(headers={**with_step_up(OTHER_OWNER), **unique_idem()}).status_code, 409)
        self.state.invalidate_step_up_for_session('bearer:demo-owner-token')
        self.assertEqual(self.request(headers={**OWNER, **unique_idem()}).status_code, 403)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-guarantee-request'))

    def test_request_failure_rolls_back_case_cancellation_closed_snapshot_and_audit(self):
        original = self.state.audit.append
        def append(**kwargs):
            result = original(**kwargs)
            if kwargs['action'] == 'BILLING_GUARANTEE_REQUESTED':
                raise RuntimeError('injected case failure')
            return result
        headers = {**with_step_up(OWNER), **unique_idem()}
        with patch.object(self.state.audit, 'append', side_effect=append):
            with self.assertRaisesRegex(RuntimeError, 'injected case failure'):
                self.request(headers=headers)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-guarantee-request'))
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-closure:' + self.initial.paid_cycle_schedule.lifecycle_id))
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'ACTIVE')
        self.assertFalse(any(e.action == 'BILLING_GUARANTEE_REQUESTED' for e in self.state.audit.list_for_tenant('demo-tenant')))
        self.assertEqual(self.request(headers=headers).status_code, 200)

    def test_reactivation_never_resets_first_paid_window(self):
        with clock(self.start + timedelta(days=8)):
            self.assertEqual(self.client.post('/billing/subscription/cancel', headers={**with_step_up(OWNER), **unique_idem()},
                json={'immediate': True}).status_code, 200)
            self.assertEqual(self.client.post('/billing/subscription/reactivate', headers={**with_step_up(OWNER), **unique_idem()}).status_code, 200)
            next_id = self.charge()
            self.assertEqual(self.payment(next_id, 'reactivated-paid').status_code, 200)
            self.assertEqual(self.get_quote()['state'], 'EXPIRED')
        self.assertEqual(self.state.idempotency.get('demo-tenant', 'billing-first-paid').result['paid_at'], self.start)

    def test_missing_historical_payment_proof_is_not_a_new_guarantee_window(self):
        original = self.state.idempotency.get
        def get(tenant, key):
            return None if key.startswith('billing-settlement-fact:') else original(tenant, key)
        with patch.object(self.state.idempotency, 'get', side_effect=get):
            self.assertEqual(self.get_quote()['state'], 'MANUAL_REVIEW')
            self.assertEqual(self.request().status_code, 409)

    def test_duplicate_payment_confirmation_does_not_reset_first_paid_fact(self):
        original = self.state.idempotency.get('demo-tenant', 'billing-first-paid').result
        with clock(self.start + timedelta(days=3)):
            self.assertEqual(self.payment(self.gateway, 'duplicate-later-paid').status_code, 200)
        self.assertEqual(self.state.idempotency.get('demo-tenant', 'billing-first-paid').result, original)
        self.assertEqual(self.get_quote()['first_paid_at'], self.start.isoformat())


class UnpaidGuaranteeTests(BillingCreditHarness, unittest.TestCase):
    def test_trial_without_payment_has_no_paid_guarantee_and_first_confirmation_starts_it(self):
        self.setup_subscription(trial=True)
        self.assertEqual(self.client.get('/billing/guarantee', headers=OWNER).json()['state'], 'UNAVAILABLE')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-first-paid'))
        self.payment(self.charge())
        self.assertEqual(self.client.get('/billing/guarantee', headers=OWNER).json()['state'], 'ELIGIBLE')

    def test_payment_fact_marker_rolls_back_with_a_failed_paid_grant(self):
        self.setup_subscription(trial=True)
        gateway = self.charge()
        invoice = self.state.charges[gateway]
        with patch('api.routes_billing.grant_paid_cycle', side_effect=RuntimeError('injected paid grant')):
            with self.assertRaisesRegex(RuntimeError, 'injected paid grant'):
                self.payment(gateway)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-first-paid'))
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-settlement-fact:' + invoice.billing_id))
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'TRIAL')
        self.assertEqual(self.payment(gateway).status_code, 200)
        self.assertEqual(self.client.get('/billing/guarantee', headers=OWNER).json()['state'], 'ELIGIBLE')
