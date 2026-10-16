"""Tenant-scoped generated-image inventory and commercial quote BFF.

Read-only first slice. No image-generation POST is exposed until the F3 cost fence,
commercial settlement and durable delivery can be orchestrated atomically.
"""
from __future__ import annotations

from datetime import datetime, timezone

from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, authorize
from .creative_repository import CreativeRepository
from .metered_execution import quote_action
from .routes_campaigns import _authorize, _get_campaign_or_404
from .errors import ApiError


def _scope(request, permission):
    fixture, state, principal = _authorize(request, permission)
    campaign = _get_campaign_or_404(state, fixture.tenant_id,
                                    request.path_params["campaignId"], principal=principal)
    if campaign.business_unit_id != fixture.business_unit_id:
        decision = authorize(principal, permission,
                             Resource(tenant_id=fixture.tenant_id,
                                      business_unit_id=campaign.business_unit_id),
                             now=datetime.now(timezone.utc))
        if not decision.allowed:
            raise ApiError("NOT_FOUND", "Campanha indisponível.", status_code=404)
    if state.db is None:
        raise ApiError("PERSISTENCE_REQUIRED", "Criativos exigem persistência F3.", status_code=503)
    return fixture, state, campaign, CreativeRepository(state.db)


def _public(row):
    identity = row["identity"]
    return {
        "id": identity["creative_id"],
        "campaign_id": identity["campaign_id"],
        "campaign_version": identity["campaign_version"],
        "state": row["state"],
        "width": row["manifest"]["width"],
        "height": row["manifest"]["height"],
        "content_type": "image/png",
        "revision": row["revision"],
        "available": row["state"] == "STORED",
    }


async def list_generated_creatives(request):
    fixture, _state, campaign, repository = _scope(request, Permission.CAMPAIGN_VIEW)
    rows = [row for _, _, row in repository.table.rows_for_tenant(fixture.tenant_id)
            if row["identity"]["campaign_id"] == campaign.campaign_id
            and row["identity"]["business_unit_id"] == campaign.business_unit_id
            and row["state"] != "DELETED"]
    rows.sort(key=lambda row: row["identity"]["creative_id"])
    return JSONResponse({"items": [_public(row) for row in rows[:50]],
                         "has_more": len(rows) > 50,
                         "generation_enabled": False},
                        headers={"Cache-Control": "private, no-store"})


async def get_generated_creative(request):
    fixture, _state, campaign, repository = _scope(request, Permission.CAMPAIGN_VIEW)
    from uuid import UUID
    try:
        candidate = str(UUID(request.path_params["creativeId"]))
    except (TypeError, ValueError):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404) from None
    record = repository.table.get_for_tenant(candidate, fixture.tenant_id)
    if (record is None or record["identity"]["campaign_id"] != campaign.campaign_id
            or record["identity"]["business_unit_id"] != campaign.business_unit_id
            or record["state"] == "DELETED"):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404)
    return JSONResponse(_public(record), headers={"Cache-Control": "private, no-store"})


async def quote_generated_creative(request):
    fixture, state, _campaign, _repository = _scope(request, Permission.CAMPAIGN_EDIT)
    # This is a preview of the existing F5 commercial ledger policy. No charge or
    # entitlement is minted by quoting, and no fallback price is hardcoded.
    quote = quote_action(state, fixture.tenant_id, "image")
    if quote["mode"] != "COMMERCIAL":
        raise ApiError("BILLING_USAGE_UNAVAILABLE", "Política de créditos de imagem indisponível.", status_code=503)
    return JSONResponse({**quote, "generation_enabled": False},
                        headers={"Cache-Control": "private, no-store"})


async def generate_campaign_image(request):
    """One governed request: commercial RESERVE -> F3-costed model -> private GCS -> SETTLE.

    No real external call unless BOTH Gemini image and private GCS are enabled.
    Unknown provider/storage results retain reservation and never auto-redispatch.
    """
    from decimal import Decimal, InvalidOperation
    from hashlib import sha256
    import base64
    import json
    import os
    from uuid import NAMESPACE_URL, uuid5
    from pydantic import BaseModel, ConfigDict, Field
    from starlette.concurrency import run_in_threadpool
    from campaia_core.ai_gateway import AIRequest, AITask, AIStatus
    from campaia_core.asset_storage import AssetStorageError
    from campaia_core.creative_assets import CreativeIdentity, CreativeManifest, CreativeState, CreativeStateTransition
    from campaia_core.gcs_asset_storage import configured_asset_storage
    from .creative_private_storage import CreativePrivateStorage
    from .deps import require_idempotency_key
    from .metered_execution import execute_metered
    from .models import CreditConfirmation
    from .bounded_body import parse_bounded_body

    class ImageInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        expected_plan_version: int = Field(ge=1)
        prompt: str = Field(min_length=8, max_length=1500)
        credit_confirmation: CreditConfirmation

    fixture, state, campaign, repository = _scope(request, Permission.CAMPAIGN_EDIT)
    key = require_idempotency_key(request)
    body = await parse_bounded_body(request, ImageInput)
    if body.expected_plan_version != campaign.plan_version or campaign.plan is None:
        raise ApiError("AI_INPUT_CHANGED", "Revise a estratégia vigente.", status_code=409)
    if not state.image_provider.config.enabled:
        raise ApiError("AI_CAPABILITY_UNAVAILABLE", "Geração de imagem indisponível.", status_code=503)
    storage = configured_asset_storage()
    if storage.mode != "PROVIDER":
        raise ApiError("ASSET_STORAGE_DISABLED", "Armazenamento privado indisponível.", status_code=503)
    try:
        ceiling = Decimal(os.environ.get("CAMPAIA_IMAGE_MAX_COST_UNITS", ""))
        if not ceiling.is_finite() or ceiling <= 0 or ceiling > Decimal("1000000"):
            raise ValueError("cost ceiling")
    except (InvalidOperation, ValueError):
        raise ApiError("AI_COST_POLICY_UNAVAILABLE", "Teto interno de imagem não configurado.", status_code=503) from None

    identity = CreativeIdentity(fixture.tenant_id, campaign.business_unit_id,
        campaign.campaign_id, campaign.plan_version,
        str(uuid5(NAMESPACE_URL, fixture.tenant_id + ":creative-image:" + key)))
    request_identity = {
        "campaign": campaign.campaign_id,
        "plan_version": campaign.plan_version, "prompt": body.prompt.strip(),
    }
    bill_key = "image:" + campaign.campaign_id + ":" + key

    def run():
        def generate():
            # Cost ledger claim/check and external dispatch are handled by the F3 gateway.
            ai_request = AIRequest(
                request_id=identity.creative_id, tenant_id=fixture.tenant_id,
                task=AITask.GENERATE_IMAGE,
                input={"prompt": body.prompt.strip(), "campaign": campaign.campaign_id,
                       "plan_version": campaign.plan_version},
                output_schema_id="generated-image", max_cost_units=ceiling,
                pinned_provider="GEMINI_IMAGE", timeout_ms=30000,
            )
            result = state.ai_gateway.execute(ai_request)
            if not result.ok or not result.provenance.cost_complete:
                raise ApiError("AI_OPERATION_PENDING",
                    "Geração sem entrega confirmada; reserva mantida para reconciliação.", status_code=503)
            output = result.output
            if not isinstance(output, dict):
                raise ApiError("AI_OUTPUT_INVALID", "Resultado inválido.", status_code=422)
            try:
                png = base64.b64decode(output["data_base64"], validate=True)
            except (KeyError, TypeError, ValueError):
                raise ApiError("AI_OUTPUT_INVALID", "Imagem inválida.", status_code=422) from None
            manifest = CreativeManifest.from_normalized_png(
                identity, png, provider="GEMINI_IMAGE",
                model=result.provenance.model or state.image_provider.config.model,
                generation_request_id=identity.creative_id,
            )
            row, replay = repository.claim(manifest, bill_key, storage.max_active_bytes)
            if not replay:
                repository.transition(identity, CreativeStateTransition(
                    CreativeState.RESERVED, CreativeState.GENERATING, row["revision"]))
            current = CreativePrivateStorage(repository, storage).upload(manifest, png)
            if current["state"] != CreativeState.STORED.value:
                raise ApiError("AI_OPERATION_PENDING",
                               "Armazenamento ainda não confirmado.", status_code=503)
            return current

        def deliver(record):
            # Revalidate current authenticated tenant/unit and campaign version
            # before debiting credits and exposing a stored creative.
            verified_fixture, _state, latest, _repo = _scope(request, Permission.CAMPAIGN_EDIT)
            if verified_fixture.tenant_id != fixture.tenant_id or (
                latest.business_unit_id != identity.business_unit_id
                or latest.plan_version != identity.campaign_version
                or latest.campaign_id != identity.campaign_id
            ):
                raise ApiError("AI_INPUT_CHANGED", "Campanha alterada durante geração.", status_code=409)
            if record["state"] != CreativeState.STORED.value:
                raise ApiError("AI_OPERATION_PENDING", "Entrega não confirmada.", status_code=503)
            state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                action="CREATIVE_IMAGE_DELIVERED", target=identity.creative_id,
                details={"campaign_id": campaign.campaign_id, "version": campaign.plan_version})
            return _public(record)

        return execute_metered(state, fixture, "http:" + bill_key,
            request_identity, body.credit_confirmation.model_dump(mode="json"),
            "image", generate, deliver)

    result = await run_in_threadpool(run)
    return JSONResponse(result, status_code=201,
                        headers={"Cache-Control": "private, no-store"})
