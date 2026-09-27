"""Testes de webhooks, outbox e inbox.

Cobrem a ameaca T-02 (webhook forjado ou repetido) e o problema do dual write.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from campaia_core.errors import TenantIsolationViolation
from campaia_core.outbox import MAX_ATTEMPTS, Inbox, Outbox, OutboxStatus
from campaia_core.webhooks import (
    RejectionReason,
    WebhookEnvelope,
    WebhookReceiver,
    compute_signature,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
T1 = "tenant-1"
T2 = "tenant-2"
SEGREDOS = {"META": b"segredo-da-meta", "GOOGLE_ADS": b"segredo-do-google"}
CORPO = b'{"campaign":"123","status":"ACTIVE"}'


def _receiver(**kw) -> WebhookReceiver:
    return WebhookReceiver(secret_resolver=SEGREDOS.get, **kw)


def _envelope(
    *,
    provider="META",
    event_id="evt-1",
    timestamp=NOW,
    body=CORPO,
    signature=None,
    sign_with=None,
    sign_timestamp=None,
) -> WebhookEnvelope:
    if signature is None:
        secret = sign_with if sign_with is not None else SEGREDOS[provider]
        signature = compute_signature(secret, sign_timestamp or timestamp, body)
    return WebhookEnvelope(
        provider=provider,
        external_event_id=event_id,
        timestamp=timestamp,
        signature=signature,
        raw_body=body,
    )


class TestAssinatura(unittest.TestCase):
    def test_assinatura_valida_e_aceita(self):
        self.assertTrue(_receiver().receive(_envelope(), now=NOW))

    def test_assinatura_errada_e_recusada(self):
        v = _receiver().receive(_envelope(signature="0" * 64), now=NOW)
        self.assertFalse(v.accepted)
        self.assertIs(v.reason, RejectionReason.SIGNATURE_INVALID)

    def test_segredo_de_outro_provedor_nao_serve(self):
        env = _envelope(provider="META", sign_with=SEGREDOS["GOOGLE_ADS"])
        self.assertIs(
            _receiver().receive(env, now=NOW).reason, RejectionReason.SIGNATURE_INVALID
        )

    def test_corpo_alterado_invalida_a_assinatura(self):
        """Um byte trocado no payload derruba a verificacao."""
        env = _envelope()
        adulterado = WebhookEnvelope(
            provider=env.provider,
            external_event_id=env.external_event_id,
            timestamp=env.timestamp,
            signature=env.signature,
            raw_body=b'{"campaign":"999","status":"ACTIVE"}',
        )
        self.assertIs(
            _receiver().receive(adulterado, now=NOW).reason,
            RejectionReason.SIGNATURE_INVALID,
        )

    def test_provedor_desconhecido_e_recusado(self):
        env = _envelope(provider="DESCONHECIDO", sign_with=b"qualquer")
        self.assertIs(
            _receiver().receive(env, now=NOW).reason, RejectionReason.UNKNOWN_PROVIDER
        )

    def test_sem_assinatura_ou_sem_id_e_recusado(self):
        for kw in ({"signature": ""}, {"event_id": ""}):
            with self.subTest(kw=kw):
                self.assertIs(
                    _receiver().receive(_envelope(**kw), now=NOW).reason,
                    RejectionReason.MISSING_FIELDS,
                )

    def test_assinatura_e_verificada_antes_da_janela(self):
        """Assinatura invalida nao deve revelar se o horario estava certo."""
        env = _envelope(timestamp=NOW - timedelta(hours=3), signature="0" * 64)
        self.assertIs(
            _receiver().receive(env, now=NOW).reason, RejectionReason.SIGNATURE_INVALID
        )


class TestReplay(unittest.TestCase):
    def test_notificacao_antiga_e_recusada_mesmo_assinada(self):
        env = _envelope(timestamp=NOW - timedelta(hours=1))
        v = _receiver().receive(env, now=NOW)
        self.assertFalse(v.accepted)
        self.assertIs(v.reason, RejectionReason.TIMESTAMP_SKEW)

    def test_notificacao_do_futuro_tambem_e_recusada(self):
        env = _envelope(timestamp=NOW + timedelta(hours=1))
        self.assertIs(
            _receiver().receive(env, now=NOW).reason, RejectionReason.TIMESTAMP_SKEW
        )

    def test_dentro_da_janela_passa(self):
        env = _envelope(timestamp=NOW - timedelta(minutes=4))
        self.assertTrue(_receiver().receive(env, now=NOW))

    def test_timestamp_faz_parte_da_assinatura(self):
        """Trocar o horario mantendo a assinatura nao funciona."""
        env = _envelope(sign_timestamp=NOW - timedelta(hours=2), timestamp=NOW)
        self.assertIs(
            _receiver().receive(env, now=NOW).reason, RejectionReason.SIGNATURE_INVALID
        )

    def test_janela_configuravel(self):
        r = _receiver(tolerance=timedelta(seconds=30))
        self.assertFalse(r.receive(_envelope(timestamp=NOW - timedelta(minutes=2)), now=NOW))


class TestDeduplicacao(unittest.TestCase):
    def test_mesma_notificacao_duas_vezes_so_produz_efeito_uma(self):
        r = _receiver()
        env = _envelope(event_id="evt-42")
        self.assertTrue(r.receive(env, now=NOW))
        v = r.receive(env, now=NOW)
        self.assertFalse(v.accepted)
        self.assertIs(v.reason, RejectionReason.DUPLICATE)

    def test_ids_diferentes_sao_processados(self):
        r = _receiver()
        self.assertTrue(r.receive(_envelope(event_id="a"), now=NOW))
        self.assertTrue(r.receive(_envelope(event_id="b"), now=NOW))

    def test_mesmo_id_em_provedores_diferentes_nao_colide(self):
        r = _receiver()
        self.assertTrue(r.receive(_envelope(provider="META", event_id="1"), now=NOW))
        self.assertTrue(r.receive(_envelope(provider="GOOGLE_ADS", event_id="1"), now=NOW))

    def test_recusa_nao_marca_como_visto(self):
        """Notificacao com assinatura invalida nao pode bloquear a legitima depois."""
        r = _receiver()
        r.receive(_envelope(event_id="evt-9", signature="0" * 64), now=NOW)
        self.assertFalse(r.already_seen("META", "evt-9"))
        self.assertTrue(r.receive(_envelope(event_id="evt-9"), now=NOW))

    def test_recusas_ficam_registradas_sem_corpo_nem_assinatura(self):
        r = _receiver()
        r.receive(_envelope(signature="0" * 64), now=NOW)
        self.assertEqual(r.rejections, [("META", RejectionReason.SIGNATURE_INVALID)])


class TestOutbox(unittest.TestCase):
    def test_evento_nasce_pendente_e_e_entregue(self):
        ob = Outbox()
        rec = ob.append(
            tenant_id=T1,
            aggregate_id="c1",
            event_type="CampaignActivated",
            payload={},
            now=NOW,
        )
        self.assertEqual(len(ob.pending()), 1)
        ob.mark_dispatched(rec.record_id)
        self.assertEqual(ob.pending(), [])

    def test_falha_de_entrega_nao_descarta_o_evento(self):
        ob = Outbox()
        rec = ob.append(
            tenant_id=T1, aggregate_id="c1", event_type="X", payload={}, now=NOW
        )
        ob.mark_failed(rec.record_id, "fila indisponivel")
        self.assertEqual(len(ob.pending()), 1)
        self.assertEqual(ob.pending()[0].attempts, 1)

    def test_esgotar_tentativas_vira_dead_letter_e_nao_some(self):
        ob = Outbox()
        rec = ob.append(
            tenant_id=T1, aggregate_id="c1", event_type="X", payload={}, now=NOW
        )
        for _ in range(MAX_ATTEMPTS):
            ob.mark_failed(rec.record_id, "erro")
        self.assertEqual(ob.pending(), [])
        self.assertEqual(len(ob.dead_letters()), 1)
        self.assertIs(ob.dead_letters()[0].status, OutboxStatus.DEAD_LETTER)

    def test_ordem_por_agregado_e_preservada(self):
        ob = Outbox()
        for tipo in ("A", "B", "C"):
            ob.append(
                tenant_id=T1, aggregate_id="c1", event_type=tipo, payload={}, now=NOW
            )
        self.assertEqual([r.event_type for r in ob.pending()], ["A", "B", "C"])

    def test_evento_sem_tenant_e_recusado(self):
        with self.assertRaises(TenantIsolationViolation):
            Outbox().append(
                tenant_id="", aggregate_id="c1", event_type="X", payload={}, now=NOW
            )

    def test_limite_de_lote(self):
        ob = Outbox()
        for i in range(5):
            ob.append(
                tenant_id=T1, aggregate_id="c1", event_type=str(i), payload={}, now=NOW
            )
        self.assertEqual(len(ob.pending(limit=2)), 2)


class TestInbox(unittest.TestCase):
    def test_primeiro_processamento_passa_segundo_nao(self):
        inbox = Inbox()
        self.assertTrue(inbox.accept(tenant_id=T1, event_id="e1", now=NOW))
        self.assertFalse(inbox.accept(tenant_id=T1, event_id="e1", now=NOW))

    def test_mesmo_event_id_em_tenants_diferentes_nao_colide(self):
        inbox = Inbox()
        self.assertTrue(inbox.accept(tenant_id=T1, event_id="e1", now=NOW))
        self.assertTrue(inbox.accept(tenant_id=T2, event_id="e1", now=NOW))

    def test_evento_sem_tenant_e_recusado(self):
        with self.assertRaises(TenantIsolationViolation):
            Inbox().accept(tenant_id="", event_id="e1", now=NOW)


class TestOutboxComInbox(unittest.TestCase):
    """As duas pecas juntas: pelo menos uma vez na saida, efeito unico na entrada."""

    def test_entrega_duplicada_produz_um_unico_efeito(self):
        ob, inbox = Outbox(), Inbox()
        rec = ob.append(
            tenant_id=T1,
            aggregate_id="c1",
            event_type="CampaignActivated",
            payload={},
            now=NOW,
        )
        efeitos = []

        # Primeira entrega: o worker publica, mas o ack se perde.
        if inbox.accept(tenant_id=rec.tenant_id, event_id=rec.record_id, now=NOW):
            efeitos.append(rec.event_type)
        ob.mark_failed(rec.record_id, "ack perdido")

        # Reentrega do mesmo evento, porque ele continua pendente.
        pendente = ob.pending()[0]
        if inbox.accept(tenant_id=pendente.tenant_id, event_id=pendente.record_id, now=NOW):
            efeitos.append(pendente.event_type)
        ob.mark_dispatched(pendente.record_id)

        self.assertEqual(efeitos, ["CampaignActivated"])  # entregue 2x, aplicado 1x
        self.assertEqual(ob.pending(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
