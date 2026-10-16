"""One external invoice across consent, checkout, concurrency and restart."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from api.billing_renewal import process_renewal_invoice
from campaia_core.billing_settlement import dispatch_frozen_charge
from tests_api.test_anniversary_lifecycle import clock
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, FINANCE, VIEWER, with_step_up, unique_idem


class BillingRenewalTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.gateway = self.charge()
        self.assertEqual(self.payment(self.gateway).status_code, 200)
        self.end = self.state.subscriptions['demo-tenant'].paid_cycle_schedule.bounds(0)[1]

    def quote(self, client=None):
        r = (client or self.client).get('/billing/renewal', headers=OWNER)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def consent_renewal(self, enabled=True, client=None, headers=None, **changes):
        q = self.quote(client)
        return (client or self.client).put('/billing/renewal',
            headers=headers or {**with_step_up(OWNER), **unique_idem()},
            json={'fingerprint': q['fingerprint'], 'enabled': enabled, **changes})

    def run_job(self, state=None, execute=True, enabled=True):
        return process_renewal_invoice(state or self.state, 'demo-tenant',
                                      execute=execute, dispatch_enabled=enabled)

    def peer(self):
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        return other

    def test_dry_run_is_read_only_and_execution_requires_prior_org_consent_and_dispatch_flag(self):
        with clock(self.end):
            with patch.object(self.state.billing_gateway, 'dispatch_frozen_charge', side_effect=AssertionError('No POST')):
                self.assertEqual(self.run_job()['state'], 'CONSENT_REQUIRED')
                self.assertEqual(self.consent_renewal().status_code, 200)
                with patch.object(self.state.billing_gateway, 'recover_charge', side_effect=AssertionError('No GET')):
                    self.assertEqual(self.run_job(execute=False)['state'], 'DRY_RUN')
                    self.assertEqual(self.run_job(enabled=False)['state'], 'DISABLED')
                identity = self.state.subscriptions['demo-tenant'].paid_cycle_schedule.obligation_id('demo-tenant', 1)
                self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-obligation:' + identity))
                self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-dispatch:' + identity))

    def test_anniversary_invoice_closes_delivered_extra_without_granting_a_new_period_until_payment(self):
        self.assertEqual(self.consent(cap='5.00').status_code, 200)
        cycle = self.usage().json()['cycle']['id']
        for i in range(3):
            self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=cycle,
                operation_id='delivered-' + str(i), action='strategy', at=datetime.now(timezone.utc))
            self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id='delivered-' + str(i),
                kind='SETTLE', reference='output-' + str(i), at=datetime.now(timezone.utc))
        self.assertEqual(self.consent_renewal().status_code, 200)
        self.assertEqual(self.run_job()['state'], 'NOT_DUE')
        with clock(self.end):
            report = self.run_job()
            self.assertEqual(report['state'], 'REGISTERED', report)
            self.assertEqual(Decimal(report['amount']), Decimal('6.00'))
            invoice = self.state.charges[report['gateway_charge_id']]
            self.assertEqual(len(invoice.line_items), 2)
            self.assertEqual(self.state.subscriptions['demo-tenant'].paid_cycle_schedule.paid_through_index, 0)
            self.assertEqual(self.usage().json()['balance']['consumed_credits'], 15)
            self.assertEqual(self.payment(report['gateway_charge_id'], 'anniversary-paid').status_code, 200)
            self.assertEqual(self.usage().json()['balance']['included_credits'], 10)
            self.assertEqual(self.state.subscriptions['demo-tenant'].paid_cycle_schedule.paid_through_index, 1)

    def test_two_workers_and_manual_checkout_share_one_dispatch_fence_and_invoice(self):
        self.assertEqual(self.consent_renewal().status_code, 200)
        other = self.peer()
        with clock(self.end):
            original = dispatch_frozen_charge
            def send(charge, gateway):
                self.assertFalse(self.state.db.in_transaction)
                self.assertIsNotNone(other.app.state.campaia.idempotency.get('demo-tenant', 'billing-dispatch:' + charge.billing_id))
                return original(charge, gateway)
            with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=send) as dispatch:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    reports = list(pool.map(lambda state: self.run_job(state),
                        [self.state, other.app.state.campaia]))
                self.assertTrue(all(r['state'] in {'REGISTERED', 'REVIEW_REQUIRED'} for r in reports), reports)
                recovered = self.run_job(other.app.state.campaia)
            self.assertEqual(recovered['state'], 'REGISTERED', recovered)
            self.assertEqual(dispatch.call_count, 1)
            with patch('api.routes_billing.dispatch_frozen_charge', side_effect=AssertionError('No checkout duplicate')):
                manual = self.client.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()},
                    json={'competence': 'browser'})
            self.assertEqual(manual.status_code, 202, manual.text)
            self.assertEqual(manual.json()['gateway_charge_id'], recovered['gateway_charge_id'])
        self.assertEqual(len(self.state.charges), 2)
        self.assertTrue(any(e.actor_kind == 'SYSTEM' and e.action == 'BILLING_DISPATCH_CLAIMED'
            for e in self.state.audit.list_for_tenant('demo-tenant')))

    def test_lost_response_restart_and_revocation_only_recover_with_get_even_with_new_dispatch_disabled(self):
        self.assertEqual(self.consent_renewal().status_code, 200)
        with clock(self.end):
            def lost(charge, gateway):
                dispatch_frozen_charge(charge, gateway)
                raise TimeoutError('lost after POST')
            with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=lost) as send:
                self.assertEqual(self.run_job()['code'], 'BILLING_DISPATCH_PENDING')
            self.assertEqual(send.call_count, 1)
            other = self.peer()
            self.assertEqual(self.consent_renewal(False, client=other).status_code, 200)
            with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=AssertionError('No retry POST')):
                recovered = self.run_job(other.app.state.campaia, enabled=False)
            self.assertEqual(recovered['state'], 'REGISTERED', recovered)
            self.assertEqual(self.quote(other)['enabled'], False)
            self.assertEqual(len(self.state.charges), 2)

    def test_unknown_absence_never_resets_fence_or_posts_again(self):
        self.assertEqual(self.consent_renewal().status_code, 200)
        with clock(self.end):
            with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=TimeoutError('unknown')) as send:
                first = self.run_job()
                again = self.run_job(self.peer().app.state.campaia)
            self.assertEqual(first['code'], 'BILLING_DISPATCH_PENDING')
            self.assertEqual(again['code'], 'BILLING_DISPATCH_PENDING')
            self.assertEqual(send.call_count, 1)
            self.assertEqual(len(self.state.charges), 1)

    def test_revocation_after_freeze_prevents_the_first_dispatch(self):
        self.assertEqual(self.consent_renewal().status_code, 200)
        other = self.peer()
        original = self.state.idempotency.execute
        def execute(tenant, key, operation):
            result = original(tenant, key, operation)
            if key.startswith('billing-request:billing_renewal:'):
                self.assertEqual(self.consent_renewal(False, client=other).status_code, 200)
            return result
        with clock(self.end):
            with patch.object(self.state.idempotency, 'execute', side_effect=execute):
                with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=AssertionError('No revoked POST')):
                    report = self.run_job()
        self.assertEqual(report['code'], 'BILLING_RENEWAL_REJECTED', report)
        identity = self.state.subscriptions['demo-tenant'].paid_cycle_schedule.obligation_id('demo-tenant', 1)
        self.assertIsNotNone(self.state.idempotency.get('demo-tenant', 'billing-obligation:' + identity))
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-dispatch:' + identity))

    def test_cancellation_after_freeze_prevents_dispatch_and_does_not_void_an_existing_invoice(self):
        self.assertEqual(self.consent_renewal().status_code, 200)
        other = self.peer()
        original = self.state.idempotency.execute
        def execute(tenant, key, operation):
            result = original(tenant, key, operation)
            if key.startswith('billing-request:billing_renewal:'):
                canceled = other.post('/billing/subscription/cancel', headers={**with_step_up(OWNER), **unique_idem()},
                    json={'immediate': True})
                self.assertEqual(canceled.status_code, 200, canceled.text)
            return result
        with clock(self.end):
            with patch.object(self.state.idempotency, 'execute', side_effect=execute):
                with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=AssertionError('No canceled POST')):
                    report = self.run_job()
        self.assertEqual(report['code'], 'BILLING_RENEWAL_REJECTED', report)
        self.assertEqual(len(self.state.charges), 1)

    def test_pending_delivery_blocks_invoice_until_known_failure_is_released(self):
        self.assertEqual(self.consent_renewal().status_code, 200)
        cycle = self.usage().json()['cycle']['id']
        self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=cycle,
            operation_id='pending', action='strategy', at=datetime.now(timezone.utc))
        with clock(self.end):
            with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=AssertionError('No estimated usage')):
                self.assertEqual(self.run_job()['state'], 'REVIEW_REQUIRED')
            self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id='pending', kind='RELEASE',
                reference='known-failure', at=self.end)
            self.assertEqual(self.run_job()['state'], 'REGISTERED')

    def test_plan_and_gateway_drift_require_new_authorization_and_new_lifecycle_does_not_inherit_it(self):
        self.assertEqual(self.consent_renewal().status_code, 200)
        old = self.state.subscriptions['demo-tenant']
        self.state.subscriptions['demo-tenant'] = replace(old, plan=replace(old.plan, monthly_price=Decimal('99.00')))
        self.assertFalse(self.quote()['valid'])
        with clock(self.end):
            self.assertEqual(self.run_job()['state'], 'CONSENT_REQUIRED')
        self.state.subscriptions['demo-tenant'] = old
        self.state.billing_gateway.provider = 'CHANGED'
        self.assertFalse(self.quote()['valid'])
        self.state.billing_gateway.provider = 'SIMULATOR'
        self.assertEqual(self.client.post('/billing/subscription/cancel',
            headers={**with_step_up(OWNER), **unique_idem()}, json={'immediate': True}).status_code, 200)
        self.assertEqual(self.client.post('/billing/subscription/reactivate',
            headers={**with_step_up(OWNER), **unique_idem()}).status_code, 200)
        self.assertFalse(self.quote()['enabled'])
        self.assertEqual(self.run_job()['state'], 'UNAVAILABLE')

    def test_auth_tamper_recent_auth_and_idempotency_are_bound_to_the_actor_and_body(self):
        q = self.quote()
        self.assertEqual(self.client.get('/billing/renewal', headers=OTHER_OWNER).status_code, 404)
        self.assertEqual(self.client.put('/billing/renewal', headers={**with_step_up(VIEWER), **unique_idem()},
            json={'enabled': True, 'fingerprint': q['fingerprint']}).status_code, 403)
        for changes in ({'enabled': 'true'}, {'tenant_id': 'other'}, {'fingerprint': '0' * 64}):
            self.assertIn(self.consent_renewal(**changes).status_code, {409, 422})
        headers = {**with_step_up(OWNER), **unique_idem()}
        first = self.consent_renewal(headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.consent_renewal(headers=headers).json(), first.json())
        self.assertEqual(self.consent_renewal(False, headers=headers).status_code, 409)
        foreign = {**with_step_up(FINANCE), 'Idempotency-Key': headers['Idempotency-Key']}
        self.assertEqual(self.consent_renewal(headers=foreign).status_code, 409)
        self.state.invalidate_step_up_for_session('bearer:demo-owner-token')
        self.assertEqual(self.consent_renewal(headers={**OWNER, **unique_idem()}).status_code, 403)

    def test_consent_failure_rolls_back_and_a_failed_dispatch_claim_never_reaches_gateway(self):
        original = self.state.audit.append
        def fail(**event):
            original(**event)
            if event['action'] in {'BILLING_RENEWAL_CONSENT_CHANGED', 'BILLING_DISPATCH_CLAIMED'}:
                raise RuntimeError('injected renewal commit')
        with patch.object(self.state.audit, 'append', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'injected renewal commit'):
                self.consent_renewal()
        self.assertFalse(self.quote()['enabled'])
        self.assertEqual(self.consent_renewal().status_code, 200)
        with clock(self.end):
            with patch.object(self.state.audit, 'append', side_effect=fail):
                with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=AssertionError('No uncommitted POST')):
                    with self.assertRaisesRegex(RuntimeError, 'injected renewal commit'):
                        self.run_job()
        identity = self.state.subscriptions['demo-tenant'].paid_cycle_schedule.obligation_id('demo-tenant', 1)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-dispatch:' + identity))


class UnpaidRenewalTests(BillingCreditHarness, unittest.TestCase):
    def test_trial_and_initial_pending_payment_never_turn_into_an_automatic_first_charge(self):
        self.setup_subscription(trial=True)
        q = self.client.get('/billing/renewal', headers=OWNER).json()
        self.assertFalse(q['can_enable'])
        r = self.client.put('/billing/renewal', headers={**with_step_up(OWNER), **unique_idem()},
            json={'enabled': True, 'fingerprint': q['fingerprint']})
        self.assertEqual(r.status_code, 409)
        with patch.object(self.state.billing_gateway, 'create_charge', side_effect=AssertionError('No auto-conversion')):
            self.assertEqual(process_renewal_invoice(self.state, 'demo-tenant', execute=True, dispatch_enabled=True)['state'], 'UNAVAILABLE')
        self.assertEqual(len(self.state.charges), 0)
