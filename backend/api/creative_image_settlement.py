"""Atomic commercial delivery of one verified, stored creative.

F3 unit-of-work is shared by idempotency, immutable creative metadata and F5
credit journal. No provider/storage I/O; caller must have reserved credits and
confirmed authenticated campaign ownership beforehand.
"""
from __future__ import annotations

from datetime import datetime, timezone

from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code
from campaia_core.creative_assets import CreativeIdentity, CreativeState


def settle_stored_creative(state, *, identity: CreativeIdentity, operation_id: str,
                           delivery_key: str, actor_id: str):
    if state.db is None or state.credit_ledger is None:
        raise AssetStorageError(Code.DISABLED)
    if any(not isinstance(x, str) or not x or len(x) > 256
           for x in (operation_id, delivery_key, actor_id)):
        raise AssetStorageError(Code.INVALID)

    def settle():
        from .creative_repository import CreativeRepository
        row = CreativeRepository(state.db).get(identity)
        if row["state"] != CreativeState.STORED.value or not row["storage_generation"]:
            raise AssetStorageError(Code.CONFLICT)
        # F5 refuses SETTLE if there was no matching RESERVE (or if already settled).
        result = state.credit_ledger.decide(identity.tenant_id, "finish",
                    operation_id=operation_id, kind="SETTLE",
                    reference="delivery:" + operation_id,
                    at=datetime.now(timezone.utc))
        state.audit.append(tenant_id=identity.tenant_id, actor=actor_id,
            action="CREATIVE_IMAGE_CREDITS_SETTLED", target=identity.creative_id,
            details={"campaign_id": identity.campaign_id, "operation_id": operation_id})
        return {"creative_id": identity.creative_id, "state": "STORED",
                "credit_entry_id": result.entry.entry_id}

    # F3 transaction wraps journal + audit + durable delivery idempotency as one unit.
    outcome, replay = state.idempotency.execute(
        identity.tenant_id, "creative-image-settle:" + delivery_key, settle)
    return outcome, replay
