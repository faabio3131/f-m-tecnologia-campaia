from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, authorize

from .deps import build_domain_principal, get_state, require_auth, require_idempotency_key
from .errors import ApiError
from .helpers import list_response, parse_body, serialize_brand_profile
from .models import BrandProfileCreate


def _authorize_brand(request: Request, permission: Permission):
    fixture = require_auth(request)
    state = get_state(request)
    principal = build_domain_principal(state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state


async def list_brand_profiles(request: Request) -> JSONResponse:
    fixture, state = _authorize_brand(request, Permission.CAMPAIGN_VIEW)
    profiles = state.brand_profiles.list_for_tenant(fixture.tenant_id)
    return list_response([serialize_brand_profile(p) for p in profiles])


async def create_brand_profile(request: Request) -> JSONResponse:
    fixture, state = _authorize_brand(request, Permission.BRAND_MANAGE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BrandProfileCreate)

    def _do_create():
        profile = state.brand_profiles.create(
            fixture.tenant_id,
            name=body.name,
            tone=body.tone,
            colors=body.colors,
            differentiators=body.differentiators,
            restrictions=body.restrictions,
        )
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BRAND_PROFILE_CREATE",
            target=profile.brand_profile_id,
        )
        return serialize_brand_profile(profile).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:create_brand_profile:{idem_key}", _do_create
    )
    return JSONResponse(result, status_code=201)
