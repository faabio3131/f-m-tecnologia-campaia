"""Testes da Saga de publicacao multicanal e do Provider Simulator."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from campaia_core.autonomy import ActionKind, AutonomySettings
from campaia_core.budget import BudgetEngine, BudgetLimits
from campaia_core.connectors import (
    ConnectorError,
    ConnectorErrorCode,
    PublishCommand,
    SecretRef,
)
from campaia_core.errors import GuardFailed
from campaia_core.infra import IdempotencyStore
from campaia_core.policy import PolicyEngine, PolicyRequest
from campaia_core.saga import (
    CompensationPolicy,
    PublicationSaga,
    StepStatus,
)
from campaia_core.simulator import ProviderSimulator
from campaia_core.states import Campaign, CampaignState

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
T1 = "tenant-1"
CANAIS = ("GOOGLE_ADS", "META_FACEBOOK")


def _budget(daily="1000", total="10000") -> BudgetEngine:
    return BudgetEngine(
        tenant_id=T1,
        campaign_id="c1",
        limits=BudgetLimits(
            currency="BRL", daily_cap=Decimal(daily), total_amount=Decimal(total)
        ),
    )


def _decision(budget: BudgetEngine, plan_version: int = 1):
    return PolicyEngine().evaluate(
        PolicyRequest(
            tenant_id=T1,
            campaign_id="c1",
            plan_version=plan_version,
            action=ActionKind.CREATE_CAMPAIGN,
            autonomy=AutonomySettings(),
            budget=budget,
            channel_support={c: True for c in CANAIS},
        ),
        now=NOW,
    )


def _campanha_aprovada() -> Campaign:
    c = Campaign("c1", T1, CampaignState.DRAFT)
    for alvo in (
        CampaignState.STRATEGY_READY,
        CampaignState.ASSETS_READY,
        CampaignState.VALIDATED,
        CampaignState.AWAITING_APPROVAL,
        CampaignState.APPROVED,
    ):
        c.transition_to(alvo)
    return c


def _saga(sim: ProviderSimulator, budget: BudgetEngine, policy: CompensationPolicy):
    return PublicationSaga(
        tenant_id=T1,
        connector=sim,
        budget=budget,
        idempotency=IdempotencyStore(),
        compensation_policy=policy,
    )


def _run(saga: PublicationSaga, campanha: Campaign, budget: BudgetEngine, **kw):
    params = dict(
        channels=CANAIS,
        decision=_decision(budget),
        approval_id="ap-1",
        plan_version=1,
        now=NOW,
        external_account_id="acct-1",
        command_id="cmd-1",
        budget_per_channel=Decimal("100"),
    )
    params.update(kw)
    return saga.run(campanha, **params)


class TestSecretRef(unittest.TestCase):
    """I-03: segredo nao vaza por log, excecao ou formatacao."""

    def test_segredo_nunca_aparece_em_repr_str_ou_format(self):
        ref = SecretRef(handle="vault://google/acct-1")
        for texto in (repr(ref), str(ref), f"{ref}", "{}".format(ref)):
            self.assertNotIn("vault://", texto)
            self.assertIn("REDACTED", texto)

    def test_handle_e_referencia_nao_e_o_segredo(self):
        sim = ProviderSimulator()
        ref = sim.resolve_secret("acct-1")
        self.assertTrue(ref.handle.startswith("vault://"))
        self.assertNotIn("vault://", repr(ref))


class TestAutorizacaoNoConector(unittest.TestCase):
    """O conector nao executa por confianca no chamador."""

    def _cmd(self, **kw) -> PublishCommand:
        base = dict(
            tenant_id=T1,
            campaign_id="c1",
            channel="GOOGLE_ADS",
            external_account_id="acct-1",
            idempotency_key="k1",
            policy_decision_id="pd-1",
            plan_version=1,
            payload={"a": 1},
        )
        base.update(kw)
        return PublishCommand(**base)

    def test_sem_policy_decision_id_recusa(self):
        with self.assertRaises(ConnectorError) as cm:
            ProviderSimulator().publish(self._cmd(policy_decision_id=""))
        self.assertIs(cm.exception.connector_code, ConnectorErrorCode.PERMISSION_DENIED)

    def test_sem_idempotency_key_recusa(self):
        with self.assertRaises(ConnectorError):
            ProviderSimulator().publish(self._cmd(idempotency_key=""))

    def test_sem_tenant_recusa(self):
        with self.assertRaises(ConnectorError):
            ProviderSimulator().publish(self._cmd(tenant_id=""))

    def test_validate_draft_nao_produz_efeito_externo(self):
        sim = ProviderSimulator()
        sim.validate_draft(self._cmd())
        self.assertEqual(sim.count("publish"), 0)

    def test_capacidade_ausente_devolve_fluxo_assistido_e_nao_simula_sucesso(self):
        sim = ProviderSimulator(unsupported_channels=frozenset({"WHATSAPP"}))
        with self.assertRaises(ConnectorError) as cm:
            sim.publish(self._cmd(channel="WHATSAPP"))
        self.assertIs(
            cm.exception.connector_code, ConnectorErrorCode.CAPABILITY_UNSUPPORTED
        )
        self.assertIsNotNone(cm.exception.assisted_flow_url)


class TestSagaCaminhoFeliz(unittest.TestCase):
    def test_todos_os_canais_confirmados_ativam_a_campanha(self):
        sim, budget = ProviderSimulator(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.PAUSE_ALL)
        out = _run(saga, _campanha_aprovada(), budget)

        self.assertIs(out.campaign_state, CampaignState.ACTIVE)
        self.assertEqual(sorted(out.confirmed_channels), sorted(CANAIS))
        self.assertFalse(out.open_saga)

        tipos = [e["event_type"] for e in out.events]
        self.assertEqual(tipos.count("PlatformResourceCreated"), 2)
        self.assertIn("PublicationStarted", tipos)
        self.assertIn("CampaignActivated", tipos)

    def test_saga_nao_publica_sem_aprovacao_humana(self):
        sim, budget = ProviderSimulator(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.PAUSE_ALL)
        with self.assertRaises(GuardFailed):
            _run(saga, _campanha_aprovada(), budget, approval_id="")
        self.assertEqual(sim.count("publish"), 0)

    def test_saga_nao_publica_com_decisao_de_outra_versao_do_plano(self):
        sim, budget = ProviderSimulator(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.PAUSE_ALL)
        with self.assertRaises(GuardFailed):
            _run(saga, _campanha_aprovada(), budget, plan_version=2)
        self.assertEqual(sim.count("publish"), 0)


class TestSagaFalhaParcial(unittest.TestCase):
    """O caso central: Google publica, Meta falha."""

    def _sim_meta_falha(self, codigo=ConnectorErrorCode.VALIDATION_REJECTED):
        return ProviderSimulator(scripted_failures={"META_FACEBOOK": [codigo] * 5})

    def test_pause_all_pausa_o_confirmado_e_nunca_exclui(self):
        sim, budget = self._sim_meta_falha(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.PAUSE_ALL)
        out = _run(saga, _campanha_aprovada(), budget)

        self.assertIs(out.campaign_state, CampaignState.PUBLISHING)
        self.assertTrue(out.open_saga)
        self.assertEqual(sim.paused, ["GOOGLE_ADS"])
        acoes = [
            e["payload"].get("action")
            for e in out.events
            if e["event_type"] == "CompensationExecuted"
        ]
        self.assertEqual(acoes, ["PAUSE"])
        # Nenhuma operacao de exclusao existe no contrato: compensacao e pausa.
        self.assertEqual(sim.count("delete"), 0)

    def test_keep_partial_mantem_ativo_o_que_deu_certo(self):
        sim, budget = self._sim_meta_falha(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.KEEP_PARTIAL)
        out = _run(saga, _campanha_aprovada(), budget)

        self.assertIs(out.campaign_state, CampaignState.PUBLISHING)
        self.assertEqual(sim.paused, [])
        self.assertEqual(out.confirmed_channels, ["GOOGLE_ADS"])
        self.assertFalse(out.needs_human)

    def test_escalate_human_nao_mexe_em_nada_e_chama_humano(self):
        sim, budget = self._sim_meta_falha(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.ESCALATE_HUMAN)
        out = _run(saga, _campanha_aprovada(), budget)

        self.assertTrue(out.needs_human)
        self.assertEqual(sim.paused, [])
        self.assertIs(out.campaign_state, CampaignState.PUBLISHING)

    def test_verba_do_canal_que_falhou_e_devolvida(self):
        sim, budget = self._sim_meta_falha(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.KEEP_PARTIAL)
        _run(saga, _campanha_aprovada(), budget)
        # So o canal confirmado segue com verba comprometida.
        self.assertEqual(budget.reserved, Decimal("100"))

    def test_falha_parcial_gera_evento_com_os_dois_lados(self):
        sim, budget = self._sim_meta_falha(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.KEEP_PARTIAL)
        out = _run(saga, _campanha_aprovada(), budget)
        evento = next(
            e for e in out.events if e["event_type"] == "PublicationPartiallyFailed"
        )
        self.assertEqual(evento["payload"]["confirmed"], ["GOOGLE_ADS"])
        self.assertEqual(evento["payload"]["failed"], ["META_FACEBOOK"])


class TestRetryECircuito(unittest.TestCase):
    def test_erro_transitorio_e_repetido_e_pode_ter_sucesso(self):
        sim = ProviderSimulator(
            scripted_failures={"META_FACEBOOK": [ConnectorErrorCode.RATE_LIMITED]}
        )
        budget = _budget()
        out = _run(_saga(sim, budget, CompensationPolicy.PAUSE_ALL), _campanha_aprovada(), budget)
        self.assertIs(out.campaign_state, CampaignState.ACTIVE)
        meta = next(s for s in out.steps if s.channel == "META_FACEBOOK")
        self.assertEqual(meta.attempts, 2)

    def test_auth_expirado_nao_e_repetido(self):
        """Repetir com token invalido nunca funciona e so queima cota."""
        sim = ProviderSimulator(
            scripted_failures={"GOOGLE_ADS": [ConnectorErrorCode.AUTH_EXPIRED] * 5}
        )
        budget = _budget()
        out = _run(_saga(sim, budget, CompensationPolicy.KEEP_PARTIAL), _campanha_aprovada(), budget)
        google = next(s for s in out.steps if s.channel == "GOOGLE_ADS")
        self.assertEqual(google.attempts, 1)
        self.assertIs(google.status, StepStatus.FAILED)

    def test_quota_esgotada_nao_e_repetida(self):
        sim = ProviderSimulator(
            scripted_failures={"GOOGLE_ADS": [ConnectorErrorCode.QUOTA_EXHAUSTED] * 5}
        )
        budget = _budget()
        out = _run(_saga(sim, budget, CompensationPolicy.KEEP_PARTIAL), _campanha_aprovada(), budget)
        self.assertEqual(
            next(s for s in out.steps if s.channel == "GOOGLE_ADS").attempts, 1
        )

    def test_transitorio_persistente_para_apos_o_limite(self):
        sim = ProviderSimulator(
            scripted_failures={"GOOGLE_ADS": [ConnectorErrorCode.TRANSIENT] * 10}
        )
        budget = _budget()
        out = _run(_saga(sim, budget, CompensationPolicy.KEEP_PARTIAL), _campanha_aprovada(), budget)
        google = next(s for s in out.steps if s.channel == "GOOGLE_ADS")
        self.assertEqual(google.attempts, 3)  # 1 tentativa + MAX_RETRIES
        self.assertIs(google.status, StepStatus.FAILED)


class TestIdempotenciaDaSaga(unittest.TestCase):
    """I-06: reexecutar a Saga inteira nao pode criar recurso duplicado."""

    def test_reexecucao_com_mesmo_command_id_nao_duplica(self):
        sim, budget = ProviderSimulator(), _budget()
        store = IdempotencyStore()

        def nova_saga():
            return PublicationSaga(
                tenant_id=T1,
                connector=sim,
                budget=budget,
                idempotency=store,
                compensation_policy=CompensationPolicy.PAUSE_ALL,
            )

        out1 = _run(nova_saga(), _campanha_aprovada(), budget)
        ids1 = sorted(s.external_resource_id for s in out1.steps)

        out2 = _run(nova_saga(), _campanha_aprovada(), budget)
        ids2 = sorted(s.external_resource_id for s in out2.steps)

        self.assertEqual(ids1, ids2)
        # O simulador so criou dois recursos, apesar de duas execucoes completas.
        self.assertEqual(len(sim._created), 2)

    def test_reserva_de_verba_tambem_nao_duplica_no_reexecutar(self):
        sim, budget = ProviderSimulator(), _budget()
        store = IdempotencyStore()
        for _ in range(2):
            saga = PublicationSaga(
                tenant_id=T1,
                connector=sim,
                budget=budget,
                idempotency=store,
                compensation_policy=CompensationPolicy.PAUSE_ALL,
            )
            _run(saga, _campanha_aprovada(), budget)
        self.assertEqual(budget.reserved, Decimal("200"))  # 2 canais, nao 4


class TestIsolamentoDaSaga(unittest.TestCase):
    def test_saga_recusa_campanha_de_outro_tenant(self):
        sim, budget = ProviderSimulator(), _budget()
        saga = _saga(sim, budget, CompensationPolicy.PAUSE_ALL)
        alheia = Campaign("c9", "tenant-2", CampaignState.APPROVED)
        with self.assertRaises(ValueError):
            _run(saga, alheia, budget)
        self.assertEqual(sim.count("publish"), 0)


class TestSimuladorFiel(unittest.TestCase):
    """Um simulador que so devolve sucesso e armadilha."""

    def test_simulador_expoe_o_modo_real_da_conta(self):
        sim = ProviderSimulator()
        budget = _budget()
        out = _run(_saga(sim, budget, CompensationPolicy.PAUSE_ALL), _campanha_aprovada(), budget)
        modos = {
            e["payload"]["mode"]
            for e in out.events
            if e["event_type"] == "PlatformResourceCreated"
        }
        self.assertEqual(modos, {"SIMULATOR"})

    def test_simulador_sabe_falhar(self):
        codigos = [
            ConnectorErrorCode.RATE_LIMITED,
            ConnectorErrorCode.AUTH_EXPIRED,
            ConnectorErrorCode.PARTIAL_FAILURE,
            ConnectorErrorCode.VALIDATION_REJECTED,
        ]
        for codigo in codigos:
            with self.subTest(codigo=codigo):
                sim = ProviderSimulator(scripted_failures={"GOOGLE_ADS": [codigo]})
                with self.assertRaises(ConnectorError) as cm:
                    sim.publish(
                        PublishCommand(
                            tenant_id=T1,
                            campaign_id="c1",
                            channel="GOOGLE_ADS",
                            external_account_id="acct-1",
                            idempotency_key="k",
                            policy_decision_id="pd",
                            plan_version=1,
                            payload={"a": 1},
                        )
                    )
                self.assertIs(cm.exception.connector_code, codigo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
