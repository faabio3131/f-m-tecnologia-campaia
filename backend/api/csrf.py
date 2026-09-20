"""CSRF protection for cookie/session-authenticated requests (WP-02, ADR-0018 "CSRF token
em toda mutacao").

Double-submit cookie pattern: login sets a non-HttpOnly `campaia_csrf` cookie; the browser
client must read it and echo it back as the `X-CSRF-Token` header on every mutating
request. An attacker's cross-site form/script can trigger the browser to *send* the cookie
automatically, but cannot *read* its value (same-origin policy) to also set the header, so
a forged request predictably fails this check while a legitimate same-origin request
predictably passes it.

Only applies to requests that carry the session cookie -- the fixture Bearer-token path
(local-dev/test only) is a non-browser API-client pattern with no cookies involved, so it
is not subject to CSRF the same way and is deliberately left unaffected (existing tests
send no cookies and are untouched by this middleware).
"""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .deps import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, get_state
from .errors import ApiError

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: /auth/login and /auth/callback are the entry points into a session (no session exists
#: yet to carry a CSRF token). /test-idp/* is the test-only issuer's own endpoints, a
#: separate trust boundary from this app's session cookie entirely.
_EXEMPT_PATH_PREFIXES = ("/auth/login", "/auth/callback", "/test-idp/")


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _SAFE_METHODS:
            return await call_next(request)
        if any(request.url.path.startswith(prefix) for prefix in _EXEMPT_PATH_PREFIXES):
            return await call_next(request)

        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if not session_id:
            # No session cookie -- this is the fixture Bearer-token path, untouched.
            return await call_next(request)

        state = get_state(request)
        record = state.get_session(session_id)
        if record is None:
            # require_auth (downstream) will raise the canonical UNAUTHENTICATED error;
            # this middleware only enforces CSRF for requests that DO have a live session.
            return await call_next(request)

        supplied = request.headers.get(CSRF_HEADER_NAME, "")
        if not supplied or not secrets.compare_digest(supplied, record.csrf_token):
            return ApiError(
                "PERMISSION_DENIED",
                "Missing or invalid CSRF token for a session-authenticated mutation.",
            ).to_response()

        return await call_next(request)
