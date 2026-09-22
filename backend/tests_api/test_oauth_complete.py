"""WP-04: proves /connections/oauth/complete actually creates a Connection, unlike
/connections/oauth/start alone (achado real: ConnectionRepository.create() existed but was
never called by any route before this Work Package -- confirmed by grep before writing this
file). `state` is always looked up server-side against AppState.oauth_pending, never trusted
at face value from the request body, mirroring the same discipline as /auth/callback's own
pending-login check (WP-02).
"""

from __future__ import annotations

import unittest

from tests_api.test_helpers import OWNER, OTHER_OWNER, idem, make_client, with_step_up


def _start(client, provider="GOOGLE_ADS"):
    r = client.post(
        "/connections/oauth/start",
        headers=with_step_up(OWNER),
        json={"provider": provider},
    )
    assert r.status_code == 200, r.text
    return r.json()["state"]


class TestOAuthComplete(unittest.TestCase):
    def test_complete_creates_a_real_connection(self):
        client = make_client()
        oauth_state = _start(client)

        r = client.post(
            "/connections/oauth/complete",
            headers={**with_step_up(OWNER), **idem("oauth-complete-1")},
            json={
                "state": oauth_state,
                "external_account_id": "acc-123",
                "display_name": "My Google Ads Account",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["provider"] == "GOOGLE_ADS"
        assert body["external_account_id"] == "acc-123"
        assert body["display_name"] == "My Google Ads Account"
        assert body["status"] == "ACTIVE"

        listed = client.get("/connections", headers=OWNER)
        assert listed.status_code == 200
        assert [c["id"] for c in listed.json()] == [body["id"]]

    def test_state_is_single_use(self):
        client = make_client()
        oauth_state = _start(client)
        headers = {**with_step_up(OWNER), **idem("oauth-complete-single-use")}
        payload = {
            "state": oauth_state,
            "external_account_id": "acc-1",
            "display_name": "First",
        }
        first = client.post("/connections/oauth/complete", headers=headers, json=payload)
        assert first.status_code == 201, first.text

        second = client.post(
            "/connections/oauth/complete",
            headers={**with_step_up(OWNER), **idem("oauth-complete-single-use-2")},
            json=payload,
        )
        assert second.status_code == 422, second.text
        assert second.json()["code"] == "VALIDATION_FAILED"

    def test_unknown_state_is_rejected(self):
        client = make_client()
        r = client.post(
            "/connections/oauth/complete",
            headers={**with_step_up(OWNER), **idem("oauth-complete-unknown")},
            json={
                "state": "never-issued-by-this-server",
                "external_account_id": "acc-1",
                "display_name": "X",
            },
        )
        assert r.status_code == 422, r.text
        assert r.json()["code"] == "VALIDATION_FAILED"

    def test_state_started_by_another_tenant_is_rejected(self):
        """A state issued while authenticated as one tenant must never complete for a
        different tenant, even though nothing about the request itself reveals which
        tenant originally started it (state is opaque) -- proves the cross-tenant guard in
        AppState.pop_pending_oauth is load-bearing, not just documented."""
        client = make_client()
        oauth_state = _start(client)  # started as OWNER (demo-tenant)

        r = client.post(
            "/connections/oauth/complete",
            headers={**with_step_up(OTHER_OWNER), **idem("oauth-complete-xtenant")},
            json={
                "state": oauth_state,
                "external_account_id": "acc-1",
                "display_name": "X",
            },
        )
        assert r.status_code == 422, r.text

        # The demo-tenant owner's original state is now consumed and gone too -- a
        # cross-tenant attempt burns the state rather than leaving it replayable.
        retry = client.post(
            "/connections/oauth/complete",
            headers={**with_step_up(OWNER), **idem("oauth-complete-xtenant-retry")},
            json={
                "state": oauth_state,
                "external_account_id": "acc-1",
                "display_name": "X",
            },
        )
        assert retry.status_code == 422, retry.text

    def test_complete_requires_step_up(self):
        client = make_client()
        oauth_state = _start(client)
        r = client.post(
            "/connections/oauth/complete",
            headers={**OWNER, **idem("oauth-complete-nostepup")},
            json={
                "state": oauth_state,
                "external_account_id": "acc-1",
                "display_name": "X",
            },
        )
        assert r.status_code == 403, r.text

    def test_complete_requires_idempotency_key(self):
        client = make_client()
        oauth_state = _start(client)
        r = client.post(
            "/connections/oauth/complete",
            headers=with_step_up(OWNER),
            json={
                "state": oauth_state,
                "external_account_id": "acc-1",
                "display_name": "X",
            },
        )
        assert r.status_code == 422, r.text

    def test_replay_with_same_idempotency_key_does_not_create_a_second_connection(self):
        client = make_client()
        oauth_state = _start(client)
        headers = {**with_step_up(OWNER), **idem("oauth-complete-replay")}
        payload = {
            "state": oauth_state,
            "external_account_id": "acc-1",
            "display_name": "X",
        }
        first = client.post("/connections/oauth/complete", headers=headers, json=payload)
        assert first.status_code == 201, first.text

        replay = client.post("/connections/oauth/complete", headers=headers, json=payload)
        assert replay.status_code == 201, replay.text
        assert replay.json() == first.json()

        listed = client.get("/connections", headers=OWNER)
        assert len(listed.json()) == 1


if __name__ == "__main__":
    unittest.main()
