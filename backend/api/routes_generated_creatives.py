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
