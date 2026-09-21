from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from campaia_core.permissions import Permission, Resource, authorize

from .deps import (
    build_domain_principal,
    get_state,
    note_step_up_header,
    require_auth,
    require_idempotency_key,
    require_step_up,
)
from .errors import ApiError
from .helpers import json_response, list_response, parse_body, serialize_connection
from .models import (
    CapabilityResponse,
    ConnectionResponse,
    OAuthCompleteRequest,
    OAuthStartRequest,
    OAuthStartResponse,
)


def _authorize(request: Request, permission: Permission):
    fixture = require_auth(request)
    state = get_state(request)
    note_step_up_header(request, fixture)
    principal = build_domain_principal(state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state


async def list_connections(request: Request) -> JSONResponse:
    fixture, state = _authorize(request, Permission.CAMPAIGN_VIEW)
    conns = state.connections.list_for_tenant(fixture.tenant_id)
    return list_response([serialize_connection(c) for c in conns])


async def oauth_start(request: Request) -> JSONResponse:
    """Synthesizes a fake authorization URL under a clearly-fake domain.

    This NEVER calls a real OAuth provider. No real network call is made here at all --
    the "authorization_url" is a placeholder string pointing at a domain that does not
    resolve to anything, purely to exercise the shape of the flow in this sandbox. `state`
    is tracked server-side (AppState.oauth_pending, WP-04) so /connections/oauth/complete
    can later verify it against the tenant/provider that actually started this attempt,
    rather than trusting whatever the client echoes back.
    """
    fixture, state = _authorize(request, Permission.CONNECTION_MANAGE)
    require_step_up(request, fixture)
    body = await parse_body(request, OAuthStartRequest)

    oauth_state = state.create_pending_oauth(tenant_id=fixture.tenant_id, provider=body.provider)
    fake_url = (
        f"https://auth.simulated-ads-provider.invalid/oauth/authorize"
        f"?provider={body.provider}&state={oauth_state}&client_id=sandbox-fixture"
    )
    state.audit.append(
        tenant_id=fixture.tenant_id,
        actor=fixture.user_id,
        action="OAUTH_START",
        target=body.provider,
        details={"note": "simulated, no real provider contacted", "state": oauth_state},
    )
    return json_response(OAuthStartResponse(authorization_url=fake_url, state=oauth_state))


async def oauth_complete(request: Request) -> JSONResponse:
    """Finalizes a /connections/oauth/start attempt (WP-04), simulating the account the
    (nonexistent) real provider would have returned after the user picked one. `state` must
    match a pending attempt started by THIS tenant -- never trusted at face value, always
    looked up server-side (AppState.pop_pending_oauth), exactly like /auth/callback's own
    pending-login check (WP-02). Creates a real, persisted Connection -- unlike
    /connections/oauth/start, which never did (the contract's own description already says
    "o callback e recebido pelo backend", i.e. this step was always intended to exist).
    """
    fixture, state = _authorize(request, Permission.CONNECTION_MANAGE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, OAuthCompleteRequest)

    def _do_create():
        # Consuming the pending OAuth state MUST happen inside the idempotency-guarded
        # closure, never before it -- IdempotencyStore.execute() never calls this closure
        # on replay, so a legitimate retry (same Idempotency-Key, e.g. a dropped response)
        # would otherwise find its own already-consumed state and fail as if it were a
        # genuine replay attack. A real second attempt (different Idempotency-Key) still
        # correctly fails, since the state truly is gone by then.
        pending = state.pop_pending_oauth(body.state, tenant_id=fixture.tenant_id)
        if pending is None:
            raise ApiError(
                "VALIDATION_FAILED", "Unknown, expired, or already-used OAuth state."
            )
        conn = state.connections.create(
            fixture.tenant_id,
            provider=pending.provider,
            external_account_id=body.external_account_id,
            display_name=body.display_name,
        )
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="CONNECTION_CREATE",
            target=conn.connection_id,
            details={"provider": pending.provider, "note": "simulated, no real provider contacted"},
        )
        return serialize_connection(conn).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:oauth_complete:{idem_key}", _do_create
    )
    return JSONResponse(result, status_code=201)


async def revoke_connection(request: Request) -> Response:
    fixture, state = _authorize(request, Permission.CONNECTION_MANAGE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    connection_id = request.path_params["connectionId"]

    conn = state.connections.get(fixture.tenant_id, connection_id)
    if conn is None:
        raise ApiError("NOT_FOUND", "Connection not found.")

    def _do_revoke():
        state.connections.revoke(fixture.tenant_id, connection_id)
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="CONNECTION_REVOKE",
            target=connection_id,
        )
        return None

    state.idempotency.execute(fixture.tenant_id, idem_key, _do_revoke)
    # Contract: 204 with no body (achado 4) -- previously returned 200 with the revoked
    # connection's JSON representation.
    return Response(status_code=204)


async def connection_capabilities(request: Request) -> JSONResponse:
    fixture, state = _authorize(request, Permission.CAMPAIGN_VIEW)
    connection_id = request.path_params["connectionId"]
    conn = state.connections.get(fixture.tenant_id, connection_id)
    if conn is None:
        raise ApiError("NOT_FOUND", "Connection not found.")

    now = datetime.now(timezone.utc)
    channels = ("GOOGLE_ADS", "META_ADS")
    results = []
    for channel in channels:
        key = f"PUBLISH:{channel}"
        supported = state.capabilities.is_supported(
            conn.provider, key, country="BR", api_version=conn.api_version, now=now
        )
        cap = state.capabilities._items.get((conn.provider, key, "BR", conn.api_version))
        results.append(
            CapabilityResponse(
                provider=conn.provider,
                capability_key=key,
                country="BR",
                api_version=conn.api_version,
                supported=supported,
                verified_at=cap.verified_at if cap else now,
                requires_approval=cap.requires_approval if cap else False,
                # No evidence-URL source exists yet in campaia_core.infra.Capability
                # (achado 7) -- always None until that tracking exists.
                evidence_url=None,
                notes=cap.notes if cap else None,
            )
        )
    return list_response(results)
