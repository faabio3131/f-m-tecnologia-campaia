# CampaIA — DECISÕES DO DIRETOR
**Fábio Aluizio da Silva**

**Data:** 26 de agosto de 2026
**Corrigido em (Fase 0E):** 26 de agosto de 2026
**Status:** ⚠️ VER `DECISION_REGISTER.md` — este documento é um registro histórico de trabalho e, onde divergir do Decision Register, o Decision Register prevalece

**Nota de correção (Fase 0E):** este documento foi escrito antes da exigência de padrão evidencial rigoroso (fonte primária hasheada). Várias linhas abaixo (ex.: "IA Gateway: OpenAI, Gemini, Claude com fallback chain inteligente" como decisão "já aprovada") tratavam a escolha de fornecedores concretos de IA como fechada, o que foi corrigido em `ADR_003`, `ADR_004` e `DECISION_REGISTER.md`. Para o estado evidencial atual de cada decisão, consultar `docs/execution/DECISION_REGISTER.md`, não este arquivo.

---

## DECISÕES CRÍTICAS FASE 0 → FASE 1

### 1. Segmento de Mercado
**Decisão:** ✅ **Qualquer negócio (não restrito a restaurantes)**

**Rationale:** Escalabilidade comercial da IA — comportamento de campanha é universal em vertical, apenas contexto muda (copy, imagens, canais preferidos).

**Impacto:**
- Personas expandidas (além restaurantes: e-commerce, serviços, SaaS, imobiliário)
- Briefing obrigatório mais robusto (tipo negócio, categoria produto, diferencial)
- Templates de negócio/vertical (Fase 2+)
- Pesquisa Fase 1: validar APIs em múltiplos setores

---

### 2. Objetivo(s) de Campanha
**Decisão:** ✅ **Todos (Leads, Vendas, Visitas, Mensagens) com foco escalabilidade e resultados**

**Prioridade MVP:** 
1. Leads (formulário + CRM)
2. Vendas (conversão direta)
3. Visitas (troca, localização física)
4. Mensagens (WhatsApp, Telegram futura)

**Rationale:** Não limitar usuário a um objetivo — oferecer suite completa. IA seleciona canal/estratégia baseado no objetivo declarado.

**Impacto:**
- F2 (Briefing): campo obrigatório "Objetivo Primário" (select + múltipla seleção secundária)
- F3 (Estratégia): IA recomenda canais por objetivo (ex: vendas → Google Shopping; leads → Meta Lead Ads)
- F6 (Publicação): criar mapeamento objetivo → asset type → canal otimizado
- Métrica Fase 12: rastrear conversão por objetivo

---

### 3. Modelo Comercial

> ⚠️ **SUPERSEDED por `docs/18_ADR_0020_MODELO_COMERCIAL_E_GATEWAY_DE_PAGAMENTO.md` (24/09/2026).**
> Este item descrevia "assinatura pura, sem créditos" com Stripe, mas D-06 (27/08/2026, um dia
> depois desta nota) já havia decidido o modelo híbrido abaixo, e nunca foi propagado para este
> documento. Mantido aqui, não apagado, por disciplina de rastreabilidade (Padrões de Construção
> Nova FM, §7). **Não seguir a decisão abaixo — ver a ADR-0020 para o modelo vigente: franquia
> mensal + créditos extras pagos por excedente, gateway Asaas.**

**Decisão (histórica, substituída):** ✅ **Assinatura (Subscription puro)**

**Modelo:**
- Plano mensal + limite de campanhas/mês
- Limite IA tokens por plano (ex: Starter 50k, Pro 500k, Enterprise ilimitado)
- Sem BYOK no MVP (✅ decisão fechada e reconciliada em 26/08/2026 — ver `docs/decisions/ADR_003_MULTIMODEL_AI_GATEWAY.md` §SEGURANÇA/BYOK e `DECISION_REGISTER.md` D008)
- Sem créditos pré-pagos — assinatura simplifica cobrança e previsibilidade

**Impacto:**
- F1 (Onboarding): seleção de plano no signup
- F4 (Policy): enforcement de limite campanhas e tokens por plan_tier
- Dashboard Fase 12: uso atual vs limite, próximas datas de renovação
- Billing Fase 2+: integração Stripe para pagamento recorrente

**Rationale:** Assinatura = receita previsível, alinhada com SaaS B2B, fácil para PMEs budgetar.

---

### 4. Prioridade Canais
**Decisão:** ✅ **Simultâneo — Cliente escolhe qual usar**

**Modelo:**
- MVP inclui ambos: **Google Search Ads** + **Meta (Facebook/Instagram)** + **Click-to-WhatsApp**
- Usuário seleciona canais desejados no F2 (Briefing): checkbox múltipla
- Cada canal tem suas recomendações IA (copy, criativo, audience)
- Publicação simultânea ou seletiva (cliente controla)
- Dashboard consolida métricas de todos os canais

**Impacto:**
- Fase 1: Pesquisa oficial de ambas APIs em paralelo
- Fase 4-5: Implementar Google Ads Adapter
- Fase 6-7: Implementar Meta Ads Adapter
- Fase 9: Integrar Click-to-WhatsApp (via Meta)
- F2 (Briefing): campo "Canais desejados" (checkbox: Google, Meta, WhatsApp)
- F3-5: Estratégia IA customizada por canal selecionado

**Rationale:** Máxima flexibilidade para cliente, cobertura maior, alinha com "qualquer negócio" — restaurante usa Google Local + Meta, e-commerce usa ambos, SaaS pode preferir Google.


---

### 5. Autonomia no MVP — Manual E Automático (Nível 2 entra no MVP)
**Decisão:** ✅ **O MVP oferece as duas opções: aprovação manual (Nível 1) E modo automático com limite definido pelo cliente (Nível 2), sob validação obrigatória por senha de administrador**

**Data da decisão:** 05/09/2026, durante revisão do B8 (Especificação das telas do app).

**Contexto:** Esta decisão reverte parcialmente o que estava registrado em `CAMPAIA_PRODUCT_CHARTER.md`
§9 ("MVP começa no Nível 1") e em `OUT_OF_SCOPE.md` ("❌ Nível 3 no MVP", "❌ Publicação sem
aprovação humana para campanhas novas", "⏳ Autonomia Nível 2-3" como item que só migraria de
OUT_OF_SCOPE para IN_SCOPE mediante decisão explícita do Diretor). Essa decisão explícita ocorreu
nesta data.

**Citação literal do Diretor:**
> "Sobre nós deixarmos tudo com, autorização humana, aqui ser lançado. Mas também vamos ter a opção
> do cliente querer escolher deixar no automático. Vamos ter essas duas opções. Aí vai de acordo
> com o cliente, se ele quiser colocar lá um exemplo, determinar um certo valor, e deixar esse
> valor rodando automático, vai ficar pelo expoledor [explorador/operador]. E depois se ele quiser
> deixar no manual, pra ele aprovar cada campanha, também interessa a opção. assim nos coloca à
> frente, está concorrente."

Em resposta à pergunta sobre como tratar o risco (dado que isso é tecnicamente Nível 2/3 de
autonomia, hoje fora do MVP por decisão anterior), o Diretor especificou a salvaguarda:

> "vamos colocar isso agora em funcionamento porém pensando na segurança e na validação essa opção
> de colocar no automático precisará ser validada por senha de adm assim não teremos riscos de
> clientes reclamar que não fez ou que não autorizou a campanha no automático pois provaremos que
> ele inseriu a senha"

**Modelo aprovado:**
- **Modo Manual (Nível 1):** comportamento já especificado — toda campanha passa por aprovação
  humana explícita antes de publicar (F5.2/F5.3/F5.4). Continua sendo a opção padrão.
- **Modo Automático (Nível 2, novo no MVP):** o cliente define um limite (ex: orçamento máximo,
  variação percentual máxima) e, dentro desse limite, o sistema publica/otimiza sem aprovação
  manual por campanha.
- **Salvaguarda obrigatória:** ativar o Modo Automático exige reautenticação por senha do
  administrador da conta no momento da ativação. O evento (quem ativou, quando, com qual limite
  configurado) é registrado de forma imutável no log de auditoria (F9.4), servindo como prova de
  autorização consciente em caso de disputa futura ("o cliente não autorizou").
- O Nível 3 (Operacional — rotinas de baixo risco sem qualquer limite definido pelo cliente)
  **continua fora do MVP** — esta decisão não abrange Nível 3, apenas Nível 2 com limite explícito
  do cliente e validação por senha.

**Impacto nos documentos:**
- `CAMPAIA_PRODUCT_CHARTER.md` §9 — tabela de Níveis de Autonomia atualizada: Nível 2 passa de
  "⏳ Fase 2" para "✅ MVP (com validação por senha de admin)".
- `OUT_OF_SCOPE.md` — remove "❌ Nível 3 no MVP" e "❌ Publicação sem aprovação humana para
  campanhas novas" como universais; adiciona nota de que Nível 2 com senha de admin está dentro do
  MVP, Nível 3 continua fora.
- `docs/product/13_ESPECIFICACAO_TELAS_APP.md` (B8) — nova tela de seleção de modo (Manual vs.
  Automático) e tela de configuração de limites com campo de senha de administrador.

**Rationale:** Diferenciação de mercado — a pesquisa de concorrentes (B8) mostrou que a maioria das
ferramentas é "insight-only" (exige trabalho manual) ou "totalmente autônoma" (sem controle fino do
cliente). Oferecer as duas opções, com a automática protegida por autenticação de administrador,
combina o diferencial de segurança/governança do CampaIA com a conveniência que o mercado já espera
de ferramentas como Revealbot/Madgicx.

**Esclarecimento adicional (05/09/2026) — campanha nova continua sempre manual:**

Ao apresentar o rascunho do B8, o Engenheiro Sênior deixou marcada uma dúvida explícita (não decidiu
sozinho): mesmo com o Modo Automático ativo, uma campanha **nova** (primeira publicação) continuaria
exigindo uma aprovação manual inicial, e só as otimizações posteriores rodariam sozinhas dentro do
limite? Ou a própria ativação do Modo Automático (senha + valor pré-definido) já autorizaria também
a publicação de campanhas novas, sem aprovação adicional?

**Citação literal do Diretor (resposta a essa pergunta):**
> "não o automatico ´so funcionará com aprovação humana mediante senha de adm e valor pre definido"

Diante da formulação ainda poder ser lida de duas formas, o Engenheiro Sênior confirmou o mecanismo
exato com o Diretor via pergunta de múltipla escolha. **Resposta escolhida pelo Diretor: "Campanha
nova sempre manual (Recomendado)"** — ou seja:

- O Modo Automático **nunca** publica uma campanha nova sem uma aprovação manual explícita primeiro.
- A senha de administrador + valor pré-definido (o "aprovação humana mediante senha de adm e valor
  pré-definido" citado pelo Diretor) autoriza exclusivamente a **otimização automática** de campanhas
  que já passaram por pelo menos uma aprovação manual — nunca a criação/publicação inicial de uma
  campanha nova.
- Toda campanha nova continua sujeita à regra já registrada no `CAMPAIA_PRODUCT_CHARTER.md` §9,
  item 1 ("✋ Campanha nova" sempre exige aprovação humana), sem exceção mesmo com o Modo Automático
  ligado.

Isso fecha, sem ambiguidade, a "Nota de configurabilidade" que estava em aberto em
`docs/product/13_ESPECIFICACAO_TELAS_APP.md` §9.1.1.

---

## DECISÕES JÁ APROVADAS (FASE 0)

⚠️ **Nome:** CampaIA — ver DECISION_REGISTER.md D001 (NÃO VERIFICADA — REQUER CONFIRMAÇÃO)
⚠️ **Slogan:** Campanhas inteligentes. Resultados reais. — ver DECISION_REGISTER.md D002 (NÃO VERIFICADA — REQUER CONFIRMAÇÃO)
⚠️ **Independência:** Produto autônomo (repo próprio, sem Kordena) — ver DECISION_REGISTER.md D003 (NÃO VERIFICADA quanto à fonte; operacionalmente adotada)
⚠️ **Diretor:** Fábio Aluizio da Silva — ver DECISION_REGISTER.md D004
⚠️ **Skill:** Marketing AI System Design (obrigatória) — ver DECISION_REGISTER.md D005 (✅ corroborada por artefato hasheado)
⚠️ **Stack:** Flutter, FastAPI, PostgreSQL — ver DECISION_REGISTER.md D010 (NÃO VERIFICADA quanto à fonte)
💭 **Monolítico inicial:** FastAPI modular (PROPOSTA — aguarda aprovação, ver ADR_002)
✅ **Arquitetura do IA Gateway:** aberta, multimodelo, multiprovedor (ver DECISION_REGISTER.md D011 — ✅ APROVADA, corroborada por artefato hasheado desta Fase 0E)
💭 **Fornecedores concretos de IA (OpenAI, Gemini, Claude):** NÃO aprovados — candidatos em avaliação, ver `ADR_004_INITIAL_AI_PROVIDERS.md` (PROPOSTA) e DECISION_REGISTER.md D012

---

## IMPACTOS NOS DOCUMENTOS FASE 1

### Arquivos a Atualizar

1. **FUNCTIONAL_REQUIREMENTS.md**
   - F1 (Onboarding): adicionar "tipo negócio" (select, obrigatório)
   - F2 (Briefing): "objetivo primário" (select) + "objetivos secundários" (checkbox)
   - F3 (Estratégia): adicionar passo "recomendação de canal por objetivo"

2. **CAPABILITY_MATRIX.md**
   - Adicionar coluna "Objetivo recomendado" a cada integração
   - Shopping Ads: avaliar para MVP (se objetivo = vendas)

3. **CAMPAIA_SYSTEM_DESIGN_V1.md**
   - Seção Business Context Agent: adicionar campo "segmento" e "objetivo"
   - Seção Strategist Agent: lógica de seleção de canal por objetivo

4. **OUT_OF_SCOPE.md**
   - Remover linha "Não suporta restaurantes exclusivamente"
   - Adicionar "Fase 2+: verticals específicas com templates pré-customizados"

---

## PRÓXIMAS DECISÕES (ANTES FASE 2)

1. **Modelo comercial:** Qual? (A/B/C/D) — avaliar margem, CAC, LTV
2. **Prioridade canais:** Google vs Meta vs Paralelo?
3. **Feature flags:** Quais capacidades IA controlar via admin (autonomia Level 2+)?
4. **Early access:** Quantos beta users para Fase 1? (recomendação: 10-20)

---

**Status:** PARCIAL — NÃO APROVADA PELO DIRETOR. Ver `docs/execution/DECISION_REGISTER.md` para o estado evidencial atual de cada decisão e `docs/execution/PHASE_0_FINAL_VALIDATION.md` para o status consolidado da Fase 0. Fase 1 não está autorizada.

**Próxima revisão:** Fim de Fase 1 (pesquisa + requisitos detalhados)
