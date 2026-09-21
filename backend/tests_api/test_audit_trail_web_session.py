"""HTTP-level integration test for WP-10 (audit trail), exercised through REAL Web session
cookies -- same discipline as test_connection_lifecycle_web_session.py (WP-09). GET
/audit-events already existed and was already covered by unit-level Bearer fixtures
(tests_api/test_smoke_endpoints.py); this proves the same real-session path WP-10's
frontend (/audit) actually uses, and confirms the trail genuinely reflects real actions
taken by other blocks (WP-04's connect flow), not a fabricated or mocked list.

Reuses this file's own login/CSRF helpers rather than importing from another test file,
matching this project's "three similar lines is better than a premature cross-test-file
dependency" convention already established for per-file test helpers throughout tests_api/.
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
    "name": "Campanha de teste de auditoria",
    "objective": "Testar trilha de auditoria",
    "total_budget": "5000",
    "daily_cap": "500",
    "channels": ["GOOGLE_ADS"],
}


class TestAuditTrailViaWebSession(unittest.TestCase):
    def test_real_events_from_another_block_appear_in_the_trail(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        # A real action from WP-04's own flow, via the same real session.
        r = owner.post(
            "/connections/oauth/start",
            headers={"x-csrf-token": _csrf(owner), "x-step-up-token": "test-stepup"},
            json={"provider": "GOOGLE_ADS"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        state = r.json()["state"]

        r = owner.post(
            "/connections/oauth/complete",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "audit-test-completexx",
            },
            json={"state": state, "external_account_id": "acc-audit", "display_name": "Google Ads (teste)"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        connection_id = r.json()["id"]

        # Owner has AUDIT_VIEW (OWNER = all permissions) -- reads the real trail via the
        # same real session.
        r = owner.get("/audit-events")
        self.assertEqual(r.status_code, 200, r.text)
        events = r.json()["items"]

        actions = {e["action"] for e in events}
        self.assertIn("OAUTH_START", actions)
        self.assertIn("CONNECTION_CREATE", actions)

        create_event = next(e for e in events if e["action"] == "CONNECTION_CREATE")
        self.assertEqual(create_event["actor_id"], "user-owner-1")
        self.assertEqual(create_event["target"], connection_id)
        self.assertEqual(create_event["actor_kind"], "USER")

    def test_campaign_id_filter_narrows_the_trail(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "audit-test-briefxxxx"},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 202, r.text)
        campaign_id = r.json()["id"]

        r = owner.post(
            "/connections/oauth/start",
            headers={"x-csrf-token": _csrf(owner), "x-step-up-token": "test-stepup"},
            json={"provider": "META"},
        )
        self.assertEqual(r.status_code, 200, r.text)

        r = owner.get(f"/audit-events?campaign_id={campaign_id}")
        self.assertEqual(r.status_code, 200, r.text)
        events = r.json()["items"]
        self.assertTrue(events)
        for event in events:
            self.assertEqual(event["target"], campaign_id)
        # The OAUTH_START event (target is the provider name, not this campaign) never
        # shows up once the filter is applied.
        self.assertNotIn("OAUTH_START", {e["action"] for e in events})

    def test_identity_without_audit_view_permission_is_rejected(self):
        app = create_app(enable_test_auth_fixtures=True)
        marketer = _client_for(app)
        _login(marketer, "marketer")

        r = marketer.get("/audit-events")
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")
