# WP-R02-16 — Encerramento financeiro da garantia
Data: 16/10/2026. CURRENT: main@71a59c35e587b7fc22bf4a5881fa627c72f7df30, PR #59 integrada.
F5/G5 permanece PARTIAL. Catálogo real desabilitado; Cloud SQL permanece desligado.

## Evidência preservada
PR #59 HEAD 56375834fb3d4943308fef72d9d1080cfb1c2f7d:
Backend 38831320902, Frontend 38831321022, F4 38831321119 verdes.
Pós-merge main@71a59c35e587b7fc22bf4a5881fa627c72f7df30:
Backend 38832165797, Frontend 38832165831, F4 38832165765 verdes.
439 testes de domínio, 443 de API (20 cenários PostgreSQL em job próprio), 118 Web,
build, contrato, navegador, segurança/dependências e container no conjunto da CI.

## Mudança
Pedido aceito congela manifesto de faturas/obrigações já existentes e lifecycles cobertos.
A primeira janela continua 7 × 24 horas; não há nova garantia/trial por reativação.
Pagamento tardio de obrigação já coberta pode ampliar a prova elegível e reabrir conciliação.
Uma nova contratação ou fechamento revisado posteriormente tem aceite próprio e não entra
automaticamente no pedido antigo. Excedente entregue ainda não pago continua devido,
conforme política aprovada; nenhum lançamento é apagado ou perdoado silenciosamente.

Finalizador privado exige prova de devolução integral no provedor por fatura,
valor bruto correspondente, ausência de divergência/chargeback e contratação encerrada.
O manifesto histórico só é derivado se o contrato cancelado e o pedido forem comprovados;
histórico ambíguo exige revisão. Transação F3 registra ajuste por obrigação, cobertura
imutável e auditoria uma vez. Não cria pagamento, franquia ou lançamento negativo fictício.
Excedente final pago e integralmente devolvido fica GUARANTEE_CLOSED, sem recobrança.
Uma nova contratação exige fatura integral e novo pagamento, preservando o primeiro pagamento.
Cobranças anteriores abertas ou dispatch incerto bloqueiam nova identidade. Retirada comprovada
também atende a contratação inicial não paga, sem confundir invoice cancelada com dinheiro devolvido.

Confirmação obsoleta não apaga prova integral encerrada. Divergência bruta ou chargeback
reabre conferência; informação ausente em leitura posterior não limpa chargeback conhecido.
FINAL_USAGE mantém o consumo original e a prova do ajuste.

## Fiscal e operação
FINANCIALLY_RESOLVED significa encerramento financeiro comprovado, não nota fiscal emitida.
fiscal_adjustment_state=PENDING_CAPABILITY é explícito na API/Web. A emissão/ajuste fiscal
permanece responsabilidade da integração fiscal e das decisões jurídicas apropriadas.
Worker de devolução sozinho continua sem finalizar. Script privado admite --execute --finalize;
default continua dry-run, sem HTTP de pagamento. Refund real permanece desligado por default,
sem job/provisionamento/credencial/migração/deploy nesta entrega.

## Validação
CI completa da PR no HEAD exato e pós-merge são obrigatórias antes de DONE_VERIFIED.
Sem execução local: servidor de comandos indisponível; validação executada em GitHub Actions.
Novos cenários: prova pendente/dry-run; excedente pago/devolvido; excedente devido;
manifesto e aceite de nova contratação; pagamento tardio; confirmações obsoletas;
divergência/chargeback persistente; concorrência/restart; rollback; isolamento;
legacy e emissão incerta. PostgreSQL exercita finalização concorrente em conexões independentes.
Web distingue encerramento financeiro e pendência fiscal, sem botão de recobrança.

## Próximo
Scheduler de cobrança único com aceite recorrente explícito; dunning e entrega honesta de
notificações; custos medidos; fiscal/homologação real. Depois avançar no restante do mestre,
preservando os gates externos. Simulador/CI não certificam pagamento real nem G5.
Não houve revisão de segurança independente nesta entrega.
