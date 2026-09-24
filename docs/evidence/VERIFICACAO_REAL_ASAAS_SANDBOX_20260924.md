# Verificação real do AsaasGateway contra a API do Asaas Sandbox

**Data:** 24/09/2026

## Método

Execução manual de `backend/scripts/asaas_smoke_test.py`, pelo Diretor, no VS Code, na própria
máquina, contra a chave de API real gerada em `sandbox.asaas.com` (conta pessoa física — CNPJ
não exigido para uso normal da API, apenas para o produto de subcontas, confirmado por pesquisa
antes de prosseguir). A chave nunca foi digitada nem colada neste chat — configurada via
`Read-Host -AsSecureString` no terminal, mascarada na tela. A tentativa via GitHub Actions
(`asaas-sandbox-smoke.yml`) foi abandonada por cota de minutos da conta esgotada; a verificação
real acabou saindo pelo caminho local, não pelo workflow automatizado.

## Achado de processo: exposição acidental de uma chave (mitigado)

Numa tentativa anterior a esta, antes do uso de `Read-Host -AsSecureString`, a chave real
apareceu em texto puro no terminal (colada diretamente após um comando, sem máscara) e foi
capturada num print enviado a este assistente. Tratada como potencialmente comprometida por
disciplina — mesmo sendo chave de Sandbox, sem risco financeiro real — e recomendada a rotação
(revogar e gerar nova). A chave finalmente usada nesta verificação foi confirmada como tendo
comprimento plausível (166 caracteres) antes do uso, e as tentativas seguintes já usaram a
técnica de entrada mascarada corretamente.

## Execução e resultado

```
Modo: SANDBOX — chave configurada: sim
Cliente HTTP construido com sucesso para o provider ASAAS.
Cobranca de teste criada: id=pay_yiiurrzcqcth6ma4 status=PENDING
Status consultado de volta: PENDING
OK — adaptador AsaasGateway verificado contra a API real (Sandbox).
```

Cliente real criado (`externalReference` do tipo `smoke-customer-<hex>`), cobrança real de
R$ 5,90 criada e consultada de volta com sucesso. Nenhum efeito real — ambiente de Sandbox.

## Defeitos reais encontrados e corrigidos nesta verificação

| # | Sintoma real (resposta da API) | Causa raiz | Correção |
|---|---|---|---|
| 1 | `VALIDATION_REJECTED` na criação do cliente | `POST /customers` do Asaas exige `cpfCnpj`, nunca enviado pelo adaptador original | `customer_document` virou campo obrigatório do contrato (`payment_gateway.py`), propagado por `Subscription`/`SubscriptionCharge` (não é peculiaridade do Asaas — qualquer gateway brasileiro real precisaria disso) |
| 2 | `VALIDATION_REJECTED`: *"O valor mínimo para cobranças com a forma de pagamento Pergunte ao Cliente é R$ 5,00"* | Cobrança de teste usava R$ 1,00, abaixo do mínimo do Asaas para `billingType: UNDEFINED` | Checagem fail-closed adicionada em `AsaasGateway.create_charge`, antes de qualquer chamada de rede; smoke test ajustado para R$ 5,90 |

Nenhum dos dois defeitos foi hipotético ou antecipado por leitura de documentação antes desta
sessão — os dois só apareceram porque o teste rodou contra a API real, não contra
`httpx.MockTransport`. Isso confirma o valor de ter feito essa verificação: `httpx.MockTransport`
prova que o código faz a chamada certa contra o *formato* documentado, mas não prova regra de
negócio específica da conta/produto real (como o mínimo de R$ 5,00).

## Estado após esta verificação

**Adaptador `AsaasGateway` verificado e funcional contra conta Sandbox real.** Pendências que
seguem em aberto:

- Migração para conta Asaas de produção (pessoa jurídica) quando o CNPJ da F&M sair.
- Definição da tabela real de preços dos planos (`plan_catalog.py` já pronto para recebê-la).
- `fm-security-review` e `fm-certify-change` formais, ainda não executadas.
