# Evidência — Fase 1: documentação de `/auth/session`, `/me/memberships`, `/auth/session/switch`

**Data:** 25/09/2026 · **Branch:** `feat/campaia-wp01-web-foundation` (PR #5).

## FATO CONFIRMADO antes da mudança

`contracts/bff-openapi.yaml` é o contrato do "Mobile BFF API", com `security` global
`bearerAuth` (Bearer JWT). Os 3 endpoints de sessão real da Web (WP-02/WP-03) usam um
mecanismo de autenticação **diferente** — cookie HttpOnly/Secure/SameSite=Lax +
double-submit CSRF — nunca reconciliado no contrato compartilhado. Pendência já
registrada em sessões anteriores, não corrigida até agora.

## DECISÃO

Documentar os 3 endpoints com precisão técnica, não só "encaixá-los" sob `bearerAuth`:
novo `securitySchemes.cookieAuth` (apiKey/cookie), override de `security` por operação
(`security: []` no login, `security: [cookieAuth: []]` nos demais), novo parâmetro
`CsrfToken` (X-CSRF-Token) referenciado só nas mutações sob `cookieAuth`. Schemas novos:
`SessionUser`, `MembershipItem`, `MembershipsResponse` — espelhando exatamente
`backend/api/models.py` (`SessionLoginResponse`, `MembershipItem`, `MembershipsResponse`).

**Divergência registrada, não corrigida (fora de escopo desta correção pontual):** o
schema `Me` já existente usa `format: uuid` para `user_id`/`tenant_id`, mas os valores
reais do backend não são UUID (`"user-owner-1"`, `"demo-tenant"`). Os novos schemas usam
`type: string` simples, tecnicamente corretos — a inconsistência com `Me` é pré-existente
e não foi tocada.

## Gates executados

| Gate | Resultado |
|---|---|
| `python3 -c "import yaml; yaml.safe_load(...)"` | OK |
| `npm run contracts:generate` (web) | OK, sem erro |
| `npm run contracts:check` (web) | OK, gerado em sincronia |
| `npm run typecheck` (web) | OK |
| `npm run lint` (web) | OK |
| `npm run test` (web) | `35 passed` |
| `npm run boundary:check` (web) | OK, 0 violações |
| `npm run build` (web) | OK, 11 rotas |
| `python3 validate_events_asyncapi.py` (contracts) | `24/24 eventos` |
| `python3 -m unittest discover -s tests` (backend) | `368 passed` |
| `python3 -m unittest discover -s tests_api -t .` (backend) | `151 passed` |

Nenhum path/schema pré-existente foi alterado além do ajuste de `format`/`required`
necessário para os schemas novos gerarem tipos corretos (`business_unit_id` marcado
`required` em `SessionUser`/`MembershipItem` porque o backend sempre o serializa, mesmo
quando `null` — nunca omite o campo).

`web/src/types/session.ts` migrado para reexportar os tipos agora gerados do contrato
(`SessionUser`, `Membership`, `MembershipsResponse`), removendo os tipos manuais e a
PENDÊNCIA que os acompanhava desde a Etapa 2.

## Status

`FASE 1 (gap de contrato /auth/session*) — FECHADA.` Nenhum merge/deploy nesta sessão.
