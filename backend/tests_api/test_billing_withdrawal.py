from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from campaia_core.billing_settlement import charge_command
from campaia_core.payment_gateway import GatewayChargeStatus
from decimal import Decimal
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from campaia_core.subscription import ChargeStatus
from tests_api.test_anniversary_lifecycle import clock
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, FINANCE, with_step_up, unique_idem


class UnpaidRenewalWithdrawalTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.payment(self.charge())
        self.assertEqual(self.consent(cap='20.00').status_code, 200)
        self.initial = self.state.subscriptions['demo-tenant']
        self.cycle = self.initial.paid_cycle_schedule.obligation_id('demo-tenant', 0)
        self.end = self.initial.paid_cycle_schedule.bounds(0)[1]
        for index in range(3):
            self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=self.cycle,
                operation_id=f'usage-{index}', action='strategy', at=datetime.now(timezone.utc))
            self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id=f'usage-{index}',
                kind='SETTLE', reference=f'delivery-{index}', at=datetime.now(timezone.utc))
        with clock(self.end):
            self.gateway = self.charge()
            result = self.client.post('/billing/subscription/cancel',
                headers={**with_step_up(OWNER), **unique_idem()}, json={'immediate': True})
            self.assertEqual(result.status_code, 200, result.text)
        self.invoice = self.state.charges[self.gateway]
        self.fingerprint = self.item()['withdrawal_fingerprint']
        self.assertIsNotNone(self.fingerprint)

    def item(self, client=None):
        return next(item for item in (client or self.client).get('/billing/charges', headers=OWNER).json()['items']
                    if item['gateway_charge_id'] == self.gateway)

    def withdraw(self, *, client=None, headers=None, body=None):
        return (client or self.client).post(f'/billing/charges/{self.gateway}/withdraw',
            headers=headers or {**with_step_up(OWNER), **unique_idem()},
            json=body if body is not None else {'fingerprint': self.fingerprint, 'accept': True})

    def test_verified_unpaid_withdrawal_preserves_history_and_allows_only_final_delivered_usage(self):
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')
        original = self.state.billing_gateway.void_charge
        def void(*args):
            self.assertFalse(self.state.db.in_transaction)
            return original(*args)
        self.state.charges[self.gateway] = replace(self.invoice, gateway_status='OVERDUE')
        headers = {**with_step_up(OWNER), **unique_idem()}
        with patch.object(self.state.billing_gateway, 'void_charge', side_effect=void) as dispatch:
            result = self.withdraw(headers=headers)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(self.withdraw(headers=headers).json(), result.json())
            conflict = {**with_step_up(FINANCE), 'Idempotency-Key': headers['Idempotency-Key']}
            self.assertEqual(self.withdraw(headers=conflict).status_code, 409)
            self.assertEqual(self.withdraw(headers={**with_step_up(FINANCE), **unique_idem()}).status_code, 200)
        self.assertEqual(dispatch.call_count, 1)
        self.assertEqual(self.item()['withdrawal_state'], 'VOID')
        self.assertIsNone(self.item()['withdrawal_fingerprint'])
        self.assertEqual(self.state.charges[self.gateway].amount, self.invoice.amount)
        self.assertNotEqual(self.state.charges[self.gateway].status, ChargeStatus.SETTLED)
        self.assertEqual(len(self.state.charges), 2)
        self.assertIsNotNone(self.state.idempotency.get('demo-tenant', 'billing-obligation:' + self.invoice.billing_id))
        quote = self.client.get('/billing/closure', headers=OWNER).json()
        self.assertEqual(quote['state'], 'INVOICE_REQUIRED')
        self.assertEqual(quote['amount'], '5.00')
        closed = self.client.post('/billing/closure', headers={**with_step_up(OWNER), **unique_idem()},
            json={'fingerprint': quote['fingerprint'], 'accept': True})
        self.assertEqual(closed.status_code, 200, closed.text)
        final = next(c for _key, c in self.state.charges.items_for_tenant('demo-tenant') if c.purpose.value == 'FINAL_USAGE')
        self.assertEqual(final.amount, Decimal('5.00'))
        final_id = next(key for key, c in self.state.charges.items_for_tenant('demo-tenant') if c.purpose.value == 'FINAL_USAGE')
        self.assertEqual(self.payment(final_id, 'final-after-withdrawal').status_code, 200)
        reactivated = self.client.post('/billing/subscription/reactivate', headers={**with_step_up(OWNER), **unique_idem()})
        self.assertEqual(reactivated.status_code, 200, reactivated.text)
        self.assertEqual(reactivated.json()['status'], 'PENDING_PAYMENT')
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 1)

    def test_timeout_after_external_delete_recovers_read_only_after_restart(self):
        original = self.state.billing_gateway.void_charge
        def lost(*args):
            original(*args)
            raise TimeoutError('lost acknowledgement')
        with patch.object(self.state.billing_gateway, 'void_charge', side_effect=lost) as dispatch:
            self.assertEqual(self.withdraw().status_code, 503)
        self.assertEqual(dispatch.call_count, 1)
        self.assertEqual(self.item()['withdrawal_state'], 'REQUESTED')
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')
        restarted = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(restarted.app.state.campaia.db._conn.close)
        with patch.object(restarted.app.state.campaia.billing_gateway, 'void_charge', side_effect=AssertionError('No repeat DELETE')):
            result = self.withdraw(client=restarted)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.item()['withdrawal_state'], 'VOID')

    def test_uncertain_before_delete_and_absence_never_authorize_a_second_attempt(self):
        with patch.object(self.state.billing_gateway, 'void_charge', side_effect=TimeoutError('unknown')) as dispatch:
            self.assertEqual(self.withdraw().status_code, 503)
            self.assertEqual(self.withdraw().status_code, 503)
        self.assertEqual(dispatch.call_count, 1)
        self.assertEqual(self.item()['withdrawal_state'], 'REQUESTED')
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')

    def test_two_workers_with_different_keys_delete_once(self):
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        from campaia_core.payment_simulator import PaymentGatewaySimulator
        original = PaymentGatewaySimulator.void_charge
        with patch.object(PaymentGatewaySimulator, 'void_charge', autospec=True, side_effect=original) as dispatched:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda client: self.withdraw(client=client), [self.client, other]))
        self.assertTrue(all(result.status_code == 200 for result in results), [r.text for r in results])
        self.assertEqual(dispatched.call_count, 1)
        self.assertEqual(len(self.state.charges), 2)

    def test_payment_and_restoration_after_withdrawal_block_separation_without_reactivation(self):
        self.assertEqual(self.withdraw().status_code, 200)
        paid = self.payment(self.gateway, 'paid-after-withdrawal')
        self.assertEqual(paid.status_code, 200, paid.text)
        self.assertFalse(paid.json()['reconciled'])
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'CANCELLATION_CONFLICT')
        self.assertEqual(self.item()['withdrawal_state'], 'REVIEW')
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'CANCELED')
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 1)
        self.state.billing_gateway.confirm(self.gateway)
        reconciled = self.client.post(f'/billing/charges/{self.gateway}/reconcile',
            headers={**with_step_up(OWNER), **unique_idem()})
        self.assertEqual(reconciled.status_code, 200)
        self.assertFalse(reconciled.json()['reconciled'])

    def test_restoring_a_withdrawn_invoice_keeps_its_debt_in_review(self):
        self.assertEqual(self.withdraw().status_code, 200)
        restored = self.client.post('/webhooks/asaas', headers={'asaas-access-token': 'test-webhook-secret'},
            json={'id': 'restored-withdrawal', 'event': 'PAYMENT_RESTORED',
                  'payment': {'id': self.gateway, 'status': 'PENDING', 'value': str(self.invoice.amount)}})
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(self.item()['withdrawal_state'], 'REVIEW')
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')

    def test_auth_review_context_and_paid_provider_reject_before_any_delete(self):
        headers = {**with_step_up(OWNER), **unique_idem()}
        with patch.object(self.state.billing_gateway, 'void_charge', side_effect=AssertionError('No DELETE')):
            self.assertEqual(self.withdraw(headers={**with_step_up(OTHER_OWNER), **unique_idem()}).status_code, 404)
            self.assertEqual(self.withdraw(body={'fingerprint': self.fingerprint, 'accept': 'true'}).status_code, 422)
            self.assertEqual(self.withdraw(body={'fingerprint': '0' * 64, 'accept': True}).status_code, 409)
            self.assertEqual(self.withdraw(body={'fingerprint': self.fingerprint, 'accept': False}).status_code, 422)
            self.state.invalidate_step_up_for_session('bearer:demo-owner-token')
            self.assertEqual(self.withdraw(headers={**OWNER, **unique_idem()}).status_code, 403)
        self.state.billing_gateway.confirm(self.gateway)
        self.assertEqual(self.withdraw(headers=headers).status_code, 503)
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')

    def test_readback_requires_explicit_deleted_matching_value_environment_and_unpaid_status(self):
        base = self.state.billing_gateway.inspect_charge(self.gateway, charge_command(self.invoice))
        for overrides in ({'deleted': None}, {'deleted': 1}, {'deleted': True, 'observed_amount': Decimal('0')},
                          {'deleted': True, 'provider': 'OTHER'}, {'deleted': True, 'status': GatewayChargeStatus.CONFIRMED},
                          {'deleted': True, 'source_status': 'UNKNOWN'}):
            with self.subTest(overrides=overrides):
                bad = replace(base, **overrides)
                with patch.object(self.state.billing_gateway, 'void_charge', return_value=bad):
                    with patch.object(self.state.billing_gateway, 'inspect_charge', return_value=bad):
                        self.assertEqual(self.withdraw().status_code, 503)
                self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-void-result:' + self.invoice.billing_id))
                self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')

    def test_failure_committing_local_proof_recovers_by_get_without_repeating_external_delete(self):
        original = self.state.idempotency.execute
        def execute(tenant, key, operation):
            if key == 'billing-void-result:' + self.invoice.billing_id:
                def failing():
                    operation()
                    raise RuntimeError('proof transaction failed')
                return original(tenant, key, failing)
            return original(tenant, key, operation)
        headers = {**with_step_up(OWNER), **unique_idem()}
        with patch.object(self.state.idempotency, 'execute', side_effect=execute):
            with self.assertRaisesRegex(RuntimeError, 'proof transaction failed'):
                self.withdraw(headers=headers)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-void-result:' + self.invoice.billing_id))
        self.assertFalse(any(event.action == 'BILLING_UNPAID_RENEWAL_WITHDRAWAL_CONFIRMED'
                             for event in self.state.audit.list_for_tenant('demo-tenant')))
        with patch.object(self.state.billing_gateway, 'void_charge', side_effect=AssertionError('No repeat DELETE')):
            recovered = self.withdraw(headers=headers)
        self.assertEqual(recovered.status_code, 200, recovered.text)
