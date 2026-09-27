"""Saga de publicacao multicanal.

O caso que este modulo existe para tratar: Google publica, Meta falha. O que acontece?

A resposta NAO e improvisada durante a falha. Ela e politica configurada por tenant ANTES
da publicacao:

  PAUSE_ALL       pausa o que ja foi criado e mantem a campanha em PUBLISHING
  KEEP_PARTIAL    mantem ativo o que deu certo e sinaliza o que faltou
  ESCALATE_HUMAN  nao mexe em nada e chama um humano para decidir

Regra que atravessa as tres: recurso externo NUNCA e apagado silenciosamente. A compensacao
padrao e pausar, nao excluir. Excluir e irreversivel e destroi historico de aprendizado da
plataforma; pausar e reversivel.

E ACTIVE so e declarado quando TODOS os canais planejados tem ID externo confirmado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .budget import BudgetEngine
from .connectors import (
    AdsConnector,
    ConnectorError,
    ConnectorErrorCode,
    PublishCommand,
)
from .infra import IdempotencyStore
from .policy import PolicyDecision
from .states import (
    Campaign,
    CampaignState,
    ExternalResource,
    SyncStatus,
    TransitionContext,
)

MAX_RETRIES = 2


class CompensationPolicy(StrEnum):
    PAUSE_ALL = "PAUSE_ALL"
    KEEP_PARTIAL = "KEEP_PARTIAL"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"


@dataclass
class SagaStep:
    channel: str
    status: StepStatus = StepStatus.PENDING
    external_resource_id: str | None = None
    error_code: ConnectorErrorCode | None = None
    attempts: int = 0
    reservation_id: str | None = None


@dataclass
class SagaOutcome:
    saga_id: str
    campaign_state: CampaignState
    steps: list[SagaStep]
    events: list[dict]
    needs_human: bool = False
    open_saga: bool = False

    @property
    def confirmed_channels(self) -> list[str]:
        return [s.channel for s in self.steps if s.status is StepStatus.CONFIRMED]

    @property
    def failed_channels(self) -> list[str]:
        return [s.channel for s in self.steps if s.status is StepStatus.FAILED]


@dataclass
class PublicationSaga:
    tenant_id: str
    connector: AdsConnector
    budget: BudgetEngine
    idempotency: IdempotencyStore
    compensation_policy: CompensationPolicy = CompensationPolicy.PAUSE_ALL
    events: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------ eventos

    def _emit(self, event_type: str, campaign_id: str, **payload) -> None:
        """Envelope canonico reduzido (contracts/event-envelope.schema.json)."""
        self.events.append(
            {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "tenant_id": self.tenant_id,
                "campaign_id": campaign_id,
                "payload": payload,
            }
        )

    # ------------------------------------------------------------------ execucao

    def run(
        self,
        campaign: Campaign,
        *,
        channels: tuple[str, ...],
        decision: PolicyDecision,
        approval_id: str,
        plan_version: int,
        now,
        external_account_id: str,
        command_id: str,
        budget_per_channel: Decimal,
        payload: dict | None = None,
    ) -> SagaOutcome:
        if campaign.tenant_id != self.tenant_id:
            raise ValueError("Saga nao opera campanha de outro tenant.")

        autorizacao_valida = decision.is_valid_for(
            now=now,
            campaign_id=campaign.campaign_id,
            plan_version=plan_version,
            tenant_id=self.tenant_id,
        )

        # A guarda da maquina de estados e quem recusa. A Saga nao decide por conta propria.
        campaign.transition_to(
            CampaignState.PUBLISHING,
            TransitionContext(
                policy_decision_valid=autorizacao_valida, human_approval_id=approval_id
            ),
            reason=f"saga:{command_id}",
        )

        saga_id = str(uuid.uuid4())
        steps = [SagaStep(channel=c) for c in channels]
        self._emit(
            "PublicationStarted",
            campaign.campaign_id,
            saga_id=saga_id,
            channels=list(channels),
            policy_decision_id=decision.policy_decision_id,
        )

        for step in steps:
            self._publish_channel(
                campaign=campaign,
                step=step,
                decision=decision,
                plan_version=plan_version,
                external_account_id=external_account_id,
                command_id=command_id,
                budget_per_channel=budget_per_channel,
                payload=payload or {"stub": True},
            )

        return self._finish(campaign, saga_id, steps, channels)

    def _publish_channel(
        self,
        *,
        campaign: Campaign,
        step: SagaStep,
        decision: PolicyDecision,
        plan_version: int,
        external_account_id: str,
        command_id: str,
        budget_per_channel: Decimal,
        payload: dict,
    ) -> None:
        # Chave estavel por (comando, canal): repetir a Saga inteira nao duplica recurso.
        idempotency_key = f"{command_id}:{step.channel}"

        try:
            reserva = self.budget.reserve(
                budget_per_channel, command_id=idempotency_key
            )
            step.reservation_id = reserva.reservation_id
        except Exception as exc:  # BudgetLimitExceeded
            step.status = StepStatus.FAILED
            step.error_code = ConnectorErrorCode.VALIDATION_REJECTED
            self._emit(
                "ExternalOperationFailed",
                campaign.campaign_id,
                channel=step.channel,
                reason=str(exc),
                stage="budget_reservation",
            )
            return

        command = PublishCommand(
            tenant_id=self.tenant_id,
            campaign_id=campaign.campaign_id,
            channel=step.channel,
            external_account_id=external_account_id,
            idempotency_key=idempotency_key,
            policy_decision_id=decision.policy_decision_id or "",
            plan_version=plan_version,
            payload=payload,
        )

        while step.attempts <= MAX_RETRIES:
            step.attempts += 1
            try:
                resultado, _replay = self.idempotency.execute(
                    self.tenant_id,
                    idempotency_key,
                    lambda: self.connector.publish(command),
                )
                step.status = StepStatus.CONFIRMED
                step.external_resource_id = resultado.external_resource_id
                self._emit(
                    "PlatformResourceCreated",
                    campaign.campaign_id,
                    channel=step.channel,
                    external_resource_id=resultado.external_resource_id,
                    mode=str(resultado.mode),
                )
                return
            except ConnectorError as exc:
                step.error_code = exc.connector_code
                if not exc.retryable or step.attempts > MAX_RETRIES:
                    break

        step.status = StepStatus.FAILED
        # Verba reservada para um canal que falhou volta imediatamente para o cliente.
        if step.reservation_id:
            self.budget.release(step.reservation_id)
        self._emit(
            "ExternalOperationFailed",
            campaign.campaign_id,
            channel=step.channel,
            error_code=str(step.error_code),
            attempts=step.attempts,
        )

    def _finish(
        self,
        campaign: Campaign,
        saga_id: str,
        steps: list[SagaStep],
        channels: tuple[str, ...],
    ) -> SagaOutcome:
        confirmados = [s for s in steps if s.status is StepStatus.CONFIRMED]
        falhos = [s for s in steps if s.status is StepStatus.FAILED]

        if not falhos:
            campaign.transition_to(
                CampaignState.ACTIVE,
                TransitionContext(
                    planned_channels=channels,
                    external_resources=tuple(
                        ExternalResource(
                            s.channel, s.external_resource_id, SyncStatus.CONFIRMED
                        )
                        for s in confirmados
                    ),
                ),
                reason=f"saga:{saga_id}",
            )
            self._emit("CampaignActivated", campaign.campaign_id, saga_id=saga_id)
            return SagaOutcome(saga_id, campaign.state, steps, self.events)

        self._emit(
            "PublicationPartiallyFailed",
            campaign.campaign_id,
            saga_id=saga_id,
            confirmed=[s.channel for s in confirmados],
            failed=[s.channel for s in falhos],
            policy=str(self.compensation_policy),
        )

        needs_human = False
        if self.compensation_policy is CompensationPolicy.PAUSE_ALL:
            for s in confirmados:
                self.connector.pause(
                    PublishCommand(
                        tenant_id=self.tenant_id,
                        campaign_id=campaign.campaign_id,
                        channel=s.channel,
                        external_account_id="compensacao",
                        idempotency_key=f"{saga_id}:pause:{s.channel}",
                        policy_decision_id=f"compensation:{saga_id}",
                        plan_version=0,
                    )
                )
                s.status = StepStatus.COMPENSATED
            self._emit(
                "CompensationExecuted",
                campaign.campaign_id,
                saga_id=saga_id,
                action="PAUSE",
                note="Recurso externo pausado, nunca excluido.",
            )
        elif self.compensation_policy is CompensationPolicy.ESCALATE_HUMAN:
            needs_human = True

        # Em todos os casos a campanha permanece em PUBLISHING com a Saga aberta.
        return SagaOutcome(
            saga_id=saga_id,
            campaign_state=campaign.state,
            steps=steps,
            events=self.events,
            needs_human=needs_human,
            open_saga=True,
        )
