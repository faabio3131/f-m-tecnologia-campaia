# CampaIA — Ponto Zero Web · 17. Certificação do WP-10 (Trilha de auditoria)

**Estado máximo declarado neste documento:** `WP-10 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`

Este documento certifica a execução real do WP-10 — um bloco **não presente no roadmap
original**, definido nesta mesma missão por reconciliação de CURRENT (ver
`docs/web/06_ROADMAP_WORK_PACKAGES.md` §"WP-10 — Trilha de auditoria"), sob a mesma
autorização explícita do Diretor de construir mais 3 blocos ("pode sim construa mais 3
blocos") do WP-09, reafirmando a autorização contínua de construção durante o bloqueio de
cota do CI do GitHub Actions. Sobre a branch `feat/campaia-v1-complete-saas` (PR #6).

Como todo bloco desde o WP-02, esta execução **não inclui nem simula uma revisão de QA
formal** — essa revisão permanece uma pendência genuína, registrada aqui, nunca presumida
como satisfeita.

---

## 1. Escopo executado

| Área | Arquivos |
|---|---|
| Web: nova página `/audit`, Server Component puro | `web/src/app/audit/page.tsx`, `page.module.css` |
| Web: leitura server-side da trilha real | `web/src/lib/session.ts` (`getServerAuditEvents`) |
| Web: novo tipo de contrato | `web/src/contracts/types.ts` (`AuditEvent`) |
| Web: link de navegação a partir do dashboard | `web/src/app/dashboard/page.tsx` |
| Backend: teste de jornada via sessão Web real (eventos reais de outro bloco aparecem; filtro `campaign_id`; permissão negada) | `backend/tests_api/test_audit_trail_web_session.py` |
| E2E cross-stack real, novo spec dedicado | `web/e2e-crossstack/audit-trail.spec.ts` |
| Correção de bug real pré-existente, encontrada durante a regressão deste bloco (ver §2) | `web/src/app/onboarding/page.tsx`, `web/tests/onboarding-page.test.tsx` |

Nenhum arquivo em `backend/campaia_core/`, `backend/db/`, `backend/api/routes_audit.py`,
`backend/api/models.py`, `permissions.py`, `mobile/` foi alterado (confirmado por `git
status`). Nenhuma rota de backend nova foi criada — `GET /audit-events` já existia desde
antes deste bloco, já testada por fixtures Bearer unitárias, e já era escrita por
praticamente todo bloco desde o WP-04. Este bloco construiu inteiramente a primeira tela que
exibe essa trilha, sem alterar o domínio.

## 2. Nenhum achado de contrato — e um achado real de bug de UI pré-existente

Diferente de todo bloco WP-06 a WP-09, a leitura direta do schema `AuditEvent`
(`contracts/bff-openapi.yaml`) contra `AuditEventResponse`/`AuditEvent` (`api/models.py`),
feita antes de qualquer código, **não revelou divergência**. Nenhuma correção de contrato foi
necessária neste bloco.

Em vez disso, a regressão E2E completa deste bloco encontrou um **bug real pré-existente**,
não introduzido por este bloco: `web/src/app/onboarding/page.tsx` calculava
`canFinishOnboarding` a partir de `connections.length > 0` — a lista bruta de conexões,
incluindo revogadas. Antes do WP-09 introduzir desconexão (`DELETE /connections/{id}`),
toda conexão devolvida por `GET /connections` era sempre `ACTIVE`, então contar o tamanho
bruto da lista era equivalente a contar conexões ativas. O WP-09 quebrou essa equivalência ao
introduzir o status `REVOKED` real — mas nenhum teste até este bloco exercitou o cenário "uma
conexão existe apenas em forma revogada, nenhuma ativa" contra a asserção do WP-04 de que
"Concluir Onboarding" deve ficar desabilitado com zero canais conectados.

Encontrado da seguinte forma: `audit-trail.spec.ts` (este bloco) precisa conectar uma conta
real para gerar eventos reais de auditoria (`OAUTH_START`, `CONNECTION_CREATE`) e, como todo
spec cross-stack desta suíte (`workers: 1`, um único processo de backend real compartilhado
por todo o arquivo e por toda a suíte), deve desconectar essa conta ao final para não poluir
`onboarding.spec.ts`, que roda depois na mesma execução — mesma disciplina de higiene de
estado já aplicada pelo próprio WP-09 (achado P-34). Ao rodar a suíte completa pela primeira
vez com esse novo spec, os dois primeiros testes de `onboarding.spec.ts` falharam: a conta
`WHATSAPP` conectada-e-depois-desconectada por `audit-trail.spec.ts` deixava um registro de
conexão `REVOKED` para trás, e a página de onboarding mostrava incorretamente o link
"Concluir Onboarding" mesmo com as três contas exibindo "Não conectado".

Corrigido usando `activeConnections.length > 0` (variável já calculada na mesma página para a
busca de capacidades do WP-09) em vez de `connections.length > 0`. Um novo teste Vitest de
regressão (`onboarding-page.test.tsx`, "keeps 'Concluir Onboarding' disabled when the only
connection on record is revoked") cobre exatamente esse estado. Investigado por causa raiz —
não mascarado, não contornado ajustando o spec novo para evitar o cenário.

## 3. Achado real, confirmado por teste de backend via sessão Web real

`test_audit_trail_web_session.py` (3 testes, via sessão Web real, não fixtures Bearer):

- A trilha realmente reflete ações reais de outro bloco — conectar uma conta pelo fluxo do
  WP-04 produz `OAUTH_START` e `CONNECTION_CREATE` reais, visíveis em `GET /audit-events` com
  `actor_id: "user-owner-1"`, `target` igual ao `connection_id` real, `actor_kind: "USER"`.
- O filtro `campaign_id` realmente restringe a trilha: criar um brief e conectar uma conta
  não relacionada confirma que apenas os eventos com `target == campaign_id` retornam, e o
  evento `OAUTH_START` (cujo `target` é o nome do provedor, não um `campaign_id`) nunca
  aparece quando o filtro está ativo.
- Identidade sem `AUDIT_VIEW` (marketer) recebe `403 PERMISSION_DENIED` real do servidor.

## 4. Testes — comando e resultado

```
$ cd backend && python3 -m unittest discover -s tests_api
Ran 176 tests
OK
```

176 = 173 pré-existentes (WP-01 a WP-09, inalterados) + 3 novos
(`tests_api/test_audit_trail_web_session.py`).

| Suite | Cobre |
|---|---|
| `test_audit_trail_web_session.py` (3) | Eventos reais de outro bloco aparecem na trilha (`OAUTH_START`, `CONNECTION_CREATE`, `actor_id`/`target`/`actor_kind` corretos); filtro `campaign_id` restringe corretamente; identidade sem `AUDIT_VIEW` recusada com `403 PERMISSION_DENIED` |

```
$ cd backend && python3 -m unittest discover -s tests
Ran 267 tests
OK   (sem alteração -- campaia_core intocado)

$ python3 contracts/validate_events_asyncapi.py
ALL CHECKS PASSED (24 events)   (sem alteração)

$ cd web && npm run lint && npm run typecheck && npm run contracts:check && npx vitest run && npm run build
todos verdes   (132/132 Vitest -- 7 novos desde o WP-09: 6 em audit-page.test.tsx + 1 novo em
onboarding-page.test.tsx, achado do bug real do §2 -- soma exata: 132 - 125 pré-existentes = 7)

$ node web/scripts/check-security-boundaries.mjs
OK: nenhuma violação (64 arquivos verificados, allowlist inalterada em 12 arquivos --
/audit é Server Component puro, zero chamada de rede client-side, nenhum arquivo novo
precisou entrar na allowlist)

$ cd web && CAMPAIA_CHROMIUM_PATH=<chromium> npx playwright test -c playwright.crossstack.config.ts
12 passed (11 pré-existentes + 1 novo: conectar WHATSAPP -> ver eventos reais em /audit ->
desconectar WHATSAPP, restaurando o estado compartilhado da suíte) -- confirmado verde
apenas após a correção do §2; a primeira execução com o spec novo (antes da correção)
reproduziu a falha real em onboarding.spec.ts, exatamente como o bug foi encontrado.
```

Sem novo spec de fumaça dedicado (`npm run test:e2e`, sem backend): `/audit`, como toda outra
página autenticada desta aplicação, não faz nenhuma chamada BFF quando
`NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN` está ausente — coberto pela mesma lógica de configuração já
testada em `audit-page.test.tsx` ("shows a configuration notice...").

## 5. Prova de ausência de secrets

- Nenhum token/segredo real no diff (mesma verificação dirigida das certificações
  anteriores; nenhum literal novo introduzido).
- `/audit` é um Server Component puro: zero chamada de rede client-side, zero uso de
  `localStorage`/`sessionStorage`/cookies no cliente. Confirmado por `node
  scripts/check-security-boundaries.mjs` (64 arquivos verificados, 0 violações, allowlist
  inalterada).
- `AuditEvent.target` é exibido em texto bruto, nunca traduzido ou adivinhado (achado 15,
  documentado no próprio código-fonte e no roadmap) — a página nunca fabrica um rótulo
  legível para um campo cujo significado depende da ação.

## 6. Escopo do diff (confirmado por `git status`)

Novos: `web/src/app/audit/page.tsx`, `web/src/app/audit/page.module.css`,
`backend/tests_api/test_audit_trail_web_session.py`, `web/e2e-crossstack/audit-trail.spec.ts`,
este documento.

Modificados: `web/src/lib/session.ts`, `web/src/contracts/types.ts`,
`web/src/app/dashboard/page.tsx`, `web/tests/audit-page.test.tsx` (novo arquivo de teste),
`web/src/app/onboarding/page.tsx` (correção do bug do §2), `web/tests/onboarding-page.test.tsx`
(novo teste de regressão do §2), `docs/web/06_ROADMAP_WORK_PACKAGES.md`.

`contracts/bff-openapi.yaml`: **intocado** (§2 — nenhum achado de contrato).

`mobile/`, `backend/campaia_core/`, `backend/db/`, `backend/api/routes_audit.py`,
`backend/api/models.py`, `permissions.py`: **intocados**.

## 7. Itens não verificados / pendências reais

- **Revisão de FM QA Engineer** — não realizada nesta execução; pendência explícita, como em
  todo bloco desde o WP-02.
- **Paginação real** — `next_cursor` de `GET /audit-events` é sempre `null` (achado 3/15,
  pré-existente, documentado no próprio código); a tela exibe honestamente a lista completa
  devolvida, sem fabricar paginação que não existe. Não corrigido neste bloco — fora de
  escopo, é um gap real de `campaia_core`, não de apresentação.
- **CI remoto do GitHub Actions** — não confirmado verde nesta execução; **FATO CONFIRMADO
  pelo Diretor**: cota gratuita de minutos esgotada. Não é regressão de código. Toda a
  evidência deste documento vem de execução local real.

## 8. Confirmações negativas

- `permissions.py`, `backend/campaia_core/`, `backend/db/`, `mobile/`: intocados.
- Nenhuma rota de backend nova criada (`GET /audit-events` já existia).
- `contracts/bff-openapi.yaml`: intocado — nenhum achado de contrato neste bloco (§2).
- Nenhuma credencial real usada ou necessária.
- Nenhum merge, nenhum deploy.
- Nenhum bloco além do WP-11 foi definido; WP-11 segue definido mas ainda não implementado.

## 9. Critérios (Gate 5, extensão)

| Critério | Situação |
|---|---|
| Usuário com `AUDIT_VIEW` visualiza a trilha real do tenant | Sim, testado via sessão Web real e E2E cross-stack |
| Usuário sem a permissão recebe a recusa real do servidor | Sim, testado (`403 PERMISSION_DENIED`) |
| Trilha reflete ações reais de outro bloco, nunca fabricada | Sim, testado (`OAUTH_START`/`CONNECTION_CREATE` reais) |
| Filtro `campaign_id` funciona corretamente | Sim, testado |
| `permissions.py` inalterado | Sim |
| Nenhuma rota de backend nova | Sim (confirmado por `git status`) |
| Fronteira de rede do frontend inalterada (Server Component puro) | Sim |
| Achado real de bug pré-existente investigado por causa raiz e corrigido | Sim (§2) |
| Revisão de FM QA Engineer | **Pendente** |
| Autorização do Diretor | Sim ("pode sim construa mais 3 blocos", 21/09/2026, mesma do WP-09) |

Veredito correto: `WP-10 IMPLEMENTADO E AUTOTESTADO — REVISÃO DE FM QA ENGINEER PENDENTE`.
