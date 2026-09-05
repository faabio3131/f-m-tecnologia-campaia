"""Idempotencia e Capability Registry.

Idempotencia: repetir um comando NAO pode duplicar efeito externo. A chave e sempre
composta com o `tenant_id` - uma chave de um tenant jamais alcanca o resultado de outro
(invariante I-04). Tentar isso levanta erro, em vez de vazar dado em silencio.

Capability Registry: a interface so oferece o que esta comprovado para aquela conta, pais e
versao de API. Capacidade sem verificacao recente e tratada como INDISPONIVEL, nao como
"provavelmente funciona".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .errors import CapabilityUnsupported, TenantIsolationViolation

#: Capacidade verificada ha mais tempo que isto deixa de ser oferecida.
DEFAULT_MAX_AGE = timedelta(days=30)


@dataclass(frozen=True)
class StoredResult:
    tenant_id: str
    idempotency_key: str
    result: Any
    stored_at: datetime


class IdempotencyStore:
    """Em memoria para teste de dominio. Em producao, tabela com constraint de unicidade."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], StoredResult] = {}

    def _key(self, tenant_id: str, idempotency_key: str) -> tuple[str, str]:
        if not tenant_id:
            raise TenantIsolationViolation("Operacao sem tenant_id nao e permitida.")
        return (tenant_id, idempotency_key)

    def get(self, tenant_id: str, idempotency_key: str) -> StoredResult | None:
        return self._entries.get(self._key(tenant_id, idempotency_key))

    def execute(self, tenant_id: str, idempotency_key: str, operation) -> tuple[Any, bool]:
        """Executa `operation` uma unica vez por (tenant, chave).

        Retorna (resultado, foi_replay). Em replay, `operation` NAO e chamada.
        """
        key = self._key(tenant_id, idempotency_key)
        existing = self._entries.get(key)
        if existing is not None:
            return existing.result, True

        result = operation()
        self._entries[key] = StoredResult(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            result=result,
            stored_at=datetime.now(timezone.utc),
        )
        return result, False


@dataclass(frozen=True)
class Capability:
    provider: str
    capability_key: str
    country: str
    api_version: str
    supported: bool
    verified_at: datetime
    evidence_url: str | None = None
    requires_approval: bool = False
    notes: str | None = None


@dataclass
class CapabilityRegistry:
    """Dado versionado, nao codigo. Carregado de configuracao (Capability Matrix)."""

    max_age: timedelta = DEFAULT_MAX_AGE
    _items: dict[tuple[str, str, str, str], Capability] = field(default_factory=dict)

    def register(self, cap: Capability) -> None:
        self._items[(cap.provider, cap.capability_key, cap.country, cap.api_version)] = cap

    def is_supported(
        self,
        provider: str,
        capability_key: str,
        *,
        country: str,
        api_version: str,
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.now(timezone.utc)
        cap = self._items.get((provider, capability_key, country, api_version))
        if cap is None or not cap.supported:
            return False
        return (now - cap.verified_at) <= self.max_age

    def require(
        self,
        provider: str,
        capability_key: str,
        *,
        country: str,
        api_version: str,
        now: datetime | None = None,
    ) -> Capability:
        if not self.is_supported(
            provider, capability_key, country=country, api_version=api_version, now=now
        ):
            raise CapabilityUnsupported(
                "Capacidade nao comprovada para esta conta, pais e versao de API. "
                "A acao nao e oferecida nem simulada.",
                provider=provider,
                capability_key=capability_key,
                country=country,
                api_version=api_version,
            )
        return self._items[(provider, capability_key, country, api_version)]
