"""Human decisions are contextual, immutable after closure, and never rearm an applied approval."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from campaia_core.permissions import Role
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import (OWNER, APPROVER, FINANCE, MARKETER, VIEWER, OTHER_OWNER,
                                   create_campaign, unique_idem, with_step_up)
from tests_support.creative_ai import install_test_creative_provider


class ApprovalReviewTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.campaign = create_campaign(self.client)["id"]
        generated = self.client.post("/campaigns/" + self.campaign + "/plan/regenerate",
                                    headers={**OWNER, **unique_idem()}, json={})
        self.assertEqual(generated.status_code, 202, generated.text)

    def request(self, *, body=None, headers=None):
        return self.client.post("/approvals", headers=headers or {**OWNER, **unique_idem()},
            json=body or {"campaign_id": self.campaign, "kind": "PUBLISH"})

    def decision(self, identity, decision="APPROVE", reason=None, headers=None, client=None):
        return (client or self.client).post("/approvals/" + identity + "/decision",
            headers=headers or {**with_step_up(APPROVER), **unique_idem()},
            json={"decision": decision, "reason": reason})

    def row(self, identity):
        return self.state.approvals.get("demo-tenant", identity)


    def test_legacy_cache_returns_only_scoped_historical_facts_without_reexecuting(self):
        created = self.request().json()
        create_headers = {**OWNER, **unique_idem()}
        self.state.idempotency.execute("demo-tenant", "http:create_approval:" + create_headers["Idempotency-Key"],
                                       lambda: created)
        self.assertEqual(self.request(headers=create_headers).json(), created)
        changed = {**MARKETER, "Idempotency-Key": create_headers["Idempotency-Key"]}
        self.assertEqual(self.request(headers=changed).status_code, 409)
        voted = self.decision(created["id"]).json()
        vote_headers = {**with_step_up(APPROVER), **unique_idem()}
        self.state.idempotency.execute("demo-tenant", "http:decide_approval:" + vote_headers["Idempotency-Key"],
                                       lambda: voted)
        before = len(self.state.audit.list_for_tenant("demo-tenant"))
        replay = self.decision(created["id"], headers=vote_headers)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json(), voted)
        self.assertEqual(len(self.state.audit.list_for_tenant("demo-tenant")), before)
        wrong_actor = {**with_step_up(FINANCE), "Idempotency-Key": vote_headers["Idempotency-Key"]}
        self.assertEqual(self.decision(created["id"], headers=wrong_actor).status_code, 409)

    def test_consumed_budget_approval_cannot_be_rearmed_by_another_eligible_reviewer(self):
        created = self.request(body={"campaign_id": self.campaign, "kind": "BUDGET_CHANGE"}).json()
        identity = created["id"]
        vote = self.decision(identity)
        self.assertEqual(vote.status_code, 200, vote.text)
        applied = self.client.patch("/campaigns/" + self.campaign + "/budget",
            headers={**with_step_up(OWNER), **unique_idem()}, json={"approval_id": identity, "new_daily_cap": "550"})
        self.assertEqual(applied.status_code, 202, applied.text)
        self.assertEqual(self.row(identity).status, "APPLIED")
        rearm = self.decision(identity, headers={**with_step_up(FINANCE), **unique_idem()})
        self.assertEqual(rearm.status_code, 409, rearm.text)
        self.assertEqual(rearm.json()["code"], "APPROVAL_FINALIZED")
        self.assertEqual(self.row(identity).status, "APPLIED")
        second = self.client.patch("/campaigns/" + self.campaign + "/budget",
            headers={**with_step_up(OWNER), **unique_idem()}, json={"approval_id": identity, "new_daily_cap": "600"})
        self.assertEqual(second.status_code, 403, second.text)
        self.assertEqual(self.client.get("/campaigns/" + self.campaign, headers=OWNER).json()["budget"]["daily_cap"], "550")

    def test_approved_rejected_and_changes_requested_are_terminal_for_new_decisions(self):
        for decision, expected in (("APPROVE", "APPROVED"), ("REJECT", "REJECTED"),
                                   ("REQUEST_CHANGES", "CHANGES_REQUESTED")):
            identity = self.request().json()["id"]
            closed = self.decision(identity, decision, reason="Confira o texto.")
            self.assertEqual(closed.status_code, 200, closed.text)
            self.assertEqual(closed.json()["status"], expected)
            for next_decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
                retry = self.decision(identity, next_decision, headers={**with_step_up(FINANCE), **unique_idem()})
                self.assertEqual(retry.status_code, 409, retry.text)
                self.assertEqual(self.row(identity).status, expected)

    def test_same_nonce_replays_historical_vote_without_changing_consumed_status(self):
        identity = self.request(body={"campaign_id": self.campaign, "kind": "BUDGET_CHANGE"}).json()["id"]
        headers = {**with_step_up(APPROVER), **unique_idem()}
        first = self.decision(identity, headers=headers)
        self.assertEqual(first.status_code, 200)
        applied = self.client.patch("/campaigns/" + self.campaign + "/budget",
            headers={**with_step_up(OWNER), **unique_idem()}, json={"approval_id": identity, "new_daily_cap": "550"})
        self.assertEqual(applied.status_code, 202, applied.text)
        replay = self.decision(identity, headers=headers)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(self.row(identity).status, "APPLIED")
        votes = [entry for entry in self.state.audit.list_for_tenant("demo-tenant") if entry.action == "APPROVAL_APPROVE"]
        self.assertEqual(len(votes), 1)

    def test_context_binding_rejects_decision_actor_reason_action_and_target_rebind(self):
        identity = self.request(body={"campaign_id": self.campaign, "kind": "PUBLISH",
                                      "requires_dual_approval": True}).json()["id"]
        headers = {**with_step_up(APPROVER), **unique_idem()}
        first = self.decision(identity, headers=headers)
        self.assertEqual(first.json()["status"], "PENDING")
        for kwargs in ({"decision": "REJECT"}, {"reason": "Outro motivo"},
                       {"headers": {**with_step_up(FINANCE), "Idempotency-Key": headers["Idempotency-Key"]}}):
            response = self.decision(identity, **{"headers": headers, **kwargs})
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json()["code"], "IDEMPOTENCY_CONFLICT")
        other = self.request().json()["id"]
        self.assertEqual(self.decision(other, headers=headers).status_code, 409)
        self.assertEqual(self.row(identity).status, "PENDING")
        self.assertEqual(len(self.row(identity).decided_by), 1)
        second = self.decision(identity, headers={**with_step_up(FINANCE), **unique_idem()})
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["status"], "APPROVED")
        self.assertEqual(len(second.json()["decided_by"]), 2)

    def test_create_nonce_is_bound_to_body_actor_and_business_unit(self):
        body, headers = {"campaign_id": self.campaign, "kind": "PUBLISH"}, {**OWNER, **unique_idem()}
        first = self.request(body=body, headers=headers)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.request(body=body, headers=headers).json(), first.json())
        for changed in ({**body, "kind": "BUDGET_CHANGE"}, {**body, "amount": "10"},
                        {**body, "requires_dual_approval": True}):
            self.assertEqual(self.request(body=changed, headers=headers).status_code, 409)
        actor = {**MARKETER, "Idempotency-Key": headers["Idempotency-Key"]}
        self.assertEqual(self.request(body=body, headers=actor).status_code, 409)
        self.state.tokens["demo-owner-token"] = replace(self.state.tokens["demo-owner-token"], business_unit_id="other-unit")
        self.assertEqual(self.request(body=body, headers=headers).status_code, 409)
        self.assertEqual(len(self.state.approvals.list_for_tenant("demo-tenant")), 1)

    def test_changes_reason_survives_restart_and_is_returned_only_with_owned_approval(self):
        identity = self.request().json()["id"]
        reason = "Ajuste o convite e evite uma promessa de resultado."
        result = self.decision(identity, "REQUEST_CHANGES", reason)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["decision_reason"], reason)
        peer = TestClient(create_app(env="test", db_path=str(self.path)))
        self.addCleanup(peer.app.state.campaia.db.close)
        listed = peer.get("/approvals", headers=VIEWER)
        self.assertEqual(listed.headers["Cache-Control"], "private, no-store")
        self.assertEqual(listed.json()[0]["decision_reason"], reason)
        self.assertEqual(peer.get("/approvals", headers=OTHER_OWNER).json(), [])
        self.state.tokens["demo-viewer-token"] = replace(self.state.tokens["demo-viewer-token"], business_unit_id="foreign-unit")
        self.assertEqual(self.client.get("/approvals", headers=VIEWER).json(), [])

    def test_same_actor_cannot_cast_a_second_vote_in_dual_review(self):
        identity = self.request(body={"campaign_id": self.campaign, "kind": "PUBLISH",
                                      "requires_dual_approval": True}).json()["id"]
        self.assertEqual(self.decision(identity).status_code, 200)
        repeat = self.decision(identity)
        self.assertEqual(repeat.status_code, 403, repeat.text)
        self.assertEqual(repeat.json()["code"], "SEPARATION_OF_DUTIES")
        self.assertEqual(self.row(identity).status, "PENDING")

    def test_current_policy_upgrades_an_incorrect_legacy_pending_dual_flag_before_first_vote(self):
        install_test_creative_provider(self.state)
        material = self.client.post("/campaigns/" + self.campaign + "/proposals/audience",
            headers={**OWNER, **unique_idem()}, json={"expected_plan_version": 1, "channel": "GOOGLE_ADS",
                "audience": "Adultos", "region": "BR", "sensitive_declared": True})
        self.assertEqual(material.status_code, 201, material.text)
        validated = self.client.post("/campaigns/" + self.campaign + "/validate",
                                     headers={**OWNER, **unique_idem()})
        self.assertTrue(validated.json()["requires_dual_approval"])
        identity = self.request().json()["id"]
        self.row(identity).requires_dual_approval = False  # Legacy incomplete metadata, not a client authority.
        first = self.decision(identity)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertTrue(first.json()["requires_dual_approval"])
        self.assertEqual(first.json()["status"], "PENDING")
        final = self.decision(identity, headers={**with_step_up(FINANCE), **unique_idem()})
        self.assertEqual(final.status_code, 200, final.text)
        self.assertEqual(final.json()["status"], "APPROVED")

    def test_two_reviewers_cannot_close_a_single_review_with_conflicting_decisions(self):
        identity = self.request().json()["id"]
        peer = TestClient(create_app(env="test", db_path=str(self.path)))
        self.addCleanup(peer.app.state.campaia.db.close)
        gate = threading.Barrier(2)
        def run(client, decision, actor):
            gate.wait()
            return self.decision(identity, decision, headers={**with_step_up(actor), **unique_idem()}, client=client)
        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(run, self.client, "APPROVE", APPROVER)
            two = pool.submit(run, peer, "REJECT", FINANCE)
            results = [one.result(timeout=10), two.result(timeout=10)]
        self.assertEqual(sorted(result.status_code for result in results), [200, 409],
                         [result.text for result in results])
        actions = [entry.action for entry in self.state.audit.list_for_tenant("demo-tenant")
                   if entry.action in ("APPROVAL_APPROVE", "APPROVAL_REJECT")]
        self.assertEqual(len(actions), 1)

    def test_audit_failure_rolls_back_status_reason_and_contextual_idempotency(self):
        identity = self.request().json()["id"]
        headers = {**with_step_up(APPROVER), **unique_idem()}
        original = self.state.audit.append
        def fail(**event):
            original(**event)
            if event["action"] == "APPROVAL_REQUEST_CHANGES":
                raise RuntimeError("injected review rollback")
        with patch.object(self.state.audit, "append", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "injected review rollback"):
                self.decision(identity, "REQUEST_CHANGES", "Ajustar.", headers=headers)
        self.assertEqual(self.row(identity).status, "PENDING")
        self.assertNotIn("decision_reason", self.row(identity).context)
        self.assertIsNone(self.state.idempotency.get("demo-tenant", "http:decide_approval:" + headers["Idempotency-Key"]))
        fixed = self.decision(identity, "REQUEST_CHANGES", "Ajustar.", headers=headers)
        self.assertEqual(fixed.status_code, 200, fixed.text)

    def test_authority_is_rechecked_inside_the_f3_transaction(self):
        identity = self.request().json()["id"]
        original = self.state.idempotency.execute
        def revoke(tenant, key, operation):
            if key.startswith("http:decide_approval:"):
                self.state.tokens["demo-approver-token"] = replace(self.state.tokens["demo-approver-token"],
                                                                  roles=frozenset({Role.VIEWER}))
            return original(tenant, key, operation)
        with patch.object(self.state.idempotency, "execute", side_effect=revoke):
            result = self.decision(identity)
        self.assertEqual(result.status_code, 403, result.text)
        self.assertEqual(self.row(identity).status, "PENDING")

    def test_large_or_invalid_unicode_decision_has_no_effect(self):
        identity = self.request().json()["id"]
        before = len(self.state.audit.list_for_tenant("demo-tenant"))
        for reason in ("x" * 1001, chr(0xD800)):
            result = self.decision(identity, "REQUEST_CHANGES", reason)
            self.assertEqual(result.status_code, 422, result.text)
        oversized = self.client.post("/approvals/" + identity + "/decision",
            headers={**with_step_up(APPROVER), **unique_idem(), "Content-Type": "application/json"},
            content=b"x" * (64 * 1024 + 1))
        self.assertEqual(oversized.status_code, 413, oversized.text)
        self.assertEqual(self.row(identity).status, "PENDING")
        self.assertEqual(len(self.state.audit.list_for_tenant("demo-tenant")), before)


if __name__ == "__main__":
    unittest.main()
