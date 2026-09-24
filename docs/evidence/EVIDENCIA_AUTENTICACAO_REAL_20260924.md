# Evidência — autenticação real via Google Identity Platform (item 1.3/WP-02)

**Data:** 24/09/2026 · **ADRs:** ADR-0018 (sessão OAuth/OIDC via cookie), ADR-0022 (provedor:
Google Identity Platform) · **Branch:** `verify/wp02-auth-review` (base: `claude/sweet-mayer-xoiz25`,
commits `53eebb9` + `99e9dd0`, mais os dois achados corrigidos nesta branch).

## Histórico

A construção original (identity_provider.py, session.py, identity_directory.py,
routes_auth.py, e as mudanças em deps.py/state.py/main.py/models.py) foi feita por uma
sessão Claude Code irmã, por conta própria, enquanto esta sessão estava em modo de
planejamento aguardando duas decisões do Diretor (autorização de projeto Google Cloud e
estratégia de provisionamento de usuários) — decisões essas que acabaram não sendo
necessárias porque o WP-02, como especificado, nunca autoprovisiona usuário nenhum (ver
"Fail-closed" abaixo).

Esta sessão **verificou de forma independente** (nunca aceitando o auto-relato como prova):
leu o diff completo commit a commit, rodou a suíte de testes do zero no HEAD exato da
branch, e revisou os dois achados não bloqueantes que a sessão irmã reportou de seu próprio
`fm-security-review`. O Diretor decidiu corrigir os dois agora (não adiar); esta sessão
implementou as correções, adicionou testes para elas, e revalidou a suíte inteira antes do
merge.

## O que foi construído

- **`campaia_core/identity_provider.py`** — `FirebaseIdTokenVerifier` verifica o ID token do
  Google Identity Platform via `firebase-admin` (SDK oficial, nunca verificação
  JWT/JWKS feita à mão). `AlwaysRejectIdTokenVerifier` é o padrão quando nenhum projeto
  Firebase está configurado — **nunca** um simulador permissivo (diferente do padrão usado
  para IA/pagamento: um simulador permissivo de autenticação seria um buraco de segurança).
  `VerifiedIdentity` prova só QUEM é o usuário (subject/email/email_verified) — nunca
  tenant/role.

- **`api/identity_directory.py`** — `IdentityDirectory` resolve e-mail verificado → 
  `TokenPrincipal` (tenant_id/roles/business_unit_id). `InMemoryIdentityDirectory` +
  `seed_dev_identity_directory()` (6 usuários fixture, só em `test`/`dev-local`). Um e-mail
  verificado pelo Google mas sem vínculo aqui é **recusado**, nunca autoprovisionado —
  decisão do Diretor, fora do escopo deste item.

- **`api/session.py`** — sessão server-side real: cookie `HttpOnly`/`Secure`/`SameSite=Lax`
  carregando só um `session_id` opaco (nunca o JWT bruto), CSRF via double-submit
  (`csrf_secret` comparado com `hmac.compare_digest`), TTL absoluto de 24h sem refresh
  silencioso, `session_id`/`csrf_secret` sempre gerados novos no login (nunca reaproveita um
  valor vindo do cliente — proteção contra session fixation). `InMemorySessionStore` nesta
  etapa (reiniciar o processo desloga todo mundo — aceitável até o item 1.6 existir; não
  declarado pronto para produção por causa disso).

- **`api/routes_auth.py`** — `POST/DELETE /auth/session` (login/logout) e (adicionado nesta
  branch) `GET /auth/login-nonce`.

- **`api/deps.py`** — `require_auth` tenta a sessão real primeiro; só cai para o fixture de
  bearer de dev se não houver cookie de sessão nenhum (um cookie presente mas inválido/
  expirado nunca cai silenciosamente para o fixture). CSRF verificado em toda mutação.

- **`api/state.py`** — `AppState.env` (lido de `CAMPAIA_ENV`, default `"production"`).
  **Fail-closed por construção**: `__post_init__` levanta `RuntimeError` se o fixture de
  bearer de dev estiver populado fora de `env in {"test", "dev-local"}` — não é só "esconder
  a opção por padrão", é impossível de habilitar por engano em preview/staging/produção.

## Achados do `fm-security-review` da sessão irmã e como foram resolvidos

**Achado 1 — login-CSRF (severidade baixa)**: sem proteção, um site malicioso podia
disparar `POST /auth/session` com o **próprio** id_token do atacante; o navegador da vítima
processaria a resposta e receberia um `Set-Cookie` autenticado **como o atacante**
("forced login"). `SameSite=Lax` não cobre isso — o ataque não depende de enviar cookie
nenhum, só do navegador processar a resposta same-origin.

*Decisão do Diretor (24/09/2026): corrigir agora.*

**Correção**: nonce de pré-login com double-submit. `GET /auth/login-nonce` gera um valor
aleatório (`secrets.token_urlsafe(32)`), grava um cookie efêmero (`campaia_login_csrf`,
`HttpOnly`/`Secure`/`SameSite=Lax`, TTL 10 min) e devolve o mesmo valor no corpo.
`POST /auth/session` agora exige esse valor de volta em `login_csrf_token` e o compara em
tempo constante contra o cookie **antes** de sequer tentar verificar o `id_token` — um site
cross-origin não consegue ler o cookie (`HttpOnly`) nem forjar o par cookie+corpo sem ver a
resposta same-origin do `GET`.

**Achado 2 — `csrf_token` não recuperável sem novo login (funcional/UX, não segurança)**: o
`csrf_token` só vinha no corpo da resposta de login; uma aba recarregada ficava autenticada
para leitura (via cookie de sessão) mas incapaz de qualquer mutação sem logar de novo.

*Decisão do Diretor (24/09/2026): resolver agora, expor em `GET /me`.*

**Correção**: `MeResponse` ganhou o campo `csrf_token: str | None`. `GET /me` agora lê o
cookie de sessão e busca o `SessionRecord` correspondente para popular o campo; `None`
quando autenticado via fixture de bearer de dev/teste (que não tem sessão/CSRF nenhuma).

## Verificação

Suíte completa rodada **por esta sessão**, no HEAD exato da branch, após as duas correções:

```
python3 -m unittest discover -s tests           # 366 testes — domínio, OK
python3 -m unittest discover -s tests_api -t .  # 130 testes — API, OK
```

(490 relatados originalmente pela sessão irmã + 6 testes novos desta branch: nonce válido/
ausente/errado, login com nonce correto, `csrf_token` exposto via sessão real, `csrf_token`
ausente via fixture de bearer.)

Nenhuma rota de negócio (campanhas, aprovações, autonomia, billing, conexões) foi tocada —
confirmado por leitura direta do diff, não só pela descrição da sessão irmã. Nenhuma
credencial fixa em código. `deps.py`/`state.py` mantêm as assinaturas de
`require_auth`/`note_step_up_header`/`require_step_up`/`build_domain_principal` inalteradas
— zero raio de impacto nos arquivos de rota de negócio.

## Limitação registrada (não escondida)

`InMemorySessionStore` não sobrevive a reinício de processo nem é compartilhado entre
instâncias — aceitável nesta etapa porque o item 1.6 (infraestrutura real: Cloud SQL/Redis)
ainda não foi autorizado pelo Diretor. Isto **não** é declarado pronto para produção em
múltiplas instâncias; revisitar quando 1.6 avançar.

## Veredito

Item 1.3/WP-02 **CONCLUÍDO**: provedor de identidade real integrado, sessão server-side
real, CSRF (incluindo login-CSRF) mitigado, `fm-security-review` sem achado bloqueante, 496
testes verdes. Depende de 1.6 apenas para o *SessionStore* deixar de ser em memória — não
bloqueia o uso funcional do login real nem o avanço para a Etapa 2 (Web).
