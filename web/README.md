# CampaIA Web — Fundação e sessão real (WP-01 + WP-02)

Fundação técnica do frontend Web do CampaIA. Este diretório implementa o
**WP-01 — Fundação do frontend Web** (aprovado pela ADR-0017) e o
**WP-02 — Autenticação e sessão Web real** (aprovado pela ADR-0018,
implementado em 20/09/2026 — ver
`docs/web/09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md`; revisão de
segurança humana por um FM Security Engineer ainda pendente).

**Não é** um produto comercial concluído. WP-01 (a tela `/`) permanece
inteiramente fixture-based, sem nenhuma chamada de rede — essa garantia
não mudou. WP-02 adiciona a página `/account`, que lê uma sessão real
(quando `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` está configurado) e permite
login/logout reais contra o backend — mas não implementa nenhuma tela de
produto, dashboard ou regra de negócio (isso é WP-03 em diante).

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

Nenhuma dependência de estado global, autenticação, SDK de provedor de
nuvem, analytics ou credencial foi instalada — deliberadamente fora do
escopo do WP-01.

## Instalação

```bash
cd web
npm ci
```

## Comandos

```bash
npm run dev            # servidor de desenvolvimento
npm run lint            # ESLint
npm run typecheck       # gera tipos de rota do Next.js + tsc --noEmit (modo estrito)
npm run test             # Vitest: unitários, componentes, acessibilidade, fronteiras
npm run test:e2e         # Playwright: smoke E2E (desktop + mobile)
npm run build             # build de produção (Next.js)
npm run contracts:generate  # regenera src/contracts/bff-openapi.generated.ts a partir de ../contracts/bff-openapi.yaml
npm run contracts:check     # falha se o arquivo gerado estiver desatualizado (drift)
npm run boundary:check      # varre web/src por token/segredo/localStorage/chamada de rede fora da allowlist (session.ts, LogoutButton.tsx)
npm run check              # agrega lint + typecheck + contracts:check + boundary:check + test + build
```

`npm run check` é o gate local completo (exceto E2E, que sobe um servidor
real e roda à parte via `npm run test:e2e`). Qualquer falha em qualquer um
desses comandos termina com código de saída diferente de zero.

### Executando o E2E localmente

O Playwright precisa de um binário Chromium compatível com a versão
instalada (`@playwright/test`). Em ambientes com um Chromium pré-instalado
em um caminho não padrão, exporte `CAMPAIA_CHROMIUM_PATH` antes de rodar:

```bash
CAMPAIA_CHROMIUM_PATH=/caminho/para/chromium npm run test:e2e
```

Se a variável não estiver definida, o Playwright usa o Chromium que ele
mesmo baixou (`npx playwright install chromium`).

## Variáveis de ambiente (WP-02)

| Variável | Obrigatória? | Efeito |
|---|---|---|
| `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` | Não | Origem pública do backend (BFF), ex. `https://api.campaia.app`. Sem ela, `/account` degrada honestamente para "não configurado" — nenhuma chamada de rede é feita, nenhuma sessão é simulada. **Não é um segredo**: é a mesma origem para a qual o navegador é redirecionado em `/auth/login`. |

Nenhuma outra variável de ambiente é lida por `web/`. Credenciais do
provedor de identidade (`CAMPAIA_OIDC_*`) e a flag de fixtures de teste
(`CAMPAIA_ENV`) vivem inteiramente no backend (`backend/`) — nunca no
frontend.

## Estrutura

```text
web/
  src/
    app/          # App Router: layout, página de fundação (/), página de conta (/account, WP-02)
    components/    # Button, Card, Badge, PageContainer, StatusPanel, LogoutButton (WP-02, client)
    contracts/     # types.ts (import estável) + bff-openapi.generated.ts (gerado, não editar)
    fixtures/       # dado fictício local, tipado a partir do contrato (usado só por /)
    lib/            # session.ts (WP-02): leitura de sessão real, server-only
    styles/         # tokens.css — variáveis de design (cor, espaçamento, tipografia, motion)
  tests/           # Vitest: unitários, componentes, acessibilidade, fronteiras de segurança/contrato
  e2e/             # Playwright: smoke de / (WP-01) e /account (WP-02)
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

## O que ainda não existe (fora do escopo do WP-01/WP-02)

- Contexto de tenant/unidade real, shell autenticado do dashboard — WP-03.
- Qualquer chamada ao BFF fora de `session.ts`/`LogoutButton.tsx` — a
  tela `/` (WP-01) permanece inteiramente fixture-based.
- Onboarding, Brand Kit, briefing, geração por IA, campanhas, publicação,
  conectores reais (Google Ads/Meta/WhatsApp).
- Deploy, infraestrutura, qualquer configuração de nuvem.
- Revisão de segurança humana (FM Security Engineer) da superfície de
  autenticação — pendência explícita, ver certificação do WP-02.

## Fronteiras de segurança (WP-01 + WP-02)

Verificadas automaticamente por `npm run boundary:check` (e por
`tests/boundaries.test.ts`, que roda a mesma lógica sem subprocesso) a
cada execução local e no CI:

- Nenhum token, segredo, senha ou API key hardcoded no código-fonte.
- Nenhuma variável `NEXT_PUBLIC_*` com nome sensível (exposta ao
  navegador) — `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` é intencionalmente
  pública, não sensível.
- Nenhum uso de `localStorage`/`sessionStorage` para credenciais.
- Nenhuma chamada de rede (`fetch`/`axios`/`XMLHttpRequest`) em
  `web/src`, **exceto** `src/lib/session.ts` (leitura de sessão
  server-only) e `src/components/LogoutButton.tsx` (logout client-side,
  protegido por CSRF) — os dois únicos pontos legítimos introduzidos
  pelo WP-02. Todo o resto de `web/src`, incluindo a tela `/` e os 5
  componentes do WP-01, permanece em zero chamadas de rede.

Este script **não certifica segurança formal do produto** — apenas as
proibições explícitas de escopo do WP-01/WP-02.

## Próximo gate

Gate 2 (WP-01) concluído — ver
`docs/web/08_CERTIFICACAO_WP01_FUNDACAO_WEB.md`. Gate 3 (WP-02,
autenticação) **implementado e autotestado, mas não formalmente
aprovado** — depende de revisão de segurança humana (FM Security
Engineer), ver `docs/web/09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md`.
O próximo passo — WP-03, contexto de tenant/unidade e shell autenticado —
**não foi iniciado nesta execução**.
