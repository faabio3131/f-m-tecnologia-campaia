# CampaIA — CONTROLE MESTRE DE EXECUÇÃO F0–F20

**Data-base:** 27/09/2026  
**Status:** G0 `DONE_VERIFIED`; F1/G1 `PARTIAL` — onboarding comercial implementado e CI verde, mas G1 não certificado sem evidência E2E sem fixture/IdP real e sem o fechamento do fluxo comercial de trial/compra. Não implica merge, deploy ou produção.  
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
| F3 | G3 | Atomicidade/idempotência/concorrência | PRODUCTION_GATE |
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
