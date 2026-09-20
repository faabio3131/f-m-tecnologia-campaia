"""Self-contained, provider-neutral OIDC test identity provider (WP-02).

Exists ONLY because no commercial identity provider is approved yet (ADR-0018
Pendencias). It is a real, spec-shaped OIDC issuer -- discovery document, authorization
endpoint, token endpoint, JWKS -- so the client code in api/oidc.py and api/routes_auth.py
is exercised exactly as it would be against a real provider later, with zero code changes
when that provider is chosen.

Fail-closed by construction: this class is only ever instantiated by AppState when the
SAME two-signal check that gates the fixture Bearer tokens (enable_test_auth_fixtures=True
AND CAMPAIA_ENV=test|local_dev) already passed -- see AppState.__post_init__. There is
deliberately only one fail-closed switch to reason about, not two that could drift apart.

No real password: the "authorize" endpoint renders an HTML picker of the fixture test
identities (same identities as the pre-WP-02 Bearer token fixtures) and issues a real
signed ID token for whichever one is chosen, after a real PKCE-protected code exchange.
"""

from __future__ import annotations

import base64
import time
import uuid
from dataclasses import dataclass, field

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

from .oidc import verify_pkce

_CODE_TTL_SECONDS = 120
_ID_TOKEN_TTL_SECONDS = 300

#: Fixture test identities -- same tenants/roles/ids the pre-WP-02 Bearer fixtures used, so
#: existing expectations about "owner has these permissions in demo-tenant" carry over
#: unchanged to the real session mechanism.
TEST_IDENTITIES: dict[str, dict] = {
    "owner": {
        "sub": "user-owner-1",
        "email": "owner@demo-tenant.test",
        "tenant_id": "demo-tenant",
        "business_unit_id": "bu-1",
        "roles": ["OWNER"],
        "mfa_enabled": True,
    },
    "marketer": {
        "sub": "user-marketer-1",
        "email": "marketer@demo-tenant.test",
        "tenant_id": "demo-tenant",
        "business_unit_id": "bu-1",
        "roles": ["MARKETER"],
        "mfa_enabled": True,
    },
    "approver": {
        "sub": "user-approver-1",
        "email": "approver@demo-tenant.test",
        "tenant_id": "demo-tenant",
        "business_unit_id": "bu-1",
        "roles": ["APPROVER"],
        "mfa_enabled": True,
    },
    "finance": {
        "sub": "user-finance-1",
        "email": "finance@demo-tenant.test",
        "tenant_id": "demo-tenant",
        "business_unit_id": "bu-1",
        "roles": ["FINANCE"],
        "mfa_enabled": True,
    },
    "viewer": {
        "sub": "user-viewer-1",
        "email": "viewer@demo-tenant.test",
        "tenant_id": "demo-tenant",
        "business_unit_id": "bu-1",
        "roles": ["VIEWER"],
        "mfa_enabled": True,
    },
    "other_owner": {
        "sub": "user-owner-2",
        "email": "owner@other-tenant.test",
        "tenant_id": "other-tenant",
        "business_unit_id": "bu-2",
        "roles": ["OWNER"],
        "mfa_enabled": True,
    },
}


@dataclass
class _PendingAuthorization:
    client_id: str
    redirect_uri: str
    state: str
    nonce: str
    code_challenge: str
    base_url: str
    created_at: float = field(default_factory=time.time)


class TestIdentityProvider:
    """One instance per AppState -- an isolated RSA keypair per app instance means two
    concurrently running test apps (see tests_api/test_persistence.py's
    test_default_app_instances_do_not_share_state pattern) never share signing material.
    """

    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._kid = uuid.uuid4().hex
        self._codes: dict[str, tuple[_PendingAuthorization, str]] = {}

    def issuer(self, base_url: str) -> str:
        return f"{base_url}/test-idp"

    def jwks(self) -> dict:
        public_numbers = self._private_key.public_key().public_numbers()

        def _b64(n: int, length: int) -> str:
            raw = n.to_bytes(length, "big")
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self._kid,
                    "n": _b64(public_numbers.n, 256),
                    "e": _b64(public_numbers.e, 3),
                }
            ]
        }

    def discovery_document(self, base_url: str) -> dict:
        issuer = self.issuer(base_url)
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/authorize",
            "token_endpoint": f"{issuer}/token",
            "jwks_uri": f"{issuer}/jwks.json",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "code_challenge_methods_supported": ["S256"],
        }

    def start_authorization(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_challenge: str,
        base_url: str,
    ) -> str:
        """Returns an authorization_code for the picker page to hand to the browser once a
        test identity is chosen. Not exposed to the browser until then.
        """
        code = uuid.uuid4().hex
        self._codes[code] = (
            _PendingAuthorization(
                client_id=client_id,
                redirect_uri=redirect_uri,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge,
                base_url=base_url,
            ),
            "",  # test_identity_key filled in by pick_identity
        )
        return code

    def pick_identity(self, code: str, identity_key: str) -> _PendingAuthorization:
        if code not in self._codes:
            raise KeyError("Unknown or expired authorization code.")
        if identity_key not in TEST_IDENTITIES:
            raise KeyError("Unknown test identity.")
        pending, _ = self._codes[code]
        self._codes[code] = (pending, identity_key)
        return pending

    def exchange_code(
        self, *, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str
    ) -> str:
        """Validates PKCE + client credentials + redirect_uri, then returns a signed ID
        token. Single-use: the code is deleted whether or not this call succeeds, so a
        replayed code (even with a correct verifier) always fails on the second attempt.
        """
        entry = self._codes.pop(code, None)
        if entry is None:
            raise ValueError("Unknown, expired, or already-used authorization code.")
        pending, identity_key = entry

        if time.time() - pending.created_at > _CODE_TTL_SECONDS:
            raise ValueError("Authorization code expired.")
        if client_id != self._client_id or client_secret != self._client_secret:
            raise ValueError("Invalid client credentials.")
        if redirect_uri != pending.redirect_uri:
            raise ValueError("redirect_uri does not match the original authorization request.")
        if not identity_key:
            raise ValueError("No test identity was ever selected for this code.")
        if not verify_pkce(code_verifier, pending.code_challenge):
            raise ValueError("PKCE code_verifier does not match the original code_challenge.")


        identity = TEST_IDENTITIES[identity_key]
        now = int(time.time())
        claims = {
            "iss": self.issuer(pending.base_url),
            "aud": self._client_id,
            "sub": identity["sub"],
            "email": identity["email"],
            "iat": now,
            "exp": now + _ID_TOKEN_TTL_SECONDS,
            "nonce": pending.nonce,
            "campaia_tenant_id": identity["tenant_id"],
            "campaia_business_unit_id": identity["business_unit_id"],
            "campaia_roles": identity["roles"],
            "campaia_mfa_enabled": identity["mfa_enabled"],
        }
        return jwt.encode(
            claims, self._private_key, algorithm="RS256", headers={"kid": self._kid}
        )


async def discovery(request: Request) -> JSONResponse:
    idp: TestIdentityProvider = request.app.state.campaia.test_idp
    base = str(request.base_url).rstrip("/")
    return JSONResponse(idp.discovery_document(base))


async def jwks(request: Request) -> JSONResponse:
    idp: TestIdentityProvider = request.app.state.campaia.test_idp
    return JSONResponse(idp.jwks())


_PICKER_TEMPLATE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>CampaIA Test Identity Provider</title></head>
<body>
<h1>Test Identity Provider — pick a fixture identity</h1>
<p>This page exists ONLY in test/local-dev (CAMPAIA_ENV). It is never reachable in
preview, staging, or production.</p>
<form method="post" action="/test-idp/authorize">
<input type="hidden" name="code" value="{code}">
{options}
<button type="submit">Continue</button>
</form>
</body>
</html>"""


async def authorize_get(request: Request) -> HTMLResponse:
    idp: TestIdentityProvider = request.app.state.campaia.test_idp
    params = request.query_params
    code = idp.start_authorization(
        client_id=params["client_id"],
        redirect_uri=params["redirect_uri"],
        state=params["state"],
        nonce=params["nonce"],
        code_challenge=params["code_challenge"],
        base_url=str(request.base_url).rstrip("/"),
    )
    options = "\n".join(
        f'<div><button type="submit" name="identity" value="{key}">{data["email"]} '
        f'({", ".join(data["roles"])}, {data["tenant_id"]})</button></div>'
        for key, data in TEST_IDENTITIES.items()
    )
    return HTMLResponse(_PICKER_TEMPLATE.format(code=code, options=options))


async def authorize_post(request: Request) -> RedirectResponse:
    idp: TestIdentityProvider = request.app.state.campaia.test_idp
    form = await request.form()
    code = str(form["code"])
    identity_key = str(form["identity"])
    pending = idp.pick_identity(code, identity_key)

    return RedirectResponse(
        url=f"{pending.redirect_uri}?code={code}&state={pending.state}", status_code=303
    )


async def token(request: Request) -> JSONResponse:
    idp: TestIdentityProvider = request.app.state.campaia.test_idp
    form = await request.form()
    try:
        id_token = idp.exchange_code(
            code=str(form["code"]),
            redirect_uri=str(form["redirect_uri"]),
            client_id=str(form["client_id"]),
            client_secret=str(form["client_secret"]),
            code_verifier=str(form["code_verifier"]),
        )
    except (KeyError, ValueError) as exc:
        return JSONResponse({"error": "invalid_grant", "error_description": str(exc)}, status_code=400)

    return JSONResponse(
        {
            "id_token": id_token,
            "token_type": "Bearer",
            "expires_in": _ID_TOKEN_TTL_SECONDS,
        }
    )


test_idp_routes = [
    Route("/test-idp/.well-known/openid-configuration", discovery, methods=["GET"]),
    Route("/test-idp/jwks.json", jwks, methods=["GET"]),
    Route("/test-idp/authorize", authorize_get, methods=["GET"]),
    Route("/test-idp/authorize", authorize_post, methods=["POST"]),
    Route("/test-idp/token", token, methods=["POST"]),
]
