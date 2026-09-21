# CampaIA — Ponto Zero Web · 06. Roadmap e Work Packages

**Status:** TARGET com decisões arquiteturais APROVADAS (ADR-0016–0019) — **WP-01 implementado e validado** (19/09/2026), **WP-02 implementado, com revisão de segurança humana pendente** (20/09/2026, ver `docs/web/09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md`), **WP-03 implementado, com a mesma revisão de segurança humana pendente** (21/09/2026, ver `docs/web/10_CERTIFICACAO_WP03_TENANCY_SHELL.md`), **WP-04 implementado, revisão de FM QA Engineer pendente** (21/09/2026, ver `docs/web/11_CERTIFICACAO_WP04_ONBOARDING_BRAND_KIT.md`), **WP-05 implementado, fechando o Gate 5 (primeira jornada crítica), revisão de FM QA Engineer pendente** (21/09/2026, ver `docs/web/12_CERTIFICACAO_WP05_BRIEFING_APROVACAO.md`), **WP-06 implementado (alteração de orçamento, definido nesta mesma missão por reconciliação de CURRENT), mesma revisão pendente** (21/09/2026, ver `docs/web/13_CERTIFICACAO_WP06_ALTERACAO_ORCAMENTO.md`) e **WP-07 implementado (nível de autonomia/Modo Manual-Automático, definido nesta mesma missão por reconciliação de CURRENT, sob nova autorização do Diretor de continuar a construção enquanto a cota do CI está esgotada), mesma revisão pendente** (21/09/2026, ver `docs/web/14_CERTIFICACAO_WP07_NIVEL_AUTONOMIA.md`). Nenhum bloco além do WP-07 foi definido.

---

## 1. Reconciliação da sequência sugerida com o CURRENT real

A sequência de 25 blocos sugerida no prompt mestre foi confrontada com `01_CURRENT_E_MATRIZ_CURRENT_TARGET.md`. Ajustes feitos, com justificativa:

- **Fundação do frontend Web** e **design system mínimo** permanecem primeiro — nada os antecede, pois hoje não existe frontend.
- **Autenticação e sessão** vem antes de **contexto de tenant/unidade** na prática — como o domínio de tenancy já está pronto (`permissions.py`), o bloco real de trabalho é a sessão que o alimenta, não o domínio em si.
- **Shell do dashboard** depois de autenticação, não antes — não há por que construir um shell que ninguém pode acessar de forma autenticada.
- **Onboarding**, **Brand Kit**, **briefing**, **estratégia por IA**, **assets**, **aprovação**, **conexões**, **criação de campanha** seguem a ordem do prompt mestre, pois já são as rotas na ordem em que a API as expõe (`GET/POST /brand-profiles` → `POST /connections/oauth/start` → `POST /briefs` → `GET/POST .../plan` → `POST .../validate` → `GET/POST /approvals`).
- **Publicação sandbox** exige adaptador real de ao menos um provider — não pode vir antes de o Work Package de integração existir, mesmo que o prompt mestre a liste antes de "reconciliação"; mantido, mas explicitamente dependente de credenciais de sandbox externas (bloqueio de terceiro, não técnico).
- **Métricas**, **orçamento**, **recomendações**, **otimização limitada** — orçamento já tem API e domínio prontos (`PATCH /budget`); pode, na prática, ser paralelizável ao bloco de aprovação, mas mantido na ordem sugerida para não expandir escopo do roadmap sem necessidade.
- **Hardening, acessibilidade, observabilidade, segurança, staging, produção controlada** — mantidos como fechamento, conforme sugerido, e amarrados aos Gates 6–7 de `05_TESTES_CICD_MIGRACAO.md`.

Esta seção registra a reconciliação de ordem original, anterior a qualquer execução. **WP-01 foi implementado e validado em 19/09/2026** (ver abaixo); WP-02 em diante permanecem não executados, na ordem aqui reconciliada.

---

## 2. Primeiros 5 Work Packages prontos para execução futura

### WP-01 — Fundação do frontend Web — **IMPLEMENTADO E VALIDADO (19/09/2026)**

- **Objetivo**: scaffold do projeto Next.js/React, com lint, typecheck, testes de componente configurados, sem lógica de negócio. **Executado.**
- **Escopo realizado**: `web/` — Next.js 16.3.5 (App Router) + React 19.2.8 + TypeScript estrito, ESLint, Vitest (unitário/componente/acessibilidade), Playwright (smoke E2E desktop+mobile), design tokens mínimos e 5 componentes (`Button`, `Card`, `Badge`, `PageContainer`, `StatusPanel`), tela de fundação explicitamente identificada como "CampaIA Web Foundation — WP-01". Nenhuma chamada de rede real ao BFF — confirmado que `GET /me` exige `require_auth` e não existe endpoint público no BFF (`backend/api/main.py`, `backend/api/routes_me.py`, inalterados). Consumo do contrato via **fixture local tipada** (`src/fixtures/me.local.ts`), gerada a partir de tipos derivados deterministicamente de `contracts/bff-openapi.yaml` (`openapi-typescript`, `src/contracts/bff-openapi.generated.ts`, com verificação de drift em CI).
- **Fora do escopo, confirmado intocado**: nenhuma tela funcional, nenhuma autenticação real, nenhum dado de produção, nenhuma chamada de rede ao BFF, nenhuma alteração em `backend/campaia_core/`, `backend/api/`, `backend/db/`, `contracts/` ou `mobile/`.
- **Dependências**: ADR-0017 (aprovada 19/09/2026).
- **Arquivos/componentes criados**: diretório `web/` completo (ver `docs/web/08_CERTIFICACAO_WP01_FUNDACAO_WEB.md` para a lista completa) e `.github/workflows/frontend-tests.yml` (novo, CI próprio do frontend; `backend-tests.yml` inalterado).
- **Contratos afetados**: nenhum — apenas leitura de `bff-openapi.yaml` para gerar tipos; `contracts:check` falha o CI se o gerado divergir do contrato.
- **Segurança**: verificado por script automatizado (`npm run boundary:check`, integrado ao CI e aos testes) — nenhum token no bundle, nenhuma variável `NEXT_PUBLIC_*` sensível, nenhuma credencial em `localStorage`/`sessionStorage`, nenhuma chamada de rede em `web/src`. Não certifica segurança formal do produto.
- **Critérios de aceitação**: todos atendidos — build reproduzível a partir de `npm ci` limpo, lint/typecheck/contract-drift/boundary-check/testes/build verdes localmente e em CI, smoke E2E verde (desktop + mobile), app renderiza a tela de fundação a partir da fixture local, zero chamadas de rede ao BFF confirmadas em teste E2E.
- **Testes**: 15 testes Vitest (unitários, componentes, acessibilidade automatizada via `jest-axe`, fronteiras de segurança e drift de contrato) + 4 testes Playwright (smoke desktop/mobile).
- **Evidências**: `docs/web/08_CERTIFICACAO_WP01_FUNDACAO_WEB.md` — comandos reais, resultados reais, HEAD, CI.
- **Riscos**: baixo, como previsto; nenhum materializado.
- **Rollback**: remover `web/` e `.github/workflows/frontend-tests.yml`; nenhum impacto no backend (confirmado por regressão completa — ver certificação).
- **Gate**: Gate 2 (Scaffold Web) — **aprovado**, condicionado ao CI verde da PR (ver certificação).
- **Definição de pronto**: **atingida** — scaffold builda e roda contra fixture local, sem lógica de negócio e sem nenhuma chamada de rede real.
- **Autorização**: ADR-0017 aprovada + "PROMPT MESTRE — CAMPAIA WEB FIRST / EXECUÇÃO REAL E COMPLETA DO WP-01", 19/09/2026.

### WP-02 — Autenticação e sessão Web real — **IMPLEMENTADO (20/09/2026), REVISÃO DE SEGURANÇA HUMANA PENDENTE**

- **Objetivo**: substituir o token fixo de teste por sessão real (ADR-0018), alimentando `Principal` (`permissions.py`) — **executado, `permissions.py` intocado** (confirmado por `git diff`).
- **Escopo realizado**: OIDC Authorization Code + PKCE **provider-neutral** real (`backend/api/oidc.py`), cookies de sessão `HttpOnly`/`Secure`/`SameSite=Lax` (`backend/api/routes_auth.py`), CSRF por double-submit cookie (`backend/api/csrf.py`), logout com revogação server-side, mapeamento de claims → `roles`/`business_unit_ids` (`TokenPrincipal.from_verified_id_token`, roles desconhecidas descartadas, nunca concedidas). Nenhum provedor comercial aprovado ainda (ADR-0018 Pendências) — implementado um **provedor de identidade de teste real, próprio, fail-closed** (`backend/api/test_idp.py`), spec-compliant (discovery, authorize, token, JWKS), para que o mecanismo seja exercitado ponta a ponta sem inventar aprovação de vendor. Suporte a um provedor real via `CAMPAIA_OIDC_*` já existe (zero mudança de código ao configurar um).
- **Fora do escopo, confirmado não implementado**: MFA avançado além de `REQUIRES_MFA`; provisionamento de convite de usuário; escolha de provedor comercial.
- **Dependências**: WP-01 (satisfeita), ADR-0018 aprovada (satisfeita); provedor de identidade comercial **ainda não escolhido** — a mesma lacuna que já existia antes desta execução, não fechada por ela (ver Pendências).
- **Contratos afetados**: `api/deps.py` (mecanismo de autenticação: sessão real primeiro, fixture Bearer como fallback fail-closed) — nenhuma rota de negócio pré-existente mudou de contrato; 3 rotas novas (`/auth/login`, `/auth/callback`, `/auth/logout`) adicionadas a `contracts/bff-openapi.yaml`, aditivamente.
- **Segurança**: superfície nova implementada com sessão real, CSRF, cookies seguros — **auto-testada exaustivamente nesta execução** (37 novos testes automatizados: PKCE, state/nonce, verificação de assinatura/issuer/audience/expiração de ID token, sessão ausente/desconhecida/adulterada/expirada/revogada, CSRF ausente/incorreto/correto, isolamento cross-tenant via sessão, replay de state e de código de autorização, fail-closed ponta a ponta). **A revisão formal por um FM Security Engineer humano, exigida pela autorização original deste Work Package, não ocorreu nesta execução** — permanece uma pendência real e explícita, não uma aprovação presumida.
- **Critérios de aceitação**: login real funciona (confirmado, fluxo completo via TestClient real) — **Sim**; rota protegida recusa acesso sem sessão válida — **Sim**; teste automatizado de tentativa cross-tenant confirma isolamento — **Sim** (`test_other_tenant_owner_cannot_see_demo_tenant_brand_profile`).
- **Testes**: automatizados de CSRF (3), isolamento cross-tenant (1), sessão negativa (5), integridade do fluxo de autorização/replay (3), verificação de ID token (11), PKCE/unicidade (8), fail-closed (10, incluindo os 8 já cobertos no WP-01/fixture). CORS explícito por ambiente **não implementado nesta execução** — pendência real. Step-up: reforçado por herança do domínio existente (`permissions.py` já testado), sem teste novo dedicado de step-up via sessão Web nesta execução — pendência.
- **Evidências**: `docs/web/09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md`.
- **Riscos**: alto, como previsto — mitigado por cobertura de teste extensa, mas **não substitui revisão humana de segurança**, que continua pendente.
- **Rollback**: implementado e testado — fixture Bearer permanece fail-closed por construção (WP-01, reforçado); o provedor de teste (novo nesta execução) segue a mesma disciplina, com o mesmo único interruptor fail-closed (`enable_test_auth_fixtures` + `CAMPAIA_ENV=test|local_dev`), confirmado por teste automatizado que suas rotas (`/test-idp/*`) nem existem fora desse contexto.
- **Gate**: Gate 3 (Autenticação) — **implementação concluída; gate formal aguarda a revisão de segurança humana pendente**.
- **Definição de pronto**: nenhuma rota protegida acessível sem sessão válida — **atingido**; RBAC/ABAC exercitado ponta a ponta pela primeira vez via Web — **atingido**, para as 6 identidades fixture (owner/marketer/approver/finance/viewer/other-tenant owner).
- **Autorização necessária**: FM Security Engineer + Diretor. **Autorização de execução recebida do Diretor** ("PROMPT MESTRE — CAMPAIA SaaS V1 COMPLETO", 20/09/2026); **a revisão do FM Security Engineer é uma pendência real, não satisfeita por esta execução** — registrada explicitamente, não presumida como concluída.

### WP-03 — Contexto de tenant/unidade e shell do dashboard — **IMPLEMENTADO (21/09/2026)**

- **Objetivo**: resolver tenant/unidade ativa a partir da sessão (nunca de header), construir o shell autenticado do dashboard. **Executado.**
- **Escopo realizado**: `campaia_memberships` como claim opcional do ID token (`backend/api/oidc.py` `Membership`/`_parse_memberships`, `backend/api/test_idp.py`'s identidade `multi_tenant_owner`, a única com mais de um tenant real — OWNER em `demo-tenant`, VIEWER em `other-tenant`); `SessionRecord` passa a carregar `memberships: tuple[Membership, ...]` (`backend/api/oidc.py`, `backend/api/state.py`); duas rotas novas, autenticadas apenas por sessão real (nunca pelo fixture Bearer, ver `require_web_session`) — `GET /session/memberships` e `POST /session/switch-tenant` (`backend/api/routes_session.py`), a segunda reemitindo a sessão (novo `campaia_session`/`campaia_csrf`, mesma disciplina de rotação do login) e invalidando `step_up_at` em **todos** os tenants do usuário, não só no que está sendo deixado (`AppState.switch_tenant`). Frontend: `/dashboard` (`web/src/app/dashboard/page.tsx`) resolve tenant/unidade ativos exclusivamente de `GET /me`/`GET /session/memberships`; `TenantSwitcher` (client, só renderiza com >1 membership) chama `POST /session/switch-tenant` com CSRF, igual ao `LogoutButton`; três componentes de estado padronizado novos — `LoadingState` (via `loading.tsx`, convenção do App Router), `ErrorState`, `EmptyState`. Confirmado por leitura direta de `backend/campaia_core/permissions.py` (não alterado) que "troca de unidade" já era suportada nativamente (`Principal.business_unit_ids: frozenset[str] | None`); só "troca de tenant" exigia mecanismo novo.
- **Achado real, fora do escopo original, corrigido nesta execução**: a suíte cross-stack (`web/playwright.crossstack.config.ts`, backend real + frontend real, duas origens distintas em `127.0.0.1`, exatamente a topologia que `web/README.md` já documentava desde o WP-01) expôs dois problemas reais no mecanismo de login do WP-02, nunca antes exercitados por um navegador de verdade contra duas origens: (1) `/auth/callback`/`/auth/logout` redirecionavam para um caminho relativo, que um navegador resolve contra a origem do PRÓPRIO backend, não a do frontend — 404 real em qualquer deploy onde as origens de fato diferem; (2) nenhum header CORS existia, então o navegador recusa de saída as chamadas com `credentials: include` de `LogoutButton`/`TenantSwitcher` (bloqueadas no preflight) — a mesma pendência já registrada explicitamente na execução do WP-02 ("CORS explícito por ambiente não implementado"). Ambos corrigidos por uma única variável de ambiente nova, opcional, do backend — `CAMPAIA_WEB_ORIGIN` — que (a) faz `_frontend_url` (`backend/api/routes_auth.py`) redirecionar para a origem real do frontend em vez de um caminho relativo, e (b) habilita `CORSMiddleware` (`backend/api/main.py` `_build_middleware`) permitindo **apenas** essa origem exata (nunca curinga, já que `allow_credentials=True`). Ausente (todo teste pré-existente, e qualquer deploy de origem única/atrás do mesmo proxy reverso), o comportamento é idêntico ao anterior — zero regressão. 9 testes novos (`backend/tests_api/test_cross_origin.py`) cobrem os dois estados (com/sem a variável) e confirmam que o guard contra open-redirect do `redirect_after_login` client-supplied continua intacto.
- **Fora do escopo, confirmado não implementado**: qualquer funcionalidade de negócio além da navegação (onboarding, Brand Kit, campanhas — WP-04 em diante); nenhuma tela de produto em `/dashboard`, que permanece deliberadamente um placeholder rotulado (`EmptyState`).
- **Dependências**: WP-02 (satisfeita).
- **Contratos afetados**: `contracts/bff-openapi.yaml` — `GET /session/memberships`, `POST /session/switch-tenant`, schemas `Membership`/`SessionMemberships`/`SwitchTenantInput`, resposta `PermissionDenied` — todos aditivos; nenhuma rota pré-existente mudou de forma. `src/contracts/bff-openapi.generated.ts` regenerado, sem drift.
- **Segurança**: `tenant_id` do switch nunca aceito às cegas — validado contra os memberships reais da sessão no servidor (`AppState.switch_tenant`); tentativa de trocar para um tenant sem membership real recebe `403 PERMISSION_DENIED` e a sessão atual permanece intacta (testado). Isolamento cross-tenant reforçado no nível de UI pela suíte cross-stack: o painel de sessão ativa nunca mistura papéis/tenant do membership inativo com o ativo (testado explicitamente, inclusive imediatamente após o switch). `CAMPAIA_WEB_ORIGIN`/CORS seguem o mesmo padrão fail-closed-by-default das demais flags deste projeto — ausente, comportamento idêntico ao pré-WP-03.
- **Critérios de aceitação**: troca de tenant/unidade funciona e invalida `step_up_at` (conforme ADR-0018) — **Sim**, confirmado por teste dedicado (`test_switch_invalidates_step_up_across_all_tenants`) e por E2E cross-stack.
- **Testes**: backend — 12 nos (`backend/tests_api/test_tenant_switch.py`: memberships GET, switch com sucesso/negado/sem CSRF/sem sessão, rotação de cookie, isolamento entre duas sessões concorrentes, invalidação de step-up) + 8 de parsing do claim `campaia_memberships` (`backend/tests_api/test_oidc_unit.py`, `TestMemberships`) + 9 de CORS/redirect cross-origin (`backend/tests_api/test_cross_origin.py`). Frontend — 15 novos Vitest (estados padronizados, `TenantSwitcher`, `/dashboard` em cada estado) + 1 E2E de fumaça (`e2e/dashboard.spec.ts`, sem backend, igual ao padrão WP-01/02) + 3 E2E cross-stack reais (`e2e-crossstack/tenant-switch.spec.ts`: login real lista os dois memberships; troca real muda tenant/papéis sem misturar; troca real rotaciona o cookie de sessão no servidor). Regressão completa: 267 domínio + 155 API (126 + 12 + 8 + 9) + 24/24 AsyncAPI + 36 Vitest + 8 E2E de fumaça — todos verdes, zero regressão.
- **Riscos**: médio, como previsto — parcialmente materializado (o gap de CORS/redirect cross-origin), corrigido dentro desta própria execução assim que a suíte cross-stack o expôs, não deixado como pendência.
- **Rollback**: reverter para `/account` sem `/dashboard`/seletor — `CAMPAIA_WEB_ORIGIN` ausente já reduz o backend ao comportamento pré-WP-03 sem exigir reverter código.
- **Gate**: Gate 4 (Tenancy) — **implementação concluída; gate formal aguarda a mesma revisão de segurança humana pendente do WP-02** (nunca satisfeita por autoexecução).
- **Definição de pronto**: shell autenticado navega corretamente por tenant/unidade — **atingido**, incluindo o caminho cross-origin real (frontend e backend em origens diferentes), não apenas o caminho same-origin implícito no WP-02.
- **Autorização necessária**: aprovação de FM Security Engineer no teste de isolamento. **Autorização de execução recebida do Diretor** ("PROMPT MESTRE — CAMPAIA SaaS V1 COMPLETO", 20/09/2026, continuada); **a revisão do FM Security Engineer é uma pendência real, não satisfeita por esta execução** — registrada explicitamente, não presumida como concluída (mesma pendência do WP-02, ainda em aberto).

### WP-04 — Onboarding e Brand Kit — **IMPLEMENTADO (21/09/2026)**

- **Objetivo**: primeira jornada funcional real: cadastro de marca, conexão de contas (via `POST /connections/oauth/start`, ainda sem provider real por trás — usar o simulador já citado no domínio). **Executado.**
- **Escopo realizado**: `/onboarding` (`web/src/app/onboarding/page.tsx`) — Brand Kit (`BrandKitForm.tsx`, `POST/GET /brand-profiles`) e Conectar Contas (`ConnectAccountCard.tsx`, três cartões — Google Ads/Meta/WhatsApp — `POST /connections/oauth/start` + `POST /connections/oauth/complete`, `GET /connections`), conforme `13_ESPECIFICACAO_TELAS_APP.md` §3.4/§4 (fonte funcional, não o código Flutter). Regra de negócio "Concluir Onboarding habilitada assim que ≥1 canal conectado" implementada e testada.
- **Achado real, fora do escopo original, corrigido nesta execução**: `POST /connections/oauth/start` nunca criava uma `Connection` — `ConnectionRepository.create()` existia mas só era chamado diretamente em testes (`client.app.state.campaia.connections.create(...)`), nunca por nenhuma rota HTTP real. A descrição do próprio contrato já dizia "o callback é recebido pelo backend" — a metade que faltava. Fechado com uma rota nova, aditiva, `POST /connections/oauth/complete` (`backend/api/routes_connections.py`), que finaliza o `state` emitido por `/oauth/start` (rastreado server-side em `AppState.oauth_pending`, nunca confiado do cliente, mesmo padrão de `PendingLogin` do WP-02) e cria a `Connection` de fato. Sem essa rota, o critério de aceitação deste WP ("concluir onboarding habilitado assim que 1 canal conectado") seria estruturalmente impossível de satisfazer — nenhum canal jamais ficaria conectado de verdade.
- **Fora do escopo, confirmado não implementado**: cadastro de empresa/CNPJ e unidade de negócio (`13_ESPECIFICACAO_TELAS_APP.md` §3.2/§3.3) — nenhum endpoint de criação de tenant/unidade existe no backend (tenant_id vem sempre da sessão autenticada, nunca é criado via API); essas duas telas descrevem um TARGET que este Work Package deliberadamente não constrói, para não fabricar uma tela sem chamada de rede real por trás. OAuth real de provider (depende de Work Package de integração, fora desta lista).
- **Dependências**: WP-03 (satisfeita).
- **Contratos afetados**: `contracts/bff-openapi.yaml` — `POST /connections/oauth/complete`, aditivo; nenhuma rota pré-existente mudou de forma.
- **Segurança**: `state` do OAuth simulado nunca aceito às cegas — validado contra `AppState.oauth_pending` (tenant + single-use + TTL), mesma disciplina do `PendingLogin`. Achado real corrigido durante o próprio desenvolvimento: o consumo do `state` acontecia fora do bloco protegido por idempotência, fazendo um retry legítimo (mesma `Idempotency-Key`) falhar como se fosse um replay malicioso — corrigido movendo o consumo para dentro do fechamento idempotente, pego por teste antes de qualquer deploy.
- **Critérios de aceitação**: usuário completa onboarding e vê Brand Kit salvo — **Sim**, testado via E2E cross-stack real; regra "concluir onboarding habilitado assim que 1 canal conectado" — **Sim**, testado.
- **Testes**: backend — 7 novos (`backend/tests_api/test_oauth_complete.py`: cria conexão real, state single-use, state de outro tenant rejeitado, exige step-up, exige idempotency-key, replay não duplica). Frontend — 17 novos Vitest (`BrandKitForm`, `ConnectAccountCard`, `OnboardingPage` em cada estado) + 1 E2E de fumaça sem backend (`e2e/onboarding.spec.ts`) + 3 E2E cross-stack reais (`e2e-crossstack/onboarding.spec.ts`: nada conectado no início, conectar uma conta habilita "Concluir Onboarding", Brand Kit salvo persiste após reload). Regressão completa: 267 domínio + 162 API (155 + 7) + 24/24 AsyncAPI + 53 Vitest + 10 E2E de fumaça + 6 E2E cross-stack — todos verdes, zero regressão.
- **Riscos**: baixo, como previsto — o único risco real materializado (gap de criação de conexão) foi encontrado e fechado dentro desta própria execução, não deixado como pendência.
- **Rollback**: reverter para o shell sem `/onboarding`; `/connections/oauth/complete` ausente faz `/onboarding` degradar para "nada conectável", nunca para um estado inconsistente.
- **Gate**: Gate 5 (Primeira jornada) — parcial nesta etapa; completado pelo WP-05 (ver abaixo).
- **Definição de pronto**: onboarding e Brand Kit funcionais ponta a ponta — **atingido**, incluindo o caminho de conexão real (antes, estruturalmente impossível).
- **Autorização necessária**: FM QA Engineer. **Autorização de execução recebida do Diretor** (continuação de "PROMPT MESTRE — CAMPAIA SaaS V1 COMPLETO"); a revisão de QA formal não ocorreu nesta execução — pendência real, registrada, não presumida como satisfeita.

### WP-05 — Briefing, estratégia e aprovação (fecha a primeira jornada crítica)

**IMPLEMENTADO (21/09/2026)**

- **Objetivo**: completar o Gate 5 — briefing → estratégia (IA) → validação → fila de aprovação, com segregação de funções real (usuário distinto aprova). **Executado.**
- **Escopo realizado**: todas as 6 rotas do escopo original já existiam no backend desde blocos anteriores (`POST /briefs`, `GET /campaigns/{id}`, `GET/POST /campaigns/{id}/plan[/regenerate]`, `POST .../validate`, `GET/POST /approvals`, `POST /approvals/{id}/decision`) — CURRENT reconstruído por leitura direta do código confirmou isso antes de qualquer implementação. WP-05 construiu inteiramente a camada Web: `web/src/app/campaigns/page.tsx` (lista + `BriefForm`), `web/src/app/campaigns/[campaignId]/page.tsx` (detalhe: `PlanPanel` gera/regenera estratégia, `ValidationPanel` valida e solicita aprovação), `web/src/app/approvals/page.tsx` (fila de aprovação com `ApprovalDecisionCard`), mais os helpers `getServerCampaigns/getServerCampaign/getServerPlan/getServerApprovals` em `web/src/lib/session.ts`.
- **Achado real corrigido (contrato)**: `ApprovalRequest` no contrato (`contracts/bff-openapi.yaml`) não listava `requested_by`, embora `api/helpers.py serialize_approval` sempre o retorne — descoberto pelo próprio TypeScript ao tipar `ApprovalDecisionCard.tsx` contra o schema gerado. Corrigido aditivamente no contrato; `requested_by` é exatamente o campo que a UI precisa para comunicar segregação de funções ao usuário.
- **Achado real corrigido (frontend, 2)**: (a) `ValidationPanel.tsx`'s `handleValidate()` não enviava `X-CSRF-Token` — `CSRFMiddleware` exige o header em toda mutação autenticada por sessão, sem exceção por rota; pego por teste de backend com sessão real antes de qualquer E2E. (b) `PlanPanel.tsx` tentava renderizar `plan.output` como texto simples; o output real do agente `strategist` (`campaia_core/agents.py`) é um objeto estruturado (`objetivo`, `funil`, `canais`, `justificativa`), não texto livre — React lançou "Objects are not valid as a React child" na primeira execução real do E2E cross-stack contra o backend de verdade. Corrigido tipando `StrategistPlanOutput` e renderizando cada campo.
- **Fora do escopo confirmado**: publicação real (`POST .../publish`) — depende de adaptador de provider real, fora desta lista, nenhuma tela deste WP chama essa rota.
- **Dependências**: WP-04. Nenhuma alteração em `campaia_core`, `db` ou `permissions.py` — segregação de funções (`can_approve`) já existia e foi apenas exercitada, nunca reimplementada no frontend.
- **Segurança**: segregação de funções aplicada inteiramente pelo servidor (`campaia_core.permissions.can_approve`, `requester_id` check) — `ApprovalDecisionCard.tsx` nunca esconde ou desabilita os botões de decisão com base em "esta é minha própria aprovação"; a rejeição real do servidor (`403 SEPARATION_OF_DUTIES`) é o que fica visível. Testado tanto via sessão real de backend (`tests_api/test_briefing_approval_web_session.py`) quanto via navegador real em dois `BrowserContext` distintos (E2E cross-stack).
- **Critérios de aceitação**: jornada completa de briefing até aprovação funciona com dois usuários distintos — **Sim**, testado via E2E cross-stack real (`owner` propõe, `approver` decide); tentativa de autoaprovação é recusada visivelmente — **Sim**, testado nos dois níveis (backend com sessão real, E2E com navegador real).
- **Testes**: backend — 2 novos (`tests_api/test_briefing_approval_web_session.py`: jornada completa via cookie de sessão real com dois `TestClient` sobre o mesmo `AppState`, e recusa de `viewer` sem `CAMPAIGN_CREATE`). Frontend — 37 novos Vitest (`BriefForm`, `PlanPanel`, `ValidationPanel`, `ApprovalDecisionCard`, `CampaignsPage`, `CampaignDetailPage`, `ApprovalsPage`) + 2 E2E de fumaça sem backend (`e2e/campaigns.spec.ts`, `e2e/approvals.spec.ts`) + 1 E2E cross-stack real de dois usuários (`e2e-crossstack/briefing-approval-journey.spec.ts`). Regressão completa: 267 domínio + 164 API (162 + 2) + 24/24 AsyncAPI + 90 Vitest (53 + 37) + 14 E2E de fumaça (10 + 4, dois specs novos × 2 browsers) + 7 E2E cross-stack (6 + 1) — todos verdes, zero regressão.
- **Riscos**: médio, como previsto — os 3 achados reais (gap de contrato, CSRF ausente, shape de output do agente) foram todos encontrados e corrigidos dentro desta própria execução, nenhum deixado como pendência silenciosa.
- **Rollback**: reverter para o shell sem `/campaigns`/`/approvals`; nenhuma rota de backend nova foi criada neste WP (só o contrato foi corrigido aditivamente), então o rollback é puramente de frontend.
- **Gate**: Gate 5 (Primeira jornada) — **completo**.
- **Definição de pronto**: jornada crítica onboarding → briefing → aprovação funciona ponta a ponta com dados simulados — **atingido**, confirmado por E2E cross-stack real com dois usuários.
- **Autorização necessária**: FM QA Engineer + Diretor (fecha Gate 5, abre caminho para Gate 6/Sandbox). **Autorização de execução recebida do Diretor** (continuação de "PROMPT MESTRE — CAMPAIA SaaS V1 COMPLETO", decisão "pode avançar mais 3 blocos"); a revisão de QA formal não ocorreu nesta execução — pendência real, registrada, não presumida como satisfeita.

---

### WP-06 — Alteração de orçamento (Web sobre API já pronta)

**IMPLEMENTADO (21/09/2026)**

**Definido em 21/09/2026, por reconciliação de CURRENT** (não fazia parte do roadmap
original — este é o 3º bloco autorizado pelo Diretor, "pode avançar mais 3 blocos",
depois de WP-04 e WP-05). Escolhido entre os candidatos da Seção 3 (abaixo) por ser o
único tecnicamente desbloqueado sem decisão humana nova ou credencial externa: reutiliza
inteiramente a máquina de aprovação (`POST /approvals`, `POST /approvals/{id}/decision`) já
construída e testada pelo WP-05, sobre uma rota de backend (`PATCH /campaigns/{id}/budget`)
que já existe e já é testada desde blocos anteriores — "Web sobre API já pronta", exatamente
como a Seção 3 original descrevia este candidato.

- **Objetivo**: permitir alterar o teto diário (`daily_cap`) de uma campanha pela Web, com
  aprovação humana obrigatória (segregação de funções — quem propõe não aprova a própria
  proposta, igual ao WP-05) e respeitando o limite de variação percentual já aplicado pelo
  domínio (`campaia_core/budget.py BudgetEngine.validate_change`).
- **Escopo**: exibir o orçamento atual na tela de detalhe da campanha (`/campaigns/{id}`,
  já construída pelo WP-05); formulário para propor um novo `daily_cap`, que cria uma
  aprovação (`POST /approvals`, `kind: BUDGET_CHANGE`) — decisão continua acontecendo na
  fila de aprovação já existente (`/approvals`, WP-05), sem tela nova; uma vez aprovada,
  aplicar a mudança (`PATCH /campaigns/{id}/budget`, `daily_cap` + `approval_id`, CSRF +
  `X-Step-Up-Token` + `Idempotency-Key`).
- **Fora do escopo**: alteração de `total_amount` (orçamento total). **Achado real de
  contrato, não corrigido nesta definição, registrado como pendência**: o contrato
  (`bff-openapi.yaml`, `updateBudget` requestBody) declara `total_amount` como propriedade
  opcional aceita, mas `BudgetPatchRequest` (`api/models.py`, `extra="forbid"`) não tem esse
  campo — um cliente que o enviasse seria recusado com `422 VALIDATION_FAILED`. Como este
  WP-06 nunca envia `total_amount`, o achado não bloqueia sua execução, mas é uma
  divergência real de contrato×código que alguém precisa decidir como fechar (documentar o
  campo como não implementado, ou implementá-lo) — não decidido aqui, para não expandir o
  escopo deste bloco.
- **Dependências**: WP-05 (reutiliza `/approvals` inteiramente, inclusive sua UI de
  decisão).
- **Segurança**: `X-Step-Up-Token` na aplicação da mudança (rota já exige, comportamento
  preexistente, não alterado); segregação de funções aplicada pelo mesmo mecanismo do
  WP-05, nunca reimplementada na UI; variação percentual fora do limite configurado é
  recusada pelo domínio com `BUDGET_LIMIT`, nunca "ajustada automaticamente" — a UI deve
  mostrar essa recusa, não escondê-la ou tentar contornar.
- **Critérios de aceitação**: usuário propõe uma mudança de orçamento; um segundo usuário
  aprova (ou rejeita) na fila já existente; mudança aprovada é aplicada de verdade e reflete
  no orçamento exibido; mudança fora do limite percentual é recusada visivelmente.
- **Achados reais corrigidos durante a execução (contrato, 3)**: `ApprovalRequest.kind` e
  `.amount` estavam ausentes do contrato apesar de sempre presentes na resposta real
  (`api/helpers.py serialize_approval`) — `kind` já era descrito no próprio código como
  "extra, not in the contract"; `amount` nunca fora sequer mencionado. Sem `amount`
  tipado, a Web não teria como aplicar de fato uma alteração já aprovada (precisaria
  reconstruir o valor proposto de outra origem); sem `kind` tipado, não haveria forma
  confiável de distinguir um pedido de `BUDGET_CHANGE` de um de `PUBLISH` na fila de
  aprovação. Adicionalmente, `POST /approvals` (já implementado e já usado pelo WP-05)
  nunca estivera documentado no contrato — corrigido aditivamente junto, já que estava
  sendo tocado nesta mesma área.
- **Achado real corrigido durante a execução (frontend)**: `Campaign.budget` (`total_amount`,
  `daily_cap`, `spent_to_date`) é tipado `number` pelo contrato, mas a resposta real
  serializa esses campos `Decimal` como **string JSON** (confirmado por teste de backend:
  `"500"`, não `500`). Uma comparação estrita (`!==`) sem coerção nunca teria detectado
  corretamente "esta aprovação já foi aplicada", escondendo permanentemente o botão
  "Aplicar alteração". Corrigido coerindo ambos os lados via `Number(...)` no componente;
  a divergência de tipo em si (contrato × serialização real) não foi corrigida no backend
  — mudança maior, fora do escopo deste bloco, registrada como pendência.
- **Testes**: backend — 2 novos (`test_budget_change_web_session.py`: jornada completa
  propor→aprovar→aplicar via sessão Web real com dois usuários distintos; alteração além do
  limite percentual recusada visivelmente na aplicação). Frontend — 9 novos Vitest
  (`BudgetPanel`) + 1 E2E cross-stack real de dois usuários
  (`e2e-crossstack/budget-change.spec.ts`). Regressão completa: 267 domínio + 166 API
  (164 + 2) + 24/24 AsyncAPI + 99 Vitest (90 + 9) + 14 E2E de fumaça + 8 E2E cross-stack
  (7 + 1) — todos verdes, zero regressão.
- **Riscos**: baixo, como previsto — nenhuma rota nova de backend foi necessária; os
  achados reais foram todos de contrato (campos ausentes) e de tipo (Decimal serializado
  como string), nenhum deles bloqueou a execução.
- **Rollback**: reverter para o estado do WP-05; `PATCH /campaigns/{id}/budget` não é
  chamado por nenhuma outra tela, então o rollback é puramente de frontend.
- **Gate**: nenhum gate formal do roadmap original cobre este bloco (é um bloco novo,
  definido nesta reconciliação) — tratado como uma extensão do Gate 5, já que reutiliza sua
  infraestrutura de aprovação por completo.
- **Definição de pronto**: alteração de orçamento funciona ponta a ponta com dois usuários
  distintos (proponente e aprovador) e dados simulados — **atingido**, confirmado por E2E
  cross-stack real.
- **Autorização necessária**: mesma autorização já concedida pelo Diretor para o 3º bloco
  ("pode avançar mais 3 blocos"); revisão de FM QA Engineer permanece pendente, como em
  todo bloco desde o WP-02.

---

### WP-07 — Nível de autonomia (Modo Manual/Automático)

**IMPLEMENTADO (21/09/2026)**

**Definido em 21/09/2026, por reconciliação de CURRENT**, sob nova autorização do Diretor
("a cota será renovada no dia 31 então vamos continuar trabalhando na construção e fazer
tudo que for possível sem atrasar o término e no final faremos os testes necessários" —
autoriza continuar a construção; os "testes necessários" referem-se à confirmação do CI
remoto do GitHub Actions, bloqueado por cota até o dia 31, não aos testes locais desta
execução, que seguem obrigatórios a cada passo). CURRENT reconstruído por leitura direta de
`backend/api/routes_autonomy.py` e `backend/campaia_core/autonomy.py` antes de qualquer
código: `GET/PUT /autonomy` já existem, já testados (`test_autonomy_get_and_put`,
`test_autonomy_put_requires_approved_approval`, `test_autonomy_put_rejects_pending_approval`
em `tests_api/test_smoke_endpoints.py`), e reutilizam a mesma máquina de aprovação dos
WP-05/06 (`kind: AUTONOMY_CHANGE`) — nenhuma rota nova de backend esperada. Este é o Modo
Manual/Automático explicitamente decidido pelo Diretor como diferencial competitivo
(`docs/product/DECISOES_DIRETOR.md` item 5): "vamos ter a opção do cliente querer escolher
deixar no automático... assim nos coloca à frente da concorrência", com a salvaguarda de que
a ativação "precisará ser validada por senha de adm" — no sandbox, representada pelo mesmo
mecanismo honesto de step-up já usado em toda a aplicação (marcador não-vazio, nunca uma
senha real), e por `AUTONOMY_CHANGE` estar na lista fechada `ALWAYS_REQUIRE_HUMAN` do
domínio — muda de nível SEMPRE exige aprovação humana, em qualquer nível atual, sem exceção.

- **Objetivo**: permitir visualizar e propor mudança do nível de autonomia do tenant
  (ASSISTENTE/APROVADO/LIMITADO/OPERACIONAL) pela Web, com aprovação humana obrigatória e
  respeitando o teto contratado (`max_level_allowed`) já aplicado pelo domínio.
- **Escopo**: painel em `/dashboard` (shell tenant-level — autonomia é uma configuração do
  tenant inteiro, `state.tenant_autonomy[tenant_id]`, nunca por campanha) mostrando nível
  atual, rótulo, teto contratado, lista de gatilhos que sempre exigem humano
  (`always_require_human`) e data da última alteração; formulário para propor um novo nível,
  que cria uma aprovação (`POST /approvals`, `kind: AUTONOMY_CHANGE`) — decisão continua na
  fila `/approvals` já existente, sem tela nova; uma vez aprovada, aplicar (`PUT /autonomy`,
  `level` + `approval_id`, CSRF + `X-Step-Up-Token` + `Idempotency-Key`).
- **Achado real de backend, não corrigido nesta definição, registrado como restrição de
  design**: `POST /approvals` (`create_approval`, `api/routes_approvals.py`) exige
  `campaign_id` para **qualquer** `kind`, inclusive `AUTONOMY_CHANGE` — mesmo essa mudança
  sendo conceitualmente tenant-wide, não amarrada a uma campanha específica. A tela precisa
  de ao menos uma campanha existente para propor uma alteração de autonomia (usa a primeira
  campanha do tenant só para satisfazer essa exigência real da API, documentado no próprio
  código, nunca escondido do usuário); sem nenhuma campanha, o formulário fica desabilitado
  com uma explicação honesta, em vez de inventar uma campanha fictícia ou contornar a API.
- **Fora do escopo**: alterar `max_level_allowed` (o teto contratado) — nenhuma rota de API
  expõe essa alteração; é tratado como configuração comercial/plano, fora desta tela.
- **Dependências**: WP-05/06 (reutiliza `/approvals` inteiramente).
- **Segurança**: `AUTONOMY_CHANGE` está em `ALWAYS_REQUIRE_HUMAN` no domínio — mudar de nível
  sempre exige aprovação humana, mesmo já no nível OPERACIONAL; `AutonomySettings.__post_init__`
  recusa qualquer nível acima do teto contratado (guarda anti-auto-promoção, invariante I-11),
  nunca reimplementado nem contornado na UI; segregação de funções reutilizada do WP-05.
- **Critérios de aceitação**: usuário propõe uma mudança de nível; um segundo usuário aprova
  na fila já existente; mudança aprovada é aplicada de verdade e reflete no painel; tentativa
  de nível acima do teto contratado é recusada visivelmente.
- **Achado real de contrato, corrigido durante a execução**: `AutonomySettings.max_level_allowed`
  e `Campaign.business_unit_id` estão sempre presentes na resposta real
  (`campaia_core/autonomy.py`, `api/models.py CampaignResponse`), mas nenhum dos dois constava
  do contrato — mesma classe dos achados `requested_by`/`kind`/`amount` dos WP-05/06.
  `max_level_allowed` foi descoberto ao projetar o painel (sem ele tipado, a Web não teria como
  desabilitar corretamente os níveis acima do teto contratado); `business_unit_id` foi
  descoberto pelo próprio `tsc` ao escrever `autonomy-panel.test.tsx` (um fixture `Campaign`
  totalmente tipado, ausente nos fixtures anteriores por não terem anotação de tipo explícita,
  o que mascarava a lacuna via checagem de excesso de propriedade do TypeScript). Ambos
  corrigidos aditivamente; `npm run contracts:generate`/`contracts:check` confirmaram sincronia
  após cada correção.
- **Testes**: backend — 2 novos (`test_autonomy_change_web_session.py`: jornada completa
  propor→aprovar→aplicar via sessão Web real com dois usuários distintos, nível 1→0, a única
  mudança dentro do teto disponível sob a configuração padrão do tenant; proposta e até
  aprovação de um nível acima do teto contratado são aceitas, mas a aplicação é recusada com
  `422 VALIDATION_FAILED` pela própria guarda anti-auto-promoção do domínio, invariante I-11).
  Frontend — 10 novos Vitest (`AutonomyPanel`) + 1 novo teste em `dashboard-page.test.tsx` + 1
  E2E cross-stack real de dois usuários (`e2e-crossstack/autonomy-change.spec.ts`). Regressão
  completa: 267 domínio + 168 API (166 + 2) + 24/24 AsyncAPI + 110 Vitest (99 + 11) + build +
  fronteiras de segurança (11 arquivos) + 9 E2E cross-stack (8 + 1) — todos verdes, zero
  regressão.
- **Achado real corrigido durante a execução (regressão E2E, não de produto)**: ao rodar a
  suíte cross-stack completa, `briefing-approval-journey.spec.ts` (WP-05) revelou duas
  asserções `getByText("APPROVED")` sem escopo, que se tornaram ambíguas (violação de modo
  estrito do Playwright) assim que `autonomy-change.spec.ts` passou a deixar seu próprio card
  `APPROVED` na mesma fila de aprovação do backend compartilhado (todos os specs cross-stack
  rodam sequencialmente, `workers: 1`, contra um único `AppState`). Corrigido delimitando ambas
  as asserções por `data-testid` (`approval-card-PUBLISH-{campaignId}`), mesma disciplina que
  `budget-change.spec.ts` (WP-06) já usava para si mesmo — causa raiz corrigida, não mascarada.
- **Riscos**: baixos, como previsto — nenhuma rota nova de backend foi necessária; os achados
  reais foram de contrato (campos ausentes) e de fronteira de teste (asserção E2E sem escopo).
- **Rollback**: reverter para o estado do WP-06; painel novo isolado em `/dashboard`, nenhuma
  outra tela depende dele.
- **Gate**: nenhum gate formal do roadmap original cobre este bloco — tratado como extensão
  do Gate 5, mesma infraestrutura de aprovação.
- **Definição de pronto**: mudança de nível de autonomia funciona ponta a ponta com dois
  usuários distintos e dados simulados — **atingido**, confirmado por E2E cross-stack real.
- **Autorização necessária**: autorização do Diretor de continuar a construção enquanto a
  cota do CI está esgotada ("vamos continuar trabalhando na construção..."), 21/09/2026;
  revisão de FM QA Engineer permanece pendente, como em todo bloco desde o WP-02.

---

## 3. Blocos além do WP-07 (não detalhados como Work Package nesta missão)

**Nota (21/09/2026): WP-01 a WP-07 estão todos implementados**, o WP-07 sob a autorização do
Diretor de continuar a construção enquanto a cota do CI do GitHub Actions está esgotada
("vamos continuar trabalhando na construção e fazer tudo que for possível sem atrasar o
término e no final faremos os testes necessários", 21/09/2026 — os "testes necessários"
referem-se à confirmação do CI remoto, não aos testes locais, que seguem obrigatórios e
executados a cada passo). Nenhum bloco além do WP-07 foi definido; qualquer bloco seguinte
exige a mesma disciplina de reconciliação de CURRENT usada para definir o WP-07.

Publicação sandbox (depende de credenciais reais de sandbox de ao menos 1 provider — bloqueio externo, não técnico), reconciliação, métricas, recomendações/otimização limitada, hardening, acessibilidade, observabilidade, segurança formal, staging, produção controlada — todos dependem de decisões e Work Packages anteriores não executados nesta missão até 21/09/2026. Orçamento, único candidato tecnicamente desbloqueado desta lista, foi promovido a WP-06 (ver acima).
