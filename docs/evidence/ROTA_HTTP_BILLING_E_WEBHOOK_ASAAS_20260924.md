# Rota HTTP do motor de cobrança + webhook do Asaas (B11 / ADR-0020)

**Data:** 24/09/2026 · **A pedido de:** Fábio Aluizio da Silva.

## O que foi construído

Integração do motor de cobrança (até aqui só domínio, `campaia_core/`) com a camada `api/`,
seguindo o mesmo padrão de toda rota existente (autorização via `permissions.authorize`,
idempotência via `state.idempotency`, serialização via Pydantic):

| Rota | Papel |
|---|---|
| `PUT /billing/subscription` | Cria/substitui a assinatura ativa do tenant. Busca o plano em `plan_catalog.py` — falha com `503 BILLING_CATALOG_UNAVAILABLE` se o catálogo não estiver configurado ou o `plan_id` não existir, nunca inventa um plano |
| `GET /billing/subscription` | Consulta a assinatura do tenant |
| `POST /billing/charges` | Calcula a cobrança do ciclo (`compute_cycle_charge`) e envia ao gateway (`charge_subscription`); guarda a cobrança em `state.charges`, indexada pelo `gateway_charge_id` real — é assim que o webhook encontra de volta a cobrança |
| `POST /webhooks/asaas` | Único endpoint sem Bearer token de usuário — autenticidade vem do token estático do Asaas (`asaas-access-token`), verificado por `AsaasWebhookReceiver` |

Nova permissão `BILLING_VIEW`/`BILLING_MANAGE` em `permissions.py` (achado #4 do
fm-security-review, agora resolvido): `BILLING_MANAGE` exige step-up e MFA (mesma classe de
`BUDGET_CHANGE`), concedida a OWNER e FINANCE; `BILLING_VIEW` mais ampla (OWNER, ADMIN,
FINANCE, APPROVER).

`AppState` ganhou `subscriptions`, `charges`, `billing_gateway` (simulador por padrão — só usa
`AsaasGateway` real se `ASAAS_API_KEY` estiver configurada, mesma disciplina de "nunca um
provedor real por padrão" já usada por `ai_provider`) e `asaas_webhook`.

## Achado real encontrado durante a construção (corrigido)

Esqueci de chamar `note_step_up_header()` antes de `authorize()` — sem isso, o header
`X-Step-Up-Token` nunca era reconhecido e toda chamada a `BILLING_MANAGE` falhava com
`STEP_UP_REQUIRED`, mesmo enviando o header certo. Descoberto pelos próprios testes (6 falhas
reais antes da correção, não hipotéticas). Corrigido replicando a ordem já usada em
`routes_campaigns.py`/`routes_approvals.py`.

## Achado novo, registrado e NÃO corrigido nesta rodada

**Dedupe do webhook também só existe em memória** (`AsaasWebhookReceiver._seen`) — mesma
classe de problema do achado #3 do fm-security-review anterior (idempotência de cobrança),
agora do lado da recepção. Se o processo reiniciar, um evento já processado que o Asaas
reenvie (entrega "pelo menos uma vez") pode ser processado de novo, gerando um segundo
registro de auditoria e um segundo handoff fiscal para o mesmo `billing_id`. **Mesma
correção arquitetural do achado #3 se aplicaria aqui** (um dedupe persistido), mas não foi
construída nesta rodada — o escopo já era grande o suficiente para uma sessão. Registrado
para não ser esquecido, não escondido.

## Testes

`backend/tests_api/test_billing.py` — 16 testes novos: autorização (papel sem permissão,
sem step-up, isolamento entre tenants), catálogo de planos ausente/plano desconhecido,
criação de cobrança e idempotência HTTP, e o webhook (token errado → 401, evento duplicado
→ rejeitado, `payment_id` desconhecido → aceito mas não processado, status pendente → aceito
mas não liquidado, status confirmado → liquidado de ponta a ponta).

```
cd backend && python3 -m unittest discover -s tests        # 338 OK, inalterado
cd backend && python3 -m unittest discover -s tests_api -t .   # 97 OK (81 + 16 novos)
```

Zero regressão nos testes preexistentes.

## Estado exato

**`IMPLEMENTADO`, `INTEGRADO` e `TESTADO`** — agora sim ligado a `api/`, testado via HTTP de
ponta a ponta. **Não** `HOMOLOGADO` (nenhum processo formal de QA), **não** `PRONTO PARA
PRODUÇÃO` (dedupe de webhook não persistido, sem conta de produção do Asaas, sem tabela real
de preços, sem rate limiting no webhook público, sem `fm-certify-change` re-executado sobre
este HEAD especificamente).
