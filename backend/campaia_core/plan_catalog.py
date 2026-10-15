"""Catalogo de planos comerciais do CampaIA — dado externo, nunca preco fixo em codigo.

Mesmo principio ja usado no Capability Registry (`infra.py`, ver `docs/08_CAPABILITY_MATRIX.md`
secao 5): "o capability_registry e dado, nao codigo". Aqui vale igual para preco de plano,
franquia de creditos e preco do credito extra (ADR-0020) — o Diretor pediu explicitamente que
alterar valores nunca exija mexer em codigo, porque os planos mudam com frequencia muito maior
que o motor de cobranca que os interpreta (`subscription.py`).

O catalogo mora num arquivo JSON externo, cujo caminho e configuravel por variavel de ambiente
(`CAMPAIA_PLAN_CATALOG_PATH`). Nenhum valor de exemplo deste modulo e usado como padrao real —
sem arquivo configurado, carregar o catalogo falha de forma fechada (fail-closed), nunca inventa
um preco.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

from .credit_ledger import CreditPolicy

from .subscription import (
    CancellationMode,
    DunningPolicy,
    PastDueAccessMode,
    PlanChangeActivation,
    PlanChangeBillingMode,
    PlanChangeKind,
    PlanChangeRule,
    PlanDefinition,
    PlanEntitlements,
    ReactivationBillingMode,
    ReactivationMode,
)

#: Variavel de ambiente que aponta para o arquivo real de planos (dado de configuracao,
#: tipicamente gerido fora do repositorio de codigo — ex.: montado no deploy, ou em um caminho
#: gerenciado pelo Diretor/operacoes). Nunca commitar valores reais de preco no repositorio.
CATALOG_PATH_ENV_VAR = "CAMPAIA_PLAN_CATALOG_PATH"


class PlanCatalogError(ValueError):
    """Catalogo ausente, ilegivel ou com dado invalido. Fail-closed: nunca segue com um
    plano inventado ou parcialmente carregado."""


def _load_raw(path: Path) -> list[dict]:
    if not path.exists():
        raise PlanCatalogError(
            f"Catalogo de planos nao encontrado em {path}. Configure "
            f"{CATALOG_PATH_ENV_VAR} apontando para o arquivo real, gerido fora do codigo."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlanCatalogError(f"Catalogo de planos em {path} nao e um JSON valido: {exc}") from exc

    if not isinstance(data, list):
        raise PlanCatalogError(
            f"Catalogo de planos em {path} deve ser uma lista de planos, recebeu {type(data).__name__}."
        )
    return data


def _parse_entitlements(entry: dict, *, source: Path) -> PlanEntitlements | None:
    raw = entry.get("entitlements")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PlanCatalogError(
            f"entitlements em {source} deve ser objeto JSON, recebeu {type(raw).__name__}."
        )

    def _tuple(name: str) -> tuple[str, ...]:
        value = raw.get(name, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise PlanCatalogError(
                f"entitlements.{name} em {source} deve ser lista de strings."
            )
        return tuple(value)

    try:
        return PlanEntitlements(
            max_users=raw.get("max_users"),
            max_active_campaigns=raw.get("max_active_campaigns"),
            channels=_tuple("channels"),
            ai_capabilities=_tuple("ai_capabilities"),
            resources=_tuple("resources"),
        )
    except ValueError as exc:
        raise PlanCatalogError(
            f"Entitlements invalidos em {source}: {raw!r} — {exc}"
        ) from exc


def _parse_plan_changes(entry: dict, *, source: Path) -> tuple[PlanChangeRule, ...]:
    raw = entry.get("plan_changes", [])
    if not isinstance(raw, list):
        raise PlanCatalogError(f"plan_changes em {source} deve ser lista.")
    rules: list[PlanChangeRule] = []
    try:
        for item in raw:
            if not isinstance(item, dict):
                raise PlanCatalogError(f"plan_changes em {source} deve conter objetos.")
            rules.append(
                PlanChangeRule(
                    target_plan_id=item["target_plan_id"],
                    kind=PlanChangeKind(item["kind"]),
                    activation=PlanChangeActivation(item.get("activation", "SETTLED_PAYMENT")),
                    billing_mode=PlanChangeBillingMode(item["billing_mode"]),
                )
            )
    except (KeyError, ValueError) as exc:
        raise PlanCatalogError(f"plan_changes invalido em {source}: {raw!r} — {exc}") from exc
    return tuple(rules)


def _parse_dunning_policy(entry: dict, *, source: Path) -> DunningPolicy | None:
    raw = entry.get("dunning_policy")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PlanCatalogError(f"dunning_policy em {source} deve ser objeto JSON.")

    offsets = raw.get("reminder_offsets_days")
    if not isinstance(offsets, list):
        raise PlanCatalogError(
            f"dunning_policy.reminder_offsets_days em {source} deve ser lista."
        )

    try:
        return DunningPolicy(
            grace_period_days=raw["grace_period_days"],
            access_mode=PastDueAccessMode(raw["access_mode"]),
            reminder_offsets_days=tuple(offsets),
        )
    except (KeyError, ValueError) as exc:
        raise PlanCatalogError(
            f"dunning_policy invalida em {source}: {raw!r} — {exc}"
        ) from exc


def _parse_credit_policy(entry: dict) -> CreditPolicy | None:
    raw = entry.get("credit_policy")
    if raw is None:
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("action_weights"), dict):
        raise PlanCatalogError("credit_policy exige objeto e action_weights versionados.")
    try:
        return CreditPolicy(
            version=raw["version"],
            action_weights=tuple(sorted(raw["action_weights"].items())),
            trial_credits=raw["trial_credits"],
            trial_max_users=raw["trial_max_users"],
            trial_max_active_campaigns=raw["trial_max_active_campaigns"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanCatalogError("credit_policy incompleta ou inválida.") from exc


def _to_plan_definition(entry: dict, *, source: Path) -> PlanDefinition:
    required = {"plan_id", "name", "monthly_price", "included_credits", "extra_credit_unit_price"}
    missing = required - entry.keys()
    if missing:
        raise PlanCatalogError(
            f"Plano incompleto em {source}: faltam os campos {sorted(missing)} em {entry!r}."
        )
    try:
        entitlements = _parse_entitlements(entry, source=source)
        historical_max_users = entry.get("max_users")
        if (
            historical_max_users is None
            and entitlements is not None
            and entitlements.max_users is not None
        ):
            historical_max_users = entitlements.max_users

        return PlanDefinition(
            plan_id=entry["plan_id"],
            name=entry["name"],
            monthly_price=Decimal(str(entry["monthly_price"])),
            included_credits=Decimal(str(entry["included_credits"])),
            extra_credit_unit_price=Decimal(str(entry["extra_credit_unit_price"])),
            max_users=historical_max_users,
            currency=entry.get("currency", "BRL"),
            trial_days=entry.get("trial_days"),
            entitlements=entitlements,
            plan_changes=_parse_plan_changes(entry, source=source),
            cancellation_mode=(
                CancellationMode(entry["cancellation_mode"])
                if entry.get("cancellation_mode") is not None
                else None
            ),
            reactivation_mode=(
                ReactivationMode(entry["reactivation_mode"])
                if entry.get("reactivation_mode") is not None
                else None
            ),
            reactivation_billing_mode=(
                ReactivationBillingMode(entry["reactivation_billing_mode"])
                if entry.get("reactivation_billing_mode") is not None
                else None
            ),
            dunning_policy=_parse_dunning_policy(entry, source=source),
            credit_policy=_parse_credit_policy(entry),
        )
    except (ValueError, ArithmeticError) as exc:
        raise PlanCatalogError(f"Plano invalido em {source}: {entry!r} — {exc}") from exc


def load_plan_catalog(path: str | os.PathLike | None = None) -> dict[str, PlanDefinition]:
    """Carrega o catalogo de planos vigente de um arquivo JSON externo.

    Resolucao do caminho, em ordem: `path` explicito -> variavel de ambiente
    `CAMPAIA_PLAN_CATALOG_PATH` -> falha fechada (nunca um caminho padrao com precos de
    exemplo). Rejeita `plan_id` duplicado — duplicata e sinal de erro de edicao do arquivo,
    nao algo para resolver silenciosamente escolhendo o primeiro ou o ultimo.
    """
    resolved = path or os.environ.get(CATALOG_PATH_ENV_VAR)
    if not resolved:
        raise PlanCatalogError(
            f"Nenhum catalogo de planos configurado — defina {CATALOG_PATH_ENV_VAR} ou "
            "passe `path` explicitamente. Nao ha catalogo padrao embutido no codigo."
        )

    source = Path(resolved)
    raw_entries = _load_raw(source)

    catalog: dict[str, PlanDefinition] = {}
    for entry in raw_entries:
        plan = _to_plan_definition(entry, source=source)
        if plan.plan_id in catalog:
            raise PlanCatalogError(
                f"plan_id duplicado '{plan.plan_id}' em {source} — corrija o arquivo."
            )
        catalog[plan.plan_id] = plan

    if not catalog:
        raise PlanCatalogError(f"Catalogo de planos em {source} esta vazio.")

    for plan in catalog.values():
        for rule in plan.plan_changes:
            if rule.target_plan_id not in catalog:
                raise PlanCatalogError(
                    f"plan_changes do plano '{plan.plan_id}' aponta para "
                    f"target_plan_id inexistente '{rule.target_plan_id}' em {source}."
                )

    return catalog


def get_plan(plan_id: str, catalog: dict[str, PlanDefinition]) -> PlanDefinition:
    """Busca um plano no catalogo ja carregado. Falha fechada — nunca devolve um plano
    aproximado ou um default silencioso quando o `plan_id` nao existe."""
    try:
        return catalog[plan_id]
    except KeyError as exc:
        disponiveis = ", ".join(sorted(catalog)) or "(catalogo vazio)"
        raise PlanCatalogError(
            f"plan_id '{plan_id}' nao existe no catalogo. Disponiveis: {disponiveis}."
        ) from exc


__all__ = [
    "CATALOG_PATH_ENV_VAR",
    "PlanCatalogError",
    "get_plan",
    "load_plan_catalog",
]
