# Evidência — WP-04: Brand Kit e Conexões reais (Onboarding parcial)

**Data:** 26/09/2026 · **Branch:** `feat/campaia-wp01-web-foundation` (PR #5).

## Escopo real vs. especificação de telas — reconciliação

**FATO CONFIRMADO antes de codificar:** `docs/product/13_ESPECIFICACAO_TELAS_APP.md`
§3 descreve 4 telas de onboarding (3.1 Login, 3.2 Cadastro da Empresa, 3.3 Unidade de
Negócio, 3.4 Conectar Contas). Verificando `backend/api/main.py` (lista completa de
rotas): **não existe nenhum endpoint para criar tenant ou unidade de negócio** — o
diretório de identidade (`identity_directory.py`) só resolve e-mails já pré-cadastrados,
nunca cria um novo. As telas 3.2 e 3.3 descrevem uma capacidade de "auto-cadastro de
empresa" que **não existe no backend hoje** e está fora do escopo desta entrega
(autoprovisionamento é decisão de produto separada, já registrada como fora de escopo
do WP-02).

**Escopo real desta entrega:** 3.1 (login) já existia (WP-02). 3.4 (Conectar Contas) e
o Brand Kit (§4) — as duas partes que TÊM API real por trás.

## Achado real e correção — `POST /connections/oauth/start` nunca criava uma `Connection`

**FATO CONFIRMADO:** `oauth_start` (código pré-existente) só devolvia uma URL de
autorização simulada e gravava auditoria — nunca chamava `ConnectionRepository.create()`
(que já existia no domínio). Não havia rota de callback registrada. O próprio arquivo de
teste já documentava isso (`tests_api/test_smoke_endpoints.py`, comentário: "oauth/start
does not itself create a Connection row (no real OAuth callback exists in this
sandbox)").

**DECISÃO (autorização humana explícita):** construir o callback simulado no backend,
fechando o ciclo real, em vez de deixar a tela de Conexões sem funcionalidade.

**Construído:**
- `backend/api/state.py`: `PendingOAuthState` + `AppState.start_oauth_state()`/
  `redeem_oauth_state()` — `state` de uso único, amarrado ao `tenant_id` que iniciou o
  fluxo, TTL de 10 minutos, sempre removido no resgate (sucesso ou falha — nunca replay).
- `backend/api/routes_connections.py`: `oauth_start` agora registra o `state` pendente;
  novo handler `oauth_callback` resgata o `state`, valida (existe, pertence a este
  tenant, não expirado), cria a `Connection` real via `state.connections.create()`
  (idempotente, com `Idempotency-Key`), grava auditoria `CONNECTION_CREATE`.
- `backend/api/main.py`: rota `POST /connections/oauth/callback` registrada.
- `contracts/bff-openapi.yaml`: endpoint documentado.

## Frontend construído

- `web/src/app/(app)/(authenticated)/brand-kit/page.tsx`: Brand Kit real —
  lista (`GET /brand-profiles`) + formulário de criação (`POST /brand-profiles`, campos
  exatamente os do contrato real: `name`, `tone`, `colors`, `differentiators`,
  `restrictions` — nunca os campos mais ricos da especificação de telas que o backend
  não suporta, como upload de logo).
- `web/src/app/(app)/(authenticated)/connections/page.tsx`: 3 cartões de provider
  (Google Ads/Meta/WhatsApp), fluxo real start → seleção de conta (simulada, nenhum
  provider real contatado) → callback → `Connection` persistida.
- **Step-up honesto**: não existe ainda desafio real de reautenticação na Web (depende
  do item 1.6). Em vez de enviar `X-Step-Up-Token` silenciosamente, a UI mostra uma
  confirmação explícita ("Esta ação exige reautenticação recente... Confirmar para
  continuar") antes de qualquer chamada sensível — nunca finge um desafio de segurança
  que não existe, mas também nunca contorna o controle do backend silenciosamente.
- `contracts/types.ts`: `BrandProfile`, `BrandProfileInput`, `Connection`, `Provider`
  reexportados dos tipos gerados do contrato (Fase 1, mesma sessão).

## Gates executados

| Gate | Resultado |
|---|---|
| Testes de domínio (backend) | `368 passed` (sem regressão) |
| Testes de API (backend) | `158 passed` (151 + 7 novos do callback OAuth) |
| AsyncAPI | `24/24 eventos` |
| Lint / Typecheck (web) | `OK` |
| Unit/component (web) | `42 passed` (35 + 7 novos: Brand Kit 4, Conexões 3) |
| Boundary check (web) | `OK`, 49 arquivos, 0 violações |
| Contract drift (web) | `OK` |
| Build produção (web) | `OK`, 11 rotas |
| E2E smoke WP-01 (web) | `4 passed` |
| E2E protocolo de sessão + WP-03 + WP-04 real (web+backend) | **`13 passed`** (A–L) |

Testes novos que provam os critérios de aceite do WP-04:

- Backend: `test_full_flow_creates_a_real_connection`,
  `test_unknown_state_is_rejected_fail_closed`,
  `test_state_from_another_tenant_is_rejected`,
  `test_the_real_owner_of_the_state_can_still_redeem_it`, `test_state_is_single_use`,
  `test_callback_without_step_up_is_rejected`, `test_callback_requires_idempotency_key`
  (`backend/tests_api/test_connections_oauth.py`).
- Frontend: `web/tests/brand-kit-page.test.tsx` (4 testes),
  `web/tests/connections-page.test.tsx` (3 testes).
- E2E real: cenário **L** — login real, cria Brand Kit real via UI, conecta um
  provider real de ponta a ponta (start → confirmação → seleção de conta → callback),
  confirma a `Connection` via `GET /connections` direto no backend (não só na UI).

## Pendências registradas (fora de escopo desta entrega)

- Cadastro de empresa/unidade de negócio pela Web (telas 3.2/3.3 da especificação) —
  não existe backend para isso; autoprovisionamento é decisão de produto separada.
- Desafio real de step-up (senha/OTP) — depende do item 1.6.
- Integração real com Google Ads/Meta/WhatsApp (Fases 5–7) — este WP permanece
  simulado por decisão de escopo, nunca contata um provider real.
- Upload de logo, seleção de cor por color-picker — o contrato real (`colors`) é uma
  lista de strings; a UI usa texto livre (uma cor por linha), não um color-picker
  visual (nenhuma perda de funcionalidade real, só de refinamento visual, fora de
  escopo desta etapa por decisão já registrada — "funcionalidade primeiro, visual
  premium depois").

## Status

`WP-04 (Brand Kit + Conexões reais) — IMPLEMENTADO + TESTADO, PRONTO PARA REVISÃO.`
Onboarding completo (3.2/3.3) permanece fora de escopo, pendência registrada. Nenhum
merge/deploy nesta sessão.
