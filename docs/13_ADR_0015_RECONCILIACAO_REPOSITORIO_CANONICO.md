# ADR-0015 — Repositório canônico do CampaIA e estratégia de reconciliação

**Status:** APROVADA · **Data:** 19/09/2026 · **Aprovador:** Fábio Aluizio da Silva

## Contexto

Uma auditoria completa (19/09/2026, modo somente leitura) identificou que dois repositórios GitHub distintos —
`faabio3131/campaia` (nome canônico no GitHub: `CampaIA`) e `faabio3131/f-m-tecnologia-campaia` — contêm o
mesmo produto CampaIA, com um ancestral Git genuinamente comum (`21faaab`, `ab4173a` — mesmo SHA nos dois),
divergindo em paralelo a partir de 05/09/2026. Nenhum dos dois é superset do outro; dos 107 caminhos de
arquivo compartilhados, 106 eram byte-idênticos e apenas `backend/api/models.py` divergia em conteúdo.

O Diretor definiu a decisão canônica antes desta ADR ser redigida; esta ADR formaliza e registra essa decisão
já tomada, não a propõe pela primeira vez.

## Trabalho exclusivo identificado em cada repositório (auditoria de 19/09/2026)

**Exclusivo de `faabio3131/CampaIA` (fonte histórica):**
- `backend/campaia_core/fiscal_handoff.py` e `backend/tests/test_fiscal_handoff.py` — boundary fail-closed
  FISC V2-16.5, formalmente bloqueado por ausência de autoridade real de billing próprio (commits `bb2b84d`,
  `55f5b95`, `bdebbc3`, mergeados via PR#1).
- `docs/evidence/V2_16_5_FISCAL_INTEGRATION_BLOCKER_20260913.md`.

**Exclusivo de `faabio3131/f-m-tecnologia-campaia` (repositório canônico):**
- Governança institucional Nova FM (`CLAUDE.md`, `docs/nova-fm/`, `.claude/skills/`, `.claude/commands/`).
- `docs/product/` completo (Product Charter, Functional/Non-Functional Requirements, Out of Scope, Decisões
  do Diretor, Especificação de Telas).
- App mobile Flutter (`mobile/`) — fluxos de Onboarding e Nova Campanha.
- Fix de alias `daily_cap` em `backend/api/models.py` (Achado 18, commit `8eee393`), corrigindo um bug real
  de contrato ausente no outro repositório.
- Painel de execução v18 (mais recente que o v17, última versão comum aos dois).

## Opções analisadas

| Opção | Vantagem | Custo/Risco | Reversibilidade |
|---|---|---|---|
| A — `faabio3131/CampaIA` canônico | Preserva o nome histórico original do repositório GitHub | Perde governança Nova FM, documentação de produto, fix `daily_cap` e o único app cliente construído até hoje | Baixa sem reconciliação manual |
| **B — `faabio3131/f-m-tecnologia-campaia` canônico (escolhida)** | Já opera sob a governança institucional vigente; tem a linha de commits mais recente e mais densa em evidência; custo de reconciliação baixo (1 arquivo de código divergente) | Exige importar o bloco fiscal (`FISC V2-16.5`) do repositório histórico antes de se tornar completo | Alta — reconciliação unidirecional, sem perda, com histórico Git preservado por cherry-pick |
| C — Repositório terceiro novo | "Começar limpo" | Descarta histórico Git de ambos; maior custo; contraria Documento Mestre §61 ("Evolução sem reconstrução") | Baixa |

## Decisão

**`faabio3131/f-m-tecnologia-campaia` é o repositório canônico** do produto CampaIA a partir de 19/09/2026.

**`faabio3131/campaia` (`CampaIA`) passa a ser fonte histórica temporária, estritamente somente leitura.**
Nenhuma alteração, commit, push, merge, branch, PR ou configuração deve ser feita nele a partir desta data.

## Razão

O custo de reconciliação é baixo (apenas um arquivo de código realmente divergia em conteúdo entre os dois
repositórios) frente ao valor descartado em qualquer outra opção. O repositório canônico escolhido já está
sob a constituição operacional Nova FM (`CLAUDE.md`) — condição que `faabio3131/CampaIA` não satisfaz — e
concentra o maior volume de trabalho de produto (documentação, mobile, correção de bug de contrato) sem
perder o trabalho fiscal do outro repositório, que é importado por esta mesma reconciliação.

## Estratégia de consolidação

**Unidirecional**: todo o trabalho exclusivo de `faabio3131/CampaIA` com valor comprovado é importado para
`faabio3131/f-m-tecnologia-campaia` via cherry-pick (preservando autoria e histórico original). Nenhum
trabalho flui na direção oposta. A branch de reconciliação é `reconciliation/campaia-ponto-zero-web`, aberta
como PR em modo `DRAFT` contra `main`, sem merge automático.

## Proibições explícitas desta decisão

- **Proibido desenvolvimento paralelo.** Nenhum trabalho novo deve ser iniciado em `faabio3131/CampaIA` a
  partir desta data. Toda evolução futura do CampaIA ocorre exclusivamente em
  `faabio3131/f-m-tecnologia-campaia`.
- **Proibida exclusão ou arquivamento de `faabio3131/CampaIA` antes da certificação completa** da
  reconciliação (matriz de validação executada e aprovada no repositório canônico, com o bloco fiscal e o
  fix `daily_cap` confirmados coerentes).

## Critérios para futura desativação do repositório não canônico

`faabio3131/CampaIA` só deve ser renomeado (para algo como `campaia-deprecated`) e arquivado — nunca
excluído — quando, cumulativamente:
1. A branch `reconciliation/campaia-ponto-zero-web` estiver mergeada em `main` do repositório canônico;
2. A matriz de validação completa tiver sido executada e aprovada no HEAD final do repositório canônico;
3. O Diretor confirmar explicitamente que nenhum trabalho adicional em `faabio3131/CampaIA` ficou de fora
   desta reconciliação.

## Itens derivados ainda em aberto (não resolvidos por esta ADR)

- Destino final do app mobile (`mobile/`) — permanece em quarentena arquitetural (ver
  `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md`), decisão adiada para depois do System Design
  Web.
- System Design e Ponto Zero Web da aplicação Web real — ainda não produzidos, fora do escopo desta ADR.
- Renomeação/arquivamento formal de `faabio3131/CampaIA` — condicionado aos critérios acima, não executado
  nesta reconciliação.

## Consequências

Fica mais fácil: existe, a partir de agora, uma única fonte de verdade ativa para o CampaIA, sob governança
institucional. Fica mais difícil: nenhuma — o custo de reconciliação já foi absorvido nesta mesma mudança,
sem trabalho remanescente de sincronização bidirecional.

## Riscos

| Risco | Mitigação |
|---|---|
| Alguém continuar commitando em `faabio3131/CampaIA` por hábito | Esta ADR e o achado da auditoria tornam explícita a proibição; repositório deve ser tratado como somente leitura a partir de 19/09/2026 |
| Perda de contexto sobre por que dois repositórios existiram | Auditoria completa de 19/09/2026 preservada como evidência; esta ADR referencia os commits exatos migrados |
| Reconexão indevida do fiscal handoff a billing sintético durante a importação | Importação por cherry-pick preserva o código exatamente como certificado (fail-closed, desconectado de campanha/orçamento), sem nenhuma modificação de escopo |

## Reversibilidade

Alta. O histórico de `faabio3131/CampaIA` permanece intacto e acessível (fonte histórica, não apagada); a
reconciliação foi feita por cherry-pick (não por reescrita), preservando a rastreabilidade de cada commit
original.

## Gatilho de revisão

Necessidade real de reverter a decisão canônica só surgiria se `faabio3131/f-m-tecnologia-campaia` se
mostrar tecnicamente inviável como base (não há evidência disso nesta data) — cenário não previsto e não
esperado.

---

**Evidências utilizadas nesta decisão:** auditoria completa "AUDITORIA CAMPAIA — CURRENT, RECONCILIAÇÃO E
DEFINIÇÃO DO PONTO ZERO WEB" (19/09/2026, mesma sessão); commits `bb2b84d6113522939d0d95667071bae9814269e4`,
`55f5b95861d6029e87c866115a4ebcfb47ceeaa5`, `bdebbc3558ff8b07c1a38e0cb728be0dc3635c4b` (origem:
`faabio3131/campaia`, PR#1); `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md`.
