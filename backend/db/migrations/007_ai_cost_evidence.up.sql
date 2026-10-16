-- Source only. Real application/rollout requires explicit authorization.
CREATE TABLE IF NOT EXISTS campaia_runtime.ai_cost_journal (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_cost_journal_tenant_seq_idx
    ON campaia_runtime.ai_cost_journal (tenant_id, seq);
CREATE TABLE IF NOT EXISTS campaia_runtime.ai_cost_caps (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_cost_caps_tenant_seq_idx
    ON campaia_runtime.ai_cost_caps (tenant_id, seq);
CREATE TRIGGER ai_cost_journal_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.ai_cost_journal
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();
CREATE TRIGGER ai_cost_caps_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.ai_cost_caps
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();
CREATE OR REPLACE FUNCTION campaia_runtime.reject_ai_cost_journal_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'AI cost evidence is append-only';
END;
$$;
CREATE TRIGGER ai_cost_journal_append_only
BEFORE UPDATE OR DELETE ON campaia_runtime.ai_cost_journal
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_ai_cost_journal_mutation();
