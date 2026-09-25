"""Verificador de ID token deterministico -- SOMENTE para o harness de E2E.

Reconhece exatamente os tokens fixos definidos aqui, nunca um valor arbitrario --
qualquer outro id_token e recusado fail-closed, exatamente como `AlwaysRejectIdTokenVerifier`
faria em produção sem projeto Google Cloud real (item 1.6).
"""

from __future__ import annotations

from campaia_core.identity_provider import IdentityError, VerifiedIdentity

#: Tokens fixos reconhecidos pelo harness de E2E -- nunca usados fora de testes.
#: Os e-mails correspondem exatamente aos ja seedados em
#: api.identity_directory.seed_dev_identity_directory() (dois tenants distintos,
#: para o teste cross-tenant obrigatorio da Etapa 2).
E2E_TOKEN_TENANT_A_OWNER = "e2e-test-id-token-tenant-a-owner"
E2E_TOKEN_TENANT_B_OWNER = "e2e-test-id-token-tenant-b-owner"
E2E_TOKEN_UNVERIFIED_EMAIL = "e2e-test-id-token-unverified-email"
E2E_TOKEN_UNKNOWN_EMAIL = "e2e-test-id-token-unknown-email"
#: WP-03 (25/09/2026): identidade com DOIS vinculos reais (seed_dev_identity_directory),
#: para o E2E real de listagem/troca de tenant/unidade ativo na sessao.
E2E_TOKEN_MULTI_TENANT_OWNER = "e2e-test-id-token-multi-tenant-owner"

_IDENTITIES: dict[str, VerifiedIdentity] = {
    E2E_TOKEN_TENANT_A_OWNER: VerifiedIdentity(
        subject="e2e-google-uid-tenant-a-owner",
        email="owner@demo-tenant.campaia.test",
        email_verified=True,
    ),
    E2E_TOKEN_TENANT_B_OWNER: VerifiedIdentity(
        subject="e2e-google-uid-tenant-b-owner",
        email="owner@other-tenant.campaia.test",
        email_verified=True,
    ),
    E2E_TOKEN_UNVERIFIED_EMAIL: VerifiedIdentity(
        subject="e2e-google-uid-unverified",
        email="owner@demo-tenant.campaia.test",
        email_verified=False,
    ),
    E2E_TOKEN_UNKNOWN_EMAIL: VerifiedIdentity(
        subject="e2e-google-uid-unknown",
        email="nao-cadastrado@example.com",
        email_verified=True,
    ),
    E2E_TOKEN_MULTI_TENANT_OWNER: VerifiedIdentity(
        subject="e2e-google-uid-multi-tenant-owner",
        email="owner@multi-tenant.campaia.test",
        email_verified=True,
    ),
}


class DeterministicTestIdTokenVerifier:
    """Implementa `IdTokenVerifier` (campaia_core.identity_provider) com uma tabela
    fixa. Qualquer token fora de `_IDENTITIES` e recusado -- mesma disciplina
    fail-closed do verificador real."""

    def verify(self, id_token: str) -> VerifiedIdentity:
        identity = _IDENTITIES.get(id_token)
        if identity is None:
            raise IdentityError("E2E: id_token nao reconhecido pelo harness de teste.")
        return identity


__all__ = [
    "DeterministicTestIdTokenVerifier",
    "E2E_TOKEN_TENANT_A_OWNER",
    "E2E_TOKEN_TENANT_B_OWNER",
    "E2E_TOKEN_UNVERIFIED_EMAIL",
    "E2E_TOKEN_UNKNOWN_EMAIL",
    "E2E_TOKEN_MULTI_TENANT_OWNER",
]
