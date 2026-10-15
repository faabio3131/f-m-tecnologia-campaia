# WP-R02-05 — Ciclo por aniversário, franquia e consentimento

**Status:** PARTIAL — candidato interno; G5 continua aberto.
**Base:** main@2bfbe10425387432f792e4bb86856d9e4d22f5c1 (PR #48 integrada).
**Branch:** feat/wp-r02-credit-cycle-integration.

## Autoridade e CURRENT

Em 15/10/2026, às 17:58 de São Paulo, o Diretor autorizou continuidade das tarefas:
“Se passar verde, prossiga. Se não passar verde, faça a correção e prossiga”.
A autorização cobre implementação, correções e integração após gates completos. Não muda
os gates de produção, credenciais reais, migrations externas, gasto relevante, decisões
comerciais/jurídicas novas ou GO/NO-GO. O executor não deve repetir pedidos para tarefas
rotineiras já autorizadas. O resultado é medido por implementação, evidência, CI da PR e
pós-merge; não por quantidade de documentos ou por porcentagem estimada.

A PR #48 foi integrada em 2bfbe10425387432f792e4bb86856d9e4d22f5c1.
CI pós-merge: Backend 38806376654, Frontend 38806376521, F4 38806376563: success.
Isso certifica a fundação interna do journal, não a cobrança de entregas de IA em produção.

## Delta implementado

- Componente temporal da assinatura: aniversário no fuso America/Sao_Paulo, UTC persistido,
  dia original preservado após mês curto, períodos [início, fim) e índice mensal estável.
- Identidade da obrigação inclui produto, tenant, lifecycle, finalidade e índice. Primeiro
  pagamento fixa a âncora; recuperação não a desloca; replay não concede franquia novamente.
  O componente temporal não antecipa a vigência por pagamento adiantado.
- Catálogo externo pode declarar credit_policy versionada, pesos e condições do trial.
  Não existe default comercial ativo ou alteração silenciosa de contrato já armazenado.
- Trial abre somente sua franquia configurada. Pagamento vinculado a obrigação/lifecycle
  abre a franquia paga integral, sem somar o saldo de trial. Leitura nunca cria franquia.
- Renovação comercial usa período server-side e excedente efetivamente liquidado do ciclo
  anterior, com linhas separadas. Recusa uso informado pelo browser e fechamento com reserva
  incerta. Emissão continua pela rota existente; scheduler operacional ainda é pendência.
- GET /billing/usage entrega saldo, reservas, consumo, preço, teto e alertas 80/100 por tenant;
  ausência de medição retorna UNAVAILABLE com balance null, nunca zero inventado.
- POST /billing/usage/consent exige BILLING_MANAGE, step-up, CSRF para cookie, idempotência
  e revisão de ciclo/preço/versão. Adesão persistida até revogação, com snapshot por ciclo;
  teto reseta por ciclo. Preço/versão diferente não herda consentimento antigo.
- Durante carência configurada, o journal permite somente a franquia paga remanescente,
  sem excedente nem nova franquia antes de pagamento.
- Web mostra consumo persistido, distingue reserva de entrega e apresenta autorização
  com revisão explícita, teto editável e zero para revogar. Retries mantêm corpo e chave.
- Contratos, tipos gerados, testes negativos e teste PostgreSQL entre workers acompanham o delta.

## Correção de causa raiz no webhook

FATO CONFIRMADO: o receptor marcava o evento como visto antes das mutações comerciais,
sem transação que incluísse dedupe, assinatura, observação e franquia. Também confirmava
cobrança ainda desconhecida, inclusive quando o callback antecedesse o commit da emissão.

CORREÇÃO: autenticação separada da marcação de processamento; evento conhecido usa a
transação existente F3 e o mesmo lock de tenant das mutações HTTP. Falha na concessão
reverte assinatura e dedupe juntos; a próxima entrega pode concluir. Cobrança autenticada
ainda ausente retorna 503 sem marcar vista; duplicata realmente processada retorna 200.
Pagamento confirmado de ciclo comercial não pode ser desfeito por OVERDUE atrasado.

Provas: injeção de falha com rollback + retry, chegada antes da cobrança + retry após
persistência, replay após restart e processamento concorrente em dois workers PostgreSQL.
Os testes antigos de dedupe agora criam cobrança conhecida via API; não confundem evento
processado com referência inexistente. Rate limit continua comprovado antes da autenticação.

Fonte primária conferida em 15/10/2026:
https://docs.asaas.com/docs/faq-de-webhooks — HTTP 200 confirma entrega; falhas provocam
retentativas, com interrupção após falhas consecutivas. Referências permanentemente não
conciliadas precisam de diagnóstico operacional antes desse limite, não retries infinitos.
Inbox assíncrono e monitoramento operacional final permanecem no escopo F12/F17.

## Compatibilidade, ativação e rollback

Novas condições são opcionais. Catálogos e contratos legados mantêm o comportamento
certificado. A emissão comercial é opt-in por credit_policy no catálogo externo, ainda
não ativada em staging/produção. Nenhum preço real foi incorporado como default do código.

O codec mantém campos novos em envelope commercial_v1 allowlisted e preserva construtores
financeiros antigos. Isso não autoriza writer antigo sobre contrato V1: ele ignoraria a
extensão. Antes de rollback, bloquear mutações de billing/IA e drenar workers. Não certificar
rollback financeiro automático sem esse gate. Default None continua lendo registros antigos.

Startup persistente agora exige a migration 005 já versionada; não aplica PostgreSQL
implicitamente. Deploy exige aprovação e migration antes da revisão nova. Cloud SQL não foi
religado; nenhuma credencial, migration externa, cobrança real ou deploy foi executado.

## Pendências que não podem desaparecer

- Vincular cada entrega IA à reserva já commitada e ao resultado durável recuperável;
  nenhuma rota IA é comercialmente debitada por este bloco.
- Enforcement dos limites de usuários/campanhas do trial e plano nos comandos correspondentes.
- Upgrade/downgrade na próxima vigência, cancelamento de renovação e reativação com lifecycle
  novo. Contratos opt-in recusam os endpoints legados incompatíveis e a Web informa a pendência;
  contratos legados continuam exercitados. Não ativar catálogo comercial antes de fechar isso.
- Scheduler único de renovação/dunning/avisos e reconciliação operacional, checkout final,
  ajustes/reversões após fechamento, refunds, residual mínimo e custos reais.
- Homologação externa Asaas e G5 real; F16/F17/F18/F19/F20 permanecem seus próprios gates.

## Validação

Resultados no commit exato serão anexados à PR. Execução local: domínio 414 testes passaram;
API completa deve permanecer verde após os novos cenários; 19 PostgreSQL não executam sem
DSN local e precisam do job PostgreSQL 16. Web check passou: lint, strict typecheck, drift,
boundaries, 93 testes e build. Não chamar componente simulado de pagamento real.
