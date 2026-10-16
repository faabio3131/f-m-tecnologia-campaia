from contextlib import contextmanager, ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from campaia_core.subscription import ChargeStatus
from campaia_core.payment_gateway import ChargeResult, GatewayMode, GatewayChargeStatus
from campaia_core.states import CampaignState
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, with_step_up, unique_idem, DEFAULT_BRIEF


@contextmanager
def clock(at):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return at
    with ExitStack() as stack:
        for module in ('api.routes_billing', 'api.deps', 'api.billing_credits',
                       'campaia_core.subscription', 'api.commercial_limits', 'api.metered_execution', 'api.billing_renewal'):
            stack.enter_context(patch(module + '.datetime', Clock))
        yield


class AnniversaryLifecycleTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.initial_gateway = self.charge()
        self.assertEqual(self.payment(self.initial_gateway).status_code, 200)
        self.initial = self.state.subscriptions['demo-tenant']
        self.end = self.initial.paid_cycle_schedule.bounds(0)[1]

    def action(self, name, body=None):
        return self.client.post('/billing/subscription/' + name,
            headers={**with_step_up(OWNER), **unique_idem()}, json=body)

    def change(self, plan_id):
        plans = self.client.get('/billing/plans', headers=OWNER).json()['items']
        fingerprint = next(p['fingerprint'] for p in plans if p['plan_id'] == plan_id)
        return self.action('change-plan', {'target_plan_id': plan_id, 'expected_plan_fingerprint': fingerprint})

    def test_upgrade_is_scheduled_without_invoice_then_payment_activates_correct_cycle(self):
        response = self.change('exemplo-pro')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['plan_id'], 'exemplo-essencial')
        self.assertEqual(response.json()['pending_plan_id'], 'exemplo-pro')
        self.assertIsNotNone(response.json()['pending_plan_effective_at'])
        self.assertEqual(len(self.state.charges.items_for_tenant('demo-tenant')), 1)
        early = self.client.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()}, json={'competence': 'browser'})
        self.assertEqual(early.status_code, 422)
        with clock(self.end):
            gateway = self.charge()
            invoice = self.state.charges[gateway]
            self.assertEqual(invoice.amount, Decimal('2.00'))
            self.assertEqual(invoice.purpose.value, 'PLAN_CHANGE')
            self.assertEqual(invoice.commercial_plan.plan_id, 'exemplo-pro')
            self.assertEqual(self.state.subscriptions['demo-tenant'].plan.plan_id, 'exemplo-essencial')
            self.assertEqual(self.payment(gateway, 'upgrade-payment').status_code, 200)
            self.assertEqual(self.usage().json()['balance']['included_credits'], 20)
        sub = self.state.subscriptions['demo-tenant']
        self.assertEqual(sub.plan.plan_id, 'exemplo-pro')
        self.assertEqual(sub.paid_cycle_schedule.anchor_at, self.initial.paid_cycle_schedule.anchor_at)

    def test_downgrade_checks_occupancy_and_future_cap_can_be_withdrawn(self):
        self.assertEqual(self.change('exemplo-pro').status_code, 200)
        with clock(self.end):
            self.assertEqual(self.payment(self.charge(), 'upgrade-payment').status_code, 200)
            ids = []
            for _ in range(2):
                created = self.client.post('/briefs', headers={**OWNER, **unique_idem()}, json=DEFAULT_BRIEF)
                self.assertEqual(created.status_code, 202, created.text)
                ids.append(created.json()['id'])
                self.state.campaigns.get('demo-tenant', ids[-1]).campaign.state = CampaignState.ACTIVE
            blocked = self.change('exemplo-essencial')
            self.assertEqual(blocked.status_code, 409, blocked.text)
            paused = self.client.post(f'/campaigns/{ids[0]}/pause', headers={**OWNER, **unique_idem()})
            self.assertEqual(paused.status_code, 202, paused.text)
            self.assertEqual(self.change('exemplo-essencial').status_code, 200)
            blocked_resume = self.client.post(f'/campaigns/{ids[0]}/resume', headers={**with_step_up(OWNER), **unique_idem()})
            self.assertEqual(blocked_resume.status_code, 409)
            self.assertEqual(self.action('undo-plan').status_code, 200)
            resumed = self.client.post(f'/campaigns/{ids[0]}/resume', headers={**with_step_up(OWNER), **unique_idem()})
            self.assertEqual(resumed.status_code, 202, resumed.text)

    def test_cancel_renewal_keeps_access_and_removing_schedule_creates_no_new_invoice(self):
        canceled = self.action('cancel')
        self.assertEqual(canceled.status_code, 200, canceled.text)
        self.assertEqual(canceled.json()['status'], 'ACTIVE')
        self.assertTrue(canceled.json()['entitlement_access_active'])
        self.assertIsNotNone(canceled.json()['cancel_at_period_end'])
        kept = self.action('reactivate')
        self.assertEqual(kept.status_code, 200, kept.text)
        self.assertIsNone(kept.json()['cancel_at_period_end'])
        self.assertEqual(len(self.state.charges.items_for_tenant('demo-tenant')), 1)
        self.assertEqual(self.state.subscriptions['demo-tenant'].paid_cycle_schedule, self.initial.paid_cycle_schedule)
        self.assertEqual(self.action('cancel').status_code, 200)
        with clock(self.end):
            ended = self.client.get('/billing/subscription', headers=OWNER)
            self.assertEqual(ended.json()['status'], 'CANCELED')
            self.assertFalse(ended.json()['entitlement_access_active'])
            rejected = self.client.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()}, json={'competence': 'browser'})
            self.assertEqual(rejected.status_code, 422)

    def test_immediate_cancel_reactivation_has_new_invoice_and_old_payment_cannot_activate_it(self):
        canceled = self.action('cancel', {'immediate': True})
        self.assertEqual(canceled.json()['status'], 'CANCELED')
        usage = self.usage().json()
        self.assertEqual(usage['availability'], 'AVAILABLE')
        self.assertFalse(usage['access_active'])
        self.assertFalse(usage['can_authorize_extras'])
        pending = self.action('reactivate')
        self.assertEqual(pending.status_code, 200, pending.text)
        self.assertEqual(pending.json()['status'], 'PENDING_PAYMENT')
        self.assertEqual(self.payment(self.initial_gateway, 'old-payment-after-reactivation').status_code, 200)
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'PENDING_PAYMENT')
        gateway = self.charge()
        self.assertNotEqual(gateway, self.initial_gateway)
        invoice = self.state.charges[gateway]
        self.assertEqual(invoice.purpose.value, 'REACTIVATION')
        self.assertNotEqual(invoice.commercial_lifecycle_id, self.initial.paid_cycle_schedule.lifecycle_id)
        self.assertEqual(self.payment(gateway, 'new-reactivation-payment').status_code, 200)
        self.assertEqual(self.usage().json()['balance']['included_credits'], 10)

    def test_overdue_debt_blocks_new_lifecycle_and_foreign_debt_does_not(self):
        self.assertEqual(self.action('cancel', {'immediate': True}).status_code, 200)
        debt = replace(self.state.charges[self.initial_gateway], billing_id='prior-debt',
                       gateway_status='OVERDUE', status=ChargeStatus.OPEN)
        self.state.charges['prior-debt'] = debt
        self.assertEqual(self.action('reactivate').status_code, 409)
        del self.state.charges['prior-debt']
        self.state.charges['foreign-debt'] = replace(debt, tenant_id='another-tenant')
        self.assertEqual(self.action('reactivate').status_code, 200)

    def test_plan_snapshot_review_and_external_value_divergence_fail_closed(self):
        changed = self.action('change-plan', {'target_plan_id': 'exemplo-pro', 'expected_plan_fingerprint': '0' * 64})
        self.assertEqual(changed.status_code, 409)
        self.assertIsNone(self.state.subscriptions['demo-tenant'].pending_plan)
        self.assertEqual(self.action('cancel', {'immediate': True}).status_code, 200)
        self.assertEqual(self.action('reactivate').status_code, 200)
        mismatch = ChargeResult('mismatch-id', GatewayChargeStatus.PENDING, 'SIMULATOR', GatewayMode.SIMULATOR,
                                observed_amount=Decimal('999.00'))
        with patch('api.routes_billing.dispatch_frozen_charge', return_value=mismatch):
            response = self.client.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()}, json={'competence': 'ignored'})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIsNone(self.state.charges.get('mismatch-id'))
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'PENDING_PAYMENT')

    def test_frozen_obligation_blocks_plan_withdrawal_even_before_gateway_history_exists(self):
        self.assertEqual(self.change('exemplo-pro').status_code, 200)
        with clock(self.end):
            with patch('api.routes_billing.dispatch_frozen_charge', side_effect=RuntimeError('uncertain dispatch')):
                response = self.client.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()},
                                            json={'competence': 'untrusted'})
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(self.action('undo-plan').status_code, 409)
        self.assertEqual(len(self.state.charges), 1)
        self.assertIsNotNone(self.state.subscriptions['demo-tenant'].pending_plan)
