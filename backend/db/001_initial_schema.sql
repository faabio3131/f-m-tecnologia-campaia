-- CAMPAIA — B7: DDL inicial do Postgres (migration 001)
--
-- ESCOPO (decisão do Diretor, 04/09/2026, após pesquisa prévia de escopo): este DDL cobre
-- exclusivamente as entidades que já são persistidas hoje em `backend/api/db.py`
-- (SQLite opcional, uma tabela JSON-blob por repositório: brand_profiles, connections,
-- campaigns, approvals, audit_events, idempotency, tenant_autonomy,
-- tenant_autonomy_updated_at). Não inventa tabelas novas para módulos de domínio que hoje
-- só existem em memória (budget/reservas fora do que já está aninhado em CampaignRecord,
-- outbox/inbox, reconciliation, AI gateway/cost ledger, permissions/RBAC) — isso seria um
-- modelo de dados especulativo, sem precedente de persistência real no código, e ficou
-- deliberadamente fora deste bloco.
--
-- As saídas do B5 (`pacing.PacingAssessment`, `optimizer.Recommendation`/`OptimizationReport`)
-- também não geram tabela aqui: são cálculos puros retornados por funções sem estado
-- (`PacingEngine.assess()`, `evaluate_campaign()`), nunca persistidos em código algum hoje.
-- Se o Diretor decidir no futuro que o histórico de sugestões deve ser auditável, isso é uma
-- tabela nova e deliberada — não uma migração do que já existe.
--
-- FORMATO: upgrade real do shape hoje genérico ((id, tenant_id, data JSON) por tabela) para
-- colunas reais nos campos que já são de fato consultados por igualdade/filtro no código
-- (id, tenant_id, status/estado, timestamps de corte), mantendo os campos aninhados/
-- complexos (brief, plano, decisão de política, histórico de estado, etc.) como JSONB — sem
-- reconstruir manualmente cada campo de cada dataclass em coluna própria, o que arriscaria
-- divergir da forma real dos objetos Python sem trazer nenhum benefício de consulta.
--
-- MULTI-TENANCY (decisão do Diretor, 04/09/2026): tenant_id é obrigatório e toda tabela tem
-- Row Level Security, por já ser invariante arquitetural registrado
-- (docs/security/TENANT_ISOLATION.md, "INVARIANTE ARQUITETURAL #4" — acesso cross-tenant
-- deve responder NOT_FOUND, nunca PERMISSION_DENIED). business_unit_id é uma coluna própria
-- mas sempre NULLABLE: a decisão D-03 (single-tenant-com-unidades-de-negócio vs. suporte a
-- agência multi-empresa) segue em aberto, e permissions.py já documenta que qualquer extensão
-- para agência deve ser aditiva (um nível de escopo acima de business_unit_id, não uma
-- reforma do que já existe) — este DDL não tenta antecipar essa decisão, só evita bloqueá-la.
--
-- VERIFICAÇÃO NESTA SANDBOX: ao contrário do que se presumia no início deste bloco, esta
-- sandbox tem um Postgres 16 real instalado. Este arquivo foi executado de fato contra um
-- servidor Postgres real (não apenas revisado por sintaxe) via db/verify_ddl_postgres.sh,
-- que aplica a migration inteira e testa RLS, CHECK, foreign key e chave composta com casos
-- válidos e inválidos. Ver docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md para o registro
-- completo da verificação, incluindo as duas execuções reprodutíveis do script.

BEGIN;

-- Extensão usada só para gen_random_uuid() como default de conveniência em id's gerados no
-- banco (a aplicação hoje gera seus próprios ids em Python via new_id(); este default existe
-- apenas para permitir inserts manuais/administrativos sem depender da aplicação).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Papel de aplicação que faz todas as queries via a API (BFF). RLS abaixo é escrito contra
-- este papel; o papel de superusuário/migração (quem roda este arquivo) não tem RLS aplicado
-- a ele por padrão no Postgres, o que é o comportamento esperado para migrations.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'campaia_app') THEN
    CREATE ROLE campaia_app LOGIN;
  END IF;
END
$$;

-- ============================================================================================
-- brand_profiles
-- Espelha api/repositories.py:BrandProfile. Campos de lista (colors, differentiators,
-- restrictions) viram JSONB por não serem hoje filtrados/indexados individualmente.
-- ============================================================================================

CREATE TABLE IF NOT EXISTS brand_profiles (
    brand_profile_id    TEXT PRIMARY KEY,
    tenant_id           TEXT NOT NULL,
    business_unit_id    TEXT NULL,
    name                TEXT NOT NULL,
    tone                TEXT NOT NULL,
    colors              JSONB NOT NULL DEFAULT '[]'::jsonb,
    differentiators     JSONB NOT NULL DEFAULT '[]'::jsonb,
    restrictions        JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS brand_profiles_tenant_idx ON brand_profiles (tenant_id);

ALTER TABLE brand_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY brand_profiles_tenant_isolation ON brand_profiles
    USING (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================================================
-- connections
-- Espelha api/repositories.py:Connection. `status` e `mode` viram colunas próprias (com CHECK
-- refletindo os enums do contrato) porque rotas filtram/decidem sobre eles diretamente.
-- ============================================================================================

CREATE TABLE IF NOT EXISTS connections (
    connection_id        TEXT PRIMARY KEY,
    tenant_id            TEXT NOT NULL,
    business_unit_id     TEXT NULL,
    provider             TEXT NOT NULL,
    external_account_id  TEXT NOT NULL,
    display_name         TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'ACTIVE'
                             CHECK (status IN ('ACTIVE', 'EXPIRED', 'REVOKED', 'NEEDS_REAUTH')),
    api_version          TEXT NOT NULL DEFAULT 'sim-1',
    mode                 TEXT NOT NULL DEFAULT 'SIMULATOR',
    last_synced_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS connections_tenant_idx ON connections (tenant_id);

ALTER TABLE connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY connections_tenant_isolation ON connections
    USING (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================================================
-- campaigns
-- Espelha api/repositories.py:CampaignRecord, que por sua vez envolve o Campaign de domínio
-- (campaia_core/states.py), o BudgetEngine (campaia_core/budget.py) e o AutonomySettings
-- (campaia_core/autonomy.py) daquela campanha especificamente (nunca compartilhados entre
-- campanhas, conforme já documentado em budget.py). `state` vira coluna própria com CHECK
-- pelos 13 valores de CampaignState, pois é o campo mais consultado/filtrado de toda a tabela
-- (rotas de listagem, transições, gates de aprovação). Todo o resto do envelope de domínio
-- (histórico de transição, budget engine completo, autonomy settings, plano, decisão de
-- política, recursos externos por canal) permanece JSONB — são objetos aninhados complexos,
-- versionados pelo próprio código Python via campaia_core, não por este schema.
-- ============================================================================================

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id          TEXT PRIMARY KEY,
    tenant_id            TEXT NOT NULL,
    business_unit_id     TEXT NULL,
    state                TEXT NOT NULL DEFAULT 'DRAFT'
                             CHECK (state IN (
                                 'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'PUBLISHING',
                                 'ACTIVE', 'OPTIMIZING', 'PAUSED', 'PAUSING', 'RESUMING',
                                 'COMPLETED', 'FAILED', 'CANCELLED', 'ARCHIVED'
                             )),
    connection_id        TEXT NULL REFERENCES connections (connection_id),
    plan_version         INTEGER NOT NULL DEFAULT 0,
    approval_id          TEXT NULL,
    created_by           TEXT NULL,
    brief                JSONB NOT NULL,
    plan                 JSONB NULL,
    planned_channels     JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_policy_decision JSONB NULL,
    external_resources   JSONB NOT NULL DEFAULT '{}'::jsonb,
    domain_state         JSONB NOT NULL,  -- Campaign completo (states.py), incl. history[]
    budget_engine        JSONB NOT NULL,  -- BudgetEngine completo (budget.py)
    autonomy_settings    JSONB NOT NULL,  -- AutonomySettings completo (autonomy.py)
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_synced_at       TIMESTAMPTZ NULL,

    -- Nota de verificação (achado explícito nesta migration, não corrigido aqui): a lista de
    -- 13 valores acima foi extraída de campaia_core/states.py:CampaignState nesta sessão.
    -- Antes de rodar contra um Postgres real, confirmar essa lista por leitura direta do
    -- enum outra vez -- não presumir que ela não mudou entre esta migration e a execução.
    CONSTRAINT campaigns_business_unit_requires_tenant
        CHECK (business_unit_id IS NULL OR tenant_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS campaigns_tenant_idx ON campaigns (tenant_id);
CREATE INDEX IF NOT EXISTS campaigns_tenant_state_idx ON campaigns (tenant_id, state);

ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
CREATE POLICY campaigns_tenant_isolation ON campaigns
    USING (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================================================
-- approvals
-- Espelha api/repositories.py:ApprovalRequest. `status` e `kind` viram colunas (com CHECK)
-- porque são o eixo de toda a UI/fluxo de aprovação (Nível 1 do MVP exige aprovação humana
-- para praticamente toda ação, conforme autonomy.py). `decided_by` (um set[str] em Python)
-- vira JSONB array — nenhuma consulta hoje filtra "aprovações decididas por X".
-- ============================================================================================

CREATE TABLE IF NOT EXISTS approvals (
    approval_id             TEXT PRIMARY KEY,
    tenant_id               TEXT NOT NULL,
    campaign_id             TEXT NOT NULL REFERENCES campaigns (campaign_id),
    kind                    TEXT NOT NULL
                                CHECK (kind IN ('PUBLISH', 'BUDGET_CHANGE', 'AUTONOMY_CHANGE')),
    status                  TEXT NOT NULL DEFAULT 'PENDING'
                                CHECK (status IN (
                                    'PENDING', 'APPROVED', 'REJECTED',
                                    'CHANGES_REQUESTED', 'EXPIRED'
                                )),
    requested_by            TEXT NOT NULL,
    amount                  NUMERIC(18, 2) NULL,
    plan_version            INTEGER NOT NULL DEFAULT 0,
    requires_dual_approval  BOOLEAN NOT NULL DEFAULT false,
    decided_by              JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at              TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS approvals_tenant_idx ON approvals (tenant_id);
CREATE INDEX IF NOT EXISTS approvals_tenant_status_idx ON approvals (tenant_id, status);
CREATE INDEX IF NOT EXISTS approvals_campaign_idx ON approvals (campaign_id);

ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
CREATE POLICY approvals_tenant_isolation ON approvals
    USING (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================================================
-- audit_events
-- Espelha api/repositories.py:AuditEvent. Somente-inserção por natureza (trilha de auditoria):
-- nenhuma rota atualiza um evento existente, então não há necessidade de RLS de UPDATE além
-- do padrão -- a política abaixo cobre SELECT/INSERT/DELETE igualmente, mas o código da
-- aplicação nunca invoca UPDATE/DELETE sobre esta tabela.
-- ============================================================================================

CREATE TABLE IF NOT EXISTS audit_events (
    audit_event_id       TEXT PRIMARY KEY,
    tenant_id            TEXT NOT NULL,
    actor_kind           TEXT NOT NULL DEFAULT 'USER',
    actor                TEXT NOT NULL,
    action               TEXT NOT NULL,
    target                TEXT NOT NULL,
    policy_decision_id   TEXT NULL,
    details              JSONB NOT NULL DEFAULT '{}'::jsonb,
    timestamp            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_tenant_idx ON audit_events (tenant_id);
CREATE INDEX IF NOT EXISTS audit_events_tenant_timestamp_idx ON audit_events (tenant_id, timestamp);

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_events_tenant_isolation ON audit_events
    USING (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================================================
-- idempotency
-- Espelha api/db.py:PersistentIdempotencyStore, que hoje usa uma chave composta
-- "{tenant_id}\x1f{idempotency_key}" como id de linha. Aqui viram duas colunas reais com uma
-- constraint UNIQUE composta, em vez de uma chave-string concatenada -- upgrade direto de
-- uma decisão que só existia no SQLite para caber no shape genérico (id, tenant_id, data).
-- `result` é o retorno arbitrário da operação original (pode ser qualquer estrutura
-- serializável do domínio) e continua JSONB por essa razão.
-- ============================================================================================

CREATE TABLE IF NOT EXISTS idempotency (
    tenant_id          TEXT NOT NULL,
    idempotency_key    TEXT NOT NULL,
    result             JSONB NOT NULL,
    stored_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, idempotency_key)
);

ALTER TABLE idempotency ENABLE ROW LEVEL SECURITY;
CREATE POLICY idempotency_tenant_isolation ON idempotency
    USING (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================================================
-- tenant_autonomy
-- Espelha api/db.py:PersistentTenantAutonomy, que hoje grava o dict inteiro
-- {tenant_id: AutonomySettings} como um único blob sob a chave fixa "all" (comentário do
-- próprio código: "the number of tenants in this BFF is small"). Aqui vira uma linha real por
-- tenant -- normalização direta, sem mudar o significado dos dados -- porque um blob único
-- de todos os tenants não pode ter RLS por tenant_id de forma alguma (a linha "all" não tem
-- um tenant_id só seu), o que quebraria o invariante de isolamento assim que este dado
-- fosse ao Postgres.
-- ============================================================================================

CREATE TABLE IF NOT EXISTS tenant_autonomy (
    tenant_id          TEXT PRIMARY KEY,
    settings           JSONB NOT NULL,  -- AutonomySettings completo (autonomy.py)
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE tenant_autonomy ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_autonomy_tenant_isolation ON tenant_autonomy
    USING (tenant_id = current_setting('app.tenant_id', true));

-- Nota: a tabela separada `tenant_autonomy_updated_at` do SQLite (api/state.py linha 198) foi
-- absorvida na própria coluna `updated_at` acima -- no schema original ela existe só porque o
-- shape genérico (id, tenant_id, data) não tinha uma coluna de timestamp própria para
-- consultar sem decodificar o JSON; aqui isso deixa de ser necessário.

COMMIT;
