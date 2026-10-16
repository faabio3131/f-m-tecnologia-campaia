from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import io
import unittest
from unittest.mock import patch

from PIL import Image
from starlette.testclient import TestClient

from api.main import create_app
from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code
from tests_support.asset_storage import TestOnlyAssetStorage
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_brand_versions import BODY
from tests_api.test_helpers import OWNER, OTHER_OWNER, VIEWER, unique_idem


def png(color="red"):
    stream = io.BytesIO()
    Image.new("RGB", (3, 2), color).save(stream, format="PNG")
    return stream.getvalue()


class BrandAssetTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.storage = TestOnlyAssetStorage()
        self.state.asset_storage = self.storage
        result = self.client.post("/brand-profiles", headers={**OWNER, **unique_idem()}, json=BODY)
        self.assertEqual(result.status_code, 201)
        self.brand = result.json()["id"]
        self.base = "/brand-profiles/" + self.brand + "/assets"

    def upload(self, *, client=None, headers=None, data=None, kind="LOGO", base=None):
        return (client or self.client).post((base or self.base) + "?kind=" + kind,
            headers={**(headers or {**OWNER, **unique_idem()}), "Content-Type": "application/octet-stream"},
            content=png() if data is None else data)

    def peer(self):
        client = TestClient(create_app(env="test", db_path=str(self.path)))
        client.app.state.campaia.asset_storage = self.storage
        self.addCleanup(client.app.state.campaia.db._conn.close)
        return client

    def remove(self, asset, headers=None, client=None):
        return (client or self.client).delete(self.base + "/" + asset,
            headers=headers or {**OWNER, **unique_idem()})

    def recover(self, asset, headers=None, client=None):
        return (client or self.client).post(self.base + "/" + asset + "/reconcile",
            headers=headers or {**OWNER, **unique_idem()})

    def read(self, asset, headers=OWNER, client=None):
        return (client or self.client).get(self.base + "/" + asset + "/content", headers=headers)

    def test_upload_private_read_metadata_delete_and_quota(self):
        result = self.upload()
        self.assertEqual(result.status_code, 201, result.text)
        item = result.json()
        self.assertEqual(item["status"], "READY")
        self.assertEqual((item["width"], item["height"]), (3, 2))
        self.assertEqual(item["content_url"], "/api/campaia" + self.base + "/" + item["id"] + "/content")
        self.assertEqual(set(item), {"id", "brand_profile_id", "kind", "status", "width", "height",
                                    "size_bytes", "content_type", "created_at", "updated_at", "content_url"})
        page = self.client.get(self.base, headers=OWNER).json()
        self.assertEqual(page["capability"]["mode"], "SIMULATOR")
        self.assertEqual(page["capability"]["used_bytes"], item["size_bytes"])
        content = self.read(item["id"], headers=VIEWER)
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.headers["Cache-Control"], "private, no-store")
        self.assertEqual(content.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(content.headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertEqual(content.headers["Content-Type"], "image/png")
        self.assertEqual(Image.open(io.BytesIO(content.content)).size, (3, 2))
        removed = self.remove(item["id"])
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(removed.json()["status"], "DELETED")
        self.assertEqual(self.read(item["id"]).status_code, 404)
        page = self.client.get(self.base, headers=OWNER).json()
        self.assertEqual(page["items"], [])
        self.assertEqual(page["capability"]["used_bytes"], 0)
        self.assertEqual(self.storage.calls.count("POST"), 1)
        self.assertEqual(self.storage.calls.count("DELETE"), 1)

    def test_upload_replay_after_deletion_does_not_recreate_the_object(self):
        headers = {**OWNER, **unique_idem()}
        item = self.upload(headers=headers).json()
        self.assertEqual(self.remove(item["id"]).status_code, 200)
        replay = self.upload(headers=headers)
        self.assertEqual(replay.status_code, 409, replay.text)
        self.assertEqual(replay.json()["code"], "ASSET_REMOVED")
        self.assertEqual(self.storage.calls.count("POST"), 1)

    def test_default_disabled_never_accesses_adc(self):
        from campaia_core.asset_storage import DisabledAssetStorage
        self.state.asset_storage = DisabledAssetStorage()
        with patch("google.auth.default", side_effect=AssertionError("must not discover")) as adc:
            self.assertFalse(self.client.get(self.base, headers=OWNER).json()["capability"]["enabled"])
            self.assertEqual(self.upload().status_code, 503)
            adc.assert_not_called()

    def test_auth_rbac_and_cross_tenant_precede_body_decoder_and_provider(self):
        with patch("api.routes_brand_assets.normalize_asset_image", side_effect=AssertionError("must not decode")) as decode:
            self.assertEqual(self.upload(headers=unique_idem()).status_code, 401)
            self.assertEqual(self.upload(headers={**VIEWER, **unique_idem()}).status_code, 403)
            self.assertEqual(self.upload(headers={**OTHER_OWNER, **unique_idem()}).status_code, 404)
            self.assertEqual(self.client.get(self.base, headers=OTHER_OWNER).status_code, 404)
            decode.assert_not_called()
        self.assertEqual(self.storage.calls, [])
        item = self.upload().json()
        before = list(self.storage.calls)
        for call in (lambda: self.read(item["id"], OTHER_OWNER),
                     lambda: self.remove(item["id"], {**OTHER_OWNER, **unique_idem()}),
                     lambda: self.recover(item["id"], {**OTHER_OWNER, **unique_idem()})):
            self.assertEqual(call().status_code, 404)
        self.assertEqual(self.storage.calls, before)
        self.assertEqual(self.remove(item["id"], {**VIEWER, **unique_idem()}).status_code, 403)

    def test_replay_is_actor_unit_body_kind_and_profile_bound(self):
        headers = {**OWNER, **unique_idem()}
        first = self.upload(headers=headers)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.upload(headers=headers).json(), first.json())
        self.assertEqual(self.upload(headers=headers, data=png("blue")).status_code, 409)
        self.assertEqual(self.upload(headers=headers, kind="REFERENCE").status_code, 409)
        other = self.client.post("/brand-profiles", headers={**OWNER, **unique_idem()}, json=BODY).json()["id"]
        self.assertEqual(self.upload(headers=headers, base="/brand-profiles/" + other + "/assets").status_code, 409)
        owner = self.state.tokens["demo-owner-token"]
        for token, principal in (("asset-peer", replace(owner, user_id="peer")),
                                 ("asset-unit", replace(owner, business_unit_id="other-unit"))):
            self.state.tokens[token] = principal
            self.assertEqual(self.upload(headers={**headers, "Authorization": "Bearer " + token}).status_code, 409)
        self.assertEqual(self.storage.calls.count("POST"), 1)
        self.assertEqual(len(self.state.asset_store.rows("demo-tenant")), 1)

    def test_response_lost_then_restart_recovers_without_second_upload(self):
        original = self.storage.upload_once
        def lost(manifest, data):
            original(manifest, data)
            raise AssetStorageError(Code.UNCERTAIN)
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.storage, "upload_once", side_effect=lost):
            pending = self.upload(headers=headers)
        self.assertEqual(pending.status_code, 202, pending.text)
        self.assertEqual(pending.json()["status"], "UPLOAD_UNCERTAIN")
        self.assertIsNone(pending.json()["content_url"])
        self.assertEqual(self.read(pending.json()["id"]).status_code, 404)
        peer = self.peer()
        restored = self.upload(headers=headers, client=peer)
        self.assertEqual(restored.status_code, 201, restored.text)
        self.assertEqual(restored.json()["id"], pending.json()["id"])
        self.assertEqual(restored.json()["status"], "READY")
        self.assertEqual(self.storage.calls.count("POST"), 1)

    def test_crash_before_dispatch_holds_quota_and_never_redispatches_on_404(self):
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.storage, "upload_once", side_effect=RuntimeError("crash before dispatch")):
            with self.assertRaisesRegex(RuntimeError, "crash before dispatch"):
                self.upload(headers=headers)
        rows = self.state.asset_store.rows("demo-tenant")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "UPLOADING")
        self.assertGreater(self.state.asset_store.usage("demo-tenant"), 0)
        peer = self.peer()
        result = self.upload(headers=headers, client=peer)
        self.assertEqual(result.status_code, 202, result.text)
        self.assertEqual(self.storage.calls, ["GET"])
        self.assertEqual(self.remove(rows[0]["asset_id"]).status_code, 409)

    def test_concurrent_nonce_or_quota_has_one_winner(self):
        peer = self.peer()
        self.storage.max_active_bytes = len(png())
        # Normalized fresh PNG has the same size for this fixture.
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda client: self.upload(client=client), [self.client, peer]))
        self.assertEqual(sorted(result.status_code for result in results), [201, 409], [r.text for r in results])
        self.assertEqual(self.storage.calls.count("POST"), 1)
        self.assertEqual(len(self.state.asset_store.rows("demo-tenant")), 1)

    def test_concurrent_same_nonce_dispatches_once(self):
        peer = self.peer()
        headers = {**OWNER, **unique_idem()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda client: self.upload(client=client, headers=headers), [self.client, peer]))
        self.assertTrue(all(r.status_code in (201, 202) for r in results), [r.text for r in results])
        self.assertEqual(len({r.json()["id"] for r in results}), 1)
        self.assertEqual(self.storage.calls.count("POST"), 1)

    def test_delete_tombstones_before_effect_and_uncertainty_only_gets_recovery(self):
        item = self.upload().json()
        original = self.storage.delete_once
        def lost(asset):
            self.assertEqual(self.read(item["id"]).status_code, 404)
            original(asset)
            raise AssetStorageError(Code.UNCERTAIN)
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.storage, "delete_once", side_effect=lost):
            deleted = self.remove(item["id"], headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json()["status"], "DELETED")
        peer = self.peer()
        self.assertEqual(self.remove(item["id"], headers, peer).status_code, 200)
        self.assertEqual(self.storage.calls.count("DELETE"), 1)
        self.assertEqual(sum(e.action == "BRAND_ASSET_DELETE_REQUESTED"
            for e in self.state.audit.list_for_tenant("demo-tenant")), 1)

    def test_failed_delete_stays_hidden_holds_quota_and_is_not_retried(self):
        item = self.upload().json()
        def blocked(asset):
            self.storage.calls.append("DELETE")
            raise AssetStorageError(Code.UNCERTAIN)
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.storage, "delete_once", side_effect=blocked):
            pending = self.remove(item["id"], headers)
        self.assertEqual(pending.status_code, 202, pending.text)
        self.assertEqual(pending.json()["status"], "DELETE_UNCERTAIN")
        self.assertEqual(self.read(item["id"]).status_code, 404)
        self.assertEqual(self.state.asset_store.usage("demo-tenant"), item["size_bytes"])
        self.assertEqual(self.remove(item["id"], headers).status_code, 202)
        self.assertEqual(self.recover(item["id"]).json()["status"], "DELETE_UNCERTAIN")
        self.assertEqual(self.storage.calls.count("DELETE"), 1)

    def test_namespace_change_and_corruption_fail_closed(self):
        item = self.upload().json()
        self.state.asset_storage = TestOnlyAssetStorage()
        self.assertEqual(self.read(item["id"]).status_code, 409)
        self.assertEqual(self.remove(item["id"]).status_code, 409)
        self.state.asset_storage = self.storage
        path = next(iter(self.storage.objects))
        asset, data = self.storage.objects[path]
        self.storage.objects[path] = (asset, data[:-1] + b"x")
        self.assertEqual(self.read(item["id"]).status_code, 503)

    def test_invalid_input_rate_and_busy_do_not_claim_or_contact_storage(self):
        self.assertEqual(self.upload(data=b"<svg/>").status_code, 422)
        self.assertEqual(self.upload(kind="OTHER").status_code, 422)
        self.assertEqual(self.upload(data=b"x" * (5 * 1024 * 1024 + 1)).status_code, 413)
        self.assertEqual(self.state.asset_store.rows("demo-tenant"), [])
        self.assertEqual(self.storage.calls, [])
        self.state.asset_upload_slots.acquire()
        self.state.asset_upload_slots.acquire()
        try:
            self.assertEqual(self.upload().status_code, 429)
        finally:
            self.state.asset_upload_slots.release()
            self.state.asset_upload_slots.release()
        for _ in range(30):
            self.state.asset_rate_limiter.allow("demo-tenant", now=datetime.now(timezone.utc))
        self.assertEqual(self.upload().status_code, 429)

    def test_metadata_commit_failure_after_cloud_write_recovers_without_duplicate(self):
        headers = {**OWNER, **unique_idem()}
        original = self.state.audit.append
        def fail(**event):
            original(**event)
            if event["action"] == "BRAND_ASSET_READY":
                raise RuntimeError("injected asset commit")
        with patch.object(self.state.audit, "append", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "injected asset commit"):
                self.upload(headers=headers)
        self.assertEqual(self.state.asset_store.rows("demo-tenant")[0]["status"], "UPLOADING")
        self.assertEqual(self.upload(headers=headers).status_code, 201)
        self.assertEqual(self.storage.calls.count("POST"), 1)


if __name__ == "__main__":
    unittest.main()
