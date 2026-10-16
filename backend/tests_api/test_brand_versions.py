"""Editing preserves brand history and rejects stale, rebound or foreign requests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from api.db import encode, decode
from api.brand_versions import version_key
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, VIEWER, unique_idem


BODY = {'name': 'Marca inicial', 'tone': 'claro', 'colors': ['#112233'],
        'differentiators': ['Atendimento local'], 'restrictions': ['Sem promessa de retorno garantido']}


class BrandVersionTests(BillingCreditHarness, unittest.TestCase):
    def create(self, headers=None, body=None, client=None):
        return (client or self.client).post('/brand-profiles',
            headers=headers or {**OWNER, **unique_idem()}, json=body or BODY)

    def update(self, identity, version=1, headers=None, client=None, **fields):
        return (client or self.client).put('/brand-profiles/' + identity,
            headers=headers or {**OWNER, **unique_idem()},
            json={**BODY, **fields, 'expected_version': version})

    def peer(self):
        other = TestClient(create_app(env='test', db_path=str(self.path)))
        self.addCleanup(other.app.state.campaia.db._conn.close)
        return other

    def test_update_keeps_identity_creation_time_and_exact_prior_revision(self):
        first = self.create().json()
        changed = self.update(first['id'], tone='direto', name='Marca revisada')
        self.assertEqual(changed.status_code, 200, changed.text)
        current = changed.json()
        self.assertEqual(current['id'], first['id'])
        self.assertEqual(current['created_at'], first['created_at'])
        self.assertEqual(current['version'], 2)
        self.assertIsNotNone(current['updated_at'])
        self.assertEqual(self.client.get('/brand-profiles/' + first['id'], headers=OWNER).json(), current)
        history = self.client.get('/brand-profiles/' + first['id'] + '/versions', headers=OWNER).json()
        self.assertEqual(history['items'], [current, first])
        self.assertIsNone(history['next_cursor'])

    def test_two_workers_have_one_winner_and_no_silent_overwrite(self):
        first = self.create().json()
        other = self.peer()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda client: self.update(first['id'], client=client,
                tone='a' if client is self.client else 'b'), [self.client, other]))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409], [r.text for r in responses])
        winner = next(r.json() for r in responses if r.status_code == 200)
        self.assertEqual(other.get('/brand-profiles/' + first['id'], headers=OWNER).json(), winner)
        self.assertEqual(len(other.get('/brand-profiles/' + first['id'] + '/versions', headers=OWNER).json()['items']), 2)
        self.assertEqual(sum(e.action == 'BRAND_PROFILE_UPDATE'
            for e in self.state.audit.list_for_tenant('demo-tenant')), 1)

    def test_create_replay_is_actor_body_and_unit_bound_without_creating_a_duplicate(self):
        headers = {**OWNER, **unique_idem()}
        first = self.create(headers=headers)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(self.create(headers=headers).json(), first.json())
        self.assertEqual(self.create(headers=headers, body={**BODY, 'name': 'other'}).status_code, 409)
        owner = self.state.tokens['demo-owner-token']
        self.state.tokens['brand-other-owner'] = replace(owner, user_id='brand-other-owner')
        self.assertEqual(self.create(headers={**headers, 'Authorization': 'Bearer brand-other-owner'}).status_code, 409)
        self.state.tokens['brand-other-unit'] = replace(owner, business_unit_id='brand-other-unit')
        self.assertEqual(self.create(headers={**headers, 'Authorization': 'Bearer brand-other-unit'}).status_code, 409)
        self.assertEqual(len(self.client.get('/brand-profiles', headers=OWNER).json()), 1)

    def test_update_replay_preserves_original_response_after_later_edit_and_rejects_rebinding(self):
        first = self.create().json()
        headers = {**OWNER, **unique_idem()}
        changed = self.update(first['id'], headers=headers, tone='second')
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(self.update(first['id'], version=2, tone='third').status_code, 200)
        self.assertEqual(self.update(first['id'], headers=headers, tone='second').json(), changed.json())
        self.assertEqual(self.update(first['id'], headers=headers, tone='different').status_code, 409)
        another = self.create(body={**BODY, 'name': 'Another brand'}).json()
        self.assertEqual(self.update(another['id'], headers=headers, tone='second').status_code, 409)
        self.assertEqual(self.client.get('/brand-profiles/' + another['id'], headers=OWNER).json()['version'], 1)

    def test_cross_tenant_rbac_and_client_authority_are_rejected(self):
        first = self.create().json()
        for suffix in ('', '/versions'):
            self.assertEqual(self.client.get('/brand-profiles/' + first['id'] + suffix, headers=OTHER_OWNER).status_code, 404)
        self.assertEqual(self.update(first['id'], headers={**OTHER_OWNER, **unique_idem()}).status_code, 404)
        self.assertEqual(self.update(first['id'], headers={**VIEWER, **unique_idem()}).status_code, 403)
        self.assertEqual(self.client.get('/brand-profiles/' + first['id'] + '/versions', headers=VIEWER).status_code, 200)
        tampered = {**BODY, 'expected_version': 1, 'tenant_id': 'other'}
        self.assertEqual(self.client.put('/brand-profiles/' + first['id'],
            headers={**OWNER, **unique_idem()}, json=tampered).status_code, 422)
        for version in (True, 1.5, 0, '1'):
            result = self.client.put('/brand-profiles/' + first['id'],
                headers={**OWNER, **unique_idem()}, json={**BODY, 'expected_version': version})
            self.assertEqual(result.status_code, 422, result.text)

    def test_failed_commit_rolls_back_current_revision_snapshot_and_audit_then_same_key_retries(self):
        first = self.create().json()
        original = self.state.audit.append
        def fail(**event):
            original(**event)
            if event['action'] == 'BRAND_PROFILE_UPDATE':
                raise RuntimeError('injected brand commit')
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.state.audit, 'append', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'injected brand commit'):
                self.update(first['id'], headers=headers)
        self.assertEqual(self.client.get('/brand-profiles/' + first['id'], headers=OWNER).json(), first)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', version_key(first['id'], 2)))
        self.assertFalse(any(e.action == 'BRAND_PROFILE_UPDATE' for e in self.state.audit.list_for_tenant('demo-tenant')))
        self.assertEqual(self.update(first['id'], headers=headers).status_code, 200)

    def test_legacy_profile_read_is_not_a_fabricated_history_write_and_first_edit_preserves_it(self):
        profile = self.state.brand_profiles.create('demo-tenant', **BODY)
        identity = profile.brand_profile_id
        before = self.client.get('/brand-profiles/' + identity, headers=OWNER).json()
        self.assertIsNone(before['updated_at'])
        self.assertEqual(before['version'], 1)
        self.assertIsNone(self.state.idempotency.get('demo-tenant', version_key(identity, 1)))
        self.assertEqual(self.client.get('/brand-profiles/' + identity + '/versions', headers=OWNER).json()['items'], [before])
        self.assertIsNone(self.state.idempotency.get('demo-tenant', version_key(identity, 1)))
        self.assertEqual(self.update(identity, tone='new tone').status_code, 200)
        other = self.peer()
        history = other.get('/brand-profiles/' + identity + '/versions', headers=OWNER).json()['items']
        self.assertEqual(history[-1], before)
        baseline = self.state.idempotency.get('demo-tenant', version_key(identity, 1)).result
        self.assertIsNone(baseline['editor_id'])
        self.assertIsNone(baseline['recorded_at'])

    def test_missing_or_divergent_history_cannot_be_silently_replaced(self):
        first = self.create().json()
        current = self.state.brand_profiles.get('demo-tenant', first['id'])
        current.tone = 'changed by a stale writer fixture'
        blocked = self.update(first['id'])
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(blocked.json()['code'], 'BRAND_HISTORY_INCOMPLETE')
        current.version = 3
        missing = self.client.get('/brand-profiles/' + first['id'] + '/versions', headers=OWNER)
        self.assertEqual(missing.status_code, 503, missing.text)

    def test_history_paginates_without_duplicates_and_cursors_do_not_jump_beyond_current(self):
        first = self.create().json()
        for version in range(1, 52):
            response = self.update(first['id'], version=version, tone='revision-' + str(version + 1))
            self.assertEqual(response.status_code, 200, response.text)
        endpoint = '/brand-profiles/' + first['id'] + '/versions'
        page = self.client.get(endpoint, headers=OWNER).json()
        self.assertEqual(len(page['items']), 50)
        self.assertEqual(page['items'][0]['version'], 52)
        next_page = self.client.get(endpoint + '?cursor=' + page['next_cursor'], headers=OWNER).json()
        self.assertEqual([r['version'] for r in next_page['items']], [2, 1])
        self.assertIsNone(next_page['next_cursor'])
        for cursor in ('53', '0', '-1', '1.0', 'x', '9' * 100):
            self.assertEqual(self.client.get(endpoint + '?cursor=' + cursor, headers=OWNER).status_code, 422)
        page['items'][0]['colors'].append('client-only mutation')
        self.assertNotIn('client-only mutation', str(self.client.get(endpoint, headers=OWNER).json()))

    def test_input_limits_and_output_history_do_not_truncate_legacy_data(self):
        for changes in ({'name': 'x' * 121}, {'tone': 'x' * 201},
                        {'colors': ['x'] * 65}, {'restrictions': ['x' * 2001]}):
            response = self.create(body={**BODY, **changes})
            self.assertEqual(response.status_code, 422, response.text)
        old = self.state.brand_profiles.create('demo-tenant', **{**BODY, 'name': 'legacy-' + 'x' * 200})
        response = self.client.get('/brand-profiles/' + old.brand_profile_id, headers=OWNER)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['name'], old.name)

    def test_brand_codec_preserves_constructor_compatibility_and_checks_metadata(self):
        profile = self.state.brand_profiles.create('demo-tenant', **BODY)
        encoded = encode(profile)
        self.assertIn('brand_v1', encoded)
        self.assertNotIn('version', encoded['fields'])
        self.assertEqual(decode(encoded).version, 1)
        encoded['brand_v1']['version'] = 2
        self.assertEqual(decode(encoded).version, 2)
        legacy = {key: value for key, value in encoded.items() if key != 'brand_v1'}
        self.assertEqual(decode(legacy).version, 1)
        encoded['brand_v1']['unexpected'] = 'not allowed'
        with self.assertRaises(ValueError):
            decode(encoded)

    def test_previous_create_response_can_replay_without_allocating_another_profile(self):
        profile = self.state.brand_profiles.create('demo-tenant', **BODY)
        from api.helpers import serialize_brand_profile
        previous = serialize_brand_profile(profile).model_dump(mode='json')
        key = 'fixture-old-create-key'
        self.state.idempotency.execute('demo-tenant', 'http:create_brand_profile:' + key, lambda: previous)
        replay = self.create(headers={**OWNER, 'Idempotency-Key': key})
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json(), previous)
        self.assertEqual(len(self.client.get('/brand-profiles', headers=OWNER).json()), 1)
