"""HTTP-level integration test for WP-11 (honest campaign metrics), exercised through REAL
Web session cookies -- same discipline as test_audit_trail_web_session.py (WP-10). GET
/campaigns/{id}/insights already existed and was already covered by unit-level Bearer
fixtures (tests_api/test_smoke_endpoints.py: test_insights_is_honest_placeholder,
test_insights_validates_date_query_params); this proves the same real-session path WP-11's
frontend (/campaigns/{id}'s "Métricas" section) actually uses, and confirms the `note` field
this Work Package added to the contract (achado real, contracts/bff-openapi.yaml's
InsightSeries) is genuinely present in the real response, not just in the Pydantic model.

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
    "name": "Campanha de teste de métricas",
    "objective": "Testar métricas honestas",
    "total_budget": "5000",
    "daily_cap": "500",
    "channels": ["GOOGLE_ADS"],
}


class TestInsightsViaWebSession(unittest.TestCase):
    def test_real_session_sees_the_honest_empty_placeholder_with_a_real_note(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "insights-test-briefxx"},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 202, r.text)
        campaign_id = r.json()["id"]

        r = owner.get(f"/campaigns/{campaign_id}/insights")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["campaign_id"], campaign_id)
        self.assertEqual(body["points"], [])
        self.assertTrue(body["note"], "note must be a real, non-empty string, not omitted")

    def test_marketer_can_also_view_insights_campaign_view_is_broad(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "insights-test-briefxx2"},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 202, r.text)
        campaign_id = r.json()["id"]

        marketer = _client_for(app)
        _login(marketer, "marketer")
        r = marketer.get(f"/campaigns/{campaign_id}/insights")
        self.assertEqual(r.status_code, 200, r.text)
