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

from .subscription import PlanDefinition

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


def _to_plan_definition(entry: dict, *, source: Path) -> PlanDefinition:
    required = {"plan_id", "name", "monthly_price", "included_credits", "extra_credit_unit_price"}
    missing = required - entry.keys()
    if missing:
        raise PlanCatalogError(
            f"Plano incompleto em {source}: faltam os campos {sorted(missing)} em {entry!r}."
        )
    try:
        return PlanDefinition(
            plan_id=entry["plan_id"],
            name=entry["name"],
            monthly_price=Decimal(str(entry["monthly_price"])),
            included_credits=Decimal(str(entry["included_credits"])),
            extra_credit_unit_price=Decimal(str(entry["extra_credit_unit_price"])),
            currency=entry.get("currency", "BRL"),
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
