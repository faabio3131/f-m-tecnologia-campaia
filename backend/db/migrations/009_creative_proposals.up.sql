-- Source only. Real migration and provider activation require explicit authorization.
CREATE TABLE IF NOT EXISTS campaia_runtime.creative_proposals (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS creative_proposals_tenant_seq_idx
    ON campaia_runtime.creative_proposals (tenant_id, seq);
CREATE TRIGGER creative_proposals_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.creative_proposals
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();
CREATE OR REPLACE FUNCTION campaia_runtime.reject_creative_proposal_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Creative proposals are immutable; append a revision';
END;
$$;
CREATE TRIGGER creative_proposals_append_only
BEFORE UPDATE OR DELETE ON campaia_runtime.creative_proposals
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_creative_proposal_mutation();
