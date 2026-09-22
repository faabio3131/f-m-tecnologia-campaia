"""GET /health -- Missão de fechamento integral (Etapa A17, 22/09/2026): a real liveness
check, added because Etapa A3's audit found no observability of any kind in this backend.
Must never report success while a configured database is genuinely unreachable
(docs/nova-fm/02-PADROES-DE-CONSTRUCAO-NOVA-FM.md §46).
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from api.db import Database
from api.main import create_app

os.environ.setdefault("CAMPAIA_ENV", "test")


class TestHealth(unittest.TestCase):
    def test_health_is_unauthenticated_and_ok_in_pure_in_memory_mode(self):
        app = create_app()
        client = TestClient(app, base_url="https://testserver")

        r = client.get("/health")

        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_health_is_ok_when_a_configured_database_is_genuinely_reachable(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(db_path=os.path.join(tmp, "health-test.sqlite3"))
            client = TestClient(app, base_url="https://testserver")

            r = client.get("/health")

            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json(), {"status": "ok"})

    def test_health_reports_503_when_the_configured_database_is_unreachable(self):
        """Proves this never reports success while a critical dependency is down -- the
        one behavior docs/nova-fm/02-PADROES-DE-CONSTRUCAO-NOVA-FM.md §46 explicitly
        requires a health check to get right."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(db_path=os.path.join(tmp, "health-test-2.sqlite3"))
            client = TestClient(app, base_url="https://testserver")

            with patch.object(Database, "ping", return_value=False):
                r = client.get("/health")

            self.assertEqual(r.status_code, 503, r.text)
            self.assertEqual(r.json(), {"status": "unavailable", "database": "unreachable"})
