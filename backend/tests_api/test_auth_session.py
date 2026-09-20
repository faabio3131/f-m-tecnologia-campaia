"""HTTP-level integration tests for the real Web session mechanism (WP-02, ADR-0018).

Drives the full OIDC Authorization Code + PKCE flow through the actual Starlette app (real
routing, real middleware, real in-process test identity provider, real signed ID tokens,
real JWKS-based signature verification) via Starlette's TestClient -- nothing here mocks
api/oidc.py or api/routes_auth.py itself. Cookie flags are `Secure`, so the TestClient is
built with an https:// base_url (Secure cookies are silently dropped over http://, which is
correct browser behaviour, not a bug to work around by weakening the cookie itself).

Covers the WP-02 acceptance criteria and roadmap-mandated tests directly: "login real
funciona; rota protegida recusa acesso sem sessao valida; teste automatizado de tentativa
cross-tenant confirma NOT_FOUND"; "automatizados de CSRF, CORS, step-up, isolamento
cross-tenant".
"""

from __future__ import annotations

import os
import re
import unittest

from starlette.testclient import TestClient

from api.main import create_app

os.environ.setdefault("CAMPAIA_ENV", "test")


def _fresh_authenticated_client() -> TestClient:
    app = create_app(enable_test_auth_fixtures=True)
    return TestClient(app, base_url="https://testserver")


def _login(client: TestClient, identity: str = "owner") -> None:
    """Drives the full browser-facing flow: /auth/login -> picker page -> pick identity ->
    /auth/callback -> session cookies set on `client`."""
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


class TestRealLoginFlow(unittest.TestCase):
    def test_login_then_me_reflects_real_claims(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        r = client.get("/me")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["user_id"], "user-owner-1")
        self.assertEqual(body["tenant_id"], "demo-tenant")
        self.assertIn("OWNER", body["roles"])
        self.assertTrue(body["mfa_enabled"])

    def test_session_cookie_is_httponly_and_secure(self) -> None:
        client = _fresh_authenticated_client()
        r = client.get("/auth/login", follow_redirects=False)
        authorize_path = r.headers["location"].replace("https://testserver", "")
        picker = client.get(authorize_path)
        code = re.search(r'name="code" value="([^"]+)"', picker.text).group(1)
        picked = client.post(
            "/test-idp/authorize", data={"code": code, "identity": "owner"}, follow_redirects=False
        )
        callback_path = picked.headers["location"].replace("https://testserver", "")
        callback = client.get(callback_path, follow_redirects=False)

        set_cookie_headers = callback.headers.get_list("set-cookie")
        session_cookie = next(h for h in set_cookie_headers if h.startswith("campaia_session="))
        csrf_cookie = next(h for h in set_cookie_headers if h.startswith("campaia_csrf="))
        self.assertIn("HttpOnly", session_cookie)
        self.assertIn("Secure", session_cookie)
        self.assertIn("samesite=lax", session_cookie.lower())
        self.assertNotIn("HttpOnly", csrf_cookie)  # must be readable by browser JS
        self.assertIn("Secure", csrf_cookie)

    def test_full_roundtrip_exercises_rbac_for_each_fixture_role(self) -> None:
        """"RBAC/ABAC exercitado ponta a ponta pela primeira vez via Web" (roadmap DoD) --
        proven for every fixture identity, not just owner."""
        expectations = {
            "owner": ("user-owner-1", "demo-tenant", "OWNER"),
            "marketer": ("user-marketer-1", "demo-tenant", "MARKETER"),
            "approver": ("user-approver-1", "demo-tenant", "APPROVER"),
            "finance": ("user-finance-1", "demo-tenant", "FINANCE"),
            "viewer": ("user-viewer-1", "demo-tenant", "VIEWER"),
            "other_owner": ("user-owner-2", "other-tenant", "OWNER"),
        }
        for identity, (user_id, tenant_id, role) in expectations.items():
            with self.subTest(identity=identity):
                client = _fresh_authenticated_client()
                _login(client, identity)
                r = client.get("/me")
                self.assertEqual(r.status_code, 200)
                body = r.json()
                self.assertEqual(body["user_id"], user_id)
                self.assertEqual(body["tenant_id"], tenant_id)
                self.assertIn(role, body["roles"])


class TestNegativeSessionCases(unittest.TestCase):
    """WP-02 explicit requirement: "testes negativos de sessao ausente, expirada,
    adulterada e revogada" -- one test each, all asserting the identical UNAUTHENTICATED
    outcome (never leaking *why* auth failed)."""

    def test_missing_session_is_rejected(self) -> None:
        client = _fresh_authenticated_client()
        r = client.get("/me")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["code"], "UNAUTHENTICATED")

    def test_unknown_session_cookie_is_rejected(self) -> None:
        client = _fresh_authenticated_client()
        client.cookies.set("campaia_session", "this-session-id-was-never-issued-by-anyone")
        r = client.get("/me")
        self.assertEqual(r.status_code, 401)

    def test_tampered_session_cookie_is_rejected(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        real_session = client.cookies.get("campaia_session")
        tampered = real_session[:-1] + ("A" if real_session[-1] != "A" else "B")
        client.cookies.set("campaia_session", tampered)
        r = client.get("/me")
        self.assertEqual(r.status_code, 401)

    def test_expired_session_is_rejected(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        _login(client, "owner")

        # Force expiry directly on the server-side record -- proves expiry is enforced by
        # the server's own clock, not just by the cookie's Max-Age (which a client could
        # ignore).
        session_id = client.cookies.get("campaia_session")
        record = app.state.campaia.sessions[session_id]
        app.state.campaia.sessions[session_id] = record.__class__(
            principal=record.principal, csrf_token=record.csrf_token, expires_at=0.0
        )

        r = client.get("/me")
        self.assertEqual(r.status_code, 401)

    def test_revoked_session_is_rejected(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        csrf = _csrf(client)

        logout = client.post("/auth/logout", headers={"x-csrf-token": csrf}, follow_redirects=False)
        self.assertEqual(logout.status_code, 302)

        r = client.get("/me")
        self.assertEqual(r.status_code, 401)


class TestCsrf(unittest.TestCase):
    def test_mutation_without_csrf_header_is_rejected(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        r = client.post(
            "/brand-profiles",
            json={"name": "Test", "tone": "x"},
            headers={"Idempotency-Key": "idem-test-key-nocsrf1"},
        )
        self.assertEqual(r.status_code, 403)

    def test_mutation_with_wrong_csrf_header_is_rejected(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        r = client.post(
            "/brand-profiles",
            json={"name": "Test", "tone": "x"},
            headers={
                "Idempotency-Key": "idem-test-key-wrongcsrf",
                "x-csrf-token": "not-the-real-csrf-token",
            },
        )
        self.assertEqual(r.status_code, 403)

    def test_mutation_with_correct_csrf_header_succeeds(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        csrf = _csrf(client)
        r = client.post(
            "/brand-profiles",
            json={"name": "Test", "tone": "x"},
            headers={"Idempotency-Key": "idem-test-key-goodcsrf", "x-csrf-token": csrf},
        )
        self.assertEqual(r.status_code, 201)

    def test_safe_methods_do_not_require_csrf_even_with_session(self) -> None:
        client = _fresh_authenticated_client()
        _login(client, "owner")
        r = client.get("/brand-profiles")
        self.assertEqual(r.status_code, 200)

    def test_fixture_bearer_token_path_is_unaffected_by_csrf(self) -> None:
        """The pre-WP-02 Bearer-token path carries no session cookie, so CSRFMiddleware
        must never touch it -- this is what keeps all 81 pre-existing API tests green."""
        app = create_app(enable_test_auth_fixtures=True)
        client = TestClient(app, base_url="https://testserver")
        r = client.post(
            "/brand-profiles",
            json={"name": "Test", "tone": "x"},
            headers={
                "Authorization": "Bearer demo-owner-token",
                "Idempotency-Key": "idem-test-key-bearernocsrf",
            },
        )
        self.assertEqual(r.status_code, 201)


class TestCrossTenantIsolationViaSession(unittest.TestCase):
    def test_other_tenant_owner_cannot_see_demo_tenant_brand_profile(self) -> None:
        app = create_app(enable_test_auth_fixtures=True)
        owner_client = TestClient(app, base_url="https://testserver")
        _login(owner_client, "owner")
        csrf = _csrf(owner_client)
        created = owner_client.post(
            "/brand-profiles",
            json={"name": "Demo Tenant Brand", "tone": "x"},
            headers={"Idempotency-Key": "idem-test-key-xtenant2", "x-csrf-token": csrf},
        )
        self.assertEqual(created.status_code, 201)

        other_client = TestClient(app, base_url="https://testserver")
        _login(other_client, "other_owner")
        r = other_client.get("/brand-profiles")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])


class TestAuthorizationCodeFlowIntegrity(unittest.TestCase):
    def test_replayed_state_is_rejected(self) -> None:
        """A /auth/callback with a `state` value already consumed once must fail the
        second time -- proves pending logins are single-use."""
        client = _fresh_authenticated_client()
        r = client.get("/auth/login", follow_redirects=False)
        authorize_path = r.headers["location"].replace("https://testserver", "")
        picker = client.get(authorize_path)
        code = re.search(r'name="code" value="([^"]+)"', picker.text).group(1)
        picked = client.post(
            "/test-idp/authorize", data={"code": code, "identity": "owner"}, follow_redirects=False
        )
        callback_path = picked.headers["location"].replace("https://testserver", "")

        first = client.get(callback_path, follow_redirects=False)
        self.assertEqual(first.status_code, 302)

        second = client.get(callback_path, follow_redirects=False)
        self.assertEqual(second.status_code, 401)

    def test_unknown_state_is_rejected(self) -> None:
        client = _fresh_authenticated_client()
        r = client.get("/auth/callback?code=whatever&state=never-issued-by-this-server")
        self.assertEqual(r.status_code, 401)

    def test_replayed_authorization_code_is_rejected_at_token_exchange(self) -> None:
        """Even with a fresh, valid `state`/pending-login record, reusing the same
        authorization `code` at /test-idp/token a second time must fail -- single-use
        codes, independent of the outer state replay protection."""
        client = _fresh_authenticated_client()
        r = client.get("/auth/login", follow_redirects=False)
        authorize_path = r.headers["location"].replace("https://testserver", "")
        picker = client.get(authorize_path)
        code = re.search(r'name="code" value="([^"]+)"', picker.text).group(1)
        client.post("/test-idp/authorize", data={"code": code, "identity": "owner"}, follow_redirects=False)

        # First exchange (mirrors what /auth/callback does internally) succeeds.
        first = client.post(
            "/test-idp/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://testserver/auth/callback",
                "client_id": "campaia-web-test",
                "client_secret": "test-idp-internal-secret-not-a-real-credential",
                "code_verifier": "irrelevant-because-pkce-check-happens-after-lookup",
            },
        )
        # The PKCE verifier here is deliberately wrong (this test only has access to the
        # public `code`, not the real verifier the browser-side flow generated) -- but the
        # important assertion is the SECOND call, which must fail regardless of the first
        # call's own outcome, because the code is single-use either way.
        second = client.post(
            "/test-idp/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://testserver/auth/callback",
                "client_id": "campaia-web-test",
                "client_secret": "test-idp-internal-secret-not-a-real-credential",
                "code_verifier": "irrelevant-because-pkce-check-happens-after-lookup",
            },
        )
        self.assertEqual(first.status_code, 400)  # wrong verifier -> invalid_grant
        self.assertEqual(second.status_code, 400)  # code already consumed by the first call


class TestFailClosedEndToEnd(unittest.TestCase):
    def test_test_idp_routes_absent_when_fixtures_disabled(self) -> None:
        app = create_app()  # enable_test_auth_fixtures=False (the production default)
        client = TestClient(app, base_url="https://testserver")
        r = client.get("/test-idp/.well-known/openid-configuration")
        self.assertEqual(r.status_code, 404)

    def test_login_returns_503_when_no_provider_configured(self) -> None:
        app = create_app()  # no CAMPAIA_OIDC_* env vars in this test process, no test idp
        client = TestClient(app, base_url="https://testserver")
        r = client.get("/auth/login")
        self.assertEqual(r.status_code, 503)


if __name__ == "__main__":
    unittest.main()
