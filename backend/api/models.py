"""Pydantic request/response schemas for the BFF contract.

None of these ever declare a `tenant_id` field on an input model -- that is the mechanism
that makes invariant #1 (tenant_id never accepted from the client) structural rather than
just a runtime check. Extra fields are forbidden on request bodies so a client-supplied
`tenant_id` is rejected by validation rather than silently dropped.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- /me


class MeResponse(BaseModel):
    user_id: str
    tenant_id: str
    business_unit_id: str | None
    roles: list[str]
    permissions: list[str]
    mfa_enabled: bool


# --------------------------------------------------------------------------- auth / sessao (item 1.3/WP-02)


class SessionLoginRequest(ApiModel):
    #: ID token do Google Identity Platform, obtido pelo frontend apos o usuario
    #: autenticar -- nunca um token opaco de dev/teste (isso e o header Bearer legado).
    id_token: str


class SessionLoginResponse(BaseModel):
    user_id: str
    tenant_id: str
    business_unit_id: str | None
    roles: list[str]
    #: Cliente deve devolver este valor no header X-CSRF-Token em toda mutacao
    #: subsequente (double-submit cookie, ver api/session.py).
    csrf_token: str


# --------------------------------------------------------------------------- onboarding comercial (F1)


class TenantOnboardingRequest(ApiModel):
    id_token: str = Field(min_length=1)
    company_name: str = Field(min_length=1, max_length=160)
    document: str | None = Field(default=None, max_length=32)
    segment: str = Field(min_length=1, max_length=120)
    language: str = Field(default="pt-BR", min_length=2, max_length=20)
    timezone: str = Field(default="America/Sao_Paulo", min_length=1, max_length=80)
    entry_mode: Literal["TRIAL", "PURCHASE"] = "TRIAL"


class OrganizationResponse(BaseModel):
    tenant_id: str
    name: str
    document: str | None
    segment: str
    language: str
    timezone: str
    entry_mode: str
    plan_id: str | None
    status: str
    default_business_unit_id: str | None
    created_at: datetime


class MembershipResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    roles: list[str]
    business_unit_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None


class TenantOnboardingResponse(BaseModel):
    session: SessionLoginResponse
    organization: OrganizationResponse
    membership: MembershipResponse


class InvitationCreateRequest(ApiModel):
    email: str = Field(min_length=3, max_length=254)
    roles: list[str] = Field(min_length=1)
    business_unit_id: str | None = None


class InvitationResponse(BaseModel):
    id: str
    email: str
    roles: list[str]
    business_unit_id: str | None
    status: str
    created_at: datetime
    expires_at: datetime
    accepted_by: str | None
    # O token bruto e devolvido SOMENTE na primeira criacao para que o Owner/Admin possa
    # compartilhar o link. O repositorio guarda apenas SHA-256; replay idempotente devolve
    # null em vez de persistir este segredo em claro no idempotency store.
    accept_token: str | None = None


class InvitationAcceptRequest(ApiModel):
    id_token: str = Field(min_length=1)
    accept_token: str = Field(min_length=16, max_length=512)


# --------------------------------------------------------------------------- F2 organization / IAM administration


class BusinessUnitResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime


class BusinessUnitCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)


class BusinessUnitRenameRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)


class MembershipAccessUpdateRequest(ApiModel):
    roles: list[str] = Field(min_length=1)
    business_unit_id: str



# --------------------------------------------------------------------------- vinculos multi-tenant (WP-03)


class MembershipItem(BaseModel):
    #: Identificador estavel do VINCULO (nunca do e-mail/identidade) -- e' o valor que o
    #: cliente devolve em SwitchMembershipRequest.user_id para selecionar este vinculo.
    user_id: str
    tenant_id: str
    business_unit_id: str | None
    roles: list[str]
    #: True para exatamente um item da lista: o vinculo ativo na sessao agora.
    active: bool


class MembershipsResponse(BaseModel):
    memberships: list[MembershipItem]


class SwitchMembershipRequest(ApiModel):
    #: user_id do vinculo-alvo (um dos devolvidos por GET /me/memberships) -- nunca um
    #: tenant_id livre: a troca so aceita um vinculo que ja pertença a esta identidade,
    #: nunca um tenant arbitrario informado pelo cliente (mesma disciplina de
    #: `reject_client_tenant_id`, api/deps.py).
    user_id: str


# --------------------------------------------------------------------------- brand profiles


class BrandProfileCreate(ApiModel):
    name: str
    # Contract declares `required: [name, tone]` (bff-openapi.yaml BrandProfileInput) --
    # no default here, so a missing tone is a 422 VALIDATION_FAILED, not a silent "".
    tone: str
    colors: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)


class BrandProfileResponse(BaseModel):
    # Contract's BrandProfile schema names the identifier `id` (achado 1).
    id: str
    name: str
    tone: str
    colors: list[str]
    differentiators: list[str]
    restrictions: list[str]
    created_at: datetime


# --------------------------------------------------------------------------- connections


class ConnectionResponse(BaseModel):
    # Contract's Connection schema names the identifier `id` (achado 1). The path param
    # `connectionId` is unaffected -- only the response body field changes.
    id: str
    provider: str
    external_account_id: str
    display_name: str
    status: str
    api_version: str
    # Contract declares `last_synced_at` nullable (achado 6).
    last_synced_at: datetime | None


class OAuthStartRequest(ApiModel):
    provider: str
    display_name: str = ""


class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCallbackRequest(ApiModel):
    #: `state` devolvido por POST /connections/oauth/start -- resgatado uma unica vez,
    #: amarrado ao tenant que iniciou o fluxo (nunca aceito de outro tenant).
    state: str
    #: Conta selecionada pelo usuario no provedor (simulado nesta etapa -- nenhum
    #: provider real e contatado). Nunca inventada pelo backend: sempre o que o
    #: cliente envia apos a "selecao" na tela (real, quando existir, ou simulada, como
    #: hoje).
    external_account_id: str
    display_name: str


#: SECURITY FIX (Fase 3, achado 4, 27/09/2026 -- auditoria independente): o campo
#: `credential` que este endpoint aceitava foi RETIRADO do contrato publico. O TARGET
#: comercial nunca deixa um token real do provedor trafegar pelo browser at' este
#: endpoint -- a troca real de OAuth e' server-side (ver ADR-0013, adendo). O mecanismo
#: abaixo (`DevAttachCredentialRequest`) e' explicitamente dev/test-only, usado so por
#: `POST /connections/{connectionId}/dev-attach-credential` (nao documentado no
#: contrato OpenAPI publico, fail-closed fora de test/dev-local) -- existe so para o
#: Vault poder ser testado de ponta a ponta sem inventar uma troca de OAuth real.
class DevAttachCredentialRequest(ApiModel):
    credential: dict


class CapabilityResponse(BaseModel):
    provider: str
    capability_key: str
    country: str
    api_version: str
    supported: bool
    # ACHADO 20 (Fase 3, 26/09/2026): nullable -- quando nenhum registro real de
    # capacidade existe para o modo de conexao consultado (routes_connections.py::
    # connection_capabilities), o backend nunca fabrica um "verificado agora"; None
    # significa honestamente "nunca verificado".
    verified_at: datetime | None
    requires_approval: bool
    # Contract's Capability schema adds `evidence_url` (nullable). There is no real
    # evidence-URL source yet (no capability-evidence tracking in campaia_core), so this
    # is always None for now (achado 7) -- documented here rather than invented.
    evidence_url: str | None
    notes: str | None


# --------------------------------------------------------------------------- briefs / campaigns


class BriefCreate(ApiModel):
    objective: str
    product: str = ""
    audience: str = ""
    region: str = "BR"
    currency: str = "BRL"
    total_budget: Decimal = Decimal("10000")
    daily_cap: Decimal = Decimal("1000")
    channels: list[str] = Field(default_factory=lambda: ["GOOGLE_ADS"])
    connection_id: str | None = None
    business_unit_id: str | None = None
    # Contract's Campaign schema has top-level `name` -- BriefCreate has no dedicated
    # `name` field today, so we accept an optional one and fall back to a derived default
    # in the serializer (see helpers.serialize_campaign) rather than inventing a required
    # field the contract's `/briefs` requestBody (a bare `type: object`) does not mandate.
    name: str = ""


class ExternalResourceResponse(BaseModel):
    channel: str
    external_resource_id: str
    sync_status: str
    last_synced_at: datetime | None


class BudgetResponse(BaseModel):
    currency: str
    total_amount: Decimal
    daily_cap: Decimal
    spent_to_date: Decimal


class CampaignResponse(BaseModel):
    # Contract's Campaign schema names the identifier `id` (achado 1).
    id: str
    business_unit_id: str | None
    state: str
    name: str
    objective: str
    brief: dict
    # Contract renames `planned_channels` -> `channels` (achado 5).
    channels: list[str]
    plan_version: int
    connection_id: str | None
    # Contract replaces the flat {channel: id} dict with an array of objects carrying
    # sync_status and last_synced_at per channel (achado 5).
    external_resources: list[ExternalResourceResponse]
    budget: BudgetResponse
    last_synced_at: datetime | None
    created_at: datetime


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    next_cursor: str | None = None


class PlanResponse(BaseModel):
    campaign_id: str
    plan_version: int
    plan: dict | None


class PolicyFindingResponse(BaseModel):
    code: str
    severity: str
    explanation: str


class PolicyDecisionResponse(BaseModel):
    policy_decision_id: str | None
    outcome: str
    campaign_id: str
    plan_version: int
    issued_at: datetime
    expires_at: datetime | None
    requires_human_approval: bool
    requires_dual_approval: bool
    findings: list[PolicyFindingResponse]


class PublishRequest(ApiModel):
    policy_decision_id: str
    approval_id: str
    external_account_id: str | None = None


class BudgetPatchRequest(ApiModel):
    # Achado 18: contract names this field `daily_cap` (bff-openapi.yaml updateBudget
    # requestBody, required: [daily_cap, approval_id]), not `new_daily_cap`. A client
    # sending the contract's literal `daily_cap` was previously rejected outright --
    # `extra="forbid"` refused the unknown field and `new_daily_cap` was still missing.
    # Fixed by aliasing `new_daily_cap` to `daily_cap` and setting `populate_by_name=True`,
    # so both spellings validate: the contract's `daily_cap` and the attribute name
    # `new_daily_cap` already used by existing callers/tests. `extra="forbid"` (inherited
    # from ApiModel) still rejects anything else.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    approval_id: str
    new_daily_cap: Decimal = Field(alias="daily_cap")


class KillSwitchRequest(ApiModel):
    # Contract enum is uppercase: CAMPAIGN, ACCOUNT, TENANT, PLATFORM, GLOBAL (achado 13).
    scope: str
    # Contract names this field `target_id`, not `campaign_id` -- it is interpreted
    # per-scope in the handler (campaign id, connection/account id, or unused).
    target_id: str | None = None
    reason: str = ""


# --------------------------------------------------------------------------- approvals


class ApprovalResponse(BaseModel):
    # Contract's ApprovalRequest schema names the identifier `id` (achado 1). campaign_id
    # here refers to ANOTHER entity (the campaign this approval is about), so it keeps
    # its name per the achado 1 instructions.
    id: str
    campaign_id: str
    # Contract replaces `kind` with a free-text `reason` describing why approval was
    # required (achado 9). We keep `kind` too (extra, not in the contract) since removing
    # internal bookkeeping fields is unnecessary and nothing in the contract forbids
    # additional properties on responses; `reason` is what conformance actually checks.
    kind: str
    reason: str
    requested_by: str
    amount: str | None
    plan_version: int
    status: str
    decided_by: list[str]
    requires_dual_approval: bool
    created_at: datetime
    expires_at: datetime


class ApprovalDecisionRequest(ApiModel):
    decision: str  # "APPROVE" | "REJECT" | "REQUEST_CHANGES"
    reason: str | None = Field(default=None, max_length=1000)


class ApprovalCreateRequest(ApiModel):
    campaign_id: str
    kind: str  # PUBLISH | BUDGET_CHANGE | AUTONOMY_CHANGE
    amount: Optional[Decimal] = None
    requires_dual_approval: bool = False


# --------------------------------------------------------------------------- autonomy


class AutonomyResponse(BaseModel):
    level: int
    level_label: str
    max_level_allowed: int
    always_require_human: list[str]
    # Contract declares this as a number (achado 11) -- was serialized as `str`.
    max_budget_change_pct: float
    updated_at: datetime


class AutonomyUpdateRequest(ApiModel):
    level: int
    # Contract requires `approval_id` for /autonomy PUT (achado 12): the level change
    # must reference an already-APPROVED ApprovalRequest, exactly like publish/budget.
    approval_id: str


# --------------------------------------------------------------------------- insights


class InsightPoint(BaseModel):
    date: str
    channel: str
    impressions: int
    clicks: int
    spend: Decimal
    conversions: int
    cpa: Decimal | None


class InsightSeriesResponse(BaseModel):
    campaign_id: str
    points: list[InsightPoint]
    last_synced_at: datetime | None
    note: str


# --------------------------------------------------------------------------- audit


class AuditEventResponse(BaseModel):
    # Contract's AuditEvent schema names the identifier `id` (achado 1).
    id: str
    occurred_at: datetime
    actor_kind: str
    actor_id: str | None
    action: str
    target: str
    policy_decision_id: str | None
    # Contract declares this nullable ([object, 'null']); AuditLog.append always stores {}
    # rather than None today, but the response type should still allow null per-contract.
    evidence: dict | None


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict
    assisted_flow_url: str | None


# --------------------------------------------------------------------------- billing (B11)


class BillingSubscriptionUpsert(ApiModel):
    plan_id: str
    #: CPF ou CNPJ do cliente cobrado — obrigatorio, mesma exigencia do dominio
    #: (subscription.Subscription, payment_gateway.ChargeCommand).
    customer_document: str
    #: Trial e opt-in explicito. False cria assinatura PENDING_PAYMENT.
    #: A duracao nunca vem do cliente; vem do catalogo comercial do plano.
    start_trial: bool = False
    initial_only: bool = False
    expected_plan_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class BillingPlanChangeRequest(ApiModel):
    target_plan_id: str


class BillingEntitlementsResponse(BaseModel):
    max_users: int | None
    max_active_campaigns: int | None
    channels: list[str]
    ai_capabilities: list[str]
    resources: list[str]


class BillingPlanChangeRuleResponse(BaseModel):
    target_plan_id: str
    kind: str
    billing_mode: str | None


class BillingPlanResponse(BaseModel):
    fingerprint: str
    plan_id: str
    name: str
    currency: str
    monthly_price: str
    included_credits: str
    extra_credit_unit_price: str
    trial_days: int | None
    credit_policy: dict | None = None
    cancellation_mode: str | None
    reactivation_mode: str | None
    reactivation_billing_mode: str | None
    plan_changes: list[BillingPlanChangeRuleResponse]


class BillingSubscriptionResponse(BaseModel):
    commercial_terms: BillingPlanResponse
    tenant_id: str
    customer_ref: str
    customer_document: str
    plan_id: str
    plan_name: str
    status: str
    trial_started_at: datetime | None = None
    trial_ends_at: datetime | None = None
    activated_at: datetime | None = None
    pending_plan_id: str | None = None
    pending_plan_name: str | None = None
    pending_plan_change_kind: str | None = None
    pending_plan_change_billing_mode: str | None = None
    canceled_at: datetime | None = None
    reactivation_requested_at: datetime | None = None
    past_due_at: datetime | None = None
    grace_period_ends_at: datetime | None = None
    past_due_in_grace: bool = False
    past_due_access_mode: str | None = None
    dunning_reminders_sent: int = 0
    next_dunning_reminder_at: datetime | None = None
    entitlement_access_active: bool
    entitlements: BillingEntitlementsResponse | None = None


class BillingCreditConsentRequest(ApiModel):
    cycle_id: str = Field(min_length=1, max_length=256)
    policy_version: str = Field(min_length=1, max_length=256)
    extra_credit_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    cap: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class BillingChargeCreate(ApiModel):
    competence: str
    extra_credits_used: Decimal = Decimal("0")


class BillingChargeResponse(BaseModel):
    billing_id: str
    tenant_id: str
    competence: str
    currency: str
    amount: Decimal
    gateway_charge_id: str
    gateway_status: str


class BillingChargeHistoryItem(BaseModel):
    billing_id: str
    gateway_charge_id: str
    competence: str
    currency: str
    amount: str
    plan_id: str | None
    purpose: str
    created_at: datetime | None
    gateway_status: str | None
    gateway_provider: str | None
    gateway_mode: str | None
    status_observed_at: datetime | None
    status_source: str | None
    invoice_url: str | None


class BillingChargeHistoryResponse(BaseModel):
    items: list[BillingChargeHistoryItem]
    next_cursor: str | None
