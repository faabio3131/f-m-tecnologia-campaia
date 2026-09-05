"""In-memory repositories owned by the API layer.

None of these exist in campaia_core because none of them are tested domain logic --
they are plain tenant-scoped storage for things the BFF needs to hold state for:
brand profiles, connections, campaigns (wrapping campaia_core.states.Campaign plus
BFF-only metadata like plan/policy/budget engines), approval requests, and the audit log.

Every lookup method takes tenant_id and returns None (never another tenant's row) so
route handlers can turn "not found or wrong tenant" into a uniform 404 -- this mirrors
I-04 in the domain layer (tenant isolation responds NOT_FOUND, never PERMISSION_DENIED).
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from campaia_core.autonomy import AutonomySettings
from campaia_core.budget import BudgetEngine, BudgetLimits
from campaia_core.connectors import ConnectionMode
from campaia_core.policy import PolicyDecision
from campaia_core.states import Campaign

if TYPE_CHECKING:
    from .db import RecordTable

_id_counter = itertools.count(1)


def new_id(prefix: str) -> str:
    return f"{prefix}_{next(_id_counter):06d}_{uuid.uuid4().hex[:8]}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _attach_persistence(table: "RecordTable | None", id_: str, tenant_id: str, obj: Any) -> Any:
    """No-op in ephemeral mode (``table is None``): returns ``obj`` unchanged, so every
    pre-existing (persistence-unaware) test keeps operating on plain, unwrapped dataclass
    instances exactly as before this module gained persistence support.

    In persistent mode: wraps ``obj``'s mutable tree so any later in-place mutation (a
    route handler doing ``approval.status = "APPROVED"``, ``campaign.history.append(...)``,
    etc. with no explicit "save" call) re-persists the whole record immediately (see
    ``db.wrap_for_notify``), then writes the record's current state to `table` right away
    so a record is durable before its creating call even returns -- not just on its first
    future mutation.
    """
    if table is None:
        return obj
    from .db import wrap_for_notify

    wrapped = wrap_for_notify(obj, lambda: table.put(id_, tenant_id, wrapped))
    table.put(id_, tenant_id, wrapped)
    return wrapped


def _wrap_loaded(table: "RecordTable | None", id_: str, tenant_id: str, obj: Any) -> Any:
    """Like ``_attach_persistence`` but for a record just rehydrated from `table` at
    startup: wraps it for notify-on-mutation WITHOUT an immediate redundant re-write (its
    on-disk state is already exactly this state -- that is where it was just read from).
    """
    if table is None:
        return obj
    from .db import wrap_for_notify

    wrapped = wrap_for_notify(obj, lambda: table.put(id_, tenant_id, wrapped))
    return wrapped


# --------------------------------------------------------------------------- brand profiles


@dataclass
class BrandProfile:
    brand_profile_id: str
    tenant_id: str
    name: str
    tone: str
    colors: list[str]
    differentiators: list[str]
    restrictions: list[str]
    created_at: datetime = field(default_factory=now_utc)


class BrandProfileRepository:
    def __init__(self, table: "RecordTable | None" = None) -> None:
        self._table = table
        self._items: dict[str, BrandProfile] = {}
        if table is not None:
            for id_, tenant_id, obj in table.all_rows():
                self._items[id_] = _wrap_loaded(table, id_, tenant_id, obj)

    def list_for_tenant(self, tenant_id: str) -> list[BrandProfile]:
        return [p for p in self._items.values() if p.tenant_id == tenant_id]

    def create(self, tenant_id: str, **fields: Any) -> BrandProfile:
        profile = BrandProfile(
            brand_profile_id=new_id("bp"), tenant_id=tenant_id, **fields
        )
        profile = _attach_persistence(self._table, profile.brand_profile_id, tenant_id, profile)
        self._items[profile.brand_profile_id] = profile
        return profile

    def get(self, tenant_id: str, brand_profile_id: str) -> BrandProfile | None:
        item = self._items.get(brand_profile_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item


# --------------------------------------------------------------------------- connections


@dataclass
class Connection:
    connection_id: str
    tenant_id: str
    provider: str
    external_account_id: str
    display_name: str
    # Contract's Connection.status enum is [ACTIVE, EXPIRED, REVOKED, NEEDS_REAUTH] --
    # ACTIVE is the correct initial value (achado 6), not the non-conformant "CONNECTED".
    status: str = "ACTIVE"  # ACTIVE | EXPIRED | REVOKED | NEEDS_REAUTH
    api_version: str = "sim-1"
    last_synced_at: datetime = field(default_factory=now_utc)
    mode: ConnectionMode = ConnectionMode.SIMULATOR


class ConnectionRepository:
    def __init__(self, table: "RecordTable | None" = None) -> None:
        self._table = table
        self._items: dict[str, Connection] = {}
        if table is not None:
            for id_, tenant_id, obj in table.all_rows():
                self._items[id_] = _wrap_loaded(table, id_, tenant_id, obj)

    def list_for_tenant(self, tenant_id: str) -> list[Connection]:
        return [c for c in self._items.values() if c.tenant_id == tenant_id]

    def get(self, tenant_id: str, connection_id: str) -> Connection | None:
        item = self._items.get(connection_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    def create(self, tenant_id: str, **fields: Any) -> Connection:
        conn = Connection(connection_id=new_id("conn"), tenant_id=tenant_id, **fields)
        conn = _attach_persistence(self._table, conn.connection_id, tenant_id, conn)
        self._items[conn.connection_id] = conn
        return conn

    def revoke(self, tenant_id: str, connection_id: str) -> Connection | None:
        conn = self.get(tenant_id, connection_id)
        if conn is None:
            return None
        conn.status = "REVOKED"
        return conn


# --------------------------------------------------------------------------- campaigns


@dataclass
class ExternalResourceState:
    """One channel's reconciled external-resource state, per the contract's
    Campaign.external_resources[] item shape (achado 5)."""

    channel: str
    external_resource_id: str
    sync_status: str = "PENDING"  # PENDING | CONFIRMED | DIVERGENT
    last_synced_at: datetime | None = None


@dataclass
class CampaignRecord:
    """BFF-level wrapper around the real domain Campaign.

    Holds the domain state machine plus everything the BFF needs to orchestrate it:
    the per-campaign BudgetEngine (budget.py explicitly says "instance per campaign,
    never shared"), autonomy settings, plan version/content, last policy decision, and
    the connection used to publish.
    """

    campaign_id: str
    tenant_id: str
    business_unit_id: str | None
    brief: dict
    campaign: Campaign
    budget: BudgetEngine
    autonomy: AutonomySettings
    connection_id: str | None = None
    planned_channels: tuple[str, ...] = ()
    plan_version: int = 0
    plan: dict | None = None
    last_policy_decision: PolicyDecision | None = None
    approval_id: str | None = None
    created_by: str | None = None
    created_at: datetime = field(default_factory=now_utc)
    last_synced_at: datetime | None = None
    # Contract's Campaign.external_resources is an array of {channel, external_resource_id,
    # sync_status, last_synced_at} (achado 5), not a flat {channel: id} dict. Keyed here by
    # channel for easy per-channel updates from publish_campaign; helpers.serialize_campaign
    # turns this into the contract's array shape. There is no per-channel last_synced_at
    # tracked anywhere else in the domain layer, so we reuse the moment each channel's
    # resource id was recorded as that channel's own last_synced_at (a reasonable,
    # documented simplification -- see routes_campaigns.publish_campaign).
    external_resources: dict[str, "ExternalResourceState"] = field(default_factory=dict)


class CampaignRepository:
    def __init__(self, table: "RecordTable | None" = None) -> None:
        self._table = table
        self._items: dict[str, CampaignRecord] = {}
        if table is not None:
            for id_, tenant_id, obj in table.all_rows():
                self._items[id_] = _wrap_loaded(table, id_, tenant_id, obj)

    def list_for_tenant(self, tenant_id: str) -> list[CampaignRecord]:
        return [c for c in self._items.values() if c.tenant_id == tenant_id]

    def get(self, tenant_id: str, campaign_id: str) -> CampaignRecord | None:
        item = self._items.get(campaign_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    def create(self, tenant_id: str, *, brief: dict, business_unit_id: str | None,
                created_by: str | None) -> CampaignRecord:
        campaign_id = new_id("camp")
        limits = BudgetLimits(
            currency=brief.get("currency", "BRL"),
            daily_cap=Decimal(str(brief.get("daily_cap", "1000"))),
            total_amount=Decimal(str(brief.get("total_budget", "10000"))),
        )
        record = CampaignRecord(
            campaign_id=campaign_id,
            tenant_id=tenant_id,
            business_unit_id=business_unit_id,
            brief=brief,
            campaign=Campaign(campaign_id=campaign_id, tenant_id=tenant_id),
            budget=BudgetEngine(tenant_id=tenant_id, campaign_id=campaign_id, limits=limits),
            autonomy=AutonomySettings(),
            created_by=created_by,
        )
        record = _attach_persistence(self._table, campaign_id, tenant_id, record)
        self._items[campaign_id] = record
        return record


# --------------------------------------------------------------------------- approvals


# Contract requires ApprovalRequest.expires_at. There is no expiry policy defined
# elsewhere in campaia_core for approvals, so we pick a fixed, documented window (achado 9):
# an approval is valid for 24h after creation. This is a deliberate, simple default, not a
# discovered domain rule -- revisit if/when a real policy for approval expiry exists.
APPROVAL_EXPIRY = timedelta(hours=24)


@dataclass
class ApprovalRequest:
    approval_id: str
    tenant_id: str
    campaign_id: str
    kind: str  # PUBLISH | BUDGET_CHANGE | AUTONOMY_CHANGE
    requested_by: str
    amount: Decimal | None
    # plan_version of the campaign at the time the approval was requested (contract
    # requires ApprovalRequest.plan_version) -- captured at creation time so it reflects
    # "the plan version this approval was actually about", not a live lookup that could
    # drift if the plan is regenerated after the approval is created.
    plan_version: int = 0
    # Contract enum: PENDING | APPROVED | REJECTED | CHANGES_REQUESTED | EXPIRED (achado 9/10).
    status: str = "PENDING"
    decided_by: set[str] = field(default_factory=set)
    requires_dual_approval: bool = False
    created_at: datetime = field(default_factory=now_utc)
    expires_at: datetime | None = field(default=None)  # set in __post_init__
    context: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.expires_at is None:
            self.expires_at = self.created_at + APPROVAL_EXPIRY


class ApprovalRepository:
    def __init__(self, table: "RecordTable | None" = None) -> None:
        self._table = table
        self._items: dict[str, ApprovalRequest] = {}
        if table is not None:
            for id_, tenant_id, obj in table.all_rows():
                self._items[id_] = _wrap_loaded(table, id_, tenant_id, obj)

    def list_for_tenant(self, tenant_id: str) -> list[ApprovalRequest]:
        return [a for a in self._items.values() if a.tenant_id == tenant_id]

    def get(self, tenant_id: str, approval_id: str) -> ApprovalRequest | None:
        item = self._items.get(approval_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    def create(self, tenant_id: str, **fields: Any) -> ApprovalRequest:
        approval = ApprovalRequest(approval_id=new_id("appr"), tenant_id=tenant_id, **fields)
        approval = _attach_persistence(self._table, approval.approval_id, tenant_id, approval)
        self._items[approval.approval_id] = approval
        return approval


# --------------------------------------------------------------------------- audit log


@dataclass
class AuditEvent:
    audit_event_id: str
    tenant_id: str
    actor: str
    # Contract's AuditEvent splits the actor into actor_kind (enum) + actor_id (nullable)
    # (achado 15). Every audit event recorded by this BFF today originates from an
    # authenticated HTTP request made by a human user, so actor_kind is always "USER" for
    # now -- there is no SYSTEM/AI/EXTERNAL_PROVIDER-originated audit event yet. Documented
    # simplification, not a discovered domain rule.
    actor_kind: str
    action: str
    target: str
    policy_decision_id: str | None
    timestamp: datetime = field(default_factory=now_utc)
    details: dict = field(default_factory=dict)


class AuditLog:
    def __init__(self, table: "RecordTable | None" = None) -> None:
        self._table = table
        # Audit events are append-only -- never mutated in place after creation by any
        # route handler -- so loaded rows are used exactly as decoded, with no
        # notify-wrapping needed (there is nothing for a wrapper to ever notice change).
        self._items: list[AuditEvent] = [obj for _id, _tenant_id, obj in table.all_rows()] if table is not None else []

    def append(
        self,
        *,
        tenant_id: str,
        actor: str,
        action: str,
        target: str,
        policy_decision_id: str | None = None,
        details: dict | None = None,
        actor_kind: str = "USER",
    ) -> AuditEvent:
        event = AuditEvent(
            audit_event_id=new_id("audit"),
            tenant_id=tenant_id,
            actor=actor,
            actor_kind=actor_kind,
            action=action,
            target=target,
            policy_decision_id=policy_decision_id,
            details=details or {},
        )
        if self._table is not None:
            self._table.put(event.audit_event_id, tenant_id, event)
        self._items.append(event)
        return event

    def list_for_tenant(self, tenant_id: str) -> list[AuditEvent]:
        return [e for e in self._items if e.tenant_id == tenant_id]
