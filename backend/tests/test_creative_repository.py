"""Real SQLite F3 persistence tests; PostgreSQL migration/runtime not certified."""
import os
import tempfile
import threading
import unittest
from uuid import uuid4

from api.db import Database
from api.creative_repository import CreativeRepository
from campaia_core.asset_storage import AssetStorageError
from campaia_core.creative_assets import CreativeIdentity, CreativeManifest, CreativeState, CreativeStateTransition
from campaia_core.asset_images import normalize_asset_image
from tests.test_asset_images import encoded


def fixture(tenant="a", creative_id=None):
    identity = CreativeIdentity(tenant, "unit-1", "campaign-1", 1, creative_id or str(uuid4()))
    png = normalize_asset_image(encoded()).data
    return CreativeManifest.from_normalized_png(identity, png, provider="GEMINI_IMAGE",
         model="gemini-nano-banana-2.1", generation_request_id="req-1")


class CreativeRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "test.sqlite")
        self.db = Database(self.path)
        self.addCleanup(self.db.close)
        self.repo = CreativeRepository(self.db)

    def test_claim_replay_and_restart(self):
        m = fixture()
        first, replay = self.repo.claim(m, "key-1", m.size)
        self.assertFalse(replay)
        second, replay = self.repo.claim(m, "key-1", m.size)
        self.assertTrue(replay)
        self.assertEqual(first, second)
        self.db.close()
        reopened = Database(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(CreativeRepository(reopened).get(m.identity), first)
        with self.assertRaises(AssetStorageError):
            CreativeRepository(reopened).claim(m, "key-other", m.size)

    def test_quota_and_cross_tenant_are_atomic(self):
        m = fixture()
        other = fixture(tenant="b")
        self.repo.claim(m, "key", m.size)
        with self.assertRaises(AssetStorageError):
            self.repo.claim(fixture(), "key2", m.size)
        self.repo.claim(other, "key", other.size)
        self.assertEqual(self.repo.usage("a"), m.size)
        self.assertEqual(self.repo.usage("b"), other.size)
        forged = CreativeIdentity("b", m.identity.business_unit_id, m.identity.campaign_id,
                                 m.identity.campaign_version, m.identity.creative_id)
        with self.assertRaises(AssetStorageError):
            self.repo.get(forged)

    def test_concurrent_claim_has_one_winner(self):
        m1, m2 = fixture(), fixture()
        results = []
        barrier = threading.Barrier(2)
        def worker(m):
            barrier.wait()
            try:
                self.repo.claim(m, str(m.identity.creative_id), m.size)
                results.append("ok")
            except AssetStorageError:
                results.append("rejected")
        ts = [threading.Thread(target=worker, args=(m,)) for m in (m1,m2)]
        for t in ts: t.start()
        for t in ts: t.join(timeout=5)
        self.assertFalse(any(t.is_alive() for t in ts))
        self.assertEqual(sorted(results), ["ok", "rejected"])
        self.assertEqual(self.repo.usage("a"), m1.size)

    def test_transition_cas_replay_and_generation_proof(self):
        m = fixture()
        self.repo.claim(m, "key", m.size)
        for before, after, revision in [
            (CreativeState.RESERVED, CreativeState.GENERATING, 0),
            (CreativeState.GENERATING, CreativeState.STORAGE_PENDING, 1),
        ]:
            self.repo.transition(m.identity, CreativeStateTransition(before, after, revision))
        with self.assertRaises(AssetStorageError):
            self.repo.transition(m.identity, CreativeStateTransition(CreativeState.GENERATING, CreativeState.STORAGE_PENDING, 1))
        with self.assertRaises(AssetStorageError):
            self.repo.transition(m.identity, CreativeStateTransition(CreativeState.STORAGE_PENDING, CreativeState.STORED, 2))
        stored = self.repo.transition(m.identity, CreativeStateTransition(CreativeState.STORAGE_PENDING, CreativeState.STORED, 2), storage_generation="123")
        self.assertEqual(stored["storage_generation"], "123")
        self.assertEqual(stored["revision"], 3)


if __name__ == "__main__":
    unittest.main()
