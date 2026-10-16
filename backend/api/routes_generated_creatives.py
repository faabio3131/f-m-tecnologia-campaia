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
        "content_url": ("/api/campaia/campaigns/" + identity["campaign_id"] +
                        "/images/" + identity["creative_id"] + "/content")
                       if row["state"] == "STORED" else None,
    }


def _storage_usable(state, storage):
    return (storage.mode == "PROVIDER" or
            (state.env in ("test", "dev-local") and storage.mode == "SIMULATOR"))


def _generation_available(state, tenant_id):
    from campaia_core.gcs_asset_storage import configured_asset_storage
    from campaia_core.asset_storage import AssetStorageError
    if not state.image_provider.config.enabled:
        return False
    try:
        storage = configured_asset_storage()
        return _storage_usable(state, storage) and quote_action(
            state, tenant_id, "image")["mode"] == "COMMERCIAL"
    except (ApiError, AssetStorageError, ValueError):
        return False


def _paginate_private_creatives(rows, cursor):
    """Cursor valid only within the caller's already tenant/unit/campaign-filtered rows."""
    rows.sort(key=lambda row: row["identity"]["creative_id"])
    if cursor is not None:
        from uuid import UUID
        try:
            if str(UUID(cursor)) != cursor:
                raise ValueError("non-canonical cursor")
        except (TypeError, ValueError):
            raise ApiError("VALIDATION_FAILED", "Cursor inválido.", status_code=422) from None
        # Never accept a cursor referring to a different tenant, unit or campaign.
        if not any(row["identity"]["creative_id"] == cursor for row in rows):
            raise ApiError("NOT_FOUND", "Cursor indisponível.", status_code=404)
        rows = [row for row in rows if row["identity"]["creative_id"] > cursor]
    selected = rows[:50]
    return selected, len(rows) > 50


async def list_generated_creatives(request):
    fixture, state, campaign, repository = _scope(request, Permission.CAMPAIGN_VIEW)
    rows = [row for _, _, row in repository.table.rows_for_tenant(fixture.tenant_id)
            if row["identity"]["campaign_id"] == campaign.campaign_id
            and row["identity"]["business_unit_id"] == campaign.business_unit_id
            and row["state"] != "DELETED"]
    selected, has_more = _paginate_private_creatives(rows, request.query_params.get("cursor"))
    return JSONResponse({"items": [_public(row) for row in selected],
                         "has_more": has_more,
                         "next_cursor": selected[-1]["identity"]["creative_id"]
                             if has_more else None,
                         "generation_enabled": _generation_available(state, fixture.tenant_id)},
                        headers={"Cache-Control": "private, no-store"})


async def get_generated_creative(request):
    fixture, state, campaign, repository = _scope(request, Permission.CAMPAIGN_VIEW)
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


def _preview_policy(row, campaign, review=None):
    """Fail-closed image preview: stored bytes never imply human approval/publishability."""
    version_current = row["identity"]["campaign_version"] == campaign.plan_version
    stored = row["state"] == "STORED" and bool(row.get("storage_generation"))
    from .creative_image_review import decision_applies
    approved = stored and version_current and decision_applies(row, review)
    width, height = row["manifest"]["width"], row["manifest"]["height"]
    # Geometric hints only, never a provider-specific media acceptance certificate.
    ratio = width / height if height > 0 else 0
    format_hints = ([name for name, target in
                     (("SQUARE", 1.0), ("PORTRAIT_4_5", 0.8), ("STORY_9_16", 9 / 16))
                     if abs(ratio - target) <= 0.02] if width > 0 else [])
    return {
        "preview_available": stored and version_current,
        "campaign_version_current": version_current,
        "storage_verified": stored,
        "format_hints": format_hints,
        "channel_media_validated": False,
        "human_review": (review.get("decision", "NOT_REVIEWED") if review else "NOT_REVIEWED"),
        "publication_allowed": False,
        "blocking_reasons": (
            ([] if stored else ["IMAGE_NOT_STORED"]) +
            ([] if version_current else ["CAMPAIGN_VERSION_CHANGED"]) +
            ([] if approved else ["HUMAN_REVIEW_REQUIRED"])
        ),
    }


async def preview_generated_creative(request):
    """Read-only preview policy without impersonating an approval decision."""
    fixture, state, campaign, repository = _scope(request, Permission.CAMPAIGN_VIEW)
    from uuid import UUID
    try:
        creative_id = str(UUID(request.path_params["creativeId"]))
    except (TypeError, ValueError):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404) from None
    row = repository.table.get_for_tenant(creative_id, fixture.tenant_id)
    if (row is None or row["identity"]["campaign_id"] != campaign.campaign_id
            or row["identity"]["business_unit_id"] != campaign.business_unit_id
            or row["state"] == "DELETED"):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404)
    from .creative_image_review import CreativeImageReviewStore
    from campaia_core.creative_assets import CreativeIdentity
    review = CreativeImageReviewStore(state).get(CreativeIdentity(**row["identity"]))
    return JSONResponse({"creative": _public(row), "policy": _preview_policy(row, campaign, review)},
                        headers={"Cache-Control": "private, no-store"})


async def quote_generated_creative(request):
    fixture, state, _campaign, _repository = _scope(request, Permission.CAMPAIGN_EDIT)
    # This is a preview of the existing F5 commercial ledger policy. No charge or
    # entitlement is minted by quoting, and no fallback price is hardcoded.
    quote = quote_action(state, fixture.tenant_id, "image")
    if quote["mode"] != "COMMERCIAL":
        raise ApiError("BILLING_USAGE_UNAVAILABLE", "Política de créditos de imagem indisponível.", status_code=503)
    return JSONResponse({**quote, "generation_enabled": _generation_available(state, fixture.tenant_id)},
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
        expected_plan_version: int = Field(ge=1, strict=True)
        prompt: str = Field(min_length=8, max_length=1500)
        credit_confirmation: CreditConfirmation

    fixture, state, campaign, repository = _scope(request, Permission.CAMPAIGN_EDIT)
    key = require_idempotency_key(request)
    body = await parse_bounded_body(request, ImageInput)
    if len(body.prompt.strip()) < 8:
        raise ApiError("VALIDATION_FAILED", "Descreva a imagem em pelo menos oito caracteres.", status_code=422)
    if body.expected_plan_version != campaign.plan_version or campaign.plan is None:
        raise ApiError("AI_INPUT_CHANGED", "Revise a estratégia vigente.", status_code=409)
    from .campaign_brand import require_brand_assets, brand_agent_context
    require_brand_assets(state, campaign)
    if not state.image_provider.config.enabled:
        raise ApiError("AI_CAPABILITY_UNAVAILABLE", "Geração de imagem indisponível.", status_code=503)
    storage = configured_asset_storage()
    if not _storage_usable(state, storage):
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
                       "plan_version": campaign.plan_version,
                       "brand": brand_agent_context(campaign)},
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
            operation = sha256((fixture.tenant_id + ":" + "http:" + bill_key).encode()).hexdigest()
            row, replay = repository.claim(manifest, bill_key, storage.max_active_bytes,
                                           credit_operation_id=operation, requested_by=fixture.user_id)
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
            require_brand_assets(state, latest)
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


async def reconcile_campaign_image(request):
    """Recover an unknown GCS upload and matching reserved F5 credits without redispatch."""
    from uuid import UUID
    from campaia_core.asset_storage import AssetStorageError
    from campaia_core.creative_assets import CreativeIdentity, CreativeState
    from campaia_core.gcs_asset_storage import configured_asset_storage
    from .creative_private_storage import CreativePrivateStorage
    from .creative_image_settlement import settle_stored_creative
    from .deps import require_idempotency_key
    from starlette.concurrency import run_in_threadpool

    fixture, state, campaign, repository = _scope(request, Permission.CAMPAIGN_EDIT)
    require_idempotency_key(request)
    try:
        creative_id = str(UUID(request.path_params["creativeId"]))
    except (TypeError, ValueError):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404) from None
    row = repository.table.get_for_tenant(creative_id, fixture.tenant_id)
    if (row is None or row["identity"]["campaign_id"] != campaign.campaign_id
            or row["identity"]["business_unit_id"] != campaign.business_unit_id
            or row["state"] == CreativeState.DELETED.value):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404)
    operation_id = row.get("credit_operation_id")
    if not operation_id:
        raise ApiError("CREDIT_RECONCILIATION_UNAVAILABLE",
                       "Registro não possui reserva comercial verificável.", status_code=409)
    storage = configured_asset_storage()
    if not _storage_usable(state, storage):
        raise ApiError("ASSET_STORAGE_DISABLED", "Armazenamento não configurado.", status_code=503)
    identity = CreativeIdentity(**row["identity"])
    if identity.campaign_version != campaign.plan_version:
        raise ApiError("AI_INPUT_CHANGED", "Esta geração pertence a outra versão da estratégia.", status_code=409)

    def reconcile():
        checked = CreativePrivateStorage(repository, storage).reconcile_after_restart(identity)
        if checked["state"] == CreativeState.STORED.value:
            # Same canonical F5 reference used by execute_metered; repeated GET/POST
            # reconciliation cannot consume new credits or redispatch AI.
            settle_stored_creative(state, identity=identity, operation_id=operation_id,
                delivery_key=operation_id, actor_id=fixture.user_id)
        return _public(checked)

    result = await run_in_threadpool(reconcile)
    return JSONResponse(result, status_code=200 if result["available"] else 202,
                        headers={"Cache-Control": "private, no-store"})


async def read_generated_creative_content(request):
    """Authenticated same-origin PNG proxy pinned to immutable GCS generation."""
    from uuid import UUID
    from starlette.responses import Response
    from starlette.concurrency import run_in_threadpool
    from campaia_core.asset_storage import StoredAsset
    from campaia_core.creative_assets import CreativeIdentity, CreativeManifest, recovery_storage_manifest
    from campaia_core.gcs_asset_storage import configured_asset_storage

    fixture, state, campaign, repository = _scope(request, Permission.CAMPAIGN_VIEW)
    try:
        creative_id = str(UUID(request.path_params["creativeId"]))
    except (TypeError, ValueError):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404) from None
    record = repository.table.get_for_tenant(creative_id, fixture.tenant_id)
    if (record is None or record["identity"]["campaign_id"] != campaign.campaign_id
            or record["identity"]["business_unit_id"] != campaign.business_unit_id
            or record["state"] != "STORED" or not record["storage_generation"]):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404)
    identity = CreativeIdentity(**record["identity"])
    manifest = CreativeManifest(identity=identity, **{
        k: v for k, v in record["manifest"].items() if k != "identity"
    })
    storage = configured_asset_storage()
    if not _storage_usable(state, storage):
        raise ApiError("ASSET_STORAGE_DISABLED", "Armazenamento privado indisponível.", status_code=503)
    asset = StoredAsset(recovery_storage_manifest(manifest), record["storage_generation"])
    data = await run_in_threadpool(storage.read, asset)
    return Response(data, media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    })

async def decide_generated_creative_review(request):
    """Only a freshly stepped-up, authorized independent reviewer can decide."""
    from uuid import UUID
    from pydantic import BaseModel, ConfigDict
    from .deps import require_idempotency_key, require_step_up, build_domain_principal
    from .bounded_body import parse_bounded_body
    from .creative_image_review import CreativeImageReviewStore, ReviewDecision
    from campaia_core.creative_assets import CreativeIdentity
    from campaia_core.asset_storage import AssetStorageError

    class ImageReviewInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        decision: ReviewDecision
        expected_sha256: str
        expected_generation: str

    fixture, state, campaign, repository = _scope(request, Permission.APPROVAL_DECIDE)
    require_step_up(request, fixture)
    require_idempotency_key(request)
    body = await parse_bounded_body(request, ImageReviewInput, max_bytes=2048)
    try:
        creative_id = str(UUID(request.path_params["creativeId"]))
    except (ValueError, TypeError):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404) from None
    row = repository.table.get_for_tenant(creative_id, fixture.tenant_id)
    if (row is None or row["identity"]["campaign_id"] != campaign.campaign_id
            or row["identity"]["business_unit_id"] != campaign.business_unit_id
            or row["identity"]["campaign_version"] != campaign.plan_version):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404)
    # Reviewer must be distinct from the verified generator actor. Older assets
    # without server-persisted authorship cannot be safely approved.
    requester_id = row.get("requested_by")
    if not requester_id:
        raise ApiError("REVIEW_ORIGIN_UNAVAILABLE", "Autoria não comprovada.", status_code=409)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=campaign.business_unit_id,
                        resource_id=creative_id, created_by=requester_id)
    from campaia_core.permissions import can_approve
    decision = can_approve(principal, resource, now=datetime.now(timezone.utc),
                           requester_id=requester_id, already_decided_by=frozenset(), amount=None)
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    identity = CreativeIdentity(**row["identity"])
    try:
        record, replayed = CreativeImageReviewStore(state).decide(
            identity, reviewer_id=fixture.user_id, requester_id=requester_id,
            decision=body.decision, expected_sha256=body.expected_sha256,
            expected_generation=body.expected_generation)
    except AssetStorageError:
        raise ApiError("REVIEW_CONFLICT", "Decisão incompatível com a versão da imagem.", status_code=409) from None
    return JSONResponse({"decision": record["decision"], "reviewer_id": record["reviewer_id"],
                         "replayed": replayed}, headers={"Cache-Control": "private, no-store"})



async def delete_generated_creative(request):
    """Authorized tombstone-before-delete; unknown GCS outcomes remain pending."""
    from uuid import UUID
    from starlette.concurrency import run_in_threadpool
    from .deps import require_idempotency_key, require_step_up
    from .creative_private_storage import CreativePrivateStorage
    from campaia_core.creative_assets import CreativeIdentity
    from campaia_core.gcs_asset_storage import configured_asset_storage

    fixture, state, campaign, repository = _scope(request, Permission.CAMPAIGN_EDIT)
    require_step_up(request, fixture)
    require_idempotency_key(request)
    try:
        creative_id = str(UUID(request.path_params["creativeId"]))
    except (ValueError, TypeError):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404) from None
    row = repository.table.get_for_tenant(creative_id, fixture.tenant_id)
    if (row is None or row["identity"]["campaign_id"] != campaign.campaign_id
            or row["identity"]["business_unit_id"] != campaign.business_unit_id
            or row["identity"]["campaign_version"] != campaign.plan_version):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404)
    if row["state"] not in ("STORED", "DELETE_PENDING", "DELETED"):
        raise ApiError("IMAGE_NOT_DELETABLE", "O criativo ainda não pode ser excluído.", status_code=409)
    storage = configured_asset_storage()
    if not _storage_usable(state, storage):
        raise ApiError("ASSET_STORAGE_DISABLED", "Armazenamento privado indisponível.", status_code=503)
    identity = CreativeIdentity(**row["identity"])
    # Safety: never delete reviewed/approved material as a regular edit mutation.
    from .creative_image_review import CreativeImageReviewStore
    review = CreativeImageReviewStore(state).get(identity)
    if review and review.get("decision") == "APPROVE":
        raise ApiError("IMAGE_REVIEW_LOCKED", "Criativo aprovado exige fluxo de revogação governado.", status_code=409)
    result = await run_in_threadpool(CreativePrivateStorage(repository, storage).delete, identity)
    return JSONResponse({"id": creative_id, "state": result["state"],
                         "deletion_confirmed": result["state"] == "DELETED",
                         "retention_note": "Metadados e trilha de auditoria preservados."},
                        status_code=200 if result["state"] == "DELETED" else 202,
                        headers={"Cache-Control": "private, no-store"})

async def revoke_generated_creative_review(request):
    """Governed terminal revocation; never resurrects an approval."""
    from uuid import UUID
    from pydantic import BaseModel, ConfigDict, Field
    from .deps import require_idempotency_key, require_step_up, build_domain_principal
    from .bounded_body import parse_bounded_body
    from .creative_image_review import CreativeImageReviewStore
    from campaia_core.creative_assets import CreativeIdentity
    from campaia_core.permissions import can_approve
    from campaia_core.asset_storage import AssetStorageError

    class RevokeInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        expected_sha256: str
        expected_generation: str
        reason: str = Field(min_length=8, max_length=500)

    fixture, state, campaign, repository = _scope(request, Permission.APPROVAL_DECIDE)
    require_step_up(request, fixture)
    require_idempotency_key(request)
    body = await parse_bounded_body(request, RevokeInput, max_bytes=2048)
    try:
        creative_id = str(UUID(request.path_params["creativeId"]))
    except (ValueError, TypeError):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404) from None
    row = repository.table.get_for_tenant(creative_id, fixture.tenant_id)
    if (row is None or row["identity"]["campaign_id"] != campaign.campaign_id
            or row["identity"]["business_unit_id"] != campaign.business_unit_id
            or row["identity"]["campaign_version"] != campaign.plan_version):
        raise ApiError("NOT_FOUND", "Criativo indisponível.", status_code=404)
    # Channel-side compensation is not implemented: never silently revoke an image
    # once this campaign has a recorded external resource.
    if campaign.external_resources:
        raise ApiError("IMAGE_REVOCATION_REQUIRES_COMPENSATION",
                       "Suspenda e reconcilie a publicação externa antes de revogar a arte.",
                       status_code=409)
    author = row.get("requested_by")
    if not author:
        raise ApiError("REVIEW_ORIGIN_UNAVAILABLE", "Autoria não comprovada.", status_code=409)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=campaign.business_unit_id,
                        resource_id=creative_id, created_by=author)
    verdict = can_approve(principal, resource, now=datetime.now(timezone.utc),
                          requester_id=author, already_decided_by=frozenset(), amount=None)
    if not verdict.allowed:
        raise ApiError(verdict.code.value, verdict.reason)
    try:
        result, replay = CreativeImageReviewStore(state).revoke(
            CreativeIdentity(**row["identity"]), actor_id=fixture.user_id,
            expected_sha256=body.expected_sha256,
            expected_generation=body.expected_generation, reason=body.reason)
    except AssetStorageError:
        raise ApiError("REVIEW_CONFLICT", "Revogação incompatível com a imagem.", status_code=409) from None
    return JSONResponse({"creative_id": creative_id, "decision": result["decision"],
                         "replayed": replay}, headers={"Cache-Control": "private, no-store"})
