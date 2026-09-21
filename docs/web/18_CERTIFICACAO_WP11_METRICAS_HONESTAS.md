# CampaIA — Ponto Zero Web · 18. Certificação do WP-11 (Métricas honestas da campanha)

**Estado máximo declarado neste documento:** `WP-11 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`

Este documento certifica a execução real do WP-11 — um bloco **não presente no roadmap
original**, definido nesta mesma missão por reconciliação de CURRENT (ver
`docs/web/06_ROADMAP_WORK_PACKAGES.md` §"WP-11 — Métricas honestas da campanha"), sob a
mesma autorização explícita do Diretor de construir mais 3 blocos ("pode sim construa mais 3
blocos") do WP-09 e WP-10. Sobre a branch `feat/campaia-v1-complete-saas` (PR #6).

**Com este bloco, a autorização de "mais 3 blocos" do Diretor está integralmente executada**
(WP-09, WP-10, WP-11).

Como todo bloco desde o WP-02, esta execução **não inclui nem simula uma revisão de QA
formal** — essa revisão permanece uma pendência genuína, registrada aqui, nunca presumida
como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| Contrato: campo `note` ausente, adicionado aditivamente | `contracts/bff-openapi.yaml` |
| Web: seção "Métricas" em `/campaigns/{id}` | `web/src/app/campaigns/[campaignId]/page.tsx`, `page.module.css` |
| Web: leitura server-side de insights | `web/src/lib/session.ts` (`getServerInsights`) |
| Web: novo tipo de contrato | `web/src/contracts/types.ts` (`InsightSeries`) |
| Backend: teste de jornada via sessão Web real (placeholder honesto com `note` real; `CAMPAIGN_VIEW` é ampla) | `backend/tests_api/test_insights_web_session.py` |
| E2E cross-stack real, novo spec dedicado | `web/e2e-crossstack/insights.spec.ts` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `backend/api/routes_campaigns.py`,
`backend/api/models.py`, `permissions.py`, `mobile/` foi alterado (confirmado por `git
status`). Nenhuma rota de backend nova foi criada — `GET /campaigns/{id}/insights` já
existia desde antes deste bloco, já testada por fixtures Bearer unitárias
(`test_insights_is_honest_placeholder`, `test_insights_validates_date_query_params`). Este
bloco construiu inteiramente a primeira tela que exibe essa resposta, sem alterar o domínio.

## 2. Achado real de contrato, corrigido durante a execução

A leitura direta de `InsightSeriesResponse` (`api/models.py`) contra o schema `InsightSeries`
(`contracts/bff-openapi.yaml`), feita antes de qualquer componente, confirmou o gap já
identificado na reconciliação de CURRENT deste bloco: o campo `note` está sempre presente na
resposta real (`routes_campaigns.py get_insights` sempre o preenche com uma frase honesta
explicando a ausência de camada de analytics), mas nunca foi declarado no schema. Corrigido
aditivamente; `npm run contracts:generate`/`contracts:check` confirmaram sincronia. Diferente
de todo bloco WP-08 a WP-10, a regressão completa deste bloco **não encontrou nenhum outro
achado real** — nem de contrato, nem de bug de UI pré-existente.

## 3. Achado real, confirmado por teste de backend via sessão Web real

`test_insights_web_session.py` (2 testes, via sessão Web real, não fixtures Bearer):

- Uma sessão real, após criar uma campanha pelo fluxo real do WP-05, vê o placeholder
  honesto vazio (`points: []`) com um `note` real e não vazio — confirma que o campo
  recém-corrigido no contrato realmente chega ao cliente, não apenas ao Pydantic model.
- `Permission.CAMPAIGN_VIEW` é genuinamente ampla: toda role declarada em
  `ROLE_PERMISSIONS` (`campaia_core/permissions.py`) a possui, confirmado por leitura direta
  antes de escrever o teste. Por isso este bloco, diferente de todo WP anterior, **não tem um
  teste de fronteira de permissão recusando um papel** — não existe identidade real capaz de
  exercitar essa recusa para este endpoint. O segundo teste prova isso positivamente: uma
  identidade `marketer` (que não é a `owner` que criou a campanha) também consegue ler os
  insights.

## 4. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api
Ran 178 tests
OK
```

178 = 176 pré-existentes (WP-01 a WP-10, inalterados) + 2 novos
(`tests_api/test_insights_web_session.py`).

| Suite | Cobre |
|---|---|
| `test_insights_web_session.py` (2) | Placeholder honesto com `note` real via sessão Web real; `CAMPAIGN_VIEW` é ampla (identidade `marketer`, não a criadora da campanha, também lê os insights) |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração -- campaia_core intocado)

$ python3 contracts/validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run lint && npm run typecheck && npm run contracts:check && npx vitest run && npm run build
todos verdes   (135/135 Vitest -- 3 novos desde o WP-10: nota real exibida quando `points`
está vazio, pontos reais exibidos quando não está, estado de erro quando a leitura falha --
soma exata: 135 - 132 pré-existentes = 3)

$ node web/scripts/check-security-boundaries.mjs
OK: nenhuma violação (64 arquivos verificados, allowlist inalterada em 12 arquivos -- a
seção "Métricas" é markup server-rendered dentro do Server Component já existente de
/campaigns/{id}, nenhum novo Client Component, nenhuma chamada de rede client-side nova)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npx playwright test -c playwright.crossstack.config.ts
13 passed (12 pré-existentes + 1 novo: submeter um brief real -> ver a nota honesta real na
seção "Métricas" de /campaigns/{id})
```

Sem novo spec de fumaça dedicado (`npm run test:e2e`, sem backend): a seção "Métricas" é
markup puro dentro da mesma página já coberta pelos specs de fumaça existentes do WP-05.

## 5. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida das certificações
  anteriores; nenhum literal novo introduzido).
- A seção "Métricas" não introduz nenhuma chamada de rede client-side: `getServerInsights` é
  server-only (`web/src/lib/session.ts`, sem `"use client"`), chamada dentro do mesmo Server
  Component de `/campaigns/{id}` que já busca campanha, plano e aprovações. Confirmado por
  `node scripts/check-security-boundaries.mjs` (64 arquivos verificados, 0 violações,
  allowlist inalterada em 12 arquivos).
- Nenhum dado de métrica é inventado, estimado ou calculado pela Web — a tela exibe
  exclusivamente o que `GET /campaigns/{id}/insights` devolve, campo a campo.

## 6. Escopo do diff (confirmado por `git status`)

Novos: `backend/tests_api/test_insights_web_session.py`, `web/e2e-crossstack/insights.spec.ts`,
este documento.

Modificados: `contracts/bff-openapi.yaml`, `web/src/contracts/{bff-openapi.generated.ts,
types.ts}`, `web/src/lib/session.ts`, `web/src/app/campaigns/[campaignId]/{page.tsx,
page.module.css}`, `web/tests/campaign-detail-page.test.tsx`,
`docs/web/06_ROADMAP_WORK_PACKAGES.md`.

`mobile/`, `backend/campaia_core/`, `backend/db/`, `backend/api/routes_campaigns.py`,
`backend/api/models.py`, `permissions.py`: **intocados**.

## 7. Itens não verificados / pendências reais

- **Revisão de FM QA Engineer** — não realizada nesta execução; pendência explícita, como em
  todo bloco desde o WP-02.
- **Camada de analytics real** — `campaia_core` não calcula nem armazena métricas de
  campanha; `points` permanece sempre vazio até essa camada existir (fora do escopo desta
  missão, achado pré-existente ao WP-11, confirmado no próprio código-fonte).
- **CI remoto do GitHub Actions** — não confirmado verde nesta execução; **FATO CONFIRMADO
  pelo Diretor**: cota gratuita de minutos esgotada. Não é regressão de código. Toda a
  evidência deste documento vem de execução local real.

## 8. Confirmações negativas

- `permissions.py`, `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma rota de backend nova criada (`GET /campaigns/{id}/insights` já existia).
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- Nenhum bloco além do WP-11 foi definido. Com este bloco, a autorização do Diretor de
  construir mais 3 blocos ("pode sim construa mais 3 blocos") está integralmente executada.

## 9. Critérios (Gate 5, extensão)

| Critério | Situação |
|---|---|
| Usuário visualiza a seção de métricas e vê a nota real da API quando vazia | Sim, testado via sessão Web real e E2E cross-stack |
| A tela nunca inventa um gráfico ou dado quando `points` está vazio | Sim, confirmado por leitura direta do componente |
| `permissions.py` inalterado | Sim |
| Nenhuma rota de backend nova | Sim (confirmado por `git status`) |
| Fronteira de rede do frontend inalterada (nenhuma chamada client-side nova) | Sim |
| Achado real de contrato corrigido | Sim (§2) |
| Revisão de FM QA Engineer | **Pendente** |
| Autorização do Diretor | Sim ("pode sim construa mais 3 blocos", 21/09/2026, mesma do WP-09/10) |

Veredito correto: `WP-11 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`.
