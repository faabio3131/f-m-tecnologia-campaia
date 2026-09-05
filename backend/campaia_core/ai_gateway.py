"""AI Model Gateway.

Aqui a regra central do produto vira codigo: a IA PROPOE, o servico deterministico executa.

O gateway devolve dados estruturados e validados. Ele nao conhece conector, nao conhece
Saga e nao tem como produzir efeito externo - nem por engano, nem por prompt injection.
Existe um teste arquitetural que le a arvore sintatica deste arquivo e falha se alguem
importar `connectors` ou `saga` aqui.

Quatro travas que este modulo implementa:

  CUSTO       Teto por requisicao E teto por tenant. Tentativa que chegou ao provedor
              custa dinheiro mesmo quando a resposta e imprestavel - por isso o debito
              acontece na tentativa, nao no sucesso.

  SCHEMA      Saida fora do contrato e REJEITADA, nunca "consertada". Remendar saida de
              modelo esconde regressao de qualidade e produz dado silenciosamente errado.

  FALLBACK    Trocar de provedor e permitido; trocar em silencio nao. Toda tentativa,
              inclusive as que falharam, aparece na proveniencia e na auditoria.

  SEGREDO     Credencial nunca entra em payload de IA. O gateway recusa a requisicao antes
              de sair do backend (invariante I-03).

Nota de escopo: a sanitizacao de PII vive em `sanitizer.py` e e aplicada pelos agentes.
Aqui fica a trava de credencial, que e a que protege dinheiro e contas.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from .connectors import SecretRef  # apenas o tipo, para RECUSAR seu uso em payload
from .errors import CampaiaError, TenantIsolationViolation

MAX_ATTEMPTS_PER_REQUEST = 3
CIRCUIT_THRESHOLD = 3


class AITask(StrEnum):
    PLAN_CAMPAIGN = "PLAN_CAMPAIGN"
    GENERATE_COPY = "GENERATE_COPY"
    GENERATE_IMAGE = "GENERATE_IMAGE"
    ANALYZE_CREATIVE = "ANALYZE_CREATIVE"
    PROPOSE_AUDIENCE = "PROPOSE_AUDIENCE"
    INTERPRET_METRICS = "INTERPRET_METRICS"
    MODERATE = "MODERATE"
    EMBED = "EMBED"


class AIStatus(StrEnum):
    OK = "OK"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    BLOCKED_BY_MODERATION = "BLOCKED_BY_MODERATION"
    COST_LIMIT = "COST_LIMIT"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NO_PROVIDER = "NO_PROVIDER"


class Outcome(StrEnum):
    OK = "OK"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    COST_LIMIT = "COST_LIMIT"


class Prefer(StrEnum):
    QUALITY = "QUALITY"
    COST = "COST"
    LATENCY = "LATENCY"


# --------------------------------------------------------------------------- erros


class ProviderError(CampaiaError):
    code = "PROVIDER_ERROR"


class ProviderTimeout(CampaiaError):
    code = "TIMEOUT"


class ModerationBlocked(CampaiaError):
    code = "BLOCKED_BY_MODERATION"


class CredentialInPayload(CampaiaError):
    """Nunca deve acontecer. Se acontecer, e defeito grave e a requisicao nao sai."""

    code = "PERMISSION_DENIED"


# --------------------------------------------------------------- trava de credencial

#: Padroes obvios de credencial. Nao pretende ser exaustivo: a defesa real e nunca
#: colocar segredo em payload. Isto e a rede de seguranca de ultimo momento.
_SECRET_PATTERNS = (
    re.compile(r"\bvault://", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
    re.compile(r"\bEAA[A-Za-z0-9]{20,}"),  # formato de token da Meta
    re.compile(r"\b(access_token|refresh_token|developer_token|client_secret)\b", re.I),
)


def assert_no_credentials(value: Any, *, path: str = "input") -> None:
    """Percorre o payload e recusa qualquer coisa parecida com credencial."""
    if isinstance(value, SecretRef):
        raise CredentialInPayload(
            f"Referencia a segredo em {path}: credencial nunca vai para provedor de IA."
        )
    if isinstance(value, str):
        for padrao in _SECRET_PATTERNS:
            if padrao.search(value):
                raise CredentialInPayload(
                    f"Conteudo com aparencia de credencial em {path}."
                )
    elif isinstance(value, dict):
        for chave, item in value.items():
            assert_no_credentials(chave, path=f"{path}.<chave>")
            assert_no_credentials(item, path=f"{path}.{chave}")
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            assert_no_credentials(item, path=f"{path}[{i}]")


# ------------------------------------------------------------------------- contratos


@dataclass(frozen=True)
class AIRequest:
    request_id: str
    tenant_id: str
    task: AITask
    input: dict
    output_schema_id: str
    max_cost_units: Decimal
    timeout_ms: int = 30000
    prefer: Prefer = Prefer.QUALITY
    pinned_provider: str | None = None
    prompt_version: str = "v1"


@dataclass(frozen=True)
class Attempt:
    provider: str
    outcome: Outcome
    reason: str | None = None


@dataclass(frozen=True)
class Provenance:
    provider: str | None
    model: str | None
    prompt_version: str
    cost_units: Decimal
    latency_ms: int
    attempts: tuple[Attempt, ...]

    @property
    def fallback_used(self) -> bool:
        """True quando o provedor que respondeu nao foi o primeiro escolhido."""
        return len(self.attempts) > 1 and self.attempts[-1].outcome is Outcome.OK


@dataclass(frozen=True)
class AIResult:
    request_id: str
    ai_run_id: str
    status: AIStatus
    output: dict | None
    provenance: Provenance

    @property
    def ok(self) -> bool:
        return self.status is AIStatus.OK


@dataclass(frozen=True)
class ProviderResponse:
    output: dict
    cost_units: Decimal
    latency_ms: int
    model: str
    model_version: str | None = None


class AIProvider(Protocol):
    name: str

    def supports(self, task: AITask) -> bool: ...
    def generate(self, request: AIRequest) -> ProviderResponse: ...


# ------------------------------------------------------------------ custo por tenant


@dataclass
class CostLedger:
    """Consumo de IA por tenant. Base de qualquer modelo comercial (D-06)."""

    caps: dict[str, Decimal] = field(default_factory=dict)
    spent: dict[str, Decimal] = field(default_factory=dict)

    def set_cap(self, tenant_id: str, cap: Decimal) -> None:
        self.caps[tenant_id] = cap

    def used(self, tenant_id: str) -> Decimal:
        return self.spent.get(tenant_id, Decimal("0"))

    def remaining(self, tenant_id: str) -> Decimal | None:
        cap = self.caps.get(tenant_id)
        return None if cap is None else cap - self.used(tenant_id)

    def would_exceed(self, tenant_id: str, amount: Decimal) -> bool:
        restante = self.remaining(tenant_id)
        return restante is not None and amount > restante

    def charge(self, tenant_id: str, amount: Decimal) -> None:
        """Debita SEMPRE que a chamada chegou ao provedor.

        Resposta imprestavel tambem foi cobrada pelo fornecedor. Debitar so no sucesso
        faria o custo real divergir do medido, e a margem sumiria sem aparecer em lugar
        nenhum.
        """
        if not tenant_id:
            raise TenantIsolationViolation("Consumo de IA sem tenant_id.")
        self.spent[tenant_id] = self.used(tenant_id) + amount


# --------------------------------------------------------------- validacao de schema


@dataclass(frozen=True)
class OutputSchema:
    """Validacao estrutural minima, sem dependencia externa.

    Em producao isto e substituido por JSON Schema completo; o contrato ja existe em
    `contracts/`. O que importa aqui e a regra: saida invalida e rejeitada, nao remendada.
    """

    schema_id: str
    required: frozenset[str]
    types: dict[str, type] = field(default_factory=dict)

    def validate(self, output: Any) -> str | None:
        if not isinstance(output, dict):
            return "Saida nao e um objeto."
        faltando = sorted(self.required - output.keys())
        if faltando:
            return f"Campos obrigatorios ausentes: {faltando}."
        for campo, tipo in self.types.items():
            if campo in output and not isinstance(output[campo], tipo):
                return f"Campo {campo} deveria ser {tipo.__name__}."
        return None


# ------------------------------------------------------------------------- gateway


@dataclass
class _Circuit:
    consecutive_failures: int = 0
    open: bool = False


@dataclass
class AIGateway:
    providers: list[AIProvider] = field(default_factory=list)
    schemas: dict[str, OutputSchema] = field(default_factory=dict)
    ledger: CostLedger = field(default_factory=CostLedger)
    #: Custo estimado por unidade de qualidade, usado na ordenacao por preferencia.
    provider_cost_hint: dict[str, Decimal] = field(default_factory=dict)
    provider_latency_hint: dict[str, int] = field(default_factory=dict)
    provider_quality_hint: dict[str, int] = field(default_factory=dict)
    _circuits: dict[str, _Circuit] = field(default_factory=dict)

    # ------------------------------------------------------------------ selecao

    def _circuit(self, name: str) -> _Circuit:
        return self._circuits.setdefault(name, _Circuit())

    def candidates(self, request: AIRequest) -> list[AIProvider]:
        aptos = [p for p in self.providers if p.supports(request.task)]

        if request.pinned_provider:
            aptos = [p for p in aptos if p.name == request.pinned_provider]

        if request.prefer is Prefer.COST:
            aptos.sort(key=lambda p: self.provider_cost_hint.get(p.name, Decimal("0")))
        elif request.prefer is Prefer.LATENCY:
            aptos.sort(key=lambda p: self.provider_latency_hint.get(p.name, 0))
        else:
            aptos.sort(key=lambda p: -self.provider_quality_hint.get(p.name, 0))

        return aptos

    # ------------------------------------------------------------------ execucao

    def execute(self, request: AIRequest) -> AIResult:
        if not request.tenant_id:
            raise TenantIsolationViolation("Requisicao de IA sem tenant_id.")

        # Trava de credencial ANTES de qualquer chamada externa.
        assert_no_credentials(request.input)

        run_id = str(uuid.uuid4())
        tentativas: list[Attempt] = []
        custo_total = Decimal("0")
        schema = self.schemas.get(request.output_schema_id)

        if self.ledger.would_exceed(request.tenant_id, request.max_cost_units):
            return self._fail(
                request, run_id, AIStatus.COST_LIMIT,
                (Attempt("-", Outcome.COST_LIMIT, "Teto de custo do tenant atingido."),),
                custo_total,
            )

        candidatos = self.candidates(request)
        if not candidatos:
            return self._fail(
                request, run_id, AIStatus.NO_PROVIDER,
                (Attempt("-", Outcome.ERROR, "Nenhum provedor apto para a tarefa."),),
                custo_total,
            )

        ultimo_status = AIStatus.PROVIDER_ERROR

        for provider in candidatos[:MAX_ATTEMPTS_PER_REQUEST]:
            circuito = self._circuit(provider.name)
            if circuito.open:
                tentativas.append(
                    Attempt(provider.name, Outcome.CIRCUIT_OPEN, "Circuito aberto.")
                )
                continue

            try:
                resposta = provider.generate(request)
            except ProviderTimeout as exc:
                self._register_failure(provider.name)
                tentativas.append(Attempt(provider.name, Outcome.TIMEOUT, str(exc)))
                ultimo_status = AIStatus.TIMEOUT
                continue
            except ModerationBlocked as exc:
                # Moderacao NAO e falha do provedor: nao abre circuito e nao tenta outro.
                tentativas.append(Attempt(provider.name, Outcome.ERROR, str(exc)))
                return self._fail(
                    request, run_id, AIStatus.BLOCKED_BY_MODERATION,
                    tuple(tentativas), custo_total,
                )
            except ProviderError as exc:
                self._register_failure(provider.name)
                tentativas.append(Attempt(provider.name, Outcome.ERROR, str(exc)))
                ultimo_status = AIStatus.PROVIDER_ERROR
                continue

            # Chegou ao provedor: custou dinheiro, independentemente do que voltou.
            custo_total += resposta.cost_units
            self.ledger.charge(request.tenant_id, resposta.cost_units)

            if custo_total > request.max_cost_units:
                tentativas.append(
                    Attempt(provider.name, Outcome.COST_LIMIT, "Custo acima do teto da requisicao.")
                )
                return self._fail(
                    request, run_id, AIStatus.COST_LIMIT, tuple(tentativas), custo_total
                )

            erro = schema.validate(resposta.output) if schema else None
            if erro is not None:
                # Saida invalida NAO e corrigida aqui. Outro provedor pode tentar.
                self._register_failure(provider.name)
                tentativas.append(Attempt(provider.name, Outcome.SCHEMA_INVALID, erro))
                ultimo_status = AIStatus.SCHEMA_INVALID
                continue

            circuito.consecutive_failures = 0
            tentativas.append(Attempt(provider.name, Outcome.OK))
            return AIResult(
                request_id=request.request_id,
                ai_run_id=run_id,
                status=AIStatus.OK,
                output=resposta.output,
                provenance=Provenance(
                    provider=provider.name,
                    model=resposta.model,
                    prompt_version=request.prompt_version,
                    cost_units=custo_total,
                    latency_ms=resposta.latency_ms,
                    attempts=tuple(tentativas),
                ),
            )

        return self._fail(request, run_id, ultimo_status, tuple(tentativas), custo_total)

    # ------------------------------------------------------------------ auxiliares

    def _register_failure(self, name: str) -> None:
        circuito = self._circuit(name)
        circuito.consecutive_failures += 1
        if circuito.consecutive_failures >= CIRCUIT_THRESHOLD:
            circuito.open = True

    def _fail(
        self,
        request: AIRequest,
        run_id: str,
        status: AIStatus,
        tentativas: tuple[Attempt, ...],
        custo: Decimal,
    ) -> AIResult:
        """Falha tambem tem proveniencia: sem isso, nao se audita o que foi tentado."""
        return AIResult(
            request_id=request.request_id,
            ai_run_id=run_id,
            status=status,
            output=None,
            provenance=Provenance(
                provider=None,
                model=None,
                prompt_version=request.prompt_version,
                cost_units=custo,
                latency_ms=0,
                attempts=tentativas,
            ),
        )
