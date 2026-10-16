"""A membership switch is explicit and atomic; general tenant guards remain strict."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from api.main import create_app


class PersistentSessionSwitchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temporary.name) / "runtime.db")
        self.a = create_app(env="test", db_path=self.path).state.campaia
        self.b = create_app(env="test", db_path=self.path).state.campaia
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.a.db.close)
        self.addCleanup(self.b.db.close)
        self.first = self.a.tokens["demo-owner-token"]
        self.second = replace(self.first, tenant_id="other-tenant", user_id="another-membership")
        self.record = self.a.sessions.create(self.first, now=datetime.now(timezone.utc),
            available_principals=(self.first, self.second), subject="same-google-identity")

    def test_switch_preserves_cookie_csrf_identity_and_immutable_guard(self):
        changed = self.a.sessions.switch_principal(self.record.session_id, self.second)
        self.assertEqual(changed.session_id, self.record.session_id)
        self.assertEqual(changed.csrf_secret, self.record.csrf_secret)
        self.assertEqual(changed.subject, self.record.subject)
        self.assertEqual(changed.available_principals, self.record.available_principals)
        self.assertEqual(self.b.sessions.get(changed.session_id).principal, self.second)
        self.assertIsNone(self.b.db.table("sessions").get_for_tenant(changed.session_id, self.first.tenant_id))
        self.assertEqual(self.b.sessions.switch_principal(changed.session_id, self.first).principal, self.first)
        with self.assertRaises(Exception):
            self.a.db.table("sessions").put(changed.session_id, "foreign-tenant", changed)

    def test_target_must_be_an_existing_captured_membership(self):
        forged = replace(self.second, user_id="foreign-membership")
        self.assertIsNone(self.a.sessions.switch_principal(self.record.session_id, forged))
        self.assertEqual(self.b.sessions.get(self.record.session_id).principal, self.first)

    def test_failed_insert_rolls_back_the_prior_row(self):
        with patch.object(self.a.sessions._table, "put", side_effect=RuntimeError("injected session write")):
            with self.assertRaisesRegex(RuntimeError, "injected session write"):
                self.a.sessions.switch_principal(self.record.session_id, self.second)
        current = self.b.sessions.get(self.record.session_id)
        self.assertEqual(current.principal, self.first)
        self.assertEqual(current.csrf_secret, self.record.csrf_secret)

    def test_concurrent_switch_and_logout_cannot_resurrect_session(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            switched = pool.submit(self.a.sessions.switch_principal, self.record.session_id, self.second)
            revoked = pool.submit(self.b.sessions.invalidate, self.record.session_id)
            switched.result(timeout=5)
            revoked.result(timeout=5)
        self.assertIsNone(self.a.sessions.get(self.record.session_id))

    def test_concurrent_switch_and_membership_revocation_cannot_resurrect_session(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            switched = pool.submit(self.a.sessions.switch_principal, self.record.session_id, self.second)
            revoked = pool.submit(self.b.sessions.invalidate_membership, self.first.user_id)
            switched.result(timeout=5)
            revoked.result(timeout=5)
        self.assertIsNone(self.a.sessions.get(self.record.session_id))


if __name__ == "__main__":
    unittest.main()
