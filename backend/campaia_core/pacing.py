"""Motor de pacing: ritmo de gasto de uma campanha ao longo do tempo.

Escopo desta sessao, confirmado pelo Diretor (04/09/2026): este modulo e o `optimizer.py`
formam o B5 ("motor de otimizacao e pacing"), mas SOMENTE calculam e sugerem. Nenhum dos
dois executa uma mudanca sozinho. Toda recomendacao vira uma `PolicyRequest` (policy.py),
que usa o `autonomy.py` ja existente para decidir se exige aprovacao humana -- e o teto de
autonomia do MVP (`AutonomyLevel.APROVADO`) faz com que, hoje, isso seja sempre "sim".

Por que essa restricao: `docs/product/FUNCTIONAL_REQUIREMENTS.md` (Fase 0, 26/08/2026) marca
F8.2 ("executar otimizacoes automaticas") como fora do escopo do MVP, reservado para o Nivel
3 de autonomia (Fase 3 de produto, distinta da Fase 3 tecnica deste painel). F8.1 ("sugerir
otimizacoes dentro de limites") esta dentro do escopo. Este modulo implementa apenas F8.1.

Problema real que o pacing resolve: uma campanha com orcamento total X e prazo de N dias pode
gastar tudo nos 2 primeiros dias (esgotando o teto diario do budget.py sem ritmo) ou nao gastar
o suficiente e terminar o periodo com verba nao utilizada. O pacing calcula, a cada momento, se
o gasto observado esta adiantado, atrasado ou dentro da faixa esperada em relacao ao tempo
decorrido do periodo contratado -- e sugere (nunca executa) um novo teto diario para corrigir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


def _d(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class PacingStatus(StrEnum):
    ON_TRACK = "ON_TRACK"
    UNDERPACING = "UNDERPACING"  # gasto abaixo do esperado para o tempo decorrido
    OVERPACING = "OVERPACING"  # gasto acima do esperado para o tempo decorrido
    EXHAUSTED = "EXHAUSTED"  # verba total ja comprometida antes do fim do periodo


@dataclass(frozen=True)
class PacingWindow:
    """O periodo contratado da campanha. Datas sao inclusivas."""

    start_date: date
    end_date: date
    total_amount: Decimal

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError("Data final nao pode ser anterior a data inicial.")
        if self.total_amount <= 0:
            raise ValueError("Orcamento total do periodo deve ser positivo.")

    @property
    def total_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def elapsed_days(self, *, as_of: date) -> int:
        """Dias decorridos, contando o dia atual como parcialmente decorrido.

        Antes do inicio: 0. No ou apos o fim: total_days (periodo inteiro decorrido).
        """
        if as_of < self.start_date:
            return 0
        if as_of >= self.end_date:
            return self.total_days
        return (as_of - self.start_date).days + 1

    def expected_spend(self, *, as_of: date) -> Decimal:
        """Gasto linear esperado ate `as_of`, proporcional ao tempo decorrido.

        Linear e a linha de base mais simples e auditavel. Curvas de pacing nao lineares
        (ex.: acelerar no fim de semana) sao uma extensao futura, fora deste escopo.
        """
        fraction = Decimal(self.elapsed_days(as_of=as_of)) / Decimal(self.total_days)
        return (self.total_amount * fraction).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class PacingAssessment:
    status: PacingStatus
    #: Positivo = gastando mais rapido que o esperado; negativo = mais devagar.
    variance_amount: Decimal
    variance_pct: Decimal
    expected_spend: Decimal
    actual_spend: Decimal
    #: Novo teto diario sugerido para os dias restantes, para corrigir a trajetoria.
    #: None quando nao ha dias restantes (periodo encerrado) ou correcao nao se aplica.
    suggested_daily_cap: Decimal | None
    remaining_days: int
    explanation: str


#: Fora desta faixa (em % do gasto esperado), o pacing deixa de ser considerado ON_TRACK.
#: Simetrico e configuravel por instancia via `PacingEngine`, nao hardcoded no calculo.
DEFAULT_TOLERANCE_PCT = Decimal("15")


@dataclass
class PacingEngine:
    """Calcula o estado de ritmo de UMA campanha. Sem estado proprio: le do BudgetEngine."""

    window: PacingWindow
    tolerance_pct: Decimal = DEFAULT_TOLERANCE_PCT

    def __post_init__(self) -> None:
        if self.tolerance_pct < 0:
            raise ValueError("Tolerancia de pacing nao pode ser negativa.")

    def assess(
        self, *, actual_spend: Decimal | int | str, as_of: date
    ) -> PacingAssessment:
        """Compara gasto real com o esperado e sugere (nao aplica) uma correcao de teto diario.

        `actual_spend` deve vir do `BudgetEngine.spent_total` (gasto confirmado) da mesma
        campanha -- este modulo nao acessa o BudgetEngine diretamente para nao acoplar as
        duas instancias; quem chama decide qual numero de gasto e a fonte de verdade.
        """
        actual_spend = _d(actual_spend)
        expected = self.window.expected_spend(as_of=as_of)
        remaining_days = max(0, self.window.total_days - self.window.elapsed_days(as_of=as_of))

        variance_amount = actual_spend - expected
        variance_pct = (
            (variance_amount / expected * Decimal("100"))
            if expected > 0
            else Decimal("0")
        )

        if actual_spend >= self.window.total_amount:
            status = PacingStatus.EXHAUSTED
            suggested_daily_cap = Decimal("0") if remaining_days > 0 else None
            explanation = (
                "Orcamento total do periodo ja foi integralmente comprometido. "
                "Nenhum gasto adicional deveria ocorrer nos dias restantes."
            )
        elif remaining_days == 0:
            status = PacingStatus.ON_TRACK if variance_pct.copy_abs() <= self.tolerance_pct else (
                PacingStatus.OVERPACING if variance_amount > 0 else PacingStatus.UNDERPACING
            )
            suggested_daily_cap = None
            explanation = "Periodo encerrado: nao ha dias restantes para ajustar o teto diario."
        elif variance_pct > self.tolerance_pct:
            status = PacingStatus.OVERPACING
            remaining_budget = self.window.total_amount - actual_spend
            suggested_daily_cap = (remaining_budget / remaining_days).quantize(Decimal("0.01"))
            explanation = (
                f"Gasto {variance_pct:.1f}% acima do esperado para o tempo decorrido. "
                f"Sugestao: reduzir o teto diario para o restante do periodo, para nao "
                f"esgotar o orcamento total antes do fim."
            )
        elif variance_pct < -self.tolerance_pct:
            status = PacingStatus.UNDERPACING
            remaining_budget = self.window.total_amount - actual_spend
            suggested_daily_cap = (remaining_budget / remaining_days).quantize(Decimal("0.01"))
            explanation = (
                f"Gasto {variance_pct.copy_abs():.1f}% abaixo do esperado para o tempo "
                f"decorrido. Sugestao: aumentar o teto diario para o restante do periodo, "
                f"para nao terminar com verba nao utilizada."
            )
        else:
            status = PacingStatus.ON_TRACK
            suggested_daily_cap = None
            explanation = (
                f"Gasto dentro da tolerancia de {self.tolerance_pct}% em relacao ao esperado. "
                f"Nenhum ajuste de teto diario sugerido."
            )

        return PacingAssessment(
            status=status,
            variance_amount=variance_amount,
            variance_pct=variance_pct,
            expected_spend=expected,
            actual_spend=actual_spend,
            suggested_daily_cap=suggested_daily_cap,
            remaining_days=remaining_days,
            explanation=explanation,
        )
