# CAMPAIA — ADRs

Estados: `PROPOSTA` | `APROVADA` | `SUBSTITUÍDA` | `REJEITADA`

Nenhuma ADR é marcada `APROVADA` sem decisão explícita do Diretor.

---

## ADR-0001 — Nome e identidade do produto: CAMPAIA

**Status:** **APROVADA** · **Data:** 25/08/2026 · **Aprovador:** Fábio Aluizio da Silva
**Base:** definição explícita do Diretor em 25/08/2026

**Contexto.** O produto vinha sendo tratado como "Kordena Marketing AI". A Ordem Mestra proíbe usar a marca
Kordena.

**Decisão.** Adotar `CAMPAIA` como nome canônico do produto, do repositório, dos namespaces técnicos
(`campaia.*`), da documentação e da identidade do aplicativo.

**Consequências.** Fica mais fácil comercializar de forma independente e evitar confusão de marca. Fica mais
difícil aproveitar reconhecimento existente do Kordena. Toda a documentação herdada precisa ser revisada.

**Riscos e mitigação.** Colisão de marca, domínio ou nome nas lojas. Mitigação: busca de anterioridade no
INPI e verificação de domínio/lojas **antes** de investir em identidade visual, submissão às lojas ou
material comercial.

**Reversibilidade.** Alta agora; baixa após registro de marca, publicação nas lojas e aquisição de usuários.

**Estado da verificação:** `NÃO VERIFICADO` — nenhuma busca de marca, domínio ou loja foi realizada (P-04).

---

## ADR-0002 — Independência em relação ao Kordena

**Status:** **APROVADA** · **Data:** 25/08/2026 · **Aprovador:** Fábio Aluizio da Silva
**Decisão do Diretor (D-02):** "Independente, integração futura" → **opção C**

**Contexto.** Divergência DIV-01: a Arquitetura V1.1 (§1 e §14) definia o produto como bounded context
conectado ao Core do Kordena; a Ordem Mestra (§2) e a skill exigem independência.

**Opções.**

| Opção | Vantagem | Custo | Risco | Reversibilidade |
|---|---|---|---|---|
| A — Módulo acoplado ao Core | Reaproveita identidade, tenants e contexto; time-to-market menor | Acoplamento de release, banco e autenticação | Impede venda autônoma | Baixa |
| B — Produto independente | Venda autônoma; domínio limpo; ciclo próprio | Reimplementar identidade, tenancy, auditoria | Duplicação inicial | Alta |
| **C — Independente hoje, integração opcional futura (escolhida)** | Mantém B e preserva a opção de integrar | Exige disciplina de contrato | Baixo | Alta |

**Decisão tomada.** Opção **C**: CAMPAIA nasce independente; o Kordena — ou qualquer outro sistema — poderá,
no futuro, tornar-se **consumidor externo** da API pública, mediante decisão expressa.

**Regras da porta de integração (vinculantes).**

1. Integração apenas por API pública versionada e webhooks. Nunca por banco, schema ou biblioteca compartilhada.
2. CAMPAIA não conhece entidades do Kordena; um consumidor externo é um `api_client` de um `tenant`.
3. Nenhum requisito do Kordena entra no roadmap da CAMPAIA sem ADR própria.
4. Teste arquitetural que quebra o build se qualquer módulo referenciar artefato do Kordena.

**Consequências.** CAMPAIA precisa de identidade, tenancy, auditoria, cofre e infraestrutura próprios
(Fase 2 cresce). Em troca, nenhuma decisão do Kordena bloqueia a CAMPAIA.

**Ação executada.** Emitida a Arquitetura Mestra V2. A V1.1 passa a `SUBSTITUÍDA`.

---

## ADR-0003 — Monólito modular com workers e workflow durável

**Status:** PROPOSTA · **Data:** 25/08/2026

**Contexto.** Volume esperado baixo (hipótese: 50–500 tenants no primeiro ano); a complexidade real está em
governança, integrações e consistência com plataformas externas — não em escala.

**Decisão.** Iniciar como monólito modular (fronteiras de módulo = bounded contexts) + workers assíncronos +
workflow durável para processos longos. Extrair serviço independente somente com justificativa comprovada de
escala, segurança, isolamento de falha, desempenho, risco ou operação independente.

**Consequências.** Ganha-se velocidade, transação local e depuração simples. Perde-se isolamento de falha
entre módulos; exige disciplina de fronteira (import cruzado entre contextos é proibido).

**Gatilho de revisão.** Um módulo que exija escala, janela de deploy ou perfil de segurança próprios.

---

## ADR-0004 — Saga para publicação multicanal; CQRS seletivo; Event Sourcing não adotado

**Status:** PROPOSTA · **Data:** 25/08/2026

**Decisão.**
- **Saga** obrigatória na publicação multicanal e em processos longos com efeito externo, com compensação
  explícita e decisão de política para falha parcial. Recursos externos nunca são apagados silenciosamente.
- **CQRS seletivo:** comandos críticos passam pelo Orchestrator e pela trilha auditável; dashboards leem
  projeções otimizadas.
- **Event Sourcing integral:** **não adotado** no MVP. A auditoria exigida é atendida por trilha append-only
  + versionamento de campanha, a um custo muito menor.

**Consequências.** Falha parcial vira decisão explícita e auditável em vez de estado ambíguo. Em troca,
publicação multicanal fica mais complexa de implementar e testar.

**Implementação.** `backend/campaia_core/saga.py`, com as três políticas de compensação testadas. Confirmado
em 27/08/2026 (ver ADR-0010) que a implementação real é uma execução síncrona de curta duração, sem esperas
longas aguardando evento externo no meio da saga.

---

## ADR-0005 — AI Model Gateway com contrato canônico e sem autoridade de execução

**Status:** PROPOSTA · **Data:** 25/08/2026

**Decisão.** Todo provedor de IA (OpenAI, Gemini, futuros) implementa o mesmo contrato canônico. O gateway
concentra seleção por tarefa/custo/qualidade, timeout, retry, circuit breaker, teto de custo, saída
estruturada validada por schema, versionamento de prompt, proveniência e sanitização de dados sensíveis.
Nenhuma tela ou regra de negócio referencia um fornecedor específico.

**Invariantes.** A IA **não** possui credenciais de anúncios, não executa ação externa, não altera política,
orçamento ou o próprio nível de autonomia. Fallback silencioso que altere comportamento crítico é proibido:
toda troca de modelo é registrada com motivo.

**Consequências.** Troca de fornecedor vira configuração. Em troca, o contrato canônico é o menor denominador
comum — capacidades exclusivas de um provedor exigem extensão explícita e versionada.

---

## ADR-0006 — Segredos e credenciais exclusivamente no backend

**Status:** PROPOSTA · **Data:** 25/08/2026

**Decisão.** Tokens OAuth de Google/Meta/WhatsApp e chaves de OpenAI/Gemini vivem apenas em cofre gerenciado,
com criptografia em repouso, rotação e escopo mínimo. O app mobile nunca recebe, armazena ou intermedia
segredo. Logs são sanitizados; prompts jamais contêm token.

**Consequências.** O app depende sempre do backend, inclusive para operações que "pareceriam" locais. Em
troca, o comprometimento de um dispositivo não compromete contas de anúncios nem verba.

**Implementação parcial.** `SecretRef` em `campaia_core/connectors.py`: a redação vive no tipo, não na
disciplina de quem escreve o log. Testado.

---

## ADR-0007 — Sequência de canais: Google → Meta → conjunto → WhatsApp

**Status:** **APROVADA** · **Data:** 25/08/2026 · **Aprovador:** Fábio Aluizio da Silva

**Contexto.** Decisão D-04, confirmada explicitamente pelo Diretor: 1) Google Ads, 2) Meta (Facebook +
Instagram), 3) operação conjunta dos dois, 4) WhatsApp. Coerente com as Fases 5, 6 e 7 da Ordem Mestra.

**Decisão.** Integrar um canal por vez, na ordem acima, cada um até o Gate de Integração com sandbox antes de
iniciar o seguinte. A Saga multicanal e a alocação de verba entre plataformas são **desenhadas** desde a
etapa 1, mas só exercitadas de fato na etapa 3.

**Consequências.** Aprendizado real antes de dobrar a superfície de integração; processos externos podem
correr em paralelo. Em troca, o produto fica monocanal por mais tempo.

**Restrição técnica registrada.** Click-to-WhatsApp é criado pelo fluxo de anúncios da Meta. A etapa 4 depende
da etapa 2 concluída — WhatsApp não é um canal isolável.

**Gatilho de revisão.** Bloqueio prolongado na aprovação de um canal; nesse caso, avaliar inversão de ordem
em vezg.de esperar parado.

---

## ADR-0010 — Motor de workflow durável: Cloud Workflows

**Status:** **APROVADA** · **Data:** 27/08/2026 · **Aprovador:** Fábio Aluizio da Silva
**Depende de:** D-08 (APROVADA, 27/08/2026 — Google Cloud, região São Paulo)
**Fonte da aprovação:** `docs/evidence/DIRETOR_DECISAO_ADR0010_WORKFLOW_20260827.md`, SHA-256 `7180dd1a5a0ea2685430af3cd3ac13796be8f7c8be3c3f05774cf479f401018d`

**Contexto.** Com D-08 aprovada (Google Cloud, região São Paulo), restava escolher o motor de orquestração
para a Saga de publicação multicanal (ADR-0004): Cloud Workflows (nativo do Google Cloud) ou Temporal
auto-hospedado.

**Decisão.** **Cloud Workflows** é o motor de orquestração da Saga de publicação multicanal do CAMPAIA.

**Razão.** Análise direta do código-fonte real já implementado e testado (`backend/campaia_core/saga.py`,
`backend/tests/test_saga.py`) mostrou que a `PublicationSaga` é uma execução síncrona de curta duração —
itera canais, publica em cada um, aplica política de compensação em caso de falha parcial, e retorna o
resultado dentro da mesma chamada. A aprovação humana é exigida antes da saga iniciar, não durante. Não há,
no desenho real, nenhuma espera de longa duração (horas/dias) no meio da execução. Esse perfil é exatamente
o caso de uso que Cloud Workflows resolve nativamente, sem exigir infraestrutura própria. Temporal
auto-hospedado exigiria a equipe instalar e manter um cluster próprio — carga operacional desnecessária para
o perfil de execução real hoje — e Temporal Cloud (a alternativa hospedada) não tem nenhuma região no Brasil,
criando risco de conflito com a expectativa de residência de dados assumida em D-09.

**Gatilho de revisão explícito.** Esta decisão deve ser reaberta se o desenho da saga evoluir para incluir
esperas de longa duração aguardando evento externo ou aprovação humana no meio da execução — cenário que o
código real, na data desta decisão, não contempla.

**Implementação** Ainda não iniciada — depende da Fase 2 (infraestrutura real), com D-08 já aprovada. O
desenho de como a saga síncrona atual será adaptada para rodar como um Workflow do Google Cloud em produção
é trabalho de engenharia futuro, não resolvido por esta ADR.

---

## ADR-0008 — Modelo comercial de IA: híbrido (franquia + créditos extras)

**Status:** **APROVADA** · **Data:** 27/08/2026 · **Aprovador:** Fábio Aluizio da Silva
**Depende de:** D-06 (APROVADA, 27/08/2026)
**Fonte da aprovação:** `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md`, SHA-256 `0579d36008c49f453117d1365736dc58792c08d0173f2c405f6f17ba1a85269e`

**Contexto.** O CAMPAIA usa IA (via AI Model Gateway, ADR-0005) para tarefas de marketing em nome do cliente. Era preciso decidir como o custo real de IA (pago pela F&M aos provedores) se traduz em cobrança ao cliente: absorver 100% no preço fixo do plano, repassar 100% via BYOK (cliente traz sua própria chave de provedor de IA), ou um modelo híbrido.

**Decisão.** Modelo **híbrido**: cada plano inclui uma **franquia de uso de IA** (custo absorvido pela F&M Tecnologia, com **teto rígido por tenant** — não é "uso ilimitado dentro do plano"), e o cliente pode comprar **créditos extras** ao ultrapassar a franquia.

**Consequências.** Exige que o AI Model Gateway (ADR-0005) meça consumo real por tarefa/tenant em tempo real e aplique o teto como invariante técnica — ao esgotar franquia e créditos, a IA deve recusar a tarefa (bloqueio explícito), nunca degradar silenciosamente ou gerar custo não coberto. A compra de créditos extras precisa de um fluxo de pagamento que não processe dados de cartão diretamente no CAMPAIA (roteado a um provedor de pagamento terceirizado), consistente com a postura geral de segurança de nunca manusear credenciais/dados sensíveis desnecessariamente. Em troca, o modelo evita o risco de custo variável não controlado (cenário 100% repasse/BYOK exigiria o cliente gerenciar sua própria chave, fricção alta para o segmento-alvo de D-03 — pequeno negócio local) e evita a F&M absorver custo ilimitado (cenário 100% inclusivo sem teto).

**Itens derivados ainda em aberto (não resolvidos por esta ADR):** tamanho da franquia por plano/tier comercial; mecanismo técnico de medição de consumo em tempo real; fluxo de compra de créditos extras; regra de bloqueio exata ao esgotar franquia + créditos.

**Riscos e mitigação.** Risco de estouro de custo se o teto não for aplicado corretamente no Gateway. Mitigação: o teto é uma invariante testável no AI Model Gateway (ADR-0005) — bloquear chamadas além do limite é comportamento padrão, não uma exceção a ser tratada caso a caso.

**Reversibilidade.** Média — mudar o modelo comercial após haver clientes pagantes exige migração cuidadosa de faturamento, mas a arquitetura técnica de medição de consumo e cofre de créditos é reaproveitável independentemente do modelo comercial adotado no futuro.

**Gatilho de revisão.** Se o custo real de IA por tenant divergir significativamente da franquia estimada nos primeiros meses de operação, revisar o **tamanho** da franquia — não a decisão estrutural do modelo híbrido em si.

---

## ADR-0009 — Nuvem alvo, região e estratégia de custo de infraestrutura: Google Cloud, São Paulo

**Status:** **APROVADA** · **Data:** 27/08/2026 · **Aprovador:** Fábio Aluizio da Silva
**Depende de:** D-08 (APROVADA, 27/08/2026)
**Fonte da aprovação:** `docs/evidence/DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md`, SHA-256 `468eb35f3d98f9ff7af51be658f3c28e462aa8b93c986ecfa0b55aaac6cab784`
**Fonte da pesquisa de valores exatos:** `docs/evidence/PESQUISA_VALORES_EXATOS_GOOGLE_CLOUD_20260827.md`, SHA-256 `09c8513d55c572952a7793ded868a7308564c2242eb245e7f17f31bdd45da00c`

**Contexto.** Nenhuma decisão de infraestrutura real (Fase 2) podia avançar sem escolher provedor de nuvem, região e ter clareza de custo. O Diretor não tinha preferência prévia e pediu recomendação técnica de engenharia sênior.

**Decisão.** **Google Cloud Platform, região São Paulo (southamerica-east1)**, como nuvem-alvo da infraestrutura do CAMPAIA — Cloud SQL (PostgreSQL), Memorystore (Redis), Pub/Sub, Cloud Workflows (ver ADR-0010), Cloud Storage, Secret Manager (ver ADR-0006).

**Razão.** Ecossistema único cobrindo todos os serviços necessários (banco, fila, workflow, segredo, armazenamento) sob um único provedor e faturamento, reduzindo complexidade de integração — coerente com a filosofia de ADR-0003 (monólito modular, não adicionar complexidade sem justificativa comprovada). Presença de região em São Paulo, atendendo à expectativa de residência de dados assumida em D-09/ADR-0011.

**Valores oficiais confirmados (27/08/2026):** Cloud SQL (PostgreSQL) — US\$ 0,0413/hora por vCPU + US\$ 0,007/GB-hora de memória, região São Paulo. Pub/Sub — US\$ 40/TiB (preço único mundial, sem sobretaxa regional). Cloud Workflows, Secret Manager e Cloud Storage — preço único mundial, sem sobretaxa regional (Cloud Storage ≈ US\$ 0,02/GB/mês). **Exceção registrada:** preço de Memorystore (Redis) específico da região São Paulo não obtido nesta sessão (dependia de seletor JavaScript inacessível) — mantido como pendência isolada (P-11) por instrução explícita do Diretor ("marque como pendente e vamos avançar"), sem bloquear esta ADR.

**Consequências.** Abertura de conta/projeto real no GCP é pré-requisito para qualquer trabalho de Fase 2 (dependência externa ainda não iniciada). Toda infraestrutura como código (IaC) futura tem como alvo serviços GCP. Aceita-se vendor lock-in em troca de menor complexidade operacional para uma equipe pequena.

**Riscos e mitigação.** Preço de Memorystore não confirmado pode alterar a estimativa de orçamento total. Mitigação: tratado como pendência isolada (P-11), não bloqueia esta nem outras decisões de infraestrutura.

**Reversibilidade.** Alta agora (nenhum recurso real provisionado); baixa após provisionamento de dados e cargas de trabalho em produção.

**Gatilho de revisão.** Divergência significativa entre custo real e estimado após uso em produção; ou exigência de multi-cloud por cliente enterprise (fora do escopo do MVP, D-03).

---

## ADR-0011 — Base legal LGPD, retenção e tratamento de listas de clientes

**Status:** **APROVADA** quanto aos papéis Controlador/Operadora · **Data:** 27/08/2026 · **Aprovador:** Fábio Aluizio da Silva
**Depende de:** D-09 (APROVADA quanto a papéis, 27/08/2026)
**Fonte da aprovação:** `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md`, SHA-256 `0579d36008c49f453117d1365736dc58792c08d0173f2c405f6f17ba1a85269e`

**Contexto.** O CAMPAIA processa dados pessoais que pertencem aos clientes contratantes (ex.: listas de clientes deles, usadas para segmentação/campanhas). Era preciso definir os papéis de LGPD entre F&M Tecnologia e cada cliente antes de qualquer uso real de dados pessoais de terceiros.

**Decisão.** Cada cliente contratante do CAMPAIA é o **Controlador** (Art. 5º, VI, LGPD) dos dados pessoais que ele próprio insere na plataforma (ex.: suas próprias listas de clientes). A **F&M Tecnologia é a Operadora** (Art. 5º, VII, LGPD), responsável pela segurança técnica dos dados dentro do aplicativo, processando-os por conta e segundo instruções do Controlador.

**Consequências.** A F&M deve implementar e manter medidas técnicas e organizacionais de segurança como Operadora — criptografia em repouso e cofre de segredos (ADR-0006), controle de acesso, trilha auditável (ADR-0004). A F&M deve oferecer aos clientes um instrumento formal de tratamento de dados (cláusula ou contrato de operação de dados, ainda não redigido) deixando claro seu papel de Operadora. Cada cliente permanece legalmente responsável por ter base legal própria (consentimento, legítimo interesse etc.) para os dados pessoais que insere — o CAMPAIA não verifica isso em nome do cliente, e isso deve constar explicitamente nos Termos de Uso.

**Itens derivados ainda em aberto (não resolvidos por esta ADR):** conclusão da abertura do CNPJ da F&M Tecnologia (em andamento via contabilidade do Diretor) — pré-requisito para formalizar o papel de Operadora perante terceiros, já que um instrumento de tratamento de dados exige uma pessoa jurídica constituída para assiná-lo; redação de política de retenção de dados; redação de Termos de Uso e Política de Privacidade; nomeação de responsável por privacidade.

**Riscos e mitigação.** Operar com dados pessoais reais de clientes (em especial listas para WhatsApp, Fase 7) antes do CNPJ ser emitido e antes de Termos/instrumento de tratamento de dados redigidos criaria exposição jurídica real. Mitigação: **gate explícito** — nenhum processamento real de dados pessoais de clientes finais até o CNPJ estar emitido e os Termos/instrumento de tratamento estarem redigidos e revisados (idealmente com apoio jurídico formal, fora do escopo de atuação do Claude).

**Reversibilidade.** Baixa uma vez que dados reais de clientes estejam sendo processados sem essas bases formais — por isso o gate é preventivo, não corretivo.

**Gatilho de revisão.** Emissão do CNPJ da F&M Tecnologia (desbloqueia a redação do instrumento de tratamento de dados e dos Termos); ou orientação jurídica formal que altere a interpretação dos papéis aqui assumida — esta ADR não constitui parecer jurídico.

---

## ADR-0013 — Modelo de credenciais e limites da configurabilidade

**Status:** PROPOSTA · **Data:** 25/08/2026

Documento próprio: `09_ADR_0013_CREDENCIAIS_E_CONFIGURABILIDADE.md`.

Resumo: dois modos de credencial (PLATFORM e BYO); a conta do cliente é configurável, a credencial de
plataforma não; lista fechada do que **não** pode ser desativado pelo cliente; Provider Simulator obrigatório.

---

## ADR-0012 — Estratégia de autenticação de usuários: Google Identity Platform

**Status:** **APROVADA** · **Data:** 27/08/2026 · **Aprovador:** Fábio Aluizio da Silva
**Depende de:** D-08 (APROVADA, 27/08/2026 — Google Cloud escolhido)
**Fonte da aprovação:** `docs/evidence/DIRETOR_DECISAO_ADR0012_AUTENTICACAO_20260827.md`

**Contexto.** Diferente de ADR-0008, ADR-0009 e ADR-0011, esta ADR não formalizava uma decisão D-numerada já tomada — era uma recomendação técnica nova, apresentada ao Diretor após D-08 (Google Cloud) já aprovada, sobre como resolver login e gestão de identidade de usuários do CAMPAIA (o próprio Diretor e, futuramente, os usuários de cada cliente/tenant).

**Opções analisadas.**

| Opção | Vantagem | Custo/Risco | Reversibilidade |
|---|---|---|---|
| A — Autenticação própria (construída do zero) | Controle total sobre o fluxo | Superfície de risco de segurança alta para equipe pequena (hash de senha, tokens de recuperação, gestão de sessão) | Baixa após usuários reais existirem |
| **B — Google Identity Platform (escolhida)** | Serviço gerenciado nativo do GCP já escolhido (D-08); cobre e-mail/senha, login social, redefinição de senha; suporte nativo a multi-tenant | Custo por usuário ativo acima de cota gratuita (irrelevante no volume inicial esperado, ADR-0003); dependência de vendor | Média — usa padrões abertos (JWT) |
| C — Terceiro especializado (Auth0, Clerk, Okta) | Recursos avançados prontos | Fornecedor adicional fora do GCP, contrariando a lógica de unificação de provedor de D-08/ADR-0009 | Média |

**Decisão.** **Google Identity Platform** é o serviço de autenticação de usuários do CAMPAIA — login por e-mail/senha e login social, com suporte a separação lógica multi-tenant entre os usuários de cada cliente contratante.

**Razão.** Para uma equipe pequena que já escolheu o Google Cloud como base de toda a infraestrutura (D-08/ADR-0009), a Opção B é a que menos gera trabalho extra de engenharia e menor risco de segurança, sem introduzir mais um fornecedor externo a gerenciar. A Opção A foi descartada por concentrar risco de segurança desnecessário numa área (autenticação) onde erros são custosos e bem conhecidos. A Opção C foi descartada por contrariar a lógica de unificação de provedor que motivou a escolha do GCP.

**Consequências.** Nenhuma senha de usuário é armazenada ou processada diretamente pelo `campaia_core` — o backend passa a validar tokens (JWT) emitidos pelo Identity Platform em cada requisição, nunca credenciais brutas. Provisionamento e convite de usuários por tenant precisam de um desenho próprio (item derivado, não resolvido por esta ADR).

**Itens derivados ainda em aberto (não resolvidos por esta ADR):** desenho detalhado de validação de token no backend; fluxo de convite/provisionamento de usuários por tenant; política de autenticação multifator (MFA) — pode ser oferecida como opção por tenant em fase futura, não obrigatória no MVP.

**Reversibilidade.** Média — migrar para outro provedor de autenticação no futuro é trabalho real de engenharia, mas não catastrófico, pois o Identity Platform usa padrões abertos (JWT) que a maioria das alternativas também compreende.

**Gatilho de revisão.** Necessidade de recurso de autenticação corporativa avançada (ex.: SSO/SAML exigido por um cliente enterprise) não coberto adequadamente pelo Identity Platform — fora do escopo do MVP (D-03, pequeno negócio local).

---

**Nota (27/08/2026):** ADR-0008, ADR-0009, ADR-0011 e ADR-0012 foram formalizadas nesta data — ver seções acima. ADR-0008, ADR-0009 e ADR-0011 já correspondiam a decisões D-numeradas explicitamente aprovadas pelo Diretor (D-06, D-08, D-09); esta atualização apenas redigiu o documento técnico formal, sem introduzir nenhuma decisão nova. ADR-0012 era uma recomendação técnica nova (não correspondia a uma decisão D-numerada prévia) — apresentada ao Diretor com três opções, discutida a seu pedido, e confirmada antes de ser marcada APROVADA. Nenhuma ADR permanece pendente de abertura nesta data.
