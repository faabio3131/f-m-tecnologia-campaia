"""ACHADO 21 (Fase 3 da missao de reconciliacao/takeover, item 3, 26/09/2026): regressao
para a paginacao real de `GET /audit-events`.

FATO CONFIRMADO por execucao real (nesta sessao, antes da correcao): o contrato
(`contracts/bff-openapi.yaml`) sempre prometeu paginacao opaca por `cursor`/
`next_cursor`, mas a implementacao real (`api/routes_audit.py::list_audit_events`)
sempre devolvia `next_cursor: null` e a lista INTEIRA de eventos do tenant de uma vez --
um stub honesto (nunca fabricava uma pagina que nao existia, achado 3/15 original), mas
incompleto: um `cursor` desconhecido/obsoleto era silenciosamente IGNORADO (devolvia a
pagina inteira de novo, sem sinalizar nada de errado) em vez de falhar de forma
controlada.

Avaliada a implementacao historica da PR#6 (paginacao real por cursor opaco = id do
ultimo evento, pagina fixa de 50, cursor desconhecido -> 422 VALIDATION_FAILED) e
adaptada aqui sobre o CURRENT (mesma logica, reconstruida com os nomes de campo e a
convencao de erro ja usados neste modulo, sem copia cega do codigo da PR#6)."""

from __future__ import annotations

import unittest

import api.routes_audit as routes_audit
from tests_api.test_helpers import OWNER, create_campaign, make_client


class TestAuditPagination(unittest.TestCase):
    def test_walking_every_page_via_cursor_yields_every_event_once_no_gaps_no_duplicates(self):
        client = make_client()
        page_size = routes_audit._PAGE_SIZE
        total_events = page_size + 7
        for _ in range(total_events):
            create_campaign(client)

        r = client.get("/audit-events", headers=OWNER)
        self.assertEqual(r.status_code, 200, r.text)
        first_page = r.json()
        self.assertEqual(len(first_page["items"]), page_size)
        self.assertIsNotNone(first_page["next_cursor"])

        seen_ids = [e["id"] for e in first_page["items"]]
        cursor = first_page["next_cursor"]
        pages_walked = 1
        while cursor is not None:
            r = client.get(f"/audit-events?cursor={cursor}", headers=OWNER)
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertLessEqual(len(body["items"]), page_size)
            seen_ids.extend(e["id"] for e in body["items"])
            cursor = body["next_cursor"]
            pages_walked += 1

        self.assertGreater(pages_walked, 1, "deve existir mais de uma pagina real")
        self.assertEqual(len(seen_ids), len(set(seen_ids)), "nenhum evento duplicado entre paginas")
        self.assertEqual(len(seen_ids), total_events, "nenhum evento perdido entre paginas")

    def test_unknown_cursor_fails_closed_instead_of_silently_restarting(self):
        client = make_client()
        create_campaign(client)

        r = client.get("/audit-events?cursor=audit_999999_deadbeef", headers=OWNER)
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "VALIDATION_FAILED")

    def test_last_page_reports_next_cursor_null(self):
        client = make_client()
        create_campaign(client)
        r = client.get("/audit-events", headers=OWNER)
        body = r.json()
        self.assertLess(len(body["items"]), routes_audit._PAGE_SIZE)
        self.assertIsNone(body["next_cursor"])

    def test_campaign_id_filter_still_applies_across_pagination(self):
        client = make_client()
        camp1 = create_campaign(client)
        for _ in range(routes_audit._PAGE_SIZE):
            create_campaign(client)

        r = client.get("/audit-events", headers=OWNER, params={"campaign_id": camp1["id"]})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(all(e["target"] == camp1["id"] for e in body["items"]))
        self.assertGreater(len(body["items"]), 0)
        # Poucos eventos existem para uma unica campanha -- nunca deveria precisar de
        # uma segunda pagina neste teste.
        self.assertIsNone(body["next_cursor"])


if __name__ == "__main__":
    unittest.main()
