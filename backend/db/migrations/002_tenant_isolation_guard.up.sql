-- F3 database-level tenant ownership guard.
-- RLS was evaluated but a single tenant-GUC policy is not safe for every runtime store:
-- sessions are looked up by an opaque pre-tenant id and may intentionally switch active
-- tenant. Tenant-owned rows instead get an equivalent database invariant: tenant_id is
-- immutable after INSERT. Tenant-scoped repositories also use tenant predicates.

CREATE OR REPLACE FUNCTION campaia_runtime.reject_tenant_rehome()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
        RAISE EXCEPTION 'tenant_id is immutable for %.%', TG_TABLE_SCHEMA, TG_TABLE_NAME
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS brand_profiles_tenant_immutable ON campaia_runtime.brand_profiles;
CREATE TRIGGER brand_profiles_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.brand_profiles
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS connections_tenant_immutable ON campaia_runtime.connections;
CREATE TRIGGER connections_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.connections
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS credential_vault_tenant_immutable ON campaia_runtime.credential_vault;
CREATE TRIGGER credential_vault_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.credential_vault
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS campaigns_tenant_immutable ON campaia_runtime.campaigns;
CREATE TRIGGER campaigns_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.campaigns
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS approvals_tenant_immutable ON campaia_runtime.approvals;
CREATE TRIGGER approvals_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.approvals
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS audit_events_tenant_immutable ON campaia_runtime.audit_events;
CREATE TRIGGER audit_events_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.audit_events
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS organizations_tenant_immutable ON campaia_runtime.organizations;
CREATE TRIGGER organizations_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.organizations
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS idempotency_tenant_immutable ON campaia_runtime.idempotency;
CREATE TRIGGER idempotency_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.idempotency
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS step_up_states_tenant_immutable ON campaia_runtime.step_up_states;
CREATE TRIGGER step_up_states_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.step_up_states
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS oauth_pending_states_tenant_immutable ON campaia_runtime.oauth_pending_states;
CREATE TRIGGER oauth_pending_states_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.oauth_pending_states
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS tenant_autonomy_tenant_immutable ON campaia_runtime.tenant_autonomy;
CREATE TRIGGER tenant_autonomy_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.tenant_autonomy
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS tenant_autonomy_updated_at_tenant_immutable ON campaia_runtime.tenant_autonomy_updated_at;
CREATE TRIGGER tenant_autonomy_updated_at_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.tenant_autonomy_updated_at
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS asaas_webhook_seen_events_tenant_immutable ON campaia_runtime.asaas_webhook_seen_events;
CREATE TRIGGER asaas_webhook_seen_events_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.asaas_webhook_seen_events
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

