from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, authorize, can_approve, dual_approval_complete
from .bounded_body import parse_bounded_body
from .deps import (build_domain_principal, get_state, note_step_up_header, require_auth,
                   require_idempotency_key, require_step_up)
from .errors import ApiError
from .helpers import list_response, serialize_approval
from .models import ApprovalCreateRequest, ApprovalDecisionRequest
from .routes_campaigns import _get_campaign_or_404


def _authorize(request, permission):
    fixture = require_auth(request)
    state = get_state(request)
    note_step_up_header(request, fixture)  # External token verification, if any, precedes F3.
    principal = build_domain_principal(request, state, fixture)
    decision = authorize(principal, permission,
        Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id),
        now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state, principal


def _fresh_campaign(request, original, state, campaign_id, permission):
    current = require_auth(request)
    if (current.tenant_id, current.user_id, current.business_unit_id) != (
            original.tenant_id, original.user_id, original.business_unit_id):
        raise ApiError("AUTH_CONTEXT_CHANGED", "A sessão mudou durante a operação.", status_code=409)
    principal = build_domain_principal(request, state, current)
    campaign = _get_campaign_or_404(state, current.tenant_id, campaign_id, principal=principal)
    decision = authorize(principal, permission,
        Resource(tenant_id=current.tenant_id, business_unit_id=campaign.business_unit_id),
        now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return current, principal, campaign


def _context(fixture, body, target=None):
    try:
        payload = [fixture.user_id, fixture.business_unit_id, target, body.model_dump(mode="json")]
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ApiError("VALIDATION_FAILED", "Confira os campos do pedido.", status_code=422) from None
    return sha256(encoded).hexdigest()


def _unpack(result, context, legacy_matches):
    if result.get("approval_context_v1") is not None:
        if result["approval_context_v1"] == context:
            return result["response"]
    elif legacy_matches(result):
        # Legacy reads require visible actor/target evidence. New writes bind the full context.
        return result
    raise ApiError("IDEMPOTENCY_CONFLICT", "A chave já identifica outro pedido ou contexto.", status_code=409)


def _pack(context, result):
    return {"approval_context_v1": context, "response": result}


async def list_approvals(request):
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    approvals = []
    for approval in state.approvals.list_for_tenant(fixture.tenant_id):
        campaign = state.campaigns.get(fixture.tenant_id, approval.campaign_id)
        if campaign is None:
            continue
        if (principal.business_unit_ids is not None and campaign.business_unit_id is not None
                and campaign.business_unit_id not in principal.business_unit_ids):
            continue
        approvals.append(serialize_approval(approval))
    response = list_response(approvals)
    response.headers["Cache-Control"] = "private, no-store"
    return response


async def create_approval(request):
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_CREATE)
    nonce = require_idempotency_key(request)
    body = await parse_bounded_body(request, ApprovalCreateRequest, max_bytes=64 * 1024)
    _fresh_campaign(request, fixture, state, body.campaign_id, Permission.CAMPAIGN_CREATE)
    context = _context(fixture, body)
    key = "http:create_approval:" + nonce
    def legacy(result):
        amount = str(body.amount) if body.amount is not None else None
        return (result.get("campaign_id") == body.campaign_id and result.get("requested_by") == fixture.user_id
                and result.get("kind") == body.kind and result.get("amount") == amount
                and result.get("requires_dual_approval") == body.requires_dual_approval)
    previous = state.idempotency.get(fixture.tenant_id, key)
    if previous is not None:
        return JSONResponse(_unpack(previous.result, context, legacy), status_code=201,
                            headers={"Cache-Control": "private, no-store"})
    def create():
        current, _principal, campaign = _fresh_campaign(
            request, fixture, state, body.campaign_id, Permission.CAMPAIGN_CREATE)
        dual = bool(body.kind == "PUBLISH" and campaign.last_policy_decision
                    and campaign.last_policy_decision.requires_dual_approval)
        approval = state.approvals.create(current.tenant_id, campaign_id=body.campaign_id,
            kind=body.kind, requested_by=current.user_id, amount=body.amount,
            requires_dual_approval=body.requires_dual_approval or dual, plan_version=campaign.plan_version)
        state.audit.append(tenant_id=current.tenant_id, actor=current.user_id,
                           action="APPROVAL_REQUEST_CREATE", target=approval.approval_id)
        return _pack(context, serialize_approval(approval).model_dump(mode="json"))
    result, _replay = state.idempotency.execute(fixture.tenant_id, key, create)
    return JSONResponse(_unpack(result, context, legacy), status_code=201,
                        headers={"Cache-Control": "private, no-store"})


async def decide_approval(request):
    fixture, state, _principal = _authorize(request, Permission.APPROVAL_DECIDE)
    require_step_up(request, fixture)
    nonce = require_idempotency_key(request)
    approval_id = request.path_params["approvalId"]
    body = await parse_bounded_body(request, ApprovalDecisionRequest, max_bytes=64 * 1024)
    if body.decision not in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
        raise ApiError("VALIDATION_FAILED", "decision must be APPROVE, REJECT or REQUEST_CHANGES.")
    scoped = state.approvals.get(fixture.tenant_id, approval_id)
    if scoped is None:
        raise ApiError("NOT_FOUND", "Approval not found.")
    _fresh_campaign(request, fixture, state, scoped.campaign_id, Permission.APPROVAL_DECIDE)
    context = _context(fixture, body, approval_id)
    key = "http:decide_approval:" + nonce
    def legacy(result):
        return (result.get("id") == approval_id and body.decision == "APPROVE" and not body.reason
                and fixture.user_id in result.get("decided_by", []))
    previous = state.idempotency.get(fixture.tenant_id, key)
    if previous is not None:
        return JSONResponse(_unpack(previous.result, context, legacy),
                            headers={"Cache-Control": "private, no-store"})

    def decide():
        approval = state.approvals.get(fixture.tenant_id, approval_id)
        if approval is None:
            raise ApiError("NOT_FOUND", "Approval not found.")
        current, principal, campaign = _fresh_campaign(
            request, fixture, state, approval.campaign_id, Permission.APPROVAL_DECIDE)
        if body.decision == "APPROVE" and approval.plan_version != campaign.plan_version:
            raise ApiError("APPROVAL_STALE", "A campanha mudou. Solicite uma nova aprovação.", status_code=409)
        resource = Resource(tenant_id=current.tenant_id, business_unit_id=campaign.business_unit_id,
                            resource_id=approval.campaign_id, created_by=approval.requested_by)
        decision = can_approve(principal, resource, now=datetime.now(timezone.utc),
            requester_id=approval.requested_by, already_decided_by=frozenset(approval.decided_by), amount=approval.amount)
        if not decision.allowed:
            raise ApiError(decision.code.value, decision.reason)
        if approval.status != "PENDING":
            raise ApiError("APPROVAL_FINALIZED", "Este pedido já foi encerrado. Registre um novo pedido para outra decisão.", status_code=409)
        if (approval.kind == "PUBLISH" and campaign.last_policy_decision
                and campaign.last_policy_decision.plan_version == approval.plan_version
                and campaign.last_policy_decision.requires_dual_approval):
            approval.requires_dual_approval = True
        if body.decision == "REJECT":
            approval.status = "REJECTED"
        elif body.decision == "REQUEST_CHANGES":
            approval.status = "CHANGES_REQUESTED"
        else:
            approval.decided_by.add(current.user_id)
            approval.status = ("APPROVED" if not approval.requires_dual_approval
                               or dual_approval_complete(frozenset(approval.decided_by)) else "PENDING")
        if body.reason:
            approval.context["decision_reason"] = body.reason
        state.audit.append(tenant_id=current.tenant_id, actor=current.user_id,
            action="APPROVAL_" + body.decision, target=approval.approval_id,
            details={"reason": body.reason} if body.reason else None)
        return _pack(context, serialize_approval(approval).model_dump(mode="json"))

    result, _replay = state.idempotency.execute(fixture.tenant_id, key, decide)
    return JSONResponse(_unpack(result, context, legacy), headers={"Cache-Control": "private, no-store"})
