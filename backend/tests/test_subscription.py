from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from campaia_core.subscription import (
    PlanDefinition,
    PlanEntitlements,
    Subscription,
    SubscriptionStatus,
    activate_from_settled_payment,
    compute_cycle_charge,
    entitlement_access_is_active,
    refresh_trial_status,
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


if __name__ == "__main__":
    unittest.main()
