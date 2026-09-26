"""WP-04 (26/09/2026): fecha o ciclo real de POST /connections/oauth/start ->
POST /connections/oauth/callback -> Connection persistida.

FATO CONFIRMADO antes desta mudanca (ver EVIDENCIA_WP04_ONBOARDING_BRAND_KIT_20260926.md):
`oauth_start` nunca criava uma Connection -- so devolvia uma URL simulada e o `state`.
Este arquivo prova o ciclo completo real, incluindo os caminhos fail-closed (state
desconhecido, de outro tenant, ou reutilizado).
"""

from __future__ import annotations

import unittest

from tests_api.test_helpers import OTHER_OWNER, OWNER, make_client, unique_idem, with_step_up


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


if __name__ == "__main__":
    unittest.main()
