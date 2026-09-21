# CampaIA — Ponto Zero Web · 15. Certificação do WP-08 (Parada de emergência / Kill Switch)

**Estado máximo declarado neste documento:** `WP-08 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`

Este documento certifica a execução real do WP-08 — um bloco **não presente no roadmap
original**, definido nesta mesma missão por reconciliação de CURRENT (ver
`docs/web/06_ROADMAP_WORK_PACKAGES.md` §"WP-08 — Parada de emergência (Kill Switch)"), sob a
mesma autorização do Diretor que definiu o WP-07 (cota do GitHub Actions esgotada, autorização
de continuar a construção reafirmada explicitamente: "vamos continuar a construção eu autorizo
prosseguir e no final iremos auditar e corrigir o que for necessário"). Sobre a branch
`feat/campaia-v1-complete-saas` (PR #6).

Como todo bloco desde o WP-02, esta execução **não inclui nem simula uma revisão de QA
formal** — essa revisão permanece uma pendência genuína, registrada aqui, nunca presumida
como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| Contrato: schema de resposta real ausente, adicionado aditivamente | `contracts/bff-openapi.yaml` |
| Web: componente de parada de emergência (escopo, motivo, acionar, exibir resultado) | `web/src/components/KillSwitchPanel.tsx` |
| Web: painel integrado ao shell do dashboard | `web/src/app/dashboard/page.tsx` |
| Fronteira de segurança do frontend atualizada (allowlist de 12 arquivos) | `web/scripts/{check-security-boundaries.mjs,lib/security-boundaries.mjs}` |
| Backend: teste de jornada via sessão Web real (escopo CAMPAIGN pausa de verdade; escopo TENANT sem campanha pausável; permissão negada) | `backend/tests_api/test_kill_switch_web_session.py` |
| E2E cross-stack real | `web/e2e-crossstack/kill-switch.spec.ts` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `backend/api/routes_campaigns.py`,
`backend/api/models.py`, `permissions.py`, `mobile/` foi alterado (confirmado por `git
status`). Nenhuma rota de backend nova foi criada — `POST /kill-switch` já existia desde
blocos anteriores; este bloco construiu inteiramente a camada Web sobre ela. Diferente de
todo bloco desde o WP-05, este NÃO reutiliza a fila `/approvals` — o próprio domínio dispensa
aprovação para o kill switch, porque a ação só reduz efeito, nunca amplia.

## 2. Achado real de contrato, corrigido durante a execução

Ao projetar `KillSwitchPanel.tsx` (antes de escrever qualquer chamada de rede), a leitura
direta de `contracts/bff-openapi.yaml`'s `/kill-switch` revelou que a resposta `202` não
tinha `content`/schema **nenhum** definido, apesar de sempre devolver
`{scope, affected_campaign_ids}` (`api/routes_campaigns.py _do_kill_switch`, confirmado por
leitura direta). Diferente dos achados anteriores (um campo isolado ausente de um schema já
existente), este era o schema de resposta inteiro ausente — mesma classe de achado (real,
sempre presente, nunca documentado), desta vez em maior escala. Corrigido aditivamente:
`KillSwitchResult` adicionado a `contracts/bff-openapi.yaml`'s `components/schemas`, e
referenciado pela resposta `202` de `/kill-switch`. `npm run contracts:generate`/
`contracts:check` confirmaram sincronia após a correção.

## 3. Decisão de escopo tomada durante a reconciliação de CURRENT (antes de qualquer código)

Duas decisões de engenharia foram tomadas nesta reconciliação, ambas documentadas em
`docs/web/06_ROADMAP_WORK_PACKAGES.md` antes de qualquer implementação:

- **Kill switch escolhido sobre "pausar campanha" (`POST /campaigns/{id}/pause`)**: a
  investigação de CURRENT revelou que, embora `PAUSED → ACTIVE` seja uma transição real e
  guardada no domínio (`campaia_core/states.py _guard_resume`), **nenhuma rota HTTP existe
  para retomar uma campanha pausada**, e o Protocol `AdsConnector`
  (`campaia_core/connectors.py`) não define nenhuma operação canônica de retomada — apenas
  `validate_draft`, `publish` e `pause`. Construir "pausar" sem "retomar" deixaria o usuário
  genuinamente travado; construir "retomar" de verdade exigiria adicionar uma operação
  canônica nova ao Protocol dos conectores, uma expansão arquitetural real não autorizada por
  esta reconciliação. O kill switch não sofre desse problema: é desenhado para ser
  unidirecional por definição ("só reduz efeito, nunca amplia", comentário do próprio
  domínio). Registrado como achado real, não corrigido (P-40, ver painel v28).
- **Apenas os escopos `CAMPAIGN` e `TENANT` expostos na Web**: o endpoint real aceita 5
  escopos (`CAMPAIGN`, `ACCOUNT`, `TENANT`, `PLATFORM`, `GLOBAL`). `GLOBAL` cruza tenants por
  desenho documentado do próprio domínio; `ACCOUNT`/`PLATFORM` pausam múltiplas campanhas de
  uma vez sem seleção individual. Nenhum dos três é apropriado para um dashboard de tenant
  comum sem uma decisão de produto/segurança explícita sobre uma futura tela de operador de
  plataforma — decisão que não foi tomada nesta reconciliação. Esta é uma escolha do lado Web,
  não uma alteração de backend: a API continua aceitando os 5 escopos.

## 4. Achado real de teste, encontrado ao investigar o alcance do E2E cross-stack

Nenhuma tela do Web app aciona `POST /campaigns/{id}/publish` — confirmado por leitura direta
do próprio comentário em `web/src/app/campaigns/[campaignId]/page.tsx` ("nada nesta tela chama
POST .../publish"), um limite já existente desde o WP-05, não introduzido por este bloco. Isso
significa que **nenhum caminho puramente de navegador** consegue levar uma campanha a um
estado pausável (`APPROVED`/`PUBLISHING`/`ACTIVE`/`OPTIMIZING`) — o E2E cross-stack deste
bloco só pode exercitar de verdade o resultado "nenhuma campanha afetada" (escopo `TENANT`
sobre uma campanha `DRAFT`, o único estado alcançável via UI). O caso "campanha realmente
pausada" (escopo `CAMPAIGN`) é coberto pelo teste de backend via sessão Web real, que chega a
`APPROVED`/`PUBLISHING` diretamente via HTTP — o mesmo fluxo completo que o WP-05 já havia
provado ponta a ponta (brief → plano → validação → aprovação → decisão → publicação), agora
seguido de uma chamada real a `POST /kill-switch` e confirmado por uma leitura fresca de
`GET /campaigns/{id}` mostrando `state: "PAUSED"`.

## 5. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api
Ran 171 tests
OK
```

171 = 168 pré-existentes (WP-01 a WP-07, inalterados) + 3 novos
(`tests_api/test_kill_switch_web_session.py`).

| Suite | Cobre |
|---|---|
| `test_kill_switch_web_session.py` (3) | Escopo `CAMPAIGN` pausa de verdade uma campanha `APPROVED`/publicada via sessão Web real, sem `X-Step-Up-Token` (confirmando o desenho do próprio domínio: `KILL_SWITCH` está fora de `REQUIRES_STEP_UP`); escopo `TENANT` sobre uma campanha `DRAFT` devolve lista de afetados vazia, sem erro; identidade sem a permissão `KILL_SWITCH` (marketer) é recusada com `403 PERMISSION_DENIED` |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração -- campaia_core intocado)

$ cd contracts && python3 validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run lint && npm run typecheck && npm run contracts:check && npm run test && npm run build
todos verdes   (120/120 Vitest -- 10 novos desde o WP-07: KillSwitchPanel (9) + 1 novo em
dashboard-page.test.tsx -- soma exata: 120 - 110 pré-existentes = 10)

$ node web/scripts/check-security-boundaries.mjs
OK: nenhuma violação (62 arquivos verificados, allowlist de 12 arquivos: os 11 do WP-02 a
WP-07 + KillSwitchPanel.tsx)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npm run test:e2e:crossstack
10 passed (9 pré-existentes + 1 novo: acionar parada de emergência com escopo TENANT sobre
uma campanha recém-criada, ainda DRAFT -- resultado real "nenhuma campanha afetada" exibido
na tela, ver §4 sobre o alcance real deste E2E)
```

Sem novo spec de fumaça dedicado (`npm run test:e2e`, sem backend): `/dashboard` já é coberto
pelos specs existentes de WP-02/WP-03 (nenhuma chamada BFF quando
`NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` está ausente); o painel de parada de emergência em si só é
exercitável com um backend real, coberto pelo E2E cross-stack acima.

## 6. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida das certificações
  anteriores; nenhum literal novo introduzido).
- Fronteira do frontend atualizada, não removida: chamada de rede ao BFF agora permitida em
  exatamente 12 arquivos (os 11 do WP-02 a WP-07 + `KillSwitchPanel.tsx`, protegido por
  CSRF). Todo o resto de `web/src` permanece em zero chamadas de rede, confirmado por
  `node scripts/check-security-boundaries.mjs` (62 arquivos verificados, 0 violações).
- Diferente de todo componente anterior que envia `X-Step-Up-Token`, `KillSwitchPanel.tsx`
  deliberadamente **não** envia esse header — reflete fielmente a decisão do próprio domínio
  (`Permission.KILL_SWITCH` fora de `REQUIRES_STEP_UP`), nunca inventada nem contornada aqui.

## 7. Escopo do diff (confirmado por `git status`)

Modificados: `contracts/bff-openapi.yaml`, `web/scripts/{check-security-boundaries.mjs,
lib/security-boundaries.mjs}`, `web/src/contracts/{bff-openapi.generated.ts,types.ts}`,
`web/src/app/dashboard/page.tsx`, `web/tests/dashboard-page.test.tsx`.

Novos: `backend/tests_api/test_kill_switch_web_session.py`,
`web/e2e-crossstack/kill-switch.spec.ts`,
`web/src/components/KillSwitchPanel.{tsx,module.css}`, `web/tests/kill-switch-panel.test.tsx`.

`mobile/`, `backend/campaia_core/`, `backend/db/`, `backend/api/routes_campaigns.py`,
`backend/api/models.py`, `permissions.py`: **intocados**.

## 8. Itens não verificados / pendências reais

- **Revisão de FM QA Engineer** — não realizada nesta execução; pendência explícita, como
  em todo bloco desde o WP-02.
- **Retomar campanha pausada (resume)** — confirmado como um candidato real, mas bloqueado
  por uma lacuna arquitetural genuína (nenhuma operação canônica de retomada no Protocol dos
  conectores); não corrigido aqui, registrado como pendência (P-40).
- **Escopos `ACCOUNT`, `PLATFORM`, `GLOBAL`** — a API os aceita, mas nenhum é exposto nesta
  tela; permanecem candidatos reais para uma futura tela de operador de plataforma, sob uma
  decisão de produto/segurança que não foi tomada nesta reconciliação.
- **CI remoto do GitHub Actions** — não confirmado verde nesta execução; **FATO CONFIRMADO
  pelo Diretor**: cota gratuita de minutos esgotada, renovação prevista para o dia 31. Não é
  regressão de código. Toda a evidência deste documento vem de execução local real.

## 9. Confirmações negativas

- `permissions.py`, `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma rota de backend nova criada (`POST /kill-switch` já existia).
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- Nenhum bloco além do WP-08 foi definido; qualquer trabalho futuro exige a mesma disciplina
  de reconciliação de CURRENT usada para definir este bloco.

## 10. Critérios (Gate 5, extensão)

| Critério | Situação |
|---|---|
| Parada de emergência funciona ponta a ponta, escopo CAMPAIGN (campanha realmente pausada) | Sim, testado via sessão Web real (backend) |
| Parada de emergência funciona ponta a ponta, escopo TENANT | Sim, testado (backend e E2E cross-stack real) |
| Sem X-Step-Up-Token, por desenho do próprio domínio | Sim, confirmado no teste real |
| `permissions.py` inalterado | Sim |
| Nenhuma rota de backend nova | Sim (confirmado por `git status`) |
| Revisão de FM QA Engineer | **Pendente** |
| Autorização do Diretor | Sim (autorização de continuar a construção, reafirmada em 21/09/2026) |

Veredito correto: `WP-08 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`.
Nenhum bloco além do WP-08 foi definido; qualquer bloco seguinte exige a mesma disciplina de
reconciliação de CURRENT usada para definir este.
