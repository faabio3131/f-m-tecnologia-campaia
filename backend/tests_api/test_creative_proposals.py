"""Delivered proposals are immutable and charged once; AI/provider uncertainty is not replayed."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
import threading
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from api.main import create_app
from campaia_core.ai_gateway import ProviderTimeout
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, VIEWER, APPROVER, FINANCE, MARKETER, unique_idem, with_step_up
from tests_support.creative_ai import install_test_creative_provider

BRIEF = {"objective": "Campanha de proposta", "product": "Oferta de calçados", "audience": "Adultos interessados em calçados",
         "total_budget": "100", "daily_cap": "10"}


class CreativeProposalTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.provider = install_test_creative_provider(self.state)
        result = self.client.post("/briefs", headers={**OWNER, **unique_idem()}, json=BRIEF)
        self.campaign = result.json()["id"]
        generated = self.client.post("/campaigns/" + self.campaign + "/plan/regenerate",
            headers={**OWNER, **unique_idem()}, json={})
        self.assertEqual(generated.status_code, 202, generated.text)
        self.base = "/campaigns/" + self.campaign + "/proposals/"

    def record(self):
        return self.state.campaigns.get("demo-tenant", self.campaign)

    def body(self, kind="copy", *, commercial=False, **changes):
        values = {"expected_plan_version": self.record().plan_version, "channel": "GOOGLE_ADS"}
        values.update({"offer": BRIEF["product"], "tone": "claro", "variants": 5} if kind == "copy" else
                      {"audience": BRIEF["audience"], "region": "BR", "exclusions": [], "sensitive_declared": False})
        if commercial:
            quote = self.client.get(self.base + kind + "/quote", headers=OWNER)
            self.assertEqual(quote.status_code, 200, quote.text)
            values["credit_confirmation"] = {key: quote.json()[key]
                for key in ("cycle_id", "policy_version", "credits", "extra_amount")}
        return {**values, **changes}

    def send(self, kind="copy", body=None, headers=None, client=None):
        return (client or self.client).post(self.base + kind, headers=headers or {**OWNER, **unique_idem()},
                                          json=body if body is not None else self.body(kind))

    def history(self, kind="copy", client=None, headers=OWNER):
        return (client or self.client).get(self.base + kind, headers=headers)

    def peer(self):
        other = TestClient(create_app(env="test", db_path=str(self.path)))
        install_test_creative_provider(other.app.state.campaia)
        self.addCleanup(other.app.state.campaia.db.close)
        return other

    def included(self):
        return self.usage().json()["balance"]["included_available"]

    def validate(self):
        return self.client.post("/campaigns/" + self.campaign + "/validate", headers={**OWNER, **unique_idem()})

    def approval(self, **changes):
        result = self.client.post("/approvals", headers={**OWNER, **unique_idem()},
            json={"campaign_id": self.campaign, "kind": "PUBLISH", "requires_dual_approval": False, **changes})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def approve(self, identity, headers=None):
        return self.client.post("/approvals/" + identity + "/decision",
            headers=headers or {**with_step_up(APPROVER), **unique_idem()}, json={"decision": "APPROVE"})

    def publish(self, policy, approval):
        return self.client.post("/campaigns/" + self.campaign + "/publish",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"policy_decision_id": policy, "approval_id": approval})


    def test_legacy_known_invalid_output_replays_failure_without_another_dispatch(self):
        body, headers = self.body(), {**OWNER, **unique_idem()}
        original = self.provider.generate
        def invalid(request):
            return replace(original(request), output={"variacoes": [" "] * 5})
        with patch.object(self.provider, "generate", side_effect=invalid):
            first = self.send(body=body, headers=headers)
        self.assertEqual(first.status_code, 422, first.text)
        before = self.provider.calls
        repeated = self.send(body=body, headers=headers)
        self.assertEqual(repeated.status_code, 422, repeated.text)
        self.assertEqual(repeated.json()["code"], "AI_OPERATION_FAILED")
        self.assertEqual(self.provider.calls, before)
        self.assertEqual(self.history().json()["items"], [])


    def test_agents_receive_strategy_and_declared_context_without_internal_plan_metadata(self):
        captured = []
        original = self.provider.generate
        def inspect(request):
            captured.append(request.input)
            return original(request)
        with patch.object(self.provider, "generate", side_effect=inspect):
            response = self.send()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(captured[0]["estrategia"], self.record().plan["output"])
        self.assertEqual(captured[0]["objetivo"], BRIEF["objective"])
        self.assertEqual(captured[0]["quantidade_variacoes"], 5)
        self.assertNotIn("proposal_id", captured[0])
        self.assertNotIn("provenance", captured[0])


    def test_mismatched_agent_or_tenant_proposal_is_never_delivered_or_charged(self):
        self.setup_subscription(trial=True)
        runner = self.state.agent_runner
        original = runner.run
        for changes in ({"tenant_id": "other-tenant"}, {"agent": "audience"}):
            def wrong(*args, **kwargs):
                return replace(original(*args, **kwargs), **changes)
            with patch.object(runner, "run", side_effect=wrong):
                result = self.send(body=self.body(commercial=True))
            self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(self.included(), 30)
        self.assertEqual(self.history().json()["items"], [])


    def test_other_business_unit_cannot_read_generate_or_request_decide_and_list_approval(self):
        approved = self.approval()
        before = self.provider.calls
        for token in ("demo-marketer-token", "demo-approver-token", "demo-viewer-token"):
            self.state.tokens[token] = replace(self.state.tokens[token], business_unit_id="other-unit")
        marketer = {**MARKETER, **unique_idem()}
        self.assertEqual(self.history(headers=MARKETER).status_code, 404)
        self.assertEqual(self.client.get(self.base + "copy/quote", headers=MARKETER).status_code, 404)
        self.assertEqual(self.send(body=self.body(), headers=marketer).status_code, 404)
        requested = self.client.post("/approvals", headers={**MARKETER, **unique_idem()},
            json={"campaign_id": self.campaign, "kind": "PUBLISH"})
        self.assertEqual(requested.status_code, 404, requested.text)
        decided = self.approve(approved["id"])
        self.assertEqual(decided.status_code, 404, decided.text)
        self.assertEqual(self.client.get("/approvals", headers=VIEWER).json(), [])
        self.assertEqual(self.provider.calls, before)

    def test_copy_five_variants_and_audience_charge_three_and_two_only_on_delivery(self):
        self.setup_subscription(trial=True)
        before = self.included()
        copy = self.send(body=self.body(commercial=True))
        self.assertEqual(copy.status_code, 201, copy.text)
        self.assertEqual(len(copy.json()["output"]["variacoes"]), 5)
        self.assertEqual(self.included(), before - 3)
        audience = self.send("audience", self.body("audience", commercial=True))
        self.assertEqual(audience.status_code, 201, audience.text)
        self.assertEqual(self.included(), before - 5)
        self.assertTrue(self.history().json()["items"][0]["current"])
        self.assertEqual(self.record().plan_version, 3)
        self.assertIsNone(self.record().last_policy_decision)

    def test_response_lost_restart_and_replay_keep_the_same_body_output_and_charge(self):
        self.setup_subscription(trial=True)
        body, headers = self.body(commercial=True), {**OWNER, **unique_idem()}
        before = self.provider.calls
        first = self.send(body=body, headers=headers)
        self.assertEqual(first.status_code, 201, first.text)
        peer = self.peer()
        replay = self.send(body=body, headers=headers, client=peer)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(self.provider.calls, before + 1)
        self.assertEqual(peer.app.state.campaia.ai_provider.calls, 0)
        self.assertEqual(len(self.history(client=peer).json()["items"]), 1)
        self.assertEqual(self.included(), 27)
        conflict = self.send(body={**body, "variants": 1}, headers=headers)
        self.assertEqual(conflict.status_code, 409, conflict.text)

    def test_legacy_replay_is_namespaced_and_actor_body_and_business_unit_bound(self):
        body, headers = self.body(), {**OWNER, **unique_idem()}
        first = self.send(body=body, headers=headers)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(self.send(body=body, headers=headers).json(), first.json())
        self.assertEqual(self.send(body={**body, "tone": "outra voz"}, headers=headers).status_code, 409)
        owner = self.state.tokens["demo-owner-token"]
        self.state.tokens["creative-peer"] = replace(owner, user_id="another-creator")
        self.assertEqual(self.send(body=body, headers={**headers, "Authorization": "Bearer creative-peer"}).status_code, 409)
        self.state.tokens["creative-unit"] = replace(owner, business_unit_id="other-unit")
        self.assertEqual(self.send(body=body, headers={**headers, "Authorization": "Bearer creative-unit"}).status_code, 404)

    def test_rbac_cross_tenant_and_unit_precede_provider_and_quota(self):
        before = self.provider.calls
        for headers, status in ((VIEWER, 403), (OTHER_OWNER, 404), ({}, 401)):
            result = self.send(body=self.body(), headers={**headers, **unique_idem()})
            self.assertEqual(result.status_code, status, result.text)
        self.assertEqual(self.history(headers=OTHER_OWNER).status_code, 404)
        self.assertEqual(self.client.get(self.base + "copy/quote", headers=VIEWER).status_code, 403)
        self.assertEqual(self.provider.calls, before)
        self.assertTrue(self.history(headers=VIEWER).json()["capability"]["enabled"])
        self.assertFalse(self.history(headers=VIEWER).json()["capability"]["can_generate"])

    def test_default_provider_does_not_pretend_to_support_copy(self):
        peer = TestClient(create_app(env="test", db_path=str(self.path)))
        self.addCleanup(peer.app.state.campaia.db.close)
        page = self.history(client=peer).json()
        self.assertFalse(page["capability"]["enabled"])
        self.assertEqual(self.send(body=self.body(), client=peer).status_code, 503)
        self.assertEqual(peer.app.state.campaia.ai_provider.calls, 0)

    def test_missing_or_wrong_context_and_oversize_body_never_dispatch(self):
        before = self.provider.calls
        self.assertEqual(self.send(body=self.body(tone="")).status_code, 422)
        self.assertEqual(self.send(body=self.body(channel="WHATSAPP")).status_code, 422)
        self.assertEqual(self.send(body=self.body(variants=True)).status_code, 422)
        self.assertEqual(self.send(body={**self.body(), "tenant_id": "foreign"}).status_code, 422)
        large = self.client.post(self.base + "copy", headers={**OWNER, **unique_idem(), "Content-Type": "application/json"},
            content=b"x" * (256 * 1024 + 1))
        self.assertEqual(large.status_code, 413)
        self.assertEqual(self.provider.calls, before)
        self.assertEqual(self.history().json()["items"], [])

    def test_invalid_output_releases_customer_credits_but_keeps_internal_cost_evidence(self):
        self.setup_subscription(trial=True)
        body = self.body(commercial=True)
        internal_before = self.state.ai_gateway.ledger.used("demo-tenant")
        original = self.provider.generate
        def invalid(request):
            result = original(request)
            return replace(result, output={"variacoes": [" "] * 5})
        with patch.object(self.provider, "generate", side_effect=invalid):
            response = self.send(body=body)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.included(), 30)
        self.assertEqual(self.usage().json()["balance"]["reserved_credits"], 0)
        self.assertEqual(self.history().json()["items"], [])
        self.assertEqual(self.state.ai_gateway.ledger.used("demo-tenant"), internal_before + Decimal("1"))

    def test_invalid_unicode_cannot_settle_an_undeliverable_response(self):
        self.setup_subscription(trial=True)
        original = self.provider.generate
        def invalid(request):
            return replace(original(request), output={"variacoes": [chr(0xD800)] * 5})
        with patch.object(self.provider, "generate", side_effect=invalid):
            result = self.send(body=self.body(commercial=True))
        self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(self.included(), 30)
        self.assertEqual(self.history().json()["items"], [])
        self.assertEqual(self.record().plan_version, 1)

    def test_unknown_timeout_holds_reservation_and_restart_never_redispatches(self):
        self.setup_subscription(trial=True)
        body, headers = self.body(commercial=True), {**OWNER, **unique_idem()}
        with patch.object(self.provider, "generate", side_effect=ProviderTimeout("fixture timeout")) as called:
            first = self.send(body=body, headers=headers)
            self.assertEqual(first.status_code, 503, first.text)
            self.assertEqual(self.send(body=body, headers=headers).status_code, 503)
            self.assertEqual(called.call_count, 1)
        peer = self.peer()
        self.assertEqual(self.send(body=body, headers=headers, client=peer).status_code, 503)
        self.assertEqual(peer.app.state.campaia.ai_provider.calls, 0)
        self.assertEqual(self.usage().json()["balance"]["reserved_credits"], 3)
        self.assertEqual(self.history().json()["items"], [])

    def test_provider_runs_without_db_transaction_and_role_revocation_discards_delivery(self):
        self.setup_subscription(trial=True)
        body = self.body(commercial=True)
        original = self.provider.generate
        def revoke(request):
            self.assertFalse(self.state.db.in_transaction)
            output = original(request)
            self.state.tokens["demo-owner-token"] = replace(self.state.tokens["demo-owner-token"],
                roles=self.state.tokens["demo-viewer-token"].roles)
            return output
        with patch.object(self.provider, "generate", side_effect=revoke):
            response = self.send(body=body)
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.history(headers=VIEWER).json()["items"], [])
        self.assertEqual(self.usage(headers=FINANCE).json()["balance"]["reserved_credits"], 0)

    def test_concurrent_same_nonce_has_one_dispatch_and_one_delivery(self):
        self.setup_subscription(trial=True)
        body, headers, peer = self.body(commercial=True), {**OWNER, **unique_idem()}, self.peer()
        started, release = threading.Event(), threading.Event()
        original = self.provider.generate
        def held(request):
            started.set()
            if not release.wait(timeout=5):
                raise RuntimeError("test dispatch not released")
            return original(request)
        with patch.object(self.provider, "generate", side_effect=held):
            with ThreadPoolExecutor(max_workers=2) as pool:
                future = pool.submit(self.send, "copy", body, headers)
                try:
                    self.assertTrue(started.wait(timeout=5))
                    pending = self.send(body=body, headers=headers, client=peer)
                    self.assertEqual(pending.status_code, 503, pending.text)
                finally:
                    release.set()
                first = future.result(timeout=5)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(self.send(body=body, headers=headers, client=peer).json(), first.json())
        self.assertEqual(peer.app.state.campaia.ai_provider.calls, 0)
        self.assertEqual(self.included(), 27)

    def test_two_workers_with_different_nonces_cannot_deliver_against_the_same_plan_version(self):
        self.setup_subscription(trial=True)
        body, peer = self.body(commercial=True), self.peer()
        barrier = threading.Barrier(2)
        originals = [self.provider.generate, peer.app.state.campaia.ai_provider.generate]
        def run(index, request):
            barrier.wait(timeout=5)
            return originals[index](request)
        with patch.object(self.provider, "generate", side_effect=lambda request: run(0, request)):
            with patch.object(peer.app.state.campaia.ai_provider, "generate", side_effect=lambda request: run(1, request)):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    one, two = pool.submit(self.send, "copy", body), pool.submit(self.send, "copy", body, None, peer)
                    results = [one.result(timeout=10), two.result(timeout=10)]
        self.assertEqual(sorted(result.status_code for result in results), [201, 409], [r.text for r in results])
        self.assertEqual(len(self.history().json()["items"]), 1)
        self.assertEqual(self.included(), 27)
        self.assertEqual(self.usage().json()["balance"]["reserved_credits"], 0)

    def test_new_material_invalidates_policy_and_an_old_approval_cannot_publish(self):
        decision = self.validate().json()
        old = self.approval()
        self.assertEqual(self.approve(old["id"]).status_code, 200)
        self.assertEqual(self.send(body=self.body()).status_code, 201)
        self.assertIsNone(self.record().last_policy_decision)
        new = self.validate().json()
        with patch("api.routes_campaigns.ProviderSimulator", side_effect=AssertionError("no publication")):
            denied = self.publish(new["policy_decision_id"], old["id"])
        self.assertEqual(denied.status_code, 403, denied.text)
        stale = self.approve(old["id"])
        self.assertEqual(stale.status_code, 409, stale.text)

    def test_sensitive_flag_cannot_be_lowered_by_client_or_reused_legacy_approval(self):
        response = self.send("audience", self.body("audience", sensitive_declared=True))
        self.assertEqual(response.status_code, 201, response.text)
        decision = self.validate().json()
        self.assertTrue(decision["requires_dual_approval"])
        approval = self.approval(requires_dual_approval=False)
        self.assertTrue(approval["requires_dual_approval"])
        voted = self.approve(approval["id"])
        self.assertEqual(voted.status_code, 200, voted.text)
        self.assertEqual(voted.json()["status"], "PENDING")
        # Even a legacy incorrectly-marked record cannot bypass the policy's dual-review flag.
        row = self.state.approvals.get("demo-tenant", approval["id"])
        row.requires_dual_approval = False
        row.status = "APPROVED"
        with patch("api.routes_campaigns.ProviderSimulator", side_effect=AssertionError("no publication")):
            denied = self.publish(decision["policy_decision_id"], approval["id"])
        self.assertEqual(denied.status_code, 403, denied.text)

    def test_strategy_regeneration_marks_prior_material_stale_and_live_campaign_is_not_rewritten(self):
        first = self.send(body=self.body())
        self.assertEqual(first.status_code, 201, first.text)
        generated = self.client.post("/campaigns/" + self.campaign + "/plan/regenerate",
            headers={**OWNER, **unique_idem()}, json={})
        self.assertEqual(generated.status_code, 202)
        self.assertFalse(self.history().json()["items"][0]["current"])
        decision = self.validate().json()
        approved = self.approval()
        self.assertEqual(self.approve(approved["id"]).status_code, 200)
        published = self.publish(decision["policy_decision_id"], approved["id"])
        self.assertEqual(published.status_code, 202, published.text)
        before = self.provider.calls
        self.assertEqual(self.send(body=self.body()).status_code, 409)
        self.assertEqual(self.provider.calls, before)

    def test_slot_and_legacy_production_gate_do_not_dispatch(self):
        self.state.proposal_slots.acquire(); self.state.proposal_slots.acquire()
        try:
            before = self.provider.calls
            self.assertEqual(self.send(body=self.body()).status_code, 429)
            self.assertEqual(self.provider.calls, before)
        finally:
            self.state.proposal_slots.release(); self.state.proposal_slots.release()
        self.state.env = "staging"  # Test object only; production bootstrap does not expose fixture auth.
        self.assertEqual(self.send(body=self.body()).status_code, 409)
        self.assertEqual(self.history().json()["capability"]["billing_required"], True)


if __name__ == "__main__":
    unittest.main()
