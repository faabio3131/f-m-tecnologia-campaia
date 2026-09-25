"""Diretorio interno: e-mail verificado (Google) -> `TokenPrincipal` (tenant/papeis/unidade).

Decisao (Diretor, 24/09/2026, item 1.3/WP-02): a identidade do Google prova QUEM e o
usuario; tenant_id, roles e business_unit_id vem SEMPRE deste diretorio interno, nunca de
claim do provedor de identidade. E-mail verificado sem entrada aqui e RECUSADO fail-closed
-- nunca autoprovisionado. Autoprovisionamento/convite de usuario e Work Package futuro,
fora do escopo do WP-02 (decisao de produto separada, nao tecnica).
"""

from __future__ import annotations

from typing import Protocol

from campaia_core.permissions import Role

from .state import TokenPrincipal


class IdentityDirectory(Protocol):
    def resolve(self, email: str) -> TokenPrincipal | None: ...


class InMemoryIdentityDirectory:
    """Fixture de desenvolvimento -- mesmos 6 usuarios de `_seed_tokens()` (state.py),
    agora chaveados por e-mail verificado em vez de token opaco de bearer. Mesma
    disciplina: nunca um dado real, so seed local/teste."""

    def __init__(self, entries: dict[str, TokenPrincipal] | None = None) -> None:
        self._entries = dict(entries) if entries is not None else {}

    def resolve(self, email: str) -> TokenPrincipal | None:
        return self._entries.get(email)


def seed_dev_identity_directory() -> InMemoryIdentityDirectory:
    """Local dev/test fixtures only -- nunca um dado real. Mesmos usuarios/papeis/tenants
    de `state._seed_tokens()`, só chaveados por e-mail em vez de token."""
    return InMemoryIdentityDirectory(
        {
            "owner@demo-tenant.campaia.test": TokenPrincipal(
                user_id="user-owner-1",
                tenant_id="demo-tenant",
                roles=frozenset({Role.OWNER}),
                business_unit_id="bu-1",
            ),
            "marketer@demo-tenant.campaia.test": TokenPrincipal(
                user_id="user-marketer-1",
                tenant_id="demo-tenant",
                roles=frozenset({Role.MARKETER}),
                business_unit_id="bu-1",
            ),
            "approver@demo-tenant.campaia.test": TokenPrincipal(
                user_id="user-approver-1",
                tenant_id="demo-tenant",
                roles=frozenset({Role.APPROVER}),
                business_unit_id="bu-1",
            ),
            "finance@demo-tenant.campaia.test": TokenPrincipal(
                user_id="user-finance-1",
                tenant_id="demo-tenant",
                roles=frozenset({Role.FINANCE}),
                business_unit_id="bu-1",
            ),
            "viewer@demo-tenant.campaia.test": TokenPrincipal(
                user_id="user-viewer-1",
                tenant_id="demo-tenant",
                roles=frozenset({Role.VIEWER}),
                business_unit_id="bu-1",
            ),
            # Segundo tenant, para exercitar isolamento cross-tenant nos testes.
            "owner@other-tenant.campaia.test": TokenPrincipal(
                user_id="user-owner-2",
                tenant_id="other-tenant",
                roles=frozenset({Role.OWNER}),
                business_unit_id="bu-2",
            ),
        }
    )


__all__ = ["IdentityDirectory", "InMemoryIdentityDirectory", "seed_dev_identity_directory"]
