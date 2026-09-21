"""HTTP-level integration test for WP-09 (disconnect account + connection capabilities),
exercised through REAL Web session cookies -- same discipline as
test_kill_switch_web_session.py (WP-08). GET /connections/{id}/capabilities and DELETE
/connections/{id} already existed and were already covered by unit-level Bearer fixtures
(tests_api/test_smoke_endpoints.py); this proves the same real-session path WP-09's
frontend (ConnectAccountCard.tsx) actually uses, including the real contract gap this Work
Package closed (Capability.provider/.country/.api_version, previously missing from
contracts/bff-openapi.yaml despite always being present in the real response).

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


class TestConnectionLifecycleViaWebSession(unittest.TestCase):
    def _connect(self, owner: TestClient) -> str:
        r = owner.post(
            "/connections/oauth/start",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
            },
            json={"provider": "GOOGLE_ADS"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        state = r.json()["state"]

        r = owner.post(
            "/connections/oauth/complete",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "connlife-test-completexx",
            },
            json={
                "state": state,
                "external_account_id": "acc-connlife",
                "display_name": "Google Ads (teste)",
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def test_view_real_capabilities_then_disconnect_via_real_session(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        connection_id = self._connect(owner)

        # Real capabilities, via the same real session -- the contract gap this Work
        # Package closed (provider/country/api_version, always present, never documented).
        r = owner.get(f"/connections/{connection_id}/capabilities")
        self.assertEqual(r.status_code, 200, r.text)
        capabilities = r.json()
        self.assertEqual(len(capabilities), 2)
        for cap in capabilities:
            self.assertEqual(cap["provider"], "GOOGLE_ADS")
            self.assertIn(cap["country"], ("BR",))
            self.assertTrue(cap["api_version"])
            self.assertIn("capability_key", cap)
            self.assertIn("supported", cap)

        # Disconnect: CSRF + step-up + idempotency-key, 204 no body.
        r = owner.delete(
            f"/connections/{connection_id}",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "connlife-test-revokexxx",
            },
        )
        self.assertEqual(r.status_code, 204, r.text)
        self.assertEqual(r.text, "")

        # The connection is really revoked now, visible on a fresh GET.
        r = owner.get("/connections")
        self.assertEqual(r.status_code, 200, r.text)
        connections = r.json()
        revoked = next(c for c in connections if c["id"] == connection_id)
        self.assertEqual(revoked["status"], "REVOKED")

    def test_identity_without_connection_manage_permission_is_rejected(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")
        connection_id = self._connect(owner)

        marketer = _client_for(app)
        _login(marketer, "marketer")
        r = marketer.delete(
            f"/connections/{connection_id}",
            headers={
                "x-csrf-token": _csrf(marketer),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "connlife-test-revoke2xx",
            },
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")
