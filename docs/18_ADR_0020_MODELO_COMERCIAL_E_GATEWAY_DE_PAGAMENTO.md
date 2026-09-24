# ADR-0020 — Modelo comercial da assinatura do CampaIA e gateway de pagamento

**Status:** APROVADA · **Data:** 24/09/2026 · **Aprovador:** Fábio Aluizio da Silva

## Contexto

`docs/product/DECISOES_DIRETOR.md`, item 3 (26/08/2026), registra **"Assinatura pura, sem
créditos pré-pagos"**, com **Stripe** cotado para "Billing Fase 2+". Esse mesmo documento se
declara, no próprio cabeçalho, potencialmente desatualizado ("onde divergir do
`DECISION_REGISTER.md`, o Decision Register prevalece") — mas `DECISION_REGISTER.md` não existe
neste repositório (referência quebrada; confirmado por busca, não presumido).

Um dia depois (27/08/2026), no repositório histórico `faabio3131/campaia` (fonte não canônica
desde a ADR-0015), o Diretor decidiu D-06: **"Franquia inclusa no plano + créditos extras
pagos"** — um modelo híbrido, com sua fala citada literalmente em
`DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md` daquele repositório. Essa decisão nunca foi
propagada para este repositório canônico porque, na época, os dois repositórios já haviam
divergido (ver ADR-0015).

Em 24/09/2026, retomando o trabalho, o Diretor foi consultado ao vivo sobre qual gateway de
pagamento usar para operacionalizar a cobrança própria do CampaIA (autoridade humana atual e
explícita — CLAUDE.md, seção "Autoridade", item 1, e STOP condition "operação financeira sem
autoridade clara"). Optou por **Asaas**, com a ressalva explícita de manter a integração
configurável (nenhuma alteração de código para trocar de conta/ambiente/cliente).

## Conflito identificado

Este repositório carregava, sem que ninguém tivesse percebido até esta ADR, duas afirmações
comerciais incompatíveis: "assinatura pura sem créditos" (26/08) vs. o híbrido de D-06 (27/08,
nunca importado para cá). CLAUDE.md, seção "Autoridade": *"Documento histórico não prevalece
silenciosamente sobre CURRENT comprovado; registrar e reconciliar a divergência."* Esta ADR é
esse registro e essa reconciliação.

## Alternativas analisadas

| Opção | Vantagem | Custo/Risco |
|---|---|---|
| A — Manter "assinatura pura + Stripe" (item 3 de `DECISOES_DIRETOR.md`) | Já documentada neste repositório canônico | Ignora D-06, uma decisão posterior e mais específica do próprio Diretor; limite rígido de tokens/campanhas interrompe uma campanha de marketing ativa no meio do mês; Stripe é mais fraco em PIX/boleto para o público-alvo (D-03: pequeno negócio local brasileiro) |
| **B — Híbrido (D-06) + Asaas (escolhida)** | D-06 é cronologicamente posterior e mais específica sobre este exato assunto; nunca bloqueia o serviço (cobra excedente em vez de interromper); Asaas atende PIX/boleto, natural para o público brasileiro de D-03; conta Asaas já criada e testada nesta mesma data | Descarta a linha "Stripe Fase 2+" do documento de 26/08 — mitigado marcando-a como superseded, não apagando |
| C — Suspender a decisão até nova pesquisa de mercado | Evita decidir com informação incompleta | Bloqueia o motor de cobrança já construído e testado (40 testes) sem necessidade — nenhuma informação nova mudaria o fato de que D-06 é posterior a "assinatura pura" |

## Decisão

**Modelo comercial: híbrido — franquia mensal inclusa no plano + créditos extras pagos por
excedente de uso (D-06, 27/08/2026), reafirmado por autoridade humana atual em 24/09/2026.**

**Gateway de pagamento: Asaas**, integrado via um contrato próprio (`payment_gateway.py`) que
não conhece o provedor específico — trocar de gateway no futuro é configuração, não reescrita.

## Efeito sobre `docs/product/DECISOES_DIRETOR.md`

O item 3 desse documento ("Assinatura pura, sem créditos pré-pagos... Stripe") fica marcado como
**SUPERSEDED por esta ADR-0020** diretamente no arquivo (não removido, conforme
`02-PADROES-DE-CONSTRUCAO-NOVA-FM.md` §7: "Decisão substituída não deve ser apagada; deve ser
marcada como superseded").

## Motor construído sob esta decisão

Portado nesta mesma reconciliação (branch `reconciliation/b11-billing-asaas-20260924`), do
repositório histórico `faabio3131/campaia` (commits `f8cf1a8`, `06d077b`, `8338bdb` — código
apenas, sem os arquivos de painel/evidência daquele repositório, que usam numeração e formato
incompatíveis com este):

| Arquivo | Papel |
|---|---|
| `backend/campaia_core/subscription.py` | Cálculo determinístico da cobrança por competência (franquia + excedente de créditos) — `PlanDefinition` como dado de configuração, nunca preço fixo em código |
| `backend/campaia_core/payment_gateway.py` | Contrato canônico do gateway de pagamento (`PaymentGatewayConnector` Protocol) — agnóstico de provedor |
| `backend/campaia_core/payment_simulator.py` | Simulador fiel ao contrato, para dev/CI, sem depender de conta real |
| `backend/campaia_core/billing_settlement.py` | Orquestra cobrar → confirmar → gerar fato liquidado; fail-closed (pendente/recusado nunca vira fato liquidado) |
| `backend/campaia_core/asaas_gateway.py` | Adaptador real do Asaas, configurável 100% por variável de ambiente; URLs/formato verificados contra documentação oficial e SDK real (23/09/2026), não de memória |
| `backend/scripts/asaas_smoke_test.py` + `.github/workflows/asaas-sandbox-smoke.yml` | Verificação manual (workflow_dispatch) contra a API real do Asaas Sandbox, sem a chave passar pela conversa com o assistente |

Este motor alimenta o adapter fiscal fail-closed `fiscal_handoff.py` (já importado neste
repositório canônico via ADR-0015 / bloco FISC V2-16.5): fecha, em simulador, o ciclo completo
cobrar → confirmar → fato liquidado → handoff fiscal.

## O que esta ADR NÃO resolve

- O adaptador Asaas não foi verificado contra uma conta real — só contra `httpx.MockTransport`
  (o Diretor já gerou uma chave de Sandbox; verificação real pendente, tentativa via GitHub
  Actions bloqueada por cota de minutos esgotada, alternativa local pelo VS Code em andamento).
- A tabela real de preços dos planos (valor da franquia, quantidade de créditos incluídos, preço
  do crédito extra) não é decidida aqui — continua fora de código, como dado de configuração.
- Não decide o destino do `mobile/` (quarentena arquitetural, ADR anterior) nem toca no System
  Design Web.

## Consequências

Fica mais fácil: existe agora uma única decisão comercial vigente neste repositório canônico,
sem contradição interna. Fica mais difícil: nenhuma nova — o custo de reconciliação já foi
absorvido nesta mesma mudança.

## Reversibilidade

Alta. O contrato de gateway é agnóstico de provedor; trocar de Asaas para outro gateway no
futuro não exige tocar em `subscription.py` nem em `billing_settlement.py`.
