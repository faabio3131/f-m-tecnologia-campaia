# CampaIA — Ponto Zero Web · 08. Certificação do WP-01 (Fundação do frontend Web)

**Estado máximo declarado neste documento:** `WP-01 IMPLEMENTADO — AGUARDANDO CI DA PR PARA GATE 2 DEFINITIVO`

Este documento certifica a execução real do WP-01 (`docs/web/06_ROADMAP_WORK_PACKAGES.md`),
autorizada por "PROMPT MESTRE — CAMPAIA WEB FIRST / EXECUÇÃO REAL E COMPLETA DO WP-01"
(19/09/2026), sobre `main`@`41b521fed83b87d8cd0df3d1def2fd26f9af8379`
(merge certificado da PR #4, ADR-0016–0019 aprovadas).

O veredito final de Gate 2 — se `WP-01 VALIDADO — GATE 2 APROVADO` ou
`WP-01 IMPLEMENTADO — GATE 2 PENDENTE` — depende do CI da PR desta missão,
que só é conhecido depois deste documento ser escrito e commitado; por
isso ele não é antecipado aqui, seguindo a mesma disciplina de não
autorreferência já aplicada nas certificações anteriores deste repositório.
O relatório final da missão (fora deste arquivo) reporta o CI real da PR.

---

## 1. Escopo executado

Criação de `web/` — fundação Next.js/React/TypeScript do frontend Web do
CampaIA — e `.github/workflows/frontend-tests.yml`. Nenhuma outra parte do
repositório foi alterada.

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

Apenas `web/` (novo diretório completo) e
`.github/workflows/frontend-tests.yml` (novo). Confirmado por
`git status`/`git diff --stat` na execução: nenhuma alteração em
`mobile/`, `backend/campaia_core/`, `backend/api/`, `backend/db/`,
`contracts/`, nem em `.github/workflows/backend-tests.yml`.

## 17. Itens não verificados / pendências reais

- `npm audit` não foi executado nesta missão — fora do escopo explícito do WP-01.
- Cobertura de código (coverage) não foi medida — não exigida pelos critérios do WP-01.
- O CI da PR desta missão ainda não tinha rodado no momento em que este documento foi escrito — reportado no relatório final da missão, não aqui.
- Nenhum teste de carga, performance ou Lighthouse foi executado — fora do escopo do WP-01.

## 18. Confirmações negativas

- WP-02 **não foi iniciado** — nenhuma autenticação, sessão, cookie, CSRF, provedor de identidade.
- `mobile/` permaneceu em quarentena arquitetural, intocado.
- Nenhum merge foi executado por este documento.
- Nenhum deploy, nenhuma configuração de nuvem, nenhum serviço contratado.

## 19. Gate 2 — critérios (ver roadmap §WP-01)

| Critério | Situação |
|---|---|
| Branch correta, PR OPEN/DRAFT | Ver relatório final da missão |
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
| CI de frontend verde | Ver relatório final da missão |
| CI de backend verde | Reconfirmado localmente (267+81+24/24); CI real ver relatório final |
| Documentação/painel reconciliados | Sim (este documento + roadmap + doc 05 + painel) |
| Worktree limpa | Ver relatório final da missão |
| HEAD local = HEAD remoto | Ver relatório final da missão |
| Nenhuma regressão conhecida | Sim |

Enquanto os itens marcados "Ver relatório final da missão" não estiverem
confirmados, o status correto é `WP-01 IMPLEMENTADO — GATE 2 PENDENTE`.
