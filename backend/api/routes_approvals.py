from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, authorize, can_approve, dual_approval_complete

from .deps import (
    build_domain_principal,
    get_state,
    note_step_up_header,
    require_auth,
    require_idempotency_key,
    require_step_up,
)
from .errors import ApiError
from .helpers import json_response, list_response, serialize_approval, parse_body
from .models import ApprovalCreateRequest, ApprovalDecisionRequest


def _authorize(request: Request, permission: Permission):
    fixture = require_auth(request)
    state = get_state(request)
    note_step_up_header(request, fixture)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state, principal


async def list_approvals(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    approvals = state.approvals.list_for_tenant(fixture.tenant_id)
    return list_response([serialize_approval(a) for a in approvals])


async def create_approval(request: Request) -> JSONResponse:
    """Create one PENDING ApprovalRequest with exact idempotent replay."""
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_CREATE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, ApprovalCreateRequest)
    key = f"http:create_approval:{idem_key}"

    existing = state.idempotency.get(fixture.tenant_id, key)
    if existing is not None:
        return JSONResponse(existing.result, status_code=201)

    def _do_create():
        campaign = state.campaigns.get(fixture.tenant_id, body.campaign_id)
        if campaign is None:
            raise ApiError("NOT_FOUND", "campaign_id not found.")

        approval = state.approvals.create(
            fixture.tenant_id,
            campaign_id=body.campaign_id,
            kind=body.kind,
            requested_by=fixture.user_id,
            amount=body.amount,
            requires_dual_approval=body.requires_dual_approval,
            plan_version=campaign.plan_version,
        )
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="APPROVAL_REQUEST_CREATE",
            target=approval.approval_id,
        )
        return serialize_approval(approval).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, key, _do_create
    )
    return JSONResponse(result, status_code=201)


async def decide_approval(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.APPROVAL_DECIDE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    approval_id = request.path_params["approvalId"]
    body = await parse_body(request, ApprovalDecisionRequest)
    key = f"http:decide_approval:{idem_key}"

    existing = state.idempotency.get(fixture.tenant_id, key)
    if existing is not None:
        return JSONResponse(existing.result)

    if body.decision not in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
        raise ApiError("VALIDATION_FAILED", "decision must be APPROVE, REJECT or REQUEST_CHANGES.")

    def _do_decide():
        approval = state.approvals.get(fixture.tenant_id, approval_id)
        if approval is None:
            raise ApiError("NOT_FOUND", "Approval not found.")

        resource = Resource(
            tenant_id=fixture.tenant_id,
            business_unit_id=fixture.business_unit_id,
            resource_id=approval.campaign_id,
            created_by=approval.requested_by,
        )
        decision = can_approve(
            principal,
            resource,
            now=datetime.now(timezone.utc),
            requester_id=approval.requested_by,
            already_decided_by=frozenset(approval.decided_by),
            amount=approval.amount,
        )
        if not decision.allowed:
            raise ApiError(decision.code.value, decision.reason)

        if body.decision == "REJECT":
            approval.status = "REJECTED"
        elif body.decision == "REQUEST_CHANGES":
            approval.status = "CHANGES_REQUESTED"
        else:
            approval.decided_by.add(fixture.user_id)
            if approval.requires_dual_approval:
                approval.status = (
                    "APPROVED"
                    if dual_approval_complete(frozenset(approval.decided_by))
                    else "PENDING"
                )
            else:
                approval.status = "APPROVED"

        if body.reason:
            approval.context["decision_reason"] = body.reason
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action=f"APPROVAL_{body.decision}",
            target=approval.approval_id,
            details={"reason": body.reason} if body.reason else None,
        )
        return serialize_approval(approval).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, key, _do_decide
    )
    return JSONResponse(result)

