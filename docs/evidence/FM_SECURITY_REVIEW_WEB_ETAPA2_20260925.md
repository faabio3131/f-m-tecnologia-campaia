# Revisão de segurança focada — Frontend Web, Etapa 2 (Auth Client + App Shell)

**Data:** 25/09/2026 · **Escopo:** todo o diff novo desta Etapa 2 em `web/` e
`backend/tests_support/`, no HEAD `24a0e2dc6a913756704373a410e59a300e8ee471` mais os arquivos
ainda não commitados nesta sessão. **Não certifica o produto como seguro** — reporta achados
reais com severidade, nada mais.

## Achados

### 1. Open redirect via `?next=` na página de login — CORRIGIDO nesta sessão

**Severidade: média.** `web/src/app/(app)/login/page.tsx` lia `searchParams.get("next")` sem
validar e chamava `router.replace(nextPath)` após login bem-sucedido. Um link de phishing
como `/login?next=//atacante.example/pagina` poderia, em tese, redirecionar o usuário
autenticado para fora do domínio do CampaIA imediatamente após um login real.

**Correção aplicada:** `nextPath` só é aceito se começar com `/` e não com `//` (caminho
relativo interno); qualquer outro valor cai para `/dashboard`. O guard de rota
(`(authenticated)/layout.tsx`) já fazia isso corretamente via `encodeURIComponent(pathname)`
(nunca lê de `?next=` recebido de fora) — o problema era exclusivo do consumo em
`login/page.tsx`.

### 2. Tokens de teste (`e2e-test-id-token-*`) presentes no bundle de produção — residual aceito, documentado

**Severidade: baixa.** `web/src/lib/auth/test-identity-client.ts` é importado
incondicionalmente por `login/page.tsx`; as 4 strings de token de teste (nunca credenciais
reais — não são segredos, não autenticam nada fora do harness de E2E) acabam presentes como
literais inertes no bundle JS entregue ao navegador mesmo em build de produção.

**Por que não é um bypass real:** `isTestIdentityModeEnabled()` lê
`process.env.NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE`, inlined em build time — em qualquer build sem
essa variável (produção real), o botão nunca renderiza e a função `login()` nunca é chamada
com esses IDs. Mesmo que um atacante lesse o bundle e chamasse `login()` manualmente com um
desses tokens contra um backend de produção real, o backend real usa
`AlwaysRejectIdTokenVerifier`/o adapter real do Google (nunca
`DeterministicTestIdTokenVerifier`) — a string não tem efeito nenhum lá.

**Recomendação não aplicada nesta sessão (fora de escopo, não bloqueante):** poderia-se usar
`next/dynamic` com `ssr: false` e import condicional para excluir completamente o módulo do
bundle de produção; não foi feito porque o risco residual é nulo em termos de autorização
real (a autoridade nunca sai do backend) e a mudança adicionaria complexidade de
code-splitting não solicitada pela missão.

### 3. CSRF, cookies, sessão — sem achado

- Cookie de sessão: `HttpOnly; Secure; SameSite=Lax` (backend, não desta Etapa 2, mas
  verificado real em toda resposta observada nos testes E2E desta sessão).
- CSRF: double-submit real, token em memória apenas no cliente (nunca
  `localStorage`/`sessionStorage`/cookie legível por JS), fail-closed local antes de qualquer
  mutação sem token em memória (`CsrfUnavailableError`).
- Login (`POST /auth/session`) não exige `X-CSRF-Token` (não pode, não há sessão anterior) —
  protegido pelo backend via allowlist de Origin/Referer (login-CSRF), verificado
  indiretamente pelos testes E2E reais (nenhuma requisição cross-origin foi tentada nesta
  sessão contra esse allowlist especificamente; validação completa desse allowlist é
  responsabilidade do WP-02, já coberta por `tests_api`).
- 401 vs. 403: nunca tratados como sinônimos (`onUnauthenticated` só dispara em 401;
  `PERMISSION_DENIED`/403 é tratado como erro de negócio, exibido ao usuário, sessão
  preservada).

### 4. Cache de dado privado — sem achado

Nenhuma rota autenticada usa `fetch` com cache padrão do Next (`cache: "force-cache"`) nem
`revalidate`; `api.get()` sempre usa `fetch()` puro do navegador (sem cache HTTP do Next.js
Data Cache, que só se aplica a `fetch()` no lado do servidor/RSC). Nova regra estática
`private-data-caching` em `security-boundaries.mjs`, escopada ao grupo de rotas autenticado,
adicionada como guarda de regressão para o futuro.

### 5. SSR / vazamento de dado entre requisições — sem achado

`AuthProvider` só existe como `"use client"`, montado sob `app/(app)/layout.tsx`; nenhuma
página autenticada busca dado de sessão no servidor (SSR/RSC) — todo o bootstrap acontece no
navegador via `GET /auth/session`, então não há risco de um `AppState`/módulo Node
compartilhado entre requisições de usuários diferentes vazar dado de sessão (o problema
clássico de cache global de RSC em Next.js).

### 6. Cross-tenant — verificado end-to-end, sem achado

Cenário J (obrigatório) do E2E real prova: sessão do tenant A cria um recurso real; sessão do
tenant B (contexto de navegador totalmente isolado) nunca vê esse recurso via API nem via UI.
O tenant nunca é lido de header/body/query controlável pelo navegador — só da sessão real do
servidor. Ver `docs/evidence/EVIDENCIA_ETAPA2_WEB_FOUNDATION_AUTH_SHELL_20260925.md`.

### 7. Vazamento do harness de teste para produção — sem achado

`backend/tests_support/` só é importado por `backend/tests/` e pelo comando explícito
`python3 -m tests_support.e2e_server` (nunca por `api/` ou `campaia_core/`) — garantido por
teste estático (`test_architecture_boundaries.py`, 2/2 `OK`). O harness exige
`CAMPAIA_E2E_ALLOWED_ORIGIN` explícito (falha ao subir sem ele) e roda `create_app(env="test")`
— nunca `env="production"`.

### 8. Dependências (supply chain) — verificação superficial, não exaustiva

`uvicorn==0.38.0` adicionado a `backend/requirements.txt`, pinado por versão exata (mesmo
padrão das dependências já existentes). Nenhuma dependência nova adicionada a
`web/package.json` nesta Etapa 2 (todas as bibliotecas usadas — Playwright, Vitest,
Testing Library — já existiam do WP-01). `npm audit` executado nesta sessão em `web/`:
`found 0 vulnerabilities`. Não é uma auditoria de licenças nem de supply chain mais profunda
(ex.: assinatura de pacotes, SBOM) — fora do escopo desta revisão pontual.

### 9. Secrets — varredura por padrão em todo o diff novo/modificado desta sessão

Varredura por padrão (chaves AWS, blocos `PRIVATE KEY`, `api_key=`, `secret=`, `password=`,
`Bearer <token longo>`) em todos os arquivos novos/modificados: **nenhuma ocorrência**.

## Conclusão

Um achado de severidade média corrigido nesta própria sessão (open redirect), um residual de
baixa severidade aceito e documentado (tokens de teste inertes no bundle de produção), e um
item não verificado (`npm audit`) registrado como tal. Nenhum achado crítico ou de alta
severidade. Isto não é uma certificação de segurança do produto — é o resultado desta
revisão pontual, neste escopo, nesta data.
