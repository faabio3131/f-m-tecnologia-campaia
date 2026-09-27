"""Policy Engine deterministico.

Este modulo e o portao entre "a IA propos" e "o sistema executa". Ele nao chama LLM,
nao le prompt e nao aceita explicacao em linguagem natural como evidencia.

Ele emite o `policy_decision_id`, que e a unica autorizacao aceita pelo Ads Connector Hub.
A decisao expira e fica presa a uma versao especifica do plano: aprovar a versao 3 nao
autoriza publicar a versao 4.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum

from .autonomy import ActionKind, AutonomySettings, evaluate as evaluate_autonomy
from .budget import BudgetEngine

DEFAULT_TTL = timedelta(minutes=30)


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class Outcome(StrEnum):
    APPROVABLE = "APPROVABLE"
    NEEDS_CHANGES = "NEEDS_CHANGES"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    explanation: str


@dataclass(frozen=True)
class PolicyDecision:
    policy_decision_id: str | None
    outcome: Outcome
    tenant_id: str
    campaign_id: str
    plan_version: int
    issued_at: datetime
    expires_at: datetime | None
    requires_human_approval: bool
    requires_dual_approval: bool
    findings: tuple[Finding, ...] = ()

    def is_valid_for(
        self, *, now: datetime, campaign_id: str, plan_version: int, tenant_id: str
    ) -> bool:
        """Toda condicao precisa bater. Qualquer divergencia invalida a autorizacao."""
        return (
            self.policy_decision_id is not None
            and self.outcome is Outcome.APPROVABLE
            and self.expires_at is not None
            and now < self.expires_at
            and self.campaign_id == campaign_id
            and self.plan_version == plan_version
            and self.tenant_id == tenant_id
        )


@dataclass
class PolicyRequest:
    tenant_id: str
    campaign_id: str
    plan_version: int
    action: ActionKind
    autonomy: AutonomySettings
    budget: BudgetEngine
    requested_amount: Decimal = Decimal("0")
    #: Canais que o plano quer usar, e o que o Capability Registry diz sobre cada um.
    channel_support: dict[str, bool] = field(default_factory=dict)
    #: Restricoes declaradas pelo cliente. Vao para ca, nunca so para o prompt.
    brand_restrictions: tuple[str, ...] = ()
    plan_text: str = ""
    sensitive_audience: bool = False
    uses_customer_list: bool = False
    has_legal_basis: bool = False
    kill_switch_active: bool = False
    high_risk: bool = False


class PolicyEngine:
    def __init__(self, *, ttl: timedelta = DEFAULT_TTL) -> None:
        self._ttl = ttl

    def evaluate(self, req: PolicyRequest, *, now: datetime | None = None) -> PolicyDecision:
        now = now or datetime.now(timezone.utc)
        findings: list[Finding] = []

        if req.kill_switch_active:
            findings.append(
                Finding("KILL_SWITCH_ACTIVE", Severity.BLOCKING, "Kill switch ativo neste escopo.")
            )

        for channel, supported in req.channel_support.items():
            if not supported:
                findings.append(
                    Finding(
                        "CAPABILITY_UNSUPPORTED",
                        Severity.BLOCKING,
                        f"Canal {channel} nao tem capacidade comprovada para esta conta. "
                        "Acao nao e oferecida nem simulada.",
                    )
                )

        if req.requested_amount > 0:
            if req.requested_amount > req.budget.available_total:
                findings.append(
                    Finding(
                        "BUDGET_LIMIT",
                        Severity.BLOCKING,
                        "Valor solicitado excede o orcamento total autorizado.",
                    )
                )
            elif req.requested_amount > req.budget.available_today:
                findings.append(
                    Finding(
                        "BUDGET_LIMIT",
                        Severity.BLOCKING,
                        "Valor solicitado excede o teto diario autorizado.",
                    )
                )

        texto = req.plan_text.casefold()
        for termo in req.brand_restrictions:
            if termo.casefold() in texto:
                findings.append(
                    Finding(
                        "BRAND_RESTRICTION",
                        Severity.BLOCKING,
                        f"O plano contem termo vetado pelo cliente: {termo!r}.",
                    )
                )

        if req.uses_customer_list and not req.has_legal_basis:
            findings.append(
                Finding(
                    "LEGAL_BASIS_MISSING",
                    Severity.BLOCKING,
                    "Uso de lista de clientes exige base legal registrada (LGPD).",
                )
            )

        if req.sensitive_audience:
            findings.append(
                Finding(
                    "SENSITIVE_AUDIENCE",
                    Severity.WARNING,
                    "Publico sensivel: aprovacao humana obrigatoria.",
                )
            )

        autonomy = evaluate_autonomy(
            req.action,
            req.autonomy,
            high_risk=req.high_risk or req.sensitive_audience,
        )

        bloqueado = any(f.severity is Severity.BLOCKING for f in findings)
        if bloqueado:
            return PolicyDecision(
                policy_decision_id=None,
                outcome=Outcome.BLOCKED,
                tenant_id=req.tenant_id,
                campaign_id=req.campaign_id,
                plan_version=req.plan_version,
                issued_at=now,
                expires_at=None,
                requires_human_approval=True,
                requires_dual_approval=False,
                findings=tuple(findings),
            )

        return PolicyDecision(
            policy_decision_id=str(uuid.uuid4()),
            outcome=Outcome.APPROVABLE,
            tenant_id=req.tenant_id,
            campaign_id=req.campaign_id,
            plan_version=req.plan_version,
            issued_at=now,
            expires_at=now + self._ttl,
            requires_human_approval=autonomy.requires_human,
            requires_dual_approval=autonomy.requires_dual_approval,
            findings=tuple(findings),
        )
