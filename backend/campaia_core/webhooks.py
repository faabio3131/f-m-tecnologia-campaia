"""Recepcao de webhooks: assinatura, replay e deduplicacao.

Ameaca T-02 do threat model: webhook forjado ou repetido. Um webhook e um endpoint publico
que aceita dados de fora e mexe no estado interno. Se ele confiar no corpo da requisicao,
qualquer um na internet consegue marcar campanhas como ativas, injetar metricas falsas ou
disparar reprocessamento em massa.

Tres defesas, nesta ordem:

  1. ASSINATURA  HMAC-SHA256 sobre timestamp + corpo cru, comparada em tempo constante.
                 Comparacao com `==` vaza informacao por tempo de resposta e permite
                 descobrir a assinatura byte a byte.

  2. JANELA      Assinatura valida capturada ontem continua valida para sempre se nao
                 houver limite de tempo. Fora da janela, recusa.

  3. DEDUPE      Provedores entregam "pelo menos uma vez": a mesma notificacao chega duas
                 vezes normalmente, sem ninguem atacar. O consumidor e que torna o efeito
                 unico.

A assinatura e verificada sobre o CORPO CRU, antes de qualquer parse. Fazer parse primeiro
significa processar dado nao confiavel.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Callable, Protocol

#: Fora desta janela, a notificacao e recusada mesmo com assinatura correta.
DEFAULT_TOLERANCE = timedelta(minutes=5)


class RejectionReason(StrEnum):
    MISSING_FIELDS = "MISSING_FIELDS"
    UNKNOWN_PROVIDER = "UNKNOWN_PROVIDER"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    TIMESTAMP_SKEW = "TIMESTAMP_SKEW"
    DUPLICATE = "DUPLICATE"


@dataclass(frozen=True)
class WebhookEnvelope:
    """O que chega no endpoint, antes de qualquer interpretacao."""

    provider: str
    external_event_id: str
    timestamp: datetime
    signature: str
    raw_body: bytes


@dataclass(frozen=True)
class WebhookVerdict:
    accepted: bool
    reason: RejectionReason | None = None
    detail: str = ""

    def __bool__(self) -> bool:
        return self.accepted


_ACCEPTED = WebhookVerdict(accepted=True, detail="Aceito.")


class SeenEventStoreLike(Protocol):
    """Registro de "ja processei este evento" — mesmo principio de `IdempotencyStoreLike`
    (`payment_gateway.py`): a memoria de dedupe injetavel, nao fixa dentro do receptor.

    Cronograma mestre, Etapa 1, item 1.1 (24/09/2026): o dedupe do webhook era mantido so em
    memoria dentro do proprio receptor — reiniciar o processo entre duas entregas do mesmo
    evento ("pelo menos uma vez") perdia a garantia. Injetar isso permite trocar por uma
    implementacao persistida (`api.db.PersistentSeenEventStore`) sem tocar em nenhum receptor.
    """

    def mark_if_new(self, provider: str, event_id: str) -> bool:
        """Registra (provider, event_id) como visto. Devolve True se era novo (e acaba de
        ser marcado), False se ja havia sido visto antes."""
        ...

    def contains(self, provider: str, event_id: str) -> bool:
        """So consulta, sem marcar. Usado por `already_seen` (debug/teste)."""
        ...


@dataclass
class InMemorySeenEventStore:
    """Implementacao padrao — comportamento identico ao dedupe embutido que existia antes
    desta correcao. Uso: desenvolvimento, testes, CI."""

    _seen: set[tuple[str, str]] = field(default_factory=set)

    def mark_if_new(self, provider: str, event_id: str) -> bool:
        key = (provider, event_id)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def contains(self, provider: str, event_id: str) -> bool:
        return (provider, event_id) in self._seen


def _signing_payload(timestamp: datetime, raw_body: bytes) -> bytes:
    """Timestamp entra na assinatura. Se ficasse de fora, um atacante poderia reaproveitar
    uma assinatura valida com outro horario e derrubar a protecao de replay."""
    return timestamp.isoformat().encode("utf-8") + b"." + raw_body


def compute_signature(secret: bytes, timestamp: datetime, raw_body: bytes) -> str:
    return hmac.new(secret, _signing_payload(timestamp, raw_body), hashlib.sha256).hexdigest()


@dataclass
class WebhookReceiver:
    """Porta de entrada dos webhooks.

    `secret_resolver` devolve o segredo de assinatura do provedor a partir do cofre. Este e
    o unico ponto do sistema que precisa do VALOR de um segredo, e ele nao sai daqui: nao e
    guardado em atributo, nao entra em log e nao vai para mensagem de erro.
    """

    secret_resolver: Callable[[str], bytes | None]
    tolerance: timedelta = DEFAULT_TOLERANCE
    #: Injetavel (item 1.1 do cronograma mestre, 24/09/2026) — em memoria por padrao, mas
    #: pode receber uma implementacao persistida sem alterar este receptor.
    seen_store: SeenEventStoreLike = field(default_factory=InMemorySeenEventStore)
    #: Recusas registradas para observabilidade. Nunca guarda corpo nem assinatura.
    rejections: list[tuple[str, RejectionReason]] = field(default_factory=list)

    def _reject(
        self, provider: str, reason: RejectionReason, detail: str
    ) -> WebhookVerdict:
        self.rejections.append((provider, reason))
        return WebhookVerdict(False, reason, detail)

    def receive(self, envelope: WebhookEnvelope, *, now: datetime) -> WebhookVerdict:
        if not envelope.external_event_id or not envelope.signature:
            return self._reject(
                envelope.provider,
                RejectionReason.MISSING_FIELDS,
                "Notificacao sem identificador ou sem assinatura.",
            )

        secret = self.secret_resolver(envelope.provider)
        if secret is None:
            return self._reject(
                envelope.provider,
                RejectionReason.UNKNOWN_PROVIDER,
                "Provedor sem segredo de assinatura configurado.",
            )

        esperado = compute_signature(secret, envelope.timestamp, envelope.raw_body)
        # compare_digest: tempo constante. Com `==`, o tempo de resposta revelaria
        # quantos bytes iniciais estao corretos.
        if not hmac.compare_digest(esperado, envelope.signature):
            return self._reject(
                envelope.provider,
                RejectionReason.SIGNATURE_INVALID,
                "Assinatura nao confere.",
            )

        if abs(now - envelope.timestamp) > self.tolerance:
            return self._reject(
                envelope.provider,
                RejectionReason.TIMESTAMP_SKEW,
                "Notificacao fora da janela de tolerancia.",
            )

        is_new = self.seen_store.mark_if_new(envelope.provider, envelope.external_event_id)
        if not is_new:
            # Duplicata NAO e erro: provedores entregam pelo menos uma vez. Recusar o
            # efeito duplicado e o comportamento correto, e o provedor nao precisa saber.
            return self._reject(
                envelope.provider,
                RejectionReason.DUPLICATE,
                "Notificacao ja processada; efeito nao repetido.",
            )

        return _ACCEPTED

    def already_seen(self, provider: str, external_event_id: str) -> bool:
        return self.seen_store.contains(provider, external_event_id)
