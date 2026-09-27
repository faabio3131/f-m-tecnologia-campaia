"""Taxonomia canonica de erros do dominio CAMPAIA.

Codigos de provedor externo NUNCA chegam aqui. Os adaptadores traduzem para esta taxonomia
antes de devolver ao dominio (ver contracts/connector-hub-e-eventos.md, secao 1.2).
"""

from __future__ import annotations


class CampaiaError(Exception):
    """Base de todo erro de dominio. Carrega um codigo canonico."""

    code = "UNKNOWN"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class InvalidStateTransition(CampaiaError):
    code = "INVALID_STATE"


class GuardFailed(CampaiaError):
    """Transicao existe no grafo, mas a condicao obrigatoria nao foi satisfeita."""

    code = "INVALID_STATE"


class ApprovalRequired(CampaiaError):
    code = "APPROVAL_REQUIRED"


class BudgetLimitExceeded(CampaiaError):
    code = "BUDGET_LIMIT"


class PolicyViolation(CampaiaError):
    code = "POLICY_VIOLATION"


class CapabilityUnsupported(CampaiaError):
    code = "CAPABILITY_UNSUPPORTED"


class KillSwitchActive(CampaiaError):
    code = "KILL_SWITCH_ACTIVE"


class TenantIsolationViolation(CampaiaError):
    """Nunca deve acontecer. Se acontecer, e defeito grave e o processo deve falhar alto."""

    code = "PERMISSION_DENIED"
