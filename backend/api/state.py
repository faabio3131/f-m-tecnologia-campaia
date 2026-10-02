"""Process-wide application state: fixture principals, repositories, and shared engines.

Everything here is in-memory, matching the domain test suite's own style (IdempotencyStore,
CapabilityRegistry etc. are all in-memory by design -- see infra.py docstring). Nothing here
is persisted across process restarts, and nothing here is a real credential.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Import tardio evitado em runtime (identity_directory.py/session.py importam
    # TokenPrincipal deste modulo -- import no topo criaria ciclo); seguro aqui porque
    # `from __future__ import annotations` faz toda anotacao de tipo ser string.
    from .identity_directory import IdentityDirectory
    from .session import SessionStore
    from campaia_core.credential_vault import CredentialCipher

from campaia_core.agents import AGENTS, AgentRunner
from campaia_core.ai_gateway import AIGateway, AIProvider
from campaia_core.ai_simulator import SimulatedAIProvider
from campaia_core.asaas_gateway import AsaasConfig, AsaasGateway
from campaia_core.asaas_webhook import AsaasWebhookReceiver
from campaia_core.autonomy import AutonomySettings
from campaia_core.identity_provider import (
    AlwaysRejectIdTokenVerifier,
    FirebaseIdentityConfig,
    FirebaseIdTokenVerifier,
    IdTokenVerifier,
)
from campaia_core.infra import Capability, CapabilityRegistry, IdempotencyStore
from campaia_core.payment_gateway import PaymentGatewayConnector
from campaia_core.payment_simulator import PaymentGatewaySimulator
from campaia_core.permissions import Principal, Role
from campaia_core.rate_limit import FixedWindowRateLimiter
from campaia_core.subscription import Subscription, SubscriptionCharge

from .organization import OrganizationRepository
from .repositories import (
    ApprovalRepository,
    AuditLog,
    BrandProfileRepository,
    CampaignRepository,
    ConnectionRepository,
    VaultRepository,
)


@dataclass(frozen=True)
class TokenPrincipal:
    """Fixture principal bound to a fake bearer token.

    NOT a real credential: `token` is just a dictionary key seeded at startup, never
    persisted, never in a real token format (JWT, opaque OAuth token, etc).
    """

    user_id: str
    tenant_id: str
    #: SECURITY FIX (Fase 3, achado 1, 27/09/2026 -- auditoria independente): e-mail
    #: verificado desta identidade (o mesmo usado por `state.identity_directory` para
    #: resolver este vinculo -- ver identity_directory.py). Campo obrigatorio (sem
    #: default) de proposito: e' contra ELE que `api/deps.py::_is_genuine_step_up`
    #: correlaciona o ID token real apresentado no header `X-Step-Up-Token`, para provar
    #: que quem esta' se reautenticando e' de fato o dono desta sessao/vinculo -- nao so
    #: um token real de QUALQUER usuario. Sem este campo, essa correlacao nao existia
    #: (achado real: um token valido de outro usuario elevava a sessao de qualquer um).
    email: str
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


@dataclass(frozen=True)
class PendingOAuthState:
    """WP-04 (26/09/2026): registro em memoria do `state` devolvido por
    POST /connections/oauth/start, ate' ser resgatado pelo callback simulado. Nunca uma
    credencial real -- so o suficiente para amarrar o resgate ao mesmo tenant que
    iniciou o fluxo e ao provider escolhido, com expiracao curta (uso pontual, nao uma
    sessao).

    PREPARACAO para OAuth real (27/09/2026 -- correcao final pre-Google-Ads, NAO
    implementada nesta tarefa): um provider real (Google/Meta) redireciona o navegador
    de volta para `redirect_uri?code=...&state=...` -- NUNCA reenvia `X-Step-Up-Token`
    nem qualquer outro header que este backend tenha mandado no Start (o navegador do
    usuario e' quem faz essa requisicao de callback, nao este backend, e o provider nao
    conhece nem devolve headers arbitrarios do Start). Por isso um OAuth callback real
    JAMAIS podera' exigir `X-Step-Up-Token` (rota `require_step_up`) -- a prova de que o
    fluxo comecou sob step-up valido, e de que quem esta' voltando e' a MESMA
    identidade/sessao que iniciou, precisa estar amarrada a este `state` desde o Start,
    nao a um header que o provider nunca envia. Os tres campos abaixo (`user_id`,
    `session_key`, `step_up_verified_at`) existem para isso -- capturados no Start,
    nunca reconstruidos ou confiados no Callback. O callback futuro devera' validar
    `state` + esse binding de sessao/identidade (nunca um header do provider); NENHUMA
    logica de validacao nova foi adicionada ao callback simulado atual por esta
    preparacao -- so' o registro dos dados que essa validacao futura vai precisar.
    """

    tenant_id: str
    provider: str
    created_at: datetime
    #: Identidade (achado 1, mesma disciplina de `TokenPrincipal.email`/step-up) que
    #: iniciou o fluxo -- o callback futuro so' podera' resgatar este `state` para a
    #: MESMA identidade, nunca para outro usuario que descubra/adivinhe o valor do
    #: `state` (que ja e' de uso unico e curto TTL, mas isolamento por identidade e'
    #: defesa adicional, mesmo racional do achado 1 do step-up).
    user_id: str
    #: Mesma nocao de `api/deps.py::session_key_for` -- amarra o resgate a MESMA
    #: sessao/credencial que iniciou o fluxo (nunca sobrevive a logout->login ou troca
    #: de vinculo, mesma disciplina do step-up -- achados C3/3).
    session_key: str
    #: Instante do step-up persistido (`AppState.step_up_at`) que estava valido NO
    #: MOMENTO do Start -- a prova de step-up que um callback real tera' que checar,
    #: em vez de um `X-Step-Up-Token` que o provider nunca reenvia. `None` significaria
    #: que o Start ocorreu sem step-up valido (hoje isso e' impossivel: `oauth_start`
    #: exige `Permission.CONNECTION_MANAGE`, que ja esta' em `REQUIRES_STEP_UP` -- este
    #: campo so' documenta explicitamente essa prova para o callback futuro, nunca a
    #: cria).
    step_up_verified_at: datetime | None


#: Quanto tempo um `state` de OAuth pendente fica valido para resgate -- generoso o
#: bastante para o usuario escolher a conta no provedor (real ou simulado), curto o
#: bastante para nao acumular estado indefinidamente nem virar uma janela de replay
#: longa.
OAUTH_PENDING_STATE_TTL = timedelta(minutes=10)


#: Item 1.3/WP-02 (24/09/2026): ambientes onde o fixture de bearer token de dev pode
#: existir. Fora destes, `AppState.__post_init__` recusa a inicializacao -- nunca so
#: "esconde a opcao" (exigencia literal do WP-02, docs/web/06_ROADMAP_WORK_PACKAGES.md).
DEV_AUTH_FIXTURE_ALLOWED_ENVS = frozenset({"test", "dev-local"})


def _default_env() -> str:
    return os.environ.get("CAMPAIA_ENV", "production")


def _seed_tokens() -> dict[str, TokenPrincipal]:
    """Local dev fixtures only. Never anything resembling a real token format."""
    return {
        "demo-owner-token": TokenPrincipal(
            user_id="user-owner-1",
            tenant_id="demo-tenant",
            email="owner@demo-tenant.campaia.test",
            roles=frozenset({Role.OWNER}),
            business_unit_id="bu-1",
        ),
        "demo-marketer-token": TokenPrincipal(
            user_id="user-marketer-1",
            tenant_id="demo-tenant",
            email="marketer@demo-tenant.campaia.test",
            roles=frozenset({Role.MARKETER}),
            business_unit_id="bu-1",
        ),
        "demo-approver-token": TokenPrincipal(
            user_id="user-approver-1",
            tenant_id="demo-tenant",
            email="approver@demo-tenant.campaia.test",
            roles=frozenset({Role.APPROVER}),
            business_unit_id="bu-1",
        ),
        "demo-finance-token": TokenPrincipal(
            user_id="user-finance-1",
            tenant_id="demo-tenant",
            email="finance@demo-tenant.campaia.test",
            roles=frozenset({Role.FINANCE}),
            business_unit_id="bu-1",
        ),
        "demo-viewer-token": TokenPrincipal(
            user_id="user-viewer-1",
            tenant_id="demo-tenant",
            email="viewer@demo-tenant.campaia.test",
            roles=frozenset({Role.VIEWER}),
            business_unit_id="bu-1",
        ),
        # A second tenant, to exercise cross-tenant isolation in tests.
        "other-owner-token": TokenPrincipal(
            user_id="user-owner-2",
            tenant_id="other-tenant",
            email="owner@other-tenant.campaia.test",
            roles=frozenset({Role.OWNER}),
            business_unit_id="bu-2",
        ),
    }


def _default_id_token_verifier() -> IdTokenVerifier:
    """Nunca um verificador permissivo por padrao (diferente do simulador de IA/pagamento
    abaixo) -- aceitar qualquer id_token como valido seria um buraco de autenticacao, nao
    um estagiario harmless. Real so quando FIREBASE_PROJECT_ID estiver configurado (item
    1.6 provisionado); ate la, `AlwaysRejectIdTokenVerifier` (nunca autentica ninguem)."""
    config = FirebaseIdentityConfig.from_env()
    if config is not None:
        return FirebaseIdTokenVerifier(config)
    return AlwaysRejectIdTokenVerifier()


def _default_identity_directory(env: str, organizations: OrganizationRepository):
    # Import tardio: identity_directory.py importa TokenPrincipal deste modulo -- import
    # no topo do arquivo criaria ciclo (mesmo padrao ja usado para gemini_provider abaixo).
    from .identity_directory import (
        CompositeIdentityDirectory,
        OrganizationIdentityDirectory,
        seed_dev_identity_directory,
    )

    commercial = OrganizationIdentityDirectory(organizations)
    if env in DEV_AUTH_FIXTURE_ALLOWED_ENVS:
        return CompositeIdentityDirectory(seed_dev_identity_directory(), commercial)
    return commercial


def _default_plan_user_limits() -> dict[str, int]:
    """Load max_users from the SAME external plan catalog used by billing.

    F1 freezes the mechanism; F5 still owns the real commercial numbers. No catalog
    configured means no plan cap is active yet. If a catalog IS configured, its normal
    fail-closed loader validates it and max_users is read from PlanDefinition -- never
    from a second env var or a product constant.
    """
    from campaia_core.plan_catalog import CATALOG_PATH_ENV_VAR, load_plan_catalog

    if not os.environ.get(CATALOG_PATH_ENV_VAR):
        return {}
    catalog = load_plan_catalog()
    return {
        plan_id: plan.max_users
        for plan_id, plan in catalog.items()
        if plan.max_users is not None
    }


def _default_session_store():
    from .session import InMemorySessionStore

    return InMemorySessionStore()


def _default_allowed_origins() -> frozenset[str]:
    from .session import default_allowed_origins

    return default_allowed_origins()


def _default_billing_gateway() -> PaymentGatewayConnector:
    """Never a real gateway unless explicitly configured (same "never a real provider by
    default" discipline as `ai_provider` below). If `ASAAS_API_KEY` is set in the
    environment, use the real adapter (verified against the Asaas Sandbox 24/09/2026); else
    fall back to the in-memory simulator, exactly like every other connector in this app."""
    if os.environ.get("ASAAS_API_KEY"):
        return AsaasGateway(config=AsaasConfig.from_env())
    return PaymentGatewaySimulator()


def _default_asaas_webhook_receiver() -> AsaasWebhookReceiver:
    return AsaasWebhookReceiver(token_resolver=lambda: os.environ.get("ASAAS_WEBHOOK_TOKEN"))


def _default_vault_cipher(env: str):
    """Select the vault crypto backend without ever defaulting to a production root key.

    F4 production/staging uses Google Cloud KMS envelope encryption. The legacy Fernet
    environment key remains supported only for test/dev-local compatibility and is
    explicitly rejected in staging/production.
    """
    kms_key_name = os.environ.get("CAMPAIA_VAULT_KMS_KEY_NAME")
    raw_key = os.environ.get("CAMPAIA_VAULT_KEY")

    if kms_key_name:
        from .kms_vault import KmsEnvelopeCredentialCipher

        return KmsEnvelopeCredentialCipher(kms_key_name)

    if raw_key:
        if env not in DEV_AUTH_FIXTURE_ALLOWED_ENVS:
            raise RuntimeError(
                "CAMPAIA_VAULT_KEY legacy nao e permitido em staging/production. "
                "Configure CAMPAIA_VAULT_KMS_KEY_NAME e use Cloud KMS envelope encryption."
            )
        from campaia_core.credential_vault import CredentialCipher

        return CredentialCipher.from_env_value(raw_key)

    return None


def _default_ai_provider() -> AIProvider:
    """Never a real provider unless explicitly configured (same "never a real provider by
    default" discipline as `_default_billing_gateway`). If `GEMINI_API_KEY` is set in the
    environment, use the real adapter chosen in ADR-0021 (Google Gemini); else fall back to
    the in-memory simulator, whose default output matches the "strategist" agent's
    OutputSchema (`campaia_core/agents.py` AGENTS["strategist"]: requires objetivo/funil/
    canais/justificativa) so `/plan/regenerate` works out of the box without any credential.
    """
    if os.environ.get("GEMINI_API_KEY"):
        from campaia_core.gemini_provider import GeminiConfig, GeminiProvider

        schemas = {spec.output_schema.schema_id: spec.output_schema for spec in AGENTS.values()}
        return GeminiProvider(config=GeminiConfig.from_env(), schemas=schemas)
    return SimulatedAIProvider(
        output={
            "objetivo": "Gerar demanda qualificada dentro do orcamento aprovado.",
            "funil": "TOPO_MEIO",
            "canais": ["GOOGLE_ADS", "META_ADS"],
            "justificativa": "Saida simulada do SimulatedAIProvider (nunca um provedor real).",
        }
    )


#: Item 1.2 do cronograma mestre (24/09/2026): limite do unico endpoint publico sem
#: autenticacao de usuario (`/webhooks/asaas`). Generoso o bastante para nunca recusar
#: trafego legitimo do Asaas (que nao documenta um volume esperado por segundo, mas isto e
#: liquidacao de cobranca, nao um webhook de alta frequencia) e restritivo o bastante para
#: barrar flood de aplicacao de uma unica origem.
ASAAS_WEBHOOK_RATE_LIMIT_MAX_REQUESTS = 60
ASAAS_WEBHOOK_RATE_LIMIT_WINDOW = timedelta(minutes=1)


def _default_asaas_webhook_rate_limiter() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(
        max_requests=ASAAS_WEBHOOK_RATE_LIMIT_MAX_REQUESTS,
        window=ASAAS_WEBHOOK_RATE_LIMIT_WINDOW,
    )


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
    #: F3 production adapter. SQLite remains a compatibility backend for local/test use.
    database_url: str | None = None

    #: Item 1.3/WP-02 (24/09/2026). "production" (o default quando a variavel de ambiente
    #: nao esta setada) e o ambiente mais restritivo -- nunca populado com fixture de auth
    #: por acidente. Passar env="test"/"dev-local" explicitamente (ou setar CAMPAIA_ENV) e
    #: o UNICO jeito de habilitar o fixture de bearer token abaixo.
    env: str = field(default_factory=_default_env)

    #: Fixture de bearer token de dev/teste -- vazio por padrao (seguro). So populado
    #: automaticamente quando `env` esta em DEV_AUTH_FIXTURE_ALLOWED_ENVS (ver
    #: __post_init__); populado por fora disso em qualquer outro ambiente faz a
    #: inicializacao recusar (RuntimeError), nunca so ignorar silenciosamente.
    tokens: dict[str, TokenPrincipal] = field(default_factory=dict)
    # SECURITY FIX (Fase C2/C3, 27/09/2026 -- auditoria independente): chaveado por
    # (tenant_id, user_id, session_key), nao so (tenant_id, user_id) -- um step-up nao
    # pode sobreviver a logout->login (sessao nova) nem a troca de tenant/unidade dentro
    # da mesma sessao (ver api/deps.py::session_key_for). Fora de test/dev-local, o
    # header tambem precisa ser um ID token real verificado, nunca "qualquer valor
    # nao-vazio" -- ver api/deps.py::_is_genuine_step_up.
    step_up_at: dict[tuple[str, str, str], datetime] = field(default_factory=dict)

    idempotency: IdempotencyStore = field(default_factory=IdempotencyStore)
    capabilities: CapabilityRegistry = field(default_factory=_seed_capabilities)

    #: WP-04 (26/09/2026): `state` de OAuth emitido por POST /connections/oauth/start,
    #: guardado ate' o callback simulado (POST /connections/oauth/callback) resgatar --
    #: uso unico (removido no resgate), amarrado ao tenant que iniciou o fluxo, nunca
    #: aceito de um tenant diferente. Em memoria, mesma disciplina de `step_up_at`.
    oauth_pending_states: dict[str, "PendingOAuthState"] = field(default_factory=dict)

    brand_profiles: BrandProfileRepository = field(default_factory=BrandProfileRepository)
    connections: ConnectionRepository = field(default_factory=ConnectionRepository)
    #: Cofre real de credenciais de terceiro, por tenant. Em staging/producao a
    #: criptografia e resolvida em __post_init__ a partir de CAMPAIA_VAULT_KMS_KEY_NAME;
    #: a chave Fernet em env fica restrita a test/dev-local.
    vault: VaultRepository = field(default_factory=VaultRepository)
    vault_cipher: object | None = None
    campaigns: CampaignRepository = field(default_factory=CampaignRepository)
    approvals: ApprovalRepository = field(default_factory=ApprovalRepository)
    audit: AuditLog = field(default_factory=AuditLog)
    #: F1 commercial onboarding aggregate. Nova FM/FM are never seeded here; both are
    #: ordinary tenants created by the same product flow when used for homologation.
    organizations: OrganizationRepository = field(default_factory=OrganizationRepository)
    #: F1 decision approved 27/09/2026: user caps come from PlanDefinition.max_users in
    #: the external plan catalog, never hardcoded. Real commercial numbers remain F5.
    plan_user_limits: dict[str, int] = field(default_factory=_default_plan_user_limits)

    #: Tenant-level autonomy settings (GET/PUT /autonomy). Per-campaign AutonomySettings
    #: also exists on CampaignRecord for policy evaluation; this is the tenant default.
    tenant_autonomy: dict[str, AutonomySettings] = field(default_factory=dict)
    #: Contract requires AutonomySettings.updated_at (achado 11) -- tracked alongside
    #: tenant_autonomy since AutonomySettings itself (campaia_core.autonomy) is a frozen
    #: domain dataclass with no timestamp field of its own.
    tenant_autonomy_updated_at: dict[str, datetime] = field(default_factory=dict)

    #: Motor de cobranca propria do CampaIA (B11/ADR-0020). Uma assinatura ativa por tenant.
    #: Em memoria por enquanto -- persistencia fica para quando este motor tiver seu proprio
    #: bloco de integracao com `db.py`, mesmo padrao ja usado pelos outros repositorios.
    subscriptions: dict[str, Subscription] = field(default_factory=dict)
    #: Cobrancas ja enviadas ao gateway, por `gateway_charge_id` -- e o que permite ao
    #: webhook do Asaas encontrar de volta a que cobranca um pagamento confirmado pertence.
    charges: dict[str, SubscriptionCharge] = field(default_factory=dict)
    billing_gateway: PaymentGatewayConnector = field(default_factory=_default_billing_gateway)
    asaas_webhook: AsaasWebhookReceiver = field(default_factory=_default_asaas_webhook_receiver)
    #: Item 1.2 do cronograma mestre (24/09/2026) -- em memoria mesmo com `db_path`
    #: configurado: contador de janela e efemero por natureza (nao ha valor em persistir um
    #: contador que reseta a cada minuto), diferente do dedupe de evento acima.
    asaas_webhook_rate_limiter: FixedWindowRateLimiter = field(
        default_factory=_default_asaas_webhook_rate_limiter
    )

    ai_gateway: AIGateway = field(default_factory=AIGateway)
    #: `GEMINI_API_KEY` unset (the default, and every pre-existing test) -> in-memory
    #: SimulatedAIProvider, byte-for-byte the prior behaviour. Set -> real GeminiProvider
    #: (ADR-0021). See `_default_ai_provider`.
    ai_provider: AIProvider = field(default_factory=_default_ai_provider)
    agent_runner: AgentRunner = field(init=False)

    #: Item 1.3/WP-02 (24/09/2026): autenticacao real. `id_token_verifier` nunca e
    #: permissivo por padrao (ver `_default_id_token_verifier`) -- so vira o adaptador
    #: real do Google Identity Platform quando FIREBASE_PROJECT_ID estiver configurado
    #: (item 1.6 provisionado). `identity_directory` (None aqui) e resolvido em
    #: __post_init__ porque seu default depende de `env` -- dataclass default_factory
    #: nao tem acesso a outros campos. `sessions` fica em memoria nesta etapa (decisao do
    #: Diretor) -- nao e persistente/homologado para producao por causa disso.
    id_token_verifier: IdTokenVerifier = field(default_factory=_default_id_token_verifier)
    identity_directory: "IdentityDirectory | None" = None
    sessions: "SessionStore" = field(default_factory=_default_session_store)
    #: Achado de fm-security-review (24/09/2026), corrigido por decisao do Diretor:
    #: login-CSRF em POST /auth/session. Vazio por padrao -- fail-closed: nenhuma origem
    #: e aceita enquanto CAMPAIA_ALLOWED_ORIGINS nao estiver configurada. NUNCA um
    #: wildcard (nem aqui nem em session.parse_allowed_origins).
    allowed_origins: frozenset[str] = field(default_factory=_default_allowed_origins)

    def __post_init__(self) -> None:
        # vault_cipher depende do ambiente efetivo passado a AppState; resolver aqui evita
        # default_factory consultar CAMPAIA_ENV antes de considerar env="test"/"dev-local".
        if self.vault_cipher is None:
            self.vault_cipher = _default_vault_cipher(self.env)

        # Fixture de bearer token de dev/teste: so populado automaticamente quando `env`
        # permite; populado por qualquer outro meio fora desses ambientes recusa a
        # inicializacao (fail-closed por construcao -- exigencia literal do WP-02, nunca
        # so "esconder a opcao").
        if self.env in DEV_AUTH_FIXTURE_ALLOWED_ENVS and not self.tokens:
            self.tokens = _seed_tokens()
        if self.tokens and self.env not in DEV_AUTH_FIXTURE_ALLOWED_ENVS:
            raise RuntimeError(
                f"AppState.tokens (fixture de autenticacao de teste) nao pode estar "
                f"populado fora de {sorted(DEV_AUTH_FIXTURE_ALLOWED_ENVS)} -- env atual: "
                f"{self.env!r}. Isto e fail-closed por construcao (item 1.3/WP-02): o "
                f"fixture de auth nunca pode ficar disponivel em preview/staging/produção, "
                f"mesmo por engano de configuracao."
            )
        # Exactly one persistent backend may be active.
        if self.db_path is not None and self.database_url is not None:
            raise RuntimeError(
                "Configure only one persistence backend: db_path or database_url."
            )

        self.db = None
        self._persistent_step_up_store = None
        self._persistent_oauth_state_store = None

        if self.database_url is not None:
            from .postgres import PostgresDatabase

            self.db = PostgresDatabase(self.database_url)
        elif self.db_path is not None:
            from .db import Database

            self.db = Database(self.db_path)

        if self.db is not None:
            from .db import (
                PersistentIdempotencyStore,
                PersistentSeenEventStore,
                PersistentTenantAutonomy,
            )
            from .persistent_state import PersistentOAuthStateStore, PersistentStepUpStore
            from .session import PersistentSessionStore

            self.brand_profiles = BrandProfileRepository(self.db.table("brand_profiles"))
            self.connections = ConnectionRepository(self.db.table("connections"))
            self.vault = VaultRepository(self.db.table("credential_vault"))
            self.campaigns = CampaignRepository(self.db.table("campaigns"))
            self.approvals = ApprovalRepository(self.db.table("approvals"))
            self.audit = AuditLog(self.db.table("audit_events"))
            self.organizations = OrganizationRepository(self.db.table("organizations"))
            self.idempotency = PersistentIdempotencyStore(self.db.table("idempotency"))
            self.subscriptions = PersistentTenantObjectMap(
                self.db.table("billing_subscriptions")
            )
            self.charges = PersistentTenantObjectMap(self.db.table("billing_charges"))
            self.sessions = PersistentSessionStore(self.db.table("sessions"))
            self._persistent_step_up_store = PersistentStepUpStore(
                self.db.table("step_up_states")
            )
            self._persistent_oauth_state_store = PersistentOAuthStateStore(
                self.db.table("oauth_pending_states")
            )
            self.tenant_autonomy = PersistentTenantAutonomy(
                self.db.table("tenant_autonomy")
            )
            self.tenant_autonomy_updated_at = PersistentTenantAutonomy(
                self.db.table("tenant_autonomy_updated_at")
            )
            self.asaas_webhook = AsaasWebhookReceiver(
                token_resolver=self.asaas_webhook.token_resolver,
                seen_store=PersistentSeenEventStore(
                    self.db.table("asaas_webhook_seen_events")
                ),
            )
            if self.database_url is not None:
                from .postgres import PostgresFixedWindowRateLimiter

                self.asaas_webhook_rate_limiter = PostgresFixedWindowRateLimiter(
                    self.db,
                    scope="asaas-webhook",
                    max_requests=ASAAS_WEBHOOK_RATE_LIMIT_MAX_REQUESTS,
                    window=ASAAS_WEBHOOK_RATE_LIMIT_WINDOW,
                )
            # Billing gateway idempotency must share the durable store as well. Otherwise
            # a process restart can recreate the same external charge even when the HTTP
            # layer itself is persistent.
            if hasattr(self.billing_gateway, "idempotency"):
                self.billing_gateway.idempotency = self.idempotency

            # capabilities and dev/test tokens remain startup fixtures, never persisted.

        # The identity directory must be created AFTER persistence is selected so the
        # commercial directory observes the final OrganizationRepository instance.
        if self.identity_directory is None:
            self.identity_directory = _default_identity_directory(self.env, self.organizations)

        self.ai_gateway.providers.append(self.ai_provider)
        self.agent_runner = AgentRunner(gateway=self.ai_gateway)
        self.agent_runner.register_schemas()

    def lock_runtime_scope(self, scope: str) -> None:
        """Lock a mutable scope inside the active persistent transaction."""
        if self.db is not None:
            self.db.lock_key(f"runtime:{scope}")

    def record_step_up(
        self, tenant_id: str, user_id: str, session_key: str, *, at: datetime
    ) -> None:
        if self._persistent_step_up_store is not None:
            self._persistent_step_up_store.put(
                tenant_id, user_id, session_key, at=at
            )
            return
        self.step_up_at[(tenant_id, user_id, session_key)] = at

    def last_step_up(self, tenant_id: str, user_id: str, session_key: str) -> datetime | None:
        if self._persistent_step_up_store is not None:
            return self._persistent_step_up_store.get(tenant_id, user_id, session_key)
        return self.step_up_at.get((tenant_id, user_id, session_key))

    def invalidate_step_up_for_session(self, session_key: str) -> None:
        """SECURITY FIX (Fase 3, achado 3, 27/09/2026 -- auditoria independente): chamado
        por `api/routes_auth.py::switch_membership` a CADA troca de vinculo ativo dentro
        da mesma sessao. Remove TODO step-up registrado para `session_key`, qualquer que
        seja o (tenant_id, user_id) sob o qual foi gravado -- nao so o do vinculo que
        estava ativo antes da troca.

        Achado real: chavear `step_up_at` por (tenant_id, user_id, session_key) ja evita
        que o step-up de A "vaze" para B na mesma sessao (B tem um user_id diferente, a
        chave nao bate) -- mas ao voltar de B para A DENTRO da mesma sessao, o par
        (tenant_id, user_id) de A volta a ser identico ao que foi gravado antes da
        primeira troca, e o step-up antigo de A "ressuscitava" sem nenhuma reautenticacao
        nova. A regra exigida e' categorica: QUALQUER troca de tenant/unidade invalida
        TODO step-up daquela sessao, mesmo o de vinculos aos quais ela volta depois.
        """
        if self._persistent_step_up_store is not None:
            self._persistent_step_up_store.invalidate_session(session_key)
            return
        stale_keys = [key for key in self.step_up_at if key[2] == session_key]
        for key in stale_keys:
            del self.step_up_at[key]

    def start_oauth_state(
        self,
        state_token: str,
        *,
        tenant_id: str,
        provider: str,
        now: datetime,
        user_id: str,
        session_key: str,
        step_up_verified_at: datetime | None,
    ) -> None:
        pending = PendingOAuthState(
            tenant_id=tenant_id,
            provider=provider,
            created_at=now,
            user_id=user_id,
            session_key=session_key,
            step_up_verified_at=step_up_verified_at,
        )
        if self._persistent_oauth_state_store is not None:
            self._persistent_oauth_state_store.put(state_token, tenant_id, pending)
            return
        self.oauth_pending_states[state_token] = pending

    def redeem_oauth_state(
        self, state_token: str, *, tenant_id: str, now: datetime
    ) -> PendingOAuthState | None:
        """Resgate de UNICO uso: sempre remove o registro, mesmo quando a validacao
        falha (nunca deixa um `state` invalido/expirado/de outro tenant disponivel para
        uma segunda tentativa -- fail-closed, sem replay)."""
        if self._persistent_oauth_state_store is not None:
            return self._persistent_oauth_state_store.redeem(
                state_token,
                tenant_id=tenant_id,
                now=now,
                ttl=OAUTH_PENDING_STATE_TTL,
            )
        pending = self.oauth_pending_states.pop(state_token, None)
        if pending is None:
            return None
        if pending.tenant_id != tenant_id:
            return None
        if (now - pending.created_at) > OAUTH_PENDING_STATE_TTL:
            return None
        return pending
