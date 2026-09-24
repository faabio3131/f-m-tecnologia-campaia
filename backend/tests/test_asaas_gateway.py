from __future__ import annotations

import unittest
from decimal import Decimal

import httpx

from campaia_core.asaas_gateway import (
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    AsaasConfig,
    AsaasGateway,
)
from campaia_core.payment_gateway import (
    ChargeCommand,
    GatewayChargeStatus,
    GatewayMode,
    PaymentGatewayError,
    PaymentGatewayErrorCode,
)


def _config(**overrides) -> AsaasConfig:
    base = dict(api_key="$aact_hmlg_fake", mode=GatewayMode.SANDBOX, account_handle="acct-1", due_in_days=3)
    base.update(overrides)
    return AsaasConfig(**base)


def _command(idempotency_key: str = "idem-1") -> ChargeCommand:
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


class AsaasConfigTests(unittest.TestCase):
    def test_from_env_defaults_to_sandbox(self) -> None:
        env = {"ASAAS_API_KEY": "$aact_hmlg_x"}
        import os

        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            cfg = AsaasConfig.from_env()
            self.assertEqual(cfg.mode, GatewayMode.SANDBOX)
            self.assertEqual(cfg.due_in_days, 3)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_from_env_rejects_simulator_mode(self) -> None:
        import os

        old = os.environ.get("ASAAS_MODE")
        os.environ["ASAAS_MODE"] = "SIMULATOR"
        try:
            with self.assertRaises(PaymentGatewayError):
                AsaasConfig.from_env()
        finally:
            if old is None:
                os.environ.pop("ASAAS_MODE", None)
            else:
                os.environ["ASAAS_MODE"] = old

    def test_missing_api_key_fails_closed_on_construction(self) -> None:
        with self.assertRaises(PaymentGatewayError) as ctx:
            AsaasGateway(config=_config(api_key=None))
        self.assertEqual(ctx.exception.gateway_code, PaymentGatewayErrorCode.AUTH_EXPIRED)


class AsaasGatewayRequestShapeTests(unittest.TestCase):
    """Verifica a forma da requisicao e o parsing da resposta contra um transporte HTTP
    falso — nunca uma chamada de rede real (nenhuma credencial existe nesta sandbox)."""

    def _gateway(self, handler, mode: GatewayMode = GatewayMode.SANDBOX) -> AsaasGateway:
        transport = httpx.MockTransport(handler)
        return AsaasGateway(config=_config(mode=mode), transport=transport)

    def test_below_minimum_amount_is_rejected_before_any_network_call(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("nao deveria chamar a rede para valor abaixo do minimo")

        gateway = self._gateway(handler)
        command = _command()
        below_minimum = ChargeCommand(
            tenant_id=command.tenant_id,
            billing_id=command.billing_id,
            customer_ref=command.customer_ref,
            customer_document=command.customer_document,
            amount=Decimal("1.00"),
            currency=command.currency,
            competence=command.competence,
            idempotency_key=command.idempotency_key,
        )
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.create_charge(below_minimum)
        self.assertEqual(ctx.exception.gateway_code, PaymentGatewayErrorCode.VALIDATION_REJECTED)

    def test_sandbox_and_production_use_distinct_base_urls(self) -> None:
        seen_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_urls.append(str(request.url))
            if request.url.path.endswith("/customers"):
                return httpx.Response(200, json={"data": [{"id": "cus_1"}]})
            return httpx.Response(200, json={"id": "pay_1", "status": "PENDING"})

        sandbox_gw = self._gateway(handler, mode=GatewayMode.SANDBOX)
        sandbox_gw.create_charge(_command("idem-sandbox"))
        self.assertTrue(any(u.startswith(SANDBOX_BASE_URL) for u in seen_urls))

        seen_urls.clear()
        prod_gw = self._gateway(handler, mode=GatewayMode.PRODUCTION)
        prod_gw.create_charge(_command("idem-prod"))
        self.assertTrue(any(u.startswith(PRODUCTION_BASE_URL) for u in seen_urls))

    def test_create_charge_creates_customer_when_none_exists(self) -> None:
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "GET" and request.url.path.endswith("/customers"):
                return httpx.Response(200, json={"data": []})
            if request.method == "POST" and request.url.path.endswith("/customers"):
                import json

                customer_payload = json.loads(request.read())
                self.assertEqual(customer_payload["cpfCnpj"], "11144477735")
                return httpx.Response(200, json={"id": "cus_new"})
            if request.method == "POST" and request.url.path.endswith("/payments"):
                body = request.read()
                import json

                payload = json.loads(body)
                self.assertEqual(payload["customer"], "cus_new")
                self.assertEqual(payload["billingType"], "UNDEFINED")
                self.assertEqual(payload["value"], 199.90)
                self.assertEqual(payload["externalReference"], "idem-1")
                return httpx.Response(200, json={"id": "pay_1", "status": "PENDING"})
            raise AssertionError(f"chamada inesperada: {request.method} {request.url}")

        gateway = self._gateway(handler)
        result = gateway.create_charge(_command())
        self.assertEqual(result.gateway_charge_id, "pay_1")
        self.assertEqual(result.status, GatewayChargeStatus.PENDING)
        self.assertEqual(calls[0], ("GET", "/api/v3/customers"))
        self.assertEqual(calls[1], ("POST", "/api/v3/customers"))
        self.assertEqual(calls[2], ("POST", "/api/v3/payments"))

    def test_create_charge_reuses_existing_customer(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/customers"):
                return httpx.Response(200, json={"data": [{"id": "cus_existing"}]})
            import json

            payload = json.loads(request.read())
            assert payload["customer"] == "cus_existing"
            return httpx.Response(200, json={"id": "pay_2", "status": "PENDING"})

        gateway = self._gateway(handler)
        gateway.create_charge(_command())

    def test_retry_with_same_idempotency_key_never_calls_network_again(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if request.url.path.endswith("/customers"):
                return httpx.Response(200, json={"data": [{"id": "cus_1"}]})
            return httpx.Response(200, json={"id": "pay_1", "status": "PENDING"})

        gateway = self._gateway(handler)
        first = gateway.create_charge(_command())
        calls_after_first = call_count
        second = gateway.create_charge(_command())
        self.assertEqual(first.gateway_charge_id, second.gateway_charge_id)
        self.assertEqual(call_count, calls_after_first)  # nenhuma nova chamada de rede

    def test_confirmed_status_mapping(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "RECEIVED"})

        gateway = self._gateway(handler)
        status = gateway.get_charge_status("pay_1")
        self.assertEqual(status, GatewayChargeStatus.CONFIRMED)

    def test_refunded_status_maps_to_failed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "REFUNDED"})

        gateway = self._gateway(handler)
        self.assertEqual(gateway.get_charge_status("pay_1"), GatewayChargeStatus.FAILED)

    def test_unknown_status_fails_closed_to_pending(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "SOME_FUTURE_STATUS_NOT_YET_MAPPED"})

        gateway = self._gateway(handler)
        self.assertEqual(gateway.get_charge_status("pay_1"), GatewayChargeStatus.PENDING)

    def test_401_maps_to_auth_expired(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"errors": [{"description": "invalid token"}]})

        gateway = self._gateway(handler)
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.get_charge_status("pay_1")
        self.assertEqual(ctx.exception.gateway_code, PaymentGatewayErrorCode.AUTH_EXPIRED)

    def test_400_maps_to_validation_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"errors": [{"description": "bad value"}]})

        gateway = self._gateway(handler)
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.get_charge_status("pay_1")
        self.assertEqual(ctx.exception.gateway_code, PaymentGatewayErrorCode.VALIDATION_REJECTED)

    def test_429_maps_to_rate_limited(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={})

        gateway = self._gateway(handler)
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.get_charge_status("pay_1")
        self.assertEqual(ctx.exception.gateway_code, PaymentGatewayErrorCode.RATE_LIMITED)

    def test_500_maps_to_transient_and_is_retryable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal error")

        gateway = self._gateway(handler)
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.get_charge_status("pay_1")
        self.assertEqual(ctx.exception.gateway_code, PaymentGatewayErrorCode.TRANSIENT)
        self.assertTrue(ctx.exception.retryable)


if __name__ == "__main__":
    unittest.main()
