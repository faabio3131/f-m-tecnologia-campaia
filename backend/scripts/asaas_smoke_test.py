"""Verificacao real, unica e manual do adaptador Asaas contra a API de verdade.

NAO roda no CI automatico (push/PR) — so por acionamento manual
(`.github/workflows/asaas-sandbox-smoke.yml`), porque cria um cliente e uma cobranca reais
na conta Sandbox configurada em `ASAAS_API_KEY`.

Nunca imprime a chave. O GitHub Actions mascara automaticamente qualquer secret que apareca
nos logs, mas este script tambem nunca formata `config.api_key` em lugar nenhum, por
disciplina — o mesmo motivo pelo qual `SecretRef` (`connectors.py`) nunca expoe o valor cru.
"""

from __future__ import annotations

import sys
import uuid
from decimal import Decimal

from campaia_core.asaas_gateway import AsaasConfig, AsaasGateway
from campaia_core.payment_gateway import ChargeCommand, GatewayChargeStatus, PaymentGatewayError


def main() -> int:
    config = AsaasConfig.from_env()
    print(f"Modo: {config.mode.value} — chave configurada: {'sim' if config.api_key else 'nao'}")

    try:
        gateway = AsaasGateway(config=config)
    except PaymentGatewayError as exc:
        print(f"FALHOU ao construir o gateway: {exc.gateway_code.value} — {exc.message}")
        return 1
    print(f"Cliente HTTP construido com sucesso para o provider {gateway.provider}.")

    smoke_id = uuid.uuid4().hex[:12]
    command = ChargeCommand(
        tenant_id="smoke-test",
        billing_id=f"smoke:{smoke_id}",
        customer_ref=f"smoke-customer-{smoke_id}",
        amount=Decimal("1.00"),
        currency="BRL",
        competence="SMOKE-TEST",
        idempotency_key=f"campaia:smoke:{smoke_id}",
    )

    try:
        result = gateway.create_charge(command)
    except PaymentGatewayError as exc:
        print(f"FALHOU ao criar cobranca de teste: {exc.gateway_code.value} — {exc.message}")
        return 1

    print(f"Cobranca de teste criada: id={result.gateway_charge_id} status={result.status.value}")

    status = gateway.get_charge_status(result.gateway_charge_id)
    print(f"Status consultado de volta: {status.value}")

    if status not in (GatewayChargeStatus.PENDING, GatewayChargeStatus.CONFIRMED):
        print(f"Status inesperado para uma cobranca recem-criada: {status.value}")
        return 1

    print("OK — adaptador AsaasGateway verificado contra a API real (Sandbox).")
    print(
        f"Cobranca de R$ 1,00 criada em '{command.customer_ref}' — cancele manualmente no "
        "painel do Asaas Sandbox se quiser limpar, nenhum efeito real (ambiente de teste)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
