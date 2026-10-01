-- Roll back the CURRENT runtime-store migration.
-- Keep schema_migrations so the runner can record rollback atomically.

DROP TABLE IF EXISTS campaia_runtime.asaas_webhook_seen_events;
DROP TABLE IF EXISTS campaia_runtime.tenant_autonomy_updated_at;
DROP TABLE IF EXISTS campaia_runtime.tenant_autonomy;
DROP TABLE IF EXISTS campaia_runtime.oauth_pending_states;
DROP TABLE IF EXISTS campaia_runtime.step_up_states;
DROP TABLE IF EXISTS campaia_runtime.sessions;
DROP TABLE IF EXISTS campaia_runtime.idempotency;
DROP TABLE IF EXISTS campaia_runtime.organizations;
DROP TABLE IF EXISTS campaia_runtime.audit_events;
DROP TABLE IF EXISTS campaia_runtime.approvals;
DROP TABLE IF EXISTS campaia_runtime.campaigns;
DROP TABLE IF EXISTS campaia_runtime.credential_vault;
DROP TABLE IF EXISTS campaia_runtime.connections;
DROP TABLE IF EXISTS campaia_runtime.brand_profiles;
