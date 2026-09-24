"""Request-level dependencies: real session auth, dev bearer fixture, step-up,
idempotency key extraction.

Invariant #1 from the spec: tenant_id is NEVER accepted from the client. It is derived
here, from the authenticated principal only, and nowhere else in the app reads a
client-supplied tenant_id.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from starlette.requests import Request

from campaia_core.permissions import Principal

from .errors import ApiError
from .session import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from .state import AppState, TokenPrincipal

MIN_IDEMPOTENCY_KEY_LEN = 16
MAX_IDEMPOTENCY_KEY_LEN = 128

#: Metodos que mutam estado -- exigem CSRF valido quando autenticados via sessao real
#: (cookie). O fixture de bearer token (dev/teste) nunca passa por aqui: nao usa cookie,
#: entao nao ha CSRF a verificar nesse caminho (mesma logica de qualquer API sem cookie).
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_state(request: Request) -> AppState:
    return request.app.state.campaia


def _require_auth_via_session(request: Request, state: AppState) -> TokenPrincipal | None:
    """Caminho real (ADR-0018): sessao server-side via cookie HttpOnly. Devolve None se
    nao houver cookie (deixa require_auth tentar o fixture de dev/teste); levanta
    ApiError fail-closed se o cookie EXISTIR mas for invalido/expirado -- um cookie
    presente e ruim nunca cai silenciosamente para outro mecanismo."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is None:
        return None

    record = state.sessions.get(session_id)
    now = datetime.now(timezone.utc)
    if record is None or record.is_expired(now=now):
        raise ApiError("UNAUTHENTICATED", "Sessao invalida ou expirada.")

    if request.method in _MUTATING_METHODS:
        presented = request.headers.get(CSRF_HEADER_NAME)
        if not record.csrf_token_valid(presented):
            raise ApiError("PERMISSION_DENIED", "Token CSRF ausente ou invalido.")

    return record.principal


def _require_auth_via_dev_fixture(request: Request, state: AppState) -> TokenPrincipal:
    """Fixture de bearer token, SOMENTE para test/dev-local (AppState garante, por
    construcao, que `state.tokens` fica vazio fora desses ambientes -- ver
    api/state.py::DEV_AUTH_FIXTURE_ALLOWED_ENVS). Nunca um formato de credencial real."""
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError("UNAUTHENTICATED", "Missing or malformed Authorization header.")
    token = header[len("Bearer ") :].strip()
    if not token:
        raise ApiError("UNAUTHENTICATED", "Empty bearer token.")

    principal = state.tokens.get(token)
    if principal is None:
        raise ApiError("UNAUTHENTICATED", "Unknown or expired token.")
    return principal


def require_auth(request: Request) -> TokenPrincipal:
    """Sessao real (cookie) primeiro; fixture de bearer token (test/dev-local) só como
    fallback quando nao ha cookie de sessao nenhum. 401/403 fail-closed em qualquer outro
    caso -- nunca um bypass silencioso entre os dois mecanismos."""
    state = get_state(request)

    principal = _require_auth_via_session(request, state)
    if principal is not None:
        return principal

    return _require_auth_via_dev_fixture(request, state)


def note_step_up_header(request: Request, fixture: TokenPrincipal) -> None:
    """If X-Step-Up-Token is present, record "stepped up now" into AppState.

    Must run BEFORE any campaia_core.permissions.authorize() call on this request, since
    authorize() reads Principal.step_up_at to decide STEP_UP_REQUIRED itself (see
    permissions.py REQUIRES_STEP_UP / STEP_UP_MAX_AGE). If this ran after authorize(), the
    very first request with a valid header would still be rejected because the domain
    check would see step_up_at=None. This function never rejects -- it only records;
    rejection for a *missing* header on a sensitive endpoint is the domain's own
    STEP_UP_REQUIRED coming out of authorize(), so the sandbox's "any non-empty value is
    valid" rule and the real STEP_UP_MAX_AGE recency window are both genuinely enforced by
    campaia_core, not re-implemented here.
    """
    value = request.headers.get("x-step-up-token", "").strip()
    if value:
        state = get_state(request)
        state.record_step_up(fixture.tenant_id, fixture.user_id, at=datetime.now(timezone.utc))


def require_step_up(request: Request, fixture: TokenPrincipal) -> None:
    """Back-compat explicit check, for permissions that are gated at the HTTP layer only
    (not every sensitive endpoint's permission is in campaia_core.permissions.
    REQUIRES_STEP_UP -- e.g. OAuth start has no dedicated Permission of its own beyond
    CONNECTION_MANAGE, which IS covered, so this mostly acts as a defence-in-depth
    re-check). Must be called AFTER note_step_up_header/authorize.
    """
    value = request.headers.get("x-step-up-token", "").strip()
    if not value:
        raise ApiError(
            "STEP_UP_REQUIRED",
            "This operation requires a recent step-up re-authentication "
            "(X-Step-Up-Token header).",
        )


def require_idempotency_key(request: Request) -> str:
    key = request.headers.get("idempotency-key", "").strip()
    if not key:
        raise ApiError(
            "VALIDATION_FAILED",
            "This operation requires an Idempotency-Key header.",
            details={"header": "Idempotency-Key"},
        )
    if not (MIN_IDEMPOTENCY_KEY_LEN <= len(key) <= MAX_IDEMPOTENCY_KEY_LEN):
        raise ApiError(
            "VALIDATION_FAILED",
            f"Idempotency-Key must be {MIN_IDEMPOTENCY_KEY_LEN}-"
            f"{MAX_IDEMPOTENCY_KEY_LEN} characters.",
            details={"header": "Idempotency-Key", "length": len(key)},
        )
    return key


def build_domain_principal(state: AppState, fixture: TokenPrincipal) -> Principal:
    """Build the real campaia_core.permissions.Principal, including step_up_at.

    This makes the RBAC/ABAC checks in permissions.authorize (MFA, step-up recency,
    value ceilings) genuinely load-bearing rather than re-implemented at the HTTP layer.
    """
    step_up_at = state.last_step_up(fixture.tenant_id, fixture.user_id)
    return fixture.to_domain_principal(step_up_at=step_up_at)


def reject_client_tenant_id(body: dict) -> None:
    """Defence in depth: if a client-supplied body somehow carries tenant_id, refuse it
    rather than silently ignoring it. Pydantic-free version: `models.py` schemas simply
    do not declare a tenant_id field at all, so this only fires for raw/extra dict usage.
    """
    if "tenant_id" in body:
        raise ApiError(
            "VALIDATION_FAILED",
            "tenant_id is derived from the authenticated principal and must not be "
            "supplied by the client.",
            details={"field": "tenant_id"},
        )
