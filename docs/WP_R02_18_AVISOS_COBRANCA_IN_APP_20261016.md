# WP-R02-18 — Avisos de cobrança no aplicativo
Data: 16/10/2026. CURRENT main@3a4aad42fb894571bf13afaa3d168c6c37701deb.
F5/G5 permanece PARTIAL. Catálogo real desabilitado; Cloud SQL desligado.

## Evidência anterior
PR #61 HEAD a7e0081412f3f70056bef85cc8fb428f62a5fe8a:
Backend 38836110875, Frontend 38836110889, F4 38836110884 verdes.
Pós-merge main@3a4aad42fb894571bf13afaa3d168c6c37701deb:
Backend 38836296273, Frontend 38836296309, F4 38836296280 verdes.
439 domínio, 467 API (21 PostgreSQL no job próprio), contrato, navegador e containers.
O erro inicial de limpeza do teste PostgreSQL foi corrigido e não ficou no HEAD integrado.

## Lacuna
O domínio já calculava dunning, mas não havia inbox persistente nem confirmação individual
de leitura. Outbox/Inbox de eventos do domínio não representa um Notification Center
e continua preservado. O contador de lembretes externos não é incrementado por enfileiramento
ou disponibilização local.

## Comportamento
Worker privado process_billing_notices tem dry-run padrão e nunca chama gateway, e-mail,
SMS, cobrança ou settlement. Usa vencimento e política congelados da fatura V1;
D0/D2/D3/D7 são dados da política, não datas fictícias de envio.
Somente renovação paga anterior ou FINAL_USAGE devido são fontes; não cobra trial
ou converte primeira compra pendente. Fatura paga, retirada comprovada, cancelamento
de renovação ou pendência de conciliação suprimem novos avisos aplicáveis.
O texto informa pagamento ainda não confirmado no aplicativo, orientando a consulta segura
do histórico quando o cliente já pagou. Não cria ou confirma dívida adicional.

Cada invoice/marco tem uma identidade determinística por tenant. F3 grava aviso,
auditoria e fence de disponibilidade atomicamente. Nova checagem antes de commit
evita publicar aviso de uma fatura confirmada no intervalo. Falha não consome o marco.
Execução tardia disponibiliza somente o último marco vencido: não retrodata entrega nem
marca marcos perdidos como enviados. Histórico permanece após quitação/retirada/conferência.

GET /billing/notices exige BILLING_VIEW e pagina 50 itens com cursor isolado por tenant.
POST /billing/notices/{noticeId}/read exige autenticação, CSRF e nonce; usuário/tenant
derivam da sessão. Leitura de uma pessoa não marca como lido por outra.
Serialização lista apenas campos permitidos; nenhum documento do titular, dado bruto
do banco, token, credencial ou link externo no aviso.

## Persistência e migração
006_billing_notices cria billing_notices e billing_notice_reads, índices por tenant,
guards contra rehome e triggers de imutabilidade. SQLite mantém compatibilidade para teste.
A migração foi escrita para fonte/CI. NÃO foi aplicada em ambiente real. Antes de deploy
deste código, a aplicação real da 006 exige autorização específica e plano de rollback;
startup PostgreSQL não cria tabelas implicitamente. Rollback de schema com dados exige
decisão operacional; arquivos down não significam autorização para apagar histórico real.

## Configuração de exemplo
Removida chave dunning_policy duplicada e alinhado D7 ao exemplo de política aprovada.
Preços/entitlements fictícios e catálogo comercial real continuam inalterados/desabilitados.

## Validação
CI da PR no HEAD exato e pós-merge são obrigatórias antes de DONE_VERIFIED.
Sem execução local: servidor de comandos indisponível; testes executados em Actions.
API: dry-run sem provider; marcos/replay; atraso sem envio retroativo; concorrência/restart;
leitura individual; RBAC/cross-tenant/tamper/nonce; pagamento/void/conciliação; FINAL_USAGE;
rollback; pagamento entre seleção e commit; paginação/serialização minimizada.
PostgreSQL: concorrência real de conexões, persistência da leitura, isolamento, guards
e reversibilidade up/down/up da migração em serviço efêmero de CI.
Web: disponibilidade vs leitura/envio/pagamento, retry com a mesma chave/CSRF, páginas e
estados de pagamento já confirmado ou conferência. Fluxos de navegador existentes preservados.

## Limites e próximo
Entrega IN_APP não certifica e-mail/SMS ou outro canal. Nenhuma mensagem externa foi enviada,
nenhum job foi provisionado/ativado, nenhuma migration real, credencial, deploy ou pagamento.
Notification Center geral de outros domínios continua no delta F14.
Próximos: custos medidos e fiscal/homologação; avançar nos demais deltas autorizados do mestre
quando os gates externos forem o único bloqueio. Sem revisão de segurança independente.
