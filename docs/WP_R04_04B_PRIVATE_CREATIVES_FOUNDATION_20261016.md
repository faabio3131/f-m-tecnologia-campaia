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

## Continuação desta PR (16/10/2026)
- Definido contrato puro CreativeStateTransition com arestas permitidas e revision CAS para aplicação futura sob row lock F3.
- Proibidas transições que saltem geração/storage, rearmem entrega/deleção ou convertam falhas em sucesso.
- Testes de transições válidas, inválidas e revisão fora de faixa.
- **Ainda não existe repository PostgreSQL nem efeito GCS de criativos.** O contrato não é persistência transacional, nem deve ser apresentado como tal. Próximo incremento requer integração com padrões reais de migration/transactions já presentes no repositório e testes PostgreSQL dedicados.
- Sem merge, migration aplicada, deploy, credenciais ou cobrança real.

## Incremento de persistência F3 (ainda PARTIAL)
- `api.creative_repository.CreativeRepository`: operações tenant-scoped pelo `RecordTable` já existente; claim de quota e ID em transação, advisory lock por tenant; replay não faz nova reserva; updates de estado validam revision CAS.
- Testes com banco SQLite real: restart, replay, quota concorrente, cross-tenant, transições, geração obrigatória antes de STORED.
- **Não afirmar PostgreSQL verificado**: `PostgresDatabase.table("creative_assets")` requer migration versionada ainda não criada e testes de integração PostgreSQL. CI do novo HEAD pendente.
- Sem storage dispatch, GCS, créditos, API pública ou migration real. A fonte foi atualizada sem ativação operacional.
