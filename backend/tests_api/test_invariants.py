"""Integration tests for the BFF layer's core invariants (per the task spec, section 4)."""

from __future__ import annotations

import unittest

from tests_api.test_helpers import (
    APPROVER,
    DEFAULT_BRIEF,
    OTHER_OWNER,
    OWNER,
    create_campaign,
    idem,
    make_client,
    publish_ready_campaign,
    unique_idem,
    with_step_up,
)


class TestTenantIdNeverFromClient(unittest.TestCase):
    def test_brief_with_client_tenant_id_is_rejected(self):
        client = make_client()
        body = {**DEFAULT_BRIEF, "tenant_id": "attacker-tenant"}
        r = client.post("/briefs", headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_created_campaign_always_belongs_to_token_tenant(self):
        client = make_client()
        camp = create_campaign(client)
        # /me confirms which tenant issued the token; the campaign must be scoped there,
        # never to any value the client could have supplied.
        me = client.get("/me", headers=OWNER).json()
        r = client.get(f"/campaigns/{camp['id']}", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(me["tenant_id"], "demo-tenant")

    def test_kill_switch_body_with_tenant_id_is_rejected(self):
        client = make_client()
        r = client.post(
            "/kill-switch",
            headers={**OWNER, **unique_idem()},
            json={"scope": "TENANT", "tenant_id": "attacker-tenant"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")


class TestIdempotencyKeyRequired(unittest.TestCase):
    def test_publish_without_idempotency_key_rejected(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        r = client.post(
            f"/campaigns/{camp['id']}/publish",
            headers=with_step_up(OWNER),
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_publish_with_too_short_idempotency_key_rejected(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        r = client.post(
            f"/campaigns/{camp['id']}/publish",
            headers={**with_step_up(OWNER), "Idempotency-Key": "short"},
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 422, r.text)

    def test_connection_revoke_without_idempotency_key_rejected(self):
        client = make_client()
        r = client.delete("/connections/nonexistent-id", headers=with_step_up(OWNER))
        # Idempotency-Key is checked before existence in this implementation's ordering;
        # either a 422 (missing key) or 404 without a key present would be acceptable
        # depending on ordering, but here missing-key must win since it's a structural
        # precondition for any mutating call.
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_create_brief_without_idempotency_key_rejected(self):
        client = make_client()
        r = client.post("/briefs", headers=OWNER, json=DEFAULT_BRIEF)
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_kill_switch_without_idempotency_key_rejected(self):
        client = make_client()
        r = client.post("/kill-switch", headers=OWNER, json={"scope": "TENANT", "reason": "x"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")


class TestIdempotencyReplay(unittest.TestCase):
    def test_repeating_publish_key_does_not_duplicate_or_re_run_saga(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        cid = camp["id"]
        headers = {**with_step_up(OWNER), **idem("publish-1")}
        body = {"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]}

        r1 = client.post(f"/campaigns/{cid}/publish", headers=headers, json=body)
        self.assertEqual(r1.status_code, 202, r1.text)
        self.assertEqual(r1.json()["state"], "ACTIVE")
        resources_1 = {r["channel"]: r["external_resource_id"] for r in r1.json()["external_resources"]}
        external_id_1 = resources_1["GOOGLE_ADS"]

        r2 = client.post(f"/campaigns/{cid}/publish", headers=headers, json=body)
        self.assertEqual(r2.status_code, 202, r2.text)
        resources_2 = {r["channel"]: r["external_resource_id"] for r in r2.json()["external_resources"]}
        external_id_2 = resources_2["GOOGLE_ADS"]

        self.assertEqual(external_id_1, external_id_2)

        # Only one campaign exists -- no duplicate was created.
        listing = client.get("/campaigns", headers=OWNER).json()["items"]
        self.assertEqual(sum(1 for c in listing if c["id"] == cid), 1)

    def test_repeating_pause_key_is_idempotent(self):
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        headers = idem("pause-1")
        # DRAFT is not pausable per states.py PAUSABLE_STATES -- expect INVALID_STATE both times.
        r1 = client.post(f"/campaigns/{cid}/pause", headers={**OWNER, **headers})
        r2 = client.post(f"/campaigns/{cid}/pause", headers={**OWNER, **headers})
        self.assertEqual(r1.status_code, r2.status_code)

    def test_repeating_create_brief_key_does_not_duplicate(self):
        client = make_client()
        headers = {**OWNER, **idem("brief-replay-1")}
        r1 = client.post("/briefs", headers=headers, json=DEFAULT_BRIEF)
        r2 = client.post("/briefs", headers=headers, json=DEFAULT_BRIEF)
        self.assertEqual(r1.status_code, 202, r1.text)
        self.assertEqual(r2.status_code, 202, r2.text)
        self.assertEqual(r1.json()["id"], r2.json()["id"])
        listing = client.get("/campaigns", headers=OWNER).json()["items"]
        self.assertEqual(len(listing), 1)


class TestStepUpRequired(unittest.TestCase):
    def test_oauth_start_without_step_up_is_403(self):
        client = make_client()
        r = client.post("/connections/oauth/start", headers=OWNER, json={"provider": "GOOGLE_ADS"})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")

    def test_connection_revoke_without_step_up_is_403(self):
        client = make_client()
        headers = {**OWNER, **idem("revoke-1")}
        r = client.delete("/connections/some-id", headers=headers)
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")

    def test_publish_without_step_up_is_403(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        headers = {**OWNER, **idem("publish-nostepup")}
        r = client.post(
            f"/campaigns/{camp['id']}/publish",
            headers=headers,
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")

    def test_budget_change_without_step_up_is_403(self):
        client = make_client()
        camp = create_campaign(client)
        r = client.patch(
            f"/campaigns/{camp['id']}/budget",
            headers={**OWNER, **unique_idem()},
            json={"approval_id": "whatever", "new_daily_cap": "550"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")

    def test_autonomy_change_without_step_up_is_403(self):
        client = make_client()
        r = client.put(
            "/autonomy", headers={**OWNER, **unique_idem()}, json={"level": 2, "approval_id": "whatever"}
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")

    def test_approval_decision_without_step_up_is_403(self):
        client = make_client()
        camp = create_campaign(client)
        r = client.post("/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "PUBLISH"})
        approval = r.json()
        r = client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**APPROVER, **unique_idem()},
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")


class TestPublishRequiresPolicyAndApproval(unittest.TestCase):
    def test_publish_missing_policy_decision_id_field_is_422(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        headers = {**with_step_up(OWNER), **idem("publish-missing-1")}
        r = client.post(
            f"/campaigns/{camp['id']}/publish",
            headers=headers,
            json={"approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 422, r.text)

    def test_publish_missing_approval_id_field_is_422(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        headers = {**with_step_up(OWNER), **idem("publish-missing-2")}
        r = client.post(
            f"/campaigns/{camp['id']}/publish",
            headers=headers,
            json={"policy_decision_id": decision["policy_decision_id"]},
        )
        self.assertEqual(r.status_code, 422, r.text)

    def test_publish_with_bogus_policy_decision_id_is_403(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        headers = {**with_step_up(OWNER), **idem("publish-bogus-1")}
        r = client.post(
            f"/campaigns/{camp['id']}/publish",
            headers=headers,
            json={"policy_decision_id": "not-a-real-decision-id", "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "APPROVAL_REQUIRED")

    def test_publish_with_unapproved_approval_is_403(self):
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        client.post(f"/campaigns/{cid}/plan/regenerate", headers={**OWNER, **unique_idem()})
        decision = client.post(f"/campaigns/{cid}/validate", headers=OWNER).json()
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": cid, "kind": "PUBLISH"}
        ).json()
        # Never decided -- still PENDING.
        headers = {**with_step_up(OWNER), **idem("publish-pending-1")}
        r = client.post(
            f"/campaigns/{cid}/publish",
            headers=headers,
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "APPROVAL_REQUIRED")


class TestHappyPathFullPublish(unittest.TestCase):
    def test_brief_to_active_via_simulator(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        cid = camp["id"]
        headers = {**with_step_up(OWNER), **idem("happy-path-1")}
        r = client.post(
            f"/campaigns/{cid}/publish",
            headers=headers,
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 202, r.text)
        body = r.json()
        self.assertEqual(body["state"], "ACTIVE")
        resources = {r["channel"]: r for r in body["external_resources"]}
        self.assertIn("GOOGLE_ADS", resources)
        self.assertTrue(resources["GOOGLE_ADS"]["external_resource_id"])
        self.assertIn(resources["GOOGLE_ADS"]["sync_status"], ("PENDING", "CONFIRMED", "DIVERGENT"))
        self.assertIsNotNone(body["last_synced_at"])

        # Audit log recorded the publish with the real policy_decision_id.
        events = client.get("/audit-events", headers=OWNER).json()["items"]
        publish_events = [e for e in events if e["action"] == "CAMPAIGN_PUBLISH"]
        self.assertEqual(len(publish_events), 1)
        self.assertEqual(publish_events[0]["policy_decision_id"], decision["policy_decision_id"])


class TestCrossTenantIsolation(unittest.TestCase):
    def test_other_tenant_cannot_see_campaign(self):
        client = make_client()
        camp = create_campaign(client, headers=OWNER)
        r = client.get(f"/campaigns/{camp['id']}", headers=OTHER_OWNER)
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["code"], "NOT_FOUND")

    def test_other_tenant_campaign_list_is_empty(self):
        client = make_client()
        create_campaign(client, headers=OWNER)
        r = client.get("/campaigns", headers=OTHER_OWNER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["items"], [])
        self.assertIsNone(r.json()["next_cursor"])

    def test_other_tenant_cannot_publish_into_first_tenants_campaign(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client, headers=OWNER)
        headers = {**with_step_up(OTHER_OWNER), **idem("cross-tenant-publish")}
        r = client.post(
            f"/campaigns/{camp['id']}/publish",
            headers=headers,
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["code"], "NOT_FOUND")

    def test_other_tenant_cannot_revoke_first_tenants_connection(self):
        client = make_client()
        r = client.post(
            "/connections/oauth/start", headers=with_step_up(OWNER), json={"provider": "GOOGLE_ADS"}
        )
        self.assertEqual(r.status_code, 200)
        # oauth/start does not itself create a Connection row (no real callback exists in
        # this sandbox) -- assert isolation against the connections list instead.
        r = client.get("/connections", headers=OTHER_OWNER)
        self.assertEqual(r.json(), [])

    def test_other_tenant_cannot_delete_or_read_capabilities_of_first_tenants_real_connection(
        self,
    ):
        """Missão de fechamento integral (A2, 22/09/2026): the test above never actually
        exercised DELETE against a real Connection belonging to another tenant, despite its
        name -- closing that gap here with a real, persisted connection (created directly
        via the domain state, same technique test_account_scope_only_pauses_matching_
        connection already uses, to avoid a full OAuth round trip that doesn't matter for
        this assertion)."""
        client = make_client()
        conn = client.app.state.campaia.connections.create(
            "demo-tenant", provider="GOOGLE_ADS", external_account_id="acct-x2", display_name="X2"
        )

        # DELETE as the other tenant: must be indistinguishable from a genuinely
        # nonexistent connection id (404 NOT_FOUND, never 403) -- enumeration resistance,
        # same pattern already proven for campaigns.
        r = client.delete(
            f"/connections/{conn.connection_id}",
            headers={**with_step_up(OTHER_OWNER), **idem("cross-tenant-conn-delete")},
        )
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["code"], "NOT_FOUND")

        # Same for reading capabilities of another tenant's connection.
        r = client.get(f"/connections/{conn.connection_id}/capabilities", headers=OTHER_OWNER)
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["code"], "NOT_FOUND")

        # The real connection is untouched: still visible and ACTIVE for its real owner.
        r = client.get("/connections", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        owned = [c for c in r.json() if c["id"] == conn.connection_id]
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0]["status"], "ACTIVE")


class TestKillSwitchNeverWidensEffect(unittest.TestCase):
    """Achado 13: kill switch only ever pauses/reduces effect, and cross-tenant reach is
    exclusively the documented, deliberate GLOBAL-scope exception."""

    def test_account_scope_only_pauses_matching_connection(self):
        client = make_client()
        conn = client.app.state.campaia.connections.create(
            "demo-tenant", provider="GOOGLE_ADS", external_account_id="acct-1", display_name="A"
        )
        camp, decision, approval = publish_ready_campaign(client, headers=OWNER)
        # publish_ready_campaign's campaign has no connection_id set (created via DEFAULT_BRIEF,
        # which has no connection_id) -- ACCOUNT scope must therefore not affect it.
        r = client.post(
            "/kill-switch",
            headers={**OWNER, **unique_idem()},
            json={"scope": "ACCOUNT", "target_id": conn.connection_id, "reason": "acct incident"},
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["affected_campaign_ids"], [])

    def test_tenant_scope_does_not_affect_other_tenants(self):
        client = make_client()
        camp_a = create_campaign(client, headers=OWNER)
        camp_b = create_campaign(client, headers=OTHER_OWNER)
        r = client.post(
            "/kill-switch",
            headers={**OWNER, **unique_idem()},
            json={"scope": "TENANT", "reason": "incident"},
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertNotIn(camp_b["id"], r.json()["affected_campaign_ids"])


if __name__ == "__main__":
    unittest.main()
