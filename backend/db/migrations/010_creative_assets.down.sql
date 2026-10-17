-- Controlled rollback only; irreversible loss of creative metadata. Never run without director approval.
DROP TRIGGER IF EXISTS creative_assets_guard ON campaia_runtime.creative_assets;
DROP TRIGGER IF EXISTS creative_assets_tenant_immutable ON campaia_runtime.creative_assets;
DROP FUNCTION IF EXISTS campaia_runtime.guard_creative_asset_mutation();
DROP TABLE IF EXISTS campaia_runtime.creative_assets;
