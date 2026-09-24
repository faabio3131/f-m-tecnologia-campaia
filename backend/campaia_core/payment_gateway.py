"""Contrato canonico do gateway de pagamento da cobranca propria do CampaIA.

Mesmo desenho do Ads Connector Hub (connectors.py): idempotencia obrigatoria, credencial
nunca em claro (SecretRef opaco), codigo de erro do provedor traduzido para uma taxonomia
canonica antes de chegar ao dominio. Trocar de gateway — ou suportar mais de um ao mesmo
tempo — e configuracao, nao reescrita: por isso este contrato nao conhece Asaas, Stripe ou
qualquer provedor especifico. O adaptador real escolhido (Asaas, decisao do Diretor,
23/09/2026) implementa este mesmo Protocol em `payment_simulator.py` (uso: dev/testes/CI)
e, quando houver conta e credencial reais, em um adaptador dedicado.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from .connectors import SecretRef
from .errors import CampaiaError


class PaymentGatewayErrorCode(StrEnum):
    AUTH_EXPIRED = "AUTH_EXPIRED"
    VALIDATION_REJECTED = "VALIDATION_REJECTED"
    DECLINED = "DECLINED"
    RATE_LIMITED = "RATE_LIMITED"
    TRANSIENT = "TRANSIENT"
    UNKNOWN = "UNKNOWN"


#: Erros que NAO devem ser repetidos automaticamente — mesma logica de connectors.py.
NON_RETRYABLE: frozenset[PaymentGatewayErrorCode] = frozenset(
    {
        PaymentGatewayErrorCode.AUTH_EXPIRED,
        PaymentGatewayErrorCode.VALIDATION_REJECTED,
        PaymentGatewayErrorCode.DECLINED,
    }
)


class PaymentGatewayError(CampaiaError):
    def __init__(
        self, gateway_code: PaymentGatewayErrorCode, message: str, **details: object
    ) -> None:
        super().__init__(message, **details)
        self.code = gateway_code.value
        self.gateway_code = gateway_code

    @property
    def retryable(self) -> bool:
        return self.gateway_code not in NON_RETRYABLE


class GatewayChargeStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class GatewayMode(StrEnum):
    """Estado real da conta — mesma disciplina de ConnectionMode (connectors.py):
    a interface mostra isto ao usuario, sem maquiagem."""

    SIMULATOR = "SIMULATOR"
    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"


@dataclass(frozen=True, slots=True)
class ChargeCommand:
    tenant_id: str
    billing_id: str
    customer_ref: str
    amount: Decimal
    currency: str
    competence: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ChargeResult:
    gateway_charge_id: str
    status: GatewayChargeStatus
    provider: str
    mode: GatewayMode


def require_idempotency(command: ChargeCommand) -> None:
    """Guarda comum a todo adaptador. Chamada antes de qualquer efeito externo."""
    if not command.tenant_id:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.VALIDATION_REJECTED, "Cobranca sem tenant_id."
        )
    if not command.idempotency_key:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.VALIDATION_REJECTED, "Cobranca sem idempotency_key."
        )
    if command.amount <= 0:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.VALIDATION_REJECTED, "Cobranca deve ser positiva."
        )
    if command.currency != "BRL":
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.VALIDATION_REJECTED, "apenas BRL e suportado."
        )


class PaymentGatewayConnector(Protocol):
    provider: str
    mode: GatewayMode

    def resolve_secret(self, account_handle: str) -> SecretRef: ...
    def create_charge(self, command: ChargeCommand) -> ChargeResult: ...
    def get_charge_status(self, gateway_charge_id: str) -> GatewayChargeStatus: ...


__all__ = [
    "ChargeCommand",
    "ChargeResult",
    "GatewayChargeStatus",
    "GatewayMode",
    "NON_RETRYABLE",
    "PaymentGatewayConnector",
    "PaymentGatewayError",
    "PaymentGatewayErrorCode",
    "require_idempotency",
]
