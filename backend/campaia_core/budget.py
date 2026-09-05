"""Budget Engine deterministico.

Problema real que este modulo resolve: duas publicacoes concorrentes podem, cada uma
isoladamente, caber no limite - e juntas estourarem. Por isso a verba e RESERVADA antes da
publicacao e so liberada na confirmacao ou na compensacao.

Regra de ouro: o pior defeito possivel do sistema nao pode ser gasto nao autorizado.
Toda aritmetica financeira usa Decimal. Nunca float.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from .errors import BudgetLimitExceeded


def _d(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class BudgetLimits:
    currency: str
    daily_cap: Decimal
    total_amount: Decimal
    #: Variacao percentual maxima permitida em uma unica alteracao de verba.
    max_change_pct: Decimal = Decimal("20")
    #: Se True, atingir o limite PAUSA. Se False, apenas alerta.
    hard_stop: bool = True

    def __post_init__(self) -> None:
        if self.daily_cap <= 0 or self.total_amount <= 0:
            raise ValueError("Limites de orcamento devem ser positivos.")
        if self.daily_cap > self.total_amount:
            raise ValueError("Teto diario nao pode exceder o total.")


@dataclass
class Reservation:
    reservation_id: str
    command_id: str
    amount: Decimal
    active: bool = True


@dataclass
class BudgetEngine:
    """Livro de verba de UMA campanha. Instancia por campanha, nunca compartilhada."""

    tenant_id: str
    campaign_id: str
    limits: BudgetLimits
    spent_total: Decimal = Decimal("0")
    spent_today: Decimal = Decimal("0")
    _reservations: dict[str, Reservation] = field(default_factory=dict)

    # ------------------------------------------------------------------ consultas

    @property
    def reserved(self) -> Decimal:
        return sum(
            (r.amount for r in self._reservations.values() if r.active), start=Decimal("0")
        )

    @property
    def committed_total(self) -> Decimal:
        """Gasto confirmado + reservado. E este numero que o limite protege."""
        return self.spent_total + self.reserved

    @property
    def available_total(self) -> Decimal:
        return self.limits.total_amount - self.committed_total

    @property
    def available_today(self) -> Decimal:
        return self.limits.daily_cap - (self.spent_today + self.reserved)

    # ------------------------------------------------------------------ operacoes

    def reserve(self, amount: Decimal | int | str, *, command_id: str) -> Reservation:
        """Reserva verba antes do efeito externo.

        Idempotente por `command_id`: repetir o mesmo comando devolve a reserva original
        em vez de criar uma segunda. Sem isso, um retry duplicaria o compromisso financeiro.
        """
        amount = _d(amount)
        if amount <= 0:
            raise ValueError("Reserva deve ser positiva.")

        for existing in self._reservations.values():
            if existing.command_id == command_id and existing.active:
                return existing

        if amount > self.available_total:
            raise BudgetLimitExceeded(
                "Reserva excede o orcamento total autorizado.",
                requested=str(amount),
                available=str(self.available_total),
            )
        if amount > self.available_today:
            raise BudgetLimitExceeded(
                "Reserva excede o teto diario autorizado.",
                requested=str(amount),
                available=str(self.available_today),
            )

        reservation = Reservation(
            reservation_id=str(uuid.uuid4()), command_id=command_id, amount=amount
        )
        self._reservations[reservation.reservation_id] = reservation
        return reservation

    def confirm(self, reservation_id: str, actual_spend: Decimal | int | str) -> None:
        """Converte reserva em gasto real, apos confirmacao da plataforma."""
        actual_spend = _d(actual_spend)
        reservation = self._reservations[reservation_id]
        if not reservation.active:
            return  # ja confirmada ou liberada: idempotente
        if actual_spend < 0:
            raise ValueError("Gasto nao pode ser negativo.")
        reservation.active = False
        self.spent_total += actual_spend
        self.spent_today += actual_spend

    def release(self, reservation_id: str) -> None:
        """Libera reserva apos falha ou compensacao da Saga."""
        reservation = self._reservations.get(reservation_id)
        if reservation is not None:
            reservation.active = False

    def validate_change(
        self, new_daily_cap: Decimal | int | str
    ) -> tuple[bool, Decimal, str]:
        """Verifica se a alteracao de teto diario cabe na variacao maxima permitida.

        Retorna (permitido, variacao_pct, motivo). Nunca "ajusta automaticamente" o valor
        para caber: alteracao fora do limite e recusada, nao corrigida em silencio.
        """
        new_daily_cap = _d(new_daily_cap)
        if new_daily_cap <= 0:
            return False, Decimal("0"), "Teto diario deve ser positivo."

        old = self.limits.daily_cap
        change_pct = ((new_daily_cap - old) / old) * Decimal("100")

        if new_daily_cap > self.limits.total_amount:
            return False, change_pct, "Teto diario nao pode exceder o total autorizado."
        if abs(change_pct) > self.limits.max_change_pct:
            return (
                False,
                change_pct,
                f"Variacao de {change_pct:.2f}% excede o maximo de "
                f"{self.limits.max_change_pct}%.",
            )
        return True, change_pct, "Alteracao dentro do limite configurado."

    def should_stop(self) -> bool:
        """True quando o limite foi atingido e a politica manda pausar."""
        atingiu = (
            self.committed_total >= self.limits.total_amount
            or (self.spent_today + self.reserved) >= self.limits.daily_cap
        )
        return atingiu and self.limits.hard_stop
