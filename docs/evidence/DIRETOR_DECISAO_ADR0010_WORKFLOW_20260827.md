# FONTE PRIMÁRIA — DECISÃO ADR-0010: MOTOR DE WORKFLOW DURÁVEL PARA A SAGA

**Capturado em:** 27 de agosto de 2026
**Capturado por:** Claude, a partir de texto literal recebido do Diretor no turno corrente, após análise direta do código-fonte real já implementado no Drive
**Diretor:** Fábio Aluizio da Silva

---

## SEQUÊNCIA DOS FATOS

1. Após fechar D-08 (Google Cloud, região São Paulo), ficou pendente a escolha específica do motor de workflow durável para orquestrar a saga de publicação multicanal (ADR-0010, referenciada em `03_ADR_INICIAIS.md` como dependente de D-08).
2. Antes de recomendar entre Cloud Workflows e Temporal (auto-hospedado), Claude leu diretamente o código-fonte real já implementado e testado no Drive: `backend/campaia_core/saga.py` (10.411 bytes) e `backend/tests/test_saga.py` (14.724 bytes, parte dos 149 testes reais confirmados na auditoria de 27/08/2026).
3. **Achado técnico do código real:** a `PublicationSaga` implementada é uma execução síncrona, dentro de uma única chamada de função (`saga.run(...)`) — itera os canais na ordem definida, publica em cada um via `AdsConnector`, e em caso de `PARTIAL_FAILURE` aplica uma das três políticas de compensação já testadas (`PAUSE_ALL`, `KEEP_PARTIAL`, `ESCALATE_HUMAN`), retornando o resultado (`SagaOutcome`) ao final da mesma execução. Não há, no código real, nenhuma pausa de longa duração (horas/dias) aguardando evento externo ou aprovação humana no meio da execução da saga — a aprovação humana (`approval_id`) já é exigida ANTES de a saga iniciar, não durante.
4. Com base nesse achado, Claude recomendou tecnicamente **Cloud Workflows** em vez de Temporal auto-hospedado, com a seguinte justificativa: (a) o perfil real de execução da saga (curta, síncrona, sem esperas longas) é exatamente o caso de uso que Cloud Workflows resolve nativamente, sem exigir infraestrutura própria; (b) Temporal exigiria a equipe instalar e manter um cluster próprio, carga operacional desnecessária para o perfil de execução real hoje; (c) Temporal Cloud (a alternativa hospedada que evitaria essa carga operacional) não tem nenhuma região no Brasil, criando risco de conflito com a expectativa de residência de dados assumida em D-09; (d) se o produto evoluir para incluir esperas longas de verdade (ex.: pausa de dias aguardando aprovação humana em meio à execução), a decisão pode e deve ser reaberta nesse momento, com essa condição de gatilho explícita.
5. Diretor pediu explicação mais detalhada antes de decidir ("Quero entender melhor antes de decidir"). Claude explicou por analogia (regente contratado pela Google vs. orquestra particular própria) e reapresentou a recomendação com o mesmo fundamento técnico.
6. Diretor confirmou a recomendação técnica.

## RESPOSTA LITERAL FINAL DO DIRETOR

Selecionada via ferramenta de pergunta estruturada: **"Cloud Workflows (recomendação técnica)"**

## DECISÃO

**ADR-0010 = Cloud Workflows** (Google Cloud) é o motor de orquestração da saga de publicação multicanal do CAMPAIA, substituindo a alternativa de Temporal auto-hospedado.

**Gatilho de revisão explícito, registrado por transparência:** esta decisão deve ser reaberta se o desenho da saga evoluir para incluir esperas de longa duração (da ordem de horas ou dias) aguardando evento externo ou aprovação humana no meio da execução — cenário que o código real, na data desta decisão, não contempla. Até lá, Cloud Workflows é suficiente e operacionalmente mais simples para a equipe.

**Esta decisão não resolve:** o desenho detalhado de como a saga real (hoje uma função Python síncrona chamada diretamente) será adaptada para rodar como um Workflow do Google Cloud em produção (etapa de engenharia real, ainda não iniciada — depende da Fase 2/infraestrutura real com D-08 já aprovado).
