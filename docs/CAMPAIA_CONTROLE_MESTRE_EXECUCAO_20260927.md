# CampaIA — CONTROLE MESTRE DE EXECUÇÃO F0–F20

**Data-base:** 27/09/2026  
**Status CURRENT (02/10/2026):** G0 `DONE_VERIFIED`; F1 `PARTIAL` / G1 `DONE_VERIFIED`; F2/G2 `PARTIAL`; G3 `DONE_VERIFIED`; F4/G4 `DONE_VERIFIED`; F5/G5 `PARTIAL`. A `main@921d7972f4feac187a6c44f66f32acbbc0746e24` contém WP-F05-01/02/03 mergeados e com CI pós-merge verde. Produção permanece não autorizada.
**Repositório canônico:** faabio3131/f-m-tecnologia-campaia  
**Linha de trabalho CURRENT:** `main@921d7972f4feac187a6c44f66f32acbbc0746e24`; reconciliação pós-auditoria em `audit/reconcile-current-20261002`.
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
| F1 | G1 | Trial/onboarding/tenant/unidade/usuários | F1 PARTIAL / G1 DONE_VERIFIED |
| F2 | G2 | Multi-tenancy/RBAC/step-up/isolamento | PARTIAL |
| F3 | G3 | Atomicidade/idempotência/concorrência/runtime multi-process | DONE_VERIFIED no Gate G3; resíduos EXTERNAL_INFRASTRUCTURE/HUMAN_DECISION |
| F4 | G4 | Infra/Cloud SQL/segredos/CI-CD/observabilidade-base | DONE_VERIFIED |
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

## 11. Estado F3 / G3 — WP-F03-01 — fechamento técnico de 01/10/2026

**Gate G3:** `DONE_VERIFIED`.  
**Fase F3 residual:** `EXTERNAL_INFRASTRUCTURE` / `HUMAN_DECISION` somente para dependências operacionais de backup/restore/RPO/RTO que necessitam F4/F17.

**HEAD funcional certificado:** `18b98c16d19127df2c9f842a3c7b171e997add02`.

**Entregue e comprovado:**
- adapter PostgreSQL do runtime + `CAMPAIA_DATABASE_URL`;
- migrations 001/002/003 versionadas, rollback completo e reaplicação em PostgreSQL 16;
- schema CURRENT para os stores persistentes;
- atomicidade multi-tabela protegida por unit-of-work;
- advisory locks e serialização conservadora por tenant;
- idempotência exactly-once entre conexões e processos;
- crash/replay: processo terminado durante transação não deixa commit parcial; retry da mesma chave commita uma vez;
- SessionStore, step-up, OAuth Pending State, idempotência, approvals e dedupe compartilhados;
- duas instâncias/processos simultâneos compartilham session/OAuth/approval e preservam cross-tenant;
- tenant isolation no banco por query scoping + ownership imutável + triggers PostgreSQL; RLS genérico foi avaliado e rejeitado para o CURRENT porque stores pré-tenant, em especial sessions, exigiriam bypasses especiais;
- rate limiter do webhook Asaas compartilhado em PostgreSQL e provado entre processos; origem persistida somente como hash;
- `validateCampaign` e `createApproval` agora seguem o DoD de mutação: Idempotency-Key, replay exato, contrato e Web sincronizados.

**CI:** Backend #161 = `success` — 377 domínio + 279 API, pip-audit verde, AsyncAPI 24/24; job PostgreSQL 16 = 14/14 testes. Frontend #99 = `success` — npm audit 0, lint/typecheck/contracts/security/build verdes, 72 Vitest, 4 smoke E2E, 27 E2E cross-stack.

**Fronteira F3/F4/F17:** documento canônico `docs/F3_F4_F17_FRONTEIRA_RUNTIME_INFRA_20261001.md`.
- F3 fecha runtime/código e o critério G3.
- F4 provisiona Cloud SQL, rede/IAM, Secret Manager/KMS, migration gate, staging e backup/PITR gerenciado.
- F17 ensaia restore e mede RPO/RTO.
- valores-alvo de RPO/RTO permanecem `HUMAN_DECISION` porque o Cronograma não define números e eles alteram custo/risco operacional.

**Blockers reais preservados:** Cloud SQL/staging/backup real não foram executados; nenhuma evidência externa foi inventada.

**Governança:** PR #31 permanece Draft; nenhum merge, deploy ou produção foi executado.


## 12. Estado F4 / G4 — WP-F04-01 — tranche interna de 01/10/2026

**F4:** `PARTIAL`.  
**Tranche interna/repositório:** `DONE_VERIFIED`.  
**G4:** `EXTERNAL_INFRASTRUCTURE`.

**HEAD funcional certificado:** `c62c48302ff827c806425f59d91e5e6a8c274247`.

**Entregue e certificado internamente:**
- Cloud Run escolhido como runtime de container;
- Dockerfiles backend/Web non-root e Next standalone;
- liveness/readiness separados e testados;
- Terraform de staging/production para Artifact Registry, VPC privada, Serverless VPC Access, Cloud SQL PostgreSQL 16, KMS, Secret Manager, Storage, Pub/Sub e service accounts;
- Cloud SQL modelado com private IP, conexão criptografada, backups/PITR e deletion protection;
- bootstrap de GCS remote state + GitHub Workload Identity Federation;
- trust OIDC restrito a repo canônico + `main` + GitHub Environment correto;
- Vault de tenant migrado no TARGET de produção para envelope encryption com Cloud KMS; `CAMPAIA_VAULT_KEY` legado é recusado em staging/production;
- rotação KMS e proteção contra destroy;
- Data Access audit para KMS e Secret Manager;
- separação PLATFORM/TENANT preservada;
- nenhum secret value em Terraform;
- migration gate antes do deploy;
- workflow manual/aprovado para staging/produção e rollback de revisão;
- secret scan + Bandit SAST + dependency audits;
- production-image build e boot smoke no CI;
- runbook de staging do zero.

**CI:** Backend #170 = `success` (377 domínio + 286 API, PostgreSQL 14/14, pip-audit verde, AsyncAPI 24/24); Frontend #108 = `success` (npm audit 0, lint/typecheck/contracts/security/build, 72 Vitest, 4 smoke E2E, 27 E2E cross-stack); F4 Platform CI #4 = `success` (Terraform fmt/validate, container build+boot smoke, secret scan e Bandit).

**Por que G4 não é promovido:** o Gate exige staging real criado do zero. Nenhum `terraform apply`, Cloud Run, Cloud SQL, KMS, Secret Manager, DNS ou deploy real foi executado nesta tranche.

**Blockers externos:** projeto/billing/permissões GCP de staging, GitHub Environment/reviewer, apply real, configuração IdP/origens/redirect URI, release staging e ensaio de rollback. Classificação: `EXTERNAL_INFRASTRUCTURE` / `EXTERNAL_APPROVAL`.

**Evidência:** `docs/evidence/EVIDENCIA_F4_INFRA_SEGREDOS_CICD_G4_20261001.md`.  
**Runbook:** `docs/runbooks/F4_STAGING_BOOTSTRAP_RUNBOOK_20261001.md`.

**Governança:** PR #31 permanece Draft. Nenhum merge, deploy, staging ou produção foi executado.


## 13. Atualização F4 / G4 — staging real pós-merge — 02/10/2026

**F4:** `PARTIAL`.  
**G4:** `PARTIAL`.

**CURRENT confirmado:**
- repositório canônico `faabio3131/f-m-tecnologia-campaia`;
- `main` em `70bb364dd9e1a9054b5e3e8706b0988df8a8ef59`, merge commit da PR #32;
- PR #32 fechada e mergeada;
- Backend Tests pós-merge = `success`;
- Frontend Tests pós-merge = `success`;
- F4 Platform CI pós-merge = `success`;
- release staging `CAMPAIA Cloud Run Release` run #36955222281 = `success`.

**Evidência externa comprovada:**
- GitHub Environment `staging` aprovado; deployment marcado `production_environment=false`;
- build/push backend por SHA imutável;
- Cloud Run migration Job executado com sucesso;
- `Migration gate` = `success`;
- backend revision implantada e readiness smoke = 200;
- Web revision implantada e HTTP smoke = 200;
- final smoke = `success`;
- backend atual: `campaia-backend-staging-00002-pjr`, 100% do tráfego;
- Web atual: `campaia-web-staging-00001-lst`, 100% do tráfego;
- Cloud SQL real `campaia-staging-pg`: PostgreSQL 16, `RUNNABLE`, IPv4 público desabilitado, backup automático habilitado, PITR habilitado e transaction log retention = 7 dias;
- KMS `tenant-credentials` real com rotação de 90 dias configurada.

**Falha real encontrada e corrigida durante o gate:**
- primeira tentativa de staging, run #36952878196, falhou corretamente no `Migration gate`;
- causa raiz: `ModuleNotFoundError: No module named 'api'`;
- PR #32 corrigiu o entrypoint para `python3 -m scripts.migrate_postgres up` e adicionou smoke de container específico;
- CI da PR #32 e CI pós-merge ficaram verdes;
- nova tentativa real de staging concluiu o migration gate e release completo.

**Pendências que impedem `DONE_VERIFIED` de G4:**
1. ensaio real do workflow de rollback para revisão conhecida e restauração controlada da revisão corrente;
2. login Google real de usuário de teste no staging, conforme runbook de Identity Platform;
3. reconciliar a proteção contra exclusão do Cloud SQL: a consulta real reportou `settings.deletionProtectionEnabled=false`, enquanto o TARGET Terraform declara `db_deletion_protection=true`; não promover G4 antes de confirmar state/plan e corrigir qualquer drift real;
4. após a janela de homologação, executar a hibernação controlada do Cloud SQL conforme runbook econômico, sem confundir isso com fechamento do gate.

**Governança:** nenhum deploy de produção foi executado nem autorizado.


## 13. Atualização F4 / G4 — staging real pós-merge — 02/10/2026

**F4:** `PARTIAL`. **G4:** `PARTIAL`.

CURRENT: `main` em `70bb364dd9e1a9054b5e3e8706b0988df8a8ef59`; PR #32 mergeada; Backend Tests, Frontend Tests e F4 Platform CI pós-merge = `success`; release staging run #36955222281 = `success`.

Evidência real: migration gate = success; backend readiness = HTTP 200; Web = HTTP 200; backend `campaia-backend-staging-00002-pjr` com 100% do tráfego; Web `campaia-web-staging-00001-lst` com 100%; Cloud SQL `campaia-staging-pg` PostgreSQL 16, RUNNABLE, sem IPv4 público, backup automático e PITR ativos, retenção de transaction log 7 dias; KMS `tenant-credentials` com rotação de 90 dias.

A primeira tentativa de staging (run #36952878196) falhou corretamente no Migration gate por `ModuleNotFoundError: No module named 'api'`. A PR #32 corrigiu o entrypoint para `python3 -m scripts.migrate_postgres up`, adicionou smoke específico e foi validada no CI e no staging real.

Pendências para `DONE_VERIFIED` de G4:
1. login Google real do usuário de teste no staging — tentativa real em 02/10/2026 falhou com Google OAuth `Error 400: origin_mismatch`, portanto o Authorized JavaScript Origin do OAuth Client precisa ser reconciliado com a URL exata do Cloud Run Web;
2. hibernação controlada do Cloud SQL após a janela de homologação.

Rollback real: `DONE_VERIFIED`. O workflow `CAMPAIA Cloud Run Rollback` moveu 100% do tráfego do backend para `campaia-backend-staging-00001-22d`, `/health/ready` permaneceu HTTP 200, e depois restaurou 100% para `campaia-backend-staging-00002-pjr`, novamente com HTTP 200.

Achado de entrada Web: a rota `/` ainda expunha o scaffold técnico WP-01, embora `/login` já contenha a autenticação real. A correção foi aberta separadamente na PR #34 para redirecionar a raiz do produto ao login real.

Nota: `db_deletion_protection=true` no Terraform controla destruição pelo Terraform; `settings.deletionProtectionEnabled` é uma proteção GCP adicional e distinta. O valor false observado na API não caracteriza, por si só, drift do controle Terraform vigente.

Produção não foi executada.


## 14. Fechamento F4 / G4 — 02/10/2026

**F4:** `DONE_VERIFIED`.  
**G4:** `DONE_VERIFIED`.

**CURRENT final do gate:**
- repositório canônico `faabio3131/f-m-tecnologia-campaia`;
- `main` em `5a26f68fb4fada6888fd12a27d8a88bbcb117d9f`;
- PR #33 mergeada por merge commit;
- PR #34 mergeada por merge commit;
- PR #35 mergeada por merge commit;
- Backend Tests pós-merge da `main` = `success`;
- Frontend Tests pós-merge da `main` = `success`;
- F4 Platform CI pós-merge da `main` = `success`.

**Evidências reais que fecham G4:**
- bootstrap e foundation de staging reais aplicados e reconciliados;
- Cloud SQL PostgreSQL 16 privado, backup automático e PITR reais;
- KMS/Secret Manager/Storage/Pub/Sub/Artifact Registry e service accounts reais;
- GitHub OIDC/WIF e GitHub Environment `staging` reais;
- release de staging run #36955222281 = `success`;
- migration gate real = `success`;
- backend readiness real = HTTP 200;
- Web real = HTTP 200;
- rollback real para `campaia-backend-staging-00001-22d` = `success`;
- smoke durante rollback = HTTP 200;
- restauração para `campaia-backend-staging-00002-pjr` = `success`;
- smoke após restauração = HTTP 200;
- Authorized JavaScript Origin do OAuth Web Client de staging corrigido para a origem real do Cloud Run;
- service account do backend recebeu `roles/firebaseauth.viewer` em staging, permitindo verificação de revogação do Firebase/Identity Platform sem ampliar para permissões de escrita;
- login Google real passou da validação de identidade;
- tentativa sem vínculo retornou 403 fail-closed, conforme arquitetura;
- onboarding explícito criou tenant + unidade Principal + membership OWNER sem inclusão manual em banco;
- sessão autenticada real exibiu tenant, unidade, OWNER, 17 permissões e MFA;
- trilha real registrou `TENANT_ONBOARDING_CREATE`;
- telas protegidas de Campanhas, Aprovações, Brand Kit, Conexões, Auditoria, Configurações, Organização e Usuários foram acessadas sob sessão real.

**Observações de governança:**
- produção não foi executada nem autorizada;
- restore de banco/RPO/RTO continuam pertencendo a F17, conforme fronteira formal;
- hibernação econômica do Cloud SQL após janelas de homologação é operação de custo, não critério de fechamento de G4;
- a evidência de onboarding real também elimina o blocker externo de identidade que mantinha G1 aberto, mas a promoção formal de G1 será reconciliada no respectivo WP para evitar mistura de gates.

**Próximo Work Package pelo Cronograma Mestre:** F5 — Billing, Planos, Trial e Operação Comercial.

## 15. Reconciliação pós-auditoria — G1 e F5 — 02/10/2026

**CURRENT de referência:** `main@921d7972f4feac187a6c44f66f32acbbc0746e24`.

### G1

**F1:** `PARTIAL`.
**G1:** `DONE_VERIFIED`.

O critério literal de G1 — novo cliente chegar por fluxo do produto a sessão autenticada em seu próprio tenant — foi comprovado no staging real durante G4: login Google real; 403 fail-closed sem vínculo; onboarding explícito criando tenant + unidade `Principal` + membership `OWNER`; sessão real com tenant/unidade/permissões/MFA; auditoria `TENANT_ONBOARDING_CREATE`; nenhuma inclusão manual em banco.

F1 continua `PARTIAL` porque trial/compra -> entitlement comercial depende de F5.

### G2

**F2/G2 permanecem `PARTIAL`.** Falta E2E externo específico em staging exercitando administração sensível completa: reautenticar com Google -> criar/alterar unidade ou membership/role -> verificar autoridade/revogação e isolamento no ambiente real.

### F5 — WPs integrados

- WP-F05-01: `DONE_VERIFIED` no escopo funcional, PR #37 / merge `b9df47f6...`;
- WP-F05-02: `DONE_VERIFIED` no escopo funcional, PR #38 / merge `d604215...`;
- WP-F05-03: `DONE_VERIFIED` no escopo funcional, PR #39 / merge `921d797...`.

Evidências:
- `docs/evidence/EVIDENCIA_WP_F05_01_PERSISTENCIA_BILLING_20261002.md`;
- `docs/evidence/EVIDENCIA_WP_F05_02_ENTITLEMENTS_TRIAL_20261002.md`;
- `docs/evidence/EVIDENCIA_WP_F05_03_TRANSICOES_ASSINATURA_20261002.md`.

A auditoria encontrou pendência transversal: rotas de billing ausentes do OpenAPI/tipos Web. Esta reconciliação corrige o contrato sem reimplementar domínio.

**F5/G5 continuam `PARTIAL`**: política comercial real (`HUMAN_DECISION`), checkout/UI, histórico de faturas, PAST_DUE/grace period/dunning, estorno/reembolso quando definido, Asaas produção e prova real pagamento -> webhook -> entitlement.

### Dívida documental reconciliada

Arquitetura V2, ADR-0021, ADR-0022 e Threat Model receberam adendos CURRENT. PRs históricas #5, #6 e #28 são `SUPERSEDED` pelo takeover/PR #31 e pela `main` atual.


## Checkpoint WP-R01 — 15/10/2026 — provas externas G2

**Status de integração F2/G2: PARTIAL.** A pendência externa genérica do checkpoint de 02/10 foi exercitada em staging: Google Login e step-up reais; CRUD/lifecycle de unidade; convite/aceite; desativação e revogação da sessão; reativação e autoridade VIEWER; negativa RBAC na API; leitura própria positiva e leitura cross-tenant negativa; alteração de unidade com sessão antiga recusada; novo login no escopo atualizado e leitura cross-unit negativa. Eventos reais de auditoria foram conferidos.

Fonte da revisão: `docs/evidence/WP_R01_G2_REVIEW_MATRIX_20261015.md` e evidências relacionadas. Os registros anteriores de ausência dessas provas são históricos, SUPERSEDED para esse delta; não significam que as funcionalidades precisam ser reconstruídas. Não confundir leitura isolada de um recurso com pentest completo ou publicação real de canais.

PR #44 continua Draft, sem merge. Gate remanescente: CI no HEAD documental final, revisão/inclusão autorizada do SSOT e CI pós-merge antes da promoção global para DONE_VERIFIED. Main não foi modificada nesta execução. PR #43 também permanece separada; sem merge inferido.

**Banco:** campaia-staging-pg confirmado STOPPED / NEVER às 13:00 de 15/10/2026 pelo print do Cloud Shell. Não religar para documentação/CI. Nenhum deploy, migration, produção, pagamento ou anúncio publicado. Próxima fase funcional WP-R02 somente após o gate aplicável, com política comercial como HUMAN_DECISION e credenciais externas mantidas como tal.

## Checkpoint WP-R02-01 — 15/10/2026 — Billing Web

CURRENT: main@356f35448abf6b71b91c00a44a7ccc1db4e4906e, sem PR aberta na consulta inicial.
WP-R01 integrado pelas PRs #43/#44 autorizadas, CI pós-merge verde nas três trilhas;
F2/G2 DONE_VERIFIED no escopo da matriz externa, adendo registrado na própria evidência.
O checkpoint anterior com PRs Draft é histórico SUPERSEDED.

F5/G5: PARTIAL. Branch feat/wp-r02-billing-web implementa consulta de assinatura,
condições contratadas preservadas, catálogo configurado, entitlements, trial, PAST_DUE/grace,
e solicitações de troca/cancelamento/reativação via APIs existentes, com confirmação,
CSRF, step-up e chave estável no retry. Evidência: WP_R02_BILLING_WEB_20261015.md.
Sem decisão de preços, catálogo comercial real, credenciais Asaas, pagamento ou deploy.
Restam medição de consumo, histórico financeiro, contratação/checkout e E2E financeiro real,
além de aprovação comercial. Não confundir implementação/testes locais com fechamento G5.
Cloud SQL não foi ligado nesta execução; última prova externa permanece STOPPED / NEVER.
