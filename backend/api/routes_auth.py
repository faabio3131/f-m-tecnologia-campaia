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

from .deps import get_state
from .errors import ApiError
from .helpers import parse_body
from .models import SessionLoginRequest, SessionLoginResponse
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

    principal = state.identity_directory.resolve(identity.email)
    if principal is None:
        # Fail-closed por decisao do Diretor (24/09/2026): identidade do Google provada,
        # mas sem vinculo interno no CampaIA -- NUNCA autoprovisiona tenant/usuario.
        # Autoprovisionamento e decisao de produto separada, fora do escopo do WP-02.
        raise ApiError(
            "PERMISSION_DENIED",
            "Usuario autenticado pelo provedor de identidade, mas sem vinculo com "
            "nenhum tenant do CampaIA.",
        )

    now = datetime.now(timezone.utc)
    record = state.sessions.create(principal, now=now)

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
