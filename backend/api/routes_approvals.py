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
    principal = build_domain_principal(state, fixture)
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
    """Not in the paraphrased contract's endpoint list, added as a minimal, clearly-
    labeled deviation: the contract requires publish/budget-change/autonomy-change to
    reference an approval "already on record", but specifies no endpoint that puts one on
    record in the first place. Without this, /approvals/{id}/decision has nothing to act
    on and the required approval-gated flows are untestable end-to-end. This is a thin
    creator for a PENDING ApprovalRequest row; it performs no domain mutation itself.
    """
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_CREATE)
    body = await parse_body(request, ApprovalCreateRequest)

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
        # Contract's ApprovalRequest.plan_version (achado 9): captured from the related
        # campaign's CURRENT plan_version at request time, not looked up live later.
        plan_version=campaign.plan_version,
    )
    state.audit.append(
        tenant_id=fixture.tenant_id,
        actor=fixture.user_id,
        action="APPROVAL_REQUEST_CREATE",
        target=approval.approval_id,
    )
    return json_response(serialize_approval(approval), status_code=201)


async def decide_approval(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.APPROVAL_DECIDE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    approval_id = request.path_params["approvalId"]
    body = await parse_body(request, ApprovalDecisionRequest)

    approval = state.approvals.get(fixture.tenant_id, approval_id)
    if approval is None:
        raise ApiError("NOT_FOUND", "Approval not found.")

    # Idempotency check happens BEFORE `can_approve`, not just before the mutation. This
    # endpoint's own side effect (adding fixture.user_id to approval.decided_by) feeds
    # back into can_approve's own precondition (`already_decided_by`) -- so on a replay of
    # the SAME Idempotency-Key by the same actor, can_approve would see "this user already
    # decided" (true, because their own first call did it) and reject the replay with
    # SEPARATION_OF_DUTIES instead of returning the original result. That is a genuine
    # idempotency violation distinct from publish_campaign/patch_budget, where the
    # preconditions checked before their idempotency gate belong to a DIFFERENT record
    # (another ApprovalRequest) that this handler never mutates itself. Found by
    # independent verification after the P-14 fix pass; documented in
    # EVIDENCIA_P14_20260828.md as achado 16.
    existing = state.idempotency.get(fixture.tenant_id, f"http:decide_approval:{idem_key}")
    if existing is not None:
        return json_response(serialize_approval(approval))

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

    if body.decision not in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
        raise ApiError("VALIDATION_FAILED", "decision must be APPROVE, REJECT or REQUEST_CHANGES.")

    def _do_decide():
        if body.decision == "REJECT":
            approval.status = "REJECTED"
        elif body.decision == "REQUEST_CHANGES":
            # Contract adds REQUEST_CHANGES as a decision option (achado 10): marks the
            # approval CHANGES_REQUESTED rather than deciding it outright.
            approval.status = "CHANGES_REQUESTED"
        else:
            approval.decided_by.add(fixture.user_id)
            if approval.requires_dual_approval:
                approval.status = (
                    "APPROVED" if dual_approval_complete(frozenset(approval.decided_by)) else "PENDING"
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
        return True

    state.idempotency.execute(fixture.tenant_id, f"http:decide_approval:{idem_key}", _do_decide)
    return json_response(serialize_approval(approval))
