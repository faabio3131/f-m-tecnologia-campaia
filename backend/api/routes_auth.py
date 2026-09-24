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
from .session import SESSION_COOKIE_NAME, clear_session_cookie, set_session_cookie


async def login(request: Request) -> JSONResponse:
    body = await parse_body(request, SessionLoginRequest)
    state = get_state(request)

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
        SessionLoginResponse(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            business_unit_id=principal.business_unit_id,
            roles=sorted(r.value for r in principal.roles),
            csrf_token=record.csrf_secret,
        ).model_dump()
    )
    max_age = int((record.expires_at - now).total_seconds())
    set_session_cookie(response, record.session_id, max_age_seconds=max_age)
    return response


async def logout(request: Request) -> Response:
    state = get_state(request)
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is not None:
        state.sessions.invalidate(session_id)

    response = Response(status_code=204)
    clear_session_cookie(response)
    return response
