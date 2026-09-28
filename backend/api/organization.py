"""Commercial organization/onboarding aggregate for CampaIA F1.

This module deliberately lives in the API/application layer. F1 needs a real product flow
for creating tenants, the default business unit, memberships and invitations, but F2/F3
still own the normalized IAM schema and production PostgreSQL transaction model.

Persistence therefore follows the CURRENT BFF pattern: one tenant aggregate per RecordTable
row. Initial tenant + default unit + first Owner are committed as ONE aggregate record, so
F1 never creates a half-provisioned tenant in the current SQLite/in-memory runtime. F3 still
remains the production atomicity gate for multi-worker/Postgres semantics.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from campaia_core.permissions import Role

from .repositories import _attach_persistence, _wrap_loaded, new_id, now_utc

if TYPE_CHECKING:
    from .db import RecordTable

INVITATION_TTL = timedelta(days=7)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_document(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(ch for ch in value.strip().upper() if ch.isalnum())
    return normalized or None


def _invite_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass
class TenantRecord:
    tenant_id: str
    name: str
    document_normalized: str | None
    segment: str
    language: str
    timezone: str
    entry_mode: str
    plan_id: str | None
    status: str = "ACTIVE"  # ACTIVE | INACTIVE
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class BusinessUnitRecord:
    business_unit_id: str
    tenant_id: str
    name: str
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class MembershipRecord:
    membership_id: str
    tenant_id: str
    identity_subject: str
    email: str
    roles: frozenset[Role]
    business_unit_id: str | None
    status: str = "ACTIVE"  # ACTIVE | INACTIVE
    created_at: datetime = field(default_factory=now_utc)
    updated_at: datetime = field(default_factory=now_utc)
    deactivated_at: datetime | None = None


@dataclass
class InvitationRecord:
    invitation_id: str
    tenant_id: str
    email: str
    roles: frozenset[Role]
    business_unit_id: str | None
    token_digest: str
    created_by: str
    status: str = "PENDING"  # PENDING | ACCEPTED | REVOKED | EXPIRED
    created_at: datetime = field(default_factory=now_utc)
    expires_at: datetime = field(default_factory=lambda: now_utc() + INVITATION_TTL)
    accepted_by: str | None = None
    accepted_at: datetime | None = None


@dataclass
class TenantOrganization:
    tenant: TenantRecord
    business_units: dict[str, BusinessUnitRecord]
    memberships: dict[str, MembershipRecord]
    invitations: dict[str, InvitationRecord]


class OrganizationRepository:
    """Tenant aggregate repository used by F1 commercial onboarding."""

    def __init__(self, table: "RecordTable | None" = None) -> None:
        self._table = table
        self._items: dict[str, TenantOrganization] = {}
        if table is not None:
            for tenant_id, row_tenant_id, obj in table.all_rows():
                self._items[tenant_id] = _wrap_loaded(table, tenant_id, row_tenant_id, obj)

    def _persist(self, organization: TenantOrganization) -> None:
        """Force-persist the aggregate after mutations to objects added after initial wrapping.

        RecordTable's notify wrapper observes mutations of objects present when the aggregate
        is first wrapped. F1 adds invitations/memberships later; forcing the aggregate write
        here makes their subsequent status mutations restart-safe without changing the
        generic persistence machinery for unrelated modules.
        """
        if self._table is not None:
            tenant_id = organization.tenant.tenant_id
            self._table.put(tenant_id, tenant_id, organization)

    def get_organization(self, tenant_id: str) -> TenantOrganization | None:
        return self._items.get(tenant_id)

    def find_by_document(self, document: str | None) -> TenantOrganization | None:
        normalized = normalize_document(document)
        if normalized is None:
            return None
        for organization in self._items.values():
            if organization.tenant.document_normalized == normalized:
                return organization
        return None

    def create_tenant_bundle(
        self,
        *,
        company_name: str,
        document: str | None,
        segment: str,
        language: str,
        timezone_name: str,
        entry_mode: str,
        plan_id: str | None,
        identity_subject: str,
        email: str,
    ) -> tuple[TenantRecord, BusinessUnitRecord, MembershipRecord]:
        normalized_document = normalize_document(document)
        if normalized_document is not None and self.find_by_document(normalized_document) is not None:
            raise ValueError("DOCUMENT_ALREADY_EXISTS")

        tenant_id = new_id("tenant")
        unit_id = new_id("bu")
        membership_id = new_id("member")

        tenant = TenantRecord(
            tenant_id=tenant_id,
            name=company_name.strip(),
            document_normalized=normalized_document,
            segment=segment.strip(),
            language=language.strip(),
            timezone=timezone_name.strip(),
            entry_mode=entry_mode,
            plan_id=plan_id.strip() if plan_id else None,
        )
        unit = BusinessUnitRecord(
            business_unit_id=unit_id,
            tenant_id=tenant_id,
            name="Principal",
        )
        membership = MembershipRecord(
            membership_id=membership_id,
            tenant_id=tenant_id,
            identity_subject=identity_subject,
            email=normalize_email(email),
            roles=frozenset({Role.OWNER}),
            business_unit_id=unit_id,
        )
        organization = TenantOrganization(
            tenant=tenant,
            business_units={unit_id: unit},
            memberships={membership_id: membership},
            invitations={},
        )
        organization = _attach_persistence(self._table, tenant_id, tenant_id, organization)
        self._items[tenant_id] = organization
        return organization.tenant, organization.business_units[unit_id], organization.memberships[membership_id]

    def list_active_memberships_for_identity(
        self, *, email: str, subject: str | None
    ) -> list[MembershipRecord]:
        normalized_email = normalize_email(email)
        result: list[MembershipRecord] = []
        for organization in self._items.values():
            if organization.tenant.status != "ACTIVE":
                continue
            for membership in organization.memberships.values():
                if membership.status != "ACTIVE" or membership.email != normalized_email:
                    continue
                if subject is not None and membership.identity_subject != subject:
                    continue
                result.append(membership)
        return result

    def list_memberships_for_tenant(self, tenant_id: str) -> list[MembershipRecord]:
        organization = self._items.get(tenant_id)
        if organization is None:
            return []
        return list(organization.memberships.values())

    def get_membership(self, tenant_id: str, membership_id: str) -> MembershipRecord | None:
        organization = self._items.get(tenant_id)
        if organization is None:
            return None
        return organization.memberships.get(membership_id)

    def find_membership_by_email(
        self, tenant_id: str, email: str, *, include_inactive: bool = True
    ) -> MembershipRecord | None:
        organization = self._items.get(tenant_id)
        if organization is None:
            return None
        normalized = normalize_email(email)
        for membership in organization.memberships.values():
            if membership.email != normalized:
                continue
            if include_inactive or membership.status == "ACTIVE":
                return membership
        return None

    def get_business_unit(
        self, tenant_id: str, business_unit_id: str | None
    ) -> BusinessUnitRecord | None:
        if business_unit_id is None:
            return None
        organization = self._items.get(tenant_id)
        if organization is None:
            return None
        return organization.business_units.get(business_unit_id)

    def default_business_unit(self, tenant_id: str) -> BusinessUnitRecord | None:
        organization = self._items.get(tenant_id)
        if organization is None:
            return None
        for unit in organization.business_units.values():
            if unit.name == "Principal" and unit.status == "ACTIVE":
                return unit
        return next((u for u in organization.business_units.values() if u.status == "ACTIVE"), None)

    def active_membership_count(self, tenant_id: str) -> int:
        return sum(1 for m in self.list_memberships_for_tenant(tenant_id) if m.status == "ACTIVE")

    def pending_invitation_count(self, tenant_id: str, *, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        organization = self._items.get(tenant_id)
        if organization is None:
            return 0
        count = 0
        changed = False
        for invitation in organization.invitations.values():
            if invitation.status != "PENDING":
                continue
            if now >= invitation.expires_at:
                invitation.status = "EXPIRED"
                changed = True
                continue
            count += 1
        if changed:
            self._persist(organization)
        return count

    def create_invitation(
        self,
        tenant_id: str,
        *,
        email: str,
        roles: frozenset[Role],
        business_unit_id: str | None,
        created_by: str,
        now: datetime | None = None,
    ) -> tuple[InvitationRecord, str]:
        organization = self._items.get(tenant_id)
        if organization is None:
            raise KeyError("TENANT_NOT_FOUND")
        normalized_email = normalize_email(email)
        now = now or datetime.now(timezone.utc)

        for invitation in organization.invitations.values():
            if (
                invitation.email == normalized_email
                and invitation.status == "PENDING"
                and now < invitation.expires_at
            ):
                raise ValueError("INVITATION_ALREADY_PENDING")

        raw_token = secrets.token_urlsafe(32)
        invitation = InvitationRecord(
            invitation_id=new_id("invite"),
            tenant_id=tenant_id,
            email=normalized_email,
            roles=roles,
            business_unit_id=business_unit_id,
            token_digest=_invite_digest(raw_token),
            created_by=created_by,
            created_at=now,
            expires_at=now + INVITATION_TTL,
        )
        organization.invitations[invitation.invitation_id] = invitation
        self._persist(organization)
        return invitation, raw_token

    def list_invitations_for_tenant(self, tenant_id: str) -> list[InvitationRecord]:
        organization = self._items.get(tenant_id)
        if organization is None:
            return []
        return list(organization.invitations.values())

    def _find_invitation_by_token(
        self, raw_token: str
    ) -> tuple[TenantOrganization, InvitationRecord] | None:
        digest = _invite_digest(raw_token)
        for organization in self._items.values():
            for invitation in organization.invitations.values():
                if secrets.compare_digest(invitation.token_digest, digest):
                    return organization, invitation
        return None

    def accept_invitation(
        self,
        *,
        raw_token: str,
        identity_subject: str,
        email: str,
        now: datetime | None = None,
    ) -> MembershipRecord:
        found = self._find_invitation_by_token(raw_token)
        if found is None:
            raise ValueError("INVITATION_INVALID")
        organization, invitation = found
        now = now or datetime.now(timezone.utc)
        if invitation.status != "PENDING":
            raise ValueError("INVITATION_NOT_PENDING")
        if now >= invitation.expires_at:
            invitation.status = "EXPIRED"
            raise ValueError("INVITATION_EXPIRED")
        normalized_email = normalize_email(email)
        if invitation.email != normalized_email:
            raise ValueError("INVITATION_EMAIL_MISMATCH")
        if organization.tenant.status != "ACTIVE":
            raise ValueError("TENANT_INACTIVE")

        membership = self.find_membership_by_email(
            organization.tenant.tenant_id, normalized_email, include_inactive=True
        )
        if membership is None:
            membership = MembershipRecord(
                membership_id=new_id("member"),
                tenant_id=organization.tenant.tenant_id,
                identity_subject=identity_subject,
                email=normalized_email,
                roles=invitation.roles,
                business_unit_id=invitation.business_unit_id,
                created_at=now,
                updated_at=now,
            )
            organization.memberships[membership.membership_id] = membership
        else:
            membership.identity_subject = identity_subject
            membership.roles = invitation.roles
            membership.business_unit_id = invitation.business_unit_id
            membership.status = "ACTIVE"
            membership.updated_at = now
            membership.deactivated_at = None

        invitation.status = "ACCEPTED"
        invitation.accepted_by = membership.membership_id
        invitation.accepted_at = now
        self._persist(organization)
        return membership

    def deactivate_membership(
        self, tenant_id: str, membership_id: str, *, now: datetime | None = None
    ) -> MembershipRecord | None:
        membership = self.get_membership(tenant_id, membership_id)
        if membership is None:
            return None
        now = now or datetime.now(timezone.utc)
        membership.status = "INACTIVE"
        membership.updated_at = now
        membership.deactivated_at = now
        organization = self._items.get(tenant_id)
        if organization is not None:
            self._persist(organization)
        return membership

    def reactivate_membership(
        self, tenant_id: str, membership_id: str, *, now: datetime | None = None
    ) -> MembershipRecord | None:
        membership = self.get_membership(tenant_id, membership_id)
        if membership is None:
            return None
        now = now or datetime.now(timezone.utc)
        membership.status = "ACTIVE"
        membership.updated_at = now
        membership.deactivated_at = None
        organization = self._items.get(tenant_id)
        if organization is not None:
            self._persist(organization)
        return membership

    def active_owner_count(self, tenant_id: str) -> int:
        return sum(
            1
            for m in self.list_memberships_for_tenant(tenant_id)
            if m.status == "ACTIVE" and Role.OWNER in m.roles
        )


    def list_business_units_for_tenant(self, tenant_id: str) -> list[BusinessUnitRecord]:
        organization = self._items.get(tenant_id)
        if organization is None:
            return []
        return list(organization.business_units.values())

    def create_business_unit(
        self, tenant_id: str, *, name: str
    ) -> BusinessUnitRecord:
        organization = self._items.get(tenant_id)
        if organization is None:
            raise KeyError("TENANT_NOT_FOUND")
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("BUSINESS_UNIT_NAME_REQUIRED")
        if any(
            unit.name.casefold() == normalized_name.casefold()
            for unit in organization.business_units.values()
        ):
            raise ValueError("BUSINESS_UNIT_NAME_EXISTS")
        unit = BusinessUnitRecord(
            business_unit_id=new_id("bu"),
            tenant_id=tenant_id,
            name=normalized_name,
        )
        organization.business_units[unit.business_unit_id] = unit
        self._persist(organization)
        return unit

    def rename_business_unit(
        self, tenant_id: str, business_unit_id: str, *, name: str
    ) -> BusinessUnitRecord | None:
        organization = self._items.get(tenant_id)
        if organization is None:
            return None
        unit = organization.business_units.get(business_unit_id)
        if unit is None:
            return None
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("BUSINESS_UNIT_NAME_REQUIRED")
        if any(
            other.business_unit_id != business_unit_id
            and other.name.casefold() == normalized_name.casefold()
            for other in organization.business_units.values()
        ):
            raise ValueError("BUSINESS_UNIT_NAME_EXISTS")
        unit.name = normalized_name
        self._persist(organization)
        return unit

    def active_membership_count_for_unit(self, tenant_id: str, business_unit_id: str) -> int:
        return sum(
            1
            for membership in self.list_memberships_for_tenant(tenant_id)
            if membership.status == "ACTIVE"
            and membership.business_unit_id == business_unit_id
        )

    def set_business_unit_status(
        self, tenant_id: str, business_unit_id: str, *, status: str
    ) -> BusinessUnitRecord | None:
        organization = self._items.get(tenant_id)
        if organization is None:
            return None
        unit = organization.business_units.get(business_unit_id)
        if unit is None:
            return None
        if status not in {"ACTIVE", "INACTIVE"}:
            raise ValueError("BUSINESS_UNIT_STATUS_INVALID")
        if status == "INACTIVE":
            if self.active_membership_count_for_unit(tenant_id, business_unit_id) > 0:
                raise ValueError("BUSINESS_UNIT_HAS_ACTIVE_MEMBERS")
            active_units = sum(
                1
                for candidate in organization.business_units.values()
                if candidate.status == "ACTIVE"
                and candidate.business_unit_id != business_unit_id
            )
            if active_units < 1:
                raise ValueError("LAST_ACTIVE_BUSINESS_UNIT")
        unit.status = status
        self._persist(organization)
        return unit

    def update_membership_access(
        self,
        tenant_id: str,
        membership_id: str,
        *,
        roles: frozenset[Role],
        business_unit_id: str | None,
        now: datetime | None = None,
    ) -> MembershipRecord | None:
        organization = self._items.get(tenant_id)
        if organization is None:
            return None
        membership = organization.memberships.get(membership_id)
        if membership is None:
            return None
        now = now or datetime.now(timezone.utc)
        membership.roles = roles
        membership.business_unit_id = business_unit_id
        membership.updated_at = now
        self._persist(organization)
        return membership


__all__ = [
    "BusinessUnitRecord",
    "INVITATION_TTL",
    "InvitationRecord",
    "MembershipRecord",
    "OrganizationRepository",
    "TenantOrganization",
    "TenantRecord",
    "normalize_document",
    "normalize_email",
]
