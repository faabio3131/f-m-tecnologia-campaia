# EVIDÊNCIA — F3 RUNTIME, ATOMICIDADE E SHARED STATE / G3 — 01/10/2026

**WP:** WP-F03-01  
**Fase/Gate:** F3 / G3  
**Status oficial:** `PRODUCTION_GATE`  
**Repositório:** `faabio3131/f-m-tecnologia-campaia`  
**Branch:** `reconciliation/campaia-final-takeover`  
**HEAD de entrada auditado:** `cb7a43107154d58df781cadd49639267799c128d`

## 1. CURRENT confirmado antes da alteração

- PR #31: open, Draft, não mergeada, mergeable.
- Branch: `reconciliation/campaia-final-takeover`.
- HEAD: `cb7a43107154d58df781cadd49639267799c128d`.
- Backend run #145: success.
- Frontend run #83: success.
- O HEAD contém a primeira implementação F3 de transação SQLite de compatibilidade e shared state.
- Nenhum merge/deploy/produção foi executado.

## 2. Problema

A auditoria de retomada encontrou diferença entre o alcance nominal do commit F3 e o Gate G3 real. O CURRENT tinha melhora válida de atomicidade, mas ainda havia mutações críticas que escapavam da unidade transacional e métodos de IAM que podiam ler snapshots process-local obsoletos.

## 3. TARGET desta tranche

Sem declarar PostgreSQL pronto:
1. toda leitura mutável do agregado de organização deve observar o backing store quando persistência está ativa;
2. convite + quota + auditoria + reserva idempotente devem formar uma unidade local all-or-nothing;
3. invariantes críticos de IAM devem ser reavaliados dentro da unidade transacional;
4. transições locais de pré-publicação devem ocorrer dentro da mesma unidade que grava approval/audit/idempotência;
5. falha injetada deve provar rollback reproduzível.

## 4. Fora de escopo desta tranche

- adapter PostgreSQL/Cloud SQL;
- provisionamento GCP;
- múltiplos processos/containers reais;
- rate limit distribuído;
- outbox/Saga para provider externo;
- persistência final de billing;
- backup/restore e RPO/RTO;
- merge, deploy ou produção.

Esses itens permanecem `PRODUCTION_GATE`, `TARGET` ou `EXTERNAL_INFRASTRUCTURE` nos WPs correspondentes.

## 5. Achados reconciliados

### 5.1 OrganizationRepository

Parte dos métodos já relia o banco, mas vários métodos de memberships/business units/invitations consultavam `self._items` diretamente. Uma réplica que já tivesse carregado o agregado podia observar autoridade antiga. A tranche muda esses caminhos para `get_organization()`, preservando modo in-memory e forçando live-read no modo persistente.

### 5.2 Convites

Antes, `create_invitation` criava/persistia convite e auditoria antes de registrar a chave de idempotência. Crash/falha nesse intervalo podia deixar efeito sem reserva idempotente. A operação foi movida para `idempotency.execute()`; o replay continua sem reexpor o token bruto.

### 5.3 IAM administrativo

Checagens como último Owner e unidade ativa eram avaliadas antes da fronteira transacional. Elas passam a ser refeitas dentro do closure protegido, reduzindo races entre instâncias no backend persistente de compatibilidade.

### 5.4 Publicação

As transições `VALIDATED -> AWAITING_APPROVAL -> APPROVED` aconteciam antes de `idempotency.execute()`. Uma falha posterior da Saga podia deixar a campanha avançada apesar do erro. A leitura/validação/transição local passa a ocorrer dentro da unidade transacional.

**Limite explícito:** isso resolve atomicidade do estado local no adapter atual. Quando o conector for externo real, transação SQL não desfará um efeito já confirmado pelo provider; F9/F12 exigem reconciliação/Saga/outbox.

## 6. PostgreSQL — reconciliação factual

O runtime CURRENT persiste 14 stores quando `db_path` está ativo:

`brand_profiles`, `connections`, `credential_vault`, `campaigns`, `approvals`, `audit_events`, `organizations`, `idempotency`, `sessions`, `step_up_states`, `oauth_pending_states`, `tenant_autonomy`, `tenant_autonomy_updated_at`, `asaas_webhook_seen_events`.

O DDL histórico `backend/db/001_initial_schema.sql` contém 7 tabelas do modelo de 04/09. Portanto ele permanece evidência histórica válida, mas não é schema suficiente do CURRENT.

## 7. F3 x F4

- **F3:** adapter PostgreSQL no código, schema/migrations CURRENT, transações/locks, shared state, concorrência e provas multi-processo.
- **F4:** Cloud SQL real, rede/IAM, Secret Manager/KMS, ambientes, CI/CD de migration e operação gerenciada.

## 8. Testes adicionados

A tranche adiciona regressões para:
- membership alterado em réplica A ser relido corretamente pela réplica B;
- falha injetada ao criar convite não deixar convite, audit ou idempotência persistidos;
- falha injetada durante publicação restaurar campanha em `VALIDATED`, approval em `APPROVED` e não gravar resultado idempotente.

## 9. Certificação da tranche

**HEAD funcional/segurança certificado:** `4e3d00782b6c49af2bf3d2a52f3ee82490290f5c`.

### Backend — run #148 = success
- 377 testes de domínio: OK;
- 260 testes de API: OK;
- `pip-audit`: nenhuma vulnerabilidade conhecida;
- AsyncAPI: 24/24 eventos verificados end-to-end.

### Frontend — run #86 = success
- `npm audit`: 0 vulnerabilidades;
- lint: success;
- typecheck strict: success;
- contract drift: success;
- security boundary: success;
- 21 arquivos / 72 testes Vitest: success;
- production build: success;
- 4 smoke E2E: success;
- 27 E2E cross-stack backend real + frontend real: success.

Os três testes F3 adicionados passaram dentro dos 260 testes de API: stale-read organizacional cross-instance, rollback de convite e rollback da publicação.

## 10. Blocker de supply chain descoberto e corrigido durante a certificação

Na primeira repetição da CI após a correção F3, o gate `npm audit --audit-level=high` passou a reportar uma vulnerabilidade **critical** no Next.js 16.3.5 (RCE em `next/og ImageResponse`, advisory GHSA-vcvr-r3jv-pc5j). O gate falhou corretamente.

A dependência foi atualizada de `next@16.3.5` para `next@16.3.8`, junto de `@next/env` e binários SWC correspondentes no lockfile. A CI #86 confirmou `found 0 vulnerabilities`, sem regressão de lint, typecheck, build, testes ou E2E.

Este achado não altera o escopo funcional de F3, mas foi tratado porque o Documento Mestre proíbe prosseguir com blocker crítico conhecido.

## 11. Status

`PRODUCTION_GATE`. Esta evidência **não promove G3**. O próximo bloco de F3 é o adapter PostgreSQL + migrations CURRENT, seguido por prova multi-processo/multi-worker. PostgreSQL/Cloud SQL, backup/restore e ambiente real continuam abertos nos gates correspondentes. Nenhum merge, deploy ou produção foi executado.
