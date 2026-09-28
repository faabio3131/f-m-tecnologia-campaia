# CampaIA — MATRIZ MESTRE DE COBERTURA

**Data:** 27/09/2026  
**Status:** DONE_VERIFIED quanto à cobertura documental — a matriz cobre F1–F10, NFRs, superfícies Web e jornada comercial; os estados funcionais continuam sujeitos ao DoD de cada WP.

## 1. Work Packages

| WP | Fase | Entrega |
|---|---|---|
| WP-F00-01 | F0 | CURRENT/SSOT, matriz, superseded e tracker |
| WP-F01-01 | F1 | Trial, onboarding, empresa/tenant, unidade e usuários |
| WP-F02-01 | F2 | Sessão, tenancy, RBAC/ABAC, step-up e cross-tenant |
| WP-F03-01 | F3 | Atomicidade, idempotência durável, concorrência/multi-worker |
| WP-F04-01 | F4 | Postgres, infra, Secret Manager, outbox e observabilidade-base |
| WP-F05-01 | F5 | Planos, trial, assinatura, créditos/excedente, Asaas/admin |
| WP-F06-01 | F6 | Brand Kit, uploads/assets, storage e isolamento |
| WP-F07-01 | F7 | Briefing, estratégia, criativos, policy, preview e aprovação |
| WP-F08-01 | F8 | Google PLATFORM/OAuth/developer token + OAuth por tenant |
| WP-F09-01 | F9 | Adaptador Google Ads real + publicação/reconciliação |
| WP-F10-01 | F10 | Meta OAuth/API/publicação real |
| WP-F11-01 | F11 | WhatsApp Business real |
| WP-F12-01 | F12 | Orquestração multicanal, replay, Saga/compensação |
| WP-F13-01 | F13 | Métricas, pacing e otimização governada |
| WP-F14-01 | F14 | Administração, configuração, permissões e auditoria/export |
| WP-F15-01 | F15 | Revisão Visual Premium tela a tela |
| WP-F16-01 | F16 | Segurança, LGPD, hardening e supply chain |
| WP-F17-01 | F17 | Performance, carga, resiliência, DR, tracing/alertas |
| WP-F18-01 | F18 | Staging/homologação E2E |
| WP-F19-01 | F19 | Production readiness + GO/NO-GO |
| WP-F20-01 | F20 | Jornada comercial completa |

## 2. Requisitos funcionais F1–F10

| Requisito | WP primário | Complementar | Estado |
|---|---|---|---|
| F1.1 Criar empresa | WP-F01-01 | F2/F4 | PARTIAL |
| F1.2 Unidade de negócio | WP-F01-01 | F2/F4 | PARTIAL |
| F1.3 Google Ads | WP-F08-01 | F2/F9 | TARGET |
| F1.4 Meta | WP-F10-01 | F2 | TARGET |
| F1.5 WhatsApp | WP-F11-01 | F2 | TARGET |
| F2.1 Brand Kit | WP-F06-01 | F2/F4 | TARGET |
| F2.2 Aplicar Brand Kit | WP-F07-01 | F6 | TARGET |
| F3.1 Briefing estruturado | WP-F07-01 | F4 | TARGET |
| F3.2 Briefing conversacional | WP-F07-01 | — | TARGET futuro |
| F4.1 Estratégia | WP-F07-01 | F16 | PARTIAL |
| F4.2 Textos | WP-F07-01 | F16 | PARTIAL |
| F4.3 Imagens | WP-F07-01 | F6/F16 | TARGET |
| F4.4 Policy/alegações | WP-F07-01 | F16 | PARTIAL |
| F5.1 Prévia por canal | WP-F07-01 | F9/F10/F11 | TARGET |
| F5.2 Aprovar | WP-F07-01 | F2/F12 | PARTIAL |
| F5.3 Rejeitar | WP-F07-01 | F14 | PARTIAL |
| F5.4 Solicitar ajustes | WP-F07-01 | F14 | TARGET |
| F6.1 Publicar Google | WP-F09-01 | F12 | TARGET |
| F6.2 Publicar Meta | WP-F10-01 | F12 | TARGET |
| F6.3 Click-to-WhatsApp | WP-F11-01 | F10/F12 | TARGET |
| F6.4 Idempotência | WP-F03-01 | F9/F10/F11/F12 | PRODUCTION_GATE |
| F7.1 Dashboard | WP-F13-01 | F14 | TARGET |
| F7.2 Métricas | WP-F13-01 | F9/F10/F11 | TARGET |
| F7.3 Alertas orçamento | WP-F13-01 | F4/F17 | TARGET |
| F7.4 Alertas performance | WP-F13-01 | F17 | TARGET futuro |
| F8.1 Sugestões | WP-F13-01 | F7 | PARTIAL |
| F8.2 Automação limitada | WP-F13-01 | F2/F3/F12 | PARTIAL |
| F9.1 Histórico versões | WP-F14-01 | F4 | TARGET |
| F9.2 Log aprovações | WP-F14-01 | F7 | PARTIAL |
| F9.3 Explicação IA | WP-F07-01 | F13 | TARGET |
| F9.4 Auditoria/export | WP-F14-01 | F16 | PARTIAL |
| F10.1 Autonomia | WP-F13-01 | F2/F14 | PARTIAL |
| F10.2 Modelos IA | WP-F14-01 | F7 | PARTIAL |
| F10.3 Permissões | WP-F02-01 | F14 | PARTIAL |

A coluna Estado não certifica requisito. DONE_VERIFIED só será promovido no WP após o DoD completo.

## 3. NFRs

| Família | WPs | Gate |
|---|---|---|
| Performance/latência/throughput | F17 + domínio afetado | G17 |
| Retry/circuit breaker/confiabilidade | F3/F12/F17 | G17 |
| RPO/RTO/backup/restore | F4/F17 | G17 |
| Escalabilidade/filas | F3/F4/F17 | G17 |
| Auth/RBAC/step-up | F2 | G2 |
| Criptografia/segredos | F4/F16 | G16 |
| CSRF/CSP/rate limit/WAF | F2/F16 | G16 |
| LGPD/retenção/portabilidade | F14/F16 | G16 |
| Policies Google/Meta/WhatsApp | F8–F11/F16 | G16 |
| Logging/tracing/métricas/alertas | F4/F17 | G17 |
| Migrations/rollback/versionamento | F3/F4 | G4 |
| CI/CD/staging | F4/F18 | G18 |
| Compatibilidade Web | WPs Web + F15 | G15 |
| Mobile | — | HUMAN_DECISION |
| Graceful degradation/fallback | F12/F17 | G17 |

O NFR histórico de JWT 24h/refresh 30d não substitui ADR-0018/0022: sessão comercial é server-side/cookie seguro; JWT em localStorage não é arquitetura vigente.

## 4. Superfícies Web

| Superfície | WP |
|---|---|
| Login/cadastro/sessão | F1/F2 |
| Empresa/tenant | F1/F2/F4 |
| Unidade | F1/F2 |
| Usuários/convites | F1/F2/F14 |
| Conexões Google/Meta/WhatsApp | F8/F10/F11 |
| Brand Kit | F6 |
| Home/dashboard | F13/F14 |
| Briefing | F7 |
| Estratégia | F7 |
| Criativos | F7/F6 |
| Policy | F7/F16 |
| Preview | F7/F9/F10/F11 |
| Aprovação | F7/F2/F12 |
| Métricas | F13 |
| Histórico | F14 |
| Log aprovações | F14 |
| Explicabilidade | F7/F13 |
| Otimizações | F13 |
| Autonomia | F13/F14 |
| Ativar automático com step-up | F13/F2/F3 |
| Modelos IA | F14/F7 |
| Permissões | F2/F14 |
| Auditoria/export | F14/F16 |
| Trial/plano/pagamento/uso | F5/F1 |
| Assets/uploads | F6/F4 |
| Administração operacional | F14 |
| Visual Premium completo | F15 |

A especificação histórica mobile serve apenas como referência funcional; a superfície alvo comercial é Web.

## 5. Jornada comercial

compra/trial=F5; tenant=F1; usuários/unidades=F1/F2; conexões=F8–F11; Brand Kit=F6; briefing/IA/policy/preview/aprovação=F7; publicação=F9–F12; métricas/otimização=F13; cobrança/admin=F5/F14; Premium=F15; segurança/resiliência=F16/F17; staging→produção→comercial=F18/F19/F20.


## 6. Reconciliação WP-F02-01 — 28/09/2026

O CURRENT de F2 agora inclui administração Web/API de unidades, memberships, papéis e ownership seguro, com step-up, idempotência, auditoria, revogação imediata de sessão e provas cross-tenant. O contrato OpenAPI cobre as novas rotas e está sincronizado com o cliente gerado.

O estado permanece `PARTIAL`, não `DONE_VERIFIED`, porque a homologação do step-up Google real foi deliberadamente adiada por ausência de infraestrutura/credenciais externas (`EXTERNAL_INFRASTRUCTURE` / `EXTERNAL_CREDENTIAL`). PostgreSQL, concorrência multi-réplica e atomicidade de produção continuam nos WPs F3/F4.
