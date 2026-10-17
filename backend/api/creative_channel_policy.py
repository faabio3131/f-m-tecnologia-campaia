"""Conservative versioned creative-channel policy. Not a provider certification.

Rules are an internal hard-stop for unsupported channels / sensitive creatives.
Provider policy decisions, media acceptance and publication remain external gates.
"""
from __future__ import annotations

from dataclasses import dataclass

POLICY_VERSION = "G7_CREATIVE_CHANNEL_V1"
CHANNELS = frozenset({"GOOGLE_ADS", "META_FACEBOOK_INSTAGRAM", "WHATSAPP"})
SENSITIVE_CATEGORIES = frozenset({
    "HEALTH", "FINANCIAL", "POLITICAL", "GAMBLING", "ADULT", "MINORS",
    "HOUSING_EMPLOYMENT_CREDIT",
})


@dataclass(frozen=True)
class CreativeChannelDecision:
    policy_version: str
    channel: str
    category: str
    allowed_internal_review: bool
    publication_allowed: bool
    reasons: tuple[str, ...]

    def as_dict(self):
        return {
            "policy_version": self.policy_version,
            "channel": self.channel,
            "category": self.category,
            "allowed_internal_review": self.allowed_internal_review,
            "publication_allowed": self.publication_allowed,
            "blocking_reasons": list(self.reasons),
        }


def evaluate_creative_channel(channel: str, category: str | None,
                              *, reviewed: bool = False,
                              provider_verified: bool = False) -> CreativeChannelDecision:
    """Never infer authorization from a visual preview or channel name.

    Unknown categories fail closed; generic creatives may be reviewed internally,
    but provider-specific delivery requires independently verified evidence.
    """
    normalized_channel = channel if isinstance(channel, str) else ""
    normalized_category = category if isinstance(category, str) else ""
    reasons = []
    if normalized_channel not in CHANNELS:
        reasons.append("CHANNEL_UNSUPPORTED")
    if not normalized_category:
        reasons.append("CATEGORY_UNCLASSIFIED")
    elif normalized_category in SENSITIVE_CATEGORIES:
        reasons.append("SENSITIVE_CATEGORY_EXTERNAL_APPROVAL_REQUIRED")
    elif normalized_category != "GENERAL":
        reasons.append("CATEGORY_UNSUPPORTED")
    if not reviewed:
        reasons.append("HUMAN_REVIEW_REQUIRED")
    if not provider_verified:
        reasons.append("PROVIDER_MEDIA_VALIDATION_REQUIRED")
    internal_review = normalized_channel in CHANNELS and normalized_category == "GENERAL"
    return CreativeChannelDecision(
        POLICY_VERSION, normalized_channel, normalized_category,
        internal_review, not reasons, tuple(reasons),
    )
