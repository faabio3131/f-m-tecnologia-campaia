"""Process-wide application state: fixture principals, repositories, and shared engines.

Everything here is in-memory, matching the domain test suite's own style (IdempotencyStore,
CapabilityRegistry etc. are all in-memory by design -- see infra.py docstring). Nothing here
is persisted across process restarts, and nothing here is a real credential.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from campaia_core.agents import AgentRunner
from campaia_core.ai_gateway import AIGateway
from campaia_core.ai_simulator import SimulatedAIProvider
from campaia_core.autonomy import AutonomySettings
from campaia_core.infra import Capability, CapabilityRegistry, IdempotencyStore
from campaia_core.permissions import Principal, Role

from .oidc import (
    PENDING_LOGIN_TTL_SECONDS,
    SESSION_TTL_SECONDS,
    Membership,
    OidcIssuerConfig,
    PendingLogin,
    SessionRecord,
    VerifiedIdToken,
    generate_csrf_token,
    generate_session_id,
)
from .repositories import (
    ApprovalRepository,
    AuditLog,
    BrandProfileRepository,
    CampaignRepository,
    ConnectionRepository,
)
from .test_idp import TestIdentityProvider


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

    @staticmethod
    def from_verified_id_token(verified: VerifiedIdToken) -> "TokenPrincipal":
        """Maps a real, signature-verified ID token's claims to the same TokenPrincipal
        shape the pre-WP-02 fixture tokens produced -- so require_auth, permissions.py, and
        every route handler downstream of it are unaware of which mechanism authenticated
        the request. Unknown role strings are dropped (never silently granted as a
        catch-all), so a provider claiming a role campaia_core.permissions.Role doesn't
        recognize simply grants nothing for that string, rather than failing the whole
        request or being coerced into an unintended role.
        """
        return TokenPrincipal(
            user_id=verified.subject,
            tenant_id=verified.tenant_id,
            roles=_parse_roles(verified.roles),
            business_unit_id=verified.business_unit_id,
            mfa_enabled=verified.mfa_enabled,
        )

    def with_membership(self, membership: "Membership") -> "TokenPrincipal":
        """WP-03: same user, different active tenant -- returned by a successful
        POST /session/switch-tenant. `user_id` and `mfa_enabled` are the user's own and
        never change across tenants; `tenant_id`/`business_unit_id`/`roles` become whatever
        the target membership grants (never the roles of the tenant being left).
        """
        return TokenPrincipal(
            user_id=self.user_id,
            tenant_id=membership.tenant_id,
            roles=_parse_roles(membership.roles),
            business_unit_id=membership.business_unit_id,
            mfa_enabled=self.mfa_enabled,
        )


def _parse_roles(raw_roles: tuple[str, ...] | list[str]) -> frozenset[Role]:
    """Shared by from_verified_id_token and with_membership: unknown role strings are
    dropped, never silently granted as a catch-all."""
    roles: set[Role] = set()
    for raw_role in raw_roles:
        try:
            roles.add(Role(raw_role))
        except ValueError:
            continue
    return frozenset(roles)


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


#: Internal-only: the test identity provider and its "client" (this same backend's
#: /auth/login and /auth/callback) trust each other by process identity, not by a shared
#: secret that crosses any real trust boundary -- so this constant is not a credential.
TEST_IDP_CLIENT_ID = "campaia-web-test"
TEST_IDP_CLIENT_SECRET = "test-idp-internal-secret-not-a-real-credential"  # noqa: S105


def _resolve_real_oidc_config() -> OidcIssuerConfig | None:
    """A real, commercial OIDC provider is configured purely via environment variables --
    none of api/oidc.py, api/routes_auth.py, or api/test_idp.py change when one is chosen
    (ADR-0018: "a escolha do provedor especifico fica para o Work Package de
    implementacao"). Returns None unless every required variable is present -- a partially
    configured real provider must not silently fall back to the test IdP.
    """
    required = {
        "issuer": os.environ.get("CAMPAIA_OIDC_ISSUER"),
        "authorization_endpoint": os.environ.get("CAMPAIA_OIDC_AUTHORIZATION_ENDPOINT"),
        "token_endpoint": os.environ.get("CAMPAIA_OIDC_TOKEN_ENDPOINT"),
        "jwks_uri": os.environ.get("CAMPAIA_OIDC_JWKS_URI"),
        "client_id": os.environ.get("CAMPAIA_OIDC_CLIENT_ID"),
        "client_secret": os.environ.get("CAMPAIA_OIDC_CLIENT_SECRET"),
        "redirect_uri": os.environ.get("CAMPAIA_OIDC_REDIRECT_URI"),
    }
    if any(value is None for value in required.values()):
        return None
    return OidcIssuerConfig(**required)  # type: ignore[arg-type]


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

    #: Fail-closed by construction (WP-02 / ADR-0018 rollback clause): the fixture bearer
    #: tokens below must never be reachable outside test/local-dev, even by misconfiguration.
    #: Two independent signals must agree before they are seeded -- this flag AND the
    #: process environment declaring itself test/local-dev (CAMPAIA_ENV). Neither alone is
    #: enough: a stray env var in a shared environment can't turn this on by itself, and a
    #: copy-pasted True in application wiring can't either. See __post_init__.
    enable_test_auth_fixtures: bool = False

    #: Empty by default -- only ever populated by __post_init__, and only after the
    #: fail-closed check above passes. Never seeded via field(default_factory=...) here,
    #: since dataclass field defaults run before enable_test_auth_fixtures is known.
    tokens: dict[str, TokenPrincipal] = field(default_factory=dict)

    #: Real Web sessions (WP-02). Keyed by opaque session id (the cookie value) -- never a
    #: JWT or any format that itself carries claims, so a session can be revoked server-side
    #: by simple dict deletion (logout, expiry sweep) with no token-blacklist needed.
    sessions: dict[str, SessionRecord] = field(default_factory=dict)
    #: In-flight /auth/login attempts, keyed by the `state` value handed to the issuer.
    #: Consumed exactly once by /auth/callback (see pop_pending_login).
    pending_logins: dict[str, PendingLogin] = field(default_factory=dict)
    #: None unless a real OIDC issuer is configured via CAMPAIA_OIDC_* env vars, or the
    #: fail-closed test-identity-provider gate below is enabled. /auth/login returns a
    #: clear "not configured" error rather than silently succeeding when this is None.
    oidc_config: OidcIssuerConfig | None = field(default=None, init=False)
    #: Only constructed when enable_test_auth_fixtures's fail-closed check passed -- see
    #: __post_init__. There is deliberately only one fail-closed switch (that check) for
    #: both the legacy fixture tokens and this test identity provider.
    test_idp: TestIdentityProvider | None = field(default=None, init=False)
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
        if self.enable_test_auth_fixtures:
            env = os.environ.get("CAMPAIA_ENV", "").strip().lower()
            if env not in {"test", "local_dev"}:
                raise RuntimeError(
                    "enable_test_auth_fixtures=True requires CAMPAIA_ENV to be 'test' or "
                    f"'local_dev' (got {env!r}). Refusing to seed fixture auth tokens "
                    "outside test/local-dev -- this is a fail-closed safety check, not a "
                    "bug. Never set CAMPAIA_ENV=test/local_dev in preview, staging or "
                    "production."
                )
            self.tokens = _seed_tokens()
            self.test_idp = TestIdentityProvider(
                client_id=TEST_IDP_CLIENT_ID, client_secret=TEST_IDP_CLIENT_SECRET
            )

        # Independent of the fail-closed test-fixture gate above: a real provider may be
        # configured (or not) in any environment, including production.
        self.oidc_config = _resolve_real_oidc_config()

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

    # -- WP-02: pending /auth/login attempts ---------------------------------------

    def create_pending_login(
        self, *, nonce: str, code_verifier: str, redirect_after_login: str
    ) -> str:
        state_value = generate_session_id()  # same shape requirements as a session id
        self.pending_logins[state_value] = PendingLogin(
            nonce=nonce,
            code_verifier=code_verifier,
            redirect_after_login=redirect_after_login,
            created_at=time.time(),
        )
        return state_value

    def pop_pending_login(self, state_value: str) -> PendingLogin | None:
        """Consumes (removes) a pending login by its state value -- single-use, so a
        replayed /auth/callback request with the same state always fails the second time.
        Returns None for an unknown OR expired attempt; callers must treat both identically.
        """
        pending = self.pending_logins.pop(state_value, None)
        if pending is None:
            return None
        if time.time() - pending.created_at > PENDING_LOGIN_TTL_SECONDS:
            return None
        return pending

    # -- WP-02: real Web sessions ---------------------------------------------------

    def create_session(
        self, principal: TokenPrincipal, *, memberships: tuple[Membership, ...] = ()
    ) -> tuple[str, str]:
        """Returns (session_id, csrf_token). Always a fresh id and a fresh expiry --
        WP-02's "rotacao de sessao" happens at login, not via silent per-request extension
        of an existing session. `memberships` defaults to empty for callers that predate
        WP-03 (fixture-token paths); real logins (api/routes_auth.py) always pass the
        verified ID token's own memberships.
        """
        session_id = generate_session_id()
        csrf_token = generate_csrf_token()
        self.sessions[session_id] = SessionRecord(
            principal=principal,
            csrf_token=csrf_token,
            expires_at=time.time() + SESSION_TTL_SECONDS,
            memberships=memberships,
        )
        return session_id, csrf_token

    def get_session(self, session_id: str) -> SessionRecord | None:
        """Returns None for an unknown, expired, OR revoked (logged-out) session --
        callers must treat all three identically (WP-02 negative-session tests)."""
        record = self.sessions.get(session_id)
        if record is None:
            return None
        if record.expires_at <= time.time():
            del self.sessions[session_id]
            return None
        return record

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    # -- WP-03: tenant switching -----------------------------------------------------

    def switch_tenant(self, session_id: str, target_tenant_id: str) -> tuple[str, str] | None:
        """Re-issues the session (new id, new CSRF token, new expiry -- same rotation
        discipline as login) with its active principal switched to `target_tenant_id`.
        Returns the new (session_id, csrf_token), or None if the current session is
        unknown/expired OR `target_tenant_id` is not one of its real memberships -- the
        server is the only source of truth for which tenants a user may switch into, never
        client-supplied roles.

        Any step-up (recent re-auth for sensitive actions, campaia_core.permissions
        STEP_UP_MAX_AGE) the user held is invalidated across ALL tenants on switch, not
        just the one being left -- switching tenant is itself a sensitive change of
        authority, so the user must re-verify step-up freshly in whichever tenant they act
        in next, even if that happens to be the tenant they just left.
        """
        record = self.get_session(session_id)
        if record is None:
            return None
        target = next((m for m in record.memberships if m.tenant_id == target_tenant_id), None)
        if target is None:
            return None

        new_principal = record.principal.with_membership(target)
        self.delete_session(session_id)
        for key in [k for k in self.step_up_at if k[1] == new_principal.user_id]:
            del self.step_up_at[key]
        return self.create_session(new_principal, memberships=record.memberships)
