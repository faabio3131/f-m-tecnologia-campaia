# CampaIA — Ponto Zero Web · 02. Definição do Ponto Zero Web e Requisitos

**Status:** TARGET PROPOSTO — não aprovado. Subordinado a `01_CURRENT_E_MATRIZ_CURRENT_TARGET.md`.

---

## 1. Definição do Ponto Zero Web

O **Ponto Zero Web** é o estado em que o CampaIA possui uma base arquitetural Web completa, documentada, revisada e apta a iniciar implementação — **sem que a implementação em si tenha começado**.

### 1.1 O que preservar
Todo o domínio em `campaia_core/` (19 módulos), o BFF/API em `backend/api/` (21 rotas), o DDL Postgres verificado, os contratos (OpenAPI, AsyncAPI, JSON Schemas), a suíte de 267+81 testes, o fiscal handoff fail-closed, e os documentos de produto (Charter, FR, NFR, Out of Scope, Especificação de Telas) como fonte funcional.

### 1.2 O que adaptar
- `CAMPAIA_PRODUCT_CHARTER.md` e `NON_FUNCTIONAL_REQUIREMENTS.md`: a declaração de "Natureza: Aplicativo mobile" e o tratamento de Web como Fase 12 estão superados pela Lei Web First (ver `01_CURRENT_E_MATRIZ_CURRENT_TARGET.md` §4.1 e ADR-0016). Atualização formal é `PENDÊNCIA` de decisão humana, fora do escopo de execução desta missão.
- Autenticação: hoje é um token fixo de teste (`api/deps.py`); TARGET é sessão Web real (ADR-0018).
- Persistência: hoje SQLite é opcional; TARGET é Postgres como banco padrão de todo ambiente além de desenvolvimento local.

### 1.3 O que criar
Frontend Web completo (inexistente), camada de sessão/autenticação Web, adaptadores reais de Google Ads/Meta/WhatsApp (hoje só contrato + simulador), observabilidade, pipeline de CI/CD além do workflow de testes atual.

### 1.4 O que substituir
Nada no domínio ou na API precisa ser substituído — nenhuma peça testada e determinística do backend está incompatível com Web.

### 1.5 O que permanece em quarentena
`mobile/` — Flutter, integralmente, sem evolução, sem promoção, sem validação forçada nesta missão. Ver `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md`.

### 1.6 O que depende de decisão humana
- Atualização formal do Product Charter e NFR à luz da Lei Web First (§1.2).
- Framework de frontend (ADR-0017, PROPOSTA).
- Estratégia de sessão/autenticação Web (ADR-0018, PROPOSTA).
- Destino final do `mobile/` (após este System Design).
- Hospedagem/implantação alvo (ADR-0019, PROPOSTA).

### 1.7 O que depende de terceiros
Homologação Google Ads, Meta Marketing API (tier de acesso exige histórico real de chamadas com erro baixo, confirmado no painel v18/v19), WhatsApp Business Platform.

### 1.8 O que está fora do escopo desta missão
Implementação de qualquer código de frontend; evolução do backend funcional; migrations; deploy; conexão com contas reais.

---

## 2. Requisitos funcionais (Web)

Baseados em `docs/product/13_ESPECIFICACAO_TELAS_APP.md` (F1–F10, já pesquisado com concorrentes reais em 05/09/2026) e no contrato `bff-openapi.yaml` (21 rotas confirmadas). Cada item cita a rota/módulo que já o implementa no backend, quando existe.

| # | Requisito | Suportado hoje por | Status |
|---|---|---|---|
| RF-01 | Cadastro e autenticação | — | `AUSENTE` — TARGET, ADR-0018 |
| RF-02 | Onboarding (empresa, unidade de negócio, conexão de contas) | `POST /brand-profiles`, `POST /connections/oauth/start` | API existe; fluxo Web inexistente |
| RF-03 | Tenant e unidades | `permissions.py` (ABAC, `business_unit_id`) | Domínio pronto; UI inexistente |
| RF-04 | Usuários e permissões (RBAC 6 papéis) | `permissions.py` | Domínio pronto; UI inexistente |
| RF-05 | Brand Kit | `POST/GET /brand-profiles` | API existe; UI inexistente |
| RF-06 | Briefing | `POST /briefs` | API existe; UI inexistente |
| RF-07 | Estratégia (geração por IA) | `GET/POST /campaigns/{id}/plan[/regenerate]` | API existe; UI inexistente |
| RF-08 | Geração e gestão de criativos | `ai_gateway.py` (`AITask.GENERATE_IMAGE`/`GENERATE_COPY`) | Domínio parcial (gateway existe, geração de imagem real não confirmada) |
| RF-09 | Prévia e validação | `POST /campaigns/{id}/validate` | API existe; UI inexistente |
| RF-10 | Aprovação (fila, decisão, segregação de funções) | `GET/POST /approvals`, `can_approve()` | Domínio pronto e testado; UI inexistente |
| RF-11 | Conexão de contas (OAuth) | `POST /connections/oauth/start`, `GET .../capabilities` | API existe; nenhum provider real por trás |
| RF-12 | Criação de campanha | `POST /briefs` → `GET /campaigns` | API existe; UI inexistente |
| RF-13 | Publicação | `POST /campaigns/{id}/publish` → `PublicationSaga` | Domínio pronto e testado; UI inexistente |
| RF-14 | Acompanhamento/estados | `GET /campaigns/{id}` | API existe; UI inexistente |
| RF-15 | Métricas/insights | `GET /campaigns/{id}/insights` | API existe — **retorna lista vazia honestamente hoje** (confirmado no nome do teste `test_insights_is_honest_placeholder`), sem integração real de dados |
| RF-16 | Conversões | — | `AUSENTE` no contrato atual — TARGET |
| RF-17 | Orçamento | `PATCH /campaigns/{id}/budget`, `budget.py` | Domínio pronto e testado (incl. regressão do alias `daily_cap`); UI inexistente |
| RF-18 | Recomendações/otimização | `pacing.py`, `optimizer.py` | Domínio implementado (não lido linha a linha nesta missão); UI inexistente |
| RF-19 | Pausa | `POST /campaigns/{id}/pause` | API existe; UI inexistente |
| RF-20 | Kill switch | `POST /kill-switch` | API existe e testada (3 escopos: campanha/plataforma/tenant); UI inexistente |
| RF-21 | Auditoria | `GET /audit-events` | API existe; UI inexistente |
| RF-22 | Notificações | — | `AUSENTE` — TARGET |
| RF-23 | Erros em linguagem compreensível | `docs/09_CATALOGO_ERROS_USUARIO.md` (citado, v1.1.0, 21 mensagens) | Documentado; não lido nesta missão, mas confirmado existente por nome de arquivo |
| RF-24 | Configuração de autonomia | `GET/PUT /autonomy` | API existe e testada; UI inexistente |

`FATO CONFIRMADO`: RF-15 (insights) é honestamente um placeholder no código atual — o próprio nome do teste (`test_insights_is_honest_placeholder`) confirma que a API não inventa dado quando não há integração real. Isso deve ser preservado como princípio de design ao construir a Web: nunca simular sucesso de dado externo (Documento Mestre §50).

---

## 3. Requisitos não funcionais (Web)

Baseados em `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md`, reconciliados com o CURRENT e com a Lei Web First. Onde o NFR original já tratava algo como `NÃO VERIFICADO`, mantido assim aqui — não promovido a fato.

| Categoria | Requisito | Origem | Status |
|---|---|---|---|
| Segurança | OAuth 2.0, MFA para admin/financeiro, JWT com TTL, RBAC+ABAC, RLS | NFR §4, confirmado em código (`permissions.py` já exige MFA/step-up para as mesmas permissões) | `DECISÃO EXISTENTE` (domínio) + `TARGET` (camada Web) |
| Privacidade/LGPD | Consentimento, retenção configurável, direito ao esquecimento < 30 dias | NFR §5.1 | `TARGET`, não implementado |
| Isolamento entre tenants | RLS + ABAC + `NOT_FOUND` em vez de `PERMISSION_DENIED` | NFR §4.2, confirmado em `permissions.py` linha 217-222 | `FATO CONFIRMADO` no domínio; `TARGET` na camada Web (tenant nunca por header não confiável) |
| Disponibilidade | 99.9% produção (NFR §2.1) | NFR | `TARGET`, `NÃO VERIFICADO` — nenhuma infraestrutura de produção existe ainda |
| Desempenho | SLOs de latência por operação (NFR §1.1) | NFR | `TARGET`, `NÃO VERIFICADO` — nenhum teste de carga foi executado |
| Escalabilidade | Marcos de roadmap comercial (100/1.000/10.000 campanhas) | NFR §1.2, explicitamente marcado no próprio documento como "não são apenas hipótese... mas... capacidade real continua NÃO VERIFICADO" | `HIPÓTESE` de negócio, não meta técnica validada — preservado como tal, não promovido a fato nesta missão |
| Acessibilidade | Não coberta no NFR original (documento é mobile-first) | — | `TARGET NOVO` — requisito desta fase Web, ver `03_ARQUITETURA_WEB_DOMINIO_E_DADOS.md` |
| Responsividade | NFR §8.3 já previa "Web Dashboard" responsivo mobile-first | NFR | `TARGET`, adaptado — Web passa a ser a linha principal, não dashboard secundário |
| Compatibilidade de navegadores | Chrome 100+, Firefox 100+, Safari 15+ (NFR §8.3) | NFR | `TARGET`, mantido |
| Observabilidade | Logging centralizado, OpenTelemetry, métricas (NFR §6) | NFR | `TARGET`, nada implementado ainda no código lido |
| Auditabilidade | `audit_events` (tabela + rota já existentes) | DDL + `GET /audit-events` | `FATO CONFIRMADO` (parcial) — estrutura existe, cobertura completa não verificada |
| Retenção | Configurável por tenant, default 2 anos (NFR §5.1) | NFR | `TARGET` |
| Recuperação | RPO < 5min, RTO < 1h (NFR §2.3) | NFR | `TARGET`, `NÃO VERIFICADO` — sem infraestrutura real ainda; não declarar como aprovado sem autoridade humana (ver `22. Resiliência` em `04_IA_INTEGRACOES_SEGURANCA_RESILIENCIA.md`) |
| Idempotência | `command_id`/`idempotency_key` já em `budget.py`, `connectors.py`, `saga.py` | leitura direta | `FATO CONFIRMADO` no domínio |
| Consistência | Reserva-antes-de-efeito (`budget.py`), Saga com compensação | leitura direta | `FATO CONFIRMADO` no domínio |
| Rastreabilidade | Eventos AsyncAPI (24), `audit_events` | leitura + reexecução do validador | `FATO CONFIRMADO` (contrato); correlation/causation ID **não confirmados no código lido** |
| Manutenibilidade | Separação Core/Application/Infra já existente | leitura direta | `FATO CONFIRMADO` |
| Custo | Limites por plano (Starter/Professional/Enterprise), NFR §10 | NFR | `TARGET`, não implementado como enforcement |
| Portabilidade | Backend Python puro, sem lock-in de framework web específico | leitura direta | `FATO CONFIRMADO` |
| Evolução incremental | Documento Mestre §61 exige evolução sem reconstrução | governança | Princípio orientador de todo este documento |

---

## 4. Hipóteses de capacidade

`HIPÓTESE` explícita — não tratar como fato técnico. Reaproveitando os marcos já registrados pelo Diretor no NFR original (§1.2, D020), sem inflar nem reduzir:

| Cenário | Tenants | Campanhas simultâneas | Eventos/dia (estimado) | Observação |
|---|---|---|---|---|
| Inicial (MVP) | dezenas | ~100 (marco Fase 5 do NFR) | baixa centena | Sandbox de providers, sem carga real |
| Crescimento | centenas | ~1.000 (marco Fase 8 do NFR) | milhares | Requer teste de carga real antes de aceitar como validado |
| Escala elevada | até 1.000 (meta hipotética NFR §1.3) | ~10.000 (marco Fase 12 do NFR) | dezenas de milhares | Não dimensionar infraestrutura definitiva por este número sem validação prévia |

Nenhum desses números deve ser tratado como SLA contratual — o próprio NFR original já registra essa distinção (D020) e este documento a preserva integralmente.
