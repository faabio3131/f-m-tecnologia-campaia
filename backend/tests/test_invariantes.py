"""Testes dos invariantes arquiteturais da CAMPAIA.

Cada teste referencia o invariante do Plano Mestre que ele protege. Um teste que quebra aqui
significa que um invariante do produto foi violado - nao apenas que uma funcao mudou.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from campaia_core.autonomy import (
    ActionKind,
    AutonomyLevel,
    AutonomySettings,
    evaluate as evaluate_autonomy,
)
from campaia_core.budget import BudgetEngine, BudgetLimits
from campaia_core.errors import (
    BudgetLimitExceeded,
    CapabilityUnsupported,
    GuardFailed,
    InvalidStateTransition,
    TenantIsolationViolation,
)
from campaia_core.infra import Capability, CapabilityRegistry, IdempotencyStore
from campaia_core.policy import Outcome, PolicyEngine, PolicyRequest, Severity
from campaia_core.states import (
    Campaign,
    CampaignState,
    ExternalResource,
    SyncStatus,
    TransitionContext,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
T1 = "tenant-1"
T2 = "tenant-2"


def _limits(daily="100", total="1000", pct="20") -> BudgetLimits:
    return BudgetLimits(
        currency="BRL",
        daily_cap=Decimal(daily),
        total_amount=Decimal(total),
        max_change_pct=Decimal(pct),
    )


def _budget(**kw) -> BudgetEngine:
    return BudgetEngine(tenant_id=T1, campaign_id="c1", limits=_limits(**kw))


class TestMaquinaDeEstados(unittest.TestCase):
    """I-12: nunca declarar publicacao sem confirmacao externa."""

    def test_nao_publica_sem_aprovacao_humana(self):
        c = Campaign("c1", T1, CampaignState.APPROVED)
        ctx = TransitionContext(policy_decision_valid=True, human_approval_id=None)
        with self.assertRaises(GuardFailed) as cm:
            c.transition_to(CampaignState.PUBLISHING, ctx)
        self.assertIn("aprovacao humana", str(cm.exception))
        self.assertIs(c.state, CampaignState.APPROVED)

    def test_nao_publica_sem_decisao_de_politica_valida(self):
        c = Campaign("c1", T1, CampaignState.APPROVED)
        ctx = TransitionContext(policy_decision_valid=False, human_approval_id="ap-1")
        with self.assertRaises(GuardFailed):
            c.transition_to(CampaignState.PUBLISHING, ctx)

    def test_publicacao_parcial_nao_vira_ativa(self):
        c = Campaign("c1", T1, CampaignState.PUBLISHING)
        ctx = TransitionContext(
            planned_channels=("GOOGLE_ADS", "META_FACEBOOK"),
            external_resources=(
                ExternalResource("GOOGLE_ADS", "g-123", SyncStatus.CONFIRMED),
                ExternalResource("META_FACEBOOK", None, SyncStatus.PENDING),
            ),
        )
        with self.assertRaises(GuardFailed) as cm:
            c.transition_to(CampaignState.ACTIVE, ctx)
        self.assertEqual(cm.exception.details["missing_channels"], ["META_FACEBOOK"])
        self.assertIs(c.state, CampaignState.PUBLISHING)

    def test_ativa_apenas_com_todos_os_canais_confirmados(self):
        c = Campaign("c1", T1, CampaignState.PUBLISHING)
        ctx = TransitionContext(
            planned_channels=("GOOGLE_ADS", "META_FACEBOOK"),
            external_resources=(
                ExternalResource("GOOGLE_ADS", "g-123", SyncStatus.CONFIRMED),
                ExternalResource("META_FACEBOOK", "m-456", SyncStatus.CONFIRMED),
            ),
        )
        self.assertIs(c.transition_to(CampaignState.ACTIVE, ctx), CampaignState.ACTIVE)

    def test_id_externo_divergente_nao_conta_como_confirmado(self):
        c = Campaign("c1", T1, CampaignState.PUBLISHING)
        ctx = TransitionContext(
            planned_channels=("GOOGLE_ADS",),
            external_resources=(
                ExternalResource("GOOGLE_ADS", "g-123", SyncStatus.DIVERGENT),
            ),
        )
        with self.assertRaises(GuardFailed):
            c.transition_to(CampaignState.ACTIVE, ctx)

    def test_transicao_fora_do_grafo_e_recusada(self):
        c = Campaign("c1", T1, CampaignState.DRAFT)
        with self.assertRaises(InvalidStateTransition):
            c.transition_to(CampaignState.ACTIVE)

    def test_kill_switch_pausa_de_qualquer_estado_publicavel(self):
        for estado in (
            CampaignState.APPROVED,
            CampaignState.PUBLISHING,
            CampaignState.ACTIVE,
            CampaignState.OPTIMIZING,
        ):
            with self.subTest(estado=estado):
                c = Campaign("c1", T1, estado)
                self.assertIs(c.apply_kill_switch(reason="teste"), CampaignState.PAUSED)

    def test_kill_switch_nao_permite_retomar(self):
        c = Campaign("c1", T1, CampaignState.PAUSED)
        with self.assertRaises(GuardFailed):
            c.transition_to(CampaignState.ACTIVE, TransitionContext(kill_switch_active=True))


class TestAutonomia(unittest.TestCase):
    """I-09 e I-11: gatilhos obrigatorios e impossibilidade de auto-promocao."""

    def test_gatilhos_exigem_humano_ate_no_nivel_maximo(self):
        s = AutonomySettings(
            level=AutonomyLevel.OPERACIONAL, max_level_allowed=AutonomyLevel.OPERACIONAL
        )
        for acao in (
            ActionKind.CREATE_CAMPAIGN,
            ActionKind.BUDGET_INCREASE,
            ActionKind.CUSTOMER_MATCH,
            ActionKind.AUTONOMY_CHANGE,
            ActionKind.IRREVERSIBLE,
            ActionKind.UNSPECIFIED_OPERATION,
        ):
            with self.subTest(acao=acao):
                self.assertTrue(evaluate_autonomy(acao, s).requires_human)

    def test_nivel_padrao_e_1_e_exige_aprovacao(self):
        s = AutonomySettings()
        self.assertIs(s.level, AutonomyLevel.APROVADO)
        self.assertTrue(evaluate_autonomy(ActionKind.BID_ADJUSTMENT, s).requires_human)

    def test_nivel_2_executa_baixo_risco_dentro_dos_limites(self):
        s = AutonomySettings(
            level=AutonomyLevel.LIMITADO,
            max_level_allowed=AutonomyLevel.LIMITADO,
            max_budget_change_pct=Decimal("10"),
        )
        d = evaluate_autonomy(
            ActionKind.BID_ADJUSTMENT,
            s,
            within_preauthorized_limits=True,
            change_pct=Decimal("5"),
        )
        self.assertFalse(d.requires_human)

    def test_variacao_acima_do_limite_volta_para_humano(self):
        s = AutonomySettings(
            level=AutonomyLevel.LIMITADO,
            max_level_allowed=AutonomyLevel.LIMITADO,
            max_budget_change_pct=Decimal("10"),
        )
        d = evaluate_autonomy(
            ActionKind.BID_ADJUSTMENT,
            s,
            within_preauthorized_limits=True,
            change_pct=Decimal("25"),
        )
        self.assertTrue(d.requires_human)

    def test_nao_e_possivel_configurar_acima_do_teto_contratado(self):
        """ADR-0013: configuravel significa ajustavel dentro de limites, nao acima."""
        with self.assertRaises(ValueError):
            AutonomySettings(
                level=AutonomyLevel.OPERACIONAL, max_level_allowed=AutonomyLevel.APROVADO
            )

    def test_publico_sensivel_pede_aprovacao_dupla(self):
        s = AutonomySettings()
        d = evaluate_autonomy(ActionKind.SENSITIVE_AUDIENCE, s, high_risk=True)
        self.assertTrue(d.requires_dual_approval)


class TestOrcamento(unittest.TestCase):
    """I-06 e T-06: gasto nao autorizado e o pior defeito possivel."""

    def test_reservas_concorrentes_nao_estouram_o_limite(self):
        b = _budget(daily="100", total="1000")
        b.reserve("60", command_id="cmd-a")
        with self.assertRaises(BudgetLimitExceeded):
            b.reserve("60", command_id="cmd-b")

    def test_reserva_e_idempotente_por_comando(self):
        b = _budget()
        r1 = b.reserve("50", command_id="cmd-a")
        r2 = b.reserve("50", command_id="cmd-a")
        self.assertEqual(r1.reservation_id, r2.reservation_id)
        self.assertEqual(b.reserved, Decimal("50"))

    def test_liberar_reserva_devolve_a_verba(self):
        b = _budget()
        r = b.reserve("80", command_id="cmd-a")
        b.release(r.reservation_id)
        self.assertEqual(b.reserved, Decimal("0"))
        self.assertEqual(b.available_today, Decimal("100"))

    def test_confirmar_converte_reserva_em_gasto(self):
        b = _budget()
        r = b.reserve("80", command_id="cmd-a")
        b.confirm(r.reservation_id, "75")
        self.assertEqual(b.spent_total, Decimal("75"))
        self.assertEqual(b.reserved, Decimal("0"))

    def test_confirmar_duas_vezes_nao_duplica_gasto(self):
        b = _budget()
        r = b.reserve("80", command_id="cmd-a")
        b.confirm(r.reservation_id, "75")
        b.confirm(r.reservation_id, "75")
        self.assertEqual(b.spent_total, Decimal("75"))

    def test_alteracao_acima_da_variacao_e_recusada_nao_ajustada(self):
        b = _budget(daily="100", pct="20")
        ok, pct, motivo = b.validate_change("150")
        self.assertFalse(ok)
        self.assertEqual(pct, Decimal("50"))
        self.assertIn("excede", motivo)
        self.assertEqual(b.limits.daily_cap, Decimal("100"))  # nada mudou

    def test_hard_stop_ao_atingir_o_limite(self):
        b = _budget(daily="100", total="1000")
        r = b.reserve("100", command_id="cmd-a")
        b.confirm(r.reservation_id, "100")
        self.assertTrue(b.should_stop())

    def test_aritmetica_financeira_nao_usa_float(self):
        b = _budget(daily="100", total="1000")
        r = b.reserve("0.1", command_id="a")
        b.confirm(r.reservation_id, "0.1")
        r = b.reserve("0.2", command_id="b")
        b.confirm(r.reservation_id, "0.2")
        self.assertEqual(b.spent_total, Decimal("0.3"))  # com float daria 0.30000000000000004


class TestPolicyEngine(unittest.TestCase):
    """A unica fonte de autorizacao para efeito externo."""

    def _req(self, **kw) -> PolicyRequest:
        base = dict(
            tenant_id=T1,
            campaign_id="c1",
            plan_version=1,
            action=ActionKind.CREATE_CAMPAIGN,
            autonomy=AutonomySettings(),
            budget=_budget(),
            channel_support={"GOOGLE_ADS": True},
        )
        base.update(kw)
        return PolicyRequest(**base)

    def test_decisao_expira(self):
        d = PolicyEngine(ttl=timedelta(minutes=30)).evaluate(self._req(), now=NOW)
        self.assertTrue(
            d.is_valid_for(now=NOW, campaign_id="c1", plan_version=1, tenant_id=T1)
        )
        self.assertFalse(
            d.is_valid_for(
                now=NOW + timedelta(minutes=31),
                campaign_id="c1",
                plan_version=1,
                tenant_id=T1,
            )
        )

    def test_decisao_nao_serve_para_outra_versao_do_plano(self):
        """Aprovar a versao 1 nao autoriza publicar a versao 2."""
        d = PolicyEngine().evaluate(self._req(plan_version=1), now=NOW)
        self.assertFalse(
            d.is_valid_for(now=NOW, campaign_id="c1", plan_version=2, tenant_id=T1)
        )

    def test_decisao_nao_atravessa_tenant(self):
        d = PolicyEngine().evaluate(self._req(), now=NOW)
        self.assertFalse(
            d.is_valid_for(now=NOW, campaign_id="c1", plan_version=1, tenant_id=T2)
        )

    def test_canal_sem_capacidade_bloqueia_e_nao_emite_autorizacao(self):
        d = PolicyEngine().evaluate(
            self._req(channel_support={"GOOGLE_ADS": True, "WHATSAPP": False}), now=NOW
        )
        self.assertIs(d.outcome, Outcome.BLOCKED)
        self.assertIsNone(d.policy_decision_id)

    def test_termo_vetado_pelo_cliente_bloqueia(self):
        d = PolicyEngine().evaluate(
            self._req(
                brand_restrictions=("garantia de resultado",),
                plan_text="Compre hoje com GARANTIA DE RESULTADO imediata",
            ),
            now=NOW,
        )
        self.assertIs(d.outcome, Outcome.BLOCKED)
        self.assertTrue(
            any(f.code == "BRAND_RESTRICTION" for f in d.findings)
        )

    def test_lista_de_clientes_sem_base_legal_bloqueia(self):
        d = PolicyEngine().evaluate(
            self._req(uses_customer_list=True, has_legal_basis=False), now=NOW
        )
        self.assertIs(d.outcome, Outcome.BLOCKED)
        self.assertTrue(any(f.code == "LEGAL_BASIS_MISSING" for f in d.findings))

    def test_kill_switch_bloqueia_qualquer_autorizacao(self):
        d = PolicyEngine().evaluate(self._req(kill_switch_active=True), now=NOW)
        self.assertIs(d.outcome, Outcome.BLOCKED)

    def test_verba_acima_do_disponivel_bloqueia(self):
        d = PolicyEngine().evaluate(
            self._req(requested_amount=Decimal("5000")), now=NOW
        )
        self.assertIs(d.outcome, Outcome.BLOCKED)
        self.assertTrue(any(f.code == "BUDGET_LIMIT" for f in d.findings))

    def test_publico_sensivel_alerta_mas_nao_bloqueia(self):
        d = PolicyEngine().evaluate(self._req(sensitive_audience=True), now=NOW)
        self.assertIs(d.outcome, Outcome.APPROVABLE)
        self.assertTrue(d.requires_human_approval)
        self.assertTrue(
            any(f.severity is Severity.WARNING for f in d.findings)
        )


class TestIdempotenciaEIsolamento(unittest.TestCase):
    """I-04 e I-06."""

    def test_replay_nao_executa_a_operacao_de_novo(self):
        store = IdempotencyStore()
        chamadas = []

        def op():
            chamadas.append(1)
            return "publicado"

        r1, replay1 = store.execute(T1, "key-1", op)
        r2, replay2 = store.execute(T1, "key-1", op)

        self.assertEqual((r1, r2), ("publicado", "publicado"))
        self.assertFalse(replay1)
        self.assertTrue(replay2)
        self.assertEqual(len(chamadas), 1)  # efeito externo aconteceu UMA vez

    def test_mesma_chave_em_tenants_diferentes_nao_colide(self):
        store = IdempotencyStore()
        store.execute(T1, "key-1", lambda: "resultado-do-tenant-1")
        resultado, replay = store.execute(T2, "key-1", lambda: "resultado-do-tenant-2")
        self.assertEqual(resultado, "resultado-do-tenant-2")
        self.assertFalse(replay)

    def test_operacao_sem_tenant_e_recusada(self):
        store = IdempotencyStore()
        with self.assertRaises(TenantIsolationViolation):
            store.execute("", "key-1", lambda: "nao deveria executar")


class TestCapabilityRegistry(unittest.TestCase):
    """I-08: expor somente capacidade comprovada."""

    def _registry(self, verificada_em: datetime, supported=True) -> CapabilityRegistry:
        reg = CapabilityRegistry(max_age=timedelta(days=30))
        reg.register(
            Capability(
                provider="GOOGLE_ADS",
                capability_key="create_campaign",
                country="BR",
                api_version="v25",
                supported=supported,
                verified_at=verificada_em,
                evidence_url="https://developers.google.com/google-ads/api",
            )
        )
        return reg

    def test_capacidade_verificada_recentemente_e_oferecida(self):
        reg = self._registry(NOW - timedelta(days=5))
        self.assertTrue(
            reg.is_supported(
                "GOOGLE_ADS", "create_campaign", country="BR", api_version="v25", now=NOW
            )
        )

    def test_capacidade_vencida_e_tratada_como_indisponivel(self):
        reg = self._registry(NOW - timedelta(days=60))
        self.assertFalse(
            reg.is_supported(
                "GOOGLE_ADS", "create_campaign", country="BR", api_version="v25", now=NOW
            )
        )

    def test_capacidade_nao_registrada_nunca_e_assumida(self):
        reg = self._registry(NOW)
        with self.assertRaises(CapabilityUnsupported):
            reg.require(
                "META", "create_campaign", country="BR", api_version="v26", now=NOW
            )

    def test_outra_versao_de_api_nao_herda_capacidade(self):
        reg = self._registry(NOW)
        self.assertFalse(
            reg.is_supported(
                "GOOGLE_ADS", "create_campaign", country="BR", api_version="v26", now=NOW
            )
        )

    def test_outro_pais_nao_herda_capacidade(self):
        reg = self._registry(NOW)
        self.assertFalse(
            reg.is_supported(
                "GOOGLE_ADS", "create_campaign", country="PT", api_version="v25", now=NOW
            )
        )


class TestFluxoCompleto(unittest.TestCase):
    """Do plano ate ACTIVE, passando por politica, verba, aprovacao e reconciliacao."""

    def test_caminho_feliz_ponta_a_ponta(self):
        budget = _budget(daily="100", total="1000")
        engine = PolicyEngine()
        store = IdempotencyStore()
        c = Campaign("c1", T1, CampaignState.DRAFT)

        for alvo in (
            CampaignState.STRATEGY_READY,
            CampaignState.ASSETS_READY,
            CampaignState.VALIDATED,
            CampaignState.AWAITING_APPROVAL,
            CampaignState.APPROVED,
        ):
            c.transition_to(alvo)

        decisao = engine.evaluate(
            PolicyRequest(
                tenant_id=T1,
                campaign_id="c1",
                plan_version=1,
                action=ActionKind.CREATE_CAMPAIGN,
                autonomy=AutonomySettings(),
                budget=budget,
                requested_amount=Decimal("80"),
                channel_support={"GOOGLE_ADS": True},
            ),
            now=NOW,
        )
        self.assertIs(decisao.outcome, Outcome.APPROVABLE)
        self.assertTrue(decisao.requires_human_approval)

        reserva = budget.reserve("80", command_id="cmd-publish-1")

        valida = decisao.is_valid_for(
            now=NOW, campaign_id="c1", plan_version=1, tenant_id=T1
        )
        c.transition_to(
            CampaignState.PUBLISHING,
            TransitionContext(policy_decision_valid=valida, human_approval_id="ap-1"),
        )

        _, replay = store.execute(T1, "cmd-publish-1", lambda: "g-123")
        self.assertFalse(replay)
        _, replay = store.execute(T1, "cmd-publish-1", lambda: "NAO DEVE EXECUTAR")
        self.assertTrue(replay)

        c.transition_to(
            CampaignState.ACTIVE,
            TransitionContext(
                planned_channels=("GOOGLE_ADS",),
                external_resources=(
                    ExternalResource("GOOGLE_ADS", "g-123", SyncStatus.CONFIRMED),
                ),
            ),
        )
        budget.confirm(reserva.reservation_id, "78.50")

        self.assertIs(c.state, CampaignState.ACTIVE)
        self.assertEqual(budget.spent_total, Decimal("78.50"))
        self.assertEqual(budget.reserved, Decimal("0"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
