"""PostgreSQL runtime adapter for CampaIA F3.

The domain and repository layers remain storage-agnostic. This module implements the same
RecordTable surface used by the SQLite compatibility backend, while each outer transaction
owns an independent PostgreSQL connection. Separate workers and containers therefore
coordinate through PostgreSQL rather than process-local memory.

Migrations are explicit and versioned. App startup never creates or mutates the production
schema implicitly; deployment automation must run migrations before promotion.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import re
import threading
from typing import Any, Iterator

import psycopg
from psycopg.types.json import Jsonb

from .db import decode, encode

RUNTIME_SCHEMA = "campaia_runtime"
RUNTIME_TABLES = frozenset(
    {
        "brand_profiles",
        "connections",
        "credential_vault",
        "campaigns",
        "approvals",
        "audit_events",
        "organizations",
        "idempotency",
        "sessions",
        "step_up_states",
        "oauth_pending_states",
        "tenant_autonomy",
        "tenant_autonomy_updated_at",
        "asaas_webhook_seen_events",
    }
)
_TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"


def _validated_table(name: str) -> str:
    if name not in RUNTIME_TABLES or _TABLE_NAME.fullmatch(name) is None:
        raise ValueError(f"PostgreSQL runtime table not allowed: {name!r}")
    return name


class PostgresRecordTable:
    """PostgreSQL implementation of the RecordTable contract."""

    def __init__(self, database: "PostgresDatabase", name: str) -> None:
        self._database = database
        self._name = _validated_table(name)
        if not self._database.table_exists(self._name):
            raise RuntimeError(
                f"PostgreSQL runtime migration missing table "
                f"{RUNTIME_SCHEMA}.{self._name}. Run migrations before startup."
            )

    @property
    def qualified_name(self) -> str:
        return f'{RUNTIME_SCHEMA}."{self._name}"'

    def transaction(self):
        return self._database.transaction()

    def lock_key(self, key: str) -> None:
        self._database.lock_key(f"{self._name}:{key}")

    def put(self, id_: str, tenant_id: str, obj: Any) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for persisted runtime rows")
        payload = Jsonb(encode(obj))
        with self._database.connection() as conn:
            updated = conn.execute(
                f"UPDATE {self.qualified_name} SET data = %s "
                "WHERE id = %s AND tenant_id = %s",
                (payload, id_, tenant_id),
            )
            if updated.rowcount:
                return
            inserted = conn.execute(
                f"INSERT INTO {self.qualified_name} (id, tenant_id, data) "
                "VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (id_, tenant_id, payload),
            )
            if inserted.rowcount:
                return
            updated = conn.execute(
                f"UPDATE {self.qualified_name} SET data = %s "
                "WHERE id = %s AND tenant_id = %s",
                (payload, id_, tenant_id),
            )
            if updated.rowcount == 0:
                from campaia_core.errors import TenantIsolationViolation

                raise TenantIsolationViolation(
                    "Registro persistido pertence a outro tenant."
                )

    def delete(self, id_: str) -> None:
        with self._database.connection() as conn:
            conn.execute(f"DELETE FROM {self.qualified_name} WHERE id = %s", (id_,))

    def get(self, id_: str) -> Any | None:
        with self._database.connection() as conn:
            row = conn.execute(
                f"SELECT data FROM {self.qualified_name} WHERE id = %s", (id_,)
            ).fetchone()
        if row is None:
            return None
        return decode(row[0])

    def get_for_tenant(self, id_: str, tenant_id: str) -> Any | None:
        with self._database.connection() as conn:
            row = conn.execute(
                f"SELECT data FROM {self.qualified_name} "
                "WHERE id = %s AND tenant_id = %s",
                (id_, tenant_id),
            ).fetchone()
        if row is None:
            return None
        return decode(row[0])

    def delete_for_tenant(self, id_: str, tenant_id: str) -> bool:
        with self._database.connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.qualified_name} "
                "WHERE id = %s AND tenant_id = %s",
                (id_, tenant_id),
            )
        return cursor.rowcount > 0

    def rows_for_tenant(self, tenant_id: str) -> list[tuple[str, str, Any]]:
        with self._database.connection() as conn:
            rows = conn.execute(
                f"SELECT id, tenant_id, data FROM {self.qualified_name} "
                "WHERE tenant_id = %s ORDER BY seq",
                (tenant_id,),
            ).fetchall()
        return [(row[0], row[1], decode(row[2])) for row in rows]

    def all_rows(self) -> list[tuple[str, str, Any]]:
        with self._database.connection() as conn:
            rows = conn.execute(
                f"SELECT id, tenant_id, data FROM {self.qualified_name} ORDER BY seq"
            ).fetchall()
        return [(row[0], row[1], decode(row[2])) for row in rows]


class PostgresDatabase:
    """Connection-per-unit-of-work PostgreSQL runtime."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        self._dsn = dsn
        self._local = threading.local()

    @property
    def in_transaction(self) -> bool:
        return getattr(self._local, "transaction_depth", 0) > 0

    @property
    def _current_connection(self):
        return getattr(self._local, "connection", None)

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        current = self._current_connection
        if current is not None:
            yield current
            return
        with psycopg.connect(self._dsn) as conn:
            yield conn

    @contextmanager
    def transaction(self):
        depth = getattr(self._local, "transaction_depth", 0)
        if depth > 0:
            self._local.transaction_depth = depth + 1
            try:
                yield
            finally:
                self._local.transaction_depth = depth
            return

        conn = psycopg.connect(self._dsn)
        self._local.connection = conn
        self._local.transaction_depth = 1
        try:
            yield
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            self._local.transaction_depth = 0
            self._local.connection = None
            conn.close()

    def lock_key(self, key: str) -> None:
        """Serialize a logical key across independent PostgreSQL processes."""
        conn = self._current_connection
        if conn is None:
            raise RuntimeError("lock_key requires an active PostgreSQL transaction")
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (key,),
        )

    def table_exists(self, name: str) -> bool:
        name = _validated_table(name)
        with self.connection() as conn:
            row = conn.execute(
                "SELECT to_regclass(%s)",
                (f"{RUNTIME_SCHEMA}.{name}",),
            ).fetchone()
        return bool(row and row[0] is not None)

    def table(self, name: str) -> PostgresRecordTable:
        return PostgresRecordTable(self, name)

    def ping(self) -> bool:
        try:
            with self.connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def close(self) -> None:
        conn = self._current_connection
        if conn is not None:
            try:
                conn.close()
            finally:
                self._local.connection = None
                self._local.transaction_depth = 0


class PostgresFixedWindowRateLimiter:
    """Fixed-window limiter shared by every replica through PostgreSQL.

    The source key (today the webhook origin address) is SHA-256 hashed before storage so
    the runtime database never persists the raw address merely for rate limiting.
    """

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        scope: str,
        max_requests: int,
        window: timedelta,
    ) -> None:
        if not scope:
            raise ValueError("rate-limit scope is required")
        self._database = database
        self._scope = scope
        self._max_requests = max_requests
        self._window = window

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def allow(self, key: str, *, now: datetime) -> bool:
        if not key:
            return False
        key_hash = self._hash_key(key)
        with self._database.transaction():
            self._database.lock_key(
                f"rate-limit:{self._scope}:{key_hash}"
            )
            with self._database.connection() as conn:
                row = conn.execute(
                    f"SELECT window_started_at, request_count "
                    f"FROM {RUNTIME_SCHEMA}.rate_limit_windows "
                    "WHERE scope = %s AND key_hash = %s",
                    (self._scope, key_hash),
                ).fetchone()

                if row is None or (now - row[0]) >= self._window:
                    count = 1
                    conn.execute(
                        f"INSERT INTO {RUNTIME_SCHEMA}.rate_limit_windows "
                        "(scope, key_hash, window_started_at, request_count, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (scope, key_hash) DO UPDATE SET "
                        "window_started_at = EXCLUDED.window_started_at, "
                        "request_count = EXCLUDED.request_count, "
                        "updated_at = EXCLUDED.updated_at",
                        (self._scope, key_hash, now, count, now),
                    )
                else:
                    count = int(row[1]) + 1
                    conn.execute(
                        f"UPDATE {RUNTIME_SCHEMA}.rate_limit_windows "
                        "SET request_count = %s, updated_at = %s "
                        "WHERE scope = %s AND key_hash = %s",
                        (count, now, self._scope, key_hash),
                    )
        return count <= self._max_requests


class PostgresMigrationRunner:
    """Versioned up/down migration runner used by CI and deployment automation."""

    def __init__(self, dsn: str, migrations_dir: Path | None = None) -> None:
        self._dsn = dsn
        self._dir = migrations_dir or _MIGRATIONS_DIR

    def _ensure_control_table(self, conn: psycopg.Connection) -> None:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {RUNTIME_SCHEMA}")
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {RUNTIME_SCHEMA}.schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )

    def applied_versions(self) -> list[str]:
        with psycopg.connect(self._dsn) as conn:
            self._ensure_control_table(conn)
            rows = conn.execute(
                f"SELECT version FROM {RUNTIME_SCHEMA}.schema_migrations "
                "ORDER BY version"
            ).fetchall()
        return [row[0] for row in rows]

    def _up_files(self) -> list[Path]:
        return sorted(self._dir.glob("*.up.sql"))

    @staticmethod
    def _version(path: Path) -> str:
        return path.name.removesuffix(".up.sql").removesuffix(".down.sql")

    def apply_all(self) -> list[str]:
        applied_now: list[str] = []
        with psycopg.connect(self._dsn) as conn:
            self._ensure_control_table(conn)
            applied = {
                row[0]
                for row in conn.execute(
                    f"SELECT version FROM {RUNTIME_SCHEMA}.schema_migrations"
                ).fetchall()
            }
            for path in self._up_files():
                version = self._version(path)
                if version in applied:
                    continue
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute(
                    f"INSERT INTO {RUNTIME_SCHEMA}.schema_migrations (version) VALUES (%s)",
                    (version,),
                )
                applied_now.append(version)
        return applied_now

    def rollback_latest(self) -> str | None:
        with psycopg.connect(self._dsn) as conn:
            self._ensure_control_table(conn)
            row = conn.execute(
                f"SELECT version FROM {RUNTIME_SCHEMA}.schema_migrations "
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            version = row[0]
            down = self._dir / f"{version}.down.sql"
            if not down.exists():
                raise RuntimeError(f"Missing down migration for {version}")
            conn.execute(down.read_text(encoding="utf-8"))
            conn.execute(
                f"DELETE FROM {RUNTIME_SCHEMA}.schema_migrations WHERE version = %s",
                (version,),
            )
        return version

    def rollback_all(self) -> list[str]:
        rolled: list[str] = []
        while True:
            version = self.rollback_latest()
            if version is None:
                return rolled
            rolled.append(version)


__all__ = [
    "PostgresDatabase",
    "PostgresFixedWindowRateLimiter",
    "PostgresMigrationRunner",
    "PostgresRecordTable",
    "RUNTIME_SCHEMA",
    "RUNTIME_TABLES",
]
