-- F5 billing persistence: subscriptions and charges must survive process restarts.
-- Tenant ownership is immutable, matching the other tenant-owned runtime stores.

CREATE TABLE IF NOT EXISTS campaia_runtime.billing_subscriptions (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS billing_subscriptions_tenant_seq_idx
    ON campaia_runtime.billing_subscriptions (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.billing_charges (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS billing_charges_tenant_seq_idx
    ON campaia_runtime.billing_charges (tenant_id, seq);

DROP TRIGGER IF EXISTS billing_subscriptions_tenant_immutable
    ON campaia_runtime.billing_subscriptions;
CREATE TRIGGER billing_subscriptions_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.billing_subscriptions
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

DROP TRIGGER IF EXISTS billing_charges_tenant_immutable
    ON campaia_runtime.billing_charges;
CREATE TRIGGER billing_charges_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.billing_charges
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();
