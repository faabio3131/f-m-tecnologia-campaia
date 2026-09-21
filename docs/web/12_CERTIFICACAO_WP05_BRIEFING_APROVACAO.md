# CampaIA — Ponto Zero Web · 12. Certificação do WP-05 (Briefing, estratégia e aprovação)

**Estado máximo declarado neste documento:** `WP-05 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`

Este documento certifica a execução real do WP-05
(`docs/web/06_ROADMAP_WORK_PACKAGES.md`), autorizada pela continuação de "PROMPT MESTRE —
CAMPAIA SaaS V1 COMPLETO" (21/09/2026, decisão do Diretor "pode avançar mais 3 blocos"),
sobre a branch `feat/campaia-v1-complete-saas` (PR #6).

O roadmap original exige, para o Gate 5 (Primeira jornada), aprovação de **FM QA Engineer**.
Esta execução tem autorização explícita do Diretor para **implementar** o Work Package;
**não inclui nem simula uma revisão de QA formal** — essa revisão permanece uma pendência
genuína, registrada aqui, nunca presumida como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| CURRENT reconstruído por leitura direta: todas as 6 rotas do escopo já existiam no backend | `backend/api/routes_campaigns.py`, `backend/api/routes_approvals.py` |
| Contrato: campo real ausente adicionado aditivamente | `contracts/bff-openapi.yaml` |
| Web: leituras server-side de campanhas/plano/aprovações | `web/src/lib/session.ts` |
| Web: tipos novos do contrato + tipo local do output do estrategista | `web/src/contracts/types.ts` |
| Web: formulário de briefing, painel de estratégia, painel de validação, cartão de decisão | `web/src/components/{BriefForm,PlanPanel,ValidationPanel,ApprovalDecisionCard}.tsx` |
| Web: páginas de campanhas e aprovações | `web/src/app/campaigns/`, `web/src/app/approvals/` |
| Web: navegação do dashboard atualizada para as novas telas | `web/src/app/dashboard/page.tsx` |
| Fronteira de segurança do frontend atualizada (allowlist de 9 arquivos) | `web/scripts/lib/security-boundaries.mjs` |
| Backend: teste de jornada via sessão Web real (não apenas fixture Bearer) | `backend/tests_api/test_briefing_approval_web_session.py` |
| E2E de fumaça sem backend | `web/e2e/{campaigns,approvals}.spec.ts` |
| E2E cross-stack real, dois usuários distintos | `web/e2e-crossstack/briefing-approval-journey.spec.ts` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `backend/campaia_core/
permissions.py`, `mobile/` foi alterado (confirmado por `git status`). Nenhuma rota de
backend nova foi criada — todas as 6 rotas do escopo já existiam desde blocos anteriores
(pré-Web); este Work Package construiu inteiramente a camada Web sobre elas.

## 2. Achado real, fora do escopo original, corrigido nesta execução (contrato)

Ao tipar `ApprovalDecisionCard.tsx` contra o schema `ApprovalRequest` gerado do contrato,
o TypeScript recusou `approval.requested_by` — o campo simplesmente não existia no tipo
gerado. Investigação: `contracts/bff-openapi.yaml`'s `ApprovalRequest` nunca listou
`requested_by`, embora `backend/api/helpers.py serialize_approval` sempre o retorne (é o
próprio `ApprovalRequest.requested_by` do domínio, quem propôs a ação). Um gap real de
contrato, não de código: o backend sempre devolveu o campo; o contrato nunca o declarou.

Corrigido aditivamente: `requested_by` adicionado ao schema, `npm run contracts:generate`
reexecutado, `contracts:check` confirmou zero drift. Sem este campo, a UI não teria como
comunicar segregação de funções ao usuário ("proposto por fulano") de forma alguma — o
achado não era cosmético.

## 3. Achados reais de frontend, encontrados e corrigidos durante o próprio desenvolvimento

**(a) CSRF ausente em `ValidationPanel.tsx`.** A primeira versão de `handleValidate()`
chamava `POST /campaigns/{id}/validate` sem o header `X-CSRF-Token`, por suposição
equivocada de que uma rota "sem efeito colateral externo" não precisaria dele. Um teste de
backend com sessão real (`test_briefing_approval_web_session.py`) revelou o erro:
`CSRFMiddleware` (`backend/api/csrf.py`) exige o header em **toda** mutação (qualquer método
não seguro) autenticada por cookie de sessão, sem exceção por semântica de rota. Corrigido
adicionando o header, exatamente como todo outro mutador desta app já fazia.

**(b) Shape do output do estrategista.** `PlanPanel.tsx` originalmente renderizava
`plan.output` como texto direto dentro de um `<p>`. A primeira execução real do E2E
cross-stack contra o backend de verdade quebrou com "Objects are not valid as a React
child": o agente `strategist` (`backend/campaia_core/agents.py`, `AGENTS["strategist"]
.output_schema`) produz um objeto estruturado (`objetivo: str`, `funil: str`, `canais:
list`, `justificativa: str`), nunca texto livre. Corrigido tipando `StrategistPlanOutput`
em `web/src/contracts/types.ts` e renderizando cada campo em uma lista de definição (`<dl>`).

**(c) Identidade de teste errada no primeiro rascunho do teste de backend.** A primeira
versão do teste de segregação de funções usava `marketer` como proponente; a autoaprovação
falhava com `PERMISSION_DENIED` em vez de `SEPARATION_OF_DUTIES` — porque `MARKETER` nunca
teve `APPROVAL_DECIDE` no primeiro lugar (`campaia_core/permissions.py`), então o teste
media uma negação de permissão simples, não a checagem de segregação de funções que o
critério de aceitação do roadmap pede. Corrigido trocando o proponente para `owner`
(que detém todas as permissões, incluindo `APPROVAL_DECIDE`), isolando corretamente a
rejeição por `can_approve`'s `requester_id` check.

Os três achados foram capturados pela própria disciplina de teste desta execução, antes de
qualquer deploy — nenhum chegou a ser exercitado por um usuário real do produto.

## 4. Decisão de escopo: o que o WP-05 explicitamente não constrói

`POST /campaigns/{id}/publish` (publicação real) permanece fora de escopo, exatamente como
o roadmap original já declarava — depende de um adaptador de provider real que não existe.
Nenhuma tela deste Work Package chama essa rota; `ValidationPanel.tsx` para no pedido de
aprovação, nunca avança para publicação.

## 5. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api -v
Ran 164 tests
OK
```

164 = 162 pré-existentes (WP-01 a WP-04, inalterados) + 2 novos
(`tests_api/test_briefing_approval_web_session.py`).

| Suite | Cobre |
|---|---|
| `test_briefing_approval_web_session.py` (2) | Jornada completa via cookie de sessão real (não Bearer fixture): brief → plano (vazio, depois gerado) → validação → pedido de aprovação → autoaprovação recusada (403 SEPARATION_OF_DUTIES) → aprovador distinto (mesmo `AppState`, sessão separada) decide → `GET /approvals` reflete a decisão, incluindo o `requested_by` do achado do contrato; `viewer` sem `CAMPAIGN_CREATE` é recusado (403) ao tentar submeter briefing via sessão real |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração -- campaia_core intocado)

$ cd contracts && python3 validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run lint && npm run typecheck && npm run contracts:check && npm run boundary:check && npm run test && npm run build
todos verdes   (90/90 Vitest -- 37 novos desde o WP-04: BriefForm (5), PlanPanel (6),
ValidationPanel (5), ApprovalDecisionCard (5), CampaignsPage (5), CampaignDetailPage (5),
ApprovalsPage (5), mais o ajuste do teste existente dashboard-page.test.tsx para a nova
navegação -- soma exata: 90 - 53 pré-existentes = 37)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e
14 passed (desktop+mobile × foundation.spec.ts, account.spec.ts, dashboard.spec.ts,
onboarding.spec.ts, campaigns.spec.ts, approvals.spec.ts)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e:crossstack
7 passed (6 dos WP-03/04 + 1 novo: jornada completa de dois usuários reais --
`owner` propõe brief → gera estratégia → valida → pede aprovação → tenta autoaprovar
(recusado, visível) → `approver`, em um BrowserContext totalmente separado, aprova de
verdade → a fila do proponente, recarregada, reflete a decisão real do aprovador)
```

## 6. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida das certificações
  anteriores; nenhum literal novo introduzido).
- Fronteira do frontend atualizada, não removida: chamada de rede ao BFF agora permitida em
  exatamente 9 arquivos (`session.ts`, `LogoutButton.tsx`, `TenantSwitcher.tsx`,
  `BrandKitForm.tsx`, `ConnectAccountCard.tsx`, `BriefForm.tsx`, `PlanPanel.tsx`,
  `ValidationPanel.tsx`, `ApprovalDecisionCard.tsx` — os 4 últimos, novos nesta execução,
  todos protegidos por CSRF). Todo o resto de `web/src` permanece em zero chamadas de rede,
  confirmado por `npm run boundary:check` (56 arquivos verificados, 0 violações).
- O header `X-Step-Up-Token` enviado por `ApprovalDecisionCard.tsx` carrega um marcador
  literal (`web-ui-approval-decision-button-clicked`), mesmo padrão honesto estabelecido
  pelo WP-04 (`ConnectAccountCard.tsx`) — nenhuma UI de reautenticação real simulada como
  se fosse real.

## 7. Escopo do diff (confirmado por `git status`)

Modificados: `contracts/bff-openapi.yaml`, `web/scripts/{check-security-boundaries.mjs,
lib/security-boundaries.mjs}`, `web/src/contracts/{bff-openapi.generated.ts,types.ts}`,
`web/src/lib/session.ts`, `web/src/app/dashboard/{page.tsx,page.module.css}`,
`web/tests/dashboard-page.test.tsx`.

Novos: `backend/tests_api/test_briefing_approval_web_session.py`,
`web/e2e/{campaigns,approvals}.spec.ts`,
`web/e2e-crossstack/briefing-approval-journey.spec.ts`, `web/src/app/campaigns/`,
`web/src/app/approvals/`,
`web/src/components/{BriefForm,PlanPanel,ValidationPanel,ApprovalDecisionCard}.{tsx,module.css}`,
`web/tests/{brief-form,plan-panel,validation-panel,approval-decision-card,campaigns-page,
campaign-detail-page,approvals-page}.test.tsx`.

`mobile/`, `backend/campaia_core/`, `backend/db/`, `backend/api/routes_campaigns.py`,
`backend/api/routes_approvals.py`, `backend/api/models.py`: **intocados** (as rotas já
existiam; só o contrato que as descreve foi corrigido).

## 8. Itens não verificados / pendências reais

- **Revisão de FM QA Engineer** — não realizada nesta execução; pendência explícita do
  Gate 5.
- **Publicação real** (`POST .../publish`) — confirmado fora de escopo real (depende de
  adaptador de provider); permanece uma lacuna genuína do produto, não deste Work Package.
- **Regeneração de plano com ajustes do usuário** (`adjustments`) — o campo existe no
  contrato e é enviado pelo frontend quando preenchido, mas o simulador de IA
  (`campaia_core/ai_simulator.py`) não foi verificado quanto a realmente variar sua saída
  em função desse texto — não investigado nesta execução, já que não fazia parte do
  critério de aceitação do roadmap.
- **Aprovação dupla** (`requires_dual_approval`) — o campo é lido e enviado corretamente
  pela UI e testado no domínio (`campaia_core`, blocos anteriores), mas não foi exercitado
  ponta a ponta por este Work Package (nenhuma campanha do teste/E2E exigiu duas
  aprovações distintas) — pendência real de cobertura, não de implementação.

## 9. Confirmações negativas

- `permissions.py`, `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma rota de backend nova criada (as 6 rotas do escopo já existiam).
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- WP-06 em diante: não iniciados; escopo do WP-06 ainda não definido (o roadmap não o
  detalha — ver `06_ROADMAP_WORK_PACKAGES.md` §3).

## 10. Gate 5 — critérios

| Critério | Situação |
|---|---|
| Onboarding completa e Brand Kit salvo (WP-04) | Sim, testado via E2E cross-stack real |
| Briefing → estratégia → validação → aprovação funciona ponta a ponta | Sim, testado via E2E cross-stack real com dois usuários |
| Tentativa de autoaprovação recusada visivelmente | Sim, testado nos dois níveis (backend com sessão real; E2E com navegador real) |
| Segregação de funções aplicada só pelo servidor, nunca reimplementada na UI | Sim |
| `permissions.py` inalterado | Sim |
| Revisão de FM QA Engineer | **Pendente** |
| Autorização do Diretor | Sim (execução, continuação de "pode avançar mais 3 blocos") |

Dado que a revisão de QA não foi completada, o Gate 5 **não pode ser declarado
formalmente fechado** por este documento — mas todos os critérios funcionais e técnicos do
gate estão implementados e comprovados por teste real (backend, Vitest, E2E de fumaça e
E2E cross-stack de dois usuários). Veredito correto:
`WP-05 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE (GATE 5 TECNICAMENTE COMPLETO, FORMALMENTE PENDENTE DE REVISÃO)`.
