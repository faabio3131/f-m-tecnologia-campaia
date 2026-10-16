"""Immutable creative-image review decision kept apart from publication approvals.

The decision is version/hash/generation scoped and never grants publisher authority.
It can be reused by policy/preview without trusting client-supplied review status.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code


class ReviewDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


@dataclass(frozen=True, slots=True)
class CreativeReviewRecord:
    creative_id: str
    campaign_version: int
    sha256: str
    generation: str
    reviewer_id: str
    decision: ReviewDecision

    def __post_init__(self):
        if not isinstance(self.decision, ReviewDecision) or not self.reviewer_id:
            raise AssetStorageError(Code.INVALID)


def decision_applies(row: dict, review: dict | None) -> bool:
    return bool(review and
        review.get("creative_id") == row["identity"]["creative_id"] and
        review.get("campaign_version") == row["identity"]["campaign_version"] and
        review.get("sha256") == row["manifest"]["sha256"] and
        review.get("generation") == row["storage_generation"] and
        review.get("decision") == ReviewDecision.APPROVE.value)
