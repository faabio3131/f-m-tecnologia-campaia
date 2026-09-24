from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from campaia_core.billing_settlement import charge_subscription, try_settle
from campaia_core.fiscal_handoff import build_campaia_fiscal_handoff
from campaia_core.payment_simulator import PaymentGatewaySimulator
from campaia_core.subscription import PlanDefinition, Subscription, compute_cycle_charge


class BillingSettlementTests(unittest.TestCase):
    def setUp(self) -> None:
        plan = PlanDefinition(
            plan_id="essencial",
            name="Essencial",
            monthly_price=Decimal("199.90"),
            included_credits=Decimal("100"),
            extra_credit_unit_price=Decimal("1.50"),
        )
        self.subscription = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=plan,
        )
        self.gateway = PaymentGatewaySimulator()

    def test_pending_payment_never_produces_a_settled_fact(self) -> None:
        charge = compute_cycle_charge(self.subscription, competence="2026-09")
        result = charge_subscription(charge, self.gateway)
        fact = try_settle(
            charge, result, self.gateway, settled_at=datetime(2026, 9, 23, 12, tzinfo=UTC)
        )
        self.assertIsNone(fact)

    def test_failed_payment_never_produces_a_settled_fact(self) -> None:
        charge = compute_cycle_charge(self.subscription, competence="2026-09")
        result = charge_subscription(charge, self.gateway)
        self.gateway.fail(result.gateway_charge_id)
        fact = try_settle(
            charge, result, self.gateway, settled_at=datetime(2026, 9, 23, 12, tzinfo=UTC)
        )
        self.assertIsNone(fact)

    def test_confirmed_payment_produces_a_settled_fact_that_feeds_the_fiscal_handoff(
        self,
    ) -> None:
        charge = compute_cycle_charge(
            self.subscription, competence="2026-09", extra_credits_used=Decimal("120")
        )
        result = charge_subscription(charge, self.gateway)
        self.gateway.confirm(result.gateway_charge_id)

        fact = try_settle(
            charge, result, self.gateway, settled_at=datetime(2026, 9, 23, 12, tzinfo=UTC)
        )
        self.assertIsNotNone(fact)
        assert fact is not None
        self.assertEqual(fact.billing_id, "sub:tenant-1:2026-09")
        self.assertEqual(fact.amount, charge.amount)

        handoff = build_campaia_fiscal_handoff(fact)
        self.assertEqual(handoff.host_namespace, "fm.campaia")
        self.assertEqual(handoff.use_case_id, "saas-billing")
        self.assertEqual(handoff.state, "PENDING_CAPABILITY")
        self.assertEqual(handoff.idempotency_key, "campaia:billing:sub:tenant-1:2026-09:nfse:v1")

    def test_recomputing_and_recharging_the_same_cycle_never_double_charges(self) -> None:
        charge_a = compute_cycle_charge(self.subscription, competence="2026-09")
        charge_b = compute_cycle_charge(self.subscription, competence="2026-09")
        result_a = charge_subscription(charge_a, self.gateway)
        result_b = charge_subscription(charge_b, self.gateway)
        self.assertEqual(result_a.gateway_charge_id, result_b.gateway_charge_id)


if __name__ == "__main__":
    unittest.main()
