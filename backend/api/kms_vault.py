"""Google Cloud KMS envelope encryption for tenant credential payloads.

F4 production rule: the application never carries a permanent root encryption key in an
environment variable. For every payload we generate a fresh Fernet data-encryption key
(DEK), encrypt the payload locally, wrap only that DEK with Cloud KMS, and persist the
ciphertext envelope. Cloud KMS key-version rotation therefore applies to new writes while
old envelopes remain decryptable by their historical KMS key versions.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.fernet import Fernet

from campaia_core.credential_vault import VaultDecryptionFailed


_ENVELOPE_PREFIX = "kms-envelope-v1:"


class KmsEnvelopeCredentialCipher:
    """CredentialCipher-compatible adapter backed by a symmetric Cloud KMS CryptoKey."""

    def __init__(self, key_name: str, *, client: Any | None = None) -> None:
        if not key_name:
            raise ValueError("Cloud KMS key resource name is required")
        self._key_name = key_name
        if client is None:
            from google.cloud import kms_v1

            client = kms_v1.KeyManagementServiceClient()
        self._client = client

    @property
    def key_name(self) -> str:
        return self._key_name

    def encrypt_payload(self, payload: dict) -> str:
        dek = Fernet.generate_key()
        token = Fernet(dek).encrypt(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        try:
            response = self._client.encrypt(
                request={"name": self._key_name, "plaintext": dek}
            )
            wrapped_dek = bytes(response.ciphertext)
        except Exception as exc:
            raise VaultDecryptionFailed(
                "Cloud KMS nao conseguiu proteger a chave de dados do cofre."
            ) from exc

        envelope = {
            "v": 1,
            "kek": self._key_name,
            "wrapped_dek": base64.urlsafe_b64encode(wrapped_dek).decode("ascii"),
            "payload": base64.urlsafe_b64encode(token).decode("ascii"),
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        return _ENVELOPE_PREFIX + encoded

    def decrypt_payload(self, ciphertext: str) -> dict:
        if not ciphertext.startswith(_ENVELOPE_PREFIX):
            raise VaultDecryptionFailed(
                "Ciphertext do cofre nao esta no formato KMS envelope esperado."
            )
        try:
            envelope_raw = base64.urlsafe_b64decode(
                ciphertext[len(_ENVELOPE_PREFIX) :].encode("ascii")
            )
            envelope = json.loads(envelope_raw.decode("utf-8"))
            if envelope.get("v") != 1 or envelope.get("kek") != self._key_name:
                raise ValueError("invalid envelope metadata")
            wrapped_dek = base64.urlsafe_b64decode(
                envelope["wrapped_dek"].encode("ascii")
            )
            token = base64.urlsafe_b64decode(envelope["payload"].encode("ascii"))
            response = self._client.decrypt(
                request={"name": self._key_name, "ciphertext": wrapped_dek}
            )
            dek = bytes(response.plaintext)
            raw = Fernet(dek).decrypt(token)
            result = json.loads(raw.decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError("credential payload is not an object")
            return result
        except VaultDecryptionFailed:
            raise
        except Exception as exc:
            raise VaultDecryptionFailed(
                "Nao foi possivel decifrar o envelope KMS do cofre."
            ) from exc


__all__ = ["KmsEnvelopeCredentialCipher"]
