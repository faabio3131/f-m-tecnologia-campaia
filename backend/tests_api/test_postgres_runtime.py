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
from datetime import datetime, timedelta, timezone

import psycopg

from api.main import create_app
from api.postgres import (
    PostgresDatabase,
    PostgresFixedWindowRateLimiter,
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


def _process_rate_limit_worker(
    dsn, label, start_event, result_queue, attempts, now_iso
):
    limiter = PostgresFixedWindowRateLimiter(
        PostgresDatabase(dsn),
        scope="process-rate-limit-test",
        max_requests=5,
        window=timedelta(minutes=1),
    )
    now = datetime.fromisoformat(now_iso)
    if not start_event.wait(timeout=10):
        result_queue.put(("error", label, "start timeout"))
        return
    accepted = sum(
        1 for _ in range(attempts)
        if limiter.allow("203.0.113.50", now=now)
    )
    result_queue.put(("ok", label, accepted))


def _g3_state_writer(dsn, ready_event, done_event, ids_queue):
    state = create_app(database_url=dsn, env="test").state.campaia
    principal = state.tokens["demo-owner-token"]
    now = datetime.now(timezone.utc)
    session = state.sessions.create(
        principal,
        now=now,
        available_principals=(principal,),
        subject="g3-two-process-subject",
    )
    state.start_oauth_state(
        "g3-two-process-oauth",
        tenant_id="demo-tenant",
        provider="GOOGLE_ADS",
        now=now,
        user_id=principal.user_id,
        session_key=f"session:{session.session_id}",
        step_up_verified_at=now,
    )
    approval = state.approvals.create(
        "demo-tenant",
        campaign_id="g3-process-campaign",
        kind="PUBLISH",
        requested_by=principal.user_id,
        amount=None,
        requires_dual_approval=False,
        plan_version=1,
    )
    ids_queue.put((session.session_id, approval.approval_id, now.isoformat()))
    ready_event.set()
    done_event.wait(timeout=15)


def _g3_state_reader(dsn, ready_event, done_event, ids, result_queue):
    if not ready_event.wait(timeout=10):
        result_queue.put(("error",))
        return
    session_id, approval_id, now_iso = ids
    state = create_app(database_url=dsn, env="test").state.campaia
    session = state.sessions.get(session_id)
    pending = state.redeem_oauth_state(
        "g3-two-process-oauth",
        tenant_id="demo-tenant",
        now=datetime.fromisoformat(now_iso),
    )
    approval = state.approvals.get("demo-tenant", approval_id)
    wrong_tenant = state.approvals.get("other-tenant", approval_id)
    state.sessions.invalidate(session_id)
    result_queue.put(
        ("ok", session is not None, pending is not None, approval is not None, wrong_tenant is None)
    )
    done_event.set()


def _g3_crash_holder(dsn, ready_event):
    state = create_app(database_url=dsn, env="test").state.campaia

    def operation():
        state.audit.append(
            tenant_id="demo-tenant",
            actor="crashed-process",
            action="G3_CRASH_REPLAY",
            target="crash-key",
        )
        ready_event.set()
        threading.Event().wait(timeout=60)
        return {"unexpected": "survived"}

    state.idempotency.execute(
        "demo-tenant",
        "http:g3:crash-replay",
        operation,
    )


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
            conn.execute(f"TRUNCATE TABLE {RUNTIME_SCHEMA}.rate_limit_windows")

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
            {
                "001_runtime_store_schema",
                "002_tenant_isolation_guard",
                "003_distributed_rate_limit",
            },
        )
        self.assertTrue(RUNTIME_TABLES.issubset(self._runtime_tables()))

        self.assertEqual(
            self.runner.rollback_all(),
            [
                "003_distributed_rate_limit",
                "002_tenant_isolation_guard",
                "001_runtime_store_schema",
            ],
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

    def test_gate_g3_two_simultaneous_processes_share_required_state(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        ready_event = ctx.Event()
        done_event = ctx.Event()
        ids_queue = ctx.Queue()
        result_queue = ctx.Queue()

        writer = ctx.Process(
            target=_g3_state_writer,
            args=(DSN, ready_event, done_event, ids_queue),
        )
        writer.start()
        self.assertTrue(ready_event.wait(timeout=10))
        ids = ids_queue.get(timeout=5)

        reader = ctx.Process(
            target=_g3_state_reader,
            args=(DSN, ready_event, done_event, ids, result_queue),
        )
        reader.start()
        reader.join(timeout=15)
        self.assertEqual(reader.exitcode, 0)
        self.assertEqual(
            result_queue.get(timeout=5),
            ("ok", True, True, True, True),
        )

        done_event.set()
        writer.join(timeout=15)
        self.assertEqual(writer.exitcode, 0)

        state = create_app(database_url=DSN, env="test").state.campaia
        self.assertIsNone(state.sessions.get(ids[0]))
        self.assertIsNotNone(state.approvals.get("demo-tenant", ids[1]))
        self.assertIsNone(state.approvals.get("other-tenant", ids[1]))

    def test_process_crash_rolls_back_and_same_key_retries_once(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        ready_event = ctx.Event()
        crashed = ctx.Process(
            target=_g3_crash_holder,
            args=(DSN, ready_event),
        )
        crashed.start()
        self.assertTrue(ready_event.wait(timeout=10))
        crashed.terminate()
        crashed.join(timeout=15)
        self.assertNotEqual(crashed.exitcode, 0)

        state = create_app(database_url=DSN, env="test").state.campaia
        self.assertIsNone(
            state.idempotency.get("demo-tenant", "http:g3:crash-replay")
        )
        before = [
            event
            for event in state.audit.list_for_tenant("demo-tenant")
            if event.action == "G3_CRASH_REPLAY"
        ]
        self.assertEqual(before, [])

        def retry_operation():
            state.audit.append(
                tenant_id="demo-tenant",
                actor="retry-process",
                action="G3_CRASH_REPLAY",
                target="crash-key",
            )
            return {"status": "committed"}

        result, replay = state.idempotency.execute(
            "demo-tenant",
            "http:g3:crash-replay",
            retry_operation,
        )
        self.assertEqual(result, {"status": "committed"})
        self.assertFalse(replay)

        after = [
            event
            for event in state.audit.list_for_tenant("demo-tenant")
            if event.action == "G3_CRASH_REPLAY"
        ]
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0].actor, "retry-process")

    def test_rate_limiter_is_shared_across_independent_app_instances(self) -> None:
        a, b = self._states()
        now = datetime.now(timezone.utc)
        accepted = 0
        for index in range(61):
            limiter = (
                a.asaas_webhook_rate_limiter
                if index % 2 == 0
                else b.asaas_webhook_rate_limiter
            )
            accepted += int(limiter.allow("198.51.100.24", now=now))
        self.assertEqual(accepted, 60)

        with psycopg.connect(DSN) as conn:
            rows = conn.execute(
                f"SELECT key_hash, request_count "
                f"FROM {RUNTIME_SCHEMA}.rate_limit_windows "
                "WHERE scope = %s",
                ("asaas-webhook",),
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0][0], "198.51.100.24")
        self.assertEqual(rows[0][1], 61)

    def test_rate_limiter_is_global_across_spawned_processes(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        start_event = ctx.Event()
        result_queue = ctx.Queue()
        now_iso = datetime.now(timezone.utc).isoformat()
        processes = [
            ctx.Process(
                target=_process_rate_limit_worker,
                args=(DSN, label, start_event, result_queue, 4, now_iso),
            )
            for label in ("rate-a", "rate-b")
        ]
        for process in processes:
            process.start()
        start_event.set()
        for process in processes:
            process.join(timeout=15)
            self.assertEqual(process.exitcode, 0)

        results = [result_queue.get(timeout=5) for _ in processes]
        self.assertTrue(all(item[0] == "ok" for item in results), results)
        self.assertEqual(sum(item[2] for item in results), 5)

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
