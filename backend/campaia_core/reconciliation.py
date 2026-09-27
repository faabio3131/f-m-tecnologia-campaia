"""Reconciliacao entre o estado interno e o estado real das plataformas.

Ameaca T-08: divergencia silenciosa. O banco diz que a campanha esta ativa; a plataforma
diz que foi pausada por politica. Ou pior: existe um anuncio rodando e gastando que o
sistema nao sabe que criou, porque a Saga caiu depois da criacao e antes do registro.

Duas direcoes de verdade, e confundi-las e a origem de quase todo bug de sincronizacao:

  ESTADO EXTERNO   A plataforma manda. Se o Google diz PAUSED, esta pausado - nao importa
                   o que o nosso banco acha.

  INTENCAO         Nos mandamos. O que o cliente aprovou, o orcamento autorizado e a
                   estrategia sao nossos. A plataforma nao decide isso.

Regra que atravessa tudo: **o reconciliador so reduz efeito ou corrige registro.**
Ele pode pausar; nunca pode criar, reativar ou aumentar verba para "fazer bater". Um
reconciliador que recria recursos vira uma maquina de gastar dinheiro sozinha durante um
incidente - exatamente quando ninguem esta olhando.

O caso mais caro e o recurso orfao: gasto real que nao esta no nosso controle financeiro.
Ele nasce com severidade FINANCEIRA e sempre escala para humano.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .errors import TenantIsolationViolation


class ResourceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"


class DivergenceType(StrEnum):
    MISSING_EXTERNAL = "MISSING_EXTERNAL"
    ORPHAN_EXTERNAL = "ORPHAN_EXTERNAL"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    BUDGET_MISMATCH = "BUDGET_MISMATCH"
    UNCONFIRMED_PUBLICATION = "UNCONFIRMED_PUBLICATION"


class Severity(StrEnum):
    FINANCIAL = "FINANCIAL"
    STATE = "STATE"
    COSMETIC = "COSMETIC"


class Remediation(StrEnum):
    """Acoes possiveis. Note o que NAO existe: criar, reativar, aumentar verba."""

    ADOPT_EXTERNAL = "ADOPT_EXTERNAL"          # registrar internamente o que ja existe la
    UPDATE_INTERNAL_STATE = "UPDATE_INTERNAL_STATE"  # aceitar a verdade da plataforma
    PAUSE_EXTERNAL = "PAUSE_EXTERNAL"          # reduzir efeito
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


#: Somente estas podem ser aplicadas sem aprovacao, porque nenhuma amplia efeito.
AUTO_APPLICABLE: frozenset[Remediation] = frozenset(
    {Remediation.UPDATE_INTERNAL_STATE, Remediation.PAUSE_EXTERNAL, Remediation.ADOPT_EXTERNAL}
)


@dataclass(frozen=True)
class InternalResource:
    """O que o nosso banco acredita."""

    tenant_id: str
    campaign_id: str
    channel: str
    status: ResourceStatus
    external_resource_id: str | None = None
    daily_budget: Decimal | None = None


@dataclass(frozen=True)
class PlatformResource:
    """O que a plataforma respondeu. Fonte da verdade para estado externo."""

    channel: str
    external_resource_id: str
    status: ResourceStatus
    daily_budget: Decimal | None = None


@dataclass(frozen=True)
class Divergence:
    kind: DivergenceType
    severity: Severity
    channel: str
    campaign_id: str | None
    external_resource_id: str | None
    detail: str
    remediation: Remediation
    requires_human: bool

    @property
    def auto_applicable(self) -> bool:
        return self.remediation in AUTO_APPLICABLE and not self.requires_human


@dataclass
class ReconciliationRun:
    run_id: str
    tenant_id: str
    divergences: list[Divergence] = field(default_factory=list)
    compared: int = 0

    @property
    def clean(self) -> bool:
        return not self.divergences

    @property
    def financial(self) -> list[Divergence]:
        return [d for d in self.divergences if d.severity is Severity.FINANCIAL]

    @property
    def needs_human(self) -> list[Divergence]:
        return [d for d in self.divergences if d.requires_human]

    def by_kind(self, kind: DivergenceType) -> list[Divergence]:
        return [d for d in self.divergences if d.kind is kind]


class Reconciler:
    """Comparador deterministico. Nao chama IA e nao executa nada por conta propria."""

    def reconcile(
        self,
        *,
        tenant_id: str,
        internal: list[InternalResource],
        platform: list[PlatformResource],
    ) -> ReconciliationRun:
        if not tenant_id:
            raise TenantIsolationViolation("Reconciliacao sem tenant_id.")
        for recurso in internal:
            if recurso.tenant_id != tenant_id:
                raise TenantIsolationViolation(
                    "Reconciliacao recebeu recurso de outro tenant."
                )

        run = ReconciliationRun(run_id=str(uuid.uuid4()), tenant_id=tenant_id)
        por_id = {p.external_resource_id: p for p in platform}
        vistos: set[str] = set()

        for interno in internal:
            run.compared += 1

            if interno.external_resource_id is None:
                if interno.status is ResourceStatus.ACTIVE:
                    # Declaramos ativo sem ID externo confirmado: viola o invariante I-12.
                    run.divergences.append(
                        Divergence(
                            kind=DivergenceType.UNCONFIRMED_PUBLICATION,
                            severity=Severity.STATE,
                            channel=interno.channel,
                            campaign_id=interno.campaign_id,
                            external_resource_id=None,
                            detail="Campanha marcada como ativa sem ID externo confirmado.",
                            remediation=Remediation.UPDATE_INTERNAL_STATE,
                            requires_human=False,
                        )
                    )
                continue

            externo = por_id.get(interno.external_resource_id)
            if externo is None:
                # Some da plataforma: pode ter sido removido por politica ou pelo cliente
                # no portal. Nao recriamos - isso e decisao de negocio, nao de sincronia.
                run.divergences.append(
                    Divergence(
                        kind=DivergenceType.MISSING_EXTERNAL,
                        severity=Severity.STATE,
                        channel=interno.channel,
                        campaign_id=interno.campaign_id,
                        external_resource_id=interno.external_resource_id,
                        detail="Recurso nao existe mais na plataforma. Nao sera recriado.",
                        remediation=Remediation.UPDATE_INTERNAL_STATE,
                        requires_human=False,
                    )
                )
                continue

            vistos.add(externo.external_resource_id)
            self._comparar(run, interno, externo)

        for externo in platform:
            if externo.external_resource_id in vistos:
                continue
            # Orfao: existe la, gastando, e nao esta no nosso controle financeiro.
            run.divergences.append(
                Divergence(
                    kind=DivergenceType.ORPHAN_EXTERNAL,
                    severity=Severity.FINANCIAL,
                    channel=externo.channel,
                    campaign_id=None,
                    external_resource_id=externo.external_resource_id,
                    detail=(
                        "Recurso externo sem registro interno. Provavel Saga interrompida "
                        "apos a criacao. Gasto fora do controle ate ser adotado."
                    ),
                    remediation=Remediation.ADOPT_EXTERNAL,
                    requires_human=True,
                )
            )

        return run

    def _comparar(
        self, run: ReconciliationRun, interno: InternalResource, externo: PlatformResource
    ) -> None:
        if interno.status is not externo.status:
            if (
                interno.status is ResourceStatus.PAUSED
                and externo.status is ResourceStatus.ACTIVE
            ):
                # Achamos pausado, esta rodando e gastando. Reduzir efeito e seguro e
                # urgente: pausar de novo nao pode piorar nada.
                run.divergences.append(
                    Divergence(
                        kind=DivergenceType.STATUS_MISMATCH,
                        severity=Severity.FINANCIAL,
                        channel=interno.channel,
                        campaign_id=interno.campaign_id,
                        external_resource_id=externo.external_resource_id,
                        detail="Pausado internamente, ativo na plataforma: gasto nao previsto.",
                        remediation=Remediation.PAUSE_EXTERNAL,
                        requires_human=False,
                    )
                )
            else:
                # Qualquer outro descompasso: a plataforma manda no estado externo.
                run.divergences.append(
                    Divergence(
                        kind=DivergenceType.STATUS_MISMATCH,
                        severity=Severity.STATE,
                        channel=interno.channel,
                        campaign_id=interno.campaign_id,
                        external_resource_id=externo.external_resource_id,
                        detail=(
                            f"Interno={interno.status.value}, "
                            f"plataforma={externo.status.value}. A plataforma prevalece."
                        ),
                        remediation=Remediation.UPDATE_INTERNAL_STATE,
                        requires_human=False,
                    )
                )

        if (
            interno.daily_budget is not None
            and externo.daily_budget is not None
            and interno.daily_budget != externo.daily_budget
        ):
            # Verba NUNCA e ajustada automaticamente, nem para baixo: alterar orcamento e
            # uma decisao financeira, e decisao financeira exige humano.
            run.divergences.append(
                Divergence(
                    kind=DivergenceType.BUDGET_MISMATCH,
                    severity=Severity.FINANCIAL,
                    channel=interno.channel,
                    campaign_id=interno.campaign_id,
                    external_resource_id=externo.external_resource_id,
                    detail=(
                        f"Verba diaria diverge: interno={interno.daily_budget}, "
                        f"plataforma={externo.daily_budget}."
                    ),
                    remediation=Remediation.ESCALATE_HUMAN,
                    requires_human=True,
                )
            )
