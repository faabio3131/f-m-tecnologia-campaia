"""CAMPAIA BFF/API layer.

Thin HTTP adapter over the frozen, tested domain layer in `campaia_core`. This package
owns no business logic: every mutation is a call into a real domain engine
(states.Campaign, budget.BudgetEngine, policy.PolicyEngine, saga.PublicationSaga,
permissions.authorize/can_approve, autonomy.evaluate, infra.IdempotencyStore/
CapabilityRegistry). The only things genuinely implemented at this layer are things that
have no domain module: brand profile storage, connection registry, campaign/approval
repositories, and the audit log.

Built on Starlette (not FastAPI): FastAPI could not be installed in this sandbox because
pypi.org is blocked by the environment's network egress allowlist (confirmed via both
`pip` and `uv`, both returning 403). Starlette is the ASGI framework FastAPI itself wraps,
and it was already present in this environment, so the routing/dependency/response shape
below mirrors what a FastAPI app would look like as closely as Starlette allows.
"""
