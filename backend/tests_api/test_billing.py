"""HTTP tests for the CampaIA own-billing surface (B11 / ADR-0020)."""

from __future__ import annotations

import os
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from starlette.testclient import TestClient

from api.main import create_app

from .test_helpers import FINANCE, MARKETER, OTHER_OWNER, OWNER, make_client, unique_idem, with_step_up

_PLAN_CATALOG_PATH = str(
    Path(__file__).resolve().parent.parent / "config" / "plans.example.json"
)


def _with_catalog():
    """Points CAMPAIA_PLAN_CATALOG_PATH at the checked-in example catalog for the duration
    of a test, restoring whatever was there before."""

    class _Ctx:
        def __enter__(self):
            self._old = os.environ.get("CAMPAIA_PLAN_CATALOG_PATH")
            os.environ["CAMPAIA_PLAN_CATALOG_PATH"] = _PLAN_CATALOG_PATH
            return self

        def __exit__(self, *exc):
            if self._old is None:
                os.environ.pop("CAMPAIA_PLAN_CATALOG_PATH", None)
            else:
                os.environ["CAMPAIA_PLAN_CATALOG_PATH"] = self._old

    return _Ctx()


def _put_subscription(client, headers=OWNER):
    with _with_catalog():
        return client.put(
            "/billing/subscription",
            headers={**with_step_up(headers), **unique_idem()},
            json={"plan_id": "exemplo-essencial", "customer_document": "11144477735"},
        )


class BillingSubscriptionTests(unittest.TestCase):
    def test_get_without_subscription_is_not_found(self) -> None:
        client = make_client()
        r = client.get("/billing/subscription", headers=OWNER)
        assert r.status_code == 404, r.text

    def test_put_without_step_up_is_rejected(self) -> None:
        client = make_client()
        with _with_catalog():
            r = client.put(
                "/billing/subscription",
                headers={**OWNER, **unique_idem()},
                json={"plan_id": "exemplo-essencial", "customer_document": "11144477735"},
            )
        assert r.status_code == 403, r.text

    def test_marketer_cannot_manage_billing(self) -> None:
        client = make_client()
        r = _put_subscription(client, headers=MARKETER)
        assert r.status_code == 403, r.text

    def test_put_then_get_round_trips(self) -> None:
        client = make_client()
        put_response = _put_subscription(client)
        assert put_response.status_code == 200, put_response.text
        body = put_response.json()
        assert body["plan_id"] == "exemplo-essencial"
        assert body["customer_document"] == "11144477735"
        assert body["status"] == "PENDING_PAYMENT"
        assert body["entitlement_access_active"] is False
        assert body["entitlements"]["max_users"] == 1
        assert body["trial_started_at"] is None
        assert body["trial_ends_at"] is None

        get_response = client.get("/billing/subscription", headers=OWNER)
        assert get_response.status_code == 200, get_response.text
        assert get_response.json() == body

    def test_explicit_trial_uses_catalog_duration_and_entitlements(self) -> None:
        client = make_client()
        with _with_catalog():
            response = client.put(
                "/billing/subscription",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={
                    "plan_id": "exemplo-essencial",
                    "customer_document": "11144477735",
                    "start_trial": True,
                },
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "TRIAL"
        assert body["trial_started_at"] is not None
        assert body["trial_ends_at"] is not None
        assert body["entitlement_access_active"] is True
        assert body["entitlements"]["channels"] == ["EXEMPLO_CHANNEL"]

    def test_expired_trial_is_persisted_and_audited_when_observed(self) -> None:
        client = make_client()
        with _with_catalog():
            response = client.put(
                "/billing/subscription",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={
                    "plan_id": "exemplo-essencial",
                    "customer_document": "11144477735",
                    "start_trial": True,
                },
            )
        assert response.status_code == 200, response.text

        state = client.app.state.campaia
        current = state.subscriptions["demo-tenant"]
        state.subscriptions["demo-tenant"] = replace(
            current,
            trial_started_at=datetime.now(timezone.utc) - timedelta(days=8),
            trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        observed = client.get("/billing/subscription", headers=OWNER)
        assert observed.status_code == 200, observed.text
        assert observed.json()["status"] == "EXPIRED"
        assert observed.json()["entitlement_access_active"] is False
        assert state.subscriptions["demo-tenant"].status.value == "EXPIRED"

        actions = [
            event.action
            for event in state.audit.list_for_tenant("demo-tenant")
        ]
        assert "BILLING_TRIAL_EXPIRED" in actions

    def test_unknown_plan_id_fails_closed(self) -> None:
        client = make_client()
        with _with_catalog():
            r = client.put(
                "/billing/subscription",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"plan_id": "does-not-exist", "customer_document": "11144477735"},
            )
        assert r.status_code == 503, r.text

    def test_no_catalog_configured_fails_closed(self) -> None:
        client = make_client()
        old = os.environ.pop("CAMPAIA_PLAN_CATALOG_PATH", None)
        try:
            r = client.put(
                "/billing/subscription",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"plan_id": "exemplo-essencial", "customer_document": "11144477735"},
            )
            assert r.status_code == 503, r.text
        finally:
            if old is not None:
                os.environ["CAMPAIA_PLAN_CATALOG_PATH"] = old

    def test_cross_tenant_isolation(self) -> None:
        client = make_client()
        _put_subscription(client, headers=OWNER)
        r = client.get("/billing/subscription", headers=OTHER_OWNER)
        assert r.status_code == 404, r.text



    def test_upgrade_is_pending_until_target_plan_payment_settles(self) -> None:
        client = make_client()
        _put_subscription(client)
        state = client.app.state.campaia
        current = state.subscriptions["demo-tenant"]
        state.subscriptions["demo-tenant"] = replace(
            current, status=__import__("campaia_core.subscription", fromlist=["SubscriptionStatus"]).SubscriptionStatus.ACTIVE
        )

        with _with_catalog():
            changed = client.post(
                "/billing/subscription/change-plan",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"target_plan_id": "exemplo-pro"},
            )
        assert changed.status_code == 200, changed.text
        body = changed.json()
        assert body["plan_id"] == "exemplo-essencial"
        assert body["pending_plan_id"] == "exemplo-pro"
        assert body["pending_plan_change_kind"] == "UPGRADE"
        assert body["entitlements"]["max_users"] == 1

        charge = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-10"},
        )
        assert charge.status_code == 202, charge.text
        gateway_charge_id = charge.json()["gateway_charge_id"]

        old = os.environ.get("ASAAS_WEBHOOK_TOKEN")
        os.environ["ASAAS_WEBHOOK_TOKEN"] = "expected-token"
        try:
            settled = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_upgrade_1",
                    "event": "PAYMENT_RECEIVED",
                    "payment": {"id": gateway_charge_id, "status": "RECEIVED"},
                },
            )
            assert settled.status_code == 200, settled.text
        finally:
            if old is None:
                os.environ.pop("ASAAS_WEBHOOK_TOKEN", None)
            else:
                os.environ["ASAAS_WEBHOOK_TOKEN"] = old

        after = client.get("/billing/subscription", headers=OWNER).json()
        assert after["plan_id"] == "exemplo-pro"
        assert after["pending_plan_id"] is None
        assert after["entitlements"]["max_users"] == 2

    def test_cancel_and_reactivate_are_idempotent_and_payment_gated(self) -> None:
        client = make_client()
        _put_subscription(client)
        state = client.app.state.campaia
        current = state.subscriptions["demo-tenant"]
        status_enum = __import__("campaia_core.subscription", fromlist=["SubscriptionStatus"]).SubscriptionStatus
        state.subscriptions["demo-tenant"] = replace(current, status=status_enum.ACTIVE)

        headers = {**with_step_up(OWNER), **unique_idem()}
        first = client.post("/billing/subscription/cancel", headers=headers)
        replay = client.post("/billing/subscription/cancel", headers=headers)
        assert first.status_code == 200, first.text
        assert replay.json() == first.json()
        assert first.json()["status"] == "CANCELED"
        assert first.json()["entitlement_access_active"] is False

        reactivated = client.post(
            "/billing/subscription/reactivate",
            headers={**with_step_up(OWNER), **unique_idem()},
        )
        assert reactivated.status_code == 200, reactivated.text
        assert reactivated.json()["status"] == "PENDING_PAYMENT"
        assert reactivated.json()["entitlement_access_active"] is False

    def test_cross_tenant_cannot_mutate_another_subscription_transition(self) -> None:
        client = make_client()
        _put_subscription(client, headers=OWNER)
        response = client.post(
            "/billing/subscription/cancel",
            headers={**with_step_up(OTHER_OWNER), **unique_idem()},
        )
        assert response.status_code == 404, response.text

class BillingChargeTests(unittest.TestCase):
    def test_charge_without_subscription_is_not_found(self) -> None:
        client = make_client()
        r = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-09"},
        )
        assert r.status_code == 404, r.text

    def test_charge_creates_and_returns_gateway_result(self) -> None:
        client = make_client()
        _put_subscription(client)
        r = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-09"},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["amount"] == "1.0"
        assert body["gateway_status"] == "PENDING"
        assert body["gateway_charge_id"]

    def test_recharging_same_idempotency_key_does_not_duplicate(self) -> None:
        client = make_client()
        _put_subscription(client)
        headers = {**with_step_up(OWNER), **unique_idem()}
        r1 = client.post("/billing/charges", headers=headers, json={"competence": "2026-09"})
        r2 = client.post("/billing/charges", headers=headers, json={"competence": "2026-09"})
        assert r1.json() == r2.json()

    def test_finance_role_can_manage_billing(self) -> None:
        client = make_client()
        _put_subscription(client, headers=FINANCE)
        r = client.post(
            "/billing/charges",
            headers={**with_step_up(FINANCE), **unique_idem()},
            json={"competence": "2026-09"},
        )
        assert r.status_code == 202, r.text


class AsaasWebhookTests(unittest.TestCase):
    def _app_and_client(self):
        app = create_app(env="test")
        return app, TestClient(app)

    def _set_webhook_token(self, token: str):
        old = os.environ.get("ASAAS_WEBHOOK_TOKEN")
        os.environ["ASAAS_WEBHOOK_TOKEN"] = token
        return old

    def _restore_webhook_token(self, old: str | None) -> None:
        if old is None:
            os.environ.pop("ASAAS_WEBHOOK_TOKEN", None)
        else:
            os.environ["ASAAS_WEBHOOK_TOKEN"] = old

    def test_wrong_token_is_rejected_with_401(self) -> None:
        app, client = self._app_and_client()
        old = self._set_webhook_token("expected-token")
        try:
            r = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "wrong-token"},
                json={"id": "evt_1", "event": "PAYMENT_RECEIVED", "payment": {"id": "pay_1", "status": "RECEIVED"}},
            )
            assert r.status_code == 401, r.text
        finally:
            self._restore_webhook_token(old)

    def test_unknown_payment_id_is_accepted_but_not_processed(self) -> None:
        app, client = self._app_and_client()
        old = self._set_webhook_token("expected-token")
        try:
            r = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_1",
                    "event": "PAYMENT_RECEIVED",
                    "payment": {"id": "pay_does_not_exist", "status": "RECEIVED"},
                },
            )
            assert r.status_code == 200, r.text
            assert r.json() == {"accepted": True, "processed": False}
        finally:
            self._restore_webhook_token(old)

    def test_confirmed_event_settles_a_known_charge_end_to_end(self) -> None:
        app, client = self._app_and_client()
        with _with_catalog():
            client.put(
                "/billing/subscription",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"plan_id": "exemplo-essencial", "customer_document": "11144477735"},
            )
        charge_response = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-09"},
        )
        gateway_charge_id = charge_response.json()["gateway_charge_id"]

        old = self._set_webhook_token("expected-token")
        try:
            r = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_confirm_1",
                    "event": "PAYMENT_RECEIVED",
                    "payment": {"id": gateway_charge_id, "status": "RECEIVED"},
                },
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["accepted"] is True
            assert body["processed"] is True
            assert body["billing_id"]

            subscription = client.get("/billing/subscription", headers=OWNER)
            assert subscription.status_code == 200, subscription.text
            sub_body = subscription.json()
            assert sub_body["status"] == "ACTIVE"
            assert sub_body["activated_at"] is not None
            assert sub_body["entitlement_access_active"] is True
        finally:
            self._restore_webhook_token(old)

    def test_late_payment_after_cancellation_never_reactivates_entitlement(self) -> None:
        app, client = self._app_and_client()
        _put_subscription(client)
        state = client.app.state.campaia
        current = state.subscriptions["demo-tenant"]
        status_enum = __import__(
            "campaia_core.subscription", fromlist=["SubscriptionStatus"]
        ).SubscriptionStatus
        state.subscriptions["demo-tenant"] = replace(current, status=status_enum.ACTIVE)

        charge_response = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-10"},
        )
        gateway_charge_id = charge_response.json()["gateway_charge_id"]
        canceled = client.post(
            "/billing/subscription/cancel",
            headers={**with_step_up(OWNER), **unique_idem()},
        )
        assert canceled.status_code == 200, canceled.text

        old = self._set_webhook_token("expected-token")
        try:
            settled = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_late_after_cancel",
                    "event": "PAYMENT_RECEIVED",
                    "payment": {"id": gateway_charge_id, "status": "RECEIVED"},
                },
            )
            assert settled.status_code == 200, settled.text
            assert settled.json()["processed"] is True
        finally:
            self._restore_webhook_token(old)

        observed = client.get("/billing/subscription", headers=OWNER).json()
        assert observed["status"] == "CANCELED"
        assert observed["entitlement_access_active"] is False
        actions = [event.action for event in state.audit.list_for_tenant("demo-tenant")]
        assert "BILLING_SUBSCRIPTION_ACTIVATION_SKIPPED" in actions

    def test_old_plan_payment_during_pending_upgrade_does_not_apply_target_plan(self) -> None:
        app, client = self._app_and_client()
        _put_subscription(client)
        state = client.app.state.campaia
        current = state.subscriptions["demo-tenant"]
        status_enum = __import__(
            "campaia_core.subscription", fromlist=["SubscriptionStatus"]
        ).SubscriptionStatus
        state.subscriptions["demo-tenant"] = replace(current, status=status_enum.ACTIVE)

        old_charge = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-10"},
        )
        old_gateway_id = old_charge.json()["gateway_charge_id"]
        with _with_catalog():
            changed = client.post(
                "/billing/subscription/change-plan",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"target_plan_id": "exemplo-pro"},
            )
        assert changed.status_code == 200, changed.text

        old = self._set_webhook_token("expected-token")
        try:
            settled = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_old_plan_during_upgrade",
                    "event": "PAYMENT_RECEIVED",
                    "payment": {"id": old_gateway_id, "status": "RECEIVED"},
                },
            )
            assert settled.status_code == 200, settled.text
            assert settled.json()["processed"] is True
        finally:
            self._restore_webhook_token(old)

        observed = client.get("/billing/subscription", headers=OWNER).json()
        assert observed["plan_id"] == "exemplo-essencial"
        assert observed["pending_plan_id"] == "exemplo-pro"
        assert observed["entitlements"]["max_users"] == 1

    def test_overdue_event_marks_past_due_with_grace_and_audit(self) -> None:
        app, client = self._app_and_client()
        _put_subscription(client)
        state = client.app.state.campaia
        status_enum = __import__(
            "campaia_core.subscription", fromlist=["SubscriptionStatus"]
        ).SubscriptionStatus
        current = state.subscriptions["demo-tenant"]
        state.subscriptions["demo-tenant"] = replace(current, status=status_enum.ACTIVE)

        charge_response = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-10"},
        )
        assert charge_response.status_code == 202, charge_response.text
        gateway_charge_id = charge_response.json()["gateway_charge_id"]

        old = self._set_webhook_token("expected-token")
        try:
            overdue = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_overdue_1",
                    "event": "PAYMENT_OVERDUE",
                    "payment": {"id": gateway_charge_id, "status": "OVERDUE"},
                },
            )
            assert overdue.status_code == 200, overdue.text
            assert overdue.json()["processed"] is True
            assert overdue.json()["status"] == "OVERDUE"
        finally:
            self._restore_webhook_token(old)

        observed = client.get("/billing/subscription", headers=OWNER).json()
        assert observed["status"] == "PAST_DUE"
        assert observed["past_due_at"] is not None
        assert observed["grace_period_ends_at"] is not None
        assert observed["past_due_in_grace"] is True
        assert observed["entitlement_access_active"] is True
        assert observed["past_due_access_mode"] == "ALLOW_DURING_GRACE"
        assert observed["next_dunning_reminder_at"] is not None

        actions = [event.action for event in state.audit.list_for_tenant("demo-tenant")]
        assert "BILLING_SUBSCRIPTION_PAST_DUE" in actions

    def test_received_after_overdue_recovers_active_and_clears_past_due_state(self) -> None:
        app, client = self._app_and_client()
        _put_subscription(client)
        state = client.app.state.campaia
        status_enum = __import__(
            "campaia_core.subscription", fromlist=["SubscriptionStatus"]
        ).SubscriptionStatus
        current = state.subscriptions["demo-tenant"]
        state.subscriptions["demo-tenant"] = replace(current, status=status_enum.ACTIVE)

        charge_response = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-10"},
        )
        gateway_charge_id = charge_response.json()["gateway_charge_id"]

        old = self._set_webhook_token("expected-token")
        try:
            first = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_overdue_recovery_1",
                    "event": "PAYMENT_OVERDUE",
                    "payment": {"id": gateway_charge_id, "status": "OVERDUE"},
                },
            )
            assert first.status_code == 200, first.text

            recovered = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_overdue_recovery_2",
                    "event": "PAYMENT_RECEIVED",
                    "payment": {"id": gateway_charge_id, "status": "RECEIVED"},
                },
            )
            assert recovered.status_code == 200, recovered.text
            assert recovered.json()["processed"] is True
        finally:
            self._restore_webhook_token(old)

        observed = client.get("/billing/subscription", headers=OWNER).json()
        assert observed["status"] == "ACTIVE"
        assert observed["past_due_at"] is None
        assert observed["grace_period_ends_at"] is None
        assert observed["dunning_reminders_sent"] == 0
        assert observed["entitlement_access_active"] is True

        actions = [event.action for event in state.audit.list_for_tenant("demo-tenant")]
        assert "BILLING_SUBSCRIPTION_RECOVERED" in actions

    def test_failed_payment_attempt_is_audited_without_marking_past_due(self) -> None:
        app, client = self._app_and_client()
        _put_subscription(client)
        state = client.app.state.campaia
        status_enum = __import__(
            "campaia_core.subscription", fromlist=["SubscriptionStatus"]
        ).SubscriptionStatus
        current = state.subscriptions["demo-tenant"]
        state.subscriptions["demo-tenant"] = replace(current, status=status_enum.ACTIVE)

        charge_response = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-10"},
        )
        gateway_charge_id = charge_response.json()["gateway_charge_id"]

        old = self._set_webhook_token("expected-token")
        try:
            failed = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_card_refused_1",
                    "event": "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
                    "payment": {"id": gateway_charge_id, "status": "PENDING"},
                },
            )
            assert failed.status_code == 200, failed.text
            assert failed.json()["processed"] is True
        finally:
            self._restore_webhook_token(old)

        observed = client.get("/billing/subscription", headers=OWNER).json()
        assert observed["status"] == "ACTIVE"
        assert observed["past_due_at"] is None
        actions = [event.action for event in state.audit.list_for_tenant("demo-tenant")]
        assert "BILLING_PAYMENT_ATTEMPT_FAILED" in actions

    def test_overdue_is_isolated_to_the_charge_tenant(self) -> None:
        app, client = self._app_and_client()
        _put_subscription(client, headers=OWNER)
        _put_subscription(client, headers=OTHER_OWNER)
        state = client.app.state.campaia
        status_enum = __import__(
            "campaia_core.subscription", fromlist=["SubscriptionStatus"]
        ).SubscriptionStatus
        state.subscriptions["demo-tenant"] = replace(
            state.subscriptions["demo-tenant"], status=status_enum.ACTIVE
        )
        state.subscriptions["other-tenant"] = replace(
            state.subscriptions["other-tenant"], status=status_enum.ACTIVE
        )

        charge_response = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-10"},
        )
        gateway_charge_id = charge_response.json()["gateway_charge_id"]

        old = self._set_webhook_token("expected-token")
        try:
            overdue = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_cross_tenant_overdue_1",
                    "event": "PAYMENT_OVERDUE",
                    "payment": {"id": gateway_charge_id, "status": "OVERDUE"},
                },
            )
            assert overdue.status_code == 200, overdue.text
        finally:
            self._restore_webhook_token(old)

        assert client.get("/billing/subscription", headers=OWNER).json()["status"] == "PAST_DUE"
        assert client.get("/billing/subscription", headers=OTHER_OWNER).json()["status"] == "ACTIVE"

    def test_overdue_plan_change_charge_does_not_mark_current_plan_past_due(self) -> None:
        app, client = self._app_and_client()
        _put_subscription(client)
        state = client.app.state.campaia
        status_enum = __import__(
            "campaia_core.subscription", fromlist=["SubscriptionStatus"]
        ).SubscriptionStatus
        state.subscriptions["demo-tenant"] = replace(
            state.subscriptions["demo-tenant"], status=status_enum.ACTIVE
        )

        with _with_catalog():
            changed = client.post(
                "/billing/subscription/change-plan",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"target_plan_id": "exemplo-pro"},
            )
        assert changed.status_code == 200, changed.text

        charge_response = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-10"},
        )
        gateway_charge_id = charge_response.json()["gateway_charge_id"]

        old = self._set_webhook_token("expected-token")
        try:
            overdue = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_upgrade_overdue_1",
                    "event": "PAYMENT_OVERDUE",
                    "payment": {"id": gateway_charge_id, "status": "OVERDUE"},
                },
            )
            assert overdue.status_code == 200, overdue.text
            assert overdue.json()["processed"] is False
        finally:
            self._restore_webhook_token(old)

        observed = client.get("/billing/subscription", headers=OWNER).json()
        assert observed["status"] == "ACTIVE"
        assert observed["pending_plan_id"] == "exemplo-pro"
        actions = [event.action for event in state.audit.list_for_tenant("demo-tenant")]
        assert "BILLING_SUBSCRIPTION_PAST_DUE_SKIPPED" in actions

    def test_pending_status_is_accepted_but_not_settled(self) -> None:
        app, client = self._app_and_client()
        with _with_catalog():
            client.put(
                "/billing/subscription",
                headers={**with_step_up(OWNER), **unique_idem()},
                json={"plan_id": "exemplo-essencial", "customer_document": "11144477735"},
            )
        charge_response = client.post(
            "/billing/charges",
            headers={**with_step_up(OWNER), **unique_idem()},
            json={"competence": "2026-09"},
        )
        gateway_charge_id = charge_response.json()["gateway_charge_id"]

        old = self._set_webhook_token("expected-token")
        try:
            r = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "expected-token"},
                json={
                    "id": "evt_pending_1",
                    "event": "PAYMENT_CREATED",
                    "payment": {"id": gateway_charge_id, "status": "PENDING"},
                },
            )
            assert r.status_code == 200, r.text
            assert r.json()["processed"] is False
        finally:
            self._restore_webhook_token(old)

    def test_duplicate_event_id_is_rejected_the_second_time(self) -> None:
        app, client = self._app_and_client()
        old = self._set_webhook_token("expected-token")
        try:
            payload = {
                "id": "evt_dup_1",
                "event": "PAYMENT_RECEIVED",
                "payment": {"id": "pay_does_not_exist", "status": "RECEIVED"},
            }
            first = client.post(
                "/webhooks/asaas", headers={"asaas-access-token": "expected-token"}, json=payload
            )
            second = client.post(
                "/webhooks/asaas", headers={"asaas-access-token": "expected-token"}, json=payload
            )
            assert first.status_code == 200
            assert second.json()["accepted"] is False
        finally:
            self._restore_webhook_token(old)

    def test_excess_requests_from_the_same_origin_are_rate_limited(self) -> None:
        """Item 1.2 do cronograma mestre: unico endpoint publico sem autenticacao de usuario
        deste app -- prova que uma origem que excede o limite da janela recebe 429, mesmo com
        token valido, e que a origem seguinte (nao contada na mesma janela) ainda e atendida.
        """
        app, client = self._app_and_client()
        old = self._set_webhook_token("expected-token")
        try:
            app.state.campaia.asaas_webhook_rate_limiter.max_requests = 3
            headers = {"asaas-access-token": "expected-token"}
            for i in range(3):
                r = client.post(
                    "/webhooks/asaas",
                    headers=headers,
                    json={
                        "id": f"evt_rl_{i}",
                        "event": "PAYMENT_RECEIVED",
                        "payment": {"id": "pay_does_not_exist", "status": "RECEIVED"},
                    },
                )
                assert r.status_code == 200, r.text

            over_limit = client.post(
                "/webhooks/asaas",
                headers=headers,
                json={
                    "id": "evt_rl_over",
                    "event": "PAYMENT_RECEIVED",
                    "payment": {"id": "pay_does_not_exist", "status": "RECEIVED"},
                },
            )
            assert over_limit.status_code == 429, over_limit.text
            assert over_limit.json()["reason"] == "RATE_LIMITED"

            # Ate um token invalido custa o limite -- a defesa vem antes da verificacao de
            # autenticidade, exatamente porque protege contra volume, nao so contra forja.
            wrong_token = client.post(
                "/webhooks/asaas",
                headers={"asaas-access-token": "wrong-token"},
                json={"id": "evt_rl_wrong", "event": "x", "payment": {"id": "x", "status": "x"}},
            )
            assert wrong_token.status_code == 429, wrong_token.text
        finally:
            self._restore_webhook_token(old)


if __name__ == "__main__":
    unittest.main()


class BillingWebReadTests(unittest.TestCase):
    def test_catalog_requires_authentication_and_billing_permission(self):
        client = make_client()
        with _with_catalog():
            assert client.get('/billing/plans').status_code == 401
            assert client.get('/billing/plans', headers=MARKETER).status_code == 403
            assert client.get('/billing/plans', headers=FINANCE).status_code == 200

    def test_catalog_preserves_decimal_values_without_creating_subscription_or_charge(self):
        client = make_client()
        with _with_catalog():
            response = client.get('/billing/plans', headers=OWNER)
        assert response.status_code == 200, response.text
        items = response.json()['items']
        assert len(items) == 2
        assert items[0]['monthly_price'] == '1.0'
        assert items[0]['plan_changes'][0]['target_plan_id'] == 'exemplo-pro'
        assert not client.app.state.campaia.subscriptions
        assert not client.app.state.campaia.charges

    def test_missing_and_invalid_catalog_fail_closed_without_exposing_path(self):
        from unittest.mock import patch
        from tempfile import TemporaryDirectory
        client = make_client()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'private-commercial.json'
            for payload in (None, '{invalid-json', '[]'):
                if payload is not None:
                    path.write_text(payload)
                with patch.dict(os.environ, {'CAMPAIA_PLAN_CATALOG_PATH': str(path)}):
                    response = client.get('/billing/plans', headers=OWNER)
                assert response.status_code == 503, response.text
                assert directory not in response.text
                assert response.json()['code'] == 'BILLING_CATALOG_UNAVAILABLE'

    def test_subscription_terms_are_tenant_scoped_and_use_contracted_snapshot(self):
        from unittest.mock import patch
        from decimal import Decimal
        client = make_client()
        _put_subscription(client)
        state = client.app.state.campaia
        original = state.subscriptions['demo-tenant']
        state.subscriptions['demo-tenant'] = replace(
            original, plan=replace(original.plan, monthly_price=Decimal('19.1234')))
        with patch.dict(os.environ, {'CAMPAIA_PLAN_CATALOG_PATH': '/missing/catalog.json'}):
            response = client.get('/billing/subscription', headers=OWNER)
            other = client.get('/billing/subscription', headers=OTHER_OWNER)
        assert response.status_code == 200, response.text
        assert response.json()['commercial_terms']['monthly_price'] == '19.1234'
        assert other.status_code == 404, other.text
        assert not state.charges


class BillingHistoryTests(unittest.TestCase):
    def _charge(self, client, competence='2026-10'):
        response = client.post('/billing/charges',
            headers={**with_step_up(OWNER), **unique_idem()}, json={'competence': competence})
        assert response.status_code == 202, response.text
        return response.json()['gateway_charge_id']

    def test_auth_rbac_empty_and_no_gateway_calls_on_read(self):
        from unittest.mock import patch
        client = make_client()
        assert client.get('/billing/charges').status_code == 401
        assert client.get('/billing/charges', headers=MARKETER).status_code == 403
        with patch.object(client.app.state.campaia.billing_gateway, 'get_charge_status', side_effect=AssertionError('no polling')):
            response = client.get('/billing/charges', headers=FINANCE)
        assert response.json() == {'items': [], 'next_cursor': None}

    def test_history_is_tenant_scoped_redacted_and_observations_are_explicit(self):
        client = make_client()
        _put_subscription(client)
        key = self._charge(client)
        response = client.get('/billing/charges', headers=OWNER)
        item = response.json()['items'][0]
        assert item['gateway_charge_id'] == key
        assert item['amount'] == '1.0'
        assert item['gateway_mode'] == 'SIMULATOR'
        assert item['gateway_status'] == 'PENDING'
        assert item['status_source'] == 'CREATE'
        assert item['status_observed_at'] is not None
        assert item['invoice_url'] is None
        assert 'customer_document' not in item and 'customer_ref' not in item
        assert '11144477735' not in response.text
        assert client.get('/billing/charges', headers=OTHER_OWNER).json()['items'] == []
        assert client.get('/billing/charges?cursor=' + key, headers=OTHER_OWNER).status_code == 422

    def test_webhook_observation_survives_replay_of_creation_and_duplicate_event(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'ASAAS_WEBHOOK_TOKEN': 'history-test-token'}):
            client = make_client()
            _put_subscription(client)
            key = self._charge(client)
            payload = {'id': 'evt-history', 'event': 'PAYMENT_RECEIVED',
                       'payment': {'id': key, 'status': 'RECEIVED'}}
            headers = {'asaas-access-token': 'history-test-token'}
            assert client.post('/webhooks/asaas', headers=headers, json=payload).status_code == 200
            before = client.get('/billing/charges', headers=OWNER).json()
            assert before['items'][0]['gateway_status'] == 'CONFIRMED'
            assert before['items'][0]['status_source'] == 'WEBHOOK'
            assert self._charge(client) == key  # New HTTP key, same deterministic billing id.
            client.post('/webhooks/asaas', headers=headers, json=payload)
            assert client.get('/billing/charges', headers=OWNER).json() == before
            bad = {**payload, 'id': 'evt-untrusted', 'payment': {'id': key, 'status': 'OVERDUE'}}
            assert client.post('/webhooks/asaas', headers={'asaas-access-token': 'wrong'}, json=bad).status_code == 401
            assert client.get('/billing/charges', headers=OWNER).json() == before

    def test_legacy_records_remain_unknown_and_do_not_inherit_current_gateway_mode(self):
        from api.db import encode, decode
        from campaia_core.subscription import compute_cycle_charge
        client = make_client()
        _put_subscription(client)
        charge = compute_cycle_charge(client.app.state.campaia.subscriptions['demo-tenant'], competence='2020-01')
        encoded = encode(charge)
        encoded.pop('billing_observations')
        client.app.state.campaia.charges['legacy'] = decode(encoded)
        item = client.get('/billing/charges', headers=OWNER).json()['items'][0]
        assert item['gateway_status'] is None and item['gateway_mode'] is None
        assert item['status_observed_at'] is None and item['invoice_url'] is None

    def test_pagination_and_invalid_cursor_never_fall_back_to_first_page(self):
        client = make_client()
        _put_subscription(client)
        for i in range(52):
            self._charge(client, f'period-{i:03d}')
        first = client.get('/billing/charges', headers=OWNER).json()
        assert len(first['items']) == 50 and first['next_cursor']
        self._charge(client, 'newest-after-first-page')
        second = client.get('/billing/charges?cursor=' + first['next_cursor'], headers=OWNER).json()
        assert len(second['items']) == 2 and second['next_cursor'] is None
        ids = [item['gateway_charge_id'] for item in first['items'] + second['items']]
        assert len(set(ids)) == 52
        assert client.get('/billing/charges?cursor=invalid', headers=OWNER).status_code == 422

    def test_only_safe_asaas_url_with_persisted_mode_is_exposed(self):
        client = make_client()
        _put_subscription(client)
        key = self._charge(client)
        state = client.app.state.campaia
        original = state.charges[key]
        for mode, url, expected in [
            ('SANDBOX', 'https://sandbox.asaas.com/i/abc', 'https://sandbox.asaas.com/i/abc'),
            ('SANDBOX', 'https://www.asaas.com/i/abc', None),
            ('PRODUCTION', 'https://www.asaas.com/i/abc', 'https://www.asaas.com/i/abc'),
            ('PRODUCTION', 'https://evil.test/i/abc', None),
        ]:
            state.charges[key] = replace(original, gateway_provider='ASAAS', gateway_mode=mode, invoice_url=url)
            assert client.get('/billing/charges', headers=OWNER).json()['items'][0]['invoice_url'] == expected
