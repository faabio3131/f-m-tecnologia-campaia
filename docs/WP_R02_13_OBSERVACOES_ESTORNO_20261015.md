# WP-R02-13 — Evidência mínima de estornos concluídos

CURRENT: main@9fcd24172e38c0e45b28b80169877f41aefbc052, PR #56 integrada.
PR #56 no HEAD ce43f41d5a2d21d679a6ea32a0f149547f4d01e9: Backend 38825508994,
Frontend 38825509004, F4 38825509005 SUCCESS.
Pós-merge: Backend 38825731961, Frontend 38825731957, F4 38825731992 SUCCESS.

## Delta

A conferência de recebimentos detectava reversão, mas não distinguia pedido de estorno
de devolução concluída nem conservava seu valor. O adaptador de consulta Asaas e o parser
do webhook agora extraem somente pares status/valor do array refunds. Preservam multiplicidade
e enums desconhecidos, sem payload bruto, descrição do pagador, cartão, token ou dados bancários.
Formato ausente/malformado, valor sem centavos válidos, zero e negativos nunca viram devolução
confirmada. Array excessivo exige conferência; nenhum item é silenciosamente descartado
para produzir um total favorável.

A mesma autoridade de webhook/GET soma todos os itens DONE e exclui PENDING/CANCELLED do
total concluído. Marca processamento, parcial/integral, ausência de confirmação e conflitos.
Confere valor bruto original, limite total e soma comprometida antes de reconhecer um total.
Não substitui o valor da invoice pelo valor estornado, não fabrica recebimento anterior e
não transforma um pedido/negativa em dinheiro devolvido. Enum desconhecido fica inválido
para confirmação, preservado na observação mínima, sem ser traduzido em status conhecido.

Uma confirmação de recebimento que contenha refunds também exige revisão: o campo status
RECEIVED isolado não mantém recursos pagos liberados diante de uma devolução parcial.
Eventos de reversão com status PENDING passam pela conferência mesmo após quitação;
não são confundidos com um aviso de vencimento atrasado. Observação posterior mais fraca
não apaga valor de devolução já confirmado; conserva o valor anterior e sinaliza conflito.
Consulta iniciada antes de observação nova continua sujeita à proteção temporal existente.

Observações mínimas ficam no receipt F3 imutável, junto à mesma transação de charge/audit/dedupe.
Agregados atuais de estorno ficam no envelope comercial opcional da invoice. Replay não
soma novamente o mesmo valor. Falha reverte agregado, bloqueio, auditoria e dedupe juntos.

Histórico mostra valor concluído conhecido, estágio e horário separados do valor contratado.
Zero validado e ausência são distintos. Devolução integral informada pelo provedor não
remove a revisão de ajuste contratual, não reativa assinatura nem concede franquia.
O bloqueio de financiamento do período, exportação/pausa preservadas e consumo histórico
continuam com as regras anteriores. Esta entrega observa devoluções; não envia solicitação
de refund e não decide alocação, garantia, abatimento fiscal ou encerramento de disputa.

## Validação requerida

O executor local perdeu conexão após o fechamento da PR #56. Alterações foram preparadas
pelo conector do repositório; nenhuma execução local nova é alegada. A suíte completa do CI
no HEAD exato é obrigatória antes do merge, incluindo domínio/API, PostgreSQL, contratos,
Web, browser, containers, auditorias de dependências e SAST. Types opcionais foram
sincronizados com o contrato; o check de drift deve comprovar essa sincronização no CI.

Novos testes de domínio verificam parser/consulta mínima, multiplicidade, desconhecidos e
valores inválidos. API verifica processamento/parcial/integral, soma de múltiplos DONE,
não regressão, isolamento, privacidade, restart, autenticação/dedupe, GET idempotente fora
da transação e rollback. Teste PostgreSQL existente amplia a prova com observação de refund
visível em outra conexão e revisão de fechamento. Web distingue processamento e total
concluído, sem mensagem de pagamento confirmado/franquia nova.

Referências primárias consultadas em 15/10/2026:
- https://docs.asaas.com/docs/estornos
- https://docs.asaas.com/docs/webhook-para-cobrancas
- https://docs.asaas.com/reference/recuperar-uma-unica-cobranca

## Próximo delta e gates

F5/G5 permanece PARTIAL: faltam resolução/alocação dos ajustes e chargebacks, garantia da
primeira contratação, execução governada de refund, scheduler único, avisos/dunning com
entrega confirmada e custos reais. Estorno observado não certifica liquidação bancária
independente, conta/método habilitado ou validação fiscal/jurídica. Catálogo comercial real
continua desabilitado e homologação/produção mantêm seus gates. Não houve revisão
independente de segurança, deploy, migration, credencial, gasto ou movimentação real.

Rollback antigo exige bloquear/drenar writers financeiros/IA e compatibilizar metadados
novos de ChargeResult/SubscriptionCharge e receipts. Não apagar prova, dedupe, auditoria
ou journal para permitir rollback ou destravar uma revisão.
