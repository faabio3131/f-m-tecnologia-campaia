# WP-R02-02 — Histórico de cobranças e fatura hospedada

15/10/2026. Status: PARTIAL até CI/revisão/integração. F5/G5 PARTIAL.

## CURRENT confirmado

Repositório faabio3131/f-m-tecnologia-campaia. Base main
20727bcb23c64b339bde746f7c5c06c445c6ceca; checkout inicialmente limpo e consulta de PRs abertas vazia.
PR #45 integrada com autorização; pós-merge Backend 38772626146, Frontend 38772626194,
F4 38772626304 success. Preservado o motor, adapter, dedupe, settlement, entitlements e Billing Web inicial.

## Lacuna e implementação

CURRENT guardava SubscriptionCharge por ID do gateway, mas sem GET histórico e sem
observações persistidas de gateway/ambiente/data. ChargeResult descartava invoiceUrl.
TARGET desta entrega: histórico auditável pelo cliente e acesso à fatura já emitida.
Não é contratação inicial nem emissão automática de cobrança na Web.

- GET /billing/charges, BILLING_VIEW, escopo derivado da sessão, sem tenant_id fornecido pelo cliente.
- Até 50 itens, ordenação por primeiro registro/ID, cursor validado dentro do tenant. Cursor
  inválido ou de outro tenant retorna 422, nunca reinicia silenciosamente na primeira página.
- Consulta persistida usa rows_for_tenant; sem polling nem efeito financeiro no GET.
- Resposta exclui CPF/CNPJ/customer_ref, line items internos e credenciais; valores decimais string.
- Observações opcionais: ambiente/provedor, situação mapeada, origem CREATE/WEBHOOK e horário
  de observação local. O horário não é inventado como data efetiva do pagamento no provedor.
- Registros legados sem observação retornam null. Nunca presumir PENDING, produção ou pagamento.
- Replay de criação com outra chave HTTP conserva as observações recebidas depois da criação;
  evento duplicado ou token de webhook inválido não altera o histórico.
- Painel Web com vazio/erro/retry/paginação, ambiente explícito e última observação registrada.
  O snapshot de recebimento não certifica frescor ou ordenação temporal dos eventos no provedor.
- invoiceUrl retornada pelo Asaas é preservada na criação e recuperação por externalReference.
  Apenas HTTPS e host/path exatos para o modo: sandbox.asaas.com/i/... ou www.asaas.com/i/....
  Sem userinfo, porta, query, fragment, whitespace ou host arbitrário. Ausência/invalidez não
  inventa link. Frontend repete a guarda e usa noopener/noreferrer/no-referrer.
- Link não constitui confirmação de pagamento; entitlements permanecem regidos pelo fluxo existente.

## Compatibilidade de persistência

Sem migration nova. Campos opcionais de observação são gravados em billing_observations no
ENVELOPE da dataclass, preservando o mapa fields financeiro original. O decoder anterior
ignora essa chave adicional e reconstrói os tipos anteriores; o decoder novo aceita somente
as extensões explicitamente permitidas de SubscriptionCharge/ChargeResult, sem permitir
sobrescrever tenant_id/valores. Dados antigos são lidos com defaults ausentes.

Um writer anterior pode descartar observações ao regravar um objeto; elas então voltam a
indisponíveis, preservando os dados financeiros. Rollout/rollback operacional continua gate
separado, com drain de workers necessário para preservar a continuidade da projeção histórica.
Não foi executado rollout nem rollback em ambiente externo nesta etapa.

## Verificação

- Domínio completo: 409 testes, OK.
- API completa: 314 testes, OK (16 skipped por dependência PostgreSQL local).
- Foco billing/persistência/Asaas/compatibilidade: 74 testes, OK.
- Web check: lint, tipos, contrato, fronteiras, 84 testes em 23 arquivos e build, OK.
- Novo teste PostgreSQL CI: dois workers emitem a mesma competência com chaves HTTP distintas,
  recebem um único ID, leem histórico isolado e observam atualização webhook entre instâncias.
- SQLite: metadados de criação e webhook sobrevivem a reinícios de instâncias reais.
- Compatibilidade: construtores do schema anterior continuam recebendo somente seus campos;
  novo decoder preserva extensões e recusa tentativa de rehome via extensão.
- URLs: casos de host falso, ambiente trocado, userinfo, query/fragment, HTTP, whitespace e
  simulador recusados. Transport mock Asaas cobre retorno do link em criação e crash recovery.
- Web: 15 casos focados da página/painel, incluindo retry de cursor sem apagar lista anterior.
- E2E existente estendido: emissão SIMULATOR via API no tenant isolado; histórico Web mostra
  simulação/pendência/valor; outro tenant obtém lista vazia. Pipeline CI da PR valida esse cenário.
- Chromium permanece indisponível no ambiente local (falha de download anterior registrada no
  WP-R02-01); não se declara nova captura ou E2E local aprovado. Resultado final CI será registrado na PR.

## Fontes oficiais do contrato externo

Verificadas em 15/10/2026, sem efetuar chamadas financeiras reais:
- https://docs.asaas.com/docs/cobrancas-via-cartao-de-credito
- https://docs.asaas.com/reference/criar-cobranca-com-cartao-de-credito
- https://docs.asaas.com/docs/webhook-para-cobrancas

Essas fontes documentam invoiceUrl e acompanhamento por webhook. Preservado billingType
UNDEFINED do adapter vigente; nenhum método financeiro ou condição comercial nova foi escolhido.

## Pendências e limites

TARGET/HUMAN_DECISION: medição comercial persistente por competência e conversão em créditos.
CostLedger atual usa cost_units em memória, sem período persistente; não equivale à franquia
comercial. Custos internos de IA não são apresentados como saldo/créditos ao cliente.
TARGET: contratação inicial/checkout completo, reconciliação financeira/ordenação de eventos
quando definida e E2E real pagamento -> webhook -> entitlement.
HUMAN_DECISION: tabela/políticas comerciais reais; EXTERNAL_CREDENTIAL: credenciais apropriadas.

Sem merge/deploy, migration real, credencial real, gateway ligado, pagamento ou anúncio.
Cloud SQL não foi ligado nesta execução; última prova externa permanece STOPPED / NEVER.

## Adendo — integração autorizada WP-R02-02

PR #46 integrada após autorização expressa em main@f3428e6eb4a2c476a258d1f2bb7c2cb4c6907ce2.
CI pós-merge no SHA exato: Backend/PostgreSQL 38775081449, Frontend/E2E 38775081492,
F4 38775081381, todas success. WP-R02-02 DONE_VERIFIED nesse escopo. Registros anteriores de
integração/CI pendentes são SUPERSEDED. F5/G5 continuam PARTIAL. Sem deploy/religamento do banco.
