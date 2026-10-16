"""Provider-confirmed refunds close only their accepted commercial scope."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from api.billing_guarantee_resolution import finalize_guarantee, adjustment_key
from api.billing_guarantee_scope import scope_key
from api.billing_refund_worker import process_guarantee_refunds
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, with_step_up, unique_idem


class GuaranteeResolutionTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.gateway = self.charge()
        self.assertEqual(self.payment(self.gateway).status_code, 200)
        self.state.billing_gateway.confirm(self.gateway)
        self.state.billing_gateway.minimum_charge_amount = Decimal('5.00')
        self.cycle = self.usage().json()['cycle']['id']

    def action(self, name, body=None):
        return self.client.post('/billing/subscription/' + name,
            headers={**with_step_up(OWNER), **unique_idem()}, json=body)

    def extra(self):
        self.assertEqual(self.consent(cap='5.00').status_code, 200)
        for i in range(3):
            self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=self.cycle,
                operation_id='used-' + str(i), action='strategy', at=datetime.now(timezone.utc))
            self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id='used-' + str(i),
                kind='SETTLE', reference='delivered-' + str(i), at=datetime.now(timezone.utc))

    def final_invoice(self):
        q = self.client.get('/billing/closure', headers=OWNER).json()
        r = self.client.post('/billing/closure', headers={**with_step_up(OWNER), **unique_idem()},
            json={'fingerprint': q['fingerprint'], 'accept': True})
        self.assertEqual(r.status_code, 200, r.text)
        return next(gid for gid, c in self.state.charges.items_for_tenant('demo-tenant')
                    if c.purpose.value == 'FINAL_USAGE')

    def request(self):
        q = self.client.get('/billing/guarantee', headers=OWNER).json()
        r = self.client.post('/billing/guarantee', headers={**with_step_up(OWNER), **unique_idem()},
            json={'fingerprint': q['fingerprint'], 'accept': True})
        self.assertEqual(r.status_code, 200, r.text)
        self.case = r.json()
        return self.case

    def finish_refunds(self, gateways):
        report = process_guarantee_refunds(self.state, 'demo-tenant', execute=True)
        self.assertEqual(report['state'], 'PROCESSING', report)
        for gateway in gateways:
            self.state.billing_gateway.complete_refund(gateway, tenant_id='demo-tenant')
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No second refund')):
            report = process_guarantee_refunds(self.state, 'demo-tenant', execute=True)
        self.assertTrue(all(row['state'] == 'REFUND_DONE_ADJUSTMENT_PENDING' for row in report['items']), report)

    def finalize(self, state=None, execute=True):
        return finalize_guarantee(state or self.state, 'demo-tenant', execute=execute)

    def quote(self):
        return self.client.get('/billing/guarantee', headers=OWNER).json()

    def test_pending_is_not_proof_and_dry_run_cannot_close_or_emit_a_fiscal_adjustment(self):
        self.request()
        self.assertEqual(self.finalize()['state'], 'REFUND_PROOF_REQUIRED')
        process_guarantee_refunds(self.state, 'demo-tenant', execute=True)
        self.assertEqual(self.finalize()['state'], 'REFUND_PROOF_REQUIRED')
        self.state.billing_gateway.complete_refund(self.gateway, tenant_id='demo-tenant')
        process_guarantee_refunds(self.state, 'demo-tenant', execute=True)
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No money')):
            self.assertEqual(self.finalize(execute=False)['state'], 'DRY_RUN')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', adjustment_key(self.state.charges[self.gateway].billing_id)))
        self.assertEqual(self.quote()['state'], 'PROCESSING')

    def test_paid_final_extra_is_not_billed_again_and_a_new_contract_is_not_in_the_old_request(self):
        self.extra()
        self.assertEqual(self.action('cancel', {'immediate': True}).status_code, 200)
        final = self.final_invoice()
        self.assertEqual(self.payment(final, 'final-paid').status_code, 200)
        self.state.billing_gateway.confirm(final)
        self.request()
        first_paid = self.state.idempotency.get('demo-tenant', 'billing-first-paid').result
        self.finish_refunds([self.gateway, final])
        result = self.finalize()
        self.assertEqual(result['state'], 'FINANCIALLY_RESOLVED', result)
        self.assertEqual(result['fiscal_adjustment_state'], 'PENDING_CAPABILITY')
        self.assertEqual(self.quote()['state'], 'FINANCIALLY_RESOLVED')
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'GUARANTEE_CLOSED')
        self.assertEqual(self.state.credit_ledger.balance('demo-tenant', self.cycle).consumed_credits, 15)
        with patch.object(self.state.billing_gateway, 'create_charge', side_effect=AssertionError('No rebill')):
            self.assertEqual(self.action('reactivate').status_code, 200)
        self.assertFalse(self.usage().json()['access_active'])
        next_gateway = self.charge()
        self.assertNotEqual(next_gateway, self.gateway)
        self.assertEqual(self.state.charges[next_gateway].amount, Decimal('1.00'))
        self.assertEqual(self.payment(next_gateway, 'new-contract-paid').status_code, 200)
        self.assertTrue(self.usage().json()['access_active'])
        self.assertFalse(self.usage().json()['cycle']['trial'])
        self.assertEqual(self.state.idempotency.get('demo-tenant', 'billing-first-paid').result, first_paid)
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No new-contract refund')):
            report = process_guarantee_refunds(self.state, 'demo-tenant', execute=True)
        self.assertEqual(report['state'], 'FINANCIALLY_RESOLVED', report)
        self.assertIn({'billing_id': self.state.charges[next_gateway].billing_id,
                       'state': 'OUTSIDE_ACCEPTED_REQUEST'}, report['excluded'])

    def test_unpaid_delivered_extra_is_preserved_and_a_later_final_checkout_has_its_own_consent(self):
        self.extra(); self.request()
        self.finish_refunds([self.gateway])
        self.assertEqual(self.finalize()['state'], 'FINANCIALLY_RESOLVED')
        q = self.client.get('/billing/closure', headers=OWNER).json()
        self.assertEqual(q['state'], 'INVOICE_REQUIRED')
        self.assertEqual(q['amount'], '5.00')
        self.assertEqual(self.action('reactivate').status_code, 409)
        final = self.final_invoice()
        self.assertEqual(self.payment(final, 'later-final-paid').status_code, 200)
        self.assertEqual(self.quote()['state'], 'FINANCIALLY_RESOLVED')
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'SETTLED')
        self.assertEqual(self.action('reactivate').status_code, 200)

    def test_late_payment_on_an_existing_invoice_reopens_coverage_without_repeating_an_old_refund(self):
        self.extra()
        self.assertEqual(self.action('cancel', {'immediate': True}).status_code, 200)
        final = self.final_invoice()
        self.request()
        scope = self.state.idempotency.get('demo-tenant', scope_key(self.case['request_id'])).result
        self.assertIn(self.state.charges[final].billing_id, scope['billing_ids'])
        self.finish_refunds([self.gateway])
        self.assertEqual(self.finalize()['state'], 'FINANCIALLY_RESOLVED')
        self.assertEqual(self.action('reactivate').status_code, 409)
        self.assertEqual(self.payment(final, 'late-original-final').status_code, 200)
        self.state.billing_gateway.confirm(final)
        self.assertEqual(self.quote()['state'], 'PROCESSING')
        original = self.state.billing_gateway.refund_charge
        def only_new(gid, *args):
            self.assertEqual(gid, final)
            return original(gid, *args)
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=only_new) as send:
            self.finish_refunds([final])
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.finalize()['state'], 'FINANCIALLY_RESOLVED')
        self.assertEqual(self.client.get('/billing/closure', headers=OWNER).json()['state'], 'GUARANTEE_CLOSED')

    def test_stale_receipt_cannot_erase_adjustment_but_gross_conflict_and_chargeback_require_review(self):
        self.request(); self.finish_refunds([self.gateway]); self.finalize()
        self.assertEqual(self.payment(self.gateway, 'stale-confirmation').status_code, 200)
        self.assertEqual(self.quote()['state'], 'FINANCIALLY_RESOLVED')
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'GUARANTEE_REFUNDED')
        original = self.state.billing_gateway.inspect_charge
        from dataclasses import replace
        with patch.object(self.state.billing_gateway, 'inspect_charge',
                          side_effect=lambda *args: replace(original(*args), observed_amount=Decimal('2.00'))):
            r = self.client.post('/billing/charges/' + self.gateway + '/reconcile',
                headers={**with_step_up(OWNER), **unique_idem()})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotEqual(self.quote()['state'], 'FINANCIALLY_RESOLVED')
        process_guarantee_refunds(self.state, 'demo-tenant', execute=True)
        self.assertEqual(self.quote()['state'], 'FINANCIALLY_RESOLVED')
        with patch.object(self.state.billing_gateway, 'inspect_charge',
                          side_effect=lambda *args: replace(original(*args), chargeback_status='REQUESTED')):
            self.client.post('/billing/charges/' + self.gateway + '/reconcile',
                headers={**with_step_up(OWNER), **unique_idem()})
        self.assertNotEqual(self.quote()['state'], 'FINANCIALLY_RESOLVED')
        self.assertEqual(self.finalize()['state'], 'REFUND_PROOF_REQUIRED')
        process_guarantee_refunds(self.state, 'demo-tenant', execute=True)
        self.assertEqual(self.state.charges[self.gateway].gateway_chargeback_status, 'REQUESTED')
        self.assertNotEqual(self.quote()['state'], 'FINANCIALLY_RESOLVED')

    def test_two_workers_commit_one_adjustment_and_replay_after_restart(self):
        self.request(); self.finish_refunds([self.gateway])
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda s: self.finalize(s), [self.state, other.app.state.campaia]))
        self.assertTrue(all(r['state'] == 'FINANCIALLY_RESOLVED' for r in results), results)
        self.assertEqual(results[0], results[1])
        self.assertEqual(sum(e.action == 'BILLING_GUARANTEE_FINANCIALLY_RESOLVED'
            for e in self.state.audit.list_for_tenant('demo-tenant')), 1)
        self.assertEqual(other.get('/billing/guarantee', headers=OWNER).json()['state'], 'FINANCIALLY_RESOLVED')
        self.assertEqual(other.get('/billing/guarantee', headers=OTHER_OWNER).status_code, 404)
        self.assertEqual(finalize_guarantee(self.state, 'other-tenant', execute=True)['state'], 'UNAVAILABLE')

    def test_failed_financial_commit_rolls_back_adjustments_flags_and_audit(self):
        self.request(); self.finish_refunds([self.gateway])
        bill = self.state.charges[self.gateway]
        original = self.state.audit.append
        def fail(**kwargs):
            original(**kwargs)
            if kwargs['action'] == 'BILLING_GUARANTEE_FINANCIALLY_RESOLVED':
                raise RuntimeError('injected financial commit')
        with patch.object(self.state.audit, 'append', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'injected financial commit'):
                self.finalize()
        self.assertIsNone(self.state.idempotency.get('demo-tenant', adjustment_key(bill.billing_id)))
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, bill.payment_reconciliation_state)
        self.assertEqual(self.quote()['state'], 'PROCESSING')
        self.assertEqual(self.finalize()['state'], 'FINANCIALLY_RESOLVED')

    def test_legacy_scope_requires_a_proven_closed_contract_and_tampered_request_is_not_authority(self):
        self.request()
        original = self.state.idempotency.get
        def missing(tenant, key):
            return None if key == scope_key(self.case['request_id']) else original(tenant, key)
        from api.billing_guarantee_scope import ensure_scope
        with patch.object(self.state.idempotency, 'get', side_effect=missing):
            scope = ensure_scope(self.state, 'demo-tenant', self.case)
        self.assertIn(self.state.charges[self.gateway].billing_id, scope['billing_ids'])
        bad = {**self.case, 'paid_amount': '999'}
        with self.assertRaisesRegex(Exception, 'conferência'):
            ensure_scope(self.state, 'another-tenant', bad)


class UnpaidContractResolutionTests(BillingCreditHarness, unittest.TestCase):
    def test_initial_unpaid_invoice_must_be_withdrawn_before_a_new_contract(self):
        self.setup_subscription()
        gateway = self.charge()
        def action(name, body=None):
            return self.client.post('/billing/subscription/' + name,
                headers={**with_step_up(OWNER), **unique_idem()}, json=body)
        self.assertEqual(action('cancel', {'immediate': True}).status_code, 200)
        self.assertEqual(action('reactivate').status_code, 409)
        row = self.client.get('/billing/charges', headers=OWNER).json()['items'][0]
        self.assertIsNotNone(row['withdrawal_fingerprint'])
        withdrawn = self.client.post('/billing/charges/' + gateway + '/withdraw',
            headers={**with_step_up(OWNER), **unique_idem()},
            json={'fingerprint': row['withdrawal_fingerprint'], 'accept': True})
        self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertEqual(action('reactivate').status_code, 200)
        self.assertEqual(self.state.charges[gateway].status.value, 'OPEN')
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 0)

    def test_uncertain_initial_dispatch_blocks_reactivation_without_a_second_invoice(self):
        self.setup_subscription()
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=TimeoutError('unknown')) as send:
            r = self.client.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()},
                json={'competence': 'browser'})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.client.post('/billing/subscription/cancel',
            headers={**with_step_up(OWNER), **unique_idem()}, json={'immediate': True}).status_code, 200)
        with patch.object(self.state.billing_gateway, 'create_charge', side_effect=AssertionError('No new invoice')):
            r = self.client.post('/billing/subscription/reactivate',
                headers={**with_step_up(OWNER), **unique_idem()})
        self.assertEqual(r.status_code, 409)
