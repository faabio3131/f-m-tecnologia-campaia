"""Commercial delivery credits, independent of provider costs and billing emission.

Pure append-only decisions. A trusted application service supplies authenticated tenant,
paid/trial cycle snapshots and consent; the persistent adapter serializes each decision.
No clock, provider call, entitlement grant or browser-reported usage is trusted here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4


class CreditLedgerError(ValueError):
    """Conflicting operation, missing authority snapshot or invalid transition."""


class CreditLimitExceeded(CreditLedgerError):
    """The complete operation cannot fit within included credits and consent."""


def _id(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise CreditLedgerError("Nonempty reference of at most 256 characters required")


def _instant(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CreditLedgerError("Timezone-aware instant required")


def _money(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0 or value > Decimal('1000000000000'):
        raise CreditLedgerError("Finite nonnegative Decimal amount required")
    if value != value.quantize(Decimal('0.01')):
        raise CreditLedgerError("Money must have cent precision")


_FREE_ACTIONS = frozenset({
    'login', 'signup', 'manual_edit', 'metrics', 'history', 'connect', 'approve',
    'publish', 'pause', 'resume', 'export', 'kill_switch', 'policy', 'reconcile',
    'retry', 'fallback',
})


def _validate_weights(action_weights: tuple[tuple[str, int], ...]) -> None:
    if not isinstance(action_weights, tuple) or not action_weights:
        raise CreditLedgerError("Frozen action weight snapshot required")
    seen = set()
    for pair in action_weights:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise CreditLedgerError("Frozen action weight pairs required")
        action, weight = pair
        _id(action)
        if action in _FREE_ACTIONS or action in seen or type(weight) is not int or weight <= 0:
            raise CreditLedgerError("Duplicate action or invalid weight")
        seen.add(action)


@dataclass(frozen=True)
class CreditCycle:
    tenant_id: str
    cycle_id: str
    starts_at: datetime
    ends_at: datetime
    policy_version: str
    included_credits: int
    extra_credit_price: Decimal
    action_weights: tuple[tuple[str, int], ...]
    trial: bool = False
    included_grace_ends_at: datetime | None = None

    def __post_init__(self) -> None:
        for value in (self.tenant_id, self.cycle_id, self.policy_version):
            _id(value)
        _instant(self.starts_at)
        _instant(self.ends_at)
        if self.starts_at >= self.ends_at:
            raise CreditLedgerError("Empty or reversed cycle")
        if type(self.included_credits) is not int or self.included_credits < 0:
            raise CreditLedgerError("Invalid included credits")
        _money(self.extra_credit_price)
        if self.extra_credit_price == 0:
            raise CreditLedgerError("Extra unit price must be positive")
        _validate_weights(self.action_weights)
        if self.included_grace_ends_at is not None:
            _instant(self.included_grace_ends_at)
            if self.trial or self.included_grace_ends_at < self.ends_at:
                raise CreditLedgerError("Invalid included-credit grace window")



@dataclass(frozen=True)
class CreditEntry:
    entry_id: str
    tenant_id: str
    cycle_id: str
    kind: Literal['OPEN', 'CONSENT', 'RESERVE', 'SETTLE', 'RELEASE', 'REVERSE']
    at: datetime
    operation_id: str = ''
    action: str = ''
    credits: int = 0
    policy_version: str = ''
    reference: str = ''
    actor: str = ''
    cap: Decimal = Decimal('0.00')
    cycle: CreditCycle | None = None


@dataclass(frozen=True)
class CreditBalance:
    included_credits: int
    reserved_credits: int
    consumed_credits: int
    included_available: int
    extra_consumed: int
    extra_committed_amount: Decimal
    extra_consumed_amount: Decimal
    extra_cap: Decimal


class UsageJournal:
    """Replay a tenant journal and decide the next immutable entry.

    Every logical operation ID is tenant-wide (including across cycle boundaries).
    RESERVED also means externally uncertain: no automatic expiration or second call.
    Delivery references must identify atomic billable outputs, never a bundle plus children.
    """

    def __init__(self, tenant_id: str, entries: tuple[CreditEntry, ...] = ()) -> None:
        _id(tenant_id)
        if any(e.tenant_id != tenant_id for e in entries):
            raise CreditLedgerError('Cross-tenant journal')
        self.tenant_id = tenant_id
        self.entries = entries

    def _entry(self, cycle_id: str, kind: str, at: datetime, **fields) -> CreditEntry:
        _id(cycle_id)
        _instant(at)
        return CreditEntry(uuid4().hex, self.tenant_id, cycle_id, kind, at, **fields)

    def _cycle(self, cycle_id: str) -> CreditCycle:
        for entry in self.entries:
            if entry.kind == 'OPEN' and entry.cycle_id == cycle_id:
                return entry.cycle
        raise CreditLedgerError('Unknown cycle')

    def open_cycle(self, cycle: CreditCycle, at: datetime) -> CreditEntry:
        if cycle.tenant_id != self.tenant_id:
            raise CreditLedgerError('Cross-tenant cycle')
        for entry in self.entries:
            if entry.kind == 'OPEN' and entry.cycle_id == cycle.cycle_id:
                if entry.cycle != cycle:
                    raise CreditLedgerError('Cycle terms are immutable')
                return entry
        return self._entry(cycle.cycle_id, 'OPEN', at, cycle=cycle,
                           policy_version=cycle.policy_version)

    def consent(self, cycle_id: str, cap: Decimal, actor: str,
                reference: str, at: datetime) -> CreditEntry:
        cycle = self._cycle(cycle_id)
        _money(cap)
        _id(actor)
        _id(reference)
        _instant(at)
        if at >= cycle.ends_at:
            raise CreditLedgerError('Consent cannot be added after the cycle ends')
        if cycle.trial and cap != 0:
            raise CreditLedgerError('Trial cannot authorize extras')
        for entry in self.entries:
            if entry.kind == 'CONSENT' and entry.reference == reference:
                if (entry.cycle_id, entry.cap, entry.actor) != (cycle_id, cap, actor):
                    raise CreditLedgerError('Consent replay conflict')
                return entry
        return self._entry(cycle_id, 'CONSENT', at, cap=cap, actor=actor,
                           reference=reference, policy_version=cycle.policy_version)

    def _operations(self, cycle_id: str) -> dict[str, CreditEntry]:
        return {e.operation_id: e for e in self.entries
                if e.cycle_id == cycle_id and e.operation_id}

    def balance(self, cycle_id: str) -> CreditBalance:
        cycle = self._cycle(cycle_id)
        operations = self._operations(cycle_id).values()
        reserved = sum(e.credits for e in operations if e.kind == 'RESERVE')
        consumed = sum(e.credits for e in operations if e.kind == 'SETTLE')
        cap = Decimal('0.00')
        for entry in self.entries:
            if entry.kind == 'CONSENT' and entry.cycle_id == cycle_id:
                cap = entry.cap
        extra = max(consumed - cycle.included_credits, 0)
        committed = max(consumed + reserved - cycle.included_credits, 0)
        return CreditBalance(cycle.included_credits, reserved, consumed,
                             max(cycle.included_credits - consumed - reserved, 0),
                             extra, committed * cycle.extra_credit_price,
                             extra * cycle.extra_credit_price, cap)

    def reserve(self, cycle_id: str, operation_id: str, action: str,
                at: datetime) -> CreditEntry:
        _id(operation_id)
        _instant(at)
        cycle = self._cycle(cycle_id)
        credits = dict(cycle.action_weights).get(action)
        if credits is None:
            raise CreditLedgerError('Action is not billable under this policy')
        for entry in self.entries:
            if entry.kind == 'RESERVE' and entry.operation_id == operation_id:
                if (entry.cycle_id, entry.action) != (cycle_id, action):
                    raise CreditLedgerError('Operation replay conflict')
                return [e for e in self.entries if e.operation_id == operation_id][-1]
        in_grace = (cycle.included_grace_ends_at is not None
                    and cycle.ends_at <= at < cycle.included_grace_ends_at)
        if not cycle.starts_at <= at < cycle.ends_at and not in_grace:
            raise CreditLedgerError('Cycle is not open for reservations')
        balance = self.balance(cycle_id)
        committed = balance.reserved_credits + balance.consumed_credits + credits
        required = max(committed - cycle.included_credits, 0) * cycle.extra_credit_price
        if (in_grace and committed > cycle.included_credits) or required > balance.extra_cap:
            raise CreditLimitExceeded('Entire operation exceeds available credit consent')
        return self._entry(cycle_id, 'RESERVE', at, operation_id=operation_id,
                           action=action, credits=credits, policy_version=cycle.policy_version)

    def finish(self, operation_id: str, kind: Literal['SETTLE', 'RELEASE', 'REVERSE'],
               reference: str, at: datetime) -> CreditEntry:
        _id(operation_id)
        _id(reference)
        _instant(at)
        matches = [e for e in self.entries if e.operation_id == operation_id]
        if not matches:
            raise CreditLedgerError('Unknown reserved operation')
        previous = matches[-1]
        if previous.kind == kind and previous.reference == reference:
            return previous
        allowed = (previous.kind == 'RESERVE' and kind in ('SETTLE', 'RELEASE')
                   or previous.kind == 'SETTLE' and kind == 'REVERSE')
        if not allowed:
            raise CreditLedgerError('Conflicting or invalid terminal transition')
        if at < previous.at:
            raise CreditLedgerError('Transition predates previous entry')
        if kind == 'SETTLE' and any(e.kind == 'SETTLE' and e.reference == reference
                                    for e in self.entries):
            raise CreditLedgerError('Delivery already charged to another operation')
        return self._entry(previous.cycle_id, kind, at, operation_id=operation_id,
                           action=previous.action, credits=previous.credits,
                           policy_version=previous.policy_version, reference=reference)


@dataclass(frozen=True)
class CreditPolicy:
    """External contract snapshot; no price or quota defaults are invented."""
    version: str
    action_weights: tuple[tuple[str, int], ...]
    trial_credits: int
    trial_max_users: int
    trial_max_active_campaigns: int

    def __post_init__(self) -> None:
        _id(self.version)
        for value in (self.trial_credits, self.trial_max_users, self.trial_max_active_campaigns):
            if type(value) is not int or value < 1:
                raise CreditLedgerError('Trial terms must be explicit positive integers')
        _validate_weights(self.action_weights)



@dataclass(frozen=True)
class ExtraCreditConsent:
    tenant_id: str
    reference: str
    actor: str
    at: datetime
    cap: Decimal
    policy_version: str
    extra_credit_price: Decimal

    def __post_init__(self) -> None:
        for value in (self.tenant_id, self.reference, self.actor, self.policy_version):
            _id(value)
        _instant(self.at)
        _money(self.cap)
        _money(self.extra_credit_price)
        if self.extra_credit_price <= 0:
            raise CreditLedgerError('Positive accepted unit price required')
