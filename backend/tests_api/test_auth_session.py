"""Item 1.3/WP-02 (24/09/2026): autenticacao real via sessao server-side.

`FakeIdTokenVerifier` injeta identidades verificadas sem qualquer credencial/projeto
Google Cloud real -- mesmo padrao de `httpx.MockTransport` no `GeminiProvider`. Prova o
fluxo real (login -> cookie -> rota protegida -> CSRF -> logout) sem depender do item 1.6.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from starlette.testclient import TestClient

from api.main import create_app
from api.session import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, InMemorySessionStore
from api.state import AppState
from campaia_core.identity_provider import IdentityError, VerifiedIdentity
from campaia_core.permissions import Role
from tests_api.test_helpers import idem, unique_idem


class FakeIdTokenVerifier:
    """Test double do IdTokenVerifier Protocol -- nenhum projeto Google Cloud real."""

    def __init__(self, identities: dict[str, VerifiedIdentity] | None = None) -> None:
        self._identities = dict(identities) if identities else {}

    def verify(self, id_token: str):
        identity = self._identities.get(id_token)
        if identity is None:
            raise IdentityError("id_token de teste desconhecido.")
        return identity


OWNER_TOKEN = "fake-id-token-owner"
OWNER_IDENTITY = VerifiedIdentity(
    subject="google-uid-owner-1", email="owner@demo-tenant.campaia.test", email_verified=True
)
UNVERIFIED_TOKEN = "fake-id-token-unverified"
UNVERIFIED_IDENTITY = VerifiedIdentity(
    subject="google-uid-x", email="owner@demo-tenant.campaia.test", email_verified=False
)
UNKNOWN_EMAIL_TOKEN = "fake-id-token-unknown-email"
UNKNOWN_EMAIL_IDENTITY = VerifiedIdentity(
    subject="google-uid-y", email="nao-cadastrado@example.com", email_verified=True
)
OTHER_TENANT_TOKEN = "fake-id-token-other-owner"
OTHER_TENANT_IDENTITY = VerifiedIdentity(
    subject="google-uid-other", email="owner@other-tenant.campaia.test", email_verified=True
)


def _client(verifier: FakeIdTokenVerifier) -> TestClient:
    app = create_app(env="test")
    app.state.campaia.id_token_verifier = verifier
    # base_url https: o cookie de sessao e Secure=True de proposito (ADR-0018) -- o
    # cliente de teste precisa de um contexto "https" para reenviar o cookie nas
    # proximas requisicoes, exatamente como um navegador real faria em produção.
    return TestClient(app, base_url="https://testserver")


def _default_verifier() -> FakeIdTokenVerifier:
    return FakeIdTokenVerifier(
        {
            OWNER_TOKEN: OWNER_IDENTITY,
            UNVERIFIED_TOKEN: UNVERIFIED_IDENTITY,
            UNKNOWN_EMAIL_TOKEN: UNKNOWN_EMAIL_IDENTITY,
            OTHER_TENANT_TOKEN: OTHER_TENANT_IDENTITY,
        }
    )


class LoginTests(unittest.TestCase):
    def test_login_with_verified_known_email_succeeds_and_sets_cookie(self) -> None:
        client = _client(_default_verifier())
        r = client.post("/auth/session", json={"id_token": OWNER_TOKEN})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["user_id"], "user-owner-1")
        self.assertEqual(body["tenant_id"], "demo-tenant")
        self.assertIn("csrf_token", body)
        self.assertIn(SESSION_COOKIE_NAME, r.cookies)

    def test_login_with_invalid_id_token_is_rejected(self) -> None:
        client = _client(_default_verifier())
        r = client.post("/auth/session", json={"id_token": "token-que-nao-existe"})
        self.assertEqual(r.status_code, 401, r.text)
        self.assertNotIn(SESSION_COOKIE_NAME, r.cookies)

    def test_login_with_unverified_email_is_rejected(self) -> None:
        client = _client(_default_verifier())
        r = client.post("/auth/session", json={"id_token": UNVERIFIED_TOKEN})
        self.assertEqual(r.status_code, 401, r.text)
        self.assertNotIn(SESSION_COOKIE_NAME, r.cookies)

    def test_login_with_verified_but_unknown_email_is_rejected_fail_closed(self) -> None:
        """Decisao do Diretor (24/09/2026): identidade do Google provada, mas sem vinculo
        interno -> RECUSA. Nunca autoprovisiona tenant/usuario novo."""
        client = _client(_default_verifier())
        r = client.post("/auth/session", json={"id_token": UNKNOWN_EMAIL_TOKEN})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")
        self.assertNotIn(SESSION_COOKIE_NAME, r.cookies)

    def test_each_login_issues_a_fresh_session_id_never_reusing_a_client_supplied_cookie(
        self,
    ) -> None:
        """Protecao contra session fixation (NFR 4.1 + WP-02): o servidor nunca "promove"
        um session_id que o cliente ja tinha antes do login -- sempre gera um novo."""
        client = _client(_default_verifier())
        client.cookies.set(SESSION_COOKIE_NAME, "attacker-chosen-session-id")

        r = client.post("/auth/session", json={"id_token": OWNER_TOKEN})
        self.assertEqual(r.status_code, 200, r.text)
        new_session_id = r.cookies[SESSION_COOKIE_NAME]
        self.assertNotEqual(new_session_id, "attacker-chosen-session-id")

        # O id "escolhido pelo atacante" nunca foi promovido a uma sessao valida.
        probe = _client(_default_verifier())
        probe.cookies.set(SESSION_COOKIE_NAME, "attacker-chosen-session-id")
        r2 = probe.get("/me")
        self.assertEqual(r2.status_code, 401, r2.text)

    def test_two_logins_issue_two_different_session_ids(self) -> None:
        client = _client(_default_verifier())
        r1 = client.post("/auth/session", json={"id_token": OWNER_TOKEN})
        sid1 = r1.cookies[SESSION_COOKIE_NAME]
        r2 = client.post("/auth/session", json={"id_token": OWNER_TOKEN})
        sid2 = r2.cookies[SESSION_COOKIE_NAME]
        self.assertNotEqual(sid1, sid2)


class SessionAuthenticatesProtectedRoutesTests(unittest.TestCase):
    def _logged_in_client(self, token: str = OWNER_TOKEN) -> tuple[TestClient, str]:
        client = _client(_default_verifier())
        r = client.post("/auth/session", json={"id_token": token})
        self.assertEqual(r.status_code, 200, r.text)
        return client, r.json()["csrf_token"]

    def test_session_cookie_authenticates_get_me(self) -> None:
        client, _ = self._logged_in_client()
        r = client.get("/me")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["user_id"], "user-owner-1")

    def test_get_without_any_cookie_or_bearer_is_unauthenticated(self) -> None:
        client = _client(_default_verifier())
        r = client.get("/me")
        self.assertEqual(r.status_code, 401, r.text)

    def test_mutating_request_without_csrf_header_is_rejected(self) -> None:
        client, _csrf = self._logged_in_client()
        r = client.post(
            "/brand-profiles", headers=idem("no-csrf"), json={"name": "X", "tone": ""}
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")

    def test_mutating_request_with_wrong_csrf_header_is_rejected(self) -> None:
        client, _csrf = self._logged_in_client()
        r = client.post(
            "/brand-profiles",
            headers={**idem("wrong-csrf"), CSRF_HEADER_NAME: "token-errado"},
            json={"name": "X", "tone": ""},
        )
        self.assertEqual(r.status_code, 403, r.text)

    def test_mutating_request_with_correct_csrf_header_succeeds(self) -> None:
        client, csrf = self._logged_in_client()
        r = client.post(
            "/brand-profiles",
            headers={**idem("right-csrf"), CSRF_HEADER_NAME: csrf},
            json={"name": "X", "tone": ""},
        )
        self.assertEqual(r.status_code, 201, r.text)

    def test_cross_tenant_isolation_holds_through_real_session(self) -> None:
        """Mesma garantia de isolamento (I-04, permissions.py) ja testada com o fixture
        de bearer token, agora provada com o caminho real de sessao."""
        owner_client, owner_csrf = self._logged_in_client(OWNER_TOKEN)
        r = owner_client.post(
            "/brand-profiles",
            headers={**unique_idem(), CSRF_HEADER_NAME: owner_csrf},
            json={"name": "Segredo do demo-tenant", "tone": ""},
        )
        self.assertEqual(r.status_code, 201, r.text)

        other_client, _ = self._logged_in_client(OTHER_TENANT_TOKEN)
        r = other_client.get("/brand-profiles")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), [])  # nunca ve o brand profile do outro tenant


class LogoutTests(unittest.TestCase):
    def test_logout_invalidates_the_session(self) -> None:
        client = _client(_default_verifier())
        r = client.post("/auth/session", json={"id_token": OWNER_TOKEN})
        self.assertEqual(r.status_code, 200, r.text)

        r = client.delete("/auth/session")
        self.assertEqual(r.status_code, 204, r.text)

        r = client.get("/me")
        self.assertEqual(r.status_code, 401, r.text)

    def test_logout_without_any_session_is_a_no_op_204(self) -> None:
        client = _client(_default_verifier())
        r = client.delete("/auth/session")
        self.assertEqual(r.status_code, 204, r.text)


class SessionExpiryTests(unittest.TestCase):
    def test_expired_session_is_rejected(self) -> None:
        app = create_app(env="test")
        state: AppState = app.state.campaia
        state.id_token_verifier = _default_verifier()

        principal = state.identity_directory.resolve(OWNER_IDENTITY.email)
        past = datetime.now(timezone.utc) - timedelta(hours=25)
        record = state.sessions.create(principal, now=past)  # TTL padrao de 24h -> ja expirou

        client = TestClient(app, base_url="https://testserver")
        client.cookies.set(SESSION_COOKIE_NAME, record.session_id)
        r = client.get("/me")
        self.assertEqual(r.status_code, 401, r.text)


class DevFixtureFailClosedTests(unittest.TestCase):
    """Item 1.3/WP-02: o fixture de bearer token nunca pode existir fora de test/dev-local
    -- ja garantido por AppState.__post_init__ (ver tests/... nao, e api layer: aqui
    provamos o efeito observavel na API)."""

    def test_bearer_fixture_is_unusable_when_app_boots_outside_allowed_envs(self) -> None:
        from api.state import TokenPrincipal

        with self.assertRaises(RuntimeError):
            AppState(
                env="production",
                tokens={
                    "leaked-fixture-token": TokenPrincipal(
                        user_id="u", tenant_id="t", roles=frozenset({Role.OWNER})
                    )
                },
            )

    def test_default_boot_has_no_dev_fixture_and_rejects_legacy_bearer_header(self) -> None:
        # Sem tokens explicitos, o boot "production" nao levanta (tokens vazio por
        # padrao) -- so falha se alguem POPULAR tokens fora do ambiente permitido
        # (provado acima). Aqui confirmamos que, sem fixture, o Bearer legado so falha.
        app = create_app(env="production")
        client = TestClient(app)
        r = client.get("/me", headers={"Authorization": "Bearer demo-owner-token"})
        self.assertEqual(r.status_code, 401, r.text)


if __name__ == "__main__":
    unittest.main()
