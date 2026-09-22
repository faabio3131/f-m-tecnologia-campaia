"""HTTP-level integration test for WP-06 (budget change), exercised through REAL Web
session cookies -- same discipline as tests_api/test_briefing_approval_web_session.py
(WP-05). PATCH /campaigns/{id}/budget and POST /approvals already existed and were already
tested via Bearer fixtures; this proves the same real-session path WP-06's frontend
(BudgetPanel.tsx) actually uses, including the two real contract gaps this Work Package
closed (ApprovalRequest.kind and .amount, both previously missing from
contracts/bff-openapi.yaml despite always being present in the real response).

Reuses this file's own login/CSRF helpers rather than importing from
test_briefing_approval_web_session.py, matching this project's "three similar lines is
better than a premature cross-test-file dependency" convention already established for
per-file test helpers throughout tests_api/.
"""

from __future__ import annotations

import os
import re
import unittest

from starlette.testclient import TestClient

from api.main import create_app

os.environ.setdefault("CAMPAIA_ENV", "test")


def _client_for(app) -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _login(client: TestClient, identity: str) -> None:
    r = client.get("/auth/login", follow_redirects=False)
    assert r.status_code == 302, r.text
    authorize_path = r.headers["location"].replace("https://testserver", "")

    picker = client.get(authorize_path)
    assert picker.status_code == 200, picker.text
    code = re.search(r'name="code" value="([^"]+)"', picker.text).group(1)

    picked = client.post(
        "/test-idp/authorize", data={"code": code, "identity": identity}, follow_redirects=False
    )
    assert picked.status_code == 303, picked.text
    callback_path = picked.headers["location"].replace("https://testserver", "")

    callback = client.get(callback_path, follow_redirects=False)
    assert callback.status_code == 302, callback.text


def _csrf(client: TestClient) -> str:
    token = client.cookies.get("campaia_csrf")
    assert token, "no CSRF cookie set -- was _login() called first?"
    return token


BRIEF = {
    "name": "Campanha de teste de orçamento",
    "objective": "Testar alteração de orçamento",
    "total_budget": "5000",
    "daily_cap": "500",
    "channels": ["GOOGLE_ADS"],
}


class TestBudgetChangeViaWebSession(unittest.TestCase):
    def test_propose_approve_apply_via_real_session_two_distinct_users(self):
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "budget-test-briefxx"},
            json=BRIEF,
        )
        self.assertEqual(r.status_code, 202, r.text)
        campaign_id = r.json()["id"]
        # Decimal-typed budget fields serialize as JSON strings (achado real desta
        # execução, ver docs/web/13_CERTIFICACAO_WP06_ALTERACAO_ORCAMENTO.md) -- not the
        # `number` the contract declares.
        self.assertEqual(r.json()["budget"]["daily_cap"], "500")

        # Propose: POST /approvals with amount -- the real field this Work Package added to
        # the contract (ApprovalRequest.amount), previously undeclared despite always being
        # returned.
        r = owner.post(
            "/approvals",
            headers={"x-csrf-token": _csrf(owner)},
            json={"campaign_id": campaign_id, "kind": "BUDGET_CHANGE", "amount": "550"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        approval = r.json()
        self.assertEqual(approval["status"], "PENDING")
        self.assertEqual(approval["kind"], "BUDGET_CHANGE")
        self.assertEqual(approval["amount"], "550")

        # Decide: a genuinely distinct logged-in user, same real backend.
        approver = _client_for(app)
        _login(approver, "approver")
        r = approver.post(
            f"/approvals/{approval['id']}/decision",
            headers={
                "x-csrf-token": _csrf(approver),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "budget-test-decidexx",
            },
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "APPROVED")

        # Apply: back on the owner's own real session, PATCH the budget using the approved
        # approval_id -- anyone with BUDGET_CHANGE permission may apply it, not only the
        # approver (matches patch_budget's own authorization, which checks only the
        # permission, not who decided the approval).
        r = owner.patch(
            f"/campaigns/{campaign_id}/budget",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "budget-test-applyxxx",
            },
            json={"daily_cap": 550, "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["budget"]["daily_cap"], "550")

        # GET /campaigns/{id} via the owner's own session reflects the real change.
        r = owner.get(f"/campaigns/{campaign_id}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["budget"]["daily_cap"], "550")

    def test_change_beyond_max_percentage_is_rejected_at_apply_time(self):
        """The approval itself never validates the percentage change -- only patch_budget
        does, at apply time. A user can propose and even get an out-of-range change
        approved; BudgetLimits.validate_change still refuses to apply it, visibly, matching
        BudgetPanel.tsx's own error-surfacing for BUDGET_LIMIT."""
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "budget-test-brief2xx"},
            json=BRIEF,
        )
        campaign_id = r.json()["id"]

        # +100% is well beyond the domain's default max_change_pct (20%).
        r = owner.post(
            "/approvals",
            headers={"x-csrf-token": _csrf(owner)},
            json={"campaign_id": campaign_id, "kind": "BUDGET_CHANGE", "amount": "1000"},
        )
        approval = r.json()

        approver = _client_for(app)
        _login(approver, "approver")
        approver.post(
            f"/approvals/{approval['id']}/decision",
            headers={
                "x-csrf-token": _csrf(approver),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "budget-test-decide2xx",
            },
            json={"decision": "APPROVE"},
        )

        r = owner.patch(
            f"/campaigns/{campaign_id}/budget",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "budget-test-apply2xxx",
            },
            json={"daily_cap": 1000, "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["code"], "BUDGET_LIMIT")

    def test_decimal_precision_survives_propose_approve_apply_as_a_string(self):
        """P-36 regression (missão de reconciliação, 22/09/2026): every monetary field on
        the wire is now a decimal string end to end -- contract, backend, and
        BudgetPanel.tsx's own payloads (no more Number(...) round-trip). A cents-precise
        value with a fractional part that a naive float round-trip could quietly perturb
        (599.99, chosen because 599.99 has no exact IEEE-754 double representation) must
        come back byte-for-byte identical through propose -> approve -> apply -> re-read,
        sent as a JSON string the whole way, exactly like the real frontend now does."""
        app = create_app(enable_test_auth_fixtures=True)
        owner = _client_for(app)
        _login(owner, "owner")

        r = owner.post(
            "/briefs",
            headers={"x-csrf-token": _csrf(owner), "idempotency-key": "budget-test-brief3xx"},
            json=BRIEF,
        )
        campaign_id = r.json()["id"]

        precise_amount = "599.99"
        r = owner.post(
            "/approvals",
            headers={"x-csrf-token": _csrf(owner)},
            json={"campaign_id": campaign_id, "kind": "BUDGET_CHANGE", "amount": precise_amount},
        )
        self.assertEqual(r.status_code, 201, r.text)
        approval = r.json()
        self.assertEqual(approval["amount"], precise_amount, "amount must round-trip exactly")

        approver = _client_for(app)
        _login(approver, "approver")
        r = approver.post(
            f"/approvals/{approval['id']}/decision",
            headers={
                "x-csrf-token": _csrf(approver),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "budget-test-decide3xx",
            },
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 200, r.text)

        # Apply with the string exactly as BudgetPanel.tsx now sends it -- never
        # Number(approvedUnapplied.amount).
        r = owner.patch(
            f"/campaigns/{campaign_id}/budget",
            headers={
                "x-csrf-token": _csrf(owner),
                "x-step-up-token": "test-stepup",
                "idempotency-key": "budget-test-apply3xxx",
            },
            json={"daily_cap": precise_amount, "approval_id": approval["id"]},
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["budget"]["daily_cap"], precise_amount)

        r = owner.get(f"/campaigns/{campaign_id}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(
            r.json()["budget"]["daily_cap"],
            precise_amount,
            "GET must still reflect the exact decimal string, not a float-perturbed value",
        )
        self.assertIsInstance(r.json()["budget"]["daily_cap"], str)
        self.assertIsInstance(r.json()["budget"]["total_amount"], str)
        self.assertIsInstance(r.json()["budget"]["spent_to_date"], str)
