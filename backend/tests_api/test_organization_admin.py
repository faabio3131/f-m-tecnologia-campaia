"""F2 organization administration: units, RBAC changes and tenant isolation."""

from __future__ import annotations

import unittest

from starlette.testclient import TestClient

from api.session import CSRF_HEADER_NAME
from tests_api.test_commercial_onboarding import (
    ID_MEMBER,
    ID_MEMBER_2,
    ORIGIN,
    TOK_MEMBER,
    TOK_MEMBER_2,
    TOK_OWNER_A,
    TOK_OWNER_B,
    make_client,
    onboard,
)


def headers(csrf: str, idem: str) -> dict[str, str]:
    return {
        CSRF_HEADER_NAME: csrf,
        "X-Step-Up-Token": "f2-test-step-up",
        "Idempotency-Key": idem,
    }


class OrganizationAdministrationTests(unittest.TestCase):
    def _owner(self):
        client = make_client()
        response = onboard(client, TOK_OWNER_A, idem="f2-owner-onboard-0001")
        self.assertEqual(response.status_code, 201, response.text)
        return client, response.json()

    def _invite_accept(
        self,
        owner_client: TestClient,
        owner: dict,
        *,
        email: str,
        token: str,
        role: str = "VIEWER",
        idem_suffix: str,
    ):
        invite = owner_client.post(
            "/member-invitations",
            json={"email": email, "roles": [role]},
            headers=headers(
                owner["session"]["csrf_token"], f"f2-invite-{idem_suffix}-0001"
            ),
        )
        self.assertEqual(invite.status_code, 201, invite.text)
        member_client = TestClient(owner_client.app, base_url=ORIGIN)
        accepted = member_client.post(
            "/onboarding/invitations/accept",
            json={"id_token": token, "accept_token": invite.json()["accept_token"]},
            headers={
                "Origin": ORIGIN,
                "Idempotency-Key": f"f2-accept-{idem_suffix}-0001",
            },
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        return member_client, accepted.json()

    def test_owner_can_create_rename_and_list_units(self) -> None:
        client, owner = self._owner()
        created = client.post(
            "/business-units",
            json={"name": "Filial Santos"},
            headers=headers(owner["session"]["csrf_token"], "f2-create-unit-000001"),
        )
        self.assertEqual(created.status_code, 201, created.text)
        unit_id = created.json()["id"]

        renamed = client.patch(
            f"/business-units/{unit_id}",
            json={"name": "Filial Litoral"},
            headers=headers(owner["session"]["csrf_token"], "f2-rename-unit-000001"),
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()["name"], "Filial Litoral")

        listed = client.get("/business-units")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(
            {item["name"] for item in listed.json()},
            {"Principal", "Filial Litoral"},
        )

    def test_unit_mutation_is_idempotent_and_does_not_duplicate(self) -> None:
        client, owner = self._owner()
        idem = "f2-create-unit-replay-01"
        first = client.post(
            "/business-units",
            json={"name": "Unidade Dois"},
            headers=headers(owner["session"]["csrf_token"], idem),
        )
        second = client.post(
            "/business-units",
            json={"name": "Outro Nome Ignorado No Replay"},
            headers=headers(owner["session"]["csrf_token"], idem),
        )
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(len(client.get("/business-units").json()), 2)

    def test_active_unit_with_member_cannot_be_deactivated(self) -> None:
        client, owner = self._owner()
        principal_id = owner["organization"]["default_business_unit_id"]
        result = client.post(
            f"/business-units/{principal_id}/deactivate",
            headers=headers(owner["session"]["csrf_token"], "f2-unit-in-use-0000001"),
        )
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(result.json()["code"], "INVALID_STATE")

    def test_owner_updates_member_role_and_unit_and_revokes_old_session(self) -> None:
        client, owner = self._owner()
        member_client, accepted = self._invite_accept(
            client,
            owner,
            email=ID_MEMBER.email,
            token=TOK_MEMBER,
            idem_suffix="member-access",
        )
        member_id = accepted["membership"]["id"]

        unit = client.post(
            "/business-units",
            json={"name": "Comercial"},
            headers=headers(owner["session"]["csrf_token"], "f2-create-commercial-01"),
        )
        self.assertEqual(unit.status_code, 201, unit.text)

        updated = client.patch(
            f"/memberships/{member_id}",
            json={"roles": ["MARKETER"], "business_unit_id": unit.json()["id"]},
            headers=headers(owner["session"]["csrf_token"], "f2-update-member-0001"),
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["roles"], ["MARKETER"])
        self.assertEqual(updated.json()["business_unit_id"], unit.json()["id"])

        # Session snapshots old role/unit; mutation must revoke them immediately.
        stale = member_client.get("/me")
        self.assertEqual(stale.status_code, 401, stale.text)

        member_client.cookies.clear()
        relogin = member_client.post(
            "/auth/session",
            json={"id_token": TOK_MEMBER},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(relogin.status_code, 200, relogin.text)
        self.assertEqual(relogin.json()["roles"], ["MARKETER"])
        self.assertEqual(relogin.json()["business_unit_id"], unit.json()["id"])

    def test_admin_cannot_grant_owner_or_edit_owner(self) -> None:
        owner_client, owner = self._owner()
        admin_client, accepted = self._invite_accept(
            owner_client,
            owner,
            email=ID_MEMBER.email,
            token=TOK_MEMBER,
            role="ADMIN",
            idem_suffix="admin",
        )
        admin_csrf = accepted["session"]["csrf_token"]
        owner_id = owner["membership"]["id"]
        result = admin_client.patch(
            f"/memberships/{owner_id}",
            json={
                "roles": ["VIEWER"],
                "business_unit_id": owner["organization"]["default_business_unit_id"],
            },
            headers=headers(admin_csrf, "f2-admin-edit-owner-01"),
        )
        self.assertEqual(result.status_code, 403, result.text)
        self.assertEqual(result.json()["code"], "PERMISSION_DENIED")

    def test_last_owner_cannot_lose_owner_role(self) -> None:
        client, owner = self._owner()
        result = client.patch(
            f"/memberships/{owner['membership']['id']}",
            json={
                "roles": ["ADMIN"],
                "business_unit_id": owner["organization"]["default_business_unit_id"],
            },
            headers=headers(owner["session"]["csrf_token"], "f2-last-owner-guard-01"),
        )
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(result.json()["code"], "INVALID_STATE")

    def test_cross_tenant_unit_and_membership_mutations_fail_closed(self) -> None:
        client_a = make_client()
        a = onboard(
            client_a,
            TOK_OWNER_A,
            company="Tenant A",
            document="51111111000151",
            idem="f2-x-a-onboard-0001",
        ).json()
        client_b = TestClient(client_a.app, base_url=ORIGIN)
        b_response = onboard(
            client_b,
            TOK_OWNER_B,
            company="Tenant B",
            document="52222222000152",
            idem="f2-x-b-onboard-0001",
        )
        self.assertEqual(b_response.status_code, 201, b_response.text)
        b = b_response.json()

        foreign_unit = b["organization"]["default_business_unit_id"]
        unit_result = client_a.patch(
            f"/business-units/{foreign_unit}",
            json={"name": "Nao Pode"},
            headers=headers(a["session"]["csrf_token"], "f2-x-unit-rename-0001"),
        )
        self.assertEqual(unit_result.status_code, 404, unit_result.text)

        _, b_member = self._invite_accept(
            client_b,
            b,
            email=ID_MEMBER_2.email,
            token=TOK_MEMBER_2,
            idem_suffix="cross-tenant-member",
        )
        foreign_member = b_member["membership"]["id"]
        membership_result = client_a.patch(
            f"/memberships/{foreign_member}",
            json={
                "roles": ["VIEWER"],
                "business_unit_id": a["organization"]["default_business_unit_id"],
            },
            headers=headers(a["session"]["csrf_token"], "f2-x-member-update-01"),
        )
        self.assertEqual(membership_result.status_code, 404, membership_result.text)

    def test_safe_ownership_transfer_promotes_successor_before_current_owner_demotes(self) -> None:
        client, owner = self._owner()
        successor_client, accepted = self._invite_accept(
            client,
            owner,
            email=ID_MEMBER.email,
            token=TOK_MEMBER,
            role="ADMIN",
            idem_suffix="ownership-successor",
        )
        successor_id = accepted["membership"]["id"]
        unit_id = owner["organization"]["default_business_unit_id"]

        # Last-owner invariant blocks a premature self-demotion.
        premature = client.patch(
            f"/memberships/{owner['membership']['id']}",
            json={"roles": ["ADMIN"], "business_unit_id": unit_id},
            headers=headers(owner["session"]["csrf_token"], "f2-transfer-premature-01"),
        )
        self.assertEqual(premature.status_code, 409, premature.text)
        self.assertEqual(premature.json()["code"], "INVALID_STATE")

        # Current Owner explicitly promotes the successor through the normal product API.
        promoted = client.patch(
            f"/memberships/{successor_id}",
            json={"roles": ["OWNER"], "business_unit_id": unit_id},
            headers=headers(owner["session"]["csrf_token"], "f2-transfer-promote-001"),
        )
        self.assertEqual(promoted.status_code, 200, promoted.text)
        self.assertEqual(promoted.json()["roles"], ["OWNER"])

        # The successor's pre-promotion session was revoked because authority changed.
        self.assertEqual(successor_client.get("/me").status_code, 401)

        # Only after another active Owner exists may the original Owner demote themself.
        demoted = client.patch(
            f"/memberships/{owner['membership']['id']}",
            json={"roles": ["ADMIN"], "business_unit_id": unit_id},
            headers=headers(owner["session"]["csrf_token"], "f2-transfer-demote-0001"),
        )
        self.assertEqual(demoted.status_code, 200, demoted.text)
        self.assertEqual(demoted.json()["roles"], ["ADMIN"])

        # Self authority change revokes the old Owner session immediately.
        self.assertEqual(client.get("/me").status_code, 401)

        successor_client.cookies.clear()
        relogin = successor_client.post(
            "/auth/session",
            json={"id_token": TOK_MEMBER},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(relogin.status_code, 200, relogin.text)
        self.assertEqual(relogin.json()["roles"], ["OWNER"])
        tenant_id = owner["organization"]["tenant_id"]
        self.assertEqual(
            client.app.state.campaia.organizations.active_owner_count(tenant_id),
            1,
        )

    def test_role_change_is_written_to_audit_trail(self) -> None:
        client, owner = self._owner()
        _, accepted = self._invite_accept(
            client,
            owner,
            email=ID_MEMBER.email,
            token=TOK_MEMBER,
            idem_suffix="audit-role",
        )
        member_id = accepted["membership"]["id"]
        result = client.patch(
            f"/memberships/{member_id}",
            json={
                "roles": ["APPROVER"],
                "business_unit_id": owner["organization"]["default_business_unit_id"],
            },
            headers=headers(owner["session"]["csrf_token"], "f2-role-audit-000001"),
        )
        self.assertEqual(result.status_code, 200, result.text)
        events = [
            event
            for event in client.app.state.campaia.audit.list_for_tenant(
                owner["organization"]["tenant_id"]
            )
            if event.action == "MEMBERSHIP_ACCESS_UPDATE"
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].target, member_id)


if __name__ == "__main__":
    unittest.main()
