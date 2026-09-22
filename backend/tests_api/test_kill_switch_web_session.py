"""HTTP-level integration test for WP-08 (kill switch), exercised through REAL Web session
cookies -- same discipline as test_autonomy_change_web_session.py (WP-07) and
test_budget_change_web_session.py (WP-06). POST /kill-switch already existed and was already
covered by unit-level Bearer fixtures (tests_api/test_smoke_endpoints.py); this proves the
same real-session path WP-08's frontend (KillSwitchPanel.tsx) actually uses, including the
one real contract gap this Work Package closed (the 202 response's schema, previously
undeclared despite always returning {scope, affected_campaign_ids}), AND the domain's own
"no step-up needed" design choice (Permission.KILL_SWITCH is deliberately outside
REQUIRES_STEP_UP) -- unlike every other sensitive mutation this session's tests exercise,
these requests never send X-Step-Up-Token, on purpose.

Reuses this file's own login/CSRF helpers rather than importing from
test_autonomy_change_web_session.py, matching this project's "three similar lines is better
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
    "name": "Campanha de teste de kill switch",
    "objective": "Testar parada de emergência",
    "total_budget": "5000",
    "daily_cap": "500",
    "channels": ["GOOGLE_ADS"],
}


class TestKillSwitchViaWebSession(unittest.TestCase):
    def test_campaign_scope_pauses_an_approved_campaign_without_step_up(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        # Get the campaign to APPROVED (in PAUSABLE_STATES) via the same real-session flow
        # WP-05 already proved end to end: brief -> plan -> validate -> request approval ->
        # a distinct approver decides.
        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "killswitch-test-briefxx"},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 202, r.text)
        campaign_id = r.json()["id"]

        r = owner.post(
            f"/campaigns/{campaign_id}/plan/regenerate",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "killswitch-test-planxxxx"},
        )
        self.assertEqual(r.status_code, 202, r.text)

        r = owner.post(
            f"/campaigns/{campaign_id}/validate", headers={"x-csrf-token": _csrf(owner)}
        )
        self.assertEqual(r.status_code, 200, r.text)
        decision = r.json()
        self.assertEqual(decision["outcome"], "APPROVABLE", decision)

        r = owner.post(
            "/approvals",
            headers={"x-csrf-token": _csrf(owner)},
            json={"campaign_id": campaign_id, "kind": "PUBLISH"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        approval = r.json()

        approver = _client_for(app)
        _login(approver, "approver")
        r = approver.post(
            f"/approvals/{approval['id']}/decision",
            headers={
                "x-csrf-token": _csrf(approver),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "killswitch-test-decidexx",
            },
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        approval = r.json()
        self.assertEqual(approval["status"], "APPROVED")

        # Kill switch's CAMPAIGN scope only applies from PAUSABLE_STATES (APPROVED,
        # PUBLISHING, ACTIVE, OPTIMIZING) -- the campaign is still VALIDATED at this point
        # (deciding the ApprovalRequest doesn't itself move the campaign's own state
        # machine); publish it for real first, same real session, to reach a pausable state.
        r = owner.post(
            f"/campaigns/{campaign_id}/publish",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "killswitch-test-publishxx",
            },
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 202, r.text)

        # The real kill switch call: CSRF + Idempotency-Key, deliberately NO
        # X-Step-Up-Token -- Permission.KILL_SWITCH is outside REQUIRES_STEP_UP by domain
        # design (emergency stop must not wait on reauthentication).
        r = owner.post(
            "/kill-switch",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "killswitch-test-firexxx"},
            json={"scope": "CAMPAIGN", "target_id": campaign_id, "reason": "gasto inesperado"},
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["scope"], "CAMPAIGN")
        self.assertEqual(r.json()["affected_campaign_ids"], [campaign_id])

        # The campaign is really paused now, visible on a fresh GET.
        r = owner.get(f"/campaigns/{campaign_id}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["state"], "PAUSED")

    def test_tenant_scope_with_no_pausable_campaigns_returns_empty_affected_list(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "killswitch-test-brief2xx"},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 202, r.text)

        # The campaign above is still DRAFT -- not in PAUSABLE_STATES -- so a TENANT-scope
        # kill switch simply skips it rather than raising (only CAMPAIGN scope raises for a
        # non-pausable target).
        r = owner.post(
            "/kill-switch",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "killswitch-test-fire2xxx"},
            json={"scope": "TENANT", "reason": "teste"},
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["affected_campaign_ids"], [])

    def test_identity_without_kill_switch_permission_is_rejected(self):
        app = create_app(enable_test_auth_fixtures=True)
        marketer = _client_for(app)
        _login(marketer, "marketer")

        r = marketer.post(
            "/kill-switch",
            headers={
                "x-csrf-token": _csrf(marketer),
                "idempotency-key": "killswitch-test-fire3xxx",
            },
            json={"scope": "TENANT", "reason": "teste"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")
