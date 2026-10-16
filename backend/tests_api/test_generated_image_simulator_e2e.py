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
        missing_step_up = self.client.delete(route, headers={**OWNER, **unique_idem()})
        self.assertNotIn(missing_step_up.status_code, (200, 202), missing_step_up.text)
        self.assertEqual(self.client.get(route, headers=OWNER).json()["state"], "STORED")
        self.assertEqual(self.storage.calls.count("DELETE"), 0)

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
