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

from campaia_core.credential_vault import CredentialCipher

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
        client = make_client()
        state_token = _start_oauth(client, OWNER)

        r = client.post(
            "/connections/oauth/callback",
            headers={**OWNER, **unique_idem()},
            json={"state": state_token, "external_account_id": "acct-1", "display_name": "X"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")

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


class OAuthCallbackRealCredentialTests(unittest.TestCase):
    """Decisao do Diretor (27/09/2026, SaaS multi-tenant): quando um token real e'
    enviado no callback, ele tem que ser guardado de verdade no cofre -- nunca
    descartado, nunca em texto claro em nenhum lugar acessivel pela API."""

    def _clear_vault_key(self) -> str | None:
        return os.environ.pop("CAMPAIA_VAULT_KEY", None)

    def _restore_vault_key(self, old: str | None) -> None:
        if old is not None:
            os.environ["CAMPAIA_VAULT_KEY"] = old

    def test_credential_without_vault_key_configured_fails_closed(self):
        old = self._clear_vault_key()
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
                    "credential": {"refresh_token": "1//real-token"},
                },
            )
            self.assertEqual(r.status_code, 422, r.text)
            listed = client.get("/connections", headers=OWNER)
            self.assertEqual(len(listed.json()), 0)
        finally:
            self._restore_vault_key(old)

    def test_credential_is_stored_encrypted_and_never_returned_by_the_api(self):
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
                    "credential": {"refresh_token": "1//real-token"},
                },
            )
            self.assertEqual(r.status_code, 201, r.text)
            body = r.json()
            self.assertNotIn("credential", body)
            self.assertNotIn("secret_ref", body)
            self.assertNotIn("1//real-token", r.text)

            from campaia_core.connectors import SecretRef

            state = client.app.state.campaia
            conn = state.connections.get("demo-tenant", body["id"])
            self.assertIsNotNone(conn.secret_ref)
            self.assertTrue(conn.secret_ref.startswith("vault://GOOGLE_ADS/"))

            resolved = state.vault.resolve(
                "demo-tenant", SecretRef(handle=conn.secret_ref), cipher=state.vault_cipher
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
            state_token = _start_oauth(client, OWNER)

            created = client.post(
                "/connections/oauth/callback",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={
                    "state": state_token,
                    "external_account_id": "acct-real-1",
                    "display_name": "Conta real",
                    "credential": {"refresh_token": "1//real-token"},
                },
            ).json()

            state = client.app.state.campaia
            conn_before = state.connections.get("demo-tenant", created["id"])
            secret_ref_handle = conn_before.secret_ref

            revoke = client.delete(
                f"/connections/{created['id']}",
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

    def test_replaying_the_same_idempotency_key_with_credential_returns_the_original_result(self):
        """Pedido explicito de auditoria independente (27/09/2026): o replay do achado
        24 (mesma Idempotency-Key, `state` de OAuth ja consumido) tem que continuar
        funcionando quando `credential` esta presente -- nao pode falhar por o state ja
        ter sido resgatado, nao pode criar uma segunda Connection, e (Fase C6) nao pode
        criar um segundo segredo no cofre nem devolver um resultado diferente do
        original."""
        old = self._clear_vault_key()
        os.environ["CAMPAIA_VAULT_KEY"] = CredentialCipher.generate_key()
        try:
            client = make_client()
            state_token = _start_oauth(client, OWNER)
            headers = {**with_step_up(OWNER), **idem("oauth-callback-replay-credential")}
            body = {
                "state": state_token,
                "external_account_id": "acct-real-1",
                "display_name": "Conta real",
                "credential": {"refresh_token": "1//real-token"},
            }

            first = client.post("/connections/oauth/callback", headers=headers, json=body)
            self.assertEqual(first.status_code, 201, first.text)

            replay = client.post("/connections/oauth/callback", headers=headers, json=body)
            self.assertEqual(replay.status_code, 201, replay.text)
            self.assertEqual(replay.json(), first.json())

            listed = client.get("/connections", headers=OWNER)
            self.assertEqual(len(listed.json()), 1)

            from campaia_core.connectors import SecretRef

            state = client.app.state.campaia
            conn = state.connections.get("demo-tenant", first.json()["id"])
            # So um segredo no cofre para esta conexao -- o replay nao chegou a chamar
            # `_do_create` de novo (protegido por idempotency.execute), entao
            # `vault.store` nunca rodou uma segunda vez.
            resolved = state.vault.resolve(
                "demo-tenant", SecretRef(handle=conn.secret_ref), cipher=state.vault_cipher
            )
            self.assertEqual(resolved, {"refresh_token": "1//real-token"})
        finally:
            os.environ.pop("CAMPAIA_VAULT_KEY", None)
            self._restore_vault_key(old)


if __name__ == "__main__":
    unittest.main()
