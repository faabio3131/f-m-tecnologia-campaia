"""Immutable delivered text/audience proposals, not provider publication authority."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from campaia_core.states import CampaignState
from campaia_core.agents import AGENTS
from .errors import ApiError

EDITABLE_STATES = frozenset({CampaignState.DRAFT, CampaignState.STRATEGY_READY,
    CampaignState.ASSETS_READY, CampaignState.VALIDATED, CampaignState.AWAITING_APPROVAL})


def source_digest(record):
    return sha256(json.dumps([dict(record.brief), dict(record.plan or {})],
                             sort_keys=True, default=str).encode()).hexdigest()


def require_editable(record, expected):
    if record.plan is None or record.plan_version != expected:
        raise ApiError("AI_INPUT_CHANGED", "A estratégia mudou. Atualize e confira antes de gerar.", status_code=409)
    if record.campaign.state not in EDITABLE_STATES:
        raise ApiError("CAMPAIGN_NOT_EDITABLE", "Esta campanha já foi aprovada ou está em operação. Use um novo briefing para novos materiais.", status_code=409)


def invalidate_review(record):
    # Existing state graph already permits returning unapproved work to DRAFT.
    if record.campaign.state not in (CampaignState.DRAFT, CampaignState.STRATEGY_READY):
        record.campaign.transition_to(CampaignState.DRAFT, reason="creative:changed")
    if record.campaign.state is CampaignState.DRAFT:
        record.campaign.transition_to(CampaignState.STRATEGY_READY, reason="creative:review-required")
    record.plan_version += 1
    record.last_policy_decision = None
    record.approval_id = None


def serialize_proposal(row, *, current_source):
    result = {
        "id": row["id"], "campaign_id": row["campaign_id"], "kind": row["kind"],
        "version": row["version"], "plan_version": row["plan_version"],
        "current": row["source_digest"] == current_source,
        "output": deepcopy(row["output"]), "request_summary": deepcopy(row["request_summary"]),
        "provider": row["provider"], "model": row["model"], "prompt_version": row["prompt_version"],
        "created_at": row["created_at"].isoformat(),
    }
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        raise ApiError("AI_OUTPUT_INVALID", "A proposta não pode ser entregue em formato válido.", status_code=422) from None
    return result


class CreativeProposalRepository:
    def __init__(self, table):
        self.table = table

    def _rows(self, tenant, campaign, kind=None):
        return [row for _id, _tenant, row in self.table.rows_for_tenant(tenant)
                if row["campaign_id"] == campaign and (kind is None or row["kind"] == kind)]

    def latest(self, tenant, campaign, kind, digest):
        return next(iter(sorted((row for row in self._rows(tenant, campaign, kind)
                    if row["source_digest"] == digest), key=lambda row: row["version"], reverse=True)), None)

    def append(self, fixture, record, kind, output, summary, proposal):
        if not self.table._database.in_transaction:
            raise RuntimeError("A proposal delivery requires an active F3 transaction.")
        previous = self._rows(fixture.tenant_id, record.campaign_id, kind)
        row = {
            "id": str(uuid4()), "campaign_id": record.campaign_id, "kind": kind,
            "version": max((item["version"] for item in previous), default=0) + 1,
            "plan_version": record.plan_version, "source_digest": source_digest(record),
            "output": deepcopy(output), "request_summary": deepcopy(summary),
            "provider": proposal.provenance.provider, "model": proposal.provenance.model,
            "prompt_version": (getattr(proposal.provenance, "prompt_version", None) or AGENTS[kind].prompt_version),
            "created_by": fixture.user_id, "business_unit_id": fixture.business_unit_id,
            "created_at": datetime.now(timezone.utc),
        }
        serialize_proposal(row, current_source=row["source_digest"])  # Verify the complete public envelope before any write/settlement.
        if self.table.get(row["id"]) is not None:
            raise ApiError("PROPOSAL_WRITE_CONFLICT", "A entrega precisa de conferência.", status_code=409)
        self.table.put(row["id"], fixture.tenant_id, row)
        return row

    def page(self, tenant, record, kind, cursor=None):
        rows = sorted(self._rows(tenant, record.campaign_id, kind), key=lambda row: row["version"], reverse=True)
        if cursor is not None:
            before = next((row["version"] for row in rows if row["id"] == cursor), None)
            if before is None:
                raise ApiError("VALIDATION_FAILED", "Cursor de propostas inválido.", status_code=422)
            rows = [row for row in rows if row["version"] < before]
        selected = rows[:50]
        digest = source_digest(record)
        return {"items": [serialize_proposal(row, current_source=digest) for row in selected],
                "next_cursor": selected[-1]["id"] if len(rows) > 50 else None}


def current_proposal_text(state, record):
    if state.creative_proposals is None:
        return "", False
    digest = source_digest(record)
    copy = state.creative_proposals.latest(record.tenant_id, record.campaign_id, "copy", digest)
    audience = state.creative_proposals.latest(record.tenant_id, record.campaign_id, "audience", digest)
    text = json.dumps({"copy": copy["output"] if copy else None,
                       "audience": audience["output"] if audience else None}, ensure_ascii=False)
    sensitive = bool(audience and (audience["output"]["sensivel"]
                     or audience["request_summary"].get("sensitive_declared")))
    return text, sensitive
