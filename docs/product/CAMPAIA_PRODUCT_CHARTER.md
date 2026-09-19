# CampaIA — PRODUCT CHARTER
**Campanhas inteligentes. Resultados reais.**

**Data:** 26 de agosto de 2026  
**Diretor:** Fábio Aluizio da Silva  
**Engenheiro Sênior:** Claude  
**Status:** IMPLEMENTADO — AGUARDANDO VALIDAÇÃO DO DIRETOR

---

> **Nota de reconciliação (19/09/2026, ADR-0016 APROVADA):** a declaração de natureza deste documento foi
> atualizada para refletir a Lei Web First (`docs/nova-fm/00-DOCUMENTO-MESTRE-NOVA-FM-TECNOLOGIA.md` §5),
> adotada após a redação original deste Charter. Público-alvo, proposta de valor, canais, autonomia
> governada, guardrails financeiros e governança permanecem integralmente válidos — nenhum é
> Web-incompatível. Ver `docs/web/00_INDICE_PONTO_ZERO_WEB.md` para o System Design Web correspondente.

## 1. IDENTIDADE DO PRODUTO

**Nome Oficial:** CampaIA  
**Slogan:** Campanhas inteligentes. Resultados reais.  
**Natureza:** Produto Web SaaS independente. A plataforma Web é a linha principal de construção, operação e
evolução do CampaIA (Lei Web First, ADR-0016 aprovada). O aplicativo mobile (Flutter) permanece em
quarentena arquitetural (`docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md`) e poderá futuramente
operar como cliente complementar da plataforma Web, sem jamais substituí-la.  
**Categoria:** Marketing Automation + IA  
**Versão:** 1.0 (MVP)

---

## 2. VISÃO

O CampaIA democratiza a criação, publicação, monitoramento e otimização de campanhas de marketing digital de alto desempenho. Por meio de inteligência artificial governada e aprovação humana obrigatória, empresas de qualquer tamanho conseguem resultados profissionais em minutos, não em dias.

---

## 3. PROBLEMA RESOLVIDO

Hoje, criar uma campanha de marketing envolve:
- ⏱️ Dias de planejamento e pesquisa
- 🤔 Decisões desconexas entre canais
- 💰 Risco de orçamento mal alocado
- 👨‍💼 Necessidade de especialistas em cada plataforma
- 🔍 Dificuldade em aprender com resultados
- 🚫 Falta de governança e aprovações
- 📊 Métricas dispersas

**Solução:** Um assistente inteligente que entende o negócio, propõe estratégia, cria ativos, valida políticas, solicita aprovação e publica — tudo mantendo o humano no comando.

---

## 4. USUÁRIOS-ALVO

### Primário (MVP)
- **Proprietários de restaurantes** e pequenos negócios
- **Gerentes de marketing** de PMEs
- **Agências** que gerenciam múltiplos clientes
- **Empreendedores digitais**

### Perfil
- 25 a 55 anos
- Conhecimento básico a intermediário de marketing digital
- Disposição para aprender
- Orçamentos mensais entre R$ 500 e R$ 50.000

### Futuro
- Qualquer empresa com presença digital
- Franquias
- Cadeias

---

## 5. PROPOSTA DE VALOR

| Aspecto | Benefício |
|---------|-----------|
| **Velocidade** | Ir de briefing para campanha ativa em < 30 minutos |
| **Qualidade** | Textos, imagens e públicos otimizados por IA |
| **Confiabilidade** | Aprovação humana + políticas garantem conformidade |
| **Econômia** | Elimina desperdício de orçamento |
| **Inteligência** | Aprende com resultados e recomenda otimizações |
| **Simplificidade** | Interface mobile intuitiva, sem expertise técnica exigida |
| **Governança** | Trilha de auditoria completa; decisões rastreáveis |

---

## 6. CANAIS SUPORTADOS

### MVP (Fase 1–2)
- ✅ **Google Search Ads** — Anúncios de busca em tempo real
- ✅ **Facebook Ads** — Feed e stories
- ✅ **Instagram Ads** — Feed, stories e reels
- ✅ **Click-to-WhatsApp** — Anúncios de mensagem direta

### Futuro
- YouTube Ads
- LinkedIn Ads
- TikTok Ads
- Pinterest Ads
- Microsoft Ads
- Qualquer plataforma com API pública

---

## 7. PROPOSTA DE NEGÓCIO (MVP)

**Modelo:** Assinatura SaaS  
**Faturamento:** Créditos de IA ou % sobre spend (TBD)  
**Segmentação:** Free, Starter, Pro, Enterprise  
**Horizonte de Receita:** 12–24 meses

> **Nota:** Decisões comerciais devem ser aprovadas explicitamente pelo Diretor.

---

## 8. INDEPENDÊNCIA DO KORDENA

**Declaração:** O CampaIA é um produto independente.

### O que isso significa:

✅ **Código próprio** — Nenhum código compartilhado com Kordena inicialmente  
✅ **Banco próprio** — PostgreSQL independente  
✅ **Autenticação própria** — OAuth próprio (não reutiliza Kordena)  
✅ **Infraestrutura própria** — Containers e cloud independentes  
✅ **Roadmap próprio** — Decisões de produto autônomas  
✅ **Marca própria** — CampaIA tem identidade visual e nome distintos  

### Integração futura com Kordena:

- ❌ **Não autorizada agora**
- ✅ **Possível no futuro** mediante decisão expressa do Diretor
- 📋 **Será tratada como uma integração entre sistemas independentes**
- 🔐 **Manterá isolamento absoluto de dados e tenants**

### Por que?

1. **Risco reduzido** — Falha do CampaIA não afeta Kordena
2. **Evolução independente** — Roadmaps desacoplados
3. **Comercialização flexível** — Pode ser oferecido standalone
4. **Segurança** — Tenants de Kordena não vazam dados para CampaIA

---

## 9. PRINCÍPIOS FUNDAMENTAIS

### Governança
- 🤖 **IA propõe** — Modelo gera recomendações estruturadas
- 👤 **Humano controla** — Usuário aprova antes de publicação
- 🛡️ **Políticas determinam** — Regras de negócio bloqueiam ações indevidas
- 🔌 **Conectores executam** — APIs públicas fazem o trabalho

### Autonomia Governada (Níveis)

| Nível | Descrição | MVP? |
|-------|-----------|------|
| 0 — Assistente | Cria rascunhos; humano publica | ❌ |
| **1 — Aprovado** | Publica após aprovação cada vez | ✅ |
| **2 — Limitado** | Otimiza/publica automaticamente dentro de limites definidos pelo cliente | ✅ **MVP (decisão de 05/09/2026 — requer validação por senha de administrador na ativação, ver `DECISOES_DIRETOR.md` item 5)** |
| 3 — Operacional | Executa rotinas de baixo risco sem limite definido pelo cliente | ⏳ Fase 3 |

**MVP oferece Nível 1 (manual) e Nível 2 (automático com limite, protegido por senha de admin) —
o cliente escolhe qual usar por campanha ou por conta. Nível 3 continua fora do MVP.**

### Ações que SEMPRE exigem aprovação humana

1. ✋ Campanha nova
2. ✋ Aumento relevante de orçamento (> 20%)
3. ✋ Público sensível (menores, saúde, finanças)
4. ✋ Uso de lista de clientes
5. ✋ Mudança de conta de anúncios
6. ✋ Ação irreversível

---

## 10. GUARDRAILS FINANCEIROS

- 💰 **Limite diário por tenant** — Configurable
- 💰 **Limite mensal por tenant** — Configurable
- 💰 **Limite por campanha** — Configurable
- 🚨 **Kill switch** — Pausar qualquer coisa instantaneamente
- 📊 **Alertas** — Notificação em tempo real ao atingir 80% do orçamento

---

## 11. SEGURANÇA E CONFORMIDADE

- 🔐 **OAuth 2.0** — Nenhum login/senha armazenado
- 🔑 **Segredos criptografados** — AWS/GCP Secrets Manager
- 👮 **Multi-tenancy rigorosa** — Isolamento absoluto por tenant
- 📝 **Auditoria imutável** — Toda ação registrada e rastreável
- ⚖️ **LGPD** — Consentimento, opt-out, retenção configurável
- ✅ **Consentimento WhatsApp** — Respeita templates e políticas

---

## 12. AÇÕES NÃO AUTORIZADAS (AGORA)

❌ Reutilizar código do Kordena  
❌ Conectar ao banco do Kordena  
❌ Usar autenticação do Kordena  
❌ Publicar campanhas reais  
❌ Movimentar orçamento real  
❌ Criar credenciais reais (Google, Meta, WhatsApp)  
❌ Deploy em produção  
❌ Integração com Kordena sem aprovação  

---

## 13. DECISÕES APROVADAS (FUNDAÇÃO)

✅ Nome: **CampaIA**  
✅ Slogan: **Campanhas inteligentes. Resultados reais.**  
✅ Independência do Kordena  
✅ Diretor: Fábio Aluizio da Silva  
✅ Uso obrigatório da skill: **Marketing AI System Design**  
✅ Engenheiro Sênior responsável por qualidade e segurança  

---

## 14. DECISÕES PENDENTES (PARA FÁBIO)

1. **Segmento inicial** — Só restaurantes ou qualquer negócio no MVP?
2. **Primeiro objetivo** — Leads, vendas, visitas, mensagens?
3. **Modelo comercial** — Assinatura, pay-per-use, BYOK ou híbrido?
4. **Marca** — CampaIA branca, co-branding com Kordena, ou standalone?
5. **Integração Kordena** — Se/quando integrar, como?
6. **Roadmap** — Prioridade entre Google, Meta, WhatsApp?

---

## 15. PRÓXIMAS FASES

### Fase 0 ✅ (AGORA)
Baseline documental e arquitetural

### Fase 1 (Foundation + MVP)
- Autenticação e multi-tenancy
- Campaign Orchestrator
- AI Model Gateway (OpenAI + Gemini)
- Policy Engine
- Google Search Ads + Meta básico
- Prévia e aprovação
- Dashboard essencial

### Fase 2 (Produção controlada)
- Google Ads completo
- Meta completo
- Click-to-WhatsApp
- Webhooks e métricas
- Alertas financeiros

### Fase 3 (Autonomia limitada)
- Otimizações automáticas
- Seleção multimodelo
- Criação visual avançada
- Aprendizado por tenant

---

## 16. MÉTRICAS DE SUCESSO (MVP)

- ⏱️ **Tempo de campanha** < 30 minutos (de briefing a publicação)
- 📊 **Taxa de aprovação** > 70% das propostas da IA
- 💰 **Redução de desperdício** > 20% vs. baseline
- 👥 **Adoção** > 100 campanhas no mês 1
- 🔒 **Zero violações de segurança**
- 📈 **ROI médio** > 150% do que era antes

---

## 17. REFERÊNCIA

**Documento de autorização:** Ordem Expressa de Execução — CampaIA Fase 0  
**Aprovado por:** Fábio Aluizio da Silva (pendente confirmação)  
**Data de criação:** 26 de agosto de 2026  
**Status:** IMPLEMENTADO — AGUARDANDO VALIDAÇÃO

---
