"""F2 — IAM, RBAC and organization administration.

All tenant scope is derived from the authenticated session. No route accepts tenant_id.
Sensitive mutations reuse the existing session-bound step-up model and idempotency store.
"""

from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, Role, authorize

from .deps import (
    build_domain_principal,
    get_state,
    note_step_up_header,
    require_auth,
    require_idempotency_key,
    require_step_up,
)
from .errors import ApiError
from .helpers import json_response, list_response, parse_body
from .models import (
    BusinessUnitCreateRequest,
    BusinessUnitRenameRequest,
    BusinessUnitResponse,
    MembershipAccessUpdateRequest,
    MembershipResponse,
)


def _serialize_unit(unit) -> BusinessUnitResponse:
    return BusinessUnitResponse(
        id=unit.business_unit_id,
        name=unit.name,
        status=unit.status,
        created_at=unit.created_at,
    )


def _serialize_membership(membership) -> MembershipResponse:
    return MembershipResponse(
        id=membership.membership_id,
        tenant_id=membership.tenant_id,
        email=membership.email,
        roles=sorted(role.value for role in membership.roles),
        business_unit_id=membership.business_unit_id,
        status=membership.status,
        created_at=membership.created_at,
        updated_at=membership.updated_at,
        deactivated_at=membership.deactivated_at,
    )


def _authorize(request: Request, *, manage: bool):
    fixture = require_auth(request)
    state = get_state(request)
    if manage:
        note_step_up_header(request, fixture)
    principal = build_domain_principal(request, state, fixture)
    permission = Permission.MEMBER_MANAGE if manage else Permission.MEMBER_VIEW
    decision = authorize(
        principal,
        permission,
        Resource(tenant_id=fixture.tenant_id),
        now=datetime.now(timezone.utc),
    )
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    if manage:
        require_step_up(request, fixture)
    return fixture, state


def _roles_from(values: list[str]) -> frozenset[Role]:
    try:
        roles = frozenset(Role(value) for value in values)
    except ValueError as exc:
        raise ApiError("VALIDATION_FAILED", "Papel de usuario invalido.") from exc
    if not roles:
        raise ApiError("VALIDATION_FAILED", "Informe pelo menos um papel.")
    return roles


def _enforce_role_authority(actor, target, new_roles: frozenset[Role]) -> None:
    actor_is_owner = Role.OWNER in actor.roles
    target_is_owner = Role.OWNER in target.roles
    grants_owner = Role.OWNER in new_roles
    if (target_is_owner or grants_owner) and not actor_is_owner:
        raise ApiError(
            "PERMISSION_DENIED",
            "Somente Owner pode administrar ou conceder o papel Owner.",
        )


async def list_business_units(request: Request) -> JSONResponse:
    fixture, state = _authorize(request, manage=False)
    units = state.organizations.list_business_units_for_tenant(fixture.tenant_id)
    return list_response([_serialize_unit(unit) for unit in units])


async def create_business_unit(request: Request) -> JSONResponse:
    fixture, state = _authorize(request, manage=True)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BusinessUnitCreateRequest)
    key = f"http:create_business_unit:{idem_key}"
    existing = state.idempotency.get(fixture.tenant_id, key)
    if existing is not None:
        return JSONResponse(existing.result, status_code=201)

    def _do():
        try:
            unit = state.organizations.create_business_unit(
                fixture.tenant_id, name=body.name
            )
        except ValueError as exc:
            if str(exc) == "BUSINESS_UNIT_NAME_EXISTS":
                raise ApiError("INVALID_STATE", "Ja existe uma unidade com este nome.") from exc
            raise ApiError("VALIDATION_FAILED", "Nome de unidade invalido.") from exc
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BUSINESS_UNIT_CREATE",
            target=unit.business_unit_id,
            details={"name": unit.name},
        )
        return _serialize_unit(unit).model_dump(mode="json")

    result, _ = state.idempotency.execute(fixture.tenant_id, key, _do)
    return JSONResponse(result, status_code=201)


async def rename_business_unit(request: Request) -> JSONResponse:
    fixture, state = _authorize(request, manage=True)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BusinessUnitRenameRequest)
    unit_id = request.path_params["businessUnitId"]
    current = state.organizations.get_business_unit(fixture.tenant_id, unit_id)
    if current is None:
        raise ApiError("NOT_FOUND", "Unidade de negocio nao encontrada neste tenant.")
    key = f"http:rename_business_unit:{unit_id}:{idem_key}"

    def _do():
        old_name = current.name
        try:
            updated = state.organizations.rename_business_unit(
                fixture.tenant_id, unit_id, name=body.name
            )
        except ValueError as exc:
            if str(exc) == "BUSINESS_UNIT_NAME_EXISTS":
                raise ApiError("INVALID_STATE", "Ja existe uma unidade com este nome.") from exc
            raise ApiError("VALIDATION_FAILED", "Nome de unidade invalido.") from exc
        if updated is None:
            raise ApiError("NOT_FOUND", "Unidade de negocio nao encontrada neste tenant.")
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BUSINESS_UNIT_RENAME",
            target=unit_id,
            details={"from": old_name, "to": updated.name},
        )
        return _serialize_unit(updated).model_dump(mode="json")

    result, _ = state.idempotency.execute(fixture.tenant_id, key, _do)
    return JSONResponse(result)


async def _set_unit_status(request: Request, *, status: str) -> JSONResponse:
    fixture, state = _authorize(request, manage=True)
    idem_key = require_idempotency_key(request)
    unit_id = request.path_params["businessUnitId"]
    if state.organizations.get_business_unit(fixture.tenant_id, unit_id) is None:
        raise ApiError("NOT_FOUND", "Unidade de negocio nao encontrada neste tenant.")
    action = "deactivate" if status == "INACTIVE" else "reactivate"
    key = f"http:{action}_business_unit:{unit_id}:{idem_key}"

    def _do():
        try:
            updated = state.organizations.set_business_unit_status(
                fixture.tenant_id, unit_id, status=status
            )
        except ValueError as exc:
            code = str(exc)
            if code == "BUSINESS_UNIT_HAS_ACTIVE_MEMBERS":
                raise ApiError(
                    "INVALID_STATE",
                    "Realoque ou desative os usuarios ativos desta unidade antes de desativa-la.",
                ) from exc
            if code == "LAST_ACTIVE_BUSINESS_UNIT":
                raise ApiError(
                    "INVALID_STATE",
                    "O tenant precisa manter pelo menos uma unidade ativa.",
                ) from exc
            raise
        if updated is None:
            raise ApiError("NOT_FOUND", "Unidade de negocio nao encontrada neste tenant.")
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action=f"BUSINESS_UNIT_{status}",
            target=unit_id,
        )
        return _serialize_unit(updated).model_dump(mode="json")

    result, _ = state.idempotency.execute(fixture.tenant_id, key, _do)
    return JSONResponse(result)


async def deactivate_business_unit(request: Request) -> JSONResponse:
    return await _set_unit_status(request, status="INACTIVE")


async def reactivate_business_unit(request: Request) -> JSONResponse:
    return await _set_unit_status(request, status="ACTIVE")


async def update_membership_access(request: Request) -> JSONResponse:
    fixture, state = _authorize(request, manage=True)
    idem_key = require_idempotency_key(request)
    membership_id = request.path_params["membershipId"]
    target = state.organizations.get_membership(fixture.tenant_id, membership_id)
    if target is None:
        raise ApiError("NOT_FOUND", "Usuario nao encontrado neste tenant.")
    body = await parse_body(request, MembershipAccessUpdateRequest)
    roles = _roles_from(body.roles)
    _enforce_role_authority(fixture, target, roles)

    unit = state.organizations.get_business_unit(
        fixture.tenant_id, body.business_unit_id
    )
    if unit is None or unit.status != "ACTIVE":
        raise ApiError("NOT_FOUND", "Unidade de negocio ativa nao encontrada neste tenant.")

    if (
        target.status == "ACTIVE"
        and Role.OWNER in target.roles
        and Role.OWNER not in roles
        and state.organizations.active_owner_count(fixture.tenant_id) <= 1
    ):
        raise ApiError("INVALID_STATE", "O ultimo Owner ativo nunca pode perder esse papel.")

    key = f"http:update_membership_access:{membership_id}:{idem_key}"

    def _do():
        old_roles = sorted(role.value for role in target.roles)
        old_unit = target.business_unit_id
        updated = state.organizations.update_membership_access(
            fixture.tenant_id,
            membership_id,
            roles=roles,
            business_unit_id=unit.business_unit_id,
        )
        if updated is None:
            raise ApiError("NOT_FOUND", "Usuario nao encontrado neste tenant.")
        # Roles/unidade ficam capturados na sessao no login. Revogar e obrigar novo
        # login e mais seguro do que manter uma sessao com autoridade obsoleta.
        state.sessions.invalidate_membership(updated.membership_id)
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="MEMBERSHIP_ACCESS_UPDATE",
            target=updated.membership_id,
            details={
                "old_roles": old_roles,
                "new_roles": sorted(role.value for role in updated.roles),
                "old_business_unit_id": old_unit,
                "new_business_unit_id": updated.business_unit_id,
            },
        )
        return _serialize_membership(updated).model_dump(mode="json")

    result, _ = state.idempotency.execute(fixture.tenant_id, key, _do)
    return JSONResponse(result)
