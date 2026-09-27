"""Fase C2/C3 (27/09/2026 -- auditoria independente) + achados 1/2/3 da auditoria
independente #3 (mesma data): prova que o step-up parou de aceitar "qualquer valor
nao-vazio" fora de test/dev-local (C2), que passou a ficar amarrado a sessao/credencial
corrente em vez de sobreviver a logout->login ou troca de tenant na mesma sessao (C3),
que o token apresentado precisa pertencer ao MESMO usuario da sessao (achado 1), que
precisa ser recente (achado 2), e que QUALQUER troca de vinculo (WP-03) invalida todo
step-up daquela sessao, mesmo o de vinculos aos quais ela volta depois (achado 3).

Testado diretamente contra `api/deps.py` (nao via HTTP) porque toda rota protegida por
step-up hoje tambem chama `require_step_up` explicitamente por defesa em profundidade
(le o header a cada chamada) -- isso mascara, num teste HTTP, a propriedade real que
queremos provar aqui: o valor GRAVADO em `AppState.step_up_at` esta corretamente
amarrado a sessao, nao so a (tenant_id, user_id). O achado 3 tambem tem um teste REAL de
rota/sessao em `test_step_up_invalidated_on_membership_switch.py`, provando a mesma
propriedade fim-a-fim via `POST /auth/session/switch`.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from api.deps import (
    STEP_UP_TOKEN_MAX_AUTH_AGE,
    _is_genuine_step_up,
    build_domain_principal,
    note_step_up_header,
    session_key_for,
)
from api.state import AppState
from campaia_core.identity_provider import IdentityError, VerifiedIdentity


class FakeRequest:
    """Duck-type minimo do que `api/deps.py` realmente le de um `starlette.Request`
    para step-up: `.cookies` (dict), `.headers.get(...)` (chaves em minusculo, mesma
    convencao que o codigo real usa) e `.app.state.campaia` (usado por
    `get_state(request)`, chamado dentro de `note_step_up_header`)."""

    def __init__(
        self,
        *,
        cookies: dict | None = None,
        headers: dict | None = None,
        state: "AppState | None" = None,
    ) -> None:
        self.cookies = cookies or {}
        self.headers = _Headers(headers or {})
        self.app = _App(state)


class _App:
    def __init__(self, state: "AppState | None") -> None:
        self.state = _AppStateHolder(state)


class _AppStateHolder:
    def __init__(self, state: "AppState | None") -> None:
        self.campaia = state


class _Headers:
    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


class FakeIdTokenVerifier:
    """Test double do IdTokenVerifier Protocol. `tokens` mapeia token -> VerifiedIdentity
    inteira (achados 1/2, 27/09/2026): diferente da versao anterior deste arquivo, que
    sempre devolvia o mesmo e-mail fixo para QUALQUER token reconhecido -- isso nunca
    exercitava a correlacao de identidade (achado 1) nem o frescor de `auth_time`
    (achado 2), so' provava que o token era "conhecido"."""

    def __init__(self, tokens: dict[str, VerifiedIdentity]) -> None:
        self._tokens = tokens

    def verify(self, id_token: str) -> VerifiedIdentity:
        identity = self._tokens.get(id_token)
        if identity is None:
            raise IdentityError("token de teste desconhecido")
        return identity


def _identity(*, email: str = "x@example.com", auth_time: datetime | None = None) -> VerifiedIdentity:
    return VerifiedIdentity(
        subject="uid",
        email=email,
        email_verified=True,
        auth_time=auth_time if auth_time is not None else datetime.now(timezone.utc),
    )


class TestStepUpFailClosedOutsideDevTest(unittest.TestCase):
    """C2: fora de test/dev-local, qualquer valor nao-vazio de X-Step-Up-Token NAO pode
    mais bastar -- precisa ser um ID token real, verificado."""

    def test_any_nonempty_value_is_accepted_in_test_env(self) -> None:
        state = AppState(env="test")
        request = FakeRequest(headers={"x-step-up-token": "qualquer-coisa-nao-vazia"})
        self.assertTrue(_is_genuine_step_up(request, state, _fixture()))

    def test_empty_value_is_never_accepted_even_in_test_env(self) -> None:
        state = AppState(env="test")
        request = FakeRequest(headers={"x-step-up-token": "   "})
        self.assertFalse(_is_genuine_step_up(request, state, _fixture()))

    def test_random_nonempty_value_is_rejected_outside_dev_test(self) -> None:
        state = AppState(env="staging")
        state.id_token_verifier = FakeIdTokenVerifier({"real-fresh-token": _identity()})
        request = FakeRequest(headers={"x-step-up-token": "qualquer-coisa-nao-vazia"})
        self.assertFalse(_is_genuine_step_up(request, state, _fixture()))

    def test_a_real_verified_token_is_accepted_outside_dev_test(self) -> None:
        state = AppState(env="staging")
        fixture = _fixture()
        state.id_token_verifier = FakeIdTokenVerifier(
            {"real-fresh-token": _identity(email=fixture.email)}
        )
        request = FakeRequest(headers={"x-step-up-token": "real-fresh-token"})
        self.assertTrue(_is_genuine_step_up(request, state, fixture))

    def test_default_production_env_with_no_real_verifier_configured_is_fail_closed(self) -> None:
        """Sem FIREBASE_PROJECT_ID configurado, `state.id_token_verifier` e' o
        `AlwaysRejectIdTokenVerifier` por padrao -- entao em producao real, HOJE, step-up
        e' sempre recusado ate' um verificador real existir. Isso e' o comportamento
        correto (fail-closed), nao um bug."""
        state = AppState(env="production")
        request = FakeRequest(headers={"x-step-up-token": "qualquer-coisa"})
        self.assertFalse(_is_genuine_step_up(request, state, _fixture()))


class TestStepUpIdentityBinding(unittest.TestCase):
    """Achado 1 (auditoria independente #3, 27/09/2026): validar que o header e' um ID
    token real NAO bastava -- ele tambem precisa pertencer ao MESMO usuario da sessao
    corrente. Um token real e' valido, mas de OUTRO usuario, nao pode elevar esta sessao."""

    def test_session_a_with_token_belonging_to_a_is_allowed(self) -> None:
        state = AppState(env="staging")
        fixture_a = _fixture(email="a@example.com")
        state.id_token_verifier = FakeIdTokenVerifier(
            {"token-a": _identity(email="a@example.com")}
        )
        request = FakeRequest(headers={"x-step-up-token": "token-a"})
        self.assertTrue(_is_genuine_step_up(request, state, fixture_a))

    def test_session_a_with_token_belonging_to_b_is_rejected(self) -> None:
        state = AppState(env="staging")
        fixture_a = _fixture(email="a@example.com")
        state.id_token_verifier = FakeIdTokenVerifier(
            {"token-b": _identity(email="b@example.com")}
        )
        request = FakeRequest(headers={"x-step-up-token": "token-b"})
        self.assertFalse(_is_genuine_step_up(request, state, fixture_a))

    def test_invalid_token_is_rejected(self) -> None:
        state = AppState(env="staging")
        fixture_a = _fixture(email="a@example.com")
        state.id_token_verifier = FakeIdTokenVerifier({})  # nada reconhecido
        request = FakeRequest(headers={"x-step-up-token": "token-desconhecido"})
        self.assertFalse(_is_genuine_step_up(request, state, fixture_a))

    def test_note_step_up_header_never_records_a_step_up_for_the_wrong_identity(self) -> None:
        """Mesmo que `note_step_up_header` seja chamada (caminho real de toda rota
        protegida), um token de OUTRO usuario nunca grava step_up_at para a sessao."""
        state = AppState(env="staging")
        fixture_a = _fixture(email="a@example.com", tenant_id="tenant-a")
        state.id_token_verifier = FakeIdTokenVerifier(
            {"token-b": _identity(email="b@example.com")}
        )
        request = FakeRequest(
            cookies={"campaia_session": "session-x"},
            headers={"x-step-up-token": "token-b"},
            state=state,
        )
        note_step_up_header(request, fixture_a)
        self.assertIsNone(
            state.last_step_up("tenant-a", fixture_a.user_id, session_key_for(request))
        )


class TestStepUpFreshness(unittest.TestCase):
    """Achado 2 (auditoria independente #3, 27/09/2026): validade criptografica do token
    NAO prova reautenticacao recente -- `auth_time` precisa estar dentro de
    `STEP_UP_TOKEN_MAX_AUTH_AGE`."""

    def test_recent_auth_time_is_allowed(self) -> None:
        state = AppState(env="staging")
        fixture = _fixture(email="a@example.com")
        state.id_token_verifier = FakeIdTokenVerifier(
            {"token-fresh": _identity(email="a@example.com", auth_time=datetime.now(timezone.utc))}
        )
        request = FakeRequest(headers={"x-step-up-token": "token-fresh"})
        self.assertTrue(_is_genuine_step_up(request, state, fixture))

    def test_old_auth_time_is_rejected(self) -> None:
        state = AppState(env="staging")
        fixture = _fixture(email="a@example.com")
        stale_auth_time = datetime.now(timezone.utc) - STEP_UP_TOKEN_MAX_AUTH_AGE - timedelta(minutes=1)
        state.id_token_verifier = FakeIdTokenVerifier(
            {"token-stale": _identity(email="a@example.com", auth_time=stale_auth_time)}
        )
        request = FakeRequest(headers={"x-step-up-token": "token-stale"})
        self.assertFalse(_is_genuine_step_up(request, state, fixture))

    def test_production_without_real_verifier_is_fail_closed_regardless_of_freshness(self) -> None:
        state = AppState(env="production")
        request = FakeRequest(headers={"x-step-up-token": "qualquer-coisa"})
        self.assertFalse(_is_genuine_step_up(request, state, _fixture()))


class TestStepUpSessionBound(unittest.TestCase):
    """C3: o step-up gravado tem que estar amarrado a sessao/credencial corrente."""

    def test_session_key_differs_between_cookie_sessions(self) -> None:
        req_a = FakeRequest(cookies={"campaia_session": "session-aaa"})
        req_b = FakeRequest(cookies={"campaia_session": "session-bbb"})
        self.assertNotEqual(session_key_for(req_a), session_key_for(req_b))

    def test_session_key_is_stable_for_the_same_cookie(self) -> None:
        req_1 = FakeRequest(cookies={"campaia_session": "session-aaa"})
        req_2 = FakeRequest(cookies={"campaia_session": "session-aaa"})
        self.assertEqual(session_key_for(req_1), session_key_for(req_2))

    def test_step_up_does_not_survive_logout_then_login(self) -> None:
        """Logout->login real emite um session_id NOVO (ver test_auth_session.py::
        test_each_login_issues_a_fresh_session_id...) -- aqui simulamos isso
        diretamente: a MESMA (tenant_id, user_id) volta a logar, mas com um session_id
        diferente, e o step-up antigo nao pode contar para a sessao nova."""
        state = AppState(env="test")
        old_session = FakeRequest(
            cookies={"campaia_session": "session-before-logout"}, headers={"x-step-up-token": "x"}, state=state
        )
        note_step_up_header(old_session, _fixture())
        self.assertIsNotNone(
            state.last_step_up("demo-tenant", "user-1", session_key_for(old_session))
        )

        new_session = FakeRequest(cookies={"campaia_session": "session-after-login"})
        principal = build_domain_principal(new_session, state, _fixture())
        self.assertIsNone(principal.step_up_at)

    def test_step_up_in_tenant_a_does_not_leak_to_tenant_b_same_session(self) -> None:
        """A -> B: o step-up feito enquanto o principal era do tenant A nao pode contar
        quando o mesmo usuario troca (WP-03) para o tenant B na MESMA sessao."""
        state = AppState(env="test")
        same_session = FakeRequest(
            cookies={"campaia_session": "session-shared"},
            headers={"x-step-up-token": "x"},
            state=state,
        )

        fixture_a = _fixture(tenant_id="tenant-a")
        note_step_up_header(same_session, fixture_a)
        principal_a = build_domain_principal(same_session, state, fixture_a)
        self.assertIsNotNone(principal_a.step_up_at)

        fixture_b = _fixture(tenant_id="tenant-b")
        principal_b = build_domain_principal(same_session, state, fixture_b)
        self.assertIsNone(principal_b.step_up_at)

    def test_switching_back_to_a_after_invalidation_requires_a_fresh_step_up(self) -> None:
        """Achado 3 (auditoria independente #3, 27/09/2026): a versao anterior deste
        teste provava que A->B->A RESTAURAVA o step-up antigo de A so' por voltar a
        ela, contradizendo a regra exigida (QUALQUER troca invalida TODO step-up da
        sessao, mesmo o de vinculos aos quais ela volta depois). Aqui simulamos
        exatamente o que `api/routes_auth.py::switch_membership` agora faz de verdade a
        CADA troca: chamar `state.invalidate_step_up_for_session` -- ver tambem
        `test_step_up_invalidated_on_membership_switch.py` para a prova fim-a-fim via
        rota real."""
        state = AppState(env="test")
        same_session = FakeRequest(
            cookies={"campaia_session": "session-shared"},
            headers={"x-step-up-token": "x"},
            state=state,
        )

        fixture_a = _fixture(tenant_id="tenant-a")
        note_step_up_header(same_session, fixture_a)
        principal_a = build_domain_principal(same_session, state, fixture_a)
        self.assertIsNotNone(principal_a.step_up_at)

        # Troca para B: switch_membership chamaria invalidate_step_up_for_session aqui.
        state.invalidate_step_up_for_session(session_key_for(same_session))
        fixture_b = _fixture(tenant_id="tenant-b")
        principal_b = build_domain_principal(same_session, state, fixture_b)
        self.assertIsNone(principal_b.step_up_at)

        # Troca de volta para A: switch_membership invalida de novo -- mesmo sem nenhum
        # step-up ter sido feito em B, o de A tambem nao pode ter sobrevivido.
        state.invalidate_step_up_for_session(session_key_for(same_session))
        principal_a_again = build_domain_principal(same_session, state, fixture_a)
        self.assertIsNone(principal_a_again.step_up_at)


def _fixture(*, tenant_id: str = "demo-tenant", email: str = "user-1@example.com"):
    from campaia_core.permissions import Role

    from api.state import TokenPrincipal

    return TokenPrincipal(
        user_id="user-1", tenant_id=tenant_id, email=email, roles=frozenset({Role.OWNER})
    )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
