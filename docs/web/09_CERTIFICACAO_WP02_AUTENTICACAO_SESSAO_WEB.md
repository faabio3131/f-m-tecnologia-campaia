# CampaIA — Ponto Zero Web · 09. Certificação do WP-02 (Autenticação e sessão Web real)

**Estado máximo declarado neste documento:** `WP-02 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE SEGURANÇA HUMANA (FM SECURITY ENGINEER) PENDENTE`

Este documento certifica a execução real do WP-02
(`docs/web/06_ROADMAP_WORK_PACKAGES.md`), autorizada por "PROMPT MESTRE — CAMPAIA SaaS V1
COMPLETO" (20/09/2026), sobre a branch `feat/campaia-v1-complete-saas` (PR #6), criada a
partir do HEAD corrigido da PR #5 (`d2ac3a5b0cf7a5c102103550eb5331362706b6ce`).

O roadmap original exige, para o Gate 3 (Autenticação), autorização de **FM Security
Engineer + Diretor**. Esta execução tem autorização explícita do Diretor para
**implementar** o Work Package; **não inclui nem simula uma revisão de segurança
humana por um FM Security Engineer real** — essa revisão permanece uma pendência
genuína, registrada aqui e no roadmap, nunca presumida como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| Cliente OIDC provider-neutral (PKCE, state, nonce, verificação de ID token) | `backend/api/oidc.py` |
| Provedor de identidade de teste (fail-closed) | `backend/api/test_idp.py` |
| Sessão real, pending logins, gate fail-closed dos fixtures pré-WP-02 | `backend/api/state.py` |
| `require_auth`: sessão real primeiro, fixture Bearer como fallback | `backend/api/deps.py` |
| Rotas `/auth/login`, `/auth/callback`, `/auth/logout` | `backend/api/routes_auth.py` |
| Middleware CSRF (double-submit cookie) | `backend/api/csrf.py` |
| Wiring das rotas/middleware/test IdP condicional | `backend/api/main.py` |
| Dependências novas | `backend/requirements.txt` (`PyJWT`, `cryptography`, `python-multipart`) |
| Contrato: 3 rotas novas + `cookieAuth` | `contracts/bff-openapi.yaml` |
| Web: leitura de sessão server-side, logout client-side, página de conta | `web/src/lib/session.ts`, `web/src/components/LogoutButton.tsx`, `web/src/app/account/` |
| Fronteira de segurança do frontend atualizada (allowlist de 2 arquivos) | `web/scripts/lib/security-boundaries.mjs` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `mobile/` foi alterado
(confirmado por `git diff --stat`, ver §10). `permissions.py` especificamente **intocado**
— o requisito explícito do roadmap ("alimentando `Principal` sem alterar esse módulo").

## 2. Decisão arquitetural: provedor de teste real, não um mock

ADR-0018 aprova a **estratégia** (OIDC + sessão server-side), não um vendor — nenhum
provedor comercial está aprovado (`docs/16_ADR_0018...md` §Pendências, inalterada por esta
execução). Em vez de simular a resposta do provedor com dados fixos, esta execução
implementa um **provedor OIDC real, mínimo, spec-compliant** (discovery document,
authorization endpoint com picker HTML real, token endpoint com troca PKCE real, JWKS real)
— para que `api/oidc.py` e `api/routes_auth.py` sejam exercitados exatamente como seriam
contra um provedor comercial, sem nenhuma mudança de código quando um for escolhido
(`CAMPAIA_OIDC_ISSUER`/`CAMPAIA_OIDC_AUTHORIZATION_ENDPOINT`/`CAMPAIA_OIDC_TOKEN_ENDPOINT`/
`CAMPAIA_OIDC_JWKS_URI`/`CAMPAIA_OIDC_CLIENT_ID`/`CAMPAIA_OIDC_CLIENT_SECRET`/
`CAMPAIA_OIDC_REDIRECT_URI` — se todas presentes, usadas; senão, o provedor de teste,
fail-closed).

## 3. Fail-closed: o mesmo interruptor único para dois mecanismos

Antes desta execução, `AppState._seed_tokens()` era chamado **incondicionalmente** por
todo `create_app()`, incluindo o `app` de nível de módulo em `api/main.py` (o "ponto de
entrada de produção") — os tokens fixture (`demo-owner-token` etc.) estavam sempre
alcançáveis por quem soubesse a string, em qualquer ambiente. **Achado real, não
hipotético**, confirmado por leitura direta do código antes de alterá-lo.

Corrigido: dois sinais independentes devem concordar antes de qualquer credencial de teste
(fixture Bearer OU provedor de identidade de teste) existir — `enable_test_auth_fixtures=True`
passado explicitamente pelo chamador **e** `CAMPAIA_ENV` do processo declarado como
`test`/`local_dev`. Nenhum dos dois sozinho basta. Confirmado por teste automatizado
(`tests_api/test_auth_fail_closed.py`, `tests_api/test_auth_session.py::TestFailClosedEndToEnd`)
nos 4 casos: nenhum sinal, só a flag, só a env var, os dois juntos, e explicitamente que
`CAMPAIA_ENV=production`/`staging`/`""` recusam mesmo com a flag em `True`.

## 4. Prova do fluxo real (não simulado além do provedor)

Fluxo completo dirigido via `starlette.testclient.TestClient` contra a aplicação real
(roteamento real, middleware real, sem mock de `api/oidc.py`/`api/routes_auth.py`):
`GET /auth/login` → redirecionamento real ao `authorization_endpoint` → página HTML real de
escolha de identidade → `POST` real de escolha → `GET /auth/callback` com troca de código
real (PKCE) e busca real de JWKS (via `httpx.ASGITransport`, sem rede real necessária, mas
o mesmo caminho de código de uma chamada HTTPS real) → verificação real de assinatura RS256
contra o JWKS → sessão real criada → cookies `campaia_session` (`HttpOnly`/`Secure`/
`SameSite=Lax`) e `campaia_csrf` (não-`HttpOnly`) → `GET /me` retorna dados reais derivados
da sessão, não de fixture.

## 5. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api -t . -v
Ran 126 tests
OK
```

126 = 81 pré-existentes (inalterados) + 8 fail-closed (`test_auth_fail_closed.py`) + 18
unitários de OIDC (`test_oidc_unit.py`) + 19 de sessão HTTP completa
(`test_auth_session.py`). Nenhuma contagem reduzida — apenas crescimento.

| Suite | Cobre |
|---|---|
| `test_oidc_unit.py` (18) | PKCE geração/verificação/unicidade, state/nonce/session-id/csrf unicidade, ID token: aceito quando válido, rejeitado quando expirado/issuer errado/audience errada/nonce incompatível/claim de tenant ausente/roles vazias/assinatura adulterada/assinado por chave diferente |
| `test_auth_session.py` (19) | Login real reflete claims reais (6 identidades fixture); cookies `HttpOnly`+`Secure`; sessão ausente/desconhecida/adulterada/expirada/revogada — todas `401`; CSRF ausente/incorreto/correto; caminho Bearer fixture não afetado pelo CSRF; isolamento cross-tenant via sessão; replay de `state`; `state` desconhecido; replay de `code` de autorização; rotas `/test-idp/*` ausentes com fixtures desabilitadas; `/auth/login` → `503` sem provedor configurado |
| `test_auth_fail_closed.py` (8) | Os 2 sinais fail-closed, todas as combinações |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração — campaia_core intocado)

$ cd contracts && python3 validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run check
lint + typecheck + contracts:check + boundary:check + test (21/21) + build
todos verdes   (ver docs/web/08_CERTIFICACAO_WP01_FUNDACAO_WEB.md para o histórico do WP-01;
os 6 testes novos desta execução — logout-button.test.tsx, account-page.test.tsx — cobrem
o header CSRF correto no logout, ausência de fetch sem cookie CSRF, e os 3 estados da
página /account: não configurado, sem sessão, com sessão real)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e
6 passed (desktop+mobile × foundation.spec.ts, account.spec.ts)
```

## 6. Prova de ausência de secrets

- Nenhum token/segredo real no diff (verificado por grep dirigido excluindo os literais
  já documentados como não-credenciais: `dev-secret` em teste, e
  `test-idp-internal-secret-not-a-real-credential`, cujo próprio nome declara sua natureza —
  usado apenas para o provedor de teste confiar em si mesmo dentro do mesmo processo,
  nunca cruzando uma fronteira de confiança real).
- Fronteira do frontend atualizada, não removida: chamada de rede ao BFF agora permitida
  em exatamente 2 arquivos (`session.ts` — leitura de sessão server-side, nunca no bundle
  do cliente; `LogoutButton.tsx` — a única mutação client-side, protegida por CSRF). Todo
  o resto de `web/src` permanece em zero chamadas de rede, confirmado por
  `npm run boundary:check` (21 arquivos verificados, 0 violações).

## 7. Escopo do diff (confirmado por `git diff --stat`)

Modificados: `backend/api/{deps,main,state}.py`, `backend/requirements.txt`,
`backend/tests_api/{test_helpers,test_persistence}.py`, `contracts/bff-openapi.yaml`,
`web/scripts/{check-security-boundaries.mjs,lib/security-boundaries.mjs}`,
`web/src/contracts/bff-openapi.generated.ts` (regenerado, sem edição manual).

Novos: `backend/api/{csrf,oidc,routes_auth,test_idp}.py`,
`backend/tests_api/test_{auth_fail_closed,auth_session,oidc_unit}.py`,
`web/e2e/account.spec.ts`, `web/src/app/account/{page.tsx,page.module.css}`,
`web/src/components/LogoutButton.tsx`, `web/src/lib/session.ts`,
`web/tests/{account-page,logout-button}.test.tsx`.

`mobile/`, `backend/campaia_core/`, `backend/db/`: **intocados** (`git diff --stat` vazio
para os três).

## 8. Achado de ambiente documentado

`pip install -r backend/requirements.txt` falhou ao tentar desinstalar `PyJWT`/
`cryptography` pré-instalados pelo sistema (`RECORD file not found`, mesma classe de
problema já documentada para `PyYAML` em missões anteriores) — resolvido com
`pip install --ignore-installed`. O `PyJWT`/`cryptography` pré-instalados pelo sistema
estavam, além disso, genuinamente quebrados (`pyo3_runtime.PanicException` ao importar) —
não relacionado a esta mudança, apenas descoberto ao tentar usá-los.

## 9. Itens não verificados / pendências reais

- **Revisão de segurança humana (FM Security Engineer)** — não realizada nesta execução;
  pendência explícita do Gate 3.
- **Provedor de identidade comercial** — não escolhido; suporte via `CAMPAIA_OIDC_*` existe
  e não foi exercitado contra um provedor real (apenas contra o provedor de teste).
- **CORS explícito por ambiente** — não implementado nesta execução (item do roadmap não
  coberto).
- **Teste dedicado de step-up via sessão Web** — não escrito nesta execução; o mecanismo de
  step-up em si (`permissions.py`, `state.record_step_up`/`last_step_up`) é preexistente e
  já testado, mas nenhum teste novo exercita step-up especificamente através de uma sessão
  real de WP-02.
- **Rotação de sessão em atividade** — implementada apenas como reemissão no login (nova
  sessão a cada login bem-sucedido); nenhuma extensão silenciosa por atividade, decisão
  deliberada, não uma lacuna.
- **Cross-stack E2E real (Next.js + backend Python rodando juntos)** — não executado; o
  E2E do frontend roda isolado (sem `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` configurado),
  verificando a degradação honesta para "não configurado". A prova ponta a ponta do fluxo
  OIDC real foi feita inteiramente no lado do backend (`tests_api/test_auth_session.py`),
  não através do navegador real.

## 10. Confirmações negativas

- `permissions.py`: intocado.
- `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- WP-03 em diante: não iniciados.

## 11. Gate 3 — critérios

| Critério | Situação |
|---|---|
| Login real funciona | Sim |
| Rota protegida recusa acesso sem sessão válida | Sim |
| Cross-tenant confirma isolamento | Sim |
| CSRF automatizado | Sim |
| CORS automatizado | **Não implementado** |
| Step-up automatizado (via sessão Web) | **Não implementado** (mecanismo preexistente, teste novo ausente) |
| Isolamento cross-tenant automatizado | Sim |
| Fail-closed por construção | Sim, com teste ponta a ponta |
| `permissions.py` inalterado | Sim |
| Revisão de FM Security Engineer | **Pendente** |
| Autorização do Diretor | Sim (execução) |

Dado que a revisão de segurança humana e 2 dos testes automatizados explicitamente listados
no roadmap (CORS, step-up via sessão Web) não foram completados, o Gate 3 **não pode ser
declarado formalmente aprovado** por este documento. Veredito correto:
`WP-02 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE SEGURANÇA HUMANA E GATE 3 FORMAL PENDENTES`.
