# WP-R02-11 — Conferência de recebimentos e consulta sem reemissão

CURRENT: main@17fb87cdb171b78b719edb2decc4d89970bcd9f8, PR #54 integrada.
PR #54 no HEAD 42e0ee93c2f3dba5af85e7f8547c598d1e305e3c: Backend 38820696205,
Frontend 38820696349, F4 38820696170 SUCCESS.
Pós-merge: Backend 38820946243, Frontend 38820946247, F4 38820946296 SUCCESS.

## Delta implementado

Recebimento V1 exige status de confirmação e valor bruto informado pelo provedor igual
à obrigação congelada antes de liquidar, conceder franquia ou gerar o handoff fiscal.
Valor ausente, booleano, não finito ou fora dos centavos fica desconhecido; zero fica
zero, nunca o valor esperado. netValue não reduz o valor contratado pelas tarifas do gateway.
Essa verificação é uma evidência do recurso de cobrança fornecido pelo provedor, não
uma certificação independente de liquidação bancária. A homologação externa continua aberta.

O store F3 registra observação mínima imutável por evento: IDs, origem, horário,
valor esperado/informado, status e decisão. Não armazena payload bruto, cartão, token
ou documento do cliente. Autenticação, isolamento, dedupe e a mesma transação financeira
antecedem qualquer efeito; falha reverte observação, liquidação e franquia conjuntamente.
Registros legados sem lifecycle V1 preservam seu comportamento anterior.

PAYMENT_UPDATED não prova pagamento. Divergências de valor/status e estornos/chargebacks
ficam em revisão; confirmação atrasada não apaga uma reversão conhecida. Quitação histórica
não é apagada, e conferência posterior nunca concede outro ciclo. Divergência/reversão da
fatura BASE que financia o período vigente suspende novas ações pagas/publicações/expansão.
Dados, saldo histórico, exportação, pausa e kill switch são preservados. Não promete parar
anúncios externos ou gastos já existentes. Pendências bloqueiam nova obrigação/reativação;
a fatura final em revisão não é apresentada como fechamento quitado.

POST /billing/charges/{gatewayChargeId}/reconcile exige organização proprietária, BILLING_MANAGE,
step-up, CSRF e chave vinculada ao ator/unidade/fatura. O corpo não aceita valor/status/flag
paid. A consulta GET ao gateway ocorre fora da transação e valida ID, externalReference e
ambiente da obrigação. O resultado usa a mesma autoridade de liquidação do webhook, sob
lock F3 do tenant. Replay concluído não repete consulta; falha incerta não emite outra fatura.
Snapshot iniciado antes de observação mais nova é descartado. Consulta atual contraditória
mantém revisão; consulta confirmada compatível resolve divergência de recebimento sem reset
de ciclo ou consumo. Estorno/contestação continua exigindo resolução própria, não é apagado
por consultar o valor original da fatura.

Web mostra valor contratado e valor informado, ausência explícita, fonte e revisão. OWNER/FINANCE
podem consultar com autenticação recente, sem enviar valor nem emitir cobrança. Retry conserva
a chave; resposta de consulta não vira mensagem de pagamento confirmado. Troca de tenant descarta
o componente/contexto. Revisão React: chaves distintas preservadas, efeito inicial descartável,
referência de exclusão de duplo envio e tipos contratuais sincronizados.

## Validação

Local: domínio 428; API 397 (19 PostgreSQL reservados ao CI); Web 112 testes,
lint, types, drift, boundaries e build verdes. Testes novos cobrem gross/net, ausência,
zero, precisão, autenticação, dedupe, alteração de termos, reversão, atraso, isolamento,
RBAC/step-up, consulta GET sem transação, replay, rollback e nenhuma franquia duplicada.
Um teste de UI inicialmente falhou por fixture sem CSRF; foi corrigido com CSRF explícito,
sem relaxar a proteção do cliente. O contrato novo mantém campos opcionais para leitura
compatível de respostas anteriores.

O teste PostgreSQL amplia o percurso existente com divergência persistida, duas consultas
concorrentes, acesso restaurado e consumo preservado sem outro OPEN. O E2E real de browser
usa callbacks SIMULATOR com valor explícito; nenhum dado de banco/credencial real. CI da PR,
PostgreSQL e browser ainda precisam passar no HEAD exato antes do merge.

Referências primárias consultadas em 15/10/2026:
- https://docs.asaas.com/reference/recuperar-uma-unica-cobranca
- https://docs.asaas.com/docs/guia-de-cobrancas
- https://docs.asaas.com/docs/webhook-para-cobrancas

## Próximo delta e limites

F5/G5 permanece PARTIAL. Ainda faltam cancelamento/conciliação de fatura aberta com base e
excedente, resolução de refunds/chargebacks e garantia, ajustes após fechamento, scheduler
único e entrega confirmada de avisos/dunning, custos reais e homologação externa/fiscal/jurídica.
Catálogo real desabilitado. Esta entrega não executa refund, cobrança, deploy, migration real,
credencial real ou religamento Cloud SQL. Nenhuma revisão independente de segurança foi realizada.

Rollback antigo requer bloquear e drenar writers financeiros/IA e compatibilizar os novos
metadados comerciais/status_source RECONCILIATION antes de restaurar código anterior. Não
apagar observações, obrigações, dedupe, fatos quitados ou journal para destravar um rollback.
