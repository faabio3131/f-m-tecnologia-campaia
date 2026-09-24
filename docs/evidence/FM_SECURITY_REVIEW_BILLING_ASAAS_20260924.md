# fm-security-review — motor de cobrança própria + gateway Asaas

**Data:** 24/09/2026 · **Escopo revisado:** `backend/campaia_core/subscription.py`,
`payment_gateway.py`, `payment_simulator.py`, `billing_settlement.py`, `asaas_gateway.py`,
`plan_catalog.py`, `backend/scripts/asaas_smoke_test.py`. HEAD no momento da revisão: `main`
após PR #11 (`d33f287`).

Conforme a skill: **não declaro "seguro"** — apenas o escopo revisado, as evidências, os
achados e as limitações desta análise.

## Achados corrigidos nesta revisão

| # | Achado | Evidência | Impacto | Correção |
|---|---|---|---|---|
| 1 | `AsaasConfig`/`AsaasGateway` expunham a chave de API em claro no `repr()` padrão de dataclass | Reproduzido: `repr(AsaasConfig(api_key="SECRET", ...))` imprimia o valor cru, antes da correção | Alto — `print()`, log de exceção não tratada, ou traceback capturado por depurador vazaria a credencial real | `api_key` marcado com `field(repr=False)`, mesma disciplina de `SecretRef` (`connectors.py`) |
| 2 | Corpo bruto da resposta de erro do Asaas (`response.text`) ia para `PaymentGatewayError.details["body"]`, que scripts como `asaas_smoke_test.py` imprimem para diagnóstico | Erros de validação do Asaas podem ecoar de volta um campo submetido (ex.: `cpfCnpj`, que é PII) dentro da descrição do erro | Médio — PII poderia acabar em log/console em caso de erro de validação | `_error_summary()` extrai só `code`+`description` estruturados do JSON de erro, nunca o corpo bruto; 2 testes novos provam isso |

Ambos com teste automatizado provando a correção (`test_config_repr_never_exposes_the_api_key`,
`test_error_detail_never_includes_the_raw_response_body`).

## Achados #3 e #5 — corrigidos em 24/09/2026 (mesmo dia, sessão seguinte)

**Atualização:** ambos foram resolvidos a pedido explícito do Diretor, no mesmo dia desta
revisão. Ver `docs/evidence/CORRECAO_IDEMPOTENCIA_E_WEBHOOK_ASAAS_20260924.md` para o relato
completo. Resumo:

- **#3 (idempotência só em memória):** `PaymentGatewaySimulator` e `AsaasGateway` agora
  recebem `idempotency` como parâmetro injetável (`IdempotencyStoreLike`, mesma forma de
  `campaia_core.infra.IdempotencyStore` e de `api.db.PersistentIdempotencyStore`, que já
  existia). Por padrão continua em memória (comportamento anterior preservado); em produção,
  basta injetar `PersistentIdempotencyStore` — nenhuma reescrita do gateway.
- **#5 (sem webhook):** novo `campaia_core/asaas_webhook.py` — verificação do token estático
  do Asaas (`asaas-access-token`, **não** HMAC, confirmado contra a documentação oficial),
  dedupe por `id` do evento, parser do payload real do Asaas. `billing_settlement.py` ganhou
  `try_settle_from_status`, reaproveitado tanto pelo polling quanto pelo webhook.

## Achado #4 — ainda registrado, não corrigido (fora de escopo de ambas as revisões)

| # | Achado | Risco | Por que não corrigido agora |
|---|---|---|---|
| 4 | Nenhuma verificação de RBAC/permissão está embutida em `charge_subscription`/`try_settle` — qualquer código que os chame executa a cobrança | Baixo hoje (nenhuma rota HTTP os expõe ainda, mesmo padrão de B5/pacing) | Autorização é responsabilidade da camada `api/`, que ainda não foi construída para este motor — registrar como requisito quando essa camada for construída, não decidir agora |

**Nota:** a rota HTTP que efetivamente recebe o webhook do Asaas (endpoint em `api/`) também
não foi construída nesta correção — só a lógica de domínio (verificação, parsing, liquidação),
testada e completa. Expor isso como rota HTTP é integração, mesmo tipo de trabalho que o resto
deste motor de cobrança já vem deliberadamente adiando (mesmo padrão do B5/pacing).

## Caminhos negativos e testes adversariais já cobertos

Confirmado por teste automatizado (321 testes de domínio, todos executados nesta revisão):
credencial ausente/inválida (`AUTH_EXPIRED`), valor abaixo do mínimo do Asaas, moeda diferente
de BRL, `idempotency_key`/`customer_document`/`tenant_id` ausentes, status desconhecido do
Asaas (nunca vira `CONFIRMED` por padrão — fail-closed), retry não duplica cobrança (dentro da
vida do mesmo processo).

## Classificação final

Nenhum achado desta revisão é `STOP DE PRODUÇÃO` **no estado atual** (nada em produção real,
nenhuma rota HTTP exposta, gateway ainda em modo Sandbox). Os achados #3 e #5 **devem** ser
tratados como bloqueadores antes de qualquer uso em produção real — registrados aqui para não
serem esquecidos, não descartados.
