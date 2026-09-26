# CampaIA — Reconciliação final e takeover técnico (PR#5 × PR#6)

**Data:** 26/09/2026 · **Missão:** PROMPT MESTRE — CampaIA, Reconciliação Final,
Consolidação de Branches e Takeover Técnico · **Branch de trabalho:**
`reconciliation/campaia-final-takeover` (local, nascida de `feat/campaia-wp01-web-foundation`
@ `41c031d94f989de5dddcd68e771daf241c156ba5`, HEAD confirmado de PR #5 no momento do início
desta missão) · **Autor:** Claude, por instrução explícita do Diretor.

Este documento é atualizado a cada bloco (WP) concluído, não escrito de uma vez ao final.

---

## FASE 0 — CURRENT reconstruído (execução real, 26/09/2026)

| SOURCE | BRANCH | HEAD | RELATION TO MAIN | RELATION TO PR #5 |
|---|---|---|---|---|
| main | `main` | `851db13723c3575d516bed64d71535cd7fed8bca` | — | PR#5 = main + 13 commits, 0 atrás |
| PR #5 | `feat/campaia-wp01-web-foundation` | `41c031d94f989de5dddcd68e771daf241c156ba5` | 13 à frente, 0 atrás | base |
| PR #6 | `feat/campaia-v1-complete-saas` | `3cc9e07b17815a9269d369c2ae25380a5d63790b` | 69 à frente, 33 atrás | 63 à frente, 40 atrás de PR#5; 243 arquivos divergentes |

**BASE DE AUTORIDADE:** PR #5 (confirmado pelo Diretor). Backend do CURRENT (HEAD acima)
rodado nesta sessão: `PYTHONPATH=. python3 -m pytest -q` → **526 passed, 58 subtests
passed, 0 failures**. Frontend: `npm run test -- --run` → **14 arquivos, 47 testes, 0
failures**; `npm run typecheck`, `npm run lint`, `npm run contracts:check`, `npm run
boundary:check` → todos OK antes de qualquer alteração desta missão.

Achado relevante fora do escopo direto de PR#5×PR#6, registrado por transparência: o
repositório tem hoje 30 PRs no total (não 6); 12+ já mescladas em `main` desde a auditoria
de 24/09 (billing/Asaas/segurança) e outra leva mesclada via squash entre 24/09 e 26/09,
incluindo autenticação real (WP-02, PR #30) e verificação real do provider Gemini. Isso não
altera a relação main↔PR#5↔PR#6 acima.

## FASE 1 — Inventário PR#5 × PR#6, com correções do Diretor

| Domínio | Classificação inicial | Classificação final (decisão do Diretor, 26/09) |
|---|---|---|
| BILLING/Asaas | A — Manter CURRENT | confirmada |
| AUTH/SESSION | E — Conflito | **A — Manter CURRENT.** OIDC provider-neutral da PR#6 (`oidc.py`, `test_idp.py`, 20/09) foi superado pela decisão arquitetural posterior de 24/09 (Google Identity Platform + firebase-admin, identidade externa só prova QUEM, tenant/roles/business_unit_id só do diretório interno, fail-closed). Mineração seletiva de testes/invariantes de segurança ainda ausentes, permitida; arquitetura OIDC antiga NÃO portada. |
| TENANCY | B — Portar (candidato) | **A — Manter CURRENT.** PR#5 já tem `GET /me/memberships`, `POST /auth/session/switch`, troca real de vínculo, CSRF, cross-tenant isolation, auditoria `SESSION_SWITCH`/`SESSION_SWITCH_REJECTED`, step-up, UI real, E2E `session-protocol.spec.ts`. `routes_session.py` da PR#6 NÃO portado como implementação concorrente. |
| WEB (frontend) | E — Conflito grave | **Arquitetura estrutural de PR#5 é autoridade.** `providers/`, `types/`, App Router, AuthProvider, API client, shell e componentes atuais preservados. Para WP-06→11: portar comportamento sobre a arquitetura de PR#5, nunca copiar diretório `web/` da PR#6. |
| CONTRACTS | dependia de AUTH/WEB | `contracts/bff-openapi.yaml` do CURRENT é a base; mudanças de PR#6 só seletivas/aditivas, comprovadas pelo backend real. |
| WP-06→WP-11 | B — Portar (prioridade alta) | confirmada; um por vez, comportamento sobre a arquitetura de PR#5. |

## BLOQUEIO DE ESCRITA (registrado, não resolvido)

Esta sessão consegue ler/fetch o repositório via git puro, mas **não tem permissão do git
proxy para dar push** de nenhuma branch nova (`not in this session's authorized repository
set`), mesmo com o GitHub App corretamente instalado e autorizado pelo Diretor no
repositório correto — a autorização de repositório por sessão do Claude Code parece só ser
aplicada na criação da sessão, não pode ser injetada depois. Trabalho procede 100% local
por instrução do Diretor; nenhum bundle/patch será gerado até a fase de publicação final.

---

## WP-06 — Alteração de orçamento

**Estado:** `IMPLEMENTADO E TESTADO NESTA SESSÃO`. FM QA Engineer formal ainda pendente
(mesma ressalva de todos os blocos anteriores do projeto).

### CURRENT antes deste bloco

- Backend: `PATCH /campaigns/{id}/budget` (`routes_campaigns.py::patch_budget`) e
  `POST /approvals` (`routes_approvals.py::create_approval`) **já existiam** em PR#5/main,
  com validação de variação percentual, approval gate, step-up, idempotência e auditoria
  `BUDGET_CHANGE`. Nenhum desses arquivos foi alterado neste bloco.
- Contrato: `ApprovalRequest.kind`/`amount` e `POST /approvals` **já estavam documentados**
  em `contracts/bff-openapi.yaml` do CURRENT (achado: PR#6 registrava esses mesmos campos
  como "corrigidos" em 21/09, mas o CURRENT de 24-26/09 já os tinha independentemente).
- Web: **nenhuma UI de orçamento existia** em `web/src` do CURRENT (confirmado por busca
  antes de escrever qualquer código).

### Achado real de contrato, confirmado por execução nesta sessão

`Campaign.budget.total_amount`/`daily_cap`/`spent_to_date` são `Decimal` em
`backend/api/models.py`. Execução real:

```python
class Budget(BaseModel):
    total_amount: Decimal
    daily_cap: Decimal
    spent_to_date: Decimal

Budget(total_amount=Decimal('1000'), daily_cap=Decimal('500.50'), spent_to_date=Decimal('10')).model_dump_json()
# => {"total_amount":"1000","daily_cap":"500.50","spent_to_date":"10"}
```

Confirma: pydantic v2 sempre serializa `Decimal` como **string** em `model_dump_json()` —
nunca `number`. O contrato declarava `type: number` para os 3 campos desde a construção
original; nunca foi verdade em runtime (mesma classe de achado que a PR#6 registrou em
21/09 para este mesmo bloco, de forma independente).

**Corrigido nesta sessão:** os 3 campos passam a `type: string` em
`contracts/bff-openapi.yaml`, mesmo padrão já usado em `ApprovalRequest.amount`. Aditivo
para o formato real, sem mudança de comportamento do backend. Tipos regenerados
(`npm run contracts:generate`) e verificados sem drift (`npm run contracts:check`).

### O que foi construído (comportamento portado, frontend reconstruído)

- `web/src/components/BudgetPanel.tsx` (novo) — resumo do orçamento (diário/total/gasto,
  normalizando `Number(...)` para tolerar string ou number vindo da API), fluxo propor
  (`POST /approvals`, `kind: BUDGET_CHANGE`) → decidir na fila de Aprovações (WP-05,
  inalterado) → aplicar (`PATCH /campaigns/{id}/budget`, com `X-Step-Up-Token`, mesmo
  padrão já usado em `connections/page.tsx` e `approvals/page.tsx`).
- `web/src/components/BudgetPanel.module.css` (novo), usando os tokens de design já
  existentes (`--campaia-color-*`, `--campaia-space-*`).
- Integrado em `campaigns/[campaignId]/page.tsx` (import + `<BudgetPanel />`), sem alterar
  nenhum comportamento pré-existente da página.
- Nenhum arquivo de `backend/campaia_core/`, `backend/api/routes_*.py` (exceto o contrato,
  documentado acima), `permissions.py` ou `mobile/` foi alterado — confirmado por
  `git status` antes do commit.

### Testes

- Novo: `web/tests/budget-panel.test.tsx` — 3 casos (resumo normalizado, propor mudança,
  aplicar mudança aprovada com verificação do header de step-up). Todos verdes.
- Atualizado: `web/tests/campaign-detail-page.test.tsx` — mock de `GET /approvals` (novo
  fetch do `BudgetPanel` ao montar a página); teste pré-existente continua verde sem
  alteração de asserts.
- Comando: `npm run test -- --run` → **15 arquivos, 50 testes, 0 failures** (baseline era
  14/47; +1 arquivo, +3 testes).
- `npm run typecheck`, `npm run lint`, `npm run contracts:check`, `npm run boundary:check`
  (55 arquivos, antes 53) → todos OK.
- Backend regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **526 passed, 58
  subtests passed** (idêntico ao baseline — nenhuma mudança de comportamento backend).

### Pendências reais deste bloco (não escondidas)

- FM QA Engineer formal: pendente (mesma ressalva histórica do projeto desde WP-02).
- Drift de tipo residual: o contrato agora reflete a string real para os 3 campos de
  budget, mas **nenhum outro campo `Decimal` do contrato foi auditado** nesta sessão —
  pode haver o mesmo achado em outros endpoints, fora do escopo deste bloco.

### Addendum — E2E cross-stack (checkpoint do Diretor, 26/09/2026)

O Diretor corrigiu o sequenciamento acima ("CHECKPOINT WP-06 APROVADO — PEQUENO AJUSTE
ANTES DO WP-07"): o E2E cross-stack não pode ficar pendente para um bloco futuro de
consolidação — precisa fechar o WP-06 agora, antes do WP-07. Cenário reconstruído (não
copiado) sobre o harness real já usado por `session-protocol.spec.ts`
(`web/playwright.session.config.ts`: backend Starlette real via
`tests_support/e2e_server.py` + Next.js real em build de produção).

**Identidade de teste nova, necessária para o cenário:** o harness de E2E só tinha
identidades OWNER por tenant; o fluxo exige um segundo usuário real do MESMO tenant para
decidir a aprovação sem violar segregação de funções. Adicionado
`E2E_TOKEN_TENANT_A_APPROVER` (`backend/tests_support/e2e_identity.py`, mapeado para
`approver@demo-tenant.campaia.test`, já seedado em `identity_directory.py`) e a opção
correspondente em `web/src/lib/auth/test-identity-client.ts`. Confirmado por grep que
nenhum teste existente depende de uma contagem/lista exata de identidades de teste.

**Novo arquivo:** `web/e2e/budget-change.spec.ts`, dois cenários:

1. `propor -> aprovar -> aplicar, com o orçamento real exibido mudando` — três contextos
   de navegador reais (OWNER, APPROVER do mesmo tenant, OWNER de outro tenant): cria
   campanha real via UI → propõe mudança de orçamento (`POST /approvals`) → segundo
   usuário real decide na fila de Aprovações real (`POST /approvals/{id}/decision`) →
   primeiro usuário aplica (`PATCH /campaigns/{id}/budget`, com `X-Step-Up-Token`) →
   orçamento diário exibido muda de R$ 500,00 para R$ 600,00 → isolamento de tenant
   confirmado (terceiro usuário, outro tenant, recebe 403/404 ao tentar `GET` direto na
   campanha).
2. `autoaprovação recusada e aplicação sem step-up recusada` — o próprio proponente tenta
   decidir a própria proposta na fila real (UI nunca esconde o botão — recusa real do
   backend exibida); confirma que o orçamento não mudou; PATCH direto sem header de
   step-up recebe `403 STEP_UP_REQUIRED` real do backend.

**Achados reais corrigidos durante a construção do E2E (o teste pegou bugs genuínos, não
problemas do próprio teste):**

- `POST /approvals/{id}/decision` devolve `200`, não `202` (só `PATCH /campaigns/{id}/budget`
  e `POST /briefs` são `202 Accepted`, por serem efeitos assíncronos — achado no código de
  `routes_approvals.py::decide_approval`, `json_response(...)` sem `status_code` explícito).
  Assert do teste corrigido para refletir o comportamento real, não alterado no backend.
- **Bug real de UI encontrado e corrigido nesta sessão:** depois de um `PATCH
  /campaigns/{id}/budget` bem-sucedido, `BudgetPanel.tsx` só recarregava a própria lista de
  aprovações (`reloadRelevantApproval()`) — o valor de orçamento exibido continuava vindo
  da prop `budget`, buscada uma única vez pela página pai
  (`campaigns/[campaignId]/page.tsx`) no carregamento inicial, e nunca era atualizado após
  aplicar a mudança. O primeiro run do E2E pegou isso de forma real: `R$ 500,00`
  continuava na tela mesmo com o backend já tendo aplicado `R$ 600,00`. Corrigido com um
  novo prop `onApplied?: () => void | Promise<void>` em `BudgetPanel`, chamado depois do
  PATCH bem-sucedido; a página pai passa sua função já existente `loadCampaignAndPlan`
  (mesmo padrão já usado por `handleValidate`/`handleGeneratePlan`) — nenhuma segunda fonte
  de verdade criada, o componente continua sem buscar a campanha por conta própria.
- Também adicionado `data-testid="budget-daily-cap"` no valor de orçamento diário exibido
  (convenção já usada em botões de ação no projeto, ex. `approve-${id}`), porque uma busca
  de texto livre por `"R$ 500,00"` colidia com o número 500 aparecendo cru dentro do JSON
  do painel "Estratégia (IA)" (mesma página) — achado de teste frágil, não de produto.

**Execução real:**

- `npx playwright test --config=playwright.session.config.ts` (com `budget-change.spec.ts`
  incluído em `testMatch`) → **16 passed** (14 pré-existentes de `session-protocol.spec.ts`
  + 2 novos), 0 failures, 0 skips.
- `npm run typecheck`, `npm run lint`, `npm run test -- --run` (**15 arquivos, 50 testes**,
  inalterado), `npm run contracts:check`, `npm run boundary:check` (**55 arquivos**,
  inalterado) → todos OK, sem regressão da adição de identidade de teste.
- Backend: `PYTHONPATH=. python3 -m pytest -q` → **526 passed, 58 subtests passed**
  (idêntico ao baseline — nenhum arquivo de `backend/campaia_core/`, `backend/api/routes_*.py`
  ou `permissions.py` alterado neste addendum).

**Estado final do WP-06:** `IMPLEMENTADO E TESTADO (unit + component + backend regression +
E2E cross-stack)` nesta sessão. FM QA Engineer formal continua pendente (ressalva histórica
do projeto).

---

## WP-07 — Nível de autonomia

**Estado:** `IMPLEMENTADO E TESTADO NESTA SESSÃO` (unit + component + backend regression +
E2E cross-stack, seguindo o checklist de 7 pontos do checkpoint do Diretor). FM QA Engineer
formal ainda pendente (mesma ressalva histórica).

### CURRENT antes deste bloco

- Backend: `GET /autonomy` e `PUT /autonomy` (`routes_autonomy.py`) **já existiam** em
  PR#5/main, com guarda anti-autopromoção real (`AutonomySettings.__post_init__` recusa
  `level > max_level_allowed`), gate de aprovação (`approval_id` precisa estar
  `APPROVED`), step-up e auditoria `AUTONOMY_CHANGE`. Nenhum desses arquivos de
  `campaia_core`/`api/routes_autonomy.py` foi alterado neste bloco.
- Web: **nenhuma UI de autonomia existia** em `web/src` do CURRENT (confirmado por busca
  antes de escrever qualquer código).
- Autonomia é configuração de **tenant**, não de campanha -- por isso o painel foi
  colocado em `/settings` (página já existente, reaproveitada), não em
  `campaigns/[campaignId]`.

### Achado real de contrato, confirmado por execução nesta sessão

`AutonomyResponse.model_dump_json()` sempre inclui `max_level_allowed`
(`backend/api/models.py`), mas `contracts/bff-openapi.yaml`'s `AutonomySettings` nunca
declarava esse campo -- mesma classe de achado do WP-06 (campo real do backend ausente do
contrato). Corrigido de forma aditiva (`max_level_allowed: { type: integer, minimum: 0,
maximum: 3 }`), tipos regenerados e verificados sem drift.

### O que foi construído (comportamento portado, frontend reconstruído)

- `web/src/components/AutonomyPanel.tsx` (novo) -- resumo do nível vigente (rótulo, teto
  do tenant, variação máxima de orçamento por nível, gatilhos que sempre exigem humano),
  fluxo propor (`POST /approvals`, `kind: AUTONOMY_CHANGE`, com uma campanha-âncora real
  do tenant, restrição já existente no backend -- ver achado de limitação abaixo) → decidir
  na fila de Aprovações (WP-05, inalterado) → aplicar (`PUT /autonomy`, com
  `X-Step-Up-Token`, mesmo padrão de `BudgetPanel`/`connections`/`approvals`).
- `web/src/components/AutonomyPanel.module.css` (novo), mesmos tokens de design já usados
  por `BudgetPanel.module.css`.
- Integrado em `settings/page.tsx` (busca a primeira campanha do tenant via `GET
  /campaigns` para servir de âncora; se não houver nenhuma, o formulário de proposta fica
  honestamente desabilitado, com uma mensagem explicando o motivo real, em vez de
  fabricar uma campanha).
- Nenhum arquivo de `backend/campaia_core/`, `backend/api/routes_*.py` (exceto o
  contrato, documentado acima) ou `permissions.py` foi alterado -- confirmado por `git
  status` antes do commit.

### Limitação real do CURRENT, documentada e não corrigida nesta sessão (fora de escopo de Web)

`POST /approvals` para `kind: AUTONOMY_CHANGE` não carrega o nível pretendido -- o
`amount` é aceito e devolvido, mas `PUT /autonomy::routes_autonomy.py` nunca o lê; quem
aplica escolhe o nível na hora, não necessariamente o mesmo que o aprovador revisou. Isso
é comportamento real do CURRENT (não introduzido nesta sessão) -- registrado como achado,
não corrigido, porque corrigi-lo exigiria mudança de contrato/domínio, não só da Web.

**Achado real mais significativo, descoberto construindo o E2E cross-stack:** nenhum
`ApprovalRequest` é marcado como consumido depois de um `PUT /autonomy` (nem depois de um
`PATCH /campaigns/{id}/budget`, mesmo padrão) bem-sucedido -- o registro permanece com
`status: APPROVED` indefinidamente. Reproduzido de forma real nesta sessão: rodar os dois
cenários de autonomia no MESMO tenant, em sequência, faz o segundo cenário encontrar a
aprovação já usada do primeiro (ainda "pronta para aplicar") em vez de propor uma nova --
comportamento honesto do domínio real, não um bug do teste (confirmado inspecionando o
snapshot de página do Playwright na falha). Corrigir isso corretamente exigiria um novo
estado no enum de `ApprovalRequest.status` (hoje `PENDING | APPROVED | REJECTED |
CHANGES_REQUESTED | EXPIRED`, sem um "aplicado/consumido") e tocaria os três `kind`s de
aprovação (`PUBLISH`, `BUDGET_CHANGE`, `AUTONOMY_CHANGE`), não só autonomia -- mudança de
contrato/domínio cross-cutting, fora do escopo de portar a Web de um único WP. Classificado
`INTERNAL_TECHNICAL` (resolvível internamente, sem dependência externa) e reservado para
avaliação na Fase 3 (mineração de correções técnicas ainda válidas da PR#6) ou um bloco
dedicado -- não mascarado com um reset de estado artificial nesta sessão. Mitigação usada
apenas para destravar o E2E: os dois cenários deste WP rodam em tenants reais diferentes
(tenant A no caminho feliz, tenant B no caminho negativo), nunca dois cenários de
autonomia no mesmo tenant.

### Testes

- Novo: `web/tests/autonomy-panel.test.tsx` -- 4 casos (resumo do nível incluindo o campo
  aditivo `max_level_allowed`, proposta de mudança, proposta desabilitada sem campanha
  âncora, aplicação de mudança aprovada com verificação do header de step-up). Todos
  verdes.
- Comando: `npm run test -- --run` → **16 arquivos, 54 testes, 0 failures** (antes desta
  sessão: 15/50; +1 arquivo, +4 testes).
- `npm run typecheck`, `npm run lint`, `npm run contracts:check` → OK; `npm run
  boundary:check` → **57 arquivos** (antes 55) → OK.
- Backend regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **526 passed, 58
  subtests passed** (idêntico ao baseline -- só o contrato foi tocado, nenhum
  comportamento de backend mudou).
- E2E cross-stack novo: `web/e2e/autonomy-level.spec.ts`, dois cenários (propor→aprovar→
  aplicar com dois usuários reais do tenant A, nível exibido mudando de APROVADO para
  ASSISTENTE; autoaprovação recusada + aplicação sem step-up recusada com 403
  `STEP_UP_REQUIRED`, no tenant B). `npx playwright test --config=playwright.session.config.ts`
  (com `autonomy-level.spec.ts` incluído em `testMatch`) → **18 passed** (16 pré-existentes
  de `session-protocol.spec.ts`/`budget-change.spec.ts` + 2 novos), 0 failures.

### Pendências reais deste bloco (não escondidas)

- FM QA Engineer formal: pendente (ressalva histórica).
- Limitação de design do CURRENT (nível não vinculado à aprovação) e ausência de estado
  "consumido" em `ApprovalRequest`: documentadas acima, não corrigidas nesta sessão --
  candidatas a um bloco técnico dedicado (Fase 3) que toque os três `kind`s de aprovação
  de uma vez, não só autonomia.
- Guarda anti-autopromoção (subir acima do teto do tenant): coberta pelo backend real
  (`test_autonomy_get_and_put`), exercitada manualmente durante a investigação desta
  sessão, mas não duplicada no E2E cross-stack (decisão de escopo -- o caminho crítico já
  está coberto; duplicar essa regra no E2E colidiria com o achado de aprovações não
  consumidas acima, sem agregar cobertura real nova).

---

## WP-08 — Kill switch (parada de emergência)

**Estado:** `IMPLEMENTADO E TESTADO NESTA SESSÃO` (unit + component + backend regression +
E2E cross-stack). FM QA Engineer formal ainda pendente (ressalva histórica).

### CURRENT antes deste bloco

- Backend: `POST /kill-switch` (`routes_campaigns.py::kill_switch`) **já existia** em
  PR#5/main, com 5 escopos (`CAMPAIGN`, `ACCOUNT`, `TENANT`, `PLATFORM`, `GLOBAL`),
  auditoria multi-tenant real (acha­do 17: evento registrado em CADA tenant afetado, não só
  no do chamador) e a guarda "só reduz efeito, nunca amplia". Nenhum arquivo de
  `campaia_core`/`api/routes_campaigns.py` foi alterado neste bloco.
- Deliberadamente **sem** fila de aprovação e **sem** step-up
  (`campaia_core/permissions.py::REQUIRES_STEP_UP` exclui `KILL_SWITCH` de propósito --
  "emergência não espera reautenticação"). Comportamento existente, não introduzido aqui.
- Web: **nenhuma UI de kill switch existia** em `web/src` do CURRENT.

### Achado real de contrato, confirmado por execução nesta sessão

`POST /kill-switch` sempre devolve `{scope, affected_campaign_ids}` no `202`
(`tests_api/test_smoke_endpoints.py::test_kill_switch_tenant_scope` já asserta
`affected_campaign_ids`), mas o contrato não declarava NENHUM schema de resposta para o
`202` (só uma descrição em texto). Corrigido de forma aditiva.

### Decisão de escopo, deliberada e registrada (não um gap técnico)

Só os escopos `CAMPAIGN` (esta campanha) e `TENANT` (todas as campanhas deste tenant)
foram portados para a Web nesta reconciliação:

- `ACCOUNT`/`PLATFORM` mapeiam para "connection_id"/"channel" sem um seletor natural em
  nenhuma tela atual -- o próprio backend já documenta isso como simplificação (achado
  13); construir um seletor novo para eles seria inventar uma interação de produto ainda
  não desenhada, não portar um comportamento existente.
- `GLOBAL` cruza **todos os tenants da plataforma**, e a autorização real de
  `Permission.KILL_SWITCH` não distingue um "administrador de plataforma" de um
  OWNER/ADMIN/FINANCE/APPROVER comum de qualquer tenant -- expor um botão "parar a
  plataforma inteira" numa tela de configurações de um tenant comum seria uma decisão de
  produto/segurança nova, com risco real de escalada de efeito entre tenants, não uma
  simples tradução de comportamento existente para a Web.

Registrado como `DECISÃO HUMANA NECESSÁRIA` (não implementado): se/quando `GLOBAL` e
`ACCOUNT`/`PLATFORM` devem ganhar UI, e com qual controle de autorização adicional para
`GLOBAL` especificamente.

### O que foi construído (comportamento portado, frontend reconstruído)

- `web/src/components/KillSwitchPanel.tsx` (novo, componente único reutilizado com um
  prop `scope`) -- aciona `POST /kill-switch` direto (sem propor/decidir/aplicar, ao
  contrário de WP-06/07, porque o próprio domínio não exige isso aqui), mostra o número
  real de campanhas afetadas devolvido pelo backend, e trata `409 INVALID_STATE` (escopo
  `CAMPAIGN` numa campanha ainda não pausável) com uma mensagem honesta, não um erro
  genérico.
- `web/src/components/KillSwitchPanel.module.css` (novo), mesmos tokens de design.
- Integrado em `campaigns/[campaignId]/page.tsx` (escopo `CAMPAIGN`, `target_id` =
  campanha atual) e em `settings/page.tsx` (escopo `TENANT`, sem `target_id`).

### Testes

- Novo: `web/tests/kill-switch-panel.test.tsx` -- 3 casos (escopo CAMPAIGN aciona e
  mostra afetadas, 409 INVALID_STATE mostrado honestamente, escopo TENANT sem
  `target_id`). Todos verdes.
- Comando: `npm run test -- --run` → **17 arquivos, 57 testes, 0 failures** (antes desta
  sessão: 16/54; +1 arquivo, +3 testes).
- `npm run typecheck`, `npm run lint`, `npm run contracts:check` → OK; `npm run
  boundary:check` → **59 arquivos** (antes 57) → OK.
- Backend regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **526 passed, 58
  subtests passed** (idêntico ao baseline -- só o contrato foi tocado).
- E2E cross-stack novo: `web/e2e/kill-switch.spec.ts`, dois cenários -- escopo `TENANT`
  aciona de verdade (campanha real criada via UI fica em `DRAFT`, ignorada silenciosamente
  pelo backend real, `affected_campaign_ids` real verificado, e a trilha de auditoria real
  (`GET /audit-events`) confirmada contendo um evento `KILL_SWITCH`, cumprindo a exigência
  do contrato "ainda assim gera evento e auditoria" mesmo quando nada foi pausado de
  fato); escopo `CAMPAIGN` numa campanha `DRAFT` recebe `409 INVALID_STATE` real e a UI
  mostra a mensagem honesta correspondente. `npx playwright test
  --config=playwright.session.config.ts` (com `kill-switch.spec.ts` incluído em
  `testMatch`) → **20 passed** (18 pré-existentes + 2 novos), 0 failures.

### Pendências reais deste bloco (não escondidas)

- FM QA Engineer formal: pendente (ressalva histórica).
- Escopos `ACCOUNT`/`PLATFORM`/`GLOBAL` não portados para a Web -- decisão deliberada
  registrada acima, não um esquecimento; aguardando decisão humana se algum deles precisa
  de UI e, para `GLOBAL`, de um controle de autorização adicional que hoje não existe.
- A Web atual ainda não tem um botão de "Publicar" campanha (fora do escopo desta
  reconciliação) -- por isso o E2E deste bloco não conseguiu demonstrar visualmente uma
  campanha saindo de `PAUSED` de verdade (nenhuma campanha criada pela Web hoje sai de
  `DRAFT`); o caminho real de pausar uma campanha genuinamente ativa já está coberto no
  backend (`test_kill_switch_platform_scope_pauses_matching_channel`,
  `test_kill_switch_global_scope_crosses_tenants`), não duplicado aqui.
