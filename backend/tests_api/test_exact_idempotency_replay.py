"""Fase C6 (27/09/2026 -- auditoria independente): `patch_budget`, `put_autonomy`,
`decide_approval` e `publish_campaign` devolviam, no replay, uma RE-SERIALIZACAO do
estado atual do recurso -- nunca o `existing.result` de fato guardado pelo
IdempotencyStore. Isso significa que, se outra mutacao legitima (outra Idempotency-Key)
alterasse o mesmo recurso entre a chamada original e um replay tardio, a resposta do
replay refletiria esse estado NOVO, nao a resposta original que o cliente recebeu.

Este arquivo prova, para o caso mais visivel (patch_budget seguido de uma segunda
mudanca real de orcamento, depois um replay tardio da PRIMEIRA chamada), que a resposta
do replay continua sendo a original -- nunca o orcamento mais recente.
"""

from __future__ import annotations

import unittest

from tests_api.test_helpers import OWNER, idem, make_client, publish_ready_campaign, with_step_up


def _approve_budget_change(client, cid: str, new_daily_cap: str, headers=OWNER):
    r = client.post(
        "/approvals",
        headers={**with_step_up(headers), **idem(f"appr-req-{new_daily_cap}")},
        json={"campaign_id": cid, "kind": "BUDGET_CHANGE", "amount": new_daily_cap},
    )
    assert r.status_code == 201, r.text
    approval_id = r.json()["id"]
    r = client.post(
        f"/approvals/{approval_id}/decision",
        headers={**with_step_up({"Authorization": "Bearer demo-finance-token"}), **idem(f"appr-dec-{new_daily_cap}")},
        json={"decision": "APPROVE"},
    )
    assert r.status_code == 200, r.text
    return approval_id


class TestExactIdempotencyReplay(unittest.TestCase):
    def test_stale_patch_budget_replay_returns_the_original_response_not_current_state(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client, headers=OWNER)
        cid = camp["id"]
        client.post(
            f"/campaigns/{cid}/publish",
            headers={**with_step_up(OWNER), **idem(f"pub-{cid}")},
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )

        # Fixture default daily_cap e' 500 (tests_api/test_helpers.py). validate_change
        # recusa variacoes acima de 20% -- 550 (+10%) e depois 600 (+~9% sobre 550) ficam
        # dentro do limite em cada passo.
        approval_1 = _approve_budget_change(client, cid, "550")
        first_key = idem("budget-change-1")
        first = client.patch(
            f"/campaigns/{cid}/budget",
            headers={**with_step_up(OWNER), **first_key},
            json={"approval_id": approval_1, "new_daily_cap": "550"},
        )
        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(first.json()["budget"]["daily_cap"], "550")

        # Uma SEGUNDA mudanca real e legitima, com uma Idempotency-Key diferente,
        # altera o orcamento de verdade.
        approval_2 = _approve_budget_change(client, cid, "600")
        second = client.patch(
            f"/campaigns/{cid}/budget",
            headers={**with_step_up(OWNER), **idem("budget-change-2")},
            json={"approval_id": approval_2, "new_daily_cap": "600"},
        )
        self.assertEqual(second.status_code, 202, second.text)
        self.assertEqual(second.json()["budget"]["daily_cap"], "600")

        # Replay TARDIO da PRIMEIRA chamada (mesma Idempotency-Key de `first_key`): sem
        # a correcao, isso devolveria o orcamento ATUAL (600) -- a resposta correta e' a
        # ORIGINAL desta chamada (550), mesmo a campanha ja estando em outro estado.
        replay = client.patch(
            f"/campaigns/{cid}/budget",
            headers={**with_step_up(OWNER), **first_key},
            json={"approval_id": approval_1, "new_daily_cap": "550"},
        )
        self.assertEqual(replay.status_code, 202, replay.text)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(replay.json()["budget"]["daily_cap"], "550")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
