from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from threading import Event
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from api.billing_refund_worker import process_guarantee_refunds
from api.billing_refund_policy import refund_intent_key, processing_key
from campaia_core.billing_settlement import charge_command
from campaia_core.payment_gateway import GatewayChargeStatus
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, with_step_up, unique_idem


class GuaranteeRefundWorkerTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.gateway = self.charge()
        self.payment(self.gateway)
        self.state.billing_gateway.confirm(self.gateway)
        sub = self.state.subscriptions['demo-tenant']
        cycle = sub.paid_cycle_schedule.obligation_id('demo-tenant', 0)
        self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=cycle,
            operation_id='delivered', action='strategy', at=datetime.now(timezone.utc))
        self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id='delivered',
            kind='SETTLE', reference='delivery-fixture', at=datetime.now(timezone.utc))
        quote = self.client.get('/billing/guarantee', headers=OWNER).json()
        requested = self.client.post('/billing/guarantee', headers={**with_step_up(OWNER), **unique_idem()},
            json={'fingerprint': quote['fingerprint'], 'accept': True})
        self.assertEqual(requested.status_code, 200, requested.text)
        self.case = requested.json()
        self.bill = self.state.charges[self.gateway]
        self.intent = refund_intent_key(self.case['request_id'], self.bill.billing_id)

    def run_worker(self, state=None, execute=True, tenant='demo-tenant'):
        return process_guarantee_refunds(state or self.state, tenant, execute=execute)

    def restarted(self):
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        return other

    def test_dry_run_has_no_gateway_calls_fence_or_processing_mutation(self):
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=AssertionError('No GET')):
            with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No POST')):
                report = self.run_worker(execute=False)
        self.assertEqual(report['state'], 'DRY_RUN')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))
        self.assertIsNone(self.state.idempotency.get('demo-tenant', processing_key(self.case['request_id'])))
        self.assertEqual(self.client.get('/billing/guarantee', headers=OWNER).json()['state'], 'REQUESTED')

    def test_pending_then_done_are_observed_without_resolving_contract_or_granting_credits(self):
        original = self.state.billing_gateway.refund_charge
        def refund(*args):
            self.assertFalse(self.state.db.in_transaction)
            intent = self.state.idempotency.get('demo-tenant', self.intent)
            self.assertIsNotNone(intent)
            self.assertEqual(intent.result['amount'], Decimal('1.00'))
            return original(*args)
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=refund) as send:
            report = self.run_worker()
            self.assertEqual(report['items'][0]['state'], 'PROVIDER_PENDING', report)
            self.assertEqual(self.run_worker()['items'][0]['state'], 'PROVIDER_PENDING')
        self.assertEqual(send.call_count, 1)
        observed = self.client.get('/billing/guarantee', headers=OWNER).json()
        self.assertEqual(observed['state'], 'PROCESSING')
        self.assertEqual(observed['refund_progress'][0]['completed_amount'], '0.00')
        other = self.restarted()
        other.app.state.campaia.billing_gateway.complete_refund(self.gateway, tenant_id='demo-tenant')
        with patch.object(other.app.state.campaia.billing_gateway, 'refund_charge', side_effect=AssertionError('No second POST')):
            done = self.run_worker(other.app.state.campaia)
        self.assertEqual(done['items'][0]['state'], 'REFUND_DONE_ADJUSTMENT_PENDING', done)
        self.assertEqual(self.state.charges[self.gateway].gateway_refund_state, 'FULL_DONE')
        self.assertEqual(self.state.charges[self.gateway].amount, Decimal('1.00'))
        self.assertEqual(self.state.charges[self.gateway].status.value, 'SETTLED')
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 5)
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'CANCELED')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-guarantee-resolution'))
        self.assertEqual(self.client.post('/billing/subscription/reactivate',
            headers={**with_step_up(OWNER), **unique_idem()}).status_code, 409)

    def test_lost_provider_response_recovers_read_only_after_restart(self):
        original = self.state.billing_gateway.refund_charge
        def lost(*args):
            original(*args)
            raise TimeoutError('lost refund acknowledgement')
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=lost) as send:
            report = self.run_worker()
        self.assertEqual(report['items'][0]['state'], 'DISPATCH_UNCERTAIN')
        self.assertEqual(send.call_count, 1)
        other = self.restarted()
        with patch.object(other.app.state.campaia.billing_gateway, 'refund_charge', side_effect=AssertionError('No second POST')):
            recovered = self.run_worker(other.app.state.campaia)
        self.assertEqual(recovered['items'][0]['state'], 'PROVIDER_PENDING', recovered)

    def test_uncertainty_before_post_never_authorizes_another_attempt_even_with_no_refund_found(self):
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=TimeoutError('unknown')) as send:
            self.assertEqual(self.run_worker()['items'][0]['state'], 'DISPATCH_UNCERTAIN')
            self.assertEqual(self.run_worker()['items'][0]['state'], 'DISPATCH_UNCERTAIN')
        self.assertEqual(send.call_count, 1)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'sim-refund:' + self.gateway))

    def test_second_worker_only_reads_while_the_owner_is_dispatching(self):
        other = self.restarted()
        other.app.state.campaia.billing_gateway.confirm(self.gateway)
        entered, complete = Event(), Event()
        original = self.state.billing_gateway.refund_charge
        def blocked(*args):
            self.assertFalse(self.state.db.in_transaction)
            entered.set()
            if not complete.wait(timeout=10):
                raise TimeoutError('coordination timeout')
            return original(*args)
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=blocked) as send:
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(self.run_worker)
                try:
                    self.assertTrue(entered.wait(timeout=5))
                    with patch.object(other.app.state.campaia.billing_gateway, 'refund_charge', side_effect=AssertionError('No concurrent POST')):
                        second = self.run_worker(other.app.state.campaia)
                    self.assertEqual(second['items'][0]['state'], 'DISPATCH_UNCERTAIN', second)
                finally:
                    complete.set()
                self.assertEqual(first.result(timeout=5)['items'][0]['state'], 'PROVIDER_PENDING')
            self.assertEqual(self.run_worker(other.app.state.campaia)['items'][0]['state'], 'PROVIDER_PENDING')
        self.assertEqual(send.call_count, 1)

    def test_disabled_dispatch_does_not_create_a_claim_and_existing_claim_can_still_be_read(self):
        self.state.billing_gateway.refund_dispatch_enabled = False
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=AssertionError('No GET')):
            self.assertEqual(self.run_worker()['state'], 'DISABLED')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))
        self.state.billing_gateway.refund_dispatch_enabled = True
        self.assertEqual(self.run_worker()['items'][0]['state'], 'PROVIDER_PENDING')
        self.state.billing_gateway.refund_dispatch_enabled = False
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No disabled POST')):
            self.assertEqual(self.run_worker()['items'][0]['state'], 'PROVIDER_PENDING')

    def test_boleto_or_unknown_method_requires_review_without_a_card_pix_refund(self):
        self.state.billing_gateway.billing_type = 'BOLETO'
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No wrong-method POST')):
            report = self.run_worker()
        self.assertEqual(report['items'][0]['state'], 'METHOD_REVIEW_REQUIRED')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))
        quote = self.client.get('/billing/guarantee', headers=OWNER).json()
        self.assertEqual(quote['refund_progress'][0]['state'], 'REVIEW_REQUIRED')

    def test_chargeback_inside_received_snapshot_blocks_refund_and_paid_access(self):
        original = self.state.billing_gateway.inspect_charge
        def disputed(*args):
            return replace(original(*args), source_status='RECEIVED', chargeback_status='REQUESTED')
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=disputed):
            with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No dispute refund')):
                report = self.run_worker()
        self.assertEqual(report['items'][0]['state'], 'REVIEW_REQUIRED')
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'REVERSAL_PENDING')
        self.assertFalse(self.usage().json()['access_active'])
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))

    def test_other_tenant_with_no_accepted_case_never_queries_the_provider(self):
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=AssertionError('No cross-tenant GET')):
            with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No cross-tenant POST')):
                report = self.run_worker(tenant='other-tenant')
        self.assertEqual(report['state'], 'UNAVAILABLE')

    def test_provider_amount_mismatch_is_reviewed_without_creating_dispatch_claim(self):
        original = self.state.billing_gateway.inspect_charge
        def mismatch(*args):
            return replace(original(*args), observed_amount=Decimal('0.50'))
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=mismatch):
            with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No divergent POST')):
                report = self.run_worker()
        self.assertEqual(report['items'][0]['state'], 'REVIEW_REQUIRED')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))

    def test_existing_pending_refund_is_not_counted_done_or_dispatched_again(self):
        original = self.state.billing_gateway.inspect_charge
        def pending(*args):
            return replace(original(*args), status=GatewayChargeStatus.PENDING, source_status='REFUND_IN_PROGRESS',
                refund_observations=(('PENDING', Decimal('1.00')),), refunds_present=True)
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=pending):
            with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No duplicate pending POST')):
                report = self.run_worker()
        self.assertEqual(report['items'][0]['state'], 'PROVIDER_PENDING')
        self.assertEqual(self.state.charges[self.gateway].gateway_refund_amount, Decimal('0.00'))
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))

    def test_already_completed_external_refund_is_observed_without_another_post(self):
        original = self.state.billing_gateway.inspect_charge
        def done(*args):
            return replace(original(*args), status=GatewayChargeStatus.FAILED, source_status='REFUNDED',
                refund_observations=(('DONE', Decimal('1.00')),), refunds_present=True)
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=done):
            with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No already-returned POST')):
                report = self.run_worker()
        self.assertEqual(report['items'][0]['state'], 'REFUND_DONE_ADJUSTMENT_PENDING')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))

    def test_claim_commit_failure_precedes_provider_effect_and_retry_can_claim_once(self):
        original = self.state.idempotency.execute
        def execute(tenant, key, operation):
            if key == self.intent:
                def fail():
                    operation()
                    raise RuntimeError('claim commit failure')
                return original(tenant, key, fail)
            return original(tenant, key, operation)
        with patch.object(self.state.idempotency, 'execute', side_effect=execute):
            with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No uncommitted POST')):
                with self.assertRaisesRegex(RuntimeError, 'claim commit failure'):
                    self.run_worker()
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))
        self.assertEqual(self.run_worker()['items'][0]['state'], 'PROVIDER_PENDING')

    def test_local_observation_failure_after_provider_effect_recovers_without_second_post(self):
        original = self.state.audit.append
        def append(**kwargs):
            result = original(**kwargs)
            if (kwargs['action'] == 'BILLING_GUARANTEE_REFUND_OBSERVED'
                    and self.state.charges[self.gateway].gateway_refund_state == 'PROCESSING'):
                raise RuntimeError('observation commit failure')
            return result
        with patch.object(self.state.audit, 'append', side_effect=append):
            with self.assertRaisesRegex(RuntimeError, 'observation commit failure'):
                self.run_worker()
        self.assertIsNotNone(self.state.idempotency.get('demo-tenant', self.intent))
        self.assertIsNone(self.state.charges[self.gateway].gateway_refund_state)
        with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No second POST')):
            self.assertEqual(self.run_worker()['items'][0]['state'], 'PROVIDER_PENDING')

    def test_unproven_or_tampered_request_never_queries_or_refunds(self):
        original = self.state.idempotency.get
        def get(tenant, key):
            stored = original(tenant, key)
            if key == 'billing-guarantee-request' and stored is not None:
                return replace(stored, result={**stored.result, 'fingerprint': '0' * 64})
            return stored
        with patch.object(self.state.idempotency, 'get', side_effect=get):
            with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=AssertionError('No unproven GET')):
                with patch.object(self.state.billing_gateway, 'refund_charge', side_effect=AssertionError('No unproven POST')):
                    report = self.run_worker()
        self.assertEqual(report['state'], 'REVIEW_REQUIRED')
        self.assertIsNone(self.state.idempotency.get('demo-tenant', self.intent))

    def test_completed_partial_is_subtracted_from_the_server_derived_dispatch_amount(self):
        original = self.state.billing_gateway.inspect_charge
        before = replace(original(self.gateway, charge_command(self.bill)),
            source_status='RECEIVED', refund_observations=(('DONE', Decimal('0.40')),), refunds_present=True)
        after = replace(before, source_status='REFUND_IN_PROGRESS', status=GatewayChargeStatus.PENDING,
            refund_observations=(('DONE', Decimal('0.40')), ('PENDING', Decimal('0.60'))))
        with patch.object(self.state.billing_gateway, 'inspect_charge', return_value=before):
            with patch.object(self.state.billing_gateway, 'refund_charge', return_value=after) as send:
                report = self.run_worker()
        self.assertEqual(report['items'][0]['state'], 'PROVIDER_PENDING', report)
        self.assertEqual(send.call_args.args[2], Decimal('0.60'))
        self.assertEqual(self.state.idempotency.get('demo-tenant', self.intent).result['amount'], Decimal('0.60'))
        self.assertEqual(self.state.charges[self.gateway].gateway_refund_amount, Decimal('0.40'))
