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


class CreativeImageReviewStore:
    """F3 idempotency-backed immutable review; no publication decision."""

    def __init__(self, state):
        if state.db is None:
            raise AssetStorageError(Code.DISABLED)
        self.state = state

    def get(self, identity):
        from .creative_repository import CreativeRepository
        row = CreativeRepository(self.state.db).get(identity)
        key = "creative-review:" + identity.creative_id + ":" + str(identity.campaign_version)
        previous = self.state.idempotency.get(identity.tenant_id, key)
        review = previous.result if previous is not None else None
        if review and not decision_applies(row, review):
            return {"decision": "STALE", "reviewer_id": None}
        return review

    def decide(self, identity, *, reviewer_id, requester_id, decision, expected_sha256,
               expected_generation):
        from .creative_repository import CreativeRepository
        if (not isinstance(decision, ReviewDecision) or not reviewer_id
                or reviewer_id == requester_id or not requester_id):
            raise AssetStorageError(Code.CONFLICT)
        key = "creative-review:" + identity.creative_id + ":" + str(identity.campaign_version)

        def commit():
            row = CreativeRepository(self.state.db).get(identity)
            if (row["state"] != "STORED"
                    or row["manifest"]["sha256"] != expected_sha256
                    or row["storage_generation"] != expected_generation):
                raise AssetStorageError(Code.CONFLICT)
            record = {
                "creative_id": identity.creative_id,
                "campaign_version": identity.campaign_version,
                "sha256": expected_sha256,
                "generation": expected_generation,
                "reviewer_id": reviewer_id,
                "requester_id": requester_id,
                "decision": decision.value,
            }
            self.state.audit.append(tenant_id=identity.tenant_id, actor=reviewer_id,
                                    action="CREATIVE_IMAGE_REVIEW_" + decision.value,
                                    target=identity.creative_id)
            return record
        result, replay = self.state.idempotency.execute(identity.tenant_id, key, commit)
        if (result["reviewer_id"] != reviewer_id or result["decision"] != decision.value
                or result["requester_id"] != requester_id
                or result["sha256"] != expected_sha256
                or result["generation"] != expected_generation):
            raise AssetStorageError(Code.CONFLICT)
        return result, replay
