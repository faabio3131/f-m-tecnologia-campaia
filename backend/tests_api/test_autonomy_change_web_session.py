"""HTTP-level integration test for WP-07 (autonomy level change), exercised through REAL
Web session cookies -- same discipline as test_budget_change_web_session.py (WP-06) and
test_briefing_approval_web_session.py (WP-05). GET/PUT /autonomy and POST /approvals
already existed and were already covered by unit-level fixtures; this proves the same
real-session path WP-07's frontend (AutonomyPanel.tsx) actually uses, including the real
contract gap this Work Package closed (AutonomySettings.max_level_allowed, previously
missing from contracts/bff-openapi.yaml despite always being present in the real
response).

Reuses this file's own login/CSRF helpers rather than importing from
test_budget_change_web_session.py, matching this project's "three similar lines is better
than a premature cross-test-file dependency" convention already established for per-file
test helpers throughout tests_api/.
"""

from __future__ import annotations

import os
import re
import unittest

from starlette.testclient import TestClient

from api.main import create_app

os.environ.setdefault("CAMPAIA_ENV", "test")


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
    "name": "Campanha de teste de autonomia",
    "objective": "Testar alteração de nível de autonomia",
    "total_budget": "5000",
    "daily_cap": "500",
    "channels": ["GOOGLE_ADS"],
}


class TestAutonomyChangeViaWebSession(unittest.TestCase):
    def test_propose_approve_apply_via_real_session_two_distinct_users(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        # create_approval still requires a campaign_id even for a tenant-wide
        # AUTONOMY_CHANGE (real backend constraint, documented in
        # docs/web/06_ROADMAP_WORK_PACKAGES.md's WP-07 section) -- the frontend works
        # around this by using the first available campaign's id purely to satisfy the
        # API, and this test does the same.
        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "autonomy-test-briefxx"},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 202, r.text)
        campaign_id = r.json()["id"]

        # CURRENT default: level=1 (APROVADO), max_level_allowed=1 -- so the only in-ceiling
        # change available is lowering to level 0 (ASSISTENTE).
        r = owner.get("/autonomy")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["level"], 1)
        self.assertEqual(r.json()["max_level_allowed"], 1)

        # Propose: POST /approvals with amount -- the real field WP-06 added to the
        # contract (ApprovalRequest.amount), reused unchanged here.
        r = owner.post(
            "/approvals",
            headers={"x-csrf-token": _csrf(owner)},
            json={"campaign_id": campaign_id, "kind": "AUTONOMY_CHANGE", "amount": "0"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        approval = r.json()
        self.assertEqual(approval["status"], "PENDING")
        self.assertEqual(approval["kind"], "AUTONOMY_CHANGE")
        self.assertEqual(approval["amount"], "0")

        # Decide: a genuinely distinct logged-in user, same real backend. APPROVER lacks
        # AUTONOMY_CHANGE itself (separation of duties) but does have APPROVAL_DECIDE.
        approver = _client_for(app)
        _login(approver, "approver")
        r = approver.post(
            f"/approvals/{approval['id']}/decision",
            headers={
                "x-csrf-token": _csrf(approver),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "autonomy-test-decidexx",
            },
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "APPROVED")

        # Apply: back on the owner's own real session -- PUT /autonomy needs
        # Permission.AUTONOMY_CHANGE, which APPROVER's role does not carry (same
        # separation as WP-06's patch_budget: the approver decides, the owner applies).
        r = owner.put(
            "/autonomy",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "autonomy-test-applyxxx",
            },
            json={"level": 0, "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["level"], 0)
        self.assertEqual(r.json()["level_label"], "ASSISTENTE")

        # GET /autonomy via the owner's own session reflects the real change.
        r = owner.get("/autonomy")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["level"], 0)

    def test_level_above_contracted_ceiling_is_rejected_at_apply_time(self):
        """Mirrors WP-06's max-percentage-at-apply-time test: the approval itself never
        validates the level against the ceiling -- only put_autonomy does, at apply time,
        via AutonomySettings.__post_init__'s own anti-self-promotion guard (invariant
        I-11). A user can propose and even get an out-of-ceiling level approved; applying
        it still fails, visibly, matching AutonomyPanel.tsx's own disabling of
        above-ceiling radio options and error-surfacing."""
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "autonomy-test-brief2xx"},
            json=BRIEF,
        )
        campaign_id = r.json()["id"]

        # Level 2 (LIMITADO) is above the CURRENT default ceiling of 1 (APROVADO).
        r = owner.post(
            "/approvals",
            headers={"x-csrf-token": _csrf(owner)},
            json={"campaign_id": campaign_id, "kind": "AUTONOMY_CHANGE", "amount": "2"},
        )
        approval = r.json()

        approver = _client_for(app)
        _login(approver, "approver")
        approver.post(
            f"/approvals/{approval['id']}/decision",
            headers={
                "x-csrf-token": _csrf(approver),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "autonomy-test-decide2xx",
            },
            json={"decision": "APPROVE"},
        )

        r = owner.put(
            "/autonomy",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "autonomy-test-apply2xxx",
            },
            json={"level": 2, "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

        # The level was never actually changed.
        r = owner.get("/autonomy")
        self.assertEqual(r.json()["level"], 1)
