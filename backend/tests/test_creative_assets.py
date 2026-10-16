"""WP-R04-04B: pure manifest invariants (no network, storage or billing)."""
import hashlib
import unittest
from dataclasses import replace
from uuid import uuid4

from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode
from campaia_core.creative_assets import CreativeIdentity, CreativeManifest, CreativeStoredProof
from tests.test_asset_images import encoded
from campaia_core.asset_images import normalize_asset_image


def identity(**changes):
    return CreativeIdentity(**{**dict(tenant_id="tenant-a", business_unit_id="unit-a",
        campaign_id="campaign-a", campaign_version=1, creative_id=str(uuid4())), **changes})


def manifest(identity_value=None):
    data = normalize_asset_image(encoded()).data
    return CreativeManifest.from_normalized_png(identity_value or identity(), data,
        provider="GEMINI_IMAGE", model="gemini-nano-banana-2.1", generation_request_id="request-1"), data


class CreativeManifestTests(unittest.TestCase):
    def test_object_key_is_deterministic_and_opaque_with_full_scope(self):
        base = identity()
        key = base.object_name
        self.assertTrue(key.startswith("creative/v1/"))
        self.assertNotIn("tenant-a", key)
        self.assertNotIn("unit-a", key)
        self.assertNotIn("campaign-a", key)
        self.assertEqual(base.object_name, key)
        for updates in ({"tenant_id": "tenant-b"}, {"business_unit_id": "unit-b"},
                        {"campaign_id": "campaign-b"}, {"campaign_version": 2},
                        {"creative_id": str(uuid4())}):
            self.assertNotEqual(replace(base, **updates).object_name, key)

    def test_invalid_scopes_and_versions_are_fail_closed(self):
        for changes in ({"tenant_id": ""}, {"tenant_id": "\ud800"}, {"business_unit_id": " "},
                        {"campaign_id": ""}, {"campaign_version": True},
                        {"campaign_version": 0}, {"campaign_version": -1},
                        {"creative_id": "caller-file.png"}):
            with self.subTest(changes=repr(changes)), self.assertRaises(AssetStorageError):
                identity(**changes)

    def test_manifest_verifies_bytes_and_records_private_metadata(self):
        record, data = manifest()
        record.verify(data)
        self.assertEqual(record.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(record.size, len(data))
        meta = record.storage_metadata()
        self.assertEqual(meta["campaia_schema"], "generated_creative_v1")
        self.assertEqual(meta["campaign_version"], "1")
        self.assertNotIn("tenant-a", str(meta))
        self.assertNotIn("campaign-a", str(meta))
        self.assertNotIn("request-1", str(meta))
        with self.assertRaises(AssetStorageError) as caught:
            record.verify(data + b"x")
        self.assertEqual(caught.exception.code, AssetStorageErrorCode.INTEGRITY)

    def test_proof_requires_strict_storage_generation(self):
        record, _ = manifest()
        self.assertEqual(CreativeStoredProof(record, "123").storage_generation, "123")
        for value in ("0", "-1", "", "123x", 123, "1/2"):
            with self.subTest(value=value), self.assertRaises(AssetStorageError):
                CreativeStoredProof(record, value)

    def test_forged_manifest_rejects_wrong_hash_size_or_dimensions(self):
        record, _ = manifest()
        for changes in ({"sha256": "g" * 64}, {"size": 0},
                        {"width": True}, {"height": 9000}, {"generation_request_id": ""}):
            with self.subTest(changes=changes), self.assertRaises(AssetStorageError):
                replace(record, **changes)


if __name__ == "__main__":
    unittest.main()
