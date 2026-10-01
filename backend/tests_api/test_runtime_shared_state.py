"""F3 runtime atomicity and shared-state tests using two live app instances."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from starlette.testclient import TestClient

from api.main import create_app
from api.state import PendingOAuthState
from campaia_core.permissions import Role

from tests_api.test_commercial_onboarding import (
    FreshIdentityVerifier,
    ID_MEMBER,
    ID_OWNER_A,
    ORIGIN,
    TOK_OWNER_A,
    onboard,
)
from tests_api.test_helpers import OWNER, idem, publish_ready_campaign, with_step_up


class RuntimeSharedStateTests(unittest.TestCase):
    def _apps(self, path: str):
        a = create_app(db_path=path, env="test")
        b = create_app(db_path=path, env="test")
        for app in (a, b):
            app.state.campaia.id_token_verifier = FreshIdentityVerifier(
                {TOK_OWNER_A: ID_OWNER_A}
            )
            app.state.campaia.allowed_origins = frozenset({ORIGIN})
        return (
            TestClient(a, base_url=ORIGIN),
            TestClient(b, base_url=ORIGIN),
        )

    def test_session_created_on_replica_a_is_readable_and_revocable_on_b(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            principal = a.app.state.campaia.tokens["demo-owner-token"]
            now = datetime.now(timezone.utc)
            record = a.app.state.campaia.sessions.create(
                principal,
                now=now,
                available_principals=(principal,),
                subject="shared-subject",
            )
            seen = b.app.state.campaia.sessions.get(record.session_id)
            self.assertIsNotNone(seen)
            self.assertEqual(seen.principal.tenant_id, principal.tenant_id)

            b.app.state.campaia.sessions.invalidate(record.session_id)
            self.assertIsNone(a.app.state.campaia.sessions.get(record.session_id))

    def test_step_up_is_shared_and_invalidation_crosses_replicas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            at = datetime.now(timezone.utc)
            a.app.state.campaia.record_step_up(
                "demo-tenant", "user-owner-1", "session:opaque", at=at
            )
            self.assertEqual(
                b.app.state.campaia.last_step_up(
                    "demo-tenant", "user-owner-1", "session:opaque"
                ),
                at,
            )
            b.app.state.campaia.invalidate_step_up_for_session("session:opaque")
            self.assertIsNone(
                a.app.state.campaia.last_step_up(
                    "demo-tenant", "user-owner-1", "session:opaque"
                )
            )

    def test_oauth_state_is_shared_and_redeemed_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            now = datetime.now(timezone.utc)
            a.app.state.campaia.start_oauth_state(
                "state-shared",
                tenant_id="demo-tenant",
                provider="GOOGLE_ADS",
                now=now,
                user_id="user-owner-1",
                session_key="session:one",
                step_up_verified_at=now,
            )
            first = b.app.state.campaia.redeem_oauth_state(
                "state-shared", tenant_id="demo-tenant", now=now
            )
            self.assertIsNotNone(first)
            self.assertEqual(first.provider, "GOOGLE_ADS")
            self.assertIsNone(
                a.app.state.campaia.redeem_oauth_state(
                    "state-shared", tenant_id="demo-tenant", now=now
                )
            )

    def test_idempotency_transaction_rolls_back_durable_side_effects_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            state = a.app.state.campaia

            def failing_operation():
                state.audit.append(
                    tenant_id="demo-tenant",
                    actor="user-owner-1",
                    action="F3_SHOULD_ROLL_BACK",
                    target="rollback-target",
                )
                raise RuntimeError("injected failure")

            with self.assertRaisesRegex(RuntimeError, "injected failure"):
                state.idempotency.execute(
                    "demo-tenant",
                    "http:f3:rollback-key",
                    failing_operation,
                )

            # Read through a different live replica so only committed database state counts.
            events = b.app.state.campaia.audit.list_for_tenant("demo-tenant")
            self.assertFalse(any(e.action == "F3_SHOULD_ROLL_BACK" for e in events))
            self.assertIsNone(
                b.app.state.campaia.idempotency.get(
                    "demo-tenant", "http:f3:rollback-key"
                )
            )

    def test_persistent_repository_reads_fresh_state_written_by_other_replica(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            created = a.app.state.campaia.brand_profiles.create(
                "demo-tenant",
                name="Replica A",
                tone="preciso",
                colors=[],
                differentiators=[],
                restrictions=[],
            )
            seen = b.app.state.campaia.brand_profiles.get(
                "demo-tenant", created.brand_profile_id
            )
            self.assertIsNotNone(seen)
            self.assertEqual(seen.name, "Replica A")

            seen.name = "Replica B"
            reread = a.app.state.campaia.brand_profiles.get(
                "demo-tenant", created.brand_profile_id
            )
            self.assertEqual(reread.name, "Replica B")


    def test_organization_membership_read_is_fresh_across_replicas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            state_a = a.app.state.campaia
            state_b = b.app.state.campaia

            tenant, unit, membership = state_a.organizations.create_tenant_bundle(
                company_name="Replica Org",
                document="60111111000160",
                segment="servicos",
                language="pt-BR",
                timezone_name="America/Sao_Paulo",
                entry_mode="TRIAL",
                plan_id=None,
                identity_subject=ID_OWNER_A.subject,
                email=ID_OWNER_A.email,
            )
            # Replica B deliberately caches the old OWNER snapshot first.
            cached = state_b.organizations.get_membership(
                tenant.tenant_id, membership.membership_id
            )
            self.assertEqual(cached.roles, frozenset({Role.OWNER}))

            def mutate():
                updated = state_a.organizations.update_membership_access(
                    tenant.tenant_id,
                    membership.membership_id,
                    roles=frozenset({Role.ADMIN}),
                    business_unit_id=unit.business_unit_id,
                )
                return {"roles": sorted(role.value for role in updated.roles)}

            state_a.idempotency.execute(
                tenant.tenant_id, "http:f3-org-live-read-0001", mutate
            )

            reread = state_b.organizations.get_membership(
                tenant.tenant_id, membership.membership_id
            )
            self.assertEqual(reread.roles, frozenset({Role.ADMIN}))

    def test_invitation_failure_rolls_back_invite_audit_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            created = onboard(a, TOK_OWNER_A, idem="f3-invite-owner-0001")
            self.assertEqual(created.status_code, 201, created.text)
            body = created.json()
            tenant_id = body["organization"]["tenant_id"]
            idem_key = "f3-invite-rollback-0001"

            with patch.object(
                a.app.state.campaia.audit,
                "append",
                side_effect=RuntimeError("injected invitation failure"),
            ):
                failed = a.post(
                    "/member-invitations",
                    json={"email": ID_MEMBER.email, "roles": ["VIEWER"]},
                    headers={
                        "x-csrf-token": body["session"]["csrf_token"],
                        "X-Step-Up-Token": "f3-test-step-up",
                        "Idempotency-Key": idem_key,
                    },
                )
            self.assertEqual(failed.status_code, 500, failed.text)
            self.assertEqual(
                b.app.state.campaia.organizations.list_invitations_for_tenant(tenant_id),
                [],
            )
            self.assertIsNone(
                b.app.state.campaia.idempotency.get(
                    tenant_id, f"http:create_member_invitation:{idem_key}"
                )
            )

    def test_publish_failure_rolls_back_pre_publish_transitions_and_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.sqlite3")
            a, b = self._apps(path)
            camp, decision, approval = publish_ready_campaign(a, headers=OWNER)
            request_idem = idem("f3-publish-rollback-0001")

            with patch(
                "api.routes_campaigns.PublicationSaga.run",
                side_effect=RuntimeError("injected publish failure"),
            ):
                failed = a.post(
                    f"/campaigns/{camp['id']}/publish",
                    headers={**with_step_up(OWNER), **request_idem},
                    json={
                        "policy_decision_id": decision["policy_decision_id"],
                        "approval_id": approval["id"],
                    },
                )
            self.assertEqual(failed.status_code, 500, failed.text)

            campaign = b.app.state.campaia.campaigns.get("demo-tenant", camp["id"])
            self.assertIsNotNone(campaign)
            self.assertEqual(campaign.campaign.state.value, "VALIDATED")

            approval_after = b.app.state.campaia.approvals.get(
                "demo-tenant", approval["id"]
            )
            self.assertIsNotNone(approval_after)
            self.assertEqual(approval_after.status, "APPROVED")
            self.assertIsNone(
                b.app.state.campaia.idempotency.get(
                    "demo-tenant",
                    f"http:publish:{request_idem['Idempotency-Key']}",
                )
            )


if __name__ == "__main__":
    unittest.main()
