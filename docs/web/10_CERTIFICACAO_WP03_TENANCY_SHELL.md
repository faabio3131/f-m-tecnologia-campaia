# CampaIA — Ponto Zero Web · 10. Certificação do WP-03 (Contexto de tenant/unidade e shell do dashboard)

**Estado máximo declarado neste documento:** `WP-03 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE SEGURANÇA HUMANA (FM SECURITY ENGINEER) PENDENTE`

Este documento certifica a execução real do WP-03
(`docs/web/06_ROADMAP_WORK_PACKAGES.md`), autorizada pela continuação de "PROMPT MESTRE —
CAMPAIA SaaS V1 COMPLETO" (20–21/09/2026), sobre a branch `feat/campaia-v1-complete-saas`
(PR #6), a partir do HEAD `474f0975b3987b973effce17810192a1d41ab2b8` (certificação do WP-02).

O roadmap original exige, para o Gate 4 (Tenancy), aprovação de **FM Security Engineer** no
teste de isolamento. Esta execução tem autorização explícita do Diretor para **implementar**
o Work Package; **não inclui nem simula uma revisão de segurança humana por um FM Security
Engineer real** — essa revisão permanece a mesma pendência genuína já registrada no WP-02,
registrada aqui novamente, nunca presumida como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| Claim opcional `campaia_memberships`, `Membership`, parsing/validação | `backend/api/oidc.py` |
| Identidade de teste multi-tenant (`multi_tenant_owner`) | `backend/api/test_idp.py` |
| `SessionRecord.memberships`, `TokenPrincipal.with_membership`, `AppState.switch_tenant` | `backend/api/state.py`, `backend/api/oidc.py` |
| `require_web_session` (sessão real, nunca o fixture Bearer) | `backend/api/deps.py` |
| Rotas `GET /session/memberships`, `POST /session/switch-tenant` | `backend/api/routes_session.py` |
| Wiring das rotas + CORS condicional | `backend/api/main.py` |
| Redirect pós-login/logout ciente de origem cross-origin | `backend/api/routes_auth.py` |
| Modelos de resposta novos | `backend/api/models.py` |
| Dependência nova (harness de E2E cross-stack, não do produto) | `backend/requirements.txt` (`uvicorn`) |
| Contrato: 2 rotas + 3 schemas + resposta `PermissionDenied`, aditivos | `contracts/bff-openapi.yaml` |
| Web: memberships server-side, seletor de tenant, shell `/dashboard`, estados padronizados | `web/src/lib/session.ts`, `web/src/components/TenantSwitcher.tsx`, `web/src/components/{Loading,Error,Empty}State.tsx`, `web/src/app/dashboard/` |
| Fronteira de segurança do frontend atualizada (allowlist de 3 arquivos) | `web/scripts/lib/security-boundaries.mjs` |
| E2E de fumaça sem backend (padrão WP-01/02) | `web/e2e/dashboard.spec.ts` |
| E2E cross-stack real (backend + frontend reais, WP-03) | `web/playwright.crossstack.config.ts`, `web/e2e-crossstack/tenant-switch.spec.ts` |
| CI: job dedicado ao E2E cross-stack | `.github/workflows/frontend-tests.yml` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `mobile/` foi alterado
(confirmado por `git status`/leitura direta, ver §9). `permissions.py` especificamente
**intocado** — confirmado por leitura direta antes de implementar: `Principal.
business_unit_ids: frozenset[str] | None` já suportava múltiplas unidades nativamente, então
"troca de unidade" não exigia nenhuma mudança de domínio; só "troca de tenant" (`Principal.
tenant_id` é singular) exigia um mecanismo novo, inteiramente na camada de sessão
(`api/oidc.py`, `api/state.py`), nunca no domínio.

## 2. Decisão de design: por que uma claim opcional, não um novo formato de token

`VerifiedIdToken.memberships` é sempre um `tuple[Membership, ...]` não vazio, cujo primeiro
elemento é sempre o membership ativo (derivado das claims já obrigatórias
`campaia_tenant_id`/`campaia_roles`/`campaia_business_unit_id`). Quando a claim
`campaia_memberships` está ausente do ID token, `_parse_memberships` retorna esse
único-elemento — **toda identidade de teste pré-WP-03, e qualquer provedor real que nunca
venha a emitir essa claim, continua funcionando sem nenhuma mudança**, com um tenant
inalcançável a trocar. Quando presente, o membership ativo precisa aparecer na lista — um
token que reivindica memberships que não incluem o tenant no qual acabou de autenticar é
rejeitado (`IdTokenVerificationError`), não silenciosamente confiado. `multi_tenant_owner`
(`backend/api/test_idp.py`) é a única identidade de teste que emite a claim: OWNER em
`demo-tenant` (ativo no login), VIEWER em `other-tenant`.

## 3. `POST /session/switch-tenant`: nunca confia no cliente, sempre reemite a sessão

`tenant_id` no corpo da requisição é o único lugar em todo o backend onde um valor
literalmente chamado `tenant_id` é aceito do cliente — deliberado, e ainda assim nunca
confiado às cegas: `AppState.switch_tenant` só o honra quando corresponde a um dos
memberships **já registrados no servidor** para a sessão atual (`record.memberships`,
populado no login a partir do ID token verificado, nunca do próprio request de troca).
Um `tenant_id` que não é um membership real recebe `403 PERMISSION_DENIED` e a sessão
atual permanece completamente intacta — testado (`test_switch_to_a_tenant_not_in_
memberships_is_denied`).

Sucesso reemite a sessão por completo — novo `session_id`, novo `csrf_token`, nova
expiração (mesma disciplina de rotação do login do WP-02, nunca uma extensão silenciosa) —
e invalida `step_up_at` para o usuário em **todos** os tenants, não só o que está sendo
deixado: trocar de tenant é, em si, uma mudança de autoridade sensível, então step-up
recente não atravessa a troca mesmo que o usuário volte ao tenant original em seguida
(`test_switch_invalidates_step_up_across_all_tenants`, verificado diretamente contra
`AppState`, o mesmo caminho de código real que a rota chama).

## 4. Achado real, fora do escopo original do WP-03, corrigido nesta execução

A suíte cross-stack (`web/playwright.crossstack.config.ts`) sobe um backend real
(`uvicorn`) **e** um frontend real (`next dev`), em duas origens genuinamente distintas de
`127.0.0.1` sobre HTTPS — a mesma topologia que `web/README.md` já documentava desde o
WP-01 (`NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN`, ex. `https://api.campaia.app`, distinto da origem
do próprio frontend). Ao rodar um login real através de um navegador real pela primeira
vez contra duas origens de fato diferentes, dois problemas reais no próprio mecanismo do
WP-02 (não algo novo introduzido pelo WP-03) ficaram evidentes — nenhum dos dois havia sido
exercitado antes, porque o único E2E do WP-02 (`e2e/account.spec.ts`) cobre apenas o estado
"não configurado" (sem `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN`), e todos os testes HTTP do WP-02
usam `TestClient` contra uma única origem simulada (`https://testserver`):

1. **Redirect pós-login/logout resolvia contra a origem errada.** `/auth/callback`/
   `/auth/logout` redirecionavam o navegador para um caminho relativo
   (`pending.redirect_after_login`, ou `"/"` no logout) — um navegador resolve um
   `Location` relativo contra a origem que **emitiu** o redirect, ou seja, o próprio
   backend, não o frontend. Em qualquer deploy onde as duas origens de fato diferem
   (a topologia documentada), isso aterrissa o usuário em uma URL do BFF sem rota — 404
   real, reproduzido e confirmado antes de corrigir.
2. **Nenhum CORS existia.** `LogoutButton`/`TenantSwitcher` usam `credentials: "include"`
   com headers customizados (`x-csrf-token`, `content-type`) — o navegador recusa essas
   chamadas de saída (bloqueadas no preflight `OPTIONS`) contra qualquer origem que não
   seja a própria, sem headers CORS explícitos do servidor. Esta é exatamente a pendência
   já registrada, por nome, na certificação do WP-02 (`09_CERTIFICACAO_WP02...md` §9: "CORS
   explícito por ambiente — não implementado nesta execução").

Ambos corrigidos por uma única variável de ambiente nova do backend, opcional —
`CAMPAIA_WEB_ORIGIN` — que:

- faz `_frontend_url` (`backend/api/routes_auth.py`) redirecionar para a origem real do
  frontend em vez de um caminho relativo (o guard contra open-redirect do
  `redirect_after_login` fornecido pelo cliente continua idêntico e roda primeiro — a
  variável só controla PARA ONDE um caminho já validado como same-origin-relative é
  resolvido, nunca O QUE o cliente pode fornecer);
- habilita `CORSMiddleware` (`backend/api/main.py`, `_build_middleware`) permitindo
  **apenas** essa origem exata — nunca um curinga, já que `allow_credentials=True` (um
  curinga combinado com credenciais é recusado pelo próprio navegador, e seria errado aqui
  de qualquer forma: só a origem real do app deveria conseguir ler uma resposta
  autenticada por cookie).

Ausente (todo teste pré-existente do WP-01/02, e qualquer deploy de origem única — ex.
atrás do mesmo proxy reverso), o comportamento é **idêntico** ao anterior — confirmado por
9 testes novos dedicados (`backend/tests_api/test_cross_origin.py`) cobrindo os dois
estados (com/sem a variável) e a regressão completa (§6) permanecendo 100% verde.

## 5. Prova do fluxo real (E2E cross-stack, não simulado)

Diferente do WP-02 (cuja prova ponta a ponta ficou inteiramente do lado do backend, via
`TestClient`), o WP-03 prova o fluxo através de um **navegador real** (`web/e2e-
crossstack/tenant-switch.spec.ts`, Chromium via Playwright) contra um **backend real**
(`uvicorn`) e um **frontend real** (`next dev`), certificado HTTPS autoassinado gerado sob
demanda (nunca versionado): `GET /dashboard` → link real "Entrar" → `GET /auth/login` real
→ picker HTML real do provedor de teste → escolha real de `multi_tenant_owner` → `GET
/auth/callback` real, redirecionando de volta à origem real do FRONTEND (a correção do
§4) → `/dashboard` mostra os dois memberships reais, `demo-tenant` ativo → seleção real de
`other-tenant` no `<select>` → `POST /session/switch-tenant` real (CORS real, cookie CSRF
real) → cookie de sessão rotacionado no servidor → página recarregada mostra `other-tenant`/
VIEWER, sem nenhum resquício de `demo-tenant`/OWNER no painel de sessão ativa.

## 6. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api -t . -v
Ran 155 tests
OK
```

155 = 126 pré-existentes (WP-02, inalterados) + 12 de troca de tenant
(`test_tenant_switch.py`) + 8 de parsing do claim `campaia_memberships`
(`test_oidc_unit.py::TestMemberships`, agrupados com os 18 pré-existentes do arquivo,
total do arquivo agora 26) + 9 de CORS/redirect cross-origin (`test_cross_origin.py`).
Nenhuma contagem reduzida — apenas crescimento.

| Suite | Cobre |
|---|---|
| `test_tenant_switch.py` (12) | `GET /session/memberships`: 1 membership vs. 2, `is_active` correto, exige sessão real (nunca o fixture Bearer); `POST /session/switch-tenant`: sucesso muda tenant/papéis, rotaciona cookies, nega tenant fora dos memberships (sessão intacta), nega identidade de único tenant, exige CSRF, exige sessão, invalida step-up em todos os tenants, isolamento entre duas sessões concorrentes da mesma identidade |
| `test_oidc_unit.py::TestMemberships` (8) | Claim ausente → membership único; claim presente incluindo o ativo → aceito; claim sem o ativo → rejeitado; lista vazia/não-lista → rejeitado; entrada sem roles/tenant_id → rejeitado; entrada que não é objeto → rejeitado |
| `test_cross_origin.py` (9) | Redirect de callback/logout com e sem `CAMPAIA_WEB_ORIGIN`; guard contra open-redirect do cliente continua intacto com a variável setada; preflight CORS permite só a origem configurada; preflight de uma origem não configurada não é permitido; resposta real carrega `Access-Control-Allow-Credentials`; nenhum header CORS por padrão (variável ausente) |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração — campaia_core intocado)

$ cd contracts && python3 validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run check
lint + typecheck + contracts:check + boundary:check + test (36/36) + build
todos verdes   (15 novos desde o WP-02: LoadingState/ErrorState/EmptyState (5),
TenantSwitcher (5), DashboardPage (5) -- soma exata: 36 - 21 pré-existentes = 15)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e
8 passed (desktop+mobile × foundation.spec.ts, account.spec.ts, dashboard.spec.ts)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e:crossstack
3 passed (login real lista os 2 memberships; troca real muda tenant/papéis sem misturar;
troca real rotaciona o cookie de sessão no servidor)
```

## 7. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida do WP-02; nenhum literal
  novo introduzido além dos já documentados como não-credenciais).
- `web/e2e-crossstack/.certs/*.pem` (chave/certificado autoassinados, gerados sob demanda
  pela própria config do Playwright a cada execução local/CI) **nunca versionado** — já
  coberto pelo `*.pem` pré-existente em `web/.gitignore`, confirmado por `git status`
  não listar o diretório.
- Fronteira do frontend atualizada, não removida: chamada de rede ao BFF agora permitida
  em exatamente 3 arquivos (`session.ts`, `LogoutButton.tsx`, `TenantSwitcher.tsx` — o
  terceiro, novo nesta execução, também protegido por CSRF). Todo o resto de `web/src`
  permanece em zero chamadas de rede, confirmado por `npm run boundary:check` (32 arquivos
  verificados, 0 violações).

## 8. Achado de ambiente documentado: `next dev` + hidratação + Playwright

A suíte cross-stack usa `next dev` (não `next build && next start`) porque
`NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` precisa ser conhecido no momento em que o bundle do
cliente é produzido, e `next start` não expõe uma flag equivalente a
`--experimental-https` para servir com o certificado autoassinado gerado sob demanda. Isso
expôs dois problemas reais **do harness de teste em si** (não do produto), corrigidos
antes de confiar no resultado:

- `next dev` bloqueia por padrão recursos de HMR/dev de uma origem "cross-origin"
  (`127.0.0.1`, mesmo sendo a origem correta) — sem `allowedDevOrigins: ["127.0.0.1"]`
  (`web/next.config.ts`, sem efeito em `next build`/`next start`), a hidratação do lado do
  cliente nunca terminava de fato: `selectOption()` do Playwright "tinha sucesso" no nível
  do DOM nativo, mas o `onChange` do React nunca disparava (nenhuma requisição de rede
  seguia), porque o listener nunca havia sido anexado. Reproduzido e confirmado com logging
  direto antes de corrigir.
- O fetch server-side de `session.ts` (Node, não o navegador) recusava o certificado
  autoassinado do backend mesmo com `NODE_EXTRA_CA_CERTS` apontando para ele —
  confirmado reproduzindo a falha (`DEPTH_ZERO_SELF_SIGNED_CERT`) com a variável setada;
  o fetch interno do Turbopack dev server simplesmente não a honra nesta versão. Resolvido
  com `NODE_TLS_REJECT_UNAUTHORIZED=0`, escopado exclusivamente ao processo `next dev`
  deste harness (nunca ao build de produção, nunca a um deploy real, nunca commitado como
  padrão) — um certificado real nunca é autoassinado, então isso não enfraquece nenhuma
  verificação TLS que algum dia importaria de verdade.
- `next dev` também gera `AGENTS.md`/`CLAUDE.md` na raiz de `web/` por padrão (Next 16) —
  desabilitado via `agentRules: false` em `web/next.config.ts` antes de commitar (os
  arquivos gerados foram descartados, nunca versionados).

`pip install uvicorn` funcionou sem intercorrências (proxy do ambiente permite pypi.org
para este pacote, confirmado).

## 9. Escopo do diff (confirmado por `git status`)

Modificados: `backend/api/{deps,main,models,oidc,routes_auth,state,test_idp}.py`,
`backend/requirements.txt`, `backend/tests_api/test_oidc_unit.py`,
`contracts/bff-openapi.yaml`, `web/next.config.ts`, `web/package.json`,
`web/scripts/{check-security-boundaries.mjs,lib/security-boundaries.mjs}`,
`web/src/contracts/{bff-openapi.generated.ts,types.ts}`, `web/src/lib/session.ts`,
`web/tests/components.test.tsx`, `.github/workflows/frontend-tests.yml`.

Novos: `backend/api/routes_session.py`, `backend/tests_api/test_{cross_origin,
tenant_switch}.py`, `web/e2e/dashboard.spec.ts`, `web/e2e-crossstack/tenant-switch.spec.ts`,
`web/playwright.crossstack.config.ts`, `web/src/app/dashboard/`,
`web/src/components/{EmptyState,ErrorState,LoadingState,TenantSwitcher}.{tsx,module.css}`,
`web/tests/{dashboard-page,tenant-switcher}.test.tsx`.

`mobile/`, `backend/campaia_core/`, `backend/db/`: **intocados**.

## 10. Itens não verificados / pendências reais

- **Revisão de segurança humana (FM Security Engineer)** — não realizada nesta execução;
  a mesma pendência explícita do Gate 3 (WP-02), agora também do Gate 4.
- **Provedor de identidade comercial** — segue não escolhido; `campaia_memberships` é uma
  claim que este projeto define, nunca exercitada contra um provedor real que a emita de
  fato (apenas contra o provedor de teste).
- **Seletor de UNIDADE** (não de tenant) — não implementado: confirmado que o domínio já
  suporta múltiplas unidades por principal (`Principal.business_unit_ids`), mas nenhuma
  identidade de teste tem mais de uma unidade dentro do mesmo tenant, então não há UI para
  isso ainda exercitar de verdade. Item do roadmap ("seletor de tenant/unidade") parcial:
  tenant, sim; unidade, não.
- **`CAMPAIA_WEB_ORIGIN`/CORS**: corrigido nesta execução (§4), mas nunca exercitado contra
  um deploy real — apenas contra o harness local/CI cross-stack.

## 11. Confirmações negativas

- `permissions.py`: intocado.
- `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma credencial real usada ou necessária; `*.pem` do harness E2E nunca versionado.
- Nenhum merge, nenhum deploy.
- WP-04 em diante: não iniciados.

## 12. Gate 4 — critérios

| Critério | Situação |
|---|---|
| Tenant/unidade ativa resolvida exclusivamente da sessão | Sim (tenant); unidade não exercitada (§10) |
| Seletor de tenant aparece só com >1 membership real | Sim |
| Layout autenticado com estados vazio/erro/carregando padronizados | Sim (`LoadingState`/`ErrorState`/`EmptyState`) |
| Troca de tenant funciona e invalida `step_up_at` | Sim, testado explicitamente |
| Isolamento cross-tenant reforçado no nível de UI | Sim, inclusive via E2E cross-stack real |
| Nenhuma funcionalidade de negócio além de navegação | Sim (`/dashboard` é um placeholder rotulado) |
| E2E básico de troca de tenant | Sim — 3 testes cross-stack reais, não simulados |
| `permissions.py` inalterado | Sim |
| Revisão de FM Security Engineer | **Pendente** |
| Autorização do Diretor | Sim (execução, continuação do WP-02) |

Dado que a revisão de segurança humana não foi completada, o Gate 4 **não pode ser
declarado formalmente aprovado** por este documento. Veredito correto:
`WP-03 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE SEGURANÇA HUMANA E GATE 4 FORMAL PENDENTES`.
