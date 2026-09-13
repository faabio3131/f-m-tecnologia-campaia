"""Governed CampaIA -> FM Fiscal handoff boundary.

This module deliberately accepts only an explicit CampaIA *own billing* fact that
has already been settled by an authoritative billing/payment domain. Campaign
budget, media spend and ad-platform transactions are not accepted as revenue.

CampaIA currently has no authoritative own-billing/payment domain wired to this
boundary, so this builder is a safe adapter seam rather than a production event
source. FM Fiscal remains authoritative for fiscal binding, jurisdiction,
provider, tax rules, readiness and issuance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class CampaiaBillingKind(str, Enum):
    SERVICE = "service-billing"
    SAAS = "saas-billing"


@dataclass(frozen=True, slots=True)
class SettledOwnBillingFact:
    billing_id: str
    tenant_id: str
    customer_ref: str
    kind: CampaiaBillingKind
    amount: Decimal
    currency: str
    competence: str
    settled_at: datetime

    def validate(self) -> None:
        if not self.billing_id.strip():
            raise ValueError("billing_id is required")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.customer_ref.strip():
            raise ValueError("customer_ref is required")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.currency != "BRL":
            raise ValueError("only BRL own billing is supported")
        if not self.competence.strip():
            raise ValueError("competence is required")
        if self.settled_at.tzinfo is None:
            raise ValueError("settled_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CampaiaFiscalHandoff:
    host_namespace: str
    pack_id: str
    use_case_id: str
    operation_kind: str
    document_kind: str
    state: str
    billing_id: str
    tenant_id: str
    customer_ref: str
    amount: Decimal
    currency: str
    competence: str
    settled_at: datetime
    idempotency_key: str
    capabilities_path: str
    issuance_path: str
    fiscal_scope_binding_required: bool
    readiness_required_before_issuance: bool


def build_campaia_fiscal_handoff(fact: SettledOwnBillingFact) -> CampaiaFiscalHandoff:
    """Build a fail-closed fiscal handoff from an explicit settled own-billing fact."""

    fact.validate()
    operation_kind = "service" if fact.kind is CampaiaBillingKind.SERVICE else "saas_billing"
    return CampaiaFiscalHandoff(
        host_namespace="fm.campaia",
        pack_id="campaia",
        use_case_id=fact.kind.value,
        operation_kind=operation_kind,
        document_kind="nfse",
        state="PENDING_CAPABILITY",
        billing_id=fact.billing_id,
        tenant_id=fact.tenant_id,
        customer_ref=fact.customer_ref,
        amount=fact.amount,
        currency=fact.currency,
        competence=fact.competence,
        settled_at=fact.settled_at,
        idempotency_key=f"campaia:billing:{fact.billing_id}:nfse:v1",
        capabilities_path="/v1/capabilities/query",
        issuance_path="/v1/issuances",
        fiscal_scope_binding_required=True,
        readiness_required_before_issuance=True,
    )


__all__ = [
    "CampaiaBillingKind",
    "CampaiaFiscalHandoff",
    "SettledOwnBillingFact",
    "build_campaia_fiscal_handoff",
]
