# CampaIA — NON-FUNCTIONAL REQUIREMENTS

**Data:** 26 de agosto de 2026  
**Status:** NÃO VERIFICADO (requer Fase 1 — pesquisa oficial de APIs e provadores)  
**Aplicável a:** Todas as 16 fases

---

## 1. PERFORMANCE

### 1.1 Latência de API

| Operação | SLO | Notas |
|----------|-----|-------|
| Autenticação (login) | < 2s | OAuth 2.0 flow |
| Briefing submission | < 1s | Recepção e persistência |
| Strategy generation | < 10s | IA Gateway — capacidade `structured_reasoning`; fornecedor a definir via ADR_004 |
| Creative generation | < 15s | Texto + imagens estruturadas |
| Campaign preview | < 2s | Dados em cache + template |
| List campaigns | < 500ms | Paginação 50 itens |
| Fetch insights | < 3s | Agregação multi-canal |
| Publish campaign | < 5s | Coordenação Saga (não inclui IA) |

### 1.2 Throughput (marcos de roadmap comercial interno — capacidade ainda não comprovada)

**Nota (atualizada 26/08/2026 — ver `OPEN_QUESTIONS.md` Q6, fechada):** os números abaixo **não são apenas** hipótese livre de dimensionamento arquitetural. O Diretor confirmou que são **marcos de crescimento do roadmap comercial interno** — metas de negócio que a empresa pretende atingir nos prazos de fase planejados, e que a arquitetura precisa ser capaz de suportar quando esses marcos forem alcançados. **Não são**, por outro lado, um contrato/SLA assinado com cliente externo específico, nem uma promessa formal e datada a investidor/sócio — são compromisso interno de negócio, não obrigação externa com terceiros. Fonte: `docs/execution/evidence_sources/DIRETOR_RESPOSTA_Q6_THROUGHPUT_20260826.md`, SHA-256 `e900b64e50ea53d04b8db02a14992554ae63558fe8b28bc616752101ba79e66f`; registrado em `DECISION_REGISTER.md` D020.

Isso **não** muda o estado técnico: nenhuma carga real foi testada nesta fase (Fase 0 é puramente documental) e a capacidade real do sistema para sustentar esses números continua `NÃO VERIFICADO`. O que muda é a prioridade — a arquitetura deve ser desenhada, desde já, para tornar esses marcos alcançáveis nos prazos de fase indicados, não apenas "tratados como referência ilustrativa". Serão revisados com testes de carga reais em Fase 5+ (ver `TEST_STRATEGY.md` §6).

- **Marco de roadmap MVP (Fase 5):** 100 campanhas simultâneas em criação
- **Marco de roadmap Fase 8:** 1.000 campanhas
- **Marco de roadmap Fase 12:** 10.000 campanhas com otimização automática

**Pressupostos por trás destas metas:** crescimento de base de tenants proporcional ao roadmap comercial (assinatura, ver `DECISOES_DIRETOR.md`); nenhum dado real de adoção existe ainda para calibrar estes números — a natureza de "marco de negócio" não substitui a necessidade de validação técnica em Fase 5+.

### 1.3 Concorrência (metas hipotéticas de dimensionamento)

- Múltiplos usuários por tenant (sem limite arquitetural definido; não testado)
- Múltiplos tenants simultâneos (meta hipotética: escalabilidade linear até 1.000 tenants — não testado)
- Meta hipotética: até 10 requisições paralelas por usuário sem degradação — não testado

---

## 2. CONFIABILIDADE

### 2.1 Disponibilidade

| Ambiente | SLA | Tolerância |
|----------|-----|-----------|
| Produção | 99.9% | 9 horas/mês |
| Sandbox | 99.5% | 36 horas/mês |
| Development | N/A | Indisponibilidade aceitável |

### 2.2 Tolerância a Falhas

- **Timeout de workflow:** 30 minutos (Saga multicanal)
- **Retry automático:** 3 tentativas com backoff exponencial
- **Circuit breaker:** Desabilitar connector após 5 erros consecutivos
- **Fallback:** Fila persistente para publicações que falham

### 2.3 Durabilidade de Dados

- **RPO (Recovery Point Objective):** < 5 minutos (backup incremental)
- **RTO (Recovery Time Objective):** < 1 hora (restauração de backup)
- **Replicação:** Ativada para PostgreSQL em produção (Fase 16)

---

## 3. ESCALABILIDADE

### 3.1 Armazenamento

| Recurso | Fase 5 | Fase 12 | Fase 16 |
|---------|--------|---------|---------|
| Campaigns | 50 KiB (avg metadata) | 500 KiB | 5 MiB |
| Assets (images) | S3: 10 GB | S3: 100 GB | S3: 1 TB |
| Audit logs | 1 GB | 10 GB | 100 GB |
| Metrics (timeseries) | 5 GB (30 dias) | 50 GB (90 dias) | 500 GB (365 dias) |

**Estratégia:** Dados quentes em PostgreSQL; dados frios em S3 com arquivo anual.

### 3.2 Computação

- **Backend:** Escala horizontal (containers stateless)
- **IA Gateway:** Load balancing por provider (OpenAI, Gemini, Claude)
- **Workers:** Autoscale conforme fila de eventos

### 3.3 Rede

- **Rate limits:** Implementar rate limiting por tenant (100 req/min MVP → 10.000 req/min Fase 12)
- **Bandwidth:** Não impor limite (cloud-agnostic)

---

## 4. SEGURANÇA

### 4.1 Autenticação

- **Padrão:** OAuth 2.0 (Authorization Code Flow)
- **MFA:** Obrigatória para admins (TOTP ou WebAuthn)
- **Sessão:** JWT com TTL 24 horas; refresh token com TTL 30 dias
- **Session fixation:** Invalidar tokens antigos ao fazer login

### 4.2 Autorização

- **Modelo:** RBAC + ABAC
- **Roles:** Admin, Creator, Approver, Viewer (customizável por tenant)
- **Atributos:** tenant_id, unit_id, user_id, campaign_stage, budget_level
- **Enforcement:** RBAC em API; RLS em PostgreSQL (row-level security)

### 4.3 Encriptação

- **Em trânsito:** TLS 1.3 (HTTPS everywhere)
- **Em repouso:** AES-256 para chaves OAuth, API keys, segredos (AWS Secrets Manager / GCP Secret Manager)
- **Dados do usuário:** Criptografia a nível de aplicação para PII (LGPD)

### 4.4 Secrets Management

- **Armazenamento:** AWS/GCP Secrets Manager (não in-code)
- **Rotação:** 90 dias para OAuth tokens; 6 meses para JWT keys; 90 dias para API keys
- **Auditoria:** Todos os acessos a secrets auditados (imutável)

### 4.5 Validação de Entrada

- **JSON Schema:** Validar todos os inputs contra schema published
- **Sanitização:** Remover HTML/JS de text inputs
- **Rate limiting:** Por endpoint + por usuário
- **CORS:** Configurar whitelist por ambiente

### 4.6 Proteção contra Ataques

- **CSRF:** Token CSRF em todas as mutações
- **SQL Injection:** Prepared statements; ORM (SQLAlchemy)
- **XSS:** Content Security Policy (CSP) header
- **DDoS:** Rate limiting + WAF (cloud provider)
- **Secrets in logs:** Sanitizar logs (nunca expor tokens, API keys, prompts sensíveis)

---

## 5. CONFORMIDADE

### 5.1 LGPD (Lei Geral de Proteção de Dados)

- **Consentimento:** Explícito antes de armazenar dados pessoais
- **Finalidade:** Declarar uso permitido (marketing, analytics, compliance)
- **Retenção:** Configurável por tenant (default 2 anos)
- **Direito ao esquecimento:** Deletar all PII do usuário em < 30 dias (manual + automatizado)
- **Portabilidade:** Exportar dados do usuário em JSON (Fase 2+)
- **Transparência:** Privacy policy + Data Processing Agreement

### 5.2 Google Ads Policies

- Status: `NÃO VERIFICADO` (requer Fase 1 pesquisa oficial)
- Requerimentos planejados:
  - Política anti-discriminação
  - Política anti-manipulação
  - Documentação de todas as campanhas criadas por IA

### 5.3 Meta Ads Policies

- Status: `NÃO VERIFICADO` (requer Fase 1 pesquisa oficial)
- Requerimentos planejados:
  - Aprovação de conteúdo para públicos sensíveis
  - Compliance com política de transparência de anúncios políticos (se aplicável)

### 5.4 WhatsApp Business Policies

- Status: `NÃO VERIFICADO` (requer Fase 1 pesquisa oficial)
- Requerimentos planejados:
  - Opt-in confirmado antes de enviar mensagens
  - Respeitar opt-out (SAIR)
  - Templates aprovados apenas
  - Não spam (volume rates)

---

## 6. OBSERVABILIDADE

### 6.1 Logging

- **Estratégia:** Centralized logging (ELK / CloudLogging)
- **Retention:** 30 dias hot; 90 dias cold archive
- **Sanitização:** Nunca logar tokens, passwords, API keys, PII, prompts sensíveis
- **Estrutura:** JSON com timestamp, level, service, trace_id, user_id, tenant_id, message

### 6.2 Tracing

- **Padrão:** OpenTelemetry (distributed tracing)
- **Sampling:** 10% em produção; 100% em sandbox
- **Context propagation:** W3C Trace Context headers

### 6.3 Métricas

- **Sistema:** CPU, RAM, disk, network I/O (cloud provider metrics)
- **Aplicação:** Latency, throughput, error rates, cache hit rates por endpoint
- **IA Gateway:** Token usage, provider latency, fallback frequency, cost
- **Campaigns:** Creation rate, approval rate, publication rate, success rate

### 6.4 Alertas

- **Critical:** Serviço down, DB unavailable, IA provider down
- **Warning:** High error rate (> 1%), high latency (> SLO), quota threshold (> 80%)
- **Info:** Notable events (large campaign created, autonomy level changed)

---

## 7. MANUTENIBILIDADE

### 7.1 Versionamento de API

- **Estratégia:** Versioning por URI (`/api/v1/`, `/api/v2/`)
- **Deprecation:** Avisar 6 meses antes; suportar 2 versões simultâneas
- **Changelog:** Documentar breaking changes em CHANGELOG.md

### 7.2 Backward Compatibility

- **DB migrations:** Sempre suportar reversão (rollback)
- **Contracts:** Adicionar campos opcionais; nunca remover obrigatórios
- **Eventos:** Adicionar versioning a schemas de evento

### 7.3 Deployment

- **Estratégia:** Blue-green deployment (zero downtime)
- **Frequency:** Até 1x por dia (após testes em sandbox)
- **Rollback:** Automático se erro rate > 5% em 5 minutos

### 7.4 Testing

- **Cobertura:** Unit tests (80%+), integration tests (cloud endpoints), E2E (user journeys)
- **CI/CD:** Toda PR passa testes antes de merge
- **Staging:** Teste completo em sandbox antes de produção

---

## 8. COMPATIBILIDADE

> **Nota de reconciliação (19/09/2026, ADR-0016 APROVADA):** a Web (§8.3) é a linha principal de
> compatibilidade do CampaIA, não uma fase futura. O mobile (§8.1) permanece em quarentena arquitetural
> (`docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md`).

### 8.1 Mobile (Flutter) — quarentena arquitetural, cliente complementar futuro

- **Versões mínimas:** iOS 13+, Android 8+
- **Tamanho do APK:** < 150 MB (incluindo assets)
- **Conectividade:** Suportar offline caching de dados não-críticos
- Não é a linha principal de construção do CampaIA; requisitos acima preservados como referência para uma
  eventual saída de quarentena, não como compatibilidade ativa nesta fase.

### 8.2 Backend (Python/FastAPI)

- **Python:** 3.13+ (LTS supportado)
- **Dependências:** Pinned versions em requirements.txt
- **Compatibilidade:** Cloud-agnostic (Docker + Kubernetes)

### 8.3 Navegadores (Web — linha principal do produto)

- **Suportados:** Chrome 100+, Firefox 100+, Safari 15+
- **Responsividade:** abordagem "mobile-first" de breakpoints CSS (< 1280px, 1280-1920px, > 1920px) —
  convenção de design responsivo (do menor para o maior breakpoint), não relacionada à natureza do produto

---

## 9. RESILIÊNCIA

### 9.1 Graceful Degradation

- **IA indisponível:** Carregar estratégia do template (não gerar novo)
- **Insights indisponíveis:** Mostrar último snapshot conhecido
- **Google Ads indisponível:** Fila campaign para retry automático

### 9.2 Fallback Chain

- **IA:** Fornecedor primário habilitado → fornecedor(es) de fallback habilitados → template default (ordem exata de fornecedores depende de ADR_004, estado PROPOSTA, e de pesquisa oficial de Fase 1 — nenhum fornecedor está habilitado nesta fase)
- **Contas externas:** Last known state enquanto reconectando
- **Webhooks:** Retry com backoff até 3 dias

---

## 10. CUSTO E GOVERNANÇA

### 10.1 Limites de Consumo (por plano)

| Plano | Campanhas/mês | IA tokens/mês | Budget máximo |
|-------|-------------------|-----------------|----------------|
| Starter | 10 | 50 K | R$ 5.000 |
| Professional | 50 | 500 K | R$ 50.000 |
| Enterprise | Ilimitado | Ilimitado | Customizável |

**Enforcement:** Policy Engine valida contra plan_tier antes de ação.

### 10.2 Cost Tracking

- **Por tenant:** Agregado diário (campanhas, tokens IA, APIs)
- **Por provedor IA:** OpenAI, Gemini, Claude usage + cost
- **Alertas:** Avisar ao 50%, 75%, 90% do limite

---

## STATUS FASE 0

`NÃO VERIFICADO` — Requisitos não-funcionais estruturados conforme arquitetura-base.md. Fase 1 validará com pesquisa oficial de APIs e provedores.

**Próximo passo:** Fase 1 — Pesquisa e confirmação com Google, Meta, WhatsApp, OpenAI, Google Cloud, Anthropic.
