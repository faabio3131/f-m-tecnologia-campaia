"""Process-wide application state: fixture principals, repositories, and shared engines.

Everything here is in-memory, matching the domain test suite's own style (IdempotencyStore,
CapabilityRegistry etc. are all in-memory by design -- see infra.py docstring). Nothing here
is persisted across process restarts, and nothing here is a real credential.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from campaia_core.agents import AgentRunner
from campaia_core.ai_gateway import AIGateway
from campaia_core.ai_simulator import SimulatedAIProvider
from campaia_core.autonomy import AutonomySettings
from campaia_core.infra import Capability, CapabilityRegistry, IdempotencyStore
from campaia_core.permissions import Principal, Role

from .repositories import (
    ApprovalRepository,
    AuditLog,
    BrandProfileRepository,
    CampaignRepository,
    ConnectionRepository,
)


@dataclass(frozen=True)
class TokenPrincipal:
    """Fixture principal bound to a fake bearer token.

    NOT a real credential: `token` is just a dictionary key seeded at startup, never
    persisted, never in a real token format (JWT, opaque OAuth token, etc).
    """

    user_id: str
    tenant_id: str
    roles: frozenset[Role]
    business_unit_id: str | None = None
    mfa_enabled: bool = True

    def to_domain_principal(self, *, step_up_at: datetime | None) -> Principal:
        return Principal(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            roles=self.roles,
            business_unit_ids=(
                None if self.business_unit_id is None else frozenset({self.business_unit_id})
            ),
            mfa_enabled=self.mfa_enabled,
            step_up_at=step_up_at,
        )


def _seed_tokens() -> dict[str, TokenPrincipal]:
    """Local dev fixtures only. Never anything resembling a real token format."""
    return {
        "demo-owner-token": TokenPrincipal(
            user_id="user-owner-1",
            tenant_id="demo-tenant",
            roles=frozenset({Role.OWNER}),
            business_unit_id="bu-1",
        ),
        "demo-marketer-token": TokenPrincipal(
            user_id="user-marketer-1",
            tenant_id="demo-tenant",
            roles=frozenset({Role.MARKETER}),
            business_unit_id="bu-1",
        ),
        "demo-approver-token": TokenPrincipal(
            user_id="user-approver-1",
            tenant_id="demo-tenant",
            roles=frozenset({Role.APPROVER}),
            business_unit_id="bu-1",
        ),
        "demo-finance-token": TokenPrincipal(
            user_id="user-finance-1",
            tenant_id="demo-tenant",
            roles=frozenset({Role.FINANCE}),
            business_unit_id="bu-1",
        ),
        "demo-viewer-token": TokenPrincipal(
            user_id="user-viewer-1",
            tenant_id="demo-tenant",
            roles=frozenset({Role.VIEWER}),
            business_unit_id="bu-1",
        ),
        # A second tenant, to exercise cross-tenant isolation in tests.
        "other-owner-token": TokenPrincipal(
            user_id="user-owner-2",
            tenant_id="other-tenant",
            roles=frozenset({Role.OWNER}),
            business_unit_id="bu-2",
        ),
    }


def _seed_capabilities() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    now = datetime.now(timezone.utc)
    for provider, account_suffix in (("SIMULATOR", "demo-tenant"), ("SIMULATOR", "other-tenant")):
        for channel in ("GOOGLE_ADS", "META_ADS"):
            registry.register(
                Capability(
                    provider=provider,
                    capability_key=f"PUBLISH:{channel}",
                    country="BR",
                    api_version="sim-1",
                    supported=True,
                    verified_at=now,
                    notes="Simulated capability, verified in-process at startup.",
                )
            )
    return registry


@dataclass
class AppState:
    #: None (the default) means today's pure in-memory behaviour: every field below keeps
    #: its plain-Python default_factory value, byte-for-byte identical to this class before
    #: persistence existed. A real path switches every persisted field (repositories,
    #: idempotency store, tenant autonomy maps) over to a SQLite-backed counterpart in
    #: __post_init__ -- see api/db.py for the storage/serialization design. Deliberately
    #: NOT threaded through the dataclass-generated default_factory calls above/below
    #: (those run before __post_init__ and take no arguments) -- __post_init__ replaces
    #: the ephemeral defaults wholesale instead, which is also what keeps this field's
    #: presence a no-op for every pre-existing (persistence-unaware) caller of AppState().
    db_path: str | None = None

    tokens: dict[str, TokenPrincipal] = field(default_factory=_seed_tokens)
    # Step-up tokens are accepted at face value in this sandbox (no real re-auth flow) --
    # we still track a per-(tenant,user) "recent step-up" timestamp so that
    # campaia_core.permissions.authorize's STEP_UP_MAX_AGE window is honoured for real
    # rather than just checking header presence and ignoring the domain's own guard.
    step_up_at: dict[tuple[str, str], datetime] = field(default_factory=dict)

    idempotency: IdempotencyStore = field(default_factory=IdempotencyStore)
    capabilities: CapabilityRegistry = field(default_factory=_seed_capabilities)

    brand_profiles: BrandProfileRepository = field(default_factory=BrandProfileRepository)
    connections: ConnectionRepository = field(default_factory=ConnectionRepository)
    campaigns: CampaignRepository = field(default_factory=CampaignRepository)
    approvals: ApprovalRepository = field(default_factory=ApprovalRepository)
    audit: AuditLog = field(default_factory=AuditLog)

    #: Tenant-level autonomy settings (GET/PUT /autonomy). Per-campaign AutonomySettings
    #: also exists on CampaignRecord for policy evaluation; this is the tenant default.
    tenant_autonomy: dict[str, AutonomySettings] = field(default_factory=dict)
    #: Contract requires AutonomySettings.updated_at (achado 11) -- tracked alongside
    #: tenant_autonomy since AutonomySettings itself (campaia_core.autonomy) is a frozen
    #: domain dataclass with no timestamp field of its own.
    tenant_autonomy_updated_at: dict[str, datetime] = field(default_factory=dict)

    ai_gateway: AIGateway = field(default_factory=AIGateway)
    #: Default output matches the "strategist" agent's OutputSchema (campaia_core/agents.py
    #: AGENTS["strategist"]: requires objetivo/funil/canais/justificativa) so /plan/regenerate
    #: works out of the box against the SimulatedAIProvider -- never a real AI provider.
    ai_provider: SimulatedAIProvider = field(
        default_factory=lambda: SimulatedAIProvider(
            output={
                "objetivo": "Gerar demanda qualificada dentro do orcamento aprovado.",
                "funil": "TOPO_MEIO",
                "canais": ["GOOGLE_ADS", "META_ADS"],
                "justificativa": "Saida simulada do SimulatedAIProvider (nunca um provedor real).",
            }
        )
    )
    agent_runner: AgentRunner = field(init=False)

    def __post_init__(self) -> None:
        #: Handle to the open SQLite connection when db_path is set, else None. Not a
        #: dataclass field (nothing outside this method needs to construct one) -- kept
        #: only so callers that DO want to close it explicitly (see tests_api's
        #: teardown_client, and the reference persistence tests) have somewhere to reach
        #: it via app.state.campaia.db, and so __del__ on the Database can run its
        #: best-effort close when this AppState (and everything holding its repositories)
        #: is garbage collected.
        self.db = None
        if self.db_path is not None:
            from .db import Database, PersistentIdempotencyStore, PersistentTenantAutonomy

            self.db = Database(self.db_path)
            # Every field replaced below is a plain in-memory default_factory value at
            # this point (dataclass field defaults always run before __post_init__ and
            # can't see db_path) -- swapping them out here, before anything has read or
            # written through them, is what makes db_path=None (the default) leave this
            # method a no-op past this point and every existing caller of AppState()
            # completely unaffected.
            self.brand_profiles = BrandProfileRepository(self.db.table("brand_profiles"))
            self.connections = ConnectionRepository(self.db.table("connections"))
            self.campaigns = CampaignRepository(self.db.table("campaigns"))
            self.approvals = ApprovalRepository(self.db.table("approvals"))
            self.audit = AuditLog(self.db.table("audit_events"))
            self.idempotency = PersistentIdempotencyStore(self.db.table("idempotency"))
            self.tenant_autonomy = PersistentTenantAutonomy(self.db.table("tenant_autonomy"))
            self.tenant_autonomy_updated_at = PersistentTenantAutonomy(
                self.db.table("tenant_autonomy_updated_at")
            )
            # capabilities and tokens are deliberately NOT persisted: both are
            # process-startup fixture/seed data (a hardcoded Capability Matrix and a
            # hardcoded dev bearer-token map), never mutated by any route handler, so
            # there is nothing about them a restart could lose.

        self.ai_gateway.providers.append(self.ai_provider)
        self.agent_runner = AgentRunner(gateway=self.ai_gateway)
        self.agent_runner.register_schemas()

    def record_step_up(self, tenant_id: str, user_id: str, *, at: datetime) -> None:
        self.step_up_at[(tenant_id, user_id)] = at

    def last_step_up(self, tenant_id: str, user_id: str) -> datetime | None:
        return self.step_up_at.get((tenant_id, user_id))
