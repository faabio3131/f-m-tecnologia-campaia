# CampaIA — CONTROLE MESTRE DE EXECUÇÃO F0–F20

**Data-base:** 27/09/2026  
**Status:** G0 `DONE_VERIFIED`; F1/G1 `PARTIAL`; F2/G2 `PARTIAL`; F3/G3 `PRODUCTION_GATE` em execução controlada. O CURRENT de F3 já possui transação SQLite de compatibilidade e estado de segurança compartilhado, mas PostgreSQL/multi-processo/backup/restore continuam abertos. Não implica merge, deploy ou produção.  
**Repositório canônico:** faabio3131/f-m-tecnologia-campaia  
**Linha de trabalho:** PR #31, branch reconciliation/campaia-final-takeover  
**Fonte mestra:** “CAMPAIA - CRONOGRAMA MESTRE DE EXECUCAO TOTAL ATE PRONTO COMERCIAL”, v1.0, 27/09/2026.

## 1. Ordem de autoridade

1. CURRENT técnico real do repositório, PR, CI e comportamento.
2. Cronograma Mestre F0–F20 / G0–G20.
3. ADRs e decisões vigentes.
4. Evidências reproduzíveis.
5. Documentação histórica apenas como contexto.

Nenhum painel antigo ou afirmação anterior substitui CURRENT. Status oficiais: DONE_VERIFIED, PARTIAL, TARGET, HUMAN_DECISION, EXTERNAL_CREDENTIAL, EXTERNAL_INFRASTRUCTURE, EXTERNAL_APPROVAL, PRODUCTION_GATE, BLOCKED e SUPERSEDED.

## 2. CURRENT de entrada do WP-F00-01

- PR #31: aberta, Draft, não mergeada e mergeable.
- Base: main@851db13723c3575d516bed64d71535cd7fed8bca.
- HEAD de entrada: f30f76bc44a20966795e45c1eee305aee2ea78dd.
- CI desse HEAD: backend verde; frontend verde; E2E de sessão real/cross-tenant verde — 3 jobs verdes.
- ADR-0016: Web é a linha comercial; mobile permanece em quarentena.
- Simulador, sandbox, staging, homologação e produção permanecem estados diferentes.
- Merge, deploy, produção, GO/NO-GO e HUMAN_DECISION exigem autorização expressa do Diretor.

## 3. Caminho crítico

F0 → F1/F2 → F3/F4 → F5 → F6/F7 → F8/F9 → F10 → F11 → F12–F14 → F15 → F16–F17 → F18 → F19 → F20.

| Fase | Gate | Escopo principal | Estado base |
|---|---|---|---|
| F0 | G0 | CURRENT + SSOT + cobertura + superseded | DONE_VERIFIED |
| F1 | G1 | Trial/onboarding/tenant/unidade/usuários | PARTIAL |
| F2 | G2 | Multi-tenancy/RBAC/step-up/isolamento | PARTIAL |
| F3 | G3 | Atomicidade/idempotência/concorrência | PRODUCTION_GATE — execução ativa |
| F4 | G4 | Persistência/infra/segredos/observabilidade-base | TARGET |
| F5 | G5 | Billing/trial/planos/admin comercial | PARTIAL |
| F6 | G6 | Brand Kit/assets/storage | TARGET |
| F7 | G7 | Briefing→IA→policy→preview→approval | PARTIAL |
| F8 | G8 | Google Ads — PLATFORM + OAuth por tenant | EXTERNAL_INFRASTRUCTURE |
| F9 | G9 | Google Ads — adaptador/publicação real | TARGET |
| F10 | G10 | Meta — conexão/publicação real | TARGET |
| F11 | G11 | WhatsApp Business real | TARGET |
| F12 | G12 | Orquestração real, replay, compensação | TARGET |
| F13 | G13 | Métricas/otimização governada | TARGET |
| F14 | G14 | Administração/configuração/auditoria | TARGET |
| F15 | G15 | Visual Premium completo | TARGET |
| F16 | G16 | Segurança/LGPD/hardening | TARGET |
| F17 | G17 | Performance/resiliência/DR/observabilidade | TARGET |
| F18 | G18 | Staging/homologação E2E | TARGET |
| F19 | G19 | Produção — GO/NO-GO | PRODUCTION_GATE |
| F20 | G20 | Comercialmente disponível | TARGET |

## 4. Invariantes

- SaaS multi-tenant real; Nova FM Tecnologia e FM Tecnologia são tenants comuns de homologação.
- PLATFORM e TENANT são configurações distintas.
- Segredo de tenant permanece no Vault/Secret Manager e domínio usa SecretRef.
- Mutação crítica cobre happy path, negative path, replay/idempotência e cross-tenant; quando aplicável restart, concorrência e multi-worker.
- Campanha nova exige aprovação humana; automação limitada não autoriza publicação inicial.
- Nenhum segredo real entra no Git.
- Visual Premium integral ocorre após o fechamento funcional principal.

## 5. Jornada comercial obrigatória

Compra/trial → tenant → usuários/unidades → Google/Meta/WhatsApp → Brand Kit → briefing → estratégia/criativos IA → policy/preview → aprovação → publicação real → métricas → otimização governada → cobrança/administração, sem intervenção de desenvolvedor como fluxo normal.

## 6. Retomada

Toda retomada relevante deve registrar CURRENT, Fase/Gate, DONE_VERIFIED preservado, blockers, WP exato e evidências. A matriz canônica está em docs/CAMPAIA_MATRIZ_MESTRE_COBERTURA_20260927.md.


## 7. Certificação G0

O commit de reconciliação ff1d6d95ec8f5ecdab807cb46e56fce0328d7d08 foi submetido ao CI real da PR #31. Resultado: backend run 117 = success; frontend run 55 = success; os dois jobs frontend (“lint/typecheck/contracts/security/unit+component/build/E2E smoke” e “real session protocol E2E cross-tenant”) = success. Não restou contradição ativa identificada capaz de induzir arquitetura errada. Pendências de console/credenciais Google permanecem classificadas como EXTERNAL_INFRASTRUCTURE/EXTERNAL_CREDENTIAL e pertencem aos gates F8/F9/F19, não são tratadas como fato confirmado.


## 8. Estado F1 / G1 — WP-F01-01

**Status:** `PARTIAL`. Gate G1 permanece aberto.

**CURRENT confirmado em 27/09/2026:**
- PR #31 continua aberta, Draft e não mergeada na branch `reconciliation/campaia-final-takeover`.
- HEAD funcional auditado antes desta atualização documental: `9add6f540f2d81e82f4a508db11dffb6dc943232`.
- Backend run #128: `success` — 377 testes de domínio + 241 testes de API; `pip-audit` e contrato AsyncAPI verdes.
- Frontend run #66: `success` — lint, typecheck, contract drift, boundary check, 67 testes Vitest, build, 4 smoke E2E e 27 E2E cross-stack verdes.
- O E2E `commercial-onboarding.spec.ts` cria tenant sem tenant/membership pre-seedado, unidade Principal, Owner, convite, aceite, desativação, revogação de sessão, reativação e novo login.
- Testes explícitos provam que tenant A não pode convidar usando business unit de tenant B nem desativar/reativar membership de tenant B.

**Entregue no CURRENT:**
- cadastro de empresa com documento normalizado, segmento, idioma e timezone;
- primeiro Owner, unidade padrão `Principal`, vínculo de identidade ao membership interno;
- convite/aceite, lifecycle soft deactivate/reactivate e tenant switching multiempresa;
- ausência de autoprovisionamento por mero e-mail verificado;
- unicidade de documento, autoridade Owner/Admin e limite de usuários derivado do plano no servidor;
- `plan_id`/entitlement não pode ser autoatribuído pelo browser.

**Por que G1 não é `DONE_VERIFIED`:**
- o Cronograma Mestre exige E2E de tenant totalmente novo “sem fixture”; o E2E atual usa um verificador de identidade determinístico de teste e `NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test`;
- o adaptador real Google Identity Platform existe e falha fechado sem `FIREBASE_PROJECT_ID`, mas a jornada real sem fixture ainda não foi homologada nesta fase;
- `entry_mode=TRIAL|PURCHASE` existe, porém prova de compra/trial e entitlement comercial server-authoritative pertencem ao fechamento de F5/Billing.

**Blockers/dependências:** evidência com IdP real (`EXTERNAL_INFRASTRUCTURE/EXTERNAL_CREDENTIAL` até confirmação do ambiente) e integração comercial de F5. F2/F3 continuam responsáveis por ownership transfer, IAM administrativo completo e garantias multi-instância/atomicidade.

**Governança:** nenhum merge, deploy ou alteração de produção foi realizado.


## 9. Atualização F1 — decisão operacional de 28/09/2026

**Status permanece:** `PARTIAL`. Gate G1 permanece aberto.

- HEAD funcional F1 antes do avanço para F2: `124da9fd5ea97ba19c2fbcc5c906561024ee70ea`.
- Backend run #133: `success` — 377 testes de domínio + 242 testes de API.
- Frontend run #71: `success` — 21 arquivos / 72 Vitest, 4 smoke E2E e 27 E2E cross-stack, além de lint, typecheck, contract drift, boundary check e build.
- Login Google Web real já está implementado: GIS → Google Identity Platform → ID token curto → BFF → Firebase Admin. O browser não persiste refresh token.
- O onboarding público rejeita `entry_mode=PURCHASE` autoafirmado pelo cliente; entitlement pago só poderá vir de confirmação server-side de billing em F5.
- Em 28/09/2026 o Diretor determinou que deploy/homologação Google real sejam adiados até existir infraestrutura externa. Portanto a pendência fica explicitamente classificada como `EXTERNAL_INFRASTRUCTURE` / `EXTERNAL_CREDENTIAL`, sem bloquear a execução interna dos WPs seguintes.
- Nenhum merge, deploy ou alteração de produção foi executado.

## 10. Estado F2 / G2 — WP-F02-01 — 28/09/2026

**Status:** `PARTIAL`. Gate G2 permanece aberto exclusivamente para as provas externas/ambiente produtivo que não podem ser fabricadas.

**CURRENT funcional certificado:** `54a3082e59d8db821a8df51051d87331484c1c18`.

**Entregue e comprovado internamente:**
- CRUD de unidades de negócio do tenant atual: listar, criar, renomear, desativar e reativar;
- unidade com membro ativo não pode ser desativada; tenant mantém ao menos uma unidade ativa;
- papéis OWNER/ADMIN/FINANCE/APPROVER/MARKETER/VIEWER administráveis pela Web;
- somente Owner pode administrar/conceder Owner;
- último Owner ativo nunca pode perder Owner;
- transferência segura de ownership pelo fluxo do produto: primeiro promove-se o sucessor a Owner, só então o Owner atual pode se rebaixar;
- alteração de papel/unidade revoga imediatamente todas as sessões do membership alterado;
- administração preserva isolamento de business unit operacional — Owner/Admin não ganharam acesso implícito a campanhas de outra unidade;
- mutações administrativas exigem CSRF, step-up e idempotência;
- replay devolve o resultado original e não duplica unidade;
- tentativas cross-tenant de alterar unidade/membership falham fechado com 404;
- alterações relevantes escrevem trilha de auditoria;
- unidades, memberships e papéis sobrevivem restart no runtime persistente atual;
- Web possui telas de Organização e Usuários/Permissões;
- step-up Google real está integrado à Web sem armazenamento persistente de token; após prova válida o token é descartado e a janela server-side de elevação é respeitada;
- OpenAPI e tipos TypeScript gerados estão sincronizados.

**CI do HEAD funcional:**
- Backend run #143 = `success`: 377 testes de domínio + 252 testes de API; `pip-audit` sem vulnerabilidades conhecidas; AsyncAPI 24/24.
- Frontend run #81 = `success`: 21 arquivos / 72 Vitest; 4 smoke E2E; 27 E2E cross-stack; lint, typecheck, contract drift, security boundary e production build verdes; `npm audit` 0 vulnerabilidades.

**Por que G2 não é promovido a DONE_VERIFIED:**
- a reautenticação Google real depende das configurações externas já adiadas pelo Diretor (`FIREBASE_PROJECT_ID`, client ID/API pública e origens do ambiente);
- PostgreSQL/multi-réplica/atomicidade de produção pertencem a F3/F4 e continuam `PRODUCTION_GATE`/TARGET, não são inferidos a partir do SQLite/RecordTable durável usado pela suíte;
- nenhuma homologação externa, staging ou produção foi inventada.

**Governança:** PR #31 permanece Draft; nenhum merge, deploy ou alteração de produção.

## 11. Estado F3 / G3 — WP-F03-01 — reconciliação de 01/10/2026

**Status:** `PRODUCTION_GATE`. Gate G3 permanece aberto.

**CURRENT de entrada confirmado:** PR #31 Draft, branch `reconciliation/campaia-final-takeover`, HEAD `cb7a43107154d58df781cadd49639267799c128d`. Backend #145 e Frontend #83 estavam verdes antes desta tranche.

**O que `cb7a431` realmente entregou:**
- fronteira transacional explícita no backend SQLite de compatibilidade;
- rollback coordenado das escritas RecordTable executadas dentro de `PersistentIdempotencyStore.execute()`;
- SessionStore persistente/compartilhado;
- step-up state persistente/compartilhado;
- OAuth Pending State persistente, compartilhado e single-use;
- dedupe de webhook persistente;
- leitura live em parte dos repositories;
- testes com duas instâncias da aplicação compartilhando o mesmo arquivo SQLite.

**Lacunas confirmadas na auditoria de retomada:**
- duas instâncias no mesmo processo/SQLite não equivalem a múltiplos processos/containers de produção;
- não existe adapter PostgreSQL conectado ao runtime CURRENT;
- o DDL histórico `backend/db/001_initial_schema.sql` cobre 7 estruturas, enquanto o runtime persistente CURRENT usa 14 stores; faltam no DDL histórico `credential_vault`, `organizations`, `sessions`, `step_up_states`, `oauth_pending_states`, `tenant_autonomy_updated_at` e `asaas_webhook_seen_events`;
- métodos de `OrganizationRepository` ainda podiam consultar snapshots process-local obsoletos;
- `create_invitation` materializava convite/auditoria antes da reserva idempotente;
- `publish_campaign` persistia transições pré-publicação antes da unidade transacional;
- rate limiter continua process-local;
- subscriptions/charges do billing continuam em memória e pertencem ao fechamento de F5;
- efeitos externos reais exigirão outbox/Saga/reconciliação; rollback SQL não desfaz uma chamada já confirmada por provider.

**Tranche interna executada a partir desta reconciliação:** leituras organizacionais passam a reler o backing store; criação de convite coloca quota + criação + auditoria + idempotência na mesma unidade; validações críticas de IAM são refeitas dentro da transação; publicação move as transições locais para dentro da unidade transacional. Testes de regressão específicos acompanham a mudança.

**Fronteira F3 x F4 para evitar retrabalho:** F3 responde pelo adapter/runtime PostgreSQL, schema/migrations compatíveis com o CURRENT, unit-of-work/locks/concorrência, shared state e provas multi-processo. F4 responde pelo Cloud SQL/infra real, rede/IAM de serviço, Secret Manager/KMS, ambientes, CI/CD de migration, backup gerenciado e deploy repetível.

**Ainda obrigatório para G3:** PostgreSQL real no runtime, migrations CURRENT + rollback, isolamento no banco, concorrência multi-process/multi-worker, crash/replay, rate limiting distribuído quando necessário, prova de 2+ processos/réplicas e estratégia de backup/restore/RPO/RTO coordenada com F4/F17.

**Certificação desta tranche:** HEAD funcional/segurança `4e3d00782b6c49af2bf3d2a52f3ee82490290f5c`; Backend #148 = `success` (377 domínio + 260 API, pip-audit verde, AsyncAPI 24/24); Frontend #86 = `success` (npm audit 0 vulnerabilidades, lint/typecheck/contract/boundary/build verdes, 72 Vitest, 4 smoke E2E, 27 E2E cross-stack). Durante a certificação, o gate npm detectou vulnerabilidade critical no Next.js 16.3.5; o runtime foi atualizado para 16.3.8 e a suíte completa voltou a verde.

**CURRENT após a tranche:** F3 continua `PRODUCTION_GATE`. As lacunas internas comprovadas de stale-read organizacional, convite fora da unidade idempotente e transições pré-publicação fora da transação foram corrigidas e testadas. PostgreSQL/migrations CURRENT, multi-processo/multi-worker, rate limiting distribuído e backup/restore continuam abertos; nenhuma dessas pendências foi promovida artificialmente.

**Governança:** nenhuma promoção a `DONE_VERIFIED`; nenhum merge, deploy ou produção autorizado por esta atualização.

