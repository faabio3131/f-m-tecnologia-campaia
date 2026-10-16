# WP-R04-04B — Creative private persistence foundation (slice 1)

CURRENT confirmed: main@2458cb3da177537cc88b68b2cc156ce5e6bf3800.
PR #72 post-merge: Backend #328, Frontend #266, Platform F4 #162 green, evidenced in GitHub Actions screenshot from director on 2026-10-16.

Status: PARTIAL. No production execution or G7 certification.

## Current vs target
- Existing: image provider opt-in OFF, existing brand private-storage primitives and isolated Linux PNG normalization, F3 durable financial/AI foundations.
- Missing for this WP: creative-specific identity, durable creative manifest rows, storage dispatch fences, uncertain-result readback, quotas, read/delete authorization, cost/credit atomic delivery.
- This slice adds ONLY the creative-specific immutable identity/manifest/proof and tests. It is deliberately not a second storage gateway.

## Implemented
- CreativeIdentity: tenant, business unit, campaign, campaign version and generated creative UUID; opaque deterministic object prefix distinct from brand assets.
- CreativeManifest: normalized PNG verified before manifest creation; SHA256, size, dimensions, model/provider, request reference; metadata carries hashes, not secrets or names.
- CreativeStoredProof: requires a nonzero strictly formatted immutable storage generation.
- Tests exercise tenant/unit/campaign/version/creative segregation, tampered bytes and metadata, malformed identities and generations.

## Not yet implemented / blockers
- Durable F3 PostgreSQL schema + transactional claim, quota, state machine and audit (requires code integration and PostgreSQL tests).
- GCS adapter integration and immutable preconditioned upload/observe/read/delete; on UNKNOWN result, GET readback rather than blind redispatch.
- Real runtime GCS/ADC/worker proof: EXTERNAL_INFRASTRUCTURE.
- Provider generation transaction, 15-credit commercial settlement and budget observation; never charge without proven delivery; UNKNOWN keeps reserve.
- Authenticated API, Web and signed/private preview; cross-tenant E2E and server authorization.
- Production migration/deploy/credentials require explicit authorization.
- No real Google Gemini or storage call in this slice.

## Gate
Run Backend, Frontend, F4 CI on exact PR head. Do not merge until evidence and director's express authorization. This isolated slice is PARTIAL; do not mark WP-R04-04B or G7 DONE_VERIFIED.
