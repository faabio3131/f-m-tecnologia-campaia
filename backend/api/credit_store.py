"""Durable internal credit journal using the existing F3 transaction boundary.

Not an HTTP mutation surface. Callers must enforce subscription/payment authority,
RBAC + step-up for consent, output validity, and operation/delivery identity. Provider
execution must be OUTSIDE these short transactions, after reservation commits. A crash
leaves the reservation pending; reconcile it rather than starting another provider call.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from campaia_core.credit_ledger import CreditEntry, UsageJournal


@dataclass(frozen=True)
class CreditDecision:
    entry: CreditEntry
    replayed: bool


class PersistentCreditLedger:
    def __init__(self, table) -> None:
        self._table = table

    @staticmethod
    def _key(tenant_id: str, entry_id: str) -> str:
        return hashlib.sha256(f'{tenant_id}\x1f{entry_id}'.encode()).hexdigest()

    def _journal(self, tenant_id: str) -> UsageJournal:
        return UsageJournal(tenant_id, tuple(row[2] for row in
                            self._table.rows_for_tenant(tenant_id)))

    def decide(self, tenant_id: str, command: str, **arguments) -> CreditDecision:
        if command not in {'open_cycle', 'consent', 'reserve', 'finish'}:
            raise ValueError('Unsupported credit journal command')
        with self._table.transaction():
            # All cycles share a lock: an operation/delivery cannot be charged twice
            # by different workers, even across the monthly boundary.
            self._table.lock_key(f'credit-tenant:{tenant_id}')
            journal = self._journal(tenant_id)
            entry = getattr(journal, command)(**arguments)
            key = self._key(tenant_id, entry.entry_id)
            replayed = self._table.get_for_tenant(key, tenant_id) is not None
            if not replayed:
                self._table.put(key, tenant_id, entry)
            return CreditDecision(entry, replayed)

    def balance(self, tenant_id: str, cycle_id: str):
        return self._journal(tenant_id).balance(cycle_id)

    def entries(self, tenant_id: str) -> tuple[CreditEntry, ...]:
        return self._journal(tenant_id).entries
