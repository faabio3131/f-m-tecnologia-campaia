# CampaIA — Painel Vigente (26/09/2026)

**Este documento substitui, como retrato do estado real:** a seção "Onde estamos agora"
de `docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md` (datada de 24/09/2026, hoje parcialmente
desatualizada — ver correções abaixo) e qualquer "painel de execução" herdado da PR#6
(`origin/feat/campaia-v1-complete-saas`, ex.: "painel v31" no histórico daquela branch,
que descrevia um CURRENT diferente e nunca chegou a `main`). Este é o único painel vigente
a partir de 26/09/2026.

**Base:** branch `reconciliation/campaia-final-takeover`, HEAD `d47e33a` no momento em que
este documento foi escrito (mais commits de Fase 5 seguem abaixo dele). Todo item aqui é
`FATO CONFIRMADO` por execução real nesta sessão, nunca presumido — a mesma disciplina do
resto do projeto.

## Por que este painel existe

A missão de reconciliação/takeover (`docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md`,
documento completo com todo o raciocínio, evidência e commits de cada correção) comparou
`main`, PR#5 (`architecture/campaia-ponto-zero-web`) e PR#6
(`feat/campaia-v1-complete-saas`), reconciliou os achados tecnicamente válidos de ambos
sobre a arquitetura correta (PR#5 para Web, CURRENT para AUTH/SESSION/TENANCY), minerou a
PR#6 em busca de correções técnicas ainda pendentes (Fase 3), fechou lacunas internas onde
o domínio já suportava a funcionalidade (Fase 4), e este documento é a consolidação final
(Fase 5) desse trabalho. Nenhum merge, deploy ou alteração de produção ocorreu ou está
sendo proposto aqui — ver "Estado do PR de takeover" ao final.

## Estado real confirmado (26/09/2026)

| Área | Estado | Evidência |
|---|---|---|
| Suíte de testes do backend (`backend/`) | **553 passed, 58 subtests passed, 0 failures** | `PYTHONPATH=. python3 -m pytest -q`, execução real nesta sessão |
| Suíte de testes do Web (unit/component) | **67 passed em 20 arquivos, 0 failures** | `npm run test -- --run`, execução real nesta sessão |
| E2E cross-stack (Playwright, backend + Next.js build de produção reais) | **26 passed, 0 failures** | `npx playwright test --config=playwright.session.config.ts`, execução real nesta sessão |
| Dependências do backend (`pip-audit` contra o PyPI Advisory Database real) | **0 vulnerabilidades conhecidas** | Starlette `1.0.0 -> 1.3.1` fechou 5 CVEs reais (achado 22, Fase 3 item 4) |
| Contrato (`contracts/bff-openapi.yaml`) × geração TypeScript × fronteiras de segurança Web | **Sem drift, sem violação** | `npm run contracts:check`, `npm run boundary:check` (65 arquivos), execução real |
| Autenticação real (item 1.3 do cronograma de 24/09) | **CONCLUÍDA** — corrige o cronograma antigo, que ainda a listava como "integração não construída" | `campaia_core/identity_provider.py::FirebaseIdTokenVerifier` (SDK oficial `firebase_admin`, fail-closed por padrão — `AlwaysRejectIdTokenVerifier` até `FIREBASE_PROJECT_ID` ser configurado); sessão real server-side, CSRF, step-up — `api/routes_auth.py`, `api/session.py` |
| Endpoint de liveness (`GET /health`) | **NOVO nesta missão** (achado 23, Fase 3 item 5) — checagem real de banco quando persistência está configurada, nunca fabrica "saudável" | `backend/api/routes_health.py` |
| Paginação real de auditoria (`GET /audit-events`) | **NOVO nesta missão** (achado 21, Fase 3 item 3) — antes sempre devolvia `next_cursor: null` apesar do contrato prometer paginação | `backend/api/routes_audit.py` |
| Consumo de aprovações (approvals não podem ser reutilizadas) | **NOVO nesta missão** (achado 19, Fase 3 item 1) | `ApprovalRequest.status` ganhou `APPLIED` |
| Retomar campanha pausada (`POST /campaigns/{id}/resume`) | **NOVO nesta missão** (achado 25, Fase 4 item A) — domínio já suportava, só faltava exposição | `backend/api/routes_campaigns.py::resume_campaign` |
| Métricas/insights reais (Google Ads/Meta) | **Ainda não iniciado** (Fase 9 do cronograma antigo) — placeholder honesto, nunca fabricado | `GET /campaigns/{id}/insights` devolve `points: []` com nota explícita |
| Conectores reais (Google Ads, Meta, WhatsApp) | **Ainda não iniciado** (Fases 5–7 do cronograma antigo) — só `ProviderSimulator` | `campaia_core/simulator.py` |
| Infraestrutura de nuvem real (Cloud SQL, Secret Manager, Pub/Sub) | **Ainda não provisionada** — Diretor optou por não autorizar ainda em 24/09/2026 | `docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md`, item 1.6 |
| Conta Asaas de produção | **Ainda em Sandbox** — CNPJ da F&M não saiu | `docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md`, item 1.7 |
| Unidade de negócio (CRUD real) | **HUMAN_DECISION** (Fase 4 item B desta missão) — hoje só uma string livre sem entidade, sem API, sem UI de gestão | `RECONCILIACAO_TAKEOVER_FINAL_20260926.md`, Fase 4 item B |
| Cadastro de empresa/tenant (onboarding) | **HUMAN_DECISION** (Fase 4 item C) — já era decisão de produto explicitamente adiada desde o WP-02 | idem, Fase 4 item C |
| Brand Kit — upload real de logo | **EXTERNAL_INFRASTRUCTURE** (Fase 4 item D) — depende de Cloud Storage/GCP inexistente | idem, Fase 4 item D |
| Analytics real | **EXTERNAL_CREDENTIAL** (Fase 4 item E) — já honesto, sem ação necessária | idem, Fase 4 item E |
| App mobile (Flutter) | **Em quarentena arquitetural**, sem evolução nesta missão (fora do escopo desta reconciliação, que é Web/backend) | `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` |

## PR#5 e PR#6: confirmação de avaliação completa

Ambas as branches candidatas foram integralmente avaliadas nesta missão, não apenas
parcialmente:

- **Fase 1** (`RECONCILIACAO_TAKEOVER_FINAL_20260926.md`, seção "FASE 1") comparou
  `main` × PR#5 × PR#6 por área (AUTH/SESSION, TENANCY, WEB, CONTRACTS), com decisão
  explícita e justificada por área — nunca um "PR#5 vence tudo" ou "PR#6 vence tudo"
  genérico.
- **Fase 2** (WP-06 → WP-11, já concluída e aprovada pelo Diretor antes da autorização de
  Fase 3/4/5) reconstruiu sobre a arquitetura Web de PR#5 o comportamento de 6 telas que só
  existiam, corretamente, em PR#6 — nunca copiando o diretório `web/` da PR#6, sempre
  reconstruindo sobre `providers/`, `types/`, App Router e AuthProvider do CURRENT.
- **Fase 3** (6 itens, `RECONCILIACAO_TAKEOVER_FINAL_20260926.md`, seção "FASE 3")
  minerou tecnicamente a PR#6 em busca de correções e testes ainda válidos: consumo de
  aprovações, registro de capacidades, paginação de auditoria, dependências/segurança,
  observabilidade, e uma comparação arquivo-a-arquivo de todo o inventário de testes da
  PR#6 (`backend/tests_api/*.py`, `web/e2e/*.spec.ts`) contra o CURRENT — nenhum teste
  real de segurança ou negativo da PR#6 ficou sem avaliação; os únicos não portados foram
  os que testavam uma arquitetura de autenticação (OIDC) que a Fase 1 já havia classificado
  "A — Manter CURRENT", cuja cobertura equivalente (e mais extensa) já existe em
  `test_auth_session.py`/`session-protocol.spec.ts`.
- **Nenhum código tecnicamente válido foi abandonado sem avaliação**: cada item das Fases
  1 e 3 tem uma classificação explícita (portado, superado, ou por que não se aplica) —
  nunca um "descartado silenciosamente".

## O que ainda não foi resolvido (decisões do Diretor, não técnicas)

Itens que dependem de uma decisão ou insumo do Diretor, listados sem ambiguidade, sem
recomendação implícita de qual escolher:

1. Autorizar o provisionamento real de infraestrutura de nuvem (item 1.6 do cronograma
   antigo) — segue não autorizado desde 24/09/2026.
2. CNPJ da F&M, necessário para a conta Asaas de produção (item 1.7) e para WhatsApp
   Business (item 3.3).
3. As 4 pendências de produto já registradas na especificação de telas (item 2.4 do
   cronograma antigo): login real (já resolvido nesta missão — ver tabela acima),
   edição de Brand Kit, escopo de objetivos do briefing, superfície de UI da assinatura.
4. Decisão final sobre o app mobile (item 2.5) — sair da quarentena, descartar, ou
   retomar depois do Web.
5. As 5 perguntas de domínio sobre unidade de negócio (Fase 4, item B desta missão).
6. As 4 perguntas de domínio sobre cadastro de empresa/tenant (Fase 4, item C).
7. Autorização expressa e específica para produção (item 3.8 do cronograma antigo) —
   nunca presumida, e ainda mais distante hoje: nenhum conector real, nenhuma
   infraestrutura provisionada.

## Estado do PR de takeover

Nenhum merge, deploy, release ou alteração de produção ocorreu nesta missão, em nenhum
momento — a autorização do Diretor para as Fases 3/4/5 foi explícita neste sentido
("NUNCA MERGEAR"). O PR de takeover final está sendo preparado a partir da branch
`reconciliation/campaia-final-takeover`, com todos os commits desta missão (Fases 0 a 5)
como um histórico atômico e revisável, e será aberto contra `main` sem merge automático —
ver a seção final de `RECONCILIACAO_TAKEOVER_FINAL_20260926.md` para o protocolo exato de
push (uma única tentativa; se bloqueado, reportar `PUSH_BLOCKED` com todos os dados e
aguardar instrução, nunca contornar).
