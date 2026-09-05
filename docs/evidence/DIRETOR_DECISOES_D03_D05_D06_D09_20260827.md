# FONTE PRIMÁRIA — DECISÕES DO DIRETOR: D-03, D-05, D-06, D-09

**Capturado em:** 27 de agosto de 2026
**Capturado por:** Claude, a partir de respostas literais do Diretor coletadas via ferramenta de perguntas estruturadas (AskUserQuestion), em resposta direta ao texto original de `04_DECISOES_DO_DIRETOR.md` (Google Drive, fileId `18Ti7Wuk16I9MSgk8ZFesjuNUVkIGkM-f`)
**Diretor:** Fábio Aluizio da Silva
**Confirmação final literal do Diretor:** "correto sim"

---

## D-03 — Segmento inicial

**Pergunta apresentada:** "D-03 — Segmento inicial: qual tipo de cliente o CAMPAIA atende primeiro?" com opções (a) vertical específico, (b) qualquer pequeno negócio local, (c) agências.

**Resposta literal do Diretor:** "Qualquer pequeno negócio local"

**Decisão:** D-03 = (b) — CAMPAIA atende, no MVP, qualquer pequeno negócio local, sem restrição a um vertical/nicho específico (horizontal, não vertical).

**Nota técnica preservada do documento original:** esta opção era uma das duas recomendadas tecnicamente para o MVP (junto com a opção "vertical específico"), mas exige generalizar o produto (Brand Kit, públicos, prompts de IA) mais cedo do que um recorte vertical exigiria. Agências (opção c) foram descartadas por decisão do Diretor.

---

## D-05 — Objetivo primário do MVP

**Pergunta original apresentada (mal endereçada na primeira tentativa):** a primeira formulação de D-05 foi respondida pelo Diretor com "google ads, facebook, instagram e whats" — o que revelou que a pergunta original confundia CANAIS (já decididos em D-04/ADR-0007) com OBJETIVO DE CONVERSÃO (o que D-05 realmente pergunta). Isso foi esclarecido explicitamente ao Diretor antes de prosseguir.

**Pergunta esclarecida:** "Usando Google Ads + Meta (Facebook/Instagram) + WhatsApp como canais (já aprovado em D-04), qual é o RESULTADO que a campanha deve gerar para o MVP ser considerado bem-sucedido?" com opções (a) geração de leads, (b) mensagens no WhatsApp, (c) vendas no site, (d) visitas físicas à loja.

**Resposta literal do Diretor:** "a resposta para essa pergunta tambem são todas essas opções pois dependendo do tipo de negocio que usará nosso app terá que atender todas essas opções"

**Pergunta de escopo levantada em seguida:** dado que o documento original recomendava tecnicamente "escolher um só. Um MVP que 'faz todos' não prova nenhum", foi perguntado ao Diretor se a arquitetura deveria suportar os 4 objetivos desde o início mas o MVP validar com 1–2 primeiro, ou se o MVP já deveria nascer com os 4 completos.

**Resposta literal do Diretor:** "os 4 já na primeira versão"

**Decisão:** D-05 = o CAMPAIA suporta os 4 objetivos de conversão (geração de leads, vendas no site, mensagens no WhatsApp, visitas físicas à loja) como opção configurável por cliente/tenant — e os 4 devem estar completos e funcionais já na primeira versão testada (MVP), não apenas na arquitetura de base.

**⚠️ Nota de transparência obrigatória:** esta decisão substitui explicitamente a recomendação técnica registrada no documento original (`04_DECISOES_DO_DIRETOR.md`): *"Recomendação técnica. Escolher um só. Um MVP que 'faz todos' não prova nenhum."* O Diretor decidiu, com pleno conhecimento dessa recomendação (apresentada a ele antes da decisão final), seguir por um caminho diferente. Isso é registrado como decisão soberana do Diretor, não como remoção silenciosa da recomendação técnica original — a recomendação permanece visível no histórico como contraponto.

**Impacto técnico herdado do documento original (ainda válido, agora multiplicado por 4 objetivos simultâneos):** exige pixel/dataset, Conversions API e reconciliação de conversão (para leads e vendas no site); exige consentimento, templates aprovados e opt-out (para WhatsApp); mensuração mais fraca para visitas físicas à loja. Cada objetivo agora precisa de seu próprio caminho de mensuração implementado em paralelo, aumentando o escopo de engenharia do MVP em relação ao que o documento original previa.

**Ponto de atenção não resolvido por esta decisão:** o objetivo "mensagens no WhatsApp" depende estruturalmente da etapa Meta estar concluída primeiro (Click-to-WhatsApp nasce do fluxo de anúncios da Meta), o que é consistente com a ordem sequencial já aprovada em D-04/ADR-0007 (Google → Meta → operação conjunta → WhatsApp) — ou seja, mesmo com os 4 objetivos "ativos" desde o MVP, o objetivo WhatsApp só pode ser tecnicamente validado depois que a etapa Meta estiver funcionando.

---

## D-06 — Modelo comercial de IA

**Pergunta apresentada:** "D-06 — Modelo comercial de IA: como o cliente paga pelo uso de IA?" com opções (a) IA inclusa no plano, (b) créditos comprados pelo cliente, (c) BYOK, (d) híbrido.

**Resposta literal do Diretor:** "Híbrido"

**Pergunta de esclarecimento levantada em seguida (dado que "híbrido" tem múltiplas combinações possíveis):** apresentadas 3 opções de combinação híbrida concreta.

**Resposta literal do Diretor:** "Franquia inclusa no plano + créditos extras pagos"

**Decisão:** D-06 = modelo híbrido — cada plano contratado inclui uma franquia de uso de IA já embutida no preço (custo assumido pelo CAMPAIA/F&M Tecnologia, sujeita a teto rígido por tenant); ao ultrapassar essa franquia, o cliente compra créditos adicionais para continuar usando a IA no período.

**Impacto técnico herdado do documento original, ainda obrigatório:** independentemente do modelo, o `ai_cost_ledger` (livro-razão de custo de IA por tenant) e um limite rígido de gasto por tenant são obrigatórios. Este modelo específico exige adicionalmente: (1) definição do tamanho da franquia por plano/tier comercial; (2) mecanismo de medição de consumo em tempo real para saber quando a franquia se esgotou; (3) fluxo de compra de créditos extras (gateway de pagamento, sem processar cartão diretamente segundo as regras já estabelecidas nesta sessão); (4) desligamento automático ou bloqueio de novo uso de IA quando franquia e créditos se esgotarem, para não gerar prejuízo.

**Nota — BYOK não foi a opção escolhida:** BYOK (cliente traz a própria chave de API) permanece mencionado no documento original e na ADR-0013 do Drive como opção que ainda estava em aberto/proposta, mas o Diretor optou pelo modelo híbrido franquia+créditos, não por BYOK nem por híbrido incluindo BYOK. Isso é distinto e não deve ser confundido com o registro anterior desta sessão (sandbox local, não Drive) que havia fechado BYOK como "não suportado no MVP" — aquele registro tratava de BYOK para conexão de contas de anúncio (ADR-0013), enquanto D-06 trata especificamente do modelo comercial de consumo de IA. Ambos os pontos, tratados separadamente, agora resultam em: nenhum dos dois usa BYOK no momento, por decisões independentes do Diretor.

---

## D-08 — Nuvem, região e orçamento de infraestrutura

**Status: PERMANECE EM ABERTO.** O Diretor indicou inicialmente que já tinha uma preferência, mas ao ser perguntado qual, respondeu literalmente: "não sei qual seria a melhor opção e de menor custo beneficio". Por disciplina de não decidir por suposição, esta pendência NÃO foi fechada. Foi acordado que Claude fará uma pesquisa comparativa real de custo-benefício (nuvem, banco gerenciado, fila, workflow durável, residência de dados no Brasil — relevante para a decisão D-09 abaixo) antes de trazer uma recomendação concreta ao Diretor, seguindo o mesmo padrão usado para a pesquisa de provedores de IA (Fase 1).

**Esta pendência não bloqueia o registro das demais 4 decisões desta rodada**, mas continua bloqueando formalmente a ADR-0009, a ADR-0010 e o início real da Fase 2, exatamente como o documento original já indicava.

---

## D-09 — Entidade legal, LGPD e tratamento de dados pessoais

**Pergunta apresentada:** esclarecimento detalhado dos 4 itens que compõem D-09 (controlador dos dados; base legal para listas de clientes; política de retenção; responsável por privacidade + termos de uso).

**Resposta literal do Diretor:** "nosso app vai ser comercialmente usado ditretamente pelo clienque que queira contratar nosso app para facilitar a vida dele no quesito marketing enta~cada cliente ficará responsavel peloa dados inseridos e nos a empresa fornecedora do app F&M Tecnologia sera responsável pela segurança dos dados no app"

**Perguntas de esclarecimento adicionais e respostas literais:**
- "A F&M Tecnologia já é uma empresa formalmente aberta (CNPJ existente)?" → **"Ainda não, está em processo de abertura"**
- "Qual papel legal a F&M Tecnologia assume sobre os dados que passam pelo CAMPAIA?" → **"Operadora (processa dados por conta do cliente)"**

**Decisão:**
1. **Controlador dos dados:** cada cliente contratante do CAMPAIA (o dono do negócio que assina o plano) é o Controlador dos dados que ele mesmo insere no sistema — incluindo a lista de contatos/clientes finais dele, usada por exemplo em Customer Match.
2. **Operadora:** **F&M Tecnologia** é a Operadora dos dados — processa os dados por conta e instrução do cliente contratante (o Controlador), e responde pela segurança técnica dos dados dentro do aplicativo (criptografia, controle de acesso, resposta a incidentes).
3. **Pré-requisito formal pendente:** F&M Tecnologia **ainda não possui CNPJ aberto** — está em processo de abertura. Isso é registrado como bloqueio formal: nenhuma operação real de produção que envolva dados pessoais de terceiros (em especial Fase 7/WhatsApp e qualquer uso de lista de clientes/Customer Match) pode iniciar antes da constituição formal da empresa, porque não há hoje uma pessoa jurídica que possa legalmente assumir o papel de Operadora perante a LGPD e a ANPD.
4. **Base legal para listas de clientes:** decorre da estrutura acima — cabe ao cliente contratante (Controlador) garantir que tem base legal/consentimento para a própria lista que ele sobe no CAMPAIA; o CAMPAIA/F&M, como Operadora, deve prever isso contratualmente nos Termos de Uso (ainda não redigidos).
5. **Itens ainda não resolvidos dentro de D-09:** política de retenção de dados após cancelamento (prazo específico não definido); redação formal de Termos de Uso e Política de Privacidade (não existe ainda); nomeação de uma pessoa/cargo específico como responsável por privacidade dentro da F&M Tecnologia (não definido — a decisão de papel foi organizacional/jurídica, mas não nomeou uma pessoa física).

**Bloqueio técnico que permanece ativo até a abertura do CNPJ:** Fase 7 (WhatsApp) e qualquer uso de lista de clientes em produção real com dados de terceiros verdadeiros.

---

## Resumo de status após esta rodada

| Decisão | Status antes | Status agora |
|---|---|---|
| D-03 — Segmento inicial | Aberta | ✅ Fechada — pequeno negócio local, horizontal |
| D-05 — Objetivo do MVP | Aberta | ✅ Fechada — 4 objetivos completos desde o MVP (diverge da recomendação técnica original, por decisão soberana do Diretor) |
| D-06 — Modelo comercial de IA | Aberta | ✅ Fechada — híbrido: franquia inclusa + créditos extras |
| D-08 — Infraestrutura | Aberta | ⏳ Permanece aberta — aguardando pesquisa de custo-benefício antes de decisão |
| D-09 — Legal/LGPD | Aberta | ✅ Fechada quanto a papéis (Controlador=cliente, Operadora=F&M Tecnologia) — mas com pré-requisito formal pendente (CNPJ da F&M ainda não existe) e 3 itens ainda por redigir (retenção, termos de uso, responsável nomeado) |
