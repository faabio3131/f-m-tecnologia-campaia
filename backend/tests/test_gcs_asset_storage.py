from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

import httpx

from campaia_core.asset_storage import (
    AssetIdentity, AssetManifest, AssetStorageError, AssetStorageErrorCode as Code,
    PNG_SIGNATURE, StoredAsset,
)
from campaia_core.gcs_asset_storage import GCSAssetConfig, GCSAssetStorage, LazyGoogleToken

IDENTITY = AssetIdentity("tenant-a", "bp-brand", "a9f72ebe-f5aa-4c10-a61c-244e62cb825a")
DATA = PNG_SIGNATURE + b"transport fixture"
MANIFEST = AssetManifest.from_normalized_png(IDENTITY, DATA)
ASSET = StoredAsset(MANIFEST, "12345")
CONFIG = GCSAssetConfig("fixture-assets", 5 * 1024 * 1024, enabled=True)


def metadata(manifest=MANIFEST, **overrides):
    return {
        "bucket": CONFIG.bucket, "name": manifest.identity.object_name,
        "generation": "12345", "contentType": "image/png",
        "size": str(manifest.size), "md5Hash": manifest.md5_base64,
        "cacheControl": "private, no-store",
        "metadata": manifest.identity.tags(manifest.sha256), **overrides,
    }


def adapter(handler, *, token=None, config=CONFIG):
    return GCSAssetStorage(config, token_provider=token or Mock(return_value="fixture-token"),
                           transport=httpx.MockTransport(handler))


class GCSAssetStorageTests(unittest.TestCase):
    def test_upload_one_multipart_request_without_overwrite_or_acl(self):
        seen = []
        def handler(request):
            seen.append(request)
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.scheme, "https")
            self.assertEqual(request.url.host, "storage.googleapis.com")
            self.assertEqual(request.url.path, "/upload/storage/v1/b/fixture-assets/o")
            self.assertEqual(dict(request.url.params), {"uploadType": "multipart", "ifGenerationMatch": "0"})
            self.assertEqual(request.headers["Authorization"], "Bearer fixture-token")
            content_type = request.headers["Content-Type"]
            boundary = content_type.split("boundary=")[1].encode()
            parts = request.content.split(b"--" + boundary)
            facts = json.loads(parts[1].split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n"))
            self.assertEqual(facts["metadata"], IDENTITY.tags(MANIFEST.sha256))
            self.assertEqual(facts["md5Hash"], MANIFEST.md5_base64)
            self.assertEqual(facts["cacheControl"], "private, no-store")
            self.assertNotIn("acl", facts)
            self.assertNotIn("predefinedAcl", request.url.params)
            self.assertEqual(parts[2].split(b"\r\n\r\n", 1)[1], DATA + b"\r\n")
            return httpx.Response(200, json=metadata())
        self.assertEqual(adapter(handler).upload_once(MANIFEST, DATA), ASSET)
        self.assertEqual(len(seen), 1)

    def test_integrity_checks_every_expected_metadata_fact(self):
        bad_values = {
            "bucket": "other-bucket", "name": "foreign/object",
            "generation": True, "contentType": "text/html", "size": MANIFEST.size,
            "md5Hash": "wrong", "cacheControl": "public, max-age=3600",
            "metadata": {**IDENTITY.tags(MANIFEST.sha256), "tenant_sha256": "foreign"},
            "contentEncoding": "gzip",
        }
        for key, value in bad_values.items():
            with self.subTest(key=key):
                storage = adapter(lambda request: httpx.Response(200, json=metadata(**{key: value})))
                with self.assertRaises(AssetStorageError) as caught:
                    storage.observe(MANIFEST)
                self.assertEqual(caught.exception.code, Code.INTEGRITY)

    def test_other_tenant_profile_or_asset_cannot_be_misbound(self):
        for identity in (
            AssetIdentity("tenant-b", "bp-brand", IDENTITY.asset_id),
            AssetIdentity("tenant-a", "bp-other", IDENTITY.asset_id),
            AssetIdentity("tenant-a", "bp-brand", "1f09496b-b779-44c5-ad4c-26f49d7d2c76"),
        ):
            other = AssetManifest.from_normalized_png(identity, DATA)
            with self.assertRaises(AssetStorageError) as caught:
                adapter(lambda request: httpx.Response(200, json=metadata())).observe(other)
            self.assertEqual(caught.exception.code, Code.INTEGRITY)

    def test_observe_generation_and_encoded_object_path(self):
        def handler(request):
            self.assertIn(b"%2F", request.url.raw_path)
            self.assertEqual(request.url.params["generation"], "12345")
            self.assertEqual(request.url.params["projection"], "noAcl")
            return httpx.Response(200, json=metadata())
        self.assertEqual(adapter(handler).observe(MANIFEST, "12345"), ASSET)
        with self.assertRaises(AssetStorageError):
            adapter(lambda request: httpx.Response(200, json=metadata(generation="67890"))).observe(MANIFEST, "12345")

    def test_404_is_only_absence_observation_not_a_retry_permission(self):
        calls = []
        storage = adapter(lambda request: calls.append(request.method) or httpx.Response(404))
        self.assertIsNone(storage.observe(MANIFEST))
        self.assertEqual(calls, ["GET"])

    def test_read_pins_both_metadata_and_bytes_and_checks_digest(self):
        calls = []
        def handler(request):
            calls.append(request)
            self.assertEqual(request.url.params["generation"], "12345")
            if request.url.params.get("alt") == "media":
                self.assertEqual(request.url.params["ifGenerationMatch"], "12345")
                return httpx.Response(200, content=DATA)
            return httpx.Response(200, json=metadata())
        self.assertEqual(adapter(handler).read(ASSET), DATA)
        self.assertEqual([r.method for r in calls], ["GET", "GET"])

    def test_read_corruption_and_replacement_fail_closed(self):
        for media in (DATA[:-1] + b"X", DATA + b"extra", DATA[:-1]):
            def handler(request):
                return (httpx.Response(200, content=media) if request.url.params.get("alt") == "media"
                        else httpx.Response(200, json=metadata()))
            with self.subTest(size=len(media)), self.assertRaises(AssetStorageError):
                adapter(handler).read(ASSET)
        seen = []
        def replaced(request):
            seen.append(request)
            return httpx.Response(200, json=metadata(generation="67890"))
        with self.assertRaises(AssetStorageError):
            adapter(replaced).read(ASSET)
        self.assertEqual(len(seen), 1)

    def test_delete_is_one_conditional_request_with_no_retention_claim(self):
        calls = []
        def handler(request):
            calls.append(request)
            self.assertEqual(request.method, "DELETE")
            self.assertEqual(dict(request.url.params), {"generation": "12345", "ifGenerationMatch": "12345"})
            self.assertEqual(request.content, b"")
            return httpx.Response(204)
        self.assertIsNone(adapter(handler).delete_once(ASSET))
        self.assertEqual(len(calls), 1)

    def test_timeout_never_retries_mutation_and_recovery_is_get_only(self):
        calls = []
        def lost_response(request):
            calls.append(request.method)
            raise httpx.ReadTimeout("sensitive-provider-response", request=request)
        storage = adapter(lost_response)
        for mutate in (lambda: storage.upload_once(MANIFEST, DATA), lambda: storage.delete_once(ASSET)):
            with self.assertRaises(AssetStorageError) as caught:
                mutate()
            self.assertEqual(caught.exception.code, Code.UNCERTAIN)
            self.assertNotIn("sensitive", str(caught.exception))
        self.assertEqual(calls, ["POST", "DELETE"])
        # A fresh adapter can reconcile the previously persisted manifest/generation.
        recovery = adapter(lambda request: calls.append(request.method) or httpx.Response(200, json=metadata()))
        self.assertEqual(recovery.observe(MANIFEST), ASSET)
        self.assertEqual(calls, ["POST", "DELETE", "GET"])

    def test_http_statuses_do_not_expose_response_or_retry(self):
        for status, code in ((401, Code.AUTH), (403, Code.AUTH), (409, Code.CONFLICT),
                             (412, Code.CONFLICT), (429, Code.UNCERTAIN), (500, Code.UNCERTAIN),
                             (302, Code.UNCERTAIN), (400, Code.UNCERTAIN)):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, content=b"secret-body", headers={"Location": "https://evil.invalid"})
            with self.subTest(status=status), self.assertRaises(AssetStorageError) as caught:
                adapter(handler).upload_once(MANIFEST, DATA)
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(len(calls), 1)
            self.assertNotIn("secret", str(caught.exception))

    def test_response_size_and_encoding_bounds(self):
        responses = [
            httpx.Response(200, content=b"x" * (64 * 1024 + 1)),
            httpx.Response(200, content=b"{}", headers={"Content-Length": "99999999"}),
            httpx.Response(200, content=b"{}", headers={"Content-Length": "not-an-int"}),
            httpx.Response(200, content=b"{}"),
            httpx.Response(200, content=b"not json"),
            httpx.Response(200, json=[]),
        ]
        responses[3].headers["Content-Encoding"] = "br"
        for response in responses:
            with self.subTest(headers=dict(response.headers)), self.assertRaises(AssetStorageError):
                adapter(lambda request: response).observe(MANIFEST)

    def test_invalid_input_disabled_and_invalid_token_never_reach_http(self):
        handler = Mock(side_effect=AssertionError("must not call HTTP"))
        token = Mock(return_value="fixture-token")
        with self.assertRaises(AssetStorageError):
            adapter(handler, token=token).upload_once(MANIFEST, DATA[:-1] + b"X")
        token.assert_not_called()
        disabled = GCSAssetConfig(CONFIG.bucket, CONFIG.max_active_bytes)
        with self.assertRaises(AssetStorageError) as caught:
            adapter(handler, token=token, config=disabled).observe(MANIFEST)
        self.assertEqual(caught.exception.code, Code.DISABLED)
        token.assert_not_called()
        for bad in ("bad\r\nInjected: yes", "", None):
            with self.assertRaises(AssetStorageError) as caught:
                adapter(handler, token=Mock(return_value=bad)).observe(MANIFEST)
            self.assertEqual(caught.exception.code, Code.AUTH)
        handler.assert_not_called()

    def test_operational_object_limit_before_token(self):
        token = Mock(return_value="fixture-token")
        storage = adapter(Mock(), token=token, config=GCSAssetConfig(CONFIG.bucket, 9, True))
        with self.assertRaises(AssetStorageError):
            storage.upload_once(MANIFEST, DATA)
        token.assert_not_called()

    def test_adc_is_lazy_and_auth_failures_redacted(self):
        with patch("google.auth.default", side_effect=RuntimeError("secret-credential-path")) as adc:
            token = LazyGoogleToken()
            adc.assert_not_called()
            with self.assertRaises(AssetStorageError) as caught:
                token()
            self.assertEqual(str(caught.exception), "AUTH")
            self.assertNotIn("secret", str(caught.exception))
            adc.assert_called_once()


if __name__ == "__main__":
    unittest.main()
