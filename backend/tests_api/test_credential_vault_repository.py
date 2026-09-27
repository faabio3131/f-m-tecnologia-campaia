"""Prova o cofre real (VaultRepository + CredentialCipher) na camada de API.

Diferente de test_credential_vault.py (backend/tests, so a criptografia pura), este
arquivo prova o que o repositorio acrescenta: isolamento por tenant (uma SecretRef de um
tenant nunca decifra para outro, mesmo com a chave certa) e sobrevivencia a um restart de
processo quando `db_path` e' usado -- mesma disciplina de tests_api/test_persistence.py.
"""

from __future__ import annotations

import gc
import os
import tempfile
import unittest

from api.db import Database
from api.repositories import VaultAccessDenied, VaultRepository
from campaia_core.connectors import SecretRef
from campaia_core.credential_vault import CredentialCipher


class TestVaultRepositoryEphemeral(unittest.TestCase):
    def setUp(self) -> None:
        self.cipher = CredentialCipher.from_env_value(CredentialCipher.generate_key())
        self.vault = VaultRepository()

    def test_store_then_resolve_returns_original_payload(self) -> None:
        ref = self.vault.store(
            "tenant-a",
            provider="google_ads",
            external_account_id="123-456-7890",
            payload={"refresh_token": "1//real-token"},
            cipher=self.cipher,
        )

        resolved = self.vault.resolve("tenant-a", ref, cipher=self.cipher)

        self.assertEqual(resolved, {"refresh_token": "1//real-token"})

    def test_resolving_from_a_different_tenant_is_denied(self) -> None:
        ref = self.vault.store(
            "tenant-a",
            provider="google_ads",
            external_account_id="123-456-7890",
            payload={"refresh_token": "1//real-token"},
            cipher=self.cipher,
        )

        with self.assertRaises(VaultAccessDenied):
            self.vault.resolve("tenant-b", ref, cipher=self.cipher)

    def test_unknown_secret_ref_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.vault.resolve(
                "tenant-a", SecretRef(handle="vault://google_ads/does-not-exist"), cipher=self.cipher
            )

    def test_revoked_secret_can_no_longer_be_resolved(self) -> None:
        ref = self.vault.store(
            "tenant-a",
            provider="google_ads",
            external_account_id="123-456-7890",
            payload={"refresh_token": "1//real-token"},
            cipher=self.cipher,
        )

        self.vault.revoke("tenant-a", ref)

        with self.assertRaises(KeyError):
            self.vault.resolve("tenant-a", ref, cipher=self.cipher)


class TestVaultRepositoryPersistence(unittest.TestCase):
    """Sobrevive a um restart real de processo (arquivo SQLite fechado e reaberto)."""

    def test_credential_survives_process_restart(self) -> None:
        cipher = CredentialCipher.from_env_value(CredentialCipher.generate_key())
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "vault-restart-test.sqlite3")

            db1 = Database(db_path)
            vault1 = VaultRepository(db1.table("credential_vault"))
            ref = vault1.store(
                "tenant-a",
                provider="google_ads",
                external_account_id="123-456-7890",
                payload={"refresh_token": "1//real-token"},
                cipher=cipher,
            )
            db1.close()
            del db1, vault1
            gc.collect()

            db2 = Database(db_path)
            vault2 = VaultRepository(db2.table("credential_vault"))
            resolved = vault2.resolve("tenant-a", ref, cipher=cipher)
            db2.close()

            self.assertEqual(resolved, {"refresh_token": "1//real-token"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
