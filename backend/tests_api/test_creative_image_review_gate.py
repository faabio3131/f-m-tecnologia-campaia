"""Review record gates do not confer publishing authority."""
import unittest

from api.creative_image_review import decision_applies
from api.routes_generated_creatives import _preview_policy
from types import SimpleNamespace


class CreativeHumanReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "identity": {"creative_id": "creative1", "campaign_version": 2},
            "manifest": {"sha256": "a" * 64},
            "storage_generation": "124", "state": "STORED",
        }
        self.review = {
            "creative_id": "creative1", "campaign_version": 2,
            "sha256": "a" * 64, "generation": "124",
            "reviewer_id": "different-human", "decision": "APPROVE",
        }

    def test_exact_binding_only(self):
        self.assertTrue(decision_applies(self.row, self.review))
        for field, value in (("creative_id", "other"),
                             ("campaign_version", 3),
                             ("sha256", "b" * 64),
                             ("generation", "125"),
                             ("decision", "REJECT")):
            with self.subTest(field=field):
                changed = dict(self.review, **{field: value})
                self.assertFalse(decision_applies(self.row, changed))

    def test_preview_uses_verified_review_and_never_grants_publication(self):
        campaign = SimpleNamespace(plan_version=2)
        approved = _preview_policy(self.row, campaign, self.review)
        self.assertEqual(approved["human_review"], "APPROVE")
        self.assertFalse(approved["publication_allowed"])
        self.assertNotIn("HUMAN_REVIEW_REQUIRED", approved["blocking_reasons"])
        revoked = _preview_policy(self.row, campaign, {"decision": "REVOKED"})
        self.assertFalse(revoked["publication_allowed"])
        self.assertIn("HUMAN_REVIEW_REQUIRED", revoked["blocking_reasons"])

    def test_missing_review_is_not_approval(self):
        self.assertFalse(decision_applies(self.row, None))


if __name__ == "__main__":
    unittest.main()
