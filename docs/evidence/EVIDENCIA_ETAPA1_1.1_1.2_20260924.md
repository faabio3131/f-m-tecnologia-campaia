# Evidência — Etapa 1, itens 1.1 e 1.2 do cronograma mestre

**Data:** 24/09/2026 · **HEAD de partida:** `main` em `4c30bba` (PR #16, "Cronograma mestre
de finalização"). **Branch de trabalho:**
`fix/webhook-dedupe-persistido-e-rate-limit`.

Baseline confirmado por execução real antes de qualquer mudança: `python3 -m unittest
discover -s tests` (338 testes de domínio) e `python3 -m unittest discover -s tests_api -t .`
(97 testes de API), ambos `OK`.

## Item 1.1 — Dedupe do webhook do Asaas persistido (não só em memória)

**Achado (já registrado em `docs/evidence/FM_SECURITY_REVIEW_BILLING_ASAAS_20260924.md`,
achado #5, e no próprio cronograma):** `AsaasWebhookReceiver` e o `WebhookReceiver` genérico
guardavam o conjunto de eventos já vistos (`_seen`) como atributo em memória do próprio
objeto. O Asaas documenta entrega "pelo menos uma vez" — o mesmo evento pode chegar
novamente depois de um restart de processo. Sem persistência, um restart entre a primeira e
a segunda entrega do mesmo evento perdia a garantia contra reprocessar (risco concreto: um
evento `PAYMENT_RECEIVED` processado duas vezes não duplica cobrança — `try_settle_from_status`
já é idempotente por natureza no fato fiscal —, mas duplica efeitos colaterais como
auditoria e, no futuro, qualquer hook adicional acoplado ao dedupe).

**Correção — mesmo padrão já estabelecido para `IdempotencyStoreLike`
(`payment_gateway.py`)**, injeção de dependência em vez de um mecanismo paralelo:

- `campaia_core/webhooks.py`: novo `SeenEventStoreLike` (Protocol) + `InMemorySeenEventStore`
  (comportamento padrão, idêntico ao anterior). `WebhookReceiver` e `AsaasWebhookReceiver`
  passam a receber `seen_store: SeenEventStoreLike` em vez de manter o `set` internamente.
- `api/db.py`: novo `PersistentSeenEventStore`, SQLite-backed, mesma forma de
  `PersistentIdempotencyStore` (chave composta `provider\x1fevent_id`, get-then-put — mesma
  limitação de não-atomicidade sob concorrência real já aceita e documentada para
  `PersistentIdempotencyStore`, proporcional ao estágio atual: uma conexão, sem worker pool).
- `api/state.py`: quando `db_path` é configurado, `AppState.__post_init__` reconstrói
  `self.asaas_webhook` com `seen_store=PersistentSeenEventStore(...)`. `db_path=None`
  (padrão) permanece 100% em memória, comportamento anterior inalterado.

**Teste que prova o achado antes da correção → agora prova a correção:**
`tests_api/test_persistence.py::TestAsaasWebhookDedupeSurvivesRestart
.test_duplicate_event_after_restart_is_still_rejected` — sobe um cliente, entrega um evento,
derruba o processo (`teardown_client`: fecha a conexão SQLite, `gc.collect()`), sobe um
processo novo apontando para o mesmo arquivo, reentrega o mesmo `id` de evento e confirma
`accepted: false, reason: DUPLICATE`; confirma também que um evento nunca visto continua
sendo aceito normalmente na instância nova (a persistência só bloqueia o que já foi visto).

## Item 1.2 — Rate limiting no endpoint público `/webhooks/asaas`

**Achado:** `/webhooks/asaas` é o único endpoint deste app sem autenticação de usuário — é
chamado pelo Asaas, não por um Bearer token de sessão. Sem limite de taxa, é o único alvo de
flood de aplicação de uma única origem (mesmo sem token válido: cada requisição, válida ou
não, custa processamento).

**Correção:** `campaia_core/rate_limit.py` — `FixedWindowRateLimiter`, domínio puro (sem
I/O), janela fixa por chave (IP de origem), falha fechado quando a chave está vazia. Não é
defesa contra um atacante distribuído (muitos IPs) — é defesa contra volume sustentado de uma
única origem, a ameaça proporcional ao estágio atual do produto (um processo, sem
Redis/infra de rate limit compartilhada). Limite atual: 60 requisições/minuto por IP,
generoso o bastante para nunca recusar tráfego legítimo do Asaas.

`api/state.py`: novo campo `AppState.asaas_webhook_rate_limiter`, deliberadamente em memória
mesmo com `db_path` configurado (um contador de janela de 1 minuto não tem valor em
sobreviver a um restart). `api/routes_billing.py::asaas_webhook`: a verificação de rate limit
é a PRIMEIRA coisa que a rota faz, antes até da verificação do token — um token inválido não
deve custar processamento ilimitado. Excedente responde `429 {"accepted": false, "reason":
"RATE_LIMITED"}`, sem detalhe de quanto falta (não ajuda quem está testando o limite, e o
Asaas reenvia notificações legítimas de qualquer forma independente do motivo do não-2xx).

**Testes:**
- `tests/test_rate_limit.py` (5 testes de domínio): permite até o limite, recusa acima do
  limite na mesma janela, reseta após a janela expirar, chaves independentes não interferem
  entre si, chave vazia falha fechado.
- `tests_api/test_billing.py::AsaasWebhookTests
  .test_excess_requests_from_the_same_origin_are_rate_limited`: prova via HTTP real que a
  quarta requisição da mesma origem (limite ajustado para 3 neste teste) recebe 429, e que
  isso vale mesmo com token inválido.

## Testes executados neste HEAD (branch `fix/webhook-dedupe-persistido-e-rate-limit`)

- `python3 -m unittest discover -s tests` → **343 testes, OK** (338 + 5 novos de
  `test_rate_limit.py`).
- `python3 -m unittest discover -s tests_api -t .` → **99 testes, OK** (97 + 1 novo de
  dedupe persistido em `test_persistence.py` + 1 novo de rate limit em `test_billing.py`).

Nenhuma regressão nos testes pré-existentes.

## Limitações conhecidas, registradas e não escondidas

- `PersistentSeenEventStore.mark_if_new`: get-then-put não é atômico sob concorrência real
  para a mesma chave (mesma limitação já aceita em `PersistentIdempotencyStore`).
- `FixedWindowRateLimiter`: por processo, não compartilhado entre réplicas — se este BFF
  algum dia rodar com mais de um worker/processo, cada um terá sua própria janela (o limite
  efetivo escala com o número de processos). Aceitável hoje (um processo); registrar como
  requisito se/quando a implantação ganhar múltiplas réplicas (ADR-0019 já aponta contêineres
  no Google Cloud — quando isso virar >1 réplica, este limitador precisa de um contador
  compartilhado, ex. Redis).
- Rate limit por IP não distingue um NAT/proxy legítimo compartilhando IP de um atacante
  único — mesma limitação de qualquer rate limit por IP; proporcional ao estágio atual.
