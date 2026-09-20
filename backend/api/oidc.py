"""Provider-neutral OIDC Authorization Code + PKCE client (WP-02, ADR-0018).

No commercial identity provider is approved yet (ADR-0018 §Pendencias) -- this module
implements the OIDC *standard* itself, not a vendor SDK, so it works unmodified against
any spec-compliant issuer (the test identity provider in api/test_idp.py today; a real
provider later, only by changing configuration, never this code).

Nothing here trusts client input: state/nonce/PKCE verifier are generated and held
server-side (api/state.py AppState.pending_logins), and the ID token's signature is always
verified against the issuer's own published JWKS before any claim is read.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import jwt
from jwt import PyJWKSet

if TYPE_CHECKING:
    # Deferred: state.py imports this module, so a runtime import here would cycle.
    # `from __future__ import annotations` (above) makes every annotation in this file
    # lazy, so this is only ever evaluated by type checkers, never at import time.
    from .state import TokenPrincipal

#: RFC 7636 recommends 43-128 characters of unreserved base64url output.
_PKCE_VERIFIER_BYTES = 64
_STATE_BYTES = 32
_NONCE_BYTES = 32

#: How long a login attempt (state/nonce/PKCE verifier) may remain unclaimed before it is
#: no longer accepted at /auth/callback -- bounds the window for a stolen/replayed
#: authorization code to be useful, and bounds unbounded growth of pending logins that are
#: abandoned mid-flow (browser closed before completing the redirect).
PENDING_LOGIN_TTL_SECONDS = 600

#: Real sessions expire and must be re-established -- WP-02 rollback/ADR-0018 "Expiracao e
#: rotacao de sessao". A session is re-issued (new id, new expiry) on every successful
#: login; there is no silent extension of an existing session on activity.
SESSION_TTL_SECONDS = 12 * 60 * 60


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Returns (code_verifier, code_challenge) per RFC 7636 S256."""
    verifier = _b64url(secrets.token_bytes(_PKCE_VERIFIER_BYTES))
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = _b64url(digest)
    return verifier, challenge


def verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return secrets.compare_digest(_b64url(digest), code_challenge)


def generate_state() -> str:
    return _b64url(secrets.token_bytes(_STATE_BYTES))


def generate_nonce() -> str:
    return _b64url(secrets.token_bytes(_NONCE_BYTES))


def generate_session_id() -> str:
    return _b64url(secrets.token_bytes(32))


def generate_csrf_token() -> str:
    return _b64url(secrets.token_bytes(32))


@dataclass(frozen=True)
class OidcIssuerConfig:
    """Everything needed to talk to one OIDC issuer. Provider-neutral: swapping to a real
    commercial provider later means constructing a different OidcIssuerConfig, never
    changing this module or routes_auth.py.
    """

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    client_id: str
    client_secret: str
    redirect_uri: str


def build_authorize_url(
    config: OidcIssuerConfig, *, state: str, nonce: str, code_challenge: str
) -> str:
    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{config.authorization_endpoint}?{urlencode(params)}"


@dataclass(frozen=True)
class PendingLogin:
    """One /auth/login attempt, held server-side between the redirect to the issuer and
    the browser coming back to /auth/callback. Never exposed to the client except as the
    opaque `state` value (which the client must echo back unmodified -- OIDC's own CSRF
    protection for the authorization redirect itself, independent of the app-session CSRF
    token issued after login succeeds).
    """

    nonce: str
    code_verifier: str
    redirect_after_login: str
    created_at: float


@dataclass(frozen=True)
class SessionRecord:
    """A real, server-validated Web session (WP-02 / ADR-0018) -- the thing
    `api/deps.py`'s `require_auth` now checks before falling back to the fixture Bearer
    token. `principal` is the same TokenPrincipal shape the old fixture tokens produced,
    so nothing downstream of require_auth needs to know which path authenticated the
    request.
    """

    principal: "TokenPrincipal"
    csrf_token: str
    expires_at: float


@dataclass(frozen=True)
class VerifiedIdToken:
    subject: str
    email: str | None
    tenant_id: str
    business_unit_id: str | None
    roles: tuple[str, ...]
    mfa_enabled: bool


class IdTokenVerificationError(Exception):
    """Raised for any ID token that fails signature, issuer, audience, expiry, or nonce
    verification. Callers must treat this identically to "no session" -- never partially
    trust a token that failed verification.
    """


def verify_id_token(
    id_token: str, *, config: OidcIssuerConfig, expected_nonce: str, jwks: dict
) -> VerifiedIdToken:
    """Verifies signature (against the caller-supplied JWKS -- see below), issuer,
    audience, expiry, and nonce -- in that order, so a token failing an earlier check never
    reaches a later one that might read attacker-controlled claims. Only after every check
    passes are claims read.

    ``jwks`` is a plain dict (already fetched by the caller from ``config.jwks_uri``),
    never fetched by this function itself. This is deliberate: PyJWT's own PyJWKClient
    fetches JWKS with its own internal HTTP client, which cannot be pointed at an in-process
    ASGI transport -- against the test identity provider (api/test_idp.py) that means a real
    socket connection to a host that only exists inside the test process, which sandboxed
    environments correctly refuse. Callers (api/routes_auth.py) fetch the JWKS themselves,
    in-process for the test IdP and over real HTTP for a real provider, using the SAME
    httpx client either way -- one HTTP stack to reason about, not two.
    """
    try:
        key_set = PyJWKSet.from_dict(jwks)
        header = jwt.get_unverified_header(id_token)
        kid = header.get("kid")
        signing_key = next(
            (k for k in key_set.keys if k.key_id == kid), key_set.keys[0] if key_set.keys else None
        )
        if signing_key is None:
            raise IdTokenVerificationError("No matching signing key found in the issuer's JWKS.")
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config.client_id,
            issuer=config.issuer,
            options={"require": ["exp", "iat", "sub", "nonce"]},
        )
    except jwt.PyJWTError as exc:
        raise IdTokenVerificationError(f"ID token failed verification: {exc}") from exc

    if not secrets.compare_digest(str(claims.get("nonce", "")), expected_nonce):
        raise IdTokenVerificationError("ID token nonce does not match the login attempt.")

    tenant_id = claims.get("campaia_tenant_id")
    if not tenant_id:
        raise IdTokenVerificationError("ID token is missing the required campaia_tenant_id claim.")

    roles = claims.get("campaia_roles")
    if not isinstance(roles, list) or not roles:
        raise IdTokenVerificationError("ID token is missing or has an empty campaia_roles claim.")

    return VerifiedIdToken(
        subject=str(claims["sub"]),
        email=claims.get("email"),
        tenant_id=str(tenant_id),
        business_unit_id=claims.get("campaia_business_unit_id"),
        roles=tuple(str(r) for r in roles),
        mfa_enabled=bool(claims.get("campaia_mfa_enabled", False)),
    )
