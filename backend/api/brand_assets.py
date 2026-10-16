"""Durable asset metadata / quota / dispatch fences, separate from external bytes.

Every mutation claims under F3's tenant transaction. External storage is always called
after commit. An uncertain cloud mutation is observed, never automatically redispatched.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from campaia_core.asset_storage import AssetIdentity, AssetManifest, StoredAsset, AssetStorageError
from .errors import ApiError

_PENDING_UPLOAD = frozenset({"UPLOADING", "UPLOAD_UNCERTAIN"})
_PENDING_DELETE = frozenset({"DELETE_REQUESTED", "DELETE_UNCERTAIN"})


def manifest(record):
    values = record["manifest"]
    return AssetManifest(AssetIdentity(**values["identity"]), values["size"],
                         values["sha256"], values["md5_base64"])


def stored(record):
    return StoredAsset(manifest(record), record["generation"])


def public_asset(record):
    ready = record["status"] == "READY"
    identity = record["asset_id"]
    brand = record["brand_profile_id"]
    return {
        "id": identity, "brand_profile_id": brand, "kind": record["kind"],
        "status": record["status"], "width": record["width"], "height": record["height"],
        "size_bytes": record["manifest"]["size"], "content_type": "image/png",
        "created_at": record["created_at"].isoformat(),
        "updated_at": record["updated_at"].isoformat(),
        "content_url": f"/api/campaia/brand-profiles/{brand}/assets/{identity}/content" if ready else None,
    }


class BrandAssetStore:
    def __init__(self, state):
        self.state = state
        self.table = state.db.table("brand_assets")

    def rows(self, tenant):
        return [record for _id, _tenant, record in self.table.rows_for_tenant(tenant)]

    def get(self, tenant, profile, identity):
        row = self.table.get_for_tenant(identity, tenant)
        if row is None or row["brand_profile_id"] != profile:
            raise ApiError("NOT_FOUND", "Arquivo indisponível.", status_code=404)
        return row

    def usage(self, tenant):
        return sum(row["manifest"]["size"] for row in self.rows(tenant) if row["status"] != "DELETED")

    def page(self, tenant, profile, cursor=None):
        rows = sorted((r for r in self.rows(tenant) if r["brand_profile_id"] == profile and r["status"] != "DELETED"),
                      key=lambda r: (r["created_at"], r["asset_id"]), reverse=True)
        if cursor is not None:
            current = self.get(tenant, profile, cursor)
            before = (current["created_at"], current["asset_id"])
            rows = [r for r in rows if (r["created_at"], r["asset_id"]) < before]
        selected = rows[:50]
        return {"items": [public_asset(row) for row in selected],
                "next_cursor": selected[-1]["asset_id"] if len(rows) > 50 else None}

    def _scope(self, record, storage):
        if record["storage_namespace"] != storage.namespace:
            raise ApiError("ASSET_STORAGE_CHANGED", "O arquivo precisa de conferência no armazenamento de origem.", status_code=409)

    def _outside(self):
        if self.state.db.in_transaction:
            raise RuntimeError("Asset dispatch requires a committed fence.")

    def reserve(self, fixture, profile, key, raw_digest, kind, image, storage):
        facts = [fixture.user_id, fixture.business_unit_id, profile, raw_digest, kind,
                 image.width, image.height, sha256(image.data).hexdigest(), storage.namespace]
        context = sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
        def claim():
            if self.usage(fixture.tenant_id) + len(image.data) > storage.max_active_bytes:
                raise ApiError("ASSET_QUOTA_EXCEEDED", "O limite de arquivos da organização foi atingido.", status_code=409)
            identity = str(uuid4())
            now = datetime.now(timezone.utc)
            expected = AssetManifest.from_normalized_png(AssetIdentity(fixture.tenant_id, profile, identity), image.data)
            row = {
                "asset_id": identity, "brand_profile_id": profile, "kind": kind,
                "manifest": asdict(expected), "width": image.width, "height": image.height,
                "storage_namespace": storage.namespace, "status": "UPLOADING", "generation": None,
                "created_at": now, "updated_at": now, "deleted_at": None,
                "actor_id": fixture.user_id, "business_unit_id": fixture.business_unit_id,
                "request_context": context,
            }
            self.table.put(identity, fixture.tenant_id, row)
            self.state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                action="BRAND_ASSET_RESERVED", target=identity,
                details={"brand_profile_id": profile, "kind": kind, "bytes": expected.size})
            return {"asset_id": identity, "context": context}
        result, replay = self.state.idempotency.execute(fixture.tenant_id, "brand-asset-upload:" + key, claim)
        if result["context"] != context:
            raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outro arquivo ou contexto.", status_code=409)
        return self.get(fixture.tenant_id, profile, result["asset_id"]), not replay

    def _transition(self, tenant, record, event, change):
        def commit():
            current = self.get(tenant, record["brand_profile_id"], record["asset_id"])
            update = change(current)
            if update is not None:
                at = datetime.now(timezone.utc)
                updated = {**current, **update, "updated_at": at}
                self.table.put(record["asset_id"], tenant, updated)
                self.state.audit.append(tenant_id=tenant, actor="brand-asset-storage", actor_kind="SYSTEM",
                    action="BRAND_ASSET_" + updated["status"], target=record["asset_id"],
                    details={"brand_profile_id": record["brand_profile_id"], "status": updated["status"]})
            return {"checked": True}
        self.state.idempotency.execute(tenant, "brand-asset-event:" + record["asset_id"] + ":" + event, commit)
        return self.get(tenant, record["brand_profile_id"], record["asset_id"])

    def _ready(self, tenant, record, observed):
        if observed.manifest != manifest(record):
            raise ApiError("ASSET_INTEGRITY_FAILED", "Não foi possível conferir o arquivo.", status_code=409)
        def change(current):
            if current["generation"] is not None and current["generation"] != observed.generation:
                raise ApiError("ASSET_INTEGRITY_FAILED", "A versão do arquivo diverge.", status_code=409)
            return {"status": "READY", "generation": observed.generation} if current["status"] in _PENDING_UPLOAD else None
        return self._transition(tenant, record, "ready:" + observed.generation, change)

    def upload(self, tenant, record, image, storage, dispatch):
        self._scope(record, storage)
        self._outside()
        if not dispatch:
            return self.reconcile(tenant, record, storage)
        try:
            observed = storage.upload_once(manifest(record), image.data)
        except AssetStorageError:
            return self._transition(tenant, record, "upload-uncertain",
                lambda current: {"status": "UPLOAD_UNCERTAIN"} if current["status"] in _PENDING_UPLOAD else None)
        return self._ready(tenant, record, observed)

    def remember_intent(self, fixture, record, key, action):
        context = sha256(json.dumps([fixture.user_id, fixture.business_unit_id,
            record["brand_profile_id"], record["asset_id"], action], sort_keys=True).encode()).hexdigest()
        result, _ = self.state.idempotency.execute(fixture.tenant_id, "brand-asset-intent:" + key,
            lambda: {"context": context})
        if result["context"] != context:
            raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outra ação ou contexto.", status_code=409)

    def reconcile(self, tenant, record, storage):
        self._scope(record, storage)
        self._outside()
        current = self.get(tenant, record["brand_profile_id"], record["asset_id"])
        if current["status"] in _PENDING_UPLOAD:
            try:
                observed = storage.observe(manifest(current))
            except AssetStorageError:
                return current
            # Absence does not prove an earlier upload failed. Hold quota, never POST again.
            return self._ready(tenant, current, observed) if observed is not None else current
        if current["status"] in _PENDING_DELETE:
            try:
                observed = storage.observe(manifest(current), current["generation"])
            except AssetStorageError:
                return current
            if observed is None:
                return self._transition(tenant, current, "deleted",
                    lambda latest: {"status": "DELETED", "deleted_at": datetime.now(timezone.utc)}
                    if latest["status"] in _PENDING_DELETE else None)
        return current

    def delete(self, fixture, record, key, storage):
        self._scope(record, storage)
        context = sha256(json.dumps([fixture.user_id, fixture.business_unit_id,
            record["brand_profile_id"], record["asset_id"]], sort_keys=True).encode()).hexdigest()
        def claim():
            current = self.get(fixture.tenant_id, record["brand_profile_id"], record["asset_id"])
            if current["status"] in _PENDING_UPLOAD:
                raise ApiError("ASSET_PENDING", "Confira o envio antes de solicitar a exclusão.", status_code=409)
            dispatch = current["status"] == "READY"
            if dispatch:
                updated = {**current, "status": "DELETE_REQUESTED", "updated_at": datetime.now(timezone.utc)}
                self.table.put(record["asset_id"], fixture.tenant_id, updated)
                self.state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                    action="BRAND_ASSET_DELETE_REQUESTED", target=record["asset_id"],
                    details={"brand_profile_id": record["brand_profile_id"]})
            return {"context": context, "dispatch": dispatch}
        result, replay = self.state.idempotency.execute(fixture.tenant_id, "brand-asset-delete:" + key, claim)
        if result["context"] != context:
            raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outra exclusão ou contexto.", status_code=409)
        current = self.get(fixture.tenant_id, record["brand_profile_id"], record["asset_id"])
        self._outside()
        if result["dispatch"] and not replay and current["status"] == "DELETE_REQUESTED":
            try:
                storage.delete_once(stored(current))
            except AssetStorageError:
                self._transition(fixture.tenant_id, current, "delete-uncertain",
                    lambda latest: {"status": "DELETE_UNCERTAIN"} if latest["status"] in _PENDING_DELETE else None)
        return self.reconcile(fixture.tenant_id, current, storage)
