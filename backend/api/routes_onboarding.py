"""F1 — commercial tenant onboarding and membership administration."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.identity_provider import IdentityError
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
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationResponse,
    MembershipResponse,
    OrganizationResponse,
    TenantOnboardingRequest,
    TenantOnboardingResponse,
)
from .organization import normalize_document, normalize_email
from .session import is_same_origin, set_session_cookie


def _validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if len(normalized) > 254 or normalized.count("@") != 1:
        raise ApiError("VALIDATION_FAILED", "E-mail de convite invalido.")
    local, domain = normalized.split("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ApiError("VALIDATION_FAILED", "E-mail de convite invalido.")
    return normalized


def _verify_public_identity(request: Request, id_token: str):
    state = get_state(request)
    if not is_same_origin(request, state.allowed_origins):
        raise ApiError(
            "PERMISSION_DENIED",
            "Origem da requisicao ausente, invalida ou nao autorizada.",
        )
    try:
        identity = state.id_token_verifier.verify(id_token)
    except IdentityError as exc:
        raise ApiError("UNAUTHENTICATED", f"ID token invalido: {exc}") from exc
    if not identity.email_verified:
        raise ApiError(
            "UNAUTHENTICATED",
            "O provedor de identidade nao confirma este e-mail como verificado.",
        )
    return state, identity


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


def _serialize_invitation(invitation, *, accept_token: str | None = None) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.invitation_id,
        email=invitation.email,
        roles=sorted(role.value for role in invitation.roles),
        business_unit_id=invitation.business_unit_id,
        status=invitation.status,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        accepted_by=invitation.accepted_by,
        accept_token=accept_token,
    )


def _issue_session(state, identity, membership):
    principal = state.identity_directory.resolve_all(
        identity.email, subject=identity.subject
    )
    active = next((p for p in principal if p.user_id == membership.membership_id), None)
    if active is None:
        raise ApiError("UNKNOWN", "Vinculo criado, mas nao foi possivel materializar a sessao.")
    now = datetime.now(timezone.utc)
    record = state.sessions.create(
        active,
        now=now,
        available_principals=tuple(principal),
        subject=identity.subject,
    )
    payload = {
        "user_id": active.user_id,
        "tenant_id": active.tenant_id,
        "business_unit_id": active.business_unit_id,
        "roles": sorted(role.value for role in active.roles),
        "csrf_token": record.csrf_secret,
    }
    return record, payload, now


async def create_tenant(request: Request) -> JSONResponse:
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, TenantOnboardingRequest)
    state, identity = _verify_public_identity(request, body.id_token)

    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError as exc:
        raise ApiError(
            "VALIDATION_FAILED",
            "Timezone invalido. Use um identificador IANA, por exemplo America/Sao_Paulo.",
            details={"field": "timezone"},
        ) from exc

    # F1/F5 boundary: the public onboarding endpoint may create a TRIAL tenant,
    # but the browser can never self-assert that a purchase happened. PURCHASE becomes
    # valid only when F5 supplies a server-verified billing/checkout proof and an
    # internal entitlement transition. Until then we fail closed instead of recording
    # commercially false state.
    if body.entry_mode == "PURCHASE":
        raise ApiError(
            "PERMISSION_DENIED",
            "Onboarding por compra exige confirmacao server-side do billing; "
            "o cliente nao pode autoafirmar PURCHASE.",
            details={"entry_mode": "PURCHASE"},
        )

    scope = f"onboarding:{identity.subject}"
    idem_scope_key = f"http:create_tenant:{idem_key}"
    existing = state.idempotency.get(scope, idem_scope_key)
    normalized_document = normalize_document(body.document)

    if existing is None:
        def _create():
            if normalized_document is not None:
                state.lock_runtime_scope(f"onboarding-document:{normalized_document}")
                if state.organizations.find_by_document(normalized_document):
                    raise ApiError(
                        "INVALID_STATE",
                        "Ja existe uma empresa com este documento. Acesso deve ser "
                        "recuperado por convite/reativacao; nunca e criado um tenant duplicado.",
                        details={"field": "document"},
                    )

            tenant, unit, membership = state.organizations.create_tenant_bundle(
                company_name=body.company_name,
                document=body.document,
                segment=body.segment,
                language=body.language,
                timezone_name=body.timezone,
                entry_mode=body.entry_mode,
                # F1 security boundary: plan/entitlement is never selected by the browser.
                # F5 billing will attach a server-verified plan after trial/purchase proof.
                plan_id=None,
                identity_subject=identity.subject,
                email=identity.email,
            )
            state.audit.append(
                tenant_id=tenant.tenant_id,
                actor=membership.membership_id,
                action="TENANT_ONBOARDING_CREATE",
                target=tenant.tenant_id,
                details={
                    "entry_mode": tenant.entry_mode,
                    "default_business_unit_id": unit.business_unit_id,
                    "document_present": tenant.document_normalized is not None,
                },
            )
            return {
                "tenant_id": tenant.tenant_id,
                "business_unit_id": unit.business_unit_id,
                "membership_id": membership.membership_id,
            }

        result, _ = state.idempotency.execute(scope, idem_scope_key, _create)
    else:
        result = existing.result

    organization = state.organizations.get_organization(result["tenant_id"])
    if organization is None:
        raise ApiError("UNKNOWN", "Resultado idempotente aponta para tenant inexistente.")
    membership = state.organizations.get_membership(
        result["tenant_id"], result["membership_id"]
    )
    if membership is None or membership.identity_subject != identity.subject:
        raise ApiError("PERMISSION_DENIED", "Vinculo de onboarding nao pertence a esta identidade.")

    record, session_payload, now = _issue_session(state, identity, membership)
    response_model = TenantOnboardingResponse(
        session=session_payload,
        organization=OrganizationResponse(
            tenant_id=organization.tenant.tenant_id,
            name=organization.tenant.name,
            document=organization.tenant.document_normalized,
            segment=organization.tenant.segment,
            language=organization.tenant.language,
            timezone=organization.tenant.timezone,
            entry_mode=organization.tenant.entry_mode,
            plan_id=organization.tenant.plan_id,
            status=organization.tenant.status,
            default_business_unit_id=result["business_unit_id"],
            created_at=organization.tenant.created_at,
        ),
        membership=_serialize_membership(membership),
    )
    response = json_response(response_model, status_code=201)
    max_age = int((record.expires_at - now).total_seconds())
    set_session_cookie(response, record.session_id, max_age_seconds=max_age)
    return response


def _authorize_member_view(request: Request):
    fixture = require_auth(request)
    state = get_state(request)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(
        tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id
    )
    decision = authorize(
        principal, Permission.MEMBER_VIEW, resource, now=datetime.now(timezone.utc)
    )
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state


def _authorize_member_manage(request: Request):
    fixture = require_auth(request)
    state = get_state(request)
    note_step_up_header(request, fixture)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(
        tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id
    )
    decision = authorize(
        principal, Permission.MEMBER_MANAGE, resource, now=datetime.now(timezone.utc)
    )
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    require_step_up(request, fixture)
    return fixture, state


async def list_members(request: Request) -> JSONResponse:
    fixture, state = _authorize_member_view(request)
    memberships = state.organizations.list_memberships_for_tenant(fixture.tenant_id)
    return list_response([_serialize_membership(m) for m in memberships])


async def list_invitations(request: Request) -> JSONResponse:
    fixture, state = _authorize_member_manage(request)
    invitations = state.organizations.list_invitations_for_tenant(fixture.tenant_id)
    return list_response([_serialize_invitation(i) for i in invitations])


async def create_invitation(request: Request) -> JSONResponse:
    fixture, state = _authorize_member_manage(request)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, InvitationCreateRequest)
    email = _validate_email(body.email)

    try:
        roles = frozenset(Role(role) for role in body.roles)
    except ValueError as exc:
        raise ApiError("VALIDATION_FAILED", "Papel de usuario invalido.") from exc
    if not roles:
        raise ApiError("VALIDATION_FAILED", "Informe pelo menos um papel para o convite.")
    if Role.OWNER in roles and Role.OWNER not in fixture.roles:
        raise ApiError(
            "PERMISSION_DENIED",
            "Somente Owner pode convidar outro Owner.",
        )

    key = f"http:create_member_invitation:{idem_key}"
    existing = state.idempotency.get(fixture.tenant_id, key)
    if existing is not None:
        invitation = next(
            (
                i
                for i in state.organizations.list_invitations_for_tenant(fixture.tenant_id)
                if i.invitation_id == existing.result["invitation_id"]
            ),
            None,
        )
        if invitation is None:
            raise ApiError("UNKNOWN", "Convite idempotente nao encontrado.")
        # O token bruto e one-shot: replay nunca o reexpoe.
        return json_response(_serialize_invitation(invitation, accept_token=None), status_code=201)

    created_raw_token: str | None = None

    def _create():
        nonlocal created_raw_token

        # Tudo que pode mudar por concorrencia fica dentro da mesma unidade transacional:
        # organizacao/unidade corrente, quota, convite, auditoria e reserva idempotente.
        organization = state.organizations.get_organization(fixture.tenant_id)
        if organization is None:
            raise ApiError(
                "INVALID_STATE",
                "Este tenant ainda nao possui organizacao comercial provisionada.",
            )

        active_existing = state.organizations.find_membership_by_email(
            fixture.tenant_id, email, include_inactive=False
        )
        if active_existing is not None:
            raise ApiError("INVALID_STATE", "Este e-mail ja possui acesso ativo neste tenant.")

        unit = (
            state.organizations.get_business_unit(fixture.tenant_id, body.business_unit_id)
            if body.business_unit_id
            else state.organizations.default_business_unit(fixture.tenant_id)
        )
        if unit is None or unit.status != "ACTIVE":
            raise ApiError("NOT_FOUND", "Unidade de negocio nao encontrada neste tenant.")

        plan_id = organization.tenant.plan_id
        max_users = state.plan_user_limits.get(plan_id) if plan_id else None
        if max_users is not None:
            occupied = state.organizations.active_membership_count(fixture.tenant_id)
            reserved = state.organizations.pending_invitation_count(fixture.tenant_id)
            if occupied + reserved >= max_users:
                raise ApiError(
                    "QUOTA_EXHAUSTED",
                    "Limite de usuarios do plano atingido.",
                    details={"plan_id": plan_id, "max_users": max_users},
                )

        try:
            invitation, raw_token = state.organizations.create_invitation(
                fixture.tenant_id,
                email=email,
                roles=roles,
                business_unit_id=unit.business_unit_id,
                created_by=fixture.user_id,
            )
        except ValueError as exc:
            if str(exc) == "INVITATION_ALREADY_PENDING":
                raise ApiError(
                    "INVALID_STATE", "Ja existe um convite pendente para este e-mail."
                ) from exc
            raise

        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="MEMBER_INVITE_CREATE",
            target=invitation.invitation_id,
            details={
                "roles": sorted(role.value for role in invitation.roles),
                "business_unit_id": invitation.business_unit_id,
            },
        )
        created_raw_token = raw_token
        # Persistir apenas o identificador; nunca guardar o token bruto no replay cache.
        return {"invitation_id": invitation.invitation_id}

    result, replay = state.idempotency.execute(fixture.tenant_id, key, _create)
    invitation = next(
        (
            i
            for i in state.organizations.list_invitations_for_tenant(fixture.tenant_id)
            if i.invitation_id == result["invitation_id"]
        ),
        None,
    )
    if invitation is None:
        raise ApiError("UNKNOWN", "Convite idempotente nao encontrado.")

    return json_response(
        _serialize_invitation(
            invitation,
            accept_token=None if replay else created_raw_token,
        ),
        status_code=201,
    )


async def accept_invitation(request: Request) -> JSONResponse:
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, InvitationAcceptRequest)
    state, identity = _verify_public_identity(request, body.id_token)
    scope = f"invitation:{identity.subject}"
    scoped_key = f"http:accept_invitation:{idem_key}"

    existing = state.idempotency.get(scope, scoped_key)
    if existing is None:
        token_digest = hashlib.sha256(body.accept_token.encode("utf-8")).hexdigest()

        def _accept():
            state.lock_runtime_scope(f"invitation-token:{token_digest}")
            try:
                membership = state.organizations.accept_invitation(
                    raw_token=body.accept_token,
                    identity_subject=identity.subject,
                    email=identity.email,
                )
            except ValueError as exc:
                code = str(exc)
                if code == "INVITATION_EMAIL_MISMATCH":
                    raise ApiError("PERMISSION_DENIED", "Este convite pertence a outro e-mail.") from exc
                if code in {"INVITATION_INVALID", "INVITATION_NOT_PENDING", "INVITATION_EXPIRED"}:
                    raise ApiError("INVALID_STATE", "Convite invalido, expirado ou ja utilizado.") from exc
                if code == "TENANT_INACTIVE":
                    raise ApiError("INVALID_STATE", "Tenant inativo.") from exc
                raise
            state.audit.append(
                tenant_id=membership.tenant_id,
                actor=membership.membership_id,
                action="MEMBER_INVITE_ACCEPT",
                target=membership.membership_id,
            )
            return {
                "tenant_id": membership.tenant_id,
                "membership_id": membership.membership_id,
            }

        result, _ = state.idempotency.execute(scope, scoped_key, _accept)
    else:
        result = existing.result

    membership = state.organizations.get_membership(
        result["tenant_id"], result["membership_id"]
    )
    if membership is None or membership.identity_subject != identity.subject:
        raise ApiError("PERMISSION_DENIED", "Vinculo do convite nao pertence a esta identidade.")

    organization = state.organizations.get_organization(membership.tenant_id)
    if organization is None:
        raise ApiError("UNKNOWN", "Tenant do convite nao encontrado.")

    record, session_payload, now = _issue_session(state, identity, membership)
    response_model = TenantOnboardingResponse(
        session=session_payload,
        organization=OrganizationResponse(
            tenant_id=organization.tenant.tenant_id,
            name=organization.tenant.name,
            document=organization.tenant.document_normalized,
            segment=organization.tenant.segment,
            language=organization.tenant.language,
            timezone=organization.tenant.timezone,
            entry_mode=organization.tenant.entry_mode,
            plan_id=organization.tenant.plan_id,
            status=organization.tenant.status,
            default_business_unit_id=membership.business_unit_id,
            created_at=organization.tenant.created_at,
        ),
        membership=_serialize_membership(membership),
    )
    response = json_response(response_model)
    max_age = int((record.expires_at - now).total_seconds())
    set_session_cookie(response, record.session_id, max_age_seconds=max_age)
    return response


def _enforce_target_role_authority(actor, target) -> None:
    if Role.OWNER in target.roles and Role.OWNER not in actor.roles:
        raise ApiError("PERMISSION_DENIED", "Somente Owner pode administrar outro Owner.")


async def deactivate_member(request: Request) -> JSONResponse:
    fixture, state = _authorize_member_manage(request)
    idem_key = require_idempotency_key(request)
    membership_id = request.path_params["membershipId"]

    def _do():
        target = state.organizations.get_membership(fixture.tenant_id, membership_id)
        if target is None:
            raise ApiError("NOT_FOUND", "Usuario nao encontrado neste tenant.")
        if target.membership_id == fixture.user_id:
            raise ApiError("INVALID_STATE", "Auto-desativacao nao e permitida.")
        _enforce_target_role_authority(fixture, target)
        if Role.OWNER in target.roles and state.organizations.active_owner_count(fixture.tenant_id) <= 1:
            raise ApiError("INVALID_STATE", "O ultimo Owner ativo nunca pode ser removido.")

        updated = state.organizations.deactivate_membership(fixture.tenant_id, membership_id)
        if updated is None:
            raise ApiError("NOT_FOUND", "Usuario nao encontrado neste tenant.")
        state.sessions.invalidate_membership(updated.membership_id)
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="MEMBER_DEACTIVATE",
            target=updated.membership_id,
        )
        return _serialize_membership(updated).model_dump(mode="json")

    result, _ = state.idempotency.execute(
        fixture.tenant_id, f"http:deactivate_member:{idem_key}", _do
    )
    return JSONResponse(result)


async def reactivate_member(request: Request) -> JSONResponse:
    fixture, state = _authorize_member_manage(request)
    idem_key = require_idempotency_key(request)
    membership_id = request.path_params["membershipId"]

    def _do():
        target = state.organizations.get_membership(fixture.tenant_id, membership_id)
        if target is None:
            raise ApiError("NOT_FOUND", "Usuario nao encontrado neste tenant.")
        _enforce_target_role_authority(fixture, target)

        organization = state.organizations.get_organization(fixture.tenant_id)
        plan_id = organization.tenant.plan_id if organization else None
        max_users = state.plan_user_limits.get(plan_id) if plan_id else None
        if target.status != "ACTIVE" and max_users is not None:
            if state.organizations.active_membership_count(fixture.tenant_id) >= max_users:
                raise ApiError(
                    "QUOTA_EXHAUSTED",
                    "Limite de usuarios do plano atingido.",
                    details={"plan_id": plan_id, "max_users": max_users},
                )

        updated = state.organizations.reactivate_membership(fixture.tenant_id, membership_id)
        if updated is None:
            raise ApiError("NOT_FOUND", "Usuario nao encontrado neste tenant.")
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="MEMBER_REACTIVATE",
            target=updated.membership_id,
        )
        return _serialize_membership(updated).model_dump(mode="json")

    result, _ = state.idempotency.execute(
        fixture.tenant_id, f"http:reactivate_member:{idem_key}", _do
    )
    return JSONResponse(result)

