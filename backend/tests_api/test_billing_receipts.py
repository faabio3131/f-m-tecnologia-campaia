from decimal import Decimal
import unittest
from unittest.mock import patch

from api.db import encode
from campaia_core.subscription import ChargeStatus
from campaia_core.states import CampaignState
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, FINANCE, with_step_up, unique_idem, DEFAULT_BRIEF

MISSING = object()


class BillingReceiptTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription(trial=True)
        self.gateway = self.charge()
        self.counter = 0

    def event(self, amount=MISSING, *, kind='PAYMENT_RECEIVED', status='RECEIVED', event_id=None, extra=None, token='test-webhook-secret'):
        self.counter += 1
        payment = {'id': self.gateway, 'status': status, **(extra or {})}
        if amount is not MISSING:
            payment['value'] = amount
        return self.client.post('/webhooks/asaas', headers={'asaas-access-token': token},
            json={'id': event_id or f'receipt-{self.counter}', 'event': kind, 'payment': payment})

    def reconcile(self, headers=None, body=None):
        return self.client.post(f'/billing/charges/{self.gateway}/reconcile',
            headers=headers or {**with_step_up(OWNER), **unique_idem()}, json=body)

    def test_gross_amount_must_match_and_net_fees_cannot_reduce_the_contract_amount(self):
        wrong = self.event('0.50', extra={'netValue': '0.45', 'creditCard': {'creditCardToken': 'NEVER-PERSIST-CARD'}})
        self.assertEqual(wrong.status_code, 200, wrong.text)
        self.assertFalse(wrong.json()['reconciled'])
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'TRIAL')
        self.assertEqual(self.usage().json()['balance']['included_credits'], 30)
        charge = self.state.charges[self.gateway]
        self.assertEqual(charge.status, ChargeStatus.OPEN)
        self.assertEqual(charge.payment_reconciliation_state, 'AMOUNT_MISMATCH')
        observation = self.state.idempotency.get('demo-tenant', 'billing-receipt:receipt-1').result
        self.assertEqual(observation['observed_amount'], Decimal('0.50'))
        self.assertNotIn('NEVER-PERSIST-CARD', str(encode(observation)))
        correct = self.event('1.00', extra={'netValue': '0.95'})
        self.assertTrue(correct.json()['reconciled'])
        self.assertEqual(self.state.charges[self.gateway].gateway_observed_amount, Decimal('1.00'))
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'MATCHED')
        self.assertEqual(self.usage().json()['balance']['included_credits'], 10)

    def test_missing_invalid_and_zero_amounts_never_become_a_full_paid_invoice(self):
        for amount in (MISSING, None, True, 'NaN', '1.001', {'unexpected': '1.00'}):
            with self.subTest(amount=amount):
                response = self.event(amount)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertFalse(response.json()['reconciled'])
                self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'AMOUNT_MISSING')
                self.assertIsNone(self.state.charges[self.gateway].gateway_observed_amount)
        self.event(0)
        self.assertEqual(self.state.charges[self.gateway].gateway_observed_amount, Decimal('0'))
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'AMOUNT_MISMATCH')
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 1)

    def test_authentication_and_event_dedupe_precede_financial_observation(self):
        denied = self.event('1.00', token='wrong', event_id='same-receipt')
        self.assertEqual(denied.status_code, 401)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-receipt:same-receipt'))
        self.event('0.50', event_id='same-receipt')
        self.event('1.00', event_id='same-receipt')
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'TRIAL')
        self.assertEqual(self.state.charges[self.gateway].gateway_observed_amount, Decimal('0.50'))
        self.assertTrue(self.state.asaas_webhook.already_seen('same-receipt'))

    def test_editing_terms_is_not_payment_and_cannot_clear_missing_cash(self):
        self.event('1.00', kind='PAYMENT_UPDATED', status='CONFIRMED')
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'TRIAL')
        self.event('0.50')
        self.event('0.75', kind='PAYMENT_UPDATED', status='PENDING')
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'AMOUNT_MISMATCH')
        self.event('1.00', kind='PAYMENT_UPDATED', status='CONFIRMED')
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'TRIAL')
        self.event('1.00')
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'ACTIVE')

    def test_reversal_cannot_be_erased_by_late_confirmation_or_used_to_grant_a_cycle(self):
        self.event('1.00', kind='PAYMENT_REFUNDED', status='REFUNDED')
        self.event('1.00')
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'TRIAL')
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'REVERSAL_PENDING')
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 1)

    def test_current_funding_reversal_blocks_new_paid_actions_without_blocking_pause_or_erasing_quota(self):
        self.event('1.00')
        created = self.client.post('/briefs', headers={**OWNER, **unique_idem()}, json=DEFAULT_BRIEF)
        campaign = created.json()['id']
        self.state.campaigns.get('demo-tenant', campaign).campaign.state = CampaignState.ACTIVE
        self.event('1.00', kind='PAYMENT_REFUNDED', status='REFUNDED')
        self.assertFalse(self.usage().json()['access_active'])
        self.assertEqual(self.usage().json()['balance']['included_credits'], 10)
        self.assertFalse(self.client.get('/billing/subscription', headers=OWNER).json()['entitlement_access_active'])
        self.assertEqual(self.client.get(f'/campaigns/{campaign}/plan/quote', headers=OWNER).status_code, 409)
        paused = self.client.post(f'/campaigns/{campaign}/pause', headers={**OWNER, **unique_idem()})
        self.assertEqual(paused.status_code, 202, paused.text)
        self.event('1.00')
        self.assertFalse(self.usage().json()['access_active'])
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 2)

    def test_provider_lookup_is_read_only_outside_transaction_and_replay_never_queries_or_grants_twice(self):
        self.event()
        self.state.billing_gateway.confirm(self.gateway)
        original = self.state.billing_gateway.inspect_charge
        def inspect(*args):
            self.assertFalse(self.state.db.in_transaction)
            return original(*args)
        headers = {**with_step_up(OWNER), **unique_idem()}
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=inspect) as lookup:
            with patch.object(self.state.billing_gateway, 'create_charge', side_effect=AssertionError('No create')):
                result = self.reconcile(headers)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertTrue(result.json()['reconciled'])
                self.assertEqual(self.reconcile(headers).json(), result.json())
        self.assertEqual(lookup.call_count, 1)
        self.assertEqual(self.state.charges[self.gateway].status_source, 'RECONCILIATION')
        self.assertEqual(self.usage().json()['balance']['included_credits'], 10)

    def test_lookup_cannot_accept_a_client_paid_flag_or_cross_tenant_or_stale_step_up(self):
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=AssertionError('No lookup')):
            self.assertEqual(self.reconcile(body={'value': '1.00', 'paid': True}).status_code, 422)
            self.assertEqual(self.reconcile({**with_step_up(OTHER_OWNER), **unique_idem()}).status_code, 404)
            self.state.invalidate_step_up_for_session('bearer:demo-owner-token')
            self.assertEqual(self.reconcile({**OWNER, **unique_idem()}).status_code, 403)

    def test_lookup_failure_rolls_back_settlement_and_retry_recovers_without_another_invoice(self):
        self.event(); self.state.billing_gateway.confirm(self.gateway)
        headers = {**with_step_up(OWNER), **unique_idem()}
        with patch('api.routes_billing.grant_paid_cycle', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.reconcile(headers)
        self.assertEqual(self.state.charges[self.gateway].status, ChargeStatus.OPEN)
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'AMOUNT_MISSING')
        self.assertEqual(self.reconcile(headers).status_code, 200)
        self.assertEqual(len(self.state.charges), 1)
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 2)

    def test_stale_lookup_cannot_regress_a_newer_webhook_confirmation(self):
        original = self.state.billing_gateway.inspect_charge
        def inspect(*args):
            pending = original(*args)
            self.event('1.00')
            return pending
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=inspect):
            result = self.reconcile()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['reconciliation_state'], 'STALE_OBSERVATION')
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'MATCHED')
        self.assertTrue(self.usage().json()['access_active'])

    def test_contradictory_fresh_status_holds_current_funding_without_resetting_its_cycle(self):
        self.event('1.00')
        anchor = self.state.subscriptions['demo-tenant'].paid_cycle_schedule.anchor_at
        # Simulator is still PENDING: this explicit provider read contradicts the callback.
        self.assertEqual(self.reconcile().status_code, 200)
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'STATUS_MISMATCH')
        self.assertFalse(self.usage().json()['access_active'])
        self.state.billing_gateway.confirm(self.gateway)
        self.assertEqual(self.reconcile().status_code, 200)
        self.assertEqual(self.state.charges[self.gateway].payment_reconciliation_state, 'MATCHED')
        self.assertTrue(self.usage().json()['access_active'])
        self.assertEqual(self.state.subscriptions['demo-tenant'].paid_cycle_schedule.anchor_at, anchor)
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 2)

    def test_amount_divergence_after_payment_holds_access_until_verified_without_another_grant(self):
        self.event('1.00')
        before = self.state.subscriptions['demo-tenant'].paid_cycle_schedule
        self.event('0.50')
        self.assertEqual(self.state.charges[self.gateway].status, ChargeStatus.SETTLED)
        self.assertFalse(self.usage().json()['access_active'])
        self.state.billing_gateway.confirm(self.gateway)
        self.assertTrue(self.reconcile().json()['reconciled'])
        self.assertTrue(self.usage().json()['access_active'])
        self.assertEqual(self.state.subscriptions['demo-tenant'].paid_cycle_schedule, before)
        self.assertEqual(sum(e.kind == 'OPEN' for e in self.state.credit_ledger.entries('demo-tenant')), 2)

    def test_reconciliation_key_is_bound_to_actor_and_finance_is_authorized_for_a_fresh_lookup(self):
        headers = {**with_step_up(OWNER), **unique_idem()}
        self.assertEqual(self.reconcile(headers).status_code, 200)
        finance = {**with_step_up(FINANCE), 'Idempotency-Key': headers['Idempotency-Key']}
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=AssertionError('No second lookup')):
            self.assertEqual(self.reconcile(finance).status_code, 409)
        self.assertEqual(self.reconcile({**with_step_up(FINANCE), **unique_idem()}).status_code, 200)
