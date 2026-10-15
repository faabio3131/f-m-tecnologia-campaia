from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from api.main import create_app
from api.errors import ApiError
from campaia_core.states import CampaignState
from tests_api.test_billing_credit_integration import BillingCreditHarness
from tests_api.test_helpers import OWNER, OTHER_OWNER, with_step_up, unique_idem, DEFAULT_BRIEF


class MeteredStrategyTests(BillingCreditHarness, unittest.TestCase):
    def test_subscription_closed_during_generation_discards_delivery_and_releases_credit(self):
        original = self.state.agent_runner.run
        def closed_before_delivery(*args, **kwargs):
            result = original(*args, **kwargs)
            canceled = self.client.post('/billing/subscription/cancel',
                headers={**with_step_up(OWNER), **unique_idem()}, json={'immediate': True})
            self.assertEqual(canceled.status_code, 200, canceled.text)
            return result
        initial = self.state.campaigns.get('demo-tenant', self.campaign).plan_version
        with patch.object(self.state.agent_runner, 'run', side_effect=closed_before_delivery):
            response = self.request()
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['code'], 'AI_SUBSCRIPTION_CHANGED')
        self.assertEqual(self.state.campaigns.get('demo-tenant', self.campaign).plan_version, initial)
        entries = self.state.credit_ledger.entries('demo-tenant')
        self.assertEqual(sum(entry.kind == 'SETTLE' for entry in entries), 0)
        self.assertEqual(sum(entry.kind == 'RELEASE' for entry in entries), 1)

    def setUp(self):
        super().setUp()
        self.setup_subscription(trial=True)
        created = self.client.post('/briefs', headers={**OWNER, **unique_idem()}, json=DEFAULT_BRIEF)
        self.assertEqual(created.status_code, 202, created.text)
        self.campaign = created.json()['id']
        self.endpoint = f'/campaigns/{self.campaign}/plan/regenerate'

    def request(self, confirmation=None, headers=None):
        if confirmation is None:
            quote = self.client.get(f'/campaigns/{self.campaign}/plan/quote', headers=OWNER)
            self.assertEqual(quote.status_code, 200, quote.text)
            confirmation = {key: quote.json()[key] for key in ('cycle_id', 'policy_version', 'credits', 'extra_amount')}
        return self.client.post(self.endpoint, headers=headers or {**OWNER, **unique_idem()},
                                json={'credit_confirmation': confirmation})

    def test_reservation_commits_before_provider_and_delivery_settles_once(self):
        original = self.state.agent_runner.run
        def observed(*args, **kwargs):
            self.assertFalse(self.state.db.in_transaction)
            fresh = TestClient(create_app(env='test', db_path=str(self.path)))
            try:
                balance = fresh.get('/billing/usage', headers=OWNER).json()['balance']
                self.assertEqual(balance['reserved_credits'], 5)
                self.assertEqual(balance['consumed_credits'], 0)
            finally:
                fresh.app.state.campaia.db._conn.close()
            return original(*args, **kwargs)
        headers = {**OWNER, **unique_idem()}
        with patch.object(self.state.agent_runner, 'run', side_effect=observed) as provider:
            first = self.request(headers=headers)
            self.assertEqual(first.status_code, 202, first.text)
            second = self.request(headers=headers)
            self.assertEqual(second.json(), first.json())
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 5)
        self.assertEqual(self.usage().json()['balance']['reserved_credits'], 0)

    def test_quote_required_stale_price_and_quota_rejected_before_dispatch(self):
        with patch.object(self.state.agent_runner, 'run') as provider:
            missing = self.client.post(self.endpoint, headers={**OWNER, **unique_idem()}, json={})
            self.assertEqual(missing.status_code, 409)
            bad = self.request({'cycle_id': 'tampered', 'policy_version': 'wrong', 'credits': 1, 'extra_amount': '0.00'})
            self.assertEqual(bad.status_code, 409)
            self.assertEqual(provider.call_count, 0)
        for _ in range(6):
            self.assertEqual(self.request().status_code, 202)
        exhausted = self.client.get(f'/campaigns/{self.campaign}/plan/quote', headers=OWNER)
        self.assertEqual(exhausted.status_code, 409)
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 30)
        record = self.state.campaigns.get('demo-tenant', self.campaign)
        record.campaign.state = CampaignState.ACTIVE
        emergency = self.client.post('/kill-switch', headers={**OWNER, **unique_idem()},
            json={'scope': 'CAMPAIGN', 'target_id': self.campaign, 'reason': 'test emergency'})
        self.assertEqual(emergency.status_code, 202, emergency.text)
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 30)


    def test_known_failure_and_policy_rejection_release_without_consumption(self):
        with patch.object(self.state.agent_runner, 'run', side_effect=ApiError('VALIDATION_FAILED', 'invalid output')):
            response = self.request()
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 0)
        self.assertEqual(self.usage().json()['balance']['reserved_credits'], 0)
        class Blocked:
            outcome = type('Outcome', (), {'value': 'BLOCKED'})()
        with patch('api.routes_campaigns.PolicyEngine.evaluate', return_value=Blocked()):
            response = self.request()
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 0)
        self.assertEqual(self.state.campaigns.get('demo-tenant', self.campaign).plan_version, 0)

    def test_uncertain_outcome_stays_reserved_and_never_redispatches_after_restart(self):
        headers = {**OWNER, **unique_idem()}
        quote = self.client.get(f'/campaigns/{self.campaign}/plan/quote', headers=OWNER).json()
        confirmation = {key: quote[key] for key in ('cycle_id', 'policy_version', 'credits', 'extra_amount')}
        with patch.object(self.state.agent_runner, 'run', side_effect=RuntimeError('unknown external outcome')) as provider:
            self.assertEqual(self.request(confirmation, headers).status_code, 503)
            self.assertEqual(self.request(confirmation, headers).status_code, 503)
            self.assertEqual(provider.call_count, 1)
        fresh = TestClient(create_app(env='test', db_path=str(self.path)))
        try:
            with patch.object(fresh.app.state.campaia.agent_runner, 'run') as provider:
                retry = fresh.post(self.endpoint, headers=headers, json={'credit_confirmation': confirmation})
                self.assertEqual(retry.status_code, 503)
                self.assertEqual(provider.call_count, 0)
            self.assertEqual(fresh.get('/billing/usage', headers=OWNER).json()['balance']['reserved_credits'], 5)
        finally:
            fresh.app.state.campaia.db._conn.close()

    def test_gateway_timeout_status_keeps_reservation_instead_of_releasing(self):
        from campaia_core.agents import AgentFailure
        from campaia_core.ai_gateway import AIStatus
        failure = AgentFailure(agent='strategist', tenant_id='demo-tenant', status=AIStatus.TIMEOUT,
                               reason='external timeout')
        with patch.object(self.state.agent_runner, 'run', return_value=failure):
            response = self.request()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(self.usage().json()['balance']['reserved_credits'], 5)
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 0)

    def test_two_workers_same_operation_dispatch_only_once_and_recover_delivery(self):
        fresh = TestClient(create_app(env='test', db_path=str(self.path)))
        entered, complete = Event(), Event()
        original = self.state.agent_runner.run
        headers = {**OWNER, **unique_idem()}
        quote = self.client.get(f'/campaigns/{self.campaign}/plan/quote', headers=OWNER).json()
        body = {'credit_confirmation': {k: quote[k] for k in ('cycle_id', 'policy_version', 'credits', 'extra_amount')}}
        def blocked(*args, **kwargs):
            entered.set()
            if not complete.wait(timeout=10):
                raise RuntimeError('test coordination timeout')
            return original(*args, **kwargs)
        try:
            with patch.object(self.state.agent_runner, 'run', side_effect=blocked) as provider:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    running = pool.submit(self.client.post, self.endpoint, headers=headers, json=body)
                    self.assertTrue(entered.wait(timeout=5))
                    pending = fresh.post(self.endpoint, headers=headers, json=body)
                    self.assertEqual(pending.status_code, 503, pending.text)
                    complete.set()
                    first = running.result(timeout=5)
                self.assertEqual(first.status_code, 202, first.text)
                replay = fresh.post(self.endpoint, headers=headers, json=body)
                self.assertEqual(replay.json(), first.json())
                self.assertEqual(provider.call_count, 1)
        finally:
            complete.set()
            fresh.app.state.campaia.db._conn.close()

    def test_resource_authorization_precedes_replay_and_input_change_releases(self):
        headers = {**OWNER, **unique_idem()}
        self.assertEqual(self.request(headers=headers).status_code, 202)
        response = self.client.post(self.endpoint, headers={**OTHER_OWNER, **unique_idem()}, json={})
        self.assertEqual(response.status_code, 404)
        owner = self.state.tokens['demo-owner-token']
        self.state.tokens['same-tenant-other-unit'] = replace(owner, business_unit_id='other-unit')
        response = self.client.post(self.endpoint,
            headers={**headers, 'Authorization': 'Bearer same-tenant-other-unit'}, json={})
        self.assertEqual(response.status_code, 404)
        original = self.state.agent_runner.run
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            record = self.state.campaigns.get('demo-tenant', self.campaign)
            record.plan_version += 1
            return result
        with patch.object(self.state.agent_runner, 'run', side_effect=changed):
            self.assertEqual(self.request().status_code, 409)
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 5)
        self.assertEqual(self.usage().json()['balance']['reserved_credits'], 0)

    def test_campaign_limit_holds_slot_and_resume_does_not_consume_credits(self):
        first = self.state.campaigns.get('demo-tenant', self.campaign)
        first.campaign.state = CampaignState.ACTIVE
        created = self.client.post('/briefs', headers={**OWNER, **unique_idem()}, json=DEFAULT_BRIEF)
        second_id = created.json()['id']
        second = self.state.campaigns.get('demo-tenant', second_id)
        second.campaign.state = CampaignState.PAUSED
        response = self.client.post(f'/campaigns/{second_id}/resume', headers={**with_step_up(OWNER), **unique_idem()})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['code'], 'QUOTA_EXHAUSTED')
        self.assertEqual(self.usage().json()['balance']['consumed_credits'], 0)
        first.campaign.state = CampaignState.PAUSED
        resumed = self.client.post(f'/campaigns/{second_id}/resume', headers={**with_step_up(OWNER), **unique_idem()})
        self.assertEqual(resumed.status_code, 202, resumed.text)


class MemberCreditLimitTests(BillingCreditHarness, unittest.TestCase):
    def test_trial_blocks_new_invites_and_preexisting_invite_acceptance_atomically(self):
        from tests_api.test_commercial_onboarding import (
            make_client, onboard, TOK_OWNER_A, TOK_MEMBER, ORIGIN, mut_headers,
        )
        owner = make_client(db_path=str(self.path))
        member = make_client(db_path=str(self.path))
        try:
            created = onboard(owner, TOK_OWNER_A)
            self.assertEqual(created.status_code, 201, created.text)
            tenant = created.json()['organization']['tenant_id']
            csrf = created.json()['session']['csrf_token']
            invitation = owner.post('/member-invitations',
                headers=mut_headers(csrf, 'credit-limit-invite-before-trial'),
                json={'email': 'member@fresh.example', 'roles': ['VIEWER']})
            self.assertEqual(invitation.status_code, 201, invitation.text)
            token = invitation.json()['accept_token']
            fingerprint = owner.get('/billing/plans').json()['items'][0]['fingerprint']
            setup = owner.put('/billing/subscription', headers=mut_headers(csrf, 'credit-limit-trial-setup'),
                json={'plan_id': 'exemplo-essencial', 'customer_document': '11144477735', 'start_trial': True,
                      'initial_only': True, 'expected_plan_fingerprint': fingerprint})
            self.assertEqual(setup.status_code, 200, setup.text)
            blocked = owner.post('/member-invitations', headers=mut_headers(csrf, 'credit-limit-second-invite'),
                                 json={'email': 'another@fresh.example', 'roles': ['VIEWER']})
            self.assertEqual(blocked.status_code, 409, blocked.text)
            accepted = member.post('/onboarding/invitations/accept',
                headers={'Origin': ORIGIN, 'Idempotency-Key': 'credit-limit-accept-pending'},
                json={'id_token': TOK_MEMBER, 'accept_token': token})
            self.assertEqual(accepted.status_code, 409, accepted.text)
            state = owner.app.state.campaia
            self.assertEqual(state.organizations.active_membership_count(tenant), 1)
            self.assertEqual(state.organizations.pending_invitation_count(tenant), 1)
        finally:
            owner.app.state.campaia.db._conn.close()
            member.app.state.campaia.db._conn.close()
