# CampaIA Web — Fundação, sessão real, shell autenticado e onboarding (WP-01 a WP-04)

Fundação técnica do frontend Web do CampaIA. Este diretório implementa o
**WP-01 — Fundação do frontend Web** (aprovado pela ADR-0017), o
**WP-02 — Autenticação e sessão Web real** (aprovado pela ADR-0018,
implementado em 20/09/2026 — ver
`docs/web/09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md`; revisão de
segurança humana por um FM Security Engineer ainda pendente), o
**WP-03 — Contexto de tenant/unidade e shell do dashboard** (ver
`docs/web/10_CERTIFICACAO_WP03_TENANCY_SHELL.md`) e o
**WP-04 — Onboarding e Brand Kit** (ver
`docs/web/11_CERTIFICACAO_WP04_ONBOARDING_BRAND_KIT.md`; revisão de FM QA
Engineer ainda pendente).

**Não é** um produto comercial concluído. WP-01 (a tela `/`) permanece
inteiramente fixture-based, sem nenhuma chamada de rede — essa garantia
não mudou. WP-02 adiciona a página `/account` (login/logout reais). WP-03
adiciona a página `/dashboard` (shell autenticado, seletor de tenant).
WP-04 adiciona a página `/onboarding` (Brand Kit real, conexão simulada de
contas) — mas nenhum implementa a jornada completa de produto (briefing,
geração por IA, campanhas, publicação — isso é WP-05 em diante).

## Requisitos

- Node.js 22.x (usado para construir esta fundação; qualquer Node ≥ 20
  compatível com Next.js 16 deve funcionar, mas 22 é a versão verificada).
- npm (lockfile `package-lock.json` versionado — use `npm ci` para
  instalação reproduzível).

## Versões-base

| Dependência | Versão |
|---|---|
| Next.js | 16.3.5 (App Router) |
| React | 19.2.8 |
| TypeScript | ^5 (modo `strict`) |

Nenhuma dependência de estado global, SDK de provedor de nuvem ou
analytics foi instalada — deliberadamente fora do escopo do WP-01 a WP-04.

## Instalação

```bash
cd web
npm ci
```

## Comandos

```bash
npm run dev                  # servidor de desenvolvimento
npm run lint                 # ESLint
npm run typecheck            # gera tipos de rota do Next.js + tsc --noEmit (modo estrito)
npm run test                 # Vitest: unitários, componentes, acessibilidade, fronteiras
npm run test:e2e             # Playwright: smoke E2E (desktop + mobile), sem backend
npm run test:e2e:crossstack  # Playwright: WP-03, login + troca de tenant reais (backend + frontend reais)
npm run build                # build de produção (Next.js)
npm run contracts:generate   # regenera src/contracts/bff-openapi.generated.ts a partir de ../contracts/bff-openapi.yaml
npm run contracts:check      # falha se o arquivo gerado estiver desatualizado (drift)
npm run boundary:check       # varre web/src por token/segredo/localStorage/chamada de rede fora da allowlist
npm run check                # agrega lint + typecheck + contracts:check + boundary:check + test + build
```

`npm run check` é o gate local completo (exceto E2E, que sobe servidor(es)
reais e roda à parte). Qualquer falha em qualquer um desses comandos
termina com código de saída diferente de zero.

### Executando o E2E de fumaça localmente (sem backend)

O Playwright precisa de um binário Chromium compatível com a versão
instalada (`@playwright/test`). Em ambientes com um Chromium pré-instalado
em um caminho não padrão, exporte `CAMPAIA_CHROMIUM_PATH` antes de rodar:

```bash
CAMPAIA_CHROMIUM_PATH=/caminho/para/chromium npm run test:e2e
```

Se a variável não estiver definida, o Playwright usa o Chromium que ele
mesmo baixou (`npx playwright install chromium`).

### Executando o E2E cross-stack (WP-03, com backend real)

`npm run test:e2e:crossstack` (config separada,
`playwright.crossstack.config.ts`, nunca lida por `npm run test:e2e`) sobe
um backend real (`uvicorn`, provedor de identidade de teste, fail-closed
por construção — `CAMPAIA_ENV=test` + `CAMPAIA_ENABLE_TEST_AUTH_FIXTURES=1`)
**e** um frontend real (`next dev`, com `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN`
apontando para o backend), ambos em origens diferentes de `127.0.0.1`
(mesma topologia documentada abaixo) sobre HTTPS com um certificado
autoassinado gerado sob demanda (`web/e2e-crossstack/.certs/*.pem`,
nunca versionado — `*.pem` está no `.gitignore`). Requer `python3`,
`openssl` e as dependências de `backend/requirements.txt` instaladas.
Login (OIDC Authorization Code + PKCE contra o provedor de teste) e troca
de tenant são exercitados ponta a ponta por um navegador real, não por
`TestClient`. CI roda isso em um job dedicado
(`.github/workflows/frontend-tests.yml`, job `crossstack-e2e`).

## Variáveis de ambiente

| Variável | Onde | Obrigatória? | Efeito |
|---|---|---|---|
| `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` | `web/` | Não | Origem pública do backend (BFF), ex. `https://api.campaia.app`. Sem ela, `/account` e `/dashboard` degradam honestamente para "não configurado" — nenhuma chamada de rede é feita, nenhuma sessão é simulada. **Não é um segredo**: é a mesma origem para a qual o navegador é redirecionado em `/auth/login`. |
| `CAMPAIA_WEB_ORIGIN` | `backend/` | Não (WP-03) | Origem pública do frontend, ex. `https://app.campaia.app`. Quando ausente, `/auth/callback`/`/auth/logout` redirecionam para um caminho relativo (correto só se frontend e backend compartilham a mesma origem, ex. atrás do mesmo proxy reverso) e nenhum header CORS é emitido. Quando presente, os redirects pós-login/logout apontam para essa origem e o backend passa a responder `Access-Control-Allow-Origin` **apenas** para ela (nunca um curinga — `allow_credentials=True` exige uma origem exata), permitindo que `LogoutButton`/`TenantSwitcher` funcionem quando o frontend e o backend são, de fato, origens diferentes (a topologia que este próprio arquivo documenta). Nunca aceito do cliente — só controla o que o BACKEND, já confiável, devolve. |

Nenhuma outra variável de ambiente é lida por `web/`. Credenciais do
provedor de identidade (`CAMPAIA_OIDC_*`) e a flag de fixtures de teste
(`CAMPAIA_ENV`) vivem inteiramente no backend (`backend/`) — nunca no
frontend.

## Estrutura

```text
web/
  src/
    app/          # App Router: layout, fundação (/), conta (/account, WP-02),
                    # dashboard (/dashboard, WP-03), onboarding (/onboarding, WP-04)
    components/    # Button, Card, Badge, PageContainer, StatusPanel (WP-01);
                    # LogoutButton, TenantSwitcher (client, chamadas de rede -- WP-02/03);
                    # LoadingState, ErrorState, EmptyState (estados padronizados -- WP-03);
                    # BrandKitForm, ConnectAccountCard (client, chamadas de rede -- WP-04)
    contracts/     # types.ts (import estável) + bff-openapi.generated.ts (gerado, não editar)
    fixtures/       # dado fictício local, tipado a partir do contrato (usado só por /)
    lib/            # session.ts: leitura de sessão (WP-02), memberships (WP-03),
                    # Brand Kits/conexões (WP-04) real, server-only
    styles/         # tokens.css — variáveis de design (cor, espaçamento, tipografia, motion)
  tests/           # Vitest: unitários, componentes, acessibilidade, fronteiras de segurança/contrato
  e2e/             # Playwright: smoke de /, /account, /dashboard, /onboarding -- sem backend (CI padrão)
  e2e-crossstack/  # Playwright: WP-03/04, login, troca de tenant e onboarding reais -- com backend (job dedicado)
  scripts/         # CLIs de verificação (drift de contrato, fronteiras de segurança) + lógica compartilhada em scripts/lib/
  public/          # ativos estáticos (favicon)
```

## O que é a fixture local

`src/fixtures/me.local.ts` exporta um valor `Me` inteiramente fictício
(UUIDs de exemplo, papéis de exemplo), tipado a partir do schema `Me` de
`contracts/bff-openapi.yaml` via `openapi-typescript`
(`src/contracts/bff-openapi.generated.ts`, regenerado por
`npm run contracts:generate` — nunca editado manualmente, cabeçalho no
topo do arquivo identifica a origem). A tela de fundação
(`src/app/page.tsx`) importa esse valor diretamente; **nenhuma chamada de
rede ocorre** para obtê-lo.

Se o contrato mudar de um jeito incompatível com a fixture, o TypeScript
falha no `typecheck`/`build`, e `npm run contracts:check` detecta
divergência entre o arquivo gerado versionado e uma nova geração a partir
do YAML atual.

## Login e sessão real (WP-02)

`/account` mostra três estados possíveis, dependendo do que está
configurado/ativo — nenhum é simulado no frontend:

1. **Sem `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN`**: aviso de configuração
   ausente. Nenhuma chamada de rede.
2. **Configurado, sem sessão**: link "Entrar" para
   `{BFF_ORIGIN}/auth/login?redirect_after_login=/account` — o backend
   conduz o fluxo OIDC Authorization Code + PKCE real (ver
   `backend/api/oidc.py`, `backend/api/routes_auth.py`); o frontend nunca
   vê um token ou segredo.
3. **Configurado, com sessão**: `web/src/lib/session.ts` lê o cookie
   `campaia_session` (`HttpOnly`) **no servidor** (Server Component,
   `next/headers`) e chama `GET /me` no BFF, encaminhando o cookie —
   nunca no bundle do cliente. `LogoutButton` (Client Component) é a
   única chamada de rede feita pelo navegador: lê o cookie
   `campaia_csrf` (não-`HttpOnly`, por desenho) e o envia como header
   `X-CSRF-Token` em `POST {BFF_ORIGIN}/auth/logout`.

## Shell autenticado e troca de tenant (WP-03)

`/dashboard` é o shell autenticado real: tenant/unidade ativos vêm
exclusivamente da sessão (`GET /me`, `GET /session/memberships`) — nunca
de um header ou parâmetro fornecido pelo cliente. Estados padronizados
(`LoadingState`, `ErrorState`, `EmptyState`) cobrem carregando (via
`loading.tsx`, convenção do App Router), não configurado, não autenticado,
falha ao carregar memberships, e o próprio conteúdo (vazio até o WP-04
adicionar funcionalidade de negócio).

Quando a sessão tem mais de um membership real (hoje só a identidade de
teste `multi_tenant_owner`, ver `backend/api/test_idp.py`), um seletor de
tenant (`TenantSwitcher`, Client Component) aparece. Escolher um tenant
diferente faz `POST {BFF_ORIGIN}/session/switch-tenant` (protegido por
CSRF, igual ao logout) e recarrega a página — a sessão é reemitida
(novo `campaia_session`/`campaia_csrf`, mesma disciplina de rotação do
login) com o tenant escolhido como ativo, e qualquer step-up recente é
invalidado em TODOS os tenants do usuário (ADR-0018). Um usuário com um
único membership real nunca vê o seletor — não há nada para trocar.

## Onboarding e Brand Kit (WP-04)

`/onboarding` implementa a parte de `docs/product/13_ESPECIFICACAO_TELAS_APP.md`
§3.4/§4 que tem rota real por trás:

- **Conectar contas**: três cartões independentes (Google Ads, Meta,
  WhatsApp — `ConnectAccountCard`, Client Component). Nenhum provedor real
  existe ainda, então não há lista real de contas para escolher — clicar
  em "Conectar (simulado)" encadeia `POST {BFF_ORIGIN}/connections/oauth/
  start` e `POST {BFF_ORIGIN}/connections/oauth/complete` (ambos
  protegidos por CSRF; o `complete` também exige `Idempotency-Key`), que
  juntos criam uma `Connection` real e persistida — tudo rotulado
  "(simulado)" para nunca ser confundido com uma conexão real. Cada canal
  é opcional individualmente.
- **Brand Kit**: formulário (`BrandKitForm`, Client Component) com nome,
  tom de voz, cores, diferenciais e restrições, via `POST
  {BFF_ORIGIN}/brand-profiles` (CSRF + `Idempotency-Key`). Estado vazio
  explica que o Brand Kit não bloqueia a criação de campanhas.
- **Concluir Onboarding**: habilitado assim que `GET /connections` (lido
  server-side) retorna pelo menos uma conexão — a mesma regra de negócio
  do onboarding Flutter original, preservada como especificação
  funcional, nunca como código portado.

Fora de escopo, deliberadamente: cadastro de empresa/CNPJ e unidade de
negócio (§3.2/§3.3 do mesmo documento) — nenhum endpoint de criação de
tenant/unidade existe no backend (o `tenant_id` vem sempre da sessão
autenticada, WP-02/03); upload de logo (nenhum endpoint de upload existe).

## O que ainda não existe (fora do escopo do WP-01 a WP-04)

- Jornada de produto completa (briefing, estratégia por IA, aprovação,
  campanhas, publicação, conectores reais de provedor) — WP-05 em diante.
- Qualquer chamada ao BFF fora de `session.ts`/`LogoutButton.tsx`/
  `TenantSwitcher.tsx`/`BrandKitForm.tsx`/`ConnectAccountCard.tsx` — a
  tela `/` (WP-01) permanece inteiramente fixture-based.
- Deploy, infraestrutura, qualquer configuração de nuvem.
- Revisão de segurança humana (FM Security Engineer) da superfície de
  autenticação — pendência explícita, ver certificação do WP-02 (segue
  pendente; nenhuma revisão humana ocorreu em nenhuma execução até
  agora). Revisão de FM QA Engineer do WP-04 — também pendente.

## Fronteiras de segurança (WP-01 a WP-04)

Verificadas automaticamente por `npm run boundary:check` (e por
`tests/boundaries.test.ts`, que roda a mesma lógica sem subprocesso) a
cada execução local e no CI:

- Nenhum token, segredo, senha ou API key hardcoded no código-fonte.
- Nenhuma variável `NEXT_PUBLIC_*` com nome sensível (exposta ao
  navegador) — `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` é intencionalmente
  pública, não sensível.
- Nenhum uso de `localStorage`/`sessionStorage` para credenciais.
- Nenhuma chamada de rede (`fetch`/`axios`/`XMLHttpRequest`) em
  `web/src`, **exceto** `src/lib/session.ts` (leituras server-only),
  `src/components/LogoutButton.tsx` (logout client-side, protegido por
  CSRF), `src/components/TenantSwitcher.tsx` (troca de tenant, WP-03) e
  `src/components/{BrandKitForm,ConnectAccountCard}.tsx` (Brand Kit e
  conexão simulada de contas, WP-04) — os cinco únicos pontos legítimos,
  todos protegidos por CSRF. Todo o resto de `web/src`, incluindo a tela
  `/` e os componentes do WP-01, permanece em zero chamadas de rede.

Este script **não certifica segurança formal do produto** — apenas as
proibições explícitas de escopo do WP-01 a WP-04.

## Próximo gate

Gate 2 (WP-01) concluído — ver
`docs/web/08_CERTIFICACAO_WP01_FUNDACAO_WEB.md`. Gate 3 (WP-02,
autenticação) **implementado e autotestado, mas não formalmente
aprovado** — depende de revisão de segurança humana (FM Security
Engineer), ver `docs/web/09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md`.
Gate 4 (WP-03, tenancy) **implementado e autotestado** — ver
`docs/web/10_CERTIFICACAO_WP03_TENANCY_SHELL.md`; também depende de
aprovação de FM Security Engineer para o teste de isolamento, não
concedida nesta execução. Gate 5 (Primeira jornada) **parcialmente
implementado** pelo WP-04 (Onboarding e Brand Kit — ver
`docs/web/11_CERTIFICACAO_WP04_ONBOARDING_BRAND_KIT.md`, revisão de FM QA
Engineer pendente); só fecha por completo com o WP-05 (briefing,
estratégia e aprovação), **não iniciado nesta execução**.
