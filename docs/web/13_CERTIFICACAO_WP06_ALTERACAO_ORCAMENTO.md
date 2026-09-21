# CampaIA — Ponto Zero Web · 13. Certificação do WP-06 (Alteração de orçamento)

**Estado máximo declarado neste documento:** `WP-06 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`

Este documento certifica a execução real do WP-06 — um bloco **não presente no roadmap
original**, definido nesta mesma missão por reconciliação de CURRENT (ver
`docs/web/06_ROADMAP_WORK_PACKAGES.md` §"WP-06 — Alteração de orçamento"), autorizado pela
continuação de "PROMPT MESTRE — CAMPAIA SaaS V1 COMPLETO" (21/09/2026, decisão do Diretor
"pode avançar mais 3 blocos" — WP-06 é o 3º e último bloco desta autorização, depois de
WP-04 e WP-05), sobre a branch `feat/campaia-v1-complete-saas` (PR #6).

Como todo bloco desde o WP-02, esta execução **não inclui nem simula uma revisão de QA
formal** — essa revisão permanece uma pendência genuína, registrada aqui, nunca presumida
como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| Contrato: 3 campos/rota reais ausentes, adicionados aditivamente | `contracts/bff-openapi.yaml` |
| Web: componente de orçamento (propor, exibir status, aplicar) | `web/src/components/BudgetPanel.tsx` |
| Web: card de decisão ganha `data-testid` estável (confiabilidade de teste E2E) | `web/src/components/ApprovalDecisionCard.tsx` |
| Web: painel de orçamento integrado ao detalhe da campanha; correção de um bug real de filtragem de aprovação pendente | `web/src/app/campaigns/[campaignId]/page.tsx` |
| Fronteira de segurança do frontend atualizada (allowlist de 10 arquivos) | `web/scripts/lib/security-boundaries.mjs` |
| Backend: teste de jornada via sessão Web real (propor→aprovar→aplicar, dois usuários) | `backend/tests_api/test_budget_change_web_session.py` |
| E2E cross-stack real, dois usuários distintos | `web/e2e-crossstack/budget-change.spec.ts` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `backend/api/routes_campaigns.py`,
`backend/api/routes_approvals.py`, `backend/api/models.py`, `permissions.py`, `mobile/` foi
alterado (confirmado por `git status`). Nenhuma rota de backend nova foi criada — `PATCH
/campaigns/{id}/budget` e `POST /approvals` já existiam desde blocos anteriores; este bloco
construiu inteiramente a camada Web sobre eles, reutilizando por completo a fila de
aprovação (`/approvals`, `ApprovalDecisionCard.tsx`) já construída pelo WP-05.

## 2. Achados reais de contrato, corrigidos durante a execução

Ao projetar `BudgetPanel.tsx` (antes de escrever qualquer chamada de rede), a leitura direta
de `contracts/bff-openapi.yaml`'s `ApprovalRequest` revelou dois campos ausentes, apesar de
sempre presentes na resposta real (`api/helpers.py serialize_approval`):

- **`kind`** — já era descrito no próprio código-fonte do backend como "extra, not in the
  contract" (comentário em `api/models.py ApprovalResponse`, preexistente). Sem `kind`
  tipado, a Web não teria forma confiável de distinguir um pedido `BUDGET_CHANGE` de um
  `PUBLISH` na fila de aprovação — corresponder por texto de `reason` seria frágil e a
  camada errada para fazer essa distinção.
- **`amount`** — nunca fora sequer mencionado no contrato. Sem ele tipado, a Web não teria
  como aplicar de fato uma alteração já aprovada (`PATCH /campaigns/{id}/budget` exige o
  `daily_cap` exato) sem reconstruir o valor proposto de outra origem que não a própria
  resposta da API.

Adicionalmente, `POST /approvals` — já implementado desde antes do WP-05 e já usado
extensivamente por ele (`ValidationPanel.tsx`, `BudgetPanel.tsx` agora também) — nunca
estivera documentado no contrato (o próprio código já o descrevia como "Not in the
paraphrased contract's endpoint list, added as a minimal, clearly-labeled deviation").
Corrigido aditivamente junto aos dois campos acima, já que a mesma área do arquivo estava
sendo tocada.

Todas as três correções são aditivas: `npm run contracts:generate`/`contracts:check`
confirmaram sincronia após cada uma, sem quebrar nenhum consumidor existente.

## 3. Achado real de tipo, encontrado e corrigido durante o próprio desenvolvimento

Um teste de backend (`test_budget_change_web_session.py`, primeira verificação real do
valor de `daily_cap` retornado pela API, nunca comparado a um literal antes) revelou que
`Campaign.budget.daily_cap`/`total_amount`/`spent_to_date` — tipados `number` pelo
contrato — na verdade serializam como **string JSON** (`"500"`, não `500`). Isso nunca fora
detectado antes porque nenhum teste ou código anterior fazia comparação numérica sobre
esses campos (testes existentes só verificavam o conjunto de chaves do objeto `budget`, ver
`tests_api/test_smoke_endpoints.py:144`).

Isso quebrava `BudgetPanel.tsx`'s própria lógica de "esta aprovação já foi aplicada":
`Number(a.amount) !== budget?.daily_cap` compara um `number` a uma `string` em runtime,
sempre `true` por tipos diferentes, escondendo permanentemente o botão "Aplicar alteração"
mesmo após uma aplicação bem-sucedida. Corrigido coerindo os dois lados via `Number(...)`.
A divergência de tipo em si (contrato declara `number`, serialização real emite string para
todo campo `Decimal`) não foi corrigida — mudança de escopo maior (afetaria toda resposta
com campos `Decimal`, não só orçamento), registrada como pendência real, não escondida.

## 4. Achado real de correção, encontrado ao integrar `BudgetPanel` à tela existente

Adicionar `BudgetPanel` à mesma tela que já continha `ValidationPanel` (WP-05) expôs um bug
latente: `hasPendingApproval` (calculado em `page.tsx` e passado para `ValidationPanel`)
verificava **qualquer** aprovação `PENDING` da campanha, sem filtrar por `kind`. Antes do
WP-06, toda campanha só podia ter aprovações `PUBLISH`, então o bug nunca se manifestava. A
partir do WP-06, uma aprovação `BUDGET_CHANGE` pendente passaria a desabilitar incorretamente
o botão "Solicitar aprovação" de `ValidationPanel` (que é sobre publicação, não orçamento).
Corrigido filtrando explicitamente por `approval.kind === "PUBLISH"` antes de qualquer
`BudgetPanel` ser escrito, uma vez que o gap foi identificado durante a integração.

## 5. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api
Ran 166 tests
OK
```

166 = 164 pré-existentes (WP-01 a WP-05, inalterados) + 2 novos
(`tests_api/test_budget_change_web_session.py`).

| Suite | Cobre |
|---|---|
| `test_budget_change_web_session.py` (2) | Jornada completa propor→aprovar→aplicar via cookie de sessão real, dois `TestClient` distintos (owner propõe e aplica, approver decide) sobre o mesmo `AppState`; alteração além do limite percentual configurado (`max_change_pct`) é recusada com `422 BUDGET_LIMIT` no momento de aplicar, mesmo já tendo sido aprovada |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração -- campaia_core intocado)

$ cd contracts && python3 validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run lint && npm run typecheck && npm run contracts:check && npm run boundary:check && npm run test && npm run build
todos verdes   (99/99 Vitest -- 9 novos desde o WP-05: BudgetPanel (9) -- soma exata:
99 - 90 pré-existentes = 9)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e
14 passed (sem novo spec dedicado -- a rota /campaigns/[id] com BudgetPanel não é
exercitável sem backend real além do que e2e/campaigns.spec.ts já cobre: nenhuma chamada
BFF quando NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN está ausente)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e:crossstack
8 passed (7 dos WP-03/04/05 + 1 novo: propor uma alteração de orçamento -> um segundo
usuário real, em um BrowserContext separado, aprova na fila /approvals já existente ->
o proponente aplica a mudança de verdade -> o orçamento exibido reflete o novo valor)
```

## 6. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida das certificações
  anteriores; nenhum literal novo introduzido).
- Fronteira do frontend atualizada, não removida: chamada de rede ao BFF agora permitida em
  exatamente 10 arquivos (os 9 do WP-02 a WP-05 + `BudgetPanel.tsx`, protegido por CSRF).
  Todo o resto de `web/src` permanece em zero chamadas de rede, confirmado por
  `npm run boundary:check` (58 arquivos verificados, 0 violações).
- O header `X-Step-Up-Token` enviado por `BudgetPanel.tsx` carrega um marcador literal
  (`web-ui-apply-budget-change-button-clicked`), mesmo padrão honesto estabelecido pelo
  WP-04/WP-05 — nenhuma UI de reautenticação real simulada como se fosse real.

## 7. Escopo do diff (confirmado por `git status`)

Modificados: `contracts/bff-openapi.yaml`, `web/scripts/{check-security-boundaries.mjs,
lib/security-boundaries.mjs}`, `web/src/contracts/{bff-openapi.generated.ts,types.ts}`,
`web/src/app/campaigns/[campaignId]/page.tsx`, `web/src/components/ApprovalDecisionCard.tsx`.

Novos: `backend/tests_api/test_budget_change_web_session.py`,
`web/e2e-crossstack/budget-change.spec.ts`,
`web/src/components/BudgetPanel.{tsx,module.css}`, `web/tests/budget-panel.test.tsx`.

`mobile/`, `backend/campaia_core/`, `backend/db/`, `backend/api/routes_campaigns.py`,
`backend/api/routes_approvals.py`, `backend/api/models.py`, `permissions.py`:
**intocados**.

## 8. Itens não verificados / pendências reais

- **Revisão de FM QA Engineer** — não realizada nesta execução; pendência explícita, como
  em todo bloco desde o WP-02.
- **`total_amount` (orçamento total)** — confirmado fora de escopo deste bloco; a rota
  aceita alterar só `daily_cap`. O contrato declara `total_amount` como propriedade opcional
  aceita por `updateBudget`, mas `BudgetPatchRequest` (`extra="forbid"`) não tem esse campo
  — um cliente que o enviasse seria recusado com `422 VALIDATION_FAILED`. Divergência real
  de contrato×código, não fechada aqui (decisão de implementar ou formalmente remover o
  campo do contrato fica para quem assumir esse trabalho).
- **Serialização de campos `Decimal` como string** (achado §3) — corrigido apenas no ponto
  de uso deste bloco (`BudgetPanel.tsx`); a divergência de tipo entre contrato (`number`) e
  runtime (string) permanece em todo outro campo `Decimal` da API, não auditada
  exaustivamente nesta execução.
- **Aprovação dupla** (`requires_dual_approval`) para `BUDGET_CHANGE` — não exercitada
  ponta a ponta neste bloco, mesma pendência já registrada pelo WP-05 para `PUBLISH`.

## 9. Confirmações negativas

- `permissions.py`, `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma rota de backend nova criada (`PATCH /campaigns/{id}/budget` e `POST /approvals`
  já existiam).
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- Nenhum bloco além do WP-06 foi definido; a autorização de 3 blocos do Diretor ("pode
  avançar mais 3 blocos") está integralmente executada com este bloco (WP-04, WP-05,
  WP-06).

## 10. Critérios (Gate 5, extensão)

| Critério | Situação |
|---|---|
| Alteração de orçamento funciona ponta a ponta com dois usuários distintos | Sim, testado via E2E cross-stack real |
| Segregação de funções reutilizada do WP-05, nunca reimplementada | Sim |
| Variação percentual fora do limite é recusada visivelmente | Sim, testado (backend e componente) |
| `permissions.py` inalterado | Sim |
| Nenhuma rota de backend nova | Sim (confirmado por `git status`) |
| Revisão de FM QA Engineer | **Pendente** |
| Autorização do Diretor | Sim (execução, 3º bloco de "pode avançar mais 3 blocos") |

Veredito correto: `WP-06 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`.
Com este bloco, a autorização de 3 blocos concedida pelo Diretor está integralmente
executada; qualquer bloco além do WP-06 exige nova autorização ou nova reconciliação de
CURRENT + definição de escopo, pela mesma disciplina usada para definir este.
