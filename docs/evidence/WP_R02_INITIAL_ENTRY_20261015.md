# WP-R02-03 — Entrada inicial/trial pela Web

15/10/2026. Status: PARTIAL até CI/revisão/integração. F5/G5 continuam PARTIAL.

## CURRENT / lacuna

Repo faabio3131/f-m-tecnologia-campaia, base main@f3428e6eb4a2c476a258d1f2bb7c2cb4c6907ce2.
Checkout inicialmente limpo, nenhuma PR aberta na consulta inicial. PRs #45/#46 integradas
com autorização e CI pós-merge verde. Web já consultava plano/catálogo/histórico e lifecycle,
mas, sem assinatura, só mostrava um estado vazio; iniciar trial exigia cliente HTTP técnico.
Motor, Asaas, entitlements e todos os cenários anteriores preservados.

## TARGET implementado

- OWNER/FINANCE escolhem um plano do catálogo configurado e informam documento do titular.
- Trial é opt-in e aparece apenas quando a duração existe no plano. Sem opção pré-selecionada.
- Revisão explícita mostra plano, mensalidade, franquia e duração do trial ou estado pendente.
- Confirmação usa PUT /billing/subscription existente, CSRF e step-up compartilhados.
- Pedido sem trial permanece PENDING_PAYMENT, com acesso pago bloqueado. Nenhuma cobrança
  ou link de pagamento é gerado automaticamente por esta confirmação.
- Corpo e chave permanecem estáveis no retry; campos ficam congelados durante a confirmação.
  Documento permanece apenas no estado transitório do formulário e é descartado ao concluir
  ou trocar tenant/unidade/membership. Nenhum storage de navegador é usado.
- initial_only=true recusa qualquer assinatura já existente, sem sobrescrever documento,
  período de trial, status ou condições. É obrigatório informar a versão revisada nesse fluxo.
- Fingerprint SHA-256 canônico inclui todas as condições do PlanDefinition, inclusive
  entitlements/lifecycle. Alteração no catálogo devolve 409 antes de criar assinatura/trial.
- Valores/trial não são decididos em código. Sem catálogo/planos, a criação não é disponibilizada.
- Correção identificada: PUT legado de atualização documental usava o plano recarregado do
  catálogo e podia repricificar o contrato silenciosamente. Agora conserva existing.plan;
  mudança comercial continua nos fluxos explícitos existentes.
- Auditoria inclui fingerprint efetivo e initial_only, sem adicionar documento ao evento.
- Contratos/tipos sincronizados; campos novos de entrada opcionais para compatibilidade
  com clientes existentes. Mecanismo inicial create-only exige fingerprint na API.

## Verificação local

- Backend domínio completo: 409 testes, OK.
- Backend API completo: 320 testes, OK, 17 skipped pela dependência PostgreSQL local.
- Billing API focado: 44 testes, OK.
- Web check: lint, tipos, contrato, fronteiras, 89 testes em 23 arquivos e build, OK.
- Cinco novos casos API: pending/replay/segunda criação; auth/RBAC/step-up/escopo/revisão;
  drift de preço/trial; trial não reiniciado; documento sem repricing do contrato.
- Cinco novos casos Web: revisão/trial, pending sem acesso, retry com corpo/chave/CSRF/step-up,
  step-up/read-only e rejeição por condições alteradas.
- Novo PostgreSQL CI: duas instâncias criam com chaves diferentes; exatamente uma vence
  (200), outra recebe 409; o mesmo trial fica visível entre workers, sem cobrança emitida.
- E2E de Billing substitui o seed técnico do trial por formulário real: selecionar plano,
  documento, opt-in, revisão e confirmação na UI; conserva testes de cancelamento/reativação,
  histórico SIMULATOR e isolamento de outro tenant. Dados fictícios, IdP determinístico,
  Next/Starlette reais; nenhuma chamada financeira externa.
- Chromium local continua indisponível por restrição de download anteriormente registrada;
  não se declara E2E/visual local aprovado. CI da PR valida navegador e PostgreSQL;
  resultado final no HEAD exato será registrado na PR antes de solicitar integração.

## Fora de escopo / gates remanescentes

Esta entrega fecha a entrada inicial da assinatura/trial na Web, não o checkout financeiro.
A UI informa expressamente que a confirmação não emite cobrança e que o fluxo de pagamento
continua em conclusão. Não é prova de pagamento, oferta comercial publicada nem ativação paga.

TARGET/HUMAN_DECISION: consumo persistente por competência e regra de conversão em créditos,
tabela/políticas comerciais reais e termos de ciclo/cobrança. CostLedger atual em memória
não é convertido nem exposto como saldo comercial. Checkout financeiro completo e E2E real
pagamento -> webhook -> entitlement permanecem TARGET/EXTERNAL_CREDENTIAL/PRODUCTION_GATE
conforme ambiente. Histórico/fatura hospedada já existentes são preservados.

Nenhum merge, deploy, migration real, conta, credencial real, pagamento, anúncio ou
religamento do Cloud SQL. Última prova externa do banco permanece STOPPED / NEVER.
