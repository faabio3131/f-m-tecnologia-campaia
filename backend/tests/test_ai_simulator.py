"""Testes de campaia_core.ai_simulator — fechando a lacuna P-12."""

from __future__ import annotations

from decimal import Decimal

import unittest

from campaia_core.ai_gateway import (
    AIRequest,
    AITask,
    ModerationBlocked,
    ProviderError,
    ProviderTimeout,
)
from campaia_core.ai_simulator import Behavior, SimulatedAIProvider


def _req(task=AITask.GENERATE_COPY) -> AIRequest:
    return AIRequest(
        request_id="r1",
        tenant_id="tenant-a",
        task=task,
        input={},
        output_schema_id="x",
        max_cost_units=Decimal("100"),
    )


class TestSupports(unittest.TestCase):
    def test_suporta_todas_as_tarefas_por_padrao(self):
        provider = SimulatedAIProvider()
        for task in AITask:
            self.assertTrue(provider.supports(task))

    def test_respeita_lista_restrita_de_tarefas(self):
        provider = SimulatedAIProvider(supported_tasks=frozenset({AITask.MODERATE}))
        self.assertTrue(provider.supports(AITask.MODERATE))
        self.assertFalse(provider.supports(AITask.GENERATE_COPY))


class TestComportamentoPadrao(unittest.TestCase):
    def test_sem_script_sempre_devolve_ok(self):
        provider = SimulatedAIProvider(output={"variacoes": ["a"]})
        resposta = provider.generate(_req())
        self.assertEqual(resposta.output, {"variacoes": ["a"]})
        self.assertEqual(resposta.cost_units, Decimal("1"))

    def test_generate_incrementa_contador_de_chamadas(self):
        provider = SimulatedAIProvider()
        provider.generate(_req())
        provider.generate(_req())
        self.assertEqual(provider.calls, 2)

    def test_generate_devolve_um_novo_dict_a_cada_chamada(self):
        # `generate` faz `dict(self.output)`: o dict de topo e novo a cada chamada (uma
        # atribuicao de chave de topo em r1.output nao aparece em r2.output), ainda que
        # valores aninhados mutaveis (como uma lista) continuem sendo o mesmo objeto -
        # isso e o comportamento real do simulador, nao um bug a esconder no teste.
        provider = SimulatedAIProvider(output={"variacoes": ["a"]})
        r1 = provider.generate(_req())
        r2 = provider.generate(_req())
        self.assertIsNot(r1.output, r2.output)
        r1.output["nova_chave"] = "so em r1"
        self.assertNotIn("nova_chave", r2.output)


class TestComportamentosProgramados(unittest.TestCase):
    def test_timeout_levanta_provider_timeout(self):
        provider = SimulatedAIProvider().script(Behavior.TIMEOUT)
        with self.assertRaises(ProviderTimeout):
            provider.generate(_req())

    def test_error_levanta_provider_error(self):
        provider = SimulatedAIProvider().script(Behavior.ERROR)
        with self.assertRaises(ProviderError):
            provider.generate(_req())

    def test_moderation_levanta_moderation_blocked(self):
        provider = SimulatedAIProvider().script(Behavior.MODERATION)
        with self.assertRaises(ModerationBlocked):
            provider.generate(_req())

    def test_bad_schema_devolve_saida_fora_do_contrato(self):
        provider = SimulatedAIProvider().script(Behavior.BAD_SCHEMA)
        resposta = provider.generate(_req())
        self.assertIn("texto_solto", resposta.output)

    def test_expensive_multiplica_custo_por_cem(self):
        provider = SimulatedAIProvider(cost_units=Decimal("2")).script(Behavior.EXPENSIVE)
        resposta = provider.generate(_req())
        self.assertEqual(resposta.cost_units, Decimal("200"))

    def test_comportamentos_sao_consumidos_em_ordem_fila(self):
        provider = SimulatedAIProvider().script(Behavior.ERROR, Behavior.OK)
        with self.assertRaises(ProviderError):
            provider.generate(_req())
        resposta = provider.generate(_req())  # segundo comportamento: OK
        self.assertEqual(resposta.output, {"ok": True})

    def test_fila_vazia_apos_consumida_volta_a_ser_sempre_ok(self):
        provider = SimulatedAIProvider().script(Behavior.OK)
        provider.generate(_req())
        # fila esgotada -> comportamento default (OK) continua valendo
        resposta = provider.generate(_req())
        self.assertEqual(resposta.output, {"ok": True})

    def test_script_retorna_self_para_encadeamento(self):
        provider = SimulatedAIProvider()
        retorno = provider.script(Behavior.OK)
        self.assertIs(retorno, provider)


if __name__ == "__main__":
    unittest.main()
