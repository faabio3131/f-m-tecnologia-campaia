import json
import os
import unittest
from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch

import httpx
from campaia_core.asaas_gateway import AsaasConfig, AsaasGateway
from campaia_core.payment_gateway import (ChargeCommand, ChargeResult, GatewayChargeStatus, GatewayMode,
    PaymentGatewayError, refund_snapshot)


def command():
    return ChargeCommand(tenant_id='fixture-tenant', billing_id='fixture-bill', customer_ref='fixture-customer',
        customer_document='11144477735', amount=Decimal('1.00'), currency='BRL',
        competence='fixture-cycle', idempotency_key='campaia:subscription:fixture-bill')


def gateway(handler, enabled=True):
    return AsaasGateway(config=AsaasConfig(api_key='fixture-asaas-key', mode=GatewayMode.SANDBOX,
        account_handle='fixture-account', due_in_days=3, refund_dispatch_enabled=enabled),
        transport=httpx.MockTransport(handler))


def payment(**overrides):
    return {'id': 'pay-fixture', 'externalReference': command().idempotency_key,
            'value': '1.00', 'status': 'RECEIVED', 'billingType': 'PIX', **overrides}


class GuaranteeRefundGatewayTests(unittest.TestCase):
    def test_dispatch_is_explicitly_disabled_by_default_without_any_http(self):
        with patch.dict(os.environ, {'ASAAS_REFUND_DISPATCH_ENABLED': '', 'ASAAS_API_KEY': 'fixture-only'}):
            self.assertFalse(AsaasConfig.from_env().refund_dispatch_enabled)
        calls = []
        driver = gateway(lambda request: calls.append(request), enabled=False)
        with self.assertRaises(PaymentGatewayError):
            driver.refund_charge('pay-fixture', command(), Decimal('1.00'))
        self.assertEqual(calls, [])

    def test_pix_refund_reads_before_post_and_readback_does_not_confirm_pending_as_done(self):
        calls = []
        posted = False
        def handle(request):
            nonlocal posted
            calls.append(request.method)
            if request.method == 'POST':
                self.assertTrue(request.url.path.endswith('/payments/pay-fixture/refund'))
                body = json.loads(request.content)
                self.assertEqual(Decimal(str(body['value'])), Decimal('1.00'))
                self.assertEqual(set(body), {'value', 'description'})
                posted = True
                return httpx.Response(200, json={'id': 'pay-fixture'})
            return httpx.Response(200, json=payment(status='REFUND_IN_PROGRESS' if posted else 'RECEIVED',
                refunds=[{'status': 'PENDING', 'value': '1.00'}] if posted else None))
        result = gateway(handle).refund_charge('pay-fixture', command(), Decimal('1.00'))
        self.assertEqual(calls, ['GET', 'POST', 'GET'])
        self.assertEqual(result.observed_amount, Decimal('1.00'))
        self.assertEqual(refund_snapshot(result, command())['state'], 'PROVIDER_PENDING')
        self.assertEqual(refund_snapshot(result, command())['completed'], Decimal('0.00'))

    def test_existing_completed_partial_is_deducted_and_only_remaining_can_be_refunded(self):
        calls = []
        posted = False
        def handle(request):
            nonlocal posted
            calls.append(request.method)
            if request.method == 'POST':
                self.assertEqual(Decimal(str(json.loads(request.content)['value'])), Decimal('0.60'))
                posted = True
                return httpx.Response(200, json={'id': 'pay-fixture'})
            refunds = [{'status': 'DONE', 'value': '0.40'}]
            if posted:
                refunds.append({'status': 'PENDING', 'value': '0.60'})
            return httpx.Response(200, json=payment(refunds=refunds))
        result = gateway(handle).refund_charge('pay-fixture', command(), Decimal('0.60'))
        self.assertEqual(refund_snapshot(result, command())['completed'], Decimal('0.40'))
        self.assertEqual(refund_snapshot(result, command())['state'], 'PROVIDER_PENDING')
        self.assertEqual(calls.count('POST'), 1)

    def test_unsupported_method_pending_unknown_dispute_and_mismatch_never_post(self):
        cases = [payment(billingType='BOLETO'), payment(billingType='UNDEFINED'),
            payment(status='RECEIVED_IN_CASH'), payment(status='DUNNING_RECEIVED'),
            payment(refunds=[{'status': 'PENDING', 'value': '1.00'}]),
            payment(refunds=[{'status': 'UNKNOWN', 'value': '1.00'}]),
            payment(value='0.50'), payment(chargeback={'status': 'REQUESTED', 'reason': 'PRIVATE-REASON'}),
            payment(chargeback={'status': 'REVERSED'}), payment(chargeback={}),
            payment(externalReference='another-obligation')]
        for body in cases:
            with self.subTest(body=body):
                calls = []
                def handle(request):
                    calls.append(request.method)
                    return httpx.Response(200, json=body)
                with self.assertRaises(PaymentGatewayError):
                    gateway(handle).refund_charge('pay-fixture', command(), Decimal('1.00'))
                self.assertEqual(calls, ['GET'])

    def test_budget_rejects_more_than_remaining_and_invalid_cent_amounts(self):
        for value in (Decimal('1.01'), Decimal('1.001'), Decimal('NaN'), Decimal('0'), Decimal('-1')):
            calls = []
            def handle(request):
                calls.append(request.method)
                return httpx.Response(200, json=payment())
            with self.assertRaises(PaymentGatewayError):
                gateway(handle).refund_charge('pay-fixture', command(), value)
            self.assertNotIn('POST', calls)

    def test_completed_and_cancelled_are_separate_from_pending_and_original_value(self):
        result = ChargeResult('pay-fixture', GatewayChargeStatus.CONFIRMED, 'ASAAS', GatewayMode.SANDBOX,
            observed_amount=Decimal('1.00'), refund_observations=(('DONE', Decimal('0.40')),
                ('CANCELLED', Decimal('0.60'))), refunds_present=True, billing_type='CREDIT_CARD')
        self.assertEqual(refund_snapshot(result, command()), {'state': 'READY', 'completed': Decimal('0.40'), 'remaining': Decimal('0.60')})
        done = replace(result, refund_observations=(('DONE', Decimal('0.40')), ('DONE', Decimal('0.60'))))
        self.assertEqual(refund_snapshot(done, command())['state'], 'FULL_DONE')
        self.assertEqual(done.observed_amount, Decimal('1.00'))
        self.assertEqual(refund_snapshot(replace(done, chargeback_status='FUTURE_DISPUTE'), command())['state'], 'REVIEW_REQUIRED')

    def test_private_cli_requires_explicit_execute_and_defaults_to_dry_run(self):
        from scripts.process_guarantee_refunds import parser
        self.assertFalse(parser().parse_args(['--tenant', 'fixture']).execute)
        self.assertTrue(parser().parse_args(['--tenant', 'fixture', '--execute']).execute)
