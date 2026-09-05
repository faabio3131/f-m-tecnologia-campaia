"""Motor de otimizacao: sugere ajustes de performance. Nunca executa sozinho.

Implementa F8.1 (`docs/product/FUNCTIONAL_REQUIREMENTS.md`, Fase 0): "sugerir otimizacoes"
com base em metricas observadas -- aumentar budget se CTR alto, pausar se CPA alto, ajustar
lance se volume baixo, expandir publico se CPC alto. F8.2 ("executar otimizacoes automaticas")
esta marcado como fora do escopo do MVP naquele documento e portanto NAO e implementado aqui:
este modulo devolve `Recommendation`, nunca aplica a mudanca.

Cada `Recommendation` carrega o `ActionKind` (autonomy.py) que a executaria, para que quem
consome a recomendacao monte uma `PolicyRequest` (policy.py) e deixe o `autonomy.py` e o
`PolicyEngine` decidirem se ela pode seguir sem humano -- decisao que este modulo nao toma.
No teto de autonomia do MVP (`AutonomyLevel.APROVADO`), essa decisao e sempre "exige humano".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .autonomy import ActionKind


def _d(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class RecommendationCode(StrEnum):
    INCREASE_BUDGET_HIGH_CTR = "INCREASE_BUDGET_HIGH_CTR"
    PAUSE_HIGH_CPA = "PAUSE_HIGH_CPA"
    ADJUST_BID_LOW_VOLUME = "ADJUST_BID_LOW_VOLUME"
    EXPAND_AUDIENCE_HIGH_CPC = "EXPAND_AUDIENCE_HIGH_CPC"


@dataclass(frozen=True)
class PerformanceSnapshot:
    """Metricas observadas de uma campanha (ou de um canal dela) em um periodo.

    Todas as taxas em fracao decimal (0.02 = 2%), nunca em float -- mesma disciplina do
    `budget.py`. `volume` e a contagem de conversoes (ou o evento-alvo definido no plano).
    """

    ctr: Decimal
    cpc: Decimal
    cpa: Decimal
    volume: int
    currency: str


@dataclass(frozen=True)
class OptimizationTargets:
    """Metas e limiares configurados para a campanha. Nada aqui e hardcoded no motor:
    o cliente ou o Plano de campanha definem os proprios alvos."""

    cpa_target: Decimal
    volume_target: int
    #: Limiares default vem de F7.4 (mesmo documento): CTR baixo e definido como <0.5%.
    #: Aqui usamos o espelho para o lado "alto": acima disso, ha sinal de sobra de budget.
    high_ctr_threshold: Decimal = Decimal("0.02")
    #: CPA acima de `cpa_multiplier_for_pause` vezes o alvo dispara sugestao de pausa,
    #: espelhando o "Alto CPA (>2x objetivo)" de F7.4.
    cpa_multiplier_for_pause: Decimal = Decimal("2")
    #: CPC acima deste valor absoluto (mesma moeda do snapshot) dispara sugestao de
    #: expandir publico. Nao ha um "objetivo de CPC" universal, por isso e um teto absoluto
    #: configurado por campanha, nao um multiplicador de meta.
    high_cpc_ceiling: Decimal = Decimal("0")


@dataclass(frozen=True)
class Recommendation:
    code: RecommendationCode
    action: ActionKind
    explanation: str
    #: Percentual de mudanca sugerido, quando aplicavel (ex.: +15% de budget). None quando
    #: a recomendacao nao e uma variacao percentual (ex.: PAUSE).
    suggested_change_pct: Decimal | None = None
    metrics: PerformanceSnapshot | None = None


@dataclass(frozen=True)
class OptimizationReport:
    campaign_id: str
    recommendations: tuple[Recommendation, ...] = field(default_factory=tuple)

    @property
    def has_recommendations(self) -> bool:
        return len(self.recommendations) > 0


#: Percentual de ajuste sugerido quando uma regra dispara. Constantes nomeadas, nao magicas,
#: e sempre dentro da faixa que `docs/product/OUT_OF_SCOPE.md` marca como aceitavel
#: ("otimizacoes automaticas agressivas" = mudanca >10% esta fora do escopo mesmo como
#: sugestao automatica recorrente; por isso o motor sugere um valor moderado por padrao).
DEFAULT_BUDGET_INCREASE_PCT = Decimal("10")
DEFAULT_BID_ADJUSTMENT_PCT = Decimal("5")


def evaluate_campaign(
    campaign_id: str,
    snapshot: PerformanceSnapshot,
    targets: OptimizationTargets,
) -> OptimizationReport:
    """Aplica as 4 regras de F8.1 a um snapshot de performance. Deterministico: nao chama
    LLM, nao depende de contexto conversacional. Mais de uma regra pode disparar ao mesmo
    tempo (ex.: CTR alto e CPA alto simultaneamente) -- cada uma vira uma recomendacao
    separada, e quem consome decide como priorizar ou combinar.
    """
    recommendations: list[Recommendation] = []

    if snapshot.ctr > targets.high_ctr_threshold:
        recommendations.append(
            Recommendation(
                code=RecommendationCode.INCREASE_BUDGET_HIGH_CTR,
                action=ActionKind.BUDGET_INCREASE,
                explanation=(
                    f"CTR de {snapshot.ctr:.2%} acima do limiar de "
                    f"{targets.high_ctr_threshold:.2%}. Ha sinal de demanda nao atendida "
                    f"pelo orcamento atual."
                ),
                suggested_change_pct=DEFAULT_BUDGET_INCREASE_PCT,
                metrics=snapshot,
            )
        )

    cpa_ceiling = targets.cpa_target * targets.cpa_multiplier_for_pause
    if snapshot.cpa > cpa_ceiling:
        recommendations.append(
            Recommendation(
                code=RecommendationCode.PAUSE_HIGH_CPA,
                action=ActionKind.PAUSE,
                explanation=(
                    f"CPA de {snapshot.cpa} {snapshot.currency} excede "
                    f"{targets.cpa_multiplier_for_pause}x o objetivo de "
                    f"{targets.cpa_target} {snapshot.currency} "
                    f"(teto: {cpa_ceiling} {snapshot.currency})."
                ),
                metrics=snapshot,
            )
        )

    if snapshot.volume < targets.volume_target:
        recommendations.append(
            Recommendation(
                code=RecommendationCode.ADJUST_BID_LOW_VOLUME,
                action=ActionKind.BID_ADJUSTMENT,
                explanation=(
                    f"Volume de {snapshot.volume} abaixo da meta de "
                    f"{targets.volume_target}. Ajuste de lance pode aumentar competitividade "
                    f"nos leiloes."
                ),
                suggested_change_pct=DEFAULT_BID_ADJUSTMENT_PCT,
                metrics=snapshot,
            )
        )

    if targets.high_cpc_ceiling > 0 and snapshot.cpc > targets.high_cpc_ceiling:
        recommendations.append(
            Recommendation(
                code=RecommendationCode.EXPAND_AUDIENCE_HIGH_CPC,
                action=ActionKind.TARGETING_CHANGE,
                explanation=(
                    f"CPC de {snapshot.cpc} {snapshot.currency} acima do teto de "
                    f"{targets.high_cpc_ceiling} {snapshot.currency}. Publico pode estar "
                    f"saturado ou excessivamente restrito."
                ),
                metrics=snapshot,
            )
        )

    return OptimizationReport(campaign_id=campaign_id, recommendations=tuple(recommendations))
