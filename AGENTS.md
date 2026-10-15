# CampaIA — AGENTS.md

## Cronograma Mestre Operacional — DELTA REAL RESTANTE

**Data de reconciliação:** 15/10/2026
**Repositório canônico:** `faabio3131/f-m-tecnologia-campaia`  
**CURRENT confirmado:** `main@9fcd24172e38c0e45b28b80169877f41aefbc052`
**Produção:** não autorizada  
**Fonte mestra:** Cronograma Mestre F0–F20/G0–G20  
**Evidência desta reconciliação:** `docs/evidence/AUDITORIA_CURRENT_DELTA_REAL_RESTANTE_20261014.md`

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
- Brand Kit ainda não possui upload/assets completos;
- fluxo de criativos/imagem/preview ainda não está completo;
- Billing Web inicial e histórico/fatura hospedada integrados nas PRs #45/#46; entrada inicial/trial integrados na PR #47; consumo e checkout completo pendentes;
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
| F5 | PARTIAL avançado | política comercial + Billing Web + produção Asaas + E2E real |
| F6 | PARTIAL | upload/assets + aplicação do Brand Kit |
| F7 | PARTIAL avançado | wiring dos agentes, imagem/criativos, preview/ajustes |
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

### Falta
1. política V1 aprovada pelo Diretor em 15/10/2026; registro na proposta da PR #48;
   publicação segue condicionada a custos/jurídico/homologação/produção;
2. arquivo/catálogo comercial real;
3. Billing Web restante:
   - medição comercial persistente de uso/créditos (CostLedger em memória não é franquia mensal);
   - entrada inicial/trial Web: WP-R02-03 integrado na PR #47, preservar;
   - contratação inicial/checkout completo;
4. credenciais/conta Asaas produção quando apropriado;
5. checkout/fluxo de pagamento real;
6. E2E real:
   trial/assinatura -> cobrança -> pagamento -> webhook -> entitlement.

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
excedente final. Ver `docs/WP_R02_12_RETIRADA_RENOVACAO_ABERTA_20261015.md`. WP-R02-13 em validação:\nevidência mínima de devoluções pendentes/parciais/integralmente concluídas, sem nova franquia.\nVer `docs/WP_R02_13_OBSERVACOES_ESTORNO_20261015.md`. Antes da ativação V1,
resolver refunds/chargebacks, garantia e conflitos; depois scheduler/dunning único. Catálogo real continua
desabilitado; não certificar G5 com simulador ou apenas CI.

**Gate G5:** pagamento real ativa entitlement sem intervenção de desenvolvedor.

---

## WP-R03 — Completar F6 Brand Kit/assets
**Status:** PARTIAL

### Já existe
Brand Profile textual, persistência, Web, Cloud Storage na infraestrutura.

### Falta
- edit/update do Brand Kit;
- upload real de logo/assets;
- metadata e private/signed access;
- isolamento cross-tenant dos objetos;
- lifecycle/delete/retenção;
- aplicar Brand Kit selecionado ao pipeline de campanha/IA.

**Não reprovisionar Cloud Storage sem drift comprovado.**

---

## WP-R04 — Completar F7 IA/criativos/preview
**Status:** PARTIAL avançado

### Já existe
AIGateway, Gemini real, agentes copy/audience/policy/performance/strategist, Policy Engine e approvals.

### Falta
- ligar copy/audience/policy/performance ao fluxo API/Web;
- completar creative asset model;
- geração de imagem real;
- armazenar criativos no storage do tenant;
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
