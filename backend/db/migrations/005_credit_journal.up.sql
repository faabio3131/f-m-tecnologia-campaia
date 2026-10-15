-- Additive commercial journal, separate from provider costs and payment obligations.
CREATE TABLE campaia_runtime.credit_journal (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL
);
CREATE INDEX credit_journal_tenant_seq_idx
    ON campaia_runtime.credit_journal (tenant_id, seq);
CREATE FUNCTION campaia_runtime.reject_credit_journal_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'credit_journal is append-only; append an explicit reversal';
END;
$$;
CREATE TRIGGER credit_journal_append_only
BEFORE UPDATE OR DELETE ON campaia_runtime.credit_journal
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_credit_journal_mutation();
