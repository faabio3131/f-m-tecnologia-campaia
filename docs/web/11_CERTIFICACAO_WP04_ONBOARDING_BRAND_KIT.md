# CampaIA — Ponto Zero Web · 11. Certificação do WP-04 (Onboarding e Brand Kit)

**Estado máximo declarado neste documento:** `WP-04 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`

Este documento certifica a execução real do WP-04
(`docs/web/06_ROADMAP_WORK_PACKAGES.md`), autorizada pela continuação de "PROMPT MESTRE —
CAMPAIA SaaS V1 COMPLETO" (21/09/2026), sobre a branch `feat/campaia-v1-complete-saas`
(PR #6), a partir do HEAD `420590e64ad640aaa1a70012fd5caf921f4b383d` (certificação do WP-03).

O roadmap original exige, para o Gate 5 (Primeira jornada), aprovação de **FM QA Engineer**.
Esta execução tem autorização explícita do Diretor para **implementar** o Work Package;
**não inclui nem simula uma revisão de QA formal** — essa revisão permanece uma pendência
genuína, registrada aqui, nunca presumida como satisfeita. O Gate 5 também depende do WP-05
(briefing/estratégia/aprovação) para se fechar por completo — este documento certifica
apenas a parte do WP-04.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| `PendingOAuth`, `AppState.oauth_pending`, criação/consumo single-use | `backend/api/state.py` |
| Rota nova `POST /connections/oauth/complete`; `oauth_start` passa a rastrear o `state` server-side | `backend/api/routes_connections.py` |
| Modelo de request novo | `backend/api/models.py` |
| Wiring da rota | `backend/api/main.py` |
| Contrato: 1 rota nova, aditiva | `contracts/bff-openapi.yaml` |
| Web: leituras server-side de Brand Kits/conexões | `web/src/lib/session.ts` |
| Web: tipos novos do contrato | `web/src/contracts/types.ts` |
| Web: formulário de Brand Kit, cartões de conexão, página de onboarding | `web/src/components/{BrandKitForm,ConnectAccountCard}.tsx`, `web/src/app/onboarding/` |
| Fronteira de segurança do frontend atualizada (allowlist de 5 arquivos) | `web/scripts/lib/security-boundaries.mjs` |
| E2E de fumaça sem backend | `web/e2e/onboarding.spec.ts` |
| E2E cross-stack real (backend + frontend reais) | `web/e2e-crossstack/onboarding.spec.ts` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `mobile/` foi alterado (confirmado
por `git status`). `permissions.py` **intocado**.

## 2. Achado real, fora do escopo original, corrigido nesta execução

Antes de escrever qualquer linha de frontend, a leitura direta de `backend/api/
routes_connections.py` revelou que `oauth_start` **nunca cria uma `Connection`** — devolve
apenas uma URL de autorização falsa e um `state`. `ConnectionRepository.create()`
(`backend/api/repositories.py`) existe e é usado, mas **somente dentro de testes**
(`client.app.state.campaia.connections.create(...)`, confirmado por `grep` em todo o
`backend/` antes de assumir que o gap era real). Nenhuma rota HTTP jamais chamava esse
método.

Isso não é uma lacuna nova introduzida por este Work Package — é uma lacuna herdada do
WP-01/WP-02 que só se torna um bloqueio real quando o WP-04 exige, pela primeira vez, que um
canal fique de fato "conectado". Sem corrigi-la, o próprio critério de aceitação do
roadmap ("concluir onboarding habilitado assim que 1 canal conectado") seria estruturalmente
impossível de satisfazer honestamente — nenhuma chamada real jamais deixaria `GET
/connections` retornar algo diferente de uma lista vazia.

A descrição já existente no próprio contrato (`bff-openapi.yaml`, `/connections/oauth/
start`: "O callback e recebido pelo backend; o token nunca transita pelo aplicativo") já
declarava a intenção de uma segunda etapa server-side — nunca implementada. Fechado com uma
rota nova, aditiva: `POST /connections/oauth/complete`. Mecanismo:

- `oauth_start` agora registra a tentativa em `AppState.oauth_pending` (`PendingOAuth`:
  `tenant_id`, `provider`, `created_at`), TTL de 600s, mesmo padrão do `PendingLogin` do
  WP-02.
- `oauth_complete` consome o `state` exatamente uma vez (`AppState.pop_pending_oauth`),
  validando que pertence ao tenant autenticado — um `state` emitido pelo tenant A nunca
  completa para o tenant B, mesmo que de alguma forma vaze (testado).
- Como nenhum provider real existe, a "conta selecionada pelo usuário" é simulada: o
  frontend (`ConnectAccountCard.tsx`) encadeia `start` → `complete` na mesma interação de
  clique, rotulando tudo como "(simulado)" — nunca fingindo uma lista real de contas que não
  existe.

## 3. Achado real de design, encontrado e corrigido durante o próprio desenvolvimento

A primeira versão de `oauth_complete` consumia o `state` **fora** do bloco protegido por
`IdempotencyStore.execute()`. Um teste escrito para provar que um retry legítimo (mesma
`Idempotency-Key`, ex. resposta perdida na rede) não deveria falhar revelou que, na prática,
falhava — porque `pop_pending_oauth` já havia consumido o `state` na primeira tentativa,
antes mesmo de a camada de idempotência verificar se já existia um resultado em cache.
Corrigido movendo o consumo do `state` para **dentro** do fechamento (`_do_create`), que só é
chamado de fato quando a operação ainda não foi executada — replay genuíno nunca mais toca
`pop_pending_oauth`. Pego por teste antes de qualquer deploy, não em produção.

## 4. Decisão de escopo: o que o WP-04 explicitamente não constrói

`13_ESPECIFICACAO_TELAS_APP.md` §3 descreve cinco telas de onboarding: Criar Conta/Login
(§3.1, já resolvida pelo WP-02), Cadastro da Empresa (§3.2), Unidade de Negócio (§3.3),
Conectar Contas (§3.4) e Brand Kit (§4). O roadmap do WP-04 lista explicitamente apenas as
rotas que já existem (`POST/GET /brand-profiles`, `POST /connections/oauth/start`, `GET
/connections`) — nenhuma rota de criação de empresa/tenant ou de unidade de negócio jamais
existiu no backend (confirmado por `grep -rn "onboarding" backend/ contracts/` antes de
implementar: zero resultados). `tenant_id` vem sempre da sessão autenticada (WP-02/03), nunca
é criado via API. Construir §3.2/§3.3 fabricaria uma tela sem nenhuma chamada de rede real
por trás — exatamente o que este projeto nunca fez desde o WP-01. Confirmado como fora de
escopo, documentado no próprio código (`onboarding/page.tsx`) e aqui, não silenciosamente
omitido.

## 5. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api -t . -v
Ran 162 tests
OK
```

162 = 155 pré-existentes (WP-01/02/03, inalterados) + 7 novos
(`tests_api/test_oauth_complete.py`).

| Suite | Cobre |
|---|---|
| `test_oauth_complete.py` (7) | `complete` cria uma `Connection` real e ela aparece em `GET /connections`; `state` é single-use (segunda tentativa falha); `state` desconhecido é rejeitado; `state` iniciado por outro tenant é rejeitado (e consumido mesmo assim, não fica reutilizável); exige `X-Step-Up-Token`; exige `Idempotency-Key`; replay com a mesma `Idempotency-Key` não cria uma segunda conexão |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração -- campaia_core intocado)

$ cd contracts && python3 validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run check
lint + typecheck + contracts:check + boundary:check + test (53/53) + build
todos verdes   (17 novos desde o WP-03: BrandKitForm (6), ConnectAccountCard (6),
OnboardingPage (5) -- soma exata: 53 - 36 pré-existentes = 17)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e
10 passed (desktop+mobile × foundation.spec.ts, account.spec.ts, dashboard.spec.ts,
onboarding.spec.ts)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e:crossstack
6 passed (3 do WP-03 + 3 novos: nada conectado no início com "Concluir Onboarding"
desabilitado; conectar uma conta simulada habilita "Concluir Onboarding" sem marcar os
outros dois canais como conectados; Brand Kit salvo persiste após reload via API real)
```

## 6. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida das certificações
  anteriores; nenhum literal novo introduzido).
- Fronteira do frontend atualizada, não removida: chamada de rede ao BFF agora permitida em
  exatamente 5 arquivos (`session.ts`, `LogoutButton.tsx`, `TenantSwitcher.tsx`,
  `BrandKitForm.tsx`, `ConnectAccountCard.tsx` — os dois últimos, novos nesta execução,
  ambos protegidos por CSRF). Todo o resto de `web/src` permanece em zero chamadas de rede,
  confirmado por `npm run boundary:check` (39 arquivos verificados, 0 violações).
- O header `X-Step-Up-Token` enviado por `ConnectAccountCard.tsx` carrega um marcador
  literal (`web-ui-connect-account-button-clicked`), documentado no próprio código como não
  sendo uma prova real de MFA -- o mecanismo de step-up deste sandbox só verifica a
  presença de um valor não vazio (`backend/api/deps.py`, comportamento preexistente, não
  alterado aqui). Esta é a primeira vez que o frontend envia esse header; nenhuma UI de
  reautenticação real foi construída ou simulada como se fosse real.

## 7. Escopo do diff (confirmado por `git status`)

Modificados: `backend/api/{main,models,routes_connections,state}.py`,
`contracts/bff-openapi.yaml`, `web/scripts/{check-security-boundaries.mjs,
lib/security-boundaries.mjs}`, `web/src/contracts/{bff-openapi.generated.ts,types.ts}`,
`web/src/lib/session.ts`.

Novos: `backend/tests_api/test_oauth_complete.py`, `web/e2e/onboarding.spec.ts`,
`web/e2e-crossstack/onboarding.spec.ts`, `web/src/app/onboarding/`,
`web/src/components/{BrandKitForm,ConnectAccountCard}.{tsx,module.css}`,
`web/tests/{brand-kit-form,connect-account-card,onboarding-page}.test.tsx`.

`mobile/`, `backend/campaia_core/`, `backend/db/`: **intocados**.

## 8. Itens não verificados / pendências reais

- **Revisão de FM QA Engineer** — não realizada nesta execução; pendência explícita do
  Gate 5.
- **Cadastro de empresa/unidade de negócio** (§3.2/§3.3) — confirmado fora de escopo real
  (nenhum endpoint existe); permanece uma lacuna genuína do produto, não deste Work Package.
- **Upload de logo** (Brand Kit §4.1) — não implementado; nenhum endpoint de upload de
  arquivo existe no backend hoje.
- **Provider comercial real** (Google Ads/Meta/WhatsApp) — segue não escolhido/integrado;
  `POST /connections/oauth/complete` simula exatamente o passo que um callback real
  ocuparia, mas nunca foi exercitado contra um provider de verdade.

## 9. Confirmações negativas

- `permissions.py`: intocado.
- `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- WP-05 em diante: não iniciados.

## 10. Gate 5 (parcial) — critérios

| Critério | Situação |
|---|---|
| Onboarding completa e Brand Kit salvo | Sim, testado via E2E cross-stack real |
| Regra "concluir habilitado com ≥1 canal" | Sim, testado (positivo e negativo) |
| Conexão simulada real, não fictícia | Sim -- `GET /connections` reflete o estado real do servidor |
| `permissions.py` inalterado | Sim |
| Revisão de FM QA Engineer | **Pendente** |
| Briefing/estratégia/aprovação (WP-05) | **Não iniciado** -- Gate 5 só fecha por completo depois |
| Autorização do Diretor | Sim (execução, continuação do WP-03) |

Dado que a revisão de QA não foi completada e o WP-05 (parte restante do Gate 5) ainda não
começou, o Gate 5 **não pode ser declarado fechado** por este documento. Veredito correto:
`WP-04 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER E GATE 5 COMPLETO PENDENTES`.
