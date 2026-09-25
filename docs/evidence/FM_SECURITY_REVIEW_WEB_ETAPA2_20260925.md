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

---

## Revisão adicional — WP-03 (troca real de tenant/unidade, 25/09/2026)

**Escopo:** `backend/api/identity_directory.py` (`resolve_all`), `backend/api/session.py`
(`SessionRecord.available_principals`, `SessionStore.switch_principal`),
`backend/api/deps.py` (`require_session_record`), `backend/api/routes_auth.py`
(`list_memberships`, `switch_membership`), `backend/api/models.py`, `backend/api/main.py`
(novas rotas `GET /me/memberships`, `POST /auth/session/switch`),
`web/src/providers/AuthProvider.tsx` (`switchMembership`),
`web/src/components/TenantSwitcher.tsx`.

### Verificado, sem achado

1. **Escalada via troca**: `switch_membership` só aceita um `user_id` presente em
   `record.available_principals` — capturado no login, exclusivamente da mesma
   identidade (`identity_directory.resolve_all(email)`). Não há caminho para trocar para
   um vínculo de outra identidade. Confirmado por teste real
   (`test_switch_to_a_membership_not_owned_by_this_identity_is_rejected_fail_closed`).
2. **CSRF**: a troca passa por `require_session_record` → mesma checagem de CSRF de
   qualquer mutação via sessão (`_MUTATING_METHODS`). Confirmado por teste
   (`test_switch_without_csrf_token_is_rejected`).
3. **Invalidação de `step_up_at`**: a chave é `(tenant_id, user_id)` — uma troca real de
   vínculo sempre muda pelo menos `tenant_id` (nos fixtures atuais, muda os dois), então a
   chave nunca é reaproveitada. Confirmado por teste real fazendo uma operação
   `REQUIRES_STEP_UP` antes e depois da troca
   (`test_switching_tenant_requires_fresh_step_up_for_sensitive_operations`).
4. **Isolamento cross-tenant dentro da mesma sessão após a troca**: `authorize()`
   continua recebendo `Resource(tenant_id=fixture.tenant_id, ...)` onde `fixture` vem do
   `principal` ATIVO (atualizado pela troca) — nenhuma mudança na lógica de autorização
   em si. Confirmado por teste real criando um recurso antes da troca e listando depois
   (`test_switching_tenant_never_leaks_a_resource_from_the_previous_tenant`).
5. **`GET /me/memberships` não expõe vínculos de outras identidades**: só lê
   `record.available_principals`, capturado exclusivamente da identidade que fez login
   nesta sessão.
6. **Fixture de bearer token (dev) não ganhou nenhum poder novo**: `require_session_record`
   devolve `None`/recusa (401) quando a autenticação foi via bearer fixture — nenhum
   `SessionRecord` sintético é fabricado para esse caminho. Confirmado por teste
   (`test_switch_via_dev_bearer_fixture_is_rejected`,
   `test_memberships_requires_a_real_session_never_the_dev_bearer_fixture`).

### Achado corrigido nesta sessão

**Severidade: baixa/média (rastreabilidade, não uma falha de controle de acesso).**
A troca de vínculo ativo mudava o contexto de autorização de uma sessão sem deixar
nenhum rastro no audit log (`state.audit`), diferente de outras operações sensíveis do
mesmo produto (OAuth start, mudança de autonomia, etc., todas auditadas). Corrigido:
`switch_membership` agora grava `SESSION_SWITCH` (sucesso, com `from_tenant_id`/
`to_tenant_id` em `details`) e `SESSION_SWITCH_REJECTED` (tentativa rejeitada, com o
`user_id` alvo) — confirmado por 2 testes reais lendo `GET /audit-events` depois da
chamada.

### Achado residual, não corrigido (proporcional ao risco atual)

**Severidade: baixa, teórica com os dados de hoje.** A invalidação de `step_up_at`
depende de `tenant_id` mudar entre vínculos. Se um dia existir um vínculo com o MESMO
`tenant_id` E o MESMO `user_id`, mas `business_unit_id` diferente (não existe hoje em
`seed_dev_identity_directory()`, e nada no domínio sugere essa forma), a troca entre esses
dois vínculos NÃO forçaria nova reautenticação para operações `REQUIRES_STEP_UP` — a
chave de `step_up_at` é só `(tenant_id, user_id)`, sem `business_unit_id`. Não é
explorável com o modelo de dados atual (cada vínculo sempre tem `user_id` próprio,
diferente por vínculo); registrado para não ser esquecido caso o modelo de multi-unidade
por vínculo mude no futuro.

### Não verificado nesta revisão

- Comportamento sob concorrência real (duas trocas simultâneas na mesma sessão) — o
  `InMemorySessionStore` não usa lock explícito; dado que é um único dicionário Python e
  cada operação é uma escrita atômica de referência (GIL), a pior consequência de uma
  corrida é "a troca que terminar por último vence", nunca um estado corrompido — não
  testado explicitamente, proporcional ao estágio (mesma disciplina já aceita para outros
  stores em memória deste projeto).
