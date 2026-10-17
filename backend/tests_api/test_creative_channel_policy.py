"""G7 deterministic creative policy never grants a publication shortcut."""
import unittest

from api.creative_channel_policy import (
    CHANNELS, POLICY_VERSION, SENSITIVE_CATEGORIES, evaluate_creative_channel,
)


class CreativeChannelPolicyTests(unittest.TestCase):
    def test_all_channels_require_independent_media_proof_and_review(self):
        for channel in CHANNELS:
            with self.subTest(channel=channel):
                d = evaluate_creative_channel(channel, "GENERAL")
                self.assertEqual(d.policy_version, POLICY_VERSION)
                self.assertFalse(d.publication_allowed)
                self.assertIn("HUMAN_REVIEW_REQUIRED", d.reasons)
                self.assertIn("PROVIDER_MEDIA_VALIDATION_REQUIRED", d.reasons)

    def test_human_review_does_not_replace_provider_validation(self):
        for channel in CHANNELS:
            d = evaluate_creative_channel(channel, "GENERAL", reviewed=True)
            self.assertFalse(d.publication_allowed)
            self.assertTrue(d.allowed_internal_review)
            self.assertEqual(d.reasons, ("PROVIDER_MEDIA_VALIDATION_REQUIRED",))

    def test_sensitive_categories_are_fail_closed_even_with_all_proofs(self):
        for channel in CHANNELS:
            for category in SENSITIVE_CATEGORIES:
                with self.subTest(channel=channel, category=category):
                    d = evaluate_creative_channel(channel, category, reviewed=True,
                                                  provider_verified=True)
                    self.assertFalse(d.publication_allowed)
                    self.assertIn("SENSITIVE_CATEGORY_EXTERNAL_APPROVAL_REQUIRED", d.reasons)

    def test_unknown_channel_or_category_fails_closed(self):
        cases = [("UNSUPPORTED", "GENERAL", "CHANNEL_UNSUPPORTED"),
                 ("GOOGLE_ADS", "", "CATEGORY_UNCLASSIFIED"),
                 ("WHATSAPP", "UNKNOWN", "CATEGORY_UNSUPPORTED")]
        for channel, category, reason in cases:
            with self.subTest(channel=channel, category=category):
                d = evaluate_creative_channel(channel, category, reviewed=True,
                                              provider_verified=True)
                self.assertFalse(d.publication_allowed)
                self.assertIn(reason, d.reasons)

    def test_only_verifiably_generic_fully_approved_creative_is_eligible(self):
        for channel in CHANNELS:
            d = evaluate_creative_channel(channel, "GENERAL", reviewed=True,
                                          provider_verified=True)
            self.assertTrue(d.publication_allowed)
            self.assertEqual(d.reasons, ())


if __name__ == "__main__":
    unittest.main()
