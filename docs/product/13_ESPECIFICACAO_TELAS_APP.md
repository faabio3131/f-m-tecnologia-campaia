# CampaIA — ESPECIFICAÇÃO DAS TELAS DO APP (B8)
**Campanhas inteligentes. Resultados reais.**

**Data:** 05 de setembro de 2026 (revisado com pesquisa de mercado)
**Bloco:** B8 — Especificação das telas do app
**Status:** PROPOSTA — AGUARDANDO VALIDAÇÃO DO DIRETOR
**Base evidencial:** `docs/product/FUNCTIONAL_REQUIREMENTS.md`, `docs/product/CAMPAIA_PRODUCT_CHARTER.md`,
`docs/product/OUT_OF_SCOPE.md`, `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md`, `docs/product/DECISOES_DIRETOR.md`

---

## 0. PESQUISA DE MERCADO (CONCORRENTES) — RESUMO PARA O DIRETOR

A pedido do Diretor, antes de fechar esta especificação foi feita uma pesquisa sobre ferramentas
concorrentes reais de automação de campanhas com IA. Achados relevantes:

| Ferramenta | O que realmente faz | Onde o CampaIA se posiciona diferente |
|---|---|---|
| **Madgicx** | Foco em Meta apenas; forte em "Creative Analytics" (qual elemento visual/copy performou melhor) e em insights — mas admite que "você ainda implementa a maioria das otimizações manualmente" | CampaIA cobre 3 canais desde o MVP (Google + Meta + WhatsApp) e vai além de insight: propõe e prepara a publicação, sempre com aprovação |
| **Revealbot** | Automação por regras "se/então" (ex: "se ROAS < 1.3, pausar") executadas sem intervenção humana, inclusive sem mecanismo de reautenticação documentado | O CampaIA passou a oferecer, por decisão do Diretor em 05/09/2026, um Modo Automático equivalente para **otimização** de campanhas já aprovadas — mas com uma salvaguarda que a Revealbot não tem: ativação exige senha de administrador, limite definido pelo próprio cliente, e log de auditoria imutável como prova de autorização. Publicação de campanha **nova** continua sempre exigindo aprovação manual, em qualquer modo — isso a Revealbot não distingue |
| **Smartly.io** | Automação de criativos em nível enterprise, 8 canais, sem interface conversacional, preço alto | CampaIA mira PME (qualquer negócio pequeno/médio), não enterprise — segmento diferente por decisão do Diretor (D-03) |
| **AdCreative.ai** | Gera criativos a partir de URL do site/produto; funciona como "caixa-preta" sem transparência de processo nas reviews públicas | CampaIA expõe explicitamente o "Por que isso?" (F9.3) em cada decisão da IA — transparência é parte do produto, não um detalhe |
| **Meta Advantage+** (referência de fluxo, não concorrente direto) | Fluxo em etapas: objetivo → orçamento/público → upload de múltiplos formatos de criativo (vertical, quadrado, carrossel) → "Opportunity Score" → publicar | Confirma que nossa sequência de etapas (Briefing→Estratégia→Criativos→Prévia→Aprovação) segue o padrão de mercado; identificou 2 lacunas corrigidas nesta revisão (ver §6.3 e §7.1) |

**Conclusão da pesquisa:** a estrutura geral do fluxo já especificado está alinhada com o padrão de
mercado. O diferencial real do CampaIA — aprovação humana obrigatória com motivo estruturado
(F5.3/F5.4) e explicação da decisão da IA (F9.3) — é incomum entre os concorrentes pesquisados
(a maioria é "insight-only" como Madgicx, ou autônoma como Revealbot). Duas lacunas funcionais
foram identificadas e corrigidas: breakdown de performance por variação específica de criativo
(§7.1) e suporte a múltiplos formatos de imagem por criativo já na etapa de geração (§6.3).

Fontes: [Best AI Tools for Managing Ad Campaigns 2026 — Pipeboard](https://pipeboard.co/best-ai-tools-manage-ads),
[Madgicx Review 2026 — Get Ryze](https://www.get-ryze.ai/blog/madgicx-review-2026-meta-ads-alternatives),
[AdCreative.ai Review — Zeely](https://zeely.ai/blog/adcreative-review/),
[Meta Advantage+ Campaign Setup Guide 2026 — 1ClickReport](https://www.1clickreport.com/blog/meta-advantage-plus-campaign-setup-2026)

---

## 1. OBJETIVO DESTE DOCUMENTO

Especificar, tela por tela, a interface mobile do CampaIA necessária para cobrir os requisitos
funcionais já aprovados (F1 a F10 em `FUNCTIONAL_REQUIREMENTS.md`), respeitando estritamente:

- O que está **aprovado para o MVP** — Nível de autonomia 1 (manual, toda publicação exige
  aprovação humana) **e** Nível 2 (automático, dentro de limite definido pelo cliente e protegido
  por senha de administrador na ativação — decisão do Diretor de 05/09/2026, ver
  `DECISOES_DIRETOR.md` item 5). O cliente escolhe qual modo usar.
- O que está **fora de escopo** (`OUT_OF_SCOPE.md`): Nível 3 de autonomia (sem limite definido pelo
  cliente), qualquer ação automática que exceda o limite que o próprio cliente configurou, canais
  além de Google/Meta/WhatsApp, briefing conversacional por chat (F3.2 é Fase 2), alertas de
  performance automáticos como notificação push (F7.4 é Fase 2).
- A decisão do Diretor de segmento **"qualquer negócio, não restrito a restaurantes"** (D-03) —
  portanto nenhuma tela assume um vertical específico; todos os campos de negócio são genéricos
  (tipo de negócio, categoria de produto, diferencial).

Este documento não especifica visual (cores, tipografia, componentes de design system) — apenas
estrutura de telas, campos, estados e navegação. Design visual é um bloco separado, a ser tratado
após validação desta especificação funcional.

---

## 2. MAPA DE NAVEGAÇÃO (VISÃO GERAL)

```
Login/Onboarding
  └─ Home (Dashboard de Campanhas)
       ├─ Nova Campanha (fluxo em etapas)
       │    ├─ 1. Briefing
       │    ├─ 2. Estratégia (proposta da IA)
       │    ├─ 3. Criativos (textos + imagens)
       │    ├─ 4. Prévia por Canal
       │    └─ 5. Aprovação
       ├─ Detalhe da Campanha
       │    ├─ Métricas
       │    ├─ Histórico de Versões
       │    └─ Log de Aprovações
       ├─ Brand Kit
       ├─ Conexões (Google / Meta / WhatsApp)
       ├─ Configurações
       │    ├─ Autonomia
       │    ├─ Modelos de IA
       │    └─ Permissões (roles)
       └─ Auditoria (admin)
```

---

## 3. ONBOARDING (cobre F1.1–F1.5)

### 3.1 Tela: Criar Conta / Login
- Campos: e-mail, senha (ou OAuth social, se decidido em bloco de autenticação — não coberto aqui).
- Sem armazenamento de senha em texto puro (ver `NON_FUNCTIONAL_REQUIREMENTS.md` §4.1).

### 3.2 Tela: Cadastro da Empresa (F1.1)
- Campos obrigatórios: nome da empresa, CNPJ, **tipo de negócio** (select genérico — não é lista de
  "restaurante"; inclui e-commerce, serviços, SaaS, imobiliário, varejo físico, outro), idioma.
- Validação: CNPJ formatado; nome único por tenant.
- Ação: "Continuar" → avança para Unidade de Negócio.

### 3.3 Tela: Unidade de Negócio (F1.2)
- Campos: nome da unidade (filial/marca/região), endereço (se aplicável ao tipo de negócio).
- Pode ser pulada com "Adicionar depois" — uma empresa pode operar com uma única unidade padrão.

### 3.4 Tela: Conectar Contas (F1.3, F1.4, F1.5)
- Três cartões independentes, cada um com estado próprio (Não conectado / Conectado / Erro):
  - **Google Ads** — botão "Conectar" inicia OAuth 2.0; após sucesso, lista contas do usuário e
    exige seleção de uma conta.
  - **Meta (Facebook/Instagram)** — botão "Conectar" inicia OAuth 2.0; após sucesso, lista Ad
    Accounts do Meta Business e exige seleção.
  - **WhatsApp Business** — botão "Conectar"; requer número comercial e aceite de permissões.
- Cada conexão é **opcional individualmente** — o usuário pode prosseguir tendo conectado apenas
  um canal (reflete a decisão D-06: "cliente escolhe qual usar", MVP simultâneo mas não obrigatório).
- Ação: "Concluir Onboarding" habilitada assim que pelo menos um canal estiver conectado.

---

## 4. BRAND KIT (cobre F2.1, F2.2)

### 4.1 Tela: Brand Kit
- Campos: logo (upload de imagem), paleta de cores (2–4 cores principais), tom de voz (select:
  formal / casual / técnico / inspirador — ou texto livre), lista de produtos/serviços,
  diferenciais competitivos (texto livre, múltiplas entradas), restrições de comunicação (texto
  livre — ex. "não mencionar concorrentes", "não usar superlativos").
- Estado vazio: tela orienta que o Brand Kit é usado pela IA na geração de criativos (F2.2) e pode
  ser editado a qualquer momento — não bloqueia a criação de campanhas, mas um aviso não-bloqueante
  aparece se a campanha for criada sem Brand Kit preenchido.

---

## 5. DASHBOARD / HOME (cobre F7.1)

### 5.1 Tela: Home
- Lista de campanhas com filtro por status: **Ativas / Pausadas / Em aprovação / Rascunho /
  Finalizadas**.
- Cada item de lista mostra: nome da campanha, canal(is), status, orçamento gasto vs. limite
  (barra de progresso), CTR resumido.
- Botão flutuante "Nova Campanha" sempre visível.
- Estado vazio (nenhuma campanha ainda): CTA central "Criar sua primeira campanha".

---

## 6. FLUXO DE NOVA CAMPANHA

### 6.1 Etapa 1 — Briefing (F3.1)
- Formulário único de rolagem, campos:
  - Objetivo primário (select: Leads / Vendas / Visitas / Mensagens) — obrigatório.
  - Objetivos secundários (checkbox múltiplo, opcional) — reflete D-04 ("todos os objetivos, com
    prioridade Leads > Vendas > Visitas > Mensagens" quando não especificado pelo usuário).
  - Oferta/produto (texto livre).
  - Público-alvo (texto livre + opção de targeting estruturado: idade, localização, interesses —
    estrutura mínima; refinamento de targeting avançado não é MVP).
  - Região geográfica (texto ou seleção de raio a partir de um endereço).
  - Orçamento total e período (datas de início/fim).
  - Upload de materiais existentes (textos, imagens, vídeos) — opcional.
  - Seleção de canais desejados (checkbox: Google / Meta / WhatsApp) — só aparecem os canais já
    conectados no onboarding; um canal não conectado aparece desabilitado com link para conectá-lo.
- **Fora de escopo nesta tela:** briefing conversacional por chat (F3.2 é Fase 2) — o formulário
  estruturado é a única via de briefing no MVP.
- Ação: "Gerar Estratégia" → chama IA Gateway, avança para Etapa 2.

### 6.2 Etapa 2 — Estratégia Proposta (F4.1)
- Tela somente-leitura com edição pontual, mostrando o que a IA propôs:
  - Canais recomendados (pode diferir da seleção do usuário, com explicação — liga a F9.3).
  - Públicos-alvo sugeridos por canal.
  - Distribuição de orçamento entre canais (gráfico simples de barras/pizza + valores).
  - Formatos de anúncio por canal.
- Cada bloco tem um ícone "Por que isso?" que expande a explicação da IA (F9.3 — explicabilidade).
- Ações: "Ajustar" (volta para edição manual de qualquer campo) ou "Continuar para Criativos".

### 6.3 Etapa 3 — Criativos (F4.2, F4.3, F4.4)
- Sub-abas por canal (uma aba por canal selecionado).
- Dentro de cada aba:
  - Textos gerados: título(s), descrição(ões), CTA — cada um com variações A/B lado a lado,
    editáveis inline.
  - Imagens geradas: miniaturas por formato (quadrada, story, banner, vertical 9:16 conforme o
    canal) — cada criativo é gerado automaticamente em **todos os formatos relevantes do canal
    selecionado** (não apenas um formato padrão), com botão "Gerar outra versão" por formato e
    upload manual como alternativa. Isso segue o padrão observado no fluxo do Meta Advantage+, que
    pede múltiplos formatos (vertical, quadrado, carrossel) já na etapa de criativo, não depois.
  - Indicador de validação de política (F4.4): selo verde "Aprovado pela política" ou aviso
    amarelo/vermelho "Revisar: [motivo]" quando a IA detecta possível violação (categoria
    sensível, alegação não permitida) — bloqueia avanço até o usuário resolver ou confirmar ciência.
- Ação: "Continuar para Prévia".

### 6.4 Etapa 4 — Prévia por Canal (F5.1)
- Visualização simulada de como o anúncio aparecerá em cada canal selecionado (mockup de feed do
  Google/Facebook/Instagram, mockup de mensagem do WhatsApp).
- Permite edição de texto diretamente na prévia e ajuste manual de público.
- Navegação por abas ou carrossel entre canais.
- Ação: "Continuar para Aprovação".

### 6.5 Etapa 5 — Aprovação (F5.2, F5.3, F5.4)
- Resumo final da campanha (todos os parâmetros consolidados em uma tela de revisão).
- **Nota de posicionamento (pós-pesquisa de mercado):** esta tela é o ponto onde o CampaIA se
  diferencia da maioria dos concorrentes pesquisados — nenhuma publicação acontece sem essa
  etapa, e o app deve deixar isso visualmente claro (ex: selo "Nenhuma campanha é publicada sem
  sua aprovação"), não apenas como regra de backend invisível. Ferramentas como Revealbot
  publicam/pausam sozinhas por regras automáticas; o CampaIA nunca faz isso no MVP.
- Três ações possíveis, visíveis apenas para usuário com permissão de aprovador (F10.3):
  - **Aprovar** — campo de comentário opcional, timestamp registrado automaticamente (F5.2).
  - **Rejeitar** — campo de motivo **obrigatório**, campanha retorna para rascunho (F5.3).
  - **Solicitar Ajustes** — comentário estruturado por seção (texto / imagem / público / orçamento),
    campanha retorna para a etapa correspondente com o feedback anexado (F5.4).
- Nota de guardrail: se o orçamento ultrapassar o limite configurado ou representar aumento > 20%
  sobre uma campanha anterior semelhante, um aviso de aprovação reforçada aparece (reflete Charter
  §9 — ações que sempre exigem aprovação humana). Isso é uma tela de aviso, não um bloqueio
  automático adicional — o MVP não implementa lógica de bloqueio automática de orçamento além da
  aprovação humana já obrigatória em todo o fluxo (Nível 1).
- Após aprovação: publicação é disparada (F6.1–F6.4), tela de confirmação com status "Publicando…"
  e depois "Publicada" ou erro com opção de retry (idempotente, F6.4).

---

## 7. DETALHE DA CAMPANHA (cobre F7.2, F9.1, F9.2, F9.3)

### 7.1 Tela: Métricas da Campanha (F7.2)
- Cartões de métrica: CTR, CPC, CPA, ROAS — agregados e por canal.
- Breakdown por criativo **até o nível de variação individual** (ex: Variação A do título vs.
  Variação B, Imagem 1 vs. Imagem 2) — não apenas um agregado por criativo. Cada variação mostra
  suas métricas próprias lado a lado, permitindo identificar qual elemento específico (texto,
  imagem, CTA) teve melhor desempenho. Isso cobre uma lacuna real frente ao mercado: ferramentas
  como Madgicx oferecem "Creative Analytics" neste nível de detalhe, e nossa especificação
  original só prometia um breakdown genérico "por criativo".
- Comparação vs. objetivo declarado no briefing.
- **Fora de escopo:** alertas automáticos de performance anômala (F7.4 é Fase 2) — esta tela é
  consulta, não monitoramento ativo com notificações de anomalia.

### 7.2 Tela: Histórico de Versões (F9.1)
- Timeline vertical: cada versão da campanha como um marco, com data, autor da mudança, e diff
  resumido (o que mudou entre versões).

### 7.3 Tela: Log de Aprovações (F9.2)
- Lista cronológica: quem aprovou/rejeitou/solicitou ajuste, quando, e o comentário associado.

### 7.4 Explicações da IA (F9.3)
- Não é uma tela isolada — é um padrão de UI (ícone "Por que isso?") reutilizado nas telas de
  Estratégia (6.2) e Métricas (7.1), sempre expandindo texto explicativo gerado pela IA sobre a
  decisão em questão (público escolhido, distribuição de orçamento, modelo usado).

---

## 8. OTIMIZAÇÕES (cobre F8.1 e, condicionalmente, F8.2 dentro do Modo Automático — revisado 05/09/2026)

### 8.1 Tela: Sugestões de Otimização
- Lista de sugestões geradas pelo Performance Agent, cada uma com: descrição da sugestão (ex.
  "Aumentar orçamento em 15% — CTR está em 2.3%, acima do limite de referência"), canal afetado.
- **Comportamento depende do modo de autonomia configurado pelo cliente (ver §9.1):**
  - **Modo Manual (Nível 1):** botões **"Aplicar"** / **"Ignorar"** — toda aplicação passa pelo
    fluxo de aprovação humana normal, nenhuma sugestão é executada sozinha. Este é o comportamento
    original desta tela.
  - **Modo Automático (Nível 2), quando ativo e a sugestão está dentro do limite configurado pelo
    cliente:** a sugestão aparece com um selo "Aplicada automaticamente" em vez dos botões — o
    sistema já executou, e a tela serve como registro/transparência, não como fila de aprovação.
    Toda aplicação automática gera entrada no log de auditoria (F9.4) e uma notificação ao usuário
    (não bloqueante — é informativo, não pede aprovação).
  - **Sugestão que excede o limite configurado, mesmo com Modo Automático ativo:** cai de volta
    para o fluxo manual (botões Aplicar/Ignorar) — o sistema nunca ultrapassa o teto que o cliente
    definiu sem voltar a pedir aprovação explícita.
- Esta é a atualização de escopo que faz F8.2 ("Executar otimizações automáticas") deixar de ser
  puramente "Out of scope MVP (Fase 3)" — agora está condicionalmente dentro do MVP, mas só dentro
  do Modo Automático ativado com senha de administrador (ver §9.1.1) e só dentro do limite que o
  próprio cliente configurou. Fora dessas condições, a regra antiga permanece: sugerir, nunca
  executar sozinho.
- Esta tela é acessível a partir do Detalhe da Campanha, não do fluxo principal.

---

## 9. CONFIGURAÇÕES (cobre F10.1, F10.2, F10.3)

### 9.1 Tela: Autonomia — Manual ou Automático (F10.1, revisado 05/09/2026)

**Atualização de escopo:** por decisão do Diretor (ver `DECISOES_DIRETOR.md` item 5, citação
literal registrada em 05/09/2026), o MVP agora oferece **duas opções reais de funcionamento**, não
apenas uma. Esta tela deixou de ser um seletor com opções desabilitadas e passa a ser um controle
funcional completo.

- Dois cartões grandes, lado a lado ou empilhados, cada um representando um modo:
  - **Modo Manual (Nível 1)** — "Toda campanha passa por sua aprovação antes de publicar."
    Selecionado por padrão para novas contas.
  - **Modo Automático (Nível 2)** — "Defina um limite e deixe o CampaIA otimizar suas campanhas já
    aprovadas dentro dele, sem precisar aprovar cada ajuste. Campanhas novas continuam sempre
    passando por sua aprovação." Badge "Requer senha de administrador para ativar".
- A troca de Manual → Automático dispara o fluxo descrito em 9.1.1 abaixo (não é uma troca simples
  de toggle).
- A troca de Automático → Manual é imediata (não requer senha — só ativar automação exige,
  desativar não precisa dessa fricção).
- Nível 0 (Assistente) e Nível 3 (Operacional) continuam fora do MVP; aparecem desabilitados com
  rótulo "Disponível em fase futura", para transparência de roadmap sem implicar disponibilidade
  atual.
- Configuração de limites de autonomia (diário/mensal/por campanha) existe em ambos os modos,
  ligando aos Guardrails Financeiros do Charter §10 — no Modo Manual eles são um teto de alerta; no
  Modo Automático eles são o teto que o sistema nunca ultrapassa sem nova aprovação.

#### 9.1.1 Tela: Ativar Modo Automático (nova — salvaguarda de senha)
- Acionada ao tentar mudar de Manual para Automático.
- Passo 1 — Definir limites: campos obrigatórios do limite que o sistema poderá operar sozinho
  dentro dele — orçamento máximo diário/mensal por campanha, variação percentual máxima permitida
  em ajustes automáticos, e quais ações ficam cobertas. **Fechado em 05/09/2026 (ver
  `DECISOES_DIRETOR.md` item 5):** o escopo do Modo Automático cobre exclusivamente **otimização/
  ajuste de campanhas que já tiveram pelo menos uma publicação aprovada manualmente** — nunca a
  criação/publicação de uma campanha nova. Este campo não oferece "publicação de campanha nova"
  como ação configurável, porque essa ação nunca é elegível ao Modo Automático (ver nota abaixo).
- Passo 2 — Revisão: tela de resumo mostrando exatamente o que o Modo Automático poderá fazer
  sozinho dentro dos limites definidos, em linguagem direta (ex: "O CampaIA poderá ajustar lances
  em até 10% e mover orçamento entre canais, sempre respeitando o teto de R$ X/dia, em campanhas
  já aprovadas por você. Você será notificado de cada ação, mas não precisará aprovar cada uma.
  Campanhas novas continuam sempre passando por uma tela de aprovação sua antes de publicar.").
- Passo 3 — Confirmação por senha: campo de senha do administrador da conta (reautenticação, não
  apenas sessão já logada). Texto de aviso fixo: "Ao confirmar, você autoriza o CampaIA a otimizar
  automaticamente, dentro dos limites acima, campanhas já aprovadas por você. Este evento fica
  registrado com data, hora e usuário para sua segurança." Botão "Confirmar e Ativar" só habilita
  após senha correta.
- Registro: o evento completo (quem, quando, quais limites, de qual IP/dispositivo se disponível)
  é gravado no log de auditoria (F9.4) de forma imutável — é a prova de autorização em caso de
  disputa futura, conforme a preocupação expressa pelo Diretor ("provaremos que ele inseriu a
  senha").
- Erro de senha: mensagem genérica de erro (não revela se o e-mail/usuário existe), limite de
  tentativas antes de bloqueio temporário (alinhado a boas práticas de autenticação, ver
  `NON_FUNCTIONAL_REQUIREMENTS.md` §4.1).

**Regra de campanha nova (confirmada pelo Diretor em 05/09/2026 — não é mais uma nota em aberto):**
mesmo com o Modo Automático ativo, a **criação/publicação de uma campanha nova** sempre exige uma
aprovação humana explícita antes de ir ao ar, sem exceção — alinhado ao Charter §9, item 1 ("✋
Campanha nova" está na lista de ações que sempre exigem aprovação humana). A senha de administrador
+ valor pré-definido do Passo 3 acima autoriza apenas a otimização automática de campanhas que já
passaram por essa aprovação manual inicial pelo menos uma vez. O Diretor confirmou este mecanismo
explicitamente ao responder à dúvida levantada nesta especificação: *"não o automatico só
funcionará com aprovação humana mediante senha de adm e valor pré-definido"*, e, diante de uma
pergunta de fechamento com duas opções concretas, escolheu "Campanha nova sempre manual" como a
leitura correta — ver `DECISOES_DIRETOR.md` item 5, seção "Esclarecimento adicional".

### 9.2 Tela: Modelos de IA (F10.2)
- Seleção de modelo padrão (lista dependente do que for aprovado por ADR — hoje nenhum fornecedor
  concreto está aprovado, ver `DECISOES_DIRETOR.md`; esta tela deve ser implementada de forma
  agnóstica a fornecedor, lendo a lista disponível de uma configuração, não hardcoded).
- Opção de fallback (ligar/desligar) e campo de BYOK key — **nota:** BYOK está decidido como fora
  do MVP (`DECISOES_DIRETOR.md` "Sem BYOK no MVP"); o campo deve ficar oculto/desabilitado até essa
  decisão ser revista, não deve ser removido da especificação para não exigir retrabalho futuro.

### 9.3 Tela: Permissões (F10.3)
- Lista de usuários da empresa, cada um com role atribuída (Criador / Aprovador / Visualizador),
  editável apenas por Administrador.
- Restrições por canal, orçamento e objetivo — checkboxes/limites numéricos por usuário.

---

## 10. AUDITORIA (cobre F9.4, acesso restrito a Administrador)

### 10.1 Tela: Auditoria
- Filtros: por usuário, por período, por tipo de ação.
- Botão "Exportar" (CSV/PDF) gerando o audit trail completo (quem fez o quê, quando, por quê).
- Relatório de conformidade como visualização agregada (contagem de ações por categoria).

---

## 11. TELAS EXPLICITAMENTE FORA DE ESCOPO DESTE DOCUMENTO

Para que não haja ambiguidade de escopo ao implementar a partir desta especificação:

- ❌ Chat de briefing conversacional (F3.2 — Fase 2).
- ❌ Alertas automáticos de performance/anomalia como notificação push (F7.4 — Fase 2).
- ❌ Execução automática de otimização **sem limite definido pelo cliente e sem senha de
  administrador** (isso é Nível 3, continua Fase 3). Execução automática **dentro** do limite
  configurado pelo cliente e com Modo Automático ativado via senha **está dentro do MVP** desde a
  decisão de 05/09/2026 (ver §8.1 e §9.1.1) — não confundir as duas coisas.
- ❌ Telas para canais além de Google, Meta e WhatsApp (YouTube, LinkedIn, TikTok etc. —
  `OUT_OF_SCOPE.md`).
- ❌ Dashboard web (Fase 12 — `NON_FUNCTIONAL_REQUIREMENTS.md` §8.3); esta especificação cobre
  somente o app mobile.
- ❌ Telas de billing/pagamento detalhado (mencionadas como Fase 2+ em `DECISOES_DIRETOR.md`,
  ponto 3 — Modelo Comercial).

---

## 12. PRÓXIMOS PASSOS SUGERIDOS

1. Validação desta especificação pelo Diretor (aprovar / pedir ajustes).
2. Definição de wireframes visuais (fora do escopo deste documento — bloco de design separado).
3. Priorização de implementação: onboarding + fluxo de nova campanha são o caminho crítico do MVP
   (sem eles, nenhuma campanha pode ser criada); Configurações e Auditoria podem vir em paralelo
   ou logo depois.

---

**Status:** PROPOSTA — AGUARDANDO VALIDAÇÃO DO DIRETOR
