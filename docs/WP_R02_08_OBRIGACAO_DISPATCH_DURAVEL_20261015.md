# WP-R02-08 — Obrigação financeira antes do efeito externo

CURRENT: main@7eb05a41170f18c97a602cad090568efe66ec94e, PR #51 integrada.
PR #51 no HEAD 95937d6bdb0701d1169c4aafaff144d483f4e491: Backend 38813559244,
Frontend 38813559223, F4 38813559243 SUCCESS.
Pós-merge: Backend 38813807916, Frontend 38813808070, F4 38813808142 SUCCESS.

## Delta

O contrato V1 usa o store F3 existente para persistir uma obrigação imutável identificada
por tenant/lifecycle/ciclo, com valor, linhas, documento e snapshot comercial. Isso acontece
antes de qualquer emissão externa. Chaves HTTP diferentes recuperam a mesma obrigação,
sem recalcular silenciosamente seus termos. Contexto/corpo diferente na mesma chave é 409.

Um claim de dispatch separado é commitado antes do gateway. Somente a primeira execução
pode criar a cobrança. Retry, outro worker ou restart consultam resultado durável ou fazem
GET por externalReference. Ausência, ambiguidade ou resposta inválida permanecem pendentes;
não autorizam outro POST. Não existe expiração/reset automático da fence financeira.

O adaptador Asaas expõe entrada específica para obrigação já protegida: HTTP fica fora da
transação de idempotência do adaptador. O fluxo legado permanece na entrada antiga. Recuperação
V1 valida referência externa, unicidade e valor observado antes da persistência do histórico.
Resultado do provedor é salvo antes da finalização da resposta/histórico, recuperável após falha.
Callback antecipado continua 503 sem dedupe até o histórico conhecido, conforme WP-R02-05.

Desistência de troca passa a consultar também a obrigação congelada, mesmo quando o gateway
ainda não tem registro local. Cancelamento entre freeze e dispatch bloqueia nova emissão.
Cancelamento após dispatch ainda exige conciliação/cancelamento da fatura externa no próximo bloco.

Carência V1 e datas de dunning são ancoradas no fim do último ciclo pago, não na chegada do
webhook OVERDUE. Aviso tardio não concede mais três dias nem permite antecipar vencimento.
Leitura defensiva limita também carência persistida anteriormente além da data contratada.

## Evidência

- Freeze e claim visíveis a outro worker antes de HTTP, sem transação aberta no callback.
- Timeout após efeito externo: mesmo invoice/valor após restart e mudança de termos locais.
- Resultado externo ausente: novas chaves não redisparam emissão.
- Falha na finalização reverte histórico/HTTP juntos, preserva resultado do provedor.
- Dois workers concorrentes: uma emissão; segundo pendente e depois recuperável.
- Cancelamento após freeze e antes de dispatch não chama provedor.
- Asaas com MockTransport: timeout após POST, retry somente GET, uma emissão e nenhuma
  transação DB envolvendo HTTP. Não representa homologação financeira real.
- Consulta rejeita referência divergente, vários resultados, hasMore e listagem malformada.
- PostgreSQL amplia teste entre workers para provar freeze commitado antes do gateway.
- Domínio valida aviso atrasado e carência antiga excessiva sem prolongar acesso.

Local: domínio 422 testes; API completa 367 testes, 19 PostgreSQL reservados ao CI.
Resultados finais e CI no HEAD exato ficam na PR. Web sem mudança funcional neste bloco;
CI completo continua obrigatório. Uma execução local encontrou proxy SOCKS do ambiente
sem socksio; repetir sem variáveis de proxy, como nos demais testes locais, removeu a causa.
Não alteramos dependências de produção para acomodar esse proxy de teste.

Fonte primária consultada em 15/10/2026: https://docs.asaas.com/reference/listar-cobrancas
documenta GET /payments com filtro externalReference para recuperação/conciliação pontual.
Essa consulta não oferece transação distribuída nem prova de que uma emissão não ocorreu;
por isso resposta vazia após dispatch incerto não permite criação automática.

## Pendências e operação

F5/G5 continuam PARTIAL. Checkout com revisão da obrigação, vencimento no aniversário,
scheduler único, fechamento de excedente final, notificações/dunning deduplicadas, ajustes,
refunds/chargebacks/mínimo gateway, custos e homologação externa permanecem deltas próprios.
Operações com resultado permanentemente ausente exigem procedimento de conciliação com
evidência externa; não excluir registros de idempotência nem pedir nova chave para reenviar.

Não há migration nova: usa registros F3 existentes, sem namespace financeiro paralelo.
Rollback para versão que ignore fences exige bloquear writers/dispatch V1 e drenar operações;
preservar snapshots e resultados. Não autoriza rollback vivo com emissão habilitada.
Sem credenciais/cobranças reais, deploy, migration externa ou religamento Cloud SQL.
