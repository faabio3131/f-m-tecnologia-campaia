"""F4 tests for Cloud KMS envelope encryption and production vault policy."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from api.kms_vault import KmsEnvelopeCredentialCipher
from api.state import AppState
from campaia_core.credential_vault import CredentialCipher, VaultDecryptionFailed


class _Response:
    def __init__(self, *, ciphertext: bytes | None = None, plaintext: bytes | None = None):
        self.ciphertext = ciphertext
        self.plaintext = plaintext


class FakeKmsClient:
    """Deterministic fake of the KMS boundary; it never sees credential plaintext."""

    def __init__(self) -> None:
        self._wrapping_key = CredentialCipher.generate_key().encode("ascii")
        self.encrypt_calls = []
        self.decrypt_calls = []

    def encrypt(self, *, request):
        self.encrypt_calls.append(request)
        dek = request["plaintext"]
        wrapped = __import__("cryptography.fernet").fernet.Fernet(
            self._wrapping_key
        ).encrypt(dek)
        return _Response(ciphertext=wrapped)

    def decrypt(self, *, request):
        self.decrypt_calls.append(request)
        dek = __import__("cryptography.fernet").fernet.Fernet(
            self._wrapping_key
        ).decrypt(request["ciphertext"])
        return _Response(plaintext=dek)


class KmsEnvelopeCredentialCipherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key_name = (
            "projects/p/locations/southamerica-east1/keyRings/campaia/"
            "cryptoKeys/tenant-credentials"
        )
        self.client = FakeKmsClient()
        self.cipher = KmsEnvelopeCredentialCipher(
            self.key_name, client=self.client
        )

    def test_round_trip_uses_fresh_wrapped_dek_and_hides_plaintext(self):
        payload = {"refresh_token": "tenant-secret", "scope": "ads"}
        first = self.cipher.encrypt_payload(payload)
        second = self.cipher.encrypt_payload(payload)

        self.assertNotEqual(first, second)
        self.assertNotIn("tenant-secret", first)
        self.assertEqual(self.cipher.decrypt_payload(first), payload)
        self.assertEqual(len(self.client.encrypt_calls), 2)
        self.assertEqual(len(self.client.decrypt_calls), 1)

    def test_wrong_kms_key_metadata_fails_closed(self):
        ciphertext = self.cipher.encrypt_payload({"token": "secret"})
        other = KmsEnvelopeCredentialCipher(
            self.key_name + "-other", client=self.client
        )
        with self.assertRaises(VaultDecryptionFailed):
            other.decrypt_payload(ciphertext)

    def test_corrupted_envelope_fails_closed(self):
        with self.assertRaises(VaultDecryptionFailed):
            self.cipher.decrypt_payload("kms-envelope-v1:not-valid-base64")


class ProductionVaultPolicyTests(unittest.TestCase):
    def test_legacy_env_root_key_is_rejected_in_production(self):
        with patch.dict(
            os.environ,
            {
                "CAMPAIA_ENV": "production",
                "CAMPAIA_VAULT_KEY": CredentialCipher.generate_key(),
            },
            clear=False,
        ):
            with patch.dict(
                os.environ,
                {"CAMPAIA_VAULT_KMS_KEY_NAME": ""},
                clear=False,
            ):
                with self.assertRaisesRegex(RuntimeError, "legacy nao e permitido"):
                    AppState()

    def test_legacy_key_remains_available_only_in_test(self):
        with patch.dict(
            os.environ,
            {
                "CAMPAIA_ENV": "test",
                "CAMPAIA_VAULT_KEY": CredentialCipher.generate_key(),
                "CAMPAIA_VAULT_KMS_KEY_NAME": "",
            },
            clear=False,
        ):
            state = AppState()
            self.assertIsNotNone(state.vault_cipher)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
