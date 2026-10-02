# CampaIA — Ponto Zero Web · 05. Testes, Gates, CI/CD/Implantação TARGET, Migração e Preservação

**Status:** TARGET com decisões arquiteturais APROVADAS (ADR-0016–0019, 19/09/2026) — **WP-01 implementado e validado** (fundação do frontend Web, ver `docs/web/08_CERTIFICACAO_WP01_FUNDACAO_WEB.md`); WP-02 em diante ainda não iniciados.

---

## 1. Baseline real (reexecutado nesta sessão, HEAD desta branch)

| Suíte | Comando | Resultado |
|---|---|---|
| Domínio | `python3 -m unittest discover -s tests -v` | **267 aprovados**, 0 falhas |
| API | `python3 -m unittest discover -s tests_api -t . -v` | **81 aprovados**, 0 falhas |
| Contrato AsyncAPI | `python3 validate_events_asyncapi.py` | **ALL CHECKS PASSED** — 24/24 eventos |

Números confirmados por execução real nesta sessão (ver `07_CERTIFICACAO_PONTO_ZERO_WEB.md` para o log completo com HEAD e timestamp). Não reutilizados de sessão anterior.

---

## 2. Pirâmide e matriz de testes (TARGET, Web)

| Camada | Já existe | TARGET a adicionar |
|---|---|---|
| Unitários (domínio) | 267 testes, `campaia_core/` | manter; crescer com cada Work Package |
| API/contrato | 81 testes, `tests_api/` | manter; crescer com autenticação real |
| Schema/contrato | AsyncAPI validado, OpenAPI conferido campo a campo (P-14) | manter validação em CI a cada mudança de contrato |
| Integração (banco real) | `verify_ddl_postgres.sh`, reexecutado com sucesso nesta sessão | rodar em CI, não só manualmente |
| RLS | Coberto pelo script acima (tenant-a/tenant-b/sem contexto) | manter |
| OAuth simulado | "Provider Simulator" citado no painel (não lido nesta missão) | expandir para os 3 providers reais quando adaptadores existirem |
| Sandbox oficial | Inexistente | TARGET — depende de credenciais de sandbox de cada provider |
| Frontend/componentes | Inexistente | TARGET, junto com o scaffold (ADR-0017) |
| Acessibilidade | Inexistente | TARGET, requisito novo desta fase (§2 de `02_PONTO_ZERO_WEB_E_REQUISITOS.md`) |
| E2E | Inexistente | TARGET, jornadas críticas: onboarding → briefing → aprovação → publicação |
| Segurança | Inexistente formalmente | TARGET — StrideChecklist de `04_...md` §4 vira suíte de testes de autorização/CSRF/CORS |
| Carga/concorrência | Inexistente | TARGET, só depois de infraestrutura real — não simular número fictício |
| Idempotência | Já coberta no domínio (budget, connectors) | manter; adicionar na camada Web (dedupe de duplo clique) |
| Resiliência/recuperação | Inexistente | TARGET |
| IA/evals | `ai_gateway.py`/`agents.py`/`ai_simulator.py` lidos integralmente nesta correção — cobrem schema/custo/circuit breaker/moderação, não evals formais | `PENDÊNCIA` — evals formais não encontrados em nenhum dos arquivos lidos; contagem exata de `test_ai_gateway.py`/`test_ai_simulator.py` não reexecutada isoladamente nesta correção (coberta pela suíte completa de 267 testes validada na Etapa 9) |
| Reconciliação | `test_reconciliation.py` citado (26 testes no painel, não relidos nesta missão) | manter |
| Smoke | Workflow atual roda as suítes a cada push/PR | expandir para ambientes reais quando existirem |
| Pós-deploy | Inexistente | TARGET, depende de ADR-0019 |

---

## 3. Gates (proporcionais ao risco, não todos obrigatórios para toda mudança)

| # | Gate | Pré-condições | Evidência exigida | Aprovador | Critério GO |
|---|---|---|---|---|---|
| 1 | Arquitetura | Este Ponto Zero Web revisado | PR desta missão aprovada | Diretor / FM Solution Architect | Documentação suficiente para começar scaffold sem improviso |
| 2 | Scaffold Web | Gate 1 passado, ADR-0017 decidida | Projeto inicial builda, lint/typecheck passam | FM SaaS Builder | Scaffold roda localmente, sem lógica de negócio ainda |
| 3 | Autenticação | Gate 2 passado, ADR-0018 decidida | Sessão Web real, testes de CSRF/CORS/step-up passando | FM Security Engineer | Nenhuma rota protegida acessível sem sessão válida |
| 4 | Tenancy | Gate 3 passado | Teste automatizado de isolamento cross-tenant na camada Web (equivalente ao já existente no DDL) | FM Security Engineer | Tentativa cross-tenant sempre `NOT_FOUND`, nunca vaza dado |
| 5 | Primeira jornada | Gate 4 passado | Onboarding → briefing → aprovação, E2E verde | FM QA Engineer | Jornada crítica funciona ponta a ponta com dados simulados |
| 6 | Sandbox | Gate 5 passado, credenciais de sandbox obtidas | Ao menos 1 adaptador real publica em sandbox de provider | FM Integration & Providers Engineer | Publicação real em sandbox, sem erro |
| 7 | Produção controlada | Gate 6 passado | Todos os gates de segurança do Documento Mestre §39 verificados | FM Security Engineer + FM QA Engineer | Nenhum STOP crítico aberto |
| 8 | Aumento de autonomia | Produto já em produção controlada | Evidência de operação estável no nível anterior | Diretor | Decisão humana explícita, nunca automática |

`REGRA`: falha em gate obrigatório bloqueia progressão até correção ou exceção formalmente aprovada (Documento Mestre §59).

---

## 4. CI/CD e Implantação TARGET (desenhado, não executado)

### 4.1 CURRENT do CI
`FATO CONFIRMADO` (reconfirmado na execução do WP-01): 2 workflows.
- `backend-tests.yml` — instala dependências, roda as 2 suítes de teste do backend, valida AsyncAPI. Inalterado por esta missão.
- `frontend-tests.yml` (**novo, WP-01**) — instala dependências de `web/` via `npm ci`, roda lint, typecheck (`next typegen` + `tsc --noEmit` estrito), verificação de drift do contrato OpenAPI, verificação das fronteiras de segurança do WP-01, testes unitários/componente/acessibilidade (Vitest), build de produção (Next.js) e smoke E2E (Playwright, desktop + mobile). Sem deploy.

Sem lint/typecheck/testes/build do frontend antes desta missão — WP-01 fecha essa lacuna especificamente para a fundação, dentro do seu escopo (nenhuma funcionalidade de negócio, nenhuma chamada real ao BFF).

### 4.2 TARGET de ambientes
| Ambiente | Finalidade | Status |
|---|---|---|
| Desenvolvimento | Estação local do engenheiro | já é o padrão implícito hoje |
| Preview por PR | Validar mudança isolada antes de merge | TARGET |
| Testes (CI) | O que já existe hoje | `FATO CONFIRMADO`, operacional |
| Staging | Ensaio geral antes de produção | TARGET |
| Sandbox de providers | Testar integrações reais sem afetar contas de produção | TARGET, depende de credenciais de cada provider |
| Produção | Cliente real | TARGET, não iniciado |

### 4.3 O que falta desenhar antes de qualquer deploy real
Build/artefatos do frontend (depende de ADR-0017), estratégia de migration (Postgres já tem schema — falta runner de migrations versionado), rollback, feature flags, secrets management real (hoje não há nenhum secret real no repositório, por disciplina), deploy gradual, health checks/readiness, smoke pós-deploy, controle de custo.

### 4.4 Hospedagem (comparação, sem contratar nada)
`docs/evidence/DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md` — **lido integralmente nesta correção** — registra Google Cloud, região São Paulo (`southamerica-east1`), como decisão já aprovada (D-08, 27/08/2026, resposta literal do Diretor: *"pode seguir sua recomendação e depois faremos a pesquisa exata dos valores"*) — **tratada aqui como restrição arquitetural existente**, não uma escolha nova desta missão. Pendências reais herdadas de D-08 (orçamento exato, confirmação jurídica de residência de dados) detalhadas em ADR-0019. ADR-0019 formaliza a implantação TARGET **sobre** essa base já decidida, sem reabri-la sem necessidade.

`PENDÊNCIA` real (preservada, não a de releitura — já eliminada acima): orçamento mensal exato e confirmação contratual/jurídica de que a região São Paulo cumpre a expectativa de residência de dados de D-09/LGPD — a própria fonte primária já registra ambas como não resolvidas (ver ADR-0019).

Nenhum serviço foi contratado, nenhuma nuvem foi configurada, nenhum deploy foi realizado nesta missão.

---

## 5. Estratégia de migração e preservação (CURRENT → TARGET)

| Item | Classificação | Justificativa |
|---|---|---|
| `campaia_core/` (19 módulos) | `PRESERVAR` | Testado, framework-agnóstico, autoridade canônica já correta |
| `backend/api/` (BFF Starlette) | `PRESERVAR` | Framework não é bloqueio (ver `01_...md` §3); contratos e testes preservados |
| DDL Postgres | `PRESERVAR` | Verificado contra servidor real nesta mesma sessão |
| Contratos (`contracts/`) | `PRESERVAR` | Validados nesta sessão |
| Fiscal handoff | `MANTER EM QUARENTENA FUNCIONAL` — implementado mas deliberadamente bloqueado | Sem fato real de billing próprio |
| `mobile/` | `MANTER EM QUARENTENA` | Decisão já formalizada, não revisitada nesta missão |
| Product Charter / NFR (pontos "mobile-first") | `ADAPTAR` | Superados pela Lei Web First; adaptação é decisão humana, não execução automática desta missão (ADR-0016) |
| Autenticação (token fixo de teste) | `SUBSTITUIR` | Nunca foi produção; TARGET é sessão real (ADR-0018) |
| Persistência (SQLite opcional) | `ADAPTAR` | Postgres passa a ser padrão nos ambientes além de dev local; schema já existe |
| Conectores reais (Google/Meta/WhatsApp) | `CRIAR` | Inexistentes hoje |
| Frontend Web | `CRIAR` | Inexistente |
| Observabilidade real | `CRIAR` | Inexistente |

### Regras de preservação obrigatórias (repetidas aqui deliberadamente, por serem STOP conditions)
- Não duplicar regra de negócio no frontend — toda regra já existe em `campaia_core`/`api`, o frontend só a consome.
- Preservar contratos compatíveis — `bff-openapi.yaml`/`events.asyncapi.yaml` continuam a fonte de verdade de forma.
- Versionar mudanças necessárias — nenhuma mudança de contrato breaking nesta missão.
- Manter o mobile em quarentena — reafirmado, sem exceção.
- Não copiar cegamente código Flutter para Web — a especificação funcional (`13_ESPECIFICACAO_TELAS_APP.md`) é a fonte, não o código Dart.
- Não reimplementar domínio já existente — `campaia_core` é reutilizado, não reescrito.
- Manter o fiscal handoff fail-closed — nenhum Work Package desta fase o conecta a nada.
- Não inventar billing — reafirmado.
- Não quebrar os 267 testes de domínio, 81 testes de API, 24 eventos AsyncAPI — validado nesta sessão como baseline; qualquer Work Package futuro deve reexecutar essa mesma matriz no seu próprio HEAD antes de certificar.
- Não reduzir segurança — toda trava existente (`authorize()`, `require_authorization()`, `assert_no_credentials()`, guardas de `states.py`) é ponto de partida, nunca removida sem ADR e aprovação humana.
- Não perder histórico — Git preservado; nenhuma reescrita de commit nesta missão.
