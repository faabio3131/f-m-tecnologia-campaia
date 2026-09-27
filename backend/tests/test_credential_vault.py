"""Testes do cofre de credenciais (criptografia pura, sem SQLite).

Prova o essencial para um cofre de SaaS multi-tenant: round-trip real (nao um mock que
sempre "funciona"), fail-closed quando a chave nao existe ou e invalida, e que uma
chave errada nunca decifra por acidente -- decifra ou levanta erro, nunca devolve lixo
silenciosamente.
"""

from __future__ import annotations

import unittest

from campaia_core.credential_vault import (
    CredentialCipher,
    VaultDecryptionFailed,
    VaultKeyMissing,
)


class TestCredentialCipherRoundTrip(unittest.TestCase):
    def test_encrypt_then_decrypt_returns_original_payload(self) -> None:
        cipher = CredentialCipher.from_env_value(CredentialCipher.generate_key())
        payload = {"refresh_token": "1//real-looking-token", "scope": "adwords"}

        ciphertext = cipher.encrypt_payload(payload)

        self.assertNotIn("1//real-looking-token", ciphertext)
        self.assertEqual(cipher.decrypt_payload(ciphertext), payload)

    def test_ciphertext_is_not_the_plaintext_json(self) -> None:
        cipher = CredentialCipher.from_env_value(CredentialCipher.generate_key())
        ciphertext = cipher.encrypt_payload({"refresh_token": "abc123"})

        self.assertNotIn("abc123", ciphertext)
        self.assertNotIn("refresh_token", ciphertext)


class TestCredentialCipherFailClosed(unittest.TestCase):
    def test_missing_key_raises_instead_of_using_a_default(self) -> None:
        with self.assertRaises(VaultKeyMissing):
            CredentialCipher.from_env_value(None)

    def test_empty_key_raises(self) -> None:
        with self.assertRaises(VaultKeyMissing):
            CredentialCipher.from_env_value("")

    def test_malformed_key_raises(self) -> None:
        with self.assertRaises(VaultKeyMissing):
            CredentialCipher.from_env_value("nao-e-uma-chave-fernet-valida")


class TestCredentialCipherWrongKey(unittest.TestCase):
    def test_decrypting_with_a_different_key_fails_loudly(self) -> None:
        cipher_a = CredentialCipher.from_env_value(CredentialCipher.generate_key())
        cipher_b = CredentialCipher.from_env_value(CredentialCipher.generate_key())
        ciphertext = cipher_a.encrypt_payload({"refresh_token": "secret"})

        with self.assertRaises(VaultDecryptionFailed):
            cipher_b.decrypt_payload(ciphertext)

    def test_corrupted_ciphertext_fails_loudly_not_silently(self) -> None:
        cipher = CredentialCipher.from_env_value(CredentialCipher.generate_key())
        ciphertext = cipher.encrypt_payload({"refresh_token": "secret"})
        corrupted = ciphertext[:-4] + "abcd"

        with self.assertRaises(VaultDecryptionFailed):
            cipher.decrypt_payload(corrupted)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
