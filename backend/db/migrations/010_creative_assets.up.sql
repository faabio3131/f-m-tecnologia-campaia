-- WP-R04-04B. Source only; production migration requires director approval.
CREATE TABLE campaia_runtime.creative_assets (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL,
    CONSTRAINT creative_state_check CHECK (data->>'state' IN (
        'RESERVED','GENERATING','STORAGE_PENDING','STORED',
        'FAILED','DELETE_PENDING','DELETED')),
    CONSTRAINT creative_revision_check CHECK (
        jsonb_typeof(data->'revision') = 'number'
        AND (data->>'revision') ~ '^(0|[1-9][0-9]*)$'
        AND (data->>'revision')::NUMERIC < 9223372036854775807),
    CONSTRAINT creative_tenant_check CHECK (data->'identity'->>'tenant_id' = tenant_id),
    CONSTRAINT creative_id_check CHECK (data->'identity'->>'creative_id' = id),
    CONSTRAINT creative_generation_check CHECK (
        (data->>'state' IN ('STORED','DELETE_PENDING','DELETED')
         AND COALESCE(data->>'storage_generation','') ~ '^[1-9][0-9]{0,24}$')
        OR (data->>'state' NOT IN ('STORED','DELETE_PENDING','DELETED')
            AND data->>'storage_generation' IS NULL))
);
CREATE INDEX creative_assets_tenant_seq_idx
    ON campaia_runtime.creative_assets (tenant_id, seq);
CREATE TRIGGER creative_assets_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.creative_assets
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

CREATE FUNCTION campaia_runtime.guard_creative_asset_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    a TEXT;
    b TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Creative metadata cannot be deleted directly';
    END IF;
    IF OLD.id IS DISTINCT FROM NEW.id OR
       (OLD.data - ARRAY['state','revision','storage_generation'])
          IS DISTINCT FROM (NEW.data - ARRAY['state','revision','storage_generation']) THEN
        RAISE EXCEPTION 'Creative identity, context and manifest are immutable';
    END IF;
    IF OLD.data->>'storage_generation' IS NOT NULL AND
       OLD.data->>'storage_generation' IS DISTINCT FROM NEW.data->>'storage_generation' THEN
        RAISE EXCEPTION 'Creative storage generation is immutable';
    END IF;
    a := OLD.data->>'state';
    b := NEW.data->>'state';
    IF NOT (
        (a = 'RESERVED' AND b IN ('GENERATING','FAILED')) OR
        (a = 'GENERATING' AND b IN ('STORAGE_PENDING','FAILED')) OR
        (a = 'STORAGE_PENDING' AND b = 'STORED') OR
        (a = 'STORED' AND b = 'DELETE_PENDING') OR
        (a = 'DELETE_PENDING' AND b = 'DELETED')
    ) THEN
        RAISE EXCEPTION 'Invalid creative state transition or replay';
    END IF;
    IF (NEW.data->>'revision')::NUMERIC IS DISTINCT FROM
       (OLD.data->>'revision')::NUMERIC + 1 THEN
        RAISE EXCEPTION 'Creative revision must increment exactly once';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER creative_assets_guard
BEFORE UPDATE OR DELETE ON campaia_runtime.creative_assets
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.guard_creative_asset_mutation();
