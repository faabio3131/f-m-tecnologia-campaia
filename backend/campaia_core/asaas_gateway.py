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

Verificado com sucesso contra a API real do Asaas Sandbox em 24/09/2026 (ver
docs/evidence/VERIFICACAO_REAL_ASAAS_SANDBOX_20260924.md) — os testes automatizados
(`test_asaas_gateway.py`) continuam validando forma de requisicao/resposta contra
`httpx.MockTransport`, nunca rede real, mas a verificacao pontual contra a conta real ja
aconteceu e encontrou (e corrigiu) dois defeitos reais nao previstos pelo desenho original.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import httpx

from .billing_cycles import COMMERCIAL_TIMEZONE
from .connectors import SecretRef
from .payment_urls import safe_asaas_invoice_url
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

#: Verificado contra o SDK open-source `asaas` (github.com/eduardobernardo/asaas), 23/09/2026.
#: Contas, dados e chaves de API NAO sao compartilhados entre os dois ambientes.
PRODUCTION_BASE_URL = "https://api.asaas.com/v3"
SANDBOX_BASE_URL = "https://sandbox.asaas.com/api/v3"

#: Confirmado por resposta real da API em 24/09/2026 (verificacao manual, Sandbox):
#: "O valor minimo para cobrancas com a forma de pagamento Pergunte ao Cliente e R$ 5,00" —
#: `billingType: UNDEFINED` mapeia para "Pergunte ao Cliente" na interface do Asaas. Validado
#: aqui, antes de qualquer chamada de rede, para falhar cedo e com mensagem clara em vez de
#: deixar o Asaas recusar.
MINIMUM_CHARGE_AMOUNT = Decimal("5.00")

#: Status confirmados na documentacao oficial (docs.asaas.com/docs/status-possiveis),
#: 23/09/2026. Qualquer status nao listado aqui cai em PENDING pelo `.get(..., PENDING)`
#: abaixo — fail-closed por desenho: nunca inventa CONFIRMED para um status desconhecido.
_CONFIRMED_ASAAS_STATUSES: frozenset[str] = frozenset(
    {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH", "DUNNING_RECEIVED"}
)
#: Status de cobranca vencida confirmado pela documentacao oficial do Asaas.
_OVERDUE_ASAAS_STATUSES: frozenset[str] = frozenset({"OVERDUE"})
#: Unico status que representa reversao definitiva do valor — nunca deve virar fato fiscal.
_FAILED_ASAAS_STATUSES: frozenset[str] = frozenset({"REFUNDED"})


def map_asaas_status(asaas_status: str) -> GatewayChargeStatus:
    """Publica (nao mais privada) para que `asaas_webhook.py` reuse exatamente a mesma
    tabela de mapeamento em vez de duplicá-la — um evento de webhook e uma consulta de
    polling devem classificar o mesmo status do Asaas do mesmo jeito, sempre."""
    if asaas_status in _CONFIRMED_ASAAS_STATUSES:
        return GatewayChargeStatus.CONFIRMED
    if asaas_status in _OVERDUE_ASAAS_STATUSES:
        return GatewayChargeStatus.OVERDUE
    if asaas_status in _FAILED_ASAAS_STATUSES:
        return GatewayChargeStatus.FAILED
    return GatewayChargeStatus.PENDING


def _error_summary(response: httpx.Response) -> str:
    """Extrai so `code`+`description` do corpo de erro do Asaas — nunca o corpo bruto.

    Achado de fm-security-review (24/09/2026): o corpo de um erro de validacao pode ecoar de
    volta um campo submetido (ex.: `cpfCnpj`, PII) dentro da mensagem. Logar/propagar o corpo
    inteiro arrisca vazar isso em `PaymentGatewayError.details`, que scripts como
    `asaas_smoke_test.py` imprimem para diagnostico. Extrair so os campos estruturados de
    erro reduz — sem eliminar por completo — esse risco, mantendo o diagnostico util.
    """
    try:
        data = response.json()
        errors = data.get("errors", [])
        return "; ".join(
            f"{e.get('code', '?')}: {e.get('description', '?')}" for e in errors
        ) or "(corpo de erro sem campo 'errors' reconhecivel)"
    except (ValueError, AttributeError):
        return "(corpo de erro nao pode ser interpretado como JSON)"


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
            error_summary=_error_summary(response),
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
            error_summary=_error_summary(response),
        )


def _observed_payment_amount(value) -> Decimal | None:
    try:
        amount = Decimal(str(value))
        if amount.is_finite() and amount > 0 and amount == amount.quantize(Decimal('0.01')):
            return amount
    except (InvalidOperation, ValueError, TypeError):
        pass
    return None


@dataclass(frozen=True, slots=True)
class AsaasConfig:
    """Configuracao lida do ambiente — nunca fixa em codigo.

    `due_in_days` e um termo de cobranca especifico do Asaas (a API exige `dueDate`); fica
    aqui, nao no contrato generico de `payment_gateway.py`, porque outro gateway pode nem ter
    esse conceito. E um valor de configuracao (placeholder ate o Diretor definir um prazo de
    pagamento formal), nunca um numero fixo dentro de `create_charge`.
    """

    #: `repr=False` — achado de fm-security-review (24/09/2026): o repr padrao de dataclass
    #: expunha a chave em claro (`print(config)`, log de excecao, traceback capturado por
    #: depurador). Mesma disciplina de `SecretRef` (`connectors.py`), que redige por tipo,
    #: nao por disciplina de quem escreve o log.
    api_key: str | None = field(repr=False)
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
    #: Injetavel (achado de fm-security-review, 24/09/2026): por padrao em memoria
    #: (`IdempotencyStore`), mas em producao deve receber `api.db.PersistentIdempotencyStore`
    #: — sem isso, reiniciar o processo entre criar e confirmar uma cobranca perde a garantia
    #: contra duplicar uma cobranca real no Asaas.
    idempotency: IdempotencyStoreLike = field(default_factory=IdempotencyStore)
    _client: httpx.Client = field(init=False, repr=False)

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
        if command.amount < MINIMUM_CHARGE_AMOUNT:
            raise PaymentGatewayError(
                PaymentGatewayErrorCode.VALIDATION_REJECTED,
                f"Valor da cobranca (R$ {command.amount}) abaixo do minimo do Asaas para "
                f"'Pergunte ao Cliente' (R$ {MINIMUM_CHARGE_AMOUNT}).",
            )

        # Legacy entrypoint retains its original idempotency contract. V1 billing uses
        # dispatch_frozen_charge only after the API commits the financial dispatch fence;
        # an empty externalReference lookup cannot prove absence after uncertain POST.
        result, _replay = self.idempotency.execute(
            command.tenant_id, command.idempotency_key, lambda: self._create_charge_once(command)
        )
        return result

    def dispatch_frozen_charge(self, command: ChargeCommand) -> ChargeResult:
        """Caller MUST commit a durable obligation/dispatch fence before calling once.

        Unlike the legacy adapter entrypoint, no DB idempotency transaction wraps HTTP.
        Any uncertain retry must use recover_charge, which never creates a payment.
        """
        require_idempotency(command)
        if command.amount < MINIMUM_CHARGE_AMOUNT:
            raise PaymentGatewayError(PaymentGatewayErrorCode.VALIDATION_REJECTED,
                                      "Valor inferior ao mínimo do gateway; conciliação necessária.")
        return self._create_charge_once(command, strict=True)

    def _create_charge_once(self, command: ChargeCommand, *, strict=False) -> ChargeResult:
        # Initial dispatch checks for an existing reference before creating. After an
        # uncertain V1 dispatch, callers MUST use recover_charge instead of this method.
        existing = self._find_payment_by_external_reference(command.idempotency_key, strict=strict)
        if existing is not None:
            return existing

        customer_id = self._ensure_customer(command.customer_ref, command.customer_document)
        due_date = (command.due_at.astimezone(COMMERCIAL_TIMEZONE).date() if command.due_at is not None
                    else date.today() + timedelta(days=self.config.due_in_days))
        response = self._client.post(
            "/payments",
            json={
                "customer": customer_id,
                "billingType": "UNDEFINED",
                "value": float(command.amount.quantize(Decimal("0.01"))),
                "dueDate": due_date.isoformat(),
                "description": f"CampaIA — competencia {command.competence}",
                "externalReference": command.idempotency_key,
                **({"interest": {"value": 0}, "fine": {"value": 0}} if strict else {}),
            },
        )
        _raise_for_response(response)
        body = response.json()
        return ChargeResult(
            gateway_charge_id=body["id"],
            status=map_asaas_status(body["status"]),
            provider=self.provider,
            mode=self.mode,
            invoice_url=safe_asaas_invoice_url(body.get("invoiceUrl"), self.mode),
            observed_amount=_observed_payment_amount(body.get("value")),
            observed_due_date=body.get("dueDate"),
        )

    def recover_charge(self, command: ChargeCommand) -> ChargeResult | None:
        """Read-only recovery; missing results never cause a payment POST."""
        require_idempotency(command)
        return self._find_payment_by_external_reference(command.idempotency_key, strict=True)

    def get_charge_status(self, gateway_charge_id: str) -> GatewayChargeStatus:
        response = self._client.get(f"/payments/{gateway_charge_id}")
        _raise_for_response(response)
        return map_asaas_status(response.json()["status"])

    # ------------------------------------------------------------------ apoio

    def _find_payment_by_external_reference(
        self, external_reference: str, *, strict: bool = False
    ) -> ChargeResult | None:
        """Recover a payment created by a previous process before local commit.

        Asaas supports filtering GET /payments by externalReference. Exactly one match is
        reusable. More than one is a reconciliation divergence and must fail closed rather
        than silently choosing one of several financial records.
        """
        response = self._client.get(
            "/payments",
            params={"externalReference": external_reference, "limit": 2},
        )
        _raise_for_response(response)
        listing = response.json()
        if not isinstance(listing, dict) or not isinstance(listing.get("data"), list):
            raise PaymentGatewayError(PaymentGatewayErrorCode.UNKNOWN,
                                      "Resposta de conciliação sem listagem válida.")
        data = listing["data"]
        if not data and not listing.get("hasMore", False):
            return None
        if len(data) != 1 or listing.get("hasMore", False):
            raise PaymentGatewayError(
                PaymentGatewayErrorCode.UNKNOWN,
                "Mais de uma cobranca Asaas encontrada para a mesma externalReference.",
                external_reference=external_reference,
                match_count=len(data),
            )
        payment = data[0]
        if strict and payment.get("externalReference") != external_reference:
            raise PaymentGatewayError(PaymentGatewayErrorCode.UNKNOWN,
                                      "Referência externa divergente na conciliação.")
        return ChargeResult(
            gateway_charge_id=payment["id"],
            status=map_asaas_status(payment["status"]),
            provider=self.provider,
            mode=self.mode,
            invoice_url=safe_asaas_invoice_url(payment.get("invoiceUrl"), self.mode),
            observed_amount=_observed_payment_amount(payment.get("value")),
            observed_due_date=payment.get("dueDate"),
        )

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
    "MINIMUM_CHARGE_AMOUNT",
    "PRODUCTION_BASE_URL",
    "SANDBOX_BASE_URL",
    "map_asaas_status",
]
