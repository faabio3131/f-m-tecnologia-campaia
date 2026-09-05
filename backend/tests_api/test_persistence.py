"""Proves that api/db.py's SQLite backing actually survives a process restart.

Every test here builds one Starlette app pointed at a real file under a temp directory,
drives it through the HTTP layer (never reaching into repository internals), deletes every
reference to that app/state so the object -- and its underlying sqlite3 connection -- is
actually torn down (not just "a dict got cleared"), then builds a brand new app/state
instance pointed at the *same* file and confirms the data is still there via GET.

Ephemeral mode (the default, used by every other file in this package) is completely
untouched by any of this: these tests are the only ones in the suite that ever pass
`db_path=` to `create_app`.

Response field names here follow the CURRENT, P-14-fixed contract as actually implemented
by api/helpers.py's serializers (achado 1: identifiers are `id`, not `<entity>_id`; achado
5: `external_resources` is an array of {channel, external_resource_id, sync_status,
last_synced_at} objects, not a flat {channel: id} dict; `channels` not `planned_channels`).
"""

from __future__ import annotations

import gc
import os
import tempfile
import unittest

from starlette.testclient import TestClient

from api.main import create_app

OWNER = {"Authorization": "Bearer demo-owner-token"}
APPROVER = {"Authorization": "Bearer demo-approver-token"}
FINANCE = {"Authorization": "Bearer demo-finance-token"}
STEP_UP = {"X-Step-Up-Token": "sandbox-fixture-stepup-value"}


def with_step_up(headers: dict) -> dict:
    return {**headers, **STEP_UP}


def idem(suffix: str) -> dict:
    return {"Idempotency-Key": f"idem-persist-{suffix}".ljust(16, "x")}


DEFAULT_BRIEF = {
    "objective": "Sell shoes",
    "product": "Shoes",
    "audience": "Runners",
    "region": "BR",
    "currency": "BRL",
    "total_budget": "5000.50",
    "daily_cap": "500.25",
    "channels": ["GOOGLE_ADS"],
}


class PersistenceTestCase(unittest.TestCase):
    """Gives every test a private temp-dir DB file, cleaned up afterwards."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "campaia.db")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def new_client(self) -> TestClient:
        """A fresh app/state instance pointed at this test's db file."""
        return TestClient(create_app(db_path=self.db_path))

    def teardown_client(self, client: TestClient) -> None:
        """Drop every reference to the client/app/state so they are actually garbage
        collected (not just "cleared") before a new instance opens the same file --
        this is what proves the next `new_client()` is reading real, on-disk state and
        not just reusing an in-memory object that happened to survive.
        """
        app = client.app
        client.close()
        del client
        del app
        gc.collect()


class TestBrandProfileSurvivesRestart(PersistenceTestCase):
    def test_brand_profile_survives_restart(self) -> None:
        c1 = self.new_client()
        r = c1.post(
            "/brand-profiles",
            headers={**OWNER, **idem("bp1")},
            json={"name": "Acme Run Co", "tone": "energetic", "colors": ["#FF0000"]},
        )
        self.assertEqual(r.status_code, 201, r.text)
        created = r.json()

        # Sanity: it is actually there before any restart.
        r = c1.get("/brand-profiles", headers=OWNER)
        self.assertEqual(len(r.json()), 1)

        self.teardown_client(c1)

        c2 = self.new_client()
        r = c2.get("/brand-profiles", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        profiles = r.json()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["id"], created["id"])
        self.assertEqual(profiles[0]["name"], "Acme Run Co")
        self.assertEqual(profiles[0]["colors"], ["#FF0000"])


class TestCampaignSurvivesRestart(PersistenceTestCase):
    def test_campaign_and_decimal_budget_survive_restart(self) -> None:
        c1 = self.new_client()
        r = c1.post("/briefs", headers={**OWNER, **idem("brief1")}, json=DEFAULT_BRIEF)
        self.assertEqual(r.status_code, 202, r.text)
        campaign_id = r.json()["id"]

        self.teardown_client(c1)

        c2 = self.new_client()
        r = c2.get(f"/campaigns/{campaign_id}", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        campaign = r.json()
        self.assertEqual(campaign["id"], campaign_id)
        self.assertEqual(campaign["state"], "DRAFT")
        # Decimal fields must round-trip byte-for-byte -- "5000.50" staying "5000.50"
        # (never drifting to a float-ish "5000.5" or losing the cents) is exactly the
        # failure mode this module's docstring calls out as unacceptable for money.
        self.assertEqual(campaign["brief"]["total_budget"], "5000.50")
        self.assertEqual(campaign["brief"]["daily_cap"], "500.25")
        self.assertEqual(campaign["budget"]["total_amount"], "5000.50")
        self.assertEqual(campaign["budget"]["daily_cap"], "500.25")


class TestCampaignStateMachineSurvivesRestart(PersistenceTestCase):
    """Exercises the deep, in-place mutation path: publish (saga -> ACTIVE, budget
    reservations, external_resources dict) then pause, all via direct attribute mutation
    on objects returned by CampaignRepository.get() with no explicit "save" call anywhere
    in the route handlers -- proving api/db.py's notify-wrapping actually captures every
    level of that mutation, not just top-level CampaignRecord field assignment.
    """

    def _publish_ready_campaign(self, client: TestClient) -> tuple[str, dict, dict]:
        r = client.post("/briefs", headers={**OWNER, **idem("brief-a")}, json=DEFAULT_BRIEF)
        self.assertEqual(r.status_code, 202, r.text)
        campaign_id = r.json()["id"]

        r = client.post(
            f"/campaigns/{campaign_id}/plan/regenerate", headers={**OWNER, **idem("regen-a")}
        )
        self.assertEqual(r.status_code, 202, r.text)

        r = client.post(f"/campaigns/{campaign_id}/validate", headers=OWNER)
        self.assertEqual(r.status_code, 200, r.text)
        decision = r.json()
        self.assertEqual(decision["outcome"], "APPROVABLE")

        r = client.post(
            "/approvals",
            headers={**OWNER, **idem("appr-a")},
            json={"campaign_id": campaign_id, "kind": "PUBLISH"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        approval = r.json()

        r = client.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **idem("dec-a")},
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        approval = r.json()
        self.assertEqual(approval["status"], "APPROVED")

        return campaign_id, decision, approval

    def test_publish_then_pause_state_and_budget_survive_restart(self) -> None:
        c1 = self.new_client()
        campaign_id, decision, approval = self._publish_ready_campaign(c1)

        publish_headers = {**with_step_up(OWNER), **idem("publish")}
        r = c1.post(
            f"/campaigns/{campaign_id}/publish",
            headers=publish_headers,
            json={
                "policy_decision_id": decision["policy_decision_id"],
                "approval_id": approval["id"],
            },
        )
        self.assertEqual(r.status_code, 202, r.text)
        published = r.json()
        self.assertEqual(published["state"], "ACTIVE")
        self.assertTrue(published["external_resources"])  # saga confirmed the channel
        self.assertEqual(published["external_resources"][0]["sync_status"], "CONFIRMED")

        pause_headers = {**OWNER, **idem("pause")}
        r = c1.post(f"/campaigns/{campaign_id}/pause", headers=pause_headers)
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["state"], "PAUSED")

        self.teardown_client(c1)

        c2 = self.new_client()
        r = c2.get(f"/campaigns/{campaign_id}", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        campaign = r.json()
        self.assertEqual(campaign["state"], "PAUSED")
        self.assertEqual(campaign["external_resources"], published["external_resources"])
        # BudgetEngine.spent_total (BFF-exposed as spent_to_date) survives too -- the
        # saga reserved+confirmed real spend against it during publish.
        self.assertEqual(campaign["budget"]["spent_to_date"], published["budget"]["spent_to_date"])

        # The pause idempotency key must not be replayable in a way that duplicates the
        # mutation: calling it again on the *new* process must return the same cached
        # result (still PAUSED, HTTP 202) rather than raising an invalid-transition error
        # or otherwise re-running the pause logic against an already-paused campaign.
        r = c2.post(f"/campaigns/{campaign_id}/pause", headers=pause_headers)
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["state"], "PAUSED")


class TestIdempotencyRecordSurvivesRestart(PersistenceTestCase):
    def test_repeated_key_after_restart_does_not_reexecute(self) -> None:
        c1 = self.new_client()
        r = c1.post("/briefs", headers={**OWNER, **idem("brief-b")}, json=DEFAULT_BRIEF)
        campaign_id = r.json()["id"]

        r = c1.post(
            f"/campaigns/{campaign_id}/plan/regenerate", headers={**OWNER, **idem("regen-b")}
        )
        self.assertEqual(r.status_code, 202)
        r = c1.post(f"/campaigns/{campaign_id}/validate", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        r = c1.post(
            "/approvals",
            headers={**OWNER, **idem("appr-b")},
            json={"campaign_id": campaign_id, "kind": "PUBLISH"},
        )
        approval = r.json()
        r = c1.post(
            f"/approvals/{approval['id']}/decision",
            headers={**with_step_up(APPROVER), **idem("dec-b")},
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 200)
        approval = r.json()

        # Move the campaign to a pausable state (APPROVED/PUBLISHING/ACTIVE/OPTIMIZING --
        # DRAFT/VALIDATED are not) the same way TestCampaignStateMachineSurvivesRestart does,
        # then pause it. This is deliberate: it proves that IF the idempotency key were
        # replayed by re-invoking `operation()` instead of returning the stored result, a
        # later call would see a *different* response (INVALID_STATE, since PAUSED -> PAUSED
        # is not a real transition) than the first. Getting the exact same 202-with-PAUSED
        # response from a brand new process is only possible if the first, successful call's
        # result was durably stored and is the one being replayed -- not a fresh execution.
        decision = c1.post(f"/campaigns/{campaign_id}/validate", headers=OWNER).json()
        pause_headers = {**OWNER, **idem("survives")}

        publish_headers = {**with_step_up(OWNER), **idem("survives-publish")}
        r = c1.post(
            f"/campaigns/{campaign_id}/publish",
            headers=publish_headers,
            json={
                "policy_decision_id": decision["policy_decision_id"],
                "approval_id": approval["id"],
            },
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json()["state"], "ACTIVE")

        r = c1.post(f"/campaigns/{campaign_id}/pause", headers=pause_headers)
        self.assertEqual(r.status_code, 202, r.text)
        first_result = r.json()
        self.assertEqual(first_result["state"], "PAUSED")

        # Replay on the SAME instance: must be the identical cached result, not a second
        # (now-invalid, PAUSED -> PAUSED is not a real transition) execution.
        r = c1.post(f"/campaigns/{campaign_id}/pause", headers=pause_headers)
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json(), first_result)

        self.teardown_client(c1)

        c2 = self.new_client()
        # Replay on a BRAND NEW process/instance with a rehydrated idempotency store: same
        # assertion, now proving the idempotency record -- not just the campaign's own
        # state -- survived the restart and is what is actually being consulted.
        r = c2.post(f"/campaigns/{campaign_id}/pause", headers=pause_headers)
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(r.json(), first_result)

    def test_dual_approval_decided_by_set_survives_restart(self) -> None:
        """Exercises decided_by: set[str], mutated via `.add()` (never a top-level
        attribute assignment on the ApprovalRequest itself) -- the one mutation site that
        `wrap_for_notify`'s dataclass __setattr__ hook alone would not catch, only the
        recursive wrapping of the set field itself.
        """
        c1 = self.new_client()
        r = c1.post("/briefs", headers={**OWNER, **idem("brief-c")}, json=DEFAULT_BRIEF)
        campaign_id = r.json()["id"]

        r = c1.post(
            "/approvals",
            headers={**OWNER, **idem("appr-c")},
            json={
                "campaign_id": campaign_id,
                "kind": "BUDGET_CHANGE",
                "amount": "123.45",
                "requires_dual_approval": True,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        approval_id = r.json()["id"]

        r = c1.post(
            f"/approvals/{approval_id}/decision",
            headers={**with_step_up(FINANCE), **idem("dec-c")},
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        approval = r.json()
        # Only one of two required approvers has decided -- still PENDING.
        self.assertEqual(approval["status"], "PENDING")
        self.assertEqual(approval["decided_by"], ["user-finance-1"])

        self.teardown_client(c1)

        c2 = self.new_client()
        r = c2.get("/approvals", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        approvals = r.json()
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["id"], approval_id)
        self.assertEqual(approvals[0]["status"], "PENDING")
        self.assertEqual(approvals[0]["decided_by"], ["user-finance-1"])
        self.assertEqual(approvals[0]["amount"], "123.45")

        # The rehydrated approval must still be a genuinely mutable, notify-wrapped
        # object: deciding it again (the second required financeiro-like approver -- here
        # just re-approving as OWNER to complete dual approval isn't valid per roles, so
        # instead prove mutability by adding a second FINANCE-equivalent decision is not
        # applicable here; instead assert a second decision attempt properly reflects
        # SEPARATION_OF_DUTIES, which only fires if decided_by was correctly rehydrated as
        # a real set that already contains this decider).
        r = c2.post(
            f"/approvals/{approval_id}/decision",
            headers={**with_step_up(FINANCE), **idem("dec-c-again")},
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "SEPARATION_OF_DUTIES")


class TestAuditLogSurvivesRestart(PersistenceTestCase):
    def test_audit_events_survive_restart(self) -> None:
        c1 = self.new_client()
        r = c1.post(
            "/brand-profiles",
            headers={**OWNER, **idem("bp-d")},
            json={"name": "Acme", "tone": "bold"},
        )
        self.assertEqual(r.status_code, 201)
        r = c1.post("/briefs", headers={**OWNER, **idem("brief-d")}, json=DEFAULT_BRIEF)
        self.assertEqual(r.status_code, 202)

        r = c1.get("/audit-events", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        before = r.json()["items"]
        self.assertGreaterEqual(len(before), 2)
        actions_before = sorted(e["action"] for e in before)

        self.teardown_client(c1)

        c2 = self.new_client()
        r = c2.get("/audit-events", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        after = r.json()["items"]
        self.assertEqual(len(after), len(before))
        self.assertEqual(sorted(e["action"] for e in after), actions_before)
        self.assertEqual(
            sorted(e["id"] for e in after),
            sorted(e["id"] for e in before),
        )


class TestTenantAutonomySurvivesRestart(PersistenceTestCase):
    def test_autonomy_level_and_updated_at_survive_restart(self) -> None:
        c1 = self.new_client()
        r = c1.post("/briefs", headers={**OWNER, **idem("brief-e")}, json=DEFAULT_BRIEF)
        campaign_id = r.json()["id"]

        r = c1.post(
            "/approvals",
            headers={**OWNER, **idem("appr-e")},
            json={"campaign_id": campaign_id, "kind": "AUTONOMY_CHANGE"},
        )
        approval_id = r.json()["id"]
        r = c1.post(
            f"/approvals/{approval_id}/decision",
            headers={**with_step_up(FINANCE), **idem("dec-e")},
            json={"decision": "APPROVE"},
        )
        self.assertEqual(r.json()["status"], "APPROVED")

        r = c1.put(
            "/autonomy",
            headers={**with_step_up(OWNER), **idem("auto-e")},
            json={"level": 1, "approval_id": approval_id},
        )
        self.assertEqual(r.status_code, 200, r.text)
        before = r.json()
        self.assertEqual(before["level"], 1)

        self.teardown_client(c1)

        c2 = self.new_client()
        r = c2.get("/autonomy", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        after = r.json()
        self.assertEqual(after["level"], before["level"])
        self.assertEqual(after["updated_at"], before["updated_at"])


class TestEphemeralModeUnaffected(unittest.TestCase):
    """The default (no db_path) app must still be fully in-memory and never touch disk --
    two default instances must never share state.
    """

    def test_default_app_instances_do_not_share_state(self) -> None:
        c1 = TestClient(create_app())
        c2 = TestClient(create_app())

        r = c1.post(
            "/brand-profiles",
            headers={**OWNER, **idem("eph1")},
            json={"name": "Only In C1", "tone": ""},
        )
        self.assertEqual(r.status_code, 201)

        r = c2.get("/brand-profiles", headers=OWNER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])


if __name__ == "__main__":
    unittest.main()
