# WP-R02-10 — Consumo final sem nova mensalidade

CURRENT: main@bcfeeee30edd682de8eb190e924c55f953fe36d8, PR #53 integrada.
PR #53 no HEAD f5624fce16383fe84ca11435c5d8daaf8d3645f4: Backend 38817547261,
Frontend 38817547252, F4 38817547417 SUCCESS.
Pós-merge: Backend 38817801066, Frontend 38817801088, F4 38817800973 SUCCESS.

## Delta

O encerramento efetivo preserva o snapshot do lifecycle pago no store F3 antes que uma
reativação possa substituir a identidade. GET/POST /billing/closure mostram e confirmam
apenas excedente autorizado, entregue e ainda não fechado na renovação seguinte. Não
incluem nova mensalidade e nunca concedem franquia ou reativam assinatura pelo pagamento final.

FINAL_USAGE tem identidade distinta de BASE, mantendo o hash histórico das mensalidades.
Usa a mesma obrigação imutável, fence de dispatch, resultado durável, histórico e webhook.
Idempotência HTTP distingue fechamento da emissão comum; duas chaves/workers reutilizam
a mesma fatura final. Fingerprint vincula condições financeiras e ambiente, sem invalidar
uma revisão só porque o primeiro worker já registrou a invoice.

Reservas incertas bloqueiam fechamento. Outra obrigação de renovação já congelada bloqueia
separar esse consumo em uma segunda fatura até conciliar/cancelar a anterior. Nova contratação
aguarda resolução do fechamento anterior: zero, residual absorvido ou invoice efetivamente quitada.
Pagamento da fatura final mantém a assinatura cancelada e a franquia anterior sem reset.

Residual abaixo do mínimo validado é absorvido pela FM no encerramento, com registro próprio;
não vira pagamento externo, invoice fictícia ou alteração no consumo entregue do ledger.
Para Asaas, ASAAS_MINIMUM_CHARGE_AMOUNT exige configuração explícita, positiva e em centavos;
ausência bloqueia decidir um fechamento positivo. O valor deve ser homologado por conta/método,
não presumido a partir do exemplo de R$ 5,00. O simulator usa capacidade fictícia de R$ 0,01;
testes de residual configuram R$ 5,00 explicitamente, sem configurar oferta real.

Uma invoice final já congelada não pode ser absorvida silenciosamente se o mínimo mudar:
ela continua sob a fence de emissão/recuperação. Sem expiração automática, limpeza de
idempotência ou nova chave usada como permissão para um segundo POST.

IA em execução verifica contratação/ciclo novamente na transação da entrega. Encerramento
antes da entrega descarta a saída e libera a reserva sem consumo. Resultado externo incerto
continua reservado para reconciliação; não há reexecução automática pelo fechamento.

## Web e testes

Painel de fechamento exige revisão, checkbox, step-up e CSRF. Mostra residual absorvido,
invoice pendente, consumo incerto e conciliação de outra obrigação com estados distintos.
Histórico rotula FINAL_USAGE como excedente final. Todos os painéis mantêm chaves React distintas.

Local: domínio 426, API 384 testes (19 PostgreSQL reservados ao CI), Web 110 testes e
lint/types/drift/boundaries/build verdes. Novos testes cobrem final somente de excedente,
pagamento sem franquia, residual sem pagamento inventado, pendências/overlap, dois workers,
mudança do mínimo após dispatch incerto, isolamento e cancelamento durante geração.

O teste PostgreSQL existente amplia a prova para consumo + fechamento entre workers +
pagamento final sem outro OPEN no ledger. Simulator corrigido para IDs derivados de
tenant/idempotência, evitando colisão de contadores locais ao reiniciar outro worker.
Seu contrato preserva chaves diferentes com cobranças distintas e replay estável.

O E2E de checkout foi ampliado: callback autenticado SIMULATOR concede o primeiro ciclo,
API real entrega três estratégias com consentimento de excedente, UI encerra e confirma
fatura final; callback final deve preservar cancelamento e o mesmo saldo/ciclo. Não há
endpoint de bypass nem credencial real. Esse percurso ampliado ainda depende do CI Chromium;
não representa liquidação bancária externa ou G5 real. Artefatos ficam no workflow.

## Próximo delta obrigatório antes de ativar V1

- Reconciliar o valor efetivamente recebido no webhook com a obrigação congelada antes de
  considerar a dívida quitada/liberar recursos; hoje os testes usam recebimentos simulados.
- Cancelamento/conciliação de fatura aberta com mensalidade + excedente, sem dupla cobrança.
- Ajustes após fechamento, refunds/chargebacks, garantia da primeira contratação e custos reais.
- Scheduler único, avisos/dunning com dedupe e confirmação real de entrega das comunicações.
- Homologação externa de vencimento, mínimo, meios, juros/multa e pagamento; fiscal/LGPD e
  produção mantêm gates próprios. Catálogo comercial real continua desabilitado.

Nenhuma migration nova. **Rollback:** FINAL_USAGE é novo valor de enum persistido; reader
antigo não conhece essa finalidade. Não liberar rollback antigo sobre esses registros sem
compatibilidade e bloqueio/drenagem dos writers financeiros/IA. Preservar snapshots, fatos,
idempotência e journal. Sem deploy, credencial real, cobrança externa, migration real ou
religamento Cloud SQL nesta etapa.
