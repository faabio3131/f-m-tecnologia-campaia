"""Motor de assinatura/cobranca propria do CampaIA (V2-16.5).

Resolve o vazio identificado no bloqueio fiscal parcial (ver
docs/evidence/V2_16_5_FISCAL_INTEGRATION_BLOCKER_20260913.md): ate aqui nao existia nenhum
codigo que calculasse quanto um tenant deve pela ASSINATURA do CampaIA (franquia + creditos
extras, D-06) nem que confirmasse que esse valor foi pago. Sem isso o adapter fail-closed em
fiscal_handoff.py nao tinha o que emitir.

Este modulo so calcula e representa o estado da cobranca. Nunca fala com um gateway de
pagamento (isso e payment_gateway.py) nem decide regra fiscal (isso e FM Fiscal, via
fiscal_handoff.py). Um plano e os seus valores nunca sao fixados aqui: vem de
`PlanDefinition`, dado de configuracao — assim um preco novo ou um cliente novo nao exige
alterar codigo.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


def _d(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class SubscriptionStatus(StrEnum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"


class ChargeStatus(StrEnum):
    OPEN = "OPEN"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    """Um plano comercial. Dado de configuracao — nunca um valor fixo em codigo."""

    plan_id: str
    name: str
    monthly_price: Decimal
    included_credits: Decimal
    extra_credit_unit_price: Decimal
    currency: str = "BRL"

    def __post_init__(self) -> None:
        if self.monthly_price <= 0:
            raise ValueError("monthly_price deve ser positivo.")
        if self.included_credits < 0:
            raise ValueError("included_credits nao pode ser negativo.")
        if self.extra_credit_unit_price < 0:
            raise ValueError("extra_credit_unit_price nao pode ser negativo.")
        if self.currency != "BRL":
            raise ValueError("apenas BRL e suportado nesta versao.")


@dataclass(frozen=True, slots=True)
class Subscription:
    tenant_id: str
    customer_ref: str
    plan: PlanDefinition
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class ChargeLineItem:
    description: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class SubscriptionCharge:
    """Cobranca de UM ciclo (competencia). Determinada — nunca recalculada em silencio."""

    billing_id: str
    tenant_id: str
    customer_ref: str
    competence: str
    currency: str
    line_items: tuple[ChargeLineItem, ...]
    status: ChargeStatus = ChargeStatus.OPEN

    @property
    def amount(self) -> Decimal:
        return sum((item.amount for item in self.line_items), start=Decimal("0"))


def compute_cycle_charge(
    subscription: Subscription,
    *,
    competence: str,
    extra_credits_used: Decimal | int | str = 0,
) -> SubscriptionCharge:
    """Calcula a cobranca de UMA competencia. Puro — nao muda estado, nao chama gateway.

    Franquia (D-06): o preco mensal do plano cobre `included_credits`. Uso alem disso e
    cobrado por unidade — nunca de graca, nunca com desconto inventado.
    """
    if subscription.status is SubscriptionStatus.CANCELED:
        raise ValueError("assinatura cancelada nao gera cobranca.")
    if not competence.strip():
        raise ValueError("competence e obrigatoria.")

    extra = _d(extra_credits_used)
    if extra < 0:
        raise ValueError("extra_credits_used nao pode ser negativo.")

    plan = subscription.plan
    billable_extra = max(extra - plan.included_credits, Decimal("0"))

    line_items = [
        ChargeLineItem(f"Assinatura {plan.name} ({competence})", plan.monthly_price)
    ]
    if billable_extra > 0:
        line_items.append(
            ChargeLineItem(
                f"Creditos extras ({billable_extra} un.)",
                (billable_extra * plan.extra_credit_unit_price).quantize(Decimal("0.01")),
            )
        )

    billing_id = f"sub:{subscription.tenant_id}:{competence}"
    return SubscriptionCharge(
        billing_id=billing_id,
        tenant_id=subscription.tenant_id,
        customer_ref=subscription.customer_ref,
        competence=competence,
        currency=plan.currency,
        line_items=tuple(line_items),
    )


__all__ = [
    "ChargeLineItem",
    "ChargeStatus",
    "PlanDefinition",
    "Subscription",
    "SubscriptionCharge",
    "SubscriptionStatus",
    "compute_cycle_charge",
]
