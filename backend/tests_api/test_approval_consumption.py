"""ACHADO 19 (Fase 3 da missao de reconciliacao/takeover, 26/09/2026): regressao para a
lacuna de consumo de ApprovalRequest.

FATO CONFIRMADO por execucao real (nesta sessao, antes da correcao): uma ApprovalRequest
com status APPROVED nunca era marcada como consumida apos ser efetivamente usada para
aplicar a mudanca que autorizava. O mesmo `approval_id`, reutilizado com uma
Idempotency-Key NOVA, autorizava indefinidamente novas mudancas independentes -- em
PATCH /campaigns/{id}/budget e PUT /autonomy (achado presente nos dois fluxos que fazem
uma mutacao de estado *fora* da propria ApprovalRequest a partir de uma aprovacao ja
concedida). POST /campaigns/{id}/publish nunca foi diretamente explorável por este mesmo
vetor porque a maquina de estados da campanha ja o protegia incidentalmente (uma campanha
nao volta sozinha para APPROVED apos ACTIVE) -- mas o mesmo consumo foi adicionado la
tambem por defesa em profundidade, dando um motivo de negocio explicito (aprovacao ja
usada) em vez de depender apenas desse efeito colateral, e mantendo a semantica
consistente entre os tres fluxos.

Correcao: `ApprovalRequest.status` ganha um novo estado terminal `APPLIED` (contrato e
dominio, aditivo -- nenhum valor existente foi removido). Os tres handlers
(`patch_budget`, `publish_campaign`, `put_autonomy`) passam a marcar a aprovacao usada
como APPLIED apos a mutacao real, e o gate de replay por Idempotency-Key foi movido para
ANTES da checagem de `approval.status`, preservando o comportamento idempotente ja
testado (repetir a MESMA Idempotency-Key sempre devolve o resultado original, nunca
reexecuta e nunca reavalia a aprovacao)."""

from __future__ import annotations

import unittest

from tests_api.test_helpers import (
    APPROVER,
    OWNER,
    create_campaign,
    make_client,
    publish_ready_campaign,
    unique_idem,
    with_step_up,
)


class TestBudgetApprovalConsumption(unittest.TestCase):
    def test_approved_budget_approval_cannot_authorize_a_second_independent_change(self):
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": cid, "kind": "BUDGET_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )

        first_idem = unique_idem()
        r1 = client.patch(
            f"/campaigns/{cid}/budget",
            headers={**with_step_up(OWNER), **first_idem},
            json={"approval_id": approval["id"], "new_daily_cap": "550"},
        )
        self.assertEqual(r1.status_code, 202, r1.text)
        self.assertEqual(r1.json()["budget"]["daily_cap"], "550")

        # Nova tentativa (Idempotency-Key DIFERENTE) reaproveitando o mesmo approval_id
        # -- deve ser recusada: a aprovacao ja foi usada para autorizar a mudanca acima.
        r2 = client.patch(
            f"/campaigns/{cid}/budget",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"approval_id": approval["id"], "new_daily_cap": "600"},
        )
        self.assertEqual(r2.status_code, 403, r2.text)
        self.assertEqual(r2.json()["code"], "APPROVAL_REQUIRED")

        # O orcamento real nao pode ter mudado por causa da tentativa de reuso recusada.
        r_get = client.get(f"/campaigns/{cid}", headers=OWNER)
        self.assertEqual(r_get.json()["budget"]["daily_cap"], "550")

        approvals = client.get("/approvals", headers=OWNER).json()
        mine = next(a for a in approvals if a["id"] == approval["id"])
        self.assertEqual(mine["status"], "APPLIED")

    def test_replaying_the_same_idempotency_key_still_returns_the_original_result(self):
        """Uma aprovacao consumida nao pode ser reusada para uma mudanca NOVA, mas repetir
        a MESMA Idempotency-Key (replay legitimo, ex.: cliente retransmitindo por timeout
        de rede) precisa continuar funcionando -- nunca reavaliar approval.status."""
        client = make_client()
        camp = create_campaign(client)
        cid = camp["id"]
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": cid, "kind": "BUDGET_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )

        idem_key = unique_idem()
        body = {"approval_id": approval["id"], "new_daily_cap": "550"}
        r1 = client.patch(f"/campaigns/{cid}/budget", headers={**with_step_up(OWNER), **idem_key}, json=body)
        self.assertEqual(r1.status_code, 202, r1.text)

        r2 = client.patch(f"/campaigns/{cid}/budget", headers={**with_step_up(OWNER), **idem_key}, json=body)
        self.assertEqual(r2.status_code, 202, r2.text)
        self.assertEqual(r2.json()["budget"]["daily_cap"], "550")


class TestAutonomyApprovalConsumption(unittest.TestCase):
    def test_approved_autonomy_approval_cannot_authorize_a_second_independent_change(self):
        client = make_client()
        camp = create_campaign(client)
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "AUTONOMY_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )

        r1 = client.put(
            "/autonomy",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"level": 0, "approval_id": approval["id"]},
        )
        self.assertEqual(r1.status_code, 200, r1.text)
        self.assertEqual(r1.json()["level"], 0)

        # Reaproveitar a mesma aprovacao para descer para outro nivel deve ser recusado.
        r2 = client.put(
            "/autonomy",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"level": 1, "approval_id": approval["id"]},
        )
        self.assertEqual(r2.status_code, 403, r2.text)
        self.assertEqual(r2.json()["code"], "APPROVAL_REQUIRED")

        r_get = client.get("/autonomy", headers=OWNER)
        self.assertEqual(r_get.json()["level"], 0)

        approvals = client.get("/approvals", headers=OWNER).json()
        mine = next(a for a in approvals if a["id"] == approval["id"])
        self.assertEqual(mine["status"], "APPLIED")

    def test_replaying_the_same_idempotency_key_still_returns_the_original_result(self):
        client = make_client()
        camp = create_campaign(client)
        approval = client.post(
            "/approvals", headers=OWNER, json={"campaign_id": camp["id"], "kind": "AUTONOMY_CHANGE"}
        ).json()
        client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **unique_idem()},
            json={"decision": "APPROVE"},
        )

        idem_key = unique_idem()
        body = {"level": 0, "approval_id": approval["id"]}
        r1 = client.put("/autonomy", headers={**with_step_up(OWNER), **idem_key}, json=body)
        self.assertEqual(r1.status_code, 200, r1.text)

        r2 = client.put("/autonomy", headers={**with_step_up(OWNER), **idem_key}, json=body)
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r2.json()["level"], 0)


class TestPublishApprovalConsumption(unittest.TestCase):
    def test_publish_approval_is_marked_applied_and_still_protected_by_campaign_state(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        cid = camp["id"]

        r1 = client.post(
            f"/campaigns/{cid}/publish",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r1.status_code, 202, r1.text)
        self.assertEqual(r1.json()["state"], "ACTIVE")

        approvals = client.get("/approvals", headers=OWNER).json()
        mine = next(a for a in approvals if a["id"] == approval["id"])
        self.assertEqual(mine["status"], "APPLIED")

        # Uma segunda tentativa (Idempotency-Key nova) com o mesmo approval_id agora e
        # recusada pelo proprio gate de aprovacao (status == APPLIED, nao mais APPROVED)
        # -- antes mesmo de chegar na maquina de estados da campanha, que ja protegia este
        # caminho de forma incidental (campanha nao volta sozinha para APPROVED). O
        # consumo explicito da aprovacao passa a ser a razao primaria da recusa, dando um
        # motivo de negocio explicito (APPROVAL_REQUIRED) em vez de um efeito colateral do
        # estado da campanha.
        r2 = client.post(
            f"/campaigns/{cid}/publish",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r2.status_code, 403, r2.text)
        self.assertEqual(r2.json()["code"], "APPROVAL_REQUIRED")

    def test_replaying_the_same_idempotency_key_still_returns_the_original_result(self):
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        cid = camp["id"]

        idem_key = unique_idem()
        body = {"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]}
        r1 = client.post(f"/campaigns/{cid}/publish", headers={**with_step_up(OWNER), **idem_key}, json=body)
        self.assertEqual(r1.status_code, 202, r1.text)

        r2 = client.post(f"/campaigns/{cid}/publish", headers={**with_step_up(OWNER), **idem_key}, json=body)
        self.assertEqual(r2.status_code, 202, r2.text)
        self.assertEqual(r2.json()["state"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
