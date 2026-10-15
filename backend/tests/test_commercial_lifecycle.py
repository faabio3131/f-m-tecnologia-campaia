from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from campaia_core.billing_cycles import PaidCycleSchedule
from campaia_core.credit_ledger import CreditPolicy
from campaia_core.subscription import (
    Subscription, SubscriptionStatus, PlanDefinition, PlanEntitlements, PlanChangeRule,
    PlanChangeKind, PlanChangeActivation, PlanChangeBillingMode, CancellationMode,
    ReactivationMode, ReactivationBillingMode, ChargePurpose, DunningPolicy, PastDueAccessMode,
    request_plan_change, cancel_subscription, request_reactivation, refresh_trial_status,
    activate_commercial_payment, entitlement_access_is_active, start_trial,
    mark_past_due, past_due_is_in_grace,
)

AT = datetime(2026, 1, 31, 15, tzinfo=timezone.utc)
POLICY = CreditPolicy('test-v1', (('strategy', 5),), 30, 1, 1)


def plans():
    base = PlanDefinition('a', 'Teste A', Decimal('1.00'), Decimal(10), Decimal('1.00'),
        trial_days=7, entitlements=PlanEntitlements(max_users=2, max_active_campaigns=3),
        credit_policy=POLICY, cancellation_mode=CancellationMode.PERIOD_END,
        reactivation_mode=ReactivationMode.PAYMENT_REQUIRED,
        reactivation_billing_mode=ReactivationBillingMode.CURRENT_PLAN_FULL_CYCLE,
        dunning_policy=DunningPolicy(3, PastDueAccessMode.ALLOW_DURING_GRACE),
        plan_changes=(PlanChangeRule('b', PlanChangeKind.UPGRADE, PlanChangeActivation.NEXT_ANNIVERSARY,
                                     PlanChangeBillingMode.TARGET_PLAN_FULL_CYCLE),))
    return base, replace(base, plan_id='b', name='Teste B', monthly_price=Decimal('2.00'),
                         included_credits=Decimal(20), plan_changes=())


def subscription():
    plan, _ = plans()
    schedule = PaidCycleSchedule('first-life')
    schedule = schedule.confirm_payment('tenant', schedule.obligation_id('tenant', 0), 0, AT)
    return Subscription('tenant', 'customer', 'test-document', plan,
                        status=SubscriptionStatus.ACTIVE, activated_at=AT, paid_cycle_schedule=schedule)


class CommercialLifecycleTests(unittest.TestCase):
    def test_late_overdue_notice_never_extends_anniversary_grace(self):
        original = subscription(); due = original.paid_cycle_schedule.bounds(0)[1]
        late = mark_past_due(original, overdue_at=due + timedelta(days=10),
                            billed_plan_id=original.plan.plan_id, billed_purpose=ChargePurpose.REGULAR)
        self.assertEqual(late.past_due_at, due)
        self.assertEqual(late.grace_period_ends_at, due + timedelta(days=3))
        self.assertFalse(entitlement_access_is_active(late, now=due + timedelta(days=10)))
        old_record = replace(late, grace_period_ends_at=due + timedelta(days=30))
        self.assertFalse(past_due_is_in_grace(old_record, now=due + timedelta(days=3)))
        with self.assertRaises(ValueError):
            mark_past_due(original, overdue_at=due - timedelta(seconds=1),
                          billed_plan_id=original.plan.plan_id, billed_purpose=ChargePurpose.REGULAR)

    def test_plan_change_waits_for_date_and_payment(self):
        original = subscription(); target = plans()[1]
        pending = request_plan_change(original, target, now=AT + timedelta(days=1))
        due = original.paid_cycle_schedule.bounds(0)[1]
        self.assertEqual(pending.pending_plan_effective_at, due)
        self.assertEqual(refresh_trial_status(pending, now=due).plan, original.plan)
        schedule = pending.paid_cycle_schedule
        identity = schedule.obligation_id('tenant', 1)
        confirmed = schedule.confirm_payment('tenant', identity, 1, due)
        active = activate_commercial_payment(pending, schedule=confirmed, billed_plan=target,
            billed_index=1, billed_purpose=ChargePurpose.PLAN_CHANGE, billing_id=identity, settled_at=due)
        self.assertEqual(active.plan, target)
        self.assertIsNone(active.pending_plan)
        self.assertEqual(active.activated_at, AT)

    def test_early_paid_change_keeps_current_plan_until_anniversary(self):
        original = subscription(); target = plans()[1]
        pending = request_plan_change(original, target, now=AT + timedelta(days=1))
        schedule = pending.paid_cycle_schedule; identity = schedule.obligation_id('tenant', 1)
        early = AT + timedelta(days=10)
        confirmed = schedule.confirm_payment('tenant', identity, 1, early)
        active = activate_commercial_payment(pending, schedule=confirmed, billed_plan=target,
            billed_index=1, billed_purpose=ChargePurpose.PLAN_CHANGE, billing_id=identity, settled_at=early)
        self.assertEqual(active.plan, original.plan)
        self.assertEqual(refresh_trial_status(active, now=pending.pending_plan_effective_at).plan, target)
        canceled = cancel_subscription(active, now=early)
        self.assertEqual(canceled.cancel_at_period_end, confirmed.bounds(1)[1])
        self.assertIsNotNone(canceled.pending_plan)

    def test_cancel_renewal_keeps_paid_period_and_reactivate_before_end_is_free(self):
        original = subscription(); end = original.paid_cycle_schedule.bounds(0)[1]
        canceled = cancel_subscription(original, now=AT + timedelta(days=1))
        self.assertEqual(canceled.status, SubscriptionStatus.ACTIVE)
        self.assertTrue(entitlement_access_is_active(canceled, now=end - timedelta(seconds=1)))
        self.assertFalse(entitlement_access_is_active(canceled, now=end))
        kept = request_reactivation(canceled, now=AT + timedelta(days=2))
        self.assertIsNone(kept.cancel_at_period_end)
        self.assertEqual(kept.paid_cycle_schedule, original.paid_cycle_schedule)

    def test_after_end_reactivation_has_new_identity_and_never_restarts_trial(self):
        original = replace(subscription(), trial_started_at=AT - timedelta(days=7), trial_ends_at=AT)
        end = original.paid_cycle_schedule.bounds(0)[1]
        closed = refresh_trial_status(cancel_subscription(original, now=AT + timedelta(days=1)), now=end)
        self.assertEqual(closed.status, SubscriptionStatus.CANCELED)
        pending = request_reactivation(closed, now=end, lifecycle_id='second-life')
        self.assertEqual(pending.status, SubscriptionStatus.PENDING_PAYMENT)
        self.assertIsNone(pending.paid_cycle_schedule.anchor_at)
        self.assertNotEqual(pending.paid_cycle_schedule.obligation_id('tenant', 0),
                            original.paid_cycle_schedule.obligation_id('tenant', 0))
        with self.assertRaises(ValueError):
            start_trial(pending, now=end)
        with self.assertRaises(ValueError):
            request_reactivation(closed, now=end, lifecycle_id='first-life')
        again = request_reactivation(pending, now=end, lifecycle_id='third-life')
        self.assertEqual(again.paid_cycle_schedule.lifecycle_id, 'second-life')

    def test_immediate_cancel_and_wrong_payment_do_not_restore_access(self):
        original = subscription()
        closed = cancel_subscription(original, now=AT + timedelta(days=1), immediate=True)
        self.assertEqual(closed.status, SubscriptionStatus.CANCELED)
        pending = request_reactivation(closed, now=AT + timedelta(days=2), lifecycle_id='second-life')
        schedule = pending.paid_cycle_schedule; identity = schedule.obligation_id('tenant', 0)
        confirmed = schedule.confirm_payment('tenant', identity, 0, AT + timedelta(days=2))
        with self.assertRaises(ValueError):
            activate_commercial_payment(pending, schedule=confirmed, billed_plan=pending.plan,
                billed_index=0, billed_purpose=ChargePurpose.REGULAR, billing_id=identity,
                settled_at=AT + timedelta(days=2))
        self.assertFalse(entitlement_access_is_active(pending, now=AT + timedelta(days=2)))

    def test_contract_snapshot_must_match_payment_and_legacy_rules_fail_closed(self):
        original = subscription(); target = plans()[1]
        pending = request_plan_change(original, target, now=AT + timedelta(days=1))
        schedule = pending.paid_cycle_schedule; identity = schedule.obligation_id('tenant', 1)
        due = schedule.bounds(0)[1]
        confirmed = schedule.confirm_payment('tenant', identity, 1, due)
        with self.assertRaises(ValueError):
            activate_commercial_payment(pending, schedule=confirmed, billed_plan=replace(target, included_credits=Decimal(99)),
                billed_index=1, billed_purpose=ChargePurpose.PLAN_CHANGE, billing_id=identity, settled_at=due)
        legacy_rule = replace(original.plan.plan_changes[0], activation=PlanChangeActivation.SETTLED_PAYMENT)
        with self.assertRaises(ValueError):
            request_plan_change(replace(original, plan=replace(original.plan, plan_changes=(legacy_rule,))), target, now=AT)
