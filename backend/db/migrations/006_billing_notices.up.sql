-- Source migration only: applying to any real environment requires explicit approval.
CREATE TABLE IF NOT EXISTS campaia_runtime.billing_notices (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS billing_notices_tenant_seq_idx
    ON campaia_runtime.billing_notices (tenant_id, seq);

CREATE TABLE IF NOT EXISTS campaia_runtime.billing_notice_reads (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS billing_notice_reads_tenant_seq_idx
    ON campaia_runtime.billing_notice_reads (tenant_id, seq);

CREATE TRIGGER billing_notices_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.billing_notices
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();
CREATE TRIGGER billing_notice_reads_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.billing_notice_reads
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

CREATE OR REPLACE FUNCTION campaia_runtime.reject_billing_notice_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'billing notice facts are immutable';
END;
$$;
CREATE TRIGGER billing_notices_append_only
BEFORE UPDATE OR DELETE ON campaia_runtime.billing_notices
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_billing_notice_mutation();
CREATE TRIGGER billing_notice_reads_append_only
BEFORE UPDATE OR DELETE ON campaia_runtime.billing_notice_reads
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_billing_notice_mutation();
