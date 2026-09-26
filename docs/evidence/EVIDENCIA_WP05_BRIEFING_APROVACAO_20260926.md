# Evidência — WP-05: Briefing → Estratégia → Validação → Fila de Aprovação

**Data:** 26/09/2026 · **Branch:** `feat/campaia-wp01-web-foundation` (PR #5).

## CURRENT confirmado antes de codificar

Fluxo real do backend, já implementado e testado (`backend/api/routes_campaigns.py`,
`routes_approvals.py`, `tests_api/test_helpers.py::publish_ready_campaign`):
`POST /briefs` (cria DRAFT) → `POST /campaigns/{id}/plan/regenerate` (IA simulada,
avança para STRATEGY_READY) → `POST /campaigns/{id}/validate` (Policy Engine real,
avança até VALIDATED se aprovável, emite `policy_decision_id`) → `POST /approvals`
(cria pedido PENDING) → `POST /approvals/{id}/decision` (segregação de funções real,
`campaia_core.permissions.can_approve`). Publicação real (`POST .../publish`)
permanece **fora de escopo do WP-05** por decisão já registrada no roadmap (depende de
integração com provider — Fases 5–7).

**Achado (não bloqueante, registrado):** `POST /approvals` (criação do pedido) e os
campos `kind`/`requested_by`/`amount` de `ApprovalRequest` nunca tinham sido
documentados em `contracts/bff-openapi.yaml`, apesar de reais e testados — mesmo
padrão de gap já corrigido para outros endpoints nesta sessão. Documentados agora.

## Construído

### Frontend

- `web/src/app/(app)/(authenticated)/campaigns/page.tsx`: lista real (`GET
  /campaigns`) + formulário de briefing (`POST /briefs`).
- `web/src/app/(app)/(authenticated)/campaigns/[campaignId]/page.tsx` (novo): detalhe
  real — gera/regenera estratégia (`POST .../plan/regenerate` + `GET .../plan`),
  valida (`POST .../validate`, mostra `PolicyDecision` real com findings), solicita
  aprovação (`POST /approvals`) quando `outcome === "APPROVABLE"`.
- `web/src/app/(app)/(authenticated)/approvals/page.tsx`: fila real (`GET
  /approvals`), decide (`POST /approvals/{id}/decision`) — segregação de funções
  decidida 100% pelo backend; a UI exibe o erro real (`SEPARATION_OF_DUTIES`) quando o
  backend recusa, nunca esconde ou pré-filtra isso no cliente.

### Contrato

- `POST /approvals` documentado (criação de pedido).
- `ApprovalRequest`: campos reais `kind`/`requested_by`/`amount` adicionados.
- `PolicyDecision`/`ApprovalRequest`: `required` corrigido para bater com o que o
  backend sempre serializa (Pydantic não-opcional) — sem isso, os tipos gerados
  ficavam incorretamente opcionais e o `tsc` recusava o código real.

## Gates executados

| Gate | Resultado |
|---|---|
| Testes de domínio (backend) | `368 passed` (inalterado, nenhum arquivo de domínio tocado) |
| Testes de API (backend) | `158 passed` (inalterado — nenhuma rota backend nova neste WP, só contrato) |
| AsyncAPI | `24/24 eventos` |
| Lint / Typecheck (web) | `OK` |
| Unit/component (web) | `47 passed` (42 + 5 novos: Campaigns 1, CampaignDetail 1, Approvals 3) |
| Boundary check (web) | `OK`, 53 arquivos, 0 violações |
| Contract drift (web) | `OK` |
| Build produção (web) | `OK`, 12 rotas (nova rota dinâmica `/campaigns/[campaignId]`) |
| E2E protocolo de sessão + WP-03 + WP-04 + WP-05 real (web+backend) | **`14 passed`** (A–M) |

Teste E2E novo (**M**) prova o critério de aceite central do WP-05 de ponta a ponta,
contra o backend real: briefing → estratégia → validação (`APPROVABLE`) → pedido de
aprovação criado (PENDING) → **tentativa de autoaprovação pelo próprio proponente é
recusada pelo backend real com `SEPARATION_OF_DUTIES` (403)** → o pedido aparece na
fila real de Aprovações.

## Pendências registradas (fora de escopo desta entrega)

- Publicação real de campanha (`POST /campaigns/{id}/publish`) — depende de
  integração real com provider (Fases 5–7), decisão já registrada no roadmap.
- Teste E2E com DOIS usuários reais distintos decidindo uma aprovação (hoje só prova
  que o PRÓPRIO proponente é recusado; a aprovação bem-sucedida por outro ator já é
  coberta a nível de API/domínio em `tests_api`/`tests`, não repetida aqui).
- Regras mais ricas do Brand Kit na geração de criativos (F2.2) — fora de escopo,
  módulo de criativos não construído ainda.

## Status

`WP-05 (Briefing → Estratégia → Validação → Fila de Aprovação) — IMPLEMENTADO +
TESTADO, PRONTO PARA REVISÃO.` Publicação real permanece fora de escopo. Nenhum
merge/deploy nesta sessão.

---

## Fechamento do Bloco 1/3 (Fases 1–4 do painel mestre)

Com WP-04 e WP-05 concluídos nesta sessão, além da Fase 1 (contrato):

- **Fase 1 (contratos):** `/auth/session`, `/me/memberships`, `/auth/session/switch`,
  `/connections/oauth/callback`, `POST /approvals` documentados. Fechada.
- **Fase 2 (fundação/auth):** WP-02 + WP-03 confirmados implementados e testados
  (sessões anteriores).
- **Fase 3 (núcleo de campanhas):** WP-04 (Brand Kit + Conexões) e WP-05
  (Briefing→Aprovação) implementados e testados nesta sessão.
- **Fase 4 (IA):** confirmado — só testes unitários determinísticos contra provider
  simulado, sem suíte de evals real. Não construída nesta sessão (exigiria critério
  de avaliação de qualidade de saída de modelo real, decisão de produto/ADR fora do
  escopo "sem decisão pendente" deste bloco — registrada como pendência para decisão
  humana futura, não presumida).

Recomendação para o Bloco 2/3: integrações reais (Google Ads → Meta → WhatsApp,
Fases 5–7) bloqueadas por credenciais reais de terceiro (confirmar disponibilidade
antes de iniciar); mobile (Fase 8) bloqueado por decisão de destino ainda não tomada;
analytics (Fase 9) pode avançar sem bloqueio externo.
