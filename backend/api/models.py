"""Pydantic request/response schemas for the BFF contract.

None of these ever declare a `tenant_id` field on an input model -- that is the mechanism
that makes invariant #1 (tenant_id never accepted from the client) structural rather than
just a runtime check. Extra fields are forbidden on request bodies so a client-supplied
`tenant_id` is rejected by validation rather than silently dropped.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

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


# --------------------------------------------------------------------------- WP-03 tenant membership


class MembershipResponse(BaseModel):
    tenant_id: str
    business_unit_id: str | None
    roles: list[str]
    is_active: bool


class SessionMembershipsResponse(BaseModel):
    memberships: list[MembershipResponse]


class SwitchTenantRequest(ApiModel):
    tenant_id: str


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


class OAuthCompleteRequest(ApiModel):
    """WP-04: finalizes the /connections/oauth/start attempt named by `state`. No real
    provider exists yet -- this simulates the account-selection step a real callback would
    receive (contract's own description of /connections/oauth/start: "o callback e recebido
    pelo backend"), never a client-supplied provider or tenant (both come from the pending
    attempt `state` references, looked up server-side)."""

    state: str
    external_account_id: str
    display_name: str


class CapabilityResponse(BaseModel):
    provider: str
    capability_key: str
    country: str
    api_version: str
    supported: bool
    verified_at: datetime
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
    # Explicitly `str`, not `Decimal` -- same pattern already established by
    # ApprovalResponse.amount (achado P-36 fix, missão de reconciliação, 22/09/2026).
    # Pydantic v2 already serializes a Decimal field to this exact same JSON string by
    # default (no wire-format change), but declaring the type as `str` makes the real,
    # precision-preserving contract explicit rather than implicit, and matches
    # contracts/bff-openapi.yaml's corresponding `type: string` fix.
    currency: str
    total_amount: str
    daily_cap: str
    spent_to_date: str


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
