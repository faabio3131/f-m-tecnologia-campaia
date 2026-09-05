from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, authorize

from .deps import build_domain_principal, get_state, require_auth
from .errors import ApiError
from .helpers import json_response, serialize_audit_event
from .models import AuditEventListResponse


async def list_audit_events(request: Request) -> JSONResponse:
    fixture = require_auth(request)
    state = get_state(request)
    principal = build_domain_principal(state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, Permission.AUDIT_VIEW, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)

    events = state.audit.list_for_tenant(fixture.tenant_id)
    events = sorted(events, key=lambda e: e.timestamp)

    # AuditEvent.target is a generic "whatever entity this action was about" field --
    # for campaign-scoped actions (CAMPAIGN_CREATE, PLAN_REGENERATE, CAMPAIGN_PUBLISH,
    # CAMPAIGN_PAUSE, BUDGET_CHANGE, CAMPAIGN_VALIDATE, campaign-scope KILL_SWITCH) it IS
    # the campaign_id, which is the best available mapping given there is no dedicated
    # campaign_id column on AuditEvent today (documented simplification, achado 15).
    campaign_id_filter = request.query_params.get("campaign_id")
    if campaign_id_filter:
        events = [e for e in events if e.target == campaign_id_filter]

    # `cursor` is accepted but there is no real pagination layer over AuditLog yet -- we
    # always return next_cursor: null rather than fabricate pagination that does not
    # exist (achado 3/15), matching the same documented approach as /campaigns.
    envelope = AuditEventListResponse(
        items=[serialize_audit_event(e) for e in events], next_cursor=None
    )
    return json_response(envelope)
