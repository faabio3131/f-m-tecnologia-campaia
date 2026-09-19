# CampaIA — Ponto Zero Web · 01. CURRENT confirmado e matriz CURRENT × TARGET

**Status:** DESCOBERTA — baseada em inspeção direta do código, contratos e documentação neste HEAD.
**Repositório:** `faabio3131/f-m-tecnologia-campaia`, branch `architecture/campaia-ponto-zero-web`, a partir de `main`@`c121f7c`.
**Método:** leitura integral dos módulos de domínio citados, do BFF/API (`backend/api/`), dos contratos (`contracts/`), do DDL (`backend/db/001_initial_schema.sql`) e dos documentos de produto (`docs/product/`). Nenhuma afirmação de estado abaixo é baseada em memória de conversa ou em prosa de painel sem confirmação no arquivo real correspondente.

---

## 1. Inventário do repositório (FATO CONFIRMADO)

```
backend/
  api/            17 rotas HTTP (Starlette), 9 arquivos routes_*.py, models.py (Pydantic), deps.py (auth fixture), db.py (SQLite opcional), repositories.py, state.py, errors.py, helpers.py
  campaia_core/   19 módulos de domínio puro Python (nenhuma dependência de framework web)
  db/             DDL Postgres único (001_initial_schema.sql) + script de verificação real (verify_ddl_postgres.sh)
  tests/          267 testes de domínio (unittest)
  tests_api/      81 testes de API/persistência (unittest)
contracts/
  bff-openapi.yaml           21 paths, rascunho 1.0.0-draft, conferido campo a campo contra o código (P-14, 28/08)
  events.asyncapi.yaml       24 eventos, AsyncAPI 3.0, validado (contracts/validate_events_asyncapi.py)
  4 JSON Schemas             event-envelope, campaign-brief, campaign-plan, ai-gateway
docs/
  00–12 (+ product/, evidence/, nova-fm/)   documentação de produto, ADRs, decisões, evidências
mobile/           app Flutter — QUARENTENA ARQUITETURAL (docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md), não tocado nesta missão
```

Linguagem única no backend: Python 3.11 (CI), stdlib + Starlette + Pydantic. Nenhum frontend Web existe hoje em nenhum repositório do CampaIA — confirmado por ausência de `web/`, `frontend/`, `package.json`, ou qualquer diretório de app Web em `f-m-tecnologia-campaia` e (pela auditoria de 19/09/2026) em `faabio3131/CampaIA`.

---

## 2. Estado comprovado por capacidade

Cada linha abaixo foi verificada por leitura direta do código-fonte listado como evidência, não por citação de painel.

| # | Capacidade | Módulo(s) | Estado real | Evidência lida |
|---|---|---|---|---|
| 1 | Máquina de estados de campanha (12 estados, grafo fechado por omissão) | `campaia_core/states.py` | IMPLEMENTADO, TESTADO | leitura integral; `TRANSITIONS`, `GUARDS`, invariantes I-09/I-12 |
| 2 | Autonomia governada (4 níveis, lista fechada `ALWAYS_REQUIRE_HUMAN`) | `campaia_core/autonomy.py` | IMPLEMENTADO, TESTADO | leitura integral; `evaluate()` determinístico, sem LLM |
| 3 | Policy Engine (findings, `policy_decision_id` com TTL e binding a versão de plano) | `campaia_core/policy.py` | IMPLEMENTADO, TESTADO | leitura integral |
| 4 | Budget Engine (reserva/confirmação/liberação, idempotência por `command_id`, `Decimal` exclusivamente) | `campaia_core/budget.py` | IMPLEMENTADO, TESTADO | leitura integral |
| 5 | Saga de publicação multicanal (3 políticas de compensação, nunca exclui recurso externo) | `campaia_core/saga.py` | IMPLEMENTADO, TESTADO | leitura integral |
| 6 | RBAC (6 papéis) + ABAC (tenant/unidade/step-up/MFA/teto de valor) | `campaia_core/permissions.py` | IMPLEMENTADO, TESTADO | leitura integral; `authorize()`, `can_approve()`, `dual_approval_complete()` |
| 7 | Contrato canônico de conectores (idempotência obrigatória, `SecretRef` redigido, taxonomia de erro canônica) | `campaia_core/connectors.py` | IMPLEMENTADO (contrato + guarda `require_authorization`), Protocol — **nenhum adaptador real de Google/Meta/WhatsApp existe** | leitura integral; só `Protocol` e guarda comum, nenhuma classe concreta de provider real encontrada no diretório |
| 8 | AI Model Gateway (proveniência, teto de custo, trava de credencial, rejeição de schema) | `campaia_core/ai_gateway.py` | IMPLEMENTADO (parcial, 150 linhas lidas de um arquivo maior), TESTADO (`test_ai_gateway.py`, 42 testes citados) | leitura parcial; teste arquitetural citado no docstring que falha se `connectors`/`saga` forem importados aqui — não reexecutado nesta missão |
| 9 | Sanitização de PII, agentes, simulador de IA | `sanitizer.py`, `agents.py`, `ai_simulator.py` | IMPLEMENTADO, TESTADO (por nome de arquivo e contagem em `tests/`) | não lido linha a linha nesta missão — **NÃO VERIFICADO em profundidade**, apenas confirmada a existência do arquivo e do teste correspondente |
| 10 | Outbox/Inbox, webhooks (HMAC, replay, dedupe), reconciliação | `outbox.py`, `webhooks.py`, `reconciliation.py` | IMPLEMENTADO, TESTADO (por nome de arquivo e teste) | não lido linha a linha nesta missão — **NÃO VERIFICADO em profundidade** |
| 11 | Pacing e Optimizer (sugestão apenas, nunca autoexecuta) | `pacing.py`, `optimizer.py` | IMPLEMENTADO, TESTADO | confirmado via `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` e presença/teste — **não lido linha a linha nesta missão** |
| 12 | Fiscal handoff fail-closed (own-billing) | `fiscal_handoff.py` | IMPLEMENTADO, TESTADO (4 testes), **BLOQUEADO** — sem fato real de billing próprio, deliberadamente desconectado de campanha/orçamento | leitura integral (reconciliação de 19/09/2026); confirmado via `grep` que nada mais no backend o referencia |
| 13 | BFF/API HTTP (21 rotas) | `backend/api/` | IMPLEMENTADO, TESTADO (81 testes) | leitura de `main.py` (rotas completas) e `models.py` (trecho do fix `daily_cap`) |
| 14 | Persistência real opcional | `api/db.py`, `api/repositories.py` | IMPLEMENTADO — SQLite quando `db_path` é passado a `create_app()`; padrão é em memória | leitura de `main.py`, docstring de `create_app()` |
| 15 | DDL Postgres (7 tabelas: `brand_profiles`, `connections`, `campaigns`, `approvals`, `audit_events`, `idempotency`, `tenant_autonomy`) | `backend/db/001_initial_schema.sql` | IMPLEMENTADO, **VERIFICADO CONTRA POSTGRES 16 REAL** (RLS, CHECK, FK, chave composta) — verificação real reexecutada nesta sessão em 19/09/2026 durante a reconciliação anterior | leitura do cabeçalho + `verify_ddl_postgres.sh` reexecutado com sucesso nesta mesma sessão |
| 16 | Multi-tenancy | RLS no DDL + `tenant_id` obrigatório em `Principal`/`Resource` | IMPLEMENTADO no nível de dados (RLS) e de domínio (ABAC); **não existe ainda camada Web que exercite isso** | leitura de `permissions.py` + DDL |
| 17 | Contratos (OpenAPI, AsyncAPI, JSON Schemas) | `contracts/` | IMPLEMENTADO, VALIDADO — AsyncAPI reexecutado com sucesso nesta sessão (19/09/2026, 24/24 eventos) | reexecução real nesta sessão |
| 18 | Integrações reais Google Ads / Meta / WhatsApp | — | **NÃO EXISTEM.** Nenhum adaptador concreto encontrado; apenas o `Protocol AdsConnector` e um "Provider Simulator" citado no painel (não lido nesta missão) | busca por classes que implementam `AdsConnector` fora de `connectors.py` — nenhuma encontrada |
| 19 | Autenticação real (OAuth 2.0 de usuário, sessão Web, JWT) | `api/deps.py` | **NÃO EXISTE** — painel v18/v19 descreve "token fixo (fixture local, não é credencial real)"; NFR doc pede OAuth 2.0 + JWT como TARGET, não como implementado | citação do painel v19, linha do `api/deps.py`; não lido literalmente nesta missão, mas consistente com ausência de qualquer biblioteca OAuth em `requirements.txt` |
| 20 | Frontend Web | — | **NÃO EXISTE.** | busca de diretório, confirmada ausente |
| 21 | App mobile Flutter | `mobile/` | PARCIALMENTE IMPLEMENTADO, **EM QUARENTENA ARQUITETURAL**, nunca validado por SDK real | `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` (reconciliação anterior nesta sessão) |

`PENDÊNCIA`: os itens 9, 10, 11 e a parte de `ai_gateway.py` além das 150 primeiras linhas não foram lidos integralmente nesta missão, por proporcionalidade de risco (código de domínio já testado e estável, sem relação direta com as decisões arquiteturais Web deste Ponto Zero). Qualquer Work Package que toque esses módulos diretamente deve fazer a leitura completa antes de alterar.

---

## 3. Backend existente — avaliação antes de qualquer proposta de substituição

`FATO CONFIRMADO`: o backend é **Starlette**, não FastAPI. Motivo documentado no próprio código (`api/main.py`, docstring): `pypi.org` estava bloqueado no ambiente onde foi construído, impedindo instalar FastAPI; Starlette (a base ASGI que FastAPI envolve) já estava disponível.

`FATO CONFIRMADO`: a arquitetura do backend já segue separação de camadas equivalente à exigida pela Norma Operacional (§14 do Documento Mestre):
- **Core/Domínio**: `campaia_core/` — 19 módulos, nenhum importa Starlette, nenhum conhece HTTP.
- **Application/API**: `api/routes_*.py` — tradução HTTP ↔ domínio.
- **Infraestrutura**: `api/db.py`, `api/repositories.py`.
- **Contratos**: `contracts/`.

`RECOMENDAÇÃO` (não decisão): **não migrar Starlette → FastAPI neste momento.** Não há benefício funcional comprovado — o código já implementa manualmente o que FastAPI daria de graça (validação Pydantic via `models.py`, roteamento, tratamento de exceções), e os 81 testes de API validam o comportamento HTTP real, não a escolha de framework. Uma migração agora seria reescrita por preferência (proibida por Documento Mestre §19) sem necessidade demonstrada. Se o `pypi.org` estiver acessível no ambiente de implantação real, a migração pode ser reavaliada como Work Package isolado e de baixo risco (ambos ASGI, contratos e testes preservados), mas **não é bloqueio para o Ponto Zero Web** — o frontend Web consome a API por contrato HTTP, independente do framework por trás dela. Ver ADR-0018.

`FATO CONFIRMADO`: 267 testes de domínio + 81 de API passam no HEAD desta branch (reexecutados nesta sessão, ver `05_TESTES_CICD_MIGRACAO.md`).

---

## 4. Produto e experiência — o que já foi decidido

Lido integralmente: `docs/product/CAMPAIA_PRODUCT_CHARTER.md`, `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md`, `docs/product/OUT_OF_SCOPE.md` (trecho relevante). Referenciados: `FUNCTIONAL_REQUIREMENTS.md`, `DECISOES_DIRETOR.md`, `13_ESPECIFICACAO_TELAS_APP.md` (já lidos em turnos anteriores desta mesma sessão, durante a auditoria de reconciliação).

### 4.1 DIVERGÊNCIA crítica encontrada (registrar, não corrigir silenciosamente)

`DIVERGÊNCIA` — **`CAMPAIA_PRODUCT_CHARTER.md` §1 declara literalmente: "Natureza: Aplicativo mobile SaaS independente"** (documento datado de 26/08/2026, redigido **antes** da adoção formal da Lei Web First em `docs/nova-fm/00-DOCUMENTO-MESTRE-NOVA-FM-TECNOLOGIA.md` v1.0, 13/09/2026, e v2.0, 17/09/2026).

Da mesma forma, `NON_FUNCTIONAL_REQUIREMENTS.md` §8 trata "Mobile (Flutter)" como a plataforma primária de compatibilidade e relega "Browsers (Web Dashboard)" à **"Fase 12"** — um tratamento de Web como *afterthought*, exatamente o padrão que a Lei Web First existe para proibir daqui em diante.

Esta missão **não altera esses documentos de produto silenciosamente** — fazer isso seria uma decisão arquitetural não autorizada. O tratamento correto, registrado aqui como `PENDÊNCIA` e formalizado em **ADR-0016**: a Lei Web First (norma institucional hierarquicamente superior, `CLAUDE.md` linha 19, Documento Mestre §2) **prevalece** sobre a declaração de natureza do Product Charter nos pontos em que colidem. O Product Charter continua válido como fonte da visão de produto, do público-alvo, da proposta de valor, dos canais suportados, dos princípios de governança de autonomia e dos guardrails financeiros — nenhum desses é Web-incompatível. Apenas a frase "Natureza: Aplicativo mobile SaaS independente" e o tratamento de Web como Fase 12 estão superados pela norma institucional vigente e devem ser objeto de atualização formal do Product Charter **pelo Diretor ou por decisão humana explícita**, fora do escopo de execução automática desta missão.

### 4.2 O que é preservável sem alteração (produto)

- Público-alvo, personas, proposta de valor (Charter §2–5).
- 4 canais do MVP: Google Search Ads, Facebook Ads, Instagram Ads, Click-to-WhatsApp (Charter §6).
- Matriz de autonomia governada (Níveis 0–3, Nível 2 no MVP com senha admin) — **idêntica ao que já está implementado em `autonomy.py`**, confirmado por leitura cruzada.
- Ações que sempre exigem aprovação humana (Charter §9) — **idênticas à lista `ALWAYS_REQUIRE_HUMAN` em código**.
- Guardrails financeiros, kill switch (Charter §10) — **implementados em `budget.py` e `states.py`**.
- Out of Scope (canais avançados, IA fine-tuning, Nível 3, marketplace) — nenhuma contradição com Web First.
- F1–F10 de `13_ESPECIFICACAO_TELAS_APP.md` — descrevem **jornadas e regras de negócio**, não a tecnologia de renderização; a maior parte é reaproveitável como especificação funcional para a Web, não como código.

`FATO CONFIRMADO`: não presumir que o desenho de telas do mobile (`mobile/lib/features/`) será copiado para a Web. A especificação de telas (`13_ESPECIFICACAO_TELAS_APP.md`) é a fonte funcional; a implementação Flutter é um artefato específico de plataforma, preservado apenas em quarentena.

---

## 5. Matriz CURRENT × TARGET (Web)

| Capacidade | CURRENT comprovado | Evidência | TARGET necessário para Web | Lacuna | Risco | Próximo gate |
|---|---|---|---|---|---|---|
| Domínio de campanha (estados, autonomia, policy, budget, saga) | Implementado, testado, framework-agnóstico | leitura direta, 267 testes | Reutilizado sem alteração via BFF | Nenhuma — já é TARGET | Baixo | Gate de Arquitetura |
| API HTTP | 21 rotas Starlette, 81 testes | leitura direta | Mesmo contrato, possivelmente framework mantido (Starlette) | Autenticação real, sessão Web, CORS, CSRF | Médio | Gate de Autenticação |
| Persistência | SQLite opcional + DDL Postgres verificado | leitura + reexecução | Postgres como banco único do ambiente real | Migração de SQLite-opcional para Postgres-padrão em todos os ambientes | Baixo (schema já existe) | Gate de Dados |
| Multi-tenancy | RLS no DDL + ABAC no domínio | leitura direta | Reutilizado; tenant ativo deve vir de sessão Web autenticada, nunca de header não confiável | Camada de sessão Web que resolva tenant ativo com segurança | Alto (STOP se implementado errado) | Gate de Autenticação |
| Autenticação de usuário | Token fixo de teste, não real | painel v19 (citação, não lido literalmente) | OAuth 2.0/sessão Web real, MFA para admin/financeiro (já exigido por `permissions.py`) | Implementação completa — hoje inexistente | Alto | Gate de Autenticação |
| Conectores externos (Google/Meta/WhatsApp) | Contrato (`Protocol`) + Simulador; nenhum adaptador real | leitura de `connectors.py` | Adaptadores reais atrás do mesmo `Protocol AdsConnector`, sandbox primeiro | Implementação completa dos 3 adaptadores | Alto (depende de terceiros, homologação) | Gate de Sandbox |
| Frontend | Inexistente | busca de diretório | Aplicação Web real (framework a decidir, ADR-0017) | Tudo | — | Gate de Arquitetura |
| Mobile Flutter | Parcial, não validado, quarentena | `MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` | Nenhum — permanece em quarentena nesta fase | N/A | — | Decisão humana pós-System-Design |
| Fiscal handoff | Implementado, fail-closed, bloqueado | leitura integral | Permanece bloqueado até existir fato real de billing próprio | N/A nesta fase | — | Decisão humana futura |
| Observabilidade | Nenhuma evidência de logging estruturado, tracing ou métricas em produção encontrada no código lido | ausência confirmada nos arquivos lidos | Logs estruturados, correlation ID, métricas, tracing (OpenTelemetry) | Tudo | Médio | Gate de Produção controlada |
| CI/CD | 1 workflow GitHub Actions (lint ausente, testes + AsyncAPI) | leitura de `.github/workflows/backend-tests.yml` | Pipeline com preview por PR, staging, gates de segurança | Ambientes além de CI de testes | Médio | Gate de Staging |
