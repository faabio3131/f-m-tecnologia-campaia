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

    def reconcile(self, manifest: CreativeManifest, png: bytes):
        """Unknown and missing are held pending; absence never proves safe redispatch."""
        self._outside_transaction()
        identity = manifest.identity
        current = self.repository.get(identity)
        if current["manifest"] != asdict(manifest):
            raise AssetStorageError(Code.CONFLICT)
        if current["state"] != CreativeState.STORAGE_PENDING.value:
            return current
        expected = storage_manifest(manifest, png)
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
