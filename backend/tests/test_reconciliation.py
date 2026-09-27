"""Testes do reconciliador (ameaca T-08 e invariante I-12)."""

from __future__ import annotations

import ast
import pathlib
import unittest
from decimal import Decimal

from campaia_core.errors import TenantIsolationViolation
from campaia_core.reconciliation import (
    AUTO_APPLICABLE,
    DivergenceType,
    InternalResource,
    PlatformResource,
    Reconciler,
    Remediation,
    ResourceStatus,
    Severity,
)

T1 = "tenant-1"
T2 = "tenant-2"


def _int(
    *,
    campaign="c1",
    channel="GOOGLE_ADS",
    status=ResourceStatus.ACTIVE,
    ext="g-0001",
    budget=None,
    tenant=T1,
) -> InternalResource:
    return InternalResource(
        tenant_id=tenant,
        campaign_id=campaign,
        channel=channel,
        status=status,
        external_resource_id=ext,
        daily_budget=budget,
    )


def _ext(
    *, channel="GOOGLE_ADS", ext="g-0001", status=ResourceStatus.ACTIVE, budget=None
) -> PlatformResource:
    return PlatformResource(
        channel=channel, external_resource_id=ext, status=status, daily_budget=budget
    )


def _run(internal, platform, tenant=T1):
    return Reconciler().reconcile(tenant_id=tenant, internal=internal, platform=platform)


class TestSemDivergencia(unittest.TestCase):
    def test_estados_iguais_produzem_execucao_limpa(self):
        r = _run([_int()], [_ext()])
        self.assertTrue(r.clean)
        self.assertEqual(r.compared, 1)

    def test_verba_igual_nao_gera_alerta(self):
        r = _run(
            [_int(budget=Decimal("50"))], [_ext(budget=Decimal("50"))]
        )
        self.assertTrue(r.clean)

    def test_execucao_tem_identificador_proprio(self):
        self.assertNotEqual(_run([], []).run_id, _run([], []).run_id)


class TestRecursoSumiuDaPlataforma(unittest.TestCase):
    def test_ausente_na_plataforma_gera_divergencia(self):
        r = _run([_int()], [])
        d = r.by_kind(DivergenceType.MISSING_EXTERNAL)[0]
        self.assertIs(d.severity, Severity.STATE)

    def test_reconciliador_nunca_recria_o_recurso(self):
        """Recriar seria decisao de negocio disfarcada de sincronizacao."""
        d = _run([_int()], []).by_kind(DivergenceType.MISSING_EXTERNAL)[0]
        self.assertIs(d.remediation, Remediation.UPDATE_INTERNAL_STATE)
        self.assertIn("Nao sera recriado", d.detail)


class TestOrfao(unittest.TestCase):
    """O caso mais caro: gasto real fora do controle financeiro."""

    def test_recurso_externo_sem_registro_interno_e_financeiro(self):
        r = _run([], [_ext(ext="g-9999")])
        d = r.by_kind(DivergenceType.ORPHAN_EXTERNAL)[0]
        self.assertIs(d.severity, Severity.FINANCIAL)
        self.assertEqual(len(r.financial), 1)

    def test_orfao_sempre_escala_para_humano(self):
        d = _run([], [_ext(ext="g-9999")]).by_kind(DivergenceType.ORPHAN_EXTERNAL)[0]
        self.assertTrue(d.requires_human)
        self.assertFalse(d.auto_applicable)

    def test_orfao_e_adotado_nao_apagado(self):
        """Apagar destruiria historico da plataforma e seria irreversivel."""
        d = _run([], [_ext(ext="g-9999")]).by_kind(DivergenceType.ORPHAN_EXTERNAL)[0]
        self.assertIs(d.remediation, Remediation.ADOPT_EXTERNAL)

    def test_recurso_conhecido_nao_vira_orfao(self):
        r = _run([_int(ext="g-1")], [_ext(ext="g-1")])
        self.assertEqual(r.by_kind(DivergenceType.ORPHAN_EXTERNAL), [])


class TestDescompassoDeEstado(unittest.TestCase):
    def test_pausado_aqui_ativo_la_e_financeiro_e_pausa_automatica(self):
        """Gasto nao previsto acontecendo agora. Pausar de novo nao pode piorar nada."""
        r = _run(
            [_int(status=ResourceStatus.PAUSED)], [_ext(status=ResourceStatus.ACTIVE)]
        )
        d = r.by_kind(DivergenceType.STATUS_MISMATCH)[0]
        self.assertIs(d.severity, Severity.FINANCIAL)
        self.assertIs(d.remediation, Remediation.PAUSE_EXTERNAL)
        self.assertTrue(d.auto_applicable)

    def test_ativo_aqui_pausado_la_apenas_corrige_o_registro(self):
        """A plataforma manda no estado externo. Reativar seria ampliar efeito."""
        r = _run(
            [_int(status=ResourceStatus.ACTIVE)], [_ext(status=ResourceStatus.PAUSED)]
        )
        d = r.by_kind(DivergenceType.STATUS_MISMATCH)[0]
        self.assertIs(d.remediation, Remediation.UPDATE_INTERNAL_STATE)
        self.assertIn("plataforma prevalece", d.detail)

    def test_removido_na_plataforma_corrige_o_registro(self):
        r = _run([_int()], [_ext(status=ResourceStatus.REMOVED)])
        self.assertIs(
            r.by_kind(DivergenceType.STATUS_MISMATCH)[0].remediation,
            Remediation.UPDATE_INTERNAL_STATE,
        )


class TestPublicacaoNaoConfirmada(unittest.TestCase):
    """I-12: nunca declarar publicacao sem confirmacao externa."""

    def test_ativo_sem_id_externo_e_divergencia(self):
        r = _run([_int(ext=None)], [])
        self.assertTrue(r.by_kind(DivergenceType.UNCONFIRMED_PUBLICATION))

    def test_rascunho_sem_id_externo_e_normal(self):
        r = _run([_int(ext=None, status=ResourceStatus.PAUSED)], [])
        self.assertTrue(r.clean)


class TestVerba(unittest.TestCase):
    def test_divergencia_de_verba_escala_para_humano(self):
        r = _run(
            [_int(budget=Decimal("50"))], [_ext(budget=Decimal("500"))]
        )
        d = r.by_kind(DivergenceType.BUDGET_MISMATCH)[0]
        self.assertIs(d.severity, Severity.FINANCIAL)
        self.assertTrue(d.requires_human)

    def test_verba_nunca_e_ajustada_automaticamente(self):
        """Nem para baixo: alterar orcamento e decisao financeira."""
        d = _run([_int(budget=Decimal("500"))], [_ext(budget=Decimal("50"))]).by_kind(
            DivergenceType.BUDGET_MISMATCH
        )[0]
        self.assertIs(d.remediation, Remediation.ESCALATE_HUMAN)
        self.assertFalse(d.auto_applicable)

    def test_verba_desconhecida_de_um_lado_nao_gera_alarme_falso(self):
        r = _run([_int(budget=None)], [_ext(budget=Decimal("50"))])
        self.assertEqual(r.by_kind(DivergenceType.BUDGET_MISMATCH), [])


class TestRegraDeOuro(unittest.TestCase):
    """O reconciliador so reduz efeito ou corrige registro."""

    def test_nao_existe_remediacao_que_amplie_efeito(self):
        proibidas = {"CREATE", "RESUME", "REACTIVATE", "INCREASE_BUDGET", "PUBLISH"}
        self.assertEqual(proibidas & {r.value for r in Remediation}, set())

    def test_toda_remediacao_automatica_e_redutora_ou_de_registro(self):
        self.assertEqual(
            AUTO_APPLICABLE,
            frozenset(
                {
                    Remediation.UPDATE_INTERNAL_STATE,
                    Remediation.PAUSE_EXTERNAL,
                    Remediation.ADOPT_EXTERNAL,
                }
            ),
        )

    def test_escalate_human_nunca_e_automatico(self):
        self.assertNotIn(Remediation.ESCALATE_HUMAN, AUTO_APPLICABLE)


class TestIsolamentoEDeterminismo(unittest.TestCase):
    def test_recurso_de_outro_tenant_e_recusado(self):
        with self.assertRaises(TenantIsolationViolation):
            _run([_int(tenant=T2)], [])

    def test_reconciliacao_sem_tenant_e_recusada(self):
        with self.assertRaises(TenantIsolationViolation):
            _run([], [], tenant="")

    def test_mesma_entrada_produz_mesmas_divergencias(self):
        internal = [_int(status=ResourceStatus.PAUSED), _int(campaign="c2", ext="g-2")]
        platform = [_ext(), _ext(ext="g-3")]
        a = _run(internal, platform)
        b = _run(internal, platform)
        self.assertEqual(
            [(d.kind, d.remediation) for d in a.divergences],
            [(d.kind, d.remediation) for d in b.divergences],
        )

    def test_execucao_repetida_nao_acumula_divergencias(self):
        internal, platform = [_int()], [_ext(status=ResourceStatus.PAUSED)]
        self.assertEqual(
            len(_run(internal, platform).divergences),
            len(_run(internal, platform).divergences),
        )


class TestCenarioSagaInterrompida(unittest.TestCase):
    """Google criou, Meta falhou, e o processo caiu antes de registrar o Google."""

    def test_orfao_do_google_e_meta_ausente_aparecem_juntos(self):
        internal = [_int(campaign="c1", channel="META_FACEBOOK", ext=None)]
        platform = [_ext(channel="GOOGLE_ADS", ext="g-0001")]
        r = _run(internal, platform)

        self.assertEqual(len(r.by_kind(DivergenceType.ORPHAN_EXTERNAL)), 1)
        self.assertEqual(len(r.financial), 1)
        self.assertTrue(r.needs_human)


class TestArquiteturaDoReconciliador(unittest.TestCase):
    def test_reconciliador_nao_usa_ia(self):
        """Comparar estado e deterministico. Modelo nao decide o que e divergencia."""
        caminho = (
            pathlib.Path(__file__).resolve().parents[1]
            / "campaia_core"
            / "reconciliation.py"
        )
        arvore = ast.parse(caminho.read_text())
        importados: set[str] = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module:
                importados.add(no.module.lstrip("."))
            elif isinstance(no, ast.Import):
                importados.update(a.name.split(".")[0] for a in no.names)
        for proibido in ("ai_gateway", "agents", "ai_simulator"):
            with self.subTest(proibido=proibido):
                self.assertNotIn(proibido, importados)


if __name__ == "__main__":
    unittest.main(verbosity=2)
