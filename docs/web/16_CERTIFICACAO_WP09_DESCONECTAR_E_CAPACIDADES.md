# CampaIA — Ponto Zero Web · 16. Certificação do WP-09 (Desconectar conta e ver capacidades)

**Estado máximo declarado neste documento:** `WP-09 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`

Este documento certifica a execução real do WP-09 — um bloco **não presente no roadmap
original**, definido nesta mesma missão por reconciliação de CURRENT (ver
`docs/web/06_ROADMAP_WORK_PACKAGES.md` §"WP-09 — Desconectar conta e ver capacidades da
conexão"), sob autorização explícita do Diretor para construir mais 3 blocos ("pode sim
construa mais 3 blocos"), reafirmando a autorização contínua de construção durante o
bloqueio de cota do CI do GitHub Actions. Sobre a branch `feat/campaia-v1-complete-saas`
(PR #6).

Como todo bloco desde o WP-02, esta execução **não inclui nem simula uma revisão de QA
formal** — essa revisão permanece uma pendência genuína, registrada aqui, nunca presumida
como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| Contrato: 3 campos reais ausentes, adicionados aditivamente | `contracts/bff-openapi.yaml` |
| Web: `ConnectAccountCard.tsx` estendido (desconectar + exibir capacidades) | `web/src/components/ConnectAccountCard.tsx` |
| Web: leitura server-side de capacidades | `web/src/lib/session.ts` (`getServerConnectionCapabilities`) |
| Web: onboarding busca capacidades para cada conexão ativa | `web/src/app/onboarding/page.tsx` |
| Backend: teste de jornada via sessão Web real (conectar→capacidades→desconectar; permissão negada) | `backend/tests_api/test_connection_lifecycle_web_session.py` |
| E2E cross-stack real, estendendo o spec já existente do WP-04 | `web/e2e-crossstack/onboarding.spec.ts` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `backend/api/routes_connections.py`,
`backend/api/models.py`, `permissions.py`, `mobile/` foi alterado (confirmado por `git
status`). Nenhuma rota de backend nova foi criada — `DELETE /connections/{id}` e `GET
/connections/{id}/capabilities` já existiam desde antes do WP-04; este bloco construiu
inteiramente a camada Web sobre elas, completando o ciclo de vida da conexão que o WP-04
havia começado (conectar, listar) mas não terminado (desconectar, capacidades).

## 2. Achado real de contrato, corrigido durante a execução

Ao projetar o texto exibido pelas capacidades (antes de escrever qualquer chamada de rede),
a leitura direta de `contracts/bff-openapi.yaml`'s `Capability` revelou que o schema não
declarava `provider`, `country` nem `api_version`, apesar de `CapabilityResponse`
(`api/models.py`) sempre devolvê-los — mesma classe dos achados reais anteriores (campo
real, sempre presente, nunca documentado). Corrigido aditivamente; `npm run
contracts:generate`/`contracts:check` confirmaram sincronia após a correção.

## 3. Decisão de design tomada durante a implementação (correção de rumo transparente)

A definição de escopo original deste bloco (commit de reconciliação de CURRENT, antes de
qualquer código) descrevia a consulta de capacidades como uma chamada `GET` client-side —
seria a primeira desta aplicação, já que `GET`/`HEAD`/`OPTIONS` estão fora do
`CSRFMiddleware` (`backend/api/csrf.py _SAFE_METHODS`) e portanto não precisariam do header
`X-CSRF-Token`. Ao começar a implementação, essa decisão foi revisitada: toda leitura (GET)
nesta aplicação, sem exceção desde o WP-02, passa por `web/src/lib/session.ts`,
server-side — nunca pelo cliente. Introduzir a primeira chamada GET client-side seria abrir
uma segunda forma do cliente falar com o BFF sem necessidade real (as capacidades de uma
conexão são conhecidas assim que a lista de conexões é conhecida, no servidor). Corrigido
antes de qualquer commit: `getServerConnectionCapabilities` foi adicionada a `session.ts`,
e `onboarding/page.tsx` busca as capacidades de cada conexão ativa em paralelo
(`Promise.all`), passando o resultado como prop para `ConnectAccountCard.tsx`. O boundary de
rede desta aplicação (fronteiras de segurança, `web/scripts/lib/security-boundaries.mjs`)
permanece exatamente como estava — nenhum arquivo novo precisou entrar na allowlist de
chamadas de rede client-side, porque não há nenhuma chamada de rede GET no cliente.

## 4. Achado real de teste E2E, encontrado ao escrever o cross-stack

O spec de E2E deste bloco estende o arquivo já existente do WP-04
(`e2e-crossstack/onboarding.spec.ts`), que roda todos os seus testes sequencialmente contra
um único processo de backend real compartilhado (`playwright.crossstack.config.ts`,
`workers: 1`) — um teste anterior no mesmo arquivo conecta `GOOGLE_ADS` e nunca desconecta.
A primeira versão deste spec usava `GOOGLE_ADS` também, e falhou por timeout esperando o
botão "Conectar (simulado)", que nunca aparece porque a conta já estava conectada, herdada
do teste anterior. Investigado e corrigido usando o provider `META` em vez de `GOOGLE_ADS`
(que permanece genuinamente desconectado até este teste) — mesma causa raiz já documentada
nesta missão como P-34 (fullyParallel: false só serializa DENTRO de um arquivo; o estado do
backend real ainda é compartilhado entre todos os testes desse arquivo).

## 5. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api
Ran 173 tests
OK
```

173 = 171 pré-existentes (WP-01 a WP-08, inalterados) + 2 novos
(`tests_api/test_connection_lifecycle_web_session.py`).

| Suite | Cobre |
|---|---|
| `test_connection_lifecycle_web_session.py` (2) | Conectar → consultar capacidades reais (provider/country/api_version sempre presentes) → desconectar (204, CSRF + step-up + idempotency-key) → `GET /connections` confirma `status: REVOKED`, tudo via sessão Web real; identidade sem `CONNECTION_MANAGE` (marketer) recusada com `403 PERMISSION_DENIED` |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração -- campaia_core intocado)

$ cd contracts && python3 validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run lint && npm run typecheck && npm run contracts:check && npm run test && npm run build
todos verdes   (125/125 Vitest -- 5 novos desde o WP-08: ConnectAccountCard (4) + 1 novo em
onboarding-page.test.tsx -- soma exata: 125 - 120 pré-existentes = 5)

$ node web/scripts/check-security-boundaries.mjs
OK: nenhuma violação (62 arquivos verificados, allowlist inalterada em 12 arquivos --
ConnectAccountCard.tsx já estava presente desde o WP-04, nenhum arquivo novo precisou
entrar, ver §3)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e:crossstack
11 passed (10 pré-existentes + 1 novo: conectar → ver capacidades reais → desconectar →
volta a "Não conectado", estendendo o spec já existente do WP-04)
```

Sem novo spec de fumaça dedicado (`npm run test:e2e`, sem backend): `/onboarding` já é
coberto pelos specs existentes do WP-01/04 (nenhuma chamada BFF quando
`NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` está ausente).

## 6. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida das certificações
  anteriores; nenhum literal novo introduzido).
- Fronteira do frontend **inalterada** (§3): nenhuma chamada de rede GET client-side foi
  introduzida; a única chamada de rede nova (`DELETE /connections/{id}`) acontece dentro de
  `ConnectAccountCard.tsx`, já presente na allowlist desde o WP-04, protegida por CSRF.
  Confirmado por `node scripts/check-security-boundaries.mjs` (62 arquivos verificados, 0
  violações).
- O header `X-Step-Up-Token` enviado por `ConnectAccountCard.tsx` ao desconectar carrega um
  marcador literal novo (`web-ui-disconnect-account-button-clicked`), distinto do usado para
  conectar, mesmo padrão honesto estabelecido pelos WP-04 a WP-08.

## 7. Escopo do diff (confirmado por `git status`)

Modificados: `contracts/bff-openapi.yaml`, `web/src/contracts/{bff-openapi.generated.ts,
types.ts}`, `web/src/lib/session.ts`, `web/src/app/onboarding/page.tsx`,
`web/src/components/ConnectAccountCard.{tsx,module.css}`,
`web/e2e-crossstack/onboarding.spec.ts`, `web/tests/{connect-account-card,
onboarding-page}.test.tsx`.

Novos: `backend/tests_api/test_connection_lifecycle_web_session.py`.

`mobile/`, `backend/campaia_core/`, `backend/db/`, `backend/api/routes_connections.py`,
`backend/api/models.py`, `permissions.py`: **intocados**.

## 8. Itens não verificados / pendências reais

- **Revisão de FM QA Engineer** — não realizada nesta execução; pendência explícita, como
  em todo bloco desde o WP-02.
- **`evidence_url`** — `CapabilityResponse.evidence_url` permanece sempre `None`
  (achado 7, pré-existente ao WP-09: "No evidence-URL source exists yet in
  campaia_core.infra.Capability"); a Web não inventa um valor, exibe o que a API
  devolve.
- **CI remoto do GitHub Actions** — não confirmado verde nesta execução; **FATO CONFIRMADO
  pelo Diretor**: cota gratuita de minutos esgotada. Não é regressão de código. Toda a
  evidência deste documento vem de execução local real.

## 9. Confirmações negativas

- `permissions.py`, `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma rota de backend nova criada (`DELETE /connections/{id}` e `GET
  /connections/{id}/capabilities` já existiam).
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- Nenhum bloco além do WP-11 foi definido (WP-10 e WP-11 seguem em execução sob a mesma
  autorização de "mais 3 blocos").

## 10. Critérios (Gate 5, extensão)

| Critério | Situação |
|---|---|
| Desconectar uma conta funciona ponta a ponta, com o estado real refletido | Sim, testado via sessão Web real e E2E cross-stack |
| Consultar capacidades reais funciona ponta a ponta, nunca inventado | Sim, testado |
| `permissions.py` inalterado | Sim |
| Nenhuma rota de backend nova | Sim (confirmado por `git status`) |
| Fronteira de rede do frontend inalterada (nenhuma chamada GET client-side introduzida) | Sim |
| Revisão de FM QA Engineer | **Pendente** |
| Autorização do Diretor | Sim ("pode sim construa mais 3 blocos", 21/09/2026) |

Veredito correto: `WP-09 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`.
