"""ACHADO 20 (Fase 3 da missao de reconciliacao/takeover, 26/09/2026): regressao para o
descasamento de indexacao entre `CapabilityRegistry` e `GET
/connections/{connectionId}/capabilities`.

FATO CONFIRMADO por execucao real (nesta sessao, antes da correcao): toda `Connection`
real criada pelo fluxo de OAuth tem `provider` no rotulo do contrato (`GOOGLE_ADS`,
`META`, `WHATSAPP`), mas `api/state.py::_seed_capabilities()` so registra capacidades sob
`provider="SIMULATOR"` -- a mesma chave que `routes_campaigns.py::validate_campaign` ja
usa (com o literal `"SIMULATOR"`, hardcoded) para decidir se uma campanha pode ser
publicada de verdade. O handler de capacidades, porem, consultava o registro com
`conn.provider` em vez do modo real de execucao da conexao (`conn.mode`,
`ConnectionMode`), entao NUNCA batia com a unica chave seedada -- `GET
/connections/{id}/capabilities` reportava `supported: false` para QUALQUER conta real,
mesmo quando a mesma campanha publicava de fato com sucesso via
`POST /campaigns/{id}/publish` usando exatamente essa capacidade. Reportava tambem um
`verified_at` fabricado (`datetime.now()`) quando nenhuma verificacao de fato ocorreu.

Correcao: o handler passa a mapear `conn.mode` (o eixo real de execucao, unico hoje:
`ConnectionMode.SIMULATOR`) para a chave do registro de capacidades, consistente com
`validate_campaign`. `supported: true` aqui nunca afirma homologacao externa real -- so
que a plataforma sabe executar a acao hoje (via simulador), o que ja e a base real usada
em outro lugar do dominio; o campo `notes` do proprio registro ja disclosa "Simulated
capability, verified in-process at startup." Um modo de conexao sem adaptador real
seedado (TEST/PRODUCTION, nenhum hoje) cai honestamente em `supported: false` e
`verified_at: null` -- nunca em `true`/timestamp fabricados."""

from __future__ import annotations

import unittest

from campaia_core.connectors import ConnectionMode
from tests_api.test_helpers import OWNER, make_client


class TestCapabilityRegistryProviderMapping(unittest.TestCase):
    def test_simulator_mode_connection_shows_the_same_capability_validate_campaign_relies_on(self):
        client = make_client()
        conn = client.app.state.campaia.connections.create(
            "demo-tenant",
            provider="GOOGLE_ADS",
            external_account_id="acct-1",
            display_name="Test Account",
        )
        self.assertIs(conn.mode, ConnectionMode.SIMULATOR)

        r = client.get(f"/connections/{conn.connection_id}/capabilities", headers=OWNER)
        self.assertEqual(r.status_code, 200, r.text)
        caps = {c["capability_key"]: c for c in r.json()}

        for key in ("PUBLISH:GOOGLE_ADS", "PUBLISH:META_ADS"):
            self.assertIn(key, caps)
            self.assertTrue(caps[key]["supported"], caps[key])
            # `provider` no corpo continua sendo o rotulo real da conta OAuth, nao a
            # chave interna do registro.
            self.assertEqual(caps[key]["provider"], "GOOGLE_ADS")
            self.assertIsNotNone(caps[key]["verified_at"])
            # Nunca afirma homologacao externa real -- o disclosure do proprio registro
            # deixa claro que isto e simulado, nao uma integracao real verificada.
            self.assertIn("Simulated", caps[key]["notes"] or "")
            # achado 7 (WP-09): evidence_url nunca fabricado.
            self.assertIsNone(caps[key]["evidence_url"])

    def test_connection_mode_without_a_seeded_capability_is_honestly_unsupported_never_fabricated(self):
        client = make_client()
        conn = client.app.state.campaia.connections.create(
            "demo-tenant",
            provider="META",
            external_account_id="acct-2",
            display_name="Prod Account",
            mode=ConnectionMode.PRODUCTION,
        )

        r = client.get(f"/connections/{conn.connection_id}/capabilities", headers=OWNER)
        self.assertEqual(r.status_code, 200, r.text)
        caps = r.json()
        self.assertTrue(len(caps) > 0)
        for cap in caps:
            self.assertFalse(cap["supported"], cap)
            # Nunca fabrica um "verificado agora" quando nada foi de fato verificado.
            self.assertIsNone(cap["verified_at"])
            self.assertIsNone(cap["evidence_url"])

    def test_capability_reported_matches_what_validate_campaign_actually_relies_on(self):
        """As duas rotas devem concordar sobre o mesmo fato real: se a plataforma sabe
        publicar um canal hoje (via simulador), tanto `GET /connections/{id}/capabilities`
        quanto o gate interno de `validate_campaign` devem refletir o mesmo `True`."""
        from campaia_core.infra import CapabilityRegistry

        client = make_client()
        state = client.app.state.campaia
        conn = state.connections.create(
            "demo-tenant", provider="GOOGLE_ADS", external_account_id="acct-3", display_name="Acc"
        )

        registry: CapabilityRegistry = state.capabilities
        internal_answer = registry.is_supported(
            "SIMULATOR", "PUBLISH:GOOGLE_ADS", country="BR", api_version="sim-1"
        )
        self.assertTrue(internal_answer)

        r = client.get(f"/connections/{conn.connection_id}/capabilities", headers=OWNER)
        exposed = next(c for c in r.json() if c["capability_key"] == "PUBLISH:GOOGLE_ADS")
        self.assertEqual(exposed["supported"], internal_answer)


if __name__ == "__main__":
    unittest.main()
