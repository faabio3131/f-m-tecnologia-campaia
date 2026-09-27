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

## Status

C6: `CORRIGIDO + TESTADO`. C5: `INVESTIGADO, achado real documentado, correção
arquitetural maior registrada como pendência explícita (não fabricada como resolvida)`.
Nenhum merge/deploy nesta sessão.
