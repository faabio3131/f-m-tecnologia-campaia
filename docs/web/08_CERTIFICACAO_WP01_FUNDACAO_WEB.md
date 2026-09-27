# CampaIA — Ponto Zero Web · 08. Certificação do WP-01 (Fundação do frontend Web)

**Estado máximo declarado neste documento:** `WP-01 VALIDADO — GATE 2 APROVADO`

Este documento certifica a execução real do WP-01 (`docs/web/06_ROADMAP_WORK_PACKAGES.md`),
autorizada por "PROMPT MESTRE — CAMPAIA WEB FIRST / EXECUÇÃO REAL E COMPLETA DO WP-01"
(19/09/2026), sobre `main`@`41b521fed83b87d8cd0df3d1def2fd26f9af8379`
(merge certificado da PR #4, ADR-0016–0019 aprovadas).

**Reconciliação (20/09/2026)**: esta seção inicial foi corrigida após confirmação direta do
CI real da PR #5 no HEAD `cb6d8fe` — ambos os workflows (`CAMPAIA Backend Tests` run
`35481949324` e `CAMPAIA Frontend Tests` run `35481949368`) `completed`/`success`,
confirmado via `mcp__github__actions_list`. O veredito `WP-01 VALIDADO — GATE 2 APROVADO`
substitui o anterior `WP-01 IMPLEMENTADO — AGUARDANDO CI DA PR PARA GATE 2 DEFINITIVO`,
que era o estado correto no momento em que este documento foi escrito pela primeira vez
(antes do CI existir) — ver §19 para o checklist completo.

---

## 1. Escopo executado

Criação de `web/` — fundação Next.js/React/TypeScript do frontend Web do
CampaIA — e `.github/workflows/frontend-tests.yml`. Nenhum arquivo de
`backend/campaia_core/`, `backend/api/`, `backend/db/`, `contracts/` ou
`mobile/` foi alterado.

**Correção (20/09/2026)**: a frase anterior ("nenhuma outra parte do
repositório foi alterada") estava imprecisa — o mesmo commit que introduz
este documento também atualiza `docs/web/00,02,03,04,05,06_*.md` (propagação
de status) e cria `backend/01_PAINEL_EXECUCAO_v21_VIGENTE.md` (painel), como
o próprio §16 já detalhava corretamente. O escopo real da PR #5 inteira é
**49 arquivos**: todo `web/` (código, testes, config), 1 workflow novo, e a
documentação/painel citados — confirmado por `git diff --stat main..HEAD` e
pelo `changed_files` da PR no GitHub.

## 2. Versões-base

| Dependência | Versão |
|---|---|
| Node.js (usado nesta execução) | v22.22.2 |
| Next.js | 16.3.5 (App Router) |
| React | 19.2.8 |
| TypeScript | ^5, modo `strict: true` |

## 3. Dependências adicionadas e justificativa

| Dependência | Categoria | Justificativa |
|---|---|---|
| `next`, `react`, `react-dom` | runtime | base do framework aprovado (ADR-0017) |
| `typescript`, `@types/*` | dev | TypeScript estrito |
| `eslint`, `eslint-config-next` | dev | lint (scaffold padrão do `create-next-app`) |
| `openapi-typescript` | dev | geração determinística de tipos a partir de `contracts/bff-openapi.yaml`, sem editar o contrato |
| `vitest`, `@vitejs/plugin-react`, `jsdom` | dev | test runner unitário/componente |
| `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event` | dev | testes de componente e interação real (clique, teclado) |
| `jest-axe`, `@types/jest-axe` | dev | baseline automatizada de acessibilidade |
| `@playwright/test` | dev | smoke E2E |

Nenhuma biblioteca de estado global, autenticação, SDK de provedor de
nuvem, analytics ou credencial foi instalada — confirmado por leitura de
`package.json` (ver §12, prova de ausência de secrets).

## 4. Contrato OpenAPI utilizado e fixture criada

Fonte: `contracts/bff-openapi.yaml`, schema `Me` (endpoint `GET /me`,
`operationId: getMe`). Tipos gerados deterministicamente por
`openapi-typescript` em `web/src/contracts/bff-openapi.generated.ts`
(cabeçalho no topo do arquivo identifica a origem; comentário proíbe
edição manual). Import estável em `web/src/contracts/types.ts`
(`export type Me = components["schemas"]["Me"]`).

Fixture: `web/src/fixtures/me.local.ts` — um único objeto `Me`
inteiramente fictício (UUIDs de exemplo `00000000-…-000000000001`/`…002`,
papel `owner`, `mfa_enabled: false`), tipado estaticamente contra `Me`.
Consumida diretamente por `web/src/app/page.tsx`.

## 5. Prova de ausência de chamada real ao BFF

- Varredura estática: `npm run boundary:check` — nenhuma ocorrência de
  `fetch(`/`axios`/`XMLHttpRequest` em `web/src` (ver §6).
- Prova dinâmica: `e2e/foundation.spec.ts` registra todas as requisições
  de rede feitas pela página real, em um navegador real (Chromium), e
  falha se qualquer uma corresponder a um padrão de BFF (`/me`,
  `localhost:8000`, `:8000/`) — **0 requisições desse tipo capturadas**.

## 6. Prova de ausência de secrets

- `npm run boundary:check` (lógica em `scripts/lib/security-boundaries.mjs`,
  compartilhada com `tests/boundaries.test.ts`) varre `web/src` por:
  chamada de rede, uso de `localStorage`/`sessionStorage` para
  `setItem`/`getItem`, valor literal `Bearer …`, atribuição de literal a
  variável de nome `token`/`secret`/`password`/`apiKey`, variável
  `NEXT_PUBLIC_*` com nome sensível, padrão de chave estilo AWS
  (`AKIA…`). **Resultado: 0 violações em 17 arquivos.**
- Varredura adicional manual (grep) sobre todo `web/` (exceto
  `node_modules`/`.next`) por `AKIA[0-9A-Z]{16}`, `Bearer <token real>`,
  chave privada PEM, e atribuição de senha literal — **nenhuma ocorrência**.
- Não certifica segurança formal do produto — apenas as proibições
  explícitas do escopo do WP-01.

## 7. Testes unitários e de componente — comando e resultado

```
$ npm run test
> vitest run
 Test Files  5 passed (5)
      Tests  15 passed (15)
```

Arquivos: `tests/me-fixture.test.ts` (fixture corresponde ao schema `Me`,
usa apenas UUIDs fictícios), `tests/components.test.tsx` (`Button`,
`Badge`, `Card`, `StatusPanel` — renderização, clique, navegação por
teclado), `tests/foundation-page.test.tsx` (nome/slogan do CampaIA, aviso
explícito de fundação técnica, aviso de "nenhuma sessão real ativa", dado
de fixture visível, ausência de indicador de sessão real como logout),
`tests/boundaries.test.ts` (fronteiras de segurança e drift de contrato,
executados in-process a partir de `scripts/lib/`).

## 8. Acessibilidade — comando e resultado

```
$ npm run test  # inclui tests/accessibility.test.tsx
✓ FoundationPage accessibility baseline > has no detectable automated accessibility violations
```

Executado com `jest-axe` sobre a árvore renderizada da tela de fundação.
Uma violação real foi encontrada durante o desenvolvimento (`landmark-unique`
— dois `<section>` com o mesmo `aria-labelledby`) e corrigida na origem:
`StatusPanel` agora deriva um `id` de heading único a partir do título
(`src/components/StatusPanel.tsx`), não apenas silenciada.

Veredito máximo permitido: **baseline automatizada de acessibilidade
aprovada para o scaffold** — não é certificação WCAG completa.

## 9. E2E smoke — comando e resultado

```
$ CAMPAIA_CHROMIUM_PATH=<chromium> npx playwright test
  ✓ [desktop-chromium] loads the foundation page with no critical console errors and no BFF network calls
  ✓ [desktop-chromium] renders without horizontal overflow at the current viewport
  ✓ [mobile-chromium] loads the foundation page with no critical console errors and no BFF network calls
  ✓ [mobile-chromium] renders without horizontal overflow at the current viewport
  4 passed
```

Projetos: `desktop-chromium` (Desktop Chrome) e `mobile-chromium`
(Pixel 7). Sem simulação de login, conforme exigido.

## 10. Lint — comando e resultado

```
$ npm run lint
> eslint .
(sem erros)
```

## 11. Typecheck — comando e resultado

```
$ npm run typecheck
> next typegen && tsc --noEmit
✓ Types generated successfully
(sem erros)
```

`next typegen` é executado antes de `tsc --noEmit` porque os tipos de
rota do App Router (`LayoutProps<'/'>`) são gerados pelo Next.js, não
existem em um checkout limpo antes da primeira geração — confirmado ao
reproduzir o erro `Cannot find name 'LayoutProps'` em um `node_modules`/`.next`
limpos e corrigido adicionando o passo, não suprimindo o erro.

## 12. Build de produção — comando e resultado

```
$ npm run build
> next build
✓ Compiled successfully
✓ Generating static pages (4/4)
Route (app): / , /_not-found — ambas (Static)
```

Reproduzido do zero: `rm -rf node_modules .next && npm ci && npm run check`
— todos os gates (lint, typecheck, contract-drift, boundary-check, testes,
build) verdes a partir de checkout limpo, sem depender de arquivo local
não versionado, segredo, serviço externo, backend, banco, Docker ou
credencial de provider.

## 13. Backend — domínio (regressão, comando e resultado)

```
$ cd backend && python3 -m unittest discover -s tests -v
Ran 267 tests
OK
```

Igual ao baseline anterior à execução do WP-01 (267 aprovados) — nenhuma
regressão.

## 14. Backend — API (regressão, comando e resultado)

```
$ cd backend && python3 -m unittest discover -s tests_api -t . -v
Ran 81 tests
OK
```

Igual ao baseline (81 aprovados) — nenhuma regressão.

## 15. AsyncAPI (regressão, comando e resultado)

```
$ cd contracts && python3 validate_events_asyncapi.py
=== ALL CHECKS PASSED (24 events verified end-to-end) ===
```

Igual ao baseline (24/24) — nenhuma regressão.

## 16. Escopo do diff

**49 arquivos alterados** (`main..HEAD` da PR #5, confirmado por
`git diff --stat` e pelo `changed_files` do GitHub): todo `web/` (novo
diretório completo — código, testes, configuração), 1 workflow novo
(`.github/workflows/frontend-tests.yml`), e documentação/painel
(`docs/web/00,02,03,04,05,06,08_*.md`, `backend/01_PAINEL_EXECUCAO_v21_VIGENTE.md`).
Confirmado por `git diff --stat main..HEAD -- mobile/ backend/campaia_core
backend/api backend/db contracts/`: **nenhuma alteração** em nenhum desses
diretórios, nem em `.github/workflows/backend-tests.yml`.

## 17. Itens não verificados / pendências reais

- `npm audit` não foi executado nesta missão — fora do escopo explícito do WP-01.
- Cobertura de código (coverage) não foi medida — não exigida pelos critérios do WP-01.
- Nenhum teste de carga, performance ou Lighthouse foi executado — fora do escopo do WP-01.

## 18. Confirmações negativas

- WP-02 **não foi iniciado** — nenhuma autenticação, sessão, cookie, CSRF, provedor de identidade.
- `mobile/` permaneceu em quarentena arquitetural, intocado.
- Nenhum merge foi executado por este documento.
- Nenhum deploy, nenhuma configuração de nuvem, nenhum serviço contratado.

## 19. Gate 2 — critérios (ver roadmap §WP-01)

| Critério | Situação |
|---|---|
| Branch correta, PR OPEN/DRAFT | Sim — PR #5, `open`/`draft: true`/`merged: false`, `mergeable_state: clean` |
| Scaffold Next.js/React criado | Sim |
| TypeScript estrito | Sim |
| Lockfile presente | Sim (`package-lock.json`) |
| Lint verde | Sim |
| Typecheck verde | Sim |
| Testes unitários/componente verdes | Sim (15/15) |
| Baseline de acessibilidade verde | Sim |
| Fixture tipada compatível com OpenAPI | Sim |
| Nenhuma chamada real ao BFF | Sim (estático + E2E) |
| Nenhum token/segredo | Sim |
| Verificação de fronteiras verde | Sim |
| Build de produção verde | Sim |
| Smoke E2E verde | Sim (4/4) |
| CI de frontend verde | Sim — run `35481949368` (`CAMPAIA Frontend Tests`), `completed`/`success` no HEAD `cb6d8fe` |
| CI de backend verde | Sim — run `35481949324` (`CAMPAIA Backend Tests`), `completed`/`success` no HEAD `cb6d8fe`; reconfirmado localmente (267+81+24/24) |
| Documentação/painel reconciliados | Sim (este documento + roadmap + doc 05 + painel) |
| Worktree limpa | Sim — `git status` → "nothing to commit, working tree clean" |
| HEAD local = HEAD remoto | Sim — `cb6d8feead7e4f40405f38632474559ce1f9d4e6` em ambos, confirmado via `git ls-remote` |
| Nenhuma regressão conhecida | Sim |

Todos os critérios estão satisfeitos e confirmados diretamente (CI via
`mcp__github__actions_list`, não apenas localmente) — o status correto é
`WP-01 VALIDADO — GATE 2 APROVADO`.
