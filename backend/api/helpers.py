"""Small shared helpers: JSON body parsing/validation, domain-object serialization."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .errors import ApiError
from .repositories import ApprovalRequest, AuditEvent, BrandProfile, CampaignRecord, Connection

T = TypeVar("T", bound=BaseModel)


async def parse_body(request: Request, model: Type[T]) -> T:
    raw = await request.body()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise ApiError("VALIDATION_FAILED", f"Invalid JSON body: {exc}") from exc

    if not isinstance(payload, dict):
        raise ApiError("VALIDATION_FAILED", "Request body must be a JSON object.")

    # Structural rejection of a client-supplied tenant_id, in addition to the "extra
    # fields forbidden" behaviour on ApiModel -- gives a specific, on-brand error code
    # instead of pydantic's generic "extra fields not permitted".
    if "tenant_id" in payload:
        raise ApiError(
            "VALIDATION_FAILED",
            "tenant_id is derived from the authenticated principal and must not be "
            "supplied by the client.",
            details={"field": "tenant_id"},
        )

    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ApiError(
            "VALIDATION_FAILED",
            "Request body failed validation.",
            details={"errors": exc.errors(include_url=False, include_context=False)},
        ) from exc


def json_response(model: BaseModel, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(json.loads(model.model_dump_json()), status_code=status_code)


def list_response(models: list[BaseModel], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        [json.loads(m.model_dump_json()) for m in models], status_code=status_code
    )


# --------------------------------------------------------------------------- serializers


def serialize_brand_profile(p: BrandProfile):
    from .models import BrandProfileResponse

    return BrandProfileResponse(
        id=p.brand_profile_id,
        name=p.name,
        tone=p.tone,
        colors=p.colors,
        differentiators=p.differentiators,
        restrictions=p.restrictions,
        created_at=p.created_at,
    )


def serialize_connection(c: Connection):
    from .models import ConnectionResponse

    return ConnectionResponse(
        id=c.connection_id,
        provider=c.provider,
        external_account_id=c.external_account_id,
        display_name=c.display_name,
        status=c.status,
        api_version=c.api_version,
        last_synced_at=c.last_synced_at,
    )


def serialize_campaign(rec: CampaignRecord):
    from .models import BudgetResponse, CampaignResponse, ExternalResourceResponse

    # name/objective: the contract's Campaign schema has top-level `name` and `objective`.
    # BriefCreate.objective maps directly. There is no dedicated brief "name" field in the
    # legacy brief shape, so we fall back to BriefCreate.name (added, defaults to "") --
    # documented in models.BriefCreate rather than inventing a brief key that never existed.
    name = rec.brief.get("name") or ""
    objective = rec.brief.get("objective", "")

    budget = BudgetResponse(
        currency=rec.budget.limits.currency,
        total_amount=rec.budget.limits.total_amount,
        daily_cap=rec.budget.limits.daily_cap,
        # BudgetEngine's real attribute is `spent_total` (campaia_core/budget.py) -- the
        # contract's `spent_to_date` is served from it, not a made-up attribute name.
        spent_to_date=rec.budget.spent_total,
    )

    external_resources = [
        ExternalResourceResponse(
            channel=r.channel,
            external_resource_id=r.external_resource_id,
            sync_status=r.sync_status,
            last_synced_at=r.last_synced_at,
        )
        for r in rec.external_resources.values()
    ]

    return CampaignResponse(
        id=rec.campaign_id,
        business_unit_id=rec.business_unit_id,
        state=rec.campaign.state.value,
        name=name,
        objective=objective,
        brief=rec.brief,
        channels=list(rec.planned_channels),
        plan_version=rec.plan_version,
        connection_id=rec.connection_id,
        external_resources=external_resources,
        budget=budget,
        last_synced_at=rec.last_synced_at,
        created_at=rec.created_at,
    )


def serialize_policy_decision(decision):
    from .models import PolicyDecisionResponse, PolicyFindingResponse

    return PolicyDecisionResponse(
        policy_decision_id=decision.policy_decision_id,
        outcome=decision.outcome.value,
        campaign_id=decision.campaign_id,
        plan_version=decision.plan_version,
        issued_at=decision.issued_at,
        expires_at=decision.expires_at,
        requires_human_approval=decision.requires_human_approval,
        requires_dual_approval=decision.requires_dual_approval,
        findings=[
            PolicyFindingResponse(code=f.code, severity=f.severity.value, explanation=f.explanation)
            for f in decision.findings
        ],
    )


#: Human-readable reason text per approval `kind`, used to populate the contract's
#: free-text ApprovalRequest.reason field (achado 9). Kept as a small fixed mapping rather
#: than free-form text generation since `kind` is itself a closed, small set of values.
_APPROVAL_REASON_BY_KIND = {
    "PUBLISH": "Aprovacao necessaria para publicacao da campanha.",
    "BUDGET_CHANGE": "Aprovacao necessaria para alteracao de orcamento.",
    "AUTONOMY_CHANGE": "Aprovacao necessaria para alteracao de nivel de autonomia.",
}


def serialize_approval(a: ApprovalRequest):
    from .models import ApprovalResponse

    reason = _APPROVAL_REASON_BY_KIND.get(a.kind, f"Aprovacao necessaria: {a.kind}.")

    return ApprovalResponse(
        id=a.approval_id,
        campaign_id=a.campaign_id,
        kind=a.kind,
        reason=reason,
        requested_by=a.requested_by,
        amount=str(a.amount) if a.amount is not None else None,
        plan_version=a.plan_version,
        status=a.status,
        decided_by=sorted(a.decided_by),
        requires_dual_approval=a.requires_dual_approval,
        created_at=a.created_at,
        expires_at=a.expires_at,
    )


def serialize_audit_event(e: AuditEvent):
    from .models import AuditEventResponse

    return AuditEventResponse(
        id=e.audit_event_id,
        occurred_at=e.timestamp,
        actor_kind=e.actor_kind,
        # e.actor holds a user_id string today (every event so far is actor_kind=USER);
        # surfaced as actor_id per the contract's split (achado 15).
        actor_id=e.actor,
        action=e.action,
        target=e.target,
        policy_decision_id=e.policy_decision_id,
        evidence=e.details,
    )
