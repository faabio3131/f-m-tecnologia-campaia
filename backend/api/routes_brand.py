from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, authorize

from .deps import build_domain_principal, get_state, require_auth, require_idempotency_key
from .errors import ApiError
from .helpers import list_response, parse_body, serialize_brand_profile
from .models import BrandProfileCreate, BrandProfileUpdate
from .brand_versions import freeze_version, version_page


def _authorize_brand(request: Request, permission: Permission):
    fixture = require_auth(request)
    state = get_state(request)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state


async def list_brand_profiles(request: Request) -> JSONResponse:
    fixture, state = _authorize_brand(request, Permission.CAMPAIGN_VIEW)
    profiles = state.brand_profiles.list_for_tenant(fixture.tenant_id)
    return list_response([serialize_brand_profile(p) for p in profiles])


def _owned_profile(state, tenant, identity):
    profile = state.brand_profiles.get(tenant, identity)
    if profile is None:
        raise ApiError('NOT_FOUND', 'Brand Kit indisponível.', status_code=404)
    return profile


def _context(fixture, identity, body):
    return sha256(json.dumps([fixture.user_id, fixture.business_unit_id, identity, body],
                             sort_keys=True).encode()).hexdigest()


async def create_brand_profile(request: Request) -> JSONResponse:
    fixture, state = _authorize_brand(request, Permission.BRAND_MANAGE)
    key = require_idempotency_key(request)
    body = await parse_body(request, BrandProfileCreate)
    fields = body.model_dump()
    context = _context(fixture, 'CREATE', fields)
    def create():
        at = datetime.now(timezone.utc)
        profile = state.brand_profiles.create(fixture.tenant_id, **fields, created_at=at, updated_at=at)
        snapshot = freeze_version(state, profile, editor_id=fixture.user_id, recorded_at=at)
        state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
            action='BRAND_PROFILE_CREATE', target=profile.brand_profile_id,
            details={'version': profile.version})
        return {'context': context, 'response': snapshot}
    result, _ = state.idempotency.execute(fixture.tenant_id, 'http:create_brand_profile:' + key, create)
    if 'context' in result and 'response' in result:
        if result['context'] != context:
            raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outra criação ou contexto.', status_code=409)
        result = result['response']
    elif any(result.get(field) != value for field, value in fields.items()):
        raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outro Brand Kit.', status_code=409)
    _owned_profile(state, fixture.tenant_id, result['id'])
    return JSONResponse(result, status_code=201)


async def get_brand_profile(request: Request) -> JSONResponse:
    fixture, state = _authorize_brand(request, Permission.CAMPAIGN_VIEW)
    return JSONResponse(serialize_brand_profile(_owned_profile(
        state, fixture.tenant_id, request.path_params['brandProfileId'])).model_dump(mode='json'))


async def update_brand_profile(request: Request) -> JSONResponse:
    fixture, state = _authorize_brand(request, Permission.BRAND_MANAGE)
    key = require_idempotency_key(request)
    identity = request.path_params['brandProfileId']
    _owned_profile(state, fixture.tenant_id, identity)  # Authority before replay.
    body = await parse_body(request, BrandProfileUpdate)
    context = _context(fixture, identity, body.model_dump())
    def update():
        current = _owned_profile(state, fixture.tenant_id, identity)
        if current.version != body.expected_version:
            raise ApiError('BRAND_VERSION_CHANGED', 'O Brand Kit mudou em outra edição. Atualize e revise antes de salvar.', status_code=409)
        freeze_version(state, current)
        at = datetime.now(timezone.utc)
        profile = state.brand_profiles.replace_profile(fixture.tenant_id, identity,
            expected_version=body.expected_version, at=at, **body.model_dump(exclude={'expected_version'}))
        snapshot = freeze_version(state, profile, editor_id=fixture.user_id, recorded_at=at)
        state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
            action='BRAND_PROFILE_UPDATE', target=identity,
            details={'previous_version': body.expected_version, 'version': profile.version})
        return {'context': context, 'response': snapshot}
    result, _ = state.idempotency.execute(fixture.tenant_id, 'http:update_brand_profile:' + key, update)
    if result['context'] != context:
        raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outra alteração ou contexto.', status_code=409)
    return JSONResponse(result['response'])


async def list_brand_versions(request: Request) -> JSONResponse:
    fixture, state = _authorize_brand(request, Permission.CAMPAIGN_VIEW)
    # All lookups share one short tenant transaction, no mixed revision page.
    if state.db is not None:
        with state.db.transaction():
            state.idempotency._table.lock_key('tenant:' + fixture.tenant_id)
            profile = _owned_profile(state, fixture.tenant_id, request.path_params['brandProfileId'])
            return JSONResponse(version_page(state, profile, request.query_params.get('cursor')))
    profile = _owned_profile(state, fixture.tenant_id, request.path_params['brandProfileId'])
    return JSONResponse(version_page(state, profile, request.query_params.get('cursor')))
