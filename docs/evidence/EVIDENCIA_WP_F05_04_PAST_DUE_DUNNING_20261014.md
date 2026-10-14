# WP-F05-04 — PAST_DUE, grace period, dunning e recovery

**Data:** 14/10/2026  
**Base:** `main@13341f2fb077240199c98f5740552226ccf0f1ce`  
**Branch:** `feat/f5-past-due-dunning`  
**Status desta evidência:** `PARTIAL` até CI remoto da PR, merge autorizado e certificação pós-merge.

## Problema confirmado no CURRENT

Antes deste WP:

- `SubscriptionStatus.PAST_DUE` existia apenas nominalmente;
- não havia `past_due_at`, grace period ou agenda de dunning;
- entitlement em `PAST_DUE` era sempre bloqueado;
- `PAYMENT_OVERDUE`/status `OVERDUE` do Asaas não alterava lifecycle comercial;
- não havia recuperação explícita `PAST_DUE -> ACTIVE` com limpeza do estado de cobrança;
- falha de tentativa de pagamento não tinha auditoria própria.

## TARGET implementado

### Política comercial como dado

`PlanDefinition.dunning_policy` é opcional e externa ao código. Quando existe, contém:

- `grace_period_days`;
- `access_mode`: `ALLOW_DURING_GRACE` ou `BLOCK_IMMEDIATELY`;
- `reminder_offsets_days`: agenda ordenada de lembretes a partir de `past_due_at`.

Ausência de política impede a transição para PAST_DUE — fail-closed, sem inventar dias ou acesso.

### Lifecycle

- somente cobrança `REGULAR` identificada e do plano vigente pode marcar PAST_DUE;
- `PAYMENT_OVERDUE`/status `OVERDUE` marca a assinatura PAST_DUE;
- grace period governa entitlement pela política do plano;
- após o fim do grace, entitlement é bloqueado;
- pagamento confirmado da cobrança regular vencida recupera `PAST_DUE -> ACTIVE`;
- pagamento de upgrade/plan change não pode recuperar inadimplência do plano atual;
- assinatura PAST_DUE não gera nova cobrança regular até reconciliar a pendência.

### Dunning

O domínio calcula `next_dunning_reminder_at`, detecta quando a ação está vencida e registra
execução com `reminder_index` replay-safe.

Este WP **não envia e-mail/SMS** e **não solicita negativação** no Asaas. O canal de entrega é
separado do motor de estado. A documentação oficial do Asaas distingue `PAYMENT_OVERDUE`
(cobrança vencida) dos eventos de negativação `PAYMENT_DUNNING_REQUESTED` /
`PAYMENT_DUNNING_RECEIVED`; o CampaIA não conflui esses conceitos.

### Falha de tentativa

Eventos explícitos de tentativa recusada, como `PAYMENT_CREDIT_CARD_CAPTURE_REFUSED` e
`PAYMENT_REPROVED_BY_RISK_ANALYSIS`, são auditados como
`BILLING_PAYMENT_ATTEMPT_FAILED` sem bloquear prematuramente o entitlement. Apenas o
vencimento efetivo leva a PAST_DUE.

### API/contrato

`GET /billing/subscription` passa a expor:

- `past_due_at`;
- `grace_period_ends_at`;
- `past_due_in_grace`;
- `past_due_access_mode`;
- `dunning_reminders_sent`;
- `next_dunning_reminder_at`;
- `entitlement_access_active` já refletindo o grace.

OpenAPI e tipos TypeScript foram sincronizados. `GatewayChargeStatus` ganhou `OVERDUE`.

## Segurança e invariantes

- ausência de dunning_policy: fail-closed;
- cobrança legada sem plan_id: não marca PAST_DUE;
- cobrança de outro plano: não marca PAST_DUE;
- plan change/reactivation charge: não marca PAST_DUE;
- plan-change payment: não recupera PAST_DUE;
- replay do mesmo passo de dunning não incrementa contador;
- tentativa de pular índice de dunning falha fechada;
- webhook continua deduplicado por event id;
- cross-tenant comprovado em teste HTTP;
- cancelamento limpa estado de inadimplência;
- produção e credenciais reais não são necessárias para este WP.

## Evidência preflight

Run temporário: `38638081131` — `success`.

- 106/106 testes focados PASS:
  - subscription;
  - plan catalog;
  - Asaas gateway;
  - billing settlement;
  - billing API.
- OpenAPI types generation: PASS;
- contract drift: PASS;
- `git diff --cached --check`: PASS no artefato gerado;
- workflow temporário removido automaticamente após sucesso.

## Evidência externa consultada

Documentação oficial Asaas consultada em 14/10/2026:

- Eventos para cobranças: `PAYMENT_OVERDUE` = cobrança vencida;
- `PAYMENT_CREDIT_CARD_CAPTURE_REFUSED` = falha na captura de cartão;
- `PAYMENT_REPROVED_BY_RISK_ANALYSIS` = pagamento reprovado em análise;
- `PAYMENT_DUNNING_REQUESTED` e `PAYMENT_DUNNING_RECEIVED` pertencem ao processo separado
  de negativação.

## Fora de escopo / pendências F5

- política comercial real de dias/cadência: `HUMAN_DECISION`;
- envio real de lembretes por e-mail/SMS/WhatsApp;
- negativação/credit bureau: não autorizada e não implementada;
- UI comercial de billing;
- histórico de faturas/pagamentos;
- checkout/assinatura real;
- estorno/reembolso;
- credenciais Asaas produção / prova real de G5.

