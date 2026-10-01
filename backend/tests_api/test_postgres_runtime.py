"""F3 PostgreSQL integration tests.

Skipped in the ordinary fast suite and run in a dedicated GitHub Actions job against a
real PostgreSQL 16 service.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import os
import queue
import threading
import time
import unittest
from datetime import datetime, timezone

import psycopg

from api.main import create_app
from api.postgres import (
    PostgresDatabase,
    PostgresMigrationRunner,
    RUNTIME_SCHEMA,
    RUNTIME_TABLES,
)


DSN = os.environ.get("CAMPAIA_TEST_DATABASE_URL")


def _process_idempotency_worker(dsn, label, start_event, result_queue, executed_queue):
    state = create_app(database_url=dsn, env="test").state.campaia
    if not start_event.wait(timeout=10):
        result_queue.put(("error", label, "start timeout"))
        return

    def operation():
        executed_queue.put(label)
        time.sleep(0.25)
        state.audit.append(
            tenant_id="demo-tenant",
            actor=label,
            action="PG_PROCESS_EXACTLY_ONCE",
            target="same-key",
        )
        return {"winner": label}

    try:
        result, replay = state.idempotency.execute(
            "demo-tenant",
            "http:pg:process-concurrent-idempotency",
            operation,
        )
        result_queue.put(("ok", result, replay))
    except Exception as exc:  # pragma: no cover - surfaced to parent assertion
        result_queue.put(("error", label, repr(exc)))


@unittest.skipUnless(DSN, "CAMPAIA_TEST_DATABASE_URL not configured")
class PostgresRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = PostgresMigrationRunner(DSN)
        cls.runner.rollback_all()
        cls.runner.apply_all()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.runner.rollback_all()

    def setUp(self) -> None:
        self.runner.apply_all()
        with psycopg.connect(DSN) as conn:
            for table in RUNTIME_TABLES:
                conn.execute(
                    f'TRUNCATE TABLE {RUNTIME_SCHEMA}."{table}" RESTART IDENTITY'
                )

    def _states(self):
        a = create_app(database_url=DSN, env="test").state.campaia
        b = create_app(database_url=DSN, env="test").state.campaia
        return a, b

    def _runtime_tables(self) -> set[str]:
        with psycopg.connect(DSN) as conn:
            return {
                row[0]
                for row in conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s",
                    (RUNTIME_SCHEMA,),
                ).fetchall()
            }

    def test_00_migration_up_down_up_is_reversible_and_covers_current_stores(self) -> None:
        self.assertEqual(
            set(self.runner.applied_versions()),
            {"001_runtime_store_schema", "002_tenant_isolation_guard"},
        )
        self.assertTrue(RUNTIME_TABLES.issubset(self._runtime_tables()))

        self.assertEqual(
            self.runner.rollback_latest(),
            "001_runtime_store_schema",
        )
        self.assertTrue(RUNTIME_TABLES.isdisjoint(self._runtime_tables()))

        self.runner.apply_all()
        self.assertTrue(RUNTIME_TABLES.issubset(self._runtime_tables()))

    def test_database_rejects_cross_tenant_rehome_and_scopes_reads(self) -> None:
        table = PostgresDatabase(DSN).table("brand_profiles")
        table.put("shared-id", "tenant-a", {"value": "a"})

        with self.assertRaises(Exception):
            table.put("shared-id", "tenant-b", {"value": "b"})

        self.assertEqual(
            table.get_for_tenant("shared-id", "tenant-a"),
            {"value": "a"},
        )
        self.assertIsNone(table.get_for_tenant("shared-id", "tenant-b"))
        self.assertFalse(table.delete_for_tenant("shared-id", "tenant-b"))

        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(DSN) as conn:
                conn.execute(
                    "UPDATE campaia_runtime.brand_profiles "
                    "SET tenant_id = %s WHERE id = %s",
                    ("tenant-b", "shared-id"),
                )

    def test_sessions_are_explicit_pre_tenant_exception_to_rehome_trigger(self) -> None:
        with psycopg.connect(DSN) as conn:
            triggers = {
                row[0]
                for row in conn.execute(
                    "SELECT trigger_name FROM information_schema.triggers "
                    "WHERE event_object_schema = %s AND event_object_table = %s",
                    (RUNTIME_SCHEMA, "sessions"),
                ).fetchall()
            }
        self.assertNotIn("sessions_tenant_immutable", triggers)

    def test_two_independent_app_instances_share_session_and_revocation(self) -> None:
        a, b = self._states()
        principal = a.tokens["demo-owner-token"]
        session = a.sessions.create(
            principal,
            now=datetime.now(timezone.utc),
            available_principals=(principal,),
            subject="postgres-shared-subject",
        )
        seen = b.sessions.get(session.session_id)
        self.assertIsNotNone(seen)
        self.assertEqual(seen.principal.tenant_id, principal.tenant_id)

        b.sessions.invalidate(session.session_id)
        self.assertIsNone(a.sessions.get(session.session_id))

    def test_cross_tenant_repository_lookup_fails_closed(self) -> None:
        a, b = self._states()
        profile = a.brand_profiles.create(
            "tenant-a",
            name="A",
            tone="preciso",
            colors=[],
            differentiators=[],
            restrictions=[],
        )
        self.assertIsNone(
            b.brand_profiles.get("tenant-b", profile.brand_profile_id)
        )
        self.assertIsNotNone(
            b.brand_profiles.get("tenant-a", profile.brand_profile_id)
        )

    def test_transaction_rollback_is_visible_from_another_connection(self) -> None:
        a, b = self._states()

        def failing():
            a.audit.append(
                tenant_id="demo-tenant",
                actor="postgres-test",
                action="PG_SHOULD_ROLL_BACK",
                target="rollback",
            )
            raise RuntimeError("injected postgres rollback")

        with self.assertRaisesRegex(RuntimeError, "injected postgres rollback"):
            a.idempotency.execute(
                "demo-tenant",
                "http:pg:rollback-key",
                failing,
            )

        self.assertFalse(
            any(
                event.action == "PG_SHOULD_ROLL_BACK"
                for event in b.audit.list_for_tenant("demo-tenant")
            )
        )
        self.assertIsNone(
            b.idempotency.get("demo-tenant", "http:pg:rollback-key")
        )

    def test_same_idempotency_key_is_exactly_once_across_connections(self) -> None:
        a, b = self._states()
        started = threading.Barrier(2)
        executed: list[str] = []
        executed_lock = threading.Lock()

        def run(state, label):
            started.wait()

            def operation():
                with executed_lock:
                    executed.append(label)
                time.sleep(0.15)
                state.audit.append(
                    tenant_id="demo-tenant",
                    actor=label,
                    action="PG_EXACTLY_ONCE",
                    target="same-key",
                )
                return {"winner": label}

            return state.idempotency.execute(
                "demo-tenant",
                "http:pg:concurrent-idempotency",
                operation,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, a, "a")
            second = pool.submit(run, b, "b")
            results = [first.result(timeout=10), second.result(timeout=10)]

        self.assertEqual(len(executed), 1)
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(result[1] for result in results), [False, True])

        events = [
            e
            for e in a.audit.list_for_tenant("demo-tenant")
            if e.action == "PG_EXACTLY_ONCE"
        ]
        self.assertEqual(len(events), 1)

    def test_different_idempotency_keys_same_tenant_are_serialized(self) -> None:
        a, b = self._states()
        barrier = threading.Barrier(2)
        guard = threading.Lock()
        active = 0
        max_active = 0

        def run(state, key):
            nonlocal active, max_active
            barrier.wait()

            def operation():
                nonlocal active, max_active
                with guard:
                    active += 1
                    max_active = max(max_active, active)
                time.sleep(0.12)
                with guard:
                    active -= 1
                return {"key": key}

            return state.idempotency.execute("demo-tenant", key, operation)

        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(run, a, "http:pg:tenant-lock-a")
            two = pool.submit(run, b, "http:pg:tenant-lock-b")
            one.result(timeout=10)
            two.result(timeout=10)

        self.assertEqual(max_active, 1)

    def test_same_idempotency_key_is_exactly_once_across_spawned_processes(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        start_event = ctx.Event()
        result_queue = ctx.Queue()
        executed_queue = ctx.Queue()
        processes = [
            ctx.Process(
                target=_process_idempotency_worker,
                args=(DSN, label, start_event, result_queue, executed_queue),
            )
            for label in ("proc-a", "proc-b")
        ]
        for process in processes:
            process.start()
        start_event.set()
        for process in processes:
            process.join(timeout=15)
            self.assertEqual(process.exitcode, 0)

        results = [result_queue.get(timeout=5) for _ in processes]
        self.assertTrue(all(item[0] == "ok" for item in results), results)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(sorted(item[2] for item in results), [False, True])

        executed = [executed_queue.get(timeout=5)]
        with self.assertRaises(queue.Empty):
            executed_queue.get(timeout=0.25)
        self.assertEqual(len(executed), 1)

        state = create_app(database_url=DSN, env="test").state.campaia
        events = [
            event
            for event in state.audit.list_for_tenant("demo-tenant")
            if event.action == "PG_PROCESS_EXACTLY_ONCE"
        ]
        self.assertEqual(len(events), 1)

    def test_database_ping_and_table_contract_are_real_postgres(self) -> None:
        db = PostgresDatabase(DSN)
        self.assertTrue(db.ping())
        table = db.table("brand_profiles")
        table.put("bp-pg", "tenant-a", {"value": 1})
        self.assertEqual(table.get("bp-pg"), {"value": 1})
        self.assertEqual(
            table.rows_for_tenant("tenant-a"),
            [("bp-pg", "tenant-a", {"value": 1})],
        )


if __name__ == "__main__":
    unittest.main()
