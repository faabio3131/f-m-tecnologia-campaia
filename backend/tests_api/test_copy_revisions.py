"""Selective one-credit changes preserve the original batch and its authorization history."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from campaia_core.ai_gateway import ProviderTimeout
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_creative_proposals import BRIEF
from tests_api.test_helpers import OWNER, OTHER_OWNER, VIEWER, MARKETER, FINANCE, unique_idem
from tests_support.creative_ai import install_test_creative_provider


class CopyRevisionTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        config = Path(self.tmp.name) / "catalog.json"
        plans = json.loads(config.read_text())
        for plan in plans:
            plan["credit_policy"]["action_weights"]["revision"] = 1
        config.write_text(json.dumps(plans))
        self.provider = install_test_creative_provider(self.state)
        created = self.client.post("/briefs", headers={**OWNER, **unique_idem()}, json=BRIEF)
        self.assertEqual(created.status_code, 202, created.text)
        self.campaign = created.json()["id"]
        generated = self.client.post("/campaigns/" + self.campaign + "/plan/regenerate",
                                    headers={**OWNER, **unique_idem()}, json={})
        self.assertEqual(generated.status_code, 202, generated.text)
        self.setup_subscription(trial=True)
        self.base = "/campaigns/" + self.campaign + "/proposals/copy"
        quoted = self.client.get(self.base + "/quote", headers=OWNER).json()
        copied = self.client.post(self.base, headers={**OWNER, **unique_idem()}, json={
            "expected_plan_version": 1, "channel": "GOOGLE_ADS", "offer": BRIEF["product"],
            "tone": "claro", "variants": 5, "credit_confirmation": self.confirmation(quoted)})
        self.assertEqual(copied.status_code, 201, copied.text)
        self.parent = copied.json()
        self.endpoint = self.base + "/" + self.parent["id"] + "/revisions"

    @staticmethod
    def confirmation(quote):
        return {key: quote[key] for key in ("cycle_id", "policy_version", "credits", "extra_amount")}

    def record(self):
        return self.state.campaigns.get("demo-tenant", self.campaign)

    def body(self, **changes):
        quote = self.client.get(self.endpoint + "/quote", headers=OWNER)
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertEqual(quote.json()["credits"], 1)
        return {"expected_plan_version": self.record().plan_version, "channel": "GOOGLE_ADS",
                "variant_index": 1, "instructions": "Deixe o convite mais direto.",
                "credit_confirmation": self.confirmation(quote.json()), **changes}

    def send(self, body=None, headers=None, client=None, endpoint=None):
        return (client or self.client).post(endpoint or self.endpoint,
            headers=headers or {**OWNER, **unique_idem()}, json=body if body is not None else self.body())

    def included(self):
        return self.usage().json()["balance"]["included_available"]

    def history(self):
        return self.client.get(self.base, headers=OWNER).json()["items"]

    def peer(self):
        client = TestClient(create_app(env="test", db_path=str(self.path)))
        install_test_creative_provider(client.app.state.campaia)
        self.addCleanup(client.app.state.campaia.db.close)
        return client


    def _foreign_copy(self, product="Outra oferta"):
        result = self.client.post("/briefs", headers={**OTHER_OWNER, **unique_idem()},
                                  json={**BRIEF, "product": product})
        self.assertEqual(result.status_code, 202, result.text)
        campaign = result.json()["id"]
        generated = self.client.post("/campaigns/" + campaign + "/plan/regenerate",
                                     headers={**OTHER_OWNER, **unique_idem()}, json={})
        self.assertEqual(generated.status_code, 202, generated.text)
        base = "/campaigns/" + campaign + "/proposals/copy"
        copied = self.client.post(base, headers={**OTHER_OWNER, **unique_idem()}, json={
            "expected_plan_version": 1, "channel": "GOOGLE_ADS", "offer": "", "tone": "claro", "variants": 5})
        self.assertEqual(copied.status_code, 201, copied.text)
        return base, copied.json()

    def test_foreign_source_is_not_usable_even_under_an_owned_campaign_url(self):
        _foreign_base, source = self._foreign_copy()
        before = self.provider.calls
        body = self.body()
        endpoint = self.base + "/" + source["id"] + "/revisions"
        self.assertEqual(self.send(body, endpoint=endpoint).status_code, 404)
        self.assertEqual(self.client.get(endpoint + "/quote", headers=OWNER).status_code, 404)
        self.assertEqual(self.provider.calls, before)
        self.assertEqual(self.included(), 27)

    def test_revision_reuses_delivered_fallback_context_without_treating_it_as_new_input(self):
        base, source = self._foreign_copy(product="x" * 2200)
        self.assertEqual(len(source["request_summary"]["offer"]), 2200)
        result = self.client.post(base + "/" + source["id"] + "/revisions",
            headers={**OTHER_OWNER, **unique_idem()}, json={
                "expected_plan_version": 2, "channel": "GOOGLE_ADS", "variant_index": 1,
                "instructions": "Convite mais claro"})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()["request_summary"]["offer"], source["request_summary"]["offer"])

    def test_one_credit_replaces_one_text_and_preserves_original_batch_and_review_history(self):
        policy = self.client.post("/campaigns/" + self.campaign + "/validate",
                                 headers={**OWNER, **unique_idem()})
        self.assertEqual(policy.status_code, 200, policy.text)
        approval = self.client.post("/approvals", headers={**OWNER, **unique_idem()},
                                   json={"campaign_id": self.campaign, "kind": "PUBLISH"})
        self.assertEqual(approval.status_code, 201, approval.text)
        captured, original = [], self.provider.generate
        def inspect(request):
            self.assertFalse(self.state.db.in_transaction)
            captured.append(request.input)
            return original(request)
        with patch.object(self.provider, "generate", side_effect=inspect):
            result = self.send()
        self.assertEqual(result.status_code, 201, result.text)
        revised = result.json()
        self.assertEqual(revised["version"], 2)
        self.assertEqual(revised["plan_version"], 3)
        self.assertEqual(revised["request_summary"]["revision_of"], self.parent["id"])
        self.assertEqual(captured[0]["quantidade_variacoes"], 1)
        self.assertEqual(captured[0]["revisao"]["texto_original"], self.parent["output"]["variacoes"][1])
        for index, original_text in enumerate(self.parent["output"]["variacoes"]):
            if index == 1:
                self.assertNotEqual(revised["output"]["variacoes"][index], original_text)
            else:
                self.assertEqual(revised["output"]["variacoes"][index], original_text)
        self.assertEqual(self.included(), 26)
        self.assertIsNone(self.record().last_policy_decision)
        self.assertIsNone(self.record().approval_id)
        self.assertEqual(self.history()[1]["output"], self.parent["output"])

    def test_replay_after_restart_is_the_same_revision_and_debit_without_redispatch(self):
        body, headers = self.body(), {**OWNER, **unique_idem()}
        first = self.send(body, headers)
        self.assertEqual(first.status_code, 201, first.text)
        client = self.peer()
        second = self.send(body, headers, client=client)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(client.app.state.campaia.ai_provider.calls, 0)
        self.assertEqual(self.included(), 26)
        changed = self.send({**body, "instructions": "Outra solicitação"}, headers)
        self.assertEqual(changed.status_code, 409, changed.text)

    def test_previous_batch_and_another_strategy_cannot_be_used_as_revision_source(self):
        body = self.body()
        self.assertEqual(self.send(body).status_code, 201)
        before = self.provider.calls
        stale = self.send({**body, "expected_plan_version": self.record().plan_version})
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(self.client.get(self.endpoint + "/quote", headers=OWNER).status_code, 409)
        self.assertEqual(self.provider.calls, before)

    def test_strategy_regeneration_invalidates_all_old_sources_before_provider(self):
        body = self.body()
        from tests_api.test_helpers import unique_idem
        quote = self.client.get("/campaigns/" + self.campaign + "/plan/quote", headers=OWNER).json()
        result = self.client.post("/campaigns/" + self.campaign + "/plan/regenerate",
            headers={**OWNER, **unique_idem()}, json={"credit_confirmation": self.confirmation(quote)})
        self.assertEqual(result.status_code, 202, result.text)
        before = self.provider.calls
        stale = self.send({**body, "expected_plan_version": self.record().plan_version})
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(self.provider.calls, before)

    def test_invalid_or_missing_context_and_scope_never_dispatch_or_charge(self):
        body = self.body()
        before = self.provider.calls
        for changes in ({"variant_index": 5}, {"variant_index": True}, {"instructions": " "},
                        {"instructions": "x" * 2001}, {"variants": 2}, {"channel": "WHATSAPP"},
                        {"expected_plan_version": 1}, {"tenant_id": "foreign"}):
            result = self.send({**body, **changes})
            self.assertIn(result.status_code, (409, 422), result.text)
        for headers, status in ((VIEWER, 403), (OTHER_OWNER, 404)):
            self.assertEqual(self.send(body, {**headers, **unique_idem()}).status_code, status)
        unknown = self.base + "/missing-source/revisions"
        self.assertEqual(self.send(body, endpoint=unknown).status_code, 404)
        self.state.tokens["demo-marketer-token"] = replace(self.state.tokens["demo-marketer-token"], business_unit_id="other-unit")
        self.assertEqual(self.send(body, {**MARKETER, **unique_idem()}).status_code, 404)
        self.assertEqual(self.provider.calls, before)
        self.assertEqual(self.included(), 27)

    def test_copy_batch_index_must_exist_even_if_below_global_maximum(self):
        quote = self.client.get(self.base + "/quote", headers=OWNER).json()
        smaller = self.client.post(self.base, headers={**OWNER, **unique_idem()}, json={
            "expected_plan_version": self.record().plan_version, "channel": "GOOGLE_ADS",
            "offer": "Oferta", "tone": "claro", "variants": 1,
            "credit_confirmation": self.confirmation(quote)})
        self.assertEqual(smaller.status_code, 201, smaller.text)
        self.endpoint = self.base + "/" + smaller.json()["id"] + "/revisions"
        before = self.provider.calls
        result = self.send()
        self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(self.provider.calls, before)
        self.assertEqual(self.included(), 24)

    def test_unchanged_or_invalid_output_releases_one_credit_and_keeps_original(self):
        original = self.provider.generate
        for output in ({"variacoes": [self.parent["output"]["variacoes"][1]]},
                       {"variacoes": ["one", "two"]}, {"variacoes": [" "]}):
            def invalid(request):
                return replace(original(request), output=output)
            headers, body = {**OWNER, **unique_idem()}, self.body()
            with patch.object(self.provider, "generate", side_effect=invalid):
                result = self.send(body, headers)
            self.assertEqual(result.status_code, 422, result.text)
            before = self.provider.calls
            self.assertEqual(self.send(body, headers).status_code, 422)
            self.assertEqual(self.provider.calls, before)
        self.assertEqual(self.included(), 27)
        self.assertEqual(len(self.history()), 1)

    def test_timeout_holds_one_credit_and_peer_cannot_redispatch(self):
        body, headers = self.body(), {**OWNER, **unique_idem()}
        with patch.object(self.provider, "generate", side_effect=ProviderTimeout("unknown fixture outcome")):
            result = self.send(body, headers)
        self.assertEqual(result.status_code, 503, result.text)
        usage = self.usage().json()["balance"]
        self.assertEqual(usage["reserved_credits"], 1)
        client = self.peer()
        repeated = self.send(body, headers, client=client)
        self.assertEqual(repeated.status_code, 503, repeated.text)
        self.assertEqual(client.app.state.campaia.ai_provider.calls, 0)
        self.assertEqual(len(self.history()), 1)

    def test_two_workers_can_deliver_only_one_revision_for_the_same_batch_version(self):
        client = self.peer()
        original_a, original_b = self.state.agent_runner.run, client.app.state.campaia.agent_runner.run
        gate = threading.Barrier(2)
        def blocked(original):
            def run(*args, **kwargs):
                gate.wait(timeout=5)
                return original(*args, **kwargs)
            return run
        body = self.body()
        with patch.object(self.state.agent_runner, "run", side_effect=blocked(original_a)), \
             patch.object(client.app.state.campaia.agent_runner, "run", side_effect=blocked(original_b)):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.send, body, {**OWNER, **unique_idem()}, current)
                           for current in (self.client, client)]
                results = [future.result(timeout=10) for future in futures]
        self.assertEqual(sorted(result.status_code for result in results), [201, 409],
                         [result.text for result in results])
        self.assertEqual(self.included(), 26)
        self.assertEqual(self.usage().json()["balance"]["reserved_credits"], 0)
        self.assertEqual(len(self.history()), 2)

    def test_authority_is_rechecked_after_revision_generation(self):
        from campaia_core.permissions import Role
        original = self.provider.generate
        def revoke(request):
            self.state.tokens["demo-owner-token"] = replace(self.state.tokens["demo-owner-token"],
                                                           roles=frozenset({Role.VIEWER}))
            return original(request)
        body = self.body()
        with patch.object(self.provider, "generate", side_effect=revoke):
            result = self.send(body)
        self.assertEqual(result.status_code, 403, result.text)
        self.assertEqual(self.usage(FINANCE).json()["balance"]["included_available"], 27)
        self.assertEqual(len(self.history()), 1)


if __name__ == "__main__":
    unittest.main()
