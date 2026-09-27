"""Fase C4 (27/09/2026 -- auditoria independente): `pause_campaign`, `resume_campaign`
e `revoke_connection` guardavam o resultado no idempotency store usando a
Idempotency-Key CRUA, sem prefixo de operacao (`http:<operacao>:<chave>`, ja usado por
todo outro endpoint mutante). Isso significa que a MESMA chave literal, reaproveitada
para duas operacoes diferentes do mesmo tenant, colidia no mesmo `(tenant_id, chave)`
do store: a segunda operacao devolvia o resultado CACHEADO da primeira, em vez de
executar de verdade.

Este arquivo prova que, apos a correcao, reaproveitar a mesma Idempotency-Key entre
`pause` e `resume` (ou `revoke_connection`) nao causa colisao -- cada operacao executa
de verdade e devolve o proprio resultado.
"""

from __future__ import annotations

import unittest

from tests_api.test_helpers import OWNER, idem, make_client, publish_ready_campaign, with_step_up


class TestIdempotencyNamespacing(unittest.TestCase):
    def test_same_key_reused_for_pause_then_resume_does_not_collide(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client, headers=OWNER)
        cid = camp["id"]
        client.post(
            f"/campaigns/{cid}/publish",
            headers={**with_step_up(OWNER), **idem(f"pub-{cid}")},
            json={
                "policy_decision_id": decision["policy_decision_id"],
                "approval_id": approval["id"],
            },
        )

        shared_key = idem("shared-key-reused")

        paused = client.post(f"/campaigns/{cid}/pause", headers={**OWNER, **shared_key})
        self.assertEqual(paused.status_code, 202, paused.text)
        self.assertEqual(paused.json()["state"], "PAUSED")

        # SEM a correcao, esta chamada devolveria o resultado CACHEADO de pause (mesma
        # chave, mesmo tenant) em vez de executar resume de verdade -- o teste falharia
        # com state=="PAUSED" em vez de "ACTIVE".
        resumed = client.post(
            f"/campaigns/{cid}/resume", headers={**with_step_up(OWNER), **shared_key}
        )
        self.assertEqual(resumed.status_code, 202, resumed.text)
        self.assertEqual(resumed.json()["state"], "ACTIVE")

    def test_same_key_reused_for_pause_then_revoke_connection_does_not_collide(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client, headers=OWNER)
        cid = camp["id"]
        client.post(
            f"/campaigns/{cid}/publish",
            headers={**with_step_up(OWNER), **idem(f"pub2-{cid}")},
            json={
                "policy_decision_id": decision["policy_decision_id"],
                "approval_id": approval["id"],
            },
        )

        conn = client.app.state.campaia.connections.create(
            "demo-tenant", provider="GOOGLE_ADS", external_account_id="acct-1", display_name="A"
        )

        shared_key = idem("shared-key-reused-2")

        paused = client.post(f"/campaigns/{cid}/pause", headers={**OWNER, **shared_key})
        self.assertEqual(paused.status_code, 202, paused.text)

        revoked = client.delete(
            f"/connections/{conn.connection_id}",
            headers={**with_step_up(OWNER), **shared_key},
        )
        # SEM a correcao, isso devolveria o 202 cacheado de pause (corpo de campanha),
        # nunca chegando a revogar a conexao de verdade.
        self.assertEqual(revoked.status_code, 204, revoked.text)
        self.assertEqual(
            client.app.state.campaia.connections.get("demo-tenant", conn.connection_id).status,
            "REVOKED",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
