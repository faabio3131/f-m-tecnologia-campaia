"""Explicit task-aware AI fixture, never imported by production bootstrap."""
from decimal import Decimal
from threading import Lock

from campaia_core.ai_gateway import AITask, CostObservation, ProviderResponse
from campaia_core.ai_simulator import SimulatedAIProvider


class TestOnlyCreativeAIProvider(SimulatedAIProvider):
    def __init__(self):
        super().__init__(name="SIM-CREATIVE-FIXTURE", model="sim-creative-model",
            supported_tasks=frozenset({AITask.PLAN_CAMPAIGN, AITask.GENERATE_COPY, AITask.PROPOSE_AUDIENCE}))
        self._fixture_lock = Lock()

    def generate(self, request):
        with self._fixture_lock:
            self.calls += 1
        if request.task is AITask.GENERATE_COPY:
            count = request.input.get("quantidade_variacoes", 5)
            output = {"variacoes": [f"Proposta simulada {index + 1}: conheça a oferta e confira as condições."
                                    for index in range(count)]}
            if "revisao" in request.input:
                output = {"variacoes": ["Texto revisado simulado: confira a oferta e as condições disponíveis."]}
        elif request.task is AITask.PROPOSE_AUDIENCE:
            output = {"segmentos": ["Pessoas interessadas na oferta declarada"],
                      "exclusoes": list(request.input.get("exclusoes_declaradas", [])),
                      "sensivel": bool(request.input.get("sensivel_declarado", False))}
        else:
            output = {"objetivo": "Gerar demanda qualificada dentro do orcamento aprovado.",
                      "funil": "TOPO_MEIO", "canais": ["GOOGLE_ADS", "META_ADS"],
                      "justificativa": "Saida simulada, nunca um provedor real."}
        return ProviderResponse(output=output, cost_units=Decimal("1"), latency_ms=1, model=self.model,
            cost_observation=CostObservation("SIMULATED", Decimal("1"), model=self.model))


def install_test_creative_provider(state):
    if state.env not in ("test", "dev-local"):
        raise RuntimeError("Creative AI fixture is forbidden outside test/dev-local.")
    provider = TestOnlyCreativeAIProvider()
    state.ai_provider = provider
    state.ai_gateway.providers = [provider]
    return provider
