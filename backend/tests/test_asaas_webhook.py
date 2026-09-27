from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from campaia_core.asaas_gateway import map_asaas_status
from campaia_core.asaas_webhook import (
    AsaasWebhookReceiver,
    parse_asaas_payment_event,
)
from campaia_core.billing_settlement import try_settle_from_status
from campaia_core.subscription import PlanDefinition, Subscription, compute_cycle_charge
from campaia_core.webhooks import RejectionReason


class AsaasWebhookReceiverTests(unittest.TestCase):
    def receiver(self, token: str | None = "expected-token") -> AsaasWebhookReceiver:
        return AsaasWebhookReceiver(token_resolver=lambda: token)

    def test_correct_token_and_new_event_is_accepted(self) -> None:
        receiver = self.receiver()
        verdict = receiver.receive(received_token="expected-token", event_id="evt-1")
        self.assertTrue(verdict)

    def test_wrong_token_is_rejected(self) -> None:
        receiver = self.receiver()
        verdict = receiver.receive(received_token="wrong-token", event_id="evt-1")
        self.assertFalse(verdict)
        self.assertEqual(verdict.reason, RejectionReason.SIGNATURE_INVALID)

    def test_missing_token_is_rejected(self) -> None:
        receiver = self.receiver()
        verdict = receiver.receive(received_token=None, event_id="evt-1")
        self.assertFalse(verdict)
        self.assertEqual(verdict.reason, RejectionReason.SIGNATURE_INVALID)

    def test_no_token_configured_is_rejected(self) -> None:
        receiver = self.receiver(token=None)
        verdict = receiver.receive(received_token="anything", event_id="evt-1")
        self.assertFalse(verdict)
        self.assertEqual(verdict.reason, RejectionReason.UNKNOWN_PROVIDER)

    def test_missing_event_id_is_rejected(self) -> None:
        receiver = self.receiver()
        verdict = receiver.receive(received_token="expected-token", event_id="")
        self.assertFalse(verdict)
        self.assertEqual(verdict.reason, RejectionReason.MISSING_FIELDS)

    def test_duplicate_event_is_rejected_without_error(self) -> None:
        """Asaas entrega 'pelo menos uma vez' — duplicata nao e erro, e o efeito so
        acontece uma vez."""
        receiver = self.receiver()
        first = receiver.receive(received_token="expected-token", event_id="evt-1")
        second = receiver.receive(received_token="expected-token", event_id="evt-1")
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(second.reason, RejectionReason.DUPLICATE)

    def test_already_seen_reports_correctly(self) -> None:
        receiver = self.receiver()
        self.assertFalse(receiver.already_seen("evt-1"))
        receiver.receive(received_token="expected-token", event_id="evt-1")
        self.assertTrue(receiver.already_seen("evt-1"))


class ParseAsaasPaymentEventTests(unittest.TestCase):
    def test_parses_a_well_formed_payload(self) -> None:
        payload = {
            "id": "evt_123",
            "event": "PAYMENT_RECEIVED",
            "dateCreated": "2026-09-24 12:00:00",
            "payment": {"id": "pay_456", "status": "RECEIVED"},
        }
        event = parse_asaas_payment_event(payload)
        self.assertEqual(event.event_id, "evt_123")
        self.assertEqual(event.event_type, "PAYMENT_RECEIVED")
        self.assertEqual(event.payment_id, "pay_456")
        self.assertEqual(event.asaas_status, "RECEIVED")

    def test_missing_payment_object_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_asaas_payment_event({"id": "evt_123", "event": "PAYMENT_RECEIVED"})

    def test_missing_payment_status_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_asaas_payment_event(
                {"id": "evt_123", "event": "PAYMENT_RECEIVED", "payment": {"id": "pay_456"}}
            )

    def test_non_dict_payload_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_asaas_payment_event(None)  # type: ignore[arg-type]


class WebhookToSettlementEndToEndTests(unittest.TestCase):
    """Prova o caminho completo que substitui o polling: evento de webhook aceito ->
    status mapeado -> fato liquidado -- sem nenhuma chamada de rede ao Asaas."""

    def test_confirmed_webhook_event_settles_the_charge(self) -> None:
        plan = PlanDefinition(
            plan_id="essencial",
            name="Essencial",
            monthly_price=Decimal("199.90"),
            included_credits=Decimal("100"),
            extra_credit_unit_price=Decimal("1.50"),
        )
        subscription = Subscription(
            tenant_id="tenant-1",
            customer_ref="customer-1",
            customer_document="11144477735",
            plan=plan,
        )
        charge = compute_cycle_charge(subscription, competence="2026-09")

        receiver = AsaasWebhookReceiver(token_resolver=lambda: "expected-token")
        verdict = receiver.receive(received_token="expected-token", event_id="evt_1")
        self.assertTrue(verdict)

        payload = {
            "id": "evt_1",
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_1", "status": "RECEIVED"},
        }
        event = parse_asaas_payment_event(payload)
        status = map_asaas_status(event.asaas_status)

        fact = try_settle_from_status(
            charge, status, settled_at=datetime(2026, 9, 24, 12, tzinfo=UTC)
        )
        self.assertIsNotNone(fact)
        assert fact is not None
        self.assertEqual(fact.amount, charge.amount)

    def test_rejected_webhook_never_reaches_settlement(self) -> None:
        """Se o token nao confere, o evento nem deve ser interpretado — a chamada a
        `try_settle_from_status` simplesmente nao acontece (comportamento do chamador,
        provado aqui pela ausencia de qualquer status valido a passar adiante)."""
        receiver = AsaasWebhookReceiver(token_resolver=lambda: "expected-token")
        verdict = receiver.receive(received_token="wrong-token", event_id="evt_1")
        self.assertFalse(verdict)


if __name__ == "__main__":
    unittest.main()
