"""Provider Simulator do gateway de pagamento.

Mesmo desenho de simulator.py (Ads Connector Hub): fiel ao contrato de
payment_gateway.py, com falhas programaveis. Um simulador que so devolve sucesso e uma
armadilha — esconde exatamente os caminhos que quebram quando um adaptador real (Asaas)
existir. Trocar este simulador por um adaptador real e configuracao, nao reescrita.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from hashlib import sha256
import json

from .billing_cycles import COMMERCIAL_TIMEZONE
from .connectors import SecretRef
from .infra import IdempotencyStore
from .payment_gateway import (
    ChargeCommand,
    ChargeResult,
    GatewayChargeStatus,
    GatewayMode,
    IdempotencyStoreLike,
    PaymentGatewayError,
    PaymentGatewayErrorCode,
    require_idempotency,
    parse_observed_amount,
    refund_snapshot,
)


@dataclass
class PaymentGatewaySimulator:
    """Adaptador falso, fiel ao contrato. Uso: desenvolvimento, testes e CI.

    `idempotency` e injetavel (achado de fm-security-review, 24/09/2026): por padrao usa
    `IdempotencyStore` em memoria (comportamento identico ao anterior), mas em producao pode
    receber `api.db.PersistentIdempotencyStore` — mesma interface, sem tocar neste arquivo.
    """

    provider: str = "SIMULATOR"
    mode: GatewayMode = GatewayMode.SIMULATOR
    #: Falhas programadas, consumidas em ordem a cada chamada de create_charge.
    scripted_failures: list[PaymentGatewayErrorCode] = field(default_factory=list)
    #: Status que get_charge_status deve devolver, por gateway_charge_id.
    scripted_status: dict[str, GatewayChargeStatus] = field(default_factory=dict)
    idempotency: IdempotencyStoreLike = field(default_factory=IdempotencyStore)
    _counter: int = 0
    minimum_charge_amount: Decimal | None = Decimal('0.01')
    refund_dispatch_enabled: bool = True
    billing_type: str = 'PIX'

    def resolve_secret(self, account_handle: str) -> SecretRef:
        return SecretRef(handle=f"vault://{self.provider}/{account_handle}")

    def create_charge(self, command: ChargeCommand) -> ChargeResult:
        require_idempotency(command)

        def _do_create() -> ChargeResult:
            if self.scripted_failures:
                codigo = self.scripted_failures.pop(0)
                raise PaymentGatewayError(codigo, "Falha programada na cobranca.")

            self._counter += 1
            resultado = ChargeResult(
                gateway_charge_id="sim-charge-" + sha256(
                    json.dumps([command.tenant_id, command.idempotency_key], separators=(",", ":")).encode()).hexdigest()[:24],
                status=GatewayChargeStatus.PENDING,
                provider=self.provider,
                mode=self.mode,
                observed_amount=command.amount,
                observed_due_date=(command.due_at.astimezone(COMMERCIAL_TIMEZONE).date().isoformat()
                                   if command.due_at is not None else None),
            )
            self.scripted_status.setdefault(
                resultado.gateway_charge_id, GatewayChargeStatus.PENDING
            )
            return resultado

        resultado, _replay = self.idempotency.execute(
            command.tenant_id, command.idempotency_key, _do_create
        )
        return resultado

    def dispatch_frozen_charge(self, command: ChargeCommand) -> ChargeResult:
        # Simulated side effect only; its durable result is available for recovery.
        return self.create_charge(command)

    def recover_charge(self, command: ChargeCommand) -> ChargeResult | None:
        require_idempotency(command)
        stored = self.idempotency.get(command.tenant_id, command.idempotency_key)
        return stored.result if stored is not None else None

    def inspect_charge(self, gateway_charge_id: str, command: ChargeCommand) -> ChargeResult:
        require_idempotency(command)
        stored = self.idempotency.get(command.tenant_id, command.idempotency_key)
        if stored is None or stored.result.gateway_charge_id != gateway_charge_id:
            raise PaymentGatewayError(PaymentGatewayErrorCode.VALIDATION_REJECTED, "Cobrança simulada desconhecida.")
        refund = self.idempotency.get(command.tenant_id, 'sim-refund:' + gateway_charge_id)
        if refund is not None:
            completed = self.idempotency.get(command.tenant_id, 'sim-refund-done:' + gateway_charge_id) is not None
            observations = refund.result['before'] + (('DONE' if completed else 'PENDING', refund.result['amount']),)
            full = sum((value for status, value in observations if status == 'DONE'), Decimal('0.00')) == command.amount
            return replace(stored.result, status=(GatewayChargeStatus.FAILED if full else
                GatewayChargeStatus.CONFIRMED if completed else GatewayChargeStatus.PENDING),
                source_status='REFUNDED' if full else 'RECEIVED' if completed else 'REFUND_IN_PROGRESS',
                refund_observations=observations, refunds_present=True, billing_type=self.billing_type)
        return replace(stored.result, status=self.get_charge_status(gateway_charge_id),
                       billing_type=self.billing_type,
                       deleted=self.idempotency.get(command.tenant_id, 'sim-void:' + gateway_charge_id) is not None)

    def void_charge(self, gateway_charge_id: str, command: ChargeCommand) -> ChargeResult:
        current = self.inspect_charge(gateway_charge_id, command)
        if (current.status not in {GatewayChargeStatus.PENDING, GatewayChargeStatus.OVERDUE}
                or current.refunds_present or current.chargeback_status is not None):
            raise PaymentGatewayError(PaymentGatewayErrorCode.VALIDATION_REJECTED, "Cobrança simulada paga não admite retirada.")
        self.idempotency.execute(command.tenant_id, 'sim-void:' + gateway_charge_id, lambda: {'deleted': True})
        return self.inspect_charge(gateway_charge_id, command)

    def refund_charge(self, gateway_charge_id: str, command: ChargeCommand, amount: Decimal) -> ChargeResult:
        current = self.inspect_charge(gateway_charge_id, command)
        existing = self.idempotency.get(command.tenant_id, 'sim-refund:' + gateway_charge_id)
        if existing is not None:
            if existing.result['amount'] != amount:
                raise PaymentGatewayError(PaymentGatewayErrorCode.VALIDATION_REJECTED, "Outro estorno simulado já registrado.")
            return current
        snapshot = refund_snapshot(current, command)
        if (self.refund_dispatch_enabled is not True or self.billing_type not in {'PIX', 'CREDIT_CARD'}
                or not isinstance(amount, Decimal) or parse_observed_amount(amount) != amount or amount <= 0
                or snapshot['state'] != 'READY' or amount > snapshot['remaining']):
            raise PaymentGatewayError(PaymentGatewayErrorCode.VALIDATION_REJECTED, "Estorno simulado indisponível.")
        self.idempotency.execute(command.tenant_id, 'sim-refund:' + gateway_charge_id,
            lambda: {'amount': amount, 'before': current.refund_observations or ()})
        return self.inspect_charge(gateway_charge_id, command)

    def complete_refund(self, gateway_charge_id: str, *, tenant_id: str) -> None:
        """Fixture control: a request alone never becomes a completed refund."""
        if self.idempotency.get(tenant_id, 'sim-refund:' + gateway_charge_id) is None:
            raise PaymentGatewayError(PaymentGatewayErrorCode.UNKNOWN, "Não há pedido de estorno simulado.")
        self.idempotency.execute(tenant_id, 'sim-refund-done:' + gateway_charge_id, lambda: {'done': True})

    def get_charge_status(self, gateway_charge_id: str) -> GatewayChargeStatus:
        return self.scripted_status.get(gateway_charge_id, GatewayChargeStatus.PENDING)

    # ------------------------------------------------------------------ controle de teste

    def confirm(self, gateway_charge_id: str) -> None:
        """Atalho de teste: simula a confirmacao real (PIX pago, boleto compensado)."""
        self.scripted_status[gateway_charge_id] = GatewayChargeStatus.CONFIRMED

    def fail(self, gateway_charge_id: str) -> None:
        """Atalho de teste: simula recusa/expiracao da cobranca."""
        self.scripted_status[gateway_charge_id] = GatewayChargeStatus.FAILED


__all__ = ["PaymentGatewaySimulator"]
