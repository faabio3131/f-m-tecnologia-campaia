from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch

from campaia_core.payment_gateway import ChargeResult, GatewayChargeStatus, GatewayMode
from tests_api.test_anniversary_lifecycle import clock
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, with_step_up, unique_idem


class BillingCheckoutTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()

    def checkout(self, headers=OWNER):
        return self.client.get('/billing/checkout', headers=headers)

    def issue(self, quote, **changes):
        return self.client.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()},
            json={'competence': quote['competence'], 'expected_quote_fingerprint': quote['fingerprint'],
                  'accept_quote': True, **changes})

    def test_review_has_no_external_effect_or_financial_freeze_and_minimizes_holder_data(self):
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=AssertionError('No dispatch')):
            response = self.checkout()
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json(); quote = payload['quote']
        self.assertEqual(payload['state'], 'READY')
        self.assertEqual(quote['amount'], '1.00')
        self.assertEqual(quote['mode'], 'SIMULATOR')
        self.assertEqual(quote['holder_document_masked'], '***7735')
        self.assertNotIn('11144477735', response.text)
        self.assertNotIn('customer_ref', response.text)
        self.assertIsNone(quote['period_starts_at'])
        self.assertEqual(len(self.state.charges), 0)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-obligation:' + quote['billing_id']))
        self.assertEqual(self.checkout(OTHER_OWNER).status_code, 404)

    def test_requires_accepted_unchanged_review_and_emission_is_not_payment(self):
        quote = self.checkout().json()['quote']
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=AssertionError('No dispatch')):
            self.assertEqual(self.issue(quote, accept_quote=False).status_code, 422)
            self.assertEqual(self.issue(quote, expected_quote_fingerprint='0' * 64).status_code, 409)
        issued = self.issue(quote)
        self.assertEqual(issued.status_code, 202, issued.text)
        self.assertEqual(self.checkout().json()['state'], 'REGISTERED')
        self.assertEqual(self.state.subscriptions['demo-tenant'].status.value, 'PENDING_PAYMENT')
        charge = self.state.charges[issued.json()['gateway_charge_id']]
        self.assertEqual(charge.commercial_due_at, datetime.fromisoformat(quote['due_at']))
        self.assertTrue(any(event.action == 'BILLING_CHECKOUT_ACCEPTED'
                            for event in self.state.audit.list_for_tenant('demo-tenant')))

    def test_terms_and_environment_drift_require_new_review_before_freeze(self):
        quote = self.checkout().json()['quote']
        sub = self.state.subscriptions['demo-tenant']
        self.state.subscriptions['demo-tenant'] = replace(sub, plan=replace(sub.plan, monthly_price=Decimal('2.00')))
        self.assertEqual(self.issue(quote).status_code, 409)
        fresh = self.checkout().json()['quote']
        self.state.billing_gateway.mode = GatewayMode.SANDBOX
        self.assertEqual(self.issue(fresh).status_code, 409)
        self.assertEqual(len(self.state.charges), 0)

    def test_renewal_is_due_at_anniversary_with_prior_extra_separate_from_base(self):
        self.payment(self.charge())
        self.assertEqual(self.checkout().json()['state'], 'NOT_DUE')
        self.assertEqual(self.consent(cap='5.00').status_code, 200)
        sub = self.state.subscriptions['demo-tenant']; schedule = sub.paid_cycle_schedule
        start, end = schedule.bounds(0)
        cycle_id = schedule.obligation_id('demo-tenant', 0)
        for index in range(3):
            self.state.credit_ledger.decide('demo-tenant', 'reserve', cycle_id=cycle_id,
                operation_id=f'test-delivery-{index}', action='strategy', at=start + timedelta(minutes=1))
            self.state.credit_ledger.decide('demo-tenant', 'finish', operation_id=f'test-delivery-{index}',
                kind='SETTLE', reference=f'test-output-{index}', at=start + timedelta(minutes=2))
        with clock(end):
            quote = self.checkout().json()['quote']
            self.assertEqual(quote['amount'], '6.00')
            self.assertEqual([line['amount'] for line in quote['lines']], ['1.00', '5.00'])
            self.assertEqual(datetime.fromisoformat(quote['due_at']), end)
            self.assertEqual(datetime.fromisoformat(quote['period_starts_at']), end)
            self.assertEqual(self.issue(quote).status_code, 202)

    def test_uncertain_dispatch_can_be_consulted_without_second_creation(self):
        quote = self.checkout().json()['quote']
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=RuntimeError('uncertain')) as dispatched:
            self.assertEqual(self.issue(quote).status_code, 503)
            pending = self.checkout().json()
            self.assertEqual(pending['state'], 'PENDING')
            self.assertEqual(pending['quote']['fingerprint'], quote['fingerprint'])
            self.assertEqual(self.issue(quote).status_code, 503)
        self.assertEqual(dispatched.call_count, 1)

    def test_external_due_date_must_match_reviewed_obligation(self):
        quote = self.checkout().json()['quote']
        wrong = ChargeResult('wrong-due', GatewayChargeStatus.PENDING, 'SIMULATOR', GatewayMode.SIMULATOR,
                             observed_amount=Decimal('1.00'), observed_due_date='2099-01-01')
        with patch('api.routes_billing.dispatch_frozen_charge', return_value=wrong):
            response = self.issue(quote)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'BILLING_RECONCILIATION_REQUIRED')
        self.assertIsNone(self.state.charges.get('wrong-due'))

    def test_quote_explicitly_closes_when_renewal_is_canceled(self):
        self.payment(self.charge())
        canceled = self.client.post('/billing/subscription/cancel',
            headers={**with_step_up(OWNER), **unique_idem()})
        self.assertEqual(canceled.status_code, 200)
        self.assertEqual(self.checkout().json()['state'], 'CLOSED')

    def test_gateway_environment_cannot_change_after_uncertain_dispatch(self):
        quote = self.checkout().json()['quote']
        with patch('api.routes_billing.dispatch_frozen_charge', side_effect=RuntimeError('uncertain')) as dispatched:
            self.assertEqual(self.issue(quote).status_code, 503)
            self.state.billing_gateway.mode = GatewayMode.SANDBOX
            frozen = self.checkout().json()['quote']
            self.assertEqual(frozen['mode'], 'SIMULATOR')
            self.assertEqual(self.issue(frozen).status_code, 409)
        self.assertEqual(dispatched.call_count, 1)
