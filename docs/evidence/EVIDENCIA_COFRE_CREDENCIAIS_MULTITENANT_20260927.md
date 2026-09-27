# Evidência — Cofre real de credenciais, por tenant (portado para o CURRENT autoritativo)

**Data:** 27/09/2026 · **Branch:** `reconciliation/campaia-final-takeover` (PR #31).

## Correção de rumo (histórico, para rastreabilidade)

O cofre foi implementado inicialmente sobre `feat/campaia-wp01-web-foundation` (PR #5,
commit `27000cbe2506843c45588292ccddc02136bd3a24`) por decisão do Diretor de 27/09/2026:
*"CampaIA é SaaS comercial multi-tenant... tudo que depender de configurações externas
tem que ser configurável [por cliente]"*.

Em seguida, o Diretor corrigiu o CURRENT autoritativo: a PR #5 estava 47 commits atrás
da PR #31 (`reconciliation/campaia-final-takeover`), que já havia reconciliado a PR #5
com a PR #6 (WP-06 a WP-11, correções de segurança, replay de OAuth, etc.). Este
documento registra o **porte** do cofre para esse CURRENT correto — não uma nova
construção.

## CURRENT confirmado antes de portar (verificação real, não presumida)

- `git rev-parse origin/reconciliation/campaia-final-takeover` → `5ddaa24103...` —
  confere exatamente com a PR #31 (`mcp__github__pull_request_read`, base `main`,
  60 commits ahead / 0 behind).
- `git rev-list --left-right --count origin/feat/campaia-wp01-web-foundation...origin/reconciliation/campaia-final-takeover`
  → `1  47` — confirma que a PR #5 tem exatamente 1 commit exclusivo (o do cofre) e está
  47 commits atrás.
- Comparação arquivo a arquivo do commit do cofre contra este CURRENT: `credential_vault.py`,
  `test_credential_vault.py` e `test_credential_vault_repository.py` **ausentes** (porte
  direto); `repositories.py`, `state.py`, `models.py`, `requirements.txt`, `bff-openapi.yaml`
  **presentes e idênticos** nos pontos tocados (adaptação de baixo risco); `routes_connections.py`
  **já contém o fix de replay do achado 24** (`state.idempotency.get(...)` antes de
  `redeem_oauth_state`) que a versão do cofre na PR #5 não tinha — preservado
  explicitamente ao adaptar, não sobrescrito.

## Portado / Adaptado

| Arquivo | Ação |
|---|---|
| `campaia_core/credential_vault.py` | PORT (idêntico à PR #5) |
| `tests/test_credential_vault.py` | PORT (idêntico à PR #5) |
| `tests_api/test_credential_vault_repository.py` | PORT (idêntico à PR #5) |
| `api/repositories.py` | ADAPT — `Connection.secret_ref` + `VaultRepository` |
| `api/state.py` | ADAPT — `vault`/`vault_cipher` + wiring SQLite |
| `api/models.py` | ADAPT — `OAuthCallbackRequest.credential` |
| `api/routes_connections.py` | ADAPT cuidadoso — lógica do cofre inserida **preservando** o fix de replay (achado 24) já existente no CURRENT |
| `requirements.txt` | ADAPT — só `cryptography==50.0.1` somado; `starlette==1.3.1` do CURRENT preservado (não revertido para `1.0.0`) |
| `contracts/bff-openapi.yaml` | ADAPT — campo `credential` documentado |
| `tests_api/test_connections_oauth.py` | ADAPT — nova classe `OAuthCallbackRealCredentialTests` acrescentada ao final; teste de replay (achado 24) já existente no CURRENT preservado sem alteração |

## Gates executados neste CURRENT, após o porte

| Gate | Resultado |
|---|---|
| Domínio (`backend/tests`) | `375 passed` (inclui os 7 testes portados do cofre) |
| API (`backend/tests_api`) | `193 passed` (inclui as 3 novas classes/testes de credencial real; o teste de replay do achado 24, já existente, permanece intacto e passando) |
| Contract drift (web) | `OK` |
| Contagem líquida de testes novos | `+15` (7 domínio + 5 repositório + 3 fluxo de credencial real no callback) — confirmado contando os métodos de teste adicionados, não por diff antes/depois (`git stash` não isola arquivos ainda não rastreados, então uma medição direta de baseline ficaria contaminada; a contagem líquida acima foi verificada por inspeção dos arquivos, não por essa comparação). |

Nenhuma regressão: o teste de replay do OAuth callback (achado 24) continua passando
sem modificação, prova de que a adaptação não regrediu a correção já consolidada na
PR #31.

## Pendência registrada — não alterada por este porte

A troca automática real de OAuth com o Google/Meta (redirecionamento server-side, sem o
refresh token nunca passar pelo browser) continua fora de escopo: exige Client OAuth tipo
"Aplicativo da Web" com domínio de callback publicado, inexistente hoje. Classificação:
`EXTERNAL_INFRASTRUCTURE`.

O uso de Fernet como cifra é adequado para esta fase, mas não deve ser documentado como
arquitetura final de produção. Hardening futuro registrado como pendência: key
versioning, key rotation, KMS/Secret Manager/HSM, envelope encryption, política de
retenção/backup, auditoria de acesso ao cofre.

## Status

`Cofre de credenciais multi-tenant — PORTADO e ADAPTADO ao CURRENT (PR #31),
IMPLEMENTADO + TESTADO, sem regressão.` Nenhum merge/deploy nesta sessão.
