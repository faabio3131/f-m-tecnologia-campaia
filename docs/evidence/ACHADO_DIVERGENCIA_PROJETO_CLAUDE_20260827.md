# CampaIA — ACHADO: Divergência entre o Google Drive real e a "Project" do claude.ai

**Data:** 27 de agosto de 2026
**Autor:** Claude (Engenheiro Sênior), por ordem explícita do Diretor de investigar antes de prosseguir com qualquer novo documento
**Gatilho:** ao preparar um plano de permissões Meta App Review, encontrei que o documento base que eu estava lendo (via a ferramenta "Projects" do claude.ai, conectada a esta sessão) não corresponde a nenhum arquivo real no Google Drive. Investiguei antes de escrever qualquer coisa nova, por instrução direta do Diretor.

---

## RESUMO EXECUTIVO

**O Google Drive é a única fonte real e viva deste projeto.** A "Project" do claude.ai chamada "APP Marketing", anexada a esta sessão de trabalho, **não estava sincronizada ao Google Drive** — ela continha 52 documentos escritos diretamente nela por uma sessão anterior do Claude, em uma única rajada de ~72 segundos na noite de 26/08/2026, descrevendo uma versão **reescrita e parcialmente diferente** da mesma história (numeração de ADR diferente, IDs de decisão diferentes, datas diferentes, e em alguns pontos, decisões com texto diferente do que foi realmente registrado no Drive). Essa Project nunca foi atualizada depois daquela rajada — enquanto o Google Drive real continuou sendo atualizado ativamente, inclusive naquele dia, até às 17h50 (horário de Brasília: 14h50).

**Nenhum trabalho foi perdido.** O Drive real contém tudo: os documentos numerados `00` a `10`, o backend `campaia_core/` com 18 arquivos Python e testes, a pasta `evidence/` com os marcos registrados (Google Ads, Meta Business Manager, WhatsApp, etc.). Nada disso desapareceu — só não estava refletido na Project do claude.ai, que era uma cópia paralela desatualizada e, em pontos específicos, tinha seu conteúdo reescrito de forma diferente do original.

**Risco que isso gerou:** eu (Claude, nesta sessão) estava prestes a criar um novo documento (`META_APP_REVIEW_PERMISSIONS_PLAN.md`) e corrigir dois arquivos (`META_ADS.md`, `WHATSAPP_BUSINESS.md`) **que não existiam no Drive real** — eu teria subido esses arquivos para o local errado ou criado documentos desconectados da base real, sem perceber a tempo, se não tivesse parado para investigar a divergência.

---

## O QUE ERA CADA COISA, EXATAMENTE

### 1. Google Drive real (fonte de verdade)

Pasta raiz: **`CAMPAIA`** (ID `17TJFSYw7dV_e9Rso-k-JeNeOe_YlLnxi`), criada em 25/08/2026, com três subpastas:

- `docs/` (ID `1ZpfJFspuO7L-nSQ7sUdvQKN8WZZ1g8_x`) — documentos numerados `00_DIAGNOSTICO_INICIAL.md` até `10_PLANO_AQUI_VS_PC.md`, mais `CHECKLIST_CADASTROS_PLATAFORMAS_20260827.md` e a subpasta `evidence/`.
- `backend/campaia_core/` (ID `1qUAbtVmX6fHafW2MlHfHXrEcMo2y-5yx`) — arquivos Python (states.py, autonomy.py, budget.py, policy.py, infra.py, connectors.py, simulator.py, saga.py, errors.py, permissions.py, webhooks.py, outbox.py, ai_gateway.py, agents.py, sanitizer.py, ai_simulator.py, reconciliation.py, `__init__.py`).
- `backend/tests/` (ID `1pWobUq9Q6cRXW7MQtHw8K5FsbsGbwKDu`) — arquivos de teste (test_invariantes.py, test_saga.py, test_permissions.py, test_webhooks_outbox.py, test_reconciliation.py).

O documento `03_ADR_INICIAIS.md` (ID `1sTupkvVbcK0x3vQF6DHq4vqY_oxqPg1W`) já continha ADR-0001 até ADR-0013, incluindo uma nota de fechamento confirmando que nenhuma ADR permanecia pendente de abertura naquela data.

### 2. Project "APP Marketing" do claude.ai (cópia paralela desatualizada, não sincronizada)

Confirmado via `project_info`: `"sync_sources": []` — não havia nenhuma fonte de sincronização configurada. Os 52 documentos listados eram texto simples escrito diretamente na Project via chamadas de escrita, não uma leitura do Drive.

Evidência de que foi uma rajada única: 46 dos 52 documentos tinham `created_at` entre `23:17:47` e `23:18:59` UTC de 26/08/2026 — um intervalo de ~72 segundos, consistente com um processo automatizado de escrita em lote, não uma sincronização real de arquivos do Drive.

**Diferenças de conteúdo confirmadas** (não era apenas questão de nome de arquivo — o texto em si divergia):
- O Drive real registra a decisão de independência do CampaIA como **ADR-0002**, decisão **D-02**, com três opções (A/B/C), opção C escolhida.
- A Project do claude.ai registrava a mesma decisão como **ADR-001**, datada de 26/08/2026, com apenas duas opções (A/B), sem referência a "D-02", e usando a grafia "CampaIA" em vez de "CAMPAIA".

---

## LINHA DO TEMPO

1. **25/08/2026, ~22h28 UTC** — Pasta `CAMPAIA` criada no Drive real; numeração `D-0x`/`ADR-00xx` iniciada. Este é o esqueleto que continuou vivo e sendo atualizado.
2. **25/08/2026, 21h29 UTC (mais cedo no mesmo dia)** — Dois documentos mais antigos foram escritos na Project do claude.ai, ainda com a marca antiga "Kordena" — de uma fase anterior à própria renomeação para CampaIA.
3. **26/08/2026, 18h52–19h06 UTC** — Mais três documentos escritos na Project.
4. **26/08/2026, 23h17–23h18 UTC** — Rajada principal: 46 documentos escritos na Project em ~72 segundos, com uma reformulação completa da numeração de decisões e ADRs.
5. **26/08/2026 em diante** — O Drive real continuou sendo ativamente atualizado. **A Project do claude.ai não recebeu nenhuma atualização desde a rajada do passo 4.**

**Conclusão da linha do tempo:** a Project não era uma segunda linha de trabalho paralela e legítima — era uma cópia narrativa de um momento específico, escrita uma única vez e depois abandonada, enquanto o trabalho real continuou só no Drive.

---

## NADA FOI PERDIDO

O backend `campaia_core/` estava presente e íntegro no Drive real, e era ativamente referenciado pelo `03_ADR_INICIAIS.md` (ex.: ADR-0004 e ADR-0010 citam análise direta de `backend/campaia_core/saga.py` e `backend/tests/test_saga.py` como evidência técnica). Isso não aparecia na Project porque a Project nunca recebeu esse conteúdo — não porque foi apagado de algum lugar.

---

## FECHAMENTO (27/08/2026, mesma data)

O Diretor pediu uma comparação de conteúdo completa (não só timestamps) antes de decidir. Essa comparação foi feita documento por documento (todos os 52 da Project vs. todo o Drive, incluindo `evidence/`) e concluiu: nenhuma decisão, aprovação ou instrução do Diretor existia exclusivamente na Project — toda decisão de negócio já estava replicada ou superada no Drive. Foram identificadas 5 peças de documentação técnica de referência (sem decisão de negócio associada) que só existiam na Project: matriz RBAC/ABAC operação-por-operação, cronograma de rotação de segredos + resposta a vazamento, schema de log de auditoria, estrutura da matriz de rastreabilidade de requisitos, e uma tabela de preços de modelos de IA (baixa prioridade). Essas 5 peças foram copiadas para `docs/11_REFERENCIA_TECNICA_RECUPERADA_DA_PROJECT.md` antes de qualquer exclusão.

**Decisão do Diretor:** "pode apagar" — confirmado.

**Ação executada:** os 52 documentos da Project do claude.ai "APP Marketing" foram apagados via `project_delete`, um por um. Confirmado via `project_info`: a Project ficou zerada (`docs: []`, `knowledge_size: 0`).

**Achado adicional no mesmo fechamento:** a skill "Marketing AI System Design" (referenciada como base de todo o System Design do projeto) nunca havia sido salva no Drive — existia apenas em sandbox local efêmero desta sessão. Foi preservada integralmente (skill + `arquitetura-base.md`) em `docs/12_SKILL_MARKETING_AI_SYSTEM_DESIGN.md`, com nota de integridade (hash MD5 do arquivo original). Confirmado salvo via `get_file_metadata` antes de reportar ao Diretor.

**Estado final:** o Google Drive (pasta `CAMPAIA`) é a única fonte de documentação deste projeto, sem ambiguidade ou conteúdo paralelo. Este documento substitui a versão anterior (mesma pasta `evidence/`), que foi movida para a lixeira ao ser atualizado com esta seção de fechamento — mantendo a disciplina de que toda atualização de evidência gera um arquivo novo, nunca edição in-loco.

**Nota de correção técnica:** a primeira tentativa de recriar este arquivo nesta mesma rodada de fechamento falhou silenciosamente — foi convertido para Google Doc vazio (1 byte) por omissão do parâmetro de tipo de conteúdo na chamada de upload. Detectado e corrigido antes de prosseguir; o arquivo malformado foi movido para a lixeira e este é o substituto correto, em texto plano.
