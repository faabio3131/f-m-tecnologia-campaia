# CampaIA — Ponto Zero Web: Índice

**Missão:** Ponto Zero Web e System Design completo do CampaIA.
**Repositório canônico:** `faabio3131/f-m-tecnologia-campaia`, branch `architecture/campaia-ponto-zero-web`, a partir de `main`@`c121f7c`.
**Fase:** descoberta, documentação, planejamento **e decisão arquitetural aprovada (19/09/2026)**. Nenhuma implementação de frontend ou mudança arquitetural em código foi executada **nesta missão** (documentos 00–07) — a implementação do WP-01 foi executada em uma missão posterior e separada, ver `08_CERTIFICACAO_WP01_FUNDACAO_WEB.md`.

## Documentos

| # | Documento | Conteúdo |
|---|---|---|
| 01 | `01_CURRENT_E_MATRIZ_CURRENT_TARGET.md` | Inventário do repositório, estado comprovado por capacidade, avaliação do backend existente, produto, matriz CURRENT × TARGET |
| 02 | `02_PONTO_ZERO_WEB_E_REQUISITOS.md` | Definição do Ponto Zero Web, requisitos funcionais e não funcionais, hipóteses de capacidade |
| 03 | `03_ARQUITETURA_WEB_DOMINIO_E_DADOS.md` | Bounded contexts, diagramas Mermaid, estrutura Web, fluxos críticos, estados/workflows, modelo de dados, autenticação/autorização/tenancy |
| 04 | `04_IA_INTEGRACOES_SEGURANCA_RESILIENCIA.md` | IA/agentes, integrações externas, matriz de autonomia/orçamento/aprovação, threat model, resiliência, observabilidade |
| 05 | `05_TESTES_CICD_MIGRACAO.md` | Baseline de testes, pirâmide de testes TARGET, gates, CI/CD/implantação TARGET, estratégia de migração e preservação |
| 06 | `06_ROADMAP_WORK_PACKAGES.md` | Roadmap reconciliado, 5 primeiros Work Packages prontos para execução futura |
| 07 | `07_CERTIFICACAO_PONTO_ZERO_WEB.md` | Matriz de validação real, pendências, riscos, certificação do estado alcançado |
| 08 | `08_CERTIFICACAO_WP01_FUNDACAO_WEB.md` | Certificação da execução real do WP-01 (fundação do frontend Web), missão separada e posterior a esta ("PROMPT MESTRE — CAMPAIA WEB FIRST / EXECUÇÃO REAL E COMPLETA DO WP-01", 19/09/2026) |
| 09 | `09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md` | Certificação da execução real do WP-02 (autenticação e sessão Web real), missão separada e posterior ("PROMPT MESTRE — CAMPAIA SaaS V1 COMPLETO", 20/09/2026) — implementado e autotestado, revisão de segurança humana (FM Security Engineer) pendente |
| 10 | `10_CERTIFICACAO_WP03_TENANCY_SHELL.md` | Certificação da execução real do WP-03 (contexto de tenant/unidade e shell do dashboard), mesma missão continuada (21/09/2026) — implementado e autotestado, incluindo correção de um gap real de CORS/redirect cross-origin descoberto por E2E cross-stack; revisão de segurança humana (FM Security Engineer) pendente |
| 11 | `11_CERTIFICACAO_WP04_ONBOARDING_BRAND_KIT.md` | Certificação da execução real do WP-04 (onboarding e Brand Kit), mesma missão continuada (21/09/2026) — implementado e autotestado, incluindo o fechamento de um gap real (POST /connections/oauth/start nunca criava uma Connection); revisão de FM QA Engineer pendente |
| 12 | `12_CERTIFICACAO_WP05_BRIEFING_APROVACAO.md` | Certificação da execução real do WP-05 (briefing, estratégia, validação e aprovação — fecha o Gate 5), mesma missão continuada (21/09/2026) — implementado e autotestado, incluindo 3 achados reais corrigidos (campo ausente no contrato, CSRF ausente numa mutação, shape do output do agente estrategista); revisão de FM QA Engineer pendente |

ADRs (raiz de `docs/`, seguindo a convenção de arquivo próprio já usada em `docs/09_ADR_0013_...md` e `docs/13_ADR_0015_...md`) — **APROVADAS em 19/09/2026** pelo Diretor Fábio Aluizio da Silva:

| ADR | Título | Status |
|---|---|---|
| `docs/14_ADR_0016_LEI_WEB_FIRST_VS_NATUREZA_MOBILE_CHARTER.md` | Precedência da Lei Web First sobre a declaração de natureza mobile do Charter | **APROVADA** |
| `docs/15_ADR_0017_FRAMEWORK_FRONTEND_WEB.md` | Framework de frontend Web | **APROVADA** |
| `docs/16_ADR_0018_AUTENTICACAO_SESSAO_WEB.md` | Autenticação e sessão Web | **APROVADA** |
| `docs/17_ADR_0019_IMPLANTACAO_TARGET.md` | Implantação TARGET sobre a infraestrutura já decidida (D-08) | **APROVADA** |

## O que este conjunto de documentos NÃO é

- Não é, por si só, uma implementação: os documentos 00–07 são exclusivamente System Design e decisão arquitetural. A implementação do WP-01 (19/09/2026), do WP-02 (20/09/2026, revisão de segurança humana pendente), do WP-03 (21/09/2026, mesma revisão pendente), do WP-04 (21/09/2026, revisão de FM QA Engineer pendente) e do WP-05 (21/09/2026, mesma revisão de FM QA Engineer pendente) foi executada em missões separadas e posteriores, certificadas em `08_CERTIFICACAO_WP01_FUNDACAO_WEB.md`, `09_CERTIFICACAO_WP02_AUTENTICACAO_SESSAO_WEB.md`, `10_CERTIFICACAO_WP03_TENANCY_SHELL.md`, `11_CERTIFICACAO_WP04_ONBOARDING_BRAND_KIT.md` e `12_CERTIFICACAO_WP05_BRIEFING_APROVACAO.md` — WP-06 em diante permanecem **não iniciados**.
- Não é uma alteração do backend funcional, dos contratos vigentes ou dos documentos normativos da Nova FM.
- Não é uma reclassificação do mobile — `mobile/` permanece em quarentena, exatamente como formalizado em `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md`.
- Não é homologação nem produção — as ADRs aprovadas autorizam a arquitetura Web, não sua implementação, integração ou operação.

## Estado máximo permitido para esta missão (System Design, documentos 00–07)

`SYSTEM DESIGN WEB APROVADO, DOCUMENTAÇÃO RECONCILIADA E MERGE CERTIFICADO — WP-01 AINDA NÃO INICIADO`

Este veredito descreve o estado no encerramento da missão de System Design
(PR #4, mergeada). Ele **não é reaberto nem reescrito** pela execução
posterior do WP-01 — o estado da execução do WP-01 é reportado em
`08_CERTIFICACAO_WP01_FUNDACAO_WEB.md` e no relatório da sua própria
missão, com seu próprio veredito.
