"""Provider Simulator do gateway de pagamento.

Mesmo desenho de simulator.py (Ads Connector Hub): fiel ao contrato de
payment_gateway.py, com falhas programaveis. Um simulador que so devolve sucesso e uma
armadilha — esconde exatamente os caminhos que quebram quando um adaptador real (Asaas)
existir. Trocar este simulador por um adaptador real e configuracao, nao reescrita.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
                gateway_charge_id=f"sim-charge-{self._counter:04d}",
                status=GatewayChargeStatus.PENDING,
                provider=self.provider,
                mode=self.mode,
            )
            self.scripted_status.setdefault(
                resultado.gateway_charge_id, GatewayChargeStatus.PENDING
            )
            return resultado

        resultado, _replay = self.idempotency.execute(
            command.tenant_id, command.idempotency_key, _do_create
        )
        return resultado

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
