from __future__ import annotations

import unittest
from decimal import Decimal

from campaia_core.payment_gateway import (
    ChargeCommand,
    GatewayChargeStatus,
    PaymentGatewayError,
    PaymentGatewayErrorCode,
)
from campaia_core.infra import IdempotencyStore
from campaia_core.payment_simulator import PaymentGatewaySimulator


class PaymentGatewaySimulatorTests(unittest.TestCase):
    def command(self, idempotency_key: str = "idem-1") -> ChargeCommand:
        return ChargeCommand(
            tenant_id="tenant-1",
            billing_id="sub:tenant-1:2026-09",
            customer_ref="customer-1",
            customer_document="11144477735",
            amount=Decimal("199.90"),
            currency="BRL",
            competence="2026-09",
            idempotency_key=idempotency_key,
        )

    def test_create_charge_starts_pending(self) -> None:
        gateway = PaymentGatewaySimulator()
        result = gateway.create_charge(self.command())
        self.assertEqual(result.status, GatewayChargeStatus.PENDING)
        self.assertEqual(
            gateway.get_charge_status(result.gateway_charge_id), GatewayChargeStatus.PENDING
        )

    def test_retry_with_same_idempotency_key_does_not_duplicate(self) -> None:
        gateway = PaymentGatewaySimulator()
        first = gateway.create_charge(self.command())
        second = gateway.create_charge(self.command())
        self.assertEqual(first.gateway_charge_id, second.gateway_charge_id)

    def test_different_idempotency_keys_create_distinct_charges(self) -> None:
        gateway = PaymentGatewaySimulator()
        first = gateway.create_charge(self.command("idem-1"))
        second = gateway.create_charge(self.command("idem-2"))
        self.assertNotEqual(first.gateway_charge_id, second.gateway_charge_id)

    def test_confirm_moves_status_to_confirmed(self) -> None:
        gateway = PaymentGatewaySimulator()
        result = gateway.create_charge(self.command())
        gateway.confirm(result.gateway_charge_id)
        self.assertEqual(
            gateway.get_charge_status(result.gateway_charge_id), GatewayChargeStatus.CONFIRMED
        )

    def test_scripted_failure_is_raised_and_not_retried_silently(self) -> None:
        gateway = PaymentGatewaySimulator(
            scripted_failures=[PaymentGatewayErrorCode.DECLINED]
        )
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.create_charge(self.command())
        self.assertEqual(ctx.exception.gateway_code, PaymentGatewayErrorCode.DECLINED)
        self.assertFalse(ctx.exception.retryable)

    def test_transient_failure_is_marked_retryable(self) -> None:
        gateway = PaymentGatewaySimulator(
            scripted_failures=[PaymentGatewayErrorCode.TRANSIENT]
        )
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.create_charge(self.command())
        self.assertTrue(ctx.exception.retryable)

    def test_missing_idempotency_key_is_rejected(self) -> None:
        gateway = PaymentGatewaySimulator()
        with self.assertRaises(PaymentGatewayError):
            gateway.create_charge(self.command(""))

    def test_non_brl_currency_is_rejected(self) -> None:
        gateway = PaymentGatewaySimulator()
        bad = ChargeCommand(
            tenant_id="tenant-1",
            billing_id="b",
            customer_ref="c",
            customer_document="11144477735",
            amount=Decimal("10"),
            currency="USD",
            competence="2026-09",
            idempotency_key="idem-x",
        )
        with self.assertRaises(PaymentGatewayError):
            gateway.create_charge(bad)

    def test_non_positive_amount_is_rejected(self) -> None:
        gateway = PaymentGatewaySimulator()
        bad = ChargeCommand(
            tenant_id="tenant-1",
            billing_id="b",
            customer_ref="c",
            customer_document="11144477735",
            amount=Decimal("0"),
            currency="BRL",
            competence="2026-09",
            idempotency_key="idem-x",
        )
        with self.assertRaises(PaymentGatewayError):
            gateway.create_charge(bad)

    def test_missing_customer_document_is_rejected(self) -> None:
        gateway = PaymentGatewaySimulator()
        bad = ChargeCommand(
            tenant_id="tenant-1",
            billing_id="b",
            customer_ref="c",
            customer_document="",
            amount=Decimal("10"),
            currency="BRL",
            competence="2026-09",
            idempotency_key="idem-x",
        )
        with self.assertRaises(PaymentGatewayError):
            gateway.create_charge(bad)

    def test_resolve_secret_never_exposes_a_raw_value(self) -> None:
        gateway = PaymentGatewaySimulator()
        secret = gateway.resolve_secret("acct-1")
        self.assertEqual(repr(secret), "<SecretRef REDACTED>")

    def test_idempotency_survives_a_process_restart_via_shared_external_store(self) -> None:
        """fm-security-review (24/09/2026): idempotencia so em memoria dentro do gateway
        perdia a garantia contra cobranca duplicada num reinicio de processo. Duas instancias
        de gateway compartilhando o mesmo `IdempotencyStore` externo simulam exatamente esse
        cenario — a segunda instancia (o "processo reiniciado") deve devolver o mesmo
        resultado, nunca criar uma segunda cobranca."""
        shared_store = IdempotencyStore()
        first_process = PaymentGatewaySimulator(idempotency=shared_store)
        result_before_restart = first_process.create_charge(self.command())

        second_process = PaymentGatewaySimulator(idempotency=shared_store)
        result_after_restart = second_process.create_charge(self.command())

        self.assertEqual(
            result_before_restart.gateway_charge_id, result_after_restart.gateway_charge_id
        )

if __name__ == "__main__":
    unittest.main()
