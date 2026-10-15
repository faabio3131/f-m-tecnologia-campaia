# WP-R02-01 — Billing Web / 15-10-2026

Status: PARTIAL, proposto para revisão/CI. F5/G5 continuam PARTIAL.

## CURRENT e lacuna

Repo canônico faabio3131/f-m-tecnologia-campaia; base main
356f35448abf6b71b91c00a44a7ccc1db4e4906e. Consulta inicial de PRs abertas: nenhuma.
Motor, persistência, adapter Asaas, webhook e lifecycle preservados.
Faltava superfície Web para assinatura e operações já existentes; faltava GET de catálogo.
WP-R01 integrado nas PRs #43/#44 autorizadas e CI pós-merge verde, conforme adendo na matriz G2.

## Delta implementado

- GET /billing/plans: BILLING_VIEW, somente catálogo externo configurado; sem fallback.
  Falha ausente/inválida retorna 503 sem expor caminho de arquivo.
- GET/mutações da assinatura adicionam commercial_terms do snapshot contratado, sem
  recalcular o preço a partir do catálogo atual. Decimais serializados em strings.
- /billing: plano/condições atuais, catálogo, limites, trial, acesso e PAST_DUE/carência/lembretes.
- OWNER/FINANCE podem solicitar transições configuradas, cancelamento imediato e reativação
  via APIs existentes. ADMIN/APPROVER possuem consulta, conforme RBAC canônico.
- Confirmação explícita, CSRF do cliente central, step-up compartilhado e chave de idempotência
  conservada no retry da mesma confirmação. Backend continua autoridade de permissão/estado.
- Mudança de tenant/unidade/membership descarta a tela e a confirmação antigas.
- CPF/CNPJ não é exibido na tela. Consumo indisponível é declarado, nunca exibido como zero.
- Contrato OpenAPI e tipos gerados sincronizados. Nenhuma migration/dependência de produção nova.
- Harness E2E recebe identidade isolada e catálogo fictício somente de teste; nenhuma configuração
  de staging/produção é alterada. Next de teste usa loopback explícito. Ajuste mínimo do shell
  para quebra de contexto longo em viewport estreito, preservando design system.

## Verificação local

- Backend domínio: 406 testes, OK.
- Backend API: 305 testes, OK, 15 skipped (dependência PostgreSQL local).
  Primeira tentativa encontrou dependência socksio ausente por proxy SOCKS ambiental no teste
  preexistente de wiring Gemini; repetição sem variáveis de proxy passou. Sem alteração do produto
  para esse problema de ambiente, sem chamada Gemini real.
- Billing API focado: 33 testes, OK; quatro novos casos de catálogo/auth/snapshot/isolamento.
- Web check: lint, tipos, contrato, fronteiras, 79 testes em 22 arquivos e build, OK.
- Dez casos Web novos cobrem ausência/403/503, snapshot vs catálogo, atraso, leitura apenas,
  step-up, confirmação, retry com mesma chave + CSRF, troca pendente e troca de tenant.
- E2E adicionado: onboarding de identidade isolada, assinatura trial via API real, Web cancela e
  pede reativação; recarga mantém PENDING_PAYMENT/bloqueado; outro tenant recebe 404.
  Capturas desktop/mobile previstas no próprio teste. Execução local BLOCKED: download do
  Chromium retornou arquivo inválido e executável não disponível. Backend/Next subiram após
  ajuste de hostname explícito. Nenhum resultado visual/E2E local declarado como aprovado.
- CI da PR: pendente no momento da criação desta evidência. Registrar resultado real na PR.

## Fora de escopo / delta restante

HUMAN_DECISION: planos/preços/trial/grace/dunning/refund comerciais reais.
EXTERNAL_CREDENTIAL: conta/segredos Asaas produção.
TARGET: medição de consumo, histórico de cobranças, contratação/checkout e E2E financeiro
pagamento -> webhook -> entitlement. A tela não emite cobrança, não gera link de pagamento,
não simula consumo e não trata seleção de plano como pagamento.

Nenhum merge, deploy, migration real, pagamento, anúncio ou gasto de provedor executado.
Cloud SQL não foi ligado; última prova externa segue STOPPED / NEVER (WP-R01).
Não classificar G5 nem disponibilidade comercial como DONE_VERIFIED.

## Primeira CI e ajuste do harness

HEAD inicial 23978e9: Backend #242 e F4 #76 success; checks gerais Web/smoke success.
Suíte de sessão executou 28 cenários: 27 passaram; novo billing falhou na preparação
PUT (401), antes da UI. O APIRequestContext em HTTP loopback não envia o cookie Secure
emitido no onboarding. Preparação ajustada para fetch do navegador com credentials include,
seguindo o protocolo real da Web; nenhuma regra de cookie/auth relaxada no produto.
A negativa final também consulta pelo navegador autenticado. Nova CI necessária.
