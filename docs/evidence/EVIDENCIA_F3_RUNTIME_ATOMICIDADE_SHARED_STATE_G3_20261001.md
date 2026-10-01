# EVIDÊNCIA — F3 RUNTIME DE PRODUÇÃO / G3 — 01/10/2026

**WP:** WP-F03-01  
**Fase:** F3 — Persistência e Runtime de Produção  
**Gate:** G3  
**Status do Gate G3:** `DONE_VERIFIED`  
**Status residual da Fase F3:** `EXTERNAL_INFRASTRUCTURE` para Cloud SQL gerenciado, backup/restore operacional e medição real de RPO/RTO  
**Repositório:** `faabio3131/f-m-tecnologia-campaia`  
**Branch:** `reconciliation/campaia-final-takeover`  
**PR:** #31, Draft, não mergeada  
**HEAD funcional certificado:** `18b98c16d19127df2c9f842a3c7b171e997add02`

## 1. Critério oficial do Gate G3

O Gate G3 exige que o backend rode com 2+ réplicas sem perder sessão, OAuth state, idempotência, approval ou isolamento.

Esse critério está comprovado no CURRENT por testes reais contra PostgreSQL 16, incluindo processos Python separados executados simultaneamente. Isso fecha o gate técnico de runtime; não equivale a afirmar que Cloud SQL/staging/produção já existem.

## 2. CURRENT entregue

### PostgreSQL e migrations

- runtime PostgreSQL selecionável por `CAMPAIA_DATABASE_URL`;
- SQLite preservado somente como backend de compatibilidade para teste/dev;
- migration `001_runtime_store_schema`: schema CURRENT dos 14 stores persistentes;
- migration `002_tenant_isolation_guard`: proteção de ownership de tenant no banco;
- migration `003_distributed_rate_limit`: estado compartilhado de rate limit;
- migration runner versionado com `up`, `down` e `status`;
- CI executa migration completa, rollback completo e reaplicação em PostgreSQL 16 real;
- aplicação não cria schema de produção implicitamente no startup.

### Atomicidade, locks e crash/replay

- `PersistentIdempotencyStore.execute()` é a unidade de trabalho transacional;
- mutações críticas do mesmo tenant são serializadas por advisory lock PostgreSQL;
- mesma Idempotency-Key em conexões/processos concorrentes executa efeito exatamente uma vez;
- chaves diferentes do mesmo tenant são serializadas de forma conservadora para proteger invariantes;
- convite, IAM, publicação, budget, autonomy, approval e fluxos críticos relêem estado mutável dentro da fronteira protegida quando aplicável;
- processo encerrado abruptamente no meio de uma transação não deixa audit/idempotência parcialmente commitados; retry da mesma chave executa e commita uma única vez;
- `validateCampaign` e `createApproval` agora também exigem Idempotency-Key e possuem replay exato, com contrato e Web sincronizados.

### Shared state

Em PostgreSQL o CURRENT compartilha entre instâncias/processos:

- SessionStore;
- step-up state;
- OAuth Pending State com single-use atômico;
- idempotência;
- approvals e demais repositories persistentes;
- dedupe de webhook;
- rate limit do webhook Asaas.

O teste de G3 mantém dois processos separados vivos ao mesmo tempo: o processo A cria sessão, OAuth state e approval; o processo B lê/consome o estado compartilhado, confirma isolamento cross-tenant e revoga a sessão. A prova passa em PostgreSQL 16 real.

## 3. Tenant isolation no banco — decisão RLS x mecanismo equivalente

RLS foi avaliado e **não foi aplicado como política única indiscriminada**.

Motivo: nem todo store do runtime já possui tenant conhecido no primeiro lookup. `sessions`, por exemplo, é localizado por um ID opaco antes da resolução do vínculo ativo e pode trocar o tenant ativo da mesma sessão. Uma policy genérica baseada em um tenant GUC poderia bloquear fluxos legítimos ou levar a bypasses especiais.

O mecanismo adotado para o CURRENT é defesa em profundidade equivalente e explícita:

1. queries tenant-scoped usam `tenant_id` no predicado SQL;
2. `tenant_id` de rows tenant-owned é imutável após INSERT;
3. migration 002 instala triggers de banco que rejeitam tentativa de re-home cross-tenant;
4. `RecordTable.put()` também recusa colisão de ID pertencente a outro tenant;
5. testes negativos provam que leitura/delete/re-home com tenant errado falham;
6. `sessions` é exceção documentada ao trigger de imutabilidade porque o mesmo session ID pode legitimamente trocar o vínculo ativo; autorização da sessão permanece server-side e testada.

RLS por tabela poderá ser reavaliado em F16 se o modelo de conexão/contexto for refinado, mas não é necessário para afirmar o Gate G3 porque o isolamento exigido já está comprovado por mecanismo de banco + query scoping + testes cross-tenant.

## 4. Rate limiting distribuído

O único endpoint público sem autenticação de usuário, `/webhooks/asaas`, não usa mais contador process-local quando o runtime está em PostgreSQL.

`PostgresFixedWindowRateLimiter`:

- compartilha a janela entre réplicas/processos;
- usa advisory lock por chave;
- persiste somente SHA-256 da chave/origem, nunca o IP bruto apenas para rate limiting;
- mantém o limite global mesmo com dois processos concorrentes.

WAF, proteção de rede e DDoS multi-origem continuam pertencendo à infraestrutura/hardening de F4/F16; o requisito F3 era impedir que o limite de aplicação fosse multiplicado pelo número de réplicas.

## 5. F3 x F4 x F17 — fronteira reconciliada

### F3 — runtime/código

F3 responde por:

- adapter PostgreSQL;
- schema/migrations CURRENT e rollback testado;
- atomicidade/unit-of-work;
- locks e concorrência multi-process;
- crash/replay;
- shared session/step-up/OAuth/idempotency/dedupe;
- tenant isolation no banco;
- rate limiting distribuído quando necessário;
- prova técnica do Gate G3.

### F4 — infraestrutura real

F4 responde por:

- projeto/ambientes Google Cloud;
- serviço de container escolhido;
- **Cloud SQL realmente provisionado**;
- rede privada, IAM de serviço e least privilege;
- Secret Manager/KMS;
- CI/CD com migration gate;
- staging/deploy repetível;
- rollback operacional de aplicação/banco;
- política de backup/PITR no serviço gerenciado.

### F17 — medição operacional/DR

F17 complementa F4 com:

- restore ensaiado no ambiente real;
- medição de RPO/RTO;
- carga, resiliência, DR, tracing e alertas.

O Cronograma Mestre lista backup/restore/RPO/RTO em F3; a exigência permanece válida, mas a **evidência operacional** depende de infraestrutura que ainda não existe. Portanto ela não é inventada e permanece `EXTERNAL_INFRASTRUCTURE`, com medição final em F17.

Os valores-alvo de RPO/RTO não são definidos pelo CURRENT nem pelo Cronograma Mestre auditado; fixá-los envolve custo/risco de negócio e permanece `HUMAN_DECISION` antes da certificação de DR.

## 6. Certificação reproduzível do HEAD funcional

### Backend — run #161 = `success`

- 377 testes de domínio: PASS;
- 279 testes API no job geral: PASS;
- `pip-audit`: nenhuma vulnerabilidade conhecida;
- AsyncAPI: 24/24 eventos verificados;
- job PostgreSQL 16: **14 testes PASS**.

Entre as provas PostgreSQL:

- migration up/down/up;
- todos os stores CURRENT;
- cross-tenant read/delete/re-home fail-closed;
- tenant ownership imutável no banco;
- sessão compartilhada/revogação entre instâncias;
- idempotência exactly-once entre conexões;
- idempotência exactly-once entre processos spawn;
- mutações diferentes do mesmo tenant serializadas;
- dois processos simultâneos compartilham sessão/OAuth/approval e preservam isolamento;
- crash de processo faz rollback e retry da mesma chave commita uma única vez;
- rate limit compartilhado entre instâncias;
- rate limit global entre processos.

### Frontend — run #99 = `success`

- `npm audit`: 0 vulnerabilidades;
- lint: PASS;
- typecheck: PASS;
- contract drift: PASS;
- security boundary: PASS;
- 21 arquivos / 72 Vitest: PASS;
- production build: PASS;
- 4 smoke E2E: PASS;
- 27 E2E cross-stack backend real + frontend real: PASS.

## 7. Blockers que NÃO pertencem a G3 técnico

Permanecem reais e visíveis:

- Cloud SQL/Google Cloud real: `EXTERNAL_INFRASTRUCTURE` / F4;
- backup automático/PITR no serviço real: `EXTERNAL_INFRASTRUCTURE` / F4;
- restore real e RPO/RTO medidos: `EXTERNAL_INFRASTRUCTURE` / F17;
- valores-alvo de RPO/RTO: `HUMAN_DECISION`;
- efeitos externos reais de Google/Meta/Asaas não podem ser revertidos por rollback SQL; outbox/Saga/reconciliação continuam nos WPs próprios;
- subscriptions/charges finais do billing pertencem a F5.

## 8. Status final desta tranche

**Gate G3: `DONE_VERIFIED`.**

O critério de saída do gate foi provado no CURRENT com PostgreSQL real e múltiplos processos, sem inferir sucesso de Cloud SQL, staging ou produção.

**Fase F3 não recebe declaração genérica de “100% concluída”** porque seus requisitos de backup/restore/RPO/RTO ainda dependem de F4/F17 e permanecem explicitamente `EXTERNAL_INFRASTRUCTURE` / `HUMAN_DECISION`.

Nenhum merge, deploy, staging ou produção foi executado.
