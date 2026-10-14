# CampaIA — AGENTS.md

## Cronograma Mestre Operacional das Tarefas Restantes até Pronto Comercial

**Data de reconciliação:** 14/10/2026  
**Repositório canônico:** faabio3131/f-m-tecnologia-campaia  
**CURRENT confirmado na criação deste arquivo:** main@4d17f41c35d95ff473ab420be5164407c9166bb5  
**Produção:** não autorizada e não tocada nesta reconciliação  
**Fonte mestra:** docs/CRONOGRAMA_MESTRE_EXECUCAO_TOTAL_CAMPAIA_20260927.md quando presente no repositório, e o documento “CAMPAIA - CRONOGRAMA MESTRE DE EXECUCAO TOTAL ATE PRONTO COMERCIAL” v1.0 de 27/09/2026.  
**Tracker complementar:** docs/CAMPAIA_CONTROLE_MESTRE_EXECUCAO_20260927.md

Este arquivo é a camada operacional para futuros agentes/executores. Ele organiza o trabalho restante a partir do CURRENT real. Ele NÃO substitui a fonte mestra, ADRs, evidências nem o CURRENT técnico.

---

## 1. REGRA SUPREMA

Antes de executar qualquer tarefa relevante:

1. Confirmar repositório canônico.
2. Confirmar branch, HEAD e estado real da main.
3. Confirmar PRs abertas relacionadas ao bloco.
4. Ler este AGENTS.md.
5. Ler somente o Cronograma Mestre, ADRs e evidências diretamente ligados ao Work Package.
6. Comparar CURRENT x TARGET.
7. Preservar tudo que já estiver DONE_VERIFIED.
8. Executar um Work Package por vez, salvo trilhas explicitamente paralelas.
9. Testar antes de commit.
10. Gerar evidência reproduzível.
11. Atualizar tracker/evidência do bloco.
12. Parar antes de merge, deploy, produção, GO/NO-GO, alteração irreversível ou HUMAN_DECISION sem autorização expressa do Diretor.

Documentação histórica nunca prevalece silenciosamente sobre o CURRENT.

---

## 2. STATUS OFICIAIS

Usar somente:

- DONE_VERIFIED — construído e comprovado por código/evidência/teste no CURRENT.
- PARTIAL — parte existe, mas o bloco ainda não satisfaz a Definition of Done.
- TARGET — ainda precisa ser construído.
- HUMAN_DECISION — exige decisão explícita do Diretor.
- EXTERNAL_CREDENTIAL — depende de credencial externa.
- EXTERNAL_INFRASTRUCTURE — depende de infraestrutura/conta externa.
- EXTERNAL_APPROVAL — depende de aprovação de terceiro.
- PRODUCTION_GATE — funciona antes de produção, mas exige gate específico para promoção.
- BLOCKED — bloqueado por dependência real.
- SUPERSEDED — substituído por estado/documento/fluxo mais novo.

Nunca declarar “100% pronto”, “homologado”, “produção pronta” ou “comercialmente disponível” sem evidência correspondente ao gate.

---

## 3. INVARIANTES CONSTITUCIONAIS DO CAMPAIA

- CampaIA é SaaS comercial multi-tenant.
- Nova FM Tecnologia e FM Tecnologia são tenants comuns de teste/homologação.
- Nenhuma conta FM pode possuir privilégio oculto, ID hardcoded, código exclusivo, token manual de desenvolvedor ou deploy especial.
- PLATFORM e TENANT são configurações distintas.
- Segredos de tenant ficam em Vault/Secret Manager e domínio referencia segredo por SecretRef ou mecanismo equivalente.
- Nenhum segredo real entra no Git.
- Mutação crítica cobre happy path, negative path, replay/idempotência e cross-tenant; quando aplicável também restart, concorrência, atomicidade e multi-worker.
- Campanha nova exige aprovação humana conforme política vigente.
- Simulador, mock, sandbox, staging, homologação e produção são estados diferentes.
- Sucesso em mock/sandbox não prova integração real de produção.
- Visual Premium integral somente após fechamento funcional principal.
- Nenhum merge/deploy/produção/GO-NO-GO sem autorização expressa.

---

## 4. CURRENT CERTIFICADO A PRESERVAR

### F0 / G0
- G0 DONE_VERIFIED.
- Matriz CURRENT/TARGET e reconciliação documental já realizadas.
- Documentos históricos superseded preservados sem orientar nova implementação.

### F1 / G1
- G1 DONE_VERIFIED.
- Login Google real em staging já comprovado.
- Onboarding explícito cria tenant, unidade Principal e OWNER sem inclusão manual em banco.
- F1 permanece PARTIAL somente porque entrada comercial trial/compra precisa ser fechada com F5/G5.

### F2 / G2
- F2/G2 PARTIAL.
- CRUD de unidades, usuários/memberships/roles, ownership transfer, revogação de sessões, RBAC, step-up e Web já existem e foram certificados internamente.
- Pendência concreta: E2E externo em staging de administração sensível completa com reautenticação Google real, mutação administrativa e prova de autoridade/revogação/cross-tenant.

### F3 / G3
- G3 DONE_VERIFIED.
- PostgreSQL/Cloud SQL runtime adapter, migrations, atomicidade, locks, idempotência persistente, shared sessions/OAuth/approvals/dedupe e multi-process já certificados.
- Não refazer runtime base.

### F4 / G4
- F4/G4 DONE_VERIFIED.
- Staging real, Cloud Run, Cloud SQL, KMS, Secret Manager, OIDC/WIF, migration gate, rollback e login/onboarding real já certificados.
- Não reprovisionar arquitetura por documentação antiga.

### F5 / G5
- F5/G5 PARTIAL.
- WP-F05-01 persistência billing: DONE_VERIFIED.
- WP-F05-02 entitlements/trial lifecycle: DONE_VERIFIED.
- WP-F05-03 upgrade/downgrade/cancelamento/reativação: DONE_VERIFIED.
- WP-F05-04 PAST_DUE/grace/dunning/recovery: DONE_VERIFIED.
- PR #42 pós-merge certificada em main@4d17f41c35d95ff473ab420be5164407c9166bb5.
- Backend #223, Frontend #161 e F4 Platform CI #57: success.
- Correção de security audit frontend da PR #41 permanece DONE_VERIFIED.

### F6 — CURRENT parcial
- Brand Profile textual já possui create/list, persistência e tenant scoping.
- Ainda não é Brand Kit completo com assets reais.

### F7 — CURRENT parcial
- AIGateway e provider Gemini real já existem quando configurados.
- SimulatedAIProvider permanece fallback de dev/test sem fingir produção.
- Estratégia textual, state machine, policy base e approvals já possuem componentes.
- Geração de imagens, criativos completos, preview por canal e fluxo completo até aprovação ainda não estão fechados.

### F8 — CURRENT ainda não real
- OAuth de Connections permanece explicitamente simulado no produto atual.
- State single-use, tenant binding, step-up e Vault já possuem fundação reutilizável.
- Conector Google Ads real multi-tenant ainda precisa ser implementado/homologado.

### F9 — CURRENT
- Publicação real Google Ads ainda não existe.
- Publish/pause atuais usam ProviderSimulator.
- Insights atuais retornam placeholder vazio de forma honesta.

### F12 — CURRENT parcial
- PublicationSaga e state machine de publicação existem.
- Ainda operam sem três conectores reais; não reimplementar Saga do zero.

### F13 — CURRENT parcial
- Budget engine, autonomy, kill switch, audit e endpoint de insights existem.
- Analytics real e loop de otimização ainda faltam.

### F14 — CURRENT parcial
- Organização, usuários, permissões, connections, audit, autonomy e parte das telas administrativas existem.
- Self-service comercial completo, exportações, notificações, suporte e lifecycle legal ainda faltam.

---

## 5. CAMINHO CRÍTICO RESTANTE

A ordem preferencial é:

1. Fechar resíduo G2 quando ambiente estiver disponível.
2. Fechar F5/G5.
3. F6 Brand Kit/assets reais.
4. F7 IA/criativos/policy/previews.
5. F8 Google connect real.
6. F9 Google publish/reconciliation/metrics.
7. F10 Meta real.
8. F11 WhatsApp real.
9. F12 orquestração multicanal.
10. F13 analytics/alertas/otimização.
11. F14 administração/support self-service.
12. F15 Visual Premium total.
13. F16 security/LGPD/compliance.
14. F17 performance/resiliência/observabilidade/DR.
15. F18 homologação ponta a ponta.
16. F19 release candidate + GO/NO-GO.
17. F20 produção + liberação comercial controlada.

Não iniciar F15 antes do freeze funcional principal F5-F14.

---

# 6. FILA MESTRA DE WORK PACKAGES RESTANTES

## WP-G2-01 — Homologação externa IAM/RBAC sensível

**Status:** PARTIAL / EXTERNAL_INFRASTRUCTURE  
**Pode rodar em paralelo com F5 quando staging estiver disponível.**

### TARGET
Executar no staging real:

- login Google real;
- step-up por reautenticação Google;
- criar/renomear/desativar/reativar unidade;
- convidar/alterar membership/role;
- promover novo OWNER;
- rebaixar OWNER anterior sem remover último OWNER;
- provar revogação imediata de sessão;
- provar cross-tenant e business-unit isolation;
- provar que admin de tenant não recebe autoridade de plataforma;
- registrar audit trail real.

### DoD
G2 pode virar DONE_VERIFIED somente com evidência E2E externa reproduzível.

---

# FASE 5 — BILLING, PLANOS, TRIAL E OPERAÇÃO COMERCIAL

## WP-F05-05 — Congelar política comercial real

**Status:** HUMAN_DECISION

Decisões que precisam de aprovação explícita antes de serem tratadas como produto real:

- nomes dos planos;
- preços;
- franquias;
- excedentes/créditos;
- limites de usuários;
- limites de campanhas;
- canais/recursos/IA por plano;
- duração de trial;
- regras comerciais de upgrade/downgrade;
- grace period real;
- cadência real de dunning;
- métodos de pagamento de lançamento;
- política de refund/estorno quando aplicável;
- política fiscal/tributária junto a contador/jurídico.

**Regra:** mecanismo já existe; não hardcodar números comerciais no código.

## WP-F05-06 — Checkout/assinatura e Asaas real

**Status:** EXTERNAL_CREDENTIAL / EXTERNAL_APPROVAL / TARGET

- configurar conta/credenciais Asaas de produção quando juridicamente disponíveis;
- manter credenciais de plataforma fora do repositório;
- implementar checkout/assinatura real;
- Pix/boleto/cartão conforme política aprovada;
- validar webhook real em ambiente apropriado;
- provar dedupe/replay;
- testar pagamento duplicado, atrasado, recusado e cancelado;
- garantir que evento financeiro é a autoridade do entitlement;
- não liberar plano pago apenas por retorno do browser;
- reconciliação polling/webhook quando necessária.

## WP-F05-07 — Billing self-service Web

**Status:** TARGET

- tela de plano atual;
- status da assinatura;
- consumo/franquia/créditos;
- upgrade/downgrade;
- cancelamento/reativação;
- PAST_DUE/grace/status de cobrança;
- histórico de pagamentos/faturas;
- estados loading/erro/retry;
- RBAC Finance/Owner adequado;
- step-up para mutações sensíveis;
- responsive/a11y mínima sem antecipar F15.

## WP-F05-08 — Refund/fiscal/handoff real

**Status:** HUMAN_DECISION / EXTERNAL_APPROVAL

- fechar política de estorno/reembolso se aplicável;
- fechar responsabilidade por NF/tributação;
- ligar fiscal handoff real somente quando juridicamente definido;
- testar reversão/reconciliação;
- jamais declarar emissão fiscal pronta sem homologação externa.

## WP-F05-09 — Gate G5 real

**Status:** PRODUCTION_GATE / EXTERNAL_CREDENTIAL

E2E obrigatório:

trial ou assinatura -> tenant -> cobrança real -> pagamento -> webhook/reconciliação -> entitlement server-authoritative.

Cobrir também:

- trial expirado;
- conversão;
- upgrade;
- downgrade;
- PAST_DUE;
- recovery;
- cancelamento;
- reativação;
- replay;
- cross-tenant.

**Gate G5:** usuário consegue iniciar trial/assinar, pagar e ter entitlement ativado por evento real de pagamento.

**Efeito adicional:** após G5, reconciliar F1 para remover a dependência comercial residual.

---

# FASE 6 — BRAND KIT E ASSETS REAIS

## WP-F06-01 — Brand Kit CRUD completo

**Status:** PARTIAL

Preservar BrandProfile existente e completar:

- editar Brand Kit;
- produtos/ofertas;
- diferenciais;
- tom de voz;
- paleta;
- restrições;
- lifecycle/versionamento quando necessário;
- auditoria;
- RBAC;
- idempotência;
- cross-tenant.

## WP-F06-02 — Asset Storage multi-tenant

**Status:** TARGET

- upload real em Cloud Storage;
- MIME/tamanho/dimensão;
- imagem/vídeo conforme escopo;
- segurança/antimalware conforme risco;
- signed/private URLs;
- delete/retenção;
- metadata;
- isolamento por tenant;
- testes de URL/objeto cross-tenant;
- sem bucket path confiado do browser.

## WP-F06-03 — Integrar Brand Kit ao briefing/IA

**Status:** TARGET

- Brand Kit selecionável em campanha;
- assets e restrições entram no Context Pack da IA;
- reutilização de materiais por campanha;
- proveniência;
- nenhuma informação de outro tenant em prompt.

## WP-F06-04 — Gate G6

**Gate:** tenant novo cadastra sua marca e usa assets reais sem suporte técnico.

---

# FASE 7 — IA, CRIATIVOS, POLICY E PREVIEWS

## WP-F07-01 — AI Gateway comercial governado

**Status:** PARTIAL

Preservar AIGateway/Gemini existentes e completar:

- provider/model routing permitido;
- fallback governado;
- timeout/retry/backoff;
- circuit breaker real;
- custo por tenant no ledger;
- budget de IA;
- proveniência completa;
- sanitização/minimização de dados;
- observabilidade de provider;
- fail-closed para schema inválido.

## WP-F07-02 — Copy generation completa

**Status:** TARGET/PARTIAL

- títulos;
- descrições;
- CTAs;
- variações;
- formatos por canal;
- regeneração seletiva;
- versionamento;
- edição humana;
- trilha de prompt/modelo/output sem segredo.

## WP-F07-03 — Image/creative generation

**Status:** TARGET

- escolher provider real;
- quadrado;
- vertical;
- story/banner quando aplicável;
- regerar por formato;
- upload manual alternativo;
- provenance asset/model/prompt;
- armazenar outputs no storage do tenant;
- custo no ledger;
- moderation/safety apropriada.

## WP-F07-04 — Policy final

**Status:** PARTIAL

- validação determinística;
- validação assistida quando necessário;
- alegações;
- categorias sensíveis;
- regras por canal;
- políticas versionadas;
- bloqueio/alerta com motivo;
- audit trail;
- negative tests.

## WP-F07-05 — Preview e edição

**Status:** TARGET

- Preview Google;
- Preview Facebook;
- Preview Instagram;
- Preview WhatsApp/click-to-WhatsApp quando aplicável;
- edição antes da aprovação;
- responsive;
- não publicar nada nesta etapa.

## WP-F07-06 — Gate G7

Campanha deve chegar a aprovação com estratégia, copy, assets, policy e previews reais.

---

# FASE 8 — GOOGLE ADS REAL, MULTI-TENANT E CONFIGURÁVEL

## WP-F08-01 — Platform Google Ads

**Status:** EXTERNAL_INFRASTRUCTURE / EXTERNAL_APPROVAL

Reconfirmar documentação oficial atual antes de codificar detalhes finais.

- Google Cloud Project por ambiente;
- billing válido;
- Google Ads API habilitada;
- API access level confirmado;
- OAuth Client Web;
- Client Secret em Secret Manager;
- redirect URI oficial;
- escopo adwords;
- requisitos atuais de Developer Token/API access;
- nenhum ID de conta FM no código.

## WP-F08-02 — OAuth Google Ads por tenant

**Status:** TARGET

Substituir somente o fluxo simulado:

- OAuth Start real;
- state opaco/single-use;
- callback server-side;
- binding de sessão/identidade do Start;
- token exchange server-side;
- refresh token no Vault do tenant;
- access token runtime;
- revocation/invalid_grant;
- reauth;
- audit seguro.

## WP-F08-03 — Discovery e seleção de conta

**Status:** TARGET

- ListAccessibleCustomers ou mecanismo oficial atual;
- usuário escolhe conta explicitamente;
- customer ID e manager/login customer ID como metadata da Connection;
- nunca selecionar primeira conta silenciosamente;
- test account/read-only primeiro;
- cross-tenant.

## WP-F08-04 — Gate G8

Tenant arbitrário conecta a própria conta Google Ads pelo mesmo fluxo usado pelos tenants de homologação.

---

# FASE 9 — GOOGLE ADS PUBLICAÇÃO, RECONCILIAÇÃO E MÉTRICAS

## WP-F09-01 — Adapter Google Ads real

**Status:** TARGET

- Campaign;
- Budget;
- AdGroup;
- Ads;
- assets;
- mapping IDs internos/externos;
- API version centralizada;
- error taxonomy;
- quota/rate-limit.

## WP-F09-02 — Mutations seguras

- idempotência externa;
- provider-side reconciliation;
- Saga/compensação;
- partial failure;
- retries governados;
- não duplicar gasto.

## WP-F09-03 — Operação Google real

- pause;
- resume;
- budget change com approval;
- kill switch;
- drift detection;
- reconciliation jobs.

## WP-F09-04 — Métricas Google

- fetch real;
- last_synced;
- mapping para modelo interno;
- zero métricas fabricadas.

## WP-F09-05 — Gate G9

Campanha Google real criada, reconciliada, pausada, retomada e medida sem duplicação.

---

# FASE 10 — META ADS / FACEBOOK / INSTAGRAM

## WP-F10-01 — Platform Meta
**Status:** EXTERNAL_APPROVAL

- Meta App por ambiente;
- Business Verification;
- App Review/permissões;
- secrets de plataforma no Secret Manager.

## WP-F10-02 — OAuth/Accounts tenant
- OAuth tenant-scoped;
- Ad Accounts discovery;
- seleção explícita;
- Pages/Instagram linkage;
- tokens no Vault;
- expiry/reauth.

## WP-F10-03 — Publish/operate
- Campaign/Ad Set/Ads/assets;
- pause/resume;
- budget;
- reconciliation;
- insights;
- rate limit/error mapping;
- cross-tenant.

## WP-F10-04 — Gate G10
Tenant arbitrário conecta Meta e publica/mede campanha homologada.

---

# FASE 11 — WHATSAPP BUSINESS / CLICK-TO-WHATSAPP

## WP-F11-01 — Onboarding e identidade
**Status:** EXTERNAL_APPROVAL

- WABA/account onboarding;
- número comercial;
- permissions;
- tokens no Vault por tenant.

## WP-F11-02 — Webhook e delivery
- assinatura/verificação;
- entrega/erro;
- retry/idempotência;
- consentimento/opt-out;
- audit sem conteúdo sensível desnecessário.

## WP-F11-03 — Click-to-WhatsApp
- integração com Meta quando aplicável;
- templates somente onde produto realmente precisa.

## WP-F11-04 — Gate G11
Tenant real conecta WhatsApp e usa o fluxo suportado sem configuração manual de desenvolvedor.

---

# FASE 12 — ORQUESTRAÇÃO MULTICANAL

## WP-F12-01 — Connector Fabric real na Saga

**Status:** PARTIAL

Preservar PublicationSaga existente e trocar simuladores por adapters reais através de contrato comum.

## WP-F12-02 — Saga multi-provider
- publication partial failure;
- compensation segura;
- retry;
- replay;
- restart;
- reconciliation;
- provenance por provider/recurso.

## WP-F12-03 — Estado real
- PUBLISHING somente com operação real aberta;
- ACTIVE somente após reconciliação válida;
- divergência visível;
- histórico de versões/diffs.

## WP-F12-04 — Budget/kill switch multicanal
- orçamento consolidado versus canal;
- kill switch campaign/tenant/account;
- aplicação real nos providers;
- audit.

## WP-F12-05 — Gate G12
Falha parcial não corrompe estado interno nem duplica gasto.

---

# FASE 13 — MÉTRICAS, INSIGHTS, ALERTAS E OTIMIZAÇÃO

## WP-F13-01 — Analytics ingestion
**Status:** PARTIAL

Substituir placeholder vazio somente por dados reais:

- ingestão agendada;
- CTR;
- CPC;
- CPA;
- ROAS;
- gasto;
- breakdown por canal/criativo;
- snapshots históricos;
- freshness/last_synced.

## WP-F13-02 — Alertas
- 80%/100% budget;
- auth/reconnect;
- provider error;
- e-mail;
- in-app;
- dedupe/cooldown.

## WP-F13-03 — Performance Agent
- sugestões explicáveis;
- dados de origem;
- confidence/limitações;
- nenhuma ação direta fora da policy.

## WP-F13-04 — Autonomia governada
- Manual;
- Automático somente em campanhas já aprovadas;
- limites;
- step-up na ativação;
- audit;
- reversibilidade quando aplicável.

## WP-F13-05 — Gate G13
Dashboard mostra dados reais e automação respeita autonomia/limites/trilha.

---

# FASE 14 — ADMINISTRAÇÃO E SUPORTE SELF-SERVICE

## WP-F14-01 — Consolidar superfícies existentes
**Status:** PARTIAL

Reauditar antes de alterar:

- perfil/empresa;
- usuários/permissões;
- unidades;
- connections;
- billing;
- audit;
- approvals;
- autonomy.

Não reimplementar o que já existe.

## WP-F14-02 — Histórico/export
- audit filtros;
- CSV/PDF quando aplicável;
- approvals history;
- versions history;
- data export do tenant.

## WP-F14-03 — Notification Center
- central in-app;
- preferências;
- provider/billing/security notifications;
- lidas/não lidas;
- sem vazamento cross-tenant.

## WP-F14-04 — Connection lifecycle self-service
- reconnect;
- revoke;
- delete/desconectar;
- revogar segredo;
- diagnósticos seguros.

## WP-F14-05 — Account lifecycle/LGPD hooks
- export;
- solicitação de exclusão;
- encerramento;
- retention state;
- sem hard delete que destrua audit obrigatório antes da política legal.

## WP-F14-06 — Support
- help/contact;
- diagnostics seguros;
- correlation IDs;
- sem segredo/PII desnecessária.

## WP-F14-07 — Gate G14
Cliente administra a própria conta sem suporte de engenharia.

---

# FASE 15 — VISUAL PREMIUM COMPLETO

**Status:** TARGET  
**Pré-condição:** freeze funcional de F5-F14.

## WP-F15-01 — Design System Premium
- identidade oficial;
- tokens;
- tipografia;
- spacing;
- radius;
- shadows/elevation;
- motion;
- component library;
- estados loading/error/success/disabled;
- skeleton/empty;
- iconografia;
- charts;
- forms;
- tables;
- modal/drawer/confirm.

## WP-F15-02 — Revisão tela a tela
Cobrir:

- login;
- trial/onboarding;
- empresa;
- unidade;
- dashboard;
- conexões;
- Brand Kit;
- briefing;
- estratégia;
- criativos;
- preview;
- aprovação;
- métricas;
- histórico;
- otimizações;
- autonomia;
- IA/modelos;
- usuários/permissões;
- billing;
- auditoria;
- notificações;
- erros 401/403/404/429/500;
- provider unavailable.

## WP-F15-03 — Responsive e acessibilidade visual
- desktop;
- tablet;
- mobile Web;
- WCAG 2.2 AA;
- keyboard;
- focus visible;
- contrast;
- reduced motion;
- visual regression;
- Lighthouse/performance budget.

**Gate G15:** Diretor aprova visualmente todos os fluxos sem regressão funcional.

---

# FASE 16 — SECURITY, PRIVACY, LGPD E COMPLIANCE

## WP-F16-01 — Threat model final
**Status:** PARTIAL

- arquitetura final;
- trust boundaries;
- OAuth;
- uploads;
- billing;
- IA;
- providers;
- multi-tenant.

## WP-F16-02 — AppSec final
- SAST;
- dependency audit;
- secret scan;
- DAST;
- pentest/manual review;
- CSRF;
- XSS;
- SSRF;
- injection;
- open redirect;
- upload security;
- OAuth review;
- tenant isolation negative suite;
- authorization matrix;
- rate limit;
- abuse protection.

## WP-F16-03 — LGPD
**Status:** HUMAN_DECISION / EXTERNAL_APPROVAL

- mapa de dados pessoais;
- bases legais;
- privacy policy;
- termos;
- cookies quando aplicável;
- DPA;
- encarregado/processadores quando aplicável;
- retenção;
- exclusão;
- exportação;
- suboperadores;
- residência de dados;
- contratos cloud.

**Gate G16:** zero P0/P1; termos/LGPD prontos; riscos residuais aceitos formalmente.

---

# FASE 17 — PERFORMANCE, RESILIÊNCIA, OBSERVABILIDADE E DR

## WP-F17-01 — SLO/observabilidade
**Status:** TARGET

- SLOs;
- métricas;
- traces;
- logs estruturados sem segredo;
- dashboards;
- error tracking;
- alertas.

## WP-F17-02 — Load/concorrência
- fluxos críticos;
- 100 campanhas simultâneas ou critério revisado;
- multi-worker;
- queue backlog/backpressure;
- quota exhaustion.

## WP-F17-03 — Resiliência
- timeout;
- retry/backoff;
- circuit breakers;
- DB reconnect/failover;
- provider outage;
- dead-letter/reconciliation quando aplicável.

## WP-F17-04 — Backup/restore/DR
- backup real;
- restore real;
- RPO/RTO definidos;
- DR drill;
- runbooks de incidente.

**Gate G17:** incidentes críticos simulados possuem detecção, resposta e recuperação demonstradas.

---

# FASE 18 — STAGING FINAL E HOMOLOGAÇÃO PONTA A PONTA

## WP-F18-01 — UAT jornada comercial integral

Executar como empresa nova:

- novo trial;
- tenant;
- Owner;
- unidade;
- segundo usuário/aprovador;
- Brand Kit + upload;
- Google;
- Meta;
- WhatsApp;
- briefing;
- estratégia;
- criativos;
- policy;
- preview;
- aprovação por outro usuário;
- publish Google;
- publish Meta;
- fluxo WhatsApp suportado;
- reconciliação;
- insights;
- budget alert;
- pause/resume;
- kill switch;
- autonomia;
- billing/trial/upgrade/inadimplência/cancelamento;
- provider revoke/reconnect;
- audit/export;
- logout/relogin/switch multi-tenant;
- provider errors/recovery;
- premium/responsive/a11y.

## WP-F18-02 — Isolation UAT
- Tenant A nunca lê B;
- nunca resolve segredo B;
- nunca usa Connection B;
- nunca muda budget/campaign B;
- admin tenant nunca vira plataforma.

**Gate G18:** UAT assinada pelo Diretor, evidências anexadas, zero blocker conhecido.

---

# FASE 19 — PRE-PRODUCTION E GO/NO-GO

## WP-F19-01 — Release Candidate
**Status:** PRODUCTION_GATE

- main limpa;
- tag/RC imutável;
- CI completo;
- staging arquiteturalmente equivalente;
- migrations ensaiadas;
- backup pré-deploy;
- rollback testado.

## WP-F19-02 — Production configuration
- segredos;
- domínio/TLS/DNS;
- OAuth redirect URIs;
- Google/Meta/WhatsApp approvals;
- Asaas produção;
- planos/trial;
- e-mail transacional;
- monitoring/on-call;
- suporte;
- runbooks;
- zero fixture/test mode;
- zero segredo de teste;
- zero privilégio FM.

## WP-F19-03 — GO/NO-GO
Gerar relatório factual com:

- critérios;
- evidências;
- blockers;
- riscos residuais;
- custo;
- rollback;
- NO-GO automático se critério crítico estiver aberto.

**Gate G19:** decisão explícita do Diretor. Não executar deploy por silêncio.

---

# FASE 20 — PRODUÇÃO E DISPONIBILIDADE COMERCIAL

## WP-F20-01 — Deploy controlado
**Status:** PRODUCTION_GATE

Somente após autorização explícita.

- deploy;
- migration;
- smoke;
- health;
- rollback ready.

## WP-F20-02 — First-live proofs
- primeiro tenant interno/homologação;
- primeiro trial externo controlado;
- primeiro pagamento real;
- primeira conexão externa por tenant;
- primeira campanha real aprovada;
- primeira reconciliação/métricas;
- cancelamento/reativação quando seguro.

## WP-F20-03 — Hypercare
- 24–72h monitoring intensivo;
- P0/P1 zero antes de ampliar aquisição;
- incident response;
- métricas comerciais/técnicas;
- liberação gradual.

**Gate G20:** somente após estas evidências o CampaIA pode receber status COMERCIALMENTE DISPONIVEL.

---

## 7. TRACK PARALELO EXTERNO — NÃO ESQUECER

Este track pode avançar em paralelo sem furar o caminho crítico.

### Google
- confirmar Google Ads API access level atual;
- OAuth Web Client/redirects de ambientes;
- aprovação/requisitos atuais para produção.

### Meta
- Business Verification;
- App Review;
- permissions de Ads;
- permissions WhatsApp/WABA.

### WhatsApp
- WABA;
- número;
- verificação/configuração oficial;
- webhook/permissions.

### Billing/jurídico
- estrutura jurídica/CNPJ quando exigido;
- Asaas produção;
- política fiscal;
- contador;
- refund/estorno.

### LGPD/legal
- Termos;
- Privacy Policy;
- DPA/suboperadores;
- retenção/exclusão;
- revisão jurídica antes de G19.

### Operação
- e-mail transacional;
- suporte;
- monitoring/on-call;
- domínio/DNS/TLS de produção.

Nenhum blocker externo deve ser falsamente promovido para DONE_VERIFIED.

---

## 8. DEFINITION OF DONE DE TODO WORK PACKAGE

Antes de marcar DONE_VERIFIED, validar todos os pontos aplicáveis:

- implementação no CURRENT correto;
- sem segredo real no repositório;
- sem hardcode por cliente;
- tenant isolation;
- RBAC/step-up;
- happy path;
- negative path;
- cross-tenant;
- idempotência/replay;
- restart/persistência quando durável;
- concorrência/multi-worker quando crítico;
- atomicidade quando houver mutação composta;
- contrato/API sincronizado;
- frontend atualizado;
- acessibilidade mínima preservada;
- audit/observabilidade;
- docs/evidência;
- suite completa verde;
- PR CI verde;
- pós-merge CI verde;
- blocker externo honestamente classificado;
- produção não inferida de staging.

---

## 9. REGRA DE TESTES PARA MUTAÇÕES CRÍTICAS

Toda mutação de alto impacto deve cobrir, no mínimo:

1. happy path;
2. autorização negada;
3. input inválido;
4. cross-tenant;
5. replay com a mesma idempotency key;
6. chave nova após efeito anterior;
7. concorrência se possível;
8. crash/restart se houver estado durável;
9. audit event correto;
10. rollback/compensação se tocar provider externo.

Para dinheiro, campanhas, budget, permissions, OAuth e segredos, não aceitar cobertura inferior sem justificativa formal.

---

## 10. STOP CONDITIONS

Parar e solicitar autorização/decisão quando houver:

- merge;
- deploy;
- produção;
- migration real;
- credencial real nova;
- alteração de billing/spending;
- custo cloud relevante;
- criação/rotação de segredo real;
- mudança irreversível;
- GO/NO-GO;
- decisão comercial de preço/trial/refund;
- decisão jurídica/LGPD;
- alteração de arquitetura irreversível;
- promoção de permission scope externo;
- qualquer HUMAN_DECISION.

Não interpretar silêncio como autorização.

---

## 11. FORMATO OBRIGATÓRIO DE RETOMADA

Em cada nova sessão relevante, informar objetivamente:

- CURRENT confirmado: repo / branch / HEAD;
- fase/gate atual;
- DONE_VERIFIED preservado;
- blockers reais;
- Work Package exato em execução;
- TARGET;
- fora de escopo;
- riscos;
- testes planejados;
- evidências ao terminar.

Ao terminar:

- HEAD da branch;
- arquivos alterados;
- testes;
- CI;
- evidência;
- status oficial;
- pendências;
- autorização necessária para o próximo gate.

---

## 12. CHECKLIST FINAL DE “NÃO ESQUECER”

Antes de qualquer declaração de pronto comercial, todas precisam ser SIM:

- cliente novo entra sem desenvolvedor;
- cliente cria tenant/empresa;
- cliente gerencia usuários/unidades;
- cliente assina/paga/atualiza plano;
- cliente conecta Google;
- cliente conecta Meta;
- cliente conecta WhatsApp;
- nenhuma conta FM hardcoded;
- nenhum segredo tenant fora do Vault;
- Brand Kit aceita assets reais;
- IA gera estratégia/copy/assets reais;
- Policy valida;
- Preview funciona;
- Approval segregado funciona;
- publicação real é idempotente;
- partial failure é reconciliado;
- métricas são reais;
- budget/kill switch funcionam nos providers reais;
- autonomia respeita limites;
- audit/export estão completos;
- billing/fiscal estão honestamente classificados;
- banco/sessões suportam multi-instância;
- segredos usam Secret Manager/KMS em produção;
- backup/restore foram testados;
- load test passou;
- pentest/security gate passou;
- LGPD/termos estão publicados;
- Visual Premium foi aprovado tela a tela;
- acessibilidade passou;
- staging homologou jornada completa;
- CI do release candidate está verde;
- rollback foi ensaiado;
- monitoring/suporte/runbooks estão ativos;
- Diretor aprovou produção explicitamente;
- primeiro tenant externo controlado funcionou.

Se qualquer resposta crítica for NÃO, CampaIA não é COMERCIALMENTE DISPONIVEL.

---

## 13. RESULTADO FINAL OBRIGATÓRIO

Ao concluir G20, uma empresa desconhecida do time de engenharia deve conseguir, sem intervenção de desenvolvedor:

1. entrar em trial ou contratar;
2. criar empresa/tenant;
3. cadastrar usuários/unidades;
4. conectar Google/Meta/WhatsApp próprios;
5. cadastrar Brand Kit e assets;
6. criar briefing;
7. receber estratégia e criativos de IA;
8. revisar policy/preview;
9. aprovar com segregação de função;
10. publicar de forma idempotente;
11. acompanhar métricas reais;
12. receber alertas e sugestões;
13. usar autonomia dentro dos limites autorizados;
14. pagar e gerenciar plano;
15. administrar conta;
16. operar em interface premium, responsiva e acessível;
17. contar com segurança, privacidade, auditabilidade, resiliência, suporte e recuperação adequados a um SaaS comercial.

Somente esse estado encerra o Cronograma Mestre.
