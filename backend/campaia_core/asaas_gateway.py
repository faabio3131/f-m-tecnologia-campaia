"""Adaptador real do gateway Asaas (decisao do Diretor, 23/09/2026).

Implementa `PaymentGatewayConnector` (`payment_gateway.py`). Nenhum dado de conta, ambiente
ou cliente fica fixo em codigo — tudo vem de `AsaasConfig.from_env()`. Trocar de conta, de
ambiente (sandbox/producao) ou atender um tenant novo nunca exige alterar este arquivo,
apenas variaveis de ambiente. Foi o pedido explicito do Diretor ao escolher o Asaas: uma
dependencia externa nao deve exigir mexer em codigo a cada cliente novo.

URLs base e formato de chamada verificados em 23/09/2026 contra a documentacao oficial
(docs.asaas.com) e o SDK open-source `asaas` (github.com/eduardobernardo/asaas) — nao
assumidos de memoria, mesma disciplina ja aplicada a versoes de pacote neste projeto
(ver EVIDENCIA_C1_CI_HTTPX_FIX_20260905.md).

LIMITACAO DE AMBIENTE, documentada e nao escondida (Ordem Mestra): este adaptador nao foi
verificado contra uma conta real do Asaas — nenhuma credencial existe ainda nesta sandbox.
Os testes (`test_asaas_gateway.py`) validam a forma da requisicao e o parsing da resposta
contra um transporte HTTP falso (`httpx.MockTransport`), nunca uma chamada de rede real.
Verificacao contra uma conta sandbox real fica pendente de o Diretor gerar a chave de API
(ver docs/evidence/EVIDENCIA_B11_ASAAS_GATEWAY_20260923.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import httpx

from .connectors import SecretRef
from .payment_gateway import (
    ChargeCommand,
    ChargeResult,
    GatewayChargeStatus,
    GatewayMode,
    PaymentGatewayError,
    PaymentGatewayErrorCode,
    require_idempotency,
)

#: Verificado contra o SDK open-source `asaas` (github.com/eduardobernardo/asaas), 23/09/2026.
#: Contas, dados e chaves de API NAO sao compartilhados entre os dois ambientes.
PRODUCTION_BASE_URL = "https://api.asaas.com/v3"
SANDBOX_BASE_URL = "https://sandbox.asaas.com/api/v3"

#: Status confirmados na documentacao oficial (docs.asaas.com/docs/status-possiveis),
#: 23/09/2026. Qualquer status nao listado aqui cai em PENDING pelo `.get(..., PENDING)`
#: abaixo — fail-closed por desenho: nunca inventa CONFIRMED para um status desconhecido.
_CONFIRMED_ASAAS_STATUSES: frozenset[str] = frozenset(
    {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH", "DUNNING_RECEIVED"}
)
#: Unico status que representa reversao definitiva do valor — nunca deve virar fato fiscal.
_FAILED_ASAAS_STATUSES: frozenset[str] = frozenset({"REFUNDED"})


def _map_status(asaas_status: str) -> GatewayChargeStatus:
    if asaas_status in _CONFIRMED_ASAAS_STATUSES:
        return GatewayChargeStatus.CONFIRMED
    if asaas_status in _FAILED_ASAAS_STATUSES:
        return GatewayChargeStatus.FAILED
    return GatewayChargeStatus.PENDING


def _raise_for_response(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.AUTH_EXPIRED,
            "Credencial do Asaas invalida, expirada ou sem permissao.",
            status_code=response.status_code,
        )
    if response.status_code == 400:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.VALIDATION_REJECTED,
            "Asaas rejeitou a requisicao.",
            status_code=response.status_code,
            body=response.text,
        )
    if response.status_code == 429:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.RATE_LIMITED, "Asaas limitou a taxa de chamadas."
        )
    if response.status_code >= 500:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.TRANSIENT, "Erro transiente no Asaas."
        )
    if response.status_code >= 400:
        raise PaymentGatewayError(
            PaymentGatewayErrorCode.UNKNOWN,
            "Erro nao mapeado do Asaas.",
            status_code=response.status_code,
            body=response.text,
        )


@dataclass(frozen=True, slots=True)
class AsaasConfig:
    """Configuracao lida do ambiente — nunca fixa em codigo.

    `due_in_days` e um termo de cobranca especifico do Asaas (a API exige `dueDate`); fica
    aqui, nao no contrato generico de `payment_gateway.py`, porque outro gateway pode nem ter
    esse conceito. E um valor de configuracao (placeholder ate o Diretor definir um prazo de
    pagamento formal), nunca um numero fixo dentro de `create_charge`.
    """

    api_key: str | None
    mode: GatewayMode
    account_handle: str
    due_in_days: int

    @classmethod
    def from_env(cls, prefix: str = "ASAAS_") -> "AsaasConfig":
        mode_raw = os.environ.get(f"{prefix}MODE", "SANDBOX").upper()
        try:
            mode = GatewayMode[mode_raw]
        except KeyError as exc:
            raise PaymentGatewayError(
                PaymentGatewayErrorCode.VALIDATION_REJECTED,
                f"{prefix}MODE invalido: {mode_raw!r} (use SANDBOX ou PRODUCTION).",
            ) from exc
        if mode is GatewayMode.SIMULATOR:
            raise PaymentGatewayError(
                PaymentGatewayErrorCode.VALIDATION_REJECTED,
                "AsaasGateway nao roda em modo SIMULATOR — use PaymentGatewaySimulator.",
            )
        return cls(
            api_key=os.environ.get(f"{prefix}API_KEY"),
            mode=mode,
            account_handle=os.environ.get(f"{prefix}ACCOUNT_HANDLE", "default"),
            due_in_days=int(os.environ.get(f"{prefix}DUE_IN_DAYS", "3")),
        )


@dataclass
class AsaasGateway:
    """Adaptador real. `transport` so existe para injetar `httpx.MockTransport` em teste —
    nunca usado para apontar para produção a partir de sandbox nem o contrário."""

    config: AsaasConfig
    provider: str = "ASAAS"
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    _client: httpx.Client = field(init=False, repr=False)
    _created: dict[tuple[str, str], ChargeResult] = field(default_factory=dict, repr=False)

    @property
    def mode(self) -> GatewayMode:
        return self.config.mode

    def __post_init__(self) -> None:
        if not self.config.api_key:
            raise PaymentGatewayError(
                PaymentGatewayErrorCode.AUTH_EXPIRED,
                "ASAAS_API_KEY nao configurada — nenhuma chamada real e possivel.",
            )
        base_url = (
            PRODUCTION_BASE_URL if self.config.mode is GatewayMode.PRODUCTION else SANDBOX_BASE_URL
        )
        self._client = httpx.Client(
            base_url=base_url,
            headers={"access_token": self.config.api_key, "User-Agent": "CampaIA/1.0"},
            timeout=10.0,
            transport=self.transport,
        )

    def resolve_secret(self, account_handle: str) -> SecretRef:
        return SecretRef(handle=f"vault://asaas/{account_handle}")

    # ------------------------------------------------------------------ operacoes

    def create_charge(self, command: ChargeCommand) -> ChargeResult:
        require_idempotency(command)

        key = (command.tenant_id, command.idempotency_key)
        if key in self._created:
            return self._created[key]  # retry nao duplica cobranca real no Asaas

        customer_id = self._ensure_customer(command.customer_ref, command.customer_document)
        due_date = date.today() + timedelta(days=self.config.due_in_days)
        response = self._client.post(
            "/payments",
            json={
                "customer": customer_id,
                "billingType": "UNDEFINED",
                "value": float(command.amount.quantize(Decimal("0.01"))),
                "dueDate": due_date.isoformat(),
                "description": f"CampaIA — competencia {command.competence}",
                "externalReference": command.idempotency_key,
            },
        )
        _raise_for_response(response)
        body = response.json()

        result = ChargeResult(
            gateway_charge_id=body["id"],
            status=_map_status(body["status"]),
            provider=self.provider,
            mode=self.mode,
        )
        self._created[key] = result
        return result

    def get_charge_status(self, gateway_charge_id: str) -> GatewayChargeStatus:
        response = self._client.get(f"/payments/{gateway_charge_id}")
        _raise_for_response(response)
        return _map_status(response.json()["status"])

    # ------------------------------------------------------------------ apoio

    def _ensure_customer(self, customer_ref: str, customer_document: str) -> str:
        """Busca o cliente pelo `externalReference` antes de criar — nunca duplica cliente
        no Asaas a cada cobranca do mesmo tenant. `cpfCnpj` e exigido pela API do Asaas
        (confirmado em docs.asaas.com/reference/create-new-customer, 24/09/2026) — sem ele
        a criacao de cliente e recusada com VALIDATION_REJECTED."""
        response = self._client.get("/customers", params={"externalReference": customer_ref})
        _raise_for_response(response)
        existing = response.json().get("data", [])
        if existing:
            return existing[0]["id"]

        response = self._client.post(
            "/customers",
            json={
                "name": customer_ref,
                "cpfCnpj": customer_document,
                "externalReference": customer_ref,
            },
        )
        _raise_for_response(response)
        return response.json()["id"]


__all__ = [
    "AsaasConfig",
    "AsaasGateway",
    "PRODUCTION_BASE_URL",
    "SANDBOX_BASE_URL",
]
