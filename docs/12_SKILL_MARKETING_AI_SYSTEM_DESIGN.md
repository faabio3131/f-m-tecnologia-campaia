# CAMPAIA — Skill "Marketing AI System Design" (preservada do sandbox local)

**Data:** 27 de agosto de 2026
**Autor:** Claude (Engenheiro Sênior)
**Natureza deste documento:** esta skill é a base de disciplina de arquitetura usada durante todo o projeto CAMPAIA (referenciada, por exemplo, na fundamentação de D-05 em `03_ADR_INICIAIS.md`). Até hoje ela existia **apenas** como arquivo no sandbox local temporário desta sessão (`/home/claude/campaia/.skill/`), nunca havia sido salva como documento no Drive — um "desvio" que ficou pendente desde o início do projeto. Salvo aqui para que não dependa mais do ambiente temporário de uma sessão específica, que é descartado ao final de cada sessão.

**Conteúdo original preservado abaixo, sem alterações de substância** (dois arquivos: a skill em si, e sua referência de arquitetura-base).

---

## SKILL_MARKETING_AI_SYSTEM_DESIGN.md (conteúdo original)

```yaml
---
name: marketing-ai-system-design
description: Projetar, revisar, documentar e governar o System Design de um aplicativo mobile SaaS independente que cria, publica, monitora e otimiza campanhas com IA no Google Ads, Facebook, Instagram e WhatsApp Business. Usar em arquitetura, componentes, fluxos, agentes, gateway multimodelo OpenAI/Gemini, integrações de anúncios, multi-tenancy, segurança, orçamento, aprovação humana, eventos, Saga, CQRS, dados, APIs, escalabilidade, observabilidade, roadmap técnico, ADRs, threat model, testes arquiteturais ou preparação para implementação do Marketing AI. Tratar o produto como independente do Kordena; integração futura exige decisão explícita. Não autorizar implementação, produção ou campanhas reais sem ordem específica.
---
```

# Marketing AI — System Design

## Preservar autoridade e escopo

Tratar o Marketing AI como produto independente. Não reutilizar automaticamente Core, banco, autenticação, tenants, código, marca, infraestrutura ou roadmap do Kordena.

Tratar esta skill como disciplina de arquitetura e engenharia, não como autorização automática para programar, publicar campanhas, movimentar orçamento ou alterar ambientes externos.

Se houver proposta de integração futura com Kordena ou outro produto, apresentá-la como opção desacoplada e aguardar aprovação explícita.

## Carregar a base correta

Ler integralmente `references/arquitetura-base.md` (reproduzido na íntegra abaixo, Seção 2 deste documento) antes de produzir ou revisar o System Design.

Consultar fontes atuais e oficiais quando a decisão depender de APIs, permissões, políticas, quotas, versões, capacidades ou modelos que possam ter mudado. Não afirmar suporte de plataforma sem evidência oficial.

Ao retomar trabalho existente, localizar primeiro documentação canônica e decisões recentes. Classificar como `NÃO VERIFICADO` o que não puder ser comprovado.

## Aplicar o fluxo de System Design

Executar proporcionalmente ao pedido:

1. **Enquadrar:** objetivo, usuários, segmento, canais, metas, restrições, autonomia e orçamento.
2. **Separar requisitos:** funcionais, não funcionais, segurança, conformidade e operação.
3. **Modelar domínio:** bounded contexts, entidades, estados, invariantes e fontes canônicas.
4. **Desenhar arquitetura:** componentes, responsabilidades, contratos e dependências.
5. **Desenhar fluxos críticos:** conexão, criação, aprovação, publicação, reconciliação, otimização, pausa, falha e recuperação.
6. **Dimensionar:** explicitar hipóteses de tenants, campanhas, eventos, armazenamento, latência e custo; não inventar números como fatos.
7. **Projetar dados:** tenancy, consistência, idempotência, versionamento, retenção, auditoria, índices e evolução de schema.
8. **Projetar integrações:** OAuth, capabilities, rate limits, webhooks, versionamento, retry, circuit breaker e reconciliação.
9. **Projetar IA:** gateway multimodelo, seleção, outputs estruturados, avaliação, custo, fallback, proveniência e limites.
10. **Projetar governança:** policy engine determinístico, RBAC/ABAC, autonomia, aprovações, limites financeiros e kill switch.
11. **Projetar resiliência:** filas, workflows duráveis, timeouts, deduplicação, outbox/inbox, Sagas e compensações.
12. **Projetar observabilidade:** métricas, tracing, logs sanitizados, alertas, SLOs e reconciliação.
13. **Projetar validação:** testes unitários, contratos, integração, sandbox, E2E, segurança, carga e recuperação.
14. **Comparar alternativas:** vantagens, custos, riscos, reversibilidade e recomendação.
15. **Definir gates:** evidências para desenho, protótipo, sandbox, produção e aumento de autonomia.
16. **Registrar pendências:** decisão, hipótese, pergunta aberta, bloqueio e item futuro.

## Proteger invariantes arquiteturais

- Manter o app mobile como cliente não confiável; segredos e execução externa ficam no backend.
- Fazer a IA propor resultados estruturados; somente serviços determinísticos executam ações externas.
- Nunca entregar às IAs tokens do Google, Meta, WhatsApp ou outros provedores.
- Isolar `tenant_id`, unidade, usuário, conta externa e função em todas as camadas.
- Manter orçamento, políticas, autorização e auditoria fora dos prompts.
- Representar Google Ads, Meta Ads e WhatsApp por adaptadores e contratos canônicos, preservando diferenças reais.
- Expor somente capacidades comprovadas para conta, país, permissão e versão da API.
- Usar idempotência e reconciliação em toda mutação externa.
- Auditar quem propôs, aprovou, executou, alterou, pausou e reverteu cada ação.
- Impedir aprendizado ou cache que vaze dados entre tenants.
- Exigir aprovação humana por padrão para campanha nova, público sensível, lista de clientes, elevação de gasto ou ação irreversível.
- Preservar consentimento, opt-out, templates e políticas do WhatsApp.
- Não declarar publicação ou otimização sem confirmação e ID externo reconciliado.

## Usar padrões seletivamente

Preferir inicialmente monólito modular, workers e workflow durável. Extrair serviços somente por escala, isolamento de falha, risco, segurança ou independência operacional comprovada.

- **Saga:** publicação multicanal e processos longos com compensações.
- **CQRS:** comandos críticos separados de projeções de leitura quando houver benefício real.
- **Event-driven:** integração assíncrona, webhooks, métricas e tarefas longas.
- **Event Sourcing:** apenas se auditoria, replay e reconstrução justificarem o custo.

Evitar microserviços prematuros, duplicação de estado, dual write sem proteção, polling excessivo e dependência direta de schemas particulares dos provedores.

## Tratar decisões críticas por ADR

Registrar contexto, restrições, opções, decisão recomendada, consequências, riscos, mitigação, reversibilidade, gatilho de revisão, aprovador e data. Usar os estados `PROPOSTA`, `APROVADA`, `SUBSTITUÍDA` ou `REJEITADA`.

Não escrever `APROVADA` sem decisão explícita do proprietário.

## Produzir artefatos mínimos úteis

Conforme o pedido, entregar somente o necessário:

- contexto, containers e componentes;
- sequências e máquina de estados;
- modelo lógico de dados;
- catálogo de eventos e contratos;
- capability matrix por provedor;
- matriz de autonomia e aprovação;
- threat model e controles;
- SLOs, capacidade e estratégia de escala;
- plano de falhas, compensação e disaster recovery;
- ADRs e roadmap por gates.

Usar Mermaid para topologia e sequência; usar tabelas para contratos, estados, alternativas, riscos e gates.

## Exigir qualidade verificável

Antes de considerar o desenho pronto para implementação, comprovar requisitos e limites, fronteiras, fontes canônicas, contratos versionáveis, fluxos de sucesso e falha, isolamento, segredos, limites financeiros, autorização, idempotência, reconciliação, observabilidade, auditoria, testes, dependências externas, riscos e caminho incremental.

Se faltar evidência, usar `PARCIAL`, `BLOQUEADO` ou `NÃO VERIFICADO`, nunca `CONCLUÍDO`.

## Encerrar com clareza

Informar resultado arquitetural; fatos, inferências e hipóteses; componentes afetados; segurança e governança; alternativas e trade-offs; riscos; gates; próximo passo; e situação final entre `CONCLUÍDO`, `PARCIAL`, `BLOQUEADO` ou `NÃO VERIFICADO`.

---

## Arquitetura-base — Marketing AI (referência completa, conteúdo original de `references/arquitetura-base.md`)

### 1. Produto

Conceber um produto mobile SaaS independente, multiempresa e multimodelo. Não depender do Core, banco, autenticação, marca, infraestrutura ou roadmap do Kordena.

O mobile configura, acompanha e aprova. Tokens, IA, processamento, webhooks e mutações externas permanecem no backend.

### 2. Ciclo e estados

`compreender → planejar → gerar → validar → aprovar → publicar → reconciliar → acompanhar → recomendar/otimizar → aprender`

`DRAFT → STRATEGY_READY → ASSETS_READY → VALIDATED → AWAITING_APPROVAL → APPROVED → PUBLISHING → ACTIVE → OPTIMIZING → PAUSED/COMPLETED/FAILED`

Status interno não prova efeito externo. Exigir confirmação e reconciliação do provedor.

### 3. Componentes

- Mobile App: onboarding, briefing, Brand Kit, prévia, aprovação, métricas e orçamento.
- BFF/API Gateway: autenticação, autorização, rate limit e contratos mobile.
- Campaign Orchestrator: estados, tarefas, Sagas, publicação e recuperação.
- AI Model Gateway: OpenAI, Gemini e futuros provedores; fallback, custo, schema e evals.
- Agentes: contexto, estratégia, copy, criativo, audiência, política, orçamento, experimento, performance e conformidade.
- Policy/Budget/Approval Engine: RBAC/ABAC, autonomia, tetos, aprovação e kill switch.
- Ads Connector Hub: Google Ads, Meta Marketing e WhatsApp Business.
- Workflow/Event Layer: filas, retry, deduplicação, compensação e reconciliação.
- Operational Data/Analytics: estado, assets, métricas, conversões e auditoria.

### 4. Contratos canônicos

Ads Connector Hub:

```text
connectAccount, listAccounts, validateDraft, createCampaign,
createAdGroupOrAdSet, uploadAsset, createAd, publish, pause,
resume, updateBudget, fetchInsights, syncConversions, handleWebhook
```

AI Model Gateway:

```text
generateText, generateImage, analyzeCreative, planCampaign,
embed, moderate, health
```

Manter Capability Registry versionado. Preservar as diferenças entre Google, Meta e WhatsApp. Modelos não executam conectores diretamente.

### 5. Dados e eventos

Entidades: tenants, unidades, usuários, permissões, marcas, produtos, ofertas, públicos, provedores, modelos, prompts, custos, conexões, contas externas, OAuth grants, campanhas, versões, planos por canal, anúncios, assets, orçamentos, aprovações, experimentos, recomendações, insights, conversões, workflows, outbox, inbox, webhooks, auditoria e incidentes.

Eventos principais: `CampaignBriefSubmitted`, `StrategyGenerated`, `CreativeGenerated`, `CampaignValidated`, `ApprovalRequested`, `CampaignApproved`, `PublicationStarted`, `PlatformCampaignCreated`, `CampaignActivated`, `InsightImported`, `BudgetThresholdReached`, `OptimizationProposed`, `OptimizationApplied`, `CampaignPaused` e `ExternalOperationFailed`.

### 6. Governança

| Nível | Autoridade |
|---|---|
| 0 — Assistente | Rascunhos e recomendações. |
| 1 — Aprovado | Publicação após aprovação humana. |
| 2 — Limitado | Otimização dentro de limites aprovados. |
| 3 — Operacional | Baixo risco automático; exceções escalam. |

Exigir aprovação por padrão para campanha nova, elevação de verba, público sensível, lista de clientes, mudança de conta, aumento de autonomia ou ação irreversível.

### 7. Stack inicial

Flutter; backend modular Python/FastAPI sujeito à validação; OpenAPI, JSON Schema e AsyncAPI; PostgreSQL; Redis; storage S3 compatível; workflow durável; fila gerenciada no MVP; Kafka/Redpanda apenas quando justificado; OpenTelemetry; containers e infraestrutura como código.

Começar com monólito modular e workers. Não impor Kubernetes ou microserviços prematuramente.

### 8. Evolução e gates

1. Fundação: contratos, tenancy, RBAC, auditoria, cofre e OAuth.
2. Copiloto: briefing, Brand Kit, IA multimodelo, prévia e aprovação.
3. Sandbox: publicação e reconciliação em contas de teste.
4. Produção controlada: canais suportados, métricas e limites.
5. Otimização: testes A/B, recomendações e budget pacing.
6. Autonomia limitada: somente após evals, segurança e aprovação.

Gates: contratos/capabilities; threat model; isolamento; sandbox E2E; limites e kill switch; evals de IA; E2E de briefing a métricas/pausa; aprovações externas; rollout gradual.

---

## Nota de integridade

Hash MD5 do arquivo original (`SKILL_MARKETING_AI_SYSTEM_DESIGN.md`, sandbox local desta sessão, 7.445 bytes): `4296bc88a170292c1a10d382ee0b4341`. Conteúdo transcrito integralmente acima, sem edição de substância — apenas formatação para consolidar os dois arquivos originais em um único documento Drive.
