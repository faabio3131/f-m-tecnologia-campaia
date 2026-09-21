# CampaIA — Ponto Zero Web · 14. Certificação do WP-07 (Nível de autonomia)

**Estado máximo declarado neste documento:** `WP-07 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`

Este documento certifica a execução real do WP-07 — um bloco **não presente no roadmap
original**, definido nesta mesma missão por reconciliação de CURRENT (ver
`docs/web/06_ROADMAP_WORK_PACKAGES.md` §"WP-07 — Nível de autonomia (Modo Manual/Automático)"),
sob **nova autorização do Diretor**, distinta da autorização de "3 blocos" que fechou o
WP-06: a cota gratuita de minutos do GitHub Actions da conta foi confirmada esgotada
(`FATO CONFIRMADO` pelo Diretor, 21/09/2026), com renovação prevista para o dia 31; o
Diretor autorizou explicitamente continuar a construção enquanto isso ("a cota será
renovada no dia 31 então vamos continuar trabalhando na construção e fazer tudo que for
possível sem atrasar o término e no final faremos os testes necessários") — os "testes
necessários" referem-se à confirmação do CI remoto, bloqueada até o dia 31, não aos testes
locais desta execução, que seguem obrigatórios e executados a cada passo. Sobre a branch
`feat/campaia-v1-complete-saas` (PR #6).

Como todo bloco desde o WP-02, esta execução **não inclui nem simula uma revisão de QA
formal** — essa revisão permanece uma pendência genuína, registrada aqui, nunca presumida
como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| Contrato: 2 campos reais ausentes, adicionados aditivamente | `contracts/bff-openapi.yaml` |
| Web: componente de autonomia (propor, exibir status, aplicar) | `web/src/components/AutonomyPanel.tsx` |
| Web: painel de autonomia integrado ao shell do dashboard | `web/src/app/dashboard/page.tsx` |
| Web: leitura server-side de autonomia | `web/src/lib/session.ts` (`getServerAutonomy`) |
| Fronteira de segurança do frontend atualizada (allowlist de 11 arquivos) | `web/scripts/{check-security-boundaries.mjs,lib/security-boundaries.mjs}` |
| Backend: teste de jornada via sessão Web real (propor→aprovar→aplicar, dois usuários; recusa por teto acima do contratado) | `backend/tests_api/test_autonomy_change_web_session.py` |
| E2E cross-stack real, dois usuários distintos | `web/e2e-crossstack/autonomy-change.spec.ts` |
| Correção de regressão E2E pré-existente (WP-05), exposta pelo novo spec | `web/e2e-crossstack/briefing-approval-journey.spec.ts` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `backend/api/routes_autonomy.py`,
`backend/api/routes_approvals.py`, `backend/api/models.py`, `permissions.py`, `mobile/` foi
alterado (confirmado por `git status`). Nenhuma rota de backend nova foi criada — `GET/PUT
/autonomy` e `POST /approvals` já existiam desde blocos anteriores; este bloco construiu
inteiramente a camada Web sobre eles, reutilizando por completo a fila de aprovação
(`/approvals`, `ApprovalDecisionCard.tsx`) já construída pelo WP-05 e já estendida pelo WP-06.

## 2. Achados reais de contrato, corrigidos durante a execução

Ao projetar `AutonomyPanel.tsx` (antes de escrever qualquer chamada de rede), a leitura
direta de `contracts/bff-openapi.yaml`'s `AutonomySettings` revelou um campo ausente, apesar
de sempre presente na resposta real (`api/routes_autonomy.py _serialize`):

- **`max_level_allowed`** — o teto contratado (`campaia_core/autonomy.py
  AutonomySettings.max_level_allowed`), que a guarda anti-auto-promoção do domínio
  (`__post_init__`, invariante I-11) nunca permite ultrapassar. Sem esse campo tipado, a Web
  não teria como desabilitar corretamente os níveis acima do teto ao propor uma mudança —
  teria de reimplementar (ou adivinhar) a mesma regra do domínio no frontend, exatamente o
  tipo de duplicação que a Constituição Operacional do Claude Code proíbe.

Um segundo campo foi descoberto já durante a escrita dos testes, não do componente: ao
tipar explicitamente `const CAMPAIGN: Campaign = {...}` em `tests/autonomy-panel.test.tsx`
(diferente dos fixtures `Campaign` de arquivos de teste anteriores, que nunca tinham
anotação de tipo explícita e por isso nunca acionavam a checagem de excesso de propriedade
do TypeScript), `tsc` recusou `business_unit_id` como propriedade desconhecida. Comparação
direta com `backend/api/models.py CampaignResponse` confirmou que o campo é real e sempre
devolvido pela API — apenas nunca fora declarado no contrato, para nenhum consumidor
anterior. Corrigido aditivamente:

- **`Campaign.business_unit_id`** — sempre presente em `CampaignResponse.business_unit_id`
  (`api/models.py`), ausente de `contracts/bff-openapi.yaml`'s `Campaign` desde a definição
  original do schema, antes mesmo do WP-05.

Ambas as correções são aditivas: `npm run contracts:generate`/`contracts:check` confirmaram
sincronia após cada uma, sem quebrar nenhum consumidor existente. Uma investigação mais
ampla de `CampaignResponse` mostrou outros campos reais também ausentes do contrato
(`brief`, `plan_version`, `connection_id`, `last_synced_at`) — deliberadamente **não**
corrigidos nesta execução, por não bloquearem este bloco: registrados como pendência (ver
§8), consistente com a disciplina de menor mudança coerente.

## 3. Achado real de teste, encontrado e corrigido durante a própria execução

Rodar a suíte cross-stack completa (não apenas o novo spec isolado) revelou uma regressão
real em `briefing-approval-journey.spec.ts` (WP-05): duas asserções `getByText("APPROVED")`
sem escopo (linhas então 79 e 95) resolviam de forma ambígua (violação de modo estrito do
Playwright) assim que `autonomy-change.spec.ts` (este bloco) passou a deixar seu próprio
card `APPROVED` na mesma fila `/approvals` do backend compartilhado — todos os specs
cross-stack rodam sequencialmente (`playwright.crossstack.config.ts`, `workers: 1`) contra
um único processo de backend real, um único `AppState`. O problema nunca se manifestara
antes porque nenhum spec anterior deixava uma segunda aprovação `APPROVED` visível na
mesma fila ao mesmo tempo — `budget-change.spec.ts` (WP-06) já havia enfrentado e resolvido
exatamente essa classe de ambiguidade para si mesmo, delimitando sua própria asserção por
`data-testid`.

Corrigido investigando a causa raiz (não mascarando o sintoma, nem pulando/desabilitando o
teste): capturado `campaignId` logo após a criação do brief em
`briefing-approval-journey.spec.ts`, e ambas as asserções `getByText("APPROVED")` delimitadas
ao seu próprio card (`approval-card-PUBLISH-{campaignId}`), mesma disciplina já usada pelo
WP-06. Confirmado com a suíte cross-stack completa rodando verde (9/9) depois da correção.

## 4. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api
Ran 168 tests
OK
```

168 = 166 pré-existentes (WP-01 a WP-06, inalterados) + 2 novos
(`tests_api/test_autonomy_change_web_session.py`).

| Suite | Cobre |
|---|---|
| `test_autonomy_change_web_session.py` (2) | Jornada completa propor→aprovar→aplicar via cookie de sessão real, dois `TestClient` distintos (owner propõe e aplica, approver decide) sobre o mesmo `AppState`, nível 1→0 (a única mudança dentro do teto disponível sob a configuração padrão do tenant); proposta e aprovação de um nível acima do teto contratado são aceitas normalmente pela fila de aprovação, mas a aplicação é recusada com `422 VALIDATION_FAILED` pela guarda anti-auto-promoção do próprio domínio (invariante I-11), nunca reimplementada aqui |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração -- campaia_core intocado)

$ cd contracts && python3 validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run lint && npm run typecheck && npm run contracts:check && npm run test && npm run build
todos verdes   (110/110 Vitest -- 11 novos desde o WP-06: AutonomyPanel (10) + 1 novo em
dashboard-page.test.tsx -- soma exata: 110 - 99 pré-existentes = 11)

$ node web/scripts/check-security-boundaries.mjs
OK: nenhuma violação (60 arquivos verificados, allowlist de 11 arquivos: os 10 do WP-02 a
WP-06 + AutonomyPanel.tsx)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e:crossstack
9 passed (8 pré-existentes + 1 novo: propor uma alteração de nível -> um segundo usuário
real, em um BrowserContext separado, aprova na fila /approvals já existente -> o
proponente aplica a mudança de verdade -> o nível exibido reflete o novo valor; inclui a
correção de regressão em briefing-approval-journey.spec.ts, ver §3)
```

Sem novo spec de fumaça dedicado (`npm run test:e2e`, sem backend): `/dashboard` já é
coberto pelos specs existentes de WP-02/WP-03 (nenhuma chamada BFF quando
`NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` está ausente); o painel de autonomia em si só é
exercitável com um backend real, coberto pelo E2E cross-stack acima.

## 5. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida das certificações
  anteriores; nenhum literal novo introduzido).
- Fronteira do frontend atualizada, não removida: chamada de rede ao BFF agora permitida em
  exatamente 11 arquivos (os 10 do WP-02 a WP-06 + `AutonomyPanel.tsx`, protegido por CSRF).
  Todo o resto de `web/src` permanece em zero chamadas de rede, confirmado por
  `node scripts/check-security-boundaries.mjs` (60 arquivos verificados, 0 violações).
- O header `X-Step-Up-Token` enviado por `AutonomyPanel.tsx` carrega um marcador literal
  (`web-ui-apply-autonomy-change-button-clicked`), mesmo padrão honesto estabelecido pelos
  WP-04 a WP-06 — nenhuma UI de reautenticação real simulada como se fosse real.

## 6. Escopo do diff (confirmado por `git status`)

Modificados: `contracts/bff-openapi.yaml`, `web/scripts/{check-security-boundaries.mjs,
lib/security-boundaries.mjs}`, `web/src/contracts/{bff-openapi.generated.ts,types.ts}`,
`web/src/app/dashboard/page.tsx`, `web/src/lib/session.ts`, `web/tests/dashboard-page.test.tsx`,
`web/e2e-crossstack/briefing-approval-journey.spec.ts`.

Novos: `backend/tests_api/test_autonomy_change_web_session.py`,
`web/e2e-crossstack/autonomy-change.spec.ts`,
`web/src/components/AutonomyPanel.{tsx,module.css}`, `web/tests/autonomy-panel.test.tsx`.

`mobile/`, `backend/campaia_core/`, `backend/db/`, `backend/api/routes_autonomy.py`,
`backend/api/routes_approvals.py`, `backend/api/models.py`, `permissions.py`:
**intocados**.

## 7. Itens não verificados / pendências reais

- **Revisão de FM QA Engineer** — não realizada nesta execução; pendência explícita, como
  em todo bloco desde o WP-02.
- **Outros campos reais de `CampaignResponse` ausentes do contrato** (`brief`,
  `plan_version`, `connection_id`, `last_synced_at`) — confirmados por leitura direta de
  `api/models.py` durante a investigação do achado §2, deliberadamente não corrigidos aqui
  por não bloquearem este bloco (nenhum deles é consumido por `AutonomyPanel.tsx`);
  registrados como pendência real, mesma classe dos achados já fechados um a um pelos
  WP-05/06/07.
- **Serialização de campos `Decimal` como string** (achado do WP-06, P-36) — não
  reexercitada neste bloco; `AutonomySettings.max_budget_change_pct` também é `Decimal`,
  mas não é lido nem comparado numericamente por `AutonomyPanel.tsx`.
- **Alterar `max_level_allowed` (teto contratado)** — confirmado fora de escopo deste bloco
  (nenhuma rota de API expõe essa alteração; tratado como configuração comercial/plano).
- **CI remoto do GitHub Actions** — não confirmado verde nesta execução; **FATO CONFIRMADO
  pelo Diretor**: cota gratuita de minutos esgotada, renovação prevista para o dia 31. Não é
  regressão de código; nenhuma correção adicional fará o CI passar enquanto a cota estiver
  esgotada. Toda a evidência deste documento vem de execução local real (comandos e
  resultados acima), não do CI.

## 8. Confirmações negativas

- `permissions.py`, `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma rota de backend nova criada (`GET/PUT /autonomy` e `POST /approvals` já existiam).
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- Nenhum bloco além do WP-07 foi definido; qualquer trabalho futuro exige a mesma
  disciplina de reconciliação de CURRENT usada para definir este bloco.

## 9. Critérios (Gate 5, extensão)

| Critério | Situação |
|---|---|
| Alteração de nível de autonomia funciona ponta a ponta com dois usuários distintos | Sim, testado via E2E cross-stack real |
| Segregação de funções reutilizada do WP-05, nunca reimplementada | Sim |
| Nível acima do teto contratado é recusado visivelmente, na aplicação | Sim, testado (backend) |
| `permissions.py` inalterado | Sim |
| Nenhuma rota de backend nova | Sim (confirmado por `git status`) |
| Revisão de FM QA Engineer | **Pendente** |
| Autorização do Diretor | Sim (nova autorização explícita para continuar a construção durante o bloqueio de cota do CI, 21/09/2026) |

Veredito correto: `WP-07 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`.
Nenhum bloco além do WP-07 foi definido; qualquer bloco seguinte exige a mesma disciplina
de reconciliação de CURRENT usada para definir este.
