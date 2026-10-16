-- Source only. Real migration/activation requires explicit authorization.
CREATE TABLE IF NOT EXISTS campaia_runtime.brand_assets (
    seq BIGSERIAL NOT NULL,
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (tenant_id <> ''),
    data JSONB NOT NULL CHECK (data->>'status' IN (
        'UPLOADING','UPLOAD_UNCERTAIN','READY','DELETE_REQUESTED','DELETE_UNCERTAIN','DELETED'))
);
CREATE INDEX IF NOT EXISTS brand_assets_tenant_seq_idx
    ON campaia_runtime.brand_assets (tenant_id, seq);
CREATE TRIGGER brand_assets_tenant_immutable
BEFORE UPDATE OF tenant_id ON campaia_runtime.brand_assets
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.reject_tenant_rehome();

CREATE OR REPLACE FUNCTION campaia_runtime.guard_brand_asset_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    old_status TEXT;
    new_status TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Brand asset metadata cannot be deleted directly';
    END IF;
    IF OLD.id IS DISTINCT FROM NEW.id OR
       (OLD.data - ARRAY['status','generation','updated_at','deleted_at']) IS DISTINCT FROM
       (NEW.data - ARRAY['status','generation','updated_at','deleted_at']) THEN
        RAISE EXCEPTION 'Brand asset identity and manifest are immutable';
    END IF;
    IF OLD.data->>'generation' IS NOT NULL AND
       OLD.data->>'generation' IS DISTINCT FROM NEW.data->>'generation' THEN
        RAISE EXCEPTION 'Brand asset generation is immutable once known';
    END IF;
    old_status := OLD.data->>'status';
    new_status := NEW.data->>'status';
    IF old_status IS DISTINCT FROM new_status AND NOT (
        (old_status IN ('UPLOADING','UPLOAD_UNCERTAIN') AND new_status IN ('UPLOAD_UNCERTAIN','READY')) OR
        (old_status = 'READY' AND new_status = 'DELETE_REQUESTED') OR
        (old_status IN ('DELETE_REQUESTED','DELETE_UNCERTAIN') AND new_status IN ('DELETE_UNCERTAIN','DELETED'))
    ) THEN
        RAISE EXCEPTION 'Invalid brand asset state transition';
    END IF;
    IF new_status IN ('READY','DELETE_REQUESTED','DELETE_UNCERTAIN','DELETED') AND
       COALESCE(NEW.data->>'generation', '') !~ '^[1-9][0-9]{0,24}$' THEN
        RAISE EXCEPTION 'Known brand asset requires a generation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER brand_assets_manifest_and_state
BEFORE UPDATE OR DELETE ON campaia_runtime.brand_assets
FOR EACH ROW EXECUTE FUNCTION campaia_runtime.guard_brand_asset_mutation();
