"""Login/logout reais (item 1.3/WP-02, ADR-0018 + ADR-0022).

Fluxo: o frontend chama `GET /auth/login-nonce` (guarda o nonce de pre-login), autentica o
usuario contra o Google Identity Platform e obtem um ID token, e chama `POST /auth/session`
com o `id_token` + o `login_csrf_token` recebido do primeiro passo. Este endpoint verifica o
ID token (`state.id_token_verifier`), o nonce de pre-login (achado de fm-security-review,
24/09/2026 -- ver `session.py`), resolve o e-mail verificado contra o diretorio interno do
CampaIA (`state.identity_directory` -- nunca autoprovisiona), e cria uma sessao server-side
(cookie `HttpOnly`/`Secure`/`SameSite=Lax`).

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
from .helpers import json_response, parse_body
from .models import LoginNonceResponse, SessionLoginRequest, SessionLoginResponse
from .session import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    generate_login_csrf_nonce,
    login_csrf_token_valid,
    set_login_csrf_cookie,
    set_session_cookie,
)


async def login_nonce(request: Request) -> JSONResponse:
    """Passo 1 do login: emite o nonce de pre-login (double-submit) que `POST
    /auth/session` vai exigir de volta -- mitigacao do achado de login-CSRF
    (fm-security-review, 24/09/2026, ver `session.py`)."""
    nonce = generate_login_csrf_nonce()
    response = json_response(LoginNonceResponse(login_csrf_token=nonce))
    set_login_csrf_cookie(response, nonce)
    return response


async def login(request: Request) -> JSONResponse:
    body = await parse_body(request, SessionLoginRequest)
    state = get_state(request)

    if not login_csrf_token_valid(request, body.login_csrf_token):
        # Achado de fm-security-review (24/09/2026): sem isto, um site malicioso podia
        # disparar este endpoint com o PROPRIO id_token, fazendo a vitima receber um
        # cookie de sessao autenticado como o atacante ("login CSRF"). Ver session.py.
        raise ApiError(
            "PERMISSION_DENIED",
            "Token de pre-login (login_csrf_token) ausente ou invalido -- chame "
            "GET /auth/login-nonce antes de POST /auth/session.",
        )

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
