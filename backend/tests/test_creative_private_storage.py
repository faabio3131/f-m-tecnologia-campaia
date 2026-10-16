"""Private creative storage dispatch fence tests: no external network."""
import os
import tempfile
import unittest
from uuid import uuid4

from api.db import Database
from api.creative_repository import CreativeRepository
from api.creative_private_storage import CreativePrivateStorage
from campaia_core.asset_images import normalize_asset_image
from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code, StoredAsset
from campaia_core.creative_assets import CreativeIdentity, CreativeManifest, CreativeState, CreativeStateTransition
from tests.test_asset_images import encoded


class StorageFake:
    namespace = "SIMULATOR"
    max_active_bytes = 5000000

    def __init__(self):
        self.uploads = 0
        self.observations = 0
        self.saved = None
        self.uncertain = False
        self.deletes = 0
        self.delete_uncertain = False

    def upload_once(self, expected, png):
        self.uploads += 1
        self.saved = StoredAsset(expected, "17")
        if self.uncertain:
            raise AssetStorageError(Code.UNCERTAIN)
        return self.saved

    def observe(self, expected, generation=None):
        self.observations += 1
        return self.saved

    def delete_once(self, asset):
        self.deletes += 1
        self.saved = None
        if self.delete_uncertain:
            raise AssetStorageError(Code.UNCERTAIN)


class CreativePrivateStorageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Database(os.path.join(tmp.name, "creative.sqlite"))
        self.addCleanup(self.db.close)
        self.repo = CreativeRepository(self.db)
        self.storage = StorageFake()
        self.handler = CreativePrivateStorage(self.repo, self.storage)
        self.png = normalize_asset_image(encoded()).data
        self.manifest = CreativeManifest.from_normalized_png(
            CreativeIdentity("tenant1", "unit1", "campaign1", 1, str(uuid4())),
            self.png, provider="GEMINI_IMAGE", model="gemini-nano-banana-2.1",
            generation_request_id="request1")
        self.repo.claim(self.manifest, "key1", len(self.png))
        self.repo.transition(self.manifest.identity, CreativeStateTransition(
            CreativeState.RESERVED, CreativeState.GENERATING, 0))

    def test_upload_exactly_once_and_replay_only_observes(self):
        row = self.handler.upload(self.manifest, self.png)
        self.assertEqual(row["state"], "STORED")
        self.assertEqual(row["storage_generation"], "17")
        self.assertEqual(self.storage.uploads, 1)
        self.assertEqual(self.handler.upload(self.manifest, self.png), row)
        self.assertEqual(self.storage.uploads, 1)

    def test_uncertain_requires_observe_without_second_upload(self):
        self.storage.uncertain = True
        row = self.handler.upload(self.manifest, self.png)
        self.assertEqual(row["state"], "STORAGE_PENDING")
        self.assertEqual(self.storage.uploads, 1)
        self.assertEqual(self.handler.upload(self.manifest, self.png)["state"], "STORED")
        self.assertEqual(self.storage.uploads, 1)
        self.assertEqual(self.storage.observations, 1)

    def test_missing_after_uncertainty_does_not_retry_or_release_quota(self):
        self.storage.uncertain = True
        self.handler.upload(self.manifest, self.png)
        self.storage.saved = None
        self.assertEqual(self.handler.upload(self.manifest, self.png)["state"], "STORAGE_PENDING")
        self.assertEqual(self.storage.uploads, 1)
        self.assertEqual(self.repo.usage("tenant1"), len(self.png))

    def test_restart_recovers_without_original_png_or_second_post(self):
        self.storage.uncertain = True
        pending = self.handler.upload(self.manifest, self.png)
        self.assertEqual(pending["state"], "STORAGE_PENDING")
        recovered_db = Database(self.db._conn.execute("PRAGMA database_list").fetchone()[2])
        self.addCleanup(recovered_db.close)
        fresh = CreativePrivateStorage(CreativeRepository(recovered_db), self.storage)
        restored = fresh.reconcile_after_restart(self.manifest.identity)
        self.assertEqual(restored["state"], "STORED")
        self.assertEqual(restored["storage_generation"], "17")
        self.assertEqual(self.storage.uploads, 1)
        self.assertEqual(self.storage.observations, 1)

    def test_restart_missing_object_holds_quota_without_post(self):
        self.storage.uncertain = True
        self.handler.upload(self.manifest, self.png)
        self.storage.saved = None
        current = self.handler.reconcile_after_restart(self.manifest.identity)
        self.assertEqual(current["state"], "STORAGE_PENDING")
        self.assertEqual(self.repo.usage("tenant1"), len(self.png))
        self.assertEqual(self.storage.uploads, 1)

    def test_deletion_tombstones_and_never_resends_delete(self):
        self.handler.upload(self.manifest, self.png)
        result = self.handler.delete(self.manifest.identity)
        self.assertEqual(result["state"], "DELETED")
        self.assertEqual(self.storage.deletes, 1)
        self.assertEqual(self.repo.usage("tenant1"), 0)
        self.handler.delete(self.manifest.identity)
        self.assertEqual(self.storage.deletes, 1)

    def test_uncertain_delete_recovers_only_by_observation(self):
        self.handler.upload(self.manifest, self.png)
        self.storage.delete_uncertain = True
        self.assertEqual(self.handler.delete(self.manifest.identity)["state"], "DELETE_PENDING")
        self.assertEqual(self.storage.deletes, 1)
        self.assertEqual(self.handler.reconcile_delete(self.manifest.identity)["state"], "DELETED")
        self.assertEqual(self.storage.deletes, 1)

    def test_invalid_bytes_fail_before_dispatch(self):
        with self.assertRaises(AssetStorageError):
            self.handler.upload(self.manifest, self.png + b"x")
        self.assertEqual(self.storage.uploads, 0)
        self.assertEqual(self.repo.get(self.manifest.identity)["state"], "GENERATING")

    def test_external_io_never_runs_inside_f3_transaction(self):
        with self.db.transaction(), self.assertRaises(RuntimeError):
            self.handler.upload(self.manifest, self.png)
        self.assertEqual(self.storage.uploads, 0)

    def test_replay_mismatched_manifest_is_denied(self):
        other = CreativeManifest.from_normalized_png(
            self.manifest.identity, self.png, provider="DIFFERENT",
            model="gemini-nano-banana-2.1", generation_request_id="request1")
        with self.assertRaises(AssetStorageError):
            self.handler.upload(other, self.png)
        self.assertEqual(self.storage.uploads, 0)


if __name__ == "__main__":
    unittest.main()
