# CampaIA — REQUISITOS FUNCIONAIS
**Campanhas inteligentes. Resultados reais.**

**Data:** 26 de agosto de 2026  
**Status:** REQUISITOS APROVADOS PARA O ESCOPO DO MVP (Fase 0) — NÃO É UM RASTREADOR DE
IMPLEMENTAÇÃO. Cada "✅ Aprovado" abaixo significa que o requisito foi aceito no escopo do
MVP em 26/08/2026, antes de qualquer código existir — não que o comportamento descrito esteja
construído hoje. **Reconciliado em 22/09/2026** (a formulação original "IMPLEMENTADO —
AGUARDANDO VALIDAÇÃO DO DIRETOR" era objetivamente incorreta já na sua própria data de criação,
já que nenhum código do backend existia em 26/08/2026 — ver `backend/01_PAINEL_EXECUCAO_v31_VIGENTE.md`
"Registro de blocos executados", cujo primeiro bloco de construção real é datado de 27/08/2026).
O status real de implementação de cada capacidade, requisito a requisito, está no painel de
execução vigente (`backend/01_PAINEL_EXECUCAO_v31_VIGENTE.md`) e em
`docs/web/06_ROADMAP_WORK_PACKAGES.md`, não neste documento. Em particular: F1.1 (criar
empresa) e F1.2 (adicionar unidade) não têm endpoint real (nenhuma rota de criação de
tenant/unidade existe — `tenant_id` vem sempre da sessão autenticada); F1.3–F1.5 (conectar
Google Ads/Meta/WhatsApp) usam OAuth **simulado**, nunca uma integração real com provider —
ver `docs/web/11_CERTIFICACAO_WP04_ONBOARDING_BRAND_KIT.md`.

---

## F1. ONBOARDING

### F1.1 Criar empresa
**Ator:** Novo usuário  
**Requisito:** Registrar empresa com nome, CNPJ, segmento, idioma

**Aprovado:** ✅ (requisito base MVP)

### F1.2 Adicionar unidade de negócio
**Ator:** Administrador da empresa  
**Requisito:** Organizar campanha por unidade (filial, marca, região)

**Status:** ✅ Aprovado

### F1.3 Conectar Google Ads
**Ator:** Usuário com permissão  
**Requisito:** OAuth 2.0, lista de contas, seleção de conta  

**Status:** ✅ Aprovado

### F1.4 Conectar Meta
**Ator:** Usuário com permissão  
**Requisito:** OAuth 2.0, Meta Business Account, Ad Accounts  

**Status:** ✅ Aprovado

### F1.5 Conectar WhatsApp
**Ator:** Usuário com permissão  
**Requisito:** WhatsApp Business Account, número comercial, permissões  

**Status:** ✅ Aprovado

---

## F2. BRAND KIT

### F2.1 Criar/editar Brand Kit
**Ator:** Administrador da empresa  
**Requisito:** Logo, cores principais, tom de voz, produtos, diferenciais, restrições

**Status:** ✅ Aprovado

### F2.2 Aplicar Brand Kit a campanhas
**Ator:** Sistema  
**Requisito:** IA consulta Brand Kit ao gerar criativos

**Status:** ✅ Aprovado

---

## F3. BRIEFING

### F3.1 Formulário de briefing
**Ator:** Usuário  
**Requisito:** 
- Objetivo (leads, vendas, visitas, mensagens)
- Oferta/produto
- Público-alvo (descrição ou targeting)
- Região geográfica
- Orçamento total
- Período (datas)
- Materiais disponíveis (textos, imagens, vídeos)

**Status:** ✅ Aprovado

### F3.2 Briefing conversacional
**Ator:** Usuário  
**Requisito:** Chat com IA que faz perguntas e coleta briefing progressivamente

**Status:** 💭 Proposta (Fase 2)

---

## F4. ESTRATÉGIA E CRIAÇÃO

### F4.1 Gerar estratégia
**Ator:** Sistema (AI Gateway)  
**Requisito:** 
- Objetivo confirmado
- Canais recomendados (Google, Meta, WhatsApp)
- Públicos-alvo
- Distribuição de orçamento
- Formato de anúncios por canal
- Variações de mensagem

**Status:** ✅ Aprovado

### F4.2 Gerar textos
**Ator:** Sistema (Copy Agent)  
**Requisito:**
- Títulos
- Descrições
- CTAs
- Variações (A/B)
- Respeitando Brand Kit e políticas

**Status:** ✅ Aprovado

### F4.3 Gerar imagens
**Ator:** Sistema (Creative Agent)  
**Requisito:**
- Imagens por formato (quadrada, story, banner)
- Respeitando cores e tom do Brand Kit
- Texto incorporado quando necessário

**Status:** ✅ Aprovado

### F4.4 Validação de alegações
**Ator:** Sistema (Policy Agent)  
**Requisito:**
- Verificar se textos/imagens violam políticas
- Bloquear categorias proibidas (saúde, finanças, etc. quando aplicável)
- Sugerir ajustes se necessário

**Status:** ✅ Aprovado

---

## F5. PRÉVIA E APROVAÇÃO

### F5.1 Prévia por canal
**Ator:** Usuário  
**Requisito:**
- Visualizar como anúncio aparecerá em Google, Facebook, Instagram, WhatsApp
- Editar textos antes de publicação
- Ajustar públicos manualmente

**Status:** ✅ Aprovado

### F5.2 Aprovar campanha
**Ator:** Usuário com permissão  
**Requisito:**
- Clicar "Aprovar"
- Comentário opcional
- Timestamp de aprovação

**Status:** ✅ Aprovado

### F5.3 Rejeitar com motivo
**Ator:** Usuário com permissão  
**Requisito:**
- Clicar "Rejeitar"
- Motivo obrigatório
- Retornar para rascunho

**Status:** ✅ Aprovado

### F5.4 Solicitar ajustes
**Ator:** Usuário com permissão  
**Requisito:**
- Comentário estruturado (texto, imagem, público, orçamento)
- Retornar para rascunho com feedback

**Status:** ✅ Aprovado

---

## F6. PUBLICAÇÃO

### F6.1 Publicar em Google Ads
**Ator:** Sistema (Campaign Orchestrator)  
**Requisito:**
- Criar campanha
- Criar ad groups
- Upload de assets
- Criar ads
- Set budget
- Ativar campanha

**Status:** ✅ Aprovado

### F6.2 Publicar no Meta
**Ator:** Sistema  
**Requisito:**
- Criar campanha
- Criar ad sets
- Upload de assets
- Criar ads
- Set budget
- Ativar campanha

**Status:** ✅ Aprovado

### F6.3 Publicar Click-to-WhatsApp
**Ator:** Sistema  
**Requisito:**
- Dentro do fluxo Meta (Facebook/Instagram)
- Link para WhatsApp Business
- Mensagem pré-preenchida opcional

**Status:** ✅ Aprovado

### F6.4 Idempotência
**Ator:** Sistema  
**Requisito:**
- Se publicação falhar, retry não duplica
- Gerar IDs externos para deduplicação

**Status:** ✅ Aprovado

---

## F7. MONITORAMENTO

### F7.1 Dashboard de campanhas
**Ator:** Usuário  
**Requisito:**
- Lista de campanhas (ativas, pausadas, finalizadas)
- Status de cada campanha
- Orçamento gasto vs. limite
- Impressões, cliques, conversões

**Status:** ✅ Aprovado

### F7.2 Métricas por campanha
**Ator:** Usuário  
**Requisito:**
- CTR, CPC, CPA, ROAS
- Breakdown por canal
- Breakd own por criativo
- Comparação vs. objetivos

**Status:** ✅ Aprovado

### F7.3 Alertas de limite orçamento
**Ator:** Sistema  
**Requisito:**
- Notificação ao atingir 80% do limite diário
- Notificação ao atingir 100% do limite
- Email e push notification

**Status:** ✅ Aprovado

### F7.4 Alertas de performance
**Ator:** Sistema  
**Requisito:**
- Baixo CTR (<0.5% em Google)
- Alto CPA (>2x objetiv)
- Anomalias

**Status:** 💭 Proposta (Fase 2)

---

## F8. OTIMIZAÇÕES

### F8.1 Sugerir otimizações
**Ator:** Sistema (Performance Agent)  
**Requisito:**
- Aumentar budget se CTR > 2%
- Pausar se CPA > limite
- Ajustar lances se não atingir volume
- Expandir público se CPC muito alto

**Status:** 💭 Proposta (Fase 2)

### F8.2 Executar otimizações automáticas
**Ator:** Sistema (Policy autoriza)  
**Requisito:**
- Ajustes de baixo risco (ajuste de lance <5%, mudança de bid strategy)
- Requer aprovação para mudanças maiores

**Status:** ❌ Out of scope MVP (Fase 3)

---

## F9. HISTÓRICO E AUDITORIA

### F9.1 Histórico de versões
**Ator:** Usuário  
**Requisito:**
- Cada versão da campanha registrada
- Mudanças entre versões destacadas
- Timeline visual

**Status:** ✅ Aprovado

### F9.2 Log de aprovações
**Ator:** Usuário  
**Requisito:**
- Quem aprovou
- Quando
- Comentário (se houver)

**Status:** ✅ Aprovado

### F9.3 Explicação das decisões da IA
**Ator:** Usuário  
**Requisito:**
- Por que este público foi escolhido?
- Por que esta distribuição de orçamento?
- Qual modelo foi usado?

**Status:** ✅ Aprovado

### F9.4 Auditoria completa
**Ator:** Administrador  
**Requisito:**
- Export de audit trail (quem fez o quê, quando, por quê)
- Relatório de conformidade

**Status:** ✅ Aprovado

---

## F10. CONFIGURAÇÕES

### F10.1 Políticas de autonomia
**Ator:** Administrador  
**Requisito:**
- Selecionar nível (0, 1, 2, 3)
- Configurar limites de autonomia

**Status:** ✅ Aprovado (Nível 1 MVP)

### F10.2 Modelos de IA
**Ator:** Administrador  
**Requisito:**
- Escolher modelo padrão (OpenAI ou Gemini)
- Fallback
- BYOK key

**Status:** ✅ Aprovado

### F10.3 Permissões
**Ator:** Administrador  
**Requisito:**
- Atribuir roles (criador, aprovador, visualizador)
- Restringir por canal, orçamento, objetivo

**Status:** ✅ Aprovado

---

## RESUMO

| Requisito | Status |
|-----------|--------|
| Onboarding | ✅ Aprovado |
| Brand Kit | ✅ Aprovado |
| Briefing | ✅ Aprovado (formulário) |
| Estratégia | ✅ Aprovado |
| Criação | ✅ Aprovado |
| Validação | ✅ Aprovado |
| Prévia | ✅ Aprovado |
| Aprovação | ✅ Aprovado |
| Google Ads | ✅ Aprovado |
| Meta | ✅ Aprovado |
| WhatsApp | ✅ Aprovado |
| Dashboard | ✅ Aprovado |
| Métricas | ✅ Aprovado |
| Alertas (orçamento) | ✅ Aprovado |
| Histórico | ✅ Aprovado |
| Auditoria | ✅ Aprovado |
| Configurações | ✅ Aprovado |

**Total MVP: 22 requisitos**  
**Total Futuro: 4 requisitos**

---

**Status:** REQUISITOS APROVADOS PARA O ESCOPO DO MVP (Fase 0) — ver nota de reconciliação no
topo deste documento. Status real de implementação: `backend/01_PAINEL_EXECUCAO_v31_VIGENTE.md`.

