"""F2 persistence proof for commercial organization state.

F3/F4 still own PostgreSQL and multi-replica production semantics. This test proves that
the CURRENT durable RecordTable runtime does not lose commercial units, memberships or
roles across a backend process restart.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from starlette.testclient import TestClient

from tests_api.test_commercial_onboarding import (
    ID_MEMBER,
    ORIGIN,
    TOK_MEMBER,
    TOK_OWNER_A,
    make_client,
    onboard,
)
from tests_api.test_organization_admin import headers


class OrganizationPersistenceTests(unittest.TestCase):
    def test_units_memberships_and_roles_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "campaia-f2.sqlite3")
            first = make_client(db_path=db_path)
            owner_response = onboard(
                first,
                TOK_OWNER_A,
                company="Persistencia F2",
                document="61111111000161",
                idem="f2-persist-onboard-0001",
            )
            self.assertEqual(owner_response.status_code, 201, owner_response.text)
            owner = owner_response.json()

            unit = first.post(
                "/business-units",
                json={"name": "Comercial Persistente"},
                headers=headers(
                    owner["session"]["csrf_token"], "f2-persist-unit-000001"
                ),
            )
            self.assertEqual(unit.status_code, 201, unit.text)
            unit_id = unit.json()["id"]

            invite = first.post(
                "/member-invitations",
                json={
                    "email": ID_MEMBER.email,
                    "roles": ["VIEWER"],
                    "business_unit_id": unit_id,
                },
                headers=headers(
                    owner["session"]["csrf_token"], "f2-persist-invite-00001"
                ),
            )
            self.assertEqual(invite.status_code, 201, invite.text)

            member_client = TestClient(first.app, base_url=ORIGIN)
            accepted = member_client.post(
                "/onboarding/invitations/accept",
                json={
                    "id_token": TOK_MEMBER,
                    "accept_token": invite.json()["accept_token"],
                },
                headers={
                    "Origin": ORIGIN,
                    "Idempotency-Key": "f2-persist-accept-00001",
                },
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)
            member_id = accepted.json()["membership"]["id"]

            updated = first.patch(
                f"/memberships/{member_id}",
                json={"roles": ["APPROVER"], "business_unit_id": unit_id},
                headers=headers(
                    owner["session"]["csrf_token"], "f2-persist-role-0000001"
                ),
            )
            self.assertEqual(updated.status_code, 200, updated.text)

            first.app.state.campaia.db.close()

            restarted = make_client(db_path=db_path)
            owner_login = restarted.post(
                "/auth/session",
                json={"id_token": TOK_OWNER_A},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(owner_login.status_code, 200, owner_login.text)

            units = restarted.get("/business-units")
            self.assertEqual(units.status_code, 200, units.text)
            persisted_unit = next(
                (candidate for candidate in units.json() if candidate["id"] == unit_id),
                None,
            )
            self.assertIsNotNone(persisted_unit)
            self.assertEqual(persisted_unit["name"], "Comercial Persistente")
            self.assertEqual(persisted_unit["status"], "ACTIVE")

            members = restarted.get("/memberships")
            self.assertEqual(members.status_code, 200, members.text)
            persisted_member = next(
                (candidate for candidate in members.json() if candidate["id"] == member_id),
                None,
            )
            self.assertIsNotNone(persisted_member)
            self.assertEqual(persisted_member["roles"], ["APPROVER"])
            self.assertEqual(persisted_member["business_unit_id"], unit_id)

            member_login = restarted.post(
                "/auth/session",
                json={"id_token": TOK_MEMBER},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(member_login.status_code, 200, member_login.text)
            self.assertEqual(member_login.json()["roles"], ["APPROVER"])
            self.assertEqual(member_login.json()["business_unit_id"], unit_id)

            restarted.app.state.campaia.db.close()


if __name__ == "__main__":
    unittest.main()
