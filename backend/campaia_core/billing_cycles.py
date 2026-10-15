"""Anniversary billing in the commercial timezone; all stored instants are UTC.

This is the temporal component of the existing subscription authority, not another
scheduler. Payment identity is scoped to product, tenant, lifecycle and period index.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

COMMERCIAL_TIMEZONE = ZoneInfo('America/Sao_Paulo')


def utc_instant(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Instante deve informar fuso horário.')
    return value.astimezone(timezone.utc)


def anniversary(anchor: datetime, index: int) -> datetime:
    """Always derive from the ORIGINAL day, restoring 31 after short months."""
    if type(index) is not int or index < 0:
        raise ValueError('Índice mensal deve ser inteiro não negativo.')
    original = utc_instant(anchor).astimezone(COMMERCIAL_TIMEZONE)
    month_number = original.year * 12 + original.month - 1 + index
    year, month_zero = divmod(month_number, 12)
    month = month_zero + 1
    if not 1 <= year <= 9999:
        raise ValueError('Ciclo fora do calendário suportado.')
    local = original.replace(year=year, month=month,
                             day=min(original.day, monthrange(year, month)[1]))
    return local.astimezone(timezone.utc)


def period_index(anchor: datetime, at: datetime) -> int:
    anchor_utc, at_utc = utc_instant(anchor), utc_instant(at)
    if at_utc < anchor_utc:
        raise ValueError('Instante anterior à ativação paga.')
    start = anchor_utc.astimezone(COMMERCIAL_TIMEZONE)
    local = at_utc.astimezone(COMMERCIAL_TIMEZONE)
    index = (local.year - start.year) * 12 + local.month - start.month
    if anniversary(anchor_utc, index) > at_utc:
        index -= 1
    return index


@dataclass(frozen=True)
class PaidCycleSchedule:
    lifecycle_id: str
    anchor_at: datetime | None = None
    paid_through_index: int = -1
    settled_obligations: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if not self.lifecycle_id or len(self.lifecycle_id) > 128:
            raise ValueError('Identidade de lifecycle obrigatória.')
        if type(self.paid_through_index) is not int or self.paid_through_index < -1:
            raise ValueError('Índice pago inválido.')
        if self.anchor_at is not None:
            object.__setattr__(self, 'anchor_at', utc_instant(self.anchor_at))
        if (self.anchor_at is None) != (self.paid_through_index == -1):
            raise ValueError('Âncora e primeiro pagamento devem existir juntos.')
        ids = [identity for identity, _index in self.settled_obligations]
        if len(ids) != len(set(ids)):
            raise ValueError('Obrigação liquidada duplicada.')

    def obligation_id(self, tenant_id: str, index: int) -> str:
        if not tenant_id or type(index) is not int or index < 0:
            raise ValueError('Tenant e índice obrigatórios.')
        # A tuple encoded as JSON avoids delimiter collisions in arbitrary tenant IDs.
        import hashlib
        import json
        raw = json.dumps(['CampaIA', tenant_id, self.lifecycle_id, 'BASE', index],
                         separators=(',', ':'))
        return 'campaia_' + hashlib.sha256(raw.encode()).hexdigest()

    def bounds(self, index: int) -> tuple[datetime, datetime]:
        if self.anchor_at is None:
            raise ValueError('Primeiro pagamento ainda não confirmado.')
        return anniversary(self.anchor_at, index), anniversary(self.anchor_at, index + 1)

    def current_paid_index(self, at: datetime) -> int | None:
        if self.anchor_at is None or utc_instant(at) < self.anchor_at:
            return None
        current = period_index(self.anchor_at, at)
        return current if current <= self.paid_through_index else None

    def confirm_payment(self, tenant_id: str, billing_id: str, index: int,
                        settled_at: datetime) -> PaidCycleSchedule:
        expected = self.obligation_id(tenant_id, index)
        if billing_id != expected:
            raise ValueError('Pagamento não corresponde à obrigação/ciclo/lifecycle.')
        at = utc_instant(settled_at)
        if any(identity == billing_id for identity, _ in self.settled_obligations):
            return self
        if index != self.paid_through_index + 1:
            raise ValueError('Pagamento fora da sequência; reconciliar obrigações pendentes.')
        anchor = self.anchor_at or at
        return replace(self, anchor_at=anchor, paid_through_index=index,
                       settled_obligations=self.settled_obligations + ((billing_id, index),))
