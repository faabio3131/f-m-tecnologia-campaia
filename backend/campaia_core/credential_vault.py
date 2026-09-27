"""Cofre real de credenciais de terceiro, por tenant.

Decisao do Diretor (27/09/2026): CampaIA e um SaaS comercial multi-tenant. Nenhuma
credencial de cliente (token do Google Ads, do Meta, do WhatsApp Business...) pode
depender de variavel de ambiente configurada pelo engenheiro por cliente -- cada tenant
conecta a propria conta pelo produto, e o resultado tem que ficar guardado de forma
real, isolada por tenant, nunca em texto claro.

Este modulo e so a peca de criptografia/formato -- puro, sem I/O, testavel sem SQLite.
O armazenamento (linha na tabela `credential_vault`) vive em `api/repositories.py`
(mesmo padrao dos outros repositorios: nada aqui e persistencia, so dominio).

Formato do payload: um dict JSON-serializavel arbitrario (ex.: {"refresh_token": "...",
"access_token": "...", "expires_at": "..."}). O cofre nao interpreta o conteudo -- isso
e responsabilidade de cada adaptador de provedor.
"""

from __future__ import annotations

import base64
import json

from cryptography.fernet import Fernet

from .errors import CampaiaError


class VaultKeyMissing(CampaiaError):
    """A chave de criptografia do cofre nao esta configurada.

    Fail-closed deliberado (Ordem Mestra: preferir fail-closed em operacoes criticas):
    sem chave, o cofre se recusa a guardar ou ler qualquer segredo -- nunca usa uma
    chave fixa/padrao "so para nao travar".
    """

    code = "VAULT_KEY_MISSING"


class VaultDecryptionFailed(CampaiaError):
    """Ciphertext corrompido, ou criptografado com uma chave diferente da atual.

    Nunca deve ser confundido com "credencial nao encontrada" (isso e outro erro, na
    camada de repositorio) -- este e especificamente sobre o conteudo nao abrir com a
    chave fornecida.
    """

    code = "VAULT_DECRYPTION_FAILED"


class CredentialCipher:
    """Criptografia simetrica (Fernet/AES) de payloads de credencial.

    Uma unica chave por ambiente (`CAMPAIA_VAULT_KEY`), nunca por tenant -- isolamento
    entre tenants e responsabilidade do repositorio (que sempre exige tenant_id na
    leitura), nao da criptografia em si.
    """

    __slots__ = ("_fernet",)

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    @classmethod
    def from_env_value(cls, raw_key: str | None) -> "CredentialCipher":
        """Constroi a partir do valor bruto de `CAMPAIA_VAULT_KEY` (ja lido pelo caller).

        Levanta `VaultKeyMissing` se `raw_key` for None ou vazio -- nunca gera ou
        assume uma chave por conta propria.
        """
        if not raw_key:
            raise VaultKeyMissing(
                "CAMPAIA_VAULT_KEY nao configurada. O cofre de credenciais nao pode "
                "operar sem uma chave de criptografia explicita."
            )
        try:
            key_bytes = raw_key.encode("ascii")
            Fernet(key_bytes)  # valida o formato agora, nao no primeiro uso
        except Exception as exc:
            raise VaultKeyMissing(
                "CAMPAIA_VAULT_KEY presente, mas nao e uma chave Fernet valida "
                "(deve ser 32 bytes urlsafe-base64, gerada por Fernet.generate_key())."
            ) from exc
        return cls(key_bytes)

    @staticmethod
    def generate_key() -> str:
        """Gera uma chave nova, para uso em setup/documentacao -- nunca chamado em
        runtime de producao (a chave de producao vive fora do codigo)."""
        return Fernet.generate_key().decode("ascii")

    def encrypt_payload(self, payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        token = self._fernet.encrypt(raw)
        return base64.urlsafe_b64encode(token).decode("ascii")

    def decrypt_payload(self, ciphertext: str) -> dict:
        try:
            token = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
            raw = self._fernet.decrypt(token)
        except Exception as exc:
            raise VaultDecryptionFailed(
                "Nao foi possivel decifrar o segredo -- ciphertext corrompido ou "
                "chave incorreta."
            ) from exc
        return json.loads(raw.decode("utf-8"))
