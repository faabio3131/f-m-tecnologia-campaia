"""Shared test helpers: a fresh app per test, fixture headers."""

from __future__ import annotations

from starlette.testclient import TestClient

from api.main import create_app

OWNER = {"Authorization": "Bearer demo-owner-token"}
OTHER_OWNER = {"Authorization": "Bearer other-owner-token"}
MARKETER = {"Authorization": "Bearer demo-marketer-token"}
APPROVER = {"Authorization": "Bearer demo-approver-token"}
FINANCE = {"Authorization": "Bearer demo-finance-token"}
VIEWER = {"Authorization": "Bearer demo-viewer-token"}

STEP_UP = {"X-Step-Up-Token": "sandbox-fixture-stepup-value"}


def with_step_up(headers: dict) -> dict:
    return {**headers, **STEP_UP}


def make_client() -> TestClient:
    return TestClient(create_app())


_idem_counter = [0]


def idem(suffix: str) -> dict:
    """A valid Idempotency-Key header (16-128 chars)."""
    key = f"idem-test-key-{suffix}".ljust(16, "x")
    return {"Idempotency-Key": key}


def unique_idem() -> dict:
    """A fresh, never-reused Idempotency-Key header, for call sites that just need any
    mutating endpoint to get past the Idempotency-Key requirement without colliding with
    another call's key in the same test."""
    _idem_counter[0] += 1
    return idem(f"auto-{_idem_counter[0]}")


DEFAULT_BRIEF = {
    "objective": "Sell shoes",
    "product": "Shoes",
    "audience": "Runners",
    "region": "BR",
    "currency": "BRL",
    "total_budget": "5000",
    "daily_cap": "500",
    "channels": ["GOOGLE_ADS"],
}


def create_campaign(client, headers=OWNER, brief: dict | None = None) -> dict:
    r = client.post("/briefs", headers={**headers, **unique_idem()}, json=brief or DEFAULT_BRIEF)
    assert r.status_code == 202, r.text
    return r.json()


def publish_ready_campaign(client, headers=OWNER) -> tuple[dict, dict, dict]:
    """Create + plan + validate + approve a campaign. Returns (campaign, decision, approval)."""
    camp = create_campaign(client, headers)
    cid = camp["id"]

    r = client.post(f"/campaigns/{cid}/plan/regenerate", headers={**headers, **unique_idem()})
    assert r.status_code == 202, r.text

    r = client.post(f"/campaigns/{cid}/validate", headers=headers)
    assert r.status_code == 200, r.text
    decision = r.json()
    assert decision["outcome"] == "APPROVABLE", decision

    r = client.post("/approvals", headers=headers, json={"campaign_id": cid, "kind": "PUBLISH"})
    assert r.status_code == 201, r.text
    approval = r.json()

    r = client.post(
        f"/approvals/{approval['id']}/decision",
        headers={**with_step_up(APPROVER), **unique_idem()},
        json={"decision": "APPROVE"},
    )
    assert r.status_code == 200, r.text
    approval = r.json()
    assert approval["status"] == "APPROVED"

    return camp, decision, approval
