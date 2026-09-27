"""Testes de campaia_core.sanitizer — fechando a lacuna P-12."""

from __future__ import annotations

import unittest

from campaia_core.sanitizer import PII_PATTERNS, Sanitizer, sanitize


class TestPadroesIndividuais(unittest.TestCase):
    def test_cpf_e_substituido(self):
        s = Sanitizer()
        limpo = s.sanitize_text("meu CPF e 123.456.789-01")
        self.assertNotIn("123.456.789-01", limpo)
        self.assertIn("[CPF_1]", limpo)
        self.assertEqual(s.report.counts.get("CPF"), 1)

    def test_cnpj_e_substituido_e_nao_confundido_com_cpf(self):
        s = Sanitizer()
        limpo = s.sanitize_text("CNPJ 12.345.678/0001-99 da empresa")
        self.assertIn("[CNPJ_1]", limpo)
        self.assertNotIn("CPF", s.report.counts)

    def test_email_e_substituido(self):
        s = Sanitizer()
        limpo = s.sanitize_text("contato: fulano@exemplo.com.br")
        self.assertIn("[EMAIL_1]", limpo)
        self.assertNotIn("fulano@exemplo.com.br", limpo)

    def test_telefone_e_substituido(self):
        s = Sanitizer()
        limpo = s.sanitize_text("me liga no (11) 91234-5678")
        self.assertIn("[TELEFONE_1]", limpo)

    def test_cep_e_substituido(self):
        s = Sanitizer()
        limpo = s.sanitize_text("endereco no CEP 01310-100")
        self.assertIn("[CEP_1]", limpo)

    def test_cartao_e_substituido(self):
        s = Sanitizer()
        limpo = s.sanitize_text("cartao 4111 1111 1111 1111")
        self.assertIn("[CARTAO_1]", limpo)

    def test_ordem_dos_padroes_e_a_documentada(self):
        # CNPJ antes de CARTAO antes de CPF - a ordem em si e o invariante do docstring.
        rotulos = [rotulo for rotulo, _ in PII_PATTERNS]
        self.assertLess(rotulos.index("CNPJ"), rotulos.index("CARTAO"))
        self.assertLess(rotulos.index("CARTAO"), rotulos.index("CPF"))


class TestPlaceholdersEstaveis(unittest.TestCase):
    def test_mesma_ocorrencia_repetida_recebe_o_mesmo_marcador(self):
        s = Sanitizer()
        limpo = s.sanitize_text("CPF 123.456.789-01 confirmado: 123.456.789-01 de novo")
        self.assertEqual(limpo.count("[CPF_1]"), 2)
        self.assertEqual(s.report.counts["CPF"], 1)

    def test_ocorrencias_diferentes_recebem_marcadores_diferentes(self):
        s = Sanitizer()
        limpo = s.sanitize_text("CPFs: 123.456.789-01 e 987.654.321-00")
        self.assertIn("[CPF_1]", limpo)
        self.assertIn("[CPF_2]", limpo)
        self.assertEqual(s.report.counts["CPF"], 2)

    def test_placeholder_for_localiza_o_marcador_pelo_valor_original(self):
        s = Sanitizer()
        s.sanitize_text("CPF 123.456.789-01")
        self.assertEqual(s.report.placeholder_for("123.456.789-01"), "[CPF_1]")
        self.assertIsNone(s.report.placeholder_for("valor-nunca-visto"))


class TestRehydrate(unittest.TestCase):
    def test_rehydrate_restaura_o_valor_original(self):
        s = Sanitizer()
        limpo = s.sanitize_text("email: fulano@exemplo.com")
        restaurado = s.report.rehydrate(limpo)
        self.assertEqual(restaurado, "email: fulano@exemplo.com")

    def test_rehydrate_nao_afeta_texto_sem_marcador(self):
        s = Sanitizer()
        s.sanitize_text("CPF 123.456.789-01")
        self.assertEqual(s.report.rehydrate("texto qualquer sem marcador"), "texto qualquer sem marcador")


class TestSanitizeRecursivo(unittest.TestCase):
    def test_sanitize_em_dict_aninhado(self):
        limpo, relatorio = sanitize({"cliente": {"email": "a@b.com", "nome": "Fulano"}})
        self.assertNotIn("a@b.com", str(limpo))
        self.assertEqual(relatorio.counts.get("EMAIL"), 1)

    def test_sanitize_em_lista(self):
        limpo, relatorio = sanitize(["contato: a@b.com", "sem pii aqui"])
        self.assertNotIn("a@b.com", limpo[0])
        self.assertEqual(limpo[1], "sem pii aqui")

    def test_sanitize_em_tupla_preserva_tipo(self):
        limpo, _ = sanitize(("email a@b.com",))
        self.assertIsInstance(limpo, tuple)

    def test_sanitize_preserva_tipos_nao_string(self):
        limpo, relatorio = sanitize({"idade": 42, "ativo": True, "saldo": None})
        self.assertEqual(limpo, {"idade": 42, "ativo": True, "saldo": None})
        self.assertEqual(relatorio.total, 0)

    def test_sanitize_nao_altera_o_objeto_original(self):
        original = {"email": "a@b.com"}
        sanitize(original)
        self.assertEqual(original, {"email": "a@b.com"})

    def test_sanitize_sem_pii_devolve_relatorio_vazio(self):
        limpo, relatorio = sanitize({"objetivo": "vendas", "canal": "META_INSTAGRAM"})
        self.assertEqual(limpo, {"objetivo": "vendas", "canal": "META_INSTAGRAM"})
        self.assertEqual(relatorio.total, 0)
        self.assertEqual(relatorio.found_types, ())


class TestSanitizationReportRepr(unittest.TestCase):
    def test_repr_nunca_expoe_o_mapeamento_de_valores_reais(self):
        _, relatorio = sanitize({"email": "segredo@exemplo.com"})
        relatorio.counts["EMAIL"] = 1
        texto = repr(relatorio)
        self.assertNotIn("segredo@exemplo.com", texto)
        self.assertIn("EMAIL", texto)


if __name__ == "__main__":
    unittest.main()
