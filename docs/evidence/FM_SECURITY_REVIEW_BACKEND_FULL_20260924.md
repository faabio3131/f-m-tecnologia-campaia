# fm-security-review — backend completo (item 1.9 do cronograma mestre)

**Data:** 24/09/2026 · **HEAD de partida:** `main` em `e034e22` (PR #17, itens 1.1/1.2
mesclados). **Escopo:** `backend/campaia_core/` e `backend/api/` inteiros, EXCETO os
módulos de billing/Asaas/webhooks, já revisados em
`docs/evidence/FM_SECURITY_REVIEW_BILLING_ASAAS_20260924.md` e
`docs/evidence/EVIDENCIA_ETAPA1_1.1_1.2_20260924.md` (o mesmo dia, revisões anteriores).

Conforme a skill: **não declaro "seguro"** — apenas o escopo revisado, as evidências, os
achados e as limitações desta análise.

## Metodologia

Leitura completa, arquivo por arquivo, de `api/deps.py`, `api/state.py`, `api/errors.py`,
`api/repositories.py`, `api/helpers.py`, `api/models.py`, `api/main.py`,
`api/routes_campaigns.py`, `api/routes_approvals.py`, `api/routes_connections.py`,
`api/routes_autonomy.py`, `api/routes_brand.py`, `api/routes_audit.py`, `api/routes_me.py`,
`campaia_core/permissions.py`, `campaia_core/errors.py`, `campaia_core/states.py`,
`campaia_core/connectors.py`, `campaia_core/autonomy.py`, `campaia_core/infra.py`,
`campaia_core/ai_gateway.py`, `campaia_core/ai_simulator.py`, `campaia_core/sanitizer.py`,
`campaia_core/saga.py` (parcial), `api/db.py` (exceto as classes de billing já revisadas).
Não abertos nesta passada (registrado como limitação, não como "limpo"): `simulator.py`,
`saga.py` (completo), `policy.py`, `budget.py`, `agents.py`, `optimizer.py`, `pacing.py`,
`outbox.py`, `reconciliation.py`.

## Achado corrigido nesta revisão — escopo de unidade de negócio não aplicado na camada HTTP

**Severidade:** real, mesmo-tenant apenas (nunca cross-tenant — ver seção de isolamento de
tenant abaixo, que permanece sólida). Não é `STOP DE PRODUÇÃO` (nenhum tenant real hoje
opera com mais de uma unidade de negócio simultaneamente), mas é um bloqueador antes de
onboarding de qualquer tenant multi-unidade.

**O achado:** `campaia_core/permissions.py::authorize()` já implementa corretamente o
escopo de unidade de negócio (passo 3, linha ~243-253: nega com `NOT_FOUND` se
`resource.business_unit_id` não estiver entre `principal.business_unit_ids`) — e é testado
no domínio (`tests/test_permissions.py::test_usuario_restrito_nao_acessa_outra_unidade`).
Porém, **todo** helper `_authorize`/`_authorize_*` na camada HTTP
(`routes_campaigns.py`, `routes_approvals.py`, `routes_connections.py`,
`routes_autonomy.py`, `routes_brand.py`, `routes_audit.py`) construía
`Resource(business_unit_id=fixture.business_unit_id)` — **a própria unidade do
chamador**, não a do recurso alvo — antes mesmo de saber qual recurso seria acessado. Isso
faz da comparação em `authorize()` uma tautologia: `resource.business_unit_id` é sempre
igual a um elemento de `principal.business_unit_ids`, porque veio da mesma origem. Nunca
nega.

**Impacto real:** dentro do mesmo tenant, qualquer usuário com a permissão certa (ex.
`CAMPAIGN_VIEW`/`CAMPAIGN_EDIT`) conseguia ver/editar/publicar/pausar/kill-switch campanhas
de **qualquer** unidade de negócio daquele tenant, não só a própria — mesmo
`CampaignRecord.business_unit_id` sendo um campo real, atribuível pelo cliente em
`POST /briefs`. A checagem de unidade nunca falhava porque nunca comparava contra o valor
certo. Invisível nos testes existentes porque cada fixture de `state.py::_seed_tokens()`
usa exatamente uma unidade por tenant — nenhum teste prévio exercitava duas unidades no
mesmo tenant.

**Correção aplicada** (`api/routes_campaigns.py`):
- `_get_campaign_or_404` passa a aceitar `principal` e comparar
  `record.business_unit_id` (o alvo real) contra `principal.business_unit_ids` — mesma
  semântica de `authorize()` (`NOT_FOUND`, nunca `PERMISSION_DENIED`, para não revelar que
  a campanha existe em outra unidade). Todos os 9 pontos de chamada (get/plan/regenerate/
  validate/publish/pause/patch_budget/kill-switch-CAMPAIGN/insights) foram atualizados para
  passar o `principal` já retornado por `_authorize`.
- `list_campaigns` filtra o resultado por `principal.business_unit_ids` antes de devolver.
- `create_brief` valida que `body.business_unit_id` (quando informado) pertence às unidades
  do próprio principal — antes, um cliente podia atribuir a campanha recém-criada a
  **qualquer** unidade do tenant, inclusive uma que nem o próprio criador alcança depois.

**Escopo deliberadamente não estendido:** `routes_approvals.py`, `routes_brand.py`,
`routes_connections.py`, `routes_autonomy.py`, `routes_audit.py` continuam com a mesma
tautologia — mas seus tipos de recurso (`ApprovalRequest`, `BrandProfile`, `Connection`,
`AuditEvent`) **não têm campo `business_unit_id` no schema atual**, então não há um valor
real do recurso-alvo para comparar; adicionar isso exigiria uma mudança de schema maior,
fora do escopo proporcional desta correção pontual. Registrado aqui como pendência explícita
para quando/se esses recursos ganharem escopo de unidade de negócio — não escondido.

**Testes que provam o achado antes da correção → agora provam a correção:**
`tests_api/test_invariants.py::TestBusinessUnitScopeEnforcedWithinSameTenant` (6 testes) —
semeia uma campanha em `bu-other` (outra unidade do mesmo `demo-tenant`, nunca atribuível
via HTTP por um principal restrito) diretamente no repositório e confirma que `OWNER`
(unidade `bu-1`) recebe `404` em GET/pause/kill-switch-CAMPAIGN e que ela some da listagem;
confirma que `POST /briefs` recusa `business_unit_id="bu-other"` com `422
VALIDATION_FAILED`; e confirma (teste de sanidade) que uma campanha na própria unidade do
chamador continua 100% acessível — a correção não virou um bloqueio geral.

## Áreas revisadas sem achado (verificadas por leitura completa do código + testes existentes)

| Área | Verificação | Achado |
|---|---|---|
| Isolamento de tenant | Todo `.get()`/`.list_for_tenant()` de todo repositório filtra por `tenant_id`; única exceção é o kill-switch `GLOBAL`, deliberado, documentado e auditado em CADA tenant afetado (não só o do chamador) | Nenhum |
| Autorização/RBAC (`authorize()`) | Ordem de checagem correta (tenant → RBAC → unidade → MFA → step-up → teto de valor); toda rota mutante passa por `_authorize`/equivalente; `Role.OWNER` é a única role "tudo", razoável | Nenhum (além do achado de unidade acima) |
| Validação de entrada / fail-closed | `ApiModel(extra="forbid")`; `AutonomySettings.__post_init__` recusa auto-promoção (I-11); `autonomy.evaluate()` tem allow-list fechada por nível, padrão é `requires_human=True`; `states.py` só permite transições no grafo `TRANSITIONS`, `_guard_active` exige confirmação de TODOS os canais (I-12); `AIGateway.execute` nunca "corrige" saída inválida | Nenhum |
| Secrets/PII | `SecretRef.__repr__/__str__` sempre redigido; `assert_no_credentials` varre payloads de IA recursivamente contra `SecretRef` e padrões de token antes de qualquer chamada a provedor; `Sanitizer` pseudonimiza CPF/CNPJ/cartão/email/telefone/CEP, `SanitizationReport.__repr__` nunca imprime o mapeamento reverso | Nenhum (gap de teste dedicado a `SecretRef.__repr__` registrado como limitação, não como achado) |
| Idempotência | Toda rota com efeito real exige e usa `Idempotency-Key` corretamente; `decide_approval` roda a checagem de idempotência ANTES de `can_approve()` de propósito (senão um replay do mesmo ator seria rejeitado como `SEPARATION_OF_DUTIES` em vez de devolver o resultado original) | 2 rotas (`create_approval`, `oauth_start`) mutam sem exigir chave — impacto baixo (pior caso: linha duplicada que um humano ignora/rejeita), registrado como pendência, não corrigido nesta rodada por não ter efeito externo real nem corrupção de dado |
| Aprovação dupla / segregação de funções / step-up | `can_approve()` bloqueia auto-aprovação (`principal.user_id == requester_id`) e segundo voto do mesmo ator; `dual_approval_complete()` exige 2 atores distintos; janela de step-up (10 min) é verificada contra relógio real, não só presença de header | Nenhum bypass de auto-aprovação ou de janela encontrado. Nota: a PROFUNDIDADE do "step-up" em si (qualquer valor não-vazio de header conta como reautenticação) é o mesmo risco de raiz do item 1.3 (autenticação de desenvolvimento), não um achado novo desta seção |
| Auditoria | `AuditLog.append()` é o único método que escreve; nenhuma rota registrada em `main.py` edita/apaga evento de auditoria | Nenhum (sugestão de hardening: `AuditEvent` não é `frozen=True`, não é explorado hoje) |
| Operações destrutivas (kill-switch) | Todos os escopos exceto `GLOBAL` são presos ao tenant do chamador (e agora `CAMPAIGN` também à unidade); `GLOBAL` só reduz efeito, nunca eleva; idempotente | Nenhum |
| SSRF / injeção / secrets hardcoded | Nenhum `eval`/`exec`/chamada de shell encontrado; `oauth_start` nunca faz chamada de rede real (URL fixa para domínio `.invalid`); nenhum segredo real hardcoded fora dos tokens de fixture de desenvolvimento (já tratados na seção de autenticação) | Nenhum |

## Achado registrado, não corrigido — autenticação de desenvolvimento (item 1.3, já do conhecimento do Diretor)

`api/deps.py::require_auth` resolve um Bearer token por igualdade exata de string contra um
dicionário fixo (`state.tokens`), semeado uma vez em `state.py::_seed_tokens()` — 6 tokens
hardcoded, sem expiração, sem rotação, sem revogação, sem assinatura/hash. `OWNER` tem
`frozenset(Permission)` — todas as permissões, incluindo `KILL_SWITCH` e `BILLING_MANAGE`.
`note_step_up_header` trata **qualquer** valor não-vazio do header `X-Step-Up-Token` como
reautenticação válida — não verifica nenhum segundo fator de fato.

**Isto não é "autenticação fraca a ser reforçada" — é, na prática, nenhuma fronteira real de
autenticação**, caso este código rode fora de um ambiente de desenvolvimento/demo confiável:
o conjunto completo de credenciais é estático, está no repositório, e nunca expira. Não é
classificado `STOP DE PRODUÇÃO` neste momento porque está deliberadamente fora de escopo —
é exatamente o item 1.3 do cronograma mestre, que o Diretor já decidiu tratar como decisão
dele (escolha de provedor de identidade real), não como bug a corrigir agora. Registrado
aqui, formalmente, como o bloqueador que de fato é para qualquer implantação real.

## Classificação final

Nenhum achado desta revisão, corrigido ou pendente, é `STOP DE PRODUÇÃO` **no estado atual**
(nenhum tenant real, nenhuma unidade de negócio múltipla em uso hoje, ambiente de
desenvolvimento). O achado de escopo de unidade de negócio foi corrigido nesta mesma sessão,
com teste de reprodução real. O achado de autenticação de desenvolvimento (item 1.3) e as
duas rotas sem idempotency-key seguem registrados e não corrigidos, com justificativa
explícita de por que não agora.

## Testes executados neste HEAD

- `python3 -m unittest discover -s tests` → **343 testes, OK**.
- `python3 -m unittest discover -s tests_api -t .` → **105 testes, OK** (99 anteriores + 6
  novos de `TestBusinessUnitScopeEnforcedWithinSameTenant`).

Nenhuma regressão nos testes pré-existentes.

## Limitações desta análise

- Não abertos nesta passada: `simulator.py`, `saga.py` (completo), `policy.py`, `budget.py`,
  `agents.py`, `optimizer.py`, `pacing.py`, `outbox.py`, `reconciliation.py` — registrados
  como não lidos, não como "limpos".
- Não executado o "teste arquitetural" que `ai_gateway.py` afirma existir (checagem de que
  ninguém importa `connectors`/`saga` naquele arquivo) — não localizado/confirmado nesta
  revisão.
- Nenhum teste dedicado a `repr(SecretRef(...))` foi encontrado (o comportamento foi
  confirmado por leitura direta da classe, não por um teste automatizado específico).
