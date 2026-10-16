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
from decimal import Decimal, InvalidOperation
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, Protocol

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
    OVERDUE = "OVERDUE"
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
    #: CPF ou CNPJ do cliente cobrado. Obrigatorio no contrato (nao especifico do Asaas):
    #: qualquer emissao fiscal brasileira real exige identificar o contribuinte, e o
    #: adaptador de gateway nao inventa nem aproxima este dado.
    customer_document: str
    amount: Decimal
    currency: str
    competence: str
    idempotency_key: str
    due_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ChargeResult:
    gateway_charge_id: str
    status: GatewayChargeStatus
    provider: str
    mode: GatewayMode
    invoice_url: str | None = None
    observed_amount: Decimal | None = None
    observed_due_date: str | None = None
    source_status: str | None = None
    deleted: bool | None = None
    refund_observations: tuple[tuple[str, Decimal | None], ...] | None = None
    refunds_present: bool = False
    billing_type: str | None = None
    chargeback_status: str | None = None


def parse_observed_amount(value) -> Decimal | None:
    """Unrounded gross currency observation; absent/invalid never becomes zero."""
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        if amount.is_finite() and amount >= 0 and amount == amount.quantize(Decimal('0.01')):
            return amount
    except (InvalidOperation, ValueError, TypeError):
        pass
    return None


def parse_refund_observations(value) -> tuple[tuple[str, Decimal | None], ...] | None:
    """Only status/value, preserving multiplicity and unknown enums; no raw payer data."""
    if not isinstance(value, list) or len(value) > 1000:
        return None
    observations = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get('status'), str) or not item['status'].strip():
            return None
        amount = parse_observed_amount(item.get('value'))
        observations.append((item['status'], amount if amount is not None and amount > 0 else None))
    return tuple(observations)


def parse_chargeback_status(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict) and isinstance(value.get('status'), str) and value['status'].strip():
        return value['status']
    return 'UNKNOWN'


def refund_snapshot(result: ChargeResult, command: ChargeCommand) -> dict:
    """Provider evidence only; never count pending/cancelled as returned money."""
    review = {'state': 'REVIEW_REQUIRED', 'completed': None, 'remaining': None}
    if result.observed_amount != command.amount or result.chargeback_status is not None:
        return review
    entries = result.refund_observations
    if entries is None:
        if result.refunds_present:
            return review
        entries = ()
    if len(entries) > 1000:
        return review
    for status, value in entries:
        if (status not in {'DONE', 'PENDING', 'CANCELLED'} or not isinstance(value, Decimal)
                or not value.is_finite() or value <= 0 or parse_observed_amount(value) != value):
            return review
    completed = sum((value for status, value in entries if status == 'DONE'), Decimal('0.00'))
    pending = sum((value for status, value in entries if status == 'PENDING'), Decimal('0.00'))
    if completed + pending > command.amount:
        return review
    remaining = command.amount - completed
    if remaining == 0:
        state = 'FULL_DONE'
    elif pending:
        state = 'PROVIDER_PENDING'
    elif result.status is GatewayChargeStatus.CONFIRMED:
        state = 'READY'
    else:
        state = 'REVIEW_REQUIRED'
    return {'state': state, 'completed': completed, 'remaining': remaining}


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
    if not command.customer_document:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.VALIDATION_REJECTED, "Cobranca sem customer_document."
        )
    if command.due_at is not None and (command.due_at.tzinfo is None or command.due_at.utcoffset() is None):
        raise PaymentGatewayError(PaymentGatewayErrorCode.VALIDATION_REJECTED, "Vencimento exige fuso horário.")
    if command.amount <= 0:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.VALIDATION_REJECTED, "Cobranca deve ser positiva."
        )
    if command.currency != "BRL":
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.VALIDATION_REJECTED, "apenas BRL e suportado."
        )


class IdempotencyStoreLike(Protocol):
    """Mesma forma de `campaia_core.infra.IdempotencyStore` e de
    `api.db.PersistentIdempotencyStore` — os dois ja implementam este contrato sem saber
    que um gateway de pagamento existe. Achado de fm-security-review (24/09/2026): manter
    idempotencia so em memoria dentro do gateway perde a garantia contra cobranca duplicada
    se o processo reiniciar entre criar a cobranca e confirma-la. Injetar este objeto em vez
    de um dict privado permite trocar por uma implementacao persistida (a que ja existe em
    `api/db.py`) sem tocar em `payment_simulator.py` nem em `asaas_gateway.py`."""

    def execute(
        self, tenant_id: str, idempotency_key: str, operation: Callable[[], Any]
    ) -> tuple[Any, bool]: ...


class PaymentGatewayConnector(Protocol):
    provider: str
    mode: GatewayMode

    def resolve_secret(self, account_handle: str) -> SecretRef: ...
    def create_charge(self, command: ChargeCommand) -> ChargeResult: ...
    def dispatch_frozen_charge(self, command: ChargeCommand) -> ChargeResult: ...
    def recover_charge(self, command: ChargeCommand) -> ChargeResult | None: ...
    def inspect_charge(self, gateway_charge_id: str, command: ChargeCommand) -> ChargeResult: ...
    def void_charge(self, gateway_charge_id: str, command: ChargeCommand) -> ChargeResult: ...
    def refund_charge(self, gateway_charge_id: str, command: ChargeCommand, amount: Decimal) -> ChargeResult: ...
    def get_charge_status(self, gateway_charge_id: str) -> GatewayChargeStatus: ...


__all__ = [
    "parse_observed_amount",
    "parse_refund_observations",
    "refund_snapshot",
    "parse_chargeback_status",
    "ChargeCommand",
    "ChargeResult",
    "GatewayChargeStatus",
    "GatewayMode",
    "IdempotencyStoreLike",
    "NON_RETRYABLE",
    "PaymentGatewayConnector",
    "PaymentGatewayError",
    "PaymentGatewayErrorCode",
    "require_idempotency",
]
