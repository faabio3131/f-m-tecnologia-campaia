# CAMPAIA — CAPABILITY MATRIX v0.2

**Data da consulta:** 25/08/2026 · **Status:** PARCIAL

**Regra:** nenhuma capacidade é exposta na interface sem estar aqui, com fonte e data. O que não puder ser
comprovado permanece `NÃO VERIFICADO` e não é oferecido ao usuário.

**Classificação de evidência:**
- `OFICIAL` — documentação do próprio provedor, consultada nesta data
- `SECUNDÁRIA` — publicação de terceiro; serve de alerta, não de base de implementação
- `NÃO VERIFICADO` — não consultado

---

## 1. Google Ads

### 1.1 Níveis de acesso do developer token — `OFICIAL`

Fonte: Google Ads API — Access Levels and Permissible Use (página atualizada em 19/08/2026).
Referência de API observada nos links da própria página: **v25**.

| Nível | Alcance | Limite diário de operações | Revisão |
|---|---|---|---|
| Test Account | Somente contas de teste | 15.000/dia | Concedido na inscrição |
| Explorer | Teste **e produção** | 2.880/dia em produção; 15.000/dia em teste | Upgrade automático em alguns casos |
| Basic | Teste e produção | 15.000/dia | ~5 dias úteis |
| Standard | Teste e produção | Ilimitado na maioria dos serviços | ~10 dias úteis |

**Restrições do nível Explorer** (indisponíveis sem Basic/Standard): criação de conta
(`CustomerService.CreateCustomerClient`), gestão de usuários, serviços de planejamento (Keyword Plan,
Audience Insights, Reach Plan) e serviços de faturamento/pagamento.

**Permissible use** (Basic e Standard): criação/gestão de anúncios; somente relatórios; ou pesquisa de
palavras-chave e recomendações. A CAMPAIA precisa da primeira.

**Required Minimum Functionality (RMF):** aplica-se apenas ao nível Standard. Auditoria de conformidade pode
gerar cobrança por não conformidade.

**Brand verification:** opcional; funciona como sinal para acelerar a análise de Basic Access. Em alguns
casos pode ser exigida como pré-requisito.

### 1.2 Impacto direto no produto

| Consequência | Decisão de projeto |
|---|---|
| Token novo começa em Test Account | Fase 5 inteira roda em conta de teste; nenhum gasto real é possível |
| Explorer permite produção com teto de 2.880 operações/dia | A CAMPAIA precisa **contar operações por tenant** e degradar com elegância perto do teto |
| Basic tem alvo de ~5 dias úteis de revisão | Caminho crítico: solicitar cedo |
| RMF só no Standard | Não perseguir Standard antes de ter usuários reais |

### 1.3 `NÃO VERIFICADO` para Google

- versão exata a adotar e política de deprecação de versões;
- quotas por serviço além do limite do token;
- requisitos de Customer Match e restrições por país;
- comportamento de erros parciais em mutações em lote.

---

## 2. Meta (Facebook + Instagram)

### 2.1 Mudança de 04/05/2026 — `OFICIAL` (blog de desenvolvedores da Meta)

O recurso "Ads Management Standard Access" (AMSA) foi renomeado para **Marketing API Access Tier**:

- limite mínimo de chamadas para qualificação reduzido de 1.500 para **500 chamadas nos últimos 15 dias**;
- taxa de erro exigida permanece abaixo de 15%, agora calculada sobre uma janela móvel das últimas 500
  chamadas, em vej de período fixo;
- envio de gravação de tela deixou de ser exigido;
- requisitos passaram a ser exibidos no painel do app;
- não houve mudança de código nem quebra: níveis existentes foram preservados.

### 2.2 Dois portões distintos — atenção

| Portão | O que controla |
|---|---|
| Permissões (`ads_management`, `ads_read`, `business_management`) | Quais operações o app pode executar |
| Marketing API Access Tier | Limites de taxa e alcance no Business Manager |

Confundir os dois é erro comum e custa tempo de aprovação. São mecanismos de aprovação separados.

### 2.3 Impacto direto no produto

| Consequência | Decisão de projeto |
|---|---|
| O tier exige histórico real de chamadas com baixa taxa de erro | A qualidade do adaptador Meta **é pré-requisito da aprovação**: retry, backoff e tratamento de erro são caminho crítico, não refinamento |
| Operar contas de terceiros exige App Review e verificação do negócio | Sem isso, a CAMPAIA só opera contas do próprio Business Manager — que é exatamente o cenário de validação com as contas do Diretor |
| Limites de taxa variam por conta e por gasto | Rate limiting por `external_account`, não global |

### 2.4 Versão vigente — `OFICIAL`

O portal Meta for Developers, consultado em 25/08/2026, indica **Graph API v26.0 e Marketing API v26.0** como
versões correntes, com deprecações e mudanças incompatíveis descritas no changelog da v26.0. Versões
anteriores localizadas: v25.0 (fevereiro/2026), v24.0, v23.0, v22.0.

**Decisão de projeto:** o adaptador Meta fixa a versão em configuração (`api_version`), nunca em código, e
persiste a versão usada em cada recurso externo.

### 2.5 Restrição relevante — `SECUNDÁRIA`, exige confirmação oficial

Publicação de terceiro (fev/2026) atribui à Meta a informação de que, a partir da v25.0, campanhas
**Advantage+ Shopping e Advantage+ App não podem mais ser criadas nem atualizadas pela Marketing API**, com
extensão a versões seguintes. Também menciona substituição da métrica de alcance por métrica de visualizações.

**Se confirmado**, remove tipos de campanha do conjunto oferecível e altera o mapeamento de métricas do
dashboard. **Não implementar nada baseado nisso antes de checar o changelog oficial.** Pendência P-08.

### 2.6 `NÃO VERIFICADO` para Meta

- escopo exato de permissões exigido por operação;
- requisitos de Conversions API, pixel e datasets;
- regras das contas de anúncio de teste e o que de fato simulam;
- disponibilidade por país das configurações pretendidas;
- confirmação oficial do item 2.5.

---

## 3. WhatsApp Business

### 3.1 Fatos de plataforma — `OFICIAL`

- Templates são mensagens pré-construídas que **em geral exigem aprovação** antes do envio.
- Templates possuem pontuação de qualidade e estão sujeitos a limites de mensagens.
- Ao iniciar com a Cloud API, uma conta de teste e um número de teste são criados automaticamente, com
  limites relaxados e sem exigir método de pagamento para enviar templates.
- A Business Management API permite gerenciar números e templates programaticamente e expõe analytics.

### 3.2 Preços e janelas — `OFICIAL` (página de pricing, consultada 25/08/2026)

- **Janela de free entry point:** todas as mensagens, inclusive templates, são gratuitas por 72 horas quando
  enviadas dentro de uma janela de free entry point aberta.
- **Templates são o único tipo de mensagem** que pode ser enviado fora da janela de atendimento para iniciar
  contato com o usuário.
- **A janela de atendimento é independente da de free entry point:** se a de atendimento fechar, só restam
  templates.
- **Categorização de template** existe e é regida por regras próprias da plataforma.

**Mudanças de preço anunciadas com data:** atualizações para mensagens de serviço, utilidade e Meta Business
Agent com lançamento em **1º de agosto de 2026** e **1º de outubro de 2026**.

**Novidade de 2026:** empresas integradas à Marketing Messages API podem definir um **preço máximo por
entrega de mensagem de marketing**.

**Impacto direto:** o modelo de custo do WhatsApp **muda duas vezes dentro do horizonte do projeto**. Preço
não pode ser gravado em código; é dado versionado com data de vigência. Pendência P-09.

### 3.3 Ainda `SECUNDÁRIA` — exigem confirmação oficial

- limite de frequência por usuário para templates de marketing, somando todas as empresas, em janela de 24h;
- exigência de verificação de negócio e URL de política de privacidade antes de enviar templates;
- indisponibilidade de recursos de mensagens em alguns países/regiões;
- ausência de desconto por volume para templates de marketing.

### 3.4 Impacto direto no produto

| Consequência | Decisão de projeto |
|---|---|
| Template exige aprovação prévia | O app precisa de um ciclo assíncrono "criar template → aguardar aprovação → só então usar". Não pode ser prometido como imediato |
| Existe limite de frequência fora do nosso controle | A CAMPAIA **nunca** promete entrega; o estado da mensagem é sempre derivado do provedor |
| Consentimento e opt-out são obrigatórios | Base legal registrada por contato, com opt-out auditável — bloqueia a Fase 7 até D-09 |
| Conta de teste existe desde o início | Fase 7 pode ser desenvolvida sem custo e sem mensagem real |

**Limitação técnica registrada (P-10):** partes da documentação da Meta exigem login e não puderam ser
buscadas diretamente. O marcado como `OFICIAL` veio de conteúdo indexado das páginas oficiais. Confirmação
definitiva exige acesso autenticado ao portal.

---

## 4. Provedores de IA

| Item | Estado |
|---|---|
| OpenAI — saídas estruturadas | `NÃO VERIFICADO` nesta data |
| Gemini — saídas estruturadas | `NÃO VERIFICADO` nesta data |
| Modelos, preços e limites vigentes | `NÃO VERIFICADO` — dependem de D-06 e mudam com frequência |

O contrato canônico do AI Gateway foi desenhado para **não depender** desses detalhes: capacidades por modelo
ficam em registro versionado, carregado por configuração, não por código.

---

## 5. Como esta matriz é usada em runtime

O `capability_registry` é dado, não código:

```
capability(provider, capability_key, api_version, country, account_type)
  → { supported: bool, requires_approval: bool, evidence_url, verified_at, notes }
```

Regras:

1. a interface só oferece ação com `supported = true` para aquela conta, país e versão;
2. capacidade sem `verified_at` recente é tratada como indisponível;
3. quando a API não permite a ação, o app informa isso com clareza e, quando adequado, oferece fluxo
   assistido para o portal oficial — nunca simula sucesso;
4. mudança de capacidade gera evento e entra na auditoria.

Implementado e testado em `backend/campaia_core/infra.py` (`CapabilityRegistry`).

---

## 6. Fontes consultadas em 25/08/2026

- Google Ads API — Access Levels and Permissible Use: https://developers.google.com/google-ads/api/docs/api-policy/access-levels
- Google Ads API — Developer Token: https://developers.google.com/google-ads/api/docs/api-policy/developer-token
- Meta for Developers — atualização do Ads Management Standard Access: https://developers.meta.com/blog/updates-to-ads-management-standard-access-feature/
- Meta for Developers — portal (versão vigente da Graph/Marketing API): https://developers.facebook.com/
- Meta — Marketing API changelog: https://developers.facebook.com/documentation/ads-commerce/marketing-api/marketing-api-changelog
- WhatsApp Business Platform — visão geral: https://developers.facebook.com/documentation/business-messaging/whatsapp/about-the-platform
- WhatsApp Business Platform — pricing: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing
