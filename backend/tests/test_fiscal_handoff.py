from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from campaia_core.fiscal_handoff import (
    CampaiaBillingKind,
    SettledOwnBillingFact,
    build_campaia_fiscal_handoff,
)


class FiscalHandoffTests(unittest.TestCase):
    def fact(self, kind: CampaiaBillingKind = CampaiaBillingKind.SAAS) -> SettledOwnBillingFact:
        return SettledOwnBillingFact(
            billing_id="bill-1",
            tenant_id="tenant-1",
            customer_ref="customer-1",
            kind=kind,
            amount=Decimal("199.90"),
            currency="BRL",
            competence="2026-09",
            settled_at=datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
        )

    def test_saas_own_billing_maps_to_governed_nfse_handoff(self) -> None:
        handoff = build_campaia_fiscal_handoff(self.fact())
        self.assertEqual(handoff.host_namespace, "fm.campaia")
        self.assertEqual(handoff.pack_id, "campaia")
        self.assertEqual(handoff.use_case_id, "saas-billing")
        self.assertEqual(handoff.operation_kind, "saas_billing")
        self.assertEqual(handoff.document_kind, "nfse")
        self.assertEqual(handoff.state, "PENDING_CAPABILITY")
        self.assertTrue(handoff.fiscal_scope_binding_required)
        self.assertTrue(handoff.readiness_required_before_issuance)
        self.assertEqual(handoff.idempotency_key, "campaia:billing:bill-1:nfse:v1")

    def test_service_own_billing_uses_service_contract(self) -> None:
        handoff = build_campaia_fiscal_handoff(self.fact(CampaiaBillingKind.SERVICE))
        self.assertEqual(handoff.use_case_id, "service-billing")
        self.assertEqual(handoff.operation_kind, "service")
        self.assertEqual(handoff.document_kind, "nfse")

    def test_incomplete_or_unsettled_fact_fails_closed(self) -> None:
        invalid = SettledOwnBillingFact(
            billing_id="bill-2",
            tenant_id="tenant-1",
            customer_ref="",
            kind=CampaiaBillingKind.SAAS,
            amount=Decimal("0"),
            currency="BRL",
            competence="",
            settled_at=datetime(2026, 9, 13, 18, 0),
        )
        with self.assertRaises(ValueError):
            build_campaia_fiscal_handoff(invalid)

    def test_handoff_does_not_accept_campaign_budget_or_fiscal_authority_fields(self) -> None:
        fields = set(build_campaia_fiscal_handoff(self.fact()).__dataclass_fields__)
        self.assertNotIn("campaign_id", fields)
        self.assertNotIn("media_spend", fields)
        self.assertNotIn("provider_id", fields)
        self.assertNotIn("municipality_code", fields)
        self.assertNotIn("tax_rate", fields)
        self.assertNotIn("production_approved", fields)


if __name__ == "__main__":
    unittest.main()
