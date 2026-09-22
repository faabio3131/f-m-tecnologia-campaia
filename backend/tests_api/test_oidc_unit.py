"""Pure unit tests for api/oidc.py -- no HTTP, no app, no test identity provider.

Covers the security-critical primitives WP-02 depends on: PKCE generation/verification,
state/nonce/session-id/csrf-token uniqueness, and ID token verification (signature, issuer,
audience, expiry, nonce) using a locally generated RSA keypair and hand-built JWTs, so every
negative case is reproduced deterministically rather than relying on the test identity
provider's own (already correct) behaviour.
"""

from __future__ import annotations

import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from api.oidc import (
    IdTokenVerificationError,
    OidcIssuerConfig,
    generate_csrf_token,
    generate_nonce,
    generate_pkce_pair,
    generate_session_id,
    generate_state,
    verify_id_token,
    verify_pkce,
)


class TestPkce(unittest.TestCase):
    def test_generated_pair_verifies(self) -> None:
        verifier, challenge = generate_pkce_pair()
        self.assertTrue(verify_pkce(verifier, challenge))

    def test_wrong_verifier_fails(self) -> None:
        _verifier, challenge = generate_pkce_pair()
        other_verifier, _other_challenge = generate_pkce_pair()
        self.assertFalse(verify_pkce(other_verifier, challenge))

    def test_verifier_length_within_rfc7636_bounds(self) -> None:
        verifier, _challenge = generate_pkce_pair()
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)

    def test_pairs_are_unique(self) -> None:
        pairs = {generate_pkce_pair() for _ in range(20)}
        self.assertEqual(len(pairs), 20)


class TestUniqueness(unittest.TestCase):
    def test_state_values_unique(self) -> None:
        values = {generate_state() for _ in range(50)}
        self.assertEqual(len(values), 50)

    def test_nonce_values_unique(self) -> None:
        values = {generate_nonce() for _ in range(50)}
        self.assertEqual(len(values), 50)

    def test_session_ids_unique(self) -> None:
        values = {generate_session_id() for _ in range(50)}
        self.assertEqual(len(values), 50)

    def test_csrf_tokens_unique(self) -> None:
        values = {generate_csrf_token() for _ in range(50)}
        self.assertEqual(len(values), 50)


def _rsa_jwks(private_key) -> dict:
    numbers = private_key.public_key().public_numbers()
    import base64

    def _b64(n: int, length: int) -> str:
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode("ascii")

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-kid",
                "n": _b64(numbers.n, 256),
                "e": _b64(numbers.e, 3),
            }
        ]
    }


class TestVerifyIdToken(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwks = _rsa_jwks(self.private_key)
        self.config = OidcIssuerConfig(
            issuer="https://idp.example/issuer",
            authorization_endpoint="https://idp.example/authorize",
            token_endpoint="https://idp.example/token",
            jwks_uri="https://idp.example/jwks.json",
            client_id="campaia-web",
            client_secret="dev-secret",
            redirect_uri="https://app.example/auth/callback",
        )
        self.nonce = generate_nonce()

    def _make_token(self, **overrides) -> str:
        now = int(time.time())
        claims = {
            "iss": self.config.issuer,
            "aud": self.config.client_id,
            "sub": "user-owner-1",
            "iat": now,
            "exp": now + 300,
            "nonce": self.nonce,
            "campaia_tenant_id": "demo-tenant",
            "campaia_business_unit_id": "bu-1",
            "campaia_roles": ["OWNER"],
            "campaia_mfa_enabled": True,
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": "test-kid"})

    def test_valid_token_is_accepted(self) -> None:
        token = self._make_token()
        verified = verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)
        self.assertEqual(verified.subject, "user-owner-1")
        self.assertEqual(verified.tenant_id, "demo-tenant")
        self.assertEqual(verified.roles, ("OWNER",))
        self.assertTrue(verified.mfa_enabled)

    def test_expired_token_is_rejected(self) -> None:
        now = int(time.time())
        token = self._make_token(iat=now - 1000, exp=now - 500)
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_wrong_issuer_is_rejected(self) -> None:
        token = self._make_token(iss="https://attacker.example/issuer")
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_wrong_audience_is_rejected(self) -> None:
        token = self._make_token(aud="some-other-client")
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_nonce_mismatch_is_rejected(self) -> None:
        token = self._make_token(nonce="a-different-nonce-entirely")
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_missing_tenant_claim_is_rejected(self) -> None:
        token = self._make_token(campaia_tenant_id=None)
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_empty_roles_claim_is_rejected(self) -> None:
        token = self._make_token(campaia_roles=[])
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_tampered_signature_is_rejected(self) -> None:
        token = self._make_token()
        # Flip the last character of the signature segment -- still well-formed JWT shape,
        # guaranteed-invalid signature.
        header_b64, payload_b64, sig_b64 = token.split(".")
        tampered_last = "A" if sig_b64[-1] != "A" else "B"
        tampered = f"{header_b64}.{payload_b64}.{sig_b64[:-1]}{tampered_last}"
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(tampered, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_signed_by_different_key_is_rejected(self) -> None:
        """Simulates an attacker who controls a valid RSA keypair but not the real
        issuer's private key -- proves verification is against OUR jwks, not just any
        well-formed signature."""
        attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = int(time.time())
        claims = {
            "iss": self.config.issuer,
            "aud": self.config.client_id,
            "sub": "user-owner-1",
            "iat": now,
            "exp": now + 300,
            "nonce": self.nonce,
            "campaia_tenant_id": "demo-tenant",
            "campaia_roles": ["OWNER"],
        }
        token = jwt.encode(claims, attacker_key, algorithm="RS256", headers={"kid": "test-kid"})
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_unknown_role_string_is_dropped_not_granted(self) -> None:
        """TokenPrincipal.from_verified_id_token (api/state.py) is exercised separately in
        test_auth_session.py; this test only proves the raw claim survives verification
        unfiltered (filtering happens downstream, deliberately)."""
        token = self._make_token(campaia_roles=["OWNER", "SOME_ROLE_THAT_DOES_NOT_EXIST"])
        verified = verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)
        self.assertIn("SOME_ROLE_THAT_DOES_NOT_EXIST", verified.roles)


class TestMemberships(unittest.TestCase):
    """WP-03: `campaia_memberships` is optional and, when present, is validated against
    the token's own required flat claims -- see api/oidc.py's _parse_memberships."""

    setUp = TestVerifyIdToken.setUp
    _make_token = TestVerifyIdToken._make_token

    def test_absent_claim_yields_single_active_membership(self) -> None:
        token = self._make_token()
        verified = verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)
        self.assertEqual(len(verified.memberships), 1)
        m = verified.memberships[0]
        self.assertEqual(m.tenant_id, "demo-tenant")
        self.assertEqual(m.business_unit_id, "bu-1")
        self.assertEqual(m.roles, ("OWNER",))

    def test_present_claim_including_active_is_accepted(self) -> None:
        token = self._make_token(
            campaia_memberships=[
                {"tenant_id": "demo-tenant", "business_unit_id": "bu-1", "roles": ["OWNER"]},
                {"tenant_id": "other-tenant", "business_unit_id": "bu-2", "roles": ["VIEWER"]},
            ]
        )
        verified = verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)
        self.assertEqual(len(verified.memberships), 2)
        by_tenant = {m.tenant_id: m for m in verified.memberships}
        self.assertEqual(by_tenant["other-tenant"].roles, ("VIEWER",))

    def test_claim_missing_the_active_membership_is_rejected(self) -> None:
        """Defence in depth: a token claiming memberships that do NOT include the tenant
        it just authenticated the user into is malformed/malicious, not silently trusted."""
        token = self._make_token(
            campaia_memberships=[
                {"tenant_id": "other-tenant", "business_unit_id": "bu-2", "roles": ["VIEWER"]},
            ]
        )
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_empty_list_claim_is_rejected(self) -> None:
        token = self._make_token(campaia_memberships=[])
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_non_list_claim_is_rejected(self) -> None:
        token = self._make_token(campaia_memberships="not-a-list")
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_entry_missing_roles_is_rejected(self) -> None:
        token = self._make_token(
            campaia_memberships=[
                {"tenant_id": "demo-tenant", "business_unit_id": "bu-1", "roles": ["OWNER"]},
                {"tenant_id": "other-tenant", "business_unit_id": "bu-2", "roles": []},
            ]
        )
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_entry_missing_tenant_id_is_rejected(self) -> None:
        token = self._make_token(
            campaia_memberships=[
                {"tenant_id": "demo-tenant", "business_unit_id": "bu-1", "roles": ["OWNER"]},
                {"business_unit_id": "bu-2", "roles": ["VIEWER"]},
            ]
        )
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)

    def test_entry_that_is_not_an_object_is_rejected(self) -> None:
        token = self._make_token(campaia_memberships=["demo-tenant"])
        with self.assertRaises(IdTokenVerificationError):
            verify_id_token(token, config=self.config, expected_nonce=self.nonce, jwks=self.jwks)


if __name__ == "__main__":
    unittest.main()
