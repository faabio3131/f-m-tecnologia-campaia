from __future__ import annotations

import base64
import unittest
from unittest.mock import Mock, patch

from campaia_core.asset_storage import (
    AssetIdentity, AssetManifest, AssetStorageError, AssetStorageErrorCode as Code,
    DisabledAssetStorage, MAX_ASSET_BYTES, PNG_SIGNATURE, StoredAsset,
)
from campaia_core.gcs_asset_storage import GCSAssetConfig, configured_asset_storage

ASSET_ID = "a9f72ebe-f5aa-4c10-a61c-244e62cb825a"
# Transport fixture, deliberately NOT an image-validation certification.
DATA = PNG_SIGNATURE + b"transport fixture"
IDENTITY = AssetIdentity("tenant-a", "bp-brand", ASSET_ID)
MANIFEST = AssetManifest.from_normalized_png(IDENTITY, DATA)


class AssetStorageContractTests(unittest.TestCase):
    def test_object_namespace_isolates_tenant_profile_and_asset(self):
        objects = {
            AssetIdentity("tenant-a", "bp-brand", ASSET_ID).object_name,
            AssetIdentity("tenant-b", "bp-brand", ASSET_ID).object_name,
            AssetIdentity("tenant-a", "bp-other", ASSET_ID).object_name,
            AssetIdentity("tenant-a", "bp-brand", "1f09496b-b779-44c5-ad4c-26f49d7d2c76").object_name,
        }
        self.assertEqual(len(objects), 4)
        self.assertNotIn("tenant-a", IDENTITY.object_name)
        self.assertNotIn("bp-brand", IDENTITY.object_name)
        self.assertEqual(IDENTITY.object_name.count("/"), 4)

    def test_no_caller_selected_filename_or_object_path(self):
        for asset_id in ("../secret", ASSET_ID.upper(), "https://evil.invalid/x", "", None):
            with self.subTest(asset_id=asset_id), self.assertRaises(AssetStorageError):
                AssetIdentity("tenant-a", "bp-brand", asset_id)
        for owner in ("", " ", None, 1, "a" * 257):
            with self.subTest(owner=owner), self.assertRaises(AssetStorageError):
                AssetIdentity(owner, "bp-brand", ASSET_ID)

    def test_manifest_is_bounded_and_strict(self):
        for data in (b"", PNG_SIGNATURE, b"<svg>image</svg>", DATA.decode("latin1"),
                     PNG_SIGNATURE + b"x" * MAX_ASSET_BYTES):
            with self.subTest(size=len(data)), self.assertRaises(AssetStorageError):
                AssetManifest.from_normalized_png(IDENTITY, data)
        for size in (True, 9.0, 0, MAX_ASSET_BYTES + 1):
            with self.subTest(size=size), self.assertRaises(AssetStorageError):
                AssetManifest(IDENTITY, size, MANIFEST.sha256, MANIFEST.md5_base64)
        for generation in ("0", "-1", "1.0", 42, True, "", "a", "1" * 26):
            with self.subTest(generation=generation), self.assertRaises(AssetStorageError):
                StoredAsset(MANIFEST, generation)

    def test_manifest_rejects_invalid_digest_or_checksum(self):
        for sha, md5 in (("A" * 64, MANIFEST.md5_base64), ("abc", MANIFEST.md5_base64),
                         (MANIFEST.sha256, "invalid"),
                         (MANIFEST.sha256, base64.b64encode(b"too short").decode())):
            with self.assertRaises(AssetStorageError):
                AssetManifest(IDENTITY, len(DATA), sha, md5)

    def test_content_digest_not_just_length_or_prefix(self):
        MANIFEST.verify_bytes(DATA)
        with self.assertRaises(AssetStorageError) as caught:
            MANIFEST.verify_bytes(DATA[:-1] + b"X")
        self.assertEqual(caught.exception.code, Code.INTEGRITY)

    def test_defaults_and_disabled_capability_never_discover_credentials(self):
        with patch("google.auth.default", side_effect=AssertionError("must not discover ADC")) as adc:
            storage = configured_asset_storage({})
            asset = StoredAsset(MANIFEST, "12345")
            self.assertIsInstance(storage, DisabledAssetStorage)
            for call in (
                lambda: storage.upload_once(MANIFEST, DATA), lambda: storage.observe(MANIFEST),
                lambda: storage.read(asset), lambda: storage.delete_once(asset),
            ):
                with self.assertRaises(AssetStorageError) as caught:
                    call()
                self.assertEqual(caught.exception.code, Code.DISABLED)
            adc.assert_not_called()

    def test_explicit_configuration_requires_bucket_and_operational_budget(self):
        base = {"CAMPAIA_ASSET_STORAGE_ENABLED": "true",
                "CAMPAIA_ASSET_BUCKET": "fixture-assets",
                "CAMPAIA_ASSET_MAX_ACTIVE_BYTES": "5242880"}
        self.assertEqual(GCSAssetConfig.from_env(base).max_active_bytes, MAX_ASSET_BYTES)
        for key, bad in (("CAMPAIA_ASSET_STORAGE_ENABLED", "TRUE"),
                         ("CAMPAIA_ASSET_MAX_ACTIVE_BYTES", "0"),
                         ("CAMPAIA_ASSET_MAX_ACTIVE_BYTES", "1.5"),
                         ("CAMPAIA_ASSET_MAX_ACTIVE_BYTES", "-1"),
                         ("CAMPAIA_ASSET_BUCKET", "https://evil.invalid"),
                         ("CAMPAIA_ASSET_BUCKET", "bucket/path")):
            with self.subTest(key=key, bad=bad), self.assertRaises(AssetStorageError):
                GCSAssetConfig.from_env({**base, key: bad})
        for missing in ("CAMPAIA_ASSET_BUCKET", "CAMPAIA_ASSET_MAX_ACTIVE_BYTES"):
            env = dict(base)
            del env[missing]
            with self.assertRaises(AssetStorageError):
                GCSAssetConfig.from_env(env)

    def test_enabled_adapter_construction_is_lazy(self):
        with patch("google.auth.default", side_effect=AssertionError("no ADC")) as adc:
            configured_asset_storage({"CAMPAIA_ASSET_STORAGE_ENABLED": "true",
                                      "CAMPAIA_ASSET_BUCKET": "fixture-assets",
                                      "CAMPAIA_ASSET_MAX_ACTIVE_BYTES": "5242880"})
            adc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
