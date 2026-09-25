# Evidência — WP-03: contexto de tenant/unidade real (listagem e troca)

**Data:** 25/09/2026 · **Branch:** `feat/campaia-wp01-web-foundation` (mesma PR #5, reaproveitada
por decisão do Diretor — ver `EVIDENCIA_ETAPA2_WEB_FOUNDATION_AUTH_SHELL_20260925.md`).
Construído em cima do commit `57da6fb` (Etapa 2 — auth client + app shell).

## DECISÃO — o que "WP-03" realmente exigia

**FATO CONFIRMADO antes de qualquer código:** ao contrário do que o texto do roadmap
(`docs/web/06_ROADMAP_WORK_PACKAGES.md`) sugeria ("quando o usuário pertence a mais de um"),
o backend **não tinha nenhum modelo de múltiplos vínculos por identidade**.
`IdentityDirectory.resolve(email)` era estritamente 1:1 (um e-mail → um único
`tenant_id`/`business_unit_id`/papéis fixos) — não havia lista de vínculos, nem endpoint
para listar ou trocar. Isso foi verificado lendo o código real
(`backend/api/identity_directory.py`, `backend/api/state.py`), não assumido do roadmap.

**DECISÃO (autoridade humana explícita, nesta sessão):** construir o modelo real de
múltiplos vínculos por identidade no backend + os dois endpoints novos + a UI — não apenas
uma UI sobre uma API que já existia (ela não existia). Plano completo apresentado e
aprovado antes de qualquer edição de código (registrado na conversa desta sessão).

## O que foi construído

### Backend

- `backend/api/identity_directory.py`: `IdentityDirectory.resolve_all(email) ->
  tuple[TokenPrincipal, ...]` (novo) — devolve TODOS os vínculos de um e-mail.
  `resolve()` (existente, mantido por compatibilidade) continua devolvendo só o primeiro.
  `seed_dev_identity_directory()`: todos os vínculos existentes agora são tuplas de 1
  elemento (comportamento idêntico); um novo e-mail de teste,
  `owner@multi-tenant.campaia.test`, tem DOIS vínculos reais (`user-multi-1a` em
  `demo-tenant`, `user-multi-1b` em `other-tenant`).
- `backend/api/session.py`: `SessionRecord.available_principals` (novo campo, tupla,
  capturada no login) e `SessionStore.switch_principal(session_id, principal)` (novo) —
  troca o vínculo ATIVO preservando `session_id`/`csrf_secret`/`created_at`/`expires_at`.
- `backend/api/deps.py`: `require_session_record()` (novo) — como `require_auth`, mas
  devolve o `SessionRecord` inteiro; recusa (401) quando a autenticação foi via fixture de
  bearer token de dev/teste (que não tem conceito de vínculos múltiplos).
- `backend/api/routes_auth.py`: `login()` agora usa `resolve_all()` e guarda todos os
  vínculos na sessão. Dois handlers novos: `list_memberships` (`GET /me/memberships`) e
  `switch_membership` (`POST /auth/session/switch`) — este último grava `SESSION_SWITCH`/
  `SESSION_SWITCH_REJECTED` no audit log (achado de revisão de segurança, corrigido nesta
  mesma sessão — ver `FM_SECURITY_REVIEW_WEB_ETAPA2_20260925.md`).
- `backend/api/models.py`: `MembershipItem`, `MembershipsResponse`, `SwitchMembershipRequest`.
- `backend/api/main.py`: rotas `GET /me/memberships`, `POST /auth/session/switch`
  registradas.
- `backend/tests_support/e2e_identity.py`: `E2E_TOKEN_MULTI_TENANT_OWNER` — token de E2E
  determinístico para o novo e-mail multi-vínculo.

### Frontend

- `web/src/types/session.ts`: `Membership`, `MembershipsResponse`.
- `web/src/providers/AuthProvider.tsx`: `switchMembership(targetUserId)` — chama
  `POST /auth/session/switch` (mutação real, via `api.post`, CSRF já em memória),
  atualiza `session` e refaz `GET /me`.
- `web/src/components/TenantSwitcher.tsx` (+ CSS module): lista vínculos reais
  (`GET /me/memberships`), mostra qual está ativo, oferece botão de troca para os
  demais. Estado único (1 vínculo) mostra mensagem honesta em vez de UI de troca vazia.
  Erro de carregamento/troca sempre visível (`ErrorState`, `role="alert"`), nunca
  silencioso.
- `web/src/app/(app)/(authenticated)/settings/page.tsx`: substitui o placeholder de
  pendência anterior pelo `TenantSwitcher` real.
- `web/src/lib/auth/test-identity-client.ts`: nova opção de login de teste para o
  e-mail multi-vínculo.
- `web/e2e/session-protocol.spec.ts`: cenário **K** (novo) — login como identidade
  multi-vínculo, troca real via UI em `/settings`, confirma que `GET /me` da MESMA
  sessão reflete o novo tenant sem novo login.

## Gates executados (comando real + resultado real)

| Gate | Comando | Resultado |
|---|---|---|
| Testes de domínio (backend) | `python3 -m unittest discover -s tests` | `368 passed` (sem regressão) |
| Testes de API (backend) | `python3 -m unittest discover -s tests_api -t .` | `151 passed` (149 + 2 novos de audit log) |
| Lint (web) | `npm run lint` | `OK` |
| Typecheck (web) | `npm run typecheck` | `OK` |
| Unit/component (web) | `npm run test` | `35 passed` (32 + 3 novos do `TenantSwitcher`) |
| Boundary check (web) | `npm run boundary:check` | `OK`, 47 arquivos, 0 violações |
| Contract drift (web) | `npm run contracts:check` | `OK` |
| Build produção (web) | `npm run build` | `OK`, 11 rotas |
| E2E smoke WP-01 (web) | `npm run test:e2e` | `4 passed` |
| E2E protocolo de sessão real (web+backend) | `npm run test:e2e:session` | **`12 passed`** — A-K, incluindo o novo cenário K de troca de tenant |

Testes novos que provam especificamente os critérios de aceite do WP-03:

- Listagem com 1 vínculo mostra 1 item ativo
  (`test_single_membership_user_lists_exactly_one_active_membership`).
- Listagem com 2 vínculos mostra os dois, só o correto marcado ativo
  (`test_multi_membership_user_lists_both_with_only_the_first_active`).
- Troca real muda `tenant_id`/`business_unit_id` ativos, mesma sessão/cookie/CSRF
  (`test_switch_to_a_real_membership_changes_the_active_tenant`).
- Troca para um vínculo de OUTRA identidade é recusada fail-closed, 403
  (`test_switch_to_a_membership_not_owned_by_this_identity_is_rejected_fail_closed`).
- Troca sem CSRF é recusada (`test_switch_without_csrf_token_is_rejected`).
- Troca via fixture de bearer token de dev é recusada
  (`test_switch_via_dev_bearer_fixture_is_rejected`).
- Isolamento cross-tenant DENTRO da mesma sessão após a troca — recurso criado no
  vínculo antigo nunca aparece depois da troca
  (`test_switching_tenant_never_leaks_a_resource_from_the_previous_tenant`).
- `step_up_at` é invalidado pela troca — operação sensível exige nova reautenticação no
  novo vínculo mesmo tendo acabado de se reautenticar no vínculo anterior
  (`test_switching_tenant_requires_fresh_step_up_for_sensitive_operations`).
- Troca (sucesso e rejeição) fica registrada no audit log
  (`test_successful_switch_is_recorded_in_the_audit_log`,
  `test_rejected_switch_attempt_is_recorded_in_the_audit_log`).
- E2E real via UI: `K. troca real de tenant/unidade via UI (WP-03)`.

## Segurança

Revisão focada registrada em `docs/evidence/FM_SECURITY_REVIEW_WEB_ETAPA2_20260925.md`
(seção "Revisão adicional — WP-03"): 6 pontos verificados sem achado, 1 achado corrigido
nesta sessão (falta de auditoria da troca), 1 achado residual de baixa severidade/teórico
registrado (chave de `step_up_at` não inclui `business_unit_id`), 1 item não verificado
(concorrência real). **Não é uma certificação de segurança do produto.**

## Pendências (não resolvidas, fora de escopo desta entrega)

- `contracts/bff-openapi.yaml` não documenta `/me/memberships` nem
  `/auth/session/switch` — mesma pendência pré-existente já registrada para
  `/auth/session` (Etapa 2).
- Convite/provisionamento de novos vínculos para um usuário já existente — Work Package
  futuro, fora de escopo (mesma decisão já registrada para autoprovisionamento no WP-02).
- Concorrência real (duas trocas simultâneas na mesma sessão) não testada explicitamente.

## Status exato de prontidão

`WP-03 (TROCA DE TENANT/UNIDADE) IMPLEMENTADO + TESTADO — PRONTO PARA REVISÃO.`
Nunca "HOMOLOGADO" nem "PRONTO PARA PRODUÇÃO". Nenhum merge/deploy ocorreu nesta sessão.
