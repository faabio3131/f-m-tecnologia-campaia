# ADR-0021 — Provedor de IA generativa para geração de estratégia de campanha

**Status:** APROVADA · **Data:** 24/09/2026 · **Aprovador:** Fábio Aluizio da Silva

## Contexto

`campaia_core/ai_gateway.py` e `campaia_core/agents.py` implementam o motor de agentes (ex.
o agente "strategist" que gera objetivo/funil/canais/justificativa a partir de um briefing),
mas o único provedor plugado hoje é `SimulatedAIProvider` — nenhum provedor real de IA
generativa foi integrado até esta data. `AIGateway.execute()` já valida saída contra
`assert_no_credentials` e `OutputSchema`, e o design é deliberadamente agnóstico de provedor
(troca de provider é configuração, não reescrita) — esta ADR decide QUAL provedor, não como
integrá-lo (a integração real do adapter permanece TARGET, fora do escopo desta decisão).

A decisão foi puramente de negócio/arquitetura, consultada ao vivo com o Diretor em
24/09/2026 (autoridade humana atual e explícita), motivada pela necessidade de estimar
custo de operação para embasar a precificação dos planos (item 1.5 do cronograma mestre,
`docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md`).

## Pesquisa que embasou a decisão

Pesquisa de mercado (24/09/2026, ver notas de pesquisa da sessão) confirmou preço oficial
vigente dos modelos de menor custo de cada provedor:

| Provedor | Modelo | Preço entrada (US$/1M tokens) | Preço saída (US$/1M tokens) |
|---|---|---|---|
| Google | Gemini 3.8 Flash | 0,75 | 3,75 |
| OpenAI | GPT-5.4 mini | — | 4,50 |
| Anthropic | Claude Haiku 4.5 | 1,00 | 5,00 |

**Nota:** a hipótese inicial do Diretor ("Gemini 3.7 Flash") estava desatualizada — a
documentação oficial do Google já recomenda a versão 3.8 Flash para novos projetos. Mesmo
padrão de nome de modelo desatualizado se repetiu com "GPT-5 mini" (versão atual é 5.4).

Custo por geração de estratégia, em qualquer um dos três, fica entre US$0,0007 e US$0,013
por chamada mesmo no cenário mais caro — **irrelevante para a decisão** frente à margem do
negócio (diferença de poucos dólares por mês mesmo em alto volume). A decisão foi tomada por
outros critérios, não por preço de token.

## Alternativas analisadas

| Opção | Vantagem | Custo/Risco |
|---|---|---|
| A — OpenAI GPT-5.4 mini | Ligeiramente mais barato na entrada | Adiciona um segundo processador de dados (LGPD) fora do perímetro já aprovado; sem vantagem de qualidade sobre a opção B nos benchmarks públicos disponíveis |
| **B — Google Gemini 3.8 Flash (escolhida)** | Mesmo provedor da infraestrutura já aprovada (ADR-0019, Google Cloud São Paulo) — mantém dados de campanha dentro do perímetro de residência já decidido para LGPD, um único fornecedor a menos para avaliar/faturar/gerir credencial; benchmarks públicos (04/2026) mostram Gemini 3.8 Flash à frente do GPT-5.4 mini em pontuação geral (78,41 vs 62,63) e em coding (68,1 vs 42,9), liderando também em tarefas de raciocínio/agentic, com janela de contexto maior (1M vs 400K tokens) e custo de saída menor (US$3,75 vs US$4,50/1M) | Nenhum identificado nesta análise — comparação de benchmark entre provedores não é totalmente maçã-com-maçã (conjuntos de teste diferentes), a confirmar com avaliação no schema real do CampaIA quando o adapter for construído |
| C — Anthropic Claude Haiku 4.5 | Mesma família do assistente que constrói o CampaIA (Claude Code) | Mais caro que as outras duas opções nos dois eixos (entrada e saída), sem ganho de qualidade que justifique isso para esta tarefa específica; mesmo problema de processador de dados adicional da opção A |

## Decisão

**Provedor de IA generativa: Google (Gemini 3.8 Flash, ou a versão "flash" de melhor
custo-benefício vigente na documentação oficial do Google no momento da integração — nomes
de modelo mudam com frequência, a versão exata deve ser reconfirmada contra
`ai.google.dev`/Vertex AI antes de codificar o adapter).**

Motivo decisivo: alinhamento com a decisão de infraestrutura já aprovada (ADR-0019, Google
Cloud São Paulo) — mantém o dado de campanha dentro do mesmo perímetro de residência já
resolvido para LGPD, reduz o número de processadores de dados terceiros a avaliar, e reduz
superfície operacional (um fornecedor de nuvem + IA em vez de dois). O fato de o Gemini 3.8
Flash também liderar os benchmarks públicos disponíveis e custar menos que a alternativa mais
próxima reforça a decisão, mas não é o motivo primário — o custo de token é irrelevante em
qualquer uma das três opções pesquisadas.

## Efeito sobre o roadmap

Nenhum código foi alterado por esta ADR. `SimulatedAIProvider` continua sendo o único
provider ativo até que o adapter real (`GeminiProvider` ou nome equivalente, mesmo padrão de
`AsaasGateway`/`payment_gateway.py`: contrato próprio, configurável, sem acoplar
`ai_gateway.py` ao provedor concreto) seja construído — trabalho ainda não iniciado, TARGET
para quando a integração de IA real entrar no cronograma (não coberto pela Etapa 1 do
cronograma mestre, que tratou apenas do dedupe/rate-limit/autenticação/security-review do
backend).
