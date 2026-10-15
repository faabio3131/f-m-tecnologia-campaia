from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from threading import Event
import unittest
from unittest.mock import patch
import httpx

from starlette.testclient import TestClient
from api.main import create_app
from api.billing_dispatch import obligation_key
from campaia_core.billing_settlement import dispatch_frozen_charge
from campaia_core.asaas_gateway import AsaasGateway, AsaasConfig
from campaia_core.payment_gateway import GatewayMode
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, with_step_up, unique_idem


class BillingDispatchTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()

    def emit(self, client=None, headers=None, **body):
        return (client or self.client).post('/billing/charges',
            headers=headers or {**with_step_up(OWNER), **unique_idem()},
            json={'competence': 'untrusted', **body})

    def worker(self):
        client = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(client.app.state.campaia.db._conn.close)
        return client

    def test_frozen_obligation_is_visible_to_another_worker_before_external_call(self):
        other = self.worker()
        def observe(charge, gateway):
            self.assertFalse(self.state.db.in_transaction)
            record = other.app.state.campaia.idempotency.get('demo-tenant', obligation_key(charge.billing_id))
            self.assertEqual(record.result, charge)
            self.assertIsNotNone(other.app.state.campaia.idempotency.get('demo-tenant', 'billing-dispatch:' + charge.billing_id))
            return dispatch_frozen_charge(charge, gateway)
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=observe) as dispatched:
            first = self.emit()
            again = self.emit(other)
        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(again.json(), first.json())
        self.assertEqual(dispatched.call_count, 1)

    def test_crash_after_external_success_recovers_original_terms_after_restart(self):
        observed = []
        def crash(charge, gateway):
            observed.append(dispatch_frozen_charge(charge, gateway))
            raise RuntimeError('response lost after external side effect')
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=crash) as dispatched:
            self.assertEqual(self.emit().status_code, 503)
            # Simulate contract drift in the failure window: the financial obligation
            # must retain its original terms, not silently use recalculated amounts.
            old = self.state.subscriptions['demo-tenant']
            self.state.subscriptions['demo-tenant'] = replace(old, plan=replace(old.plan, monthly_price=Decimal('99.00')))
            other = self.worker()
            recovered = self.emit(other)
        self.assertEqual(recovered.status_code, 202, recovered.text)
        self.assertEqual(recovered.json()['gateway_charge_id'], observed[0].gateway_charge_id)
        self.assertEqual(Decimal(recovered.json()['amount']), Decimal('1.00'))
        self.assertEqual(dispatched.call_count, 1)
        stored = other.app.state.campaia.charges[observed[0].gateway_charge_id]
        self.assertEqual(stored.commercial_plan.monthly_price, Decimal('1.00'))

    def test_unknown_absence_never_authorizes_another_post_even_with_new_http_key(self):
        headers = {**with_step_up(OWNER), **unique_idem()}
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=RuntimeError('lost before result')) as dispatched:
            self.assertEqual(self.emit(headers=headers).status_code, 503)
            self.assertEqual(self.emit(headers=headers).status_code, 503)
            self.assertEqual(self.emit(self.worker()).status_code, 503)
        self.assertEqual(dispatched.call_count, 1)
        self.assertEqual(len(self.state.charges), 0)
        self.assertIsNone(self.state.subscriptions['demo-tenant'].paid_cycle_schedule.anchor_at)

    def test_failure_saving_history_retains_provider_result_and_retries_without_dispatch(self):
        original = self.state.audit.append
        def fail(**event):
            if event['action'] == 'BILLING_CHARGE_CREATE':
                raise RuntimeError('injected finalization failure')
            return original(**event)
        with patch('api.routes_billing.dispatch_frozen_charge', wraps=dispatch_frozen_charge) as dispatched:
            with patch.object(self.state.audit, 'append', side_effect=fail):
                with self.assertRaises(RuntimeError):
                    self.emit()
            self.assertEqual(len(self.state.charges), 0)
            recovered = self.emit(self.worker())
        self.assertEqual(recovered.status_code, 202, recovered.text)
        self.assertEqual(dispatched.call_count, 1)

    def test_parallel_workers_cannot_dispatch_the_same_obligation_twice(self):
        other = self.worker(); entered = Event(); release = Event()
        def slow(charge, gateway):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test synchronization timeout')
            return dispatch_frozen_charge(charge, gateway)
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=slow) as dispatched:
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(self.emit)
                try:
                    self.assertTrue(entered.wait(5))
                    second = self.emit(other)
                    self.assertEqual(second.status_code, 503, second.text)
                finally:
                    release.set()
                completed = first.result(timeout=5)
            recovered = self.emit(other)
        self.assertEqual(completed.status_code, 202, completed.text)
        self.assertEqual(recovered.json(), completed.json())
        self.assertEqual(dispatched.call_count, 1)

    def test_same_http_key_cannot_be_rebound_to_another_request(self):
        headers = {**with_step_up(OWNER), **unique_idem()}
        self.assertEqual(self.emit(headers=headers).status_code, 202)
        changed = self.emit(headers=headers, competence='different-body')
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(changed.json()['code'], 'IDEMPOTENCY_CONFLICT')

    def test_completed_response_from_previous_version_never_prepares_or_dispatches_again(self):
        headers = {**with_step_up(OWNER), **unique_idem()}
        key = next(value for name, value in headers.items() if name.lower() == 'idempotency-key')
        prior = {'billing_id': 'completed-before-upgrade', 'gateway_charge_id': 'prior-payment'}
        self.state.idempotency.execute('demo-tenant', 'http:billing_charge_create:' + key, lambda: prior)
        with patch('api.routes_billing.compute_cycle_charge', side_effect=AssertionError('No new preparation')):
            response = self.emit(headers=headers)
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json(), prior)

    def test_cancel_after_freeze_before_dispatch_blocks_new_external_effect(self):
        headers = {**with_step_up(OWNER), **unique_idem()}
        execute = self.state.idempotency.execute
        def crash(tenant, key, operation):
            if key.startswith('billing-dispatch:'):
                raise RuntimeError('process stopped before claiming dispatch')
            return execute(tenant, key, operation)
        with patch('api.routes_billing.dispatch_frozen_charge', wraps=dispatch_frozen_charge) as dispatched:
            with patch.object(self.state.idempotency, 'execute', side_effect=crash):
                with self.assertRaises(RuntimeError):
                    self.emit(headers=headers)
            canceled = self.client.post('/billing/subscription/cancel',
                headers={**with_step_up(OWNER), **unique_idem()}, json={'immediate': True})
            self.assertEqual(canceled.status_code, 200, canceled.text)
            resumed = self.emit(headers=headers)
        self.assertEqual(resumed.status_code, 409, resumed.text)
        self.assertEqual(dispatched.call_count, 0)

    def test_asaas_timeout_recovers_by_read_only_reference_without_db_lock_or_second_post(self):
        # MockTransport only. No real key, host connection or cloud resource is used.
        old = self.state.subscriptions['demo-tenant']
        self.state.subscriptions['demo-tenant'] = replace(old, plan=replace(old.plan, monthly_price=Decimal('12.50')))
        other = self.worker(); payment = {}; posts = []
        def handler(request):
            self.assertFalse(self.state.db.in_transaction)
            if request.method == 'GET' and request.url.path.endswith('/payments'):
                return httpx.Response(200, json={'data': [payment] if payment else []})
            if request.method == 'GET' and request.url.path.endswith('/customers'):
                return httpx.Response(200, json={'data': [{'id': 'fixture-customer'}]})
            if request.method == 'POST' and request.url.path.endswith('/payments'):
                import json
                body = json.loads(request.content)
                identity = body['externalReference'].removeprefix('campaia:subscription:')
                self.assertIsNotNone(other.app.state.campaia.idempotency.get('demo-tenant', obligation_key(identity)))
                posts.append(body)
                payment.update(id='fixture-external-payment', status='PENDING', value='12.50',
                               externalReference=body['externalReference'])
                raise httpx.ReadTimeout('simulated lost response', request=request)
            raise AssertionError('Unexpected transport request')
        class NoLocalTransaction:
            def execute(self, *args):
                raise AssertionError('Commercial HTTP must not run inside adapter DB idempotency')
        gateway = AsaasGateway(config=AsaasConfig('fixture-key', GatewayMode.SANDBOX, 'fixture-account', 3),
                               transport=httpx.MockTransport(handler), idempotency=NoLocalTransaction())
        self.addCleanup(gateway._client.close)
        self.state.billing_gateway = gateway
        self.assertEqual(self.emit().status_code, 503)
        recovered = self.emit()
        self.assertEqual(recovered.status_code, 202, recovered.text)
        self.assertEqual(recovered.json()['gateway_charge_id'], 'fixture-external-payment')
        self.assertEqual(len(posts), 1)
