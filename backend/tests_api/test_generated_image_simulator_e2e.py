"""F7 image API lifecycle on explicit fake provider/GCS; never real homologation."""
import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from campaia_core.ai_gateway import AITask, CostObservation, ProviderResponse
from campaia_core.asset_images import normalize_asset_image
from tests.test_asset_images import encoded
from tests_support.asset_storage import TestOnlyAssetStorage
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, unique_idem


class SimImageProvider:
    name = "GEMINI_IMAGE"
    def __init__(self, png):
        self.png = png
        self.calls = 0
    def supports(self, task):
        return task is AITask.GENERATE_IMAGE
    def generate(self, request):
        self.calls += 1
        return ProviderResponse(
            output={"mime_type": "image/png", "data_base64": base64.b64encode(self.png).decode(),
                    "width": 1, "height": 1},
            cost_units=Decimal("0.000001"), latency_ms=1, model="gemini-nano-banana-2.1",
            cost_observation=CostObservation("SIMULATED", Decimal("0.000001")),
        )


class ImageApiSimulationTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        # The explicit F3 internal cost ceiling is a test fixture, never a production default.
        os.environ["CAMPAIA_IMAGE_MAX_COST_UNITS"] = "1"
        # Explicit contract snapshot: commercial action image = 15 credits for test.
        catalog_file = self.path.parent / "catalog.json"
        catalog = json.loads(catalog_file.read_text())
        for plan in catalog:
            plan["credit_policy"]["action_weights"]["image"] = 15
        catalog_file.write_text(json.dumps(catalog))
        png = normalize_asset_image(encoded()).data
        from campaia_core.asset_images import verify_normalized_png
        checked = verify_normalized_png(png)
        self.fake = SimImageProvider(png)
        # Provider fixture is visibly SIMULATED: no Google account or external GCS.
        original_generate = self.fake.generate
        def with_dimensions(request):
            result = original_generate(request)
            result.output.update(width=checked.width, height=checked.height)
            return result
        self.fake.generate = with_dimensions
        self.storage = TestOnlyAssetStorage()
        self.cloud = patch("campaia_core.gcs_asset_storage.configured_asset_storage", return_value=self.storage)
        self.cloud.start()
        self.addCleanup(self.cloud.stop)
        brief = self.client.post("/briefs", headers={**OWNER, **unique_idem()},
            json={"objective": "Campanha visual", "product": "Produto de teste",
                  "audience": "Adultos", "total_budget": "100", "daily_cap": "10"})
        self.assertEqual(brief.status_code, 202, brief.text)
        self.campaign = brief.json()["id"]
        plan = self.client.post("/campaigns/" + self.campaign + "/plan/regenerate",
            headers={**OWNER, **unique_idem()}, json={})
        self.assertEqual(plan.status_code, 202, plan.text)
        self.state.ai_gateway.providers.append(self.fake)
        self.state.ai_gateway.ledger.set_cap("demo-tenant", Decimal("1000"))
        self.state.image_provider = SimpleNamespace(config=SimpleNamespace(
            enabled=True, model="gemini-nano-banana-2.1"))
        self.setup_subscription(trial=True)
        self.base = "/campaigns/" + self.campaign + "/images"

    def test_independent_review_revocation_is_terminal_and_idempotent(self):
        from tests_api.test_helpers import APPROVER, with_step_up
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        body = {"expected_plan_version": version, "prompt": "Criativo teste de revogação governada",
                "credit_confirmation": {field: quote[field] for field in
                    ("cycle_id", "policy_version", "credits", "extra_amount")}}
        created = self.client.post(self.base, headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(created.status_code, 201, created.text)
        asset_id = created.json()["id"]
        row = self.state.db.table("creative_assets").get_for_tenant(asset_id, "demo-tenant")
        binding = {"expected_sha256": row["manifest"]["sha256"],
                   "expected_generation": row["storage_generation"]}
        route = self.base + "/" + asset_id + "/review"
        denial = self.client.post(route, headers={**with_step_up(OWNER), **unique_idem()},
                                  json={**binding, "decision": "APPROVE"})
        self.assertNotIn(denial.status_code, (200, 201), denial.text)
        approved = self.client.post(route, headers={**with_step_up(APPROVER), **unique_idem()},
                                    json={**binding, "decision": "APPROVE"})
        self.assertEqual(approved.status_code, 200, approved.text)
        revoke_headers = {**with_step_up(APPROVER), **unique_idem()}
        reason = {**binding, "reason": "Cancelamento humano comprovado"}
        revoked = self.client.post(route + "/revoke", headers=revoke_headers, json=reason)
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json()["decision"], "REVOKED")
        replay = self.client.post(route + "/revoke", headers=revoke_headers, json=reason)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertTrue(replay.json()["replayed"])
        forbidden = self.client.post(route, headers={**with_step_up(APPROVER), **unique_idem()},
                                     json={**binding, "decision": "APPROVE"})
        self.assertEqual(forbidden.status_code, 409, forbidden.text)
        preview = self.client.get(self.base + "/" + asset_id + "/preview", headers=OWNER)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["policy"]["human_review"], "REVOKED")
        self.assertFalse(preview.json()["policy"]["publication_allowed"])

    def test_selected_story_format_rejects_mismatched_provider_without_storage_or_credits(self):
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        body = {"expected_plan_version": version, "prompt": "Arte story vertical para testes",
                "image_format": "STORY_9_16",
                "credit_confirmation": {field: quote[field] for field in
                    ("cycle_id", "policy_version", "credits", "extra_amount")}}
        before = self.usage().json()["balance"]["consumed_credits"]
        response = self.client.post(self.base, headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["code"], "AI_FORMAT_MISMATCH")
        self.assertEqual(self.storage.calls.count("POST"), 0)
        self.assertEqual(self.usage().json()["balance"]["consumed_credits"], before)

    def test_manual_upload_is_private_idempotent_and_free_of_ai_dispatch(self):
        from tests_api.test_helpers import with_step_up
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        png = normalize_asset_image(encoded()).data
        body = {"expected_plan_version": version,
                "image_base64": base64.b64encode(png).decode()}
        url = self.base + "/manual-upload"
        headers = {**with_step_up(OWNER), **unique_idem()}
        initial_provider_calls = self.fake.calls
        created = self.client.post(url, headers=headers, json=body)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(self.fake.calls, initial_provider_calls)
        self.assertTrue(created.json()["available"])
        original_id = created.json()["id"]
        uploads = self.storage.calls.count("POST")
        replay = self.client.post(url, headers=headers, json=body)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["id"], original_id)
        self.assertEqual(self.storage.calls.count("POST"), uploads)
        denied = self.client.post(url, headers={**with_step_up(OTHER_OWNER), **unique_idem()}, json=body)
        self.assertNotEqual(denied.status_code, 201)
        invalid = self.client.post(url, headers={**with_step_up(OWNER), **unique_idem()},
                                   json={**body, "image_base64": "!" * 32})
        self.assertEqual(invalid.status_code, 422, invalid.text)

    def test_pixel_edit_creates_new_immutable_asset_and_replays_without_duplicate_upload(self):
        from tests_api.test_helpers import with_step_up
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        original = self.client.post(self.base, headers={**OWNER, **unique_idem()},
            json={"expected_plan_version": version, "prompt": "Imagem original para edição de pixels",
                  "credit_confirmation": {field: quote[field] for field in
                      ("cycle_id", "policy_version", "credits", "extra_amount")}})
        self.assertEqual(original.status_code, 201, original.text)
        source_id = original.json()["id"]
        row = self.state.db.table("creative_assets").get_for_tenant(source_id, "demo-tenant")
        edit_url = self.base + "/" + source_id + "/pixel-edit"
        payload = {"operation": "rotate_90", "expected_sha256": row["manifest"]["sha256"],
                   "expected_generation": row["storage_generation"]}
        headers = {**with_step_up(OWNER), **unique_idem()}
        result = self.client.post(edit_url, headers=headers, json=payload)
        self.assertEqual(result.status_code, 201, result.text)
        edited_id = result.json()["id"]
        self.assertNotEqual(edited_id, source_id)
        self.assertEqual(result.json()["source_creative_id"], source_id)
        self.assertEqual((result.json()["width"], result.json()["height"]),
                         (row["manifest"]["height"], row["manifest"]["width"]))
        uploads_before_replay = self.storage.calls.count("POST")
        replay = self.client.post(edit_url, headers=headers, json=payload)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["id"], edited_id)
        self.assertEqual(self.storage.calls.count("POST"), uploads_before_replay)
        self.assertEqual(self.storage.calls.count("DELETE"), 0)
        denial = self.client.post(edit_url, headers={**with_step_up(OWNER), **unique_idem()},
                                  json={**payload, "expected_sha256": "0" * 64})
        self.assertEqual(denial.status_code, 409, denial.text)
        foreign = self.client.post(edit_url, headers={**with_step_up(OTHER_OWNER), **unique_idem()},
                                   json=payload)
        self.assertEqual(foreign.status_code, 404, foreign.text)

    def test_visual_channel_preview_is_scoped_and_cannot_claim_homologation(self):
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        body = {"expected_plan_version": version, "prompt": "Imagem visual de campanha para prévia",
                "credit_confirmation": {field: quote[field] for field in
                    ("cycle_id", "policy_version", "credits", "extra_amount")}}
        created = self.client.post(self.base, headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(created.status_code, 201, created.text)
        url = self.base + "/" + created.json()["id"] + "/visual-preview/"
        for channel in ("google", "meta", "whatsapp"):
            result = self.client.get(url + channel, headers=OWNER)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertIn("Simulação visual interna", result.text)
            self.assertIn("/content", result.text)
            self.assertIn("no-store", result.headers.get("cache-control", ""))
            self.assertIn("frame-ancestors 'none'", result.headers.get("content-security-policy", ""))
        denied = self.client.get(url + "google", headers=OTHER_OWNER)
        self.assertEqual(denied.status_code, 404, denied.text)
        unknown = self.client.get(url + "invalid", headers=OWNER)
        self.assertEqual(unknown.status_code, 404, unknown.text)

    def test_image_revision_preserves_source_and_rejects_foreign_source(self):
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        confirmation = {field: quote[field] for field in
                        ("cycle_id", "policy_version", "credits", "extra_amount")}
        original = self.client.post(self.base, headers={**OWNER, **unique_idem()},
            json={"expected_plan_version": version, "prompt": "Imagem original para revisão",
                  "credit_confirmation": confirmation})
        self.assertEqual(original.status_code, 201, original.text)
        original_id = original.json()["id"]
        updated = self.client.post(self.base, headers={**OWNER, **unique_idem()},
            json={"expected_plan_version": version, "prompt": "Revisão de composição e iluminação",
                  "source_creative_id": original_id, "credit_confirmation": confirmation})
        self.assertEqual(updated.status_code, 201, updated.text)
        self.assertNotEqual(updated.json()["id"], original_id)
        detail = self.client.get(self.base + "/" + updated.json()["id"], headers=OWNER)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["source_creative_id"], original_id)
        self.assertEqual(self.client.get(self.base + "/" + original_id, headers=OWNER).status_code, 200)
        foreign = self.client.post(self.base, headers={**OWNER, **unique_idem()},
            json={"expected_plan_version": version, "prompt": "Revisão inválida entre tenants",
                  "source_creative_id": "00000000-0000-0000-0000-000000000001",
                  "credit_confirmation": confirmation})
        self.assertEqual(foreign.status_code, 409, foreign.text)
        self.assertEqual(foreign.json()["code"], "IMAGE_SOURCE_INVALID")

    def test_unreviewed_generated_image_blocks_campaign_publication(self):
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        body = {"expected_plan_version": version, "prompt": "Imagem sujeita a revisão humana",
                "credit_confirmation": {field: quote[field] for field in
                    ("cycle_id", "policy_version", "credits", "extra_amount")}}
        generated = self.client.post(self.base, headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(generated.status_code, 201, generated.text)
        validation = self.client.post("/campaigns/" + self.campaign + "/validate",
            headers={**OWNER, **unique_idem()})
        self.assertEqual(validation.status_code, 200, validation.text)
        result = self.client.post("/campaigns/" + self.campaign + "/publish",
            headers={**OWNER, **unique_idem()},
            json={"policy_decision_id": validation.json()["policy_decision_id"],
                  "approval_id": "no-approval"})
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(result.json()["code"], "IMAGE_SELECTION_REQUIRED")
        selected = self.client.post("/campaigns/" + self.campaign + "/publish",
            headers={**OWNER, **unique_idem()},
            json={"policy_decision_id": validation.json()["policy_decision_id"],
                  "approval_id": "no-approval",
                  "selected_creative_id": generated.json()["id"]})
        self.assertEqual(selected.status_code, 409, selected.text)
        self.assertEqual(selected.json()["code"], "IMAGE_REVIEW_REQUIRED")
        # Explicit selection cannot smuggle a foreign, stale or unknown asset.
        invalid = self.client.post("/campaigns/" + self.campaign + "/publish",
            headers={**OWNER, **unique_idem()},
            json={"policy_decision_id": validation.json()["policy_decision_id"],
                  "approval_id": "no-approval",
                  "selected_creative_id": "00000000-0000-0000-0000-000000000001"})
        self.assertEqual(invalid.status_code, 409, invalid.text)
        self.assertEqual(invalid.json()["code"], "IMAGE_SELECTION_INVALID")

        self.assertEqual(self.storage.calls.count("POST"), 1)

    def test_confirm_one_delivery_no_duplicate_charge_private_png_and_cross_tenant(self):
        quote = self.client.get(self.base + "/quote", headers=OWNER)
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertEqual(quote.json()["credits"], 15)
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        body = {"expected_plan_version": version, "prompt": "Produto de teste em fundo branco",
                "credit_confirmation": {field: quote.json()[field] for field in
                    ("cycle_id", "policy_version", "credits", "extra_amount")}}
        headers = {**OWNER, **unique_idem()}
        before = self.usage().json()["balance"]["consumed_credits"]
        delivered = self.client.post(self.base, headers=headers, json=body)
        self.assertEqual(delivered.status_code, 201, delivered.text)
        self.assertTrue(delivered.json()["available"])
        self.assertEqual(self.fake.calls, 1)
        self.assertEqual(self.storage.calls.count("POST"), 1)
        self.assertEqual(self.usage().json()["balance"]["consumed_credits"] - before, 15)
        replay = self.client.post(self.base, headers=headers, json=body)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json(), delivered.json())
        self.assertEqual(self.fake.calls, 1)
        self.assertEqual(self.storage.calls.count("POST"), 1)
        found = self.client.get(self.base, headers=OWNER)
        self.assertEqual(found.status_code, 200, found.text)
        self.assertEqual(len(found.json()["items"]), 1)
        media = self.client.get(delivered.json()["content_url"].removeprefix("/api/campaia"), headers=OWNER)
        self.assertEqual(media.status_code, 200, media.text)
        self.assertEqual(media.content, self.fake.png)
        self.assertEqual(media.headers["cache-control"], "private, no-store")
        self.assertEqual(self.client.get(self.base, headers=OTHER_OWNER).status_code, 404)
        self.assertEqual(self.client.get(
            delivered.json()["content_url"].removeprefix("/api/campaia"), headers=OTHER_OWNER).status_code, 404)


    def test_delete_route_rejects_missing_step_up_and_cross_tenant(self):
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        body = {"expected_plan_version": version, "prompt": "Arte para controle de exclusão",
                "credit_confirmation": {field: quote[field] for field in
                    ("cycle_id", "policy_version", "credits", "extra_amount")}}
        created = self.client.post(self.base, headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(created.status_code, 201, created.text)
        route = self.base + "/" + created.json()["id"]
        foreign = self.client.delete(route, headers={**OTHER_OWNER, **unique_idem()})
        self.assertIn(foreign.status_code, (403, 404), foreign.text)
        # setup_subscription performed a valid step-up with this bearer session.
        # Explicitly revoke its elevation to exercise the true missing-step-up path.
        self.state.invalidate_step_up_for_session("bearer:demo-owner-token")
        missing_step_up = self.client.delete(route, headers={**OWNER, **unique_idem()})
        self.assertNotIn(missing_step_up.status_code, (200, 202), missing_step_up.text)
        self.assertEqual(self.client.get(route, headers=OWNER).json()["state"], "STORED")
        self.assertEqual(self.storage.calls.count("DELETE"), 0)
        # Session obtained a legitimate step-up earlier; revocation must be effective.
        from tests_api.test_helpers import with_step_up
        authorized = self.client.delete(route, headers={**with_step_up(OWNER), **unique_idem()})
        self.assertIn(authorized.status_code, (200, 202), authorized.text)
        self.assertEqual(self.storage.calls.count("DELETE"), 1)
        self.assertEqual(self.client.get(route, headers=OWNER).status_code, 404)
        self.assertEqual(self.client.get(
            created.json()["content_url"].removeprefix("/api/campaia"), headers=OWNER).status_code, 404)
        repeat = self.client.delete(route, headers={**OWNER, **unique_idem()})
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertEqual(self.storage.calls.count("DELETE"), 1)


    def test_uncertain_gcs_result_recovers_with_one_credit_settlement_and_no_second_post(self):
        from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        version = self.state.campaigns.get("demo-tenant", self.campaign).plan_version
        body = {"expected_plan_version": version, "prompt": "Produto visual em fundo neutro",
                "credit_confirmation": {field: quote[field] for field in
                    ("cycle_id", "policy_version", "credits", "extra_amount")}}
        initial = self.usage().json()["balance"]
        original = self.storage.upload_once
        def lost_ack(*args, **kwargs):
            original(*args, **kwargs)
            raise AssetStorageError(Code.UNCERTAIN)
        self.storage.upload_once = lost_ack
        sent = self.client.post(self.base, headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(sent.status_code, 503, sent.text)
        self.assertEqual(sent.json()["code"], "AI_OPERATION_PENDING")
        self.assertEqual(self.storage.calls.count("POST"), 1)
        inventory = self.client.get(self.base, headers=OWNER).json()
        self.assertEqual(inventory["items"][0]["state"], "STORAGE_PENDING")
        candidate = inventory["items"][0]["id"]
        repaired = self.client.post(self.base + "/" + candidate + "/reconcile",
            headers={**OWNER, **unique_idem()})
        self.assertEqual(repaired.status_code, 200, repaired.text)
        self.assertTrue(repaired.json()["available"])
        self.assertEqual(self.storage.calls.count("POST"), 1)
        self.assertEqual(self.fake.calls, 1)
        after = self.usage().json()["balance"]
        self.assertEqual(after["consumed_credits"] - initial["consumed_credits"], 15)
        self.assertEqual(after["reserved_credits"], initial["reserved_credits"])
        again = self.client.post(self.base + "/" + candidate + "/reconcile",
            headers={**OWNER, **unique_idem()})
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(self.usage().json()["balance"]["consumed_credits"], after["consumed_credits"])
        self.assertEqual(self.storage.calls.count("POST"), 1)


if __name__ == "__main__":
    unittest.main()
