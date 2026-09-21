"""Request-level dependencies: fake bearer auth, step-up, idempotency key extraction.

Invariant #1 from the spec: tenant_id is NEVER accepted from the client. It is derived
here, from the bearer token only, and nowhere else in the app reads a client-supplied
tenant_id.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from starlette.requests import Request

from campaia_core.permissions import Principal

from .errors import ApiError
from .oidc import SessionRecord
from .state import AppState, TokenPrincipal

MIN_IDEMPOTENCY_KEY_LEN = 16
MAX_IDEMPOTENCY_KEY_LEN = 128

#: WP-02 / ADR-0018: HttpOnly, so client-side script can never read it (mitigates the
#: session id itself being exfiltrated via XSS). Never localStorage/sessionStorage.
SESSION_COOKIE_NAME = "campaia_session"
#: Deliberately NOT HttpOnly -- the double-submit CSRF pattern requires browser JS to read
#: this value and echo it back as a header on mutating requests (see CSRFMiddleware in
#: api/csrf.py). It is a per-session random token, not itself a credential: knowing it
#: without also holding the (HttpOnly) session cookie grants nothing.
CSRF_COOKIE_NAME = "campaia_csrf"
CSRF_HEADER_NAME = "x-csrf-token"


def get_state(request: Request) -> AppState:
    return request.app.state.campaia


def require_auth(request: Request) -> TokenPrincipal:
    """Resolves the authenticated principal for this request. Two mechanisms, checked in
    order:

    1. Real Web session (WP-02, ADR-0018) -- an opaque, HttpOnly session cookie looked up
       in AppState.sessions. This is the only mechanism a browser client should ever use.
    2. Fixture Bearer token -- a local-dev/test-only fallback, itself fail-closed by
       construction (AppState.__post_init__ refuses to seed it outside CAMPAIA_ENV=
       test|local_dev). Existing API tests use this path unchanged.

    401 (UNAUTHENTICATED) on anything else -- an unknown, expired, or revoked session and a
    missing/unknown Bearer token are deliberately indistinguishable to the caller (no
    signal about *why* auth failed beyond "not authenticated").
    """
    state = get_state(request)

    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        record = state.get_session(session_id)
        if record is None:
            raise ApiError("UNAUTHENTICATED", "Session is invalid, expired, or revoked.")
        return record.principal

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


def require_web_session(request: Request) -> tuple[str, SessionRecord]:
    """WP-03: like require_auth, but ONLY the real Web session cookie path -- never the
    fixture Bearer token fallback. /session/memberships and /session/switch-tenant read
    and mutate AppState.sessions by session id, which a fixture Bearer token (test/local-dev
    only, never itself a session) simply does not have. Returns (session_id, record) since
    switch-tenant needs the id to replace the session, not just the principal it currently
    resolves to.
    """
    state = get_state(request)
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise ApiError("UNAUTHENTICATED", "No Web session cookie present.")
    record = state.get_session(session_id)
    if record is None:
        raise ApiError("UNAUTHENTICATED", "Session is invalid, expired, or revoked.")
    return session_id, record


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
