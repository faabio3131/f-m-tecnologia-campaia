"""WP-03: proves the backend actually supports the cross-origin Web frontend topology
README.md documents (NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN, e.g. https://api.campaia.app, a
DIFFERENT origin than the frontend's own https://app.campaia.app) -- discovered missing by
actually running a real browser through the full login + tenant-switch flow across two real
origins (web/playwright.crossstack.config.ts), not assumed correct from same-origin tests
alone. Two independent gaps, both closed here:

1. `/auth/callback` and `/auth/logout` redirected the browser to a bare relative path,
   which a browser resolves against the BACKEND's own origin (the page issuing the
   redirect), not the frontend's -- landing the user on a BFF URL with no route to serve
   it, in any real deployment where the two are actually different origins.
2. No CORS headers existed at all, so a browser refuses LogoutButton/TenantSwitcher's
   credentialed cross-origin fetches outright (blocked at the preflight OPTIONS request).

Both are gated behind the same new, optional CAMPAIA_WEB_ORIGIN env var (api/main.py
_build_middleware, api/routes_auth.py _frontend_url) -- unset (every pre-existing test)
keeps today's path-relative, CORS-less behaviour exactly as it was, correct only for a
same-origin/reverse-proxied deployment.
"""

from __future__ import annotations

import os
import re
import unittest

from starlette.testclient import TestClient

from api.main import create_app

os.environ.setdefault("CAMPAIA_ENV", "test")

_WEB_ORIGIN = "https://app.campaia.test"


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


class TestFrontendRedirectWithoutWebOrigin(unittest.TestCase):
    """CAMPAIA_WEB_ORIGIN unset -- every pre-existing WP-02 test's implicit assumption,
    preserved exactly."""

    def test_callback_redirects_to_bare_relative_path(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.get("/auth/login?redirect_after_login=/dashboard", follow_redirects=False)
        authorize_path = r.headers["location"].replace("https://testserver", "")
        picker = client.get(authorize_path)
        code = re.search(r'name="code" value="([^"]+)"', picker.text).group(1)
        picked = client.post(
            "/test-idp/authorize", data={"code": code, "identity": "owner"}, follow_redirects=False
        )
        callback_path = picked.headers["location"].replace("https://testserver", "")
        callback = client.get(callback_path, follow_redirects=False)
        self.assertEqual(callback.headers["location"], "/dashboard")

    def test_logout_redirects_to_bare_slash(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        _login(client, "owner")
        csrf = client.cookies.get("campaia_csrf")
        r = client.post("/auth/logout", headers={"x-csrf-token": csrf}, follow_redirects=False)
        self.assertEqual(r.headers["location"], "/")


class TestFrontendRedirectWithWebOrigin(unittest.TestCase):
    """CAMPAIA_WEB_ORIGIN set -- the real cross-origin deployment topology."""

    def setUp(self) -> None:
        os.environ["CAMPAIA_WEB_ORIGIN"] = _WEB_ORIGIN

    def tearDown(self) -> None:
        os.environ.pop("CAMPAIA_WEB_ORIGIN", None)

    def test_callback_redirects_to_the_frontend_origin(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.get("/auth/login?redirect_after_login=/dashboard", follow_redirects=False)
        authorize_path = r.headers["location"].replace("https://testserver", "")
        picker = client.get(authorize_path)
        code = re.search(r'name="code" value="([^"]+)"', picker.text).group(1)
        picked = client.post(
            "/test-idp/authorize", data={"code": code, "identity": "owner"}, follow_redirects=False
        )
        callback_path = picked.headers["location"].replace("https://testserver", "")
        callback = client.get(callback_path, follow_redirects=False)
        self.assertEqual(callback.headers["location"], f"{_WEB_ORIGIN}/dashboard")

    def test_logout_redirects_to_the_frontend_origin_root(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        _login(client, "owner")
        csrf = client.cookies.get("campaia_csrf")
        r = client.post("/auth/logout", headers={"x-csrf-token": csrf}, follow_redirects=False)
        self.assertEqual(r.headers["location"], f"{_WEB_ORIGIN}/")

    def test_client_supplied_redirect_still_cannot_escape_to_an_external_host(self) -> None:
        """CAMPAIA_WEB_ORIGIN widens WHERE the trusted redirect lands, never WHAT a client
        can supply -- _redirect_target's own open-redirect guard (same-origin-relative
        only) still runs first and unchanged."""
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.get(
            "/auth/login?redirect_after_login=https://attacker.example/steal",
            follow_redirects=False,
        )
        authorize_path = r.headers["location"].replace("https://testserver", "")
        picker = client.get(authorize_path)
        code = re.search(r'name="code" value="([^"]+)"', picker.text).group(1)
        picked = client.post(
            "/test-idp/authorize", data={"code": code, "identity": "owner"}, follow_redirects=False
        )
        callback_path = picked.headers["location"].replace("https://testserver", "")
        callback = client.get(callback_path, follow_redirects=False)
        self.assertEqual(callback.headers["location"], f"{_WEB_ORIGIN}/")


class TestCorsWithoutWebOrigin(unittest.TestCase):
    def test_no_cors_headers_present_by_default(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.options(
            "/session/switch-tenant",
            headers={
                "origin": "https://app.campaia.test",
                "access-control-request-method": "POST",
            },
        )
        self.assertNotIn("access-control-allow-origin", {k.lower() for k in r.headers.keys()})


class TestCorsWithWebOrigin(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CAMPAIA_WEB_ORIGIN"] = _WEB_ORIGIN

    def tearDown(self) -> None:
        os.environ.pop("CAMPAIA_WEB_ORIGIN", None)

    def test_preflight_allows_only_the_configured_frontend_origin(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.options(
            "/session/switch-tenant",
            headers={
                "origin": _WEB_ORIGIN,
                "access-control-request-method": "POST",
                "access-control-request-headers": "content-type,x-csrf-token",
            },
        )
        self.assertEqual(r.headers.get("access-control-allow-origin"), _WEB_ORIGIN)
        self.assertEqual(r.headers.get("access-control-allow-credentials"), "true")

    def test_preflight_from_an_unconfigured_origin_is_not_allowed(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.options(
            "/session/switch-tenant",
            headers={
                "origin": "https://attacker.example",
                "access-control-request-method": "POST",
            },
        )
        self.assertNotEqual(r.headers.get("access-control-allow-origin"), "https://attacker.example")

    def test_actual_cross_origin_response_carries_credentials_header(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.get("/me", headers={"origin": _WEB_ORIGIN}, follow_redirects=False)
        # 401 (no session) either way -- the assertion is only about the CORS response
        # headers a real browser would gate the fetch on.
        self.assertEqual(r.headers.get("access-control-allow-origin"), _WEB_ORIGIN)
        self.assertEqual(r.headers.get("access-control-allow-credentials"), "true")


if __name__ == "__main__":
    unittest.main()
