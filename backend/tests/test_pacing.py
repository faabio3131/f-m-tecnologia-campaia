"""Testes do motor de pacing (B5).

Provam o calculo real de ritmo de gasto -- nao apenas que o modulo importa sem erro.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from campaia_core.pacing import PacingEngine, PacingStatus, PacingWindow


class TestPacingWindow(unittest.TestCase):
    def test_rejects_end_before_start(self) -> None:
        with self.assertRaises(ValueError):
            PacingWindow(
                start_date=date(2026, 9, 10),
                end_date=date(2026, 9, 1),
                total_amount=Decimal("1000"),
            )

    def test_rejects_non_positive_total(self) -> None:
        with self.assertRaises(ValueError):
            PacingWindow(
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 10),
                total_amount=Decimal("0"),
            )

    def test_total_days_is_inclusive(self) -> None:
        window = PacingWindow(
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 10),
            total_amount=Decimal("1000"),
        )
        self.assertEqual(window.total_days, 10)

    def test_elapsed_days_before_start_is_zero(self) -> None:
        window = PacingWindow(
            start_date=date(2026, 9, 10),
            end_date=date(2026, 9, 20),
            total_amount=Decimal("1000"),
        )
        self.assertEqual(window.elapsed_days(as_of=date(2026, 9, 1)), 0)

    def test_elapsed_days_at_end_is_total(self) -> None:
        window = PacingWindow(
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 10),
            total_amount=Decimal("1000"),
        )
        self.assertEqual(window.elapsed_days(as_of=date(2026, 9, 15)), 10)

    def test_expected_spend_is_linear(self) -> None:
        # 10 dias, dia 5 decorrido (inclusive) => metade do periodo => metade do orcamento.
        window = PacingWindow(
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 10),
            total_amount=Decimal("1000"),
        )
        self.assertEqual(window.expected_spend(as_of=date(2026, 9, 5)), Decimal("500.00"))


class TestPacingEngineAssess(unittest.TestCase):
    def _window(self) -> PacingWindow:
        return PacingWindow(
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 10),
            total_amount=Decimal("1000"),
        )

    def test_on_track_within_tolerance(self) -> None:
        engine = PacingEngine(window=self._window(), tolerance_pct=Decimal("15"))
        # Esperado no dia 5 (metade decorrida): 500. Gasto real 520 = +4%, dentro de 15%.
        result = engine.assess(actual_spend=Decimal("520"), as_of=date(2026, 9, 5))
        self.assertEqual(result.status, PacingStatus.ON_TRACK)
        self.assertIsNone(result.suggested_daily_cap)

    def test_overpacing_suggests_lower_daily_cap(self) -> None:
        engine = PacingEngine(window=self._window(), tolerance_pct=Decimal("15"))
        # Esperado no dia 5: 500. Gasto real 800 = +60%, fora da tolerancia.
        result = engine.assess(actual_spend=Decimal("800"), as_of=date(2026, 9, 5))
        self.assertEqual(result.status, PacingStatus.OVERPACING)
        self.assertIsNotNone(result.suggested_daily_cap)
        # Restam 5 dias (6 a 10), 200 de orcamento restante => 40/dia.
        self.assertEqual(result.remaining_days, 5)
        self.assertEqual(result.suggested_daily_cap, Decimal("40.00"))

    def test_underpacing_suggests_higher_daily_cap(self) -> None:
        engine = PacingEngine(window=self._window(), tolerance_pct=Decimal("15"))
        # Esperado no dia 5: 500. Gasto real 200 = -60%, fora da tolerancia.
        result = engine.assess(actual_spend=Decimal("200"), as_of=date(2026, 9, 5))
        self.assertEqual(result.status, PacingStatus.UNDERPACING)
        # Restam 5 dias, 800 de orcamento restante => 160/dia.
        self.assertEqual(result.suggested_daily_cap, Decimal("160.00"))

    def test_exhausted_when_total_already_committed(self) -> None:
        engine = PacingEngine(window=self._window())
        result = engine.assess(actual_spend=Decimal("1000"), as_of=date(2026, 9, 5))
        self.assertEqual(result.status, PacingStatus.EXHAUSTED)
        self.assertEqual(result.suggested_daily_cap, Decimal("0"))

    def test_exhausted_with_no_remaining_days_has_no_suggestion(self) -> None:
        engine = PacingEngine(window=self._window())
        result = engine.assess(actual_spend=Decimal("1000"), as_of=date(2026, 9, 10))
        self.assertEqual(result.status, PacingStatus.EXHAUSTED)
        self.assertIsNone(result.suggested_daily_cap)

    def test_period_ended_has_no_suggestion_even_if_off_track(self) -> None:
        engine = PacingEngine(window=self._window(), tolerance_pct=Decimal("15"))
        result = engine.assess(actual_spend=Decimal("600"), as_of=date(2026, 9, 10))
        self.assertIsNone(result.suggested_daily_cap)
        self.assertEqual(result.remaining_days, 0)

    def test_negative_tolerance_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PacingEngine(window=self._window(), tolerance_pct=Decimal("-1"))

    def test_variance_amount_and_pct_are_signed_correctly(self) -> None:
        engine = PacingEngine(window=self._window())
        result = engine.assess(actual_spend=Decimal("800"), as_of=date(2026, 9, 5))
        self.assertEqual(result.variance_amount, Decimal("300"))
        self.assertEqual(result.variance_pct, Decimal("60"))


if __name__ == "__main__":
    unittest.main()
