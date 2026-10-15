# AUDITORIA PROFUNDA DO CURRENT — DELTA REAL RESTANTE DO CAMPAIA

**Data:** 14/10/2026  
**Base auditada:** `main@4d17f41c35d95ff473ab420be5164407c9166bb5`  
**Objetivo:** corrigir qualquer cronograma que trate como inexistente trabalho já construído, configurado ou certificado.

## Veredito

A primeira versão do `AGENTS.md` da PR #43 superestimou o trabalho restante ao decompor fases
como se vários componentes precisassem ser construídos do zero. Isso não corresponde ao CURRENT.

O CampaIA está funcionalmente avançado. O delta principal restante está concentrado em:

1. fechar F5 comercial/Asaas produção/UI;
2. completar assets/criativos/preview;
3. substituir o OAuth/conector/publicação simulados por Google Ads/Meta/WhatsApp reais;
4. ligar métricas reais aos motores já existentes;
5. fechar self-service, Premium, security/LGPD, DR e homologação final.

## Evidência de CURRENT já existente — NÃO REFAZER

### Infra/auth/runtime

- G0 DONE_VERIFIED.
- G1 DONE_VERIFIED.
- G3 DONE_VERIFIED.
- G4 DONE_VERIFIED.
- Google Identity Platform real, login Google real e onboarding real já foram comprovados em staging.
- PostgreSQL/Cloud SQL, migrations, idempotência compartilhada, atomicidade, KMS, Secret Manager,
  Cloud Storage, OIDC/WIF, release/rollback e CI já existem.

### Billing

- AsaasGateway real existe.
- Asaas Sandbox real foi verificado com criação e consulta de cobrança.
- Webhook Asaas, dedupe, settlement, idempotência externa via externalReference e fiscal handoff existem.
- WP-F05-01/02/03/04 estão DONE_VERIFIED.
- PAST_DUE, grace period, dunning authority e recovery estão na main.

O que falta em F5 não é construir o motor de billing do zero; é política comercial real, superfície Web,
credenciais/conta de produção e prova real de pagamento -> webhook -> entitlement.

### Brand/briefing/approval

- Brand Profile textual real possui GET/POST, persistência, tenant scoping e Web.
- Briefing real possui API/Web.
- Estratégia, Policy Engine e fila de aprovação existem.
- Segregação de funções da aprovação está testada.
- Budget panel, autonomia, kill switch, capabilities e audit Web/API existem.

O que falta aqui é enriquecer Brand Kit com assets reais, ligar Brand Kit ao pipeline criativo,
completar criativos/imagem/preview e fechar ajustes/rejeições quando aplicável.

### IA

- AIGateway existe.
- GeminiProvider real existe e foi validado contra API real.
- Saída estruturada nativa foi testada e implementada.
- Catálogo de agentes já contém business_context, strategist, copy, audience, policy e performance.
- sanitizer, provenance, cost ledger/cost_units, retries/fallback/circuit behavior e schema fail-closed existem.

O que falta não é criar IA do zero: é ligar os agentes já existentes ao fluxo completo de produto,
adicionar geração de imagem/asset quando necessária e homologar qualidade/UX do resultado.

### Google Ads — ativos externos já existentes

Evidências do repositório registram:

- conta gerenciadora Google Ads criada;
- developer token criado;
- nível inicial Test Account Access confirmado;
- conta de teste/homologação criada;
- OAuth Desktop Client existente para teste/manual;
- projeto `campaia-google-ads-integration` reportado como candidato de integração;
- arquitetura OAuth multi-tenant já definida;
- Credential Vault multi-tenant já construído.

NÃO recriar MCC nem developer token.

O delta real do canal é:

- verificar/reutilizar os ativos vigentes;
- criar/configurar OAuth Client Web comercial se ainda ausente;
- implementar troca OAuth server-side real por tenant;
- armazenar refresh token no Vault;
- selecionar customer account dinamicamente;
- implementar adapter real Google Ads;
- publicar/reconciliar/operar/medir;
- obter access level apropriado para contas reais quando necessário.

### Meta — ativos externos já existentes

Evidências do repositório registram:

- Meta Business Manager/portfólio "F&M Tecnologia" criado;
- Página Facebook da empresa criada e vinculada;
- App "CampaIA" criado no Meta for Developers;
- casos de uso Marketing API e WhatsApp configurados na criação do app.

NÃO recriar Business Manager, Página ou App sem prova de que foram perdidos/inválidos.

O delta real é:

- confirmar Business Verification/App Review/permissões atuais;
- implementar OAuth/token lifecycle por tenant;
- discovery de Ad Account/Page/Instagram;
- adapter Marketing API real;
- publicação/reconciliação/insights;
- promoção para uso de clientes externos somente após aprovações.

### WhatsApp — ativos externos e teste real já existentes

Evidências do repositório registram:

- WhatsApp Cloud API adicionada ao App CampaIA;
- WABA/test account criada;
- número de teste criado;
- destinatário de teste verificado;
- template de teste enviado;
- mensagem real recebida com sucesso;
- configuração de webhook foi deliberadamente pausada até existir backend público.

Hoje G4 já forneceu backend/staging público, então o próximo passo é retomar dessa etapa — não refazer o teste inicial.

O delta real é:

- configurar webhook contra endpoint real do CampaIA;
- implementar receiver/adapter específico de WhatsApp no produto;
- persistir status/replies necessários;
- número/WABA de produção e aprovações quando aplicável;
- consentimento/opt-out/LGPD.

### Orquestração/otimização

Já existem e possuem testes:

- PublicationSaga;
- Reconciler;
- Outbox/Webhook primitives;
- BudgetEngine;
- PacingEngine;
- Optimizer;
- Autonomy;
- Policy Engine;
- kill switch.

O problema atual é integração: `routes_campaigns.py` ainda instancia `ProviderSimulator`,
e Insights retorna pontos vazios honestamente.

Portanto F12/F13 são PARTIAL avançadas, não TARGET do zero.

## Prova negativa atual — o que realmente continua simulado

No CURRENT auditado:

- `routes_connections.py::oauth_start` gera URL de domínio `.invalid` e declara explicitamente
  que não contata provider real;
- callback de Connections cria Connection em modo SIMULATOR;
- `routes_campaigns.py` usa `ProviderSimulator` para publicação/pausa;
- `connection_capabilities` só mapeia modo SIMULATOR;
- requirements não possuem SDK/adaptador Google Ads/Meta específico;
- não existem adapters reais Google Ads/Meta/WhatsApp no diretório `campaia_core`;
- Insights devolve `points=[]` com nota de que analytics real não está implementado.

Isso é o maior bloco técnico real ainda aberto.

## Matriz reconciliada de fases

| Fase | Status auditado | Delta real |
|---|---|---|
| F0 | DONE_VERIFIED | nenhum |
| F1 | PARTIAL / G1 DONE_VERIFIED | remover dependência comercial após G5 |
| F2 | PARTIAL | E2E externo de administração sensível em staging |
| F3 | DONE_VERIFIED | nenhum core |
| F4 | DONE_VERIFIED | nenhum core |
| F5 | PARTIAL avançado | política comercial + UI + Asaas produção + E2E real |
| F6 | PARTIAL | upload/assets + aplicar Brand Kit |
| F7 | PARTIAL avançado | ligar copy/audience/performance, imagem, preview, ajustes |
| F8 | PARTIAL | ativos Google existem; OAuth Ads real por tenant falta |
| F9 | PARTIAL | Saga/contrato/reconcile existem; adapter/publicação/métricas Google reais faltam |
| F10 | PARTIAL / EXTERNAL_APPROVAL | BM/Page/App existem; OAuth/API real e aprovações faltam |
| F11 | PARTIAL / EXTERNAL_APPROVAL | Cloud API testada; webhook/prod connector faltam |
| F12 | PARTIAL avançado | ligar Saga/reconciliation aos adapters reais |
| F13 | PARTIAL avançado | ingestão de métricas/alertas e wiring de optimizer/pacing |
| F14 | PARTIAL | fechar self-service/export/notificações/billing/admin |
| F15 | TARGET | Premium final após freeze |
| F16 | PARTIAL | hardening/pentest/LGPD final |
| F17 | PARTIAL | load/restore/RPO-RTO/tracing/alerting final |
| F18 | TARGET | UAT E2E final |
| F19 | PRODUCTION_GATE | RC + GO/NO-GO |
| F20 | TARGET | deploy comercial controlado |

## Correção obrigatória da PR #43

O `AGENTS.md` deve:

- abandonar linguagem de "construir tudo" em F6-F14;
- separar ATIVO EXTERNO EXISTENTE de INTEGRAÇÃO AINDA SIMULADA;
- apontar "reutilizar/verificar" antes de "criar";
- condensar o cronograma no delta real;
- proteger contra retrabalho de MCC, developer token, Business Manager, Meta App, WABA teste,
  Gemini, Asaas adapter, Saga, optimizer, pacing, reconciliation e Web já existente.

