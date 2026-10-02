# Evidência — Etapa 2, Frontend Web Foundation + Auth Client + Authenticated App Shell

**Data:** 25/09/2026 · **HEAD desta execução:** `24a0e2dc6a913756704373a410e59a300e8ee471`
(merge de `main` em `feat/campaia-wp01-web-foundation`). **Branch de trabalho:**
`feat/campaia-wp01-web-foundation` (reaproveitada — ver DECISÃO abaixo). **PR associada:**
https://github.com/faabio3131/f-m-tecnologia-campaia/pull/5 (DRAFT, aberta, aguardando
decisão humana antes desta sessão).

## DECISÃO — reaproveitar a branch/PR #5 em vez de criar `feat/web-foundation-auth-shell`

**FATO CONFIRMADO:** ao iniciar esta missão, `feat/campaia-wp01-web-foundation` já existia,
remota, com PR #5 aberta em DRAFT, contendo uma fundação Next.js certificada (WP-01) —
design system mínimo, `contracts/bff-openapi.yaml` → tipos gerados, smoke E2E
(`e2e/foundation.spec.ts`), CI (`frontend-tests.yml`) — deliberadamente deixada em draft
"aguardando decisão humana" antes desta sessão.

**DECISÃO (autoridade humana, Diretor):** em vez de criar uma segunda branch/PR do zero
(`feat/web-foundation-auth-shell`, como o texto da missão nomeava literalmente), atualizar
`feat/campaia-wp01-web-foundation` com o `main` atual e construir o trabalho desta Etapa 2
(auth client + app shell autenticado) como novos commits na MESMA branch/PR #5. Reaproveita o
scaffold já certificado; evita duplicar Next.js/design system/CI web do zero. Esta decisão
substitui o nome de branch literal da missão; não há conflito de autoridade porque foi
decisão explícita e atual, mais alta na hierarquia que o texto da missão.

## Baseline confirmado antes de qualquer mudança desta Etapa 2

- `main` HEAD: `851db13723c3575d516bed64d71535cd7fed8bca` (PR #30, WP-02 auth real mergeada).
- `feat/campaia-wp01-web-foundation` já 100% caught-up com esse `main` (merge commit
  `24a0e2d`), sem conflitos.
- `python3 -m unittest discover -s tests` (backend): 366 testes, `OK`.
- `python3 -m unittest discover -s tests_api -t .` (backend): 140 testes, `OK`.
- `contracts/bff-openapi.yaml`: `Me` e `Error` documentados; **`/auth/session` (POST/GET/
  DELETE) NÃO documentado no contrato OpenAPI** — PENDÊNCIA registrada abaixo, não corrigida
  nesta sessão (fora do escopo autorizado: a missão proíbe alterar o contrato para adaptar o
  frontend).

## O que foi construído (IMPLEMENTADO + TESTADO)

### Backend — harness de E2E, nunca produção

- `backend/tests_support/` (novo pacote, docstring explícita "nunca importado por
  produção"): `e2e_identity.py` (`DeterministicTestIdTokenVerifier`, 4 tokens fixos
  mapeados aos fixtures reais de `seed_dev_identity_directory()`: tenant A owner, tenant B
  owner, e-mail não verificado, e-mail sem vínculo); `e2e_server.py` (`build_e2e_app()` monta
  `create_app(env="test")` real, substitui apenas `state.id_token_verifier` e
  `state.allowed_origins`, roda via `uvicorn` real).
- `backend/tests/test_architecture_boundaries.py` (novo): regex estático garantindo que
  `tests_support` nunca é importado por `api/` ou `campaia_core/` — 2 testes, `OK`.
- `backend/requirements.txt`: adicionado `uvicorn==0.38.0` (necessário para o harness rodar
  como servidor ASGI real nos testes E2E; não fazia parte do runtime de produção antes
  porque não havia harness de E2E real).
- Nenhum endpoint de bypass foi criado. Nenhuma rota de produção foi alterada. O harness troca
  apenas a implementação do verificador de ID token (protocolo `IdTokenVerifier` já existente)
  por uma determinística — toda a lógica real de sessão, CSRF, cookies, autorização e
  fail-closed em `api/routes_auth.py` roda sem modificação.

### Frontend — cliente HTTP central, IdentityClient, AuthProvider, app shell autenticado

- `web/src/lib/api/client.ts`: cliente HTTP único (`api.get/post/put/patch/delete`),
  `BASE_PATH = "/api/campaia"`, `credentials: "include"`, CSRF double-submit **em memória
  apenas** (nunca `localStorage`/`sessionStorage`), fail-closed local para mutação sem CSRF
  (`CsrfUnavailableError`, nunca envia a mutação), listener global de 401 (nunca confundido
  com 403), timeout/abort, parsing de erro canônico (`ApiErrorBody`).
- `web/src/lib/auth/identity-client.ts` + `test-identity-client.ts`: `IdentityClient`
  (interface), `createIdentityClient()` sempre devolve `NotConfiguredIdentityClient` em
  produção (item 1.6 do cronograma — Google Identity Platform real — permanece pendente,
  nenhuma credencial real inventada). Modo de teste só ativa via
  `NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test`, nunca em produção.
- `web/src/providers/AuthProvider.tsx`: bootstrap real via `GET /auth/session` (nunca
  confiado só à presença do cookie), listener de 401 global, `login()`/`logout()` reais.
  `logout()` deliberadamente não usa o `api.delete()` genérico (que bloqueia fail-closed
  qualquer mutação sem CSRF em memória) — logout precisa funcionar mesmo quando a sessão já
  está inválida/expirada e não há `csrf_token` algum; ainda envia o header quando disponível.
- `web/src/app/(app)/(authenticated)/layout.tsx`: route guard real — autoridade é
  `GET /auth/session` (via `AuthProvider`), nunca a mera presença do cookie. Durante bootstrap
  renderiza carregamento, nunca conteúdo privado; sessão inválida → redireciona para
  `/login?next=<rota>`.
- `web/src/app/(app)/login/page.tsx`: login real via harness de teste quando habilitado;
  produção mostra "Login com Google indisponível" (item 1.6 pendente) — nunca finge um login
  Google real.
- `web/src/app/(app)/(authenticated)/{dashboard,campaigns,approvals,brand-kit,connections,
  settings}/page.tsx`: dashboard mostra sessão/contexto reais (nenhum KPI inventado);
  campaigns/approvals/brand-kit/connections são `EmptyState` honestos (módulos de negócio
  ainda não implementados); settings mostra tenant/BU reais e registra a troca de
  tenant/BU como PENDÊNCIA (ver abaixo).
- `web/src/components/{Input,Spinner,EmptyState,ErrorState,PageHeader,AppShell}.tsx` (+ CSS
  modules): extensões do design system mínimo do WP-01, mesmas convenções.
- `web/scripts/lib/security-boundaries.mjs`: regra `network-call` original do WP-01 (zero
  chamada de rede em `app/page.tsx`) preservada intacta via `exemptPathSubstrings`, escopada
  apenas à nova camada de auth/API; nova regra `private-data-caching` (guarda de regressão
  arquitetural, escopada ao grupo de rotas autenticado) proíbe cache global de dado privado —
  exigência explícita da missão (seção 23).

## Achado real e correção — `next dev` (Turbopack) quebra hidratação neste ambiente sandboxed

**FATO CONFIRMADO (reproduzido, isolado e comprovado nesta sessão):** com o harness E2E
configurado para subir o frontend via `next dev` (decisão original, para permitir
`NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test` "lido em tempo real"), **todas** as 11 cenas do
protocolo de sessão falhavam identicamente: a UI travava para sempre no estado inicial de SSR
("Verificando sessão"), nenhum efeito React rodava, nenhum `fetch` era disparado.

Diagnóstico isolado (fora do runner de teste, com scripts de depuração descartáveis, nunca
comitados): o WebSocket de HMR do Turbopack (`ws://.../_next/hmr`) falha o handshake
(`net::ERR_INVALID_HTTP_RESPONSE`) neste container, o que impede a hidratação do React no
cliente por completo — comprovado instrumentando `window.fetch` e um `console.log` síncrono
no corpo do `AuthProvider`: nenhum dos dois disparava sob `next dev`, e ambos disparavam
normalmente sob `next build` + `next start` (produção), onde a mesma UI hidrata e o bootstrap
real (`GET /auth/session`) roda corretamente.

**Correção:** `web/playwright.session.config.ts` agora builda com
`NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test` (lido em build time, já que é inlined no bundle;
build determinístico, sempre com o mesmo valor) e serve com `next start` — nunca `next dev`.
Isso não é um mascaramento de regressão: a lógica de `AuthProvider`/route guard estava correta
o tempo todo; o defeito era exclusivamente do modo de desenvolvimento do Turbopack neste
ambiente de execução, não do código de produção.

## Achados reais e correções no próprio harness de teste E2E

Depois da correção acima, mais 2 classes de defeito real no arquivo de teste (nunca no
código de produção) apareceram e foram corrigidas:

1. **Race de rede real**: `waitForResponse((r) => r.url().endsWith("/auth/session"))`, sem
   filtrar o método, podia capturar por engano o `GET /auth/session` de bootstrap que o
   `AuthProvider` sempre dispara ao montar a página de login (mesmo sem sessão) — corrigido
   filtrando `r.request().method() === "POST"` (helper `loginViaTestHarness`).
2. **`page.request` (APIRequestContext) nunca repassa o cookie `campaia_session` setado por
   um `fetch()` do próprio script da página**, mesmo que `context.cookies()` (consulta direta
   ao navegador via CDP) já confirme o cookie presente — limitação observada do cliente de
   teste (Playwright 1.63 + Chromium), não do backend nem do `AuthProvider`: o próprio
   navegador manda o cookie corretamente em toda navegação/fetch subsequente. Corrigido
   anexando o cookie explicitamente (`sessionCookieHeader()`, lido de
   `context.cookies()`) a cada chamada de API do harness de teste.
3. Locators ambíguos (`getByText("demo-tenant")` casava 2 elementos reais — badge no topbar e
   `StatusPanel` no corpo da página, ambos exibições legítimas) — corrigido com `.first()`.
4. Mensagem amigável de erro do frontend (`PERMISSION_DENIED`) usava texto diferente do que o
   teste esperava — ajustado o texto da UI (`"...está sem vínculo com nenhum tenant..."`),
   sem alterar nenhuma decisão de autorização (a decisão real é 100% do backend).

Nenhuma dessas correções alterou lógica de autenticação, autorização, sessão, CSRF ou
isolamento de tenant — todas em código de teste (E2E spec, config do Playwright) ou texto de
UI não relacionado a segurança.

## Gates executados nesta sessão (comando real + resultado real + HEAD)

Todos no HEAD `24a0e2dc6a913756704373a410e59a300e8ee471` (mais os arquivos ainda não
commitados listados no `git status` desta sessão):

| Gate | Comando | Resultado |
|---|---|---|
| Lint (web) | `npm run lint` | `OK`, 0 problemas |
| Typecheck (web) | `npm run typecheck` | `OK`, 0 erros |
| Unit/component (web) | `npm run test` (Vitest) | `32 passed (32)`, 8 arquivos |
| Boundary check (web) | `npm run boundary:check` | `OK`, 44 arquivos, 0 violações |
| Contract drift (web) | `npm run contracts:check` | `OK`, gerado em sincronia com `bff-openapi.yaml` |
| Build produção (web) | `npm run build` | `OK`, 11 rotas, todas estáticas |
| E2E smoke WP-01 (web) | `npm run test:e2e` | `4 passed (4)` — desktop + mobile, escopado a `foundation.spec.ts` |
| E2E protocolo de sessão (web+backend real) | `npm run test:e2e:session` | **`11 passed (11)`** — cenários A–J + I2, incluindo o cross-tenant OBRIGATÓRIO (J) |
| Testes de domínio (backend) | `python3 -m unittest discover -s tests` | `368 passed` (366 + 2 novos de arquitetura) |
| Testes de API (backend) | `python3 -m unittest discover -s tests_api -t .` | `140 passed` (sem regressão de contagem) |
| AsyncAPI (contracts) | `python3 validate_events_asyncapi.py` | `ALL CHECKS PASSED (24 eventos)` |

**O cenário J (cross-tenant, OBRIGATÓRIO) passou**: sessão do tenant A cria um brand profile
real via mutação autenticada; sessão do tenant B, em `BrowserContext` totalmente separado
(cookies isolados), lista brand profiles e recebe `[]` — o tenant vem exclusivamente da
sessão real do servidor, nunca de header/body/query controlável pelo navegador. A UI de B
também nunca renderiza qualquer texto do segredo de A.

## PENDÊNCIAS registradas (não resolvidas nesta sessão, fora de escopo ou dependentes de item externo)

1. **Item 1.6 do cronograma mestre — Google Identity Platform real**: não configurado.
   `IdentityClient` de produção permanece `NotConfiguredIdentityClient`; a UI de login mostra
   explicitamente "indisponível" em produção. Nenhuma credencial real foi inventada ou
   simulada.
2. **`SessionStore` do backend ainda em memória** (WP-02, não desta Etapa 2) — persistência
   de sessão sobrevivendo a restart do processo não foi implementada; fora do escopo desta
   missão.
3. **Contrato `bff-openapi.yaml` não documenta `/auth/session`** (POST/GET/DELETE) nem seus
   schemas de request/response — gap pré-existente ao início desta sessão, registrado, não
   corrigido (a missão proíbe alterar o contrato para adaptar o frontend; corrigir o gap em si
   seria uma mudança de contrato que exige análise e aprovação próprias, fora deste escopo).
4. **Troca de tenant/BU pela UI** — `settings/page.tsx` mostra tenant/BU atuais mas não
   oferece troca; múltiplos vínculos por usuário (se existirem) não são navegáveis pela UI
   ainda. Registrado explicitamente na própria página.
5. **CI real do frontend para este novo trabalho** (workflow dedicado ou extensão do
   `frontend-tests.yml` existente cobrindo o novo E2E de protocolo de sessão) — ainda não
   escrito nesta sessão; será tratado antes do push/PR final, ou registrado como pendência
   explícita no PR se não houver tempo de sessão para configurá-lo com o backend Python
   necessário.

## Status exato de prontidão

`ETAPA 2 WEB FOUNDATION + AUTH SHELL IMPLEMENTADA + TESTADA — PRONTA PARA REVISÃO.`

Nunca `HOMOLOGADO`, nunca `PRONTO PARA PRODUÇÃO`, nunca "Google Identity homologado" — item
1.6 permanece pendente e `SessionStore` é em memória. Merge para `main` não ocorreu nesta
sessão e não está autorizado sem decisão humana explícita e atual sobre a PR #5 (a exceção do
Diretor de 24/09/2026 sobre merge com suíte 100% verde cobre apenas o gate de merge, não
substitui a decisão de merge em si nem dispensa revisão humana da PR).
