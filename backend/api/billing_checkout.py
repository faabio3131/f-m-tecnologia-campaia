"""A read-only, tenant-safe financial view, shared by review and issue validation."""
from hashlib import sha256
from decimal import Decimal
import json
from .errors import ApiError


def checkout_quote(state, charge):
    plan = charge.commercial_plan
    if plan is None or plan.credit_policy is None:
        raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Snapshot comercial incompleto; concilie antes de emitir.', status_code=503)
    schedule = state.subscriptions[charge.tenant_id].paid_cycle_schedule
    period = (schedule.bounds(charge.commercial_cycle_index)
              if schedule and schedule.anchor_at and schedule.lifecycle_id == charge.commercial_lifecycle_id else None)
    organization = state.organizations.get_organization(charge.tenant_id)
    payload = {
        'organization_name': organization.tenant.name if organization else None,
        'holder_document_masked': '***' + charge.customer_document[-4:],
        'billing_id': charge.billing_id, 'competence': charge.competence,
        'amount': str(charge.amount.quantize(Decimal('0.01'))), 'currency': charge.currency,
        'plan_id': plan.plan_id, 'plan_name': plan.name,
        'included_credits': int(plan.included_credits),
        'extra_credit_price': str(plan.extra_credit_unit_price.quantize(Decimal('0.01'))),
        'action_weights': [{'action': name, 'credits': credits} for name, credits in plan.credit_policy.action_weights],
        'policy_version': plan.credit_policy.version,
        'purpose': charge.purpose.value, 'cycle_index': charge.commercial_cycle_index,
        'due_at': charge.commercial_due_at.isoformat() if charge.commercial_due_at else None,
        'period_starts_at': period[0].isoformat() if period else None,
        'period_ends_at': period[1].isoformat() if period else None,
        'lines': [{'description': item.description, 'amount': str(item.amount.quantize(Decimal('0.01')))} for item in charge.line_items],
        'provider': charge.commercial_gateway_provider or state.billing_gateway.provider,
        'mode': charge.commercial_gateway_mode or state.billing_gateway.mode.value,
    }
    # Only the presented financial terms/environment; never expose a CPF/document hash.
    payload['fingerprint'] = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload
