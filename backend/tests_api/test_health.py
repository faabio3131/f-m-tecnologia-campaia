"""GET /health -- Fase 3, item 5 da missao de reconciliacao/takeover (Health /
Observability, 26/09/2026, achado 23): regressao para a checagem real de vivacidade.

FATO CONFIRMADO por leitura/grep real do CURRENT antes desta correcao: nenhum endpoint de
health/liveness existia (`NAO ENCONTRADO`), apesar de
`docs/nova-fm/02-PADROES-DE-CONSTRUCAO-NOVA-FM.md` (linha 960) ja exigir um que nunca
reporte sucesso com uma dependencia critica indisponivel. Uma implementacao equivalente
existiu historicamente em `feat/campaia-v1-complete-saas` (commit `84f9645`) e foi
avaliada (nao copiada as cegas) antes de ser adaptada aqui contra os nomes reais do
CURRENT.

Deve nunca reportar sucesso quando um banco configurado esta genuinamente inalcancavel.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from api.db import Database
from api.main import create_app


class TestHealth(unittest.TestCase):
    def test_health_is_unauthenticated_and_ok_in_pure_in_memory_mode(self):
        client = TestClient(create_app(env="test"))

        r = client.get("/health")

        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_health_is_ok_when_a_configured_database_is_genuinely_reachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(
                create_app(env="test", db_path=os.path.join(tmp, "health-test.sqlite3"))
            )

            r = client.get("/health")

            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json(), {"status": "ok"})

    def test_health_reports_503_when_the_configured_database_is_unreachable(self):
        """Prova que o endpoint nunca reporta sucesso com a dependencia critica indisponivel
        -- exatamente o comportamento exigido por
        docs/nova-fm/02-PADROES-DE-CONSTRUCAO-NOVA-FM.md (linha 960)."""
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(
                create_app(env="test", db_path=os.path.join(tmp, "health-test-2.sqlite3"))
            )

            with patch.object(Database, "ping", return_value=False):
                r = client.get("/health")

            self.assertEqual(r.status_code, 503, r.text)
            self.assertEqual(r.json(), {"status": "unavailable", "database": "unreachable"})


if __name__ == "__main__":
    unittest.main()
