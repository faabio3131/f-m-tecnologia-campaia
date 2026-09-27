"""Autonomia governada e gatilhos de aprovacao humana.

Ordem Mestra, secao 6. Nivel padrao inicial: 1 (Aprovado).

Regra central: existe um conjunto de acoes que exige humano em QUALQUER nivel de autonomia,
inclusive no nivel 3. Elevar autonomia nunca remove esses gatilhos - inclusive o gatilho de
elevar a propria autonomia, que e o que impede a IA de se auto-promover (invariante I-11).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum, StrEnum


class AutonomyLevel(IntEnum):
    ASSISTENTE = 0
    APROVADO = 1
    LIMITADO = 2
    OPERACIONAL = 3


DEFAULT_LEVEL = AutonomyLevel.APROVADO


class ActionKind(StrEnum):
    CREATE_CAMPAIGN = "CREATE_CAMPAIGN"
    FIRST_PUBLISH = "FIRST_PUBLISH"
    BUDGET_INCREASE = "BUDGET_INCREASE"
    SWITCH_AD_ACCOUNT = "SWITCH_AD_ACCOUNT"
    SENSITIVE_AUDIENCE = "SENSITIVE_AUDIENCE"
    CUSTOMER_LIST = "CUSTOMER_LIST"
    CUSTOMER_MATCH = "CUSTOMER_MATCH"
    TARGETING_CHANGE = "TARGETING_CHANGE"
    AUTONOMY_CHANGE = "AUTONOMY_CHANGE"
    IRREVERSIBLE = "IRREVERSIBLE"
    UNSPECIFIED_OPERATION = "UNSPECIFIED_OPERATION"
    # Acoes de baixo risco, sujeitas ao nivel de autonomia:
    BID_ADJUSTMENT = "BID_ADJUSTMENT"
    CREATIVE_ROTATION = "CREATIVE_ROTATION"
    BUDGET_DECREASE = "BUDGET_DECREASE"
    PAUSE = "PAUSE"
    REPORT_ONLY = "REPORT_ONLY"


#: Exigem humano em qualquer nivel. Lista fechada (Ordem Mestra, secao 6).
ALWAYS_REQUIRE_HUMAN: frozenset[ActionKind] = frozenset(
    {
        ActionKind.CREATE_CAMPAIGN,
        ActionKind.FIRST_PUBLISH,
        ActionKind.BUDGET_INCREASE,
        ActionKind.SWITCH_AD_ACCOUNT,
        ActionKind.SENSITIVE_AUDIENCE,
        ActionKind.CUSTOMER_LIST,
        ActionKind.CUSTOMER_MATCH,
        ActionKind.TARGETING_CHANGE,
        ActionKind.AUTONOMY_CHANGE,
        ActionKind.IRREVERSIBLE,
        ActionKind.UNSPECIFIED_OPERATION,
    }
)

#: Acoes que o nivel 2 pode executar sozinho, desde que dentro de limites pre-autorizados.
LEVEL_2_ALLOWED: frozenset[ActionKind] = frozenset(
    {ActionKind.BID_ADJUSTMENT, ActionKind.CREATIVE_ROTATION, ActionKind.BUDGET_DECREASE}
)

#: O nivel 3 acrescenta rotinas de baixo risco.
LEVEL_3_ALLOWED: frozenset[ActionKind] = LEVEL_2_ALLOWED | {
    ActionKind.PAUSE,
    ActionKind.REPORT_ONLY,
}


@dataclass(frozen=True)
class AutonomySettings:
    level: AutonomyLevel = DEFAULT_LEVEL
    #: Teto contratado. O cliente configura dentro dele, nunca acima (ADR-0013).
    max_level_allowed: AutonomyLevel = AutonomyLevel.APROVADO
    max_budget_change_pct: Decimal = Decimal("10")

    def __post_init__(self) -> None:
        if self.level > self.max_level_allowed:
            raise ValueError(
                "Nivel de autonomia acima do teto contratado. "
                "Configuravel significa ajustavel dentro de limites, nao acima deles."
            )


@dataclass(frozen=True)
class AutonomyDecision:
    requires_human: bool
    reason: str
    requires_dual_approval: bool = False


def evaluate(
    action: ActionKind,
    settings: AutonomySettings,
    *,
    within_preauthorized_limits: bool = False,
    change_pct: Decimal | None = None,
    high_risk: bool = False,
) -> AutonomyDecision:
    """Decide se a acao pode seguir sozinha ou exige aprovacao humana.

    Deterministico. Nao consulta LLM, nao depende de contexto conversacional.
    """
    if action in ALWAYS_REQUIRE_HUMAN:
        return AutonomyDecision(
            requires_human=True,
            reason=f"{action.value} exige aprovacao humana em qualquer nivel de autonomia.",
            requires_dual_approval=high_risk,
        )

    if settings.level <= AutonomyLevel.APROVADO:
        return AutonomyDecision(
            requires_human=True,
            reason=f"Nivel {int(settings.level)} publica somente apos aprovacao humana.",
        )

    permitido = LEVEL_2_ALLOWED if settings.level == AutonomyLevel.LIMITADO else LEVEL_3_ALLOWED
    if action not in permitido:
        return AutonomyDecision(
            requires_human=True,
            reason=f"{action.value} nao esta na lista permitida do nivel {int(settings.level)}.",
        )

    if not within_preauthorized_limits:
        return AutonomyDecision(
            requires_human=True,
            reason="Acao fora dos limites pre-autorizados.",
        )

    if change_pct is not None and abs(change_pct) > settings.max_budget_change_pct:
        return AutonomyDecision(
            requires_human=True,
            reason=(
                f"Variacao de {change_pct}% excede o maximo configurado "
                f"de {settings.max_budget_change_pct}%."
            ),
        )

    return AutonomyDecision(
        requires_human=False,
        reason=f"Acao de baixo risco dentro dos limites do nivel {int(settings.level)}.",
    )
