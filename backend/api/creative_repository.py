"""Durable creative metadata; uses F3 RecordTable transaction and advisory-key locks.

No provider call or credit settlement here. No API auto-activation. PostgreSQL requires
a reviewed migration before this repository can be constructed in production.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json

from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code
from campaia_core.errors import TenantIsolationViolation
from campaia_core.creative_assets import CreativeIdentity, CreativeManifest, CreativeState, CreativeStateTransition


def _context(identity: CreativeIdentity, request_key: str) -> str:
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 256:
        raise AssetStorageError(Code.INVALID)
    raw = json.dumps([asdict(identity), request_key], sort_keys=True).encode("utf-8")
    return sha256(raw).hexdigest()


class CreativeRepository:
    """F3 transaction wraps the tenant-scoped quota, claim and state mutation.

    Storage is NEVER dispatched here. STORAGE_PENDING must be reconciled using
    storage.observe; a missing object does not authorize resending a POST.
    """

    def __init__(self, db):
        self.db = db
        self.table = db.table("creative_assets")

    def get(self, identity: CreativeIdentity):
        row = self.table.get_for_tenant(identity.creative_id, identity.tenant_id)
        if row is None or row["identity"] != asdict(identity):
            raise AssetStorageError(Code.INVALID)
        return row

    def usage(self, tenant_id: str) -> int:
        return sum(r["manifest"]["size"] for _, _, r in
                   self.table.rows_for_tenant(tenant_id)
                   if r["state"] != CreativeState.DELETED.value)

    def claim(self, manifest: CreativeManifest, request_key: str, max_active_bytes: int, *,
              credit_operation_id: str | None = None):
        if not isinstance(manifest, CreativeManifest) or type(max_active_bytes) is not int or max_active_bytes <= 0:
            raise AssetStorageError(Code.INVALID)
        if credit_operation_id is not None and (not isinstance(credit_operation_id, str)
                or not __import__("re").fullmatch(r"[0-9a-f]{64}", credit_operation_id)):
            raise AssetStorageError(Code.INVALID)
        identity = manifest.identity
        context = _context(identity, request_key)
        with self.db.transaction():
            self.table.lock_key("creative-quota:" + identity.tenant_id)
            existing = self.table.get_for_tenant(identity.creative_id, identity.tenant_id)
            if existing is not None:
                if (existing["context"] != context or existing["manifest"] != asdict(manifest)
                        or existing.get("credit_operation_id") != credit_operation_id):
                    raise AssetStorageError(Code.CONFLICT)
                return existing, True
            if self.usage(identity.tenant_id) + manifest.size > max_active_bytes:
                raise AssetStorageError(Code.CONFLICT)
            row = {"identity": asdict(identity), "manifest": asdict(manifest),
                   "state": CreativeState.RESERVED.value, "revision": 0,
                   "storage_generation": None, "context": context,
                   "credit_operation_id": credit_operation_id}
            try:
                self.table.put(identity.creative_id, identity.tenant_id, row)
            except TenantIsolationViolation:
                raise AssetStorageError(Code.CONFLICT) from None
            return row, False

    def transition(self, identity: CreativeIdentity, command: CreativeStateTransition, *,
                   storage_generation: str | None = None):
        if not isinstance(command, CreativeStateTransition):
            raise AssetStorageError(Code.INVALID)
        with self.db.transaction():
            self.table.lock_key("creative:" + identity.creative_id)
            current = self.get(identity)
            if (current["state"] != command.expected.value
                    or current["revision"] != command.expected_revision):
                raise AssetStorageError(Code.CONFLICT)
            if command.target == CreativeState.STORED:
                from campaia_core.asset_storage import valid_generation
                valid_generation(storage_generation)
            elif storage_generation is not None:
                raise AssetStorageError(Code.INVALID)
            updated = {**current, "state": command.target.value,
                       "revision": command.next_revision}
            if storage_generation is not None:
                updated["storage_generation"] = storage_generation
            self.table.put(identity.creative_id, identity.tenant_id, updated)
            return updated
