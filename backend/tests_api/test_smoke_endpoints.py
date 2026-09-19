"""Smoke tests: every endpoint returns a sane response for at least one call shape."""

from __future__ import annotations

import unittest

from tests_api.test_helpers import (
    APPROVER,
    OWNER,
    create_campaign,
    idem,
    make_client,
    unique_idem,
    with_step_up,
)


class TestSmokeEndpoints(unittest.TestCase):
    def test_me(self):
        client = make_client()
        r = client.get("/me", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["tenant_id"], "demo-tenant")
        self.assertIn("CAMPAIGN_VIEW", body["permissions"])

    def test_brand_profiles_crud(self):
        client = make_client()
        r = client.get("/brand-profiles", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

        r = client.post(
            "/brand-profiles",
            headers={**OWNER, **unique_idem()},
            json={"name": "Acme", "tone": "playful", "colors": ["#fff"], "differentiators": ["fast"], "restrictions": ["no gambling"]},
        )
        self.assertEqual(r.status_code, 201, r.text)
        profile_id = r.json()["id"]

        r = client.get("/brand-profiles", headers=OWNER)
        self.assertEqual(len(r.json()), 1)
        self.assertEqual(r.json()[0]["id"], profile_id)

    def test_brand_profile_create_without_idempotency_key_rejected(self):
        client = make_client()
        r = client.post(
            "/brand-profiles",
            headers=OWNER,
            json={"name": "Acme", "tone": "playful"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_brand_profile_requires_tone(self):
        """Contract: BrandProfileInput required = [name, tone] -- no default tone."""
        client = make_client()
        r = client.post(
            "/brand-profiles",
            headers={**OWNER, **unique_idem()},
            json={"name": "Acme"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_brand_profile_denied_for_viewer(self):
        client = make_client()
        from tests_api.test_helpers import VIEWER

        r = client.post("/brand-profiles", headers={**VIEWER, **unique_idem()}, json={"name": "X", "tone": "neutral"})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")

    def test_connections_list_empty_then_oauth_start(self):
        client = make_client()
        r = client.get("/connections", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

        r = client.post(
            "/connections/oauth/start",
            headers=with_step_up(OWNER),
            json={"provider": "GOOGLE_ADS", "display_name": "Test"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("authorization_url", body)
        self.assertTrue(body["authorization_url"].startswith("https://"))
        self.assertIn(".invalid", body["authorization_url"])  # clearly-fake domain
        self.assertIn("state", body)

    def test_connection_revoke_not_found(self):
        client = make_client()
        headers = {**with_step_up(OWNER), **idem("revoke-missing")}
        r = client.delete("/connections/does-not-exist", headers=headers)
        self.assertEqual(r.status_code, 404, r.text)

    def test_connection_capabilities_not_found(self):
        client = make_client()
        r = client.get("/connections/does-not-exist/capabilities", headers=OWNER)
        self.assertEqual(r.status_code, 404, r.text)

    def test_briefs_and_campaigns_list_detail(self):
        client = make_client()
        camp = create_campaign(client)
        self.assertEqual(camp["state"], "DRAFT")

        r = client.get("/campaigns", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)
        self.assertIn("next_cursor", body)
        self.assertIsNone(body["next_cursor"])
        self.assertEqual(len(body["items"]), 1)

        r = client.get(f"/campaigns/{camp['id']}", headers=OWNER)
        self.assertEqual(r.status_code, 200)

        r = client.get("/campaigns/does-not-exist", headers=OWNER)
        self.assertEqual(r.status_code, 404)

    def test_campaigns_list_filters_by_state(self):
        client = make_client()
        camp = create_campaign(client)

        r = client.get("/campaigns", headers=OWNER, params={"state": "DRAFT"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["items"]), 1)

        r = client.get("/campaigns", headers=OWNER, params={"state": "ACTIVE"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["items"], [])

    def test_campaign_response_shape_matches_contract(self):
        client = make_client()
        camp = create_campaign(client)
        self.assertIn("id", camp)
        self.assertIn("name", camp)
        self.assertIn("objective", camp)
        self.assertIn("channels", camp)
        self.assertIn("external_resources", camp)
        self.assertIsInstance(camp["external_resources"], list)
        self.assertIn("budget", camp)
        self.assertEqual(set(camp["budget"].keys()), {"currency", "total_amount", "daily_cap", "spent_to_date"})

    def test_plan_get_and_regenerate(self):
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]

        r = client.get(f"/campaigns/{cid}/plan", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["plan"])
        self.assertEqual(r.json()["plan_version"], 0)

        r = client.post(f"/campaigns/{cid}/plan/regenerate", headers={**OWNER, **unique_idem()})
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["plan_version"], 1)
        self.assertIsNotNone(r.json()["plan"])

    def test_regenerate_plan_without_idempotency_key_rejected(self):
        client = make_client()
        camp = create_campaign(client)
        r = client.post(f"/campaigns/{camp['id']}/plan/regenerate", headers=OWNER)
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_validate_returns_policy_decision(self):
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        client.post(f"/campaigns/{cid}/plan/regenerate", headers={**OWNER, **unique_idem()})
        r = client.post(f"/campaigns/{cid}/validate", headers=OWNER)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn(r.json()["outcome"], ("APPROVABLE", "BLOCKED", "NEEDS_CHANGES"))

    def test_pause_invalid_state_from_draft(self):
        client = make_client()
        camp = create_campaign(client)
        headers = {**OWNER, **idem("pause-draft")}
        r = client.post(f"/campaigns/{camp['id']}/pause", headers=headers)
        self.assertEqual(r.status_code, 409, r.text)
        self.assertEqual(r.json()["code"], "INVALID_STATE")

    def test_kill_switch_tenant_scope(self):
        client = make_client()
        create_campaign(client)
        r = client.post(
            "/kill-switch",
            headers={**OWNER, **unique_idem()},
            json={"scope": "TENANT", "reason": "incident"},
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertIn("affected_campaign_ids", r.json())

    def test_kill_switch_campaign_scope_not_pausable_from_draft(self):
        client = make_client()
        camp = create_campaign(client)
        r = client.post(
            "/kill-switch",
            headers={**OWNER, **unique_idem()},
            json={"scope": "CAMPAIGN", "target_id": camp["id"], "reason": "test"},
        )
        # DRAFT is not in PAUSABLE_STATES -- kill switch only reduces effect from a live state.
        self.assertEqual(r.status_code, 409, r.text)
        self.assertEqual(r.json()["code"], "INVALID_STATE")

    def test_kill_switch_rejects_lowercase_scope(self):
        """Achado 13: the contract's scope enum is uppercase only."""
        client = make_client()
        r = client.post(
            "/kill-switch",
            headers={**OWNER, **unique_idem()},
            json={"scope": "tenant", "reason": "incident"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_kill_switch_platform_scope_pauses_matching_channel(self):
        client = make_client()
        camp = create_campaign(client)
        r = client.post(
            "/kill-switch",
            headers={**OWNER, **unique_idem()},
            json={"scope": "PLATFORM", "target_id": "GOOGLE_ADS", "reason": "incident"},
        )
        self.assertEqual(r.status_code, 202, r.text)
        # DRAFT campaign is not pausable so it is simply skipped, not an error.
        self.assertEqual(r.json()["affected_campaign_ids"], [])

    def test_kill_switch_global_scope_crosses_tenants(self):
        client = make_client()
        from tests_api.test_helpers import OTHER_OWNER, publish_ready_campaign

        camp, decision, approval = publish_ready_campaign(client, headers=OWNER)
        headers = {**with_step_up(OWNER), **unique_idem()}
        r = client.post(
            f"/campaigns/{camp['id']}/publish",
            headers=headers,
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 202, r.text)

        r = client.post(
            "/kill-switch",
            headers={**OTHER_OWNER, **unique_idem()},
            json={"scope": "GLOBAL", "reason": "global incident"},
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertIn(camp["id"], r.json()["affected_campaign_ids"])

    def test_insights_is_honest_placeholder(self):
        client = make_client()
        camp = create_campaign(client)
        r = client.get(f"/campaigns/{camp['id']}/insights", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["points"], [])
        self.assertIn("no analytics layer", body["note"].lower())

    def test_insights_validates_date_query_params(self):
        client = make_client()
        camp = create_campaign(client)
        r = client.get(
            f"/campaigns/{camp['id']}/insights",
            headers=OWNER,
            params={"from": "2026-01-01", "to": "2026-01-31"},
        )
        self.assertEqual(r.status_code, 200, r.text)

        r = client.get(
            f"/campaigns/{camp['id']}/insights",
            headers=OWNER,
            params={"from": "not-a-date"},
        )
        self.assertEqual(r.status_code, 422, r.text)

    def test_approvals_list_and_create(self):
        client = make_client()
        camp = create_campaign(client)
        r = client.get("/approvals", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

        r = client.post("/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "PUBLISH"})
        self.assertEqual(r.status_code, 201, r.text)
        approval = r.json()
        self.assertIn("id", approval)
        self.assertIn("reason", approval)
        self.assertIn("plan_version", approval)
        self.assertIn("expires_at", approval)

        r = client.get("/approvals", headers=OWNER)
        self.assertEqual(len(r.json()), 1)

    def test_approval_decision_separation_of_duties(self):
        """The requester cannot approve their own request (permissions.can_approve)."""
        client = make_client()
        camp = create_campaign(client)
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "PUBLISH"}
        ).json()
        r = client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(OWNER), **unique_idem()},  # OWNER is also the requester here
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "SEPARATION_OF_DUTIES")

    def test_approval_decision_request_changes(self):
        client = make_client()
        camp = create_campaign(client)
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "PUBLISH"}
        ).json()
        r = client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "REQUEST_CHANGES", "reason": "Precisa ajustar publico-alvo."},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "CHANGES_REQUESTED")

    def test_approval_decision_without_idempotency_key_rejected(self):
        client = make_client()
        camp = create_campaign(client)
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "PUBLISH"}
        ).json()
        r = client.post(
            f"/approvals/{approval['id']}/decision",
            headers=with_step_up(APPROVER),
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_autonomy_get_and_put(self):
        client = make_client()
        r = client.get("/autonomy", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["level"], 1)  # DEFAULT_LEVEL = APROVADO = 1
        self.assertEqual(body["level_label"], "APROVADO")
        self.assertIsInstance(body["max_budget_change_pct"], (int, float))
        self.assertIn("always_require_human", body)
        self.assertIn("updated_at", body)

        camp = create_campaign(client)
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "AUTONOMY_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )

        r = client.put(
            "/autonomy",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"level": 1, "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 200, r.text)

        # Above the contracted ceiling (max_level_allowed defaults to APROVADO=1) must fail.
        approval2 = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "AUTONOMY_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval2['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )
        r = client.put(
            "/autonomy",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"level": 3, "approval_id": approval2["id"]},
        )
        self.assertEqual(r.status_code, 422, r.text)

    def test_autonomy_put_requires_approved_approval(self):
        client = make_client()
        r = client.put(
            "/autonomy",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"level": 1, "approval_id": "does-not-exist"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "APPROVAL_REQUIRED")

    def test_autonomy_put_rejects_pending_approval(self):
        client = make_client()
        camp = create_campaign(client)
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "AUTONOMY_CHANGE"}
        ).json()
        r = client.put(
            "/autonomy",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"level": 1, "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "APPROVAL_REQUIRED")

    def test_audit_events_lists_after_mutation(self):
        client = make_client()
        create_campaign(client)
        r = client.get("/audit-events", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)
        self.assertIn("next_cursor", body)
        actions = [e["action"] for e in body["items"]]
        self.assertIn("CAMPAIGN_CREATE", actions)
        for event in body["items"]:
            self.assertIn("occurred_at", event)
            self.assertIn("actor_kind", event)
            self.assertIn("actor_id", event)
            self.assertIn("evidence", event)
            self.assertEqual(event["actor_kind"], "USER")

    def test_audit_events_filters_by_campaign_id(self):
        client = make_client()
        camp1 = create_campaign(client)
        camp2 = create_campaign(client)
        r = client.get("/audit-events", headers=OWNER, params={"campaign_id": camp1["id"]})
        self.assertEqual(r.status_code, 200)
        targets = {e["target"] for e in r.json()["items"]}
        self.assertIn(camp1["id"], targets)
        self.assertNotIn(camp2["id"], targets)

    def test_budget_patch_happy_path(self):
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": cid, "kind": "BUDGET_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )
        r = client.patch(
            f"/campaigns/{cid}/budget",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"approval_id": approval["id"], "new_daily_cap": "550"},
        )
        self.assertEqual(r.status_code, 202, r.text)

    def test_budget_patch_accepts_contract_daily_cap_alias(self):
        # Regression for Achado 18 (backend/api/models.py, BudgetPatchRequest):
        # bff-openapi.yaml's updateBudget requestBody names this field `daily_cap`,
        # not `new_daily_cap`. A client following the contract literally must be
        # accepted, not rejected by `extra="forbid"`.
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": cid, "kind": "BUDGET_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )
        r = client.patch(
            f"/campaigns/{cid}/budget",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"approval_id": approval["id"], "daily_cap": "550"},
        )
        self.assertEqual(r.status_code, 202, r.text)

    def test_budget_patch_without_idempotency_key_rejected(self):
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": cid, "kind": "BUDGET_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )
        r = client.patch(
            f"/campaigns/{cid}/budget",
            headers=with_step_up(OWNER),
            json={"approval_id": approval["id"], "new_daily_cap": "550"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_budget_patch_rejects_large_swing(self):
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": cid, "kind": "BUDGET_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )
        # default max_change_pct is 20% -- daily_cap 500 -> 5000 is a 900% swing.
        r = client.patch(
            f"/campaigns/{cid}/budget",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"approval_id": approval["id"], "new_daily_cap": "5000"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "BUDGET_LIMIT")

    def test_connection_revoke_returns_204_no_body(self):
        client = make_client()
        # oauth/start does not itself create a Connection row (no real OAuth callback
        # exists in this sandbox) -- seed one directly via the in-memory repository to
        # exercise the real revoke response shape end-to-end.
        conn = client.app.state.campaia.connections.create(
            "demo-tenant",
            provider="GOOGLE_ADS",
            external_account_id="acct-1",
            display_name="Test Account",
        )
        headers = {**with_step_up(OWNER), **unique_idem()}
        r = client.delete(f"/connections/{conn.connection_id}", headers=headers)
        self.assertEqual(r.status_code, 204, r.text)
        self.assertEqual(r.content, b"")

    def test_connection_status_defaults_to_active(self):
        client = make_client()
        conn = client.app.state.campaia.connections.create(
            "demo-tenant",
            provider="GOOGLE_ADS",
            external_account_id="acct-1",
            display_name="Test Account",
        )
        self.assertEqual(conn.status, "ACTIVE")


if __name__ == "__main__":
    unittest.main()
