# CampaIA — AGENTS.md

## Cronograma Mestre Operacional — DELTA REAL RESTANTE

**Data de reconciliação:** 16/10/2026
**Repositório canônico:** `faabio3131/f-m-tecnologia-campaia`  
**CURRENT confirmado em 16/10/2026:** `main@2458cb3da177537cc88b68b2cc156ce5e6bf3800`; WP-R04-04B na PR #73 Draft (revalidar antes de qualquer novo WP)
**Produção:** não autorizada  
**Fonte mestra:** Cronograma Mestre F0–F20/G0–G20  
**Evidências:** `docs/evidence/AUDITORIA_CURRENT_DELTA_REAL_RESTANTE_20261014.md`; PRs #64–#72 e documentos WP-R03/WP-R04 associados. PR #72 integrada em main@2458cb3; pós-merge Backend #328, Frontend #266 e F4 #162 verdes (evidência GitHub Actions em 16/10/2026).

Este arquivo orienta futuros agentes/executores sobre **o que ainda falta**.  
Ele existe para impedir retrabalho sobre funcionalidades, integrações de infraestrutura ou ativos externos que já existem.

---

# 1. REGRA SUPREMA

Antes de qualquer execução relevante:

1. confirmar repo, branch e HEAD reais;
2. confirmar PRs abertas e estado da main;
3. ler este arquivo e o Cronograma Mestre;
4. ler apenas ADRs/evidências ligadas ao WP;
5. comparar CURRENT x TARGET;
6. provar a lacuna antes de implementar;
7. preservar tudo que estiver DONE_VERIFIED;
8. executar um WP por vez, salvo trilhas explicitamente paralelas;
9. testar, gerar evidência e só então atualizar status;
10. parar antes de merge/deploy/produção/GO-NO-GO/HUMAN_DECISION sem autorização expressa.

**Nunca criar novamente um ativo externo sem primeiro provar que o ativo vigente foi perdido, invalidado ou substituído.**

---

# 2. STATUS OFICIAIS

Usar somente:

- DONE_VERIFIED
- PARTIAL
- TARGET
- HUMAN_DECISION
- EXTERNAL_CREDENTIAL
- EXTERNAL_INFRASTRUCTURE
- EXTERNAL_APPROVAL
- PRODUCTION_GATE
- BLOCKED
- SUPERSEDED

Nunca usar “100% pronto”, “homologado”, “produção pronta” ou equivalente sem evidência correspondente.

---

# 3. INVARIANTES

- SaaS comercial multi-tenant.
- Nova FM Tecnologia e FM Tecnologia são tenants comuns de homologação.
- Nenhum cliente exige mudança de código, commit especial, deploy específico, ID hardcoded ou inclusão manual no banco.
- PLATFORM e TENANT são configurações distintas.
- Segredo de tenant fica em Vault/Secret Manager e domínio usa SecretRef/mecanismo equivalente.
- Nenhum segredo real entra no Git.
- Mutação crítica: happy path, negative path, replay/idempotência e cross-tenant; quando aplicável restart, concorrência, atomicidade e multi-worker.
- Mock/simulador/sandbox/staging/produção são estados diferentes.
- Visual Premium integral só depois do fechamento funcional principal.
- Merge, deploy, produção, alteração irreversível e GO/NO-GO exigem autorização expressa.

---

# 4. NÃO REFAZER — CURRENT JÁ CONSTRUÍDO/CERTIFICADO

## F0/G0
- CURRENT/SSOT, matriz e reconciliação: DONE_VERIFIED.

## F1/G1
- Google Identity Platform real em staging;
- login Google real;
- onboarding cria tenant + unidade Principal + OWNER;
- convite/aceite/lifecycle de usuários;
- tenant switching;
- sessão autenticada real;
- G1 DONE_VERIFIED.

F1 só mantém dependência comercial residual até G5.

## F2
Já existem:
- CRUD de unidades;
- memberships/roles;
- ownership transfer;
- RBAC;
- step-up;
- session revocation;
- isolamento cross-tenant/business unit;
- Web de Organização e Usuários.

Não reimplementar. O delta externo específico foi exercitado no WP-R01, integrado na PR #44 e verificado pela CI pós-merge; G2 DONE_VERIFIED no escopo do gate. Ver adendo de integração na matriz WP-R01.

## F3/G3
Já existem e estão DONE_VERIFIED:
- PostgreSQL;
- migrations;
- atomicidade;
- advisory locks;
- idempotência exactly-once;
- shared sessions/OAuth/approvals/dedupe;
- multi-process;
- tenant isolation;
- rate limit persistente.

## F4/G4
Já existem e estão DONE_VERIFIED:
- Cloud Run;
- Cloud SQL PostgreSQL 16;
- KMS;
- Secret Manager;
- Cloud Storage/PubSub;
- WIF/OIDC;
- CI/CD;
- migration gate;
- rollback real;
- staging real;
- login/onboarding real.

## F5
Já estão DONE_VERIFIED:
- WP-F05-01 persistência billing;
- WP-F05-02 entitlements/trial;
- WP-F05-03 upgrade/downgrade/cancelamento/reativação;
- WP-F05-04 PAST_DUE/grace/dunning/recovery.

Também já existem:
- AsaasGateway real;
- Asaas Sandbox real testado com criação/consulta de cobrança;
- webhook Asaas;
- settlement;
- dedupe;
- externalReference para crash/replay;
- fiscal handoff.

## Brand/briefing/campanhas
Já existem:
- Brand Profile textual GET/POST + Web;
- briefing API/Web;
- estratégia;
- Policy Engine;
- approvals;
- segregation of duties;
- budget;
- autonomy;
- kill switch;
- audit;
- connection lifecycle;
- capability panel.

## IA
Já existem:
- AIGateway;
- GeminiProvider real;
- chamadas reais Gemini já validadas;
- structured output nativo;
- schema fail-closed;
- provenance/custo;
- sanitizer;
- retry/fallback/circuit behavior;
- agentes: business_context, strategist, copy, audience, policy, performance.

Não recriar gateway/agentes do zero.

## Orquestração/otimização
Já existem e possuem testes:
- PublicationSaga;
- Reconciler;
- Outbox/Webhook primitives;
- BudgetEngine;
- PacingEngine;
- Optimizer;
- Autonomy;
- Policy Engine.

O trabalho restante é wiring com providers reais e API/Web, não reescrita.

---

# 5. ATIVOS EXTERNOS JÁ EXISTENTES — NÃO RECRIAR

## Google Ads

Evidências registram:

- conta gerenciadora Google Ads criada;
- developer token criado;
- nível inicial Test Account Access confirmado;
- conta de teste/homologação criada;
- OAuth Desktop Client existente para uso manual/teste;
- projeto `campaia-google-ads-integration` reportado como ativo/candidato;
- arquitetura multi-tenant já definida;
- Credential Vault já construído.

**Não criar novo MCC nem novo developer token como tarefa padrão.**

O que falta é verificar/reutilizar esses ativos e completar OAuth Web comercial + adapter real.

## Meta

Evidências registram:

- Meta Business Manager/portfólio criado;
- Página Facebook da empresa criada;
- App `CampaIA` criado no Meta for Developers;
- use cases Marketing API + WhatsApp configurados.

**Não recriar Business Manager, Página ou App sem prova de necessidade.**

## WhatsApp

Evidências registram:

- WhatsApp Cloud API adicionada ao App CampaIA;
- WABA/test account criada;
- número de teste criado;
- destinatário validado;
- template de teste enviado;
- mensagem real recebida com sucesso.

Webhook foi deliberadamente pausado à época porque não havia backend público.  
G4 resolveu essa dependência de infraestrutura.

**Não repetir criação da conta de teste nem o teste básico de mensagem.**

---

# 6. PROVA DO DELTA REAL AINDA ABERTO

No CURRENT:

- `routes_connections.oauth_start` ainda gera URL `.invalid`;
- callback de Connections continua simulado;
- Connection comercial ainda não recebe token por OAuth real;
- `routes_campaigns` ainda usa `ProviderSimulator`;
- capabilities reais TEST/PRODUCTION não estão mapeadas;
- não existe adapter real Google Ads/Meta/WhatsApp em `campaia_core`;
- Insights devolve `points=[]` honestamente;
- optimizer/pacing/reconciliation existem, mas não estão ligados a métricas externas reais;
- Brand Kit tem edição/histórico (PR #64), assets privados API/Web (PRs #65–#67) e seleção/snapshot textual do Brand Kit na campanha (PR #68), com CI/pós-merge verdes;
  GCS/ADC/worker reais, retenção/delete e aplicação VISUAL do logo na imagem continuam pendentes;
- propostas copy/públicos e revisão humana (PRs #69–#71) já integradas; fluxo de imagem/armazenamento criativo/previews ainda incompleto. PR #72 é somente adaptador Gemini opt-in em validação;
- Billing Web/consumo/checkout revisado/encerramento/garantia/emissão/avisos e evidência interna de custos integrados nas PRs #45–#63;
  ativação do catálogo, custos reais/jurídico, jobs e pagamento externo ainda pendentes; não refazer as superfícies;
- Premium final ainda não foi executado;
- G18/G19/G20 ainda não ocorreram.

Esses são os blocos prioritários restantes.

---

# 7. MATRIZ CURRENT RECONCILIADA

| Fase | Status real | Delta restante |
|---|---|---|
| F0 | DONE_VERIFIED | nenhum |
| F1 | PARTIAL / G1 DONE_VERIFIED | reconciliar dependência comercial após G5 |
| F2 | DONE_VERIFIED | gate G2 fechado; preservar evidências WP-R01 |
| F3 | DONE_VERIFIED | nenhum core |
| F4 | DONE_VERIFIED | nenhum core |
| F5 | PARTIAL / HUMAN_DECISION / EXTERNAL_CREDENTIAL | motor e Web das PRs #45–#63 integrados; faltam ativação contratual/catálogo e custos reais, Asaas produção e pagamento→webhook→entitlement externo |
| F6 | PARTIAL / EXTERNAL_INFRASTRUCTURE | edição, assets privados API/Web e snapshot para campanha (#64–#68) integrados; GCS/worker/ADC reais, retenção/delete e uso visual nos criativos não homologados |
| F7 | PARTIAL | copy/públicos/revisões/aprovações (#69–#71) integrados; PR #72 aberta para transporte Gemini opt-in, sem ativação, imagem comercial, storage, previews ou G7 |
| F8 | PARTIAL | ativos Google existem; OAuth Ads real por tenant falta |
| F9 | PARTIAL | Saga/reconcile existem; Google publish/metrics reais faltam |
| F10 | PARTIAL / EXTERNAL_APPROVAL | BM/Page/App existem; Meta OAuth/API real + aprovações faltam |
| F11 | PARTIAL / EXTERNAL_APPROVAL | Cloud API de teste funciona; webhook/prod connector faltam |
| F12 | PARTIAL avançado | ligar Saga/reconcile/outbox aos adapters reais |
| F13 | PARTIAL avançado | ingestão real + alertas + wiring optimizer/pacing |
| F14 | PARTIAL | fechar self-service/export/notificações/admin |
| F15 | TARGET | Premium final |
| F16 | PARTIAL | hardening/pentest/LGPD final |
| F17 | PARTIAL | load/restore/RPO-RTO/tracing/alerting final |
| F18 | TARGET | UAT final |
| F19 | PRODUCTION_GATE | RC + GO/NO-GO |
| F20 | TARGET | deploy comercial controlado |

---

# 8. ORDEM MESTRA DAS TAREFAS RESTANTES

## WP-R01 — Fechar G2 externo
**Status:** DONE_VERIFIED

PRs #43/#44 integradas com autorização; CI pós-merge de main@356f35448abf6b71b91c00a44a7ccc1db4e4906e verde. Cenários abaixo já exercitados; não repetir por ausência documental.

No staging real:

- login Google real;
- novo step-up;
- criar/alterar unidade ou membership/role;
- provar sessão revogada;
- provar autoridade após mudança;
- provar cross-tenant/business-unit isolation;
- registrar evidência.

**Não reconstruir F2.**

---

## WP-R02 — Fechar F5/G5 comercial
**Status:** PARTIAL / HUMAN_DECISION / EXTERNAL_CREDENTIAL

### O que já existe
Motor de billing, Asaas adapter, webhook, settlement, entitlement e lifecycle comercial.
WP-R02-01 integrado na PR #45, main@20727bcb, com CI pós-merge verde:
Web de plano/condições contratadas/catálogo/entitlements/trial/PAST_DUE/grace e
solicitações de troca/cancelamento/reativação. Não reconstruir essas superfícies.

WP-R02-02 integrado na PR #46, main@f3428e6e, com CI pós-merge verde:
histórico paginado por tenant, observações de gateway/ambiente e fatura hospedada Asaas validada.
Não reconstruir histórico, cursor ou preservação do link do provedor.

### Falta (delta externo/ativação; não reconstruir PRs #45–#63)
1. Política V1 aprovada em 15/10/2026; publicação ainda condicionada a custos, jurídico e homologação.
2. Ativar catálogo comercial real e conferir tarifação/câmbio/margem com evidências, sem estimativa apresentada como custo real.
3. Ativar jobs controlados e migrations reais somente mediante autorização específica; preservar ledger, checkout e Web integrados.
4. Credenciais/conta Asaas produção quando apropriado e autorizado.
5. Provar E2E externo: trial/assinatura -> cobrança -> pagamento -> webhook/reconciliação -> entitlement; nenhum simulador certifica G5.

WP-R02-04 / PR #48: fundação interna do ledger comercial integrada, com CI pós-merge verde.
Não integrada às chamadas IA/checkout nem ativada no produto. Ver
`docs/WP_R02_04_LEDGER_CREDITOS_20261015.md` para limites, testes e próximos passos.
Não confundir a aprovação da política com conclusão de F5/G5.

WP-R02-05 / PR #49: ciclo/franquia/consentimento integrado, CI pós-merge verde. Escopo e pendências em
`docs/WP_R02_05_CICLO_FRANQUIA_CONSENTIMENTO_20261015.md`. Não ativar catálogo V1 antes de
fechar lifecycle, enforcement, medição por entrega e checkout operacional.

WP-R02-06 / PR #50: estratégia com claim/reserva antes do provider e limites contratuais
integrados, com CI pós-merge verde. Ver
`docs/WP_R02_06_EXECUCAO_IA_CREDITOS_LIMITES_20261015.md`. F5 continua PARTIAL;
nenhum componente simulado certifica G5 externo.

WP-R02-07 / PR #51: lifecycle V1 por aniversário, cancelamento ao fim do período pago
e reativação com nova identidade integrados, CI da PR e pós-merge completamente verdes. Ver
`docs/WP_R02_07_LIFECYCLE_ANIVERSARIO_20261015.md`. WP-R02-08 / PR #52 integrado: obrigação
congelada antes do gateway e fence de emissão/recuperação sem redispatch; CI da PR e pós-merge verdes. Ver
`docs/WP_R02_08_OBRIGACAO_DISPATCH_DURAVEL_20261015.md`. WP-R02-09 / PR #53: checkout revisado,
aceite, vencimento contratado e ambiente congelado integrados; CI da PR e pós-merge verdes. Ver
`docs/WP_R02_09_CHECKOUT_REVISADO_20261015.md`. WP-R02-10 / PR #54 integrada, CI da PR e pós-merge verdes: fechamento final
sem nova mensalidade, residual e reserva durante encerramento. Ver
`docs/WP_R02_10_FECHAMENTO_CONSUMO_FINAL_20261015.md`. WP-R02-11 / PR #55 integrada, CI da PR e pós-merge verdes: conferência
de valor/status, reversões e consulta somente leitura pelo histórico. Ver
`docs/WP_R02_11_CONFERENCIA_RECEBIMENTOS_20261015.md`. WP-R02-12 / PR #56 integrada, CI da PR e pós-merge verdes: retirada
comprovada de renovação aberta após encerramento, sem repetir DELETE incerto ou duplicar
excedente final. Ver `docs/WP_R02_12_RETIRADA_RENOVACAO_ABERTA_20261015.md`. WP-R02-13 / PR #57 integrada, CI da PR e pós-merge verdes:
evidência mínima de devoluções pendentes/parciais/integralmente concluídas, sem nova franquia.
Ver `docs/WP_R02_13_OBSERVACOES_ESTORNO_20261015.md`. WP-R02-14 / PR #58 integrada, CI da PR e pós-merge verdes: fato pago/primeira
contratação imutáveis e pedido de garantia com encerramento explícito, sem refund fictício.
Ver `docs/WP_R02_14_PEDIDO_GARANTIA_20261016.md`. WP-R02-15 / PR #59 integrada, CI da PR e pós-merge verdes: worker privado de
devolução por invoice, com dry-run/default desligado, fence antes do efeito e recuperação
somente por GET. Ver `docs/WP_R02_15_WORKER_DEVOLUCAO_GARANTIA_20261016.md`. WP-R02-16 / PR #60 integrada, CI da PR e pós-merge verdes: encerramento financeiro da garantia com prova integral,
manifesto das obrigações cobertas, preservação do excedente pago/devolvido e fiscal pendente.
Ver `docs/WP_R02_16_ENCERRAMENTO_FINANCEIRO_GARANTIA_20261016.md`.
WP-R02-17 / PR #61 integrada, CI da PR e pós-merge verdes: autorização explícita de emissão recorrente por organização,
worker privado no aniversário e fence compartilhado com checkout, sem débito automático.
Ver `docs/WP_R02_17_EMISSAO_RECORRENTE_UNICA_20261016.md`.
WP-R02-18 / PR #62 integrada, CI da PR e pós-merge verdes: avisos de cobrança persistentes no aplicativo, leitura individual,
isolamento/RBAC e migração 006 somente em fonte/CI. Não afirma envio de e-mail/SMS.
Ver `docs/WP_R02_18_AVISOS_COBRANCA_IN_APP_20261016.md`.
WP-R02-19 / PR #63 integrada, CI da PR e pós-merge verdes: tentativas e unidades de custo de IA persistentes, reservas de
orçamento/limites configurados por namespace, falhas desconhecidas preservadas e preços
legados explicitamente não verificados. Ver `docs/WP_R02_19_EVIDENCIA_CUSTOS_IA_20261016.md`.
Antes da ativação V1, fechar custos reais/tarifas/câmbio/fiscal, ativação controlada dos jobs,
migration real autorizada e canais externos quando contratados. Catálogo real continua
desabilitado; não certificar G5 com simulador ou apenas CI.

**Gate G5:** pagamento real ativa entitlement sem intervenção de desenvolvedor.

---

## WP-R03 — Completar F6 Brand Kit/assets
**Status:** PARTIAL

### Já existe
Brand Profile textual, persistência, Web, Cloud Storage na infraestrutura.

WP-R03-01 / PR #64 integrada, CI da PR e pós-merge verdes: edição textual, controle concorrente de versão e histórico imutável,
com replay seguro na Web. Ver `docs/WP_R03_01_EDICAO_HISTORICO_MARCA_20261016.md`.
O cadastro/listagem existentes foram preservados. Assets e aplicação explícita ao pipeline
permanecem próximos deltas, não certificados por esta etapa.

WP-R03-02A / PR #65 integrada, CI da PR e pós-merge verdes: contrato interno e adaptador privado GCS com leitura fixada por geração,
integridade, limites de resposta e mutações condicionais sem retry automático. Ainda sem endpoint,
AppState ou UI; nenhuma ativação ou chamada real. Ver
`docs/WP_R03_02A_TRANSPORTE_STORAGE_PRIVADO_20261016.md`.
WP-R03-02B / PR #66 integrada, CI da PR e pós-merge verdes: decoder de imagem em processo restrito, formatos estáticos
PNG/JPEG/WebP, normalização sem metadados e envelope de saída verificado pelo pai.
Sem ativação real. Ver `docs/WP_R03_02B_VALIDACAO_ISOLADA_IMAGENS_20261016.md`.
WP-R03-02C / PR #67 integrada, CI da PR e pós-merge verdes: assets privados com API/Web, quota por organização, fence de
upload/delete, normalização isolada e metadata persistente. Migração 008 somente em
fonte/CI; default desabilitado. E2E usa armazenamento SIMULATOR explícito, não prova GCS
real. Ver `docs/WP_R03_02C_ASSETS_PRIVADOS_API_WEB_20261016.md`.

WP-R03-03 / PR #68 integrada, CI da PR e pós-merge verdes: seleção explícita de Brand Kit/versão/assets no briefing,
snapshot persistente e contexto da estratégia, revisão humana para orientação em texto
e bloqueio de arquivo removido. Ver `docs/WP_R03_03_MARCA_SELECIONADA_PIPELINE_20261016.md`.
Sem seleção automática, visão multimodal ou uso visual fictício do logo.

### Falta
- homologação GCS/ADC/worker em runtime real para upload de logo/assets;
- confirmar metadata e acesso privado no GCS real (fluxo fonte/CI já integrado);
- confirmar isolamento dos objetos no GCS real (API/CI já cobertos);
- confirmar lifecycle/delete real e política jurídica de retenção;
- fechar aplicação visual nos criativos F7 (seleção/snapshot/contexto textual integrados na PR #68).

**Não reprovisionar Cloud Storage sem drift comprovado.**

---

## WP-R04 — Completar F7 IA/criativos/preview
**Status:** PARTIAL avançado

### Já existe
AIGateway, Gemini real, agentes copy/audience/policy/performance/strategist, Policy Engine e approvals.

WP-R04-01 / PR #69 integrada, CI da PR e pós-merge verdes: propostas textuais de copy/audience com versão, histórico privado,
quote/confirmação comercial, entrega atômica e invalidação das aprovações anteriores.
Migração 009 somente em fonte/CI. Propostas não certificam qualidade, targeting real,
imagem, preview de plataforma nem publicação real. Ver
`docs/WP_R04_01_PROPOSTAS_COPY_AUDIENCE_20261016.md`.

### Falta
WP-R04-02 / PR #70 integrada, CI da PR e pós-merge verdes: ajuste seletivo de uma variação por 1 crédito configurado,
lote anterior imutável e versão/validação/aprovação renovadas. Ver
`docs/WP_R04_02_REVISAO_SELETIVA_COPY_20261016.md`.

WP-R04-03 / PR #71 integrada, CI da PR e pós-merge verdes: revisão humana dos materiais, solicitação de ajustes,
reautenticação real existente e aprovações terminais sem rearmamento. Ver
`docs/WP_R04_03_REVISAO_HUMANA_MATERIAIS_20261016.md`.

- ligar policy/performance ao fluxo API/Web;
- completar creative asset model;
- geração de imagem real: WP-R04-04A em validação do adaptador interno, default OFF;
  sem AppState/rotas/UI/catálogo ativado. Ver `docs/WP_R04_04A_TRANSPORTE_IMAGEM_GEMINI_20261016.md`;
- armazenar criativos no storage do tenant: WP-R04-04B slice 1 em branch, contrato de identidade/manifests/prova e testes; ainda SEM persistência F3, GCS real, API/Web ou ativação; ver `docs/WP_R04_04B_PRIVATE_CREATIVES_FOUNDATION_20261016.md`;
- edição/regeneração seletiva;
- preview Google/Meta/WhatsApp;
- solicitar ajustes/rejeição quando aplicável;
- evals/critério de qualidade quando o Diretor definir.

**Gate G7:** briefing -> estratégia -> copy/assets -> policy -> preview -> approval funcionando de ponta a ponta.

---

## WP-R05 — Google Ads real F8/F9
**Status:** PARTIAL / EXTERNAL_APPROVAL

### Reutilizar
- MCC existente;
- developer token existente;
- conta de teste;
- projeto/ativos Google já registrados;
- Vault;
- OAuth-state security;
- Connection model;
- Connector contract;
- Saga/Reconciler.

### Confirmar antes de criar
- qual MCC está vigente;
- nível atual do developer token;
- OAuth Web Client para Google Ads;
- redirect URI;
- conta de teste vigente.

### Implementar somente o delta
- OAuth authorization_code server-side por tenant;
- refresh token no Vault;
- discovery de Customer IDs;
- escolha explícita de conta;
- adapter Google Ads real;
- validate/publish/pause/resume;
- budget changes;
- idempotência externa;
- reconciliation;
- insights.

**Gate G8:** tenant arbitrário conecta a própria conta.  
**Gate G9:** publica/opera/reconcilia/m mede uma campanha real de teste sem duplicação.

---

## WP-R06 — Meta real F10
**Status:** PARTIAL / EXTERNAL_APPROVAL

### Reutilizar
- Business Manager;
- Página;
- App CampaIA;
- Marketing API use case;
- Vault/Connections/Saga/Reconciler.

### Confirmar
- Business Verification;
- App Review;
- permissions aprovadas;
- mode Development/Live;
- Page/Instagram/Ad Account disponíveis para homologação.

### Implementar delta
- OAuth/token lifecycle por tenant;
- discovery e seleção explícita de Ad Account/Page/Instagram;
- adapter Marketing API;
- publish/pause/resume;
- reconciliation;
- insights;
- error/rate-limit mapping.

**Não recriar Business Manager/App como rotina.**

---

## WP-R07 — WhatsApp real F11
**Status:** PARTIAL / EXTERNAL_APPROVAL

### Reutilizar
- App CampaIA;
- WhatsApp product;
- WABA/test account;
- número de teste;
- teste real de template já concluído.

### Retomar do ponto correto
- configurar webhook agora que staging público existe;
- receiver de eventos/status;
- verificação/autenticação;
- dedupe/replay;
- Connection/Vault;
- consentimento/opt-out;
- número/WABA de produção quando apropriado;
- integração click-to-WhatsApp se permanecer no escopo.

**Não repetir o teste básico já certificado.**

---

## WP-R08 — Fechar F12 orquestração real
**Status:** PARTIAL avançado

### Já existe
PublicationSaga, Connector contract, Reconciler, Outbox/Webhook primitives.

### Falta
- trocar ProviderSimulator pelos adapters reais;
- persistir/recuperar Saga aberta quando necessário;
- partial failure;
- retry/backoff;
- compensation;
- reconciliation jobs;
- pause/resume/kill-switch efetivos nos providers;
- concorrência/restart/multi-worker.

**Gate G12:** falha parcial não duplica recurso nem gasto e converge para estado reconciliado.

---

## WP-R09 — Fechar F13 métricas/otimização
**Status:** PARTIAL avançado

### Já existe
Optimizer, PacingEngine, BudgetEngine, Autonomy, Performance Agent, InsightsPanel e kill switch.

### Falta
- ingestão real de métricas Google/Meta;
- modelo interno normalizado;
- histórico/freshness;
- substituir placeholder de Insights;
- ligar snapshots reais ao optimizer/pacing;
- alertas budget/auth/provider/performance;
- aplicar ações automáticas somente dentro da autonomia aprovada.

**Não reescrever optimizer/pacing.**

---

## WP-R10 — Fechar F14 self-service/admin
**Status:** PARTIAL

### Já existe
- Organização;
- Usuários;
- Permissions;
- Connections;
- Brand Kit;
- Campaigns;
- Approvals;
- Audit;
- Autonomy;
- Settings.

### Falta principal
- Billing Web final;
- export de auditoria/dados quando exigido;
- histórico de versões;
- Notification Center;
- reconnect/revoke lifecycle completo;
- account export/delete/retention hooks;
- support/diagnostics seguros;
- fechar superfícies sem intervenção de desenvolvedor.

---

## WP-R11 — F15 Visual Premium
**Status:** TARGET

Somente depois de F5–F14 funcionalmente congelados:

- revisão tela a tela;
- design system final;
- responsive;
- estados vazios/erro/loading;
- charts/tables;
- consistência visual;
- WCAG 2.2 AA;
- visual regression;
- performance Web.

Preservar integralmente as regras de negócio.

---

## WP-R12 — F16 Security/LGPD final
**Status:** PARTIAL / HUMAN_DECISION

Já existem diversos controles de auth, tenancy, secret scan, dependency audit, KMS/Vault e threat model.

Fechar:

- pentest/manual review final;
- DAST;
- SSRF/XSS/injection/upload/OAuth final;
- authorization matrix;
- privacy policy;
- termos;
- retenção;
- portabilidade;
- exclusão;
- DPA/suboperadores;
- aceite jurídico.

**Gate G16:** zero P0/P1 e riscos residuais formalmente aceitos.

---

## WP-R13 — F17 NFR/DR final
**Status:** PARTIAL

Já existem health, Cloud SQL backup/PITR, rollback e base de observabilidade.

Falta:

- load test;
- concorrência dos fluxos críticos;
- tracing/error tracking final;
- alertas operacionais;
- provider outage drills;
- restore real;
- RPO/RTO medidos;
- runbooks de incidente.

---

## WP-R14 — F18 UAT completo
**Status:** TARGET

Executar empresa nova, sem intervenção de desenvolvedor:

trial/compra -> tenant -> usuários/unidades -> Google/Meta/WhatsApp -> Brand Kit -> briefing -> estratégia/criativos -> policy/preview -> aprovação -> publicação -> métricas -> otimização -> billing/admin.

Também provar isolamento Tenant A/B.

**Gate G18:** jornada completa assinada, zero blocker.

---

## WP-R15 — F19 Release Candidate / GO-NO-GO
**Status:** PRODUCTION_GATE

- RC imutável;
- CI completa;
- migrations;
- staging equivalente;
- backup;
- rollback;
- secrets/config production;
- domains/TLS;
- approvals externos;
- monitoring/support;
- relatório de riscos.

**Gate G19:** decisão explícita do Diretor.

---

## WP-R16 — F20 Produção/comercial
**Status:** PRODUCTION_GATE

Somente após autorização:

- deploy controlado;
- migration;
- smoke;
- primeiro tenant externo controlado;
- primeiro pagamento real;
- primeira conexão real;
- primeira publicação real;
- métricas/reconciliation;
- 24–72h hypercare;
- P0/P1 zero antes de ampliar.

Somente após G20 o CampaIA pode ser classificado como `COMERCIALMENTE DISPONIVEL`.

---

# 9. TRACK EXTERNO EM PARALELO

Não reconstruir ativos. Verificar estado atual e avançar somente no que falta.

## Google Ads
- confirmar MCC vigente;
- confirmar nível vigente do developer token;
- solicitar nível que permita contas reais quando necessário;
- confirmar/criar OAuth Web Client Ads somente se ausente;
- redirect URI.

## Meta
- Business Verification;
- App Review;
- permissions;
- acesso a contas de terceiros;
- modo Live quando permitido.

## WhatsApp
- webhook;
- número/WABA de produção;
- aprovações/configuração final.

## Asaas/jurídico
- política comercial;
- estrutura jurídica/CNPJ quando exigido;
- conta produção;
- refund/fiscal.

## LGPD
- termos;
- privacidade;
- DPA;
- retenção/exclusão.

---

# 10. DEFINITION OF DONE

Todo WP aplicável precisa:

- CURRENT correto;
- nenhum segredo no repo;
- nenhum hardcode de tenant;
- isolamento;
- RBAC/step-up;
- happy path;
- negative path;
- cross-tenant;
- replay/idempotência;
- persistência/restart quando aplicável;
- concorrência/multi-worker quando aplicável;
- contrato sincronizado;
- Web quando aplicável;
- audit/observabilidade;
- evidência;
- CI da PR;
- pós-merge CI;
- blocker externo corretamente classificado.

---

# 11. STOP CONDITIONS

Autorização contínua registrada pelo Diretor em 15/10/2026 às 17:58 (São Paulo):
executar tarefas, corrigir falhas e prosseguir após verde. Inclui merges após CI completa
no HEAD exato e verificação pós-merge, sem nova confirmação de rotina. Manter evidências
e um WP por vez. Não estende autorização a produção, credenciais ou gastos reais.

Solicitar autorização específica antes de:

- deploy;
- produção;
- migration real;
- credencial/segredo real;
- rotação de segredo;
- gasto/custo relevante;
- decisão comercial;
- decisão jurídica;
- mudança irreversível;
- GO/NO-GO;
- qualquer HUMAN_DECISION.

---

# 12. FORMATO DE RETOMADA

Toda retomada informa:

- repo/branch/HEAD;
- fase/gate;
- DONE_VERIFIED preservado;
- blocker real;
- WP exato;
- CURRENT;
- TARGET;
- fora de escopo;
- testes;
- evidências.

---

# 13. CHECKLIST FINAL

Antes de declarar comercial:

- cliente novo entra sem desenvolvedor;
- tenant é criado;
- usuários/unidades funcionam;
- plano/trial/pagamento funcionam;
- Google real conecta/publica/m mede;
- Meta real conecta/publica/m mede;
- WhatsApp real conecta/usa fluxo suportado;
- nenhum tenant FM privilegiado;
- Brand Kit e assets reais;
- IA gera estratégia/copy/assets;
- policy/preview/approval;
- publicação real idempotente;
- partial failure reconciliado;
- métricas reais;
- optimizer/pacing ligados a dados reais;
- budget/kill switch reais;
- audit/export;
- billing/fiscal honestos;
- multi-instância;
- KMS/Secret Manager;
- restore/load/pentest;
- LGPD/termos;
- Premium aprovado;
- a11y;
- UAT staging;
- RC verde;
- rollback;
- monitoring/support;
- aprovação explícita do Diretor;
- primeiro tenant externo controlado.

Se qualquer requisito crítico estiver aberto, CampaIA não recebe status `COMERCIALMENTE DISPONIVEL`.


## Adendo operacional WP-R04-04B — 16/10/2026

- PR #73, branch `feat/wp-r04-04b-creative-private-foundation`, sem merge, sem deploy e sem migration aplicada em ambiente real.
- CI DONE_VERIFIED no HEAD `1dc5baaaa4fcf35d5802b504e04f4b77ef0478f6`: Backend #351, Frontend #289, F4 #185.
- Adicionado posteriormente manifesto com MD5 canônico + recuperação `reconcile_after_restart` por observação GCS, sem segundo POST; testes SQLite de restart e objeto ausente. **Essas alterações exigem nova CI no HEAD exato.**
- Continuam TARGET: contrato e2e API/Web de criativos, atomicidade do ledger 15 créditos, verificação externa GCS/ADC e recuperação/delete em todos os cenários de falha. G7 permanece PARTIAL; não ativar comercialmente.
- Evidência técnica em `docs/WP_R04_04B_PRIVATE_CREATIVES_FOUNDATION_20261016.md`.


## Diretriz do Diretor — construção completa antes da homologação externa (16/10/2026)

- Priorizar completar TODOS os componentes funcionais internos, APIs, Web, persistência, controles, segurança, testes e visual conforme dependências e sequência do Cronograma Mestre.
- Integrações externas devem ser implementadas como fluxos reais configuráveis de PLATFORM ou TENANT, nunca hardcoded para FM/Nova FM. Manter credenciais, conectividade, aprovação e homologação com serviço real documentadas como EXTERNAL_CREDENTIAL / EXTERNAL_INFRASTRUCTURE / EXTERNAL_APPROVAL até fase final de homologação externa.
- Dependência externa não deve bloquear WP interno independente. Continuar implementando e verificando internamente com mocks/simuladores explicitamente rotulados; não declarar produção homologada com evidência simulada.
- Não pular gates internos ou controles de segurança e não aplicar migrações reais, merge/deploy, produção ou ações irreversíveis sem autorização específica do Diretor.
- Próximo escopo dentro de WP-R04-04B: API/Web de criativos e controles de créditos usando contratos F3/F5 existentes; não iniciar Fase Premium antecipadamente.


## WP-R04-04B — API de leitura e cotação interna (16/10/2026)

- Implementado na PR #73 inventário GET por campanha/unidade/tenant, GET de estado de criativo e GET de cotação usando F5 `quote_action("image")`. Todos fail-closed sem F3/billing; sem dados ou URLs GCS expostos.
- Rotas de geração POST, billing de 15 créditos, liberação de mídia e UX Web de geração **ainda TARGET**; não ativar mutação de imagem antes de validar reserva, external dispatch, resultado, entrega e SETTLE/RELEASE atômicos.
- Testes de contrato impedem mutação acidental e vazamento de identidade/manifesto do objeto. CI do HEAD novo ainda pendente; não confundir código com DONE_VERIFIED.
- Homologação GCS externa: `EXTERNAL_INFRASTRUCTURE`, postergada conforme decisão do Diretor até fechamento funcional, sem bloquear WPs internos independentes.


## WP-R04-04B — extensão de liquidação interna F3/F5 (16/10/2026)

- `api.creative_image_settlement.settle_stored_creative`: subrotina interna, chamada somente após autorização e reserva comercial, exige manifesto STORED com generation persistida; SETTLE F5, idempotência e auditoria na mesma transação F3. Testes unitários de rejeição pendente e liquidação verificada.
- **Não há ainda rota POST de geração nem componente Web operacional**: não apresentar este helper como entrega API/Web completa. Integração custo F3, provedor Gemini, commit storage, créditos, entrega e status assíncrono requerem fechamento e testes E2E; dependência da homologação GCS real permanece EXTERNAL_INFRASTRUCTURE.
- Novo HEAD necessita CI. A PR #73 permanece PARTIAL; não fazer merge, deploy nem migrations reais sem aprovação específica.


## WP-R04-04B — primeira integração Web real com API de leitura (16/10/2026)

- Novo `GeneratedImagesPanel` no detalhe da campanha, utilizando `api.get` existente para inventário privado e cotação da franquia; sem token, URL de bucket, caminho de objeto nem segredo no navegador.
- Teste Vitest verifica leitura de estados, cotação e botão de geração desabilitado enquanto falta a mutação segura.
- O helper de SETTLE F3/F5 passou no Backend #364, Frontend #303 e F4 #198 no commit `9c5b9296eef06555d5efb66f330930d406045b06`.
- **Geração POST/IA/F3 cost guard/SETTLE+storage E2E não estão concluídos.** Esta tela é inventário de criativos e NÃO é a UI de geração funcional. Não avançar status além de PARTIAL sem prova concreta.
- PR #73 sem merge; após inclusão da Web, executar nova CI no HEAD exato. Homologação GCS externa permanece fora do fechamento funcional interno, como determinado pelo Diretor.


## WP-R04-04B — geração de imagens API/Web com governança interna (16/10/2026)

- POST `/campaigns/{campaignId}/images` adicionado com RBAC por tenant/unidade/campanha, Idempotency-Key, versão esperada da estratégia, confirmação da cotação de créditos F5, armazenamento GCS privado explicitamente habilitado e teto interno de custo `CAMPAIA_IMAGE_MAX_COST_UNITS` configurável.
- Provider Gemini imagem registrado no gateway F3 existente apenas mediante `GEMINI_IMAGE_ENABLED=true`; sem permissões ocultas da FM/Nova FM, sem credenciais hardcoded, sem chamadas externas por default.
- Fluxo implementado: RESERVE de créditos comercial antes do dispatch; GATE F3 de custo/credenciais; PNG normalizado; claim criativo/quota; F3 commit de fence; upload único; entrega somente com generation STORED; SETTLE de créditos+auditoria na transação F3 da entrega. Falhas incertas preservam reserva para reconciliação, não há segundo POST automático.
- UI Web agora possui formulário de imagem com revisão de créditos e confirmação explícita, além do inventário; configuração externa ausente desativa a ação, sem simular integração real.
- `PARTIAL`: homologação real GCS/Gemini continua EXTERNAL_INFRASTRUCTURE / EXTERNAL_CREDENTIAL; testes e CI do HEAD atual PENDENTES, especialmente E2E de sucesso, erro, replay, corrupção, recovery e cross-tenant.
- **Atenção:** ponte de reconciliação operacional `STORAGE_PENDING -> STORED -> SETTLE` após crash com reserva comercial segue TARGET, assim como entrega privada binária/autorizada, policy preview e paginação. Não liberar deploy/merge/G7 com esses blockers internos.


## WP-R04-04B — recuperação comercial, mídia privada e matriz E2E (16/10/2026)

- GET autenticado de mídia PNG estável: `/campaigns/{campaignId}/images/{creativeId}/content`, streaming sem URL pública, validação de manifesto e GCS generation; UI Web exibe imagem somente após status STORED.
- POST governado `/campaigns/{campaignId}/images/{creativeId}/reconcile` para observar objeto após crash e liquidar reserva F5 usando a referência canônica F3/F5 persistida, sem repetir POST Gemini/GCS; VERSION/CAMPAIGN/TENANT/UNIT/RBAC são verificados.
- Criativo persiste `credit_operation_id` imutável na claim; recuperação de imagem STORED revalida metadata GCS antes de settlement. Default externo desabilitado; `SIMULATOR` apenas em `test/dev-local`; não confundir sucesso CI com homologação externa.
- Novo teste de integração explícito `test_generated_image_simulator_e2e.py`: RESERVE -> simulação de modelo imagem com custo registrado F3 -> upload privado simulado -> F5 SETTLE -> replay sem segundo POST/débito -> GET de PNG autenticado -> bloqueio cross-tenant. Histórico real e documentação são atuais somente após CI verde.
- Dependências internas remanescentes: testes de timeout/falha de GCS + replay de recuperação após restart com SETTLE, controle de versão de campanhas e Brand Kit, formatos/variações por canal, upload manual, policy/preview e paginação conforme G7. Externos: GCS/ADC, Gemini com credencial e custos reais (EXTERNAL_INFRASTRUCTURE/EXTERNAL_CREDENTIAL).
- **O WP segue PARTIAL até evidências de todos os gates internos.** PR #73 não mergeada; nenhuma migration, produção ou homologação externa autorizadas.


## Reconciliação CI do ciclo API/Web/imagem + recuperação (16/10/2026)
- HEAD `20acfe93248e26a4be74cf3b63ecfb6e5f8f8758` na PR #73: Backend **#410 SUCCESS**, Frontend **#349 SUCCESS**, F4 **#244 SUCCESS**. Inclui PostgreSQL, simulador explícito com quota/custos F3/F5, replay sem segunda geração, cross-tenant, conteúdo PNG privado e recuperação de GCS incerto com liquidação comercial.
- HEAD posterior contém ajuste de UX para atualizar inventário após resposta incerta; repetir a CI e conferir o HEAD exato antes de chamar este incremento DONE_VERIFIED.
- **WP-R04-04B PARTIAL**: ausência de prova externa por decisão do Diretor, e gates internos ainda pendentes: política/preview e versões por canal, gerenciamento completo de asset/deleção, recuperação governada de custo de provider desconhecido, limites/comportamento de alta carga e E2E adicionais. Não confundir os cenários SIMULATOR do CI com homologação real.
- Merge/deploy/produção/migration real seguem sujeitos à autorização específica, não concedida nesta execução.


## Fechamento da rodada técnica WP-R04-04B (16/10/2026)
- PR #73 em `feat/wp-r04-04b-creative-private-foundation`, sem merge. HEAD de código+docs `75163485e32b301a3abc5596aade36772aa5c50f` com **Backend #413 SUCCESS**, **Frontend #352 SUCCESS**, **F4 #247 SUCCESS**.
- Backend inicialmente apresentou falha intermitente em teste preexistente de concorrência Asaas/PostgreSQL: uma das duas operações recebeu `BILLING_DISPATCH_PENDING` em vez de 200; rerun isolado passou. Nenhum teste foi relaxado, nenhum comportamento de cobrança alterado. Investigar estabilidade desse cenário como débito de teste no F5, não apresentar como prova de homologação bancária.
- Confirmados internamente na CI: POST de geração Gemini governada, contrato de preço por política F5 configurável, orçamento de IA F3, PNG privado, leitura autenticada, replay sem reenvio, cross-tenant, recuperação GCS incerta e liquidação F5 em simulador de storage/provedor.
- `PARTIAL`: faltam gates internos F7/G7 posteriores (formatos por canal, política de imagem/preview, upload/revisão e lifecycle/delete completo, compensação de custos desconhecidos e outros negativos) e homologação externa final. Não executar merge/deploy/produção/migrations reais sem autorização expressa.
- Nova edição documental exige verificação de CI no HEAD resultante antes de elevar qualquer status.


## WP-R04-04B — paginação privada do inventário (16/10/2026)
- Incremento interno da PR #73: paginação determinística em lotes de 50 por UUID canônico, `next_cursor` e `has_more`, com cursor validado exclusivamente no conjunto já filtrado por tenant, unidade e campanha. Cursor estranho não acessa itens alheios e falha fechado.
- Testes de três páginas sem duplicação e rejeição de cursor inválido/fora de escopo. Ainda requer CI verde no HEAD exato; não marcar DONE_VERIFIED antecipadamente.
- Permanece PARTIAL: revisão/policy de imagem e formatos por canal, lifecycle/delete, F3 custos incertos e matriz adicional de negativos. Testes externos seguem EXTERNAL_INFRASTRUCTURE/EXTERNAL_CREDENTIAL; nenhum merge/deploy/migration aplicada.


## WP-R04-04B — prévia de política fail-closed (16/10/2026)
- Adicionado GET autenticado `/campaigns/{campaignId}/images/{creativeId}/preview`: retorna estado de armazenamento, compatibilidade com versão atual da campanha e bloqueios explícitos para revisão humana. O endpoint é exclusivamente de leitura, não aprova imagem nem autoriza publicação.
- A prévia exige geração GCS confirmada e mesma versão da campanha; `publication_allowed=false` e `human_review=NOT_REVIEWED` até existir fluxo governado real de política/aprovação. Testes negativos cobrem imagens pendentes, falhas, mudança de versão e stored sem aprovação.
- Novo HEAD exige CI. WP permanece PARTIAL; isto não fecha policy engine de criativos nem fluxo de aprovação de arte. Sem merge, deploy ou migrações reais. Externos mantidos pendentes para fase final.


## WP-R04-04B — revisão humana imutável (16/10/2026)
- Revisão CURRENT confirma rota de aprovação de campanha já existente, mas ela NÃO certifica a imagem por hash+generation; não reutilizar aprovação genérica como autorização de mídia.
- Incluído contrato interno de decisão de arte `CreativeImageReviewStore`, com F3 idempotência, auditoria, separação solicitante/revisor, hash da imagem, geração GCS, versão da campanha e identidade do criativo; replay incompatível falha fechado.
- Testes negativos para decisões antigas, geração substituída, versão alterada e REJECT. **API de aprovação ainda TARGET**: requer autoria da imagem persistida e vínculo com o principal autenticado/step-up/can_approve; não aceitar requester_id informado pelo navegador. Policy/preview atual continua sem permitir publicação, mesmo com este registro interno. Não alegar aprovação completa.
- Lifecycle/delete completo também TARGET. Execução CI do novo HEAD pendente; homologação externa continua postergada. Sem merge/deploy/migration.


## WP-R04-04B — API de revisão com RBAC e step-up (16/10/2026)
- Adicionado POST /campaigns/{campaignId}/images/{creativeId}/review: autenticação server-side, escopo tenant/unidade/campanha, Permission.APPROVAL_DECIDE, step-up, Idempotency-Key, can_approve e revisão imutável ligada a SHA-256, generation GCS e versão da campanha.
- O criador de cada imagem nova é agora registrado no claim F3 via sessão autenticada (requested_by); imagens históricas sem origem comprovada falham fechado. Revisão não autoriza publicação automaticamente; policy/preview continua conservador.
- Teste do contrato de rotas atualizado. **Revisão API e lifecycle de delete ainda PARTIAL até nova CI e testes E2E negativos reais da rota.** Não declarar gate de publicação concluído; sem merge/deploy/migration.


## WP-R04-04B — tombstone e exclusão privada com fence (16/10/2026)
- Incremento de lifecycle: `CreativePrivateStorage.delete()` faz CAS STORED→DELETE_PENDING antes do DELETE externo (acesso binário já bloqueado), permite uma única tentativa de remoção da geração imutável GCS, e usa `reconcile_delete()` apenas com observação de metadata para confirmar DELETED. Em dúvida, mantém DELETE_PENDING e quota, sem repetir DELETE automaticamente.
- Testes de simulador: exclusão idempotente, liberação de quota após observação e recuperação de resposta UNCERTAIN sem segundo DELETE. Não representa homologação GCS real nem expiração de retenção externa.
- API Web de exclusão por usuário com RBAC/step-up ainda TARGET; revisar requisitos de retenção/auditoria e cobertura API e GCS negativas antes de fechar gate. HEAD atual requer nova CI, sem merge/deploy/migration.


## WP-R04-04B — API privada de exclusão de criativos e retenção (16/10/2026)
- Implementada rota DELETE autenticada por tenant/unidade/campanha/versão com Permission.CAMPAIGN_EDIT, step-up e Idempotency-Key; consulta F3 antes de qualquer ação externa. Criativo aprovado por revisão humana fica bloqueado para exclusão comum: exige futura revogação governada.
- O storage existente faz tombstone STORED→DELETE_PENDING antes de um único DELETE, impede leitura no proxy em DELETE_PENDING e reconsulta GCS para confirmar DELETED. Resposta incerta não dispara segundo DELETE e quota não é liberada sem comprovação da ausência de geração.
- Política de retenção **não confundir com apagamento físico definitivo**: metadados imutáveis e evidência de auditoria permanecem no banco. A remoção do objeto da API de GCS não certifica eliminação de backups, versões ou retenções de fornecedor. Configuração jurídica/operacional detalhada de prazos de retenção e remoção de dados pessoais continua HUMAN_DECISION/PRODUCTION_GATE antes do lançamento real.
- Testes de contrato atualizados para DELETE explícito, além dos testes existentes de fence/delete, replay e falha. A matriz E2E específica da nova rota (CSRF, cross-tenant, step-up vencido, conflito de aprovação) ainda precisa ser ampliada: WP PARTIAL até evidências. CI do HEAD deste commit pendente; sem merge/deploy/migration.


## Correção de teste de exclusão/step-up (16/10/2026)
- Backend vermelho em `b0808f5`: teste `test_delete_route_rejects_missing_step_up_and_cross_tenant` assumia erroneamente que a ausência do header significava sessão sem elevação. `BillingCreditHarness.setup_subscription()` havia concedido step-up válido persistido por sessão; a rota retornou 200 de acordo com a política vigente.
- Corrigido o **arranjo do teste**, invalidando explicitamente a elevação existente no estado canônico antes de testar ausência de step-up. Não foi removida nem flexibilizada a proteção RBAC/step-up da rota. Repetir CI exata antes de certificar.


## WP-R04-04B — matriz ampliada de exclusão governada (16/10/2026)
- Incluídos testes de API para: cross-tenant negado, step-up revogado negado, step-up fresco autorizando DELETE, mídia privada inacessível após tombstone e segundo DELETE sem repetição da operação externa.
- Incluídos testes F3/storage para resposta incerta com objeto ainda visível (mantém DELETE_PENDING/quota) e replay do DELETE entre dois handles com somente um dispatch; a exclusão confirmada só libera quota após observação.
- CURRENT permanece PR #73 sem merge, WP PARTIAL; próximos gates: revalidação completa de aprovação/retention, concorrência multiworker PostgreSQL e custo incerto do provedor. Sem declarar homologação real Gemini/GCS por simulação. Exige CI do HEAD exato e revisão de eventuais falhas.


## WP-R04-04B — auditoria final de gates internos (16/10/2026)
- Adicionado teste PostgreSQL real de corrida entre duas instâncias independentes de CreativeRepository sobre o mesmo claim: somente um writer deve criar o manifesto, outro deve receber replay; quota usada uma vez e leitura cross-tenant negada. Evidência final requer CI PostgreSQL no novo HEAD.
- Auditoria CURRENT de custo F3: `PersistentAICostLedger._stats` já mantém `held` quando não há OUTCOME ou custo observado é UNKNOWN, e `report` sinaliza `INCOMPLETE`. **Ainda não há reconciliação operacional governada com fonte externa verificada para liberar reservas incertas**: PRODUCTION_GATE / EXTERNAL_CREDENTIAL; proibido converter UNKNOWN em custo zero.
- Aprovação: `CreativeImageReviewStore` já exige revisor diferente da autoria e vincula hash, versão e generation. **A rota de preview não consulta a decisão persistida**, logo continua fail-closed para publicação, sem certificar material como aprovado. Integração efetiva no fluxo publication/policy permanece TARGET.
- Retenção: DELETE confirmado pelo transporte GCS não equivale a eliminação de versões retidas/backups; prazo LGPD e revogação de aprovação são HUMAN_DECISION/PRODUCTION_GATE. Nunca tratar a PR como pronta para GO/NO-GO enquanto pendências permanecerem.
- Escopo desta rodada: verificação CURRENT e novo teste PG. Sem merge/deploy/migration. CI HEAD pendente.


## WP-R04-04B — política de publicação e reconciliação conservadora F3 (16/10/2026)
- A rota existente de publicação agora impede publicação se existir qualquer imagem gerada pendente/não revisada da campanha e versão corrente. Imagem STORED exige revisão humana imutável correspondente ao hash+generation; caso contrário retorna IMAGE_REVIEW_REQUIRED, sem chamar provedor. Geração de imagem é opcional; campanhas sem imagens geradas preservam o fluxo anterior. Teste E2E simulado adicionado para falha fechada.
- Adicionado `PersistentAICostLedger.reconciliation_queue(tenant)` somente leitura, listando tentativas START sem OUTCOME ou com UNKNOWN_COST, preservando budget hold F3 e segregação por tenant. Teste cobre durabilidade/restart e ausência de liberação automática. Não é reconciliação com fatura real nem permissão para fixar custo zero.
- **PARTIAL:** uso efetivo da imagem selecionada no payload publicado, validação da arte pela policy e lifecycle de aprovação/revogação ainda requerem revisão/integração; reconciliação de custos com evidência assinada do provedor é EXTERNAL_CREDENTIAL/PRODUCTION_GATE. Nova CI precisa ser verificada no HEAD exato. Não solicitar merge ainda.


## WP-R04-04B — vínculo de seleção, revogação e varredura de pendências (16/10/2026)
- Publicação via simulador exige `selected_creative_id` explícito quando houver criativos ativos na versão da campanha; escopo tenant/unidade/versão, estado STORED e revisão humana hash+generation válidos. Registra prova de seleção no evento de auditoria. **Não equivale a entrega de mídia aos conectores reais**: transporte de binário, formatos por canal, criativo aprovado em payload externo e provas de publicação seguem TARGET/PRODUCTION_GATE.
- Revisão de arte passou a ter revogação terminal em F3 com auditoria e idempotência, via POST autenticado com Permission.APPROVAL_DECIDE, can_approve e step-up. Revogação invalida aprovação futura, inclusive tentativas de replay; não promove aprovação nova ou publicação. Pausar/remover publicação já aplicada após revogação ainda TARGET e exige projeto da saga de compensação.
- F3 conserva custos desconhecidos sob reserva; sem credencial e resposta oficial verificada, **reconciliação financeira externa real permanece EXTERNAL_CREDENTIAL/EXTERNAL_INFRASTRUCTURE/PRODUCTION_GATE**, não foi executada e não pode ser simulada como homologada.
- Inspeção read-only de PRs abertas: somente #73; `main` em `2458cb3da177537cc88b68b2cc156ce5e6bf3800`. #73 continua sem merge; título histórico está defasado frente ao conteúdo implementado. Não há autorização específica para merge/deploy/migration/GO. Esta inspeção não prova inexistência de pendências em PRs fechadas, cronograma mestre ou infraestrutura externa.
- Novo código e testes requerem CI exata; WP-R04-04B permanece PARTIAL até cobertura total e gates pendentes. G0-G20 NÃO declarados homologados.


## Reconciliação histórica de PRs e gates — 16/10/2026
- Consulta individual ao GitHub: PRs #48 a #72 (25 PRs) possuem `merged=true`, logo não se confundem com simplesmente closed. PR #73 está `open`, `draft=true`, `merged=false`. `main` permanece no merge da #72 (`2458cb3`). Essa faixa foi certificada; PRs #1–#47 exigem inventário separado e não foram declaradas integradas por inferência.
- HEAD auditado antes deste registro: `97ecdd97070863eebe6d10ed3330a59bb03e5585`. Os três workflows de CI estavam `queued`, inclusive jobs de Backend, PostgreSQL, F4 e Frontend. **Não há sucesso certificado desse HEAD**; tratar ausência de runner como bloqueio de infraestrutura/CI se persistir, jamais como testes verdes.
- Cronograma Mestre (27/09/2026) define G7: campanha completa chega a aprovação com estratégia/copy/assets/policy/preview reais; G9–G12 exigem publicação Google/Meta/WhatsApp e reconciliação real; G16–G20 exigem segurança, UAT, GO/NO-GO e disponibilização. Estes gates **não podem ser declarados DONE_VERIFIED** apenas por simulação ou merge.
- Pendências internas conhecidas do WP-R04-04B: vincular entrega real de mídia por conector (TARGET/EXTERNAL_APPROVAL), revogar publicação já aplicada por compensação governada (TARGET), ampliar testes de revogação/anti-replay (TARGET), evidência externa para encerrar custo incerto (EXTERNAL_CREDENTIAL), retenção jurídica (HUMAN_DECISION), e certificar CI do HEAD após qualquer alteração.
- Proibidos merge, deploy, aplicação de migrations e GO/NO-GO até autorização expressa do Diretor.


## WP-R04-04B — correção de preview e regressão de revogação (16/10/2026)
- O preview de criativo deixa de anunciar `NOT_REVIEWED` invariavelmente: consulta o registro de revisão persistido, sinaliza APPROVE/REVOKED e mantém `publication_allowed=false` (somente policy/publication governada pode autorizar). Aprovação expirada ou revogada gera bloqueio.
- Testes: preview com aprovação amarrada à evidência, preview revogado, aprovação com autor distinto, revogação auditada, replay idempotente e bloqueio de reaproveitar aprovação após revogação. Evidência pendente no novo HEAD da CI.
- Não há comprovação de implantação de mídia em Google/Meta nem revogação de campanha já publicada nos canais; permanece TARGET/EXTERNAL_APPROVAL, não pode ser substituída por simulação. Reconciliação financeira externa e retenção ainda permanecem seus gates específicos.


## Reteste WP-R04-04B — 16/10/2026, correção CI e revogação protegida
- CI em `300958a` teve PostgreSQL runtime integration SUCCESS, mas API tests FAILURE por `NameError: state is not defined` em `preview_generated_creative`, originado na nova consulta persistida. Corrigida causa direta: _scope agora vincula `state` na rota de preview. Repetir CI do HEAD atual antes de declarar DONE_VERIFIED.
- Nova regra fail-closed: revogação de imagem aprovada não é permitida via rota comum enquanto a campanha possuir `external_resources` registrados; exige compensação governada e reconciliação antes de alterar aprovação já aplicada. Sem inventar pausa/remoção externa.
- Continua vedado merge/deploy; externos Gemini/GCS/canais e custo real mantidos em EXTERNAL_CREDENTIAL/PRODUCTION_GATE. Histórico de PRs #48–#72 merged confirmado, #73 Draft.


## Retomada do Cronograma Mestre — Fase 7 / G7, WP-R04-04B (16/10/2026)
- CURRENT confirmado: PR #73 Draft contra main, HEAD anterior d25e5c2 certificado com três workflows verdes. G7 exige estratégia, copy, assets, policy e previews reais, com formatos quadrado/vertical/story, edição anterior à aprovação e proveniência; estes itens não ficam DONE_VERIFIED pelo mero sucesso de um simulador.
- Novo teste negativo: seleção de creative_id inexistente na publicação retorna IMAGE_SELECTION_INVALID antes de atingir a saga de publicação. Testa binding explícito da arte à versão da campanha; também já há cenário de seleção sem revisão.
- Sequência correta: concluir testes/controles do WP-R04-04B; depois revisão de evidências e autorização específica para eventual merge. G8 Google Ads multi-tenant real permanece posterior a G7, EXTERNAL_CREDENTIAL / EXTERNAL_APPROVAL / EXTERNAL_INFRASTRUCTURE.
- Nenhum merge/deploy/migration, nem alteração de segredo externo. Certificação do HEAD novo depende de nova CI.


## G7 — análise de formatos sem falsa homologação (16/10/2026)
- CURRENT verificado após HEAD `cd79eea`: Backend, Frontend e F4 CI SUCCESS. Gerador aceita prompt e persiste PNG normalizado/identidade, mas não oferece seleção fechada de proporções para Gemini, edição versionada da arte ou prévia real por canal. Nenhum desses itens deve ser marcado DONE_VERIFIED.
- Incremento atual: preview privado informa `format_hints` por geometria (SQUARE, PORTRAIT_4_5, STORY_9_16), sem confiar no cliente, e mantém `channel_media_validated=false` e `publication_allowed=false`. Testes de proporções verificam que dicas não viram aprovação de canal.
- Ainda TARGET: geração específica por proporção e canal, múltiplos derivados versionados e cobrados corretamente, edição antes da aprovação, preview real Google/Meta/WhatsApp e entrega de mídia nos conectores. G7 segue PARTIAL e não pode avançar para G8. Novo HEAD exige CI; sem merge, deploy ou segredos.


## G7 — seleção de formato de imagem (16/10/2026)
- CI anterior `4c43218`: F4 e Frontend PASS, Backend FAIL (contrato `_preview_policy` recebeu linhas de teste sem manifest; corrigido para preview sem dimensões não confiar em formato). Novo incremento da API gera `image_format` opt-in ORIGINAL/SQUARE/PORTRAIT_4_5/STORY_9_16, atrelado a request_identity comercial, propagado como instrução ao Gemini, valida proporção real do PNG antes da claim/storage/settlement; mismatch é fail-closed, não liquida créditos comerciais. Custo F3 de dispatch continua contabilizado mesmo em rejeição.
- Teste negativo do story incompatível assegura ausência de upload e consumo de créditos comerciais. Geração de formato correto com Gemini real e previsualização por canal não homologadas: EXTERNAL_CREDENTIAL/PRODUCTION_GATE. Edição versionada continua TARGET. O WP permanece PARTIAL até CI do HEAD exato e demais gates. Sem merge/deploy.


## G7 — correção do teste de guarda de provedor (16/10/2026)
- CI Backend do HEAD `975c6e9` falhou exclusivamente no teste `test_disabled_provider_refuses_before_cost_reservation_or_gcs`, porque o fixture `SimpleNamespace` anterior não incluía o novo campo obrigatório no fluxo interno `image_format`. A correção atual adiciona `image_format="ORIGINAL"` ao fixture, sem alterar a rota ou afrouxar o bloqueio do provedor desativado. Requer reteste do novo HEAD; nunca inferir sucesso antes da CI.


## WP-R04-04B — revisões imutáveis e previews por canal (16/10/2026)
- Implementado contrato de revisão opcional `source_creative_id` na geração paga: nova identidade criativa/idempotente e nova imagem, original preservada; só aceita origem STORED com tenant/unidade/campanha/versão correspondentes. Aprovação ou revogação existente bloqueia edição direta da origem. Linhagem gravada no manifesto de registro F3 e exposta na API de detalhe. Não altera modelo de cobrança: nova geração = nova operação de crédito; custo F3 permanece distinto.
- Prévia de imagem retorna metadados para Google Ads, Meta/Facebook/Instagram e WhatsApp explicitamente `DRAFT_ONLY` e `media_ready=false`; dica de geometria não é aceitação de criativo por canal, não autoriza publicação. Prévia visual renderizada e certificação de upload real continuam TARGET/PRODUCTION_GATE.
- Testes adicionados: origem preservada/linhagem, origem indevida negada e previews por canal sem elevação de autorização. Todos dependem do resultado de CI deste HEAD; não certificar antes da execução.
- Pendências reais: edição binária/transformação de pixels não implementada (a revisão atual é nova geração baseada em prompt), policy específica de cada canal, custos oficiais, credenciais e homologação de publicação, política de retenção HUMAN_DECISION; PR #73 ainda Draft sem merge. Não confundir estes previews informativos com visualização real da peça publicada.
