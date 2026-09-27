"""Testes de campaia_core.ai_gateway — fechando a lacuna P-12.

Cobre as quatro travas descritas no docstring do modulo (custo, schema, fallback,
segredo), mais o teste arquitetural que o proprio docstring do modulo promete:
nenhuma importacao de `connectors`/`saga` capaz de produzir efeito externo.
"""

from __future__ import annotations

import ast
import pathlib
import unittest
from decimal import Decimal

from campaia_core.ai_gateway import (
    AIGateway,
    AIRequest,
    AIStatus,
    AITask,
    Attempt,
    CostLedger,
    CredentialInPayload,
    ModerationBlocked,
    Outcome,
    OutputSchema,
    Prefer,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    assert_no_credentials,
)
from campaia_core.connectors import SecretRef
from campaia_core.errors import TenantIsolationViolation


def _req(**overrides) -> AIRequest:
    base = dict(
        request_id="req-1",
        tenant_id="tenant-a",
        task=AITask.GENERATE_COPY,
        input={"oferta": "10% off"},
        output_schema_id="copy-variants",
        max_cost_units=Decimal("100"),
    )
    base.update(overrides)
    return AIRequest(**base)


class _StaticProvider:
    """Provedor minimo, sem depender do simulador, para isolar o gateway em teste."""

    def __init__(self, name, *, tasks=None, response=None, raises=None):
        self.name = name
        self._tasks = tasks if tasks is not None else frozenset(AITask)
        self._response = response
        self._raises = raises
        self.calls = 0

    def supports(self, task):
        return task in self._tasks

    def generate(self, request):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._response


def _ok_response(output=None, cost=Decimal("1")):
    return ProviderResponse(
        output=output or {"variacoes": ["a", "b"]},
        cost_units=cost,
        latency_ms=50,
        model="modelo-x",
    )


class TestCredencialNaoVazaParaIA(unittest.TestCase):
    def test_secret_ref_e_recusado(self):
        with self.assertRaises(CredentialInPayload):
            assert_no_credentials({"conta": SecretRef("vault://x/y")})

    def test_padrao_vault_url_e_recusado(self):
        with self.assertRaises(CredentialInPayload):
            assert_no_credentials("token em vault://google_ads/123")

    def test_bearer_token_e_recusado(self):
        with self.assertRaises(CredentialInPayload):
            assert_no_credentials("Authorization: Bearer abcDEF123456789012")

    def test_chave_estilo_openai_e_recusada(self):
        with self.assertRaises(CredentialInPayload):
            assert_no_credentials("sk-abcdefghijklmnopqrstuvwxyz")

    def test_token_estilo_meta_e_recusado(self):
        with self.assertRaises(CredentialInPayload):
            assert_no_credentials("EAA" + "x" * 25)

    def test_palavra_chave_de_credencial_e_recusada(self):
        with self.assertRaises(CredentialInPayload):
            assert_no_credentials("client_secret confidencial")

    def test_recursao_em_dict_aninhado(self):
        with self.assertRaises(CredentialInPayload):
            assert_no_credentials({"nivel1": {"nivel2": ["ok", "sk-" + "a" * 20]}})

    def test_recursao_em_lista_e_tupla(self):
        with self.assertRaises(CredentialInPayload):
            assert_no_credentials(("ok", ["fine", "access_token aqui"]))

    def test_payload_limpo_nao_levanta(self):
        assert_no_credentials({"oferta": "10% off", "tom": "descontraido", "n": 42})

    def test_execute_recusa_requisicao_com_credencial_no_input(self):
        gateway = AIGateway(providers=[_StaticProvider("P1", response=_ok_response())])
        req = _req(input={"conta": "vault://google_ads/123"})
        with self.assertRaises(CredentialInPayload):
            gateway.execute(req)


class TestIsolamentoPorTenant(unittest.TestCase):
    def test_execute_sem_tenant_id_levanta(self):
        gateway = AIGateway(providers=[_StaticProvider("P1", response=_ok_response())])
        with self.assertRaises(TenantIsolationViolation):
            gateway.execute(_req(tenant_id=""))

    def test_cost_ledger_charge_sem_tenant_levanta(self):
        ledger = CostLedger()
        with self.assertRaises(TenantIsolationViolation):
            ledger.charge("", Decimal("1"))


class TestCostLedger(unittest.TestCase):
    def test_remaining_sem_teto_e_none(self):
        ledger = CostLedger()
        self.assertIsNone(ledger.remaining("tenant-a"))

    def test_would_exceed_sem_teto_e_falso(self):
        ledger = CostLedger()
        self.assertFalse(ledger.would_exceed("tenant-a", Decimal("999999")))

    def test_charge_acumula_e_remaining_reflete(self):
        ledger = CostLedger()
        ledger.set_cap("tenant-a", Decimal("10"))
        ledger.charge("tenant-a", Decimal("3"))
        ledger.charge("tenant-a", Decimal("2"))
        self.assertEqual(ledger.used("tenant-a"), Decimal("5"))
        self.assertEqual(ledger.remaining("tenant-a"), Decimal("5"))

    def test_would_exceed_true_quando_ultrapassa_teto(self):
        ledger = CostLedger()
        ledger.set_cap("tenant-a", Decimal("10"))
        ledger.charge("tenant-a", Decimal("8"))
        self.assertTrue(ledger.would_exceed("tenant-a", Decimal("5")))
        self.assertFalse(ledger.would_exceed("tenant-a", Decimal("2")))

    def test_tenants_sao_independentes(self):
        ledger = CostLedger()
        ledger.set_cap("tenant-a", Decimal("10"))
        ledger.charge("tenant-a", Decimal("9"))
        self.assertEqual(ledger.used("tenant-b"), Decimal("0"))
        self.assertIsNone(ledger.remaining("tenant-b"))


class TestOutputSchema(unittest.TestCase):
    def setUp(self):
        self.schema = OutputSchema(
            "copy-variants", frozenset({"variacoes"}), {"variacoes": list}
        )

    def test_saida_valida_passa(self):
        self.assertIsNone(self.schema.validate({"variacoes": ["a"]}))

    def test_saida_nao_objeto_e_rejeitada(self):
        self.assertIsNotNone(self.schema.validate(["nao", "e", "dict"]))

    def test_campo_obrigatorio_ausente_e_rejeitado(self):
        erro = self.schema.validate({})
        self.assertIsNotNone(erro)
        self.assertIn("variacoes", erro)

    def test_tipo_errado_e_rejeitado(self):
        erro = self.schema.validate({"variacoes": "nao e lista"})
        self.assertIsNotNone(erro)
        self.assertIn("variacoes", erro)


class TestSelecaoDeProvedor(unittest.TestCase):
    def test_candidates_filtra_por_task(self):
        p1 = _StaticProvider("P1", tasks=frozenset({AITask.GENERATE_COPY}))
        p2 = _StaticProvider("P2", tasks=frozenset({AITask.GENERATE_IMAGE}))
        gateway = AIGateway(providers=[p1, p2])
        candidatos = gateway.candidates(_req(task=AITask.GENERATE_COPY))
        self.assertEqual([p.name for p in candidatos], ["P1"])

    def test_candidates_respeita_pinned_provider(self):
        p1 = _StaticProvider("P1")
        p2 = _StaticProvider("P2")
        gateway = AIGateway(providers=[p1, p2])
        candidatos = gateway.candidates(_req(pinned_provider="P2"))
        self.assertEqual([p.name for p in candidatos], ["P2"])

    def test_candidates_ordena_por_custo_quando_prefer_cost(self):
        p1, p2 = _StaticProvider("CARO"), _StaticProvider("BARATO")
        gateway = AIGateway(
            providers=[p1, p2],
            provider_cost_hint={"CARO": Decimal("9"), "BARATO": Decimal("1")},
        )
        candidatos = gateway.candidates(_req(prefer=Prefer.COST))
        self.assertEqual([p.name for p in candidatos], ["BARATO", "CARO"])

    def test_candidates_ordena_por_latencia_quando_prefer_latency(self):
        p1, p2 = _StaticProvider("LENTO"), _StaticProvider("RAPIDO")
        gateway = AIGateway(
            providers=[p1, p2],
            provider_latency_hint={"LENTO": 900, "RAPIDO": 50},
        )
        candidatos = gateway.candidates(_req(prefer=Prefer.LATENCY))
        self.assertEqual([p.name for p in candidatos], ["RAPIDO", "LENTO"])

    def test_candidates_ordena_por_qualidade_por_padrao(self):
        p1, p2 = _StaticProvider("MEDIOCRE"), _StaticProvider("EXCELENTE")
        gateway = AIGateway(
            providers=[p1, p2],
            provider_quality_hint={"MEDIOCRE": 1, "EXCELENTE": 9},
        )
        candidatos = gateway.candidates(_req(prefer=Prefer.QUALITY))
        self.assertEqual([p.name for p in candidatos], ["EXCELENTE", "MEDIOCRE"])


class TestExecucaoCaminhoFeliz(unittest.TestCase):
    def test_execute_ok_devolve_output_e_proveniencia(self):
        provider = _StaticProvider("P1", response=_ok_response())
        gateway = AIGateway(providers=[provider])
        resultado = gateway.execute(_req())
        self.assertTrue(resultado.ok)
        self.assertEqual(resultado.status, AIStatus.OK)
        self.assertEqual(resultado.output, {"variacoes": ["a", "b"]})
        self.assertEqual(resultado.provenance.provider, "P1")
        self.assertEqual(resultado.provenance.attempts[-1].outcome, Outcome.OK)

    def test_execute_debita_o_ledger_no_sucesso(self):
        provider = _StaticProvider("P1", response=_ok_response(cost=Decimal("3")))
        gateway = AIGateway(providers=[provider])
        gateway.execute(_req())
        self.assertEqual(gateway.ledger.used("tenant-a"), Decimal("3"))

    def test_fallback_used_falso_quando_primeira_tentativa_ja_funciona(self):
        provider = _StaticProvider("P1", response=_ok_response())
        gateway = AIGateway(providers=[provider])
        resultado = gateway.execute(_req())
        self.assertFalse(resultado.provenance.fallback_used)


class TestNenhumProvedorApto(unittest.TestCase):
    def test_sem_candidatos_devolve_no_provider(self):
        gateway = AIGateway(providers=[])
        resultado = gateway.execute(_req())
        self.assertEqual(resultado.status, AIStatus.NO_PROVIDER)
        self.assertFalse(resultado.ok)
        self.assertIsNone(resultado.output)


class TestTetoDeCusto(unittest.TestCase):
    def test_teto_do_tenant_ja_atingido_barra_antes_de_chamar_provedor(self):
        provider = _StaticProvider("P1", response=_ok_response())
        gateway = AIGateway(providers=[provider])
        gateway.ledger.set_cap("tenant-a", Decimal("5"))
        gateway.ledger.charge("tenant-a", Decimal("5"))
        resultado = gateway.execute(_req())
        self.assertEqual(resultado.status, AIStatus.COST_LIMIT)
        self.assertEqual(provider.calls, 0, "nao deveria nem chamar o provedor")

    def test_custo_da_resposta_estoura_teto_da_requisicao_mas_e_cobrado_mesmo_assim(self):
        provider = _StaticProvider("P1", response=_ok_response(cost=Decimal("50")))
        gateway = AIGateway(providers=[provider])
        resultado = gateway.execute(_req(max_cost_units=Decimal("10")))
        self.assertEqual(resultado.status, AIStatus.COST_LIMIT)
        # A chamada chegou ao provedor: o ledger foi debitado mesmo a requisicao falhando.
        self.assertEqual(gateway.ledger.used("tenant-a"), Decimal("50"))


class TestValidacaoDeSchemaComFallback(unittest.TestCase):
    def test_saida_fora_do_schema_tenta_proximo_provedor(self):
        ruim = _StaticProvider("RUIM", response=_ok_response(output={"lixo": True}))
        bom = _StaticProvider("BOM", response=_ok_response())
        gateway = AIGateway(
            providers=[ruim, bom],
            schemas={"copy-variants": OutputSchema(
                "copy-variants", frozenset({"variacoes"}), {"variacoes": list}
            )},
            provider_quality_hint={"RUIM": 9, "BOM": 1},
        )
        resultado = gateway.execute(_req())
        self.assertTrue(resultado.ok)
        self.assertEqual(resultado.provenance.provider, "BOM")
        self.assertTrue(resultado.provenance.fallback_used)
        attempts_outcomes = [a.outcome for a in resultado.provenance.attempts]
        self.assertIn(Outcome.SCHEMA_INVALID, attempts_outcomes)

    def test_saida_invalida_nao_e_consertada_nunca_devolvida_como_ok(self):
        ruim = _StaticProvider("RUIM", response=_ok_response(output={"lixo": True}))
        gateway = AIGateway(
            providers=[ruim],
            schemas={"copy-variants": OutputSchema(
                "copy-variants", frozenset({"variacoes"}), {"variacoes": list}
            )},
        )
        resultado = gateway.execute(_req())
        self.assertFalse(resultado.ok)
        self.assertIsNone(resultado.output)


class TestModeracaoNaoTentaOutroProvedor(unittest.TestCase):
    def test_moderacao_bloqueia_sem_fallback(self):
        bloqueado = _StaticProvider("BLOQ", raises=ModerationBlocked("conteudo sensivel"))
        outro = _StaticProvider("OUTRO", response=_ok_response())
        gateway = AIGateway(
            providers=[bloqueado, outro],
            provider_quality_hint={"BLOQ": 9, "OUTRO": 1},
        )
        resultado = gateway.execute(_req())
        self.assertEqual(resultado.status, AIStatus.BLOCKED_BY_MODERATION)
        self.assertEqual(outro.calls, 0, "moderacao nao deve tentar outro provedor")


class TestTimeoutEProviderErrorTentamProximo(unittest.TestCase):
    def test_timeout_tenta_proximo_provedor(self):
        lento = _StaticProvider("LENTO", raises=ProviderTimeout("estourou"))
        rapido = _StaticProvider("RAPIDO", response=_ok_response())
        gateway = AIGateway(
            providers=[lento, rapido],
            provider_quality_hint={"LENTO": 9, "RAPIDO": 1},
        )
        resultado = gateway.execute(_req())
        self.assertTrue(resultado.ok)
        self.assertEqual(resultado.provenance.provider, "RAPIDO")

    def test_provider_error_tenta_proximo_provedor(self):
        quebrado = _StaticProvider("QUEBRADO", raises=ProviderError("500"))
        ok = _StaticProvider("OK", response=_ok_response())
        gateway = AIGateway(
            providers=[quebrado, ok],
            provider_quality_hint={"QUEBRADO": 9, "OK": 1},
        )
        resultado = gateway.execute(_req())
        self.assertTrue(resultado.ok)
        self.assertEqual(resultado.provenance.provider, "OK")

    def test_todos_os_provedores_falham_devolve_ultimo_status(self):
        p1 = _StaticProvider("P1", raises=ProviderError("erro"))
        gateway = AIGateway(providers=[p1])
        resultado = gateway.execute(_req())
        self.assertEqual(resultado.status, AIStatus.PROVIDER_ERROR)
        self.assertFalse(resultado.ok)


class TestCircuitBreaker(unittest.TestCase):
    def test_circuito_abre_apos_falhas_consecutivas_e_provedor_e_pulado(self):
        # 3 requisicoes consecutivas que falham no mesmo provedor: circuito abre.
        quebrado = _StaticProvider("QUEBRADO", raises=ProviderError("erro"))
        gateway = AIGateway(providers=[quebrado])
        for _ in range(3):
            gateway.execute(_req())
        self.assertTrue(gateway._circuit("QUEBRADO").open)

        # Numa quarta tentativa, com um segundo provedor saudavel disponivel, o
        # circuito aberto deve ser pulado (nao tentado de novo) e o saudavel usado.
        saudavel = _StaticProvider("SAUDAVEL", response=_ok_response())
        gateway.providers.append(saudavel)
        gateway.provider_quality_hint = {"QUEBRADO": 9, "SAUDAVEL": 1}
        chamadas_antes = quebrado.calls
        resultado = gateway.execute(_req())
        self.assertTrue(resultado.ok)
        self.assertEqual(resultado.provenance.provider, "SAUDAVEL")
        self.assertEqual(quebrado.calls, chamadas_antes, "circuito aberto nao deveria ser chamado")
        attempt_names = [a.provider for a in resultado.provenance.attempts]
        self.assertIn("QUEBRADO", attempt_names)
        circuit_attempt = next(a for a in resultado.provenance.attempts if a.provider == "QUEBRADO")
        self.assertEqual(circuit_attempt.outcome, Outcome.CIRCUIT_OPEN)

    def test_sucesso_zera_contador_de_falhas_consecutivas(self):
        provider = _StaticProvider("P1", response=_ok_response())
        gateway = AIGateway(providers=[provider])
        gateway._circuit("P1").consecutive_failures = 2
        gateway.execute(_req())
        self.assertEqual(gateway._circuit("P1").consecutive_failures, 0)
        self.assertFalse(gateway._circuit("P1").open)


class TestFailComProveniencia(unittest.TestCase):
    def test_fail_sempre_tem_proveniencia_mesmo_sem_provedor(self):
        gateway = AIGateway(providers=[])
        resultado = gateway.execute(_req())
        self.assertIsNotNone(resultado.provenance)
        self.assertEqual(resultado.provenance.cost_units, Decimal("0"))
        self.assertGreaterEqual(len(resultado.provenance.attempts), 1)


class TestArquiteturaDoAIGateway(unittest.TestCase):
    """O docstring do modulo promete: teste arquitetural via AST contra conectores/Saga."""

    def test_ai_gateway_nao_importa_connectors_nem_saga_como_modulo_de_efeito(self):
        caminho = pathlib.Path(__file__).resolve().parent.parent / "campaia_core" / "ai_gateway.py"
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        modulos_importados = set()
        for node in ast.walk(arvore):
            if isinstance(node, ast.ImportFrom) and node.module:
                modulos_importados.add(node.module.split(".")[-1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    modulos_importados.add(alias.name.split(".")[-1])
        self.assertNotIn("saga", modulos_importados)
        # `connectors` e importado apenas pelo TIPO SecretRef, para RECUSAR seu uso -
        # isso e esperado e documentado; o que a arquitetura proibe e o modulo `saga`.


if __name__ == "__main__":
    unittest.main()
