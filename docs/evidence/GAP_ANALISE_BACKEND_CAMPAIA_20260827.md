# ANÁLISE DE LACUNAS REAIS DO BACKEND CAMPAIA — baseada em código, não no painel

**Data:** 27/08/2026
**Solicitado por:** Diretor Fábio Aluizio da Silva, via resposta explícita: *"Me diga primeiro o que falta de verdade"* (elaboração registrada: "Antes de mexer no painel, quero que você identifique qual é o próximo módulo/tarefa real ainda não implementada, olhando o código e não o painel.")
**Método:** leitura direta de todo o código-fonte em `backend/campaia_core/` e `backend/tests/` no Google Drive, reconstrução verbatim em sandbox local, execução real da suite de testes, e comparação linha a linha contra os contratos formais em `contracts/` (`bff-openapi.yaml`, `connector-hub-e-eventos.md`, e os `*.schema.json`). Nenhuma alegação abaixo se baseia no painel de execução.

---

## 1. O que está genuinamente pronto (verificado por execução)

17 módulos de domínio em `backend/campaia_core/` (errors, states, autonomy, budget, policy, infra, connectors, simulator, saga, permissions, webhooks, outbox, ai_gateway, agents, sanitizer, ai_simulator, reconciliation) + 5 arquivos de teste em `backend/tests/`. Suite completa executada: **145 testes, 145 aprovados, 0 falhas, 0 erros** (não 185 como o painel afirma).

Isso cobre, com teste próprio: máquina de estados da campanha (guards de transição), motor de orçamento (reserva/confirmação/liberação), motor de política, RBAC (6 papéis reais: OWNER/ADMIN/FINANCE/APPROVER/MARKETER/VIEWER — diverge do modelo de 4 papéis preservado no doc 11, pendência já sinalizada e ainda não resolvida), Saga de publicação multicanal com as 3 políticas de compensação, reconciliador de divergência (B3 — confirmado completo), outbox/inbox, recepção de webhook com HMAC+janela+dedupe, gateway de IA com teto de custo/circuit breaker/validação de schema, e sanitização de PII.

## 2. O que falta de verdade (achado por leitura de código, não por suposição)

### 2.1 Adaptadores reais de provedor (Google Ads / Meta / WhatsApp) — AUSENTE

`backend/campaia_core/simulator.py` contém apenas `ProviderSimulator`, um adaptador falso "fiel ao contrato" para uso em desenvolvimento e CI (texto do próprio docstring). Não existe, em nenhum lugar do Drive, um adaptador que fale de fato com a API do Google Ads, da Meta ou do WhatsApp.

Além disso, o Protocol `AdsConnector` em `connectors.py` define apenas 3 métodos: `validate_draft`, `publish`, `pause`. O documento de contrato `contracts/connector-hub-e-eventos.md` especifica 14 operações canônicas (`connect_account`, `list_accounts`, `describe_capabilities`, `validate_draft`, `create_campaign`, `create_ad_set`, `upload_asset`, `create_ad`, `publish`, `pause`/`resume`, `update_budget`, `fetch_insights`, `sync_conversions`, `handle_webhook`). Apenas 3 das 14 existem no Protocol implementado.

**Nota de precisão:** esse mesmo documento (`connector-hub-e-eventos.md`) afirma "Implementado em `backend/campaia_core/connectors.py`, com o conjunto NON_RETRYABLE testado" — o que é verdade apenas para a taxonomia de erros (`NON_RETRYABLE`, testada), não para a interface completa de 14 operações. É uma terceira imprecisão documental encontrada nesta investigação (além das duas já reportadas do painel: contagem de testes e status do B3).

### 2.2 BFF / API Gateway (camada HTTP) — AUSENTE, mas honestamente rotulado como rascunho

`contracts/bff-openapi.yaml` (25,7 KB) especifica um contrato REST completo — 24 endpoints (`/me`, `/brand-profiles`, `/connections`, `/briefs`, `/campaigns/*`, `/approvals/*`, `/autonomy`, `/kill-switch`, `/audit-events` etc.). O próprio arquivo se declara `version: 1.0.0-draft`, `description: PROPOSTA, sujeita ao Gate G1`, com os dois servidores marcados `NAO PROVISIONADO — exige autorizacao do Diretor`. Diferente do caso do connector hub, aqui a documentação não superestima: é honesta sobre ser proposta, não implementação.

Confirmado por busca direta (`grep` recursivo por `fastapi|flask|starlette|@app\.|APIRouter` em todos os 17 módulos + 5 testes): **zero ocorrências**. Não existe nenhum servidor HTTP, rota ou framework web implementado em lugar nenhum do backend CAMPAIA.

### 2.3 Camada de persistência (banco de dados real) — AUSENTE

Todo estado com nome de "Store" no código é explicitamente documentado, no próprio docstring, como provisório: `IdempotencyStore` ("Em memoria para teste de dominio. Em producao, tabela com constraint de unicidade"), `Outbox` ("Em memoria... Em producao, tabela na mesma transacao do estado"). `CapabilityRegistry` também é dataclass em memória. `grep` recursivo por `sqlalchemy|psycopg|alembic`: **zero ocorrências**. Nada persiste entre execuções do processo — tudo é estrutura Python em memória.

**Nota de escopo para não confundir dois projetos da F&M:** a busca no Drive também retornou uma pasta com FastAPI + PostgreSQL + SQLAlchemy + Alembic real e funcional (README fala em "AI Food 2.0", "Fundação oficial da plataforma SaaS inteligente para gestão de restaurantes"). Esse é um projeto **diferente**, não relacionado ao CAMPAIA — sinalizo aqui apenas para que essa stack real não seja confundida com progresso do CAMPAIA.

### 2.4 Aplicativo mobile — AUSENTE

A raiz do projeto CAMPAIA no Drive (`backend/`, `contracts/`, `docs/`) não contém nenhuma pasta de app, nem código Flutter/Dart, nem `pubspec.yaml`. Existe apenas o contrato do que o app consumiria (`bff-openapi.yaml`).

### 2.5 Integração real de cofre de segredos — AUSENTE

`SecretRef` em `connectors.py` é um tipo que só redige a representação (`__repr__`/`__str__` sempre retornam `"<SecretRef REDACTED>"`) — isso é uma proteção correta de exposição, mas o `resolve_secret` do simulador apenas monta uma string fake (`f"vault://{provider}/{external_account_id}"`). Não há cliente real de um cofre (GCP Secret Manager, HashiCorp Vault, AWS Secrets Manager etc.) implementado.

### 2.6 Fila/orquestração durável real (infraestrutura de eventos) — AUSENTE

`outbox.py`/`saga.py` implementam o padrão Outbox e a lista de eventos apenas em memória (`events: list[dict]`), sem publicação real em fila gerenciada nem engine de workflow durável — infraestrutura prevista em "Stack inicial" na arquitetura, mas não presente em código.

### 2.7 Camada de dados operacionais / analytics — AUSENTE

`fetch_insights` e `sync_conversions` (operações canônicas do connector) não existem em código; `InsightSeries`/`GET /campaigns/{id}/insights` só existem no contrato OpenAPI (ainda rascunho), não em implementação.

### 2.8 Nota sobre o AI Model Gateway (item parcialmente coberto, registrado por precisão)

O enum `AITask` em `ai_gateway.py` cobre `PLAN_CAMPAIGN`, `GENERATE_COPY`, `GENERATE_IMAGE`, `ANALYZE_CREATIVE`, `PROPOSE_AUDIENCE`, `INTERPRET_METRICS`, `MODERATE`, `EMBED` — funcionalmente equivalente às operações canônicas de planCampaign/generateText/generateImage/analyzeCreative/embed/moderate da arquitetura. As travas de custo, schema, fallback e segredo estão implementadas — porém, ver item 5 abaixo: essas travas atualmente não têm nenhum teste automatizado real no Drive. Assim como no Connector Hub, só existe `ai_simulator.py` (`SimulatedAIProvider`) — nenhum provedor real de IA (OpenAI/Anthropic/Google) está integrado.

---

## 3. Síntese

O núcleo de **domínio e governança com teste real e verificado** (máquina de estados, orçamento, política, permissões, saga, reconciliador, webhooks, outbox/inbox) está genuinamente implementado e testado — isso é real, não é alegação do painel. O gateway de IA, os agentes e o sanitizador de PII existem como código, mas — ver item 5 — sem teste automatizado confirmado no Drive hoje.

O que falta de verdade, em ordem de "quão nu" está (zero código vs. só simulador):

1. Camada HTTP / BFF — zero código; existe apenas contrato rascunho (`bff-openapi.yaml`, autodeclarado draft).
2. Persistência real (banco de dados) — zero código; tudo em memória, autodocumentado como provisório.
3. Adaptadores reais de provedor de anúncios (Google Ads / Meta / WhatsApp) — zero código; só simulador, e o Protocol cobre 3 das 14 operações canônicas do contrato.
4. Adaptador real de provedor de IA — zero código; só simulador.
5. Aplicativo mobile — zero código.
6. Fila/workflow durável real — zero código; só lista em memória.
7. Cofre de segredos real — zero código; só referência opaca simulada.
8. Camada de dados operacionais/analytics — zero código.
9. Cobertura de teste de `ai_gateway.py`, `ai_simulator.py`, `sanitizer.py` e `agents.py` — zero teste real no Drive hoje (ver item 5).

Nenhum desses itens é uma opinião — cada um foi confirmado por leitura direta do código-fonte completo (verbatim, baixado do Drive) e por busca (`grep`) recursiva por bibliotecas/frameworks/imports que os implementariam ou testariam, com zero ocorrências em todos os casos.

## 4. Não verificado / fora de escopo desta análise

- Conteúdo de `docs/` além de `arquitetura-base.md` e do painel não foi revisado exaustivamente nesta rodada.
- Não foi avaliado se `contracts/campaign-brief.schema.json`, `campaign-plan.schema.json` e `ai-gateway.schema.json` têm validação de fato ligada ao código (`OutputSchema` em `ai_gateway.py` existe, mas não foi confirmado se usa esses arquivos JSON Schema especificamente ou uma validação equivalente independente).
- A pendência de reconciliação do modelo RBAC (4 papéis do doc 11 vs. 6 papéis reais em `permissions.py`) permanece sinalizada e não resolvida.

## 5. Adendo (27/08/2026) — achado adicional na contagem de testes

Ao decompor a suíte real por arquivo (`grep` de `def test_` nos 5 arquivos de `backend/tests/`, confirmados por listagem direta da pasta no Drive, parentId `1pWobUq9Q6cRXW7MQtHw8K5FsbsGbwKDu`):

| Arquivo | Testes | Existe no Drive? |
|---|---|---|
| `test_invariantes.py` | 40 | Sim |
| `test_permissions.py` | 32 | Sim |
| `test_reconciliation.py` | 26 | Sim |
| `test_saga.py` | 24 | Sim |
| `test_webhooks_outbox.py` | 23 | Sim |
| `test_ai_gateway.py` | — | **NÃO EXISTE** |
| `test_agents_sanitizer.py` | — | **NÃO EXISTE** |

Soma: 40+32+26+24+23 = **145**, batendo com a execução real da suíte.

O painel (`01_PAINEL_EXECUCAO_v3_VIGENTE.md`) atribui 29 testes a `ai_gateway.py`, 2 a `ai_simulator.py`, 14 a `sanitizer.py` e 17 a `agents.py` (total 62), e lista `tests/test_ai_gateway.py` e `tests/test_agents_sanitizer.py` como arquivos de teste existentes. Confirmado por listagem direta da pasta `tests/` no Drive (não por suposição): **esses dois arquivos não existem**. Os 4 módulos (`ai_gateway.py`, `ai_simulator.py`, `sanitizer.py`, `agents.py`) existem como código-fonte real em `campaia_core/`, mas **não têm nenhum teste automatizado no Drive hoje** — nenhum dos 5 arquivos de teste reais importa esses módulos.

Isso não significa necessariamente que os testes nunca existiram — pode ter havido perda de sincronização com o Drive em algum momento. Não há evidência aqui para afirmar a causa; apenas o estado atual, verificado.

## 6. Decisão do Diretor registrada (27/08/2026)

Após apresentação deste achado e da recomendação de próximo passo, o Diretor respondeu, textualmente: **"sim siga sua sugestão eu aprovo"** — em resposta à recomendação de (1) corrigir o painel agora com os números reais e (2) priorizar em seguida a construção da camada BFF/API sobre o domínio já testado, no sandbox, sem depender de credencial ou infraestrutura externa.
