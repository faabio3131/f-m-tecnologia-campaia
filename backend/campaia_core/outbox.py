"""Outbox e Inbox.

O problema do dual write: mudar o estado no banco e publicar o evento na fila sao duas
operacoes. Se a primeira funciona e a segunda falha, a campanha esta ativa no banco e
ninguem la fora ficou sabendo. Se a ordem se inverte, pior: avisamos sobre algo que nao
aconteceu.

Outbox resolve gravando o evento NA MESMA unidade de trabalho da mudanca de estado. Um
worker le depois e publica. Isso da entrega "pelo menos uma vez", nunca "no maximo uma vez":
na duvida, o evento sai duas vezes em vez de sumir.

Inbox e o outro lado: o consumidor deduplica por `event_id` e transforma "pelo menos uma
vez" em efeito unico. As duas pecas so funcionam juntas.

Ordem por agregado: eventos da mesma campanha saem na ordem em que foram gravados. Ordem
global nao e garantida e nao deve ser assumida.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .errors import TenantIsolationViolation

MAX_ATTEMPTS = 5


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass
class OutboxRecord:
    record_id: str
    tenant_id: str
    aggregate_id: str
    event_type: str
    payload: dict
    created_at: datetime
    sequence: int
    status: OutboxStatus = OutboxStatus.PENDING
    attempts: int = 0
    last_error: str | None = None


@dataclass
class Outbox:
    """Em memoria para teste de dominio. Em producao, tabela na mesma transacao do estado."""

    _records: list[OutboxRecord] = field(default_factory=list)
    _sequence: int = 0

    def append(
        self,
        *,
        tenant_id: str,
        aggregate_id: str,
        event_type: str,
        payload: dict,
        now: datetime,
    ) -> OutboxRecord:
        if not tenant_id:
            raise TenantIsolationViolation("Evento de outbox sem tenant_id.")
        self._sequence += 1
        record = OutboxRecord(
            record_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            created_at=now,
            sequence=self._sequence,
        )
        self._records.append(record)
        return record

    def pending(self, *, limit: int | None = None) -> list[OutboxRecord]:
        """Pendentes em ordem de gravacao. Garante ordem por agregado."""
        itens = [r for r in self._records if r.status is OutboxStatus.PENDING]
        itens.sort(key=lambda r: r.sequence)
        return itens[:limit] if limit else itens

    def mark_dispatched(self, record_id: str) -> None:
        record = self._get(record_id)
        record.status = OutboxStatus.DISPATCHED
        record.last_error = None

    def mark_failed(self, record_id: str, error: str) -> OutboxRecord:
        """Falha nao descarta o evento: ele continua pendente ate esgotar as tentativas."""
        record = self._get(record_id)
        record.attempts += 1
        record.last_error = error
        if record.attempts >= MAX_ATTEMPTS:
            record.status = OutboxStatus.DEAD_LETTER
        return record

    def dead_letters(self) -> list[OutboxRecord]:
        return [r for r in self._records if r.status is OutboxStatus.DEAD_LETTER]

    def _get(self, record_id: str) -> OutboxRecord:
        for r in self._records:
            if r.record_id == record_id:
                return r
        raise KeyError(record_id)


@dataclass
class Inbox:
    """Deduplicacao no consumidor. Converte 'pelo menos uma vez' em efeito unico."""

    _processed: dict[tuple[str, str], datetime] = field(default_factory=dict)

    def accept(self, *, tenant_id: str, event_id: str, now: datetime) -> bool:
        """True se e a primeira vez. False se ja foi processado - e nao e erro."""
        if not tenant_id:
            raise TenantIsolationViolation("Evento de inbox sem tenant_id.")
        chave = (tenant_id, event_id)
        if chave in self._processed:
            return False
        self._processed[chave] = now
        return True

    def was_processed(self, *, tenant_id: str, event_id: str) -> bool:
        return (tenant_id, event_id) in self._processed
