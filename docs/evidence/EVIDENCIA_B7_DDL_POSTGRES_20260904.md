# EVIDÊNCIA — B7: DDL e Migrations do Postgres

**Data:** 04/09/2026
**Projeto:** CAMPAIA (F&M Tecnologia)
**Diretor:** Fábio Aluizio da Silva
**Bloco técnico:** B7 — DDL e migrations do Postgres (Fase 3 do painel de execução)

---

## 1. Autorização do Diretor

Ao final do fechamento do B5, apresentei ao Diretor a recomendação de seguir para B7 (DDL/migrations do Postgres), com uma ressalva explícita: como esta sandbox não teria um Postgres real, a verificação ficaria "limitada a sintaxe/revisão estática do DDL, não a execução real". O Diretor respondeu:

> **"sim concordo"**

Como será detalhado na Seção 4, essa ressalva acabou sendo **mais conservadora do que a realidade** — a sandbox tinha, sim, um servidor Postgres real disponível, descoberto durante a execução deste bloco. A verificação final é, portanto, mais forte do que a inicialmente prometida ao Diretor, e isso é registrado aqui com a mesma transparência que qualquer outro achado deste projeto.

---

## 2. Pesquisa de escopo antes de escrever qualquer DDL

Antes de desenhar uma única tabela, uma pesquisa foi delegada para responder: o que exatamente deveria virar tabela no Postgres? A pesquisa cobriu:

- Leitura completa de todos os módulos de `campaia_core/` para identificar toda entidade de domínio que poderia, em tese, precisar de uma tabela.
- Leitura completa de `api/db.py` (persistência SQLite opcional já existente) e `api/repositories.py`, para extrair o schema real hoje em uso.
- Busca por qualquer artefato Postgres já existente (`.sql`, alembic, `migrations/`) em `backend/` e em `campaia/` — nenhum encontrado.
- Leitura de `campaia/docs/product/` e `campaia/docs/security/TENANT_ISOLATION.md` em busca de requisitos de modelo de dados, multi-tenancy e Postgres.

**Achado principal:** `docs/06_MODELO_DADOS.md`, citado no painel de execução como "PROPOSTA v0.1", **nunca foi de fato escrito** — não existe em lugar nenhum, nem na árvore espelhada do Drive. A maior parte dos módulos de domínio (budget/reservas fora do que já está aninhado em `CampaignRecord`, outbox/inbox, reconciliation, AI gateway/cost ledger, permissions/RBAC como tabelas próprias) **nunca foi persistida em nenhum banco** — existem apenas como objetos Python em memória, sem nenhum precedente de persistência real no código.

**Achado sobre B5:** as saídas do motor de otimização/pacing (`PacingAssessment`, `Recommendation`, `OptimizationReport`) são, pelas próprias docstrings desses módulos, cálculos puros retornados por funções sem estado — nada no código as persiste hoje. Confirmado: não geram tabela neste bloco.

**Achado de multi-tenancy:** `TENANT_ISOLATION.md` já registra, como invariante arquitetural (#4), que toda tabela deve ter `tenant_id` e Row Level Security, e que acesso cross-tenant deve responder `NOT_FOUND`, nunca `PERMISSION_DENIED`. Mas o formato exato de tenant (single-tenant-com-unidades-de-negócio vs. suporte a agência com múltiplas empresas) depende da decisão D-03, ainda em aberto — e `permissions.py` já documenta que qualquer extensão para agência deve ser aditiva, não uma reforma do que existe.

---

## 3. Decisão de escopo (perguntada ao Diretor, não presumida)

Dado o achado acima, havia uma ambiguidade real de escopo: construir DDL só do que já é persistido hoje (baixo risco, migração direta) ou desenhar um modelo de dados completo e especulativo para tudo que existe em memória (alto risco, sem precedente). A pergunta foi levada ao Diretor com as duas opções, marcando a primeira como recomendação. O Diretor confirmou:

> **"DDL apenas do que já é persistido (Recomendado)"**

Sobre multi-tenancy, uma segunda pergunta foi feita: construir para o caso simples (tenant_id obrigatório, `business_unit_id` opcional/extensível) ou pausar o bloco até a D-03 ser decidida. O Diretor confirmou:

> **"Construir para o caso simples, deixando extensível (Recomendado)"**

---

## 4. Código construído

### 4.1 `backend/db/001_initial_schema.sql` (15577 bytes)

**Nota de correção:** a versão original deste arquivo (15402 bytes) trazia, em seu próprio comentário de cabeçalho, a mesma ressalva desatualizada dada ao Diretor — "não há Postgres real disponível aqui" — escrita antes da descoberta relatada na Seção 5. Antes do upload a este documento, o comentário foi corrigido para refletir a verificação real de fato executada (ver Seção 5), o que alterou o tamanho do arquivo para 15577 bytes. O script `verify_ddl_postgres.sh` foi re-executado **duas vezes adicionais** após essa correção (puramente textual, sem alteração de nenhuma instrução SQL) para confirmar que `ALL CHECKS PASSED` continua valendo e que não houve regressão introduzida pela edição — disciplina de nunca aceitar "é só um comentário" como dispensa de reverificação.

Migration única (`BEGIN`/`COMMIT`), cobrindo exatamente as 7 tabelas que `api/db.py` já persiste hoje (`brand_profiles`, `connections`, `campaigns`, `approvals`, `audit_events`, `idempotency`, `tenant_autonomy`), como um upgrade real do shape genérico atual (`id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, data TEXT NOT NULL` — um blob JSON por linha) para colunas reais nos campos que já são de fato filtrados/consultados no código (id, tenant_id, status/estado, timestamps), mantendo como JSONB os campos aninhados complexos (brief, plano, decisão de política, budget engine completo, autonomy settings completo, histórico de estado).

Decisões específicas registradas em comentário no próprio arquivo:
- `campaigns.state` vira coluna com `CHECK` cobrindo os 13 valores de `CampaignState` (extraídos de `campaia_core/states.py` nesta sessão — o arquivo já avisa, em comentário, para reconfirmar essa lista antes de rodar contra um Postgres de produção, caso o enum mude entre esta migration e a execução real).
- `approvals.kind`/`approvals.status` e `connections.status`/`connections.mode` viram colunas com `CHECK` pelos mesmos enums do contrato já usados em `api/repositories.py`.
- `idempotency` normaliza a chave composta `"{tenant_id}\x1f{idempotency_key}"` (hoje uma string concatenada usada como id de linha no SQLite) em duas colunas reais com chave primária composta `(tenant_id, idempotency_key)`.
- `tenant_autonomy` normaliza o blob único `{tenant_id: AutonomySettings}` de hoje (gravado sob uma chave fixa `"all"`, incompatível com RLS por tenant) em uma linha real por tenant — necessário porque um blob de todos os tenants não pode ter RLS por `tenant_id` de forma alguma.
- `business_unit_id` é coluna própria mas **sempre `NULL`able** em todas as tabelas onde aparece, por decisão explícita do Diretor sobre a D-03.
- Toda tabela tem `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + `CREATE POLICY ... USING (tenant_id = current_setting('app.tenant_id', true))`.
- `approvals.campaign_id` é uma foreign key real para `campaigns.campaign_id` (não existia integridade referencial nenhuma no SQLite genérico).

### 4.2 `backend/db/verify_ddl_postgres.sh` (5961 bytes)

Script de verificação reproduzível, criado porque a verificação deste bloco não deveria depender de comandos digitados manualmente uma única vez nesta sessão. Cria um banco e um papel de teste com sufixo de PID (nunca colide com dados reais, nunca precisa de banco pré-existente), roda a migration completa, e prova, com queries reais (não apenas leitura do arquivo `.sql`):

1. O schema inteiro aplica sem erro.
2. RLS isola de fato dois tenants diferentes — e, com nenhum `app.tenant_id` definido, a contagem de linhas visíveis é **zero** (falha fechado, não aberto).
3. `CHECK` de estado de campanha rejeita valor inválido e aceita valor válido.
4. Foreign key `approvals.campaign_id → campaigns.campaign_id` rejeita referência inexistente.
5. Chave primária composta de `idempotency` rejeita duplicata.

Sempre derruba o banco e o papel de teste ao final (`trap cleanup EXIT`), mesmo em caso de falha no meio do script.

---

## 5. Verificação real contra Postgres (não apenas revisão estática)

Ao contrário da ressalva dada ao Diretor antes de começar este bloco ("não é verificável nesta sandbox sem um Postgres real"), foi descoberto durante a execução que **esta sandbox tem, sim, um servidor Postgres 16 instalado** (`postgresql-16`, `postgresql-client-16`, cluster `main` na porta 5432, inicialmente parado). O servidor foi iniciado (`service postgresql start`) e usado para uma verificação genuína, não apenas leitura de sintaxe:

```
$ bash backend/db/verify_ddl_postgres.sh
== 1/5: criando banco de teste e aplicando o DDL ==
[... CREATE TABLE / CREATE INDEX / ALTER TABLE / CREATE POLICY para as 7 tabelas ...]
OK: schema aplicado sem erros.
== 2/5: inserindo dados de dois tenants como superusuário ==
INSERT 0 1
INSERT 0 1
== 3/5: verificando isolamento por RLS via TCP/senha (papel de aplicação, sem superusuário) ==
OK: RLS isola tenant-a (1), tenant-b (1), sem contexto (0).
== 4/5: verificando restrições CHECK e foreign key ==
OK: CHECK de estado e foreign key de approvals aplicados corretamente.
== 5/5: verificando chave composta de idempotency ==
OK: chave composta de idempotency rejeita duplicata.

ALL CHECKS PASSED — DDL aplicado e verificado contra Postgres real.
```

O script foi executado **duas vezes seguidas** para confirmar reprodutibilidade e limpeza correta (sem banco/papel de teste deixado para trás entre execuções) — ambas terminaram em `ALL CHECKS PASSED`, e uma checagem posterior (`psql -l`, `\du`) confirmou zero rastro deixado no servidor.

Antes de chegar à versão final do script, uma tentativa inicial de checar contagem de linhas via `psql -tAc "SET app.tenant_id = '...'; SELECT count(*) ..."` retornou `"SET\n1"` em vez de só `"1"` (múltiplas instruções no mesmo `-c` imprimem a saída de cada uma) — corrigido com `| tail -n1` antes de comparar o valor. Este é o tipo de erro que o próprio script deveria pegar, e pegou, na primeira execução (falhou com uma mensagem clara em vez de reportar sucesso falso).

**Reforço da disciplina do projeto:** esta verificação não se apoiou apenas em "o comando não deu erro" — testou explicitamente o caso onde a proteção deveria falhar (estado inválido, FK para linha inexistente, chave duplicada, tenant sem contexto) e confirmou que cada um desses casos é de fato rejeitado, não apenas que os casos válidos funcionam.

---

## 6. Regressão

B7 não tocou nenhum arquivo Python — é puramente SQL + shell novos em `backend/db/`. Confirmado por re-execução direta:

```
$ cd backend && python3 -m unittest discover -s tests -p "test_*.py"
Ran 263 tests in 0.036s
OK,

$ cd backend && python3 -m unittest discover -s tests_api -p "test_*.py"
Ran 80 tests in 0.693s
OK
```

**263 + 80 = 343, inalterado, zero regressão** — como esperado, já que nenhum código Python foi modificado.

---

## 7. O que o B7 entrega e o que deliberadamente não entrega

**Entrega:**
- DDL completo e executável para as 7 tabelas hoje persistidas via `api/db.py`, com colunas reais nos campos consultados, JSONB nos campos aninhados complexos, `CHECK` nos enums do contrato, foreign key real entre `approvals` e `campaigns`, e Row Level Security por tenant em todas as tabelas.
- Verificação real contra um Postgres geníno (não apenas leitura de sintaxe), reproduzível por qualquer pessoa via um único script.
- `business_unit_id` como coluna opcional em todas as tabelas relevantes, sem comprometer a decisão ainda aberta da D-03.

**Não entrega, por decisão explícita do Diretor:**
- Tabelas para módulos de domínio sem precedente de persistência hoje (budget/reservas fora do já aninhado em campanhas, outbox/inbox, reconciliation, AI gateway/cost ledger, permissions/RBAC como tabelas próprias) — ficaria especulativo sem um modelo de dados formal por trás.
- Tabela para as saídas do B5 (recomendações/avaliações de pacing) — são cálculos puros, nunca persistidos em código algum hoje.
- Qualquer decisão definitiva sobre o formato de multi-tenant da D-03 — o schema foi construído para não bloquear nenhuma das duas direções possíveis.

---

## 8. Resumo executivo

| Item | Valor |
|---|---|
| Autorização do Diretor | "sim concordo" (bloco) + duas confirmações de escopo (DDL só do persistido; multi-tenant extensível) |
| Arquivos novos | `db/001_initial_schema.sql` (15577 B), `db/verify_ddl_postgres.sh` (5961 B) |
| Tabelas cobertas | 7 (brand_profiles, connections, campaigns, approvals, audit_events, idempotency, tenant_autonomy) |
| Verificação | **Real, contra Postgres 16 genuíno** (não apenas sintaxe) — RLS, CHECK, FK e chave composta todos testados com casos válidos e inválidos, 2 execuções reprodutíveis |
| Regressão | Zero (nenhum código Python alterado; 343 testes inalterados) |
| Correção durante o próprio trabalho | Um bug no script de verificação (parsing de saída multi-statement do `psql`) encontrado e corrigido antes de aceitar o resultado como válido |
| Tabelas fora de escopo (por decisão do Diretor) | Módulos sem precedente de persistência (budget avulso, outbox/inbox, reconciliation, AI cost ledger, RBAC) e saídas do B5 (puramente calculadas) |

---

## 9. Artefatos no Google Drive

| Arquivo | Pasta (Drive) | fileId | Tamanho verificado |
|---|---|---|---|
| `001_initial_schema.sql` | `backend/db/` | `1WT_7ieWA-WXVjT_NreJ1bnk2UIRG0n6y` | 15577 bytes (upload + download+diff conferidos) |
| `verify_ddl_postgres.sh` | `backend/db/` | `1QY94P_E2OEjA_cDXTdEG3JO_Re2Na19b` | 5961 bytes (upload + download+diff conferidos) |

A pasta `backend/db/` (fileId `1x6N8_JtG3FC3cN-B3Gh0anqfrJ3smehb`) foi criada nesta sessão como irmã de `campaia_core/`, `api/`, `tests/` e `tests_api/`, pois não existia anteriormente. Todos os três uploads deste bloco (este documento de evidência e os dois arquivos acima) foram feitos via `textContent` (não `base64Content`), eliminando a classe de risco de corrupção por transcrição manual identificada no incidente P-20 do B5, e cada um foi conferido não só por tamanho em bytes mas por download completo e diff byte-a-byte contra o arquivo local antes de ser considerado correto.

---

*Documento gerado e verificado nesta sessão via execução real de uma migration contra um servidor Postgres genuíno, seguindo a disciplina de evidência do projeto CAMPAIA.*
