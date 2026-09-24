from __future__ import annotations

import os
import unittest

from campaia_core.identity_provider import (
    AlwaysRejectIdTokenVerifier,
    FirebaseIdentityConfig,
    FirebaseIdTokenVerifier,
    IdentityError,
)


class FirebaseIdentityConfigTests(unittest.TestCase):
    def _clear(self) -> str | None:
        return os.environ.pop("FIREBASE_PROJECT_ID", None)

    def _restore(self, old: str | None) -> None:
        if old is not None:
            os.environ["FIREBASE_PROJECT_ID"] = old

    def test_from_env_is_none_when_unset(self) -> None:
        old = self._clear()
        try:
            self.assertIsNone(FirebaseIdentityConfig.from_env())
        finally:
            self._restore(old)

    def test_from_env_reads_project_id_when_set(self) -> None:
        old = self._clear()
        os.environ["FIREBASE_PROJECT_ID"] = "campaia-test-project"
        try:
            config = FirebaseIdentityConfig.from_env()
            self.assertIsNotNone(config)
            self.assertEqual(config.project_id, "campaia-test-project")
        finally:
            os.environ.pop("FIREBASE_PROJECT_ID", None)
            self._restore(old)


class AlwaysRejectIdTokenVerifierTests(unittest.TestCase):
    """Item 1.3/WP-02 (24/09/2026): este e o default de seguranca enquanto o item 1.6
    (projeto Google Cloud real) nao estiver provisionado -- nunca autentica ninguem, ao
    contrario de um simulador permissivo (que seria um buraco de autenticacao aqui)."""

    def test_verify_always_raises_identity_error(self) -> None:
        verifier = AlwaysRejectIdTokenVerifier()
        with self.assertRaises(IdentityError):
            verifier.verify("qualquer-coisa")

    def test_verify_raises_even_for_empty_token(self) -> None:
        verifier = AlwaysRejectIdTokenVerifier()
        with self.assertRaises(IdentityError):
            verifier.verify("")


class FirebaseIdTokenVerifierTests(unittest.TestCase):
    """Testa so o adaptador (construcao + fail-closed em token invalido) -- a verificacao
    criptografica real (RS256/JWKS/revogacao) e responsabilidade do SDK oficial
    `firebase-admin` (decisao do Diretor, 24/09/2026), nao reimplementada nem retestada
    aqui. Nenhum projeto Google Cloud real e necessario: `verify_id_token` falha ao tentar
    decodificar um token que nao e nem um JWT bem formado, o que ja prova que o adaptador
    embrulha qualquer falha do SDK em `IdentityError`, fail-closed."""

    def test_garbage_token_is_rejected_as_identity_error(self) -> None:
        config = FirebaseIdentityConfig(project_id="campaia-test-project")
        verifier = FirebaseIdTokenVerifier(config, app_name="campaia-test-fixture")
        with self.assertRaises(IdentityError):
            verifier.verify("isto-nao-e-um-jwt")

    def test_reusing_the_same_app_name_does_not_raise(self) -> None:
        """firebase_admin proibe inicializar duas Apps com o mesmo nome -- o adaptador
        precisa reaproveitar a instancia existente (get_app) em vez de falhar na segunda
        construcao com a mesma config, o que aconteceria se cada AppState/teste
        recriasse o mesmo `FirebaseIdTokenVerifier` mais de uma vez no mesmo processo."""
        config = FirebaseIdentityConfig(project_id="campaia-test-project-2")
        FirebaseIdTokenVerifier(config, app_name="campaia-test-fixture-2")
        FirebaseIdTokenVerifier(config, app_name="campaia-test-fixture-2")  # nao deve levantar


if __name__ == "__main__":
    unittest.main()
