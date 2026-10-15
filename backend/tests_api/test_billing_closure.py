from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from campaia_core.subscription import ChargePurpose
from campaia_core.billing_settlement import dispatch_frozen_charge
from tests_api.test_anniversary_lifecycle import clock
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, with_step_up, unique_idem


class BillingClosureTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.payment(self.charge())
        self.state.billing_gateway.minimum_charge_amount = Decimal('5.00')
        self.assertEqual(self.consent(cap='20.00').status_code, 200)
        self.cycle = self.usage().json()['cycle']['id']

    def reserve(self, operation, action='strategy', finish=True):
        self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=self.cycle,
            operation_id=operation, action=action, at=datetime.now(timezone.utc))
        if finish:
            self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id=operation,
                kind='SETTLE', reference='delivery:' + operation, at=datetime.now(timezone.utc))

    def excess(self):
        for i in range(3):
            self.reserve(f'operation-{i}')

    def cancel(self):
        response = self.client.post('/billing/subscription/cancel',
            headers={**with_step_up(OWNER), **unique_idem()}, json={'immediate': True})
        self.assertEqual(response.status_code, 200, response.text)

    def quote(self, client=None):
        response = (client or self.client).get('/billing/closure', headers=OWNER)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def close(self, quote=None, headers=None, client=None):
        return (client or self.client).post('/billing/closure',
            headers=headers or {**with_step_up(OWNER), **unique_idem()},
            json={'fingerprint': (quote or self.quote())['fingerprint'], 'accept': True})

    def reactivate(self):
        return self.client.post('/billing/subscription/reactivate', headers={**with_step_up(OWNER), **unique_idem()})

    def test_final_invoice_has_only_delivered_extra_and_payment_never_grants_a_cycle(self):
        self.excess(); self.cancel()
        quote = self.quote()
        self.assertEqual(quote['state'], 'INVOICE_REQUIRED')
        self.assertEqual(quote['amount'], '5.00')
        self.assertEqual(self.reactivate().status_code, 409)
        opened = sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant'))
        closed = self.close(quote)
        self.assertEqual(closed.status_code, 200, closed.text)
        final = next((key, charge) for key, charge in self.state.charges.items_for_tenant('demo-tenant')
                     if charge.purpose is ChargePurpose.FINAL_USAGE)
        self.assertEqual(final[1].amount, Decimal('5.00'))
        self.assertEqual(len(final[1].line_items), 1)
        self.assertNotEqual(final[1].billing_id, self.cycle)
        self.assertEqual(self.reactivate().status_code, 409)
        self.assertEqual(self.payment(final[0], 'final-paid').status_code, 200)
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'CANCELED')
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), opened)
        self.assertEqual(self.quote()['state'], 'SETTLED')
        self.assertEqual(self.reactivate().status_code, 200)
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'PENDING_PAYMENT')

    def test_zero_usage_creates_no_gateway_charge_and_residual_is_absorbed_without_fake_payment(self):
        self.reserve('a'); self.reserve('b'); self.reserve('extra-two', 'audience')
        self.cancel()
        quote = self.quote()
        self.assertEqual(quote['state'], 'ABSORBABLE')
        self.assertEqual(quote['amount'], '2.00')
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=AssertionError('No gateway')):
            result = self.close(quote)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['state'], 'ABSORBED')
        self.assertIsNone(result.json()['invoice'])
        self.assertEqual(len(self.state.charges), 1)
        self.assertEqual(self.state.credit_ledger.balance('demo-tenant', self.cycle).extra_consumed_amount, Decimal('2.00'))
        self.assertEqual(self.reactivate().status_code, 200)

    def test_pending_delivery_blocks_closure_until_explicit_release(self):
        self.reserve('pending', finish=False); self.cancel()
        self.assertEqual(self.quote()['state'], 'PENDING_USAGE')
        self.assertEqual(self.close().status_code, 409)
        self.assertEqual(self.reactivate().status_code, 409)
        self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id='pending', kind='RELEASE',
            reference='known-failure', at=datetime.now(timezone.utc))
        self.assertEqual(self.quote()['state'], 'NO_CHARGE')
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=AssertionError('No gateway')):
            self.assertEqual(self.close().status_code, 200)
        self.assertEqual(len(self.state.charges), 1)

    def test_unknown_minimum_and_existing_renewal_are_reconciliation_gates(self):
        self.excess()
        self.state.billing_gateway.minimum_charge_amount = None
        self.cancel()
        self.assertEqual(self.quote()['state'], 'MINIMUM_UNAVAILABLE')
        self.assertEqual(self.close().status_code, 409)
        self.assertEqual(self.reactivate().status_code, 409)

    def test_usage_already_on_a_renewal_cannot_be_billed_again_at_closure(self):
        self.excess()
        end = self.state.subscriptions['demo-tenant'].paid_cycle_schedule.bounds(0)[1]
        with clock(end):
            self.charge()
            self.cancel()
            self.assertEqual(self.quote()['state'], 'RECONCILIATION_REQUIRED')
            self.assertEqual(self.close().status_code, 409)
        self.assertEqual(len(self.state.charges), 2)
        self.assertFalse(any(c.purpose is ChargePurpose.FINAL_USAGE for _k, c in self.state.charges.items_for_tenant('demo-tenant')))

    def test_two_workers_reuse_one_final_invoice_and_cannot_read_another_tenant(self):
        self.excess(); self.cancel(); quote = self.quote()
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        other.app.state.campaia.billing_gateway.minimum_charge_amount = Decimal('5.00')
        with patch('api.routes_billing.dispatch_frozen_charge', wraps=dispatch_frozen_charge) as dispatched:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda client: self.close(quote, client=client), [self.client, other]))
        self.assertTrue(all(r.status_code == 200 for r in results), [r.text for r in results])
        self.assertEqual(dispatched.call_count, 1)
        self.assertEqual(len(self.state.charges), 2)
        self.assertEqual(self.client.get('/billing/closure', headers=OTHER_OWNER).status_code, 404)

    def test_uncertain_final_invoice_is_not_absorbed_when_gateway_minimum_changes(self):
        self.excess(); self.cancel(); quote = self.quote()
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=RuntimeError('uncertain')) as dispatched:
            self.assertEqual(self.close(quote).status_code, 503)
            self.state.billing_gateway.minimum_charge_amount = Decimal('10.00')
            pending = self.quote()
            self.assertEqual(pending['state'], 'INVOICE_REQUIRED')
            self.assertEqual(self.close(pending).status_code, 503)
        self.assertEqual(dispatched.call_count, 1)
        self.assertEqual(len(self.state.charges), 1)

    def test_closure_requires_accepted_review_and_cannot_rebind_a_completed_request(self):
        self.excess(); self.cancel(); quote = self.quote()
        headers = {**with_step_up(OWNER), **unique_idem()}
        rejected = self.client.post('/billing/closure', headers=headers,
            json={'fingerprint': quote['fingerprint'], 'accept': False})
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(len(self.state.charges), 1)
        accepted = self.close(quote, headers=headers)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(self.close(quote, headers=headers).json(), accepted.json())
        conflict = self.client.post('/billing/closure', headers=headers,
            json={'fingerprint': '0' * 64, 'accept': True})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()['code'], 'IDEMPOTENCY_CONFLICT')
        self.assertEqual(len(self.state.charges), 2)
