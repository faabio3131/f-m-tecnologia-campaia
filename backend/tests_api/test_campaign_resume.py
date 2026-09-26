"""ACHADO 25 (Fase 4, item A da missao de reconciliacao/takeover, 26/09/2026): POST
/campaigns/{campaignId}/resume.

FATO CONFIRMADO por leitura real do dominio antes de qualquer codigo ser escrito:
campaia_core/states.py ja modelava e testava a transicao PAUSED -> ACTIVE (guarda
`_guard_resume`) -- so faltava exposicao via API (nenhuma rota, nenhum contrato, nenhuma
UI existiam). Nenhuma mudanca de semantica de dominio foi necessaria; nenhuma chamada de
conector foi inventada (AdsConnector nao declara `resume`/`unpause` -- a propria chamada
`connector.pause(...)` que `pause_campaign` faz hoje e simbolica e sem efeito observavel,
confirmado por grep real: `ProviderSimulator()` novo e descartado a cada chamada, `.paused`
nunca lido em lugar nenhum).
"""

from __future__ import annotations

import unittest

from tests_api.test_helpers import (
    OTHER_OWNER,
    OWNER,
    idem,
    make_client,
    publish_ready_campaign,
    with_step_up,
)


def _publish_and_pause(client, headers=OWNER):
    camp, decision, approval = publish_ready_campaign(client, headers)
    cid = camp["id"]
    r = client.post(
        f"/campaigns/{cid}/publish",
        headers={**with_step_up(headers), **idem(f"pub-{cid}")},
        json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
    )
    assert r.status_code == 202, r.text
    r = client.post(f"/campaigns/{cid}/pause", headers={**headers, **idem(f"pause-{cid}")})
    assert r.status_code == 202, r.text
    assert r.json()["state"] == "PAUSED"
    return cid


class TestCampaignResume(unittest.TestCase):
    def test_resume_transitions_paused_campaign_back_to_active(self):
        client = make_client()
        cid = _publish_and_pause(client)

        r = client.post(
            f"/campaigns/{cid}/resume", headers={**with_step_up(OWNER), **idem("resume-1")}
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["state"], "ACTIVE")

    def test_resume_records_a_campaign_resume_audit_event(self):
        client = make_client()
        cid = _publish_and_pause(client)
        client.post(
            f"/campaigns/{cid}/resume", headers={**with_step_up(OWNER), **idem("resume-audit")}
        )

        audit = client.get("/audit-events", headers=OWNER).json()
        resume_events = [e for e in audit["items"] if e["action"] == "CAMPAIGN_RESUME"]
        self.assertEqual(len(resume_events), 1)
        self.assertEqual(resume_events[0]["target"], cid)

    def test_resume_requires_step_up(self):
        client = make_client()
        cid = _publish_and_pause(client)

        r = client.post(f"/campaigns/{cid}/resume", headers={**OWNER, **idem("resume-no-stepup")})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "STEP_UP_REQUIRED")

    def test_resume_requires_idempotency_key(self):
        client = make_client()
        cid = _publish_and_pause(client)

        r = client.post(f"/campaigns/{cid}/resume", headers=with_step_up(OWNER))
        self.assertEqual(r.status_code, 422, r.text)

    def test_resuming_a_campaign_that_is_not_paused_is_rejected(self):
        """Nunca amplia o grafo de transicoes do dominio -- so PAUSED -> ACTIVE e permitido,
        exatamente como campaia_core/states.py ja modelava antes desta rota existir."""
        client = make_client()
        camp, decision, approval = publish_ready_campaign(client)
        cid = camp["id"]
        r = client.post(
            f"/campaigns/{cid}/publish",
            headers={**with_step_up(OWNER), **idem(f"pub2-{cid}")},
            json={"policy_decision_id": decision["policy_decision_id"], "approval_id": approval["id"]},
        )
        self.assertEqual(r.json()["state"], "ACTIVE")

        r2 = client.post(
            f"/campaigns/{cid}/resume", headers={**with_step_up(OWNER), **idem("resume-not-paused")}
        )
        self.assertEqual(r2.status_code, 409, r2.text)
        self.assertEqual(r2.json()["code"], "INVALID_STATE")

    def test_replaying_the_same_idempotency_key_does_not_re_run_or_fail(self):
        client = make_client()
        cid = _publish_and_pause(client)
        headers = {**with_step_up(OWNER), **idem("resume-replay")}

        first = client.post(f"/campaigns/{cid}/resume", headers=headers)
        self.assertEqual(first.status_code, 202, first.text)

        second = client.post(f"/campaigns/{cid}/resume", headers=headers)
        self.assertEqual(second.status_code, 202, second.text)
        self.assertEqual(second.json()["state"], "ACTIVE")

        # Replay nao deve produzir um segundo evento de auditoria.
        audit = client.get("/audit-events", headers=OWNER).json()
        resume_events = [e for e in audit["items"] if e["action"] == "CAMPAIGN_RESUME"]
        self.assertEqual(len(resume_events), 1)

    def test_other_tenant_cannot_resume_first_tenants_campaign(self):
        client = make_client()
        cid = _publish_and_pause(client, headers=OWNER)

        r = client.post(
            f"/campaigns/{cid}/resume",
            headers={**with_step_up(OTHER_OWNER), **idem("cross-tenant-resume")},
        )
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["code"], "NOT_FOUND")

        # A campanha real do dono continua pausada, intocada.
        r = client.get(f"/campaigns/{cid}", headers=OWNER)
        self.assertEqual(r.json()["state"], "PAUSED")


if __name__ == "__main__":
    unittest.main()
