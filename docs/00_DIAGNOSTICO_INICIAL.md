# CAMPAIA — DIAGNÓSTICO INICIAL (Fase 0 — Reconhecimento)

**Produto:** CAMPAIA — aplicativo mobile SaaS de campanhas com IA governada
**Diretor / autoridade final:** Fábio Aluizio da Silva
**Data:** 25 de agosto de 2026
**Status do bloco:** CONCLUÍDO (reconhecimento)
**Autorização usada:** Ordem Mestra de Execução, itens 13 (Fase 0) e 22 (passos 1–10)

---

## 1. Documentos normativos localizados

| # | Documento | Estado |
|---|---|---|
| 1 | Skill `marketing-ai-system-design` | Localizado e lido integralmente |
| 2 | Arquitetura Mestra V1.1 | Localizado e lido integralmente (hoje SUBSTITUÍDA pela V2) |
| 3 | Ordem Mestra de Execução | Lida integralmente |
| 4 | `references/arquitetura-base.md` (citado pela skill) | **AUSENTE** |
| 5 | `CLAUDE.md`, `AGENTS.md` ou equivalente | **AUSENTE** |
| 6 | Código, configuração ou documentação prévia | **INEXISTENTE** |

**Inferência (não é fato):** o arquivo de arquitetura fornecido cumpre o papel do
`references/arquitetura-base.md` exigido pela skill. Recomenda-se canonizar formalmente esse vínculo (P-02).

---

## 2. Estado do ambiente

Inspeção executada em 25/08/2026.

| Item | Resultado | Impacto |
|---|---|---|
| Repositório Git do projeto | **Não existe** | Nada a preservar |
| Código-fonte | Inexistente | Projeto parte do zero (greenfield) |
| Git (ferramenta) | 2.43.0 disponível | Versionamento local possível |
| Python | **3.12.3** | Arquitetura recomenda 3.13 — divergência menor (P-05) |
| Node.js | 22.22.2 | Suficiente para tooling de contratos |
| Flutter / Dart | **Ausentes** | Não é possível compilar ou testar o app mobile |
| Docker | **Ausente** | Não é possível subir Postgres, Redis ou Temporal |
| PostgreSQL / Redis | **Ausentes** | Sem migrations nem testes de banco reais |
| Egress de rede no terminal | **Bloqueado (HTTP 403)** | Sem `pip install`, sem sandbox externo |
| Persistência do filesystem | Efêmera entre sessões | Nenhum estado sobrevive sozinho |

### 2.1 Consequência

O ambiente **executa Fase 0, Fase 1 e a parte determinística da Fase 3** com evidência real: arquitetura,
contratos, ADRs, threat model, plano de testes e domínio em Python puro.

O ambiente **não executa** build mobile, banco, sandbox externo nem CI. Qualquer alegação de "backend
implementado e testado em produção" produzida aqui seria não comprovável e violaria a Ordem Mestra, item 21.

Ver `10_PLANO_AQUI_VS_PC.md` para a divisão completa entre o que se constrói aqui e o que exige PC.

---

## 3. Divergência normativa identificada (item 3 da Ordem Mestra)

### DIV-01 — Acoplamento ao Kordena

| Fonte | O que diz |
|---|---|
| **Ordem Mestra, §2** | "O Marketing AI é um produto independente." Proíbe reutilizar Core, código, banco, autenticação, tenants, infraestrutura, marca e roadmap |
| **Arquitetura V1.1, §1** | Define o produto como bounded context **conectado ao Core do Kordena por contratos e eventos** |
| **Arquitetura V1.1, §14** | "Construir primeiro para o ecossistema Kordena" |
| **Skill** | Produto independente; integração futura exige decisão explícita |

**Análise:** a Ordem Mestra e a skill convergem; a Arquitetura V1.1 é a peça divergente. O nome próprio
CAMPAIA reforça a leitura de produto com marca e ciclo de vida próprios.

**Resolução (D-02, decidida pelo Diretor em 25/08/2026):** independência total, com integração futura
opcional via API pública. Registrado em ADR-0002 (APROVADA) e materializado na Arquitetura Mestra V2.

---

## 4. Identidade do produto — CAMPAIA

Nome definido pelo Diretor. Substitui "Kordena Marketing AI" como designação canônica. ADR-0001 APROVADA.

**Itens `NÃO VERIFICADO`** (exigem verificação antes de registro ou publicação):

- disponibilidade da marca CAMPAIA no INPI e classes aplicáveis;
- colisão com marcas existentes em mercados-alvo;
- disponibilidade de domínio (`campaia.com`, `.com.br`, `.app`);
- disponibilidade do nome na App Store e no Google Play;
- disponibilidade de handles em redes sociais.

Nenhuma dessas verificações foi feita. Não se afirma disponibilidade.

---

## 5. Riscos identificados

| ID | Risco | Severidade | Mitigação |
|---|---|---|---|
| R-01 | Ambiente sem Flutter/Docker/rede limita as Fases 2, 8 e 11 | Alta | Bloco C no PC (D-07 resolvida) |
| R-02 | Aprovações externas fora do controle do time, com prazo imprevisível | **Alta** | Provider Simulator; iniciar processos externos em paralelo |
| R-03 | Marca CAMPAIA não verificada juridicamente | **Alta** | Busca de anterioridade antes de investir em identidade visual |
| R-04 | Gasto de mídia não autorizado por defeito de software | **Crítica** | Budget Engine, kill switch multinível, testes financeiros bloqueantes |
| R-05 | Vazamento entre tenants | **Crítica** | `tenant_id` obrigatório, RLS + autorização, testes de isolamento |
| R-06 | Custo de IA sem teto por tenant | Média | `ai_cost_ledger`, limites, circuit breaker de custo |
| R-07 | Divergência entre estado interno e plataforma | Alta | Idempotência, outbox/inbox, reconciliação, alerta |
| R-09 | Escopo total muito superior a um MVP | **Alta** | Fatiar por gates; congelar Fases 9–12 até o Gate E2E |
| R-10 | LGPD: listas de clientes, Customer Match, consentimento de WhatsApp | Alta | Base legal documentada e opt-out auditável antes da Fase 7 |

---

## 6. Pendências abertas

| ID | Pendência | Tipo |
|---|---|---|
| P-02 | Canonizar a arquitetura como referência da skill | Documentação |
| P-04 | Verificação jurídica da marca CAMPAIA | Bloqueio externo |
| P-05 | Fixar versão de Python conforme runtime de produção | Decisão técnica |
| P-07 | Iniciar solicitações de acesso externo (Google, Meta, WABA) | Bloqueio externo |
| P-08 | Confirmar restrição da Meta a campanhas Advantage+ via Marketing API | Verificação |
| P-09 | WhatsApp: mudanças de preço em 01/08/2026 e 01/10/2026 | Verificação |
| P-10 | Documentação da Meta que exige login | Verificação |

---

## 7. Situação final do bloco

- **Fase:** 0 — Reconhecimento · **Status:** CONCLUÍDO
- **Evidência:** inspeção do ambiente e das ferramentas; verificação de egress de rede
- **Trabalho preexistente destruído:** nenhum (não havia)
- **Integrações externas:** nenhuma tocada; estado = **não iniciadas**
- **Bloqueios remanescentes:** D-03, D-05, D-06, D-08, D-09
