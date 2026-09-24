# Reconciliação: motor de cobrança própria + gateway Asaas importados de `faabio3131/campaia`

**Data:** 24/09/2026

## Achado de processo (comunicado com transparência)

Uma sessão de trabalho anterior a esta (24/09/2026, mesmo dia) operou por várias horas em
`faabio3131/campaia`, construindo um motor de assinatura/cobrança própria e um adaptador de
gateway de pagamento (Asaas), **sem saber que esse repositório havia sido declarado somente
leitura pela ADR-0015 (19/09/2026)**. A causa raiz: a sessão só tinha acesso de repositório
configurado para `faabio3131/campaia`, sem visibilidade da ADR-0015 nem do repositório canônico.
O Diretor identificou a inconsistência ao perguntar qual repositório era o mais recente.

Nenhum commit foi feito neste repositório canônico durante o período do engano — o erro ficou
inteiramente contido em `faabio3131/campaia` (fonte histórica), sem contaminar o CURRENT deste
repositório. Esta reconciliação importa o trabalho de valor comprovado e descarta o que não
tem valor aqui.

## O que foi trazido

Do repositório histórico `faabio3131/campaia`, commits `f8cf1a8`, `06d077b`, `8338bdb` (branch
`claude/vigilant-babbage-sxedm3`, mergeada via PR#2 naquele repositório) — **apenas o código e
os testes**, copiados manualmente (não via `git cherry-pick` de commit inteiro) para não
arrastar os arquivos de painel de execução daquele repositório, que usam numeração e narrativa
totalmente incompatíveis com a linha `v17→v20` deste repositório canônico:

- `backend/campaia_core/subscription.py`, `payment_gateway.py`, `payment_simulator.py`,
  `billing_settlement.py`, `asaas_gateway.py`
- `backend/tests/test_subscription.py`, `test_payment_gateway.py`, `test_billing_settlement.py`,
  `test_asaas_gateway.py`
- `backend/scripts/asaas_smoke_test.py`
- `.github/workflows/asaas-sandbox-smoke.yml`

## O que foi deliberadamente descartado (não portado)

- A especificação de telas ("B8") feita hoje naquele repositório — **redundante**: este
  repositório canônico já tem uma especificação de telas superior, feita em 05/09
  (`docs/product/13_ESPECIFICACAO_TELAS_APP.md`, cobrindo F1–F10, pesquisa de concorrentes e o
  Modo Automático de autonomia).
- Todas as edições ao arquivo de painel de execução daquele repositório
  (`backend/01_PAINEL_EXECUCAO_v18_VIGENTE.md` de lá) — incompatíveis com o painel deste
  repositório, que já está em v20 com narrativa própria (Ponto Zero Web, quarentena do mobile).
- Os arquivos de evidência daquele repositório (`EVIDENCIA_B11_*`, `EVIDENCIA_B8_*`,
  `DIRETOR_DECISAO_GATEWAY_PAGAMENTO_ASAAS_20260923.md`) — a decisão e a evidência foram
  reescritas neste documento e na ADR-0020, no formato deste repositório.

## Conflito de decisão de produto encontrado e resolvido

`docs/product/DECISOES_DIRETOR.md` (26/08/2026) descrevia um modelo comercial diferente
("assinatura pura, sem créditos", Stripe) do que foi construído. Investigado e resolvido em
`docs/18_ADR_0020_MODELO_COMERCIAL_E_GATEWAY_DE_PAGAMENTO.md` — resumo: D-06 (27/08/2026, um dia
posterior) já havia decidido o modelo híbrido (franquia + créditos extras) e nunca foi
propagado para este repositório; reafirmado por autoridade humana atual em 24/09/2026, junto
com a escolha do Asaas como gateway. Item 3 de `DECISOES_DIRETOR.md` marcado como superseded,
não apagado.

## Testes — CURRENT antes e depois, execução real

Antes da importação (branch `main`, HEAD confirmado limpo):
```
cd backend && python3 -m unittest discover -s tests        # 267 OK
cd backend && python3 -m unittest discover -s tests_api -t .   # 81 OK
```

Depois da importação (branch `reconciliation/b11-billing-asaas-20260924`):
```
cd backend && python3 -m unittest discover -s tests        # 303 OK (267 + 36 novos)
cd backend && python3 -m unittest discover -s tests_api -t .   # 81 OK (inalterado)
```

Zero regressão. Os 36 testes novos: 8 (`test_subscription.py`) + 10 (`test_payment_gateway.py`)
+ 4 (`test_billing_settlement.py`) + 14 (`test_asaas_gateway.py`).

## O que NÃO foi feito nesta reconciliação (pendências reais)

- **`fm-security-review` não foi formalmente executado** como skill deste repositório —
  autorevisão aplicada durante a construção original (idempotência, `SecretRef` nunca exposto,
  fail-closed em toda ambiguidade de status), mas não pela skill dedicada. Recomendado antes do
  merge.
- **`fm-certify-change` não foi executado** — este documento não substitui essa certificação.
- Adaptador Asaas **não verificado contra conta real** — só contra `httpx.MockTransport`. Chave
  de Sandbox já gerada pelo Diretor; verificação real pendente (tentativa via GitHub Actions
  bloqueada por cota de minutos esgotada; alternativa local via VS Code em andamento).
- **Merge não realizado.** Esta reconciliação abre PR em modo rascunho contra `main`, sem merge
  automático — mesma disciplina da ADR-0015 (reconciliação anterior). Merge requer autorização
  humana explícita e atual (CLAUDE.md, "Execução controlada").

## Status exato

`IMPLEMENTADO` e `TESTADO` (suíte local). **Não** `HOMOLOGADO`, **não** `PRONTO PARA PRODUÇÃO`,
**não** `COMERCIALMENTE DISPONÍVEL`. Merge para `main` deste repositório canônico: **pendente de
autorização explícita do Diretor**.
