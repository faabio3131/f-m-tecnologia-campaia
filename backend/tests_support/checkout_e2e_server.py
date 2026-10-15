"""Isolated commercial E2E harness: SQLite + deterministic IdP + payment simulator.

Loopback only, never imported by product entrypoints. No credentials or real gateway.
Separate from the certified session harness so its catalog/runtime are unchanged.
"""
import json
import os
from pathlib import Path
import tempfile

import uvicorn
from api.main import create_app
from tests_support.e2e_identity import DeterministicTestIdTokenVerifier

runtime = tempfile.TemporaryDirectory(prefix='campaia-checkout-e2e-')
origin = os.environ['CAMPAIA_E2E_ALLOWED_ORIGIN']
catalog = json.loads((Path(__file__).parents[1] / 'config/plans.example.json').read_text())
commercial = {**catalog[0], 'plan_id': 'e2e-commercial', 'name': 'Plano comercial E2E',
              'monthly_price': '12.50', 'included_credits': 10, 'cancellation_mode': 'PERIOD_END',
              'plan_changes': [], 'credit_policy': {'version': 'e2e-v1', 'action_weights': {'strategy': 5},
                  'trial_credits': 30, 'trial_max_users': 1, 'trial_max_active_campaigns': 1}}
path = Path(runtime.name) / 'catalog.json'
path.write_text(json.dumps([commercial]))
os.environ['CAMPAIA_PLAN_CATALOG_PATH'] = str(path)
os.environ['GEMINI_API_KEY'] = ''
os.environ['ASAAS_API_KEY'] = ''
app = create_app(env='test', db_path=str(Path(runtime.name) / 'runtime.db'))
app.state.campaia.id_token_verifier = DeterministicTestIdTokenVerifier()
app.state.campaia.allowed_origins = frozenset({origin})

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ['CAMPAIA_E2E_PORT']), log_level='warning')
