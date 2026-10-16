from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from api.main import create_app
from starlette.testclient import TestClient
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_brand_versions import BODY
from tests_api.test_brand_assets import png
from tests_api.test_helpers import OWNER, OTHER_OWNER, VIEWER, unique_idem
from tests_support.asset_storage import TestOnlyAssetStorage

BRIEF = {"objective": "Campanha com marca", "product": "Produto", "audience": "Adultos",
         "total_budget": "100", "daily_cap": "10"}


class CampaignBrandTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.state.asset_storage = TestOnlyAssetStorage()
        self.profile = self.client.post("/brand-profiles", headers={**OWNER, **unique_idem()}, json=BODY).json()
        self.base = "/brand-profiles/" + self.profile["id"] + "/assets"
        self.asset = self.client.post(self.base + "?kind=LOGO",
            headers={**OWNER, **unique_idem(), "Content-Type": "application/octet-stream"}, content=png()).json()
        self.selection = {"brand_profile_id": self.profile["id"], "expected_version": 1,
                          "asset_ids": [self.asset["id"]]}

    def create(self, selection=True, headers=None, **changes):
        body = {**BRIEF, **({"brand_selection": self.selection} if selection is True else
                {"brand_selection": selection} if selection is not False else {}), **changes}
        return self.client.post("/briefs", headers=headers or {**OWNER, **unique_idem()}, json=body)

    def generate(self, identity):
        return self.client.post("/campaigns/" + identity + "/plan/regenerate",
            headers={**OWNER, **unique_idem()}, json={})

    def test_snapshot_and_provider_input_keep_explicit_version_after_later_brand_edit(self):
        created = self.create()
        self.assertEqual(created.status_code, 202, created.text)
        item = created.json()
        frozen = deepcopy(item["brief"]["brand_snapshot_v1"])
        self.assertEqual(frozen["profile"], self.profile)
        self.assertEqual(frozen["assets"], [self.asset])
        updated = self.client.put("/brand-profiles/" + self.profile["id"],
            headers={**OWNER, **unique_idem()}, json={**BODY, "tone": "mudou", "expected_version": 1})
        self.assertEqual(updated.status_code, 200)
        with patch.object(self.state.ai_provider, "generate", wraps=self.state.ai_provider.generate) as called:
            generated = self.generate(item["id"])
        self.assertEqual(generated.status_code, 202, generated.text)
        request = called.call_args.args[0]
        self.assertEqual(request.input["marca"]["tone"], BODY["tone"])
        self.assertEqual(request.input["marca"]["restrictions"], BODY["restrictions"])
        self.assertEqual(request.input["marca_versao"], 1)
        self.assertEqual(request.input["arquivos_selecionados"], [{"referencia": "arquivo-1", "kind": "LOGO", "width": 3, "height": 2}])
        self.assertNotIn("content_url", str(request.input))
        self.assertNotIn(self.asset["id"], str(request.input))
        peer = TestClient(create_app(env="test", db_path=str(self.path)))
        self.addCleanup(peer.app.state.campaia.db.close)
        self.assertEqual(peer.get("/campaigns/" + item["id"], headers=OWNER).json()["brief"]["brand_snapshot_v1"], frozen)
        self.assertEqual(self.create().status_code, 409)


    def test_asset_references_do_not_depend_on_uuid_digits_and_never_bypass_pii_filter(self):
        from types import SimpleNamespace
        from api.campaign_brand import brand_agent_context
        from campaia_core.sanitizer import sanitize
        profile = {**self.profile, "name": "Contato +55 (11) 99999-8888"}
        assets = [{"id": identity, "kind": "LOGO", "width": 3, "height": 2}
                  for identity in ("db45bc0e-583a-44fb-bd5b-9d6764268221",
                                   "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")]
        record = SimpleNamespace(brief={"brand_snapshot_v1": {"profile": profile, "assets": assets}})
        clean, _report = sanitize(brand_agent_context(record))
        self.assertEqual(clean["arquivos_selecionados"], [
            {"referencia": "arquivo-1", "kind": "LOGO", "width": 3, "height": 2},
            {"referencia": "arquivo-2", "kind": "LOGO", "width": 3, "height": 2}])
        self.assertNotIn("+55 (11) 99999-8888", str(clean))
        self.assertIn("[TELEFONE_", clean["marca"]["name"])
        self.assertNotIn(assets[0]["id"], str(clean))
        self.assertEqual(record.brief["brand_snapshot_v1"]["assets"], assets)

    def test_no_selection_never_selects_the_first_brand_implicitly(self):
        item = self.create(selection=False).json()
        self.assertNotIn("brand_snapshot_v1", item["brief"])
        with patch.object(self.state.ai_provider, "generate", wraps=self.state.ai_provider.generate) as called:
            self.assertEqual(self.generate(item["id"]).status_code, 202)
        self.assertNotIn("marca", called.call_args.args[0].input)

    def test_client_snapshot_cross_tenant_wrong_profile_and_duplicate_assets_are_rejected(self):
        self.assertEqual(self.create(headers={**OTHER_OWNER, **unique_idem()}).status_code, 404)
        self.assertEqual(self.create(headers={**VIEWER, **unique_idem()}).status_code, 403)
        self.assertEqual(self.create(brand_snapshot_v1={"profile": self.profile}).status_code, 422)
        self.assertEqual(self.create(selection={**self.selection, "tenant_id": "foreign"}).status_code, 422)
        another = self.client.post("/brand-profiles", headers={**OWNER, **unique_idem()}, json=BODY).json()
        self.assertEqual(self.create(selection={**self.selection, "brand_profile_id": another["id"]}).status_code, 404)
        self.assertEqual(self.create(selection={**self.selection, "asset_ids": [self.asset["id"]] * 2}).status_code, 422)
        self.assertEqual(self.create(selection={**self.selection, "expected_version": True}).status_code, 422)

    def test_nonce_binds_body_actor_unit_and_selection_and_replay_keeps_original_snapshot(self):
        headers = {**OWNER, **unique_idem()}
        first = self.create(headers=headers)
        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(self.create(headers=headers).json(), first.json())
        self.assertEqual(self.create(headers=headers, objective="Outro objetivo").status_code, 409)
        self.assertEqual(self.create(headers=headers, selection=False).status_code, 409)
        owner = self.state.tokens["demo-owner-token"]
        for key, principal in (("brand-peer", replace(owner, user_id="other-user")),
                               ("brand-unit", replace(owner, business_unit_id="different-unit"))):
            self.state.tokens[key] = principal
            self.assertEqual(self.create(headers={**headers, "Authorization": "Bearer " + key}).status_code, 409)
        self.client.put("/brand-profiles/" + self.profile["id"], headers={**OWNER, **unique_idem()},
            json={**BODY, "expected_version": 1, "name": "Marca nova"})
        self.assertEqual(self.create(headers=headers).json(), first.json())

    def test_removed_asset_blocks_new_selection_strategy_and_fresh_publication_before_provider(self):
        item = self.create().json()
        self.assertEqual(self.client.delete(self.base + "/" + self.asset["id"],
            headers={**OWNER, **unique_idem()}).status_code, 200)
        self.assertEqual(self.create().status_code, 409)
        with patch.object(self.state.ai_provider, "generate", wraps=self.state.ai_provider.generate) as called:
            refused = self.generate(item["id"])
        self.assertEqual(refused.status_code, 409, refused.text)
        called.assert_not_called()
        from tests_api.test_helpers import with_step_up
        with patch("api.routes_campaigns.ProviderSimulator", side_effect=AssertionError("no publication")):
            refused = self.client.post("/campaigns/" + item["id"] + "/publish",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"policy_decision_id": "fake", "approval_id": "fake"})
        self.assertEqual(refused.status_code, 409, refused.text)
        validation = self.client.post("/campaigns/" + item["id"] + "/validate",
            headers={**OWNER, **unique_idem()})
        self.assertEqual(validation.status_code, 200, validation.text)
        self.assertEqual(validation.json()["outcome"], "BLOCKED")
        self.assertIn("BRAND_ASSET_UNAVAILABLE", [entry["code"] for entry in validation.json()["findings"]])

    def test_freeform_guidance_requires_human_review_without_false_literal_matching(self):
        item = self.create().json()
        self.assertEqual(self.generate(item["id"]).status_code, 202)
        response = self.client.post("/campaigns/" + item["id"] + "/validate", headers={**OWNER, **unique_idem()})
        self.assertEqual(response.status_code, 200, response.text)
        decision = response.json()
        self.assertEqual(decision["outcome"], "APPROVABLE")
        self.assertTrue(decision["requires_human_approval"])
        self.assertIn("BRAND_GUIDANCE_REVIEW_REQUIRED", [entry["code"] for entry in decision["findings"]])

    def test_snapshot_and_campaign_roll_back_together_on_audit_failure(self):
        original = self.state.audit.append
        def fail(**event):
            original(**event)
            if event["action"] == "CAMPAIGN_CREATE":
                raise RuntimeError("injected brand campaign write")
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.state.audit, "append", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "injected brand campaign write"):
                self.create(headers=headers)
        self.assertEqual(self.state.campaigns.list_for_tenant("demo-tenant"), [])
        self.assertIsNone(self.state.idempotency.get("demo-tenant", "http:create_brief:" + headers["Idempotency-Key"]))
        self.assertEqual(self.create(headers=headers).status_code, 202)


if __name__ == "__main__":
    unittest.main()
