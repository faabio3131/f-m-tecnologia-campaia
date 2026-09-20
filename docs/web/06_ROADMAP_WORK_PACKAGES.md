# CampaIA — Ponto Zero Web · 06. Roadmap e Work Packages

**Status:** TARGET com decisões arquiteturais APROVADAS (ADR-0016–0019) — **WP-01 implementado e validado** (19/09/2026) e **WP-02 implementado, com revisão de segurança humana pendente** (20/09/2026, ver `docs/web/09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md`). WP-03 em diante permanecem não iniciados.

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

### WP-03 — Contexto de tenant/unidade e shell do dashboard

- **Objetivo**: resolver tenant/unidade ativa a partir da sessão (nunca de header), construir o shell autenticado do dashboard.
- **Escopo**: seletor de tenant/unidade (quando o usuário pertence a mais de um), layout autenticado, estados vazio/erro/carregando padronizados.
- **Fora do escopo**: qualquer funcionalidade de negócio além da navegação.
- **Dependências**: WP-02.
- **Segurança**: reforço do teste de isolamento cross-tenant do WP-02 no nível de UI (nenhum dado de outro tenant deve aparecer nem transitoriamente).
- **Critérios de aceitação**: troca de tenant/unidade funciona e invalida `step_up_at` (conforme ADR-0018).
- **Testes**: E2E básico de troca de tenant.
- **Riscos**: médio.
- **Rollback**: reverter para tela única sem seletor, se necessário.
- **Gate**: Gate 4 (Tenancy).
- **Definição de pronto**: shell autenticado navega corretamente por tenant/unidade.
- **Autorização necessária**: aprovação de FM Security Engineer no teste de isolamento.

### WP-04 — Onboarding e Brand Kit

- **Objetivo**: primeira jornada funcional real: cadastro de marca, conexão de contas (via `POST /connections/oauth/start`, ainda sem provider real por trás — usar o simulador já citado no domínio).
- **Escopo**: telas de onboarding conforme `13_ESPECIFICACAO_TELAS_APP.md` §3 (fonte funcional, não o código Flutter), consumindo `POST/GET /brand-profiles`, `POST /connections/oauth/start`, `GET /connections`.
- **Fora do escopo**: OAuth real de provider (depende de Work Package de integração, fora desta lista de 5).
- **Dependências**: WP-03.
- **Critérios de aceitação**: usuário completa onboarding e vê Brand Kit salvo; regra de negócio "concluir onboarding habilitado assim que 1 canal conectado" (já era regra do onboarding Flutter, preservada como especificação funcional, não como código) é respeitada.
- **Testes**: E2E de onboarding completo.
- **Riscos**: baixo — usa rotas já existentes e testadas.
- **Rollback**: reverter para estado anterior do shell sem onboarding.
- **Gate**: Gate 5 (Primeira jornada) — parcial, falta briefing/aprovação para completar o gate inteiro.
- **Definição de pronto**: onboarding e Brand Kit funcionais ponta a ponta.
- **Autorização necessária**: FM QA Engineer.

### WP-05 — Briefing, estratégia e aprovação (fecha a primeira jornada crítica)

- **Objetivo**: completar o Gate 5 — briefing → estratégia (IA) → validação → fila de aprovação, com segregação de funções real (usuário distinto aprova).
- **Escopo**: `POST /briefs`, `GET/POST /campaigns/{id}/plan[/regenerate]`, `POST .../validate`, `GET/POST /approvals`, `POST /approvals/{id}/decision`.
- **Fora do escopo**: publicação real (depende de adaptador de provider, fora desta lista).
- **Dependências**: WP-04.
- **Segurança**: segregação de funções já implementada no domínio (`can_approve`); testar na Web que a UI não permite ao próprio proponente aprovar (a API já recusa; a UI deve refletir isso, não substituí-lo).
- **Critérios de aceitação**: jornada completa de briefing até aprovação funciona com dois usuários distintos; tentativa de autoaprovação é recusada visivelmente.
- **Testes**: E2E completo da jornada crítica.
- **Riscos**: médio.
- **Rollback**: reverter para o estado do WP-04.
- **Gate**: Gate 5 (Primeira jornada) — completo.
- **Definição de pronto**: jornada crítica onboarding → briefing → aprovação funciona ponta a ponta com dados simulados.
- **Autorização necessária**: FM QA Engineer + Diretor (fecha Gate 5, abre caminho para Gate 6/Sandbox).

---

## 3. Blocos além do WP-05 (não detalhados como Work Package nesta missão)

Publicação sandbox (depende de credenciais reais de sandbox de ao menos 1 provider — bloqueio externo, não técnico), reconciliação, métricas, orçamento (Web sobre API já pronta), recomendações/otimização limitada, hardening, acessibilidade, observabilidade, segurança formal, staging, produção controlada — todos dependem de decisões e Work Packages anteriores não executados nesta missão. Detalhá-los agora seria antecipar escopo sem o CURRENT que só existirá depois do WP-01 a WP-05.
