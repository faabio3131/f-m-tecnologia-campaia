# V2-16.5 — CampaIA Fiscal Integration — Evidence and Blocker

Date: 2026-09-13

## Pre-flight

- repository: `faabio3131/CampaIA`;
- baseline branch: `main`;
- baseline SHA: `b4529a803da307ecd79539a350c364a31739cbbe`;
- integration branch: `feat/fisc-v2-16-campaia-integration`;
- no open PR existed at the start of this block.

## Finding

The current CampaIA runtime models campaign creation/management, ad-platform connections, budgets, spend, approvals, autonomy, reconciliation, outbox, audit and related marketing operations.

It does **not** currently contain an authoritative CampaIA-owned billing/subscription/payment domain that can prove one of the following commercial facts:

- CampaIA service invoiceable amount;
- CampaIA SaaS subscription charge;
- CampaIA payment settlement;
- billing competence tied to CampaIA revenue;
- contracting customer fiscal identity for CampaIA own revenue.

Campaign budget and media spend are customer advertising resources and are not CampaIA revenue. They must not be reused as fiscal revenue authority.

## Safe work completed

A fail-closed adapter seam was added at `backend/campaia_core/fiscal_handoff.py`.

It accepts only an explicit `SettledOwnBillingFact`, never campaign budget or media spend. When such a future authoritative fact exists, it maps only:

- host namespace `fm.campaia`;
- pack `campaia`;
- `service-billing` -> `service` + `nfse`;
- `saas-billing` -> `saas_billing` + `nfse`;
- deterministic idempotency;
- `PENDING_CAPABILITY`;
- mandatory fiscal binding and readiness before issuance.

It does not select provider, municipality, ISS rule, tax rate, withholding, production readiness or homologation.

## Formal blocker

Runtime integration cannot be completed until CampaIA has an authoritative own-billing/payment source. Creating a synthetic subscription/payment flow solely to make fiscal integration appear complete would invent business behavior and is prohibited.

Formal state for V2-16.5 after technical certification:

**BLOQUEADO PARCIAL — ADAPTER FISCAL INTERNO IMPLEMENTADO/CERTIFICÁVEL; AUTORIDADE REAL DE FATURAMENTO/PAGAMENTO PRÓPRIO AINDA INEXISTENTE.**
