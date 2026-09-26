"""Diretorio interno: e-mail verificado (Google) -> vinculos (`TokenPrincipal`) de
tenant/papeis/unidade.

Decisao (Diretor, 24/09/2026, item 1.3/WP-02): a identidade do Google prova QUEM e o
usuario; tenant_id, roles e business_unit_id vem SEMPRE deste diretorio interno, nunca de
claim do provedor de identidade. E-mail verificado sem entrada aqui e RECUSADO fail-closed
-- nunca autoprovisionado. Autoprovisionamento/convite de usuario e Work Package futuro,
fora do escopo do WP-02 (decisao de produto separada, nao tecnica).

WP-03 (25/09/2026): um e-mail pode ter MAIS DE UM vinculo (ex.: um usuario que atua em dois
tenants distintos) -- `resolve()` continua devolvendo um unico `TokenPrincipal` (o vinculo
"padrao", o primeiro cadastrado, para nao quebrar nenhum chamador existente), e o novo
`resolve_all()` devolve TODOS os vinculos daquele e-mail, na ordem cadastrada. E' isto que
alimenta `GET /me/memberships` e a troca de tenant/unidade ativo da sessao
(`POST /auth/session/switch`, ver api/routes_auth.py e api/session.py).
"""

from __future__ import annotations

from typing import Protocol

from campaia_core.permissions import Role

from .state import TokenPrincipal


class IdentityDirectory(Protocol):
    def resolve(self, email: str) -> TokenPrincipal | None: ...
    def resolve_all(self, email: str) -> tuple[TokenPrincipal, ...]: ...


class InMemoryIdentityDirectory:
    """Fixture de desenvolvimento -- mesmos usuarios de `_seed_tokens()` (state.py),
    agora chaveados por e-mail verificado em vez de token opaco de bearer. Mesma
    disciplina: nunca um dado real, so seed local/teste."""

    def __init__(self, entries: dict[str, tuple[TokenPrincipal, ...]] | None = None) -> None:
        self._entries: dict[str, tuple[TokenPrincipal, ...]] = (
            dict(entries) if entries is not None else {}
        )

    def resolve(self, email: str) -> TokenPrincipal | None:
        memberships = self._entries.get(email)
        return memberships[0] if memberships else None

    def resolve_all(self, email: str) -> tuple[TokenPrincipal, ...]:
        return self._entries.get(email, ())


def seed_dev_identity_directory() -> InMemoryIdentityDirectory:
    """Local dev/test fixtures only -- nunca um dado real. Mesmos usuarios/papeis/tenants
    de `state._seed_tokens()`, só chaveados por e-mail em vez de token, mais um e-mail com
    DOIS vinculos (WP-03) para exercitar a troca de tenant/unidade de verdade."""
    return InMemoryIdentityDirectory(
        {
            "owner@demo-tenant.campaia.test": (
                TokenPrincipal(
                    user_id="user-owner-1",
                    tenant_id="demo-tenant",
                    roles=frozenset({Role.OWNER}),
                    business_unit_id="bu-1",
                ),
            ),
            "marketer@demo-tenant.campaia.test": (
                TokenPrincipal(
                    user_id="user-marketer-1",
                    tenant_id="demo-tenant",
                    roles=frozenset({Role.MARKETER}),
                    business_unit_id="bu-1",
                ),
            ),
            "approver@demo-tenant.campaia.test": (
                TokenPrincipal(
                    user_id="user-approver-1",
                    tenant_id="demo-tenant",
                    roles=frozenset({Role.APPROVER}),
                    business_unit_id="bu-1",
                ),
            ),
            "finance@demo-tenant.campaia.test": (
                TokenPrincipal(
                    user_id="user-finance-1",
                    tenant_id="demo-tenant",
                    roles=frozenset({Role.FINANCE}),
                    business_unit_id="bu-1",
                ),
            ),
            "viewer@demo-tenant.campaia.test": (
                TokenPrincipal(
                    user_id="user-viewer-1",
                    tenant_id="demo-tenant",
                    roles=frozenset({Role.VIEWER}),
                    business_unit_id="bu-1",
                ),
            ),
            # Segundo tenant, para exercitar isolamento cross-tenant nos testes.
            "owner@other-tenant.campaia.test": (
                TokenPrincipal(
                    user_id="user-owner-2",
                    tenant_id="other-tenant",
                    roles=frozenset({Role.OWNER}),
                    business_unit_id="bu-2",
                ),
            ),
            # WP-03 (25/09/2026): identidade com DOIS vinculos reais, um em cada tenant --
            # so este e-mail exercita `GET /me/memberships` com mais de um item e a troca
            # de tenant/unidade ativo (POST /auth/session/switch).
            "owner@multi-tenant.campaia.test": (
                TokenPrincipal(
                    user_id="user-multi-1a",
                    tenant_id="demo-tenant",
                    roles=frozenset({Role.OWNER}),
                    business_unit_id="bu-1",
                ),
                TokenPrincipal(
                    user_id="user-multi-1b",
                    tenant_id="other-tenant",
                    roles=frozenset({Role.OWNER}),
                    business_unit_id="bu-2",
                ),
            ),
        }
    )


__all__ = ["IdentityDirectory", "InMemoryIdentityDirectory", "seed_dev_identity_directory"]
