"""Explicit consent to invoice future paid anniversaries, never a debit mandate."""
from dataclasses import dataclass
from datetime import datetime
import re


@dataclass(frozen=True, slots=True)
class RenewalInvoiceConsent:
    lifecycle_id: str
    fingerprint: str
    accepted_at: datetime
    actor_id: str
    business_unit_id: str | None

    def __post_init__(self):
        if (not self.lifecycle_id or not self.actor_id or self.accepted_at.tzinfo is None
                or re.fullmatch(r'[a-f0-9]{64}', self.fingerprint) is None):
            raise ValueError('Consentimento recorrente sem contexto válido.')
