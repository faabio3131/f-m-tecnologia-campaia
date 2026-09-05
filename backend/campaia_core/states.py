"""Maquina de estados da campanha.

Invariantes materializados aqui (Plano Mestre, secao 4):

  I-12  Nunca declarar publicacao sem confirmacao externa.
        PUBLISHING -> ACTIVE exige recurso externo CONFIRMED em TODOS os canais planejados.
        Confirmacao parcial mantem a campanha em PUBLISHING, com a Saga aberta.

  I-09  Publicar exige decisao de politica valida E aprovacao humana registrada.
        APPROVED -> PUBLISHING passa por guarda, nao por confianca no chamador.

  Kill switch  So REDUZ efeito. Pode levar a PAUSED a partir de qualquer estado publicavel,
               mas nunca amplia efeito nem pula aprovacao.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .errors import GuardFailed, InvalidStateTransition


class CampaignState(str, Enum):
    DRAFT = "DRAFT"
    STRATEGY_READY = "STRATEGY_READY"
    ASSETS_READY = "ASSETS_READY"
    VALIDATED = "VALIDATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    PUBLISHING = "PUBLISHING"
    ACTIVE = "ACTIVE"
    OPTIMIZING = "OPTIMIZING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SyncStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DIVERGENT = "DIVERGENT"


@dataclass(frozen=True)
class ExternalResource:
    """Espelho local de um recurso que existe na plataforma externa."""

    channel: str
    external_resource_id: str | None
    sync_status: SyncStatus


@dataclass
class TransitionContext:
    """Tudo que as guardas precisam. Nenhuma guarda consulta servico externo."""

    planned_channels: tuple[str, ...] = ()
    external_resources: tuple[ExternalResource, ...] = ()
    policy_decision_valid: bool = False
    human_approval_id: str | None = None
    kill_switch_active: bool = False
    failure_is_terminal: bool = False


#: Grafo de transicoes permitidas. O que nao esta aqui e proibido, por omissao.
TRANSITIONS: dict[CampaignState, frozenset[CampaignState]] = {
    CampaignState.DRAFT: frozenset({CampaignState.STRATEGY_READY, CampaignState.FAILED}),
    CampaignState.STRATEGY_READY: frozenset(
        {CampaignState.ASSETS_READY, CampaignState.DRAFT, CampaignState.FAILED}
    ),
    CampaignState.ASSETS_READY: frozenset(
        {CampaignState.VALIDATED, CampaignState.DRAFT, CampaignState.FAILED}
    ),
    CampaignState.VALIDATED: frozenset(
        {CampaignState.AWAITING_APPROVAL, CampaignState.DRAFT, CampaignState.FAILED}
    ),
    CampaignState.AWAITING_APPROVAL: frozenset(
        {CampaignState.APPROVED, CampaignState.DRAFT, CampaignState.FAILED}
    ),
    CampaignState.APPROVED: frozenset(
        {CampaignState.PUBLISHING, CampaignState.PAUSED, CampaignState.FAILED}
    ),
    CampaignState.PUBLISHING: frozenset(
        {CampaignState.ACTIVE, CampaignState.PAUSED, CampaignState.FAILED}
    ),
    CampaignState.ACTIVE: frozenset(
        {
            CampaignState.OPTIMIZING,
            CampaignState.PAUSED,
            CampaignState.COMPLETED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.OPTIMIZING: frozenset(
        {
            CampaignState.ACTIVE,
            CampaignState.PAUSED,
            CampaignState.COMPLETED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.PAUSED: frozenset(
        {CampaignState.ACTIVE, CampaignState.COMPLETED, CampaignState.FAILED}
    ),
    CampaignState.COMPLETED: frozenset(),
    CampaignState.FAILED: frozenset(),
}

#: Estados a partir dos quais existe efeito externo vivo, logo o kill switch se aplica.
PAUSABLE_STATES: frozenset[CampaignState] = frozenset(
    {
        CampaignState.APPROVED,
        CampaignState.PUBLISHING,
        CampaignState.ACTIVE,
        CampaignState.OPTIMIZING,
    }
)


def _guard_publishing(ctx: TransitionContext) -> None:
    if ctx.kill_switch_active:
        raise GuardFailed("Kill switch ativo: publicacao bloqueada.")
    if not ctx.policy_decision_valid:
        raise GuardFailed("Publicacao exige decisao de politica valida e nao expirada.")
    if not ctx.human_approval_id:
        raise GuardFailed("Publicacao exige aprovacao humana registrada.")


def _guard_active(ctx: TransitionContext) -> None:
    """ACTIVE so e declarado com ID externo confirmado em TODOS os canais planejados."""
    if not ctx.planned_channels:
        raise GuardFailed("Campanha sem canais planejados nao pode ficar ativa.")

    confirmed = {
        r.channel
        for r in ctx.external_resources
        if r.sync_status is SyncStatus.CONFIRMED and r.external_resource_id
    }
    faltando = sorted(set(ctx.planned_channels) - confirmed)
    if faltando:
        raise GuardFailed(
            "Publicacao parcial: canais sem ID externo confirmado. "
            "A campanha permanece em PUBLISHING com a Saga aberta.",
            missing_channels=faltando,
        )


def _guard_resume(ctx: TransitionContext) -> None:
    if ctx.kill_switch_active:
        raise GuardFailed("Kill switch ativo: retomada bloqueada.")


GUARDS = {
    (CampaignState.APPROVED, CampaignState.PUBLISHING): _guard_publishing,
    (CampaignState.PUBLISHING, CampaignState.ACTIVE): _guard_active,
    (CampaignState.PAUSED, CampaignState.ACTIVE): _guard_resume,
}


@dataclass
class Campaign:
    campaign_id: str
    tenant_id: str
    state: CampaignState = CampaignState.DRAFT
    history: list[tuple[CampaignState, CampaignState, str]] = field(default_factory=list)

    def transition_to(
        self,
        target: CampaignState,
        ctx: TransitionContext | None = None,
        *,
        reason: str = "",
    ) -> CampaignState:
        ctx = ctx or TransitionContext()
        allowed = TRANSITIONS[self.state]

        if target not in allowed:
            raise InvalidStateTransition(
                f"Transicao {self.state.value} -> {target.value} nao e permitida.",
                current=self.state.value,
                target=target.value,
            )

        guard = GUARDS.get((self.state, target))
        if guard is not None:
            guard(ctx)

        previous = self.state
        self.state = target
        self.history.append((previous, target, reason))
        return self.state

    def apply_kill_switch(self, *, reason: str) -> CampaignState:
        """Unico caminho que dispensa a fila normal de decisao, porque so reduz efeito."""
        if self.state not in PAUSABLE_STATES:
            raise InvalidStateTransition(
                f"Kill switch nao se aplica ao estado {self.state.value}.",
                current=self.state.value,
            )
        previous = self.state
        self.state = CampaignState.PAUSED
        self.history.append((previous, CampaignState.PAUSED, f"KILL_SWITCH: {reason}"))
        return self.state
