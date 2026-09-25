"""HTTP tests for the CampaIA own-billing surface (B11 / ADR-0020)."""

from __future__ import annotations

import os
import unittest
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
        assert body["status"] == "ACTIVE"

        get_response = client.get("/billing/subscription", headers=OWNER)
        assert get_response.status_code == 200, get_response.text
        assert get_response.json() == body

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
        finally:
            self._restore_webhook_token(old)

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
