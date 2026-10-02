# WP-F05-03 — Transições de assinatura e entitlement

Data: 2026-10-02
Branch: `feat/f5-subscription-transitions`
Base confirmada: `main@d6042159a48c5652e00e03669e383682ed80d997`
Status desta evidência: `DONE_VERIFIED` no escopo funcional após merge e certificação pós-merge da `main`.

## CURRENT confirmado antes da implementação

- WP-F05-02 já estava integrado na `main`.
- troca de `plan_id` era recusada por `BILLING_PLAN_CHANGE_REQUIRES_POLICY`;
- `CANCELED` existia, mas sem fluxo HTTP de cancelamento/reativação;
- pagamento liquidado ativava entitlement, porém a cobrança não registrava o plano liquidado;
- regras comerciais de upgrade/downgrade/cancelamento/reativação não estavam configuráveis no catálogo.
## TARGET deste Work Package

- regras comerciais continuam sendo configuração externa por plano, nunca hardcode por tenant;
- upgrade/downgrade somente por transição explicitamente permitida no catálogo;
- entitlement do plano alvo somente após pagamento liquidado correspondente;
- cancelamento imediato somente quando explicitamente configurado;
- reativação somente via `PENDING_PAYMENT`, sem restaurar entitlement antes de novo pagamento;
- replay/idempotência, RBAC/step-up, auditoria e isolamento entre tenants preservados;
- pagamento tardio de cobrança antiga nunca reativa cancelamento nem promove plano incorreto.

## Implementação

O catálogo passa a suportar `plan_changes`, modo explícito de cobrança da transição, `cancellation_mode`, `reactivation_mode` e modo explícito de cobrança da reativação.
A assinatura passa a representar plano pendente e metadados de cancelamento/reativação.
A cobrança registra `plan_id`, permitindo ao webhook verificar qual plano foi efetivamente pago.
Novas superfícies HTTP:

- `POST /billing/subscription/change-plan`
- `POST /billing/subscription/cancel`
- `POST /billing/subscription/reactivate`

Todas exigem `BILLING_MANAGE`, step-up já governado pelo backend e `Idempotency-Key`.

Amostras versionadas em `config/plans.example.json` são deliberadamente fictícias e não representam oferta comercial real.

## Evidência local reproduzível

- testes focados iniciais: 40/40 PASS;
- catálogo + domínio + billing API após blindagens: 63/63 PASS;
- suíte de domínio completa final: 394/394 PASS;
- billing API isolado: 22/22 PASS antes das duas coberturas finais;
- `contracts/validate_events_asyncapi.py`: 24 eventos, todos os checks PASS;
- `git diff --check`: sem erro (somente aviso de normalização CRLF/LF no Windows).
A suíte API completa no host Windows executou 294 testes, mas terminou com 23 erros de limpeza de arquivos SQLite temporários (`WinError 32`: arquivo ainda aberto), todos em testes que removem bancos temporários. Isso não é usado como certificação verde. O gate definitivo permanece o CI Linux remoto da PR.

## Casos negativos cobertos

- transição não configurada no catálogo: fail-closed;
- target de transição inexistente: fail-closed;
- troca fora de assinatura `ACTIVE`: fail-closed;
- segunda troca enquanto outra está pendente: fail-closed;
- pagamento de plano diferente do plano aguardado: não promove entitlement;
- cobrança antiga liquidada após cancelamento: não reativa;
- cobrança do plano antigo liquidada durante upgrade pendente: não aplica plano alvo;
- cross-tenant em cancelamento: 404, sem mutação;
- cancelamento com replay da mesma idempotency key: resposta idêntica, sem duplicação lógica.

## Fora de escopo / blockers mantidos

- nomes, preços, franquias e políticas comerciais reais: `HUMAN_DECISION`;
- dunning/grace period/`PAST_DUE`: próximo bloco específico de F5;
- Asaas produção e credenciais reais: `EXTERNAL_CREDENTIAL` / `PRODUCTION_GATE`;
- produção, deploy e merge: não executados.

## Certificação pós-merge — 02/10/2026

- PR #39 mergeada por merge commit;
- merge commit: `921d7972f4feac187a6c44f66f32acbbc0746e24`;
- Backend Tests pós-merge run `37052759414` = `success`;
- Frontend Tests pós-merge run `37052761181` = `success`;
- F4 Platform CI pós-merge run `37052759430` = `success`;
- produção não foi tocada.

A seção histórica "Fora de escopo / blockers mantidos" acima registra o estado da branch antes
do merge. A referência "merge não executado" fica superseded por esta certificação
pós-merge, sem apagar a evidência original.
