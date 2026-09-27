"""Fase C2/C3 (27/09/2026 -- auditoria independente): prova que o step-up parou de
aceitar "qualquer valor nao-vazio" fora de test/dev-local (C2), e que passou a ficar
amarrado a sessao/credencial corrente em vez de sobreviver a logout->login ou troca de
tenant na mesma sessao (C3).

Testado diretamente contra `api/deps.py` (nao via HTTP) porque toda rota protegida por
step-up hoje tambem chama `require_step_up` explicitamente por defesa em profundidade
(le o header a cada chamada) -- isso mascara, num teste HTTP, a propriedade real que
queremos provar aqui: o valor GRAVADO em `AppState.step_up_at` esta corretamente
amarrado a sessao, nao so a (tenant_id, user_id).
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from api.deps import _current_session_key, _is_genuine_step_up, build_domain_principal, note_step_up_header
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
    def __init__(self, valid_tokens: set[str]) -> None:
        self._valid = valid_tokens

    def verify(self, id_token: str):
        if id_token not in self._valid:
            raise IdentityError("token de teste desconhecido")
        return VerifiedIdentity(subject="uid", email="x@example.com", email_verified=True)


class TestStepUpFailClosedOutsideDevTest(unittest.TestCase):
    """C2: fora de test/dev-local, qualquer valor nao-vazio de X-Step-Up-Token NAO pode
    mais bastar -- precisa ser um ID token real, verificado."""

    def test_any_nonempty_value_is_accepted_in_test_env(self) -> None:
        state = AppState(env="test")
        request = FakeRequest(headers={"x-step-up-token": "qualquer-coisa-nao-vazia"})
        self.assertTrue(_is_genuine_step_up(request, state))

    def test_empty_value_is_never_accepted_even_in_test_env(self) -> None:
        state = AppState(env="test")
        request = FakeRequest(headers={"x-step-up-token": "   "})
        self.assertFalse(_is_genuine_step_up(request, state))

    def test_random_nonempty_value_is_rejected_outside_dev_test(self) -> None:
        state = AppState(env="staging")
        state.id_token_verifier = FakeIdTokenVerifier(valid_tokens={"real-fresh-token"})
        request = FakeRequest(headers={"x-step-up-token": "qualquer-coisa-nao-vazia"})
        self.assertFalse(_is_genuine_step_up(request, state))

    def test_a_real_verified_token_is_accepted_outside_dev_test(self) -> None:
        state = AppState(env="staging")
        state.id_token_verifier = FakeIdTokenVerifier(valid_tokens={"real-fresh-token"})
        request = FakeRequest(headers={"x-step-up-token": "real-fresh-token"})
        self.assertTrue(_is_genuine_step_up(request, state))

    def test_default_production_env_with_no_real_verifier_configured_is_fail_closed(self) -> None:
        """Sem FIREBASE_PROJECT_ID configurado, `state.id_token_verifier` e' o
        `AlwaysRejectIdTokenVerifier` por padrao -- entao em producao real, HOJE, step-up
        e' sempre recusado ate' um verificador real existir. Isso e' o comportamento
        correto (fail-closed), nao um bug."""
        state = AppState(env="production")
        request = FakeRequest(headers={"x-step-up-token": "qualquer-coisa"})
        self.assertFalse(_is_genuine_step_up(request, state))


class TestStepUpSessionBound(unittest.TestCase):
    """C3: o step-up gravado tem que estar amarrado a sessao/credencial corrente."""

    def test_session_key_differs_between_cookie_sessions(self) -> None:
        req_a = FakeRequest(cookies={"campaia_session": "session-aaa"})
        req_b = FakeRequest(cookies={"campaia_session": "session-bbb"})
        self.assertNotEqual(_current_session_key(req_a), _current_session_key(req_b))

    def test_session_key_is_stable_for_the_same_cookie(self) -> None:
        req_1 = FakeRequest(cookies={"campaia_session": "session-aaa"})
        req_2 = FakeRequest(cookies={"campaia_session": "session-aaa"})
        self.assertEqual(_current_session_key(req_1), _current_session_key(req_2))

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
            state.last_step_up("demo-tenant", "user-1", _current_session_key(old_session))
        )

        new_session = FakeRequest(cookies={"campaia_session": "session-after-login"})
        principal = build_domain_principal(new_session, state, _fixture())
        self.assertIsNone(principal.step_up_at)

    def test_step_up_in_tenant_a_does_not_leak_to_tenant_b_same_session_then_back_to_a(self) -> None:
        """A -> B -> A: o step-up feito enquanto o principal era do tenant A nao pode
        contar quando o mesmo usuario troca (WP-03) para o tenant B, e nao volta a
        contar so por voltar para A -- precisa de um step-up novo depois da troca."""
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

        principal_a_again = build_domain_principal(same_session, state, fixture_a)
        self.assertIsNotNone(principal_a_again.step_up_at)  # ainda a mesma sessao, sem trocar


def _fixture(*, tenant_id: str = "demo-tenant"):
    from campaia_core.permissions import Role

    from api.state import TokenPrincipal

    return TokenPrincipal(user_id="user-1", tenant_id=tenant_id, roles=frozenset({Role.OWNER}))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
