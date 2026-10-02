"""WP-04 (26/09/2026): fecha o ciclo real de POST /connections/oauth/start ->
POST /connections/oauth/callback -> Connection persistida.

FATO CONFIRMADO antes desta mudanca (ver EVIDENCIA_WP04_ONBOARDING_BRAND_KIT_20260926.md):
`oauth_start` nunca criava uma Connection -- so devolvia uma URL simulada e o `state`.
Este arquivo prova o ciclo completo real, incluindo os caminhos fail-closed (state
desconhecido, de outro tenant, ou reutilizado).
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

from campaia_core.credential_vault import CredentialCipher
from campaia_core.permissions import STEP_UP_MAX_AGE

from tests_api.test_helpers import OTHER_OWNER, OWNER, idem, make_client, unique_idem, with_step_up


def _start_oauth(client, headers, provider="GOOGLE_ADS"):
    r = client.post(
        "/connections/oauth/start",
        headers=with_step_up(headers),
        json={"provider": provider},
    )
    assert r.status_code == 200, r.text
    return r.json()["state"]


class OAuthCallbackTests(unittest.TestCase):
    def test_full_flow_creates_a_real_connection(self):
        client = make_client()
        state_token = _start_oauth(client, OWNER)

        r = client.post(
            "/connections/oauth/callback",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={
                "state": state_token,
                "external_account_id": "acct-real-1",
                "display_name": "Conta Google Ads real",
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertEqual(body["provider"], "GOOGLE_ADS")
        self.assertEqual(body["external_account_id"], "acct-real-1")
        self.assertEqual(body["status"], "ACTIVE")

        listed = client.get("/connections", headers=OWNER)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(listed.json()[0]["id"], body["id"])

    def test_unknown_state_is_rejected_fail_closed(self):
        client = make_client()
        r = client.post(
            "/connections/oauth/callback",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={
                "state": "state-que-nunca-existiu",
                "external_account_id": "acct-1",
                "display_name": "X",
            },
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")

    def test_state_from_another_tenant_is_rejected(self):
        """O state foi emitido para other-tenant; OWNER (demo-tenant) nunca pode
        resgata-lo."""
        client = make_client()
        state_token = _start_oauth(client, OTHER_OWNER)

        r = client.post(
            "/connections/oauth/callback",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"state": state_token, "external_account_id": "acct-1", "display_name": "X"},
        )
        self.assertEqual(r.status_code, 403, r.text)

        listed = client.get("/connections", headers=OWNER)
        self.assertEqual(listed.json(), [])

    def test_the_real_owner_of_the_state_can_still_redeem_it(self):
        """other-tenant, o tenant que de fato iniciou o fluxo, resgata o proprio state
        normalmente -- o achado acima e sobre isolamento cross-tenant, nao sobre o
        fluxo legitimo estar quebrado."""
        client = make_client()
        state_token = _start_oauth(client, OTHER_OWNER)

        r = client.post(
            "/connections/oauth/callback",
            headers={**with_step_up(OTHER_OWNER), **unique_idem()},
            json={"state": state_token, "external_account_id": "acct-1", "display_name": "X"},
        )
        self.assertEqual(r.status_code, 201, r.text)

    def test_state_is_single_use(self):
        client = make_client()
        state_token = _start_oauth(client, OWNER)

        first = client.post(
            "/connections/oauth/callback",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"state": state_token, "external_account_id": "acct-1", "display_name": "X"},
        )
        self.assertEqual(first.status_code, 201, first.text)

        second = client.post(
            "/connections/oauth/callback",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"state": state_token, "external_account_id": "acct-2", "display_name": "Y"},
        )
        self.assertEqual(second.status_code, 403, second.text)

        listed = client.get("/connections", headers=OWNER)
        self.assertEqual(len(listed.json()), 1)

    def test_callback_without_step_up_is_rejected(self):
        """SECURITY FIX (27/09/2026 -- correcao final pre-Google-Ads): `_start_oauth` ja
        passa por um step-up genuino (`CONNECTION_MANAGE`, mesma sessao) -- antes da
        correcao de `require_step_up`, isso nao importava, porque a rota reexigia o
        header em toda chamada de qualquer forma (bug corrigido: a janela de step-up
        persistida praticamente nao existia entre requisicoes). Agora que o step-up
        persistido de fato vale por `STEP_UP_MAX_AGE`, o callback LOGO EM SEGUIDA ao
        start, sem header novo, e' esperado que FUNCIONE (ver
        test_callback_allowed_without_a_new_header_within_the_step_up_window abaixo) --
        entao este teste precisa expirar de verdade o step-up persistido para continuar
        provando a exigencia real."""
        client = make_client()
        state_token = _start_oauth(client, OWNER)

        state = client.app.state.campaia
        for key in list(state.step_up_at):
            state.step_up_at[key] = datetime.now(timezone.utc) - STEP_UP_MAX_AGE - timedelta(seconds=1)

        r = client.post(
            "/connections/oauth/callback",
            headers={**OWNER, **unique_idem()},
            json={"state": state_token, "external_account_id": "acct-1", "display_name": "X"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")

    def test_callback_allowed_without_a_new_header_within_the_step_up_window(self):
        """SECURITY FIX (27/09/2026 -- correcao final pre-Google-Ads): o step-up feito
        para iniciar o OAuth (segundos antes, mesma sessao) continua valido para o
        callback, que tambem exige `CONNECTION_MANAGE` -- nenhum header novo e'
        necessario dentro da janela de `STEP_UP_MAX_AGE`. Antes da correcao,
        `require_step_up` reexigia o header em toda chamada, contradizendo `authorize()`
        (que ja aceitava o step-up persistido) -- ver `api/deps.py::require_step_up`."""
        client = make_client()
        state_token = _start_oauth(client, OWNER)

        r = client.post(
            "/connections/oauth/callback",
            headers={**OWNER, **unique_idem()},
            json={"state": state_token, "external_account_id": "acct-1", "display_name": "X"},
        )
        self.assertEqual(r.status_code, 201, r.text)

    def test_callback_requires_idempotency_key(self):
        client = make_client()
        state_token = _start_oauth(client, OWNER)

        r = client.post(
            "/connections/oauth/callback",
            headers=with_step_up(OWNER),
            json={"state": state_token, "external_account_id": "acct-1", "display_name": "X"},
        )
        self.assertEqual(r.status_code, 422, r.text)

    def test_replaying_the_same_idempotency_key_returns_the_original_connection(self):
        """ACHADO 24 (Fase 3, item 6 -- mineracao de testes da PR#6, 26/09/2026): mesma
        classe de bug ja corrigida no achado 19 (patch_budget/publish_campaign/
        put_autonomy), aqui para o `state` de OAuth de uso unico. REPRODUZIDO por execucao
        real antes da correcao: um replay legitimo da MESMA Idempotency-Key (ex.: cliente
        retransmitindo apos timeout de rede) chegava a `redeem_oauth_state` de novo,
        encontrava o state ja consumido pela primeira chamada, e falhava com 403
        PERMISSION_DENIED em vez de devolver o 201 original -- nunca deveria falhar, e
        nunca deveria criar uma segunda Connection."""
        client = make_client()
        state_token = _start_oauth(client, OWNER)
        headers = {**with_step_up(OWNER), **idem("oauth-callback-replay")}
        body = {"state": state_token, "external_account_id": "acct-1", "display_name": "X"}

        first = client.post("/connections/oauth/callback", headers=headers, json=body)
        self.assertEqual(first.status_code, 201, first.text)

        second = client.post("/connections/oauth/callback", headers=headers, json=body)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json(), first.json())

        listed = client.get("/connections", headers=OWNER)
        self.assertEqual(len(listed.json()), 1)

    def test_oauth_start_binds_identity_session_and_step_up_proof_for_a_future_real_callback(
        self,
    ) -> None:
        """PREPARACAO para OAuth real (27/09/2026 -- correcao final pre-Google-Ads, ver
        api/state.py::PendingOAuthState): um callback real (Google/Meta) nunca reenvia
        `X-Step-Up-Token` -- o navegador do usuario e' quem faz essa requisicao, nao este
        backend, e o provider nao devolve headers arbitrarios do Start. Por isso o
        `state` de OAuth precisa carregar, desde o Start, tudo que um callback real vai
        precisar para validar identidade/sessao/step-up sem depender de um header que
        nunca chega. Este teste prova que esses tres campos sao capturados de verdade,
        nao so' declarados no dataclass."""
        client = make_client()
        r = client.post(
            "/connections/oauth/start",
            headers=with_step_up(OWNER),
            json={"provider": "GOOGLE_ADS"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        oauth_state = r.json()["state"]

        pending = client.app.state.campaia.oauth_pending_states[oauth_state]
        self.assertEqual(pending.tenant_id, "demo-tenant")
        self.assertEqual(pending.provider, "GOOGLE_ADS")
        self.assertEqual(pending.user_id, "user-owner-1")
        self.assertTrue(pending.session_key.startswith("bearer:"))
        self.assertIsNotNone(pending.step_up_verified_at)


def _create_connection(client, headers=OWNER) -> dict:
    state_token = _start_oauth(client, headers)
    r = client.post(
        "/connections/oauth/callback",
        headers={**with_step_up(headers), **unique_idem()},
        json={"state": state_token, "external_account_id": "acct-real-1", "display_name": "Conta real"},
    )
    assert r.status_code == 201, r.text
    return r.json()


class DevAttachCredentialTests(unittest.TestCase):
    """SECURITY FIX (Fase 3, achado 4, 27/09/2026 -- auditoria independente): `credential`
    foi retirado do contrato publico de `oauth_callback` -- o TARGET comercial nunca
    deixa um token real trafegar pelo browser at' esse endpoint (troca de OAuth
    server-side, ver ADR-0013). `POST /connections/{id}/dev-attach-credential` e' a
    rota explicitamente dev/test-only que permite continuar provando o cofre real de
    ponta a ponta sem essa troca automatica (que depende de infraestrutura externa
    ainda inexistente)."""

    def _clear_vault_key(self) -> str | None:
        return os.environ.pop("CAMPAIA_VAULT_KEY", None)

    def _restore_vault_key(self, old: str | None) -> None:
        if old is not None:
            os.environ["CAMPAIA_VAULT_KEY"] = old

    def test_oauth_callback_never_accepts_a_credential_field(self):
        """O contrato publico deste endpoint nao tem mais o campo `credential` --
        `OAuthCallbackRequest` (ApiModel, `extra="forbid"`) rejeita explicitamente
        qualquer campo desconhecido com 422, entao nao ha caminho pelo qual um
        `credential` enviado a esta rota chegue a ser processado ou guardado no
        cofre."""
        old = self._clear_vault_key()
        os.environ["CAMPAIA_VAULT_KEY"] = CredentialCipher.generate_key()
        try:
            client = make_client()
            state_token = _start_oauth(client, OWNER)
            r = client.post(
                "/connections/oauth/callback",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={
                    "state": state_token,
                    "external_account_id": "acct-real-1",
                    "display_name": "Conta real",
                    "credential": {"refresh_token": "1//should-be-ignored"},
                },
            )
            self.assertEqual(r.status_code, 422, r.text)
            self.assertEqual(r.json()["code"], "VALIDATION_FAILED")
        finally:
            os.environ.pop("CAMPAIA_VAULT_KEY", None)
            self._restore_vault_key(old)

    def test_dev_attach_credential_fails_closed_outside_dev_test_env(self):
        """A rota dev/test-only se recusa a rodar fora de test/dev-local, mesmo que
        alguem a chame diretamente -- nunca existe de fato em producao."""
        old = self._clear_vault_key()
        os.environ["CAMPAIA_VAULT_KEY"] = CredentialCipher.generate_key()
        try:
            client = make_client()
            conn = _create_connection(client)
            client.app.state.campaia.env = "production"

            r = client.post(
                f"/connections/{conn['id']}/dev-attach-credential",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"credential": {"refresh_token": "1//real-token"}},
            )
            self.assertEqual(r.status_code, 403, r.text)
        finally:
            os.environ.pop("CAMPAIA_VAULT_KEY", None)
            self._restore_vault_key(old)

    def test_credential_without_vault_key_configured_fails_closed(self):
        old = self._clear_vault_key()
        try:
            client = make_client()
            conn = _create_connection(client)

            r = client.post(
                f"/connections/{conn['id']}/dev-attach-credential",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"credential": {"refresh_token": "1//real-token"}},
            )
            self.assertEqual(r.status_code, 422, r.text)
        finally:
            self._restore_vault_key(old)

    def test_credential_is_stored_encrypted_and_never_returned_by_the_api(self):
        old = self._clear_vault_key()
        os.environ["CAMPAIA_VAULT_KEY"] = CredentialCipher.generate_key()
        try:
            client = make_client()
            conn = _create_connection(client)

            r = client.post(
                f"/connections/{conn['id']}/dev-attach-credential",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"credential": {"refresh_token": "1//real-token"}},
            )
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertNotIn("credential", body)
            self.assertNotIn("secret_ref", body)
            self.assertNotIn("1//real-token", r.text)

            from campaia_core.connectors import SecretRef

            state = client.app.state.campaia
            stored = state.connections.get("demo-tenant", conn["id"])
            self.assertIsNotNone(stored.secret_ref)
            self.assertTrue(stored.secret_ref.startswith("vault://GOOGLE_ADS/"))

            resolved = state.vault.resolve(
                "demo-tenant", SecretRef(handle=stored.secret_ref), cipher=state.vault_cipher
            )
            self.assertEqual(resolved, {"refresh_token": "1//real-token"})
        finally:
            os.environ.pop("CAMPAIA_VAULT_KEY", None)
            self._restore_vault_key(old)

    def test_revoking_a_real_connection_also_revokes_the_vault_secret(self):
        old = self._clear_vault_key()
        os.environ["CAMPAIA_VAULT_KEY"] = CredentialCipher.generate_key()
        try:
            client = make_client()
            conn = _create_connection(client)
            client.post(
                f"/connections/{conn['id']}/dev-attach-credential",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"credential": {"refresh_token": "1//real-token"}},
            )

            state = client.app.state.campaia
            conn_before = state.connections.get("demo-tenant", conn["id"])
            secret_ref_handle = conn_before.secret_ref

            revoke = client.delete(
                f"/connections/{conn['id']}",
                headers={**with_step_up(OWNER), **unique_idem()},
            )
            self.assertEqual(revoke.status_code, 204, revoke.text)

            from campaia_core.connectors import SecretRef

            with self.assertRaises(KeyError):
                state.vault.resolve(
                    conn_before.tenant_id,
                    SecretRef(handle=secret_ref_handle),
                    cipher=state.vault_cipher,
                )
        finally:
            os.environ.pop("CAMPAIA_VAULT_KEY", None)
            self._restore_vault_key(old)

    def test_replaying_the_same_idempotency_key_returns_the_original_result(self):
        """Mesmo achado 24 do callback (nao regride nesta rota nova): replay da MESMA
        Idempotency-Key nao cria um segundo segredo, devolve exatamente o resultado
        original."""
        old = self._clear_vault_key()
        os.environ["CAMPAIA_VAULT_KEY"] = CredentialCipher.generate_key()
        try:
            client = make_client()
            conn = _create_connection(client)
            headers = {**with_step_up(OWNER), **idem("attach-credential-replay")}
            body = {"credential": {"refresh_token": "1//real-token"}}

            first = client.post(
                f"/connections/{conn['id']}/dev-attach-credential", headers=headers, json=body
            )
            self.assertEqual(first.status_code, 200, first.text)

            replay = client.post(
                f"/connections/{conn['id']}/dev-attach-credential", headers=headers, json=body
            )
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertEqual(replay.json(), first.json())

            from campaia_core.connectors import SecretRef

            state = client.app.state.campaia
            stored = state.connections.get("demo-tenant", conn["id"])
            resolved = state.vault.resolve(
                "demo-tenant", SecretRef(handle=stored.secret_ref), cipher=state.vault_cipher
            )
            self.assertEqual(resolved, {"refresh_token": "1//real-token"})
        finally:
            os.environ.pop("CAMPAIA_VAULT_KEY", None)
            self._restore_vault_key(old)


if __name__ == "__main__":
    unittest.main()
