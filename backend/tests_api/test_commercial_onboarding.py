"""F1 — commercial onboarding from zero, invitations and access lifecycle.

No tenant/user in these tests is pre-seeded for the tested identities. The fake verifier
only proves a deterministic Google/OIDC identity; every commercial tenant/membership is
created through the product endpoints under test.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone

from starlette.testclient import TestClient

from api.main import create_app
from api.session import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from api.state import AppState
from campaia_core.identity_provider import IdentityError, VerifiedIdentity

ORIGIN = "https://testserver"


class FreshIdentityVerifier:
    def __init__(self, identities: dict[str, VerifiedIdentity]) -> None:
        self.identities = identities

    def verify(self, id_token: str) -> VerifiedIdentity:
        identity = self.identities.get(id_token)
        if identity is None:
            raise IdentityError("token de teste desconhecido")
        return identity


def identity(subject: str, email: str) -> VerifiedIdentity:
    return VerifiedIdentity(
        subject=subject,
        email=email,
        email_verified=True,
        auth_time=datetime.now(timezone.utc),
    )


TOK_OWNER_A = "f1-owner-a-token"
TOK_OWNER_B = "f1-owner-b-token"
TOK_MEMBER = "f1-member-token"
TOK_MEMBER_2 = "f1-member-2-token"
ID_OWNER_A = identity("f1-sub-owner-a", "owner-a@fresh.example")
ID_OWNER_B = identity("f1-sub-owner-b", "owner-b@fresh.example")
ID_MEMBER = identity("f1-sub-member", "member@fresh.example")
ID_MEMBER_2 = identity("f1-sub-member-2", "member2@fresh.example")


def make_client(*, db_path: str | None = None) -> TestClient:
    app = create_app(db_path=db_path, env="test")
    state: AppState = app.state.campaia
    state.id_token_verifier = FreshIdentityVerifier(
        {
            TOK_OWNER_A: ID_OWNER_A,
            TOK_OWNER_B: ID_OWNER_B,
            TOK_MEMBER: ID_MEMBER,
            TOK_MEMBER_2: ID_MEMBER_2,
        }
    )
    state.allowed_origins = frozenset({ORIGIN})
    return TestClient(app, base_url=ORIGIN)


def onboard(
    client: TestClient,
    token: str,
    *,
    company: str = "Empresa Nova",
    document: str | None = "12.345.678/0001-95",
    idem: str = "f1-onboard-0000000001",
):
    payload = {
        "id_token": token,
        "company_name": company,
        "document": document,
        "segment": "servicos",
        "language": "pt-BR",
        "timezone": "America/Sao_Paulo",
        "entry_mode": "TRIAL",
    }
    return client.post(
        "/onboarding/tenant",
        json=payload,
        headers={"Origin": ORIGIN, "Idempotency-Key": idem},
    )


def mut_headers(csrf: str, idem: str) -> dict[str, str]:
    return {
        CSRF_HEADER_NAME: csrf,
        "X-Step-Up-Token": "f1-test-step-up",
        "Idempotency-Key": idem,
    }


class CommercialOnboardingTests(unittest.TestCase):
    def test_unknown_verified_identity_is_not_autoprovisioned_by_login(self) -> None:
        client = make_client()
        r = client.post(
            "/auth/session",
            json={"id_token": TOK_OWNER_A},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")

    def test_new_tenant_from_zero_creates_owner_default_unit_and_session(self) -> None:
        client = make_client()
        r = onboard(client, TOK_OWNER_A)
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertEqual(body["organization"]["name"], "Empresa Nova")
        self.assertEqual(body["organization"]["document"], "12345678000195")
        self.assertTrue(body["organization"]["default_business_unit_id"].startswith("bu_"))
        self.assertEqual(body["membership"]["roles"], ["OWNER"])
        self.assertEqual(body["membership"]["status"], "ACTIVE")
        self.assertEqual(body["session"]["tenant_id"], body["organization"]["tenant_id"])
        self.assertEqual(
            body["session"]["business_unit_id"],
            body["organization"]["default_business_unit_id"],
        )
        self.assertIn(SESSION_COOKIE_NAME, r.cookies)

        me = client.get("/me")
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["tenant_id"], body["organization"]["tenant_id"])
        self.assertIn("OWNER", me.json()["roles"])

    def test_after_explicit_onboarding_normal_login_resolves_dynamic_membership(self) -> None:
        client = make_client()
        created = onboard(client, TOK_OWNER_A)
        self.assertEqual(created.status_code, 201, created.text)
        client.cookies.clear()

        logged = client.post(
            "/auth/session",
            json={"id_token": TOK_OWNER_A},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(logged.status_code, 200, logged.text)
        self.assertEqual(
            logged.json()["tenant_id"], created.json()["organization"]["tenant_id"]
        )

    def test_onboarding_replay_same_idempotency_key_does_not_duplicate_tenant(self) -> None:
        client = make_client()
        first = onboard(client, TOK_OWNER_A, idem="f1-replay-onboard-0001")
        self.assertEqual(first.status_code, 201, first.text)
        tenant_id = first.json()["organization"]["tenant_id"]
        client.cookies.clear()

        second = onboard(client, TOK_OWNER_A, idem="f1-replay-onboard-0001")
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["organization"]["tenant_id"], tenant_id)
        self.assertEqual(len(client.app.state.campaia.organizations._items), 1)

    def test_same_document_cannot_create_second_tenant(self) -> None:
        client_a = make_client()
        # Same application/state is required to test global uniqueness.
        app = client_a.app
        r1 = onboard(client_a, TOK_OWNER_A, document="12.345.678/0001-95")
        self.assertEqual(r1.status_code, 201, r1.text)
        client_a.cookies.clear()

        r2 = onboard(
            client_a,
            TOK_OWNER_B,
            company="Duplicada",
            document="12345678000195",
            idem="f1-duplicate-doc-00001",
        )
        self.assertEqual(r2.status_code, 409, r2.text)
        self.assertEqual(r2.json()["code"], "INVALID_STATE")
        self.assertEqual(len(app.state.campaia.organizations._items), 1)

    def test_client_cannot_self_assign_a_paid_plan_or_user_entitlement(self) -> None:
        client = make_client()
        r = client.post(
            "/onboarding/tenant",
            json={
                "id_token": TOK_OWNER_A,
                "company_name": "Empresa",
                "segment": "servicos",
                "timezone": "America/Sao_Paulo",
                "plan_id": "escala",
            },
            headers={"Origin": ORIGIN, "Idempotency-Key": "f1-no-client-plan-0001"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(len(client.app.state.campaia.organizations._items), 0)

    def test_invalid_timezone_is_rejected_before_any_tenant_is_created(self) -> None:
        client = make_client()
        r = client.post(
            "/onboarding/tenant",
            json={
                "id_token": TOK_OWNER_A,
                "company_name": "Empresa",
                "segment": "servicos",
                "timezone": "Mars/Olympus",
            },
            headers={"Origin": ORIGIN, "Idempotency-Key": "f1-invalid-tz-000001"},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(len(client.app.state.campaia.organizations._items), 0)


class InvitationAndAccessLifecycleTests(unittest.TestCase):
    def _owner(self, *, plan_id: str | None = None):
        client = make_client()
        r = onboard(client, TOK_OWNER_A)
        self.assertEqual(r.status_code, 201, r.text)
        if plan_id is not None:
            tenant_id = r.json()["organization"]["tenant_id"]
            organization = client.app.state.campaia.organizations.get_organization(tenant_id)
            self.assertIsNotNone(organization)
            organization.tenant.plan_id = plan_id
            client.app.state.campaia.organizations._persist(organization)
        return client, r.json()

    def _invite(
        self,
        client: TestClient,
        csrf: str,
        *,
        email: str,
        roles: list[str],
        idem: str,
    ):
        return client.post(
            "/member-invitations",
            json={"email": email, "roles": roles},
            headers=mut_headers(csrf, idem),
        )

    def _accept(self, client: TestClient, token: str, invite_token: str, *, idem: str):
        return client.post(
            "/onboarding/invitations/accept",
            json={"id_token": token, "accept_token": invite_token},
            headers={"Origin": ORIGIN, "Idempotency-Key": idem},
        )

    def test_owner_invites_user_and_acceptance_creates_membership_and_session(self) -> None:
        owner_client, owner = self._owner()
        invite = self._invite(
            owner_client,
            owner["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem="f1-invite-viewer-00001",
        )
        self.assertEqual(invite.status_code, 201, invite.text)
        accept_token = invite.json()["accept_token"]
        self.assertTrue(accept_token)

        member_client = make_client()
        # Use the SAME backend app/state as the owner; TestClient around same ASGI app,
        # but separate cookie jar, exactly two different browsers.
        member_client = TestClient(owner_client.app, base_url=ORIGIN)
        accepted = self._accept(
            member_client,
            TOK_MEMBER,
            accept_token,
            idem="f1-accept-viewer-00001",
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(
            accepted.json()["organization"]["tenant_id"],
            owner["organization"]["tenant_id"],
        )
        self.assertEqual(accepted.json()["membership"]["roles"], ["VIEWER"])
        self.assertIn(SESSION_COOKIE_NAME, accepted.cookies)

        members = owner_client.get("/memberships")
        self.assertEqual(members.status_code, 200, members.text)
        self.assertEqual(len(members.json()), 2)

    def test_invitation_cannot_be_accepted_by_different_email(self) -> None:
        owner_client, owner = self._owner()
        invite = self._invite(
            owner_client,
            owner["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem="f1-invite-email-bind-01",
        )
        self.assertEqual(invite.status_code, 201, invite.text)

        other = TestClient(owner_client.app, base_url=ORIGIN)
        r = self._accept(
            other,
            TOK_MEMBER_2,
            invite.json()["accept_token"],
            idem="f1-wrong-email-accept-1",
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")

    def test_user_limit_is_server_configuration_by_plan_not_client_value(self) -> None:
        owner_client, owner = self._owner(plan_id="starter")
        owner_client.app.state.campaia.plan_user_limits = {"starter": 1}
        r = self._invite(
            owner_client,
            owner["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem="f1-plan-limit-0000001",
        )
        self.assertEqual(r.status_code, 429, r.text)
        self.assertEqual(r.json()["code"], "QUOTA_EXHAUSTED")
        self.assertEqual(r.json()["details"]["max_users"], 1)

    def test_invitation_replay_survives_quota_change_and_never_duplicates(self) -> None:
        owner_client, owner = self._owner(plan_id="starter")
        owner_client.app.state.campaia.plan_user_limits = {"starter": 2}
        key = "f1-invite-replay-000001"
        first = self._invite(
            owner_client,
            owner["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem=key,
        )
        self.assertEqual(first.status_code, 201, first.text)
        invitation_id = first.json()["id"]
        self.assertTrue(first.json()["accept_token"])

        # Owner + pending invite now fill the cap. Exact replay must still return the
        # original logical invitation instead of being rejected by the later quota state.
        second = self._invite(
            owner_client,
            owner["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem=key,
        )
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["id"], invitation_id)
        self.assertIsNone(second.json()["accept_token"])
        invitations = owner_client.app.state.campaia.organizations.list_invitations_for_tenant(
            owner["organization"]["tenant_id"]
        )
        self.assertEqual(len(invitations), 1)

    def test_admin_cannot_invite_owner(self) -> None:
        owner_client, owner = self._owner()
        invite_admin = self._invite(
            owner_client,
            owner["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["ADMIN"],
            idem="f1-invite-admin-000001",
        )
        self.assertEqual(invite_admin.status_code, 201, invite_admin.text)

        admin_client = TestClient(owner_client.app, base_url=ORIGIN)
        accepted = self._accept(
            admin_client,
            TOK_MEMBER,
            invite_admin.json()["accept_token"],
            idem="f1-accept-admin-000001",
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        admin_csrf = accepted.json()["session"]["csrf_token"]

        r = self._invite(
            admin_client,
            admin_csrf,
            email=ID_MEMBER_2.email,
            roles=["OWNER"],
            idem="f1-admin-invite-owner-01",
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["code"], "PERMISSION_DENIED")

    def test_deactivation_is_soft_revokes_session_and_reactivation_preserves_membership(self) -> None:
        owner_client, owner = self._owner()
        invite = self._invite(
            owner_client,
            owner["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem="f1-invite-soft-delete-1",
        )
        member_client = TestClient(owner_client.app, base_url=ORIGIN)
        accepted = self._accept(
            member_client,
            TOK_MEMBER,
            invite.json()["accept_token"],
            idem="f1-accept-soft-delete-1",
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        member_id = accepted.json()["membership"]["id"]

        deactivated = owner_client.post(
            f"/memberships/{member_id}/deactivate",
            headers=mut_headers(
                owner["session"]["csrf_token"], "f1-deactivate-member-01"
            ),
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        self.assertEqual(deactivated.json()["status"], "INACTIVE")
        self.assertEqual(deactivated.json()["id"], member_id)

        stale_session = member_client.get("/me")
        self.assertEqual(stale_session.status_code, 401, stale_session.text)

        reactivated = owner_client.post(
            f"/memberships/{member_id}/reactivate",
            headers=mut_headers(
                owner["session"]["csrf_token"], "f1-reactivate-member-01"
            ),
        )
        self.assertEqual(reactivated.status_code, 200, reactivated.text)
        self.assertEqual(reactivated.json()["status"], "ACTIVE")
        self.assertEqual(reactivated.json()["id"], member_id)

        member_client.cookies.clear()
        relogin = member_client.post(
            "/auth/session",
            json={"id_token": TOK_MEMBER},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(relogin.status_code, 200, relogin.text)
        self.assertEqual(relogin.json()["user_id"], member_id)

    def test_owner_cannot_invite_user_into_another_tenants_business_unit(self) -> None:
        client_a = make_client()
        a_resp = onboard(
            client_a,
            TOK_OWNER_A,
            company="Tenant A",
            document="31111111000131",
            idem="f1-xtenant-unit-a-0001",
        )
        self.assertEqual(a_resp.status_code, 201, a_resp.text)
        a = a_resp.json()

        client_b = TestClient(client_a.app, base_url=ORIGIN)
        b_resp = onboard(
            client_b,
            TOK_OWNER_B,
            company="Tenant B",
            document="32222222000132",
            idem="f1-xtenant-unit-b-0001",
        )
        self.assertEqual(b_resp.status_code, 201, b_resp.text)
        b = b_resp.json()

        foreign_unit_id = b["organization"]["default_business_unit_id"]
        r = client_a.post(
            "/member-invitations",
            json={
                "email": ID_MEMBER.email,
                "roles": ["VIEWER"],
                "business_unit_id": foreign_unit_id,
            },
            headers=mut_headers(
                a["session"]["csrf_token"], "f1-xtenant-unit-invite-01"
            ),
        )
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["code"], "NOT_FOUND")
        self.assertEqual(
            client_a.app.state.campaia.organizations.list_invitations_for_tenant(
                a["organization"]["tenant_id"]
            ),
            [],
        )

    def test_owner_cannot_deactivate_or_reactivate_membership_from_another_tenant(self) -> None:
        client_a = make_client()
        a_resp = onboard(
            client_a,
            TOK_OWNER_A,
            company="Tenant A",
            document="41111111000141",
            idem="f1-xtenant-member-a-001",
        )
        self.assertEqual(a_resp.status_code, 201, a_resp.text)
        a = a_resp.json()

        client_b = TestClient(client_a.app, base_url=ORIGIN)
        b_resp = onboard(
            client_b,
            TOK_OWNER_B,
            company="Tenant B",
            document="42222222000142",
            idem="f1-xtenant-member-b-001",
        )
        self.assertEqual(b_resp.status_code, 201, b_resp.text)
        b = b_resp.json()

        invite = self._invite(
            client_b,
            b["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem="f1-xtenant-member-invite-1",
        )
        self.assertEqual(invite.status_code, 201, invite.text)

        member_client = TestClient(client_a.app, base_url=ORIGIN)
        accepted = self._accept(
            member_client,
            TOK_MEMBER,
            invite.json()["accept_token"],
            idem="f1-xtenant-member-accept-1",
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        foreign_member_id = accepted.json()["membership"]["id"]

        for operation in ("deactivate", "reactivate"):
            r = client_a.post(
                f"/memberships/{foreign_member_id}/{operation}",
                headers=mut_headers(
                    a["session"]["csrf_token"],
                    f"f1-xtenant-{operation}-0001",
                ),
            )
            self.assertEqual(r.status_code, 404, r.text)
            self.assertEqual(r.json()["code"], "NOT_FOUND")

        tenant_b_members = client_b.get("/memberships")
        self.assertEqual(tenant_b_members.status_code, 200, tenant_b_members.text)
        foreign_member = next(
            member
            for member in tenant_b_members.json()
            if member["id"] == foreign_member_id
        )
        self.assertEqual(foreign_member["status"], "ACTIVE")

    def test_multi_company_identity_can_switch_between_commercial_memberships(self) -> None:
        # Tenant A
        client_a = make_client()
        a = onboard(
            client_a,
            TOK_OWNER_A,
            company="Tenant A",
            document="11111111000111",
            idem="f1-tenant-a-000000001",
        ).json()
        inv_a = self._invite(
            client_a,
            a["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem="f1-multi-invite-a-0001",
        )
        member_browser = TestClient(client_a.app, base_url=ORIGIN)
        acc_a = self._accept(
            member_browser,
            TOK_MEMBER,
            inv_a.json()["accept_token"],
            idem="f1-multi-accept-a-0001",
        )
        self.assertEqual(acc_a.status_code, 200, acc_a.text)
        member_a_id = acc_a.json()["membership"]["id"]

        # Tenant B is created in the SAME state by another verified owner.
        owner_b_browser = TestClient(client_a.app, base_url=ORIGIN)
        b_resp = onboard(
            owner_b_browser,
            TOK_OWNER_B,
            company="Tenant B",
            document="22222222000122",
            idem="f1-tenant-b-000000001",
        )
        self.assertEqual(b_resp.status_code, 201, b_resp.text)
        b = b_resp.json()
        inv_b = self._invite(
            owner_b_browser,
            b["session"]["csrf_token"],
            email=ID_MEMBER.email,
            roles=["VIEWER"],
            idem="f1-multi-invite-b-0001",
        )
        self.assertEqual(inv_b.status_code, 201, inv_b.text)

        member_browser.cookies.clear()
        acc_b = self._accept(
            member_browser,
            TOK_MEMBER,
            inv_b.json()["accept_token"],
            idem="f1-multi-accept-b-0001",
        )
        self.assertEqual(acc_b.status_code, 200, acc_b.text)
        member_b_id = acc_b.json()["membership"]["id"]

        memberships = member_browser.get("/me/memberships")
        self.assertEqual(memberships.status_code, 200, memberships.text)
        ids = {item["user_id"] for item in memberships.json()["memberships"]}
        self.assertEqual(ids, {member_a_id, member_b_id})

        csrf = acc_b.json()["session"]["csrf_token"]
        switched = member_browser.post(
            "/auth/session/switch",
            json={"user_id": member_a_id},
            headers={CSRF_HEADER_NAME: csrf},
        )
        self.assertEqual(switched.status_code, 200, switched.text)
        self.assertEqual(switched.json()["tenant_id"], a["organization"]["tenant_id"])


class CommercialOnboardingPersistenceTests(unittest.TestCase):
    def test_deactivated_invited_membership_stays_inactive_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "campaia-f1-lifecycle.sqlite")
            owner = make_client(db_path=db_path)
            created = onboard(
                owner,
                TOK_OWNER_A,
                company="Lifecycle",
                document="55555555000155",
                idem="f1-persist-lifecycle-01",
            )
            self.assertEqual(created.status_code, 201, created.text)
            owner_body = created.json()

            invite = owner.post(
                "/member-invitations",
                json={"email": ID_MEMBER.email, "roles": ["VIEWER"]},
                headers=mut_headers(
                    owner_body["session"]["csrf_token"], "f1-persist-invite-0001"
                ),
            )
            self.assertEqual(invite.status_code, 201, invite.text)

            member = TestClient(owner.app, base_url=ORIGIN)
            accepted = member.post(
                "/onboarding/invitations/accept",
                json={
                    "id_token": TOK_MEMBER,
                    "accept_token": invite.json()["accept_token"],
                },
                headers={"Origin": ORIGIN, "Idempotency-Key": "f1-persist-accept-0001"},
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)
            membership_id = accepted.json()["membership"]["id"]

            deactivated = owner.post(
                f"/memberships/{membership_id}/deactivate",
                headers=mut_headers(
                    owner_body["session"]["csrf_token"], "f1-persist-deactivate-01"
                ),
            )
            self.assertEqual(deactivated.status_code, 200, deactivated.text)
            owner.app.state.campaia.db.close()

            restarted = make_client(db_path=db_path)
            rejected = restarted.post(
                "/auth/session",
                json={"id_token": TOK_MEMBER},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(rejected.status_code, 403, rejected.text)

            owner_login = restarted.post(
                "/auth/session",
                json={"id_token": TOK_OWNER_A},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(owner_login.status_code, 200, owner_login.text)
            reactivated = restarted.post(
                f"/memberships/{membership_id}/reactivate",
                headers=mut_headers(
                    owner_login.json()["csrf_token"], "f1-persist-reactivate-01"
                ),
            )
            self.assertEqual(reactivated.status_code, 200, reactivated.text)
            self.assertEqual(reactivated.json()["id"], membership_id)
            restarted.app.state.campaia.db.close()

            restarted_again = make_client(db_path=db_path)
            member_login = restarted_again.post(
                "/auth/session",
                json={"id_token": TOK_MEMBER},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(member_login.status_code, 200, member_login.text)
            self.assertEqual(member_login.json()["user_id"], membership_id)
            restarted_again.app.state.campaia.db.close()

    def test_commercial_identity_survives_sqlite_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "campaia-f1.sqlite")
            client1 = make_client(db_path=db_path)
            created = onboard(
                client1,
                TOK_OWNER_A,
                company="Persistente",
                document="33333333000133",
                idem="f1-persist-onboard-001",
            )
            self.assertEqual(created.status_code, 201, created.text)
            tenant_id = created.json()["organization"]["tenant_id"]
            client1.app.state.campaia.db.close()

            client2 = make_client(db_path=db_path)
            logged = client2.post(
                "/auth/session",
                json={"id_token": TOK_OWNER_A},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(logged.status_code, 200, logged.text)
            self.assertEqual(logged.json()["tenant_id"], tenant_id)
            client2.app.state.campaia.db.close()


if __name__ == "__main__":
    unittest.main()
