# WP-R02-12 — Retirada comprovada de renovação aberta

CURRENT: main@aa8149beee25a2197bc27283c5e7faf927da0e4e, PR #55 integrada.
PR #55 no HEAD f201cb3a67252fd126e6700e797a71bcb315075b: Backend 38824394290,
Frontend 38824394291, F4 38824394279 SUCCESS.
Pós-merge: Backend 38824613743, Frontend 38824613719, F4 38824613737 SUCCESS.

## Delta

Uma renovação que já continha excedente impedia o fechamento final, inclusive após
encerramento. Agora o histórico oferece revisão/retirada da invoice aberta do próximo
ciclo não pago do mesmo lifecycle encerrado. Não permite retirar uma fatura quitada,
o financiamento do período já pago, FINAL_USAGE, outro tenant/lifecycle/ambiente ou
uma cobrança em revisão. Snapshot, valor, identidade e contexto são conferidos novamente
no backend; nenhum valor/status de pagamento vem do cliente.

POST /billing/charges/{gatewayChargeId}/withdraw exige BILLING_MANAGE, autenticação
recente, CSRF, aceite estrito, fingerprint e idempotência por ator/unidade/fatura/revisão.
Reutiliza F3, a obrigação congelada e as fences existentes. Preserva invoice, obrigação,
consumo entregue, dedupe, fatos financeiros e histórico; não os apaga para liberar o fluxo.

Intent e fence de exclusão são commitados antes da chamada externa. Existe uma tentativa
de DELETE; após timeout/restart/outra chave/worker, somente GET da invoice conhecida.
Não existe expiração/reset automático da fence, nem 404 interpretado como exclusão.
Resposta exige ID/ambiente/valor compatíveis, deleted booleano true e status não pago
conhecido. A confirmação local é atômica com auditoria; falha de commit recupera por GET.
Uma tentativa que falhe antes de enviar o DELETE também fica incerta e exige conciliação;
segurança financeira tem precedência sobre repetir uma operação externa desconhecida.

Asaas faz GET vinculado à externalReference congelada, permite apenas PENDING/OVERDUE,
DELETE do ID e readback. Retirada não equivale a estorno ou devolução. Simulator persiste
a exclusão fictícia no store injetado para recuperação entre workers, sem dinheiro real.
Uma prova de retirada resolve a pendência da invoice antiga sem mudar seu valor/status
histórico para SETTLED. O excedente entregue pode então ser emitido sozinho em FINAL_USAGE;
se quitado, a reativação exige nova contratação integral, sem novo trial ou franquia grátis.
Fatura vencida com retirada comprovada não continua bloqueando a reativação como dívida ativa.

Pagamento confirmado durante/depois da intenção ou restauração posterior vira
CANCELLATION_CONFLICT. Não reativa, não concede franquia, não é apagado por consulta simples
e bloqueia novos fechamentos/obrigações até resolução própria. Um recebimento compatível
observado antes da resolução conserva o fato financeiro; não é convertido em gratuidade.
A observação disponível não é prova de irreversibilidade bancária: pagamento concorrente,
restauração ou ajuste posterior continuam sujeitos à conciliação financeira, nunca a nova
cobrança automática para compensar um conflito.

Web exige revisão e checkbox, mantém a chave em resultado incerto, mostra retirada sem
quitação/reembolso e horário específico da prova. Oculta o link da invoice em retirada ou
retirada confirmada. Consulta/retirada atualiza assinatura, saldo e fechamento sem perder o
contexto nem duplicar componentes; chaves React checkout/usage/closure continuam distintas.

## Validação

Local: domínio 430; API 407 (20 PostgreSQL no CI); Web 113 testes e
lint/types/contratos/boundaries/build verdes. Testes novos cobrem valor/ambiente/status/deleted
inválidos, aceite/RBAC/step-up, isolamento, replay/contexto, duas instâncias, timeout antes e
depois da exclusão, restart, rollback da prova, pagamento/restauração concorrente e excedente
final sem outra mensalidade. Duas asserções iniciais de contagem foram corrigidas: a fixture
sem trial possui um OPEN pago, não dois; não foi alterado o comportamento do ledger.

Novo teste PostgreSQL verifica intent visível em outra conexão antes do efeito, timeout
após exclusão e recuperação por outro worker sem segundo DELETE. O E2E de checkout existente
continua como regressão no CI; o novo botão tem teste de componente com revisão e retry.
CI completa no HEAD exato, incluindo PostgreSQL e browser, ainda é requisito para merge.

Referências primárias consultadas em 15/10/2026:
- https://docs.asaas.com/reference/excluir-cobranca
- https://docs.asaas.com/reference/recuperar-uma-unica-cobranca
- https://docs.asaas.com/docs/webhook-para-cobrancas

## Próximo delta e gates

F5/G5 permanece PARTIAL. Resolução de conflitos, refunds/chargebacks, garantia de primeira
contratação, ajustes após fechamento, scheduler/dunning e entrega real de avisos continuam
pendentes. Não presumir mínimo/meio/valor real homologado a partir do simulator ou destes
testes. Catálogo comercial real segue desabilitado; custos/jurídico/fiscal/homologação e
produção mantêm gates próprios. Nenhuma revisão independente de segurança nesta etapa.

Sem nova migration, deploy, credencial, exclusão externa real, estorno, cobrança ou
religamento Cloud SQL. Rollback requer bloquear/drenar writers financeiros/IA e manter
compatibilidade com ChargeResult.deleted e os novos registros/resultados F3. Não apagar
intent/fence/prova/audit para permitir repetir uma exclusão desconhecida.
