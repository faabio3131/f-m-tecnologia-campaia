from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, authorize

from .deps import build_domain_principal, get_state, require_auth
from .errors import ApiError
from .helpers import json_response, serialize_audit_event
from .models import AuditEventListResponse

# Missão de fechamento integral (Etapa A9, 22/09/2026): fixed page size, not a query
# param -- the contract never declared a `limit` parameter, only opaque `cursor` /
# `next_cursor`, matching the Stripe-style cursor pagination it already promised.
_PAGE_SIZE = 50


async def list_audit_events(request: Request) -> JSONResponse:
    fixture = require_auth(request)
    state = get_state(request)
    principal = build_domain_principal(state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, Permission.AUDIT_VIEW, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)

    events = state.audit.list_for_tenant(fixture.tenant_id)
    # `audit_event_id` (new_id("audit"), api/repositories.py) is generated from a single
    # process-wide monotonic counter shared by every entity type, so it is unique and
    # totally ordered exactly like creation order -- a stable tiebreaker for `timestamp`,
    # which has no such guarantee under fast, back-to-back appends.
    events = sorted(events, key=lambda e: (e.timestamp, e.audit_event_id))

    # AuditEvent.target is a generic "whatever entity this action was about" field --
    # for campaign-scoped actions (CAMPAIGN_CREATE, PLAN_REGENERATE, CAMPAIGN_PUBLISH,
    # CAMPAIGN_PAUSE, BUDGET_CHANGE, CAMPAIGN_VALIDATE, campaign-scope KILL_SWITCH) it IS
    # the campaign_id, which is the best available mapping given there is no dedicated
    # campaign_id column on AuditEvent today (documented simplification, achado 15).
    campaign_id_filter = request.query_params.get("campaign_id")
    if campaign_id_filter:
        events = [e for e in events if e.target == campaign_id_filter]

    # Missão de fechamento integral (Etapa A9, 22/09/2026): real cursor pagination,
    # replacing the previous honest stub that always returned next_cursor: null. `cursor`
    # is opaque to the client -- the last-returned event's own id, exactly like the
    # contract already promised. An unknown/stale cursor fails closed (VALIDATION_FAILED)
    # rather than silently resetting to page 1, matching this backend's existing
    # fail-closed convention for anything client-supplied and unverifiable server-side.
    start = 0
    cursor = request.query_params.get("cursor")
    if cursor:
        ids = [e.audit_event_id for e in events]
        try:
            start = ids.index(cursor) + 1
        except ValueError:
            raise ApiError("VALIDATION_FAILED", "Unknown or expired cursor.")

    page = events[start : start + _PAGE_SIZE]
    has_more = start + _PAGE_SIZE < len(events)
    next_cursor = page[-1].audit_event_id if has_more else None

    envelope = AuditEventListResponse(
        items=[serialize_audit_event(e) for e in page], next_cursor=next_cursor
    )
    return json_response(envelope)
