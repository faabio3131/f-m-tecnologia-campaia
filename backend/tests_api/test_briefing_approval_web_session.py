"""HTTP-level integration tests for WP-05 (briefing -> estrategia -> validacao ->
aprovacao), exercised through REAL Web session cookies -- not the fixture Bearer token.

Every route this journey uses (POST /briefs, GET/POST /campaigns/{id}/plan[/regenerate],
POST .../validate, GET/POST /approvals, POST /approvals/{id}/decision) already existed and
was already tested via Bearer fixtures (tests_api/test_helpers.py's publish_ready_campaign,
tests_api/test_smoke_endpoints.py). What had NEVER been verified before this Work Package is
that api/deps.py's require_auth() session-cookie branch actually authorizes these same
routes end-to-end for a REAL logged-in browser session -- the CURRENT-reconciliation check
this Work Package's own frontend depends on. Drives the full OIDC flow through the real
Starlette app exactly like tests_api/test_tenant_switch.py -- nothing here mocks api/oidc.py,
api/state.py, or api/routes_campaigns.py/api/routes_approvals.py.

Two SEPARATE TestClient instances (two separate cookie jars) stand in for two separate real
browser sessions: `owner` proposes (brief -> plan -> validate -> request approval), `approver`
decides -- proving segregation of duties (roadmap WP-05 acceptance criterion: "tentativa de
autoaprovacao e recusada visivelmente") holds under real session auth too, not just the
Bearer-fixture path test_smoke_endpoints.py already covered. `owner` (not `marketer`) is the
proposer deliberately: OWNER holds every Permission including APPROVAL_DECIDE, so their own
self-approval attempt is rejected specifically by campaia_core.permissions.can_approve's
requester_id check (SEPARATION_OF_DUTIES) rather than by a role that simply lacks
APPROVAL_DECIDE at all (a different, also-real rejection reason, covered separately by
test_viewer_role_cannot_submit_a_brief_via_real_session for CAMPAIGN_CREATE).
"""

from __future__ import annotations

import os
import re
import unittest

from starlette.testclient import TestClient

from api.main import create_app

os.environ.setdefault("CAMPAIA_ENV", "test")

_idem_counter = [0]


def _unique_idem() -> dict:
    _idem_counter[0] += 1
    return {"Idempotency-Key": f"web-session-journey-{_idem_counter[0]}".ljust(16, "x")}


def _client_for(app) -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _login(client: TestClient, identity: str) -> None:
    r = client.get("/auth/login", follow_redirects=False)
    assert r.status_code == 302, r.text
    authorize_path = r.headers["location"].replace("https://testserver", "")

    picker = client.get(authorize_path)
    assert picker.status_code == 200, picker.text
    code = re.search(r'name="code" value="([^"]+)"', picker.text).group(1)

    picked = client.post(
        "/test-idp/authorize", data={"code": code, "identity": identity}, follow_redirects=False
    )
    assert picked.status_code == 303, picked.text
    callback_path = picked.headers["location"].replace("https://testserver", "")

    callback = client.get(callback_path, follow_redirects=False)
    assert callback.status_code == 302, callback.text


def _csrf(client: TestClient) -> str:
    token = client.cookies.get("campaia_csrf")
    assert token, "no CSRF cookie set -- was _login() called first?"
    return token


BRIEF = {
    "name": "Tênis de corrida - lançamento",
    "objective": "Gerar leads qualificados para o lançamento do novo tênis",
    "product": "Tênis de corrida",
    "audience": "Corredores amadores, 25-45 anos",
    "total_budget": "5000",
    "daily_cap": "500",
    "channels": ["GOOGLE_ADS"],
}


class TestBriefingToApprovalViaWebSession(unittest.TestCase):
    def test_full_journey_via_real_session_cookie_two_distinct_users(self):
        # Both clients target the SAME app (same in-memory AppState) -- two real browser
        # sessions against one real backend, not two isolated test backends. (Separate
        # TestClient instances each get their own cookie jar, which is exactly what two
        # distinct real browsers would have.)
        app = create_app(enable_test_auth_fixtures=True)
        proposer = _client_for(app)
        _login(proposer, "owner")

        r = proposer.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(proposer), **_unique_idem()},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 202, r.text)
        campaign = r.json()
        campaign_id = campaign["id"]
        self.assertEqual(campaign["state"], "DRAFT")

        r = proposer.get(f"/campaigns/{campaign_id}/plan")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["plan"])

        r = proposer.post(
            f"/campaigns/{campaign_id}/plan/regenerate",
            headers={"x-csrf-token": _csrf(proposer), **_unique_idem()},
        )
        self.assertEqual(r.status_code, 202, r.text)
        plan = r.json()
        self.assertIsNotNone(plan["plan"])
        self.assertEqual(plan["plan_version"], 1)

        r = proposer.post(
            f"/campaigns/{campaign_id}/validate", headers={"x-csrf-token": _csrf(proposer)}
        )
        self.assertEqual(r.status_code, 200, r.text)
        decision = r.json()
        self.assertEqual(decision["outcome"], "APPROVABLE")
        self.assertTrue(decision["requires_human_approval"])

        r = proposer.post(
            "/approvals",
            headers={"x-csrf-token": _csrf(proposer)},
            json={"campaign_id": campaign_id, "kind": "PUBLISH"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        approval = r.json()
        self.assertEqual(approval["status"], "PENDING")

        # Same proposer tries to decide their own proposal via the real session -- rejected,
        # visibly, exactly like the frontend's ApprovalDecisionCard.tsx surfaces it.
        r = proposer.post(
            f"/approvals/{approval['id']}/decision",
            headers={
                "x-csrf-token": _csrf(proposer),
                "x-step-up-token": "test-stepup",
                **_unique_idem(),
            },
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "SEPARATION_OF_DUTIES")

        # A genuinely distinct logged-in user, same real backend, decides it -- accepted.
        approver = _client_for(app)
        _login(approver, "approver")
        r = approver.post(
            f"/approvals/{approval['id']}/decision",
            headers={
                "x-csrf-token": _csrf(approver),
                "x-step-up-token": "test-stepup",
                **_unique_idem(),
            },
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "APPROVED")

        # GET /approvals via the proposer's own session reflects the decision.
        r = proposer.get("/approvals")
        self.assertEqual(r.status_code, 200, r.text)
        listed = [a for a in r.json() if a["id"] == approval["id"]]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["status"], "APPROVED")
        # The contract gap this Work Package closed (requested_by was missing from
        # ApprovalRequest) -- now present and correct via the real session path too.
        self.assertEqual(listed[0]["requested_by"], "user-owner-1")

    def test_viewer_role_cannot_submit_a_brief_via_real_session(self):
        """campaia_core.permissions is never bypassed by the session-cookie auth path --
        role enforcement holds identically regardless of which of require_auth's two
        mechanisms resolved the principal."""
        viewer = _client_for(create_app(enable_test_auth_fixtures=True))
        _login(viewer, "viewer")

        r = viewer.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(viewer), **_unique_idem()},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 403, r.text)
