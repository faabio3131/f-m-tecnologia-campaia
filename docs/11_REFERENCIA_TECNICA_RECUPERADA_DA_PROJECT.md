# CAMPAIA — Referência técnica recuperada da Project do claude.ai

**Data:** 27 de agosto de 2026
**Autor:** Claude (Engenheiro Sênior)
**Natureza deste documento:** não contém nenhuma decisão nova do Diretor. É uma cópia curada de 5 peças de documentação técnica que existiam **apenas** na Project do claude.ai "APP Marketing" (não sincronizada a este Drive — ver `docs/evidence/ACHADO_DIVERGENCIA_PROJETO_CLAUDE_20260827.md`) e que não tinham equivalente em nenhum documento deste Drive. Salvo aqui, no local oficial, antes de o Diretor decidir o destino do conteúdo divergente da Project.

**Status de cada peça:** rascunho técnico de referência, nunca implementado nem aprovado como decisão — mesmo status que tinha na Project (`PARCIAL`/`PROPOSTA`). Onde este material conflitar com uma decisão real já tomada no Drive (ex.: `03_ADR_INICIAIS.md`, `04_DECISOES_DO_DIRETOR.md`, `09_ADR_0013...md`), **a decisão do Drive prevalece** — este documento é só uma base de trabalho a ser conciliada, não uma fonte de autoridade paralela.

---

## 1. MATRIZ RBAC/ABAC — OPERAÇÃO POR OPERAÇÃO

Fonte original: Project `campaia/docs/security/AUTHORIZATION_MODEL.md` (26/08/2026). O Drive já decidiu usar RBAC + ABAC como modelo (ver `07_THREAT_MODEL.md`, `09_ADR_0013...md`) e já tem `permissions.py` implementado e testado em `backend/campaia_core/` — mas não tinha, em nenhum documento, a matriz detalhada operação-por-operação abaixo.

### 1.1 Papéis base

| Role | Descrição | Campanhas | Aprovação | Orçamento | Admin |
|------|-----------|-----------|-----------|-----------|-------|
| **Admin** | Gerente de tenant (todas as permissões) | CRUD | Aprova todas | Define tetos | Full |
| **Creator** | Cria e edita campanhas | CRUD (próprias) | Solicita | Visualiza | Não |
| **Approver *| Aprova campanhas; monitora gasto | R (todas) | ✅ Aprova | Define tetos | Não |
| **Viewer** | Acesso somente leitura (analítico) | R (todas) | Não | Visualiza | Não |

*Nota de conciliação: o Drive já usa uma lista de papéis um pouco mais rica em outros pontos (ex. menção a "6 papéis" em painéis de execução). Esta tabela de 4 papéis é a versão original da Project — precisa ser expandida/reconciliada com o modelo de 6 papéis já referenciado no Drive antes de virar especificação final.*

### 1.2 Ciclo de vida da campanha

| Operação | Creator | Approver | Admin | Viewer | Regra |
|----------|---------|----------|-------|--------|--------|
| Criar campanha | ✅ | ✅ | ✅ | ❌ | tenant_id match |
| Editar rascunho | ✅ (própria) | ✅ | ✅ | ❌ | owner_id match ou admin |
| Editar validada | ❌ | ✅ | ✅ | ❌ | approver+ role |
| Solicitar aprovação | ✅ | N/A | N/A | ❌ | stage = VALIDATED |
| Aprovar campanha | ❌ | ✅ | ✅ | ❌ | role = approver+ |
| Rejeitar campanha | ❌ | ✅ | ✅ | ❌ | approver+ pode negar |
| Publicar (executar) | ❌ | ✅ (pós-aprovação) | ✅ | ❌ | após APPROVED state |
| Pausar campanha | ✅ (própria) | ✅ | ✅ | ❌ | owner ou approver+ |
| Deletar campanha | ✅ (rascunho) | ✅ | ✅ | ❌ | stage = DRAFT ou CANCELLED |
| Visualizar insights | ✅ (própria) | ✅ | ✅ | ✅ (read-only) | tenant_id match |
| Ajustar orçamento | ❌ | ✅ (até limite) | ✅ | ❌ | approver+ e within_budget_limit |

### 1.3 Orçamento e financeiro

| Operação | Creator | Approver | Admin | Viewer |
|----------|---------|----------|-------|--------|
| Visualizar gasto | ✅ (próprio) | ✅ (todo tenant) | ✅ | ✅ (read-only) |
| Definir teto mensal | ❌ | ❌ | ✅ | ❌ |
| Definir teto campanha | ❌ | ✅ | ✅ | ❌ |
| Exceder teto autorizado | ❌ | ❌ | ✅ (com auditoria) | ❌ |
| Visualizar faturas | ❌ | ❌ | ✅ | ❌ |

### 1.4 Usuários e administração

| Operação | Creator | Approver | Admin | Viewer |
|----------|---------|----------|-------|--------|
| Convidar usuário | ❌ | ❌ | ✅ | ❌ |
| Alterar role de usuário | ❌ | ❌ | ✅ | ❌ |
| Deletar usuário | ❌ | ❌ | ✅ | ❌ |
| Auditar logs | ❌ | ❌ | ✅ | ❌ |
| Configurar webhooks | ❌ | ❌ | ✅ | ❌ |

### 1.5 Integrações (Google Ads, Meta, WhatsApp)

| Operação | Creator | Approver | Admin | Viewer |
|----------|---------|----------|-------|--------|
| Conectar conta externa | ❌ | ❌ | ✅ | ❌ |
| Revisar permissões OAuth | ❌ | ❌ | ✅ | ❌ |
| Desconectar conta | ❌ | ❌ | ✅ | ❌ |
| Validar credenciais | ❌ | ❌ | ✅ | ❌ |

### 1.6 Regras de negação (denial rules)

Negar autorização se: tenant não ativo/suspenso; orçamento exaurido no mês; usuário admin sem MFA; campanha viola política (LGPD, Google, Meta, WhatsApp); tentativa de acesso cross-tenant sem autorização explícita; IP de origem suspeito (geolocalização incompatível); taxa de tentativas falhadas acima do limiar.

### 1.7 Fluxo de aprovação

```
Campaign → Solicitar Aprovação
         → Approver é avisado (email, in-app)
         → Approver valida (conteúdo, orçamento, público)
         → ✅ Aprova  → Campaign → PUBLISHING
         → ❌ Rejeita → Campaign → DRAFT (feedback para Creator)
         → ⏱️ Timeout → Campaign → EXPIRED (Creator reenvia)
```

SLO de aprovação proposto: < 4 horas em dias úteis; < 24 horas em fins de semana.

---

## 2. ROTAÇÃO DE SEGREDOS E RESPOSTA A VAZAMENTO

Fonte original: Project `campaia/docs/security/SECRETS_AND_CREDENTIALS.md` (26/08/2026). O Drive já decidiu a arquitetura de segredos (`SecretRef` em `connectors.py`, cofre gerenciado — GCP Secret Manager conforme ADR-0009) mas não tinha, em nenhum lugar, um cronograma de rotação nem um plano de resposta a vazamento.

### 2.1 Cronograma de rotação proposto por tipo de segredo

| Tipo | Rotação proposta | Crítico |
|------|-------------------|---------|
| Chave privada JWT | 180 dias | 🔴 Sim |
| OAuth Client Secrets | 90 dias | 🔴 Sim |
| Chaves de API (Google, Meta, provedores de IA) | 90 dias | 🔴 Sim |
| Senhas de banco de dados | 180 dias | 🔴 Sim |
| Senhas do Redis | 180 dias | 🔴 Sim |
| Chaves de acesso a storage de objetos | 90 dias | 🔴 Sim |
| Credenciais SMTP | 90 dias | 🟡 Importante |
| Chaves de criptografia (KMS) | Não rotaciona | 🔴 Sim |

*Nota: estes números são um ponto de partida proposto pela Project, não uma decisão do Diretor. `SECURITY_FOUNDATIONS.md`/`THREAT_MODEL.md` do Drive já mencionam "rotação 90d (API)" como referência geral — este cronograma detalha isso por tipo de segredo, mas precisa ser formalmente adotado (ou ajustado) como decisão antes de virar política.*

### 2.2 Procedimento de resposta a segredo comprometido

1. **Detectar** — alerta de monitoramento por padrão de uso anômalo de API.
2. **Isolar** — revogar o segredo no cofre gerenciado (meta: menos de 1 segundo).
3. **Rotacionar** — gerar novo segredo automaticamente.
4. **Invalidar** — chamar a API do provedor para desabilitar a chave antiga.
5. **Auditar** — registrar todos os acessos desde a detecção do comprometimento.
6. **Notificar** — alertar a equipe de operações e, se aplicável, o cliente afetado.

**SLO proposto:** revogação em menos de 5 minutos.

### 2.3 Fluxo de refresh de token OAuth

Tokens OAuth (Google Ads, Meta, WhatsApp) devem ser renovados automaticamente antes de expirar (janela de segurança proposta: renovar se restar menos de 1 hora de validade), armazenados sempre criptografados no banco (nunca em texto plano), nunca no cofre de segredos genérico (que é reservado a credenciais de plataforma, não de cliente — distinção já formalizada no Drive via ADR-0013).

---

## 3. SCHEMA DE LOG DE AUDITORIA (FORMATO PROPOSTO)

Fonte original: Project `campaia/docs/security/TENANT_ISOLATION.md` e `AUTHORIZATION_MODEL.md` (26/08/2026). O Drive já tem a decisão de auditoria append-only (`06_MODELO_DADOS.md`, tabela `audit_events`) mas não tinha um formato de campo proposto para o log em si.

Formato JSON proposto para eventos de autorização/acesso:

```json
{
  "timestamp": "2026-08-26T14:30:00Z",
  "action": "create_campaign",
  "user_id": "user-123",
  "tenant_id": "tenant-456",
  "role": "creator",
  "result": "ALLOWED",
  "reasoning": "role >= creator AND tenant_active AND budget_available",
  "campaign_id": "campaign-789",
  "audit_trail_id": "audit-uuid"
}
```

Formato proposto para tentativa de acesso cross-tenant negada:

```json
{
  "timestamp": "2026-08-26T14:30:00Z",
  "event": "campaign_access_denied",
  "user_id": "user-b-123",
  "tenant_id": "tenant-b-uuid",
  "attempted_resource": "campaign-a-789",
  "reason": "RLS_POLICY_VIOLATION",
  "severity": "WARN",
  "action_taken": "access_denied"
}
```

Formato proposto para acesso a segredo:

```json
{
  "timestamp": "2026-08-26T14:30:00Z",
  "action": "secret_access",
  "secret_name": "/campaia/production/api_key_openai",
  "accessed_by": "campaia-backend-service",
  "status": "SUCCESS",
  "audit_trail_id": "audit-uuid"
}
```

Regra geral: logs de auditoria nunca deletáveis; retenção mínima de 2 anos (compatível com LGPD).

---

## 4. MATRIZ DE RASTREABILIDADE DE REQUISITOS (FERRAMENTA DE GESTÃO)

Fonte original: Project `campaia/docs/execution/REQUIREMENTS_TRACEABILITY_MATRIX.md` (26/08/2026) — 41 requisitos funcionais organizados em 10 seções (F1 Onboarding, F2 Brand Kit & Conexões, F3 Briefing & Estratégia, F4 Criação de Ativos, F5 Aprovação & Prévia, F6 Publicação, F7 Monitoramento & Métricas, F8 Otimizações, F9 Histórico & Auditoria, F10 Configurações & Governança), cada um com: origem, estado, componente(s) responsável(is), risco, teste planejado e gate de fase.

**O que preservar não é o conteúdo linha-a-linha** (a maior parte dos requisitos individuais já está coberta, de forma dispersa, pelos documentos `02_PLANO_MESTRE.md`, `05_ARQUITETURA_V2.md`, `06_MODELO_DADOS.md` e pelo roadmap de fases do Drive) **mas o formato da ferramenta em si** — uma matriz única que cruza requisito → componente → risco → teste → gate → aprovação, útil para acompanhamento de execução. Resumo da estrutura original, para recriação futura caso o Diretor queira essa ferramenta de gestão:

| Convenção de coluna | Significado |
|---|---|
| ID | Identificador do requisito (ex.: F1.1) |
| Requisito | Descrição em linguagem natural |
| Origem | Documento/decisão de onde vem |
| Estado | ✅ Invariante / 💭 Proposto / 🔄 Verificação Fase 1 / 📋 Futuro |
| Componente(s) | Partes da arquitetura que implementam |
| Risco | Risco técnico ou comercial |
| Teste Planejado | Como será validado |
| Gate | Qual fase gateia a aprovação |
| Aprovação | Status formal de aprovação do Diretor |

Contagem original (26/08/2026, hoje desatualizada pelo avanço real do projeto): 41 requisitos rastreáveis, 3 invariantes, 2 aprovados, 28 propostos, 6 em verificação de Fase 1, 2 futuros, 1 ambíguo.

**Recomendação:** se o Diretor quiser manter esse tipo de matriz viva, ela precisa ser reconstruída a partir do estado real e atual do Drive (não copiada tal como está, que já reflete um estágio anterior do projeto) — está listada aqui como referência de formato, não como conteúdo pronto para uso.

---

## 5. TABELA DE PREÇOS DE MODELOS DE IA (PESQUISA DE 26/08/2026 — BAIXA PRIORIDADE, VALIDADE CURTA)

Fonte original: Project `campaia/docs/execution/PHASE1_RESEARCH_FINDINGS.md` §4. Preservado apenas como registro histórico de pesquisa de mercado — o Drive optou deliberadamente (ADR-0005, arquitetura de gateway multimodelo) por não fixar nomes/preços de modelo de IA na documentação de decisão, exatamente para não acoplar a arquitetura a uma tabela que envelhece rápido. Este registro é só para consulta eventual, não para reincorporar como fato atual sem reconfirmação.

| Fornecedor | Nível de entrada | Nível intermediário | Nível topo | Geração de imagem nativa | Embeddings nativos | Moderação dedicada |
|---|---|---|---|---|---|---|
| OpenAI | GPT-5.6 Luna — $0,20 / $1,20 por MTok | GPT-5.6 Terra — $2 / $12 por MTok | GPT-5.6 Sol — ~$4-5 / $20 por MTok | Sim | Sim | Sim (gratuita) |
| Google Gemini | Gemini 3.5 Flash-Lite — $0,30 / $2,50 por MTok | Gemini 3.6/3.7 Flash — $0,75 / $3,75 por MTok (promocional até 31/12/2026) | Gemini 3.1 Pro — $2-4 / $12-18 por MTok | Sim | Sim | Não (via prompt) |
| Anthropic Claude | Claude Haiku 4.5 — $1 / $5 por MTok | Claude Sonnet 5 — $2 / $10 por MTok | Claude Opus 5 — $5 / $25; Fable 5/Mythos 5 — $10 / $50 | Não | Não | Não (via prompt) |

**Nota de validade:** pesquisa de 26/08/2026, nomes e preços de modelo de IA mudam com frequência — reconfirmar diretamente na documentação oficial de cada fornecedor antes de qualquer decisão comercial que dependa desses números.

---

## PRÓXIMO PASSO

Com este material preservado aqui, no Drive oficial, a Project do claude.ai "APP Marketing" pode ter seu conteúdo divergente apagado sem perda real — resta apenas a decisão do Diretor sobre isso (ver `docs/evidence/ACHADO_DIVERGENCIA_PROJETO_CLAUDE_20260827.md`, Seção "Recomendação").
