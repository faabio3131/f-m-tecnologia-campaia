from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from campaia_core.subscription import (
    CancellationMode,
    ChargePurpose,
    DunningPolicy,
    PlanChangeBillingMode,
    PlanChangeKind,
    PlanChangeRule,
    PlanDefinition,
    PlanEntitlements,
    PastDueAccessMode,
    Subscription,
    SubscriptionStatus,
    ReactivationBillingMode,
    ReactivationMode,
    activate_from_settled_payment,
    cancel_subscription,
    compute_cycle_charge,
    dunning_reminder_is_due,
    entitlement_access_is_active,
    mark_past_due,
    next_dunning_reminder_at,
    past_due_is_in_grace,
    record_dunning_reminder,
    refresh_trial_status,
    request_plan_change,
    request_reactivation,
    start_trial,
)


class SubscriptionChargeTests(unittest.TestCase):
    def plan(self) -> PlanDefinition:
        return PlanDefinition(
            plan_id="essencial",
            name="Essencial",
            monthly_price=Decimal("199.90"),
            included_credits=Decimal("100"),
            extra_credit_unit_price=Decimal("1.50"),
        )

    def subscription(self, status: SubscriptionStatus = SubscriptionStatus.ACTIVE) -> Subscription:
        return Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.plan(),
            status=status,
        )

    def commercial_plan(self) -> PlanDefinition:
        return PlanDefinition(
            plan_id="trial-plan",
            name="Trial Plan",
            monthly_price=Decimal("99.90"),
            included_credits=Decimal("10"),
            extra_credit_unit_price=Decimal("1"),
            max_users=3,
            trial_days=14,
            entitlements=PlanEntitlements(
                max_users=3,
                max_active_campaigns=5,
                channels=("GOOGLE_ADS",),
                ai_capabilities=("TEXT_STRATEGY",),
                resources=("BRAND_KIT",),
            ),
        )

    def dunning_plan(
        self, access_mode: PastDueAccessMode = PastDueAccessMode.ALLOW_DURING_GRACE
    ) -> PlanDefinition:
        return PlanDefinition(
            plan_id="dunning-plan",
            name="Dunning Plan",
            monthly_price=Decimal("99.90"),
            included_credits=Decimal("10"),
            extra_credit_unit_price=Decimal("1"),
            entitlements=PlanEntitlements(max_users=2),
            dunning_policy=DunningPolicy(
                grace_period_days=3,
                access_mode=access_mode,
                reminder_offsets_days=(0, 2, 3),
            ),
        )

    def test_new_subscription_defaults_to_pending_payment(self) -> None:
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.commercial_plan(),
        )
        self.assertEqual(sub.status, SubscriptionStatus.PENDING_PAYMENT)
        self.assertFalse(entitlement_access_is_active(sub))

    def test_trial_start_expire_and_access_window(self) -> None:
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        pending = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.commercial_plan(),
        )
        trial = start_trial(pending, now=now)
        self.assertEqual(trial.status, SubscriptionStatus.TRIAL)
        self.assertEqual(trial.trial_started_at, now)
        self.assertEqual(trial.trial_ends_at, now + timedelta(days=14))
        self.assertTrue(entitlement_access_is_active(trial, now=now + timedelta(days=13)))

        expired = refresh_trial_status(trial, now=now + timedelta(days=14))
        self.assertEqual(expired.status, SubscriptionStatus.EXPIRED)
        self.assertFalse(entitlement_access_is_active(expired, now=now + timedelta(days=14)))

    def test_trial_fails_closed_without_commercial_configuration(self) -> None:
        pending = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.plan(),
        )
        with self.assertRaises(ValueError):
            start_trial(pending)

    def test_expired_trial_cannot_restart_without_explicit_commercial_policy(self) -> None:
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        pending = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.commercial_plan(),
        )
        trial = start_trial(pending, now=now)
        expired = refresh_trial_status(trial, now=now + timedelta(days=14))
        self.assertEqual(expired.status, SubscriptionStatus.EXPIRED)
        with self.assertRaises(ValueError):
            start_trial(expired, now=now + timedelta(days=15))

    def test_payment_activation_fails_closed_without_entitlements(self) -> None:
        pending = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.plan(),
        )
        with self.assertRaises(ValueError):
            activate_from_settled_payment(
                pending,
                settled_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
            )

    def test_settled_payment_activates_pending_or_expired_subscription(self) -> None:
        settled_at = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        pending = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.commercial_plan(),
        )
        active = activate_from_settled_payment(pending, settled_at=settled_at)
        self.assertEqual(active.status, SubscriptionStatus.ACTIVE)
        self.assertEqual(active.activated_at, settled_at)
        self.assertTrue(entitlement_access_is_active(active))

        expired = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.commercial_plan(),
            status=SubscriptionStatus.EXPIRED,
        )
        reactivated = activate_from_settled_payment(expired, settled_at=settled_at)
        self.assertEqual(reactivated.status, SubscriptionStatus.ACTIVE)

    def test_settled_payment_does_not_silently_reactivate_canceled_subscription(self) -> None:
        canceled = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.commercial_plan(),
            status=SubscriptionStatus.CANCELED,
        )
        with self.assertRaises(ValueError):
            activate_from_settled_payment(canceled)

    def test_charge_within_franchise_has_a_single_line_item(self) -> None:
        charge = compute_cycle_charge(
            self.subscription(), competence="2026-09", extra_credits_used=Decimal("50")
        )
        self.assertEqual(len(charge.line_items), 1)
        self.assertEqual(charge.amount, Decimal("199.90"))
        self.assertEqual(charge.billing_id, "sub:tenant-1:2026-09")
        self.assertEqual(charge.currency, "BRL")

    def test_usage_beyond_franchise_adds_extra_credit_line_item(self) -> None:
        charge = compute_cycle_charge(
            self.subscription(), competence="2026-09", extra_credits_used=Decimal("130")
        )
        self.assertEqual(len(charge.line_items), 2)
        # 30 creditos excedentes * 1.50
        self.assertEqual(charge.line_items[1].amount, Decimal("45.00"))
        self.assertEqual(charge.amount, Decimal("244.90"))

    def test_same_competence_is_deterministic_and_idempotent_by_billing_id(self) -> None:
        first = compute_cycle_charge(self.subscription(), competence="2026-09")
        second = compute_cycle_charge(self.subscription(), competence="2026-09")
        self.assertEqual(first.billing_id, second.billing_id)
        self.assertEqual(first.amount, second.amount)

    def test_canceled_subscription_never_generates_a_charge(self) -> None:
        with self.assertRaises(ValueError):
            compute_cycle_charge(
                self.subscription(SubscriptionStatus.CANCELED), competence="2026-09"
            )

    def test_blank_competence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compute_cycle_charge(self.subscription(), competence="  ")

    def test_negative_extra_credits_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compute_cycle_charge(
                self.subscription(), competence="2026-09", extra_credits_used=Decimal("-1")
            )

    def test_plan_definition_rejects_non_positive_price(self) -> None:
        with self.assertRaises(ValueError):
            PlanDefinition(
                plan_id="x",
                name="X",
                monthly_price=Decimal("0"),
                included_credits=Decimal("10"),
                extra_credit_unit_price=Decimal("1"),
            )

    def test_subscription_rejects_blank_customer_document(self) -> None:
        with self.assertRaises(ValueError):
            Subscription(
                tenant_id="tenant-1",
                customer_ref="customer-1",
                customer_document="  ",
                plan=self.plan(),
            )

    def test_plan_definition_rejects_non_brl_currency(self) -> None:
        with self.assertRaises(ValueError):
            PlanDefinition(
                plan_id="x",
                name="X",
                monthly_price=Decimal("10"),
                included_credits=Decimal("10"),
                extra_credit_unit_price=Decimal("1"),
                currency="USD",
            )



    def test_plan_change_is_payment_gated_and_matches_billed_plan(self) -> None:
        target = PlanDefinition(
            plan_id="pro",
            name="Pro",
            monthly_price=Decimal("299.90"),
            included_credits=Decimal("200"),
            extra_credit_unit_price=Decimal("1"),
            entitlements=PlanEntitlements(max_users=5),
        )
        current = PlanDefinition(
            plan_id="basic",
            name="Basic",
            monthly_price=Decimal("99.90"),
            included_credits=Decimal("10"),
            extra_credit_unit_price=Decimal("1"),
            entitlements=PlanEntitlements(max_users=1),
            plan_changes=(
                PlanChangeRule(
                    "pro",
                    PlanChangeKind.UPGRADE,
                    billing_mode=PlanChangeBillingMode.TARGET_PLAN_FULL_CYCLE,
                ),
            ),
        )
        sub = Subscription(
            tenant_id="tenant-1", customer_ref="customer-1",
            customer_document="11144477735", plan=current, status=SubscriptionStatus.ACTIVE,
        )
        pending = request_plan_change(sub, target)
        self.assertEqual(pending.plan.plan_id, "basic")
        self.assertEqual(pending.pending_plan.plan_id, "pro")
        self.assertTrue(entitlement_access_is_active(pending))
        with self.assertRaises(ValueError):
            activate_from_settled_payment(pending, billed_plan_id="basic")
        active = activate_from_settled_payment(
            pending, billed_plan_id="pro", billed_purpose=ChargePurpose.PLAN_CHANGE
        )
        self.assertEqual(active.plan.plan_id, "pro")
        self.assertIsNone(active.pending_plan)

    def test_cancel_then_reactivate_requires_new_payment(self) -> None:
        plan = PlanDefinition(
            plan_id="commercial", name="Commercial",
            monthly_price=Decimal("99.90"), included_credits=Decimal("10"),
            extra_credit_unit_price=Decimal("1"),
            entitlements=PlanEntitlements(max_users=2),
            cancellation_mode=CancellationMode.IMMEDIATE,
            reactivation_mode=ReactivationMode.PAYMENT_REQUIRED,
            reactivation_billing_mode=ReactivationBillingMode.CURRENT_PLAN_FULL_CYCLE,
        )
        sub = Subscription(
            tenant_id="tenant-1", customer_ref="customer-1",
            customer_document="11144477735", plan=plan, status=SubscriptionStatus.ACTIVE,
        )
        canceled = cancel_subscription(sub)
        self.assertEqual(canceled.status, SubscriptionStatus.CANCELED)
        self.assertFalse(entitlement_access_is_active(canceled))
        pending = request_reactivation(canceled)
        self.assertEqual(pending.status, SubscriptionStatus.PENDING_PAYMENT)
        self.assertFalse(entitlement_access_is_active(pending))
        active = activate_from_settled_payment(
            pending,
            billed_plan_id="commercial",
            billed_purpose=ChargePurpose.REACTIVATION,
        )
        self.assertEqual(active.status, SubscriptionStatus.ACTIVE)

    def test_past_due_fails_closed_without_dunning_policy(self) -> None:
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.commercial_plan(),
            status=SubscriptionStatus.ACTIVE,
        )
        with self.assertRaises(ValueError):
            mark_past_due(
                sub,
                billed_plan_id=sub.plan.plan_id,
                billed_purpose=ChargePurpose.REGULAR,
            )

    def test_past_due_grace_window_controls_entitlement(self) -> None:
        now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=self.dunning_plan(),
            status=SubscriptionStatus.ACTIVE,
        )
        overdue = mark_past_due(
            sub,
            overdue_at=now,
            billed_plan_id=sub.plan.plan_id,
            billed_purpose=ChargePurpose.REGULAR,
        )
        self.assertEqual(overdue.status, SubscriptionStatus.PAST_DUE)
        self.assertEqual(overdue.past_due_at, now)
        self.assertEqual(overdue.grace_period_ends_at, now + timedelta(days=3))
        self.assertTrue(past_due_is_in_grace(overdue, now=now + timedelta(days=2)))
        self.assertTrue(
            entitlement_access_is_active(overdue, now=now + timedelta(days=2))
        )
        self.assertFalse(
            entitlement_access_is_active(overdue, now=now + timedelta(days=3))
        )

    def test_past_due_can_block_immediately_when_policy_says_so(self) -> None:
        now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        plan = self.dunning_plan(PastDueAccessMode.BLOCK_IMMEDIATELY)
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
        )
        overdue = mark_past_due(
            sub,
            overdue_at=now,
            billed_plan_id=plan.plan_id,
        )
        self.assertFalse(past_due_is_in_grace(overdue, now=now))
        self.assertFalse(entitlement_access_is_active(overdue, now=now))

    def test_dunning_schedule_is_deterministic_and_recorded_only_when_due(self) -> None:
        now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        plan = self.dunning_plan()
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
        )
        overdue = mark_past_due(
            sub,
            overdue_at=now,
            billed_plan_id=plan.plan_id,
        )
        self.assertEqual(next_dunning_reminder_at(overdue), now)
        self.assertTrue(dunning_reminder_is_due(overdue, now=now))
        first = record_dunning_reminder(overdue, reminder_index=0, now=now)
        self.assertEqual(first.dunning_reminders_sent, 1)
        self.assertEqual(next_dunning_reminder_at(first), now + timedelta(days=2))

        replay = record_dunning_reminder(first, reminder_index=0, now=now)
        self.assertEqual(replay, first)

        with self.assertRaises(ValueError):
            record_dunning_reminder(first, reminder_index=1, now=now + timedelta(days=1))
        with self.assertRaises(ValueError):
            record_dunning_reminder(first, reminder_index=2, now=now + timedelta(days=2))

        second = record_dunning_reminder(
            first, reminder_index=1, now=now + timedelta(days=2)
        )
        third = record_dunning_reminder(
            second, reminder_index=2, now=now + timedelta(days=3)
        )
        self.assertEqual(third.dunning_reminders_sent, 3)
        self.assertIsNone(next_dunning_reminder_at(third))

    def test_only_regular_current_plan_charge_can_mark_past_due(self) -> None:
        plan = self.dunning_plan()
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
        )
        with self.assertRaises(ValueError):
            mark_past_due(
                sub,
                billed_plan_id=plan.plan_id,
                billed_purpose=ChargePurpose.PLAN_CHANGE,
            )
        with self.assertRaises(ValueError):
            mark_past_due(sub, billed_plan_id="outro-plano")

    def test_regular_payment_recovers_past_due_and_clears_dunning_state(self) -> None:
        now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        plan = self.dunning_plan()
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
        )
        overdue = mark_past_due(
            sub,
            overdue_at=now,
            billed_plan_id=plan.plan_id,
        )
        reminded = record_dunning_reminder(overdue, reminder_index=0, now=now)
        recovered = activate_from_settled_payment(
            reminded,
            settled_at=now + timedelta(days=1),
            billed_plan_id=plan.plan_id,
            billed_purpose=ChargePurpose.REGULAR,
        )
        self.assertEqual(recovered.status, SubscriptionStatus.ACTIVE)
        self.assertIsNone(recovered.past_due_at)
        self.assertIsNone(recovered.grace_period_ends_at)
        self.assertEqual(recovered.dunning_reminders_sent, 0)
        self.assertIsNone(recovered.last_dunning_at)

    def test_plan_change_payment_cannot_recover_past_due(self) -> None:
        plan = self.dunning_plan()
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
        )
        overdue = mark_past_due(sub, billed_plan_id=plan.plan_id)
        with self.assertRaises(ValueError):
            activate_from_settled_payment(
                overdue,
                billed_plan_id=plan.plan_id,
                billed_purpose=ChargePurpose.PLAN_CHANGE,
            )

    def test_past_due_does_not_generate_a_new_regular_charge(self) -> None:
        plan = self.dunning_plan()
        sub = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
        )
        overdue = mark_past_due(sub, billed_plan_id=plan.plan_id)
        with self.assertRaises(ValueError):
            compute_cycle_charge(overdue, competence="2026-11")


if __name__ == "__main__":
    unittest.main()
