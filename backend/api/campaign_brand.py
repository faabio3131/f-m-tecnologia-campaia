"""Freeze explicit brand choices; no client-authored snapshots or automatic defaults."""
from copy import deepcopy
from datetime import datetime, timezone

from .brand_assets import public_asset
from .brand_versions import freeze_version
from .errors import ApiError


def freeze_selected_brand(state, tenant, selection):
    if selection is None:
        return None
    profile = state.brand_profiles.get(tenant, selection.brand_profile_id)
    if profile is None:
        raise ApiError("NOT_FOUND", "Brand Kit indisponível.", status_code=404)
    if profile.version != selection.expected_version:
        raise ApiError("BRAND_VERSION_CHANGED", "O Brand Kit mudou. Atualize e confira a seleção antes de criar a campanha.", status_code=409)
    if len(set(selection.asset_ids)) != len(selection.asset_ids):
        raise ApiError("VALIDATION_FAILED", "Selecione cada arquivo apenas uma vez.", status_code=422)
    assets = []
    for identity in selection.asset_ids:
        if state.asset_store is None:
            raise ApiError("NOT_FOUND", "Arquivo indisponível.", status_code=404)
        record = state.asset_store.get(tenant, profile.brand_profile_id, identity)
        if (record["status"] != "READY" or state.asset_storage.mode == "DISABLED"
                or record["storage_namespace"] != state.asset_storage.namespace):
            raise ApiError("BRAND_ASSET_UNAVAILABLE", "Um arquivo selecionado está indisponível. Confira a seleção.", status_code=409)
        # The UUID binds an immutable manifest/generation; never expose bucket/object path.
        assets.append(public_asset(record))
    return {"profile": freeze_version(state, profile), "assets": assets,
            "recorded_at": datetime.now(timezone.utc).isoformat()}


def brand_snapshot(record):
    return record.brief.get("brand_snapshot_v1")


def brand_guidance(record):
    snapshot = brand_snapshot(record)
    return tuple(snapshot["profile"].get("restrictions", ())) if snapshot else ()


def brand_assets_ready(state, record):
    snapshot = brand_snapshot(record)
    if not snapshot or not snapshot["assets"]:
        return True
    if state.asset_store is None or state.asset_storage.mode == "DISABLED":
        return False
    for asset in snapshot["assets"]:
        try:
            current = state.asset_store.get(record.tenant_id, snapshot["profile"]["id"], asset["id"])
        except ApiError:
            return False
        if (current["status"] != "READY"
                or current["storage_namespace"] != state.asset_storage.namespace):
            return False
    return True


def require_brand_assets(state, record):
    if not brand_assets_ready(state, record):
        raise ApiError("BRAND_ASSET_UNAVAILABLE", "Um arquivo desta campanha foi removido ou está indisponível. Crie um novo briefing com arquivos disponíveis.", status_code=409)


def brand_agent_context(record):
    snapshot = brand_snapshot(record)
    if not snapshot:
        return {}
    profile = snapshot["profile"]
    return {"marca": {key: deepcopy(profile.get(key)) for key in
            ("name", "tone", "colors", "differentiators", "restrictions")},
            "arquivos_selecionados": [
                {"referencia": "arquivo-" + str(position + 1),
                 **{key: asset[key] for key in ("kind", "width", "height")}}
                for position, asset in enumerate(snapshot["assets"])],
            "marca_versao": profile["version"]}
