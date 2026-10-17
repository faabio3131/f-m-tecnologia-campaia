"""Persistent provider budget evidence never substitutes commercial credits or bank cost."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from threading import Event
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from api.db import encode, decode
from api.ai_cost_store import PersistentAICostLedger
from campaia_core.ai_gateway import (AIRequest, AITask, AIStatus, ProviderResponse,
    ProviderTimeout, CostObservation, OutputSchema, Provenance)
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, unique_idem, DEFAULT_BRIEF


class CostProvider:
    name = 'fixture-provider'
    calls = 0
    def __init__(self, callback=None, output=None, amount=Decimal('1')):
        self.callback, self.output, self.amount = callback, output or {'ok': True}, amount
        self.calls = 0
    def supports(self, task):
        return True
    def generate(self, request):
        self.calls += 1
        if self.callback:
            return self.callback(request)
        return ProviderResponse(self.output, self.amount, 1, 'fixture-model',
            cost_observation=CostObservation('SIMULATED', self.amount, model='fixture-model'))


def request(tenant='demo-tenant', ceiling=Decimal('2')):
    return AIRequest('fixture-request', tenant, AITask.GENERATE_COPY,
        {'text': 'private prompt fixture'}, 'cost-fixture', ceiling)


class AICostEvidenceTests(BillingCreditHarness, unittest.TestCase):
    def configure(self, provider=None, state=None):
        state = state or self.state
        state.ai_gateway.providers = [provider or CostProvider()]
        state.ai_gateway.schemas['cost-fixture'] = OutputSchema('cost-fixture', frozenset({'ok'}), {'ok': bool})
        return state.ai_gateway

    def peer(self):
        client = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(client.app.state.campaia.db._conn.close)
        return client

    def test_committed_attempt_is_visible_before_provider_and_known_cost_is_charged_once(self):
        other = self.peer()
        ledger = self.state.ai_gateway.ledger
        ledger.set_cap('demo-tenant', Decimal('2'))
        def observe(req):
            self.assertFalse(self.state.db.in_transaction)
            report = other.app.state.campaia.ai_gateway.ledger.report('demo-tenant')
            self.assertEqual(report['attempts'], 1)
            self.assertEqual(report['observed_attempts'], 0)
            self.assertEqual(Decimal(report['held_budget_units']), Decimal('2'))
            return ProviderResponse({'ok': True}, Decimal('1'), 1, 'fixture-model',
                cost_observation=CostObservation('SIMULATED', Decimal('1')))
        result = self.configure(CostProvider(observe)).execute(request())
        self.assertTrue(result.ok)
        self.assertTrue(result.provenance.cost_complete)
        self.assertEqual(ledger.used('demo-tenant'), Decimal('1'))
        self.assertEqual(ledger.remaining('demo-tenant'), Decimal('1'))
        report = other.app.state.campaia.ai_gateway.ledger.report('demo-tenant')
        self.assertEqual(report['observed_attempts'], 1)
        self.assertEqual(report['held_budget_units'], '0')
        self.assertEqual(report['margin_state'], 'NOT_MEASURED')
        self.assertFalse(report['ai_20_percent_validated'])
        self.assertFalse(report['direct_30_percent_validated'])

    def test_two_workers_cannot_spend_the_same_configured_cap(self):
        other = self.peer()
        self.state.ai_gateway.ledger.set_cap('demo-tenant', Decimal('2'))
        entered, finish = Event(), Event()
        def blocked(req):
            entered.set()
            if not finish.wait(5):
                raise TimeoutError('fixture coordination')
            return ProviderResponse({'ok': True}, Decimal('1'), 1, 'fixture-model')
        first_provider, second_provider = CostProvider(blocked), CostProvider()
        first = self.configure(first_provider)
        second = self.configure(second_provider, other.app.state.campaia)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(first.execute, request())
            try:
                self.assertTrue(entered.wait(5))
                denied = second.execute(request())
                self.assertEqual(denied.status, AIStatus.COST_LIMIT)
                self.assertEqual(second_provider.calls, 0)
            finally:
                finish.set()
            self.assertTrue(running.result(5).ok)
        self.assertEqual(first_provider.calls, 1)
        self.assertEqual(other.app.state.campaia.ai_gateway.ledger.used('demo-tenant'), Decimal('1'))

    def test_timeout_holds_unknown_cost_after_restart_and_prevents_another_fallback(self):
        ledger = self.state.ai_gateway.ledger
        ledger.set_cap('demo-tenant', Decimal('2'))
        def unknown(req):
            raise ProviderTimeout('unknown fixture')
        first, fallback = CostProvider(unknown), CostProvider()
        fallback.name = 'fallback-fixture'
        gateway = self.configure(first)
        gateway.providers.append(fallback)
        result = gateway.execute(request())
        self.assertEqual(result.status, AIStatus.TIMEOUT)
        self.assertFalse(result.provenance.cost_complete)
        self.assertEqual(fallback.calls, 0)
        other = self.peer()
        other_provider = CostProvider()
        self.assertEqual(self.configure(other_provider, other.app.state.campaia).execute(request()).status, AIStatus.COST_LIMIT)
        self.assertEqual(other_provider.calls, 0)
        report = other.app.state.campaia.ai_gateway.ledger.report('demo-tenant')
        self.assertEqual(Decimal(report['held_budget_units']), Decimal('2'))
        self.assertEqual(report['cost_completeness'], 'INCOMPLETE')
        self.assertFalse(report['current_prices_verified'])

    def test_uncertain_cost_reconciliation_queue_is_read_only_and_tenant_scoped(self):
        ledger = self.state.ai_gateway.ledger
        ledger.set_cap('demo-tenant', Decimal('2'))
        self.assertTrue(ledger.begin_attempt(request(), 'manual-recovery-run', 0, 'fixture-provider'))
        queue = ledger.reconciliation_queue('demo-tenant')
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]['status'], 'UNOBSERVED')
        self.assertEqual(queue[0]['reserved_budget_units'], '2')
        self.assertEqual(ledger.remaining('demo-tenant'), Decimal('0'))
        self.assertEqual(ledger.reconciliation_queue('other-tenant'), [])
        self.assertEqual(queue, self.peer().app.state.campaia.ai_gateway.ledger.reconciliation_queue('demo-tenant'))

    def test_crash_with_only_a_start_record_never_expires_the_budget_hold(self):
        ledger = self.state.ai_gateway.ledger
        ledger.set_cap('demo-tenant', Decimal('2'))
        self.assertTrue(ledger.begin_attempt(request(), 'fixture-crashed-run', 0, 'fixture-provider'))
        other = self.peer()
        self.assertEqual(other.app.state.campaia.ai_gateway.ledger.remaining('demo-tenant'), Decimal('0'))
        self.assertFalse(other.app.state.campaia.ai_gateway.ledger.begin_attempt(request(), 'fixture-crashed-run', 0, 'fixture-provider'))
        self.assertEqual(other.app.state.campaia.ai_gateway.ledger.report('demo-tenant')['observed_attempts'], 0)

    def test_failed_start_commit_stops_before_provider_and_rolls_back_the_hold(self):
        provider = CostProvider()
        gateway = self.configure(provider)
        self.state.ai_gateway.ledger.set_cap('demo-tenant', Decimal('2'))
        original = self.state.audit.append
        def fail(**event):
            original(**event)
            if event['action'] == 'AI_COST_ATTEMPT_RESERVED':
                raise RuntimeError('injected cost start commit')
        with patch.object(self.state.audit, 'append', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'injected cost start commit'):
                gateway.execute(request())
        self.assertEqual(provider.calls, 0)
        self.assertEqual(gateway.ledger.report('demo-tenant')['attempts'], 0)
        self.assertEqual(gateway.ledger.remaining('demo-tenant'), Decimal('2'))
        self.assertTrue(gateway.execute(request()).ok)

    def test_failure_recording_returned_cost_preserves_uncertainty_instead_of_assuming_zero(self):
        provider = CostProvider()
        gateway = self.configure(provider)
        gateway.ledger.set_cap('demo-tenant', Decimal('2'))
        original = self.state.audit.append
        def fail(**event):
            original(**event)
            if event['action'] == 'AI_COST_OBSERVED':
                raise RuntimeError('injected cost observation commit')
        with patch.object(self.state.audit, 'append', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'injected cost observation commit'):
                gateway.execute(request())
        self.assertEqual(provider.calls, 1)
        report = self.peer().app.state.campaia.ai_gateway.ledger.report('demo-tenant')
        self.assertEqual(report['observed_attempts'], 0)
        self.assertEqual(Decimal(report['held_budget_units']), Decimal('2'))
        self.assertEqual(gateway.execute(request()).status, AIStatus.COST_LIMIT)
        self.assertEqual(provider.calls, 1)

    def test_provider_cannot_be_called_under_an_uncommitted_caller_transaction(self):
        provider = CostProvider()
        gateway = self.configure(provider)
        with self.state.db.transaction():
            with self.assertRaisesRegex(RuntimeError, 'outside the caller transaction'):
                gateway.execute(request())
        self.assertEqual(provider.calls, 0)

    def test_known_invalid_schema_still_costs_internal_units_without_becoming_a_valid_delivery(self):
        provider = CostProvider(output={'wrong': 'private response fixture'})
        result = self.configure(provider).execute(request())
        self.assertEqual(result.status, AIStatus.SCHEMA_INVALID)
        self.assertEqual(self.state.ai_gateway.ledger.used('demo-tenant'), Decimal('1'))
        self.assertEqual(self.state.ai_gateway.ledger.report('demo-tenant')['held_budget_units'], '0')
        rows = self.state.ai_gateway.ledger._rows('demo-tenant')
        self.assertNotIn('private prompt fixture', str(rows))
        self.assertNotIn('private response fixture', str(rows))
        self.assertFalse(any('input' in row or 'output' in row or 'error_body' in row for row in rows))

    def test_outcome_replay_cannot_double_charge_or_replace_immutable_cost_evidence(self):
        ledger = self.state.ai_gateway.ledger
        req = request()
        self.assertTrue(ledger.begin_attempt(req, 'fixture-replay-run', 0, 'fixture-provider'))
        observed = CostObservation('SIMULATED', Decimal('1'))
        ledger.finish_attempt(req, 'fixture-replay-run', 0, observed, 'OK')
        ledger.finish_attempt(req, 'fixture-replay-run', 0, observed, 'OK')
        self.assertEqual(ledger.used('demo-tenant'), Decimal('1'))
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            ledger.finish_attempt(req, 'fixture-replay-run', 0, CostObservation('SIMULATED', Decimal('2')), 'OK')
        self.assertEqual(ledger.used('demo-tenant'), Decimal('1'))

    def test_namespace_tenant_and_cap_history_do_not_mix_simulation_with_another_runtime(self):
        self.state.ai_gateway.ledger.set_cap('demo-tenant', Decimal('2'))
        self.assertTrue(self.configure().execute(request()).ok)
        other_namespace = PersistentAICostLedger(self.state, namespace='other-runtime:PROVIDER')
        self.assertEqual(other_namespace.used('demo-tenant'), Decimal('0'))
        self.assertIsNone(other_namespace.cap('demo-tenant'))
        self.assertEqual(self.state.ai_gateway.ledger.used('different-tenant'), Decimal('0'))
        self.assertIsNone(self.state.ai_gateway.ledger.cap('different-tenant'))
        other = self.peer().app.state.campaia.ai_gateway.ledger
        self.assertEqual(other.cap('demo-tenant'), Decimal('2'))
        with self.assertRaises(ValueError):
            other.set_cap('demo-tenant', Decimal('NaN'))
        self.assertEqual(other.cap('demo-tenant'), Decimal('2'))

    def test_ai_codec_keeps_legacy_reading_and_rejects_injected_metadata(self):
        value = ProviderResponse({'ok': True}, Decimal('1'), 1, 'fixture-model',
            cost_observation=CostObservation('SIMULATED', Decimal('1')))
        encoded = encode(value)
        self.assertIn('ai_cost_v1', encoded)
        self.assertNotIn('cost_observation', encoded['fields'])
        self.assertEqual(decode(encoded), value)
        legacy = {k: v for k, v in encoded.items() if k != 'ai_cost_v1'}
        self.assertIsNone(decode(legacy).cost_observation)
        encoded['ai_cost_v1']['unexpected'] = True
        with self.assertRaises(ValueError):
            decode(encoded)
        previous = Provenance(None, None, 'v1', Decimal('0'), 0, ())
        self.assertFalse(decode(encode(previous)).cost_complete)


class LegacyCostExecutionTests(BillingCreditHarness, unittest.TestCase):
    def campaign(self):
        result = self.client.post('/briefs', headers={**OWNER, **unique_idem()}, json=DEFAULT_BRIEF)
        self.assertEqual(result.status_code, 202, result.text)
        return result.json()['id']

    def test_legacy_provider_runs_outside_database_and_same_key_never_repeats_it(self):
        campaign = self.campaign()
        endpoint = '/campaigns/' + campaign + '/plan/regenerate'
        original = self.state.ai_provider.generate
        def generate(req):
            self.assertFalse(self.state.db.in_transaction)
            self.assertEqual(self.peer_ledger.report('demo-tenant')['attempts'], 1)
            return original(req)
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        self.peer_ledger = other.app.state.campaia.ai_gateway.ledger
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.state.ai_provider, 'generate', side_effect=generate) as called:
            first = self.client.post(endpoint, headers=headers)
            replay = other.post(endpoint, headers=headers)
        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(called.call_count, 1)
        self.assertEqual(self.peer_ledger.used('demo-tenant'), Decimal('1'))
        self.assertEqual(other.post(endpoint, headers={**OTHER_OWNER, **unique_idem()}).status_code, 404)
        second_campaign = self.campaign()
        conflict = self.client.post('/campaigns/' + second_campaign + '/plan/regenerate', headers=headers)
        self.assertEqual(conflict.status_code, 409)

    def test_legacy_timeout_restart_keeps_the_execution_claim_and_unknown_cost_hold(self):
        campaign = self.campaign()
        endpoint = '/campaigns/' + campaign + '/plan/regenerate'
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.state.ai_provider, 'generate', side_effect=ProviderTimeout('uncertain')) as called:
            first = self.client.post(endpoint, headers=headers)
        self.assertEqual(first.status_code, 503, first.text)
        self.assertEqual(called.call_count, 1)
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        with patch.object(other.app.state.campaia.ai_provider, 'generate', side_effect=AssertionError('No repeat')):
            replay = other.post(endpoint, headers=headers)
        self.assertEqual(replay.status_code, 503, replay.text)
        report = other.app.state.campaia.ai_gateway.ledger.report('demo-tenant')
        self.assertEqual(report['cost_completeness'], 'INCOMPLETE')
        self.assertEqual(Decimal(report['held_budget_units']), Decimal('10'))

    def test_known_failure_preserves_provider_cost_but_releases_commercial_credits(self):
        self.setup_subscription(trial=True)
        campaign = self.campaign()
        quote = self.client.get('/campaigns/' + campaign + '/plan/quote', headers=OWNER).json()
        self.state.ai_provider.output = {'invalid': 'no usable strategy'}
        result = self.client.post('/campaigns/' + campaign + '/plan/regenerate', headers={**OWNER, **unique_idem()},
            json={'credit_confirmation': {k: quote[k] for k in ('cycle_id', 'policy_version', 'credits', 'extra_amount')}})
        self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(self.state.ai_gateway.ledger.used('demo-tenant'), Decimal('1'))
        balance = self.usage().json()['balance']
        self.assertEqual(balance['consumed_credits'], 0)
        self.assertEqual(balance['reserved_credits'], 0)
