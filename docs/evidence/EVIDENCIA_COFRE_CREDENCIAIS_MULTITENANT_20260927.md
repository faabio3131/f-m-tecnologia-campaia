# Evidência — Cofre real de credenciais, por tenant (correção de rumo do Bloco 2/3)

**Data:** 27/09/2026 · **Branch:** `feat/campaia-wp01-web-foundation` (PR #5).

## DECISÃO (autoridade humana, 27/09/2026)

Diretor: *"Isso aqui é um aplicativo comercial... tudo que depender de configurações
externas, bancária, gateway, tem que ser configurável [por cliente], eu não posso mexer
no código só para configurar o cliente."*

Isso corrigiu uma direção errada que eu estava prestes a seguir na Fase 5 do Prompt
Mestre 2 (construir o adaptador do Google Ads dependendo de variáveis de ambiente
globais para credenciais específicas de conta). A arquitetura correta (multi-tenant,
cada cliente conecta a própria conta pelo produto) já estava parcialmente desenhada no
código (`SecretRef`, invariante I-03 de `connectors.py`), mas a peça real — o cofre —
nunca tinha sido construída.

## CURRENT confirmado antes de codificar

Leitura real do código (não presumida):

- `campaia_core/connectors.py` já documentava a invariante I-03 ("credencial nunca
  transita como argumento; o conector resolve pelo `external_account_id` contra o
  cofre") e definia `SecretRef` (referência opaca, `repr` redigido).
- `payment_gateway.py`, `asaas_gateway.py`, `simulator.py`, `gemini_provider.py` já
  usavam o padrão `SecretRef`/`vault://provider/handle` — mas **nenhum armazenamento
  real existia por trás desse handle** em lugar nenhum do repositório.
- `api/repositories.py`: `Connection` **não tinha nenhum campo de segredo**.
- `api/routes_connections.py::oauth_callback`: comentário do próprio código confirmava
  *"Ainda simulado (nenhum provider real é contatado)"* — `external_account_id` vinha
  direto do cliente, sem nenhuma troca real de OAuth.
- `backend/requirements.txt` não listava `cryptography` (só estava presente como
  dependência transitiva de `firebase-admin`).

## Construído

### `campaia_core/credential_vault.py` (novo)

Módulo puro de domínio (sem I/O): `CredentialCipher` (Fernet/AES real, via
`cryptography`), chave lida de `CAMPAIA_VAULT_KEY` — fail-closed (`VaultKeyMissing`) se
ausente ou malformada, nunca uma chave padrão. `VaultDecryptionFailed` distinto de
"não encontrado" (isso é erro do repositório).

### `api/repositories.py`

- `Connection` ganhou `secret_ref: str | None = None`.
- `VaultRepository` (novo): `store`/`resolve`/`revoke`, por tenant, com o mesmo padrão
  de persistência SQLite opcional dos outros repositórios (`db.table("credential_vault")`).
  `resolve()` de um tenant diferente do dono levanta `VaultAccessDenied` — nunca decifra
  cross-tenant, mesmo com a chave certa.

### `api/state.py`

- `AppState.vault: VaultRepository` e `AppState.vault_cipher: CredentialCipher | None`
  (`None` quando `CAMPAIA_VAULT_KEY` não está configurada — mesma disciplina de
  `_default_ai_provider`/`_default_billing_gateway`: nunca crasha o app inteiro por uma
  integração externa opcional ausente).
- Ligação ao SQLite quando `db_path` está setado (`self.vault = VaultRepository(self.db.table("credential_vault"))`).

### `api/routes_connections.py` + `api/models.py`

- `OAuthCallbackRequest.credential: dict | None` (novo, opcional). Quando presente, a
  credencial é guardada de verdade no cofre (criptografada, por tenant) e a `Connection`
  passa a ter `mode=TEST` e `secret_ref` preenchido. Sem `credential`, comportamento
  idêntico ao anterior (`mode=SIMULATOR`, sem segredo).
- Sem `CAMPAIA_VAULT_KEY` configurada, enviar `credential` falha com `422
  VALIDATION_FAILED` explícito — nunca descarta o token silenciosamente.
- `revoke_connection` agora também revoga o segredo real no cofre, se existir.

### Contrato

- `POST /connections/oauth/callback`: campo `credential` documentado (opcional,
  nullable), com nota explícita sobre o estado real da redireção OAuth (ver Pendência).
- `contracts:generate` + `contracts:check` executados — tipos do Web regenerados e sem
  drift.

### `backend/requirements.txt`

- `cryptography==50.0.1` adicionado explicitamente (antes só transitiva).

## Gates executados

| Gate | Resultado |
|---|---|
| Testes de domínio (`backend/tests`, `unittest`) | `375 passed` (368 prévios + 7 novos do cofre) |
| Testes de API (`backend/tests_api`, `unittest`) | `166 passed` (163 prévios + 3 novos do fluxo de credencial real) |
| Contrato YAML (parse) | `OK`, 25 paths |
| Contract drift (web) | `OK` |
| Typecheck (web) | `OK` |

## Pendência registrada — NÃO construída nesta etapa

A **troca automática real de OAuth com o Google/Meta** (redirecionar o tenant para a
tela de consentimento real do provedor e receber o `code` de volta no domínio da
própria CampaIA) continua fora de escopo desta entrega. Motivo real, confirmado hoje: o
Client OAuth "Aplicativo para computador" configurado no ambiente Google Cloud não
suporta URI de redirecionamento arbitrária; um Client tipo "Aplicativo da Web" com
domínio de callback publicado é necessário, e a Web da Nova FM ainda não está em
produção. Isso não bloqueia o cofre (que é real e testado) — só o passo de "conversar
com o Google automaticamente" continua manual/pendente.

## Status

`Cofre de credenciais multi-tenant — IMPLEMENTADO + TESTADO.` Corrige a direção
arquitetural do Bloco 2/3 antes de qualquer adaptador de provedor real ser construído
sobre ele. Nenhum merge/deploy nesta sessão.
