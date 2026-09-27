"""Provedor de IA simulado.

Mesma filosofia do Provider Simulator de anuncios: um simulador que so devolve sucesso
esconde exatamente os caminhos que quebram em producao. Este sabe estourar timeout,
devolver lixo fora do schema, ser bloqueado por moderacao e cobrar caro.

Serve para construir e testar toda a governanca do AI Gateway sem chave de API, sem custo
e sem rede - e para provocar sob demanda falhas que o provedor real nao deixa provocar.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal

from .ai_gateway import (
    AIRequest,
    AITask,
    ModerationBlocked,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
)


class Behavior:
    """Comportamentos programaveis, consumidos em ordem a cada chamada."""

    OK = "OK"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    MODERATION = "MODERATION"
    BAD_SCHEMA = "BAD_SCHEMA"
    EXPENSIVE = "EXPENSIVE"


@dataclass
class SimulatedAIProvider:
    name: str = "SIM-A"
    model: str = "sim-model-1"
    supported_tasks: frozenset[AITask] = frozenset(AITask)
    cost_units: Decimal = Decimal("1")
    latency_ms: int = 120
    #: Saida devolvida no caminho feliz.
    output: dict = field(default_factory=lambda: {"ok": True})
    #: Fila de comportamentos. Vazia = sempre OK.
    behaviors: deque[str] = field(default_factory=deque)
    calls: int = 0

    def supports(self, task: AITask) -> bool:
        return task in self.supported_tasks

    def script(self, *behaviors: str) -> "SimulatedAIProvider":
        self.behaviors.extend(behaviors)
        return self

    def generate(self, request: AIRequest) -> ProviderResponse:
        self.calls += 1
        comportamento = self.behaviors.popleft() if self.behaviors else Behavior.OK

        if comportamento == Behavior.TIMEOUT:
            raise ProviderTimeout(f"{self.name}: tempo esgotado.")
        if comportamento == Behavior.ERROR:
            raise ProviderError(f"{self.name}: erro do provedor.")
        if comportamento == Behavior.MODERATION:
            raise ModerationBlocked(f"{self.name}: conteudo bloqueado por moderacao.")

        if comportamento == Behavior.BAD_SCHEMA:
            return ProviderResponse(
                output={"texto_solto": "modelo respondeu fora do contrato"},
                cost_units=self.cost_units,
                latency_ms=self.latency_ms,
                model=self.model,
            )

        custo = self.cost_units * 100 if comportamento == Behavior.EXPENSIVE else self.cost_units
        return ProviderResponse(
            output=dict(self.output),
            cost_units=custo,
            latency_ms=self.latency_ms,
            model=self.model,
        )
