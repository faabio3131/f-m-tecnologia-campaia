# ADR-0019 — Implantação TARGET sobre a infraestrutura já decidida

**Status:** PROPOSTA · **Data:** 19/09/2026 · **Aprovador proposto:** Fábio Aluizio da Silva

## Contexto

`D-08` (27/08/2026, citada em `docs/evidence/DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md` e reconciliada no painel v16/v17/v18/v19) já aprovou Google Cloud, região São Paulo, como infraestrutura do CampaIA — antes mesmo da governança Nova FM, mas consistente com o princípio cloud-first do Documento Mestre §6. Esta ADR não reabre essa escolha; formaliza como o frontend Web e o BFF existente se implantam sobre ela.

`PENDÊNCIA` desta ADR: o texto exato de `DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md` não foi relido palavra por palavra nesta missão (citado por referência do painel já lido em turno anterior desta sessão) — reconfirmar antes de qualquer contratação real.

## Restrições

- Não contratar nenhum serviço nesta missão.
- Não configurar nuvem nesta missão.
- Preservar a decisão D-08 já aprovada (não reabrir sem necessidade comprovada).
- Ambientes (dev/preview/staging/sandbox de providers/produção) devem usar a mesma linha arquitetural (Documento Mestre §42) — diferença só de configuração, credenciais, dados, capacidade.

## Opções analisadas

| Opção | Vantagem | Custo/Risco | Reversibilidade |
|---|---|---|---|
| **A — Frontend e BFF como containers/serviços gerenciados na mesma nuvem já decidida (Google Cloud, São Paulo) (recomendada)** | Unifica operação, observabilidade e rede privada entre frontend, BFF e Postgres já verificado; sem segundo fornecedor a gerenciar (consistente com D-08/ADR-0009) | Nenhum identificado além dos já assumidos pela decisão D-08 original | Média — trocar de nuvem depois é trabalho real, mas containers são portáveis |
| B — Frontend em um provedor de hospedagem de frontend dedicado + BFF na nuvem já decidida | Pode reduzir esforço operacional do frontend especificamente | Introduz um segundo fornecedor externo, contrariando a lógica de unificação que já motivou D-08/ADR-0009 (mesmo argumento já usado em `docs/09_ADR_0013...md` contra multiplicar fornecedores) | Média |

## Recomendação

**Opção A** — implantar o frontend Next.js/React (ADR-0017, se aprovada) como serviço containerizado na mesma nuvem já decidida, ao lado do BFF Starlette e do Postgres já verificado. Nenhuma decisão de serviço específico (ex.: qual produto de container da nuvem) é tomada aqui — fica para o Work Package de CI/CD.

## Decisão

Registrada como **PROPOSTA** — não aprovada.

## Consequências

Fica mais fácil: rede privada única entre frontend, BFF e banco; observabilidade centralizada. Fica mais difícil: nenhuma identificada além do esforço normal de qualquer primeira implantação.

## Riscos

| Risco | Mitigação |
|---|---|
| Reabrir D-08 sem necessidade | Esta ADR explicitamente preserva D-08; qualquer reversão exige nova ADR com justificativa técnica/econômica forte (Documento Mestre §21) |
| Ambientes divergirem estruturalmente (ex.: staging numa arquitetura diferente de produção) | Documento Mestre §42 já proíbe; reforçado aqui |

## Reversibilidade

Média.

## Gatilho de revisão

Se o Work Package de CI/CD encontrar custo ou limitação técnica real e comprovada na nuvem já decidida, revisar com dados concretos, não preferência.

## Pendências

Reconfirmação do texto exato de D-08; escolha do serviço de container específico (Work Package); aprovação humana explícita antes do Gate 6 (Sandbox) em diante.
