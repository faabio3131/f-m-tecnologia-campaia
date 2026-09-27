# CampaIA — OUT OF SCOPE
**MVP e além - O que NÃO está incluído**

**Data:** 26 de agosto de 2026  
**Status:** IMPLEMENTADO — AGUARDANDO VALIDAÇÃO DO DIRETOR

---

## CANAIS

❌ YouTube Ads  
❌ Display Ads  
❌ Shopping Ads  
❌ LinkedIn Ads  
❌ TikTok Ads  
❌ Pinterest Ads  
❌ Microsoft Ads  
❌ Amazon DSP  
❌ Programmatic Display (externa ao MVP)  

---

## RECURSOS AVANÇADOS DE IA

❌ Fine-tuning automático por tenant  
❌ Modelos customizados privados  
❌ Atribuição causal (multi-touch)  
❌ Recomendação em tempo real via ML  
❌ Previsão de performance (sem histórico suficiente MVP)  
❌ Análise de competidores  
❌ Pesquisa automática de keywords  

---

## AUTONOMIA COMPLETA

❌ Nível 3 no MVP (Operacional — rotinas de baixo risco sem limite definido pelo cliente)
❌ Publicação sem aprovação humana **E** sem limite definido pelo cliente para campanhas novas
❌ Otimizações automáticas agressivas (>10% mudança) além do limite que o próprio cliente configurou
❌ Pausar campanhas automaticamente (sem aviso) fora do limite configurado pelo cliente
❌ Alterar orçamento > 50% sem aprovação, quando isso excede o limite que o cliente definiu no Modo Automático

**Nota (atualizada 05/09/2026 — ver `DECISOES_DIRETOR.md` item 5):** o Nível 2 de autonomia
(Modo Automático, com limite explícito definido pelo próprio cliente e ativação protegida por
senha de administrador) **passou a fazer parte do MVP**. As restrições acima permanecem válidas
para tudo que estiver **fora** do limite que o cliente mesmo configurou — ou seja, o sistema nunca
excede o teto que o cliente autorizou ao ativar o Modo Automático com sua senha. O que continua
fora de escopo é autonomia **sem** limite definido pelo cliente (Nível 3) e qualquer ação que
ultrapasse o limite configurado.

---

## COMERCIALIZAÇÃO

❌ Marketplace de agentes  
❌ Plugins de terceiros  
❌ API pública para integradores  
❌ Reseller program  
❌ Integração com Kordena (revisado após MVP, decisão do Diretor)  

---

## RECURSOS OPERACIONAIS

❌ Multi-user concurrent editing de campanha  
❌ Comentários em tempo real (versão 2)  
❌ Integração com Slack/Teams  
❌ Integração com CRM (HubSpot, Salesforce, etc.)  
❌ Integração com Google Analytics 4  
❌ Import de campanhas existentes (automático)  
❌ Clone de campanha  

---

## FUNCIONALIDADES MOBILE AVANÇADAS

❌ Câmera para upload de assets  
❌ Push notifications (v2)  
❌ Modo offline  
❌ AR preview de ads  

---

## DADOS E ANALYTICS AVANÇADOS

❌ Data warehouse próprio (ClickHouse, Snowflake)  
❌ BI tool embarcado (Looker, Tableau)  
❌ Attribution modeling avançado  
❌ Cohort analysis  
❌ Funnel analysis  
❌ Retention curves  

---

## CONFORMIDADE AVANÇADA

❌ Conformidade GDPR (Europa - futuro)  
❌ Conformidade CCPA (Califórnia - futuro)  
❌ Auditoria SOC 2 (futuro)  
❌ Certificação ISO 27001 (futuro)  

---

## PERFORMANCE E ESCALA

❌ Cache distribuído (Memcached, Redis cluster)  
❌ Read replicas do banco  
❌ Sharding por tenant  
❌ Microserviços (monólito modular inicial)  
❌ Kubernetes (containers simples inicialmente)  
❌ CDN global (futuro)  

---

## O QUE FOI EXPLICITAMENTE DECIDIDO NÃO FAZER AGORA

### ✋ Integrações com Kordena

**Por quê:** Risco de contaminar baseline independente  
**Revisão:** Fase 16+ (após validação de MVP)  
**Aprovação:** Requer decisão expressa do Diretor  

### ✋ Autonomia sem aprovação humana

**Por quê:** Risco financeiro e de compliance inaceitável  
**Baseline:** Nível 1 (Aprovado) — sempre requer aprovação  
**Expansão:** Fases 2-3, com governança rigorosa  

### ✋ Múltiplas dezenas de canais

**Por quê:** Complexidade insurmountável no MVP  
**Baseline:** Google + Meta + WhatsApp  
**Expansão:** Um novo canal por fase, com priorização do Diretor  

### ✋ Atribuição causal avançada

**Por quê:** Requer histórico de dados e modelos complexos  
**Baseline:** Atribuição first-click (implementação simples)  
**Futuro:** Multi-touch quando tivermos 12+ meses de dados  

### ✋ Marketplace de agentes

**Por quwhy:** Risco de execução não-autorizada, compliance, segurança  
**Baseline:** Agentes internos apenas  
**Futuro:** Somente com governance de sandbox + approval workflow  

---

## ESCOPO QUE PODE SER REVISTO

Se o Diretor tomar uma decisão explícita, os seguintes itens podem migrar do OUT_OF_SCOPE para IN_SCOPE:

- ⏳ Integração com Kordena
- ⏳ Autonomia Nível 3 (Nível 2 já migrou para IN_SCOPE em 05/09/2026 — ver `DECISOES_DIRETOR.md` item 5)
- ⏳ YouTube Ads (canal adicional)
- ⏳ Analytics avançado (partnership com BI tool)
- ⏳ Conformidade GDPR
- ⏳ Marketplace de agentes (com governance rigorosa)

**Processo:** ADR formal, aprovação do Diretor, re-planejamento de roadmap.

---

**Status:** IMPLEMENTADO — AGUARDANDO VALIDAÇÃO DO DIRETOR

