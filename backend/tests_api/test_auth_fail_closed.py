"""WP-02: proves the fixture Bearer-token auth mechanism is fail-closed by construction.

Before WP-02, `AppState.tokens` was seeded unconditionally by every `create_app()` call --
including the module-level `app = create_app()` in api/main.py, i.e. the "production"
entrypoint -- so the fixture Bearer tokens (`demo-owner-token` etc.) were always reachable
by anyone who knew the string, in any environment. This is exactly the ADR-0018 rollback
clause WP-02 closes: "impossivel habilitar esse mecanismo em preview, staging ou producao,
mesmo por engano de configuracao -- a checagem de ambiente deve recusar a inicializacao,
nao apenas ocultar a opcao."

Two independent signals must now agree before fixture tokens exist: the caller must pass
`enable_test_auth_fixtures=True` AND the process environment must declare itself via
CAMPAIA_ENV=test|local_dev. Neither alone is enough.
"""

from __future__ import annotations

import os
import unittest

from api.main import create_app


class TestAuthFailClosed(unittest.TestCase):
    def setUp(self) -> None:
        self._original_env = os.environ.get("CAMPAIA_ENV")

    def tearDown(self) -> None:
        if self._original_env is None:
            os.environ.pop("CAMPAIA_ENV", None)
        else:
            os.environ["CAMPAIA_ENV"] = self._original_env

    def test_bare_create_app_has_no_fixture_tokens(self) -> None:
        """The module-level production `app` in api/main.py calls create_app() with no
        arguments -- this is the exact call this test reproduces."""
        os.environ.pop("CAMPAIA_ENV", None)
        app = create_app()
        self.assertEqual(app.state.campaia.tokens, {})

    def test_enable_flag_without_env_var_raises(self) -> None:
        os.environ.pop("CAMPAIA_ENV", None)
        with self.assertRaises(RuntimeError):
            create_app(enable_test_auth_fixtures=True)

    def test_env_var_without_enable_flag_seeds_nothing(self) -> None:
        os.environ["CAMPAIA_ENV"] = "test"
        app = create_app()
        self.assertEqual(app.state.campaia.tokens, {})

    def test_both_signals_together_seeds_fixture_tokens(self) -> None:
        os.environ["CAMPAIA_ENV"] = "test"
        app = create_app(enable_test_auth_fixtures=True)
        self.assertIn("demo-owner-token", app.state.campaia.tokens)

    def test_local_dev_env_value_also_accepted(self) -> None:
        os.environ["CAMPAIA_ENV"] = "local_dev"
        app = create_app(enable_test_auth_fixtures=True)
        self.assertIn("demo-owner-token", app.state.campaia.tokens)

    def test_production_env_refuses_even_with_flag_true(self) -> None:
        os.environ["CAMPAIA_ENV"] = "production"
        with self.assertRaises(RuntimeError):
            create_app(enable_test_auth_fixtures=True)

    def test_staging_env_refuses_even_with_flag_true(self) -> None:
        os.environ["CAMPAIA_ENV"] = "staging"
        with self.assertRaises(RuntimeError):
            create_app(enable_test_auth_fixtures=True)

    def test_empty_string_env_refuses_even_with_flag_true(self) -> None:
        """Guards against a misconfiguration that sets CAMPAIA_ENV="" rather than omitting
        it entirely -- must fail exactly like the unset case, never treat empty as truthy
        for either environment name."""
        os.environ["CAMPAIA_ENV"] = ""
        with self.assertRaises(RuntimeError):
            create_app(enable_test_auth_fixtures=True)


if __name__ == "__main__":
    unittest.main()
