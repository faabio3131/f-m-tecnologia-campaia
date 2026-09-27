"""Rate limiting para endpoints publicos.

Cronograma mestre, Etapa 1, item 1.2 (24/09/2026): `/webhooks/asaas` e o unico endpoint
deste app sem autenticacao de usuario (quem chama e o Asaas, nao um Bearer token de sessao)
-- exatamente por isso e o unico alvo publico de flood/DoS de aplicacao sem essa defesa.
Janela fixa por chave (aqui, IP de origem): simples, sem estado externo, proporcional ao
tamanho atual do sistema (um processo, sem fila/worker pool) -- mesma disciplina de
proporcionalidade ja usada em `PersistentIdempotencyStore`/`PersistentSeenEventStore`.

Nao e defesa contra um atacante distribuido (muitos IPs); e defesa contra excesso de volume
de uma unica origem, que e a ameaca proporcional a este estagio do produto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class FixedWindowRateLimiter:
    """`max_requests` permitidas por `window` por chave. Janela fixa (nao deslizante): mais
    simples, e a imprecisao de borda (rajada em torno da virada da janela) e aceitavel para
    a ameaca que isto mitiga -- volume sustentado de uma origem, nao um limite exato.
    """

    max_requests: int
    window: timedelta
    _windows: dict[str, tuple[datetime, int]] = field(default_factory=dict)

    def allow(self, key: str, *, now: datetime) -> bool:
        if not key:
            # Sem chave para agrupar por origem, falha fechado: nao deixa passar sem limite.
            return False
        started_at, count = self._windows.get(key, (now, 0))
        if now - started_at >= self.window:
            started_at, count = now, 0
        count += 1
        self._windows[key] = (started_at, count)
        return count <= self.max_requests


__all__ = ["FixedWindowRateLimiter"]
