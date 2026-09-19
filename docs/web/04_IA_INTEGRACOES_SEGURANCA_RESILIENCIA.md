# CampaIA — Ponto Zero Web · 04. IA, Integrações, Autonomia, Segurança, Resiliência, Observabilidade

**Status:** TARGET PROPOSTO — não aprovado.

---

## 1. IA e Agentes

`FATO CONFIRMADO`: `campaia_core/ai_gateway.py` já implementa a regra central — **"a IA propõe, o serviço determinístico executa"** — com um teste arquitetural citado no próprio docstring que falha se o arquivo importar `connectors` ou `saga`. Isso não é uma aspiração desta missão; já é comportamento de código existente.

Travas já implementadas (confirmadas por leitura integral das primeiras ~150 linhas):
- **Custo**: teto por requisição e por tenant, debitado na tentativa (mesmo se a resposta for imprestável).
- **Schema**: saída fora do contrato é rejeitada, nunca "consertada" silenciosamente.
- **Fallback**: trocar de provedor é permitido; trocar em silêncio, não — toda tentativa aparece em proveniência/auditoria.
- **Segredo**: `assert_no_credentials()` varre payloads recursivamente contra padrões de credencial (`vault://`, `Bearer ...`, `sk-...`, token Meta `EAA...`, chaves nomeadas) e contra o tipo `SecretRef` — recusa antes de sair do backend.

### 1.1 Cadeia de autoridade do Core (preservar, não redesenhar)
```
Core/IA → interpretação/recomendação → policy_decision_id (PolicyEngine) → serviço determinístico autorizado (Saga/Connector) → validação → execução → auditoria
```
Já é exatamente assim no código: `connectors.py::require_authorization()` recusa qualquer `PublishCommand` sem `policy_decision_id`; o `PolicyEngine` é quem emite esse id, nunca o `ai_gateway`.

### 1.2 O que é TARGET (não implementado, não lido em profundidade nesta missão)
- Moderação de conteúdo gerado — `AIStatus.BLOCKED_BY_MODERATION` existe como enum, comportamento real não confirmado nesta leitura.
- Evals formais — não encontrados nesta leitura; `PENDÊNCIA`.
- Cache seguro de resultados de IA — não confirmado.
- Versionamento de prompts — `prompt_version: str = "v1"` existe no `AIRequest`, estratégia de evolução não documentada.
- Proteção específica contra prompt injection além da trava de credencial — não confirmada nesta leitura; `NÃO VERIFICADO`.
- Isolamento entre tenants na camada de IA — `tenant_id` está no `AIRequest`; enforcement de que um tenant nunca vê contexto de outro não foi confirmado nesta leitura (`TenantIsolationViolation` existe como exceção importada, comportamento não lido).

**Regra obrigatória preservada**: nenhum token de provider (Google/Meta/WhatsApp) é fornecido aos modelos de IA — confirmado pela recusa de `SecretRef` em `assert_no_credentials`. Política, autorização, limites de orçamento e aprovação **não dependem de prompt** — dependem de `policy.py`/`budget.py`/`permissions.py`, código determinístico já testado.

---

## 2. Integrações externas

`FATO CONFIRMADO`: hoje existe apenas o contrato (`Protocol AdsConnector`) e a menção a um "Provider Simulator" no painel — **nenhum adaptador real de Google Ads, Meta ou WhatsApp foi encontrado no código lido**.

### 2.1 Capability Registry (TARGET)
Proposto: um registro versionado por `(provider, capability)` que o `PolicyEngine` já consulta indiretamente via `channel_support: dict[str, bool]` em `PolicyRequest` — essa estrutura **já existe no código** (`policy.py::PolicyRequest.channel_support`), então o Capability Registry é principalmente a fonte de dados real que preenche esse dicionário, não uma peça nova de domínio.

### 2.2 Contratos de operação por provider (a implementar sobre o `Protocol AdsConnector` já existente)
`connectAccount`, `listAccounts`, `validateDraft` (já existe como método do Protocol), `createCampaign`, `createAdGroupOrAdSet`, `uploadAsset`, `createAd`, `publish` (já existe), `pause` (já existe), `resume`, `updateBudget`, `fetchInsights`, `syncConversions`, `handleWebhook`.

`REGRA`: qualquer adaptador real implementado deve satisfazer o `Protocol AdsConnector` já definido e usar `require_authorization()` já existente — **não criar um segundo caminho de autorização para conectores**.

### 2.3 Por provider — o que cada TARGET precisa (nada confirmado externamente nesta missão; pesquisa aprofundada de política de plataforma fica para o Work Package correspondente, com fonte oficial e data registradas)

| Provider | OAuth | Rate limit/quota | Idempotência | Retry/backoff | Circuit breaker | Webhook | Sandbox |
|---|---|---|---|---|---|---|---|
| Google Ads | TARGET | `NÃO VERIFICADO` — requer pesquisa oficial | Já suportado pelo contrato (`idempotency_key`) | `NON_RETRYABLE` já define quais erros não repetem | TARGET | TARGET | TARGET |
| Meta Ads | TARGET | `NÃO VERIFICADO` — Marketing API Access Tier exige histórico real de chamadas com erro baixo (citado no painel v18/v19, não reverificado nesta missão) | idem | idem | TARGET | TARGET | TARGET |
| WhatsApp Business | TARGET | `NÃO VERIFICADO` | idem | idem | TARGET | TARGET (assinatura/replay já há padrão em `webhooks.py`, não lido linha a linha) | TARGET |

WhatsApp deve preservar (já são requisitos de produto no Charter/NFR, não inventados aqui): consentimento, opt-out, templates aprovados, janela de atendimento, classificação de mensagens, governança de contatos.

`REGRA`: quando a decisão depender de informação atual de plataforma, consultar somente documentação oficial, registrar URL e data da consulta, classificar como `NÃO VERIFICADO` o que não puder ser confirmado, e não bloquear todo o System Design por uma capability externa pendente — isso vira gate futuro (ver `06_ROADMAP_WORK_PACKAGES.md`). Nenhuma consulta externa foi feita nesta missão para além do que já constava nos documentos internos lidos.

---

## 3. Orçamento, Autonomia e Aprovação — matriz de autoridade

`FATO CONFIRMADO`: esta matriz **já é código real**, não proposta. Reproduzida aqui a partir de `autonomy.py`:

| Nível | Autoridade | `ActionKind` permitidas sozinhas | Confirmado em |
|---|---|---|---|
| 0 — Assistente | Rascunhos e recomendações apenas | nenhuma (tudo exige humano) | `AutonomyLevel.ASSISTENTE` |
| 1 — Aprovado (`DEFAULT_LEVEL`) | Publica só após aprovação humana | nenhuma | `evaluate()`: nível ≤ APROVADO sempre retorna `requires_human=True` |
| 2 — Limitado | Otimização dentro de limites pré-autorizados | `BID_ADJUSTMENT`, `CREATIVE_ROTATION`, `BUDGET_DECREASE` (`LEVEL_2_ALLOWED`) | `evaluate()` |
| 3 — Operacional | Acrescenta rotinas de baixo risco | + `PAUSE`, `REPORT_ONLY` (`LEVEL_3_ALLOWED`) | `evaluate()` |

**Lista fechada que exige humano em QUALQUER nível, inclusive nível 3** (`ALWAYS_REQUIRE_HUMAN`, confirmado em código): `CREATE_CAMPAIGN`, `FIRST_PUBLISH`, `BUDGET_INCREASE`, `SWITCH_AD_ACCOUNT`, `SENSITIVE_AUDIENCE`, `CUSTOMER_LIST`, `CUSTOMER_MATCH`, `TARGETING_CHANGE`, `AUTONOMY_CHANGE`, `IRREVERSIBLE`, `UNSPECIFIED_OPERATION` — **idêntico** à lista do Product Charter §9 e ao prompt mestre desta missão. Nenhuma divergência encontrada entre código, produto e governança neste ponto.

`AutonomySettings.__post_init__` já impede configurar nível acima do teto contratado (`max_level_allowed`) — "configurável significa ajustável dentro de limites, nunca acima deles", citação literal do código.

Elevação de verba exige autoridade: `budget.py::validate_change()` já recusa variação acima de `max_change_pct` (default 20%) sem "ajuste automático silencioso" — recusa, não corrige.

Kill switch: já disponível (`POST /kill-switch`, 3 escopos testados) e auditado (`Campaign.apply_kill_switch` registra em `history`).

**Nada nesta seção é TARGET** — é inventário de autoridade já implementada e testada, que a Web deve **expor**, não redesenhar.

---

## 4. Segurança e Threat Model

Metodologia: STRIDE, aplicada aos trust boundaries de `03_ARQUITETURA_WEB_DOMINIO_E_DADOS.md` §2.3.

| Ameaça | Ativo | Vetor | Impacto | Controle preventivo (já existe / TARGET) | Controle detectivo | Resposta | Gate |
|---|---|---|---|---|---|---|---|
| Cross-tenant access | Dados de outro tenant | Sessão Web mal implementada, tenant por header não confiável | Alto — vazamento entre clientes | RLS (existe) + ABAC tenant-first (existe) + sessão Web deve resolver tenant só do lado servidor (TARGET) | Auditoria (`audit_events`, existe parcialmente) | Revogar sessão, investigar escopo | Gate de Autenticação |
| Bypass de autorização | Qualquer recurso protegido | Chamar API sem passar por `authorize()` | Alto | `authorize()` já é único caminho no domínio; BFF deve sempre invocá-lo, nunca decidir sozinho | Testes de regressão (267+81 já cobrem parte) | Corrigir rota, adicionar teste | Gate de Autenticação |
| Escalada de privilégio | Permissões | Elevação de papel sem MFA/step-up | Alto | `REQUIRES_MFA`/`REQUIRES_STEP_UP` já existem no domínio | Auditoria | Revogar, forçar reautenticação | Gate de Autenticação |
| OAuth token theft | Tokens de provider | XSS, CSRF, armazenamento inseguro no cliente | Alto | `SecretRef` nunca sai do backend (existe); Web nunca guarda token de provider (TARGET, arquitetural) | — | Revogar token no provider, rotacionar | Gate de Sandbox |
| CSRF | Sessão Web | Mutação sem token CSRF | Médio | TARGET — token CSRF em toda mutação | — | — | Gate de Autenticação |
| XSS | Sessão Web, dados exibidos | Conteúdo não sanitizado (ex.: copy gerado por IA) renderizado sem escape | Médio | CSP (TARGET) + escape padrão do framework escolhido (ADR-0017) | — | — | Gate de Autenticação |
| IDOR/BOLA | Qualquer recurso por ID | Adivinhar ID de recurso de outro tenant | Alto | Já mitigado no domínio: `NOT_FOUND` em vez de `PERMISSION_DENIED` (existe) | — | — | Gate de Autenticação |
| Webhooks falsificados | Eventos de provider | Payload forjado sem assinatura válida | Médio | HMAC já citado em `webhooks.py` (não lido linha a linha — `PENDÊNCIA` de confirmação antes do Work Package de integração) | — | — | Gate de Sandbox |
| Replay de webhook | Eventos duplicados | Reenvio de payload antigo | Médio | Módulo `webhooks.py` cita "replay, dedupe" (não confirmado em profundidade) | — | — | Gate de Sandbox |
| Idempotency abuse | Budget, publicação | Reuso indevido de `idempotency_key` entre operações distintas | Médio | Chave já é composta por `command_id:channel` (existe, `saga.py`) | — | — | — |
| Prompt injection | AI Gateway | Conteúdo malicioso no briefing tentando extrair segredo ou instrução indevida | Médio | Trava de credencial já existe (`assert_no_credentials`); proteção mais ampla contra injection **não confirmada** | — | — | `NÃO VERIFICADO` — Work Package de IA |
| Exfiltração por IA | Dados de outro tenant via prompt | Contexto cruzado entre tenants | Alto | `tenant_id` no `AIRequest`; enforcement real **não confirmado nesta leitura** | — | — | `NÃO VERIFICADO` — Work Package de IA |
| Upload malicioso | Assets | Arquivo malicioso em upload de criativo | Médio | TARGET — validação de tipo/tamanho, scan | — | — | Gate de Sandbox |
| PII/LGPD | Dados pessoais de leads/clientes | Retenção indevida, falta de consentimento | Alto | Sanitização já existe (`sanitizer.py`, não lido linha a linha); política de retenção é TARGET | — | — | Gate de Produção controlada |
| Abuso financeiro | Orçamento | Publicação/otimização fora de limite | Alto | `budget.py`/`policy.py` já bloqueiam (existe, testado) | — | — | — |
| Campanha não autorizada | Publicação | Publicar sem `policy_decision_id`/aprovação | Crítico | `_guard_publishing` já recusa (existe, testado) | — | — | — |
| Alteração indevida de orçamento | Budget | Variação além do permitido | Alto | `validate_change()` já recusa (existe, testado) | — | — | — |
| Supply chain | Dependências | Pacote comprometido | Médio | `requirements.txt` com versões fixadas (existe); scanning automatizado é TARGET | — | — | Gate de Staging |
| Segredo exposto | Credenciais | Commit acidental | Crítico | Disciplina já demonstrada nas reconciliações anteriores desta sessão (grep de secrets antes de cada push) | — | Rotação imediata | STOP condition, sempre |

Nenhum segredo real foi incluído nesta matriz ou em qualquer artefato desta missão.

---

## 5. Resiliência e Consistência

`FATO CONFIRMADO` (já implementado): idempotência (`idempotency_key`, `command_id`), reserva-antes-de-efeito (`budget.py`), compensação (Saga, 3 políticas), retry com limite (`MAX_RETRIES = 2` em `saga.py`), classificação retryable/non-retryable por código de erro canônico (`connectors.py::NON_RETRYABLE`).

`TARGET, NÃO VERIFICADO/NÃO DECLARADO`:
- Backoff com jitter explícito — `saga.py` usa retry simples (`while attempts <= MAX_RETRIES`), sem backoff exponencial confirmado nesta leitura.
- Circuit breaker por provider — citado no painel para `ai_gateway.py` (`CIRCUIT_THRESHOLD = 3`, confirmado em código lido), **não confirmado para conectores de Ads**.
- Bulkhead entre tenants na camada de infraestrutura — não aplicável ainda (sem infraestrutura real).
- Dead-letter queue — citado para `outbox.py` no painel, não lido linha a linha nesta missão.
- Degradação controlada / modo somente leitura — TARGET, não implementado.
- RPO/RTO — NFR já define metas (`<5min`/`<1h`), mas são `HIPÓTESE`/`TARGET` sem infraestrutura real para validar. **Não declarar como aprovado sem autoridade humana** — permanece TARGET nesta missão.
- Backup/restore — TARGET, depende da decisão de hospedagem (ADR-0019).

---

## 6. Observabilidade

`NÃO VERIFICADO`: nenhuma evidência de logging estruturado, correlation ID, tracing ou métricas em produção foi encontrada nos módulos lidos. O `saga.py` emite eventos de domínio (`_emit`) que já carregam `event_id`, `event_type`, `tenant_id`, `campaign_id` — uma base aproveitável para correlação, mas não é OpenTelemetry nem observabilidade operacional.

TARGET mínimo, priorizado pelos fluxos críticos já identificados:
- Sucesso/falha de publicação (já gera eventos `PublicationStarted`/`CampaignActivated`/`PublicationPartiallyFailed`/`ExternalOperationFailed` — só falta exportá-los para um sistema de observabilidade real).
- Latência por rota.
- Erro por provider (`ConnectorErrorCode` já dá a taxonomia certa para métricas).
- Rate limit, fila, DLQ (quando existirem).
- Divergência de reconciliação (`reconciliation.py` existe, não lido em profundidade).
- Orçamento próximo do limite (`should_stop()` já existe em `budget.py` — falta alertar, não só bloquear).
- Campanha pausada, kill switch acionado (já gera evento de domínio via `history`).
- Tokens expirados (`AUTH_EXPIRED` já é código canônico).
- Custo de IA, fallback de modelo (`ai_gateway.py` já tem `AIStatus`/`Outcome` com essa granularidade).
- Violação de política (`Finding`/`Severity` já estruturados em `policy.py`).
- Tentativa de acesso cross-tenant (`DenialCode.NOT_FOUND` já é o sinal — hoje indistinguível de "recurso realmente não existe" na resposta ao cliente, por design de segurança; a distinção deve existir só nos logs internos, nunca na resposta HTTP).

`REGRA`: logs nunca expõem `SecretRef`, PII ou prompt sensível — já é o padrão implícito do código (`SecretRef.__repr__` sempre redige).
