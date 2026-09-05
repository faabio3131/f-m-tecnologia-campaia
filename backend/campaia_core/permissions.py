"""Autorizacao: RBAC + ABAC.

RBAC responde "que papel voce tem". ABAC responde "sobre O QUE, de QUEM, de QUANTO e HA
QUANTO TEMPO voce se autenticou". Sozinho, o papel nao basta: um financeiro de um tenant
nao pode mexer na verba de outro, e um gerente autenticado ha tres horas nao deveria
aumentar orcamento sem reautenticar.

Invariantes materializados aqui:

  I-04  Isolamento por tenant. Recurso de outro tenant responde NOT_FOUND, nunca
        PERMISSION_DENIED - negar com "sem permissao" revela que o recurso existe.

  I-09  Aprovacao humana real. Quem propos nao aprova sozinho (segregacao de funcoes), e
        aprovacao dupla exige dois atores distintos de verdade.

  T-01  Step-up auth. Operacoes sensiveis exigem reautenticacao recente, nao apenas uma
        sessao aberta em algum momento do passado.

Nota de escopo (D-03 em aberto): este modelo cobre tenant unico com unidades de negocio.
Se o segmento inicial for agencias - um tenant operando varias empresas-clientes -, a
extensao e ADITIVA: entra um nivel de escopo acima de business_unit. Nada aqui e reescrito.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

#: Reautenticacao vale por este tempo. Depois disso, operacao sensivel pede de novo.
STEP_UP_MAX_AGE = timedelta(minutes=10)


class Permission(StrEnum):
    CAMPAIGN_VIEW = "CAMPAIGN_VIEW"
    CAMPAIGN_CREATE = "CAMPAIGN_CREATE"
    CAMPAIGN_EDIT = "CAMPAIGN_EDIT"
    CAMPAIGN_PUBLISH = "CAMPAIGN_PUBLISH"
    BUDGET_VIEW = "BUDGET_VIEW"
    BUDGET_CHANGE = "BUDGET_CHANGE"
    APPROVAL_DECIDE = "APPROVAL_DECIDE"
    CONNECTION_MANAGE = "CONNECTION_MANAGE"
    AUTONOMY_CHANGE = "AUTONOMY_CHANGE"
    BRAND_MANAGE = "BRAND_MANAGE"
    MEMBER_MANAGE = "MEMBER_MANAGE"
    AI_CONFIG = "AI_CONFIG"
    AUDIT_VIEW = "AUDIT_VIEW"
    KILL_SWITCH = "KILL_SWITCH"


class Role(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    FINANCE = "FINANCE"
    APPROVER = "APPROVER"
    MARKETER = "MARKETER"
    VIEWER = "VIEWER"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(
        {
            Permission.CAMPAIGN_VIEW,
            Permission.CAMPAIGN_CREATE,
            Permission.CAMPAIGN_EDIT,
            Permission.CAMPAIGN_PUBLISH,
            Permission.BUDGET_VIEW,
            Permission.BUDGET_CHANGE,
            Permission.APPROVAL_DECIDE,
            Permission.CONNECTION_MANAGE,
            Permission.BRAND_MANAGE,
            Permission.MEMBER_MANAGE,
            Permission.AI_CONFIG,
            Permission.AUDIT_VIEW,
            Permission.KILL_SWITCH,
        }
    ),
    Role.FINANCE: frozenset(
        {
            Permission.CAMPAIGN_VIEW,
            Permission.BUDGET_VIEW,
            Permission.BUDGET_CHANGE,
            Permission.APPROVAL_DECIDE,
            Permission.AUDIT_VIEW,
            Permission.KILL_SWITCH,
        }
    ),
    Role.APPROVER: frozenset(
        {
            Permission.CAMPAIGN_VIEW,
            Permission.BUDGET_VIEW,
            Permission.APPROVAL_DECIDE,
            Permission.AUDIT_VIEW,
            Permission.KILL_SWITCH,
        }
    ),
    Role.MARKETER: frozenset(
        {
            Permission.CAMPAIGN_VIEW,
            Permission.CAMPAIGN_CREATE,
            Permission.CAMPAIGN_EDIT,
            Permission.BRAND_MANAGE,
            Permission.BUDGET_VIEW,
        }
    ),
    Role.VIEWER: frozenset({Permission.CAMPAIGN_VIEW, Permission.BUDGET_VIEW}),
}

#: Exigem reautenticacao recente. Sessao antiga nao basta.
#: KILL_SWITCH deliberadamente FORA: ele so reduz efeito, e emergencia nao espera
#: reautenticacao. Exigir step-up para parar um gasto seria proteger a coisa errada.
REQUIRES_STEP_UP: frozenset[Permission] = frozenset(
    {
        Permission.CAMPAIGN_PUBLISH,
        Permission.BUDGET_CHANGE,
        Permission.CONNECTION_MANAGE,
        Permission.AUTONOMY_CHANGE,
        Permission.APPROVAL_DECIDE,
        Permission.MEMBER_MANAGE,
    }
)

#: Exigem MFA configurado no perfil (Ordem Mestra: admins e perfis financeiros).
REQUIRES_MFA: frozenset[Permission] = frozenset(
    {
        Permission.BUDGET_CHANGE,
        Permission.CONNECTION_MANAGE,
        Permission.MEMBER_MANAGE,
        Permission.AUTONOMY_CHANGE,
    }
)

#: Teto de valor que cada papel pode aprovar sozinho. None = sem teto.
ROLE_VALUE_CEILING: dict[Role, Decimal | None] = {
    Role.OWNER: None,
    Role.ADMIN: Decimal("10000"),
    Role.FINANCE: Decimal("50000"),
    Role.APPROVER: Decimal("5000"),
    Role.MARKETER: Decimal("0"),
    Role.VIEWER: Decimal("0"),
}


class DenialCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
    MFA_REQUIRED = "MFA_REQUIRED"
    VALUE_CEILING = "VALUE_CEILING"
    SEPARATION_OF_DUTIES = "SEPARATION_OF_DUTIES"


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: frozenset[Role]
    #: None significa "todas as unidades do tenant". Conjunto vazio significa nenhuma.
    business_unit_ids: frozenset[str] | None = None
    mfa_enabled: bool = False
    step_up_at: datetime | None = None

    @property
    def permissions(self) -> frozenset[Permission]:
        """Uniao dos papeis. Papeis somam permissoes, nunca subtraem."""
        resultado: set[Permission] = set()
        for role in self.roles:
            resultado |= ROLE_PERMISSIONS.get(role, frozenset())
        return frozenset(resultado)

    @property
    def value_ceiling(self) -> Decimal | None:
        """Maior teto entre os papeis. None (sem teto) vence qualquer numero."""
        tetos = [ROLE_VALUE_CEILING.get(r, Decimal("0")) for r in self.roles]
        if any(t is None for t in tetos):
            return None
        return max(tetos) if tetos else Decimal("0")


@dataclass(frozen=True)
class Resource:
    tenant_id: str
    business_unit_id: str | None = None
    resource_id: str | None = None
    #: Quem propos/criou. Base da segregacao de funcoes.
    created_by: str | None = None


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    code: DenialCode | None = None
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


_ALLOWED = AccessDecision(allowed=True, reason="Autorizado.")


def authorize(
    principal: Principal,
    permission: Permission,
    resource: Resource,
    *,
    now: datetime,
    amount: Decimal | None = None,
) -> AccessDecision:
    """Decide o acesso. Deterministico e sem efeito colateral.

    A ordem das checagens importa: tenant primeiro, para nunca revelar por engano que um
    recurso de outro cliente existe.
    """
    # 1. Isolamento por tenant. NOT_FOUND de proposito: negar com "sem permissao"
    #    confirmaria que o recurso existe em outro lugar.
    if principal.tenant_id != resource.tenant_id:
        return AccessDecision(
            False, DenialCode.NOT_FOUND, "Recurso nao encontrado neste tenant."
        )

    # 2. RBAC.
    if permission not in principal.permissions:
        return AccessDecision(
            False,
            DenialCode.PERMISSION_DENIED,
            f"Nenhum papel do usuario concede {permission.value}.",
        )

    # 3. Escopo de unidade de negocio.
    if (
        resource.business_unit_id is not None
        and principal.business_unit_ids is not None
        and resource.business_unit_id not in principal.business_unit_ids
    ):
        return AccessDecision(
            False,
            DenialCode.NOT_FOUND,
            "Recurso fora das unidades de negocio do usuario.",
        )

    # 4. MFA para perfis administrativos e financeiros.
    if permission in REQUIRES_MFA and not principal.mfa_enabled:
        return AccessDecision(
            False,
            DenialCode.MFA_REQUIRED,
            f"{permission.value} exige MFA configurado.",
        )

    # 5. Step-up: reautenticacao recente, nao apenas sessao aberta.
    if permission in REQUIRES_STEP_UP:
        if principal.step_up_at is None or (now - principal.step_up_at) > STEP_UP_MAX_AGE:
            return AccessDecision(
                False,
                DenialCode.STEP_UP_REQUIRED,
                f"{permission.value} exige reautenticacao recente.",
            )

    # 6. Teto de valor por papel.
    if amount is not None:
        teto = principal.value_ceiling
        if teto is not None and amount > teto:
            return AccessDecision(
                False,
                DenialCode.VALUE_CEILING,
                f"Valor {amount} excede o teto de {teto} do papel do usuario.",
            )

    return _ALLOWED


def can_approve(
    principal: Principal,
    resource: Resource,
    *,
    now: datetime,
    requester_id: str,
    already_decided_by: frozenset[str] = frozenset(),
    amount: Decimal | None = None,
) -> AccessDecision:
    """Aprovacao com segregacao de funcoes.

    Quem propos nao aprova a propria proposta, e ninguem vota duas vezes numa aprovacao
    dupla. Sem isso, "aprovacao dupla" seria a mesma pessoa clicando duas vezes.
    """
    base = authorize(principal, Permission.APPROVAL_DECIDE, resource, now=now, amount=amount)
    if not base.allowed:
        return base

    if principal.user_id == requester_id:
        return AccessDecision(
            False,
            DenialCode.SEPARATION_OF_DUTIES,
            "Quem propos a acao nao pode aprova-la.",
        )

    if principal.user_id in already_decided_by:
        return AccessDecision(
            False,
            DenialCode.SEPARATION_OF_DUTIES,
            "Este usuario ja registrou decisao nesta aprovacao.",
        )

    return _ALLOWED


def dual_approval_complete(decided_by: frozenset[str]) -> bool:
    """Aprovacao dupla exige dois atores DISTINTOS."""
    return len(decided_by) >= 2
