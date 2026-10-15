"""Entitlement enforcement from the contracted subscription snapshot, never a tenant ID."""
from datetime import datetime, timezone

from campaia_core.states import CampaignState
from campaia_core.subscription import SubscriptionStatus, refresh_trial_status, entitlement_access_is_active
from .errors import ApiError
from .metered_execution import commercial_subscription
from .billing_receipts import payment_access_is_blocked

ACTIVE_CAMPAIGN_STATES = frozenset({CampaignState.PUBLISHING, CampaignState.ACTIVE, CampaignState.OPTIMIZING})


def contracted_limits(state, tenant_id):
    sub = commercial_subscription(state, tenant_id)
    if sub is None:
        return None
    now = datetime.now(timezone.utc)
    sub = refresh_trial_status(sub, now=now)
    if not entitlement_access_is_active(sub, now=now) or payment_access_is_blocked(state, sub, at=now):
        raise ApiError('BILLING_ACCESS_REQUIRED', 'A expansão exige trial ou assinatura vigente.', status_code=409)
    if sub.status is SubscriptionStatus.TRIAL:
        users = sub.plan.credit_policy.trial_max_users
        campaigns = sub.plan.credit_policy.trial_max_active_campaigns
    else:
        users = sub.plan.effective_max_users
        campaigns = sub.plan.entitlements.max_active_campaigns if sub.plan.entitlements else None
    if users is None or campaigns is None:
        raise ApiError('BILLING_TERMS_UNAVAILABLE', 'Limites do contrato não configurados.', status_code=503)
    # A scheduled downgrade must remain feasible before it takes effect.
    if sub.pending_plan is not None:
        target = sub.pending_plan
        if target.effective_max_users is not None:
            users = min(users, target.effective_max_users)
        if target.entitlements and target.entitlements.max_active_campaigns is not None:
            campaigns = min(campaigns, target.entitlements.max_active_campaigns)
    return users, campaigns


def enforce_member_capacity(state, tenant_id, *, include_pending=True, after_add=False):
    limits = contracted_limits(state, tenant_id)
    if limits is None:
        return
    occupied = state.organizations.active_membership_count(tenant_id)
    pending = state.organizations.pending_invitation_count(tenant_id) if include_pending else 0
    total = occupied + pending
    if total > limits[0] or (not after_add and total == limits[0]):
        raise ApiError('QUOTA_EXHAUSTED', 'Limite de usuários do contrato atingido, incluindo convites pendentes.',
                       status_code=409, details={'max_users': limits[0]})


def enforce_campaign_capacity(state, tenant_id, record):
    sub = commercial_subscription(state, tenant_id)
    if sub is not None and payment_access_is_blocked(state, sub, at=datetime.now(timezone.utc)):
        raise ApiError('BILLING_ACCESS_REQUIRED', 'Pagamento do período em revisão; nova publicação/expansão indisponível.', status_code=409)
    if record.campaign.state in ACTIVE_CAMPAIGN_STATES:
        return  # Never pause or revoke an existing campaign because of a counter read.
    limits = contracted_limits(state, tenant_id)
    if limits is None:
        return
    occupied = sum(r.campaign.state in ACTIVE_CAMPAIGN_STATES for r in state.campaigns.list_for_tenant(tenant_id))
    if occupied >= limits[1]:
        raise ApiError('QUOTA_EXHAUSTED', 'Limite de campanhas ativas do contrato atingido.',
                       status_code=409, details={'max_active_campaigns': limits[1]})
