# CampaIA — Ponto Zero Web: Índice

**Missão:** Ponto Zero Web e System Design completo do CampaIA.
**Repositório canônico:** `faabio3131/f-m-tecnologia-campaia`, branch `architecture/campaia-ponto-zero-web`, a partir de `main`@`c121f7c`.
**Fase:** somente descoberta, documentação e planejamento. **Nenhuma implementação de frontend ou mudança arquitetural em código foi executada.**

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

ADRs propostas (raiz de `docs/`, seguindo a convenção de arquivo próprio já usada em `docs/09_ADR_0013_...md` e `docs/13_ADR_0015_...md`):

| ADR | Título | Status |
|---|---|---|
| `docs/14_ADR_0016_LEI_WEB_FIRST_VS_NATUREZA_MOBILE_CHARTER.md` | Precedência da Lei Web First sobre a declaração de natureza mobile do Charter | PROPOSTA |
| `docs/15_ADR_0017_FRAMEWORK_FRONTEND_WEB.md` | Framework de frontend Web | PROPOSTA |
| `docs/16_ADR_0018_AUTENTICACAO_SESSAO_WEB.md` | Autenticação e sessão Web | PROPOSTA |
| `docs/17_ADR_0019_IMPLANTACAO_TARGET.md` | Implantação TARGET sobre a infraestrutura já decidida (D-08) | PROPOSTA |

## O que este conjunto de documentos NÃO é

- Não é uma implementação. Nenhum código de frontend foi escrito.
- Não é uma aprovação. Todas as ADRs estão `PROPOSTA`; nenhuma foi marcada `APROVADA` por esta missão.
- Não é uma alteração do backend funcional, dos contratos vigentes ou dos documentos normativos da Nova FM.
- Não é uma reclassificação do mobile — `mobile/` permanece em quarentena, exatamente como formalizado em `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md`.

## Estado máximo permitido para esta missão

`SYSTEM DESIGN WEB PRODUZIDO — PENDENTE DE REVISÃO E APROVAÇÃO HUMANA`
