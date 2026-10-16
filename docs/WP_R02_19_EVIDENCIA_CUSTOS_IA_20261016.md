# WP-R02-19 — Evidência persistente de custos de IA
Data: 16/10/2026. CURRENT main@066ca1bc121d1984337cf4d0194a8a150c22a22e.
F5/G5 permanece PARTIAL. Catálogo real desabilitado; Cloud SQL desligado.

## Evidência anterior
PR #62 HEAD 8a7bc9fda7a00a41969465a9292152fc1de976af:
Backend 38837138052, Frontend 38837138047, F4 38837138083 verdes.
Pós-merge main@066ca1bc121d1984337cf4d0194a8a150c22a22e:
Backend 38837412523, Frontend 38837412603, F4 38837412568 verdes.
439 domínio, 481 API (22 cenários PostgreSQL no job próprio), contrato, navegador e containers.
Migração 006 validada só em serviço efêmero de CI, não aplicada a ambiente real.

## Lacuna comprovada
CostLedger de provider era apenas memória; reinícios/worker paralelo não compartilhavam gasto.
Timeout e erro de parsing podiam terminar com subtotal zero sem indicar custo desconhecido.
Gemini interpretava uso só depois do parsing da saída, perdendo evidência de tokens quando
a saída era inválida. Campos de tokens aceitavam bool/float. O fluxo legado de regeneração
chamava IA dentro da transação, impedindo commit de evidência antes do efeito externo.

## Mudança
CostObservation guarda somente base, unidades de orçamento, tokens reportados, moeda da
estimativa e referência de tarifa/modelo. Sem prompt, saída, corpo HTTP, erro bruto ou segredo.
SIMULATED, UNVERIFIED_ESTIMATE, UNKNOWN e NOT_DISPATCHED são estados distintos.
Provenance.cost_complete descreve completude das unidades observadas; não comprova tarifa
vigente ou margem. Histórico sem o campo é incompleto por default.

PersistentAICostLedger é o ledger e journal da mesma autoridade interna de orçamento;
não é o ledger de créditos comerciais do cliente. START e reserva são confirmados em F3
antes de chamar provider, fora de transação do caller. OUTCOME preserva custo conhecido
mesmo em saída inválida ou rejeição posterior. Não há dupla cobrança pelo observer + ledger.
Cap configurado, gasto e orçamento comprometido são compartilhados por workers/reinícios.
Namespace separa ambiente e modo da configuração primária (SIMULATED/PROVIDER).
Não existe limite monetário novo inventado: caps continuam configuráveis pelo runtime confiável,
sem default comercial, sem reset mensal inferido nem edição pública neste WP.

Uma tentativa desconhecida/crash mantém orçamento reservado; não há expiração/reset automático.
O orçamento restante da requisição impede outro fallback após incerteza ter comprometido o teto.
A falha continua TIMEOUT/PROVIDER_ERROR, preservando também a reserva comercial quando há
incerteza de execução. Uma saída conhecida inválida libera créditos do cliente e mantém
as unidades internas do provider. Custos acima do teto observado continuam registrados.
O caso normal de fallback conhecido usa somente o orçamento restante.

Regeneração legada agora tem claim antes da IA, execução fora do lock, contexto por ator/unidade/
campanha, recuperação somente do resultado persistido e entrega condicionada ao briefing/versão
ainda atuais. Preserva a chave HTTP anterior e autorização do recurso antes de replay.
Nonce incerto não executa provider novamente, inclusive após restart.
Writers antigos precisam ser drenados antes de ativar esse formato; não misturar versões
que executam IA sem claim ou apagam metadados ai_cost_v1.

## Gemini e preços
Uso é interpretado antes de validar texto/JSON, inclusive nas falhas conhecidas de saída.
Tokens precisam ser inteiros exatos não negativos; bool, float, valor negativo ou contagem
ausente não viram zero. Missing usage/timeout permanecem UNKNOWN. Recusa comprovada de
contrato antes da rede é NOT_DISPATCHED. Corpo HTTP do provider não é copiado para erros.
Modelo e valores legados de tarifa NÃO foram alterados nem certificados como atuais.
Cálculo legado é UNVERIFIED_ESTIMATE e carrega referência explícita.
Nenhuma chave, chamada real ou pesquisa de preço foi usada para fabricar custo efetivo.

## Relatório e limites
report_ai_costs é privado/somente leitura: unidades conhecidas, comprometidas, bases e
completude por tenant/namespace. Não é uma tela de margem para clientes.
ai_20_percent_validated=False e direct_30_percent_validated=False permanecem explícitos.
Uso real, fatura do fornecedor, tarifa vigente/modelo, câmbio e demais custos diretos são
necessários para validar as metas de 20%/30%. Um simulador ou estimativa não atende esse gate.
Custo desconhecido exige conciliação operacional com evidência; não liberar orçamento só
porque uma consulta está vazia. Não há reconciliador que invente uma correção neste WP.

## Migração
007_ai_cost_evidence adiciona journal imutável e caps com guards de tenant.
Aplicação real/migração/deploy exige autorização específica. PostgreSQL não cria tabelas
implicitamente; preparar 006/007 antes de qualquer promoção autorizada. Arquivos down são
mecânica de rollback, não autorização para apagar evidência real.
Nenhuma migration real, credencial, gasto, job, deploy ou infraestrutura foi acionada.

## Validação
CI da PR no HEAD exato e pós-merge obrigatórias antes de DONE_VERIFIED.
Servidor de comandos local indisponível; testes em GitHub Actions.
Domínio: metadados exatos, custo inválido, completude, custo conhecido em falha, fallback
e erro minimizado. Gemini: MockTransport, JSON inválido com uso preservado, uso desconhecido/
inexato, erro HTTP minimizado e prova de contrato recusado antes da rede.
API: reserva visível antes do provider; cap concorrente; timeout/crash/restart; rollback
antes/depois da chamada; bloqueio de chamada sob transação; custo em schema inválido;
replay de observação; isolamento de tenant/namespace; codec e fluxo legado; separação de
créditos comerciais. PostgreSQL: duas conexões/workers, limites compartilhados, hold após
restart, idempotência, imutabilidade e reversibilidade da migração em banco temporário.
Sem revisão de segurança independente.

## Próximo
Validar CI/corrigir qualquer vermelho, integrar e verificar pós-merge. Depois continuar os
deltas autorizados do mestre; custos reais/fiscal/homologação permanecem gates externos
e não justificam reconstruir as superfícies já concluídas.
