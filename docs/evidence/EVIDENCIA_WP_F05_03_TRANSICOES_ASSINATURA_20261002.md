# WP-F05-03 â€” TransiÃ§Ãµes de assinatura e entitlement

Data: 2026-10-02
Branch: `feat/f5-subscription-transitions`
Base confirmada: `main@d6042159a48c5652e00e03669e383682ed80d997`
Status desta evidÃªncia: `PARTIAL` atÃ© CI remoto e eventual merge/pÃ³s-merge.

## CURRENT confirmado antes da implementaÃ§Ã£o

- WP-F05-02 jÃ¡ estava integrado na `main`.
- troca de `plan_id` era recusada por `BILLING_PLAN_CHANGE_REQUIRES_POLICY`;
- `CANCELED` existia, mas sem fluxo HTTP de cancelamento/reativaÃ§Ã£o;
- pagamento liquidado ativava entitlement, porÃ©m a cobranÃ§a nÃ£o registrava o plano liquidado;
- regras comerciais de upgrade/downgrade/cancelamento/reativaÃ§Ã£o nÃ£o estavam configurÃ¡veis no catÃ¡logo.
## TARGET deste Work Package

- regras comerciais continuam sendo configuraÃ§Ã£o externa por plano, nunca hardcode por tenant;
- upgrade/downgrade somente por transiÃ§Ã£o explicitamente permitida no catÃ¡logo;
- entitlement do plano alvo somente apÃ³s pagamento liquidado correspondente;
- cancelamento imediato somente quando explicitamente configurado;
- reativaÃ§Ã£o somente via `PENDING_PAYMENT`, sem restaurar entitlement antes de novo pagamento;
- replay/idempotÃªncia, RBAC/step-up, auditoria e isolamento entre tenants preservados;
- pagamento tardio de cobranÃ§a antiga nunca reativa cancelamento nem promove plano incorreto.

## ImplementaÃ§Ã£o

O catÃ¡logo passa a suportar `plan_changes`, modo explÃ­cito de cobranÃ§a da transiÃ§Ã£o, `cancellation_mode`, `reactivation_mode` e modo explÃ­cito de cobranÃ§a da reativaÃ§Ã£o.
A assinatura passa a representar plano pendente e metadados de cancelamento/reativaÃ§Ã£o.
A cobranÃ§a registra `plan_id`, permitindo ao webhook verificar qual plano foi efetivamente pago.
Novas superfÃ­cies HTTP:

- `POST /billing/subscription/change-plan`
- `POST /billing/subscription/cancel`
- `POST /billing/subscription/reactivate`

Todas exigem `BILLING_MANAGE`, step-up jÃ¡ governado pelo backend e `Idempotency-Key`.

Amostras versionadas em `config/plans.example.json` sÃ£o deliberadamente fictÃ­cias e nÃ£o representam oferta comercial real.

## EvidÃªncia local reproduzÃ­vel

- testes focados iniciais: 40/40 PASS;
- catÃ¡logo + domÃ­nio + billing API apÃ³s blindagens: 63/63 PASS;
- suÃ­te de domÃ­nio completa final: 394/394 PASS;
- billing API isolado: 22/22 PASS antes das duas coberturas finais;
- `contracts/validate_events_asyncapi.py`: 24 eventos, todos os checks PASS;
- `git diff --check`: sem erro (somente aviso de normalizaÃ§Ã£o CRLF/LF no Windows).
A suÃ­te API completa no host Windows executou 294 testes, mas terminou com 23 erros de limpeza de arquivos SQLite temporÃ¡rios (`WinError 32`: arquivo ainda aberto), todos em testes que removem bancos temporÃ¡rios. Isso nÃ£o Ã© usado como certificaÃ§Ã£o verde. O gate definitivo permanece o CI Linux remoto da PR.

## Casos negativos cobertos

- transiÃ§Ã£o nÃ£o configurada no catÃ¡logo: fail-closed;
- target de transiÃ§Ã£o inexistente: fail-closed;
- troca fora de assinatura `ACTIVE`: fail-closed;
- segunda troca enquanto outra estÃ¡ pendente: fail-closed;
- pagamento de plano diferente do plano aguardado: nÃ£o promove entitlement;
- cobranÃ§a antiga liquidada apÃ³s cancelamento: nÃ£o reativa;
- cobranÃ§a do plano antigo liquidada durante upgrade pendente: nÃ£o aplica plano alvo;
- cross-tenant em cancelamento: 404, sem mutaÃ§Ã£o;
- cancelamento com replay da mesma idempotency key: resposta idÃªntica, sem duplicaÃ§Ã£o lÃ³gica.

## Fora de escopo / blockers mantidos

- nomes, preÃ§os, franquias e polÃ­ticas comerciais reais: `HUMAN_DECISION`;
- dunning/grace period/`PAST_DUE`: prÃ³ximo bloco especÃ­fico de F5;
- Asaas produÃ§Ã£o e credenciais reais: `EXTERNAL_CREDENTIAL` / `PRODUCTION_GATE`;
- produÃ§Ã£o, deploy e merge: nÃ£o executados.
