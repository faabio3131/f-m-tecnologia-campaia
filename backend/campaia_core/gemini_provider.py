"""Adaptador real do Google Gemini para o `AIGateway` (ADR-0021, 24/09/2026).

Implementa `AIProvider` (`ai_gateway.py`). Mesma disciplina ja usada em `asaas_gateway.py`:
nenhuma credencial ou conta fixa em codigo (tudo vem de `GeminiConfig.from_env()`), e o
adaptador nao decide NADA de negocio — so traduz `AIRequest`/`ProviderResponse` para a forma
que a Interactions API do Gemini espera e devolve.

Endpoint e formato confirmados contra a documentacao oficial do Google (ai.google.dev,
pesquisa de 24/09/2026): a "Interactions API" (`POST /v1beta/interactions`, header
`x-goog-api-key`) e a interface recomendada para projetos novos desde junho/2026 — a antiga
`generateContent` continua funcionando mas e tratada como legado. Usamos `store: false`
deliberadamente: cada chamada deste gateway e uma requisicao isolada (um agente por vez, sem
turno de conversa), e nao ha motivo para o Google reter historico do lado dele — mesma
disciplina de minimizacao de dado ja aplicada por `sanitizer.py`.

Saida estruturada nativa (`response_format`) confirmada por chamada real em 24/09/2026 (ver
docs/evidence/EVIDENCIA_GEMINI_PROVIDER_20260924.md): a forma correta na Interactions API e
`{"type": "text", "mime_type": "application/json", "schema": <JSON Schema>}` — NAO o formato
estilo OpenAI (`type: "json_schema"`) nem `type: "object"` no nivel superior de
`response_format`; ambos foram testados contra a API real e rejeitados (400) ou devolveram
saida vazia. `_build_response_format` traduz o `OutputSchema` (contrato interno) para essa
forma. Isso e a PRIMEIRA barreira contra saida fora do contrato — `OutputSchema.validate()`
em `AIGateway.execute` continua sendo a SEGUNDA barreira e nao foi removida; a API externa
nao substitui a validacao de dominio do CampaIA.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from decimal import Decimal

import httpx

from .ai_gateway import (
    AIProvider,
    AIRequest,
    AITask,
    ModerationBlocked,
    OutputSchema,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
)

#: Verificado contra a documentacao oficial (ai.google.dev, 24/09/2026) — a Interactions API
#: e a interface recomendada para projetos novos desde junho/2026.
API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

#: Modelo escolhido em ADR-0021 (docs/20_ADR_0021_PROVEDOR_DE_IA_GENERATIVA.md). Nomes de
#: modelo do Gemini mudam com frequencia — reconfirmar contra ai.google.dev antes de trocar
#: o padrao aqui, nunca so por suposicao.
DEFAULT_MODEL = "gemini-3.8-flash"

#: Preco oficial por milhao de tokens, tarifa introdutoria vigente ate 31/12/2026 (pesquisa de
#: 24/09/2026, ver ADR-0021) — sobe para 1.50/7.50 em 2027. Usado só para converter uso real em
#: `cost_units` (que o `CostLedger` do tenant entende como "custo real da chamada", nao uma
#: unidade abstrata) — reconfirmar contra ai.google.dev/gemini-api/docs/pricing antes de
#: qualquer mudança de tarifa do Google.
INPUT_PRICE_PER_MILLION_TOKENS = Decimal("0.75")
OUTPUT_PRICE_PER_MILLION_TOKENS = Decimal("3.75")


class GeminiConfigError(ProviderError):
    """Configuracao ausente ou invalida — nunca segue com uma chamada sem credencial real."""


@dataclass(frozen=True, slots=True)
class GeminiConfig:
    """Configuracao lida do ambiente — nunca fixa em codigo, mesmo padrao de `AsaasConfig`."""

    #: `repr=False` — mesma disciplina de `AsaasConfig.api_key`/`SecretRef`: nunca aparece em
    #: `print()`, log de excecao ou traceback capturado por depurador.
    api_key: str | None = field(repr=False)
    model: str = DEFAULT_MODEL

    @classmethod
    def from_env(cls, prefix: str = "GEMINI_") -> "GeminiConfig":
        return cls(
            api_key=os.environ.get(f"{prefix}API_KEY"),
            model=os.environ.get(f"{prefix}MODEL", DEFAULT_MODEL),
        )


#: Mapeamento deterministico de tipo Python (`OutputSchema.types`) para o nome de tipo do
#: JSON Schema exigido por `response_format`. `list` nao entra aqui — tratado a parte em
#: `_json_schema_property` porque JSON Schema exige um `items` junto do `type: "array"`, nao
#: so o nome do tipo.
_JSON_SCHEMA_TYPE_NAMES: dict[type, str] = {
    str: "string",
    bool: "boolean",
    int: "integer",
    float: "number",
    dict: "object",
}


def _json_schema_property(schema: OutputSchema, campo: str) -> dict:
    """Traduz o tipo Python de um campo do `OutputSchema` para JSON Schema.

    Fail-closed: um tipo Python sem tradução conhecida nunca e adivinhado -- vira
    `ProviderError` antes de qualquer chamada de rede (ver `_build_response_format`).
    """
    tipo = schema.types.get(campo)
    if tipo is None:
        return {"type": "string"}
    if tipo is list:
        # Todos os campos `list` do catalogo atual (`agents.py`) representam lista textual
        # (ex.: "canais") -- nao ha, hoje, contrato de lista de outro tipo primitivo.
        return {"type": "array", "items": {"type": "string"}}
    nome = _JSON_SCHEMA_TYPE_NAMES.get(tipo)
    if nome is None:
        raise ProviderError(
            f"GeminiProvider nao sabe converter o tipo Python '{tipo.__name__}' do campo "
            f"'{campo}' para JSON Schema -- fail-closed: nao adivinha o tipo. Adicione a "
            f"traducao em _JSON_SCHEMA_TYPE_NAMES antes de registrar esse schema."
        )
    return {"type": nome}


def _build_response_format(schema: OutputSchema) -> dict:
    """Traduz o `OutputSchema` (contrato interno, generico para qualquer agente) para o
    `response_format` nativo da Interactions API do Gemini -- forma confirmada por chamada
    real (ver nota do modulo): `{"type": "text", "mime_type": "application/json", "schema":
    <JSON Schema>}`. Chamado antes de qualquer requisicao de rede -- um tipo nao mapeavel
    aborta aqui, fail-closed, sem gastar uma chamada real.
    """
    properties = {
        campo: _json_schema_property(schema, campo) for campo in sorted(schema.required)
    }
    return {
        "type": "text",
        "mime_type": "application/json",
        "schema": {
            "type": "object",
            "properties": properties,
            "required": sorted(schema.required),
        },
    }


def _build_prompt(request: AIRequest, schema: OutputSchema) -> str:
    """Monta o prompt a partir do contexto do agente e da tarefa.

    A ESTRUTURA da saida (JSON, campos, tipos) e imposta por `response_format`
    (`_build_response_format`), nao pelo texto do prompt -- o prompt so precisa da
    SEMANTICA da tarefa: o que preencher e a instrucao de honestidade quando falta dado.
    """
    campos = ", ".join(sorted(schema.required))
    contexto = json.dumps(request.input, ensure_ascii=False, sort_keys=True)
    return (
        f"Tarefa: {request.task.value}.\n"
        f"Contexto (JSON): {contexto}\n\n"
        f"Preencha os campos {campos} de acordo com o contexto acima. "
        f"Se algum dado necessario nao estiver no contexto, não invente valores plausiveis — "
        f"registre a ausência de forma honesta dentro do proprio campo de texto correspondente."
    )


def _extract_text(body: dict) -> str:
    """Percorre `steps` (Interactions API) e devolve o texto do ultimo `model_output`.

    Forma confirmada contra a documentacao oficial (24/09/2026): `steps` e uma lista de
    passos (`thought`, `model_output`, chamadas de ferramenta), e o texto final vem do
    ultimo passo do tipo `model_output`, dentro de `content[].text`.
    """
    steps = body.get("steps")
    if not isinstance(steps, list):
        raise ProviderError("Resposta do Gemini sem campo 'steps' reconhecivel.")
    for step in reversed(steps):
        if step.get("type") != "model_output":
            continue
        for item in step.get("content", []):
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                return item["text"]
    raise ProviderError("Resposta do Gemini sem nenhum 'model_output' de texto.")


def _parse_json_output(raw_text: str) -> dict:
    """Fail-closed: texto que nao e um objeto JSON valido nunca vira ProviderResponse.output
    — vira ProviderError, que o AIGateway trata como tentativa falha (nunca "consertada")."""
    try:
        parsed = json.loads(raw_text.strip())
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Gemini nao respondeu JSON valido: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProviderError(f"Gemini respondeu JSON valido, mas nao um objeto: {type(parsed).__name__}.")
    return parsed


def _compute_cost_units(usage: dict) -> Decimal:
    """Converte tokens de uso real em `cost_units` — aqui, custo real em USD da chamada
    (nao uma unidade abstrata), para que o teto por tenant (`CostLedger`) signifique
    dinheiro de verdade. Ausencia de `usage` no corpo (nunca deveria acontecer numa resposta
    bem-sucedida) falha fechado: cobra o maximo plausivel em vez de assumir custo zero, que
    esconderia gasto real do teto do tenant."""
    input_tokens = usage.get("total_input_tokens")
    output_tokens = usage.get("total_output_tokens")
    if not isinstance(input_tokens, (int, float)) or not isinstance(output_tokens, (int, float)):
        raise ProviderError("Resposta do Gemini sem contagem de tokens ('usage') utilizavel.")
    custo = (
        Decimal(str(input_tokens)) / Decimal("1000000") * INPUT_PRICE_PER_MILLION_TOKENS
        + Decimal(str(output_tokens)) / Decimal("1000000") * OUTPUT_PRICE_PER_MILLION_TOKENS
    )
    return custo.quantize(Decimal("0.000001"))


@dataclass
class GeminiProvider:
    """Adaptador real. `transport` so existe para injetar `httpx.MockTransport` em teste —
    mesma disciplina de `AsaasGateway.transport`.

    `schemas` e injetado (nao importado de `agents.py`) de proposito: este modulo e um
    adaptador de infraestrutura generico, nao deve conhecer o catalogo especifico de agentes
    do produto — quem liga os dois e `api/state.py`, com o mesmo dicionario de
    `OutputSchema` que ja alimenta `AIGateway.schemas`.
    """

    config: GeminiConfig
    schemas: dict[str, OutputSchema] = field(default_factory=dict)
    name: str = "GEMINI"
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    timeout_s: float = 30.0
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.config.api_key:
            raise GeminiConfigError(
                "GEMINI_API_KEY nao configurada — nenhuma chamada real e possivel."
            )
        self._client = httpx.Client(
            base_url=API_BASE_URL,
            headers={
                "x-goog-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "User-Agent": "CampaIA/1.0",
            },
            timeout=self.timeout_s,
            transport=self.transport,
        )

    def supports(self, task: AITask) -> bool:
        # Modelo de texto generalista — apto para qualquer tarefa baseada em texto do
        # catalogo de agentes atual. GENERATE_IMAGE nao e suportado por este adaptador
        # (Gemini Flash de texto nao gera imagem) — fail-closed: melhor nao se candidatar
        # do que aceitar e falhar depois.
        return task is not AITask.GENERATE_IMAGE

    def generate(self, request: AIRequest) -> ProviderResponse:
        schema = self.schemas.get(request.output_schema_id)
        if schema is None:
            raise ProviderError(
                f"GeminiProvider nao tem o contrato de saida '{request.output_schema_id}' "
                f"registrado — nao sabe que JSON pedir ao modelo."
            )

        # Fail-closed antes da rede: um tipo Python nao mapeavel para JSON Schema aborta
        # aqui, nunca depois de gastar uma chamada real.
        response_format = _build_response_format(schema)
        prompt = _build_prompt(request, schema)

        # `response.elapsed` depende de instrumentacao de rede real que o `httpx.MockTransport`
        # dos testes nao populariza de forma confiavel -- medido manualmente aqui para
        # funcionar identicamente contra o transporte real e o de teste.
        started_at = time.monotonic()
        try:
            response = self._client.post(
                "/interactions",
                json={
                    "model": self.config.model,
                    "input": prompt,
                    "store": False,
                    "response_format": response_format,
                },
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.name}: tempo esgotado.") from exc
        latency_ms = int((time.monotonic() - started_at) * 1000)

        if response.status_code == 429:
            raise ProviderError(f"{self.name}: limite de taxa atingido.")
        if response.status_code >= 400:
            raise ProviderError(
                f"{self.name}: erro HTTP {response.status_code} — {response.text[:500]}"
            )

        body = response.json()

        # Bloqueio de seguranca/moderacao do proprio Gemini vira ModerationBlocked, nao
        # ProviderError — mesma distincao que o simulador ja faz (Behavior.MODERATION),
        # para o AIGateway tratar como recusa de conteudo, nao falha tecnica.
        if body.get("status") == "blocked":
            raise ModerationBlocked(f"{self.name}: conteudo bloqueado pela moderacao do Gemini.")

        raw_text = _extract_text(body)
        output = _parse_json_output(raw_text)
        usage = body.get("usage")
        if not isinstance(usage, dict):
            raise ProviderError("Resposta do Gemini sem campo 'usage'.")
        cost_units = _compute_cost_units(usage)

        return ProviderResponse(
            output=output,
            cost_units=cost_units,
            latency_ms=latency_ms,
            model=body.get("model", self.config.model),
        )


__all__ = [
    "API_BASE_URL",
    "DEFAULT_MODEL",
    "GeminiConfig",
    "GeminiConfigError",
    "GeminiProvider",
    "INPUT_PRICE_PER_MILLION_TOKENS",
    "OUTPUT_PRICE_PER_MILLION_TOKENS",
]
