"""Inbox availability is neither an external message, a user reading nor a payment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch
from dataclasses import replace

from starlette.testclient import TestClient
from api.main import create_app
from api.billing_notices import process_billing_notices, notice_id
from tests_api.test_anniversary_lifecycle import clock
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, FINANCE, VIEWER, with_step_up, unique_idem


class BillingNoticeTests(BillingCreditHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.setup_subscription()
        self.first = self.charge()
        self.assertEqual(self.payment(self.first).status_code, 200)
        self.end = self.state.subscriptions['demo-tenant'].paid_cycle_schedule.bounds(0)[1]
        with clock(self.end):
            self.renewal = self.charge()
        self.bill = self.state.charges[self.renewal]

    def run_job(self, at=None, state=None, execute=True):
        return process_billing_notices(state or self.state, 'demo-tenant', execute=execute, at=at or self.end)

    def inbox(self, client=None, headers=OWNER, suffix=''):
        return (client or self.client).get('/billing/notices' + suffix, headers=headers)

    def mark(self, identity, client=None, headers=None, body=None):
        return (client or self.client).post('/billing/notices/' + identity + '/read',
            headers=headers or {**OWNER, **unique_idem()}, json=body)

    def peer(self):
        client = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(client.app.state.campaia.db._conn.close)
        return client

    def test_dry_run_never_contacts_gateway_mutates_invoice_or_pretends_external_delivery(self):
        original = self.state.subscriptions['demo-tenant']
        with patch.object(self.state.billing_gateway, 'inspect_charge', side_effect=AssertionError('No GET')):
            with patch.object(self.state.billing_gateway, 'create_charge', side_effect=AssertionError('No POST')):
                report = self.run_job(execute=False)
        self.assertEqual(report['items'][0]['state'], 'DRY_RUN')
        self.assertEqual(self.inbox().json()['items'], [])
        self.assertEqual(self.state.subscriptions['demo-tenant'], original)
        self.assertEqual(self.state.charges[self.renewal], self.bill)

    def test_approved_offsets_are_available_once_without_changing_payment_or_external_reminder_counter(self):
        for day in [0, 2, 3, 7]:
            self.run_job(at=self.end + timedelta(days=day))
            self.run_job(at=self.end + timedelta(days=day))
        rows = self.inbox().json()['items']
        self.assertEqual(sorted(row['offset_days'] for row in rows), [0, 2, 3, 7])
        self.assertTrue(all(row['channel'] == 'IN_APP' and row['read_at'] is None for row in rows))
        self.assertTrue(all(row['invoice_state'] == 'PENDING_CONFIRMATION' for row in rows))
        sub = self.state.subscriptions['demo-tenant']
        self.assertEqual(sub.status.value, 'ACTIVE')
        self.assertEqual(sub.dunning_reminders_sent, 0)
        self.assertEqual(sub.paid_cycle_schedule.paid_through_index, 0)
        self.assertEqual(self.state.charges[self.renewal].status.value, 'OPEN')
        self.assertEqual(sum(e.action == 'BILLING_NOTICE_AVAILABLE'
            for e in self.state.audit.list_for_tenant('demo-tenant')), 4)

    def test_late_worker_emits_latest_due_marker_and_does_not_backdate_missed_delivery(self):
        actual = self.end + timedelta(days=9)
        self.run_job(at=actual)
        rows = self.inbox().json()['items']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['offset_days'], 7)
        self.assertEqual(datetime.fromisoformat(rows[0]['created_at']), actual)
        self.assertEqual(datetime.fromisoformat(rows[0]['scheduled_at']), self.end + timedelta(days=7))
        self.assertFalse(any(e.action == 'DUNNING_SENT' for e in self.state.audit.list_for_tenant('demo-tenant')))

    def test_restart_and_two_workers_make_one_notice_and_reading_is_individual(self):
        other = self.peer()
        with ThreadPoolExecutor(max_workers=2) as pool:
            reports = list(pool.map(lambda state: self.run_job(state=state),
                [self.state, other.app.state.campaia]))
        self.assertEqual(reports[0], reports[1])
        rows = self.inbox(other).json()['items']
        self.assertEqual(len(rows), 1)
        identity = rows[0]['id']
        headers = {**OWNER, **unique_idem()}
        first = self.mark(identity, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.mark(identity, client=other, headers=headers).json(), first.json())
        self.assertIsNotNone(self.inbox(other).json()['items'][0]['read_at'])
        self.assertIsNone(self.inbox(other, headers=FINANCE).json()['items'][0]['read_at'])
        self.assertEqual(self.mark(identity, client=other, headers={**FINANCE, **unique_idem()}).status_code, 200)
        self.assertEqual(sum(e.action == 'BILLING_NOTICE_AVAILABLE'
            for e in self.state.audit.list_for_tenant('demo-tenant')), 1)

    def test_rbac_isolation_and_nonce_context_do_not_leak_other_tenant_or_reader(self):
        self.run_job()
        identity = self.inbox().json()['items'][0]['id']
        self.assertEqual(self.inbox(headers=OTHER_OWNER).json()['items'], [])
        self.assertEqual(self.inbox(headers=VIEWER).status_code, 403)
        self.assertEqual(self.mark(identity, headers={**OTHER_OWNER, **unique_idem()}).status_code, 404)
        self.assertEqual(self.mark(identity, headers={**VIEWER, **unique_idem()}).status_code, 403)
        self.assertEqual(self.inbox(headers=OTHER_OWNER, suffix='?cursor=' + identity).status_code, 422)
        self.assertEqual(self.mark(identity, body={'tenant_id': 'other'}).status_code, 422)
        headers = {**OWNER, **unique_idem()}
        self.assertEqual(self.mark(identity, headers=headers).status_code, 200)
        self.assertEqual(self.mark(identity, headers={**FINANCE, 'Idempotency-Key': headers['Idempotency-Key']}).status_code, 409)
        self.assertEqual(self.mark(identity, headers=OWNER).status_code, 422)

    def test_paid_invoice_suppresses_future_notices_and_keeps_prior_history_honest(self):
        self.run_job()
        with clock(self.end):
            self.assertEqual(self.payment(self.renewal, 'renewal-paid').status_code, 200)
        self.assertEqual(self.run_job(at=self.end + timedelta(days=3))['items'], [])
        rows = self.inbox().json()['items']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['invoice_state'], 'PAYMENT_CONFIRMED')
        self.assertIsNone(rows[0]['read_at'])

    def test_canceled_renewal_and_verified_void_never_create_new_payment_reminders(self):
        with clock(self.end):
            self.assertEqual(self.client.post('/billing/subscription/cancel',
                headers={**with_step_up(OWNER), **unique_idem()}, json={'immediate': True}).status_code, 200)
            self.assertEqual(self.run_job()['items'], [])
            row = self.client.get('/billing/charges', headers=OWNER).json()['items'][0]
            r = self.client.post('/billing/charges/' + self.renewal + '/withdraw',
                headers={**with_step_up(OWNER), **unique_idem()},
                json={'fingerprint': row['withdrawal_fingerprint'], 'accept': True})
            self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.run_job(at=self.end + timedelta(days=7))['items'], [])
        self.assertEqual(self.inbox().json()['items'], [])

    def test_receipt_conflict_is_not_presented_as_a_new_debt(self):
        self.run_job()
        self.state.charges[self.renewal] = replace(self.bill, payment_reconciliation_state='AMOUNT_MISMATCH')
        self.assertEqual(self.run_job(at=self.end + timedelta(days=3))['items'], [])
        self.assertEqual(self.inbox().json()['items'][0]['invoice_state'], 'REVIEW_REQUIRED')

    def test_final_delivered_usage_has_its_own_due_and_never_grants_another_paid_period(self):
        # Cancel and withdraw the already frozen renewal before separating the same usage.
        with clock(self.end):
            self.client.post('/billing/subscription/cancel',
                headers={**with_step_up(OWNER), **unique_idem()}, json={'immediate': True})
            row = self.client.get('/billing/charges', headers=OWNER).json()['items'][0]
            r = self.client.post('/billing/charges/' + self.renewal + '/withdraw',
                headers={**with_step_up(OWNER), **unique_idem()},
                json={'fingerprint': row['withdrawal_fingerprint'], 'accept': True})
            self.assertEqual(r.status_code, 200, r.text)
        # This fixture models a separate immutable final invoice already created by closure.
        from campaia_core.subscription import ChargePurpose, ChargeLineItem
        final = replace(self.bill, billing_id='fixture-final-usage', purpose=ChargePurpose.FINAL_USAGE,
                        commercial_cycle_index=0, line_items=(ChargeLineItem('Delivered final usage fixture', Decimal('5.00')),))
        self.state.charges['fixture-final-gateway'] = final
        self.run_job()
        rows = self.inbox().json()['items']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['billing_id'], final.billing_id)
        self.assertEqual(self.state.subscriptions['demo-tenant'].paid_cycle_schedule.paid_through_index, 0)

    def test_failed_notice_commit_rolls_back_notice_audit_and_delivery_fence(self):
        original = self.state.audit.append
        def fail(**event):
            original(**event)
            if event['action'] == 'BILLING_NOTICE_AVAILABLE':
                raise RuntimeError('injected notice commit')
        with patch.object(self.state.audit, 'append', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'injected notice commit'):
                self.run_job()
        self.assertEqual(self.inbox().json()['items'], [])
        identity = notice_id('demo-tenant', self.bill.billing_id, 0)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-notice-delivery:' + identity))
        self.assertFalse(any(e.action == 'BILLING_NOTICE_AVAILABLE'
            for e in self.state.audit.list_for_tenant('demo-tenant')))
        self.assertEqual(self.run_job()['items'][0]['state'], 'AVAILABLE')

    def test_payment_between_candidate_and_commit_suppresses_without_permanent_delivery_claim(self):
        other = self.peer()
        original = self.state.idempotency.execute
        def execute(tenant, key, operation):
            if key.startswith('billing-notice-delivery:'):
                with clock(self.end):
                    invoice = self.state.charges[self.renewal]
                    r = other.post('/webhooks/asaas', headers={'asaas-access-token': 'test-webhook-secret'},
                        json={'id': 'paid-during-notice', 'event': 'PAYMENT_RECEIVED',
                              'payment': {'id': self.renewal, 'status': 'RECEIVED', 'value': str(invoice.amount)}})
                    self.assertEqual(r.status_code, 200, r.text)
            return original(tenant, key, operation)
        with patch.object(self.state.idempotency, 'execute', side_effect=execute):
            report = self.run_job()
        self.assertEqual(report['items'][0]['state'], 'SUPPRESSED')
        self.assertEqual(self.inbox().json()['items'], [])
        identity = notice_id('demo-tenant', self.bill.billing_id, 0)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', 'billing-notice-delivery:' + identity))

    def test_cursor_pages_are_stable_and_private_fields_are_not_returned(self):
        at = self.end
        for i in range(51):
            identity = notice_id('demo-tenant', 'fixture-' + str(i), 0)
            self.state.billing_notices.append('demo-tenant', {'id': identity, 'billing_id': self.bill.billing_id,
                'gateway_charge_id': self.renewal, 'channel': 'IN_APP', 'offset_days': 0,
                'scheduled_at': at, 'created_at': at, 'due_at': at, 'amount': '1.00', 'currency': 'BRL',
                'mode': 'SIMULATOR', 'private_fixture': 'must-not-leak'})
        first = self.inbox().json()
        second = self.inbox(suffix='?cursor=' + first['next_cursor']).json()
        self.assertEqual(len(first['items']), 50)
        self.assertEqual(len(second['items']), 1)
        self.assertIsNone(second['next_cursor'])
        self.assertFalse(set(x['id'] for x in first['items']).intersection(x['id'] for x in second['items']))
        self.assertNotIn('private_fixture', str(first))
        self.assertNotIn('customer_document', str(first))


class InitialInvoiceNoticeTests(BillingCreditHarness, unittest.TestCase):
    def test_trial_or_first_unpaid_purchase_is_not_a_paid_renewal_dunning_source(self):
        self.setup_subscription(trial=True)
        self.charge()
        report = process_billing_notices(self.state, 'demo-tenant', execute=True,
            at=datetime.now(timezone.utc) + timedelta(days=30))
        self.assertEqual(report['items'], [])
        self.assertEqual(self.client.get('/billing/notices', headers=OWNER).json()['items'], [])
