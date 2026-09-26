"""ACHADO 22 (Fase 3 da missao de reconciliacao/takeover, item 4, 26/09/2026): regressao
para o vazamento do valor anti-replay `state` do OAuth simulado na trilha de auditoria.

FATO CONFIRMADO por execucao real (nesta sessao, antes da correcao): `POST
/connections/oauth/start` registrava um evento `OAUTH_START` cujo `details` incluia o
proprio valor `state` (o nonce anti-replay de uso unico, escopado por tenant, TTL curto).
Nao era uma exposicao de credencial real (o mesmo valor ja e devolvido ao chamador nesta
mesma resposta, e o fluxo nunca contata um provider real), mas uma trilha de auditoria e
para revisar acoes, nao para guardar valores de seguranca -- a PR#6 ja havia corrigido
exatamente este ponto (commit 9a0e6b3, "fix(audit): stop storing the OAuth anti-replay
state value in the audit trail"), sem nenhum teste de regressao associado la ("No test
asserted this field"). Corrigido aqui da mesma forma, com regressao desta vez."""

from __future__ import annotations

import unittest

from tests_api.test_helpers import OWNER, make_client, with_step_up


class TestOAuthAuditNoStateLeak(unittest.TestCase):
    def test_oauth_start_audit_event_never_stores_the_anti_replay_state_value(self):
        client = make_client()
        r = client.post(
            "/connections/oauth/start", headers=with_step_up(OWNER), json={"provider": "GOOGLE_ADS"}
        )
        self.assertEqual(r.status_code, 200, r.text)
        returned_state = r.json()["state"]
        self.assertTrue(returned_state)

        audit = client.get("/audit-events", headers=OWNER).json()
        oauth_events = [e for e in audit["items"] if e["action"] == "OAUTH_START"]
        self.assertEqual(len(oauth_events), 1)

        evidence = oauth_events[0]["evidence"] or {}
        self.assertNotIn("state", evidence)
        # A anti-replay state nao aparece em NENHUM valor serializado da evidencia --
        # nao so na chave "state" (defesa contra um renomeio futuro da chave que
        # reintroduza o mesmo vazamento por outro nome).
        self.assertNotIn(returned_state, [str(v) for v in evidence.values()])


if __name__ == "__main__":
    unittest.main()
