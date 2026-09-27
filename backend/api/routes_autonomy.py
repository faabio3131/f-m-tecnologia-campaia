from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.autonomy import AutonomyLevel, AutonomySettings
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
from .helpers import json_response, parse_body
from .models import AutonomyResponse, AutonomyUpdateRequest

#: Contract enum: [ASSISTENTE, APROVADO, LIMITADO, OPERACIONAL], matching
#: campaia_core.autonomy.AutonomyLevel's own member names exactly (achado 11).
_LEVEL_LABELS = {
    AutonomyLevel.ASSISTENTE: "ASSISTENTE",
    AutonomyLevel.APROVADO: "APROVADO",
    AutonomyLevel.LIMITADO: "LIMITADO",
    AutonomyLevel.OPERACIONAL: "OPERACIONAL",
}

#: Contract's `always_require_human` (achado 11): the ALWAYS_REQUIRE_HUMAN action-kind
#: names from campaia_core.autonomy are the real, closed list of triggers that require a
#: human at ANY autonomy level -- surfaced verbatim rather than inventing a separate list.
from campaia_core.autonomy import ALWAYS_REQUIRE_HUMAN

_ALWAYS_REQUIRE_HUMAN_NAMES = sorted(a.value for a in ALWAYS_REQUIRE_HUMAN)


def _authorize(request: Request, permission: Permission):
    fixture = require_auth(request)
    state = get_state(request)
    note_step_up_header(request, fixture)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state, principal


def _serialize(settings: AutonomySettings, *, updated_at: datetime) -> AutonomyResponse:
    return AutonomyResponse(
        level=int(settings.level),
        level_label=_LEVEL_LABELS[settings.level],
        max_level_allowed=int(settings.max_level_allowed),
        always_require_human=_ALWAYS_REQUIRE_HUMAN_NAMES,
        # Contract declares this as a number, not a string (achado 11).
        max_budget_change_pct=float(settings.max_budget_change_pct),
        updated_at=updated_at,
    )


async def get_autonomy(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    settings = state.tenant_autonomy.get(fixture.tenant_id, AutonomySettings())
    updated_at = state.tenant_autonomy_updated_at.get(fixture.tenant_id, datetime.now(timezone.utc))
    return json_response(_serialize(settings, updated_at=updated_at))


async def put_autonomy(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.AUTONOMY_CHANGE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, AutonomyUpdateRequest)

    # Idempotency check happens BEFORE any validation whose outcome can change after the
    # first successful call, same pattern as publish_campaign/patch_budget. ACHADO 19
    # (Fase 3, reproduzido por execucao real nesta sessao): approval.status agora passa
    # de APPROVED para APPLIED apos o uso (abaixo), entao este gate precisa vir antes da
    # checagem de status -- senao um replay legitimo da MESMA Idempotency-Key seria
    # incorretamente rejeitado como "aprovacao ja usada". Uma tentativa NOVA
    # (Idempotency-Key diferente) reaproveitando o mesmo approval_id continua caindo nas
    # checagens abaixo normalmente.
    # SECURITY FIX (Fase C6, 27/09/2026 -- auditoria independente): mesma correcao de
    # patch_budget -- o replay tinha que devolver `existing.result` (a resposta
    # ORIGINAL desta chamada), nunca uma re-serializacao do estado atual.
    existing = state.idempotency.get(fixture.tenant_id, f"http:put_autonomy:{idem_key}")
    if existing is not None:
        return JSONResponse(existing.result)

    # Contract requires approval_id for /autonomy PUT (achado 12): exactly like publish
    # and patch_budget, the level change must reference an already-APPROVED
    # ApprovalRequest belonging to this tenant before it is applied.
    approval = state.approvals.get(fixture.tenant_id, body.approval_id)
    if approval is None:
        raise ApiError("APPROVAL_REQUIRED", "approval_id not found for this tenant.")
    if approval.status != "APPROVED":
        raise ApiError("APPROVAL_REQUIRED", "Approval has not been granted.")

    current = state.tenant_autonomy.get(fixture.tenant_id, AutonomySettings())
    try:
        requested_level = AutonomyLevel(body.level)
    except ValueError:
        raise ApiError("VALIDATION_FAILED", f"Invalid autonomy level: {body.level}.")

    try:
        updated = AutonomySettings(
            level=requested_level,
            max_level_allowed=current.max_level_allowed,
            max_budget_change_pct=current.max_budget_change_pct,
        )
    except ValueError as exc:
        # AutonomySettings.__post_init__ refuses level > max_level_allowed -- this is the
        # domain's own anti-self-promotion guard (I-11), not re-implemented here.
        raise ApiError("VALIDATION_FAILED", str(exc))

    def _do_update():
        now = datetime.now(timezone.utc)
        state.tenant_autonomy[fixture.tenant_id] = updated
        state.tenant_autonomy_updated_at[fixture.tenant_id] = now
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="AUTONOMY_CHANGE",
            target=fixture.tenant_id,
            details={"new_level": int(requested_level), "approval_id": body.approval_id},
        )
        # ACHADO 19: consome a aprovacao aqui, DENTRO do fecho -- so roda para uma
        # Idempotency-Key genuinamente nova. Resposta final tambem construida aqui
        # (Fase C6): e' este valor que fica cacheado para replay exato.
        approval.status = "APPLIED"
        return _serialize(updated, updated_at=now).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:put_autonomy:{idem_key}", _do_update
    )
    return JSONResponse(result)
