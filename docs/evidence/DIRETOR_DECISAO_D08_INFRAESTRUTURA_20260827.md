# FONTE PRIMÁRIA — DECISÃO D-08: NUVEM, REGIÃO E ORÇAMENTO DE INFRAESTRUTURA

**Capturado em:** 27 de agosto de 2026
**Capturado por:** Claude, a partir de texto literal recebido do Diretor no turno corrente, em resposta direta à pesquisa comparativa de infraestrutura em nuvem e à opinião técnica solicitada
**Diretor:** Fábio Aluizio da Silva

---

## SEQUÊNCIA DOS FATOS

1. Diretor solicitou pesquisa de custo-benefício de infraestrutura em nuvem, já que D-08 havia ficado em aberto por falta de critério ("não sei qual seria a melhor opção e de menor custo beneficio").
2. Claude executou pesquisa direta em fontes primárias oficiais (aws.amazon.com, cloud.google.com, azure.microsoft.com) comparando disponibilidade e custo de: banco PostgreSQL gerenciado, cache/fila Redis, fila de mensagens, motor de workflow durável, armazenamento de objetos e cofre de segredos — nas três nuvens, com foco na região Brasil de cada uma.
3. **Limitação transparente já disclosed ao Diretor antes da decisão:** as páginas oficiais de preço das três nuvens são renderizadas via JavaScript; a ferramenta de busca não conseguiu capturar os valores exatos da região Brasil especificamente. Confiança alta foi obtida sobre disponibilidade de serviço por região; confiança média/baixa sobre preço exato da região Brasil (usados valores de região EUA + estimativa de terceiros de ajuste regional de +10-30%, não confirmado oficialmente).
4. Resultado da pesquisa, apresentado ao Diretor: Google Cloud foi a única das três nuvens com confirmação oficial explícita de que todos os 6 serviços necessários existem na região São Paulo (`southamerica-east1`); AWS teve 5 de 6 confirmados na região São Paulo (`sa-east-1`); Azure teve 3 de 6 serviços em categoria "não garantida em toda região" e não confirmados na região Brasil Sul. Google Cloud foi também a única a declarar oficialmente ausência de sobretaxa regional para pelo menos dois dos serviços pesquisados. A documentação oficial da Azure sobre residência de dados no Brasil Sul apresentou contradição interna não resolvida (página principal afirma garantia de residência única-região; nota de rodapé no mesmo documento sugere que isso hoje só vale para Singapura).
5. Diretor perguntou explicitamente a opinião técnica de Claude como "engenheiro sênior": **"creio qu no momento a google seria uma boa opção? o que vc acha qual é a sua opinião como engenheiro Senior?"**
6. Claude respondeu com recomendação técnica fundamentada por Google Cloud/São Paulo, detalhando 4 razões (disponibilidade confirmada dos 6 serviços; ausência declarada de sobretaxa regional em 2 serviços; fraqueza da Azure em PostgreSQL gerenciado e residência de dados, relevante para a decisão de LGPD já fechada em D-09; maturidade do SDK Python da Google Cloud, compatível com a stack Python/FastAPI já em uso), e propôs fechar a direção estratégica (nuvem + região) deixando o valor exato de orçamento como pendência técnica separada, a ser resolvida com a calculadora oficial de preços.

## RESPOSTA LITERAL FINAL DO DIRETOR

> "pode seguir sua recomendação e depois faremos a pesquisa exata dos valores"

## INTERPRETAÇÃO LITERAL (sem extrapolação)

1. O Diretor aprova a recomendação técnica apresentada: **Google Cloud, região São Paulo (southamerica-east1)**, com os serviços gerenciados propostos (Cloud SQL para PostgreSQL, Memorystore para Redis, Pub/Sub, Cloud Workflows — ou Temporal auto-hospedado caso a saga de publicação multicanal exija semântica de execução durável mais avançada —, Cloud Storage, Secret Manager).
2. O Diretor explicitamente separa esta decisão de direção estratégica da confirmação final de valores exatos de orçamento — "depois faremos a pesquisa exata dos valores" confirma que o orçamento mensal preciso continua como item pendente, não decidido nesta rodada, consistente com a proposta apresentada por Claude.
3. Esta decisão **não** resolve: o valor de orçamento mensal exato (pendente de conferência na calculadora oficial de preços da Google Cloud); a escolha final entre Cloud Workflows e Temporal auto-hospedado para o motor de saga (ainda depende do desenho técnico da ADR-0004, saga/compensação); a confirmação de que a região São Paulo do Google Cloud, na prática de contrato, cumpre integralmente a expectativa de residência de dados assumida em D-09 (a pesquisa indicou alta confiança de disponibilidade de serviço, mas não constitui parecer jurídico sobre LGPD).
