"""Login/logout reais (item 1.3/WP-02, ADR-0018 + ADR-0022).

Fluxo: o frontend autentica o usuario contra o Google Identity Platform e obtem um ID
token; este endpoint verifica esse token (`state.id_token_verifier`), resolve o e-mail
verificado contra o diretorio interno do CampaIA (`state.identity_directory` -- nunca
autoprovisiona), e cria uma sessao server-side (cookie `HttpOnly`/`Secure`/`SameSite=Lax`).

Identidade do Google prova QUEM e o usuario; tenant_id/roles/business_unit_id vem SEMPRE
do diretorio interno, nunca de claim do provedor -- por isso este modulo nunca constroi um
`TokenPrincipal` a partir do id_token, so consulta o diretorio.
"""

from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from campaia_core.identity_provider import IdentityError

from .deps import get_state, require_session_record, session_key_for
from .errors import ApiError
from .helpers import parse_body
from .models import (
    MembershipItem,
    MembershipsResponse,
    SessionLoginRequest,
    SessionLoginResponse,
    SwitchMembershipRequest,
)
from .session import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    is_same_origin,
    set_session_cookie,
)


def _serialize_session(principal, *, csrf_token: str) -> SessionLoginResponse:
    return SessionLoginResponse(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        business_unit_id=principal.business_unit_id,
        roles=sorted(r.value for r in principal.roles),
        csrf_token=csrf_token,
    )


async def login(request: Request) -> JSONResponse:
    state = get_state(request)

    # Achado de fm-security-review (24/09/2026), corrigido por decisao do Diretor:
    # login-CSRF. Checado ANTES de tocar em qualquer credencial -- uma origem nao
    # permitida nunca chega a gastar uma verificacao de id_token.
    if not is_same_origin(request, state.allowed_origins):
        raise ApiError(
            "PERMISSION_DENIED",
            "Origem da requisicao ausente, invalida ou nao autorizada para login.",
        )

    body = await parse_body(request, SessionLoginRequest)

    try:
        identity = state.id_token_verifier.verify(body.id_token)
    except IdentityError as exc:
        raise ApiError("UNAUTHENTICATED", f"ID token invalido: {exc}") from exc

    if not identity.email_verified:
        raise ApiError(
            "UNAUTHENTICATED", "O provedor de identidade nao confirma este e-mail como verificado."
        )

    memberships = state.identity_directory.resolve_all(identity.email, subject=identity.subject)
    if not memberships:
        # Fail-closed por decisao do Diretor (24/09/2026): identidade do Google provada,
        # mas sem vinculo interno no CampaIA -- NUNCA autoprovisiona tenant/usuario.
        # Autoprovisionamento e decisao de produto separada, fora do escopo do WP-02.
        raise ApiError(
            "PERMISSION_DENIED",
            "Usuario autenticado pelo provedor de identidade, mas sem vinculo com "
            "nenhum tenant do CampaIA.",
        )

    # WP-03 (25/09/2026): login sempre entra pelo primeiro vinculo cadastrado (mesmo
    # comportamento de sempre quando ha' so 1); os demais ficam disponiveis para troca via
    # POST /auth/session/switch, sem precisar de novo login.
    principal = memberships[0]
    now = datetime.now(timezone.utc)
    # IDENTITY HARDENING (27/09/2026 -- correcao final pre-Google-Ads): `identity.subject`
    # (o `sub` do provedor, verificado por `state.id_token_verifier` acima) capturado no
    # login -- usado depois por `api/deps.py::_is_genuine_step_up` como o binding de
    # identidade preferido para step-up (mais estavel que e-mail, que em tese pode ser
    # reciclado/ter variacao de caixa entre provedores).
    record = state.sessions.create(
        principal, now=now, available_principals=memberships, subject=identity.subject
    )

    response = JSONResponse(
        _serialize_session(principal, csrf_token=record.csrf_secret).model_dump()
    )
    max_age = int((record.expires_at - now).total_seconds())
    set_session_cookie(response, record.session_id, max_age_seconds=max_age)
    return response


async def get_session(request: Request) -> JSONResponse:
    """Recuperacao do CSRF apos reload (achado de fm-security-review, 24/09/2026,
    corrigido por decisao do Diretor): permite ao frontend reobter o `csrf_token` da
    sessao atual sem novo login. So le a sessao existente -- nunca a rotaciona/estende,
    nunca aceita o fixture de bearer token (essa rota so faz sentido para sessao real).

    Nao expoe: session_id, cookies, secrets internos, ID token ou claims do Google --
    a resposta e exatamente o mesmo shape de `login()` (user_id/tenant_id/
    business_unit_id/roles/csrf_token), nada mais.
    """
    state = get_state(request)
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is None:
        raise ApiError("UNAUTHENTICATED", "Nenhuma sessao ativa.")

    record = state.sessions.get(session_id)
    if record is None or record.is_expired(now=datetime.now(timezone.utc)):
        raise ApiError("UNAUTHENTICATED", "Sessao invalida ou expirada.")

    return JSONResponse(
        _serialize_session(record.principal, csrf_token=record.csrf_secret).model_dump()
    )


async def logout(request: Request) -> Response:
    state = get_state(request)
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is not None:
        state.sessions.invalidate(session_id)

    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


async def list_memberships(request: Request) -> JSONResponse:
    """WP-03 (25/09/2026): lista os vinculos (tenant/unidade/papeis) da sessao real
    atual -- nunca do e-mail "ao vivo" (ver docstring de SessionRecord.available_principals
    em api/session.py). Fixture de bearer token (dev/teste) e recusado aqui via
    `require_session_record` -- essa rota so faz sentido para sessao real."""
    record = require_session_record(request)
    items = [
        MembershipItem(
            user_id=membership.user_id,
            tenant_id=membership.tenant_id,
            business_unit_id=membership.business_unit_id,
            roles=sorted(r.value for r in membership.roles),
            active=membership.user_id == record.principal.user_id,
        )
        for membership in record.available_principals
    ]
    return JSONResponse(MembershipsResponse(memberships=items).model_dump())


async def switch_membership(request: Request) -> JSONResponse:
    """WP-03 (25/09/2026): troca o vinculo ATIVO da sessao para outro vinculo real da
    MESMA identidade -- nunca aceita um tenant_id livre do corpo da requisicao (so um
    `user_id` que precisa bater com um dos `available_principals` capturados no login).
    Mesma sessao/cookie/csrf_secret depois da troca (ver
    SessionStore.switch_principal) -- so o principal ativo muda. `require_session_record`
    ja valida CSRF (metodo mutante) antes de chegarmos aqui.

    SECURITY FIX (Fase 3, achado 3, 27/09/2026 -- auditoria independente): `step_up_at`
    (campaia_core.permissions.REQUIRES_STEP_UP) e' chaveado por
    `(tenant_id, user_id, session_key)` em AppState (Fase C3) -- so isso ja bastava para
    o step-up de A nao valer para B na primeira troca (user_id diferente). Mas ao voltar
    de B para A DENTRO da mesma sessao, o par (tenant_id, user_id) de A volta a ser
    identico ao de antes, e o step-up antigo de A ressuscitava sem reautenticacao nova --
    contra a regra exigida: QUALQUER troca de vinculo invalida TODO step-up daquela
    sessao. Por isso esta rota chama explicitamente
    `state.invalidate_step_up_for_session` a CADA troca bem-sucedida, antes de devolver a
    resposta -- nao e' mais um efeito colateral implicito do modelo de chaves, e' uma
    acao deliberada.
    """
    record = require_session_record(request)
    body = await parse_body(request, SwitchMembershipRequest)
    state = get_state(request)

    target = next(
        (m for m in record.available_principals if m.user_id == body.user_id), None
    )
    if target is None:
        # Achado de fm-security-review (25/09/2026): uma tentativa de trocar para um
        # vinculo que nao pertence a esta identidade e' um sinal relevante (poderia ser
        # erro de UI ou tentativa de sondagem) -- fica no audit log mesmo assim, com o
        # tenant/ator ORIGINAIS (a troca nunca chegou a acontecer).
        state.audit.append(
            tenant_id=record.principal.tenant_id,
            actor=record.principal.user_id,
            action="SESSION_SWITCH_REJECTED",
            target=body.user_id,
            details={"reason": "membership_not_owned_by_identity"},
        )
        raise ApiError(
            "PERMISSION_DENIED",
            "O vinculo solicitado nao pertence a esta identidade.",
        )

    updated = state.sessions.switch_principal(record.session_id, target)
    if updated is None:
        # So acontece se a sessao expirou/foi invalidada entre require_session_record e
        # aqui (janela de corrida real, ainda que estreita) -- fail-closed, nunca finge
        # sucesso.
        raise ApiError("UNAUTHENTICATED", "Sessao invalida ou expirada.")

    # SECURITY FIX (achado 3): toda troca de vinculo invalida TODO step-up desta sessao,
    # inclusive o do vinculo ao qual ela volta depois (ver docstring acima).
    state.invalidate_step_up_for_session(session_key_for(request))

    state.audit.append(
        tenant_id=updated.principal.tenant_id,
        actor=updated.principal.user_id,
        action="SESSION_SWITCH",
        target=updated.principal.user_id,
        details={
            "from_tenant_id": record.principal.tenant_id,
            "from_user_id": record.principal.user_id,
            "to_tenant_id": updated.principal.tenant_id,
        },
    )

    return JSONResponse(
        _serialize_session(updated.principal, csrf_token=updated.csrf_secret).model_dump()
    )
