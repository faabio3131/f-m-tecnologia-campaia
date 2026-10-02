# CampaIA Web — Fundação (WP-01)

Fundação técnica do frontend Web do CampaIA. Este diretório implementa
exclusivamente o **WP-01 — Fundação do frontend Web**
(`docs/web/06_ROADMAP_WORK_PACKAGES.md`), aprovado pela ADR-0017
(`docs/15_ADR_0017_FRAMEWORK_FRONTEND_WEB.md`).

**Não é** um produto comercial concluído, não tem autenticação real, não
chama o backend (BFF) em nenhuma rota, e não implementa nenhuma regra de
negócio. A integração autenticada real começa no WP-02 (ADR-0018), em uma
execução futura separada.

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
npm run boundary:check      # varre web/src por token/segredo/localStorage/chamada de rede proibidos no WP-01
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

## Estrutura

```text
web/
  src/
    app/          # App Router: layout, página de fundação, estilos da página
    components/    # Button, Card, Badge, PageContainer, StatusPanel (únicos usados nesta fase)
    contracts/     # types.ts (import estável) + bff-openapi.generated.ts (gerado, não editar)
    fixtures/       # dado fictício local, tipado a partir do contrato
    styles/         # tokens.css — variáveis de design (cor, espaçamento, tipografia, motion)
  tests/           # Vitest: unitários, componentes, acessibilidade, fronteiras de segurança/contrato
  e2e/             # Playwright: smoke da tela de fundação
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

## O que ainda não existe (fora do escopo do WP-01)

- Autenticação, sessão, login, logout, CSRF — WP-02 (ADR-0018).
- Contexto de tenant/unidade real, shell autenticado do dashboard — WP-03.
- Qualquer chamada real ao BFF (`GET /me` exige `require_auth`; não há
  endpoint público no backend — confirmado em `backend/api/main.py` e
  `backend/api/routes_me.py`).
- Onboarding, Brand Kit, briefing, geração por IA, campanhas, publicação,
  conectores reais (Google Ads/Meta/WhatsApp).
- Deploy, infraestrutura, qualquer configuração de nuvem.

## Fronteiras de segurança do WP-01

Verificadas automaticamente por `npm run boundary:check` (e por
`tests/boundaries.test.ts`, que roda a mesma lógica sem subprocesso) a
cada execução local e no CI:

- Nenhum token, segredo, senha ou API key hardcoded no código-fonte.
- Nenhuma variável `NEXT_PUBLIC_*` com nome sensível (exposta ao
  navegador).
- Nenhum uso de `localStorage`/`sessionStorage` para credenciais.
- Nenhuma chamada de rede (`fetch`/`axios`/`XMLHttpRequest`) em
  `web/src`.

Este script **não certifica segurança formal do produto** — apenas as
proibições explícitas do escopo do WP-01.

## Próximo gate (não iniciado nesta execução)

Gate 2 concluído para o WP-01 quando este diretório, seus testes e seu CI
estiverem verdes no HEAD da PR (ver
`docs/web/07_CERTIFICACAO_PONTO_ZERO_WEB.md` e a certificação específica
do WP-01). O próximo passo — WP-02, autenticação e sessão Web real — **não
foi iniciado nesta execução** e aguarda um Prompt Mestre de implementação
dedicado, após a escolha do provedor de identidade específico.
