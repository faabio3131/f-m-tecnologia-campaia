"""Sanitizacao de dados pessoais antes de qualquer envio a provedor de IA.

Por que pseudonimizar em vez de apagar: se o CPF do cliente virasse `[REMOVIDO]`, o modelo
perderia a nocao de que duas mencoes falam da mesma pessoa. Trocando por `[CPF_1]`, o
raciocinio se preserva e o dado nao sai do backend.

O mapa de volta (`[CPF_1]` -> valor real) fica FORA do payload, no lado de ca. Ele serve
para reidratar o texto na tela do usuario. Nunca vai para log, prompt, evento ou resposta
de API.

Ordem dos padroes importa: CNPJ e testado antes de CPF, e cartao antes de telefone, porque
uma sequencia longa de digitos casa parcialmente com o padrao mais curto e seria marcada
com o rotulo errado.

LGPD: reduzir o dado enviado a terceiros e minimizacao de finalidade, nao enfeite. A base
legal do tratamento em si continua sendo decisao do Diretor (D-09).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Pattern

#: (rotulo, padrao). A ORDEM e significativa - do mais especifico para o mais generico.
PII_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    ("CNPJ", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    ("CARTAO", re.compile(r"\b(?:\d{4}[ .-]?){3}\d{4}\b")),
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("TELEFONE", re.compile(r"(?:\+55\s?)?\(?\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}\b")),
    ("CEP", re.compile(r"\b\d{5}-\d{3}\b")),
)


@dataclass
class SanitizationReport:
    """O que foi trocado. Guarda CONTAGEM por tipo, nunca os valores."""

    counts: dict[str, int] = field(default_factory=dict)
    #: placeholder -> valor original. Fica no backend; nao serializar.
    _mapping: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def found_types(self) -> tuple[str, ...]:
        return tuple(sorted(self.counts))

    def placeholder_for(self, original: str) -> str | None:
        for placeholder, valor in self._mapping.items():
            if valor == original:
                return placeholder
        return None

    def rehydrate(self, text: str) -> str:
        """Repoe os valores reais. Use apenas para exibir ao usuario dono do dado."""
        for placeholder, valor in self._mapping.items():
            text = text.replace(placeholder, valor)
        return text

    def __repr__(self) -> str:
        return f"SanitizationReport(counts={self.counts})"


class Sanitizer:
    """Substitui PII por marcadores estaveis dentro de uma mesma sanitizacao."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self.report = SanitizationReport()

    def _placeholder(self, label: str, original: str) -> str:
        existente = self.report.placeholder_for(original)
        if existente is not None:
            return existente  # mesma ocorrencia, mesmo marcador
        self._counters[label] = self._counters.get(label, 0) + 1
        placeholder = f"[{label}_{self._counters[label]}]"
        self.report._mapping[placeholder] = original
        self.report.counts[label] = self.report.counts.get(label, 0) + 1
        return placeholder

    def sanitize_text(self, text: str) -> str:
        for label, padrao in PII_PATTERNS:
            text = padrao.sub(lambda m: self._placeholder(label, m.group(0)), text)
        return text

    def sanitize(self, value: Any) -> Any:
        """Devolve uma copia sanitizada. NUNCA altera o objeto original."""
        if isinstance(value, str):
            return self.sanitize_text(value)
        if isinstance(value, dict):
            return {k: self.sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.sanitize(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self.sanitize(v) for v in value)
        return value


def sanitize(payload: Any) -> tuple[Any, SanitizationReport]:
    """Atalho: devolve (payload_limpo, relatorio)."""
    s = Sanitizer()
    return s.sanitize(payload), s.report
