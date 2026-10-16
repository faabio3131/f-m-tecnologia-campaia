from decimal import Decimal
import unittest
from unittest.mock import patch

from campaia_core.autonomy import ActionKind, AutonomySettings, AutonomyDecision
from campaia_core.budget import BudgetEngine, BudgetLimits
from campaia_core.policy import PolicyEngine, PolicyRequest, Outcome


class BrandPolicyTests(unittest.TestCase):
    def request(self, **fields):
        return PolicyRequest(tenant_id="tenant", campaign_id="campaign", plan_version=1,
            action=ActionKind.REPORT_ONLY, autonomy=AutonomySettings(),
            budget=BudgetEngine("tenant", "campaign", BudgetLimits("BRL", Decimal("10"), Decimal("100"))),
            **fields)

    def test_guidance_requires_review_even_when_other_autonomy_rules_allow_operation(self):
        with patch("campaia_core.policy.evaluate_autonomy", return_value=AutonomyDecision(False, "preauthorized")):
            plain = PolicyEngine().evaluate(self.request())
            guided = PolicyEngine().evaluate(self.request(brand_guidance=("Evite promessas de retorno garantido.",)))
        self.assertFalse(plain.requires_human_approval)
        self.assertTrue(guided.requires_human_approval)
        self.assertEqual(guided.outcome, Outcome.APPROVABLE)
        self.assertEqual(guided.findings[0].code, "BRAND_GUIDANCE_REVIEW_REQUIRED")

    def test_literal_denylist_is_preserved_and_not_replaced_by_guidance(self):
        result = PolicyEngine().evaluate(self.request(brand_restrictions=("garantido",),
            brand_guidance=("Use linguagem clara.",), plan_text="Retorno GARANTIDO"))
        self.assertEqual(result.outcome, Outcome.BLOCKED)
        self.assertIn("BRAND_RESTRICTION", [finding.code for finding in result.findings])
        self.assertIsNone(result.policy_decision_id)

    def test_unavailable_selected_asset_never_produces_publication_authority(self):
        result = PolicyEngine().evaluate(self.request(brand_assets_ready=False))
        self.assertEqual(result.outcome, Outcome.BLOCKED)
        self.assertIsNone(result.policy_decision_id)
        self.assertEqual(result.findings[0].code, "BRAND_ASSET_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
