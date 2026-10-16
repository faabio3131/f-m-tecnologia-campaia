# WP-R02-15 — Worker privado de devolução governada da garantia

CURRENT: main@f989b6a6c3413a21faaf1f41cfd19bd6b0757234, PR #58 integrada.
PR #58 no HEAD 372449a9cee597b792b76fe9d7b2204ebf0204df: Backend 38828254098,
Frontend 38828254052, F4 38828254028 SUCCESS.
Pós-merge: Backend 38828538982, Frontend 38828538994, F4 38828539031 SUCCESS.
Evidência anterior: domínio 432, API 427 (20 PostgreSQL no job dedicado), Web 117.

## Delta e autoridade

O pedido aceito ainda não tinha processamento de devolução. Novo worker privado valida
tenant, protocolo/fingerprint do pedido original, marcador do primeiro pagamento,
tempestividade e fatos liquidados únicos da mesma obrigação. Inclui recebimentos
elegíveis posteriores ao pedido no intervalo de garantia; pagamentos fora da janela
ficam identificados para revisão, não são descartados como se não existissem.

Não existe endpoint público novo para movimentar dinheiro. A autoridade é o pedido
original aceito com RBAC/step-up/CSRF e encerramento pago. O runtime privado precisa do
contrato encerrado e do gateway/ambiente original; não recebe valor a devolver do cliente.
A projeção financeira usa os mesmos fatos F3 e a mesma autoridade de observação/liquidação
do webhook/GET existente, sem novo ledger de cobrança ou franquia.

## Uma tentativa, recuperação somente por consulta

Snapshot/fence por pedido + invoice é commitado antes do efeito externo, com valor derivado
no servidor. O dono envia uma tentativa; outro worker, restart, timeout ou novo job apenas
consulta a invoice conhecida. Ausência de devolução não permite repetir POST ou expirar/resetar
a fence. Falha de commit antes do efeito não envia; falha local após efeito conserva a fence
e recupera por GET. Não há promessa de disponibilidade automática diante de ambiguidade.

Cada tentativa consulta primeiro ID/externalReference/valor bruto/ambiente e devoluções já
existentes. Soma somente DONE, espera PENDING e exclui CANCELLED do total concluído.
Deriva apenas o saldo restante. Divergência, precisão inválida, estado desconhecido ou
disputa/chargeback exigem revisão. Dados de chargeback são reduzidos ao status; não há
payload bruto, motivo do pagador ou dados bancários nos registros novos.

O adaptador Asaas suporta este caminho automático somente para PIX/CREDIT_CARD com
confirmação/recebimento transacional conhecido. Recebimento manual em dinheiro, negativação,
boleto, meio desconhecido e disputa não viram um refund Pix/cartão por suposição. O caminho
de boleto requer processo próprio do provedor e continua pendente. Antes do POST, o
adaptador consulta novamente e confere método/saldo; após resposta, faz readback.

ASAAS_REFUND_DISPATCH_ENABLED tem padrão false e somente true explícito habilita o método.
O CLI privado exige --execute além da configuração; padrão é dry-run sem consulta de
pagamento ou mutação. Usa o runtime persistente existente; não provisiona/scheduleia infra.
Execução CLI não usa ambiente de autenticação de fixture. Resultado incerto/revisão retorna
falha operacional; código de saída zero para pending não equivale a dinheiro devolvido.

SIMGW usa registros fictícios persistidos de pedido e conclusão separados. Criar um pedido
não o conclui. Controle complete_refund só existe no simulador, sem rota de bypass.
IDs/fences/observações sobrevivem a outro worker. Nenhuma chave, DSN, documento ou conta
real é embutida no script, no relatório ou nos testes.

## Progresso honesto

Pedido imutável continua distinto do início do tratamento. Consulta da garantia deriva
PROCESSING, horário e andamento por invoice. Distingue pendência no provedor, envio incerto,
necessidade de conferência e devolução integral informada com ajuste contratual pendente.
Não concede créditos, não apaga consumo/fato pago, não reativa e não conclui a garantia
só porque uma ou todas as devoluções foram observadas. Pendência conserva os bloqueios
comerciais anteriores; não reemite excedente já envolvido em revisão.

O builder fiscal existente aceita apenas fatos positivos liquidados. Não foi usado um
fato negativo para simular nota de estorno. FM Fiscal continua autoridade de capacidade,
vínculo, readiness, jurisdição e emissão; construção de handoff não é documento emitido.
Ajuste/alocação comercial e handoff fiscal de devolução seguem delta próprio.

## Validação requerida

Executor local permanece indisponível. Nenhuma execução local nova é alegada. CI completa
no HEAD exato é requisito de merge: domínio/API, PostgreSQL, contratos/drift, Web/browser,
containers, dependências, SAST e secret scan. Core usa MockTransport; API usa somente
SIMGW e fixtures explícitas. Testes novos cobrem default desligado/dry-run, método/saldo,
parcial/PENDING/DONE, disputa, valores divergentes, origem inválida, dois workers, replay,
restart e falhas antes/depois do efeito. Nenhum teste movimenta dinheiro real.

Teste PostgreSQL amplia o percurso anterior com fence visível em outra conexão antes do
efeito, duas invoices fictícias pendentes e confirmação posterior por outro worker sem
segundo POST. Ambientes de teste financeiro zeram ASAAS_API_KEY e GEMINI_API_KEY para não
herdar credenciais. Web distingue progresso e dinheiro concluído sem declarar ajuste final.

Referências primárias consultadas:
- https://docs.asaas.com/reference/estornar-cobranca
- https://docs.asaas.com/docs/estornos
- https://docs.asaas.com/docs/chargeback
- https://docs.asaas.com/reference/estornar-boleto

## Restante e gates

F5/G5 permanece PARTIAL. Falta concluir/alocar a garantia sem rebilhetar valores pagos
devolvidos, tratar excedente ainda não pago conforme política aprovada, ajuste fiscal,
boleto/disputas e resolução operacional de envio incerto. Scheduler único, comunicações
com entrega confirmada e custos reais também continuam pendentes. Nenhuma promessa de
mínimo/método/saldo/fee real homologado decorre de MockTransport ou SIMGW.

Sem enable de refund real, credencial, operação financeira externa, deploy, migration,
novo recurso de infraestrutura ou religamento Cloud SQL. Catálogo real segue desabilitado.
Validação de custos, jurídico, fiscal, homologação e produção mantêm gates próprios.
Não houve revisão independente de segurança. Rollback exige bloqueio/drenagem de writers
e compatibilidade com novos metadados de ChargeResult/eventos e registros F3; preservar
pedido, intent, observações, fatos, dedupe, auditoria e journal.
