"""F3 shared security state backed by the runtime RecordTable interface."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class PersistentStepUpStore:
    def __init__(self, table) -> None:
        self._table = table

    @staticmethod
    def _key(tenant_id: str, user_id: str, session_key: str) -> str:
        return f"{tenant_id}\x1f{user_id}\x1f{session_key}"

    def put(
        self, tenant_id: str, user_id: str, session_key: str, *, at: datetime
    ) -> None:
        self._table.put(
            self._key(tenant_id, user_id, session_key),
            tenant_id,
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_key": session_key,
                "verified_at": at,
            },
        )

    def get(self, tenant_id: str, user_id: str, session_key: str) -> datetime | None:
        row = self._table.get(self._key(tenant_id, user_id, session_key))
        return None if row is None else row["verified_at"]

    def invalidate_session(self, session_key: str) -> None:
        # Session switching deliberately invalidates elevations for every tenant binding
        # captured by this opaque session. The backing store is authoritative, never a
        # process-local dict.
        with self._table.transaction():
            for row_id, _tenant_id, row in self._table.all_rows():
                if row.get("session_key") == session_key:
                    self._table.delete(row_id)


class PersistentOAuthStateStore:
    def __init__(self, table) -> None:
        self._table = table

    def put(self, state_token: str, tenant_id: str, pending: Any) -> None:
        self._table.put(state_token, tenant_id, pending)

    def redeem(
        self,
        state_token: str,
        *,
        tenant_id: str,
        now: datetime,
        ttl: timedelta,
    ):
        # Atomic single-use redemption. The record is deleted even when tenant/TTL
        # validation fails, preserving the pre-existing fail-closed semantics.
        with self._table.transaction():
            pending = self._table.get(state_token)
            if pending is None:
                return None
            self._table.delete(state_token)
            if pending.tenant_id != tenant_id:
                return None
            if (now - pending.created_at) > ttl:
                return None
            return pending
