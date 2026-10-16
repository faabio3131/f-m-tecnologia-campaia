# WP-R02-14 — Pedido auditável de garantia do primeiro pagamento

CURRENT: main@2356746585221315ea15b199ecc7d8e074fe8ef2, PR #57 integrada.
PR #57 no HEAD 6f1bc2b68d5cf0cbd333f80c1015901cbc6c0360: Backend 38826523409,
Frontend 38826523419, F4 38826523413 SUCCESS.
Pós-merge: Backend 38826736302, Frontend 38826736520, F4 38826736353 SUCCESS.
Data deste WP: 16/10/2026 UTC. Implementa parte da política comercial V1 aprovada,
preservando gates de homologação, custos, fiscal, jurídico e produção.

## Delta

O motor já construía um fato liquidado após confirmação/valor compatível, mas não o
conservava como referência temporal imutável para a garantia. Agora persiste uma projeção
mínima desse mesmo fato no F3, uma vez por obrigação, junto ao commit de liquidação,
auditoria e franquia. Guarda IDs, valor/moeda, instante verificado e contexto do gateway;
não cria segunda cobrança, ledger de consumo ou autoridade de liberação.

O primeiro fato pago do tenant fica identificado uma vez, inclusive após cancelamento ou
novo lifecycle. Usa o mesmo instante verificado da autoridade de liquidação/ciclo vigente.
Confirmação repetida não reinicia a janela. Histórico quitado sem fato correspondente exige
conferência: não há backfill silencioso nem janela nova inventada por uma reativação.
Falha antes do commit do grant também reverte fato e marcador do primeiro pagamento.

GET /billing/guarantee apresenta a janela de 7 x 24 horas desde o primeiro pagamento
verificado, com limite inclusivo, e pagamentos comprovados no intervalo considerado,
inclusive FINAL_USAGE pago. Valor exibido é o total pago considerado na revisão, não um
estorno concluído nem cálculo de nova obrigação. Fatos incompletos/duplicados/incompatíveis
não geram elegibilidade automática.

POST exige BILLING_MANAGE, step-up, CSRF, fingerprint, aceite estrito e chave vinculada ao
ator/unidade/revisão. Registra um único pedido por primeira contratação, com protocolo,
horário e snapshot dos pagamentos considerados. Captura recebimento antes de disputar o
lock, sem reduzir o prazo por espera interna. Pedido tempestivo continua REQUESTED após
o prazo e após restart; outra chave/worker reutiliza o mesmo pedido, sem segunda auditoria.

O aceite explicita encerramento imediato do acesso pago, aplicado pelo lifecycle existente.
Snapshot de encerramento, pedido, cancelamento e auditoria são atômicos. Preserva pagamentos,
invoice, franquia/consumo histórico e entregas; não envia DELETE ou refund. Pedido pendente
bloqueia nova obrigação/reativação e fechamento final até resolução financeira apropriada.
Confirmações posteriores continuam fatos financeiros, sem reabrir assinatura cancelada.

Prazo comercial encerrado não representa negativa genérica de direitos legais ou revisão
de cobrança indevida. O fluxo automático de garantia não substitui esses tratamentos, nem
julga aplicabilidade do CDC. Tampouco registra estorno iniciado, devolvido, processado ou
handoff fiscal de ajuste pelo simples recebimento do pedido.

## Web e validação requerida

Painel mostra primeira confirmação, prazo, pagamentos considerados, revisão explícita,
checkbox sobre encerramento imediato e protocolo recebido. Não pede dados de cartão,
banco ou mídia de terceiros. Retry conserva chave/corpo; step-up e CSRF são obrigatórios.
Protocolo longo pode quebrar linha no mobile. Atualizações de cobrança/conferência descartam
cotações antigas; chaves React distintas por painel/tenant são preservadas.

Executor local continua indisponível desde a PR #56. Nenhuma execução local nova é alegada.
A suíte completa no HEAD exato é o requisito de merge. A revisão da primeira árvore
identificou expansão indevida de texto ao inserir o regex do contrato; reconstruído a partir
do contrato preservado usando substituição literal, sem mudar validações de entrada. Novos testes API cobrem janela
inclusiva/excesso, replay, troca de ator, tenant, duas instâncias, restart, atomicidade,
primeiro pagamento imutável, reativação sem reset e ausência de prova histórica.
Teste PostgreSQL existente amplia o percurso para dois pedidos concorrentes e uma auditoria.
O CI inicial também expôs uma asserção antiga de retirada concorrente: o segundo worker
pode observar pendência antes do DELETE do primeiro terminar. A prova agora conserva as
chaves, exige um único DELETE, aceita apenas a pendência prevista e confirma no retry após
o primeiro terminar. Novo teste coordenado por eventos força essa janela; não relaxa a
regra de prova externa nem muda a implementação financeira.
Testes Web cobrem aceite/step-up, retry e distinção entre pedido e dinheiro devolvido.

E2E existente ampliado ao final do percurso: após mensalidade fictícia de 12,50 e excedente
final de 5,00 confirmados no SIMULATOR, registra garantia com dois pagamentos, mantendo
cancelamento, consumo 15 e as duas invoices sem observação fictícia de refund. Produz
screenshot mobile. Não representa prova bancária externa. Drift do contrato/types, lint,
build, segurança, dependências, containers e browser precisam passar no CI.

## Próximo delta e gates

F5/G5 permanece PARTIAL. Falta executar e reconciliar devoluções de forma governada por
invoice, considerar devoluções anteriores/pendentes e recebimentos posteriores elegíveis,
resolver alocação/ajustes e chargebacks, concluir a garantia somente com evidência adequada,
scheduler único, avisos/dunning com entrega confirmada e custos reais. Pedido não é
tratamento iniciado, refund enviado ou devolução confirmada. O SLA de iniciar tratamento
em até 2 dias úteis é a política aprovada, não uma alegação de atendimento já executado.

Não presumir dispensa de excedente não pago, restituição de mídia de terceiros ou prazo de
liquidação instantânea. Direitos legais, retenção/exportação e ajustes fiscais dependem dos
gates próprios. Catálogo comercial real continua desabilitado. Sem revisão independente de
segurança, credencial, gasto/movimento real, migration, deploy ou religamento Cloud SQL.

Rollback exige bloquear/drenar writers financeiros/IA e compatibilizar fatos/marcadores e
pedidos pendentes. Código antigo não pode ignorar um pedido de garantia e voltar a faturar
ou reativar. Não apagar pedido, prova, histórico, dedupe, auditoria ou journal para rollback.
