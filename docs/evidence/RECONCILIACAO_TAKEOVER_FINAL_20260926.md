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

---

## WP-09 — Capacidades de conexão

**Estado:** `IMPLEMENTADO E TESTADO NESTA SESSÃO` (unit + component + backend regression +
E2E cross-stack). FM QA Engineer formal ainda pendente (ressalva histórica).

### CURRENT antes deste bloco

- Backend: `GET /connections/{connectionId}/capabilities`
  (`routes_connections.py::connection_capabilities`) **já existia** em PR#5/main. Nenhum
  arquivo de `campaia_core`/`api/routes_connections.py` foi alterado neste bloco.
- Web: a página `/connections` (WP-04) já lista conexões reais e completa o ciclo
  OAuth simulado, mas **não exibia capacidades** -- confirmado por busca antes de
  escrever qualquer código.

### Achado real de contrato, confirmado por execução nesta sessão

`CapabilityResponse.model_dump_json()` sempre inclui `provider`, `country` e
`api_version`, mas o contrato's `Capability` schema só declarava `capability_key`,
`supported`, `requires_approval`, `evidence_url`, `verified_at` e `notes` -- mesma classe
de achado de WP-06/07/08 (campos reais do backend ausentes do contrato). Corrigido de
forma aditiva.

### Achado real de comportamento, confirmado por execução direta (não corrigido nesta sessão)

`campaia_core/infra.py::CapabilityRegistry` é indexado por `(provider, capability_key,
country, api_version)`. `api/state.py::_seed_capabilities()` só registra capacidades sob
`provider="SIMULATOR"` -- mas nenhuma `Connection` real criada pelo fluxo de OAuth
(`Provider` do contrato é `GOOGLE_ADS | META | WHATSAPP`, nunca `"SIMULATOR"`) jamais tem
esse provider. Confirmado por execução direta em Python: `is_supported("GOOGLE_ADS", ...)`
→ `False`; `is_supported("SIMULATOR", ...)` → `True`.

**Decisão registrada, não uma correção silenciosa:** isso significa que `GET
/connections/{id}/capabilities` hoje sempre devolve `supported: false` para qualquer
conexão real. `"SIMULATOR"` também é usado deliberadamente em
`routes_campaigns.py::validate_campaign` como o publicador simulado da PLATAFORMA
(independente da conta OAuth escolhida) -- mudar o seed para "provar" capacidades de
contas reais fabricaria um `supported: true` que nunca foi de fato verificado para
nenhuma conta real, contrariando a mesma disciplina de honestidade já aplicada a
`insights` (nunca fabricar métricas, mantido honestamente vazio) e ao Gemini/IA (nunca
inventar verificação). Por isso este bloco **não alterou** `_seed_capabilities()` --
construiu a Web para exibir fielmente o que o backend real diz, incluindo o
`supported: false` honesto, em vez de mascarar isso ou de "consertar" o seed para exibir
algo mais bonito. Registrado para avaliação futura (Fase 3 ou decisão humana): se o
objetivo do produto é algum dia mostrar capacidades "verificadas" para contas reais antes
de existir integração real, esse desenho precisa ser repensado (provavelmente exigindo o
item de verificação real de conta, não um seed estático).

### O que foi construído (comportamento portado, frontend reconstruído)

- `web/src/components/CapabilitiesPanel.tsx` (novo) -- "Ver capacidades" expansível por
  conexão ativa, busca sob demanda (só uma vez por expansão, não recarrega ao
  ocultar/mostrar de novo), mostra `capability_key`, badge Suportada/Não suportada,
  país/versão de API, `requires_approval`, `verified_at` formatado, e evidência --
  nunca inventa um `evidence_url` quando o backend devolve `null` (mostra "sem evidência
  registrada" honestamente).
- `web/src/components/CapabilitiesPanel.module.css` (novo), mesmos tokens de design.
- Integrado em `connections/page.tsx`, um painel por conexão `ACTIVE`.

### Testes

- Novo: `web/tests/capabilities-panel.test.tsx` -- 3 casos (não busca nada até expandir,
  busca e mostra capacidades reais incluindo suportada/não suportada e evidência
  ausente, busca só uma vez ao alternar mostrar/ocultar repetidamente). Todos verdes.
- Comando: `npm run test -- --run` → **18 arquivos, 60 testes, 0 failures** (antes desta
  sessão: 17/57; +1 arquivo, +3 testes).
- `npm run typecheck`, `npm run lint`, `npm run contracts:check` → OK; `npm run
  boundary:check` → **61 arquivos** (antes 59) → OK.
- Backend regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **526 passed, 58
  subtests passed** (idêntico ao baseline -- só o contrato foi tocado).
- E2E cross-stack novo: `web/e2e/capabilities.spec.ts` -- fecha o ciclo real de conexão
  (tenant B, isolado de propósito do tenant A já usado por `session-protocol.spec.ts`'s
  teste L para não competir pela mesma conexão GOOGLE_ADS), expande "Ver capacidades" e
  confirma o `GET /connections/{id}/capabilities` real: `supported: false` e
  `evidence_url: null` para as duas capacidades, exatamente o comportamento honesto
  documentado acima -- não um resultado fabricado. `npx playwright test
  --config=playwright.session.config.ts` (com `capabilities.spec.ts` incluído em
  `testMatch`) → **21 passed** (20 pré-existentes + 1 novo), 0 failures.
- Achado de teste corrigido no processo: `page.getByTestId(...).isVisible()` não espera
  a resposta real do backend nem a re-renderização da página -- usado assim, o primeiro
  run desta suite corrompeu o teste L pré-existente de `session-protocol.spec.ts`
  (competindo pela mesma conexão GOOGLE_ADS do tenant A). Corrigido usando tenant B
  neste E2E novo e uma espera real (`expect(...).toBeVisible()`) antes de decidir entre
  os dois estados possíveis da página.

### Pendências reais deste bloco (não escondidas)

- FM QA Engineer formal: pendente (ressalva histórica).
- O achado de `_seed_capabilities()` (`provider="SIMULATOR"` nunca corresponde a uma
  conexão real) não foi corrigido -- decisão deliberada de não fabricar um
  `supported: true` sem verificação real, registrada acima para decisão de produto
  futura.

---

## WP-10 — Trilha de auditoria

**Estado:** `IMPLEMENTADO E TESTADO NESTA SESSÃO` (unit + component + backend regression +
E2E cross-stack). FM QA Engineer formal ainda pendente (ressalva histórica).

### CURRENT antes deste bloco

- Backend: `GET /audit-events` (`routes_audit.py::list_audit_events`) **já existia** em
  PR#5/main e já era usado internamente por vários WPs anteriores (WP-05 a WP-09) para
  registrar suas próprias ações -- mas nenhum deles jamais o EXPÔS na Web. Nenhum arquivo
  de `campaia_core`/`api/routes_audit.py` foi alterado neste bloco.
- Filtro: só `campaign_id` (o único que o contrato real oferece); paginação: `cursor` é
  aceito mas `next_cursor` sempre `null` -- o próprio backend documenta isso como "sem
  fabricar paginação que não existe" (achado 3/15). Nenhum controle de paginação foi
  construído na Web, pela mesma razão.
- Nenhum drift de contrato encontrado neste bloco (campos do `AuditEventResponse` real já
  batiam exatamente com o schema `AuditEvent` do contrato).
- Web: **nenhuma UI de auditoria existia** em `web/src` do CURRENT -- primeira leitura da
  trilha pela Web.

### O que foi construído (comportamento portado, frontend novo)

- Nova página `/audit` (`web/src/app/(app)/(authenticated)/audit/page.tsx`) -- lista real
  de `GET /audit-events`, ordenada mais-recente-primeiro (transformação de exibição no
  cliente só; o backend real devolve ordem cronológica ascendente), filtro por
  `campaign_id` (único filtro real do contrato), exibindo ação, tipo de ator
  (Usuário/Sistema/IA/Provedor externo), ator, alvo, decisão de política quando presente,
  e a evidência real (JSON bruto) quando o backend a devolve -- nunca escondida.
- Item de navegação "Auditoria" adicionado a `AppShell.tsx` (nenhum teste dependia da
  contagem/ordem exata dos itens de navegação -- confirmado por busca antes da mudança).
- Nenhum arquivo de `backend/` foi alterado neste bloco.

### Testes

- Novo: `web/tests/audit-page.test.tsx` -- 3 casos (estado vazio, lista eventos reais
  mais-recente-primeiro mostrando evidência, filtro por `campaign_id` via UI). Todos
  verdes.
- Comando: `npm run test -- --run` → **19 arquivos, 63 testes, 0 failures** (antes desta
  sessão: 18/60; +1 arquivo, +3 testes).
- `npm run typecheck`, `npm run lint`, `npm run contracts:check` → OK; `npm run
  boundary:check` → **63 arquivos** (antes 61) → OK.
- Backend regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **526 passed, 58
  subtests passed** (idêntico ao baseline -- nenhum arquivo de backend alterado).
- E2E cross-stack novo: `web/e2e/audit-trail.spec.ts`, dois cenários -- uma ação real de
  outro WP já reconciliado (kill switch, WP-08, escolhido por não precisar de fila de
  aprovação nem de um segundo usuário) gera um evento real, e a tela `/audit` real mostra
  esse evento com sua evidência real (`{"scope": "TENANT", ...}`); filtro por campanha via
  a UI real confirma que `GET /audit-events?campaign_id=...` só devolve eventos daquela
  campanha. `npx playwright test --config=playwright.session.config.ts` (com
  `audit-trail.spec.ts` incluído em `testMatch`) → **23 passed** (21 pré-existentes + 2
  novos), 0 failures.

### Pendências reais deste bloco (não escondidas)

- FM QA Engineer formal: pendente (ressalva histórica).
- Sem paginação real na Web -- reflete honestamente a mesma limitação já documentada no
  backend (`next_cursor` sempre `null`); se o volume real de eventos crescer, isso precisa
  de uma paginação real no backend primeiro, não fabricada na Web.

## WP-11 — Métricas honestas

**Estado:** `IMPLEMENTADO E TESTADO NESTA SESSÃO` (unit + component + backend regression +
E2E cross-stack). Este é o último WP da sequência WP-06→WP-11 explicitamente autorizada
para a Fase 2 desta missão. FM QA Engineer formal ainda pendente (ressalva histórica).

### CURRENT antes deste bloco

- Backend: `GET /campaigns/{campaignId}/insights` (`routes_campaigns.py::get_insights`)
  **já existia** em PR#5/main -- um placeholder honesto, documentado no próprio código:
  "No analytics layer implemented yet in campaia_core; this is an honest placeholder, not
  fabricated data." Sempre devolve `points: []` (nenhuma camada de analytics real existe
  em `campaia_core`) e um campo `note` com esse texto. Os parâmetros `from`/`to` são
  validados (data ISO) mas não usados no resultado ainda -- documentado no próprio backend
  como achado conhecido (achado 14). Nenhum arquivo de `campaia_core`/
  `api/routes_campaigns.py` foi alterado neste bloco.
- **Drift de contrato encontrado e corrigido (achado 15, aditivo):** `InsightSeriesResponse.
  model_dump_json()` real sempre inclui o campo `note` -- confirmado por execução direta
  nesta sessão (`python3 -c "from api.models import InsightSeriesResponse; ..."` →
  `{"campaign_id":"c1","points":[],"last_synced_at":null,"note":"test note"}`). O schema
  `InsightSeries` do contrato (`contracts/bff-openapi.yaml`) nunca declarava esse campo.
  Corrigido adicionando `note: { type: string }` ao schema, sem qualquer mudança de
  comportamento do backend. `npm run contracts:generate` + `npm run contracts:check` →
  `OK: ... esta em sincronia`.
- Web: **nenhuma UI de métricas existia** em `web/src` do CURRENT -- primeira leitura de
  insights pela Web.
- PR#6 (`origin/feat/campaia-v1-complete-saas`) tinha uma seção "Métricas" na página de
  detalhe de campanha (Server Component, `getServerInsights` em `lib/session.ts`),
  mostrando a lista de pontos quando presente, ou o `note` real quando `points` vem vazio
  -- mesmo comportamento honesto do backend, mas construído sobre a arquitetura de Server
  Components da PR#6 (fora de escopo desta reconciliação: "PORTAR COMPORTAMENTO, NÃO
  FRONTEND/ARQUITETURA").

### O que foi construído (comportamento portado, frontend novo sobre a arquitetura PR#5)

- Novo componente `InsightsPanel` (`web/src/components/InsightsPanel.tsx`) -- Client
  Component (`"use client"`, `useEffect` + `useState`, mesmo padrão de `CapabilitiesPanel`/
  `AuditPage` desta reconciliação, não o padrão Server Component da PR#6), busca `GET
  /campaigns/{id}/insights` ao montar. Quando `points` tem itens, lista cada ponto (data,
  canal, impressões, cliques, conversões, CPA quando presente). Quando `points` vem vazio
  (sempre, hoje), mostra o `note` real devolvido pelo backend -- nunca um gráfico, nunca um
  placeholder genérico da Web, nunca um número inventado.
- `InsightsPanel` adicionado à página de detalhe de campanha (`campaigns/[campaignId]/
  page.tsx`), abaixo do `KillSwitchPanel` de escopo CAMPAIGN.
- `InsightSeries` exportado em `web/src/contracts/types.ts`.
- Nenhum arquivo de `backend/` foi alterado neste bloco (além do contrato, que é
  documentação, não código de execução).

### Testes

- Novo: `web/tests/insights-panel.test.tsx` -- 3 casos (nota honesta quando `points` vazio
  -- e confirma que nenhuma `<ul>`/lista é renderizada nesse caso --, lista pontos reais
  quando o backend devolve dados, erro honesto quando `GET /insights` falha). Todos
  verdes.
- Comando: `npm run test -- --run` → **20 arquivos, 66 testes, 0 failures** (antes desta
  sessão: 19/63; +1 arquivo, +3 testes).
- `npm run typecheck`, `npm run lint`, `npm run contracts:check` → OK; `npm run
  boundary:check` → **65 arquivos** (antes 63) → OK.
- Backend regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **526 passed, 58
  subtests passed** (idêntico ao baseline -- nenhum arquivo de comportamento de backend
  alterado, só o contrato).
- E2E cross-stack novo: `web/e2e/insights-honesty.spec.ts`, um cenário -- cria uma
  campanha real via UI (sem nenhum evento de analytics jamais sincronizado para ela, por
  construção), navega para o detalhe da campanha, confirma que `GET /campaigns/{id}/
  insights` real devolve `points: []` e um `note` não vazio, e que a tela mostra
  literalmente esse `note` (nunca um placeholder da Web, nunca dado fabricado).
  `npx playwright test --config=playwright.session.config.ts` (com
  `insights-honesty.spec.ts` incluído em `testMatch`) → **24 passed** (23 pré-existentes +
  1 novo), 0 failures.

### Pendências reais deste bloco (não escondidas)

- FM QA Engineer formal: pendente (ressalva histórica).
- Não há camada de analytics real em `campaia_core` -- `points` continuará vazio até que
  essa camada exista de fato (integração com providers reais). A Web não fabrica dados
  para preencher essa lacuna; apenas reflete honestamente o `note` real do backend, e já
  sabe listar pontos reais assim que existirem.
- Parâmetros `from`/`to` continuam validados mas não usados no resultado (achado 14,
  já documentado no próprio backend) -- não alterado neste bloco, pois é comportamento de
  backend fora do escopo desta reconciliação de Web.

### Fechamento da sequência WP-06→WP-11

Com WP-11 concluído, a sequência explicitamente autorizada para a Fase 2 desta missão
("COMECE A FASE 2 PELO WP-06... não espere nova autorização para WP-06→WP-11 dentro desta
missão") está completa: WP-06 (orçamento), WP-07 (autonomia), WP-08 (kill switch), WP-09
(capacidades), WP-10 (auditoria), WP-11 (métricas honestas) -- todos com comportamento
reconciliado, testes unit/component, regressão de backend, E2E cross-stack real, evidência
registrada e commit local atômico, árvore de trabalho limpa após cada bloco. Próximos
passos (Fase 3 em diante) permanecem conforme o PROMPT MESTRE original: mineração da PR#6
por correções técnicas ainda válidas (incluindo os dois achados cross-cutting já
levantados e deliberadamente não corrigidos nesta Fase 2 -- a lacuna de consumo de
`ApprovalRequest.status`, achado do WP-07, e o descasamento do seed de capacidades,
achado do WP-09), Fase 4 (gaps internos), Fase 5 (classificação final) e a PR final de
reconciliação (nunca mesclada).

## FASE 3 — Mineração técnica da PR#6

Autorização explícita do Diretor (Fábio Aluizio da Silva, 26/09/2026) para prosseguir das
Fases 3, 4 e 5 sem nova autorização entre blocos puramente técnicos ("REPRODUZIR →
CLASSIFICAR → CORRIGIR → TESTAR → DOCUMENTAR → COMMITAR", parar apenas para decisão
humana genuína, credencial/aprovação/infraestrutura externa, risco arquitetural não
autorizado, produção, merge ou deploy).

### Item 1 — Consumo de approvals (achado 19)

**Status:** `FIXED`.

**CURRENT evidence (reproduzido por execução real, ANTES da correção):**

```
first patch: 202
second patch (same approval reused): 202 {...daily_cap: 600...}
approval status after reuse: APPROVED
```

Script real executado nesta sessão (backend Starlette real, `TestClient`, sem mock):
propor `BUDGET_CHANGE`, aprovar, aplicar uma vez (`PATCH /campaigns/{id}/budget` →
`202`), e então reaproveitar o MESMO `approval_id` com uma Idempotency-Key NOVA -- o
backend aceitava (`202` de novo, orçamento mudando pela segunda vez) e
`approval.status` permanecia `APPROVED` para sempre. Reproduzido de forma idêntica para
`PUT /autonomy` (`AUTONOMY_CHANGE`). `POST /campaigns/{id}/publish` (`PUBLISH`) nunca foi
diretamente explorável pelo mesmo vetor porque a máquina de estados da campanha já o
protegia incidentalmente (uma campanha não volta sozinha para `APPROVED` depois de
`ACTIVE`), mas apresentava a mesma lacuna de modelo (a aprovação em si nunca era marcada
como usada).

**Causa raiz:** `ApprovalRequest.status` (`api/repositories.py`) só transicionava para
`REJECTED`/`CHANGES_REQUESTED`/`APPROVED` (`api/routes_approvals.py::decide_approval`) --
nunca para um estado terminal de "já usada para aplicar a mudança real". Os três
handlers que consomem uma aprovação (`patch_budget`, `publish_campaign`,
`put_autonomy` em `api/routes_campaigns.py`/`api/routes_autonomy.py`) checavam apenas
`approval.status == "APPROVED"`, sem nunca escrever de volta.

**Ação (correção na camada autoritativa, não só na UI):**

- Novo estado terminal `APPLIED` adicionado ao enum de `ApprovalRequest.status`
  (`api/repositories.py`) e ao schema `ApprovalRequest.status` do contrato
  (`contracts/bff-openapi.yaml`) -- aditivo, nenhum valor existente removido/renomeado;
  `npm run contracts:generate` + `npm run contracts:check` → `OK: ... em sincronia`.
- `patch_budget`, `publish_campaign` e `put_autonomy` passam a marcar
  `approval.status = "APPLIED"` logo após a mutação real ter sido efetivamente aplicada
  (dentro do bloco que só roda para uma Idempotency-Key genuinamente nova).
- **Idempotência preservada (não quebra replay legítimo):** o gate de replay por
  Idempotency-Key (`state.idempotency.get(...)`) foi movido para ANTES da checagem de
  `approval.status` nos três handlers -- do contrário, repetir a MESMA Idempotency-Key
  (replay legítimo, ex.: cliente retransmitindo por timeout de rede) seria incorretamente
  rejeitado como "aprovação já usada", já que a primeira chamada bem-sucedida já teria
  marcado a aprovação como `APPLIED`. Uma tentativa NOVA (Idempotency-Key diferente)
  reaproveitando o mesmo `approval_id` continua caindo nas checagens normalmente e é
  corretamente recusada com `403 APPROVAL_REQUIRED`.
- Auditoria: nenhuma mudança -- os eventos `BUDGET_CHANGE`/`AUTONOMY_CHANGE`/
  `CAMPAIGN_PUBLISH` já eram registrados por `state.audit.append(...)` como antes;
  `APPLIED` só afeta a própria `ApprovalRequest`, nunca o audit trail.
- Aprovações históricas: nenhuma migração necessária -- o repositório em memória/tabela
  não tem registros pré-existentes reais fora desta sessão de testes; uma aprovação
  histórica com `status == "APPROVED"` continua válida para UM uso (o comportamento
  correto), só deixa de ser reutilizável depois de efetivamente consumida.

**Teste (verificação real, execução direta e regressão automatizada):**

- Reprodução manual confirmada por execução real (scripts Python ad-hoc contra
  `TestClient`, antes e depois da correção) para `BUDGET_CHANGE`, `AUTONOMY_CHANGE` e
  `PUBLISH`: reuso com Idempotency-Key nova → `403 APPROVAL_REQUIRED` após a correção;
  replay com a MESMA Idempotency-Key → resultado original preservado (`202`/`200`, sem
  reexecutar a mutação nem reavaliar a aprovação).
- Novo `backend/tests_api/test_approval_consumption.py` -- 6 testes: para cada um dos 3
  kinds (`BUDGET_CHANGE`, `AUTONOMY_CHANGE`, `PUBLISH`), (a) uma segunda tentativa com
  Idempotency-Key nova reaproveitando a aprovação já usada é recusada com
  `403 APPROVAL_REQUIRED` e o estado real (orçamento/nível/campanha) não muda pela
  segunda vez, e (b) repetir a MESMA Idempotency-Key continua devolvendo o resultado
  original (replay idempotente preservado). Todos verdes.
- Regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **532 passed, 58 subtests
  passed** (526 pré-existentes + 6 novos, 0 failures, 0 skips).
- E2E cross-stack novo: `web/e2e/approval-consumption.spec.ts` -- fluxo completo real
  pela UI (propor → aprovar por um segundo usuário real do mesmo tenant → aplicar,
  orçamento real mudando de 500 para 600), seguido de uma tentativa REAL de reuso da
  mesma aprovação direto contra o backend real (`page.request.patch`, sessão/CSRF/
  step-up reais, Idempotency-Key nova) -- confirma `403 APPROVAL_REQUIRED` e que o
  orçamento real não mudou pela segunda vez. `testMatch` de
  `playwright.session.config.ts` estendido para incluir este spec.
  `npx playwright test --config=playwright.session.config.ts` → **25 passed** (24
  pré-existentes + 1 novo), 0 failures.
- `npm run typecheck`, `npm run lint`, `npm run contracts:check`, `npm run
  boundary:check` (65 arquivos) → todos OK. Nenhum arquivo de Web precisou de mudança
  de comportamento: `AutonomyPanel.tsx`/`BudgetPanel.tsx` já filtravam
  `pickRelevant()` por `status === "PENDING" || status === "APPROVED"` -- uma aprovação
  `APPLIED` já cai fora desse filtro automaticamente, sem nenhuma mudança de código Web.

**Observação sobre o achado histórico do WP-07:** o workaround documentado no E2E de
WP-07 (`web/e2e/autonomy-level.spec.ts`, usar dois tenants diferentes para o cenário
feliz e o cenário negativo, para evitar a aprovação obsoleta sendo redescoberta pelo
`pickRelevant()`) deixou de ser estritamente necessário agora que a aprovação é marcada
`APPLIED` após o uso -- mas foi deliberadamente mantido como está nesta Fase 3 (o teste
já passa, e simplificá-lo é uma limpeza cosmética sem valor de reconciliação, fora do
escopo desta correção pontual).

**Commits:** `892fb22` (fix domínio + contrato, APPLIED aditivo), `4be6399` (fix backend,
consumo real nos 3 handlers + regressão), `3ba4f37` (test e2e cross-stack).

### Item 2 — Capability Registry / Provider Mismatch (achado 20)

**Status:** `FIXED`.

**CURRENT evidence (reproduzido por execução real, ANTES da correção):**

```
connection provider: GOOGLE_ADS  api_version: sim-1
GET /connections/{id}/capabilities →
  PUBLISH:GOOGLE_ADS  supported=false  verified_at=<agora, fabricado>
  PUBLISH:META_ADS    supported=false  verified_at=<agora, fabricado>
```

Script real (`TestClient`, sem mock) contra uma `Connection` real criada com
`provider="GOOGLE_ADS"`: `GET /connections/{id}/capabilities` sempre devolvia
`supported: false` para as duas capacidades testadas, e um `verified_at` igual ao
instante da própria chamada -- mesmo nunca tendo verificado nada de fato. **Ao mesmo
tempo**, no MESMO backend, `POST /campaigns/{id}/publish` publica com sucesso para essa
mesma conexão via `ProviderSimulator` (confirmado pelos testes já verdes
`TestHappyPathFullPublish`/`session-protocol.spec.ts` teste M) -- as duas rotas
respondiam perguntas inconsistentes sobre o mesmo fato real.

**Causa raiz:** `CapabilityRegistry` (`campaia_core/infra.py`) é indexado por
`(provider, capability_key, country, api_version)`, onde `provider` sempre significou
"qual conector de execução realmente atende esta capacidade" --
`routes_campaigns.py::validate_campaign` já consulta esse mesmo registro com o literal
hardcoded `"SIMULATOR"`, independente da conta OAuth escolhida, porque hoje toda
publicação real passa pelo `ProviderSimulator` (nenhum adaptador REST real existe para
GOOGLE_ADS/META/WHATSAPP -- confirmado pelo Capability Matrix histórico da PR#6,
`docs/08_CAPABILITY_MATRIX.md`, que classifica os três como "NÃO VERIFICADO").
`api/routes_connections.py::connection_capabilities`, porém, consultava o registro com
`conn.provider` -- o RÓTULO da conta OAuth conectada (contrato `Provider`:
`GOOGLE_ADS|META|WHATSAPP`) -- que nunca bate com a única chave seedada
(`"SIMULATOR"`). Um descasamento de indexação genuíno entre duas rotas que deveriam
concordar sobre o mesmo fato, não uma decisão deliberada de honestidade (como o WP-09
havia registrado inicialmente).

**Ação (correção na indexação, sem afirmar homologação externa):**

- `ConnectionMode` (`campaia_core/connectors.py`) é o eixo certo para esta pergunta --
  seu próprio docstring diz: "Estado real da conta. A interface mostra isto ao usuário,
  sem maquiagem." Toda `Connection` hoje tem `mode == ConnectionMode.SIMULATOR` (não
  existe fluxo real de OAuth nem adaptador de produção ainda). `connection_capabilities`
  passa a mapear o MODO da conexão (não o rótulo do provider OAuth) para a chave real do
  registro de capacidades -- a mesma que `validate_campaign` já usa e confia.
- **Sem fabricar homologação:** `supported: true` aqui nunca afirma que GOOGLE_ADS/
  META/WHATSAPP estão homologados externamente -- significa apenas "a plataforma sabe
  executar esta ação para esta conexão hoje" (via simulador), o que é verdade e já é a
  base real usada por `validate_campaign` para o mesmo gate de policy. O disclosure de
  que isto é simulado, não uma integração real verificada, já vem do próprio `notes` do
  registro ("Simulated capability, verified in-process at startup.") -- nunca escondido.
- Um modo de conexão sem nenhum adaptador real seedado (`TEST`/`PRODUCTION`, nenhum
  hoje) continua honestamente `supported: false`, sem nenhuma suposição.
- `verified_at` (`api/models.py::CapabilityResponse`, contrato `Capability.verified_at`)
  passa a ser nullable -- quando nenhum registro real de capacidade existe para o modo
  consultado, o backend nunca mais fabrica um "verificado agora"; `None` é o valor
  honesto. Aditivo (só amplia o tipo existente `string` para `[string, 'null']`).
  `npm run contracts:generate` + `npm run contracts:check` → `OK: ... em sincronia`.
- `evidence_url` continua sempre `None` (achado 7, inalterado -- nenhuma fonte real de
  evidência existe ainda).
- Nenhuma "decisão real de produto" foi necessária: a semântica já estava
  inequivocamente determinada pelo comportamento existente (`validate_campaign` já
  confiava nesta mesma capacidade "SIMULATOR" para o gate real de publicação) e pelas
  normas do próprio domínio (`ConnectionMode` já existia com exatamente este propósito
  documentado). Não foi preciso introduzir um novo estado tipo
  `SUPPORTED_BY_IMPLEMENTATION`/`UNVERIFIED_EXTERNALLY` -- o par `supported` + `notes`
  já existente no domínio cobre a mesma distinção honestamente.

**Teste (verificação real, execução direta e regressão automatizada):**

- Reprodução manual confirmada por execução real (scripts Python ad-hoc contra
  `TestClient`, antes e depois da correção): conexão real `SIMULATOR` → `supported:
  true` + `verified_at` real + `notes` disclosando simulação; conexão real `PRODUCTION`
  (sem adaptador seedado) → `supported: false` + `verified_at: null`, nunca fabricado.
- Novo `backend/tests_api/test_capability_registry_provider_mapping.py` -- 3 testes:
  conexão `SIMULATOR` mostra a mesma capacidade que `validate_campaign` usa
  internamente (incluindo o disclosure "Simulated" e `evidence_url: None`); conexão
  `PRODUCTION` sem capacidade seedada nunca fabrica `supported`/`verified_at`; as duas
  rotas (`GET /connections/{id}/capabilities` e o gate interno de
  `validate_campaign`) concordam sobre o mesmo fato real. Todos verdes.
- Regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **535 passed, 58 subtests
  passed** (532 pré-existentes + 3 novos, 0 failures, 0 skips). Nenhum teste
  pré-existente assumia o comportamento antigo (nenhuma regressão).
- E2E cross-stack `web/e2e/capabilities.spec.ts` **atualizado** (não um novo arquivo):
  o comentário e as asserções do WP-09 documentavam o comportamento antigo como
  "honesto por acidente" -- reescrito para refletir e verificar o comportamento
  corrigido (uma conexão real recém-criada mostra `supported: true`, `verified_at`
  real, `evidence_url: null` e o disclosure "Simulated capability" visível na UI).
  `npx playwright test --config=playwright.session.config.ts` → **25 passed** (0 novos
  specs, 1 atualizado), 0 failures.
- `web/tests/capabilities-panel.test.tsx` (WP-09, mock de rede) não precisou de
  mudança -- já testava os casos `supported: true` e `supported: false` a partir de
  dados mockados, independentes do comportamento real do backend.
- `npm run typecheck`, `npm run lint`, `npm run contracts:check`, `npm run
  boundary:check` (65 arquivos) → todos OK. `CapabilitiesPanel.tsx` já renderizava
  `verified_at` nulo honestamente (`cap.verified_at ? ... : "—"`) -- nenhuma mudança de
  código Web foi necessária além do teste E2E.

**Commits:** `8ed6403` (fix contrato, verified_at nullable), `e78ab14` (fix backend,
indexação por ConnectionMode + regressão), `24ff50d` (test e2e atualizado).

### Item 3 — Audit Pagination (achado 21)

**Status:** `FIXED`.

**CURRENT evidence (reproduzido por execução real, ANTES da correção):**

```
GET /audit-events?cursor=bogus-cursor →
  200 OK, devolve a lista INTEIRA de eventos (cursor desconhecido silenciosamente
  ignorado, nunca sinaliza erro)
```

O contrato (`contracts/bff-openapi.yaml`) sempre prometeu paginação opaca por
`cursor`/`next_cursor`, mas `api/routes_audit.py::list_audit_events` sempre devolvia
`next_cursor: null` e a lista inteira do tenant de uma vez -- um stub honesto (nunca
fabricava uma página que não existia, achado 3/15 original), porém incompleto: um
`cursor` desconhecido era silenciosamente ignorado (devolvia a página inteira de novo)
em vez de falhar de forma controlada, como este backend já faz para qualquer entrada do
cliente que não pode ser verificada no servidor.

**Avaliação da implementação histórica da PR#6:** `origin/feat/campaia-v1-complete-saas`
implementou paginação real (Etapa A9, commit `6536b5e` lá): página fixa de 50, cursor
opaco = id do último evento da página anterior, `audit_event_id` como desempate estável
para `timestamp`, cursor desconhecido → `422 VALIDATION_FAILED`. Avaliada e considerada
correta e bem alinhada às convenções do CURRENT (mesmo padrão fail-closed, mesmo
contrato já declarado) -- adaptada aqui sem cópia cega: reconstruída sobre o CURRENT
(`api/routes_audit.py`), reutilizando os nomes de campo e a convenção `ApiError` já
usados neste módulo.

**Ação:**

- `api/routes_audit.py::list_audit_events` -- página fixa de 50 (`_PAGE_SIZE`, não um
  query param: o contrato nunca declarou `limit`); `cursor` é o id do último evento já
  devolvido; um cursor desconhecido/obsoleto falha com `422 VALIDATION_FAILED` em vez de
  silenciosamente reiniciar a paginação; desempate estável por `(timestamp,
  audit_event_id)` (o contador de ids é monotônico e compartilhado por todo tipo de
  entidade neste processo -- `api/repositories.py::new_id`).
- Nenhuma mudança de contrato foi necessária -- `cursor`/`next_cursor` já estavam
  declarados; nenhum drift novo encontrado (`npm run contracts:check` → OK, sem
  mudanças).
- **Web (`/audit`, WP-10) atualizada para seguir a paginação real**: a página
  documentava e assumia "next_cursor sempre null" -- agora que o backend pagina de
  verdade, a tela ganhou um botão "Carregar mais" que acrescenta a próxima página real
  à lista já exibida (nunca substitui, nunca fabrica um total). Sem essa mudança, um
  tenant com mais de 50 eventos reais passaria a ter eventos silenciosamente ocultos na
  Web -- a correção do backend por si só teria introduzido uma nova lacuna de
  honestidade na Web.

**Teste (verificação real, execução direta e regressão automatizada):**

- Reprodução manual confirmada por execução real (script Python ad-hoc contra
  `TestClient`): 120 eventos reais criados, percorridas todas as páginas via cursor real
  → 120 eventos únicos coletados, 0 lacunas, 0 duplicatas; cursor desconhecido → `422
  VALIDATION_FAILED` após a correção (antes: `200`, página 1 completa, sem sinalizar
  nada).
- Novo `backend/tests_api/test_audit_pagination.py` -- 4 testes: percorrer todas as
  páginas via cursor real devolve cada evento exatamente uma vez (sem lacunas, sem
  duplicatas); cursor desconhecido falha fechado; última página reporta `next_cursor:
  null`; filtro por `campaign_id` continua funcionando corretamente através da
  paginação. Todos verdes.
- Regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **539 passed, 58 subtests
  passed** (535 pré-existentes + 4 novos, 0 failures). Nenhum teste pré-existente
  assumia a lista completa sem paginação (nenhum tinha mais de 50 eventos reais para o
  mesmo tenant).
- `web/tests/audit-page.test.tsx` -- 1 novo teste (`carrega mais eventos via
  next_cursor real...`), verificando que "Carregar mais" aparece quando `next_cursor`
  não é nulo, acrescenta a próxima página sem substituir a anterior, e desaparece
  quando a última página reporta `next_cursor: null`. `npm run test -- --run` → **20
  arquivos, 67 testes, 0 failures** (antes desta correção: 20/66; +1 teste).
- E2E cross-stack novo: `web/e2e/audit-pagination.spec.ts` -- cria 55 eventos reais
  (tenant B, isolado dos specs que já checam `/audit-events` sem cursor para o tenant
  A), confirma diretamente contra o backend real que a paginação por cursor não perde
  nem duplica eventos ao longo de múltiplas páginas, confirma o cursor desconhecido
  falhando fechado, e confirma que a tela `/audit` real segue "Carregar mais" até
  esgotar as páginas, mostrando exatamente os eventos reais coletados (nunca menos,
  nunca mais). `testMatch` de `playwright.session.config.ts` estendido.
  `npx playwright test --config=playwright.session.config.ts` → **26 passed** (25
  pré-existentes + 1 novo), 0 failures -- incluindo `audit-trail.spec.ts` e
  `kill-switch.spec.ts`, que continuam corretos porque o tenant A nunca ultrapassa 50
  eventos reais nesta suíte (isolamento deliberado do novo spec no tenant B).
- `npm run typecheck`, `npm run lint`, `npm run contracts:check`, `npm run
  boundary:check` (65 arquivos) → todos OK.

**Commits:** `e67cc34` (feat backend, paginação real + regressão), `d396e32` (feat web,
Carregar mais), `688bc9f` (test e2e, sem lacunas/duplicatas).

### Item 4 — Dependency / Security Fixes (achado 22)

**Status:** FIXED (dois achados reais e verificados) + subitens classificados abaixo.

**Instrução da missão:** "NÃO assuma que os CVEs históricos existem. Execute auditoria
real contra as versões atuais." — cumprida por execução real de `pip-audit` contra o
PyPI Advisory Database, nunca por presunção a partir do histórico da PR#6.

**4.a — CVEs de dependências (FIXED):**

- `pip install pip-audit --break-system-packages -q` seguido de
  `pip-audit -r requirements.txt --desc` (execução real, nesta sessão) confirmou **5
  CVEs reais e verificáveis** em `starlette==1.0.0`: PYSEC-2026-161 (Host header →
  desalinhamento de `request.url.path`, corrigido em 1.0.1), PYSEC-2026-2280
  (`HTTPEndpoint` despacha métodos não-padrão via `getattr` irrestrito, corrigido em
  1.1.0), PYSEC-2026-2281 (`StaticFiles` vaza NTLMv2 via caminho UNC do Windows em
  `os.path.realpath`, corrigido em 1.1.0), PYSEC-2026-248 (caminho sem `/` inicial desloca
  a autoridade da URL, falsificando `request.url.hostname`, corrigido em 1.3.0),
  PYSEC-2026-249 (`request.form()` ignora `max_fields`/`max_part_size` para
  `application/x-www-form-urlencoded`, DoS por corpo grande/fragmentado, corrigido em
  1.3.1).
- Inspeção real do código do CURRENT confirmou que nenhum dos 5 é hoje explorável aqui:
  não existe uso de `HTTPEndpoint`, não existe chamada a `request.form()`, e a checagem
  de CSRF/origin usa `Origin`/`Referer` diretamente (`api/session.py::extract_request_origin`),
  nunca `request.url`. Corrigido por precaução — não por exploração confirmada — e porque a
  PR#6 já fixava exatamente essa mesma versão corrigida (`starlette==1.3.1`).
- **Ação:** `backend/requirements.txt`: `starlette==1.0.0` → `starlette==1.3.1`.
- **Teste:** regressão completa `PYTHONPATH=. python3 -m pytest -q` → **539 passed, 58
  subtests passed**, 0 failures (nenhuma quebra pela troca de versão); `pip-audit -r
  requirements.txt` re-executado após o bump → limpo, 0 vulnerabilidades conhecidas em
  qualquer dependência declarada. Um novo aviso não relacionado a segurança apareceu
  (`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`) —
  registrado como item futuro de limpeza de tooling de teste, fora de escopo desta
  correção de CVE.
- **Commit:** `1f4c0e5`.

**4.b — OAuth audit state leak (achado 22, FIXED):** ver detalhamento completo já
registrado antes deste bloco ser fechado — `api/routes_connections.py::oauth_start`
armazenava o valor anti-replay `state` no `details` do evento `OAUTH_START` de auditoria;
a PR#6 já havia corrigido exatamente este ponto (commit `9a0e6b3`) mas sem teste de
regressão associado ("No test asserted this field"). Corrigido aqui da mesma forma, desta
vez com regressão real: novo `backend/tests_api/test_oauth_audit_no_state_leak.py` (1
teste, verifica tanto a ausência da chave `"state"` quanto a ausência do valor literal
devolvido em qualquer valor serializado da evidência). Regressão completa após esta
correção: **540 passed, 58 subtests passed** (539 + 1 novo). **Commit:** `9907800`.

**Demais subitens do checklist da missão para o Item 4 — classificados por evidência real,
não por suposição:**

- **Host header:** SUPERADA — coberta pelo upgrade do Starlette (PYSEC-2026-248/161, que
  tratavam exatamente de desalinhamento de host/autoridade via `request.url`) combinada
  com o fato, já confirmado por leitura de código, de que o CURRENT nunca usa
  `request.url.hostname`/`request.url.path` para decisão de segurança — a checagem de
  origem usa `Origin`/`Referer` explicitamente.
- **CSRF:** SUPERADA — já robusta no CURRENT (token de CSRF por sessão, obrigatório em
  toda mutação, cheque de `Origin`/`Referer`), parte da arquitetura AUTH/SESSION
  classificada "A — Manter CURRENT" desde a Fase 1; nenhuma lacuna nova encontrada nesta
  auditoria.
- **Dependências:** FIXED — ver 4.a acima; `pip-audit` limpo após o bump.
- **Secrets:** NOT_REPRODUCED — varredura real (grep completo por padrões de chave/senha/
  token em `backend/` e `web/src/`) não encontrou nenhum secret hardcoded; toda credencial
  já vem de variável de ambiente (`ASAAS_API_KEY`, `GEMINI_API_KEY`); campos de secret já
  usam `repr=False` (`AsaasConfig.api_key`, provider Gemini); `_SECRET_PATTERNS` em
  `campaia_core/ai_gateway.py` já redige valores sensíveis em log. Nada para corrigir.
- **Health endpoint:** tratado separadamente — ver **Item 5** abaixo (a checagem original
  de "ausência de health endpoint" listada sob dependências/segurança na missão é a mesma
  ausência que o Item 5, Health/Observability, endereça; evitando duplicar a correção
  aqui, o achado e a correção completa (achado 23) estão documentados no Item 5).
- **Negative auth tests / cross-tenant tests / contract boundary checks:** SUPERADA
  provisoriamente — a suíte atual (543 testes de backend após o Item 5, 26 specs E2E
  incluindo `session-protocol.spec.ts` casos A–M) já cobre extensivamente acesso anônimo,
  sessão malformada/expirada/revogada, CSRF, `Origin`/`Referer`, cross-tenant,
  cross-membership, negação de permissão, e `npm run boundary:check` passa limpo em 65
  arquivos. Esta classificação é preliminar e será **verificada rigorosamente item a
  item contra o inventário real de testes negativos da PR#6** no Item 6 (Testes da
  PR#6) desta mesma Fase, em vez de ser dada como definitiva aqui.

**Commits do Item 4:** `1f4c0e5` (fix deps, CVEs do Starlette), `9907800` (fix backend,
vazamento de state em auditoria OAuth + regressão).

### Item 5 — Health / Observability (achado 23)

**Status:** FIXED.

**FATO CONFIRMADO** por auditoria real (grep completo em `backend/api/main.py` — lista de
rotas — e em `campaia_core/`, antes de qualquer código ser escrito): nenhum endpoint de
health/liveness/readiness existia no CURRENT. `NÃO ENCONTRADO`, não presumido.

Uma implementação histórica equivalente foi localizada em
`refs/remotes/origin/feat/campaia-v1-complete-saas` (commit `84f9645`, "feat(api): add
GET /health liveness endpoint (P-A17)") e **avaliada antes de ser adaptada** — não
copiada às cegas: a mesma lógica (checar `Database.ping()` de verdade quando persistência
estiver configurada; sempre saudável em modo puro em memória, que não tem dependência
externa real) foi reescrita contra os nomes e imports reais do CURRENT
(`.deps.get_state`, `AppState.db`, `api/db.py::Database` — nenhum desses símbolos existia
daquela forma na branch histórica).

**Ação:**

- `api/db.py::Database.ping()` (novo) — executa `SELECT 1` real sob o lock já existente
  da conexão SQLite; nunca levanta exceção, devolve `False` em qualquer falha, conforme
  `docs/nova-fm/02-PADROES-DE-CONSTRUCAO-NOVA-FM.md` (linha 960): "Evitar health check que
  retorna sucesso mesmo quando dependência crítica está indisponível."
- `api/routes_health.py` (novo) — `GET /health`, deliberadamente **sem autenticação** e
  **fora de `contracts/bff-openapi.yaml`** (mesmo precedente já existente no projeto para
  endpoints de infraestrutura sem contrato client-facing: `/test-idp/*` é real porém não
  documentado no contrato BFF). `200 {"status": "ok"}` quando `AppState.db is None` (modo
  puro em memória, o padrão — nenhuma dependência externa a checar) ou quando o banco
  configurado responde de verdade; `503 {"status": "unavailable", "database":
  "unreachable"}` quando `Database.ping()` falha de verdade — nunca um 200 fabricado
  enquanto a única dependência real está fora do ar.
- `api/main.py` — rota registrada, com comentário explicando por que fica fora do
  contrato.
- Deliberadamente **não** foram adicionados logging estruturado, tracing ou métricas:
  nenhum consumidor real (dashboard, alerta, APM) foi identificado para esses dados nesta
  missão, e a instrução explícita da autorização é "não construir observabilidade
  fictícia" — um endpoint de liveness real e honesto é o mínimo operacional correto para
  o estágio atual; instrumentação adicional fica como `PENDÊNCIA` para quando um
  consumidor real existir.

**Teste:**

- `backend/tests_api/test_health.py` (novo, 3 casos): `200` em modo puro em memória; `200`
  com banco SQLite configurado e genuinamente alcançável; `503` com `Database.ping`
  patchado para `False` (prova que o endpoint não pode reportar sucesso com a dependência
  crítica indisponível).
- Regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **543 passed, 58 subtests
  passed** (540 pré-existentes + 3 novos, 0 failures).
- `npm run contracts:check` → OK, sem drift (`/health` é infra-only, fora do contrato por
  desenho, não precisa estar declarado). `npm run boundary:check` → OK, 65 arquivos, sem
  violação (rota é backend-only, nenhum código Web novo).

**Commit:** `0e808a2`.

### Item 6 — Testes da PR#6 (achado 24)

**Status:** FIXED (1 bug real encontrado e corrigido) + SUPERADA para o restante do
inventário comparado.

**Metodologia:** inventário completo de `backend/tests_api/*.py` e `web/e2e/*.spec.ts` na
PR#6 (`origin/feat/campaia-v1-complete-saas`, `3cc9e07b17815a9269d369c2ae25380a5d63790b`),
comparado nome a nome contra o CURRENT, distinguindo três categorias: (1) arquivos
idênticos já portados anteriormente (`test_errors_p19.py`, `test_smoke_endpoints.py`); (2)
arquivos com sobreposição parcial, onde só os casos realmente ausentes no CURRENT foram
avaliados para porte; (3) arquivos exclusivos da arquitetura OIDC superada (`test_oidc_unit.py`,
`test_auth_fail_closed.py`, `test_cross_origin.py`) — não portados, pois testam uma
arquitetura de autenticação que a Fase 1 já classificou "A — Manter CURRENT" (Google
Identity Platform + firebase-admin), e o CURRENT já tem cobertura equivalente ou superior
para os mesmos invariantes (`test_auth_session.py`, 44 casos: CORS/origin/referer, CSRF,
sessão expirada/revogada, sem fixture fora de test/dev, cross-tenant via sessão real,
nenhum secret vazado em resposta).

**Achados por arquivo:**

- `test_errors_p19.py`, `test_smoke_endpoints.py`: **idênticos** ao CURRENT (diff vazio) —
  já portados integralmente em trabalho anterior a esta Fase. Nenhuma ação.
- `test_persistence.py`: CURRENT tem **um teste a mais** que a PR#6
  (`test_duplicate_event_after_restart_is_still_rejected`), nada faltando. SUPERADA.
- `test_invariants.py`: CURRENT já tinha todos os casos da PR#6, **exceto um**
  (`test_other_tenant_cannot_delete_or_read_capabilities_of_first_tenants_real_connection`
  — resistência a enumeração para DELETE/GET capabilities de conexão de outro tenant).
  REPRODUZIDO antes de portar: CURRENT já se comporta corretamente (404, nunca 403); só
  faltava a regressão. **Portado** (adaptado aos nomes do CURRENT). Além disso, o CURRENT
  já tem mais casos que a PR#6 não tinha (isolamento por unidade de negócio). **Commit:**
  `5081839`.
- `test_connections_oauth.py` (CURRENT) × `test_oauth_complete.py` (PR#6): mesma cobertura
  em 6 dos 7 casos; faltava
  `test_replay_with_same_idempotency_key_does_not_create_a_second_connection`. Ao escrever
  esse teste antes de portar — REPRODUZIR primeiro, nunca presumir — a execução real
  revelou um **bug genuíno no CURRENT**, não apenas uma lacuna de cobertura: mesma classe
  de erro de ordenação já corrigida no achado 19 (idempotency-replay vs. mutação/consumo
  de recurso de uso único), desta vez em `oauth_callback` × `redeem_oauth_state`. Ver
  achado 24 detalhado abaixo. **Commit:** `1fd9616`.
- `web/e2e/{account,approvals,campaigns,dashboard,foundation,onboarding}.spec.ts` (PR#6):
  inspecionados — são todos specs de um estágio muito anterior do projeto ("shows the
  configuration notice when no BFF origin is configured, with no BFF network calls"),
  testes de placeholder sem nenhum cenário negativo/de segurança real. Nada para portar; a
  cobertura E2E de segurança do CURRENT (`session-protocol.spec.ts` casos A–M,
  `audit-trail.spec.ts`, `kill-switch.spec.ts`, `capabilities.spec.ts`,
  `approval-consumption.spec.ts`, `audit-pagination.spec.ts`) já excede em profundidade e
  realismo o que existia na PR#6 nesse nível.

**ACHADO 24 (bug real, REPRODUZIDO por execução real antes de qualquer código escrito):**
`POST /connections/oauth/callback` verificava `redeem_oauth_state` (que consome o `state`
de uso único) **antes** do curto-circuito de replay por Idempotency-Key. Reprodução real
confirmada nesta sessão: primeira chamada → `201` (Connection criada); segunda chamada com
a MESMA Idempotency-Key e o MESMO `state` (replay legítimo, ex.: cliente retransmitindo
após timeout) → `403 PERMISSION_DENIED` em vez do `201` original, porque o `state` já
havia sido consumido pela primeira chamada antes do gate de idempotência sequer rodar.
Mesma classe exata do achado 19.

**Ação:** `api/routes_connections.py::oauth_callback` — `state.idempotency.get(...)` agora
roda antes de `redeem_oauth_state`; em replay, devolve `existing.result` (o corpo real já
armazenado pela primeira execução) com `201`, nunca reexecuta a criação. Uma tentativa
NOVA com uma Idempotency-Key diferente reaproveitando o mesmo `state` continua caindo
corretamente no fail-closed de uso único (`test_state_is_single_use` permanece verde sem
alteração, pois usa chaves distintas).

**Teste:** novo
`test_replaying_the_same_idempotency_key_returns_the_original_connection` em
`test_connections_oauth.py` — confirma `201` idêntico nas duas chamadas e exatamente uma
Connection criada.

**Regressão completa:**

- `PYTHONPATH=. python3 -m pytest -q` → **545 passed, 58 subtests passed** (543
  pré-existentes + 2 novos — o teste de enumeração de Item 6 e o de replay do achado 24 —,
  0 failures).
- `npx playwright test --config=playwright.session.config.ts` → **26 passed**, 0 failures
  (nenhuma regressão no fluxo real de OAuth/onboarding nem em nenhum outro spec).
- Web: `npm run typecheck`, `npm run lint`, `npm run contracts:check`, `npm run
  boundary:check` (65 arquivos) → todos OK.

**Commits do Item 6:** `5081839` (test, porte do caso de enumeração cross-tenant),
`1fd9616` (fix + teste, achado 24 — reordenação do gate de replay no oauth_callback).

## FASE 3 — Encerramento (itens 1–6)

| ITEM | STATUS | EVIDÊNCIA NO CURRENT | AÇÃO | TESTE | COMMIT(S) |
|---|---|---|---|---|---|
| 1. Consumo de Approvals | FIXED | Aprovação podia ser reutilizada indefinidamente em budget/autonomy/publish (reprodução real) | Status `APPLIED` aditivo; idempotency-check movido antes do gate de approval em 3 handlers | 6 testes unit/integração + 1 E2E cross-stack | `892fb22`, `4be6399`, `3ba4f37`, `67b7aa6` |
| 2. Capability Registry | FIXED | `connection_capabilities` indexava por `conn.provider` (rótulo OAuth), nunca batendo com a chave real `"SIMULATOR"` já usada por `validate_campaign` | Mapeamento explícito `ConnectionMode -> capability provider`; nunca fabrica `supported=true` sem base real | 3 testes unit + E2E atualizado | `8ed6403`, `e78ab14`, `24ff50d`, `0f61460` |
| 3. Audit Pagination | FIXED | `/audit-events` sempre devolvia `next_cursor: null`, ignorando `cursor` | Paginação real por cursor (`_PAGE_SIZE=50`, cursor=id do último evento, cursor inválido → 422); Web ganhou "Carregar mais" para não ocultar eventos | 4 testes backend + 1 web + 1 E2E (55 eventos reais, sem lacunas/duplicatas) | `e67cc34`, `d396e32`, `688bc9f`, `ab63079` |
| 4. Dependências/Segurança | FIXED | 5 CVEs reais em `starlette==1.0.0` (via `pip-audit`); OAuth `state` vazando na auditoria (achado já conhecido da PR#6, sem regressão lá) | Bump para `starlette==1.3.1`; `state` removido do `details` do evento `OAUTH_START` | Regressão completa + 1 teste novo (vazamento de state) | `1f4c0e5`, `9907800` |
| 5. Health/Observability | FIXED | Nenhum endpoint de liveness existia (`NÃO ENCONTRADO`) | `GET /health` real, checa `Database.ping()` quando persistência configurada, nunca fabrica "saudável" | 3 testes novos | `0e808a2` |
| 6. Testes da PR#6 | FIXED | 1 lacuna de cobertura portada (enumeração cross-tenant); 1 bug real encontrado ao escrever teste antes de portar (achado 24, replay de OAuth) | Teste de enumeração portado; gate de replay reordenado no `oauth_callback` | 2 testes novos + regressão completa (545 testes) + E2E completo (26 specs) | `5081839`, `1fd9616` |

**Regressão final da Fase 3 (após os 6 itens):** `PYTHONPATH=. python3 -m pytest -q` →
**545 passed, 58 subtests passed**, 0 failures. `npx playwright test
--config=playwright.session.config.ts` → **26 passed**, 0 failures. Web: `typecheck`,
`lint`, `contracts:check`, `boundary:check` (65 arquivos) → todos OK. Árvore de trabalho
limpa (`git status --short` vazio) após cada commit.

Nenhum item exigiu classificação `HUMAN_DECISION` ou `EXTERNAL_BLOCKED` — todos os 6 itens
do checklist da Fase 3 foram tecnicamente resolvíveis dentro da autoridade já concedida,
sem mudança de contrato ambígua, sem infraestrutura externa e sem decisão de produto
pendente. Prosseguindo diretamente para a **Fase 4**, conforme a autorização explícita do
Diretor.

## FASE 4 — Lacunas internas

Autorização explícita do Diretor (26/09/2026) para prosseguir diretamente da Fase 3 para
a Fase 4 sem nova autorização entre correções puramente técnicas.

### Item A — Retomar campanha pausada (achados 25 e 26)

**Status:** FIXED.

**FATO CONFIRMADO** por leitura real do domínio antes de qualquer código ser escrito:
`campaia_core/states.py` já modelava e testava a transição `PAUSED -> ACTIVE`
(`TRANSITIONS[CampaignState.PAUSED]` já incluía `ACTIVE`; guarda dedicada
`_guard_resume`, que bloqueia apenas se `kill_switch_active`). Confirmado por grep real
em `backend/api/main.py`, `contracts/bff-openapi.yaml` e `web/src`: **nenhuma rota,
nenhum campo de contrato e nenhuma tela** expunham essa transição — `NÃO ENCONTRADO`,
não presumido. Este é exatamente o caso que a autorização do Diretor previu: "implemente
se o domínio já suporta e só falta exposição".

**Ação:**

- `contracts/bff-openapi.yaml`: novo `POST /campaigns/{campaignId}/resume` —
  `Idempotency-Key` + `X-Step-Up-Token` obrigatórios, `202` com `Campaign`, `409
  INVALID_STATE` se a campanha não estiver `PAUSED`.
- `backend/api/routes_campaigns.py::resume_campaign` — `Permission.CAMPAIGN_PUBLISH` +
  step-up (mesmo nível de cautela de `publish_campaign`, não o de
  `pause_campaign`/`CAMPAIGN_EDIT`, porque retomar volta a gerar gasto externo real).
  **Não exige um novo `approval_id`**: a guarda de domínio para esta transição específica
  (`_guard_resume`) só verifica `kill_switch_active`, nunca aprovação humana — diferente
  de `APPROVED -> PUBLISHING`. Inventar uma exigência de aprovação que o domínio não
  modela seria o erro oposto (mais rigoroso que o domínio autoriza); a rota segue
  exatamente o que a guarda real exige, nada mais.
- **Deliberadamente não foi adicionada nenhuma chamada de conector** para "reativar" o
  recurso externo: `AdsConnector` (`campaia_core/connectors.py`) só declara
  `publish`/`pause` — não existe `resume`/`unpause` no protocolo. Confirmado por grep
  real: a própria chamada `connector.pause(...)` que `pause_campaign` já faz é simbólica
  (`ProviderSimulator()` novo e descartado a cada chamada; `.paused` nunca é lido em
  nenhum outro lugar do código) — não há nenhum efeito real a espelhar. Definir o que uma
  "retomada" deveria significar para um adaptador real (nova chamada de API do provider?
  republicar? outra coisa?) é uma decisão de protocolo de conector/produto ainda
  pendente, deliberadamente **fora do escopo** desta exposição — não inventada aqui.
  Classificação: parte não implementada = `HUMAN_DECISION` implícita, documentada, não
  bloqueante (a exposição do domínio funciona integralmente sem ela, pois o CURRENT só
  tem o simulador).
- **UI**: nenhum botão de "retomar" foi adicionado. Achado, por inspeção real do
  frontend: `pause_campaign` em si **também não tem nenhuma UI própria hoje** (o único
  controle de pausa exposto na tela de campanha é o `KillSwitchPanel`, que usa o endpoint
  `/kill-switch`, não `/campaigns/{id}/pause`). Como não existe um lugar natural já
  existente para "religar" a esse novo endpoint, adicionar uma tela nova seria construir
  superfície de UI nova, não apenas conectar exposição já existente — fora do escopo
  mínimo deste item. Documentado como decisão consciente, não como lacuna esquecida.

**ACHADO 26 (bug real, REPRODUZIDO por execução real ao escrever o teste de replay do
novo endpoint):** ao espelhar a forma de `pause_campaign` para `resume_campaign`, a
execução real do teste de replay revelou que `pause_campaign` **já tinha o mesmo bug**:
`state.audit.append(...)` rodava **fora** do fecho protegido por
`idempotency.execute()`, portanto um replay legítimo da mesma Idempotency-Key contra uma
pausa que já tivera sucesso duplicava o evento `CAMPAIGN_PAUSE` na auditoria (confirmado
por execução real: duas chamadas com a mesma chave → dois eventos, antes da correção),
sem nenhuma mutação real correspondente na segunda chamada. Corrigido em ambos os
handlers (`pause_campaign` e o novo `resume_campaign`): `audit.append` movido para dentro
do fecho `_do_pause`/`_do_resume`, executado exatamente uma vez por operação real.

**Teste:**

- `backend/tests_api/test_campaign_resume.py` (novo, 7 casos): transição real
  PAUSED→ACTIVE; evento `CAMPAIGN_RESUME` registrado; step-up obrigatório (`403
  STEP_UP_REQUIRED`); Idempotency-Key obrigatória (`422`); rejeição quando a campanha não
  está `PAUSED` (`409 INVALID_STATE`); replay da mesma Idempotency-Key não duplica nem
  falha; isolamento cross-tenant com `404` (resistência a enumeração, nunca `403`).
- `backend/tests_api/test_invariants.py` — novo
  `test_repeating_a_successful_pause_key_does_not_duplicate_the_audit_event` (achado 26
  em `pause_campaign`): confirma que o teste pré-existente
  `test_repeating_pause_key_is_idempotent` nunca havia pego esse bug porque só exercitava
  `DRAFT` (falha nas duas chamadas, nunca chega a pausar de verdade).
- Regressão completa: `PYTHONPATH=. python3 -m pytest -q` → **553 passed, 58 subtests
  passed** (545 pré-existentes + 8 novos, 0 failures).
- E2E completo: `npx playwright test --config=playwright.session.config.ts` → **26
  passed**, 0 failures (nenhuma regressão em nenhum spec pré-existente pela mudança em
  `pause_campaign`).
- Web: `npm run typecheck`, `npm run lint`, `npm run contracts:check`, `npm run
  boundary:check` (65 arquivos) → todos OK.

**Commits:** `126fd60` (feat contrato), `5d9c48f` (feat backend + achado 26 + testes).

### Item B — Unidade de negócio (business unit)

**Status:** HUMAN_DECISION.

**FATO CONFIRMADO** por leitura real do código (`backend/api/state.py`,
`api/identity_directory.py`, `api/routes_campaigns.py`, `contracts/bff-openapi.yaml`,
`web/src/**`): `business_unit_id` existe **apenas como uma string livre carregada em
`TokenPrincipal`/`Membership`**, atribuída estaticamente pelo diretório de identidade de
desenvolvimento (`seed_dev_identity_directory()`, valores fixos `"bu-1"`/`"bu-2"`). Não
existe:

- nenhuma entidade `BusinessUnit` persistida (nenhum `BusinessUnitRepository`, nenhuma
  tabela, nenhum registro além da string solta);
- nenhum endpoint de API para criar, listar, renomear ou arquivar uma unidade de negócio
  (`grep` em `contracts/bff-openapi.yaml` só encontra `business_unit_id` como campo de
  *outros* recursos — `Me`, `Membership` — nunca como recurso próprio);
- nenhuma permissão dedicada no `Permission` enum (`campaia_core/permissions.py`) para
  gerenciar unidades de negócio (existe `MEMBER_MANAGE`, `BRAND_MANAGE`, etc., mas nada
  equivalente a `BUSINESS_UNIT_MANAGE`);
- nenhuma tela de administração no Web (`business_unit_id` só aparece em **modo leitura**,
  exibindo a unidade da sessão atual em `TenantSwitcher.tsx` e na página de
  configurações — nunca um formulário de criação/seleção).

Um `OWNER` hoje pode passar **qualquer string** como `business_unit_id` ao criar uma
campanha (`principal.business_unit_ids is None` para `OWNER`, ou seja, sem nenhuma
restrição de pertencimento) — não porque exista uma lista real de unidades válidas contra
a qual validar, mas porque não há validação nenhuma para esse papel. Implementar um CRUD
real exigiria decidir, sem ambiguidade suficiente no CURRENT hoje:

1. Quais campos uma unidade de negócio tem além do id (nome de exibição? descrição?
   endereço/CNPJ próprio, se distinto do tenant?).
2. Quem tem autoridade para criar/renomear/arquivar uma unidade — só `OWNER`, ou também
   `ADMIN` (papel que existe no `Role` enum mas não tem uso real hoje)?
3. Um usuário pode pertencer a mais de uma unidade de negócio dentro do MESMO tenant
   simultaneamente, ou a associação continua 1:1 por vínculo (como hoje)?
4. As unidades "bu-1"/"bu-2" seedadas precisam de uma migração para virarem registros
   reais, e as memberships existentes precisam ganhar uma referência real (FK) a elas?
5. Existe alguma hierarquia entre unidades de negócio (ex.: sub-unidades), ou é sempre uma
   lista plana por tenant?

Nenhuma dessas perguntas tem resposta inequívoca no código, nos contratos ou na
documentação normativa (`docs/nova-fm/*.md`) existente. Implementar sem essas respostas
arriscaria exatamente o que a missão proíbe: criar uma segunda hierarquia de negócio
paralela ou uma autoridade de criação inventada. **Nenhum código foi alterado para este
item.**

### Item C — Cadastro de empresa/unidade (tenant onboarding)

**Status:** HUMAN_DECISION.

**FATO CONFIRMADO**: não existe nenhum fluxo de criação de tenant/empresa em lugar
nenhum do CURRENT — todo tenant hoje só existe como fixture estática em
`api/identity_directory.py`/`api/state.py::_seed_tokens()`. Mais importante: **o próprio
código já registra esta ausência como uma decisão de produto deliberadamente adiada**,
não uma lacuna esquecida — o docstring de `api/identity_directory.py` (escrito na sessão
do item 1.3/WP-02, 24/09/2026) diz textualmente: *"Autoprovisionamento/convite de usuario
e Work Package futuro, fora do escopo do WP-02 (decisao de produto separada, nao
tecnica)."*

Implementar um cadastro real de empresa exigiria decidir, sem base suficiente hoje:

1. É autoatendimento (qualquer e-mail verificado pelo Google Identity Platform pode criar
   um tenant novo sozinho) ou provisionamento manual/curado (alguém da Nova FM cria o
   tenant e convida o primeiro `OWNER`)? O comentário acima sugere a segunda opção, mas
   isso nunca foi formalizado como decisão de produto.
2. Quais dados de empresa são obrigatórios no cadastro (razão social? CNPJ? endereço?) —
   nenhum desses campos existe em nenhum schema hoje.
3. Como isso se relaciona com a assinatura/cobrança já real via Asaas
   (`api/routes_billing.py`) — o cadastro de empresa precisa ocorrer ANTES, DEPOIS, ou
   junto com a criação da assinatura?
4. O cadastro cria automaticamente a primeira unidade de negócio (ver Item B), ou isso é
   um passo separado?

**Nenhum código foi alterado para este item** — implementar sem essas respostas seria
inventar uma decisão de produto que a documentação normativa já classifica explicitamente
como fora do escopo técnico.

### Item D — Brand Kit / armazenamento de logo

**Status:** EXTERNAL_INFRASTRUCTURE.

**FATO CONFIRMADO** por leitura real de `backend/api/routes_brand.py` e
`backend/api/models.py::BrandProfileCreate`: o Brand Kit hoje só tem campos textuais
(`name`, `tone`, `colors`, `differentiators`, `restrictions`) — **nenhum campo de logo ou
imagem existe**, e nenhuma integração de armazenamento de arquivos (Cloud Storage, GCP, S3
ou equivalente) existe em lugar nenhum do repositório (`grep` real por
"Storage"/"GCP"/"upload"/"multipart" não encontrou nada).

Um upload real de logo depende de infraestrutura de armazenamento de arquivos que **não
existe** neste projeto hoje — por instrução explícita da missão, **nunca armazenar
base64 no banco como atalho** (isso mascararia a ausência de infraestrutura real por trás
de uma implementação aparentemente funcional, exatamente o tipo de "sucesso fabricado" que
o protocolo antialucinação deste repositório proíbe). **Nenhum código foi alterado para
este item.**

### Item E — Analytics real (Google Ads / Meta)

**Status:** EXTERNAL_CREDENTIAL — já em conformidade, nenhuma ação necessária.

**FATO CONFIRMADO**: `GET /campaigns/{id}/insights` (`api/routes_campaigns.py::get_insights`)
já é um placeholder honesto — devolve `points: []` e uma nota explícita ("No analytics
layer implemented yet in campaia_core; this is an honest placeholder, not fabricated
data"), sem nenhum dado inventado. Confirmado por grep real: não existe nenhum adaptador
real do Google Ads/Meta Ads, nenhuma credencial de API de analytics configurada, nenhuma
integração além do `ProviderSimulator` (achado 20, Fase 3). WP-11 (Fase 2, achado 15,
já registrado antes desta Fase 4) tornou esse comportamento visível também no Web
(`InsightsPanel`), com o mesmo cuidado de nunca fabricar dados.

Implementar analytics real exigiria credenciais de API do Google Ads/Meta e aprovação de
acesso a essas contas — nenhuma das duas existe neste ambiente. **Nenhum código foi
alterado para este item** — o CURRENT já está corretamente honesto, exatamente como a
missão exige ("manter insights honestamente vazios; nunca fabricar analytics").

## FASE 4 — Encerramento

| ITEM | STATUS | AÇÃO |
|---|---|---|
| A. Retomar campanha pausada | FIXED | `POST /campaigns/{id}/resume` exposto (achado 25); achado 26 (duplicação de auditoria em replay) corrigido em `pause_campaign` e `resume_campaign` |
| B. Unidade de negócio | HUMAN_DECISION | 5 perguntas de domínio listadas acima; nenhum código alterado |
| C. Cadastro de empresa/tenant | HUMAN_DECISION | 4 perguntas de domínio listadas acima; já era decisão adiada explicitamente no próprio código (WP-02) |
| D. Brand Kit / logo | EXTERNAL_INFRASTRUCTURE | depende de Cloud Storage/GCP inexistente; nenhum atalho de base64 criado |
| E. Analytics real | EXTERNAL_CREDENTIAL | já honesto (placeholder), nenhuma ação necessária |

Prosseguindo diretamente para a **Fase 5** (certificação final, consolidação de
documentação, preparação do PR de takeover — sem merge), conforme a autorização explícita
do Diretor.

## FASE 5 — Consolidação final

**Matriz de certificação final (execução real nesta sessão, HEAD no momento da execução):**

| Gate | Comando | Resultado |
|---|---|---|
| Testes backend | `PYTHONPATH=. python3 -m pytest -q` | **553 passed, 58 subtests passed, 0 failures** |
| Testes Web (unit/component) | `npm run test -- --run` | **67 passed, 20 arquivos, 0 failures** |
| E2E cross-stack | `npx playwright test --config=playwright.session.config.ts` | **26 passed, 0 failures** |
| Auditoria de dependências | `pip-audit -r requirements.txt` | **0 vulnerabilidades conhecidas** |
| Contrato × geração TS | `npm run contracts:check` | **OK, sem drift** |
| Fronteiras de segurança Web | `npm run boundary:check` | **OK, 65 arquivos, sem violação** |
| Typecheck / lint Web | `npm run typecheck` / `npm run lint` | **OK** |
| Árvore de trabalho | `git status --short` | **limpa** |

**Documentação reconciliada:** novo painel vigente publicado em
`docs/evidence/PAINEL_VIGENTE_20260926.md`, substituindo como retrato do estado real a
seção desatualizada de `docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md` (24/09/2026) e qualquer
painel herdado do histórico da PR#6 — nenhum dos dois documentos anteriores foi apagado
(ambos continuam no repositório como registro histórico), apenas superados como fonte da
verdade corrente.

**Confirmação de avaliação completa de PR#5 e PR#6:** ver seção dedicada em
`docs/evidence/PAINEL_VIGENTE_20260926.md` ("PR#5 e PR#6: confirmação de avaliação
completa"). Resumo: Fase 1 decidiu área por área (nunca uma branch vencendo tudo); Fase 2
reconstruiu 6 telas sobre a arquitetura correta; Fase 3 minerou tecnicamente toda a PR#6
(6 itens + comparação arquivo-a-arquivo de testes) sem deixar nenhum achado real sem
classificação. Nenhum código tecnicamente válido de nenhuma das duas branches foi
abandonado sem avaliação.

**Tabela consolidada de todas as fases desta missão (Fases 3, 4 e 5 — autorizadas
explicitamente nesta sessão; Fases 0–2 já haviam sido concluídas e aprovadas antes):**

| Fase | Escopo | Status |
|---|---|---|
| 3 | 6 itens de mineração técnica da PR#6 (achados 19–24) | Todos FIXED, ver tabela na seção "FASE 3 — Encerramento" |
| 4 | 5 itens de lacunas internas (achados 25–26 + 3 classificações) | A: FIXED · B, C: HUMAN_DECISION · D: EXTERNAL_INFRASTRUCTURE · E: EXTERNAL_CREDENTIAL (já conforme) |
| 5 | Certificação final, documentação, painel vigente, preparação do PR | Concluída — ver matriz acima |

**Nenhum merge, deploy, release ou alteração de produção ocorreu nesta sessão, em nenhum
momento.** O PR de takeover está sendo preparado a seguir, contra `main`, sem merge
automático.
