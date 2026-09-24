"""Prova que `AppState` nunca usa um provedor de IA real por acidente (mesma disciplina ja
aplicada ao billing_gateway: real so quando a credencial estiver explicitamente configurada
no ambiente -- ADR-0021, 24/09/2026)."""

from __future__ import annotations

import os
import unittest

from campaia_core.ai_simulator import SimulatedAIProvider
from campaia_core.gemini_provider import GeminiProvider

from api.state import AppState


class AIProviderWiringTests(unittest.TestCase):
    def _clear_gemini_env(self) -> str | None:
        return os.environ.pop("GEMINI_API_KEY", None)

    def _restore_gemini_env(self, old: str | None) -> None:
        if old is not None:
            os.environ["GEMINI_API_KEY"] = old

    def test_default_state_uses_the_simulator_never_a_real_provider(self) -> None:
        old = self._clear_gemini_env()
        try:
            state = AppState()
            self.assertIsInstance(state.ai_provider, SimulatedAIProvider)
        finally:
            self._restore_gemini_env(old)

    def test_gemini_api_key_in_env_switches_to_the_real_provider(self) -> None:
        old = self._clear_gemini_env()
        os.environ["GEMINI_API_KEY"] = "fake-key-for-wiring-test"
        try:
            state = AppState()
            self.assertIsInstance(state.ai_provider, GeminiProvider)
            # As schemas de todo o catalogo de agentes precisam estar disponiveis para o
            # GeminiProvider real montar o prompt certo por tarefa -- sem isso, toda
            # chamada falharia com "contrato de saida nao registrado".
            self.assertIn("campaign-plan", state.ai_provider.schemas)
        finally:
            os.environ.pop("GEMINI_API_KEY", None)
            self._restore_gemini_env(old)


if __name__ == "__main__":
    unittest.main()
