"""Subscription/payment is the sole authority for granting commercial credits."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from api.db import encode, decode
from campaia_core.billing_cycles import anniversary
from campaia_core.credit_ledger import CreditLimitExceeded
from tests_api.test_helpers import OWNER, OTHER_OWNER, FINANCE, APPROVER, VIEWER, with_step_up, unique_idem


class BillingCreditIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.path = root / 'runtime.db'
        catalog = json.loads((Path(__file__).parents[1] / 'config/plans.example.json').read_text())
        for plan in catalog:
            plan['included_credits'] = 10
            plan['credit_policy'] = {'version': 'test-commercial-v1',
                'action_weights': {'strategy': 5, 'copy': 3, 'audience': 2},
                'trial_credits': 30, 'trial_max_users': 1, 'trial_max_active_campaigns': 1}
        config = root / 'catalog.json'
        config.write_text(json.dumps(catalog))
        self.environ = patch.dict(os.environ, {'CAMPAIA_PLAN_CATALOG_PATH': str(config),
                                              'ASAAS_WEBHOOK_TOKEN': 'test-webhook-secret'})
        self.environ.start()
        self.client = TestClient(create_app(env='test', db_path=str(self.path)))
        self.state = self.client.app.state.campaia

    def tearDown(self):
        self.state.db._conn.close()
        self.environ.stop()
        self.tmp.cleanup()

    def setup_subscription(self, trial=False):
        fingerprint = self.client.get('/billing/plans', headers=OWNER).json()['items'][0]['fingerprint']
        response = self.client.put('/billing/subscription',
            headers={**with_step_up(OWNER), **unique_idem()},
            json={'plan_id': 'exemplo-essencial', 'customer_document': '11144477735',
                  'start_trial': trial, 'initial_only': True, 'expected_plan_fingerprint': fingerprint})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def charge(self):
        response = self.client.post('/billing/charges',
            headers={**with_step_up(OWNER), **unique_idem()}, json={'competence': 'untrusted-browser-period'})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()['gateway_charge_id']

    def payment(self, gateway_id, event='event-first'):
        return self.client.post('/webhooks/asaas', headers={'asaas-access-token': 'test-webhook-secret'},
            json={'id': event, 'event': 'PAYMENT_RECEIVED', 'payment': {'id': gateway_id, 'status': 'RECEIVED'}})

    def usage(self, headers=OWNER):
        return self.client.get('/billing/usage', headers=headers)

    def consent(self, cap='5.00', headers=None, **changes):
        usage = self.usage().json()
        body = {'cap': cap, 'cycle_id': usage['cycle']['id'],
                'policy_version': usage['cycle']['policy_version'],
                'extra_credit_price': usage['balance']['extra_credit_price'], **changes}
        return self.client.post('/billing/usage/consent',
             headers=headers or {**with_step_up(OWNER), **unique_idem()}, json=body)

    def test_trial_granted_once_no_extras_restart_and_cross_tenant(self):
        sub = self.setup_subscription(trial=True)
        self.assertEqual(sub['entitlements']['max_users'], 1)
        usage = self.usage().json()
        self.assertEqual(usage['balance']['included_credits'], 30)
        self.assertTrue(usage['cycle']['trial'])
        self.assertEqual(self.consent().status_code, 409)
        fresh = TestClient(create_app(env='test', db_path=str(self.path)))
        try:
            self.assertEqual(fresh.get('/billing/usage', headers=OWNER).json(), usage)
            self.assertEqual(self.usage(OTHER_OWNER).status_code, 404)
        finally:
            fresh.app.state.campaia.db._conn.close()
        repeat = self.client.put('/billing/subscription',
            headers={**with_step_up(OWNER), **unique_idem()},
            json={'plan_id': 'exemplo-essencial', 'customer_document': '11144477735', 'start_trial': True})
        self.assertEqual(repeat.status_code, 422)
        self.assertEqual(len(self.state.credit_ledger.entries('demo-tenant')), 1)

    def test_only_payment_grants_paid_quota_and_replay_does_not_reset(self):
        self.setup_subscription(trial=True)
        gateway = self.charge()
        self.assertTrue(self.usage().json()['cycle']['trial'])
        response = self.payment(gateway)
        self.assertEqual(response.status_code, 200, response.text)
        usage = self.usage().json()
        self.assertFalse(usage['cycle']['trial'])
        self.assertEqual(usage['balance']['included_credits'], 10)
        ledger = self.state.credit_ledger
        ledger.decide('demo-tenant', 'reserve', cycle_id=usage['cycle']['id'], operation_id='op',
                      action='strategy', at=datetime.now(timezone.utc))
        self.assertEqual(self.payment(gateway).status_code, 200)
        self.assertEqual(self.payment(gateway, 'different-event-same-payment').status_code, 200)
        self.assertEqual(self.usage().json()['balance']['reserved_credits'], 5)
        self.assertEqual(sum(e.kind == 'OPEN' for e in ledger.entries('demo-tenant')), 2)
        self.assertEqual(self.client.post('/billing/charges',
            headers={**with_step_up(OWNER), **unique_idem()}, json={'competence':'any'}).status_code, 422)

    def test_consent_rbac_step_up_tamper_replay_and_revoke(self):
        self.setup_subscription(); self.payment(self.charge())
        for role in (APPROVER, VIEWER):
            self.assertEqual(self.consent(headers={**with_step_up(role), **unique_idem()}).status_code, 403)
        self.state.invalidate_step_up_for_session("bearer:demo-owner-token")
        self.assertEqual(self.consent(headers={**OWNER, **unique_idem()}).status_code, 403)
        self.assertEqual(self.consent(policy_version='tampered').status_code, 409)
        headers = {**with_step_up(FINANCE), **unique_idem()}
        accepted = self.consent(headers=headers)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()['balance']['extra_cap'], '5.00')
        self.assertEqual(self.consent(headers=headers).json(), accepted.json())
        self.assertEqual(self.consent(cap='0.00').status_code, 200)
        self.assertEqual(self.state.subscriptions['demo-tenant'].extra_credit_consent.cap, 0)

    def test_webhook_failure_rolls_back_dedupe_activation_and_grant(self):
        self.setup_subscription(); gateway = self.charge()
        with patch('api.routes_billing.grant_current_cycle', side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError):
                self.payment(gateway)
        self.assertFalse(self.state.asaas_webhook.already_seen('event-first'))
        self.assertIsNone(self.state.subscriptions['demo-tenant'].paid_cycle_schedule.anchor_at)
        self.assertEqual(self.payment(gateway).status_code, 200)
        self.assertEqual(self.usage().json()['balance']['included_credits'], 10)

    def test_unknown_charge_not_seen_and_same_event_can_succeed_after_creation(self):
        self.setup_subscription(); gateway = self.charge()
        charge = self.state.charges[gateway]
        del self.state.charges[gateway]
        self.assertEqual(self.payment(gateway).status_code, 503)
        self.assertFalse(self.state.asaas_webhook.already_seen('event-first'))
        self.state.charges[gateway] = charge
        self.assertEqual(self.payment(gateway).status_code, 200)

    def test_read_is_not_write_and_no_provider_cost_or_fabricated_zero(self):
        self.setup_subscription()
        before = len(self.state.credit_ledger.entries('demo-tenant'))
        payload = self.usage().json()
        self.assertEqual(payload['availability'], 'UNAVAILABLE')
        self.assertIsNone(payload['balance'])
        self.assertEqual(len(self.state.credit_ledger.entries('demo-tenant')), before)
        self.assertNotIn('cost_units', json.dumps(payload))

    def test_late_overdue_cannot_revoke_a_confirmed_period(self):
        self.setup_subscription(); gateway = self.charge(); self.payment(gateway)
        response = self.client.post('/webhooks/asaas', headers={'asaas-access-token': 'test-webhook-secret'},
            json={'id': 'late-overdue', 'event': 'PAYMENT_OVERDUE',
                  'payment': {'id': gateway, 'status': 'OVERDUE'}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['processed'])
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'ACTIVE')
        self.assertEqual(self.usage().json()['balance']['included_credits'], 10)

    def test_codec_legacy_constructors_keep_shape_new_terms_round_trip(self):
        self.setup_subscription(trial=True)
        sub = self.state.subscriptions['demo-tenant']
        encoded = encode(sub)
        self.assertNotIn('paid_cycle_schedule', encoded['fields'])
        self.assertEqual(decode(encoded), sub)
        encoded['commercial_v1']['unsupported'] = 1
        with self.assertRaises(ValueError):
            decode(encoded)

    def test_renewal_uses_closed_usage_and_keeps_anchor_and_consent(self):
        self.setup_subscription(); self.payment(self.charge())
        self.assertEqual(self.consent().status_code, 200)
        sub = self.state.subscriptions['demo-tenant']
        schedule = sub.paid_cycle_schedule
        usage = self.usage().json()
        now = datetime.now(timezone.utc)
        for i in range(3):
            self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=usage['cycle']['id'],
                                          operation_id=str(i), action='strategy', at=now)
            self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id=str(i),
                                          kind='SETTLE', reference='delivery'+str(i), at=now)
        end = anniversary(schedule.anchor_at, 1)
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return end
        with patch('api.routes_billing.datetime', Clock), patch('api.deps.datetime', Clock):
            gateway = self.charge()
            charge = self.state.charges[gateway]
            self.assertEqual(charge.competence, 'cycle:1')
            self.assertEqual(charge.amount, sub.plan.monthly_price + Decimal('5.00'))
            self.assertEqual(len(charge.line_items), 2)
            self.assertEqual(self.payment(gateway, 'renewal').status_code, 200)
        updated = self.state.subscriptions['demo-tenant']
        self.assertEqual(updated.paid_cycle_schedule.anchor_at, schedule.anchor_at)
        new_id = updated.paid_cycle_schedule.obligation_id('demo-tenant', 1)
        self.assertEqual(self.state.credit_ledger.balance('demo-tenant', new_id).extra_cap, Decimal('5.00'))
        self.assertEqual(self.state.credit_ledger.balance('demo-tenant', new_id).consumed_credits, 0)
