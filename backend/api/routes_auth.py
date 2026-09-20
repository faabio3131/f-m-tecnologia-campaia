"""WP-02 real Web authentication: /auth/login, /auth/callback, /auth/logout.

Provider-neutral by construction: this module only ever talks to the OIDC *standard*
surface (api/oidc.py) via an OidcIssuerConfig, never a vendor SDK. Which config is active
is resolved fresh on every request from AppState -- a real provider (CAMPAIA_OIDC_* env
vars) if configured, else the fail-closed test identity provider if enabled, else the
request is refused rather than silently degraded.
"""

from __future__ import annotations

import httpx
from starlette.requests import Request
from starlette.responses import RedirectResponse

from .deps import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME, get_state
from .errors import ApiError
from .oidc import (
    SESSION_TTL_SECONDS,
    OidcIssuerConfig,
    build_authorize_url,
    generate_nonce,
    generate_pkce_pair,
    verify_id_token,
)
from .state import TokenPrincipal

#: Defaults to same-origin "/" so a bare /auth/login (no redirect_after_login) never
#: forwards to an attacker-controlled external host. Callers that want a different
#: post-login destination must supply a same-origin-relative path explicitly.
_DEFAULT_REDIRECT_AFTER_LOGIN = "/"


def _resolve_oidc_config(request: Request) -> tuple[OidcIssuerConfig, bool]:
    """Returns (config, is_test_idp). Raises ApiError(503) if neither a real provider nor
    the test identity provider is available -- /auth/login and /auth/callback must never
    silently do nothing.
    """
    state = get_state(request)
    if state.oidc_config is not None:
        return state.oidc_config, False

    if state.test_idp is not None:
        from .state import TEST_IDP_CLIENT_ID, TEST_IDP_CLIENT_SECRET

        base = str(request.base_url).rstrip("/")
        return (
            OidcIssuerConfig(
                issuer=state.test_idp.issuer(base),
                authorization_endpoint=f"{base}/test-idp/authorize",
                token_endpoint=f"{base}/test-idp/token",
                jwks_uri=f"{base}/test-idp/jwks.json",
                client_id=TEST_IDP_CLIENT_ID,
                client_secret=TEST_IDP_CLIENT_SECRET,
                redirect_uri=f"{base}/auth/callback",
            ),
            True,
        )

    raise ApiError(
        "UNKNOWN",
        "No OIDC identity provider is configured (no CAMPAIA_OIDC_* env vars, and the "
        "test identity provider is disabled outside test/local-dev). Cannot start login.",
        status_code=503,
    )


def _redirect_target(request: Request) -> str:
    requested = request.query_params.get("redirect_after_login", _DEFAULT_REDIRECT_AFTER_LOGIN)
    # Same-origin-relative only -- never redirect the browser to an external host after
    # login, regardless of what a caller supplies (open-redirect prevention).
    if not requested.startswith("/") or requested.startswith("//"):
        return _DEFAULT_REDIRECT_AFTER_LOGIN
    return requested


async def login(request: Request) -> RedirectResponse:
    state = get_state(request)
    config, _ = _resolve_oidc_config(request)

    code_verifier, code_challenge = generate_pkce_pair()
    nonce = generate_nonce()
    redirect_after_login = _redirect_target(request)

    state_value = state.create_pending_login(
        nonce=nonce, code_verifier=code_verifier, redirect_after_login=redirect_after_login
    )

    authorize_url = build_authorize_url(
        config, state=state_value, nonce=nonce, code_challenge=code_challenge
    )
    return RedirectResponse(url=authorize_url, status_code=302)


async def callback(request: Request) -> RedirectResponse:
    state = get_state(request)
    config, is_test_idp = _resolve_oidc_config(request)

    code = request.query_params.get("code")
    state_param = request.query_params.get("state")
    if not code or not state_param:
        raise ApiError("VALIDATION_FAILED", "Missing code or state on /auth/callback.")

    pending = state.pop_pending_login(state_param)
    if pending is None:
        raise ApiError(
            "UNAUTHENTICATED",
            "Unknown, expired, or already-used login attempt (state).",
        )

    # Real HTTP-shaped request/response for the token exchange -- exercises the exact same
    # code path (and the ID token's signature verification against a live JWKS fetch)
    # whether the issuer is the in-process test identity provider or a real external one.
    if is_test_idp:
        transport = httpx.ASGITransport(app=request.app)
        base_url = str(request.base_url).rstrip("/")
        client_kwargs = {"transport": transport, "base_url": base_url}
    else:
        client_kwargs = {}

    async with httpx.AsyncClient(**client_kwargs) as client:
        token_response = await client.post(
            config.token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.redirect_uri,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code_verifier": pending.code_verifier,
            },
        )

        if token_response.status_code != 200:
            raise ApiError(
                "UNAUTHENTICATED",
                f"Token exchange with the identity provider failed: {token_response.text}",
            )

        id_token = token_response.json().get("id_token")
        if not id_token:
            raise ApiError("UNAUTHENTICATED", "Identity provider response is missing id_token.")

        # Fetched via the SAME client (real HTTP for a real provider, ASGI transport for
        # the test IdP) -- see oidc.verify_id_token's docstring for why this is never
        # delegated to PyJWT's own JWKS fetcher.
        jwks_response = await client.get(config.jwks_uri)
        if jwks_response.status_code != 200:
            raise ApiError(
                "UNAUTHENTICATED",
                f"Fetching the identity provider's JWKS failed: {jwks_response.text}",
            )
        jwks = jwks_response.json()

    try:
        verified = verify_id_token(id_token, config=config, expected_nonce=pending.nonce, jwks=jwks)
    except Exception as exc:  # noqa: BLE001 -- any verification failure is UNAUTHENTICATED
        raise ApiError("UNAUTHENTICATED", f"ID token verification failed: {exc}") from exc

    principal = TokenPrincipal.from_verified_id_token(verified)
    session_id, csrf_token = state.create_session(principal)

    response = RedirectResponse(url=pending.redirect_after_login, status_code=302)
    _set_session_cookies(response, session_id=session_id, csrf_token=csrf_token)
    return response


async def logout(request: Request) -> RedirectResponse:
    state = get_state(request)
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        state.delete_session(session_id)

    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    return response


def _set_session_cookies(response: RedirectResponse, *, session_id: str, csrf_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=SESSION_TTL_SECONDS,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
    )
