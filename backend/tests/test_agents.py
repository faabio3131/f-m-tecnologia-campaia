"""Testes de campaia_core.agents — fechando a lacuna P-12.

Cobre o contrato central do modulo (agente = funcao pura, contexto -> proposta; nunca
inventa contexto faltante) e o teste arquitetural que o docstring do modulo promete.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

from campaia_core.agents import (
    AGENTS,
    MISSING_CONTEXT,
    UNKNOWN_AGENT,
    AgentFailure,
    AgentRunner,
    Proposal,
)
from campaia_core.ai_gateway import AIGateway, AIStatus
from campaia_core.ai_simulator import Behavior, SimulatedAIProvider
from campaia_core.errors import TenantIsolationViolation


def _runner_com_provedor(provider=None):
    provider = provider or SimulatedAIProvider(output={"resumo": "ok", "diferenciais": ["a"]})
    gateway = AIGateway(providers=[provider])
    runner = AgentRunner(gateway=gateway)
    runner.register_schemas()
    return runner, provider


class TestCatalogoDeAgentes(unittest.TestCase):
    def test_seis_agentes_no_catalogo(self):
        self.assertEqual(len(AGENTS), 6)
        self.assertEqual(
            set(AGENTS),
            {"business_context", "strategist", "copy", "audience", "policy", "performance"},
        )

    def test_register_schemas_publica_todos_os_contratos_no_gateway(self):
        gateway = AIGateway()
        runner = AgentRunner(gateway=gateway)
        runner.register_schemas()
        for spec in AGENTS.values():
            self.assertIn(spec.output_schema.schema_id, gateway.schemas)


class TestIsolamentoPorTenant(unittest.TestCase):
    def test_run_sem_tenant_id_levanta(self):
        runner, _ = _runner_com_provedor()
        with self.assertRaises(TenantIsolationViolation):
            runner.run(
                "business_context",
                tenant_id="",
                context={"empresa": "x", "produto": "y", "regiao": "SP"},
            )


class TestAgenteDesconhecido(unittest.TestCase):
    def test_agente_fora_do_catalogo_devolve_unknown_agent(self):
        runner, provider = _runner_com_provedor()
        resultado = runner.run("agente_que_nao_existe", tenant_id="t1", context={})
        self.assertIsInstance(resultado, AgentFailure)
        self.assertEqual(resultado.status, UNKNOWN_AGENT)
        self.assertEqual(provider.calls, 0)


class TestContextoInsuficienteNuncaEInventado(unittest.TestCase):
    def test_contexto_faltando_recusa_sem_chamar_o_gateway(self):
        runner, provider = _runner_com_provedor()
        resultado = runner.run(
            "strategist",
            tenant_id="t1",
            context={"objetivo": "vendas"},  # faltam orcamento, publico, regiao
        )
        self.assertIsInstance(resultado, AgentFailure)
        self.assertEqual(resultado.status, MISSING_CONTEXT)
        self.assertEqual(
            resultado.missing_context, ("orcamento", "publico", "regiao")
        )
        self.assertEqual(provider.calls, 0, "nao deveria supor o que falta e chamar a IA")

    def test_missing_context_e_ordenado_e_completo(self):
        runner, _ = _runner_com_provedor()
        resultado = runner.run("audience", tenant_id="t1", context={})
        self.assertEqual(resultado.missing_context, ("canal", "publico", "regiao"))


class TestCaminhoFeliz(unittest.TestCase):
    def test_run_com_contexto_completo_devolve_proposal(self):
        provider = SimulatedAIProvider(output={"resumo": "empresa solida", "diferenciais": ["preco"]})
        runner, _ = _runner_com_provedor(provider)
        resultado = runner.run(
            "business_context",
            tenant_id="t1",
            context={"empresa": "ACME", "produto": "Widget", "regiao": "SP"},
        )
        self.assertIsInstance(resultado, Proposal)
        self.assertTrue(resultado.is_proposal)
        self.assertEqual(resultado.tenant_id, "t1")
        self.assertEqual(resultado.agent, "business_context")
        self.assertEqual(resultado.output["resumo"], "empresa solida")

    def test_proposal_tem_id_unico_por_execucao(self):
        provider = SimulatedAIProvider(output={"resumo": "x", "diferenciais": []})
        runner, _ = _runner_com_provedor(provider)
        ctx = {"empresa": "ACME", "produto": "Widget", "regiao": "SP"}
        p1 = runner.run("business_context", tenant_id="t1", context=ctx)
        p2 = runner.run("business_context", tenant_id="t1", context=ctx)
        self.assertNotEqual(p1.proposal_id, p2.proposal_id)


class TestSanitizacaoAntesDaIA(unittest.TestCase):
    def test_pii_no_contexto_e_sanitizada_e_reportada_na_proposta(self):
        provider = SimulatedAIProvider(output={"resumo": "ok", "diferenciais": []})
        runner, _ = _runner_com_provedor(provider)
        resultado = runner.run(
            "business_context",
            tenant_id="t1",
            context={
                "empresa": "ACME",
                "produto": "Widget",
                "regiao": "SP",
                "contato_dono": "fulano@exemplo.com",
            },
        )
        self.assertIsInstance(resultado, Proposal)
        self.assertIn("EMAIL", resultado.pii_found)
        self.assertGreaterEqual(resultado.pii_count, 1)

    def test_rehydrate_restaura_pii_original_para_o_dono_do_dado(self):
        provider = SimulatedAIProvider(output={"resumo": "ok", "diferenciais": []})
        runner, _ = _runner_com_provedor(provider)
        resultado = runner.run(
            "business_context",
            tenant_id="t1",
            context={
                "empresa": "ACME",
                "produto": "Widget",
                "regiao": "SP",
                "contato_dono": "fulano@exemplo.com",
            },
        )
        placeholder = resultado.pii_found[0]
        # Descobrimos qual texto sanitizado contem o marcador olhando o proprio relatorio
        # indiretamente: reidratamos um texto que contenha o marcador conhecido.
        relatorio = runner._reports[resultado.proposal_id]
        marcador = next(iter(relatorio._mapping))
        texto_reidratado = runner.rehydrate(resultado, f"contato: {marcador}")
        self.assertEqual(texto_reidratado, "contato: fulano@exemplo.com")

    def test_rehydrate_sem_relatorio_conhecido_devolve_texto_intacto(self):
        provider = SimulatedAIProvider(output={"resumo": "ok", "diferenciais": []})
        runner, _ = _runner_com_provedor(provider)
        proposta_falsa = Proposal(
            proposal_id="id-inexistente",
            agent="business_context",
            tenant_id="t1",
            output={},
            provenance=None,
        )
        self.assertEqual(runner.rehydrate(proposta_falsa, "texto original"), "texto original")


class TestFalhaDoGatewayViraAgentFailure(unittest.TestCase):
    def test_gateway_bloqueado_por_moderacao_vira_agent_failure_com_proveniencia(self):
        provider = SimulatedAIProvider().script(Behavior.MODERATION)
        runner, _ = _runner_com_provedor(provider)
        resultado = runner.run(
            "policy", tenant_id="t1", context={"texto": "algo sensivel"}
        )
        self.assertIsInstance(resultado, AgentFailure)
        self.assertEqual(resultado.status, AIStatus.BLOCKED_BY_MODERATION)
        self.assertIsNotNone(resultado.provenance)

    def test_gateway_com_saida_fora_do_schema_vira_agent_failure(self):
        provider = SimulatedAIProvider().script(Behavior.BAD_SCHEMA)
        runner, _ = _runner_com_provedor(provider)
        resultado = runner.run(
            "copy", tenant_id="t1", context={"oferta": "10%", "tom": "leve", "canal": "META"}
        )
        self.assertIsInstance(resultado, AgentFailure)
        self.assertEqual(resultado.status, AIStatus.SCHEMA_INVALID)


class TestArquiteturaDosAgentes(unittest.TestCase):
    """O docstring do modulo promete: teste arquitetural via AST contra conector/Saga."""

    def test_agents_nao_importa_connectors_nem_saga(self):
        caminho = pathlib.Path(__file__).resolve().parent.parent / "campaia_core" / "agents.py"
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        modulos_importados = set()
        for node in ast.walk(arvore):
            if isinstance(node, ast.ImportFrom) and node.module:
                modulos_importados.add(node.module.split(".")[-1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    modulos_importados.add(alias.name.split(".")[-1])
        self.assertNotIn("connectors", modulos_importados)
        self.assertNotIn("saga", modulos_importados)


if __name__ == "__main__":
    unittest.main()
