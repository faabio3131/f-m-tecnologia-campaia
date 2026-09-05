from __future__ import annotations

import uuid
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
from .models import CapabilityResponse, ConnectionResponse, OAuthStartRequest, OAuthStartResponse


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
    resolve to anything, purely to exercise the shape of the flow in this sandbox.
    """
    fixture, state = _authorize(request, Permission.CONNECTION_MANAGE)
    require_step_up(request, fixture)
    body = await parse_body(request, OAuthStartRequest)

    oauth_state = uuid.uuid4().hex
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
