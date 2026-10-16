"""Append-only provider-attempt budget evidence, separate from commercial credits.

Known units may be simulator data or estimates based on unverified rates. Unknown
cost is retained as a budget hold, never treated as zero or expired automatically.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from uuid import uuid4

from campaia_core.ai_gateway import CostObservation, assert_no_credentials
from campaia_core.errors import TenantIsolationViolation


class PersistentAICostLedger:
    accounts_cost = True

    def __init__(self, state, *, namespace):
        self.state = state
        self.namespace = namespace
        self._journal = state.db.table('ai_cost_journal')
        self._caps = state.db.table('ai_cost_caps')

    def _id(self, tenant, *parts):
        if not tenant:
            raise TenantIsolationViolation('AI cost evidence requires tenant.')
        return sha256(json.dumps([self.namespace, tenant, *parts], sort_keys=True).encode()).hexdigest()

    def _rows(self, tenant):
        return [record for _id, _tenant, record in self._journal.rows_for_tenant(tenant)
                if record['namespace'] == self.namespace]

    def _append(self, tenant, identity, record):
        if self._journal.get_for_tenant(identity, tenant) is not None:
            raise ValueError('Duplicate AI cost event.')
        self._journal.put(identity, tenant, {**record, 'namespace': self.namespace,
                                           'recorded_at': datetime.now(timezone.utc)})

    def _stats(self, tenant, run_id=None):
        rows = self._rows(tenant)
        if run_id is not None:
            rows = [r for r in rows if r.get('run_id') == run_id]
        starts = {row['attempt_id']: row for row in rows if row['kind'] == 'START'}
        outcomes = {row['attempt_id']: row for row in rows if row['kind'] == 'OUTCOME'}
        known = sum((r['observation']['cost_units'] for r in outcomes.values()
                     if r['observation']['cost_units'] is not None), Decimal('0'))
        known += sum((r['amount'] for r in rows if r['kind'] == 'MANUAL_CHARGE'), Decimal('0'))
        held = sum((r['reserved'] for key, r in starts.items()
                    if key not in outcomes or outcomes[key]['observation']['cost_units'] is None), Decimal('0'))
        return known, held

    def cap(self, tenant):
        record = self._caps.get_for_tenant(self._id(tenant, 'cap'), tenant)
        return record['cap'] if record is not None else None

    def set_cap(self, tenant, cap):
        if not isinstance(cap, Decimal) or not cap.is_finite() or cap < 0:
            raise ValueError('AI cost cap must be a finite non-negative Decimal.')
        identity = self._id(tenant, 'cap')
        event = self._id(tenant, 'cap-change', uuid4().hex)
        def save():
            self._caps.put(identity, tenant, {'namespace': self.namespace, 'cap': cap})
            self._append(tenant, event, {'kind': 'CAP_CHANGED', 'amount': cap})
            self.state.audit.append(tenant_id=tenant, actor='ai-cost-config', actor_kind='SYSTEM',
                action='AI_COST_CAP_CONFIGURED', target=self.namespace,
                details={'cap_budget_units': str(cap), 'actual_margin_validated': False})
            return {'configured': True}
        self.state.idempotency.execute(tenant, 'ai-cost-cap:' + event, save)

    def used(self, tenant):
        return self._stats(tenant)[0]

    def remaining(self, tenant):
        cap = self.cap(tenant)
        if cap is None:
            return None
        known, held = self._stats(tenant)
        return cap - known - held

    def would_exceed(self, tenant, amount):
        remaining = self.remaining(tenant)
        return remaining is not None and amount > remaining

    def charge(self, tenant, amount):
        if not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0:
            raise ValueError('AI cost units must be a finite non-negative Decimal.')
        identity = self._id(tenant, 'manual-charge', uuid4().hex)
        def append():
            self._append(tenant, identity, {'kind': 'MANUAL_CHARGE', 'amount': amount,
                                           'basis': 'UNVERIFIED_ESTIMATE'})
            return {'charged': True}
        self.state.idempotency.execute(tenant, 'ai-cost-charge:' + identity, append)

    def _outside_transaction(self):
        if self.state.db.in_transaction:
            raise RuntimeError('Provider attempt requires a committed cost claim outside the caller transaction.')

    def begin_attempt(self, request, run_id, index, provider):
        self._outside_transaction()
        assert_no_credentials(provider)
        attempt = self._id(request.tenant_id, run_id, index)
        start_id = self._id(request.tenant_id, 'start', attempt)
        # Never replay an already claimed provider attempt.
        if self._journal.get_for_tenant(start_id, request.tenant_id) is not None:
            return False
        def reserve():
            known, held = self._stats(request.tenant_id, run_id)
            remaining_request = request.max_cost_units - known - held
            remaining_tenant = self.remaining(request.tenant_id)
            if remaining_request <= 0 or (remaining_tenant is not None and remaining_request > remaining_tenant):
                return {'allowed': False}
            self._append(request.tenant_id, start_id, {'kind': 'START', 'run_id': run_id,
                'attempt_id': attempt, 'request_id': request.request_id, 'task': request.task.value,
                'prompt_version': request.prompt_version, 'provider': provider, 'index': index,
                'max_cost_units': request.max_cost_units,
                'reserved': remaining_request})
            self.state.audit.append(tenant_id=request.tenant_id, actor='ai-cost-observer', actor_kind='SYSTEM',
                action='AI_COST_ATTEMPT_RESERVED', target=attempt,
                details={'reserved_budget_units': str(remaining_request), 'actual_cost_confirmed': False})
            return {'allowed': True}
        result, replay = self.state.idempotency.execute(request.tenant_id, 'ai-cost-start:' + start_id, reserve)
        return result['allowed'] and not replay

    def finish_attempt(self, request, run_id, index, observation, outcome):
        self._outside_transaction()
        if not isinstance(observation, CostObservation):
            raise ValueError('Invalid AI cost observation.')
        attempt = self._id(request.tenant_id, run_id, index)
        start_id = self._id(request.tenant_id, 'start', attempt)
        outcome_id = self._id(request.tenant_id, 'outcome', attempt)
        fingerprint = sha256(json.dumps([asdict(observation), outcome], sort_keys=True, default=str).encode()).hexdigest()
        def finish():
            start = self._journal.get_for_tenant(start_id, request.tenant_id)
            if (start is None or start['request_id'] != request.request_id
                    or start['task'] != request.task.value or start['max_cost_units'] != request.max_cost_units
                    or start['prompt_version'] != request.prompt_version):
                raise ValueError('AI cost observation has no matching committed dispatch.')
            self._append(request.tenant_id, outcome_id, {'kind': 'OUTCOME', 'run_id': run_id,
                'attempt_id': attempt, 'outcome': outcome, 'observation': asdict(observation)})
            self.state.audit.append(tenant_id=request.tenant_id, actor='ai-cost-observer', actor_kind='SYSTEM',
                action='AI_COST_OBSERVED', target=attempt,
                details={'basis': observation.basis, 'quantified': observation.cost_units is not None,
                         'budget_units': str(observation.cost_units) if observation.cost_units is not None else None,
                         'actual_margin_validated': False})
            return {'recorded': True, 'fingerprint': fingerprint}
        result, _ = self.state.idempotency.execute(request.tenant_id, 'ai-cost-finish:' + outcome_id, finish)
        if result['fingerprint'] != fingerprint:
            raise ValueError('Conflicting observation for an immutable AI attempt.')

    def report(self, tenant):
        rows = self._rows(tenant)
        known, held = self._stats(tenant)
        starts = [r for r in rows if r['kind'] == 'START']
        outcomes = [r for r in rows if r['kind'] == 'OUTCOME']
        basis = {}
        for row in outcomes:
            observation = row['observation']
            bucket = basis.setdefault(observation['basis'], {'attempts': 0, 'known_budget_units': Decimal('0')})
            bucket['attempts'] += 1
            bucket['known_budget_units'] += observation['cost_units'] or Decimal('0')
        return {'namespace': self.namespace, 'known_budget_units': str(known),
            'held_budget_units': str(held), 'configured_cap': str(self.cap(tenant)) if self.cap(tenant) is not None else None,
            'attempts': len(starts), 'observed_attempts': len(outcomes),
            'basis': {key: {'attempts': value['attempts'], 'known_budget_units': str(value['known_budget_units'])}
                      for key, value in basis.items()},
            'cost_completeness': 'INCOMPLETE' if held else 'OBSERVED_BUDGET_UNITS_ONLY',
            'margin_state': 'NOT_MEASURED', 'current_prices_verified': False,
            'ai_20_percent_validated': False, 'direct_30_percent_validated': False}
