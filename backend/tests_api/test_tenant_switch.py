"""HTTP-level integration tests for WP-03 tenant switching (GET /session/memberships,
POST /session/switch-tenant), ADR-0018 extension.

Drives the full OIDC flow through the real Starlette app exactly like
tests_api/test_auth_session.py -- nothing here mocks api/oidc.py, api/state.py, or
api/routes_session.py. `multi_tenant_owner` (api/test_idp.py) is the only fixture identity
with more than one real membership: OWNER in demo-tenant (active on login), VIEWER in
other-tenant -- chosen so a switch also proves roles actually change, not just tenant_id.
"""

from __future__ import annotations

import os
import re
import unittest
from datetime import datetime, timezone

from starlette.testclient import TestClient

from api.main import create_app

os.environ.setdefault("CAMPAIA_ENV", "test")


def _fresh_authenticated_client() -> TestClient:
    app = create_app(enable_test_auth_fixtures=True)
    return TestClient(app, base_url="https://testserver")


def _login(client: TestClient, identity: str = "owner") -> None:
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


class TestGetMemberships(unittest.TestCase):
    def test_single_tenant_identity_has_exactly_one_active_membership(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        r = client.get("/session/memberships")
        self.assertEqual(r.status_code, 200)
        memberships = r.json()["memberships"]
        self.assertEqual(len(memberships), 1)
        self.assertEqual(memberships[0]["tenant_id"], "demo-tenant")
        self.assertTrue(memberships[0]["is_active"])

    def test_multi_tenant_identity_lists_both_memberships_with_correct_active_flag(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "multi_tenant_owner")
        r = client.get("/session/memberships")
        self.assertEqual(r.status_code, 200)
        memberships = {m["tenant_id"]: m for m in r.json()["memberships"]}
        self.assertEqual(set(memberships), {"demo-tenant", "other-tenant"})
        self.assertTrue(memberships["demo-tenant"]["is_active"])
        self.assertFalse(memberships["other-tenant"]["is_active"])
        self.assertEqual(memberships["demo-tenant"]["roles"], ["OWNER"])
        self.assertEqual(memberships["other-tenant"]["roles"], ["VIEWER"])

    def test_requires_a_real_web_session_not_just_any_auth(self) -> None:
        client = _fresh_authenticated_client()
        r = client.get("/session/memberships")
        self.assertEqual(r.status_code, 401)

    def test_fixture_bearer_token_is_rejected_even_though_it_authenticates_elsewhere(self) -> None:
        """require_web_session deliberately never falls back to the Bearer-token path
        (api/deps.py) -- there is no AppState.sessions entry for it to look up."""
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.get("/session/memberships", headers={"Authorization": "Bearer demo-owner-token"})
        self.assertEqual(r.status_code, 401)


class TestSwitchTenant(unittest.TestCase):
    def test_switch_to_a_real_membership_succeeds_and_changes_active_tenant(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "multi_tenant_owner")
        csrf = _csrf(client)

        r = client.post(
            "/session/switch-tenant",
            json={"tenant_id": "other-tenant"},
            headers={"x-csrf-token": csrf},
        )
        self.assertEqual(r.status_code, 200)

        me = client.get("/me")
        self.assertEqual(me.status_code, 200)
        body = me.json()
        self.assertEqual(body["tenant_id"], "other-tenant")
        self.assertEqual(body["roles"], ["VIEWER"])
        self.assertEqual(body["user_id"], "user-owner-3")  # same user, never changes

    def test_switch_rotates_session_and_csrf_cookies(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        _login(client, "multi_tenant_owner")
        old_session = client.cookies.get("campaia_session")
        old_csrf = _csrf(client)

        r = client.post(
            "/session/switch-tenant",
            json={"tenant_id": "other-tenant"},
            headers={"x-csrf-token": old_csrf},
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(client.cookies.get("campaia_session"), old_session)
        self.assertNotEqual(client.cookies.get("campaia_csrf"), old_csrf)

        # The old session id is genuinely gone server-side, not just superseded client-side --
        # a second client presenting it against the SAME app instance must be rejected.
        stale_client = TestClient(app, base_url="https://testserver")
        stale_client.cookies.set("campaia_session", old_session)
        stale = stale_client.get("/me")
        self.assertEqual(stale.status_code, 401)

    def test_switch_to_a_tenant_not_in_memberships_is_denied(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "multi_tenant_owner")
        csrf = _csrf(client)

        r = client.post(
            "/session/switch-tenant",
            json={"tenant_id": "some-tenant-never-granted"},
            headers={"x-csrf-token": csrf},
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")

        # Session must be completely unaffected by a rejected switch attempt.
        me = client.get("/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["tenant_id"], "demo-tenant")

    def test_single_tenant_identity_cannot_switch_anywhere(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        csrf = _csrf(client)

        r = client.post(
            "/session/switch-tenant",
            json={"tenant_id": "other-tenant"},
            headers={"x-csrf-token": csrf},
        )
        self.assertEqual(r.status_code, 403)

    def test_switch_requires_csrf_token(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "multi_tenant_owner")
        r = client.post("/session/switch-tenant", json={"tenant_id": "other-tenant"})
        self.assertEqual(r.status_code, 403)

    def test_switch_without_session_is_rejected(self) -> None:
        client = _fresh_authenticated_client()
        r = client.post("/session/switch-tenant", json={"tenant_id": "other-tenant"})
        self.assertEqual(r.status_code, 401)

    def test_switch_invalidates_step_up_across_all_tenants(self) -> None:
        """ADR-0018 WP-03 requirement: switching tenant invalidates any recent step-up,
        even for the tenant the user is leaving -- proven directly against AppState, the
        real production code path POST /session/switch-tenant calls, not a mock."""
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        _login(client, "multi_tenant_owner")
        state = app.state.campaia
        user_id = "user-owner-3"

        now = datetime.now(timezone.utc)
        state.record_step_up("demo-tenant", user_id, at=now)
        state.record_step_up("other-tenant", user_id, at=now)
        self.assertIsNotNone(state.last_step_up("demo-tenant", user_id))
        self.assertIsNotNone(state.last_step_up("other-tenant", user_id))

        csrf = _csrf(client)
        r = client.post(
            "/session/switch-tenant",
            json={"tenant_id": "other-tenant"},
            headers={"x-csrf-token": csrf},
        )
        self.assertEqual(r.status_code, 200)

        self.assertIsNone(state.last_step_up("demo-tenant", user_id))
        self.assertIsNone(state.last_step_up("other-tenant", user_id))

    def test_cross_session_isolation_switch_on_one_client_never_affects_another(self) -> None:
        """Two independent logins as the SAME multi-tenant identity (two browser sessions)
        -- switching tenant on one must never alter the other's active tenant."""
        app = create_app(enable_test_auth_fixtures=True)
        client_a = TestClient(app, base_url="https://testserver")
        client_b = TestClient(app, base_url="https://testserver")
        _login(client_a, "multi_tenant_owner")
        _login(client_b, "multi_tenant_owner")

        csrf_a = _csrf(client_a)
        r = client_a.post(
            "/session/switch-tenant",
            json={"tenant_id": "other-tenant"},
            headers={"x-csrf-token": csrf_a},
        )
        self.assertEqual(r.status_code, 200)

        me_b = client_b.get("/me")
        self.assertEqual(me_b.status_code, 200)
        self.assertEqual(me_b.json()["tenant_id"], "demo-tenant")


if __name__ == "__main__":
    unittest.main()
