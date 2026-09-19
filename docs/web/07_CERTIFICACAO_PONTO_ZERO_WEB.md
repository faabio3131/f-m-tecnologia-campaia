# CampaIA — Ponto Zero Web · 07. Certificação, pendências e riscos

**Estado máximo declarado:** `SYSTEM DESIGN WEB CORRIGIDO E CERTIFICADO — PR DRAFT PRONTA PARA REVISÃO E DECISÃO HUMANA`

Este documento registra eventos de validação em ordem cronológica, cada um com o SHA real em que ocorreu. Ele **não declara um "HEAD final" de si mesmo** — seria uma referência autorrecursiva impossível, já que o commit que inclui esta versão do arquivo ainda não existe no momento em que ela é escrita. O HEAD real após esta correção é reportado no relatório final da missão (fora deste arquivo) e no painel de execução (`backend/01_PAINEL_EXECUCAO_v20_VIGENTE.md`, seção "Última evidência").

---

## 1. Cronologia de validação (cada evento com seu próprio SHA real)

| Evento | SHA | O que foi validado |
|---|---|---|
| Validação local de runtime (testes de domínio, testes de API, AsyncAPI, DDL/Postgres) | `a4a36ec2457fdb1ecd25319015b67470b899fd1e` | 267 testes de domínio, 81 de API, AsyncAPI 24/24, DDL/RLS contra Postgres 16 real — todos executados de fato, saída capturada |
| Commit de certificação inicial (doc 07, primeira versão) | `9a5935e` | Documental — não altera código, não exige nova execução de runtime |
| Commit do painel v20 | `0160182887a11cf1fc787ef97fdf085e6d3cdc21` | Documental — não altera código |
| **CI do GitHub Actions no HEAD `0160182`** | run **#11** (`35446255809`) | **`completed` / `success`**, confirmado diretamente via `mcp__github__actions_list` nesta correção — 267 testes de domínio + 81 de API + AsyncAPI 24/24, executados pelo runner do GitHub, não apenas localmente |
| Esta correção (task atual) | *(commits novos, ainda sem SHA no momento em que este texto é escrito)* | Corrige referências de ADR, remove token fixo do WP-01, incorpora leitura integral de 7 módulos + fonte D-08, ajusta linguagem da ADR-0016, reconcilia ADR-0019 |

**Obrigação registrada**: os commits desta correção alteram apenas documentação (nenhum código de `backend/`, `contracts/` ou `mobile/` é tocado), mas ainda assim exigem um **novo CI no novo HEAD** antes de qualquer certificação ser considerada válida para esse HEAD — reexecutado e confirmado antes do fechamento desta correção (ver relatório final da missão para o resultado real).

---

## 2. Matriz de validação real (executada no SHA `a4a36ec`, primeira execução desta missão)

| # | Verificação | Comando | Resultado | Falhas/skips/warnings |
|---|---|---|---|---|
| 1 | Testes de domínio | `python3 -m unittest discover -s tests -v` (em `backend/`) | **267 aprovados** | 0 falhas, 0 skips |
| 2 | Testes de API | `python3 -m unittest discover -s tests_api -t . -v` (em `backend/`) | **81 aprovados** | 0 falhas, 0 skips |
| 3 | Contrato AsyncAPI | `python3 validate_events_asyncapi.py` (em `contracts/`) | **ALL CHECKS PASSED** — 24/24 eventos verificados end-to-end | 0 |
| 4 | DDL/Postgres | `bash db/verify_ddl_postgres.sh` (em `backend/`, Postgres 16 real, reiniciado nesta sessão) | **ALL CHECKS PASSED** — schema, RLS (tenant-a/tenant-b/sem contexto), CHECK, FK, chave composta idempotency | 0 |
| 5 | Secrets (diff `main..a4a36ec`) | `grep` nos 11 arquivos então existentes | Nenhum segredo real encontrado (1 falso positivo textual) | — |
| 6 | Diff de escopo (diff `main..a4a36ec`) | `git diff main..a4a36ec --name-only` | 11 arquivos, todos em `docs/` | — |

**Correção sobre a versão anterior deste documento**: a contagem de "11 arquivos, todos em `docs/`" era exata **no SHA `a4a36ec`**, mas deixou de ser exata assim que o commit do painel v20 (`0160182`, em `backend/`) foi adicionado. A versão anterior deste arquivo apresentava a contagem de `a4a36ec` como se fosse do HEAD final da PR — corrigido abaixo.

## 3. Matriz de validação no HEAD real da PR no momento da criação (`0160182`)

| # | Verificação | Resultado |
|---|---|---|
| Diff de escopo | `git diff main..0160182 --name-only` → **13 arquivos**: 12 em `docs/` (8 em `docs/web/` + 4 ADRs na raiz de `docs/`), **1 em `backend/`** (`01_PAINEL_EXECUCAO_v20_VIGENTE.md`) |
| Secrets | Varredura nos 13 arquivos — nenhum segredo real encontrado |
| CI do GitHub | Run #11, `completed`/`success` (ver §1) |
| `mobile/` | Intocado |
| ADRs em `PROPOSTA` | Todas as 4 (0016–0019) — nenhuma `APROVADA` |

Esta correção (task atual) adiciona commits sobre `0160182`; a matriz de escopo/secrets/CI será reconfirmada no HEAD final resultante e reportada no relatório da missão.

---

## 4. Decisões existentes vs. propostas vs. pendentes

| Item | Classificação |
|---|---|
| Repositório canônico é `faabio3131/f-m-tecnologia-campaia` | `DECISÃO EXISTENTE` (ADR-0015, reconciliação anterior) |
| Lei Web First aplicável a todo novo software comercial | `DECISÃO EXISTENTE` (Documento Mestre v2.0) — já vigente independentemente de qualquer ADR desta missão |
| Tratamento formal da divergência entre a Lei Web First e a frase de natureza mobile do Charter | `RECOMENDAÇÃO PROPOSTA`, não decisão — ADR-0016, linguagem corrigida nesta correção para não parecer aprovada |
| Framework de frontend (Next.js/React) | `RECOMENDAÇÃO PROPOSTA` — ADR-0017 |
| Estratégia de autenticação/sessão Web | `RECOMENDAÇÃO PROPOSTA` — ADR-0018 |
| Implantação sobre Google Cloud, `southamerica-east1` (D-08) | `DECISÃO EXISTENTE` (D-08, 27/08/2026, lida integralmente nesta correção) reconfirmada como restrição; formalização da implantação Web é `RECOMENDAÇÃO PROPOSTA` — ADR-0019 |
| Cloud Workflows (vs. Temporal) | `DECISÃO EXISTENTE` (ADR-0010, já aprovada, citada no painel) — **não é mais pendência**, corrigido nesta versão |
| Preservação do backend Starlette (não migrar para FastAPI agora) | `RECOMENDAÇÃO`, não decisão formal — sem ADR própria, corrigido nesta correção para não citar uma ADR errada |
| Destino final do `mobile/` | `PENDÊNCIA` — decisão humana após aprovação deste System Design |
| Atualização literal do Product Charter/NFR | `PENDÊNCIA` — decisão humana, fora do escopo de execução desta missão |
| Provedor específico de identidade (ADR-0018) | `PENDÊNCIA` — Work Package |
| Serviço de container específico na nuvem (ADR-0019) | `PENDÊNCIA` — Work Package |
| Orçamento mensal exato e confirmação jurídica de residência de dados (D-08) | `PENDÊNCIA` real, herdada da fonte primária — nunca resolvida, confirmado por leitura integral nesta correção |

---

## 5. Riscos registrados

| Risco | Origem | Mitigação proposta |
|---|---|---|
| Documentação de produto (Charter/NFR) permanece com frase desatualizada até correção humana | ADR-0016 | Pendência explícita, rastreável; linguagem da ADR corrigida para não sugerir aprovação automática |
| Módulos de outbox/webhooks não têm persistência confirmada além de memória de processo | Leitura integral desta correção | Registrado como pendência real para Work Package de integração; não promovido a prontidão de produção |
| Nenhum adaptador real de provider existe — todo o bloco de integrações depende de terceiros (homologação, sandbox) | `04_IA_INTEGRACOES_SEGURANCA_RESILIENCIA.md` §2 | Tratado como gate futuro, não bloqueia o Ponto Zero Web em si |
| Autenticação real ainda não existe — é a maior superfície de risco de segurança do roadmap | ADR-0018, WP-02 | Gate 3 exige revisão de FM Security Engineer antes de prosseguir; WP-01 corrigido nesta versão para não usar token algum no frontend |
| Metas de capacidade (100/1.000/10.000 campanhas) são hipótese de negócio, não validação técnica | `02_PONTO_ZERO_WEB_E_REQUISITOS.md` §4 | Preservado como `HIPÓTESE`, não promovido a fato |
| Orçamento exato e residência de dados de D-08 seguem sem confirmação, mesmo após leitura integral da fonte | ADR-0019 | A própria fonte primária já registra isso como pendência não resolvida — preservado com fidelidade, não inventado |

---

## 6. Itens não verificados (consolidado, após a leitura desta correção)

- Origem real do mecanismo de moderação de IA (`AIStatus.BLOCKED_BY_MODERATION`) — comportamento de tratamento confirmado, origem/provedor não.
- Evals formais de IA — não encontrados em nenhum dos 7 módulos lidos nesta correção.
- Cache de resultados de IA — não encontrado.
- Proteção contra prompt injection além da trava de credencial — não encontrada.
- Enforcement real de isolamento entre tenants na camada de IA além da exigência de `tenant_id` não vazio — não encontrado.
- Persistência real (além de memória de processo) de `outbox.py`/`webhooks.py` — não encontrada.
- Circuit breaker para conectores de Ads (existe apenas para `ai_gateway.py`, confirmado) — não encontrado para `connectors.py`.
- Rate limits/quotas reais de Google Ads, Meta Marketing API e WhatsApp Business Platform — nenhuma consulta a fonte oficial externa foi feita nesta missão.
- Orçamento mensal exato e confirmação jurídica de residência de dados (D-08) — a própria fonte primária os registra como não resolvidos.

---

## 7. Certificação

| Estado | Situação |
|---|---|
| Documentado | Sim |
| Arquitetura produzida | Sim |
| Arquitetura revisada (tecnicamente, por esta correção) | Sim — CI real confirmado (`completed`/`success`), referências de ADR corrigidas, CURRENT ampliado por leitura integral de 7 módulos + fonte D-08 |
| Arquitetura aprovada | **Não** — nenhuma ADR foi marcada `APROVADA`; aguarda decisão humana |
| Pronto para implementação | **Parcial** — WP-01 (corrigido: mock de contrato, sem token) está pronto; WP-02 a WP-05 dependem das ADRs correspondentes |
| Frontend implementado | **Não** |
| Integrado | **Não** |
| Homologado | **Não** |
| Pronto para produção | **Não** |
| Comercialmente disponível | **Não** |

## Veredito

**`SYSTEM DESIGN WEB CORRIGIDO E CERTIFICADO — PR DRAFT PRONTA PARA REVISÃO E DECISÃO HUMANA`**

Condicionado à confirmação do novo CI no HEAD resultante desta correção (ver relatório final da missão).
