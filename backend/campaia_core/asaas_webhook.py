"""Recepcao de webhooks de pagamento do Asaas.

O Asaas NAO assina o corpo com HMAC (confirmado contra a documentacao oficial,
docs.asaas.com/docs/duvidas-frequentes-webhooks, 24/09/2026) — ele repete, no header
`asaas-access-token`, o mesmo token estatico configurado na criacao do webhook. A defesa
correta aqui e comparacao em tempo constante desse token contra o valor esperado — nao o
esquema HMAC(timestamp+corpo) de `webhooks.py`, que foi desenhado para outro tipo de
provedor e nao se aplica ao Asaas. Reaproveita `RejectionReason`/`WebhookVerdict` de
`webhooks.py` (mesmo vocabulario, verificacao diferente), em vez de duplicar esses tipos.

Dedupe por `id` do evento — o Asaas documenta entrega "pelo menos uma vez" (o mesmo evento
pode chegar mais de uma vez), mesma disciplina ja aplicada a outros provedores.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from typing import Any, Callable

from .webhooks import RejectionReason, WebhookVerdict


@dataclass
class AsaasWebhookReceiver:
    """Porta de entrada dos webhooks do Asaas.

    `token_resolver` devolve o token configurado a partir do cofre — nunca guardado em
    atributo, nunca logado, mesma disciplina de `WebhookReceiver.secret_resolver`.
    """

    token_resolver: Callable[[], str | None]
    #: Ids de evento ja processados. Nunca reprocessa o mesmo `id` duas vezes.
    _seen: set[str] = field(default_factory=set)
    rejections: list[RejectionReason] = field(default_factory=list)

    def _reject(self, reason: RejectionReason, detail: str) -> WebhookVerdict:
        self.rejections.append(reason)
        return WebhookVerdict(False, reason, detail)

    def receive(self, *, received_token: str | None, event_id: str) -> WebhookVerdict:
        expected = self.token_resolver()
        if not expected:
            return self._reject(
                RejectionReason.UNKNOWN_PROVIDER,
                "Nenhum token de webhook configurado para o Asaas.",
            )
        if not received_token or not hmac.compare_digest(received_token, expected):
            return self._reject(
                RejectionReason.SIGNATURE_INVALID, "Token do webhook do Asaas nao confere."
            )
        if not event_id:
            return self._reject(RejectionReason.MISSING_FIELDS, "Evento sem id.")
        if event_id in self._seen:
            return self._reject(
                RejectionReason.DUPLICATE, "Evento ja processado; efeito nao repetido."
            )
        self._seen.add(event_id)
        return WebhookVerdict(True, detail="Aceito.")

    def already_seen(self, event_id: str) -> bool:
        return event_id in self._seen


@dataclass(frozen=True, slots=True)
class AsaasPaymentEvent:
    event_id: str
    event_type: str
    payment_id: str
    asaas_status: str


def parse_asaas_payment_event(payload: dict[str, Any]) -> AsaasPaymentEvent:
    """Extrai os campos relevantes de um payload de webhook de cobranca do Asaas.

    Formato confirmado contra a documentacao oficial (docs.asaas.com, 24/09/2026):
    `{"id": "evt_...", "event": "PAYMENT_RECEIVED", "payment": {"id": "pay_...",
    "status": "RECEIVED", ...}}`. Falha fechado se faltar campo esperado — nunca segue
    processando um evento parcialmente interpretado.
    """
    try:
        event_id = payload["id"]
        event_type = payload["event"]
        payment = payload["payment"]
        payment_id = payment["id"]
        asaas_status = payment["status"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Payload de webhook do Asaas incompleto ou malformado: {payload!r}") from exc
    return AsaasPaymentEvent(
        event_id=event_id,
        event_type=event_type,
        payment_id=payment_id,
        asaas_status=asaas_status,
    )


__all__ = [
    "AsaasPaymentEvent",
    "AsaasWebhookReceiver",
    "parse_asaas_payment_event",
]
