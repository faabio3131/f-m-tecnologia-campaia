"""Agentes especializados.

Um agente aqui NAO e um serviço com autoridade propria. E uma funcao pura:
contexto -> requisicao de IA -> proposta estruturada e validada.

O que um agente pode: propor. So isso.

O que nenhum agente tem: credencial, conector, capacidade de alterar orcamento, politica,
autonomia ou estado externo. `Proposal` e um dataclass congelado sem nenhum metodo que
produza efeito. Um teste arquitetural le a arvore sintatica deste arquivo e falha se
aparecer import de conector ou de Saga.

Contexto faltando NAO e preenchido por suposicao. O agente recusa e diz o que falta. Um
modelo pedindo para "assumir um orcamento razoavel" e exatamente como se inventa gasto.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from .ai_gateway import (
    AIGateway,
    AIRequest,
    AIResult,
    AIStatus,
    AITask,
    OutputSchema,
    Prefer,
    Provenance,
)
from .errors import TenantIsolationViolation
from .sanitizer import SanitizationReport, sanitize


@dataclass(frozen=True)
class AgentSpec:
    name: str
    task: AITask
    output_schema: OutputSchema
    required_context: frozenset[str]
    max_cost_units: Decimal = Decimal("5")
    prompt_version: str = "v1"
    prefer: Prefer = Prefer.QUALITY


#: Catalogo da Arquitetura V2, secao 4.5. Cada um com contrato de saida proprio.
AGENTS: dict[str, AgentSpec] = {
    "business_context": AgentSpec(
        name="business_context",
        task=AITask.INTERPRET_METRICS,
        output_schema=OutputSchema(
            "business-context",
            frozenset({"resumo", "diferenciais"}),
            {"resumo": str, "diferenciais": list},
        ),
        required_context=frozenset({"empresa", "produto", "regiao"}),
    ),
    "strategist": AgentSpec(
        name="strategist",
        task=AITask.PLAN_CAMPAIGN,
        output_schema=OutputSchema(
            "campaign-plan",
            frozenset({"objetivo", "funil", "canais", "justificativa"}),
            {"objetivo": str, "funil": str, "canais": list, "justificativa": str},
        ),
        required_context=frozenset({"objetivo", "orcamento", "publico", "regiao"}),
        max_cost_units=Decimal("10"),
    ),
    "copy": AgentSpec(
        name="copy",
        task=AITask.GENERATE_COPY,
        output_schema=OutputSchema(
            "copy-variants", frozenset({"variacoes"}), {"variacoes": list}
        ),
        required_context=frozenset({"oferta", "tom", "canal"}),
    ),
    "audience": AgentSpec(
        name="audience",
        task=AITask.PROPOSE_AUDIENCE,
        output_schema=OutputSchema(
            "audience-proposal",
            frozenset({"segmentos", "exclusoes", "sensivel"}),
            {"segmentos": list, "exclusoes": list, "sensivel": bool},
        ),
        required_context=frozenset({"publico", "regiao", "canal"}),
    ),
    "policy": AgentSpec(
        name="policy",
        task=AITask.MODERATE,
        output_schema=OutputSchema(
            "policy-flags", frozenset({"alertas"}), {"alertas": list}
        ),
        required_context=frozenset({"texto"}),
    ),
    "performance": AgentSpec(
        name="performance",
        task=AITask.INTERPRET_METRICS,
        output_schema=OutputSchema(
            "performance-reading",
            frozenset({"leitura", "recomendacoes"}),
            {"leitura": str, "recomendacoes": list},
        ),
        required_context=frozenset({"metricas", "periodo"}),
    ),
}


@dataclass(frozen=True)
class Proposal:
    """Saida de agente. E SEMPRE uma proposta: nada aqui autoriza efeito externo.

    Para virar acao, precisa passar pelo Policy Engine e receber uma autorizacao propria.
    """

    proposal_id: str
    agent: str
    tenant_id: str
    output: dict
    provenance: Provenance
    pii_found: tuple[str, ...] = ()
    pii_count: int = 0

    @property
    def is_proposal(self) -> bool:
        return True


@dataclass(frozen=True)
class AgentFailure:
    agent: str
    tenant_id: str
    status: AIStatus | str
    reason: str
    missing_context: tuple[str, ...] = ()
    provenance: Provenance | None = None


MISSING_CONTEXT = "MISSING_CONTEXT"
UNKNOWN_AGENT = "UNKNOWN_AGENT"


@dataclass
class AgentRunner:
    """Executa agentes contra o AI Gateway. Nao conhece conector nem Saga."""

    gateway: AIGateway
    #: Relatorios de sanitizacao por proposta, guardados no backend para reidratacao.
    _reports: dict[str, SanitizationReport] = field(default_factory=dict)

    def register_schemas(self) -> None:
        """Publica os contratos de saida dos agentes no gateway."""
        for spec in AGENTS.values():
            self.gateway.schemas[spec.output_schema.schema_id] = spec.output_schema

    def run(
        self, agent_name: str, *, tenant_id: str, context: dict
    ) -> Proposal | AgentFailure:
        if not tenant_id:
            raise TenantIsolationViolation("Execucao de agente sem tenant_id.")

        spec = AGENTS.get(agent_name)
        if spec is None:
            return AgentFailure(
                agent=agent_name,
                tenant_id=tenant_id,
                status=UNKNOWN_AGENT,
                reason=f"Agente {agent_name!r} nao existe no catalogo.",
            )

        faltando = tuple(sorted(spec.required_context - context.keys()))
        if faltando:
            # Recusar e o comportamento correto. Preencher por suposicao seria inventar
            # publico, verba ou objetivo - e verba inventada vira gasto real.
            return AgentFailure(
                agent=agent_name,
                tenant_id=tenant_id,
                status=MISSING_CONTEXT,
                reason="Contexto insuficiente; o agente nao supoe o que falta.",
                missing_context=faltando,
            )

        limpo, relatorio = sanitize(context)

        request = AIRequest(
            request_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            task=spec.task,
            input=limpo,
            output_schema_id=spec.output_schema.schema_id,
            max_cost_units=spec.max_cost_units,
            prefer=spec.prefer,
            prompt_version=spec.prompt_version,
        )

        resultado: AIResult = self.gateway.execute(request)

        if not resultado.ok or resultado.output is None:
            return AgentFailure(
                agent=agent_name,
                tenant_id=tenant_id,
                status=resultado.status,
                reason="O gateway nao devolveu saida valida.",
                provenance=resultado.provenance,
            )

        proposal_id = str(uuid.uuid4())
        self._reports[proposal_id] = relatorio
        return Proposal(
            proposal_id=proposal_id,
            agent=agent_name,
            tenant_id=tenant_id,
            output=resultado.output,
            provenance=resultado.provenance,
            pii_found=relatorio.found_types,
            pii_count=relatorio.total,
        )

    def rehydrate(self, proposal: Proposal, text: str) -> str:
        """Repoe PII real para exibir ao proprio dono do dado. Nunca para log."""
        relatorio = self._reports.get(proposal.proposal_id)
        return relatorio.rehydrate(text) if relatorio else text
