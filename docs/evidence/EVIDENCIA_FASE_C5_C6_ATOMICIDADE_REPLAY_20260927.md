# Evidência — Fase C5 (atomicidade de approval) e C6 (replay exato)

**Data:** 27/09/2026 · **Branch:** `reconciliation/campaia-final-takeover` (PR #31).

## Fase C6 — Replay exato (CORRIGIDO, código + teste)

**Achado real, confirmado por leitura do código:** 4 endpoints mutantes devolviam, no
caminho de replay (`existing = state.idempotency.get(...); if existing is not None:
return ...`), uma **re-serialização do estado ATUAL** do recurso — nunca
`existing.result` (o valor de fato guardado pelo `IdempotencyStore` na primeira
chamada). Um endpoint (`oauth_callback`) já fazia isso corretamente
(`return JSONResponse(existing.result, ...)`), servindo de referência para a correção.

**Endpoints corrigidos:**
- `PATCH /campaigns/{id}/budget` (`patch_budget`)
- `PUT /autonomy` (`put_autonomy`)
- `POST /approvals/{id}/decision` (`decide_approval`)
- `POST /campaigns/{id}/publish` (`publish_campaign`) — o mais delicado: a mutação de
  `approval.status`, `record.external_resources` e o registro de auditoria aconteciam
  **depois** de `idempotency.execute()`, fora do fecho protegido. Movidos para dentro
  de `_do_publish()`, que agora retorna a resposta final já serializada — mesmo padrão
  usado por `oauth_callback`/`create_brief`/`kill_switch`.

**Prova real:** `tests_api/test_exact_idempotency_replay.py` — muda o orçamento duas
vezes com chaves de idempotência diferentes (500→550→600), depois reenvia a **primeira**
chamada (chave antiga). Sem a correção, isso devolveria o orçamento atual (600); com a
correção, devolve a resposta original (550) — comportamento agora provado, não só
declarado.

**Endpoints já corretos, confirmados por leitura (nenhuma mudança necessária):**
`oauth_callback`, `create_brief`, `regenerate_plan`, `kill_switch`, `create_brand_profile`,
`billing_subscription_upsert`, `billing_charge_create` — todos já retornam
`existing.result`/o valor cacheado pelo próprio `_do_X()`.

Gates: `375 domínio + 205 API`, todos verdes (+1 novo teste).

## Fase C5 — Atomicidade de consumo de approval (INVESTIGADO, NÃO alterado nesta etapa)

**O que foi verificado, de fato:**

1. **Concorrência dentro do processo:** todo fecho `_do_X()` que mistura mutação de
   campanha + consumo de approval + auditoria é **código Python síncrono, sem `await`**,
   executado inteiro dentro de uma única invocação do event loop do asyncio. Confirmado
   por leitura de `publish_campaign`, `patch_budget`, `put_autonomy`, `decide_approval` —
   nenhum ponto de suspensão existe entre a leitura do estado e a escrita. Isso significa
   que, no modelo de deploy atual (processo único), duas requisições HTTP concorrentes
   **não podem intercalar** no meio dessas mutações — o GIL/event loop de fato serializa
   isso, não é uma suposição.

2. **O que NÃO está coberto, e é uma lacuna real:** quando `db_path` está configurado
   (modo persistente), cada `RecordTable.put(...)` abre e comita sua própria transação
   SQLite **isoladamente** — não existe uma transação abrangendo múltiplas tabelas (ex.:
   a linha da campanha e a linha da approval). Se o processo morresse exatamente entre
   esses dois commits, o restart poderia encontrar um recurso mutado e o outro não —
   uma janela real de inconsistência em caso de crash, distinta de concorrência entre
   requisições.

**Decisão desta etapa:** não construir suporte a transação multi-tabela agora. Isso
exigiria reestruturar `api/db.py` (`Database`/`RecordTable`) para expor um contexto de
transação abrangendo múltiplas tabelas, e revisar todo fecho que muta mais de um
repositório — mudança arquitetural transversal, arriscada de apressar sem foco
dedicado e sem risco de regressão silenciosa. Conforme a própria diretriz desta missão
("Não declarar atomicidade se SQLite/current repository não a oferecer de verdade"),
este documento **não declara** atomicidade de crash — registra a lacuna real,
explicitamente, como pendência.

**PENDÊNCIA registrada:** `PRODUCTION_GATE` — construir transação real multi-tabela (ou
equivalente) antes de operar em produção com múltiplos tenants e volume que torne uma
janela de crash entre commits um risco prático, não só teórico.

## Adendo (27/09/2026) — achado 5, auditoria independente #3: precisão explícita do PRODUCTION_GATE

A auditoria independente #3 apontou que a seção C5 acima, embora honesta sobre não
declarar atomicidade resolvida, não enumerava com precisão suficiente TODOS os cenários
que o `PRODUCTION_GATE` cobre — havia risco de um leitor concluir, por omissão, que
apenas "crash entre commits" fica pendente. Nenhuma mudança de código foi feita por este
adendo (achado 5 é puramente documental, conforme a própria auditoria pediu); o modelo
de persistência (`api/db.py`) não foi alterado.

**O `PRODUCTION_GATE` registrado acima cobre, explicitamente, TODOS os itens a seguir —
nenhum deles está resolvido pelo estado atual do código:**

1. **Crash entre commits.** Já documentado acima: cada `RecordTable.put(...)` comita sua
   própria transação SQLite isoladamente; um crash do processo entre dois commits que
   deveriam ser atômicos (ex.: mutar a campanha e consumir a approval) pode deixar um
   mutado e o outro não. Nenhuma recuperação/reconciliação automática existe para essa
   janela.

2. **Concorrência multi-processo.** A afirmação de que "o GIL/event loop serializa as
   mutações" (item 1 da seção C5) vale **apenas dentro de um único processo Python**. Este
   código **não foi testado, e não se sabe se é seguro, sob múltiplos processos/workers**
   (ex.: `uvicorn --workers N>1`, múltiplas réplicas atrás de um load balancer, ou
   qualquer topologia horizontal). Cada processo teria seu próprio `AppState` em memória
   (`step_up_at`, `oauth_pending_states` etc. não são compartilhados entre processos) e
   suas próprias transações SQLite concorrentes sobre o mesmo arquivo — SQLite tem
   suporte limitado a escritores concorrentes (lock de arquivo, não MVCC completo como
   Postgres). **Não declarado seguro** para múltiplos processos/workers.

3. **Concorrência multi-worker/multi-réplica (implantação horizontal).** Consequência
   direta do item 2: nada nesta base de código foi desenhado, revisado ou testado para
   rodar como mais de uma réplica do processo simultaneamente contra o mesmo
   `db_path`/arquivo SQLite. Produção com mais de uma réplica ativa é, hoje,
   **NÃO VERIFICADO** e potencialmente inseguro (mesmo arquivo SQLite sob escrita
   concorrente de processos que não coordenam entre si).

4. **Consumo de approval.** O `approval.status = "APPLIED"` (ou equivalente) e o efeito
   que ele autoriza (ex.: publicar campanha, aplicar mudança de orçamento) são escritos
   em commits SQLite separados quando `db_path` está configurado — não existe uma
   transação única cobrindo "marcar approval como consumida" + "aplicar o efeito que ela
   autoriza". Um crash nessa janela pode deixar uma approval marcada como consumida sem o
   efeito ter sido aplicado, ou vice-versa, dependendo da ordem de escrita de cada
   `_do_X()`.

5. **Reserva de idempotência.** `IdempotencyStore`/`PersistentIdempotencyStore` registra
   o resultado de uma operação (para replay exato, C6) em sua própria tabela/commit,
   distinto do commit que muta o recurso de negócio em si. Não existe uma transação única
   cobrindo "reservar a chave de idempotência" + "mutar o recurso" + "gravar o resultado
   cacheado" — um crash entre esses passos pode deixar a chave sem resultado cacheado
   (uma segunda tentativa reprocessaria) ou um resultado cacheado sem a mutação
   correspondente ter sido persistida (inconsistência entre o que a API "confirmou" e o
   estado real), a depender do ponto exato da falha.

6. **Mutação de recurso.** Qualquer fecho `_do_X()` que mute mais de um recurso de
   domínio (ex.: `publish_campaign`: `approval.status`, `record.external_resources`, e o
   evento de auditoria) grava cada um em uma chamada de persistência separada — não há
   isolamento all-or-nothing entre eles hoje.

7. **Fronteira real de transação.** Não existe, em `api/db.py`, um mecanismo de
   transação que abranja múltiplas tabelas/múltiplas chamadas a `RecordTable.put(...)`
   dentro do mesmo fecho. Cada `.put(...)` é sua própria transação SQLite completa
   (BEGIN/COMMIT implícitos por chamada) — não um `BEGIN` único envolvendo todas as
   escritas de uma operação de negócio. Construir essa fronteira real (savepoint/
   transação explícita cobrindo o fecho inteiro, com rollback coordenado em caso de
   falha parcial) é o que o `PRODUCTION_GATE` exige antes de operar em produção.

**Reiteração explícita, para não deixar dúvida:** o modelo de persistência atual
(`db_path` configurado, SQLite, uma transação por `RecordTable.put(...)`) **NÃO é
declarado production-safe** para nenhum dos 7 cenários acima. Isso vale tanto para
implantação em processo único (itens 1, 4-7) quanto, com risco adicional, para qualquer
topologia com mais de um processo/worker/réplica (itens 2-3). Nenhum destes itens foi
corrigido nesta sessão — este adendo é puramente documental, conforme a diretriz de não
declarar sucesso além do que o código realmente prova.

## Status

C6: `CORRIGIDO + TESTADO`. C5: `INVESTIGADO, achado real documentado, correção
arquitetural maior registrada como pendência explícita (não fabricada como resolvida)` —
ver adendo acima para a enumeração explícita e completa do `PRODUCTION_GATE` (achado 5,
auditoria independente #3). Nenhum merge/deploy nesta sessão.
