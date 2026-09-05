"""Testes do motor de otimizacao (B5, F8.1).

Provam que cada regra dispara pela condicao certa, que multiplas regras podem coexistir, e --
o ponto mais importante deste bloco -- que a saida do motor e sempre uma sugestao (nunca uma
execucao) e que a ActionKind de cada recomendacao realmente exige aprovacao humana no teto de
autonomia do MVP, integrando de fato com autonomy.py em vez de apenas simular a integracao.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from campaia_core.autonomy import ActionKind, AutonomySettings, evaluate as evaluate_autonomy
from campaia_core.optimizer import (
    OptimizationTargets,
    PerformanceSnapshot,
    RecommendationCode,
    evaluate_campaign,
)


def _snapshot(
    *, ctr="0.01", cpc="1.00", cpa="10.00", volume=100, currency="BRL"
) -> PerformanceSnapshot:
    return PerformanceSnapshot(
        ctr=Decimal(ctr), cpc=Decimal(cpc), cpa=Decimal(cpa), volume=volume, currency=currency
    )


def _targets(
    *, cpa_target="10.00", volume_target=100, high_ctr="0.02", cpa_mult="2", cpc_ceiling="0"
) -> OptimizationTargets:
    return OptimizationTargets(
        cpa_target=Decimal(cpa_target),
        volume_target=volume_target,
        high_ctr_threshold=Decimal(high_ctr),
        cpa_multiplier_for_pause=Decimal(cpa_mult),
        high_cpc_ceiling=Decimal(cpc_ceiling),
    )


class TestNoRecommendationsWhenOnTarget(unittest.TestCase):
    def test_metrics_exactly_on_target_yield_no_recommendations(self) -> None:
        report = evaluate_campaign("c1", _snapshot(), _targets())
        self.assertFalse(report.has_recommendations)
        self.assertEqual(report.recommendations, ())


class TestIncreaseBudgetHighCtr(unittest.TestCase):
    def test_ctr_above_threshold_triggers_budget_increase(self) -> None:
        snapshot = _snapshot(ctr="0.03")
        report = evaluate_campaign("c1", snapshot, _targets(high_ctr="0.02"))
        codes = [r.code for r in report.recommendations]
        self.assertIn(RecommendationCode.INCREASE_BUDGET_HIGH_CTR, codes)
        rec = next(r for r in report.recommendations if r.code == RecommendationCode.INCREASE_BUDGET_HIGH_CTR)
        self.assertEqual(rec.action, ActionKind.BUDGET_INCREASE)
        self.assertEqual(rec.suggested_change_pct, Decimal("10"))

    def test_ctr_at_or_below_threshold_does_not_trigger(self) -> None:
        report = evaluate_campaign("c1", _snapshot(ctr="0.02"), _targets(high_ctr="0.02"))
        codes = [r.code for r in report.recommendations]
        self.assertNotIn(RecommendationCode.INCREASE_BUDGET_HIGH_CTR, codes)


class TestPauseHighCpa(unittest.TestCase):
    def test_cpa_above_multiplier_triggers_pause(self) -> None:
        snapshot = _snapshot(cpa="25.00")  # 2.5x de um alvo de 10
        report = evaluate_campaign("c1", snapshot, _targets(cpa_target="10.00", cpa_mult="2"))
        codes = [r.code for r in report.recommendations]
        self.assertIn(RecommendationCode.PAUSE_HIGH_CPA, codes)
        rec = next(r for r in report.recommendations if r.code == RecommendationCode.PAUSE_HIGH_CPA)
        self.assertEqual(rec.action, ActionKind.PAUSE)
        self.assertIsNone(rec.suggested_change_pct)

    def test_cpa_exactly_at_multiplier_does_not_trigger(self) -> None:
        snapshot = _snapshot(cpa="20.00")  # exatamente 2x
        report = evaluate_campaign("c1", snapshot, _targets(cpa_target="10.00", cpa_mult="2"))
        codes = [r.code for r in report.recommendations]
        self.assertNotIn(RecommendationCode.PAUSE_HIGH_CPA, codes)


class TestAdjustBidLowVolume(unittest.TestCase):
    def test_volume_below_target_triggers_bid_adjustment(self) -> None:
        snapshot = _snapshot(volume=50)
        report = evaluate_campaign("c1", snapshot, _targets(volume_target=100))
        codes = [r.code for r in report.recommendations]
        self.assertIn(RecommendationCode.ADJUST_BID_LOW_VOLUME, codes)
        rec = next(r for r in report.recommendations if r.code == RecommendationCode.ADJUST_BID_LOW_VOLUME)
        self.assertEqual(rec.action, ActionKind.BID_ADJUSTMENT)
        self.assertEqual(rec.suggested_change_pct, Decimal("5"))

    def test_volume_at_or_above_target_does_not_trigger(self) -> None:
        report = evaluate_campaign("c1", _snapshot(volume=100), _targets(volume_target=100))
        codes = [r.code for r in report.recommendations]
        self.assertNotIn(RecommendationCode.ADJUST_BID_LOW_VOLUME, codes)


class TestExpandAudienceHighCpc(unittest.TestCase):
    def test_cpc_above_ceiling_triggers_targeting_change(self) -> None:
        snapshot = _snapshot(cpc="5.00")
        report = evaluate_campaign("c1", snapshot, _targets(cpc_ceiling="3.00"))
        codes = [r.code for r in report.recommendations]
        self.assertIn(RecommendationCode.EXPAND_AUDIENCE_HIGH_CPC, codes)
        rec = next(
            r for r in report.recommendations if r.code == RecommendationCode.EXPAND_AUDIENCE_HIGH_CPC
        )
        self.assertEqual(rec.action, ActionKind.TARGETING_CHANGE)

    def test_ceiling_zero_disables_this_rule(self) -> None:
        """cpc_ceiling=0 (default) significa 'sem teto configurado' -- a regra fica inerte
        em vez de disparar para qualquer CPC positivo."""
        report = evaluate_campaign("c1", _snapshot(cpc="999.00"), _targets(cpc_ceiling="0"))
        codes = [r.code for r in report.recommendations]
        self.assertNotIn(RecommendationCode.EXPAND_AUDIENCE_HIGH_CPC, codes)


class TestMultipleRulesCanCoexist(unittest.TestCase):
    def test_high_ctr_and_high_cpa_both_fire(self) -> None:
        snapshot = _snapshot(ctr="0.05", cpa="30.00")
        report = evaluate_campaign("c1", snapshot, _targets(high_ctr="0.02", cpa_target="10.00"))
        codes = {r.code for r in report.recommendations}
        self.assertEqual(
            codes,
            {RecommendationCode.INCREASE_BUDGET_HIGH_CTR, RecommendationCode.PAUSE_HIGH_CPA},
        )


class TestRecommendationsNeverSelfAuthorize(unittest.TestCase):
    """O ponto central do B5 nesta sessao: o motor sugere, nunca executa. Prova real: cada
    ActionKind emitido, passado pelo autonomy.py real com o teto de autonomia do MVP, exige
    aprovacao humana -- o optimizer nao decide isso sozinho, nem inventa um caminho de bypass."""

    def test_every_emitted_action_requires_human_at_mvp_autonomy_ceiling(self) -> None:
        snapshot = _snapshot(ctr="0.05", cpa="30.00", volume=10, cpc="5.00")
        report = evaluate_campaign(
            "c1",
            snapshot,
            _targets(high_ctr="0.02", cpa_target="10.00", volume_target=100, cpc_ceiling="3.00"),
        )
        self.assertGreaterEqual(len(report.recommendations), 3)

        mvp_settings = AutonomySettings()  # teto default do MVP: AutonomyLevel.APROVADO
        for rec in report.recommendations:
            decision = evaluate_autonomy(
                rec.action,
                mvp_settings,
                within_preauthorized_limits=True,
                change_pct=rec.suggested_change_pct,
            )
            self.assertTrue(
                decision.requires_human,
                f"{rec.action} nao deveria poder executar sozinho no teto de autonomia do MVP",
            )

    def test_recommendation_is_immutable_data_not_a_callable(self) -> None:
        """Reforco estrutural: Recommendation e um dataclass frozen -- nao existe metodo
        `.apply()` ou `.execute()` neste modulo. A ausencia e o proprio teste."""
        report = evaluate_campaign("c1", _snapshot(ctr="0.05"), _targets(high_ctr="0.02"))
        rec = report.recommendations[0]
        self.assertFalse(hasattr(rec, "apply"))
        self.assertFalse(hasattr(rec, "execute"))
        with self.assertRaises(Exception):
            rec.code = RecommendationCode.PAUSE_HIGH_CPA  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
