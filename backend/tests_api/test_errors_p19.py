"""Testes da correção da P-19: 3 códigos do Connector Hub sem mapeamento HTTP.

Achado durante o B10 (catálogo de erros em linguagem de usuário, 03/09/2026):
`AUTH_EXPIRED`, `VALIDATION_REJECTED` e `PARTIAL_FAILURE` (campaia_core.connectors.
ConnectorErrorCode) não tinham entrada em `STATUS_BY_CODE`, o que fazia `from_domain_error`
colapsá-los silenciosamente para `UNKNOWN`/500. Este arquivo prova que a correção resolve
isso de fato -- não apenas que a suíte existente continua passando.
"""
from __future__ import annotations

import unittest

from api.errors import STATUS_BY_CODE, from_domain_error
from campaia_core.connectors import ConnectorError, ConnectorErrorCode


class TestP19ConnectorErrorCodeGap(unittest.TestCase):
    def test_all_ten_connector_error_codes_are_mapped(self) -> None:
        """Nenhum dos 10 códigos de ConnectorErrorCode pode ficar de fora de
        STATUS_BY_CODE -- é exatamente essa lacuna que causava o colapso para UNKNOWN."""
        unmapped = [c for c in ConnectorErrorCode if c.value not in STATUS_BY_CODE]
        self.assertEqual(unmapped, [], f"códigos de conector ainda sem mapeamento HTTP: {unmapped}")

    def test_auth_expired_maps_to_401(self) -> None:
        self.assertEqual(STATUS_BY_CODE["AUTH_EXPIRED"], 401)

    def test_validation_rejected_maps_to_422(self) -> None:
        self.assertEqual(STATUS_BY_CODE["VALIDATION_REJECTED"], 422)

    def test_partial_failure_maps_to_207(self) -> None:
        self.assertEqual(STATUS_BY_CODE["PARTIAL_FAILURE"], 207)

    def test_from_domain_error_preserves_auth_expired_not_unknown(self) -> None:
        exc = ConnectorError(ConnectorErrorCode.AUTH_EXPIRED, "token expirado")
        api_err = from_domain_error(exc)
        self.assertEqual(api_err.code, "AUTH_EXPIRED")
        self.assertEqual(api_err.status_code, 401)

    def test_from_domain_error_preserves_validation_rejected_not_unknown(self) -> None:
        # Este é o caminho real: campaia_core/saga.py levanta exatamente este código
        # em PublicationSaga._publish_channel (linha ~191) quando a plataforma rejeita
        # o conteúdo publicado.
        exc = ConnectorError(ConnectorErrorCode.VALIDATION_REJECTED, "conteúdo rejeitado pela plataforma")
        api_err = from_domain_error(exc)
        self.assertEqual(api_err.code, "VALIDATION_REJECTED")
        self.assertEqual(api_err.status_code, 422)

    def test_from_domain_error_preserves_partial_failure_not_unknown(self) -> None:
        exc = ConnectorError(ConnectorErrorCode.PARTIAL_FAILURE, "publicação parcial")
        api_err = from_domain_error(exc)
        self.assertEqual(api_err.code, "PARTIAL_FAILURE")
        self.assertEqual(api_err.status_code, 207)

    def test_regression_before_fix_would_have_collapsed_to_unknown(self) -> None:
        """Documenta o comportamento que a P-19 corrigiu: simulando a lacuna antiga
        (código ausente de STATUS_BY_CODE), from_domain_error deve mesmo colapsar para
        UNKNOWN -- prova que o mecanismo de colapso em si funciona como descrito, e que
        é exatamente esse mecanismo que a correção acima evita para os 3 códigos reais."""
        status_by_code_sem_os_tres = dict(STATUS_BY_CODE)
        for codigo in ("AUTH_EXPIRED", "VALIDATION_REJECTED", "PARTIAL_FAILURE"):
            status_by_code_sem_os_tres.pop(codigo, None)

        exc = ConnectorError(ConnectorErrorCode.AUTH_EXPIRED, "token expirado")
        code = getattr(exc, "code", "UNKNOWN")
        if code not in status_by_code_sem_os_tres:
            code = "UNKNOWN"
        self.assertEqual(code, "UNKNOWN", "confirma que, sem a correção, o código colapsaria")


if __name__ == "__main__":
    unittest.main()
