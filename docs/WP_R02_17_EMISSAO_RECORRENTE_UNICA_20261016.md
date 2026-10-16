# WP-R02-17 — Emissão recorrente única
Data: 16/10/2026. CURRENT main@91b98c0b6e156bd6b9b1a5c6918cabf2ef1b5c79.
F5/G5 segue PARTIAL. Catálogo real desabilitado. Nenhuma infraestrutura foi ligada.

## Evidência preservada
PR #60 HEAD bb59d27221ae1776d92e190eed664ec06ed36b09:
Backend 38834859159, Frontend 38834859139, F4 38834859167 verdes.
Pós-merge main@91b98c0b6e156bd6b9b1a5c6918cabf2ef1b5c79:
Backend 38835068627, Frontend 38835068534, F4 38835068602 verdes.
439 domínio, 454 API (20 PostgreSQL em job separado), 120 Web, contrato, navegador e containers.

## Lacuna e solução
O aniversário e a obrigação única já existiam, mas faltava um invocador privado recorrente
com autorização explícita do titular da organização. Não foi criado scheduler nativo Asaas.
O mesmo execute_invoice atende checkout manual e worker, usando o mesmo billing_id e fence.
Não foi duplicada a autoridade de ciclo, débito, consumo ou pagamento.

GET/PUT /billing/renewal permite OWNER/FINANCE com autenticação recente, CSRF e nonce
revisar/autorizar/desativar a emissão. Consentimento é vinculado a lifecycle,
fingerprint das condições do plano alvo e gateway/ambiente. Mudança exige nova revisão.
Autorização não é mandato de débito automático nem autorização para exceder o teto de créditos.
Trial/primeiro pagamento são sempre checkout explícito; consentimento recorrente exige contrato
pago vigente. Nova contratação não herda o consentimento da anterior.

A fatura no aniversário mantém mensalidade antecipada + excedente autorizado entregue do
período anterior, itens separados, sem nova franquia até pagamento confirmado.
Reservas incertas impedem fechamento. Cancelamento e revogação são rechecados dentro da
transação de freeze e novamente antes do primeiro claim de dispatch.
Após claim durável, retries e outros workers apenas consultam a referência externa.
Desativar não finge cancelamento de invoice já emitida ou envio em andamento.

## Operação e limites
process_renewal_invoice é privado e recebe tenant explícito do runtime confiável.
Default dry-run não faz HTTP de pagamento ou mutação de negócio.
Execução nova exige dispatch_enabled=True; CLI exige --execute e
CAMPAIA_RENEWAL_DISPATCH_ENABLED=true no runtime persistente staging/production.
Fence já existente pode ser recuperado somente por GET com novo dispatch desligado,
inclusive após revogação. Falta de resultado não é autorização para repetir POST.
Auditoria do worker usa SYSTEM, preservando o usuário que concedeu consentimento.

Nenhum job/cron/provisionamento foi ativado. Não houve credencial, deploy, migration real,
pagamento ou custo real. Cloud SQL permanece desligado. Chamadas em testes usam somente
simulador persistente/fakes; G5 externo não foi certificado.

## Persistência e rollout
Campo opcional commercial_v1 renewal_invoice_consent mantém leitura do histórico.
Não há migration de schema. Código antigo que regravar Subscription pode perder metadados
novos: drenar workers antigos e bloquear rollback de writer sem compatibilidade antes da ativação.
Sem consentimento inferido do histórico.

## Validação
CI completa no HEAD exato e pós-merge são exigidos antes de DONE_VERIFIED.
Servidor de comandos local indisponível; testes executados em Actions.
API cobre consentimento/RBAC/isolation/step-up/tamper/replay/rollback,
aniversário + excedente, flags desligadas, trial sem conversão,
concorrência, manual + worker, restart/timeout e revogação/cancelamento entre freeze e envio.
PostgreSQL usa duas conexões reais do serviço efêmero de CI e comprova fence antes do efeito.
Web exige aceite explícito, mantém a mesma chave após incerteza e separa emissão de débito;
navegador com API real verifica autorização/desativação sem criar outra fatura.

## Próximo
Entrega persistente e honesta de dunning/notificações; custos medidos; fiscal e homologação real.
Ativação do invocador em infraestrutura existente permanece sujeita à autorização específica.
Sem revisão de segurança independente nesta entrega.
