"""Canonical HTTP error taxonomy for the BFF layer.

Maps the contract's error codes to HTTP status codes and a uniform JSON body:
{code, message, details, assisted_flow_url}. Domain exceptions from campaia_core
(CampaiaError subclasses) are translated here at the boundary -- the domain layer itself
never knows about HTTP.
"""

from __future__ import annotations

from starlette.responses import JSONResponse

# Canonical codes from the contract.
UNAUTHENTICATED = "UNAUTHENTICATED"
PERMISSION_DENIED = "PERMISSION_DENIED"
STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
VALIDATION_FAILED = "VALIDATION_FAILED"
INVALID_STATE = "INVALID_STATE"
CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
BUDGET_LIMIT = "BUDGET_LIMIT"
RATE_LIMITED = "RATE_LIMITED"
QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
POLICY_VIOLATION = "POLICY_VIOLATION"
KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
NOT_FOUND = "NOT_FOUND"
TRANSIENT = "TRANSIENT"
UNKNOWN = "UNKNOWN"

#: Default HTTP status per canonical code. Individual call sites may override.
STATUS_BY_CODE: dict[str, int] = {
    UNAUTHENTICATED: 401,
    PERMISSION_DENIED: 403,
    STEP_UP_REQUIRED: 403,
    APPROVAL_REQUIRED: 403,
    VALIDATION_FAILED: 422,
    INVALID_STATE: 409,
    CAPABILITY_UNSUPPORTED: 422,
    BUDGET_LIMIT: 422,
    RATE_LIMITED: 429,
    QUOTA_EXHAUSTED: 429,
    POLICY_VIOLATION: 422,
    KILL_SWITCH_ACTIVE: 409,
    NOT_FOUND: 404,
    TRANSIENT: 503,
    UNKNOWN: 500,
    # campaia_core.permissions.DenialCode values not already covered above by name.
    # These are domain-level denial reasons surfaced verbatim as the HTTP error code
    # (rather than collapsed into PERMISSION_DENIED) because they are more specific and
    # more actionable for a client than a generic 403.
    "MFA_REQUIRED": 403,
    "VALUE_CEILING": 403,
    "SEPARATION_OF_DUTIES": 403,
    # campaia_core.connectors.ConnectorErrorCode values not previously mapped here
    # (P-19, found 2026-09-03 while building the user-facing error catalog). Without
    # these, from_domain_error() below silently collapsed all three to UNKNOWN/500,
    # even though VALIDATION_REJECTED is genuinely raised today (campaia_core/saga.py,
    # PublicationSaga._publish_channel) and simulator.py can script any of the ten
    # ConnectorErrorCode values as a scripted failure. AUTH_EXPIRED mirrors
    # UNAUTHENTICATED: the platform-side credential is no longer valid, not ours.
    # VALIDATION_REJECTED mirrors VALIDATION_FAILED: the external platform rejected the
    # submitted content/config. PARTIAL_FAILURE uses 207 Multi-Status because it is
    # genuinely a mixed outcome (some channels published, some did not), not a full
    # failure -- collapsing it to 422 would misrepresent a partial success as an error.
    "AUTH_EXPIRED": 401,
    "VALIDATION_REJECTED": 422,
    "PARTIAL_FAILURE": 207,
}


class ApiError(Exception):
    """Raised by route handlers; translated to the canonical JSON error body."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        details: dict | None = None,
        assisted_flow_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code or STATUS_BY_CODE.get(code, 500)
        self.details = details or {}
        self.assisted_flow_url = assisted_flow_url

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "assisted_flow_url": self.assisted_flow_url,
            },
            status_code=self.status_code,
        )


def from_domain_error(exc: Exception) -> ApiError:
    """Translate a campaia_core CampaiaError (or ConnectorError) into an ApiError.

    Domain error `.code` values already line up with most of the canonical taxonomy
    (see campaia_core/errors.py and connectors.py) -- this is a thin passthrough plus a
    default for anything unmapped.
    """
    code = getattr(exc, "code", UNKNOWN)
    if code not in STATUS_BY_CODE:
        code = UNKNOWN
    details = dict(getattr(exc, "details", {}) or {})
    assisted_flow_url = getattr(exc, "assisted_flow_url", None)
    return ApiError(
        code,
        str(getattr(exc, "message", exc)),
        details=details,
        assisted_flow_url=assisted_flow_url,
    )
