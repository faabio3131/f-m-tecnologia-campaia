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

## Achados registrados, NÃO corrigidos nesta revisão (exigem decisão de arquitetura)

| # | Achado | Risco | Por que não corrigido agora |
|---|---|---|---|
| 3 | Idempotência de `create_charge` (tanto no simulador quanto no `AsaasGateway`) é mantida só em memória (`_created`, dicionário do processo). Reiniciar o processo entre o envio da cobrança e a confirmação perde essa memória — um retry após reinício poderia gerar uma segunda cobrança real no Asaas | **Alto para produção** — mas hoje nenhum destes módulos está persistido nem ligado a `api/`; o risco é real assim que isso for exposto por uma rota HTTP com retry automático | Corrigir exige uma decisão de persistência (tabela de idempotência, provavelmente em `backend/db/`) — fora do escopo desta revisão pontual; **deve bloquear produção real**, não sandbox |
| 4 | Nenhuma verificação de RBAC/permissão está embutida em `charge_subscription`/`try_settle` — qualquer código que os chame executa a cobrança | Baixo hoje (nenhuma rota HTTP os expõe ainda, mesmo padrão de B5/pacing) | Autorização é responsabilidade da camada `api/`, que ainda não foi construída para este motor — registrar como requisito quando essa camada for construída, não decidir agora |
| 5 | Confirmação de pagamento hoje é só por *polling* (`get_charge_status`), sem um receptor de webhook do Asaas verificado por assinatura | Médio — polling não reage em tempo real e não cobre eventos pós-liquidação (estorno, chargeback) que mudariam o status depois do fato liquidado já ter sido gerado | Construir um webhook receptor é um bloco novo, com verificação de assinatura HMAC (mesmo padrão de `webhooks.py` já existente no domínio) — fora do escopo desta revisão pontual |

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
