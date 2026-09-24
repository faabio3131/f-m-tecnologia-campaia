"""Fecha o ciclo aberto pelo bloqueio fiscal V2-16.5.

Encadeia: cobranca calculada (subscription.py) -> gateway de pagamento
(payment_gateway.py) -> fato liquidado -> handoff fiscal (fiscal_handoff.py).

Fail-closed por desenho: `try_settle` so devolve um `SettledOwnBillingFact` quando o
gateway confirma o pagamento (`GatewayChargeStatus.CONFIRMED`). Uma cobranca pendente ou
recusada nunca vira fato liquidado — nunca inventa que foi pago (ver
docs/evidence/V2_16_5_FISCAL_INTEGRATION_BLOCKER_20260913.md).
"""

from __future__ import annotations

from datetime import datetime

from .fiscal_handoff import CampaiaBillingKind, SettledOwnBillingFact
from .payment_gateway import (
    ChargeCommand,
    ChargeResult,
    GatewayChargeStatus,
    PaymentGatewayConnector,
)
from .subscription import SubscriptionCharge


def charge_subscription(
    charge: SubscriptionCharge, gateway: PaymentGatewayConnector
) -> ChargeResult:
    """Envia a cobranca calculada ao gateway. Idempotente pelo `billing_id` do ciclo —
    recalcular ou reenviar o mesmo ciclo nunca cria uma segunda cobranca no gateway."""
    command = ChargeCommand(
        tenant_id=charge.tenant_id,
        billing_id=charge.billing_id,
        customer_ref=charge.customer_ref,
        amount=charge.amount,
        currency=charge.currency,
        competence=charge.competence,
        idempotency_key=f"campaia:subscription:{charge.billing_id}",
    )
    return gateway.create_charge(command)


def try_settle(
    charge: SubscriptionCharge,
    charge_result: ChargeResult,
    gateway: PaymentGatewayConnector,
    *,
    settled_at: datetime,
) -> SettledOwnBillingFact | None:
    """Consulta o gateway pelo status real da cobranca.

    Devolve `None` enquanto PENDING ou quando FAILED — nada e enviado ao fiscal ate a
    confirmacao real do pagamento. Devolve o fato liquidado apenas quando CONFIRMED.
    """
    status = gateway.get_charge_status(charge_result.gateway_charge_id)
    if status is not GatewayChargeStatus.CONFIRMED:
        return None

    if settled_at.tzinfo is None:
        raise ValueError("settled_at deve ser timezone-aware.")

    return SettledOwnBillingFact(
        billing_id=charge.billing_id,
        tenant_id=charge.tenant_id,
        customer_ref=charge.customer_ref,
        kind=CampaiaBillingKind.SAAS,
        amount=charge.amount,
        currency=charge.currency,
        competence=charge.competence,
        settled_at=settled_at,
    )


__all__ = ["charge_subscription", "try_settle"]
