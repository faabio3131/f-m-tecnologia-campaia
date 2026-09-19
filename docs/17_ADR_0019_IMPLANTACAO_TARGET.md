# ADR-0019 — Implantação TARGET sobre a infraestrutura já decidida

**Status:** PROPOSTA · **Data:** 19/09/2026 · **Aprovador proposto:** Fábio Aluizio da Silva

## Contexto

`D-08` (27/08/2026) já aprovou Google Cloud, **região São Paulo (`southamerica-east1`)**, como infraestrutura do CampaIA — antes mesmo da governança Nova FM, mas consistente com o princípio cloud-first do Documento Mestre §6. Esta ADR não reabre essa escolha; formaliza como o frontend Web e o BFF existente se implantam sobre ela.

`FATO CONFIRMADO` — `docs/evidence/DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md` foi lido integralmente nesta correção. Resumo fiel da fonte primária:

- Pesquisa comparativa direta (AWS, Google Cloud, Azure) cobrindo PostgreSQL gerenciado, Redis/cache-fila, fila de mensagens, motor de workflow durável, armazenamento de objetos e cofre de segredos, com foco na região Brasil de cada nuvem.
- **Google Cloud** foi a única com confirmação oficial explícita de que os 6 serviços necessários existem em `southamerica-east1`, e a única a declarar oficialmente ausência de sobretaxa regional em ao menos 2 dos serviços pesquisados.
- **AWS**: 5 de 6 serviços confirmados em `sa-east-1`. **Azure**: 3 de 6 em categoria "não garantida em toda região", não confirmados no Brasil; documentação oficial da Azure sobre residência de dados no Brasil Sul apresentou **contradição interna não resolvida** (página principal afirma garantia de residência única-região; nota de rodapé sugere que isso hoje só vale para Singapura).
- Recomendação técnica apresentada ao Diretor (Google Cloud/São Paulo) fundamentada em 4 razões: disponibilidade confirmada dos 6 serviços; ausência declarada de sobretaxa regional em 2 deles; fraqueza da Azure em Postgres gerenciado e em residência de dados (relevante para D-09/LGPD); maturidade do SDK Python da nuvem.
- **Resposta literal do Diretor**: *"pode seguir sua recomendação e depois faremos a pesquisa exata dos valores"*.
- Serviços gerenciados propostos e aprovados nessa direção estratégica: Cloud SQL (PostgreSQL), Memorystore (Redis), Pub/Sub, **Cloud Workflows** (a escolha entre Cloud Workflows e Temporal auto-hospedado já foi resolvida separadamente pela **ADR-0010**, citada no painel de execução como aprovada — não é mais uma pendência de D-08), Cloud Storage, Secret Manager.
- **O que D-08 explicitamente NÃO resolveu**, na própria interpretação literal registrada na fonte: (1) o valor de orçamento mensal exato, pendente de conferência na calculadora oficial de preços; (2) confirmação de que a região São Paulo, na prática de contrato, cumpre integralmente a expectativa de residência de dados assumida em D-09 — a fonte é explícita: **"a pesquisa indicou alta confiança de disponibilidade de serviço, mas não constitui parecer jurídico sobre LGPD"**.

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

`DECISÃO JÁ APROVADA` (D-08, não reaberta por esta ADR): Google Cloud, região `southamerica-east1`, direção estratégica dos serviços gerenciados listados no Contexto.

`PENDÊNCIAS QUE CONTINUAM REAIS` (herdadas de D-08, não resolvidas por esta ADR nem por nenhuma outra encontrada):
- Orçamento mensal exato (pendente da calculadora oficial de preços — nunca executada, segundo a própria fonte).
- Confirmação contratual/jurídica de que a região São Paulo cumpre a expectativa de residência de dados de D-09/LGPD — a fonte primária é explícita que isso não foi obtido, apenas alta confiança de disponibilidade de serviço.
- Escolha do serviço de container específico (Work Package de CI/CD).
- Dimensionamento e testes reais de capacidade — nenhuma carga real foi testada até esta data (consistente com `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md` §1.2, que já classifica os marcos de capacidade como hipótese de negócio, não validação técnica).

Cloud Workflows vs. Temporal **não é mais pendência de D-08** — resolvida pela ADR-0010 (Cloud Workflows, aprovada), conforme registrado no painel de execução.

Aprovação humana explícita desta ADR (implantação TARGET sobre a base já decidida) antes do Gate 6 (Sandbox) em diante.
