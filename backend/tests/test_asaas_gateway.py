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
from campaia_core.infra import IdempotencyStore
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
    def test_final_residual_minimum_requires_explicit_valid_configuration(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'ASAAS_API_KEY': 'fixture-key', 'ASAAS_MINIMUM_CHARGE_AMOUNT': '5.00'}):
            self.assertEqual(AsaasConfig.from_env().minimum_charge_amount, Decimal('5.00'))
        for raw in ('0', 'NaN', '1.001'):
            with patch.dict(os.environ, {'ASAAS_API_KEY': 'fixture-key', 'ASAAS_MINIMUM_CHARGE_AMOUNT': raw}):
                with self.assertRaises(PaymentGatewayError):
                    AsaasConfig.from_env()

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

    def test_receipt_inspection_uses_only_get_and_binds_frozen_external_reference(self):
        calls = []
        def handler(request):
            calls.append((request.method, request.url.path))
            return httpx.Response(200, json={'id': 'pay-known', 'externalReference': 'idem-1',
                'status': 'RECEIVED', 'value': '199.90', 'netValue': '190.00'})
        gateway = self._gateway(handler)
        result = gateway.inspect_charge('pay-known', _command())
        self.assertEqual(result.observed_amount, Decimal('199.90'))
        self.assertEqual(result.source_status, 'RECEIVED')
        self.assertEqual(result.status, GatewayChargeStatus.CONFIRMED)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'GET')
        self.assertTrue(calls[0][1].endswith('/payments/pay-known'))
        for field, value in [('id', 'another-payment'), ('externalReference', 'another-obligation')]:
            def mismatch(request):
                return httpx.Response(200, json={'id': 'pay-known', 'externalReference': 'idem-1',
                    'status': 'RECEIVED', 'value': '199.90', field: value})
            with self.assertRaises(PaymentGatewayError):
                self._gateway(mismatch).inspect_charge('pay-known', _command())

    def test_receipt_inspection_preserves_zero_and_rejects_invalid_precision_without_rounding(self):
        for value, expected in [(0, Decimal('0')), (None, None), (True, None), ('NaN', None), ('199.901', None)]:
            with self.subTest(value=value):
                def handler(request):
                    return httpx.Response(200, json={'id': 'pay-known', 'externalReference': 'idem-1',
                        'status': 'CONFIRMED', 'value': value})
                result = self._gateway(handler).inspect_charge('pay-known', _command())
                self.assertEqual(result.observed_amount, expected)

    def _gateway(self, handler, mode: GatewayMode = GatewayMode.SANDBOX) -> AsaasGateway:
        def wrapped(request: httpx.Request) -> httpx.Response:
            # Every create now performs provider-side reconciliation first. Existing request
            # shape tests are about the operation under test, so their default provider has
            # no prior payment unless a dedicated recovery test says otherwise.
            if request.method == "GET" and request.url.path.endswith("/payments"):
                return httpx.Response(200, json={"data": []})
            return handler(request)

        transport = httpx.MockTransport(wrapped)
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

    def test_idempotency_survives_a_process_restart_via_shared_external_store(self) -> None:
        """fm-security-review (24/09/2026): duas instancias de `AsaasGateway` compartilhando
        o mesmo `IdempotencyStore` externo simulam um reinicio de processo entre a criacao
        da cobranca e uma tentativa de retry — a segunda instancia nunca deve chamar a rede
        de novo para criar uma segunda cobranca real no Asaas."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if request.method == "GET" and request.url.path.endswith("/payments"):
                return httpx.Response(200, json={"data": []})
            if request.url.path.endswith("/customers"):
                return httpx.Response(200, json={"data": [{"id": "cus_1"}]})
            return httpx.Response(200, json={"id": "pay_1", "status": "PENDING"})

        transport = httpx.MockTransport(handler)
        shared_store = IdempotencyStore()

        first_process = AsaasGateway(config=_config(), transport=transport, idempotency=shared_store)
        result_before_restart = first_process.create_charge(_command())
        calls_after_first_process = call_count

        second_process = AsaasGateway(config=_config(), transport=transport, idempotency=shared_store)
        result_after_restart = second_process.create_charge(_command())

        self.assertEqual(
            result_before_restart.gateway_charge_id, result_after_restart.gateway_charge_id
        )
        self.assertEqual(call_count, calls_after_first_process)  # nenhuma nova chamada de rede

    def test_provider_reconciliation_recovers_after_local_idempotency_loss(self) -> None:
        """Crash window proof: process A creates the external payment, then its local
        idempotency result is lost before commit. Process B starts with a fresh local store.
        The deterministic externalReference lookup must recover the existing Asaas payment
        instead of issuing a second POST /payments.
        """
        provider_payment: dict | None = None
        payment_posts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal provider_payment, payment_posts
            if request.method == "GET" and request.url.path.endswith("/payments"):
                self.assertEqual(request.url.params["externalReference"], "idem-crash-window")
                return httpx.Response(
                    200,
                    json={"data": [] if provider_payment is None else [provider_payment]},
                )
            if request.method == "GET" and request.url.path.endswith("/customers"):
                return httpx.Response(200, json={"data": [{"id": "cus_1"}]})
            if request.method == "POST" and request.url.path.endswith("/payments"):
                payment_posts += 1
                provider_payment = {"id": "pay_recovered", "status": "PENDING"}
                return httpx.Response(200, json=provider_payment)
            raise AssertionError(f"chamada inesperada: {request.method} {request.url}")

        transport = httpx.MockTransport(handler)
        first_process = AsaasGateway(
            config=_config(), transport=transport, idempotency=IdempotencyStore()
        )
        before_crash = first_process.create_charge(_command("idem-crash-window"))
        self.assertEqual(before_crash.gateway_charge_id, "pay_recovered")
        self.assertEqual(payment_posts, 1)

        # Fresh store deliberately simulates loss/rollback of the local idempotency commit.
        second_process = AsaasGateway(
            config=_config(), transport=transport, idempotency=IdempotencyStore()
        )
        after_restart = second_process.create_charge(_command("idem-crash-window"))

        self.assertEqual(after_restart.gateway_charge_id, "pay_recovered")
        self.assertEqual(payment_posts, 1)

    def test_duplicate_provider_matches_fail_closed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path.endswith("/payments"):
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "pay_1", "status": "PENDING"},
                            {"id": "pay_2", "status": "PENDING"},
                        ]
                    },
                )
            raise AssertionError("duplicate reconciliation must fail before customer/create")

        gateway = AsaasGateway(
            config=_config(),
            transport=httpx.MockTransport(handler),
            idempotency=IdempotencyStore(),
        )
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.create_charge(_command("idem-duplicate-provider"))
        self.assertEqual(ctx.exception.gateway_code, PaymentGatewayErrorCode.UNKNOWN)

    def test_confirmed_status_mapping(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "RECEIVED"})

        gateway = self._gateway(handler)
        status = gateway.get_charge_status("pay_1")
        self.assertEqual(status, GatewayChargeStatus.CONFIRMED)

    def test_overdue_status_maps_to_overdue(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "OVERDUE"})

        gateway = self._gateway(handler)
        self.assertEqual(gateway.get_charge_status("pay_1"), GatewayChargeStatus.OVERDUE)

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

    def test_error_detail_never_includes_the_raw_response_body(self) -> None:
        """fm-security-review (24/09/2026): um corpo de erro de validacao pode ecoar de volta
        um campo submetido (ex.: cpfCnpj, PII). So o resumo estruturado (code+description)
        pode ir para `details` — nunca o texto bruto da resposta."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={
                    "errors": [
                        {"code": "invalid_cpfCnpj", "description": "cpfCnpj 11144477735 invalido"}
                    ]
                },
            )

        gateway = self._gateway(handler)
        with self.assertRaises(PaymentGatewayError) as ctx:
            gateway.get_charge_status("pay_1")
        self.assertNotIn("body", ctx.exception.details)
        self.assertIn("error_summary", ctx.exception.details)
        self.assertIn("invalid_cpfCnpj", ctx.exception.details["error_summary"])

    def test_config_repr_never_exposes_the_api_key(self) -> None:
        """fm-security-review (24/09/2026): repr padrao de dataclass expunha a chave em
        claro — corrigido com `field(repr=False)`."""
        config = _config(api_key="SECRET_VALUE_MUST_NOT_APPEAR")
        self.assertNotIn("SECRET_VALUE_MUST_NOT_APPEAR", repr(config))

        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
        gateway = AsaasGateway(config=config, transport=transport)
        self.assertNotIn("SECRET_VALUE_MUST_NOT_APPEAR", repr(gateway))

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


class AsaasHostedInvoiceTests(unittest.TestCase):
    def test_frozen_dispatch_uses_contracted_due_date_in_sao_paulo_without_late_fees(self):
        from dataclasses import replace
        from datetime import datetime, timezone
        import json
        posts = []
        def handler(request):
            if request.method == 'GET' and request.url.path.endswith('/payments'):
                return httpx.Response(200, json={'data': []})
            if request.method == 'GET' and request.url.path.endswith('/customers'):
                return httpx.Response(200, json={'data': [{'id': 'fixture-customer'}]})
            if request.method == 'POST' and request.url.path.endswith('/payments'):
                body = json.loads(request.content); posts.append(body)
                return httpx.Response(200, json={'id': 'fixture-payment', 'status': 'PENDING',
                    'value': body['value'], 'dueDate': body['dueDate']})
            raise AssertionError(str(request.url))
        gateway = AsaasGateway(config=_config(), transport=httpx.MockTransport(handler))
        try:
            result = gateway.dispatch_frozen_charge(replace(_command(), due_at=datetime(2026, 3, 1, 1, tzinfo=timezone.utc)))
            self.assertEqual(posts[0]['dueDate'], '2026-02-28')
            self.assertEqual(posts[0]['interest'], {'value': 0})
            self.assertEqual(posts[0]['fine'], {'value': 0})
            self.assertEqual(result.observed_due_date, '2026-02-28')
        finally:
            gateway._client.close()

    def test_recovery_only_reads_and_rejects_ambiguous_or_wrong_references(self):
        payment = {'id': 'pay-recovered', 'status': 'PENDING', 'value': '199.90', 'externalReference': 'idem-1'}
        for listing, outcome in [({'data': []}, 'missing'), ({'data': [payment]}, 'found'),
            ({'data': [payment, payment]}, 'reject'), ({'data': [], 'hasMore': True}, 'reject'),
            ({}, 'reject'), ({'data': None}, 'reject'), ({'data': [payment], 'hasMore': True}, 'reject'),
            ({'data': [{**payment, 'externalReference': 'another-obligation'}]}, 'reject')]:
            with self.subTest(outcome=outcome, listing=listing):
                calls = []
                def handler(request):
                    calls.append(request.method)
                    self.assertEqual(request.method, 'GET')
                    self.assertEqual(request.url.params['externalReference'], 'idem-1')
                    return httpx.Response(200, json=listing)
                gateway = AsaasGateway(config=_config(), transport=httpx.MockTransport(handler))
                try:
                    if outcome == 'reject':
                        with self.assertRaises(PaymentGatewayError):
                            gateway.recover_charge(_command())
                    else:
                        result = gateway.recover_charge(_command())
                        if outcome == 'missing':
                            self.assertIsNone(result)
                        else:
                            self.assertEqual(result.gateway_charge_id, 'pay-recovered')
                            self.assertEqual(result.observed_amount, Decimal('199.90'))
                    self.assertEqual(calls, ['GET'])
                finally:
                    gateway._client.close()

    def test_invoice_url_is_preserved_on_creation_and_external_reference_recovery(self):
        for recovery in [False, True]:
            with self.subTest(recovery=recovery):
                calls = []
                payment = {'id': 'pay-invoice', 'status': 'PENDING', 'value': '199.90',
                           'invoiceUrl': 'https://sandbox.asaas.com/i/invoice-test'}
                def handler(request):
                    calls.append((request.method, request.url.path))
                    if request.method == 'GET' and request.url.path.endswith('/payments'):
                        return httpx.Response(200, json={'data': [payment] if recovery else []})
                    if request.url.path.endswith('/customers'):
                        return httpx.Response(200, json={'data': [{'id': 'cus-existing'}]})
                    if request.method == 'POST' and request.url.path.endswith('/payments'):
                        return httpx.Response(200, json=payment)
                    raise AssertionError(str(request.url))
                gateway = AsaasGateway(config=_config(), transport=httpx.MockTransport(handler))
                result = gateway.create_charge(_command())
                replay = gateway.create_charge(_command())
                self.assertEqual(result, replay)
                self.assertEqual(result.invoice_url, payment['invoiceUrl'])
                self.assertEqual(result.observed_amount, Decimal('199.90'))
                self.assertEqual(sum(method == 'POST' for method, path in calls), 0 if recovery else 1)
