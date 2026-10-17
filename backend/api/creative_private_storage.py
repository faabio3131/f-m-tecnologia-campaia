"""Committed F3 dispatch fence for generated creative uploads.

Uses the existing GCSAssetStorage / PrivateAssetStorage protocol, never calls
external storage while in a database transaction, and never re-POSTs after uncertainty.
No route, provider activation, or commercial credit settlement.
"""
from __future__ import annotations

from dataclasses import asdict

from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code
from campaia_core.creative_assets import (
    CreativeManifest, CreativeState, CreativeStateTransition, storage_manifest,
    recovery_storage_manifest,
)


class CreativePrivateStorage:
    def __init__(self, repository, storage):
        self.repository = repository
        self.storage = storage

    def _outside_transaction(self):
        if self.repository.db.in_transaction:
            raise RuntimeError("Creative storage I/O requires a committed F3 fence")

    def upload(self, manifest: CreativeManifest, png: bytes):
        """Exactly one dispatch winner; all replays only observe GCS."""
        expected = storage_manifest(manifest, png)
        self._outside_transaction()
        identity = manifest.identity
        current = self.repository.get(identity)
        if current["manifest"]["sha256"] != manifest.sha256 or current["manifest"] != asdict(manifest):
            raise AssetStorageError(Code.CONFLICT)
        if current["state"] == CreativeState.GENERATING.value:
            try:
                current = self.repository.transition(identity, CreativeStateTransition(
                    CreativeState.GENERATING, CreativeState.STORAGE_PENDING, current["revision"]))
            except AssetStorageError as exc:
                if exc.code != Code.CONFLICT:
                    raise
                return self.reconcile(manifest, png)
            # CAS committed. This caller is the ONLY writer allowed to dispatch.
            self._outside_transaction()
            try:
                stored = self.storage.upload_once(expected, png)
            except AssetStorageError:
                # We do not know if GCS accepted the upload; never retry POST.
                return self.repository.get(identity)
            if stored.manifest != expected:
                raise AssetStorageError(Code.INTEGRITY)
            return self._finalize(manifest, stored.generation)
        return self.reconcile(manifest, png)

    def reconcile_after_restart(self, identity):
        """Reload persisted manifest and observe private storage without in-memory image bytes."""
        from campaia_core.creative_assets import CreativeIdentity
        if not isinstance(identity, CreativeIdentity):
            raise AssetStorageError(Code.INVALID)
        current = self.repository.get(identity)
        record = current["manifest"]
        manifest = CreativeManifest(identity=identity, **{
            k: v for k, v in record.items() if k != "identity"
        })
        if current["state"] == CreativeState.STORED.value:
            expected = recovery_storage_manifest(manifest)
            self._outside_transaction()
            observed = self.storage.observe(expected, current["storage_generation"])
            if observed is None or observed.manifest != expected:
                raise AssetStorageError(Code.INTEGRITY)
            return current
        return self.reconcile(manifest)

    def _finalize(self, manifest: CreativeManifest, generation: str):
        identity = manifest.identity
        current = self.repository.get(identity)
        if current["state"] == CreativeState.STORED.value:
            if current["storage_generation"] != generation:
                raise AssetStorageError(Code.INTEGRITY)
            return current
        if current["state"] != CreativeState.STORAGE_PENDING.value:
            raise AssetStorageError(Code.CONFLICT)
        try:
            return self.repository.transition(identity, CreativeStateTransition(
                CreativeState.STORAGE_PENDING, CreativeState.STORED, current["revision"]),
                storage_generation=generation)
        except AssetStorageError as exc:
            if exc.code != Code.CONFLICT:
                raise
            resolved = self.repository.get(identity)
            if (resolved["state"] != CreativeState.STORED.value
                    or resolved["storage_generation"] != generation):
                raise
            return resolved

    def reconcile(self, manifest: CreativeManifest, png: bytes | None = None):
        """Unknown and missing are held pending; absence never proves safe redispatch."""
        self._outside_transaction()
        identity = manifest.identity
        current = self.repository.get(identity)
        if current["manifest"] != asdict(manifest):
            raise AssetStorageError(Code.CONFLICT)
        if current["state"] != CreativeState.STORAGE_PENDING.value:
            return current
        expected = (storage_manifest(manifest, png) if png is not None
                    else recovery_storage_manifest(manifest))
        try:
            observed = self.storage.observe(expected)
        except AssetStorageError:
            return current
        if observed is None:
            # No proof that an unknown POST did not commit. Hold quota and state.
            return current
        if observed.manifest != expected:
            raise AssetStorageError(Code.INTEGRITY)
        return self._finalize(manifest, observed.generation)

    def delete(self, identity):
        """Tombstone first; only CAS winner can dispatch one DELETE."""
        from campaia_core.creative_assets import CreativeIdentity
        from campaia_core.asset_storage import StoredAsset
        if not isinstance(identity, CreativeIdentity):
            raise AssetStorageError(Code.INVALID)
        self._outside_transaction()
        row = self.repository.get(identity)
        if row["state"] == CreativeState.STORED.value:
            try:
                row = self.repository.transition(identity, CreativeStateTransition(
                    CreativeState.STORED, CreativeState.DELETE_PENDING, row["revision"]))
            except AssetStorageError as exc:
                if exc.code != Code.CONFLICT:
                    raise
                return self.reconcile_delete(identity)
            record = row["manifest"]
            manifest = CreativeManifest(identity=identity, **{
                k: v for k, v in record.items() if k != "identity"
            })
            asset = StoredAsset(recovery_storage_manifest(manifest), row["storage_generation"])
            try:
                self.storage.delete_once(asset)
            except AssetStorageError:
                return self.repository.get(identity)
        return self.reconcile_delete(identity)

    def reconcile_delete(self, identity):
        """Missing GCS generation confirms access revocation; errors retain tombstone/quota."""
        self._outside_transaction()
        row = self.repository.get(identity)
        if row["state"] != CreativeState.DELETE_PENDING.value:
            return row
        record = row["manifest"]
        manifest = CreativeManifest(identity=identity, **{
            k: v for k, v in record.items() if k != "identity"
        })
        try:
            observed = self.storage.observe(
                recovery_storage_manifest(manifest), row["storage_generation"])
        except AssetStorageError:
            return row
        if observed is not None:
            return row
        try:
            return self.repository.transition(identity, CreativeStateTransition(
                CreativeState.DELETE_PENDING, CreativeState.DELETED, row["revision"]))
        except AssetStorageError as exc:
            if exc.code != Code.CONFLICT:
                raise
            return self.repository.get(identity)
