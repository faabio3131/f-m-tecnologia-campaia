"""F3 runtime atomicity and shared-state tests using two live app instances."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone

from starlette.testclient import TestClient

from api.main import create_app
from api.state import PendingOAuthState
from campaia_core.permissions import Role

from tests_api.test_commercial_onboarding import (
    FreshIdentityVerifier,
    ID_OWNER_A,
    ORIGIN,
    TOK_OWNER_A,
)


class RuntimeSharedStateTests(unittest.TestCase):
    def _apps(self, path: str):
        a = create_app(db_path=path, env="test")
        b = create_app(db_path=path, env="test")
        for app in (a, b):
            app.state.campaia.id_token_verifier = FreshIdentityVerifier(
                {TOK_OWNER_A: ID_OWNER_A}
            )
            app.state.campaia.allowed_origins = frozenset({ORIGIN})
        return (
            TestClient(a, base_url=ORIGIN),
            TestClient(b, base_url=ORIGIN),
        )

    def test_session_created_on_replica_a_is_readable_and_revocable_on_b(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            principal = a.app.state.campaia.tokens["demo-owner-token"]
            now = datetime.now(timezone.utc)
            record = a.app.state.campaia.sessions.create(
                principal,
                now=now,
                available_principals=(principal,),
                subject="shared-subject",
            )
            seen = b.app.state.campaia.sessions.get(record.session_id)
            self.assertIsNotNone(seen)
            self.assertEqual(seen.principal.tenant_id, principal.tenant_id)

            b.app.state.campaia.sessions.invalidate(record.session_id)
            self.assertIsNone(a.app.state.campaia.sessions.get(record.session_id))

    def test_step_up_is_shared_and_invalidation_crosses_replicas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            at = datetime.now(timezone.utc)
            a.app.state.campaia.record_step_up(
                "demo-tenant", "user-owner-1", "session:opaque", at=at
            )
            self.assertEqual(
                b.app.state.campaia.last_step_up(
                    "demo-tenant", "user-owner-1", "session:opaque"
                ),
                at,
            )
            b.app.state.campaia.invalidate_step_up_for_session("session:opaque")
            self.assertIsNone(
                a.app.state.campaia.last_step_up(
                    "demo-tenant", "user-owner-1", "session:opaque"
                )
            )

    def test_oauth_state_is_shared_and_redeemed_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            now = datetime.now(timezone.utc)
            a.app.state.campaia.start_oauth_state(
                "state-shared",
                tenant_id="demo-tenant",
                provider="GOOGLE_ADS",
                now=now,
                user_id="user-owner-1",
                session_key="session:one",
                step_up_verified_at=now,
            )
            first = b.app.state.campaia.redeem_oauth_state(
                "state-shared", tenant_id="demo-tenant", now=now
            )
            self.assertIsNotNone(first)
            self.assertEqual(first.provider, "GOOGLE_ADS")
            self.assertIsNone(
                a.app.state.campaia.redeem_oauth_state(
                    "state-shared", tenant_id="demo-tenant", now=now
                )
            )

    def test_idempotency_transaction_rolls_back_durable_side_effects_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            state = a.app.state.campaia

            def failing_operation():
                state.audit.append(
                    tenant_id="demo-tenant",
                    actor="user-owner-1",
                    action="F3_SHOULD_ROLL_BACK",
                    target="rollback-target",
                )
                raise RuntimeError("injected failure")

            with self.assertRaisesRegex(RuntimeError, "injected failure"):
                state.idempotency.execute(
                    "demo-tenant",
                    "http:f3:rollback-key",
                    failing_operation,
                )

            # Read through a different live replica so only committed database state counts.
            events = b.app.state.campaia.audit.list_for_tenant("demo-tenant")
            self.assertFalse(any(e.action == "F3_SHOULD_ROLL_BACK" for e in events))
            self.assertIsNone(
                b.app.state.campaia.idempotency.get(
                    "demo-tenant", "http:f3:rollback-key"
                )
            )

    def test_persistent_repository_reads_fresh_state_written_by_other_replica(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            created = a.app.state.campaia.brand_profiles.create(
                "demo-tenant",
                name="Replica A",
                tone="preciso",
                colors=[],
                differentiators=[],
                restrictions=[],
            )
            seen = b.app.state.campaia.brand_profiles.get(
                "demo-tenant", created.brand_profile_id
            )
            self.assertIsNotNone(seen)
            self.assertEqual(seen.name, "Replica A")

            seen.name = "Replica B"
            reread = a.app.state.campaia.brand_profiles.get(
                "demo-tenant", created.brand_profile_id
            )
            self.assertEqual(reread.name, "Replica B")


if __name__ == "__main__":
    unittest.main()
