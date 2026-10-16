"""F3 PostgreSQL integration tests.

Skipped in the ordinary fast suite and run in a dedicated GitHub Actions job against a
real PostgreSQL 16 service.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import os
import queue
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg

from api.main import create_app
from api.postgres import (
    PostgresDatabase,
    PostgresFixedWindowRateLimiter,
    PostgresMigrationRunner,
    RUNTIME_SCHEMA,
    RUNTIME_TABLES,
)


DSN = os.environ.get("CAMPAIA_TEST_DATABASE_URL")


def _process_idempotency_worker(dsn, label, start_event, result_queue, executed_queue):
    state = create_app(database_url=dsn, env="test").state.campaia
    if not start_event.wait(timeout=10):
        result_queue.put(("error", label, "start timeout"))
        return

    def operation():
        executed_queue.put(label)
        time.sleep(0.25)
        state.audit.append(
            tenant_id="demo-tenant",
            actor=label,
            action="PG_PROCESS_EXACTLY_ONCE",
            target="same-key",
        )
        return {"winner": label}

    try:
        result, replay = state.idempotency.execute(
            "demo-tenant",
            "http:pg:process-concurrent-idempotency",
            operation,
        )
        result_queue.put(("ok", result, replay))
    except Exception as exc:  # pragma: no cover - surfaced to parent assertion
        result_queue.put(("error", label, repr(exc)))


def _process_rate_limit_worker(
    dsn, label, start_event, result_queue, attempts, now_iso
):
    limiter = PostgresFixedWindowRateLimiter(
        PostgresDatabase(dsn),
        scope="process-rate-limit-test",
        max_requests=5,
        window=timedelta(minutes=1),
    )
    now = datetime.fromisoformat(now_iso)
    if not start_event.wait(timeout=10):
        result_queue.put(("error", label, "start timeout"))
        return
    accepted = sum(
        1 for _ in range(attempts)
        if limiter.allow("203.0.113.50", now=now)
    )
    result_queue.put(("ok", label, accepted))


def _g3_state_writer(dsn, ready_event, done_event, ids_queue):
    state = create_app(database_url=dsn, env="test").state.campaia
    principal = state.tokens["demo-owner-token"]
    now = datetime.now(timezone.utc)
    session = state.sessions.create(
        principal,
        now=now,
        available_principals=(principal,),
        subject="g3-two-process-subject",
    )
    state.start_oauth_state(
        "g3-two-process-oauth",
        tenant_id="demo-tenant",
        provider="GOOGLE_ADS",
        now=now,
        user_id=principal.user_id,
        session_key=f"session:{session.session_id}",
        step_up_verified_at=now,
    )
    approval = state.approvals.create(
        "demo-tenant",
        campaign_id="g3-process-campaign",
        kind="PUBLISH",
        requested_by=principal.user_id,
        amount=None,
        requires_dual_approval=False,
        plan_version=1,
    )
    ids_queue.put((session.session_id, approval.approval_id, now.isoformat()))
    ready_event.set()
    done_event.wait(timeout=15)


def _g3_state_reader(dsn, ready_event, done_event, ids, result_queue):
    if not ready_event.wait(timeout=10):
        result_queue.put(("error",))
        return
    session_id, approval_id, now_iso = ids
    state = create_app(database_url=dsn, env="test").state.campaia
    session = state.sessions.get(session_id)
    pending = state.redeem_oauth_state(
        "g3-two-process-oauth",
        tenant_id="demo-tenant",
        now=datetime.fromisoformat(now_iso),
    )
    approval = state.approvals.get("demo-tenant", approval_id)
    wrong_tenant = state.approvals.get("other-tenant", approval_id)
    state.sessions.invalidate(session_id)
    result_queue.put(
        ("ok", session is not None, pending is not None, approval is not None, wrong_tenant is None)
    )
    done_event.set()


def _g3_crash_holder(dsn, ready_event):
    state = create_app(database_url=dsn, env="test").state.campaia

    def operation():
        state.audit.append(
            tenant_id="demo-tenant",
            actor="crashed-process",
            action="G3_CRASH_REPLAY",
            target="crash-key",
        )
        ready_event.set()
        threading.Event().wait(timeout=60)
        return {"unexpected": "survived"}

    state.idempotency.execute(
        "demo-tenant",
        "http:g3:crash-replay",
        operation,
    )


@unittest.skipUnless(DSN, "CAMPAIA_TEST_DATABASE_URL not configured")
class PostgresRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = PostgresMigrationRunner(DSN)
        cls.runner.rollback_all()
        cls.runner.apply_all()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.runner.rollback_all()

    def setUp(self) -> None:
        self.runner.apply_all()
        with psycopg.connect(DSN) as conn:
            for table in RUNTIME_TABLES:
                conn.execute(
                    f'TRUNCATE TABLE {RUNTIME_SCHEMA}."{table}" RESTART IDENTITY'
                )
            conn.execute(f"TRUNCATE TABLE {RUNTIME_SCHEMA}.rate_limit_windows")

    def _states(self):
        a = create_app(database_url=DSN, env="test").state.campaia
        b = create_app(database_url=DSN, env="test").state.campaia
        return a, b

    def _runtime_tables(self) -> set[str]:
        with psycopg.connect(DSN) as conn:
            return {
                row[0]
                for row in conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s",
                    (RUNTIME_SCHEMA,),
                ).fetchall()
            }

    def test_commercial_payment_webhook_is_atomic_across_workers(self) -> None:
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from tests_api.test_helpers import OWNER, with_step_up, unique_idem

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "catalog.json"
            plans = json.loads((Path(__file__).parents[1] / "config/plans.example.json").read_text())
            plans[0]["included_credits"] = 10
            plans[0]["cancellation_mode"] = "PERIOD_END"
            plans[0]["credit_policy"] = {"version": "pg-test-v1", "action_weights": {"strategy": 5},
                "trial_credits": 30, "trial_max_users": 1, "trial_max_active_campaigns": 1}
            config.write_text(json.dumps(plans))
            with patch.dict(os.environ, {"CAMPAIA_PLAN_CATALOG_PATH": str(config),
                                         "ASAAS_WEBHOOK_TOKEN": "pg-webhook-proof", "ASAAS_API_KEY": "", "GEMINI_API_KEY": ""}):
                clients = [TestClient(create_app(database_url=DSN, env="test")) for _ in range(2)]
                setup = clients[0].put("/billing/subscription",
                    headers={**with_step_up(OWNER), **unique_idem()}, json={
                        "plan_id": plans[0]["plan_id"], "customer_document": "11144477735", "start_trial": True})
                self.assertEqual(setup.status_code, 200, setup.text)
                from campaia_core.billing_settlement import dispatch_frozen_charge
                from api.billing_dispatch import obligation_key
                def prove_committed(obligation, gateway):
                    state = clients[0].app.state.campaia
                    self.assertFalse(state.db.in_transaction)
                    frozen = clients[1].app.state.campaia.idempotency.get(
                        "demo-tenant", obligation_key(obligation.billing_id))
                    self.assertEqual(frozen.result, obligation)
                    return dispatch_frozen_charge(obligation, gateway)
                reviewed = clients[0].get("/billing/checkout", headers=OWNER)
                self.assertEqual(reviewed.status_code, 200, reviewed.text)
                quote = reviewed.json()["quote"]
                with patch("api.routes_billing.dispatch_frozen_charge", side_effect=prove_committed):
                    charge = clients[0].post("/billing/charges",
                        headers={**with_step_up(OWNER), **unique_idem()}, json={
                            "competence": quote["competence"], "expected_quote_fingerprint": quote["fingerprint"],
                            "accept_quote": True})
                self.assertEqual(charge.status_code, 202, charge.text)
                payload = {"id": "pg-paid-event", "event": "PAYMENT_RECEIVED", "payment": {
                    "id": charge.json()["gateway_charge_id"], "status": "RECEIVED", "value": charge.json()["amount"]}}
                def deliver(client):
                    return client.post("/webhooks/asaas", headers={"asaas-access-token": "pg-webhook-proof"}, json=payload)
                with patch("api.routes_billing.grant_paid_cycle", side_effect=RuntimeError("injected")):
                    with self.assertRaises(RuntimeError):
                        deliver(clients[0])
                self.assertFalse(clients[1].app.state.campaia.asaas_webhook.already_seen("pg-paid-event"))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    responses = list(pool.map(deliver, clients))
                self.assertTrue(all(r.status_code == 200 for r in responses))
                self.assertEqual(sum(r.json().get("processed", False) for r in responses), 1)
                usage = clients[1].get("/billing/usage", headers=OWNER).json()
                self.assertEqual(usage["balance"]["included_credits"], 10)
                entries = clients[1].app.state.campaia.credit_ledger.entries("demo-tenant")
                self.assertEqual(sum(e.kind == "OPEN" for e in entries), 2)

                from tests_api.test_helpers import DEFAULT_BRIEF
                created = clients[0].post("/briefs", headers={**OWNER, **unique_idem()}, json=DEFAULT_BRIEF)
                self.assertEqual(created.status_code, 202, created.text)
                campaign_id = created.json()["id"]
                quote = clients[0].get(f"/campaigns/{campaign_id}/plan/quote", headers=OWNER).json()
                body = {"credit_confirmation": {k: quote[k] for k in
                    ("cycle_id", "policy_version", "credits", "extra_amount")}}
                headers = {**OWNER, **unique_idem()}
                entered, complete = threading.Event(), threading.Event()
                runner = clients[0].app.state.campaia.agent_runner
                original = runner.run
                def blocked(*args, **kwargs):
                    self.assertFalse(clients[0].app.state.campaia.db.in_transaction)
                    entered.set()
                    if not complete.wait(timeout=10):
                        raise RuntimeError("coordination timeout")
                    return original(*args, **kwargs)
                endpoint = f"/campaigns/{campaign_id}/plan/regenerate"
                with patch.object(runner, "run", side_effect=blocked) as provider:
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        running = pool.submit(clients[0].post, endpoint, headers=headers, json=body)
                        self.assertTrue(entered.wait(timeout=5))
                        pending = clients[1].post(endpoint, headers=headers, json=body)
                        self.assertEqual(pending.status_code, 503, pending.text)
                        complete.set()
                        first = running.result(timeout=5)
                    self.assertEqual(first.status_code, 202, first.text)
                    replay = clients[1].post(endpoint, headers=headers, json=body)
                    self.assertEqual(replay.json(), first.json())
                    self.assertEqual(provider.call_count, 1)
                usage = clients[1].get("/billing/usage", headers=OWNER).json()
                self.assertEqual(usage["balance"]["consumed_credits"], 5)
                self.assertEqual(usage["balance"]["reserved_credits"], 0)

                # A later authenticated divergence is durable across workers and does not
                # undo consumption. Two fresh provider reads clear it without a second grant.
                gateway_id = charge.json()["gateway_charge_id"]
                mismatch = clients[0].post("/webhooks/asaas", headers={"asaas-access-token": "pg-webhook-proof"},
                    json={"id": "pg-receipt-mismatch", "event": "PAYMENT_RECEIVED",
                          "payment": {"id": gateway_id, "status": "RECEIVED", "value": "0.50"}})
                self.assertEqual(mismatch.status_code, 200, mismatch.text)
                self.assertFalse(clients[1].get("/billing/usage", headers=OWNER).json()["access_active"])
                for client in clients:
                    client.app.state.campaia.billing_gateway.confirm(gateway_id)
                def reconcile(client):
                    state = client.app.state.campaia
                    original_inspect = state.billing_gateway.inspect_charge
                    def inspect(*args):
                        self.assertFalse(state.db.in_transaction)
                        return original_inspect(*args)
                    with patch.object(state.billing_gateway, "inspect_charge", side_effect=inspect):
                        return client.post(f"/billing/charges/{gateway_id}/reconcile",
                            headers={**with_step_up(OWNER), **unique_idem()})
                with ThreadPoolExecutor(max_workers=2) as pool:
                    reconciliations = list(pool.map(reconcile, clients))
                self.assertTrue(all(r.status_code == 200 for r in reconciliations), [r.text for r in reconciliations])
                self.assertTrue(clients[1].get("/billing/usage", headers=OWNER).json()["access_active"])
                self.assertEqual(clients[1].get("/billing/usage", headers=OWNER).json()["balance"]["consumed_credits"], 5)
                self.assertEqual(sum(e.kind == "OPEN" for e in clients[1].app.state.campaia.credit_ledger.entries("demo-tenant")), 2)
                self.assertIsNotNone(clients[1].app.state.campaia.idempotency.get("demo-tenant", "billing-receipt:pg-receipt-mismatch"))

                canceled = clients[0].post("/billing/subscription/cancel",
                    headers={**with_step_up(OWNER), **unique_idem()})
                self.assertEqual(canceled.status_code, 200, canceled.text)
                self.assertEqual(canceled.json()["status"], "ACTIVE")
                observed = clients[1].get("/billing/subscription", headers=OWNER).json()
                self.assertEqual(observed["cancel_at_period_end"], canceled.json()["cancel_at_period_end"])
                kept = clients[1].post("/billing/subscription/reactivate",
                    headers={**with_step_up(OWNER), **unique_idem()})
                self.assertEqual(kept.status_code, 200, kept.text)
                self.assertIsNone(kept.json()["cancel_at_period_end"])
                self.assertEqual(len(clients[1].app.state.campaia.charges.items_for_tenant("demo-tenant")), 1)
                usage = clients[0].get("/billing/usage", headers=OWNER).json()
                consent = clients[0].post("/billing/usage/consent",
                    headers={**with_step_up(OWNER), **unique_idem()}, json={"cap": "5.00",
                        "cycle_id": usage["cycle"]["id"], "policy_version": usage["cycle"]["policy_version"],
                        "extra_credit_price": usage["balance"]["extra_credit_price"]})
                self.assertEqual(consent.status_code, 200, consent.text)
                for _ in range(2):
                    quote = clients[0].get(f"/campaigns/{campaign_id}/plan/quote", headers=OWNER).json()
                    generated = clients[0].post(endpoint, headers={**OWNER, **unique_idem()},
                        json={"credit_confirmation": {key: quote[key] for key in
                            ("cycle_id", "policy_version", "credits", "extra_amount")}})
                    self.assertEqual(generated.status_code, 202, generated.text)
                closed = clients[0].post("/billing/subscription/cancel",
                    headers={**with_step_up(OWNER), **unique_idem()}, json={"immediate": True})
                self.assertEqual(closed.status_code, 200, closed.text)
                final_quote = clients[1].get("/billing/closure", headers=OWNER).json()
                self.assertEqual(final_quote["amount"], "5.00")
                def close_final(client):
                    return client.post("/billing/closure", headers={**with_step_up(OWNER), **unique_idem()},
                        json={"fingerprint": final_quote["fingerprint"], "accept": True})
                with ThreadPoolExecutor(max_workers=2) as pool:
                    statements = list(pool.map(close_final, clients))
                self.assertTrue(all(response.status_code == 200 for response in statements), [r.text for r in statements])
                self.assertEqual(len(clients[0].app.state.campaia.charges.items_for_tenant("demo-tenant")), 2)
                final_id = next(key for key, invoice in clients[0].app.state.campaia.charges.items_for_tenant("demo-tenant")
                                if invoice.purpose.value == "FINAL_USAGE")
                final_paid = clients[0].post("/webhooks/asaas", headers={"asaas-access-token": "pg-webhook-proof"},
                    json={"id": "pg-final-paid", "event": "PAYMENT_RECEIVED", "payment": {"id": final_id, "status": "RECEIVED", "value": final_quote["amount"]}})
                self.assertEqual(final_paid.status_code, 200, final_paid.text)
                self.assertEqual(clients[1].get("/billing/subscription", headers=OWNER).json()["status"], "CANCELED")
                self.assertEqual(clients[1].get("/billing/closure", headers=OWNER).json()["state"], "SETTLED")
                self.assertEqual(sum(entry.kind == "OPEN" for entry in
                    clients[1].app.state.campaia.credit_ledger.entries("demo-tenant")), 2)
                guarantee = clients[0].get('/billing/guarantee', headers=OWNER).json()
                self.assertEqual(guarantee['state'], 'ELIGIBLE')
                self.assertEqual(len(guarantee['items']), 2)
                def request_guarantee(client):
                    return client.post('/billing/guarantee',
                        headers={**with_step_up(OWNER), **unique_idem()},
                        json={'fingerprint': guarantee['fingerprint'], 'accept': True})
                with ThreadPoolExecutor(max_workers=2) as pool:
                    cases = list(pool.map(request_guarantee, clients))
                self.assertTrue(all(case.status_code == 200 for case in cases), [case.text for case in cases])
                self.assertEqual(cases[0].json(), cases[1].json())
                self.assertEqual(clients[1].get('/billing/guarantee', headers=OWNER).json()['state'], 'REQUESTED')
                self.assertEqual(sum(e.action == 'BILLING_GUARANTEE_REQUESTED' for e in
                    clients[1].app.state.campaia.audit.list_for_tenant('demo-tenant')), 1)
                from api.billing_refund_worker import process_guarantee_refunds
                from api.billing_refund_policy import refund_intent_key
                for client in clients:
                    client.app.state.campaia.billing_gateway.confirm(charge.json()['gateway_charge_id'])
                    client.app.state.campaia.billing_gateway.confirm(final_id)
                source_gateway = clients[0].app.state.campaia.billing_gateway
                original_refund = source_gateway.refund_charge
                def refund_proves_commit(gateway_id, command, amount):
                    self.assertFalse(clients[0].app.state.campaia.db.in_transaction)
                    intent = clients[1].app.state.campaia.idempotency.get('demo-tenant',
                        refund_intent_key(cases[0].json()['request_id'], command.billing_id))
                    self.assertIsNotNone(intent)
                    self.assertEqual(intent.result['amount'], amount)
                    return original_refund(gateway_id, command, amount)
                with patch.object(source_gateway, 'refund_charge', side_effect=refund_proves_commit) as sent:
                    pending = process_guarantee_refunds(clients[0].app.state.campaia, 'demo-tenant', execute=True)
                self.assertEqual(sent.call_count, 2)
                self.assertTrue(all(item['state'] == 'PROVIDER_PENDING' for item in pending['items']), pending)
                for gateway_id in (charge.json()['gateway_charge_id'], final_id):
                    clients[1].app.state.campaia.billing_gateway.complete_refund(gateway_id, tenant_id='demo-tenant')
                with patch.object(clients[1].app.state.campaia.billing_gateway, 'refund_charge', side_effect=AssertionError('No second refund POST')):
                    done = process_guarantee_refunds(clients[1].app.state.campaia, 'demo-tenant', execute=True)
                self.assertTrue(all(item['state'] == 'REFUND_DONE_ADJUSTMENT_PENDING' for item in done['items']), done)
                case_after = clients[0].get('/billing/guarantee', headers=OWNER).json()
                self.assertEqual(case_after['state'], 'PROCESSING')
                self.assertEqual(len(case_after['refund_progress']), 2)
                from api.billing_guarantee_resolution import finalize_guarantee
                with ThreadPoolExecutor(max_workers=2) as pool:
                    resolved = list(pool.map(lambda client: finalize_guarantee(
                        client.app.state.campaia, 'demo-tenant', execute=True), clients))
                self.assertTrue(all(r['state'] == 'FINANCIALLY_RESOLVED' for r in resolved), resolved)
                self.assertEqual(resolved[0], resolved[1])
                self.assertEqual(clients[1].get('/billing/guarantee', headers=OWNER).json()['fiscal_adjustment_state'], 'PENDING_CAPABILITY')
                self.assertEqual(clients[1].get('/billing/closure', headers=OWNER).json()['state'], 'GUARANTEE_CLOSED')
                self.assertEqual(sum(e.action == 'BILLING_GUARANTEE_FINANCIALLY_RESOLVED' for e in
                    clients[0].app.state.campaia.audit.list_for_tenant('demo-tenant')), 1)
                self.assertEqual(sum(e.kind == 'OPEN' for e in clients[0].app.state.campaia.credit_ledger.entries('demo-tenant')), 2)



    def test_consented_anniversary_worker_and_checkout_share_one_postgres_dispatch(self):
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from tests_api.test_helpers import OWNER, with_step_up, unique_idem
        from tests_api.test_anniversary_lifecycle import clock
        from api.billing_renewal import process_renewal_invoice
        from campaia_core.billing_settlement import dispatch_frozen_charge
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'catalog.json'
            plans = json.loads((Path(__file__).parents[1] / 'config/plans.example.json').read_text())
            plans[0]['included_credits'] = 10
            plans[0]['cancellation_mode'] = 'PERIOD_END'
            plans[0]['credit_policy'] = {'version': 'pg-renewal-v1', 'action_weights': {'strategy': 5},
                'trial_credits': 30, 'trial_max_users': 1, 'trial_max_active_campaigns': 1}
            config.write_text(json.dumps(plans))
            with patch.dict(os.environ, {'CAMPAIA_PLAN_CATALOG_PATH': str(config),
                    'ASAAS_WEBHOOK_TOKEN': 'pg-renewal-proof', 'ASAAS_API_KEY': '', 'GEMINI_API_KEY': ''}):
                clients = [TestClient(create_app(database_url=DSN, env='test')) for _ in range(2)]
                for client in clients:
                    self.addCleanup(client.close)
                a, b = clients
                setup = a.put('/billing/subscription', headers={**with_step_up(OWNER), **unique_idem()},
                    json={'plan_id': plans[0]['plan_id'], 'customer_document': '11144477735'})
                self.assertEqual(setup.status_code, 200, setup.text)
                first = a.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()},
                    json={'competence': 'server-cycle'})
                self.assertEqual(first.status_code, 202, first.text)
                paid = a.post('/webhooks/asaas', headers={'asaas-access-token': 'pg-renewal-proof'},
                    json={'id': 'pg-renewal-first-paid', 'event': 'PAYMENT_RECEIVED', 'payment': {
                        'id': first.json()['gateway_charge_id'], 'status': 'RECEIVED', 'value': first.json()['amount']}})
                self.assertEqual(paid.status_code, 200, paid.text)
                q = b.get('/billing/renewal', headers=OWNER).json()
                consent = a.put('/billing/renewal', headers={**with_step_up(OWNER), **unique_idem()},
                    json={'enabled': True, 'fingerprint': q['fingerprint']})
                self.assertEqual(consent.status_code, 200, consent.text)
                self.assertTrue(b.get('/billing/renewal', headers=OWNER).json()['valid'])
                sub = a.app.state.campaia.subscriptions['demo-tenant']
                with clock(sub.paid_cycle_schedule.bounds(0)[1]):
                    def dispatch(charge, gateway):
                        self.assertFalse(a.app.state.campaia.db.in_transaction)
                        self.assertIsNotNone(b.app.state.campaia.idempotency.get('demo-tenant', 'billing-dispatch:' + charge.billing_id))
                        return dispatch_frozen_charge(charge, gateway)
                    with patch('api.billing_renewal.dispatch_frozen_charge', side_effect=dispatch) as sent:
                        with ThreadPoolExecutor(max_workers=2) as pool:
                            reports = list(pool.map(lambda client: process_renewal_invoice(
                                client.app.state.campaia, 'demo-tenant', execute=True, dispatch_enabled=True), clients))
                        result = process_renewal_invoice(b.app.state.campaia, 'demo-tenant', execute=True, dispatch_enabled=True)
                    self.assertEqual(result['state'], 'REGISTERED', reports)
                    self.assertEqual(sent.call_count, 1)
                    manual = a.post('/billing/charges', headers={**with_step_up(OWNER), **unique_idem()},
                        json={'competence': 'browser'})
                    self.assertEqual(manual.status_code, 202, manual.text)
                    self.assertEqual(manual.json()['gateway_charge_id'], result['gateway_charge_id'])
                    self.assertEqual(len(b.app.state.campaia.charges.items_for_tenant('demo-tenant')), 2)
                    self.assertEqual(b.app.state.campaia.subscriptions['demo-tenant'].paid_cycle_schedule.paid_through_index, 0)
                    from api.billing_notices import process_billing_notices
                    from tests_api.test_helpers import FINANCE
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        notices = list(pool.map(lambda client: process_billing_notices(
                            client.app.state.campaia, 'demo-tenant', execute=True,
                            at=sub.paid_cycle_schedule.bounds(0)[1]), clients))
                    self.assertEqual(notices[0], notices[1])
                    inbox = b.get('/billing/notices', headers=OWNER).json()
                    self.assertEqual(len(inbox['items']), 1)
                    identity = inbox['items'][0]['id']
                    read = a.post('/billing/notices/' + identity + '/read',
                        headers={**OWNER, **unique_idem()})
                    self.assertEqual(read.status_code, 200, read.text)
                    self.assertIsNotNone(b.get('/billing/notices', headers=OWNER).json()['items'][0]['read_at'])
                    self.assertIsNone(b.get('/billing/notices', headers=FINANCE).json()['items'][0]['read_at'])
                    self.assertEqual(b.app.state.campaia.subscriptions['demo-tenant'].dunning_reminders_sent, 0)

    def test_brand_revisions_are_atomic_and_stale_updates_fail_across_connections(self):
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from tests_api.test_helpers import OWNER, OTHER_OWNER, unique_idem
        from tests_api.test_brand_versions import BODY
        with patch.dict(os.environ, {'GEMINI_API_KEY': '', 'ASAAS_API_KEY': ''}):
            a, b = [TestClient(create_app(database_url=DSN, env='test')) for _ in range(2)]
            self.addCleanup(a.close); self.addCleanup(b.close)
            created = a.post('/brand-profiles', headers={**OWNER, **unique_idem()}, json=BODY)
            self.assertEqual(created.status_code, 201, created.text)
            first = created.json()
            endpoint = '/brand-profiles/' + first['id']
            def update(client):
                return client.put(endpoint, headers={**OWNER, **unique_idem()},
                    json={**BODY, 'expected_version': 1, 'tone': 'a' if client is a else 'b'})
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(update, (a, b)))
            self.assertEqual(sorted(r.status_code for r in responses), [200, 409], [r.text for r in responses])
            current = next(r.json() for r in responses if r.status_code == 200)
            self.assertEqual(b.get(endpoint, headers=OWNER).json(), current)
            history = b.get(endpoint + '/versions', headers=OWNER).json()
            self.assertEqual(history['items'], [current, first])
            self.assertEqual(b.get(endpoint + '/versions', headers=OTHER_OWNER).status_code, 404)
            original = a.app.state.campaia.audit.append
            def fail(**event):
                original(**event)
                if event['action'] == 'BRAND_PROFILE_UPDATE':
                    raise RuntimeError('injected PG brand update')
            headers = {**OWNER, **unique_idem()}
            with patch.object(a.app.state.campaia.audit, 'append', side_effect=fail):
                with self.assertRaisesRegex(RuntimeError, 'injected PG brand update'):
                    a.put(endpoint, headers=headers, json={**BODY, 'expected_version': 2, 'tone': 'not committed'})
            self.assertEqual(b.get(endpoint, headers=OWNER).json(), current)
            self.assertEqual(b.get(endpoint + '/versions', headers=OWNER).json(), history)
            self.assertEqual(sum(e.action == 'BRAND_PROFILE_UPDATE' for e in
                b.app.state.campaia.audit.list_for_tenant('demo-tenant')), 1)

    def test_persistent_ai_cost_budget_is_shared_and_unknown_holds_survive_restart(self):
        from unittest.mock import patch
        from tests_api.test_ai_cost_evidence import CostProvider, request
        from campaia_core.ai_gateway import OutputSchema, AIStatus, CostObservation
        tenant = 'pg-cost-fixture-tenant'
        with patch.dict(os.environ, {'GEMINI_API_KEY': '', 'ASAAS_API_KEY': ''}):
            a, b = self._states()
            for state in (a, b):
                self.addCleanup(state.db.close)
                state.ai_gateway.schemas['cost-fixture'] = OutputSchema(
                    'cost-fixture', frozenset({'ok'}), {'ok': bool})
            a.ai_gateway.ledger.set_cap(tenant, Decimal('2'))
            providers = [CostProvider(), CostProvider()]
            for state, provider in zip((a, b), providers):
                state.ai_gateway.providers = [provider]
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda state: state.ai_gateway.execute(request(tenant=tenant)), (a, b)))
            self.assertEqual(sorted(result.status.value for result in results), sorted([AIStatus.OK.value, AIStatus.COST_LIMIT.value]))
            self.assertEqual(sum(provider.calls for provider in providers), 1)
            self.assertEqual(b.ai_gateway.ledger.used(tenant), Decimal('1'))
            self.assertEqual(b.ai_gateway.ledger.remaining(tenant), Decimal('1'))
            a.ai_gateway.ledger.set_cap(tenant, Decimal('3'))
            req = request(tenant=tenant)
            self.assertTrue(a.ai_gateway.ledger.begin_attempt(req, 'pg-crashed-cost-run', 0, 'fixture-provider'))
            fresh = create_app(database_url=DSN, env='test').state.campaia
            self.addCleanup(fresh.db.close)
            self.assertEqual(fresh.ai_gateway.ledger.used(tenant), Decimal('1'))
            self.assertEqual(fresh.ai_gateway.ledger.remaining(tenant), Decimal('0'))
            self.assertEqual(fresh.ai_gateway.ledger.report(tenant)['cost_completeness'], 'INCOMPLETE')
            self.assertFalse(fresh.ai_gateway.ledger.begin_attempt(req, 'pg-crashed-cost-run', 0, 'fixture-provider'))
            observation = CostObservation('SIMULATED', Decimal('1'))
            fresh.ai_gateway.ledger.finish_attempt(req, 'pg-crashed-cost-run', 0, observation, 'FIXTURE_OBSERVED')
            fresh.ai_gateway.ledger.finish_attempt(req, 'pg-crashed-cost-run', 0, observation, 'FIXTURE_OBSERVED')
            self.assertEqual(b.ai_gateway.ledger.used(tenant), Decimal('2'))
            self.assertEqual(b.ai_gateway.ledger.remaining(tenant), Decimal('1'))
            identity = a.ai_gateway.ledger._rows(tenant)[0]
            self.assertNotIn('input', identity)
            record_id = a.db.table('ai_cost_journal').rows_for_tenant(tenant)[0][0]
            self.assertIsNone(b.db.table('ai_cost_journal').get_for_tenant(record_id, 'another-tenant'))
            with psycopg.connect(DSN) as conn:
                with self.assertRaises(psycopg.errors.RaiseException):
                    conn.execute("DELETE FROM campaia_runtime.ai_cost_journal")
            with psycopg.connect(DSN) as conn:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute("UPDATE campaia_runtime.ai_cost_caps SET tenant_id = 'another-tenant'")
            self.assertEqual(b.ai_gateway.ledger.used(tenant), Decimal('2'))

    def test_billing_notice_tables_are_immutable_and_tenant_scoped(self):
        a, b = self._states()
        at = datetime.now(timezone.utc)
        record = {'id': 'notice-fixture', 'created_at': at}
        table = a.db.table('billing_notices')
        table.put('notice-fixture', 'tenant-a', record)
        self.assertEqual(b.db.table('billing_notices').get_for_tenant('notice-fixture', 'tenant-a'), record)
        self.assertIsNone(b.db.table('billing_notices').get_for_tenant('notice-fixture', 'tenant-b'))
        with self.assertRaises(Exception):
            table.put('notice-fixture', 'tenant-b', record)
        with psycopg.connect(DSN) as conn:
            with self.assertRaises(psycopg.errors.RaiseException):
                conn.execute("UPDATE campaia_runtime.billing_notices SET tenant_id = 'tenant-b'")
        with psycopg.connect(DSN) as conn:
            with self.assertRaises(psycopg.errors.RaiseException):
                conn.execute("DELETE FROM campaia_runtime.billing_notices")
        reads = a.db.table('billing_notice_reads')
        reads.put('read-fixture', 'tenant-a', {'notice_id': 'notice-fixture', 'user_id': 'reader', 'read_at': at})
        with psycopg.connect(DSN) as conn:
            with self.assertRaises(psycopg.errors.RaiseException):
                conn.execute("DELETE FROM campaia_runtime.billing_notice_reads")
        self.assertIsNone(b.db.table('billing_notice_reads').get_for_tenant('read-fixture', 'tenant-b'))

    def test_unpaid_renewal_withdrawal_fence_recovers_across_connections(self):
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from tests_api.test_helpers import OWNER, with_step_up, unique_idem
        from tests_api.test_anniversary_lifecycle import clock
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'catalog.json'
            plans = json.loads((Path(__file__).parents[1] / 'config/plans.example.json').read_text())
            plans[0]['included_credits'] = 10
            plans[0]['cancellation_mode'] = 'PERIOD_END'
            plans[0]['credit_policy'] = {'version': 'pg-void-v1', 'action_weights': {'strategy': 5},
                'trial_credits': 30, 'trial_max_users': 1, 'trial_max_active_campaigns': 1}
            config.write_text(json.dumps(plans))
            with patch.dict(os.environ, {'CAMPAIA_PLAN_CATALOG_PATH': str(config), 'ASAAS_WEBHOOK_TOKEN': 'pg-void-proof', 'ASAAS_API_KEY': '', 'GEMINI_API_KEY': ''}):
                clients = [TestClient(create_app(database_url=DSN, env='test')) for _ in range(2)]
                a, b = clients
                def post(client, path, body=None):
                    return client.post(path, headers={**with_step_up(OWNER), **unique_idem()}, json=body)
                setup = a.put('/billing/subscription', headers={**with_step_up(OWNER), **unique_idem()},
                    json={'plan_id': plans[0]['plan_id'], 'customer_document': '11144477735'})
                self.assertEqual(setup.status_code, 200, setup.text)
                first = post(a, '/billing/charges', {'competence': 'server-cycle'})
                self.assertEqual(first.status_code, 202, first.text)
                paid = a.post('/webhooks/asaas', headers={'asaas-access-token': 'pg-void-proof'},
                    json={'id': 'pg-void-first-paid', 'event': 'PAYMENT_RECEIVED', 'payment': {
                        'id': first.json()['gateway_charge_id'], 'status': 'RECEIVED', 'value': first.json()['amount']}})
                self.assertEqual(paid.status_code, 200, paid.text)
                sub = a.app.state.campaia.subscriptions['demo-tenant']
                with clock(sub.paid_cycle_schedule.bounds(0)[1]):
                    renewal = post(a, '/billing/charges', {'competence': 'server-cycle'})
                    self.assertEqual(renewal.status_code, 202, renewal.text)
                    self.assertEqual(post(a, '/billing/subscription/cancel', {'immediate': True}).status_code, 200)
                gid = renewal.json()['gateway_charge_id']
                item = next(item for item in b.get('/billing/charges', headers=OWNER).json()['items'] if item['gateway_charge_id'] == gid)
                review = {'fingerprint': item['withdrawal_fingerprint'], 'accept': True}
                self.assertIsNotNone(review['fingerprint'])
                gateway = a.app.state.campaia.billing_gateway
                original = gateway.void_charge
                def uncertain(*args):
                    self.assertFalse(a.app.state.campaia.db.in_transaction)
                    self.assertIsNotNone(b.app.state.campaia.idempotency.get('demo-tenant', 'billing-void-intent:' + item['billing_id']))
                    original(*args)
                    raise TimeoutError('lost delete response')
                with patch.object(gateway, 'void_charge', side_effect=uncertain) as dispatch:
                    self.assertEqual(post(a, f'/billing/charges/{gid}/withdraw', review).status_code, 503)
                self.assertEqual(dispatch.call_count, 1)
                with patch.object(b.app.state.campaia.billing_gateway, 'void_charge', side_effect=AssertionError('No repeat DELETE')):
                    recovered = post(b, f'/billing/charges/{gid}/withdraw', review)
                self.assertEqual(recovered.status_code, 200, recovered.text)
                self.assertEqual(recovered.json()['state'], 'VOID')
                self.assertEqual(a.get('/billing/closure', headers=OWNER).json()['state'], 'NO_CHARGE')
                self.assertEqual(len(a.app.state.campaia.charges.items_for_tenant('demo-tenant')), 2)
                # Refund proof persists across connections without restoring entitlement.
                refunded = a.post('/webhooks/asaas', headers={'asaas-access-token': 'pg-void-proof'},
                    json={'id': 'pg-refund-observation', 'event': 'PAYMENT_REFUNDED', 'payment': {
                        'id': first.json()['gateway_charge_id'], 'status': 'REFUNDED',
                        'value': first.json()['amount'], 'refunds': [
                            {'status': 'DONE', 'value': first.json()['amount']}]}})
                self.assertEqual(refunded.status_code, 200, refunded.text)
                refund_item = next(item for item in b.get('/billing/charges', headers=OWNER).json()['items']
                                   if item['gateway_charge_id'] == first.json()['gateway_charge_id'])
                self.assertEqual(refund_item['gateway_refund_state'], 'FULL_DONE')
                self.assertEqual(Decimal(refund_item['gateway_refund_amount']), Decimal(first.json()['amount']))
                self.assertEqual(b.get('/billing/closure', headers=OWNER).json()['state'], 'RECONCILIATION_REQUIRED')
                self.assertIsNotNone(b.app.state.campaia.idempotency.get('demo-tenant', 'billing-receipt:pg-refund-observation'))


    def test_credit_journal_workers_replay_caps_and_immutable_history(self) -> None:
        from api.credit_store import PersistentCreditLedger
        from campaia_core.credit_ledger import CreditLimitExceeded
        from tests_api.test_credit_ledger import NOW, cycle

        stores = [PersistentCreditLedger(PostgresDatabase(DSN).table("credit_journal"))
                  for _ in range(6)]
        stores[0].decide("a", "open_cycle", cycle=cycle(), at=NOW)
        def reserve(item):
            index, store = item
            try:
                return store.decide("a", "reserve", cycle_id="cycle-1",
                                    operation_id=str(index), action="strategy", at=NOW)
            except CreditLimitExceeded:
                return None
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(reserve, enumerate(stores)))
        self.assertEqual(sum(r is not None for r in results), 2)
        winner = next(r.entry.operation_id for r in results if r)
        with ThreadPoolExecutor(max_workers=6) as pool:
            settled = list(pool.map(lambda store: store.decide(
                "a", "finish", operation_id=winner, kind="SETTLE",
                reference="delivery-1", at=NOW + timedelta(seconds=1)), stores))
        self.assertEqual(sum(not r.replayed for r in settled), 1)
        fresh = PersistentCreditLedger(PostgresDatabase(DSN).table("credit_journal"))
        self.assertEqual(fresh.balance("a", "cycle-1").consumed_credits, 5)
        self.assertEqual(fresh.balance("a", "cycle-1").reserved_credits, 5)
        self.assertEqual(fresh.entries("b"), ())
        with self.assertRaises(Exception):
            with psycopg.connect(DSN) as conn:
                conn.execute("UPDATE campaia_runtime.credit_journal SET tenant_id = 'b'")
        with self.assertRaises(Exception):
            with psycopg.connect(DSN) as conn:
                conn.execute("DELETE FROM campaia_runtime.credit_journal")
        self.assertEqual(len(fresh.entries("a")), 4)

    def test_brand_asset_quota_fence_restart_and_pg_guards(self):
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from tests_support.asset_storage import TestOnlyAssetStorage
        from tests_api.test_brand_assets import png
        from tests_api.test_brand_versions import BODY
        from tests_api.test_helpers import OWNER, OTHER_OWNER, unique_idem
        from campaia_core.asset_storage import AssetStorageError, AssetStorageErrorCode as Code
        from campaia_core.asset_images import normalize_asset_image

        a = TestClient(create_app(database_url=DSN, env="test"))
        b = TestClient(create_app(database_url=DSN, env="test"))
        self.addCleanup(a.app.state.campaia.db.close)
        self.addCleanup(b.app.state.campaia.db.close)
        storage = TestOnlyAssetStorage(max_active_bytes=len(normalize_asset_image(png()).data))
        for client in (a, b):
            client.app.state.campaia.asset_storage = storage
        profile = a.post("/brand-profiles", headers={**OWNER, **unique_idem()}, json=BODY).json()["id"]
        base = "/brand-profiles/" + profile + "/assets"
        def upload(client, headers):
            return client.post(base + "?kind=LOGO",
                headers={**headers, "Content-Type": "application/octet-stream"}, content=png())
        headers = {**OWNER, **unique_idem()}
        original = storage.upload_once
        def lost(expected, data):
            original(expected, data)
            raise AssetStorageError(Code.UNCERTAIN)
        with patch.object(storage, "upload_once", side_effect=lost):
            pending = upload(a, headers)
        self.assertEqual(pending.status_code, 202, pending.text)
        self.assertEqual(upload(b, {**OWNER, **unique_idem()}).status_code, 409)
        ready = upload(b, headers)
        self.assertEqual(ready.status_code, 201, ready.text)
        identity = ready.json()["id"]
        self.assertEqual(storage.calls.count("POST"), 1)
        self.assertEqual(b.get(base, headers=OTHER_OWNER).status_code, 404)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(DSN) as conn:
                conn.execute("UPDATE campaia_runtime.brand_assets SET tenant_id=%s WHERE id=%s", ("foreign", identity))
        with self.assertRaises(psycopg.errors.RaiseException):
            with psycopg.connect(DSN) as conn:
                conn.execute("UPDATE campaia_runtime.brand_assets SET data=jsonb_set(data, '{kind}', %s::jsonb) WHERE id=%s", ('"REFERENCE"', identity))
        with self.assertRaises(psycopg.errors.RaiseException):
            with psycopg.connect(DSN) as conn:
                conn.execute("UPDATE campaia_runtime.brand_assets SET data=jsonb_set(data, '{generation}', %s::jsonb) WHERE id=%s", ('"999999"', identity))
        delete_headers = {**OWNER, **unique_idem()}
        self.assertEqual(a.delete(base + "/" + identity, headers=delete_headers).status_code, 200)
        self.assertEqual(b.delete(base + "/" + identity, headers=delete_headers).status_code, 200)
        self.assertEqual(storage.calls.count("DELETE"), 1)
        self.assertEqual(b.app.state.campaia.asset_store.usage("demo-tenant"), 0)
        with self.assertRaises(psycopg.errors.RaiseException):
            with psycopg.connect(DSN) as conn:
                conn.execute("UPDATE campaia_runtime.brand_assets SET data=jsonb_set(data, '{status}', %s::jsonb) WHERE id=%s", ('"READY"', identity))
        with self.assertRaises(psycopg.errors.RaiseException):
            with psycopg.connect(DSN) as conn:
                conn.execute("DELETE FROM campaia_runtime.brand_assets WHERE id=%s", (identity,))

    def test_brand_asset_concurrent_pg_quota_serializes_different_intents(self):
        from tests_support.asset_storage import TestOnlyAssetStorage
        from tests_api.test_brand_assets import png
        from campaia_core.asset_images import normalize_asset_image
        a, b = self._states()
        self.addCleanup(a.db.close)
        self.addCleanup(b.db.close)
        image = normalize_asset_image(png())
        storage = TestOnlyAssetStorage(max_active_bytes=len(image.data))
        barrier = threading.Barrier(2)
        from api.errors import ApiError
        def reserve(state, key):
            barrier.wait()
            try:
                record, dispatch = state.asset_store.reserve(state.tokens["demo-owner-token"],
                    "bp-pg-test", key, "input-digest", "LOGO", image, storage)
                return record["asset_id"], dispatch
            except ApiError as error:
                return error.code, False
        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(reserve, a, "pg-asset-quota-a")
            two = pool.submit(reserve, b, "pg-asset-quota-b")
            results = [one.result(timeout=10), two.result(timeout=10)]
        self.assertEqual(sum(result[1] for result in results), 1)
        self.assertIn(("ASSET_QUOTA_EXCEEDED", False), results)
        self.assertEqual(b.asset_store.usage("demo-tenant"), len(image.data))
        self.assertEqual(len(a.asset_store.rows("demo-tenant")), 1)

    def test_persistent_session_switch_is_atomic_and_serializes_revocation(self):
        from dataclasses import replace
        from unittest.mock import patch
        a, b = self._states()
        self.addCleanup(a.db.close)
        self.addCleanup(b.db.close)
        first = a.tokens["demo-owner-token"]
        second = replace(first, tenant_id="other-tenant", user_id="other-member")
        def create():
            return a.sessions.create(first, now=datetime.now(timezone.utc),
                available_principals=(first, second), subject="same-subject")
        record = create()
        switched = a.sessions.switch_principal(record.session_id, second)
        self.assertEqual(switched.csrf_secret, record.csrf_secret)
        self.assertEqual(b.sessions.get(record.session_id).principal, second)
        self.assertIsNone(b.db.table("sessions").get_for_tenant(record.session_id, first.tenant_id))
        self.assertIsNone(a.sessions.switch_principal(record.session_id, replace(second, user_id="foreign")))
        with patch.object(a.sessions._table, "put", side_effect=RuntimeError("session insert failed")):
            with self.assertRaisesRegex(RuntimeError, "session insert failed"):
                a.sessions.switch_principal(record.session_id, first)
        self.assertEqual(b.sessions.get(record.session_id).principal, second)
        from campaia_core.errors import TenantIsolationViolation
        # Sessions are intentionally excluded from the SQL tenant trigger (migration 002).
        # RecordTable still forbids arbitrary rehome; only the explicit switch may relocate.
        with self.assertRaises(TenantIsolationViolation):
            b.db.table("sessions").put(record.session_id, "foreign", b.sessions.get(record.session_id))
        for revoke in ("invalidate", "invalidate_membership"):
            candidate = create()
            with ThreadPoolExecutor(max_workers=2) as pool:
                switch = pool.submit(a.sessions.switch_principal, candidate.session_id, second)
                revoked = pool.submit(getattr(b.sessions, revoke),
                    candidate.session_id if revoke == "invalidate" else first.user_id)
                switch.result(timeout=10)
                revoked.result(timeout=10)
            self.assertIsNone(a.sessions.get(candidate.session_id))

    def test_campaign_brand_snapshot_survives_other_worker_edits_and_restart(self):
        from starlette.testclient import TestClient
        from tests_api.test_brand_versions import BODY
        from tests_api.test_campaign_brand import BRIEF
        from tests_api.test_helpers import OWNER, OTHER_OWNER, unique_idem
        a = TestClient(create_app(database_url=DSN, env="test"))
        b = TestClient(create_app(database_url=DSN, env="test"))
        self.addCleanup(a.app.state.campaia.db.close)
        self.addCleanup(b.app.state.campaia.db.close)
        profile = a.post("/brand-profiles", headers={**OWNER, **unique_idem()}, json=BODY).json()
        selection = {"brand_profile_id": profile["id"], "expected_version": 1, "asset_ids": []}
        headers = {**OWNER, **unique_idem()}
        body = {**BRIEF, "brand_selection": selection}
        created = a.post("/briefs", headers=headers, json=body)
        self.assertEqual(created.status_code, 202, created.text)
        snapshot = created.json()["brief"]["brand_snapshot_v1"]
        self.assertEqual(snapshot["profile"], profile)
        self.assertEqual(b.put("/brand-profiles/" + profile["id"], headers={**OWNER, **unique_idem()},
            json={**BODY, "expected_version": 1, "tone": "novo tom"}).status_code, 200)
        self.assertEqual(b.post("/briefs", headers=headers, json=body).json(), created.json())
        current = b.get("/campaigns/" + created.json()["id"], headers=OWNER)
        self.assertEqual(current.json()["brief"]["brand_snapshot_v1"], snapshot)
        self.assertEqual(b.get("/campaigns/" + created.json()["id"], headers=OTHER_OWNER).status_code, 404)
        self.assertEqual(b.post("/briefs", headers={**OWNER, **unique_idem()}, json=body).status_code, 409)

    def test_campaign_brand_selection_serializes_with_concurrent_profile_edit(self):
        from starlette.testclient import TestClient
        from tests_api.test_brand_versions import BODY
        from tests_api.test_campaign_brand import BRIEF
        from tests_api.test_helpers import OWNER, unique_idem
        a = TestClient(create_app(database_url=DSN, env="test"))
        b = TestClient(create_app(database_url=DSN, env="test"))
        self.addCleanup(a.app.state.campaia.db.close)
        self.addCleanup(b.app.state.campaia.db.close)
        profile = a.post("/brand-profiles", headers={**OWNER, **unique_idem()}, json=BODY).json()
        gate = threading.Barrier(2)
        def create():
            gate.wait()
            return a.post("/briefs", headers={**OWNER, **unique_idem()}, json={
                **BRIEF, "brand_selection": {"brand_profile_id": profile["id"], "expected_version": 1}})
        def edit():
            gate.wait()
            return b.put("/brand-profiles/" + profile["id"], headers={**OWNER, **unique_idem()},
                json={**BODY, "expected_version": 1, "tone": "concorrente"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            created, edited = pool.submit(create), pool.submit(edit)
            result, changed = created.result(timeout=10), edited.result(timeout=10)
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertIn(result.status_code, (202, 409), result.text)
        if result.status_code == 202:
            self.assertEqual(result.json()["brief"]["brand_snapshot_v1"]["profile"], profile)
        else:
            self.assertEqual(result.json()["code"], "BRAND_VERSION_CHANGED")
            self.assertEqual(a.app.state.campaia.campaigns.list_for_tenant("demo-tenant"), [])


    def _creative_clients(self):
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from tests_support.creative_ai import install_test_creative_provider
        from tests_api.test_creative_proposals import BRIEF
        from tests_api.test_helpers import OWNER, with_step_up, unique_idem
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = Path(directory.name) / "catalog.json"
        plans = json.loads((Path(__file__).parents[1] / "config/plans.example.json").read_text())
        plans[0]["credit_policy"] = {"version": "pg-creative-v1",
            "action_weights": {"strategy": 5, "copy": 3, "audience": 2, "revision": 1},
            "trial_credits": 30, "trial_max_users": 1, "trial_max_active_campaigns": 1}
        config.write_text(json.dumps(plans))
        environment = patch.dict(os.environ, {"CAMPAIA_PLAN_CATALOG_PATH": str(config),
                                              "ASAAS_API_KEY": "", "GEMINI_API_KEY": ""})
        environment.start()
        self.addCleanup(environment.stop)
        clients = [TestClient(create_app(database_url=DSN, env="test")) for _ in range(2)]
        for client in clients:
            self.addCleanup(client.app.state.campaia.db.close)
            install_test_creative_provider(client.app.state.campaia)
        created = clients[0].post("/briefs", headers={**OWNER, **unique_idem()}, json=BRIEF)
        self.assertEqual(created.status_code, 202, created.text)
        campaign = created.json()["id"]
        result = clients[0].post("/campaigns/" + campaign + "/plan/regenerate",
                                headers={**OWNER, **unique_idem()}, json={})
        self.assertEqual(result.status_code, 202, result.text)
        trial = clients[0].put("/billing/subscription",
            headers={**with_step_up(OWNER), **unique_idem()}, json={
                "plan_id": plans[0]["plan_id"], "customer_document": "11144477735", "start_trial": True})
        self.assertEqual(trial.status_code, 200, trial.text)
        return clients, campaign

    def test_creative_delivery_settlement_rollback_restart_and_immutable_isolation(self):
        from unittest.mock import patch
        from api.errors import ApiError
        from campaia_core.errors import TenantIsolationViolation
        from tests_api.test_helpers import OWNER, OTHER_OWNER, unique_idem
        clients, campaign = self._creative_clients()
        a, b = clients
        endpoint = "/campaigns/" + campaign + "/proposals/copy"
        quote = a.get(endpoint + "/quote", headers=OWNER).json()
        body = {"expected_plan_version": 1, "channel": "GOOGLE_ADS", "offer": "Oferta",
            "tone": "claro", "variants": 5, "credit_confirmation": {
                key: quote[key] for key in ("cycle_id", "policy_version", "credits", "extra_amount")}}
        repository = a.app.state.campaia.creative_proposals
        original_append = repository.append
        def rollback_after_row(*args, **kwargs):
            original_append(*args, **kwargs)
            raise ApiError("TEST_ROLLBACK", "Falha conhecida de teste.", status_code=422)
        with patch.object(repository, "append", side_effect=rollback_after_row):
            failed = a.post(endpoint, headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(failed.status_code, 422, failed.text)
        self.assertEqual(b.get(endpoint, headers=OWNER).json()["items"], [])
        self.assertEqual(b.get("/campaigns/" + campaign + "/plan", headers=OWNER).json()["plan_version"], 1)
        self.assertEqual(b.get("/billing/usage", headers=OWNER).json()["balance"]["included_available"], 30)
        headers = {**OWNER, **unique_idem()}
        delivered = a.post(endpoint, headers=headers, json=body)
        self.assertEqual(delivered.status_code, 201, delivered.text)
        replay = b.post(endpoint, headers=headers, json=body)
        self.assertEqual(replay.json(), delivered.json())
        self.assertEqual(b.app.state.campaia.ai_provider.calls, 0)
        self.assertEqual(b.get("/billing/usage", headers=OWNER).json()["balance"]["included_available"], 27)
        self.assertEqual(len(b.get(endpoint, headers=OWNER).json()["items"]), 1)
        self.assertEqual(b.get(endpoint, headers=OTHER_OWNER).status_code, 404)
        table = b.app.state.campaia.db.table("creative_proposals")
        identity = delivered.json()["id"]
        self.assertIsNone(table.get_for_tenant(identity, "other-tenant"))
        with self.assertRaises(TenantIsolationViolation):
            table.put(identity, "other-tenant", {"tenant_id": "other-tenant"})
        for statement in (
            "UPDATE campaia_runtime.creative_proposals SET data = data WHERE id = %s",
            "DELETE FROM campaia_runtime.creative_proposals WHERE id = %s",
        ):
            with self.assertRaises(psycopg.errors.RaiseException):
                with psycopg.connect(DSN) as connection:
                    connection.execute(statement, (identity,))

    def test_two_creative_workers_cannot_deliver_two_batches_for_one_plan_version(self):
        from unittest.mock import patch
        from tests_api.test_helpers import OWNER, unique_idem
        clients, campaign = self._creative_clients()
        endpoint = "/campaigns/" + campaign + "/proposals/copy"
        quote = clients[0].get(endpoint + "/quote", headers=OWNER).json()
        body = {"expected_plan_version": 1, "channel": "GOOGLE_ADS", "offer": "Oferta",
            "tone": "claro", "variants": 5, "credit_confirmation": {
                key: quote[key] for key in ("cycle_id", "policy_version", "credits", "extra_amount")}}
        gate = threading.Barrier(2)
        def blocked(original):
            def run(*args, **kwargs):
                gate.wait(timeout=10)
                return original(*args, **kwargs)
            return run
        runners = [client.app.state.campaia.agent_runner for client in clients]
        with patch.object(runners[0], "run", side_effect=blocked(runners[0].run)), \
             patch.object(runners[1], "run", side_effect=blocked(runners[1].run)):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(client.post, endpoint, headers={**OWNER, **unique_idem()}, json=body)
                           for client in clients]
                results = [future.result(timeout=20) for future in futures]
        self.assertEqual(sorted(result.status_code for result in results), [201, 409],
                         [result.text for result in results])
        self.assertEqual(len(clients[1].get(endpoint, headers=OWNER).json()["items"]), 1)
        usage = clients[1].get("/billing/usage", headers=OWNER).json()["balance"]
        self.assertEqual(usage["included_available"], 27)
        self.assertEqual(usage["reserved_credits"], 0)


    def _copy_revision_clients(self):
        from tests_api.test_helpers import OWNER, unique_idem
        clients, campaign = self._creative_clients()
        base = "/campaigns/" + campaign + "/proposals/copy"
        fields = ("cycle_id", "policy_version", "credits", "extra_amount")
        quote = clients[0].get(base + "/quote", headers=OWNER).json()
        result = clients[0].post(base, headers={**OWNER, **unique_idem()}, json={
            "expected_plan_version": 1, "channel": "GOOGLE_ADS", "offer": "Oferta", "tone": "claro",
            "variants": 5, "credit_confirmation": {key: quote[key] for key in fields}})
        self.assertEqual(result.status_code, 201, result.text)
        parent = result.json()
        endpoint = base + "/" + parent["id"] + "/revisions"
        quote = clients[0].get(endpoint + "/quote", headers=OWNER).json()
        self.assertEqual(quote["credits"], 1)
        body = {"expected_plan_version": 2, "channel": "GOOGLE_ADS", "variant_index": 1,
                "instructions": "Convite mais direto", "credit_confirmation": {key: quote[key] for key in fields}}
        return clients, base, endpoint, parent, body

    def test_copy_revision_rollback_and_replay_preserve_original_batch_and_one_credit(self):
        from unittest.mock import patch
        from api.errors import ApiError
        from tests_api.test_helpers import OWNER, unique_idem
        clients, base, endpoint, parent, body = self._copy_revision_clients()
        a, b = clients
        repository = a.app.state.campaia.creative_proposals
        original = repository.append
        def rollback_after_write(*args, **kwargs):
            original(*args, **kwargs)
            raise ApiError("TEST_ROLLBACK", "Falha conhecida de teste.", status_code=422)
        with patch.object(repository, "append", side_effect=rollback_after_write):
            rejected = a.post(endpoint, headers={**OWNER, **unique_idem()}, json=body)
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(len(b.get(base, headers=OWNER).json()["items"]), 1)
        self.assertEqual(b.get("/billing/usage", headers=OWNER).json()["balance"]["included_available"], 27)
        headers = {**OWNER, **unique_idem()}
        saved = a.post(endpoint, headers=headers, json=body)
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(b.post(endpoint, headers=headers, json=body).json(), saved.json())
        self.assertEqual(b.app.state.campaia.ai_provider.calls, 0)
        self.assertEqual(b.get("/billing/usage", headers=OWNER).json()["balance"]["included_available"], 26)
        history = b.get(base, headers=OWNER).json()["items"]
        self.assertEqual(history[1]["output"], parent["output"])
        self.assertEqual(history[0]["output"]["variacoes"][0], parent["output"]["variacoes"][0])
        self.assertNotEqual(history[0]["output"]["variacoes"][1], parent["output"]["variacoes"][1])

    def test_copy_revision_workers_have_one_winner_and_release_losing_reservation(self):
        from unittest.mock import patch
        from tests_api.test_helpers import OWNER, unique_idem
        clients, base, endpoint, _parent, body = self._copy_revision_clients()
        gate = threading.Barrier(2)
        def blocked(original):
            def run(*args, **kwargs):
                gate.wait(timeout=10)
                return original(*args, **kwargs)
            return run
        runners = [client.app.state.campaia.agent_runner for client in clients]
        with patch.object(runners[0], "run", side_effect=blocked(runners[0].run)), \
             patch.object(runners[1], "run", side_effect=blocked(runners[1].run)):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(client.post, endpoint, headers={**OWNER, **unique_idem()}, json=body)
                           for client in clients]
                results = [future.result(timeout=20) for future in futures]
        self.assertEqual(sorted(result.status_code for result in results), [201, 409],
                         [result.text for result in results])
        balance = clients[1].get("/billing/usage", headers=OWNER).json()["balance"]
        self.assertEqual(balance["included_available"], 26)
        self.assertEqual(balance["reserved_credits"], 0)
        self.assertEqual(len(clients[1].get(base, headers=OWNER).json()["items"]), 2)


    def test_approval_review_finality_prevents_rearming_applied_budget_across_workers(self):
        from starlette.testclient import TestClient
        from tests_api.test_helpers import OWNER, APPROVER, FINANCE, create_campaign, unique_idem, with_step_up
        a = TestClient(create_app(database_url=DSN, env="test"))
        b = TestClient(create_app(database_url=DSN, env="test"))
        self.addCleanup(a.app.state.campaia.db.close)
        self.addCleanup(b.app.state.campaia.db.close)
        campaign = create_campaign(a)["id"]
        identity = a.post("/approvals", headers={**OWNER, **unique_idem()},
                         json={"campaign_id": campaign, "kind": "BUDGET_CHANGE"}).json()["id"]
        headers = {**with_step_up(APPROVER), **unique_idem()}
        endpoint = "/approvals/" + identity + "/decision"
        voted = a.post(endpoint, headers=headers, json={"decision": "APPROVE"})
        self.assertEqual(voted.status_code, 200, voted.text)
        applied = b.patch("/campaigns/" + campaign + "/budget",
            headers={**with_step_up(OWNER), **unique_idem()}, json={"approval_id": identity, "new_daily_cap": "550"})
        self.assertEqual(applied.status_code, 202, applied.text)
        denied = a.post(endpoint, headers={**with_step_up(FINANCE), **unique_idem()}, json={"decision": "APPROVE"})
        self.assertEqual(denied.status_code, 409, denied.text)
        self.assertEqual(denied.json()["code"], "APPROVAL_FINALIZED")
        self.assertEqual(b.post(endpoint, headers=headers, json={"decision": "APPROVE"}).json(), voted.json())
        self.assertEqual(b.app.state.campaia.approvals.get("demo-tenant", identity).status, "APPLIED")
        rebind = b.post(endpoint, headers=headers, json={"decision": "REJECT"})
        self.assertEqual(rebind.status_code, 409, rebind.text)

    def test_concurrent_conflicting_approval_reviews_have_one_terminal_winner_in_postgres(self):
        from starlette.testclient import TestClient
        from tests_api.test_helpers import OWNER, APPROVER, FINANCE, create_campaign, unique_idem, with_step_up
        clients = [TestClient(create_app(database_url=DSN, env="test")) for _ in range(2)]
        for client in clients:
            self.addCleanup(client.app.state.campaia.db.close)
        campaign = create_campaign(clients[0])["id"]
        identity = clients[0].post("/approvals", headers={**OWNER, **unique_idem()},
            json={"campaign_id": campaign, "kind": "PUBLISH"}).json()["id"]
        gate = threading.Barrier(2)
        def vote(client, actor, decision):
            gate.wait()
            return client.post("/approvals/" + identity + "/decision",
                headers={**with_step_up(actor), **unique_idem()}, json={"decision": decision})
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(vote, clients[0], APPROVER, "APPROVE")
            b = pool.submit(vote, clients[1], FINANCE, "REJECT")
            results = [a.result(timeout=10), b.result(timeout=10)]
        self.assertEqual(sorted(result.status_code for result in results), [200, 409],
                         [result.text for result in results])
        events = [entry for entry in clients[1].app.state.campaia.audit.list_for_tenant("demo-tenant")
                  if entry.action in ("APPROVAL_APPROVE", "APPROVAL_REJECT")]
        self.assertEqual(len(events), 1)

    def test_00_migration_up_down_up_is_reversible_and_covers_current_stores(self) -> None:
        self.assertEqual(
            set(self.runner.applied_versions()),
            {
                "001_runtime_store_schema",
                "002_tenant_isolation_guard",
                "003_distributed_rate_limit",
                "004_billing_persistence",
                "005_credit_journal",
                "006_billing_notices",
                "007_ai_cost_evidence",
                "008_brand_assets",
                "009_creative_proposals",
            },
        )
        self.assertTrue(RUNTIME_TABLES.issubset(self._runtime_tables()))

        self.assertEqual(
            self.runner.rollback_all(),
            [
                "009_creative_proposals",
                "008_brand_assets",
                "007_ai_cost_evidence",
                "006_billing_notices",
                "005_credit_journal",
                "004_billing_persistence",
                "003_distributed_rate_limit",
                "002_tenant_isolation_guard",
                "001_runtime_store_schema",
            ],
        )
        self.assertTrue(RUNTIME_TABLES.isdisjoint(self._runtime_tables()))

        self.runner.apply_all()
        self.assertTrue(RUNTIME_TABLES.issubset(self._runtime_tables()))

    def test_database_rejects_cross_tenant_rehome_and_scopes_reads(self) -> None:
        table = PostgresDatabase(DSN).table("brand_profiles")
        table.put("shared-id", "tenant-a", {"value": "a"})

        with self.assertRaises(Exception):
            table.put("shared-id", "tenant-b", {"value": "b"})

        self.assertEqual(
            table.get_for_tenant("shared-id", "tenant-a"),
            {"value": "a"},
        )
        self.assertIsNone(table.get_for_tenant("shared-id", "tenant-b"))
        self.assertFalse(table.delete_for_tenant("shared-id", "tenant-b"))

        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(DSN) as conn:
                conn.execute(
                    "UPDATE campaia_runtime.brand_profiles "
                    "SET tenant_id = %s WHERE id = %s",
                    ("tenant-b", "shared-id"),
                )

    def test_billing_tables_reject_cross_tenant_rehome(self) -> None:
        table = PostgresDatabase(DSN).table("billing_charges")
        table.put(
            "pay-shared",
            "tenant-a",
            {"tenant_id": "tenant-a", "billing_id": "bill-a"},
        )

        with self.assertRaises(Exception):
            table.put(
                "pay-shared",
                "tenant-b",
                {"tenant_id": "tenant-b", "billing_id": "bill-b"},
            )

        self.assertIsNotNone(table.get_for_tenant("pay-shared", "tenant-a"))
        self.assertIsNone(table.get_for_tenant("pay-shared", "tenant-b"))

        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(DSN) as conn:
                conn.execute(
                    "UPDATE campaia_runtime.billing_charges "
                    "SET tenant_id = %s WHERE id = %s",
                    ("tenant-b", "pay-shared"),
                )

    def test_billing_history_cross_worker_replay_and_webhook_observation(self) -> None:
        from pathlib import Path
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from tests_api.test_helpers import OWNER, OTHER_OWNER, with_step_up
        catalog = str(Path(__file__).resolve().parent.parent / "config" / "plans.example.json")
        with patch.dict(os.environ, {"CAMPAIA_PLAN_CATALOG_PATH": catalog,
                                     "ASAAS_WEBHOOK_TOKEN": "pg-history-test"}):
            a = TestClient(create_app(database_url=DSN, env="test"))
            b = TestClient(create_app(database_url=DSN, env="test"))
            response = a.put("/billing/subscription",
                headers={**with_step_up(OWNER), "Idempotency-Key": "pg-history-subscription"},
                json={"plan_id": "exemplo-essencial", "customer_document": "11144477735"})
            self.assertEqual(response.status_code, 200, response.text)
            def create(args):
                client, key = args
                return client.post("/billing/charges",
                    headers={**with_step_up(OWNER), "Idempotency-Key": key},
                    json={"competence": "2026-10"})
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(create, [(a, "pg-history-worker-one"),
                                                  (b, "pg-history-worker-two")]))
            for result in results:
                self.assertEqual(result.status_code, 202, result.text)
            key = results[0].json()["gateway_charge_id"]
            self.assertEqual(results[1].json()["gateway_charge_id"], key)
            items = b.get("/billing/charges", headers=OWNER).json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["gateway_mode"], "SIMULATOR")
            self.assertEqual(b.get("/billing/charges", headers=OTHER_OWNER).json()["items"], [])
            self.assertEqual(b.get("/billing/charges?cursor=" + key, headers=OTHER_OWNER).status_code, 422)
            event = a.post("/webhooks/asaas", headers={"asaas-access-token": "pg-history-test"},
                json={"id": "evt-pg-history", "event": "PAYMENT_RECEIVED",
                      "payment": {"id": key, "status": "RECEIVED"}})
            self.assertEqual(event.status_code, 200, event.text)
            refreshed = b.get("/billing/charges", headers=OWNER).json()["items"][0]
            self.assertEqual(refreshed["gateway_status"], "CONFIRMED")
            self.assertEqual(refreshed["status_source"], "WEBHOOK")
            self.assertEqual(refreshed["gateway_mode"], "SIMULATOR")

    def test_initial_billing_entry_is_create_only_across_workers(self) -> None:
        from pathlib import Path
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from tests_api.test_helpers import OWNER, OTHER_OWNER, with_step_up
        catalog = str(Path(__file__).resolve().parent.parent / "config" / "plans.example.json")
        with patch.dict(os.environ, {"CAMPAIA_PLAN_CATALOG_PATH": catalog}):
            clients = [TestClient(create_app(database_url=DSN, env="test")) for _ in range(2)]
            plan = clients[0].get("/billing/plans", headers=OWNER).json()["items"][0]
            payload = {"plan_id": plan["plan_id"], "customer_document": "11144477735",
                       "start_trial": True, "initial_only": True,
                       "expected_plan_fingerprint": plan["fingerprint"]}
            def create(args):
                client, key = args
                return client.put("/billing/subscription", json=payload,
                    headers={**with_step_up(OWNER), "Idempotency-Key": key})
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(create, [(clients[0], "pg-initial-worker-one"),
                                                  (clients[1], "pg-initial-worker-two")]))
            self.assertEqual(sorted(result.status_code for result in results), [200, 409])
            winner = next(result.json() for result in results if result.status_code == 200)
            self.assertEqual(clients[1].get("/billing/subscription", headers=OWNER).json(), winner)
            self.assertEqual(winner["status"], "TRIAL")
            self.assertEqual(clients[0].get("/billing/subscription", headers=OTHER_OWNER).status_code, 404)
            self.assertEqual(clients[0].get("/billing/charges", headers=OWNER).json()["items"], [])

    def test_sessions_are_explicit_pre_tenant_exception_to_rehome_trigger(self) -> None:
        with psycopg.connect(DSN) as conn:
            triggers = {
                row[0]
                for row in conn.execute(
                    "SELECT trigger_name FROM information_schema.triggers "
                    "WHERE event_object_schema = %s AND event_object_table = %s",
                    (RUNTIME_SCHEMA, "sessions"),
                ).fetchall()
            }
        self.assertNotIn("sessions_tenant_immutable", triggers)

    def test_two_independent_app_instances_share_session_and_revocation(self) -> None:
        a, b = self._states()
        principal = a.tokens["demo-owner-token"]
        session = a.sessions.create(
            principal,
            now=datetime.now(timezone.utc),
            available_principals=(principal,),
            subject="postgres-shared-subject",
        )
        seen = b.sessions.get(session.session_id)
        self.assertIsNotNone(seen)
        self.assertEqual(seen.principal.tenant_id, principal.tenant_id)

        b.sessions.invalidate(session.session_id)
        self.assertIsNone(a.sessions.get(session.session_id))

    def test_cross_tenant_repository_lookup_fails_closed(self) -> None:
        a, b = self._states()
        profile = a.brand_profiles.create(
            "tenant-a",
            name="A",
            tone="preciso",
            colors=[],
            differentiators=[],
            restrictions=[],
        )
        self.assertIsNone(
            b.brand_profiles.get("tenant-b", profile.brand_profile_id)
        )
        self.assertIsNotNone(
            b.brand_profiles.get("tenant-a", profile.brand_profile_id)
        )

    def test_transaction_rollback_is_visible_from_another_connection(self) -> None:
        a, b = self._states()

        def failing():
            a.audit.append(
                tenant_id="demo-tenant",
                actor="postgres-test",
                action="PG_SHOULD_ROLL_BACK",
                target="rollback",
            )
            raise RuntimeError("injected postgres rollback")

        with self.assertRaisesRegex(RuntimeError, "injected postgres rollback"):
            a.idempotency.execute(
                "demo-tenant",
                "http:pg:rollback-key",
                failing,
            )

        self.assertFalse(
            any(
                event.action == "PG_SHOULD_ROLL_BACK"
                for event in b.audit.list_for_tenant("demo-tenant")
            )
        )
        self.assertIsNone(
            b.idempotency.get("demo-tenant", "http:pg:rollback-key")
        )

    def test_same_idempotency_key_is_exactly_once_across_connections(self) -> None:
        a, b = self._states()
        started = threading.Barrier(2)
        executed: list[str] = []
        executed_lock = threading.Lock()

        def run(state, label):
            started.wait()

            def operation():
                with executed_lock:
                    executed.append(label)
                time.sleep(0.15)
                state.audit.append(
                    tenant_id="demo-tenant",
                    actor=label,
                    action="PG_EXACTLY_ONCE",
                    target="same-key",
                )
                return {"winner": label}

            return state.idempotency.execute(
                "demo-tenant",
                "http:pg:concurrent-idempotency",
                operation,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, a, "a")
            second = pool.submit(run, b, "b")
            results = [first.result(timeout=10), second.result(timeout=10)]

        self.assertEqual(len(executed), 1)
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(result[1] for result in results), [False, True])

        events = [
            e
            for e in a.audit.list_for_tenant("demo-tenant")
            if e.action == "PG_EXACTLY_ONCE"
        ]
        self.assertEqual(len(events), 1)

    def test_different_idempotency_keys_same_tenant_are_serialized(self) -> None:
        a, b = self._states()
        barrier = threading.Barrier(2)
        guard = threading.Lock()
        active = 0
        max_active = 0

        def run(state, key):
            nonlocal active, max_active
            barrier.wait()

            def operation():
                nonlocal active, max_active
                with guard:
                    active += 1
                    max_active = max(max_active, active)
                time.sleep(0.12)
                with guard:
                    active -= 1
                return {"key": key}

            return state.idempotency.execute("demo-tenant", key, operation)

        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(run, a, "http:pg:tenant-lock-a")
            two = pool.submit(run, b, "http:pg:tenant-lock-b")
            one.result(timeout=10)
            two.result(timeout=10)

        self.assertEqual(max_active, 1)

    def test_same_idempotency_key_is_exactly_once_across_spawned_processes(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        start_event = ctx.Event()
        result_queue = ctx.Queue()
        executed_queue = ctx.Queue()
        processes = [
            ctx.Process(
                target=_process_idempotency_worker,
                args=(DSN, label, start_event, result_queue, executed_queue),
            )
            for label in ("proc-a", "proc-b")
        ]
        for process in processes:
            process.start()
        start_event.set()
        for process in processes:
            process.join(timeout=15)
            self.assertEqual(process.exitcode, 0)

        results = [result_queue.get(timeout=5) for _ in processes]
        self.assertTrue(all(item[0] == "ok" for item in results), results)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(sorted(item[2] for item in results), [False, True])

        executed = [executed_queue.get(timeout=5)]
        with self.assertRaises(queue.Empty):
            executed_queue.get(timeout=0.25)
        self.assertEqual(len(executed), 1)

        state = create_app(database_url=DSN, env="test").state.campaia
        events = [
            event
            for event in state.audit.list_for_tenant("demo-tenant")
            if event.action == "PG_PROCESS_EXACTLY_ONCE"
        ]
        self.assertEqual(len(events), 1)

    def test_gate_g3_two_simultaneous_processes_share_required_state(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        ready_event = ctx.Event()
        done_event = ctx.Event()
        ids_queue = ctx.Queue()
        result_queue = ctx.Queue()

        writer = ctx.Process(
            target=_g3_state_writer,
            args=(DSN, ready_event, done_event, ids_queue),
        )
        writer.start()
        self.assertTrue(ready_event.wait(timeout=10))
        ids = ids_queue.get(timeout=5)

        reader = ctx.Process(
            target=_g3_state_reader,
            args=(DSN, ready_event, done_event, ids, result_queue),
        )
        reader.start()
        reader.join(timeout=15)
        self.assertEqual(reader.exitcode, 0)
        self.assertEqual(
            result_queue.get(timeout=5),
            ("ok", True, True, True, True),
        )

        done_event.set()
        writer.join(timeout=15)
        self.assertEqual(writer.exitcode, 0)

        state = create_app(database_url=DSN, env="test").state.campaia
        self.assertIsNone(state.sessions.get(ids[0]))
        self.assertIsNotNone(state.approvals.get("demo-tenant", ids[1]))
        self.assertIsNone(state.approvals.get("other-tenant", ids[1]))

    def test_process_crash_rolls_back_and_same_key_retries_once(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        ready_event = ctx.Event()
        crashed = ctx.Process(
            target=_g3_crash_holder,
            args=(DSN, ready_event),
        )
        crashed.start()
        self.assertTrue(ready_event.wait(timeout=10))
        crashed.terminate()
        crashed.join(timeout=15)
        self.assertNotEqual(crashed.exitcode, 0)

        state = create_app(database_url=DSN, env="test").state.campaia
        self.assertIsNone(
            state.idempotency.get("demo-tenant", "http:g3:crash-replay")
        )
        before = [
            event
            for event in state.audit.list_for_tenant("demo-tenant")
            if event.action == "G3_CRASH_REPLAY"
        ]
        self.assertEqual(before, [])

        def retry_operation():
            state.audit.append(
                tenant_id="demo-tenant",
                actor="retry-process",
                action="G3_CRASH_REPLAY",
                target="crash-key",
            )
            return {"status": "committed"}

        result, replay = state.idempotency.execute(
            "demo-tenant",
            "http:g3:crash-replay",
            retry_operation,
        )
        self.assertEqual(result, {"status": "committed"})
        self.assertFalse(replay)

        after = [
            event
            for event in state.audit.list_for_tenant("demo-tenant")
            if event.action == "G3_CRASH_REPLAY"
        ]
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0].actor, "retry-process")

    def test_rate_limiter_is_shared_across_independent_app_instances(self) -> None:
        a, b = self._states()
        now = datetime.now(timezone.utc)
        accepted = 0
        for index in range(61):
            limiter = (
                a.asaas_webhook_rate_limiter
                if index % 2 == 0
                else b.asaas_webhook_rate_limiter
            )
            accepted += int(limiter.allow("198.51.100.24", now=now))
        self.assertEqual(accepted, 60)

        with psycopg.connect(DSN) as conn:
            rows = conn.execute(
                f"SELECT key_hash, request_count "
                f"FROM {RUNTIME_SCHEMA}.rate_limit_windows "
                "WHERE scope = %s",
                ("asaas-webhook",),
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0][0], "198.51.100.24")
        self.assertEqual(rows[0][1], 61)

    def test_rate_limiter_is_global_across_spawned_processes(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        start_event = ctx.Event()
        result_queue = ctx.Queue()
        now_iso = datetime.now(timezone.utc).isoformat()
        processes = [
            ctx.Process(
                target=_process_rate_limit_worker,
                args=(DSN, label, start_event, result_queue, 4, now_iso),
            )
            for label in ("rate-a", "rate-b")
        ]
        for process in processes:
            process.start()
        start_event.set()
        for process in processes:
            process.join(timeout=15)
            self.assertEqual(process.exitcode, 0)

        results = [result_queue.get(timeout=5) for _ in processes]
        self.assertTrue(all(item[0] == "ok" for item in results), results)
        self.assertEqual(sum(item[2] for item in results), 5)

    def test_database_ping_and_table_contract_are_real_postgres(self) -> None:
        db = PostgresDatabase(DSN)
        self.assertTrue(db.ping())
        table = db.table("brand_profiles")
        table.put("bp-pg", "tenant-a", {"value": 1})
        self.assertEqual(table.get("bp-pg"), {"value": 1})
        self.assertEqual(
            table.rows_for_tenant("tenant-a"),
            [("bp-pg", "tenant-a", {"value": 1})],
        )


if __name__ == "__main__":
    unittest.main()
