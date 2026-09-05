# EVIDÊNCIA — PESQUISA DE VALORES EXATOS: GOOGLE CLOUD, REGIÃO SÃO PAULO

**Capturado em:** 27 de agosto de 2026
**Capturado por:** Claude, a partir de consulta direta às páginas oficiais de preço da Google Cloud (cloud.google.com), em atendimento à decisão D-08 (`docs/evidence/DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md`), que aprovou a direção estratégica (Google Cloud, região São Paulo) mas deixou o valor exato de orçamento como pendência (P-11).
**Diretor:** Fábio Aluizio da Silva
**Instrução literal do Diretor:** "vamos pesquisar valores do google" → resultado apresentado → "marque como pendente e vamos avançar" (referente ao único item não confirmado, Memorystore/Redis)

---

## MÉTODO E LIMITAÇÃO TÉCNICA HONESTA

A tentativa anterior (24-27/08) de obter preços exatos da região Brasil falhou porque as páginas oficiais de preço são renderizadas via JavaScript e a ferramenta de busca automática só captura o HTML estático. Nesta rodada, a extensão de navegador Chrome desta sessão não está conectada (`mcp__claude-in-chrome__tabs_context_mcp` retornou erro de extensão não conectada), então não foi possível abrir a calculadora interativa nem os seletores de região dependentes de JavaScript. Em vez disso, foi usada busca web direcionada (`WebFetch`) nas páginas de preço oficiais, o que teve sucesso para a maioria dos serviços — a Google aparentemente publica algumas tabelas de preço por região já embutidas no HTML (Cloud SQL), enquanto outras dependem inteiramente de um seletor JavaScript (Memorystore).

---

## RESULTADOS — CONFIRMADOS COM FONTE OFICIAL DIRETA

### Cloud SQL para PostgreSQL — região southamerica-east1 (São Paulo), CONFIRMADO com números exatos
Fonte: `cloud.google.com/sql/pricing`, tabela específica da região São Paulo extraída diretamente.

| Componente | Preço sob demanda |
|---|---|
| vCPU (Enterprise, General Purpose) | US$ 0,0413 / hora |
| Memória | US$ 0,007 / GB-hora |
| vCPU com Alta Disponibilidade (HA) | US$ 0,0826 / hora |
| Memória com HA | US$ 0,014 / GB-hora |
| Armazenamento SSD | US$ 0,000232877 / GB-hora (≈ US$ 0,17/GB/mês) |
| Armazenamento HDD | US$ 0,000123288 / GB-hora |
| Backups (usado) | US$ 0,000109589 / GB-hora |
| Endereço IPv4 ocioso | US$ 0,01 / hora |
| Egress mesma região | Grátis |
| Egress outras regiões (fora América do Norte) | US$ 0,12 / GB |

**Exemplo prático de referência (não é orçamento fechado):** uma instância pequena de 2 vCPU + 4GB de memória, sem Alta Disponibilidade, ficaria em torno de **US$ 80–85/mês** apenas de computação, mais armazenamento e backups à parte. Com Alta Disponibilidade (recomendado para produção real), dobra para computação.

### Pub/Sub (fila de mensagens) — CONFIRMADO preço único mundial, sem sobretaxa regional
Fonte: `cloud.google.com/pubsub/pricing`, citação direta: *"After that, the price is $40 per TiB in all Google Cloud regions."*
- Primeiros 10 GiB/mês grátis por conta de faturamento.
- Depois: **US$ 40/TiB**, mesmo valor em São Paulo e em qualquer outra região.

### Cloud Workflows (motor de orquestração) — CONFIRMADO preço único mundial
Fonte: `cloud.google.com/workflows/pricing`.
- Passos internos: 5.000/mês grátis, depois **US$ 0,01 por 1.000 passos**.
- Passos externos: 2.000/mês grátis, depois **US$ 0,025 por 1.000 passos**.
- Documentação confirma explicitamente ausência de variação de preço por região.

### Secret Manager (cofre de segredos) — CONFIRMADO preço único mundial (sem menção de variação regional)
Fonte: `cloud.google.com/secret-manager/pricing`.
- Versão de segredo ativa: **US$ 0,06/mês** (após os 6 primeiros meses, que são grátis); 6 versões ativas grátis por mês.
- Operações de acesso: 10.000/mês grátis, depois **US$ 0,03 por 10.000 operações**.

### Cloud Storage (armazenamento de objetos) — CONFIRMADO preço uniforme entre regiões, incluindo São Paulo listada explicitamente
Fonte: `cloud.google.com/storage/pricing`.
- Armazenamento Standard: **≈ US$ 0,02/GB/mês** (US$ 0,000027397/GB-hora), mesmo valor em todas as regiões listadas, incluindo "Sao Paulo (southamerica-east1)" citada nominalmente na mesma tabela que outras regiões.
- Egress geral para internet: US$ 0,12/GB (0–10 TiB/mês), decrescente em volume maior.

---

## RESULTADO — NÃO CONFIRMADO (PENDÊNCIA MANTIDA)

### Memorystore para Redis — preço específico de São Paulo NÃO OBTIDO
Fonte tentada: `cloud.google.com/memorystore/docs/redis/pricing`. A página usa um seletor de região dependente de JavaScript; múltiplas tentativas de extração retornaram apenas a tabela de referência da região Iowa (us-central1), não a de São Paulo.

**Valor de referência (região EUA, NÃO aplicável a São Paulo com certeza):**
- Nível Básico M1 (1-4 GiB): US$ 0,049/GB-hora (≈ US$ 36/mês para 1GB).
- Nível Standard/HA M1: US$ 0,064/GB-hora.

**Decisão do Diretor sobre este item:** "marque como pendente e vamos avançar" — não foi feita nenhuma suposição de valor para São Paulo. Este item permanece formalmente pendente até ser confirmado por acesso direto à calculadora oficial (exige navegador conectado) ou por outra fonte primária.

---

## ATUALIZAÇÃO DE PENDÊNCIA

**P-11 (antes: "valor exato de orçamento mensal do Google Cloud na região São Paulo") passa a ser restrita e específica:** 5 dos 6 serviços necessários (Cloud SQL, Pub/Sub, Cloud Workflows, Secret Manager, Cloud Storage) têm agora preço oficial confirmado, com Cloud SQL sendo o único a variar por região (número já obtido) e os outros 4 confirmados como preço único mundial. **Resta pendente apenas o preço de Memorystore (Redis) especificamente para a região São Paulo** — item isolado, não mais uma incerteza generalizada sobre toda a infraestrutura.
