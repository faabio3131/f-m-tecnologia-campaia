# Correção dos achados #3 e #5 do fm-security-review (idempotência e webhook)

**Data:** 24/09/2026 · **A pedido de:** Fábio Aluizio da Silva, imediatamente após o relatório
de `fm-security-review`/`fm-certify-change`.

## Achado #3 — idempotência de cobrança só em memória

**Problema:** `PaymentGatewaySimulator` e `AsaasGateway` guardavam cobranças já criadas num
dicionário privado do processo (`_created`). Reiniciar o processo entre criar uma cobrança e
confirmá-la perdia essa memória — um retry depois do reinício poderia gerar uma segunda
cobrança real no Asaas.

**Correção:** em vez de inventar um mecanismo novo, reaproveitado o que já existe no domínio:

- `payment_gateway.py` ganhou `IdempotencyStoreLike`, um `Protocol` que descreve a mesma forma
  de `campaia_core.infra.IdempotencyStore` (em memória, já existente) e de
  `api.db.PersistentIdempotencyStore` (persistida em SQLite/Postgres, já existente) —
  `.execute(tenant_id, idempotency_key, operation) -> (resultado, foi_replay)`.
- `PaymentGatewaySimulator` e `AsaasGateway` agora recebem `idempotency: IdempotencyStoreLike`
  como campo injetável, com `IdempotencyStore()` em memória como padrão — **comportamento
  observável inalterado** para quem não passar nada (todos os testes preexistentes continuam
  passando sem modificação).
- Quando este motor for integrado a `api/` (ainda não é — decisão deliberada, mesmo padrão do
  B5/pacing), basta construir o gateway passando `idempotency=PersistentIdempotencyStore(tabela)`
  para a garantia sobreviver a um reinício de processo. Nenhuma reescrita do gateway.

**Prova:** 2 testes novos (`test_payment_gateway.py`,
`test_idempotency_survives_a_process_restart_via_shared_external_store`;
`test_asaas_gateway.py`, mesmo nome) — duas instâncias de gateway compartilhando o mesmo
`IdempotencyStore` externo (simulando duas execuções do processo) devolvem o mesmo
`gateway_charge_id`, e no caso do Asaas, **nenhuma chamada de rede nova é feita** na segunda
instância.

## Achado #5 — sem webhook de confirmação de pagamento

**Problema:** a única forma de saber se uma cobrança foi paga era consultar o Asaas
(`get_charge_status`, polling) — não reage em tempo real e não cobre eventos pós-liquidação.

**Pesquisa feita antes de codificar (não presumido):** confirmado contra a documentação oficial
do Asaas (docs.asaas.com/docs/duvidas-frequentes-webhooks) que o Asaas **não assina o corpo do
webhook com HMAC** — ele repete, no header `asaas-access-token`, o mesmo token estático
configurado na criação do webhook. Isso é diferente do desenho HMAC(timestamp+corpo) que já
existe em `campaia_core/webhooks.py`, pensado para outro tipo de provedor — forçar esse desenho
sobre o Asaas produziria um receptor que não funcionaria contra o webhook real. Confirmado
também o formato real do payload: `{"id": "evt_...", "event": "PAYMENT_RECEIVED", "payment":
{"id": "pay_...", "status": "RECEIVED", ...}}`, com entrega "pelo menos uma vez" (dedupe por
`id` necessário).

**Correção:**

- Novo `campaia_core/asaas_webhook.py`: `AsaasWebhookReceiver` (verificação do token em tempo
  constante via `hmac.compare_digest`, dedupe por `id` do evento, reaproveitando
  `RejectionReason`/`WebhookVerdict` já existentes em `webhooks.py` em vez de duplicá-los) e
  `parse_asaas_payment_event` (extrai `event_id`/`event_type`/`payment_id`/`status` do payload
  real, falha fechado se faltar campo).
- `asaas_gateway.map_asaas_status` (antes `_map_status`, privada) tornada pública, para o
  webhook reusar exatamente a mesma tabela de mapeamento de status usada pelo polling — nunca
  duas fontes de verdade para a mesma classificação.
- `billing_settlement.py` ganhou `try_settle_from_status(charge, status, *, settled_at)`,
  extraído de `try_settle` (que agora só resolve o status via polling e delega pra essa
  função) — um webhook chama `try_settle_from_status` direto com o status já mapeado do
  evento, sem nenhuma chamada de rede adicional ao Asaas.

**O que esta correção NÃO fez:** não construiu a rota HTTP que recebe o webhook de verdade
(isso é `api/`, que ainda não integra este motor de cobrança — mesma decisão deliberada de
escopo já tomada para o resto do B11). O que existe agora é a lógica de domínio completa e
testada — verificar, deduplicar, interpretar o evento e liquidar — pronta para ser chamada por
uma rota quando essa integração acontecer.

**Prova:** `tests/test_asaas_webhook.py` (17 testes: verificação de token, dedupe, parsing do
payload real, e um teste de ponta a ponta provando webhook → status → fato liquidado sem
nenhuma chamada de rede).

## Testes

```
cd backend && python3 -m unittest discover -s tests        # 338 OK (321 + 17 novos)
cd backend && python3 -m unittest discover -s tests_api -t .   # 81 OK, inalterado
```

Zero regressão. Nenhum teste preexistente precisou ser alterado para acomodar a mudança de
assinatura (os novos parâmetros têm valor padrão).
