-- CampaIA F3 CURRENT runtime schema.
-- Historical backend/db/001_initial_schema.sql remains historical evidence only.
-- This migration mirrors the 14 stores actually wired by AppState today.
--
-- RLS is not enabled blindly here: sessions and organization discovery include
-- pre-tenant or opaque-id lookups. G3 keeps database-level tenant isolation/RLS as an
-- explicit remaining gate until repository calls carry a safe tenant context for every
-- applicable table. Application-level tenant checks remain mandatory and tested.

CREATE SCHEMA IF NOT EXISTS campaia_runtime;

CREATE TABLE IF NOT EXISTS campaia_runtime.brand_profiles (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS brand_profiles_tenant_seq_idx
    ON campaia_runtime.brand_profiles (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.connections (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS connections_tenant_seq_idx
    ON campaia_runtime.connections (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.credential_vault (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS credential_vault_tenant_seq_idx
    ON campaia_runtime.credential_vault (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.campaigns (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS campaigns_tenant_seq_idx
    ON campaia_runtime.campaigns (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.approvals (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS approvals_tenant_seq_idx
    ON campaia_runtime.approvals (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.audit_events (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_events_tenant_seq_idx
    ON campaia_runtime.audit_events (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.organizations (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS organizations_tenant_seq_idx
    ON campaia_runtime.organizations (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.idempotency (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idempotency_tenant_seq_idx
    ON campaia_runtime.idempotency (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.sessions (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_tenant_seq_idx
    ON campaia_runtime.sessions (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.step_up_states (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS step_up_states_tenant_seq_idx
    ON campaia_runtime.step_up_states (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.oauth_pending_states (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS oauth_pending_states_tenant_seq_idx
    ON campaia_runtime.oauth_pending_states (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.tenant_autonomy (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS tenant_autonomy_tenant_seq_idx
    ON campaia_runtime.tenant_autonomy (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.tenant_autonomy_updated_at (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS tenant_autonomy_updated_at_tenant_seq_idx
    ON campaia_runtime.tenant_autonomy_updated_at (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.asaas_webhook_seen_events (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS asaas_webhook_seen_events_tenant_seq_idx
    ON campaia_runtime.asaas_webhook_seen_events (tenant_id, seq);

