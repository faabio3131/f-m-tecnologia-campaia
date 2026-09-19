# CampaIA — Ponto Zero Web · 07. Certificação, pendências e riscos

**Estado máximo declarado:** `SYSTEM DESIGN WEB PRODUZIDO — PENDENTE DE REVISÃO E APROVAÇÃO HUMANA`

---

## 1. Matriz de validação real (executada nesta sessão, HEAD `a4a36ec2457fdb1ecd25319015b67470b899fd1e`)

| # | Verificação | Comando | Resultado | Falhas/skips/warnings |
|---|---|---|---|---|
| 1 | Testes de domínio | `python3 -m unittest discover -s tests -v` (em `backend/`) | **267 aprovados** | 0 falhas, 0 skips |
| 2 | Testes de API | `python3 -m unittest discover -s tests_api -t . -v` (em `backend/`) | **81 aprovados** | 0 falhas, 0 skips |
| 3 | Contrato AsyncAPI | `python3 validate_events_asyncapi.py` (em `contracts/`) | **ALL CHECKS PASSED** — 24/24 eventos verificados end-to-end | 0 |
| 4 | DDL/Postgres | `bash db/verify_ddl_postgres.sh` (em `backend/`, Postgres 16 real, reiniciado nesta sessão) | **ALL CHECKS PASSED** — schema, RLS (tenant-a/tenant-b/sem contexto), CHECK, FK, chave composta idempotency | 0 |
| 5 | Secrets | `grep` nos 11 arquivos novos/alterados desta branch | Nenhum segredo real encontrado (1 falso positivo: menção textual a "Segredo exposto" numa linha de matriz de ameaças) | — |
| 6 | Diff de escopo | `git diff c121f7c..HEAD --name-only` | 11 arquivos, todos em `docs/` (`docs/web/` + 4 ADRs na raiz) | 0 arquivos fora de `docs/` |
| 7 | Mobile intocado | `git diff c121f7c..HEAD --stat -- mobile/` | Vazio — `mobile/` não sofreu nenhuma alteração | — |
| 8 | ADRs em `PROPOSTA` | `grep "Status:" docs/14_ADR*.md docs/15_ADR*.md docs/16_ADR*.md docs/17_ADR*.md` | Todas as 4 novas ADRs (0016–0019) em `PROPOSTA`; nenhuma `APROVADA` | — |
| 9 | Sem declaração indevida de produção/homologação | `grep -riE "pronto para produção\|homologad[oa]"` nos novos docs | Nenhuma ocorrência | — |
| 10 | Fences Mermaid balanceados | Inspeção manual de `03_ARQUITETURA_WEB_DOMINIO_E_DADOS.md` | 8 blocos (7 Mermaid + 1 texto), 16 marcadores, todos pareados corretamente | — |
| 11 | Links internos | `grep` de referências `docs/*.md` citadas | Resolvidos, exceto citações abreviadas em prosa (ex.: `docs/web/04_...md`) e este próprio documento, criado nesta etapa | Estilo, não erro de conteúdo |
| 12 | Lint/format/typecheck | — | **N/A** — nenhuma configuração existe neste repositório (confirmado na reconciliação anterior desta mesma sessão; não reintroduzido nesta missão) | — |

Nenhum resultado acima reutiliza número de execução anterior — os 4 comandos de teste/validação (itens 1–4) foram executados de fato nesta sessão, neste HEAD, com saída capturada.

---

## 2. Decisões existentes vs. propostas vs. pendentes

| Item | Classificação |
|---|---|
| Repositório canônico é `faabio3131/f-m-tecnologia-campaia` | `DECISÃO EXISTENTE` (ADR-0015, reconciliação anterior) |
| Lei Web First aplicável a todo novo software comercial | `DECISÃO EXISTENTE` (Documento Mestre v2.0) |
| Precedência da Lei Web First sobre a frase de natureza mobile do Charter | `TARGET PROPOSTO` — ADR-0016 |
| Framework de frontend (Next.js/React) | `TARGET PROPOSTO` — ADR-0017 |
| Estratégia de autenticação/sessão Web | `TARGET PROPOSTO` — ADR-0018 |
| Implantação sobre Google Cloud (D-08) | `DECISÃO EXISTENTE` (D-08, 27/08/2026) reconfirmada como restrição; formalização da implantação Web é `TARGET PROPOSTO` — ADR-0019 |
| Preservação do backend Starlette (não migrar para FastAPI agora) | `RECOMENDAÇÃO`, não decisão formal — sem ADR própria, por não haver alternativa sendo adotada |
| Destino final do `mobile/` | `PENDÊNCIA` — decisão humana após aprovação deste System Design |
| Atualização literal do Product Charter/NFR | `PENDÊNCIA` — decisão humana, fora do escopo de execução desta missão |
| Provedor específico de identidade (ADR-0018) | `PENDÊNCIA` — Work Package |
| Serviço de container específico na nuvem (ADR-0019) | `PENDÊNCIA` — Work Package |
| Reconfirmação literal do texto de D-08 | `PENDÊNCIA` — não relido palavra por palavra nesta missão |

---

## 3. Riscos registrados nesta missão

| Risco | Origem | Mitigação proposta |
|---|---|---|
| Documentação de produto (Charter/NFR) permanece com frase desatualizada até correção humana | ADR-0016 | Pendência explícita, rastreável |
| Módulos não lidos linha a linha (`outbox.py`, `webhooks.py`, `reconciliation.py`, `sanitizer.py`, `agents.py`, `ai_simulator.py`, restante de `ai_gateway.py`) podem conter invariantes não capturados nesta arquitetura | Proporcionalidade de risco desta missão | Qualquer Work Package que os altere deve lê-los integralmente antes |
| Nenhum adaptador real de provider existe — todo o bloco de integrações depende de terceiros (homologação, sandbox) | `04_IA_INTEGRACOES_SEGURANCA_RESILIENCIA.md` §2 | Tratado como gate futuro, não bloqueia o Ponto Zero Web em si |
| Autenticação real ainda não existe — é a maior superfície de risco de segurança do roadmap | ADR-0018, WP-02 | Gate 3 exige revisão de FM Security Engineer antes de prosseguir |
| Metas de capacidade (100/1.000/10.000 campanhas) são hipótese de negócio, não validação técnica | `02_PONTO_ZERO_WEB_E_REQUISITOS.md` §4 | Preservado como `HIPÓTESE`, não promovido a fato |

---

## 4. Itens não verificados (consolidado)

- Conteúdo integral de `outbox.py`, `webhooks.py`, `reconciliation.py`, `sanitizer.py`, `agents.py`, `ai_simulator.py`, e de `ai_gateway.py` além das ~150 primeiras linhas.
- Texto literal e completo de `docs/evidence/DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md`.
- Rate limits/quotas reais de Google Ads, Meta Marketing API e WhatsApp Business Platform — nenhuma consulta a fonte oficial externa foi feita nesta missão.
- Comportamento real de moderação de IA (`AIStatus.BLOCKED_BY_MODERATION`) e de proteção contra prompt injection além da trava de credencial.
- Existência de backoff exponencial/circuit breaker real para conectores de Ads (só confirmado para `ai_gateway.py`).

---

## 5. Certificação

| Estado | Situação |
|---|---|
| Documentado | Sim |
| Arquitetura produzida | Sim |
| Arquitetura revisada (por esta missão, tecnicamente) | Sim — validação documental e de CI executada |
| Arquitetura aprovada | **Não** — nenhuma ADR foi marcada `APROVADA`; aguarda decisão humana |
| Pronto para implementação | **Parcial** — WP-01 a WP-05 estão prontos para execução assim que as ADRs correspondentes forem aprovadas; o restante do roadmap depende desses primeiros blocos |
| Frontend implementado | **Não** |
| Integrado | **Não** |
| Homologado | **Não** |
| Pronto para produção | **Não** |
| Comercialmente disponível | **Não** |

## Veredito

**`SYSTEM DESIGN WEB PRODUZIDO — PENDENTE DE REVISÃO E APROVAÇÃO HUMANA`**
