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

## Migração PostgreSQL versionada (fonte, ainda sem promoção)
- Adicionada `010_creative_assets.up.sql` e rollback controlado `010_creative_assets.down.sql`. Tabela de runtime segregada por tenant com índices, trigger de tenant imutável e guardas DB para manifesto imutável, transições e revision CAS.
- `PostgresDatabase` passa a permitir a tabela apenas após migration explícita, sem criação implícita no startup.
- Adicionado teste real no job PostgreSQL 16 existente: corrida de reserva entre duas instâncias independentes, quota, replay, cross-tenant, recuperação de estado após reabrir conexão e proteção de trigger contra atualização forjada.
- CI no HEAD final ainda necessária. Estes testes não simulam storage, provider ou cobrança e não autorizam aplicar migration em produção.

## Integração do transporte privado (fatia interna)
- `CreativeStorageIdentity` adapta identidade do criativo ao `AssetManifest` e `GCSAssetStorage` existentes; nenhum segundo cliente GCS, nenhum bucket público ou alteração de IAM.
- `CreativePrivateStorage` exige manifesto PNG verificado e transição F3 GENERATING→STORAGE_PENDING comprometida antes de uma única chamada upload_once.
- Replays executam apenas observação; erro ou ausência de objeto permanece pendente, com quota reservada. Sem débito de crédito comercial e sem chamada a modelo.
- Testes simulados isolam upload único, UNKNOWN→observe, ausência pós-UNKNOWN, integridade, contexto incompatível e ausência de I/O sob transação. São simuladores, não prova GCS real.
- Limitações: armazenamento de bytes para reconciliação após reinício completo ainda precisa de fonte durável segura; API/Web de criativos, billing atômico e homologação GCS/ADC continuam TARGET.

## Recuperação após reinício — delta
- Manifesto normalizado inclui MD5 canônico além de SHA-256, persistido na mesma transação F3 de claim; habilita reconstruir o AssetManifest esperado sem bytes originais no novo processo.
- `reconcile_after_restart(identity)` lê manifesto persistente, executa apenas GET metadata via storage.observe e finaliza com geração imutável. Se ausência, erro ou MD5 ausente: não repete POST, mantém STORAGE_PENDING e quota.
- Testes adicionados para nova conexão SQLite após reinício, confirmação de geração sem bytes e ausência de objeto sem postagem duplicada. Validação CI no novo HEAD obrigatória. Nenhuma ativação real GCS.


## Implementação integrada API/Web + custo comercial — evidência atualizada
- As descrições anteriores deste documento que diziam "sem POST/API/Web" estão SUPERSEDED pelos incrementos posteriores da PR #73. Não removem o histórico incremental.
- Fluxo opt-in: BFF com autorização de tenant/unidade e versão da campanha → cotação/confirmação F5 → reservation idempotente F3 → AI Gateway/F3 cost journal (provider Gemini imagem habilitado explicitamente) → PNG normalizado → metadata+quota por tenant → storage privado GCS com fence de envio único → entrega e SETTLE F5 atômicos com auditoria.
- Imagem disponibilizada apenas por GET autenticado, geração GCS pinada e cache privado. Web exibe inventário, confirmação comercial e recuperação de pendência; não publica campanha.
- Reconciliação de upload incerto após reinício: observação de metadata imutável sem bytes em memória; transição STORED CAS e SETTLE F5 pela operação comercial persistida sem segundo POST.
- Testes contra SIMULATOR explícito e banco persistente: happy path, replay, quota, cross-tenant, GET PNG, ACK de upload perdido, reconciliação e débito comercial único. Sem credenciais reais nem bucket de produção.
- CI verde no commit `20acfe93248e26a4be74cf3b63ecfb6e5f8f8758`: Backend #410, Frontend #349 e F4 #244.
- **Status PARTIAL:** após esse HEAD, nova alteração de UX/documentação exige CI; F7 G7 tem pendências de formatos por canal, edição/upload alternativo, políticas/preview, lifecycle/delete e governança de custos incertos. GCS/Gemini reais ficam EXTERNAL_INFRASTRUCTURE/EXTERNAL_CREDENTIAL até fase externa final.
