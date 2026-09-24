# ADR-0022 — Provedor de identidade (OAuth/OIDC) para autenticação real

**Status:** APROVADA · **Data:** 24/09/2026 · **Aprovador:** Fábio Aluizio da Silva

## Contexto

A ADR-0018 (19/09/2026) já aprovou a estratégia de autenticação Web: provedor de identidade
OAuth/OIDC gerenciado, sessão server-side via cookie (`HttpOnly`/`Secure`/`SameSite`), CSRF
protegido, tenant ativo nunca por header não confiável. Essa ADR deliberadamente **não**
escolheu o vendor específico, deixando isso para "após pesquisa de custo, segurança e
portabilidade" (mesma disciplina já usada pela ADR-0013 para credenciais de plataforma).

Hoje (`api/deps.py`/`api/state.py`) a API ainda usa tokens fixos de desenvolvimento
(`_seed_tokens()`) — nunca uma credencial real, confirmado e documentado também na
`fm-security-review` de 24/09/2026 (`docs/evidence/FM_SECURITY_REVIEW_BACKEND_FULL_20260924.md`),
que classificou isso como equivalente a "nenhuma fronteira real de autenticação" caso chegue
a produção sem substituição — item 1.3 do cronograma mestre.

Este é exatamente o WP-02 (`docs/web/06_ROADMAP_WORK_PACKAGES.md`) que a ADR-0018 previu.

## Pesquisa que embasou a decisão

Pesquisa de mercado (24/09/2026, preços oficiais confirmados por documentação de cada
provedor) comparou três opções citadas como exemplo no cronograma mestre:

| Provedor | Grátis até | Custo acima do grátis | B2B/SSO |
|---|---|---|---|
| Auth0 | 25.000 usuários ativos/mês (B2C) | ~US$0,07/usuário (Essentials B2C, US$35→US$700 em 10 mil usuários) | Essentials B2B US$150/mês; Professional B2B US$800/mês já em baixo volume |
| **Google Identity Platform** | **50.000 usuários ativos/mês** (Tier 1: e-mail/telefone/social/anônimo) | US$0,0046–0,0055/usuário (Tier 1) | OIDC/SAML grátis até 50 usuários, depois US$0,015/usuário |
| Clerk | 50.000 usuários retidos/mês (métrica mais restrita que MAU) | US$25/mês (Pro, inclui os 50k) + US$0,02/usuário extra | Add-on separado: US$100/mês (SSO) + US$75/conexão |

Custo, na escala em que o CampaIA vai operar nos próximos meses (dezenas/centenas de
usuários), é irrelevante entre as três — todas ficam praticamente de graça. A diferença
aparece em escala: o Auth0 fica desproporcionalmente mais caro no B2B (US$150-800/mês mesmo
com poucos usuários), enquanto Google Identity Platform e Clerk continuam baratos bem além
do tamanho atual do negócio.

## Alternativas analisadas

| Opção | Vantagem | Custo/Risco |
|---|---|---|
| A — Auth0 | Telas de login prontas, SDKs maduros, forte suporte a multi-tenant "organizations" | Muito mais caro em qualquer volume real, especialmente B2B (que o CampaIA precisa, sendo multi-tenant); mais um fornecedor fora do perímetro Google já decidido |
| **B — Google Identity Platform (escolhida)** | Grátis até 50.000 usuários ativos/mês (Tier 1); mesmo provedor da infraestrutura já aprovada (ADR-0019, Google Cloud São Paulo) e do provedor de IA (ADR-0021) — mesmo perímetro de residência de dados para LGPD, um fornecedor a menos para avaliar/faturar; muito mais barato que as alternativas em qualquer escala real | Menos "pronto para uso" — não entrega tela de login pronta como Auth0/Clerk, exige construir a interface de autenticação no frontend Next.js (mitigado: ADR-0018 já decidiu sessão server-side, não client-side puro, então o ganho de um SDK client-side pronto do Clerk importa menos aqui); SSO (Tier 2/OIDC-SAML) grátis só até 50 usuários, depois cobra — não é o caso de uso do público-alvo hoje (PME/agência), mas registrar como limite conhecido caso surja demanda enterprise |
| C — Clerk | Componentes de UI prontos para React/Next.js (framework já escolhido na ADR-0017), boa produtividade inicial de implementação | B2B (organizations/SSO) é add-on pago à parte; mais um fornecedor fora do perímetro Google já decidido; métrica de cobrança (MRU) é diferente da praticada pelos outros, exige atenção redobrada ao ler a fatura |

## Decisão

**Provedor de identidade: Google Identity Platform, iniciando no plano gratuito (Tier 1: até
50.000 usuários ativos/mês).**

Motivo decisivo: mesmo raciocínio já usado na ADR-0021 (provedor de IA) — alinhamento com a
infraestrutura já aprovada (ADR-0019, Google Cloud São Paulo), reduzindo o número de
fornecedores/processadores de dados terceiros a avaliar para LGPD e mantendo um único
IAM/faturamento. Reforçado pelo fato de o custo inicial ser literalmente zero na escala em
que o CampaIA vai operar no curto prazo — decisivo por si só ("ajuda muito começar com custo
0", autorização explícita do Diretor, 24/09/2026).

Ressalva registrada, não ignorada: a interface de login/cadastro precisa ser construída pelo
time de frontend (WP-01/WP-02), diferente de um provedor com telas prontas — aceitável dado
que a ADR-0018 já previu sessão server-side, reduzindo a dependência de um SDK client-side
rico.

## Efeito sobre o roadmap

Nenhum código foi alterado por esta ADR. `api/deps.py` continua usando o token fixo de
desenvolvimento até a integração real ser construída — TARGET para o WP-02
(`docs/web/06_ROADMAP_WORK_PACKAGES.md`) e para o item 1.3 do cronograma mestre
(`docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md`), ainda não iniciado. Requer, quando essa
integração começar, um projeto Google Cloud com conta de faturamento vinculada (mesmo sem
custo dentro do limite gratuito) — depende, portanto, do mesmo provisionamento de
infraestrutura ainda não autorizado (item 1.6, ADR-0019).
