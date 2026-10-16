"""Explicit in-memory cloud fixture; never selected by production or as error fallback."""
from threading import RLock
from uuid import uuid4

from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code, StoredAsset


class TestOnlyAssetStorage:
    mode = "SIMULATOR"

    def __init__(self, *, max_active_bytes=5 * 1024 * 1024):
        self.namespace = "test-only:" + uuid4().hex
        self.max_active_bytes = max_active_bytes
        self.objects = {}
        self.calls = []
        self._lock = RLock()
        self._generation = 1000

    def upload_once(self, manifest, data):
        with self._lock:
            self.calls.append("POST")
            manifest.verify_bytes(data)
            key = manifest.identity.object_name
            if key in self.objects:
                raise AssetStorageError(Code.CONFLICT)
            self._generation += 1
            asset = StoredAsset(manifest, str(self._generation))
            self.objects[key] = (asset, data)
            return asset

    def observe(self, manifest, generation=None):
        with self._lock:
            self.calls.append("GET")
            value = self.objects.get(manifest.identity.object_name)
            if value is None or (generation is not None and value[0].generation != generation):
                return None
            if value[0].manifest != manifest:
                raise AssetStorageError(Code.INTEGRITY)
            return value[0]

    def read(self, asset):
        with self._lock:
            self.calls.append("MEDIA")
            value = self.objects.get(asset.manifest.identity.object_name)
            if value is None or value[0] != asset:
                raise AssetStorageError(Code.INTEGRITY)
            asset.manifest.verify_bytes(value[1])
            return value[1]

    def delete_once(self, asset):
        with self._lock:
            self.calls.append("DELETE")
            value = self.objects.get(asset.manifest.identity.object_name)
            if value is not None and value[0] == asset:
                del self.objects[asset.manifest.identity.object_name]
            else:
                raise AssetStorageError(Code.CONFLICT)
