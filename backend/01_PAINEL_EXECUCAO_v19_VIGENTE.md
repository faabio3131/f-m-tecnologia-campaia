# CAMPAIA — PAINEL DE EXECUÇÃO

**Atualizado em:** 19/09/2026 (RECONCILIAÇÃO CONTROLADA — repositório canônico definido pelo Diretor:
`faabio3131/f-m-tecnologia-campaia` [este repositório]. Bloco fiscal `FISC V2-16.5` importado por cherry-pick
da fonte histórica `faabio3131/CampaIA`, agora somente leitura. Ver ADR-0015
(`docs/13_ADR_0015_RECONCILIACAO_REPOSITORIO_CANONICO.md`), o registro de blocos executados desta versão, e
`docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` para o estado formal do app mobile)
**Regra:** este painel é a fonte de verdade da execução. Ao retomar qualquer sessão, reconstruir o estado a
partir de arquivos, código e testes reais — nunca apenas da memória da conversa (Ordem Mestra, item 18).

> **VERSÃO VIGENTE.** Substitui `01_PAINEL_EXECUCAO_v18_VIGENTE.md` (e as anteriores v1-v17). Versões antigas
> preservadas neste repositório Git para histórico — não apagar do controle de versão.

---

## PONTO DE RETOMADA

1. Ler este painel.
2. **Repositório canônico do CampaIA é `faabio3131/f-m-tecnologia-campaia` (este repositório), branch `main`.**
   `faabio3131/campaia` (`CampaIA`) é fonte histórica temporária, **somente leitura** — não commitar lá
   (ADR-0015).
3. Clonar/restaurar `backend/` a partir deste repositório Git — 5 subpastas: `campaia_core/` (agora com
   `fiscal_handoff.py`, importado nesta reconciliação), `tests/`, `api/`, `tests_api/`, `db/`.
4. Rodar `cd backend && python3 -m unittest discover -s tests` (sem `-t .` — `tests/` não tem `__init__.py`) → esperado: **267 aprovados** (domínio; 263 preexistentes + 4 novos de `test_fiscal_handoff.py`, importado nesta reconciliação — números confirmados por execução real na Etapa 8 da matriz de validação, não presumidos).
5. Rodar `cd backend && python3 -m unittest discover -s tests_api -t .` → esperado: **81 aprovados** (80 preexistentes + 1 novo: regressão do alias `daily_cap`, `test_budget_patch_accepts_contract_daily_cap_alias`).
5. Persistência é opcional: `create_app()` (sem argumento) continua 100% em memória; `create_app(db_path="...")` liga a um arquivo SQLite real. Ver `api/db.py` e `docs/evidence/EVIDENCIA_PERSISTENCIA_20260828.md`.
6. Catálogo de eventos formalizado como AsyncAPI 3.0 em `contracts/events.asyncapi.yaml` (24 eventos — contagem corrigida de uma caracterização anterior incorreta de 22). Verificar com `python3 contracts/validate_events_asyncapi.py`. Ver `docs/evidence/EVIDENCIA_B9_ASYNCAPI_20260829.md`.
7. Catálogo de 21 mensagens de erro em linguagem de usuário publicado em `docs/09_CATALOGO_ERROS_USUARIO.md` (v1.1.0) — os 3 códigos do Connector Hub que faltavam mapeamento (`AUTH_EXPIRED`, `VALIDATION_REJECTED`, `PARTIAL_FAILURE`) foram corrigidos em código em `api/errors.py` (`STATUS_BY_CODE`), sob autorização do Diretor ("pode corrigir não vamos deixar nenhum erro para trás"). P-19 **FECHADA** — ver `docs/evidence/EVIDENCIA_P19_FIX_20260904.md`.
8. B5 (motor de otimização e pacing) **CONCLUÍDO** (04/09) — `campaia_core/pacing.py` e `campaia_core/optimizer.py`, camada de sugestão apenas (F8.1); nenhuma execução automática (F8.2 permanece fora de escopo, confirmado pelo Diretor). Ver `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md`.
9. B7 (DDL e migrations do Postgres) **CONCLUÍDO** (04/09) — `backend/db/001_initial_schema.sql` (7 tabelas já persistidas hoje via `api/db.py`, RLS por tenant, CHECK nos enums do contrato, FK real `approvals→campaigns`) e `backend/db/verify_ddl_postgres.sh`, verificados de fato contra um Postgres 16 real descoberto nesta sandbox (não apenas sintaxe). Ver `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md`.
10. C1 (repositório Git + CI) **CONCLUÍDO E 100% OPERACIONAL** (05/09) — repositório publicado em `https://github.com/faabio3131/CampaIA` (privado), com histórico completo, `.gitignore`, `requirements.txt` (backend e contracts) e workflow do GitHub Actions (`.github/workflows/backend-tests.yml`) rodando as 2 suítes de teste + o validador do AsyncAPI a cada push. O Diretor escolheu GitHub como host remoto e autenticou o `gh` (GitHub CLI) e o Git na própria máquina via login por navegador (device code flow), sem nenhuma credencial passando por mim. A primeira execução real do CI no GitHub falhou (`ModuleNotFoundError: No module named 'httpx'` — dependência do `starlette.testclient` ausente de `backend/requirements.txt`); diagnosticado a partir do log real (`gh run view --log-failed`), corrigido (`httpx==0.28.1` adicionado, versão confirmada real no PyPI antes de fixar), e a execução seguinte confirmada com sucesso (`"conclusion": "success"`). Ver `docs/evidence/EVIDENCIA_C1_CI_HTTPX_FIX_20260905.md`.
11. Opção 2 (decisões D-03/D-05/D-06/D-08/D-09) — **RECONCILIAÇÃO CONCLUÍDA** (05/09): as 5 decisões já haviam sido tomadas pelo Diretor em 27/08/2026 (ver evidências correspondentes), mas este painel continuava listando-as como "Bloqueios" desde então. Corrigido em v17 — ver "Decisões registradas" e "Situação atual". Restam apenas 2 itens residuais, nenhum deles uma decisão do Diretor: **P-11** (preço exato do Memorystore/Redis para São Paulo, página do Google Cloud não confirma sem seleção manual de região) e a confirmação formal da emissão do CNPJ da F&M (em andamento com a contabilidade do Diretor, conforme seu próprio relato).
12. **B8 (especificação das telas do app) CONCLUÍDO** (05/09) — `docs/product/13_ESPECIFICACAO_TELAS_APP.md`, cobrindo F1–F10, com pesquisa de mercado de concorrentes (Madgicx, Revealbot, Smartly.io, AdCreative.ai, Meta Advantage+) e a especificação completa do Modo Automático de autonomia (Nível 2, com limite definido pelo cliente e ativação por senha de administrador), decisão de escopo tomada pelo Diretor em 05/09 e registrada em `docs/product/DECISOES_DIRETOR.md` item 5. Ver "Registro de blocos executados" desta versão.
13. Próximo bloco recomendado: **B6-mobile / implementação do app** (construção real das telas especificadas em B8) — ver "Situação atual" e "Blocos ainda construíveis sem PC". Não presumir escopo exato sem confirmar com o Diretor.

Se qualquer suíte não passar, corrigir antes de qualquer coisa nova.

---

## Situação atual

| Campo | Valor |
|---|---|
| **Fase atual** | Reconciliação de repositórios concluída (19/09). Repositório canônico definido: `faabio3131/f-m-tecnologia-campaia`. Bloco fiscal `FISC V2-16.5` (fail-closed, desconectado de campanha/orçamento) importado por cherry-pick da fonte histórica. App mobile (Fase 8, onboarding + fluxo de nova campanha) permanece em **QUARENTENA ARQUITETURAL** — não certificado, não evoluído nesta fase. Próximo passo autorizado: System Design da aplicação Web real (Ponto Zero Web) — ainda **não iniciado** |
| **Última tarefa concluída** | Reconciliação controlada `faabio3131/CampaIA` → `faabio3131/f-m-tecnologia-campaia`: bloco fiscal importado (3 commits, autoria preservada), teste de regressão do alias `daily_cap` adicionado (cobertura que estava genuinamente ausente), mobile registrado em quarentena formal, ADR-0015 registrando a decisão canônica. Ver "Registro de blocos executados" desta versão |
| **Status** | Núcleo de domínio determinístico **VALIDADO** — ver contagem real confirmada na Etapa 8 da matriz de validação desta reconciliação, abaixo; camada BFF/API **VALIDADA** com o alias `daily_cap` agora coberto por teste de regressão end-to-end; DDL do Postgres (B7) **CONSTRUÍDO E VERIFICADO CONTRA SERVIDOR REAL**; catálogo de eventos **FORMALIZADO** em AsyncAPI 3.0 (24 eventos); catálogo de erros de usuário **PUBLICADO E COMPLETO**; motor de otimização e pacing (B5) **CONSTRUÍDO**; repositório Git + CI **OPERACIONAL** neste repositório canônico; **B8 (especificação das telas do app) CONCLUÍDO** (documentação); **app mobile em QUARENTENA ARQUITETURAL** (código presente, não certificado, `flutter analyze`/`flutter test` nunca executados de fato — NÃO VERIFICADO); **bloco fiscal FISC V2-16.5 IMPORTADO**, permanece formalmente bloqueado por ausência de autoridade real de billing próprio da CampaIA |
| **Última evidência** | `docs/13_ADR_0015_RECONCILIACAO_REPOSITORIO_CANONICO.md`, `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md`, `docs/evidence/V2_16_5_FISCAL_INTEGRATION_BLOCKER_20260913.md` (importado) |
| **Bloqueios** | Bloco fiscal (`FISC V2-16.5`) permanece formalmente bloqueado: sem autoridade real de billing/pagamento próprio da CampaIA, o adapter não deve ser conectado a campanha/orçamento (proibição explícita, preservada nesta importação). Nenhuma outra decisão do Diretor pendente nesta reconciliação |
| **Próxima ação** | Autorização humana para iniciar o **System Design da aplicação Web real (Ponto Zero Web)** — não iniciado nesta reconciliação, por instrução explícita. Decisão de destino do app mobile (promover / reclassificar como protótipo descartável / manter quarentena) também pendente de autoridade humana, após o System Design |
| **Gate para avançar** | Gate Arquitetural (G1) — System Design Web ainda não produzido |

---

## Decisões registradas

| ID | Decisão | Resultado | ADR |
|---|---|---|---|
| — | Nome do produto | **CAMPAIA** | ADR-0001 **APROVADA** |
| D-02 | Relação com o Kordena | **Independente, com integração futura opcional via API pública** | ADR-0002 **APROVADA** |
| D-04 | Ordem de canais | **Google → Meta → conjunto → WhatsApp** | ADR-0007 **APROVADA** |
| D-07 | Ambiente de desenvolvimento | Construir em Python puro sem PC; PC com VS Code fica para o fim (Bloco C) | `10_PLANO_AQUI_VS_PC.md` |
| — | Credenciais e configurabilidade | Modos PLATFORM e BYO; travas não desativáveis | ADR-0013 PROPOSTA |
| — | Autorização | RBAC (6 papéis) + ABAC (tenant, unidade, valor, idade da autenticação) | ADR-0014 PROPOSTA |
| — | Política de salvamento | Um bloco só está concluído quando está salvo. Sem acumular para o fim do dia | Decisão do Diretor, 26/08 |
| — | Correção de painel + priorização BFF/API | Diretor: *"sim siga sua sugestão eu aprovo"* | Decisão do Diretor, 27/08 — `docs/evidence/GAP_ANALISE_BACKEND_CAMPAIA_20260827.md` |
| — | Fechar a lacuna P-12 (testes de IA/agentes/PII) | Diretor: *"fechar a lacuna"* | Decisão do Diretor, 27/08 — `docs/evidence/EVIDENCIA_P12_20260827.md` |
| — | Conferir a API contra o contrato literal (recomendação de engenharia B) | Diretor: *"faça assim segundo a sua recomendação B"* | Decisão do Diretor, 28/08 — `docs/evidence/EVIDENCIA_P14_20260828.md` |
| — | Corrigir todas as divergências encontradas na conferência | Diretor: *"corrigir tudo"* | Decisão do Diretor, 28/08 — `docs/evidence/EVIDENCIA_P14_20260828.md` |
| — | Corrigir a imprecisão de `connector-hub-e-eventos.md` antes de qualquer avanço, depois seguir para persistência e para os blocos pendentes | Diretor: *"fazer essa correção primeiro antes de avançar e não deixar nada para tras, e depois na sequencia as opções 1 e a 2 pode executar dessa forma"* | Decisão do Diretor, 28/08 — `docs/evidence/EVIDENCIA_P15_20260828.md` |
| — | Achado de processo comunicado ao Diretor de forma transparente assim que descoberto (código da P-14 nunca salvo no Drive), com remediação iniciada imediatamente, sem aguardar resposta | Comunicação enviada ao Diretor, 28/08 — `docs/evidence/EVIDENCIA_REMEDIACAO_P14_20260828.md` | — |
| — | Persistência real (opção 1) construída sobre a base corrigida, não sobre uma restauração do Drive; verificada independentemente antes de aceitar o trabalho do agente delegado | Execução conforme a sequência autorizada pelo Diretor, 28/08 — `docs/evidence/EVIDENCIA_PERSISTENCIA_20260828.md` | — |
| — | Instrução de processo: como engenheiro sênior, sempre apresentar as opções com uma recomendação claramente marcada, em vez de um menu neutro | Diretor: *"vc é o eng senior sempre de as opções com a marcação de recomendo na melhor entre as opções"* | Decisão de processo do Diretor, 28/08 |
| — | Recomendação de engenharia para "opção 2": priorizar B9 (AsyncAPI) sobre B5/B7/B8/B10 — B7 não verificável sem credenciais reais; B8/B10 dependem de D-03/D-05 em aberto; B5 tem o maior escopo e menor base já verificada; B9 formaliza um catálogo já corrigido e verificado (P-15) | Recomendação apresentada e executada sob a autorização "pode executar dessa forma" do Diretor, 28-29/08 — `docs/evidence/EVIDENCIA_B9_ASYNCAPI_20260829.md` | — |
| — | Recomendação de engenharia para o bloco seguinte a B9: priorizar B10 (catálogo de erros em linguagem de usuário) sobre B5/B7/B8 — B7 não verificável sem credenciais reais; B8 depende de D-03 em aberto; B5 tem o maior escopo restante; B10 é documentação sobre uma taxonomia de erro já estável no código | Diretor: *"b10"*, 03/09 — `docs/evidence/EVIDENCIA_B10_CATALOGO_ERROS_20260903.md` | — |
| — | Corrigir o gap da P-19 (3 códigos do Connector Hub sem mapeamento HTTP), sem deixar nenhuma inconsistência entre código e documentação | Diretor: *"pode corrigir não vamos deixar nenhum erro para trás"*, 04/09 — `docs/evidence/EVIDENCIA_P19_FIX_20260904.md` | — |
| — | Construir B5 (motor de otimização e pacing), seguindo a recomendação apresentada ao final do fechamento da P-19 | Diretor: *"siga sua recomendação"*, 04/09 — `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` | — |
| — | Escopo do B5: motor que apenas calcula e sugere otimizações (F8.1); execução automática (F8.2) permanece fora de escopo do MVP — decisão tomada mediante pergunta explícita, após a pesquisa de documentação revelar a distinção F8.1/F8.2 já registrada na Fase 0 de produto | Diretor: *"Motor que só sugere/calcula (Recomendado)"*, 04/09 — `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` | — |
| — | Construir B7 (DDL e migrations do Postgres), seguindo a recomendação apresentada ao final do fechamento do B5, com a ressalva (que se mostrou incorreta — ver Seção 5 da evidência) de que a verificação seria apenas estática | Diretor: *"sim concordo"*, 04/09 — `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` | — |
| — | Escopo do B7 (parte 1): DDL cobrindo apenas as entidades já persistidas hoje via `api/db.py` (7 tabelas), não um modelo de dados especulativo para módulos que hoje só existem em memória | Diretor: *"DDL apenas do que já é persistido (Recomendado)"*, 04/09 — `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` | — |
| — | Escopo do B7 (parte 2): multi-tenancy construída para o caso simples (tenant_id obrigatório + RLS em toda tabela), com `business_unit_id` nullable e extensível, sem aguardar a resolução da D-03 | Diretor: *"Construir para o caso simples, deixando extensível (Recomendado)"*, 04/09 — `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` | — |
| D-03 | Segmento-alvo do MVP | **Qualquer pequeno negócio local** | Diretor, 27/08/2026 — `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md`; reconciliado neste painel em 05/09 |
| D-05 | Objetivo do MVP (metas de conversão) | Diretor: *"os 4 já na primeira versão"* — as 4 metas de conversão completas já na v1, não um subconjunto | Diretor, 27/08/2026 — `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md`; reconciliado neste painel em 05/09 |
| D-06 | Modelo comercial de IA | Diretor: *"Franquia inclusa no plano + créditos extras pagos"* — modelo híbrido | Diretor, 27/08/2026 — `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md`; reconciliado neste painel em 05/09 |
| D-08 | Infraestrutura de nuvem | Google Cloud, região São Paulo. Diretor: *"pode seguir sua recomendação e depois faremos a pesquisa exata dos valores"* | Diretor, 27/08/2026 — `docs/evidence/DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md`; valores exatos de Cloud SQL, Pub/Sub, Cloud Workflows, Secret Manager e Cloud Storage confirmados em `docs/evidence/PESQUISA_VALORES_EXATOS_GOOGLE_CLOUD_20260827.md` — só o preço do Memorystore/Redis para São Paulo segue sem confirmação exata (P-11, página do GCP exige seleção manual de região); reconciliado neste painel em 05/09 |
| D-09 | Papéis de LGPD / entidade legal | Cliente = Controlador; F&M = Operadora | Diretor, 27/08/2026 — `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md`; pré-requisito formal (CNPJ da F&M) em andamento — Diretor: *"a abertura do cnpj já esta em andamento já resolvi isso com minha contabilidade"* (`docs/evidence/DIRETOR_ATUALIZACAO_CNPJ_FM_20260827.md`); reconciliado neste painel em 05/09 |
| — | Workflow de orquestração (infra) | Cloud Workflows (não Temporal auto-hospedado) — ADR-0010. Diretor: *"Cloud Workflows (recomendação técnica)"* | Diretor, 27/08/2026 — `docs/evidence/DIRETOR_DECISAO_ADR0010_WORKFLOW_20260827.md`; reconciliado neste painel em 05/09 |
| — | Marcos de cadastro em plataformas: Google Ads Manager criado ("F&M Tecnologia", ID 975-498-3401), acesso de teste ao developer token | Marco registrado, sem token literal guardado (segredo nunca registrado, por disciplina do projeto) | Diretor, 27/08/2026 — `docs/evidence/DIRETOR_MARCO_GOOGLE_ADS_MANAGER_CRIADO_20260827.md`; reconciliado neste painel em 05/09 |
| — | Construir C1 (repositório Git + CI) e, em sequência, resolver as decisões então listadas como bloqueio (D-03/D-05/D-06/D-08/D-09) | Diretor: *"faça a opção 1 e depois na sequencia a opção 2 para não ficar nada pendente para trás"* | Decisão do Diretor, 05/09 — ver "Registro de blocos executados" |
| — | Host Git remoto do C1: GitHub | Diretor criou o repositório `https://github.com/faabio3131/CampaIA` (privado) e autenticou `gh`/`git` na própria máquina via login por navegador, sem nenhuma credencial passando por mim | Decisão do Diretor, 05/09 |
| — | Construir B8 (especificação das telas do app), com pesquisa real de mercado antes de fechar a especificação, priorizando funcionalidade sobre visual premium | Diretor: *"importante agora no momento é a funcionalidade. Depois nós vamos dar aquele talento num visual premium final. Depois que tiver tudo pronto testado."* | Decisão do Diretor, 05/09 — `docs/product/13_ESPECIFICACAO_TELAS_APP.md` |
| — | Autonomia no MVP: oferecer Modo Manual (Nível 1) E Modo Automático (Nível 2, limite definido pelo cliente), como diferencial competitivo | Diretor: *"Sobre nós deixarmos tudo com, autorização humana... Mas também vamos ter a opção do cliente querer escolher deixar no automático... assim nos coloca à frente, está concorrente."* | Decisão do Diretor, 05/09 — `docs/product/DECISOES_DIRETOR.md` item 5 |
| — | Salvaguarda do Modo Automático: ativação exige senha de administrador, criando prova de autorização contra disputas futuras | Diretor: *"essa opção de colocar no automatico precisará ser validada por senha de adm assim não teremos riscos de clientes reclamar que não fez ou que não autorizou"* | Decisão do Diretor, 05/09 — `docs/product/DECISOES_DIRETOR.md` item 5 |
| — | Campanha nova sempre exige aprovação manual, mesmo com Modo Automático ativo — a senha + limite autorizam apenas otimização de campanhas já aprovadas, nunca publicação inicial | Diretor: *"não o automatico só funcionará com aprovação humana mediante senha de adm e valor pré-definido"*, confirmado como "Campanha nova sempre manual (Recomendado)" em pergunta de fechamento | Decisão do Diretor, 05/09 — `docs/product/DECISOES_DIRETOR.md` item 5, seção "Esclarecimento adicional" |
| — | Repositório canônico do CampaIA: `faabio3131/f-m-tecnologia-campaia`; `faabio3131/CampaIA` vira fonte histórica somente leitura | Decisão do Diretor, baseada em auditoria completa de 19/09/2026 | ADR-0015 **APROVADA** — `docs/13_ADR_0015_RECONCILIACAO_REPOSITORIO_CANONICO.md` |
| — | App mobile (`mobile/`) em quarentena arquitetural — sem evolução, sem declaração de prontidão, decisão de destino adiada para depois do System Design Web | Decisão do Diretor, 19/09/2026 | `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` |

---

## Estados por fase

Estados permitidos: `NÃO INICIADA`, `EM ANÁLISE`, `EM EXECUÇÃO`, `EM CORREÇÃO`, `BLOQUEADA`,
`IMPLEMENTADA — AGUARDANDO TESTES`, `EM VALIDAÇÃO`, `AGUARDANDO DEPENDÊNCIA EXTERNA`, `VALIDADA`, `CONCLUÍDA`.

| Fase | Escopo | Status | Gate de saída |
|---|---|---|---|
| 0 | Reconhecimento | **CONCLUÍDA** | — |
| 1 | Plano Mestre, ADRs, contratos, threat model, capability matrix | **EM VALIDAÇÃO** — contrato do BFF conferido campo a campo; catálogo de eventos agora formalizado em AsyncAPI 3.0 (ver Fase 3) | G1 Arquitetural |
| 2 | Fundação: projeto, auth, banco, segredos, CI | **EM EXECUÇÃO** — CI concluído e 100% operacional (C1, GitHub Actions rodando e verde); persistência da camada API real (SQLite opcional); restam auth de produção, segredos geridos e provisionamento real de infraestrutura de nuvem (Fase 5+) | G2 Segurança |
| 3 | Núcleo de campanhas + camada HTTP | **EM EXECUÇÃO** — 19 módulos de domínio (263 testes, incluindo `pacing.py`/`optimizer.py` do B5) + camada BFF/API sobre Starlette conforme ao contrato literal, com persistência real opcional (SQLite) e P-19 corrigida (80 testes), DDL do Postgres construído e verificado contra servidor real (B7, `backend/db/`), catálogo de eventos formalizado em AsyncAPI 3.0 (24 eventos), catálogo de erros de usuário publicado e completo (21 códigos, 10/10 valores de conector mapeados) e motor de otimização/pacing (B5) como camada de sugestão apenas, tudo efetivamente salvo no Drive | G6 parcial |
| 4 | IA: gateway multimodelo, agentes, evals | **EM EXECUÇÃO** — código testado (88 testes, P-12 fechada 27/08, inalterado); apenas evals seguem pendentes | G3 IA |
| 5 | Google Ads | NÃO INICIADA | G4 Integração |
| 6 | Meta (Facebook + Instagram) | NÃO INICIADA | G4 Integração |
| 7 | WhatsApp Business | NÃO INICIADA | G4 Integração |
| 8 | Aplicativo mobile completo | **EM ANÁLISE** — especificação de telas (B8) **CONCLUÍDA** (`docs/product/13_ESPECIFICACAO_TELAS_APP.md`); implementação real do app ainda NÃO INICIADA (já tem uma API real e conforme ao contrato para consumir, ainda que sem persistência) | G5 Mobile |
| 9 | Analytics e otimização | NÃO INICIADA — `GET /insights` da API devolve lista vazia, honestamente, sem inventar dado; formato do ponto agora bate com o contrato | G6 Financeiro |
| 10 | Segurança e robustez | NÃO INICIADA | G2 final |
| 11 | Homologação | NÃO INICIADA | G7 Final |
| 12 | Produção | NÃO INICIADA | Autorização expressa do Diretor |

---

## Código construído (`backend/campaia_core/` — B5 novo nesta sessão)

| Módulo | Responsabilidade | Testes confirmados no Drive |
|---|---|---|
| `errors.py` | Taxonomia canônica de erros | — |
| `states.py` | Máquina de estados com guardas | 8 (dentro de `test_invariantes.py`) |
| `autonomy.py` | Níveis 0–3 e gatilhos de aprovação | (dentro de `test_invariantes.py`) |
| `budget.py` | Reservas de verba e tetos | (dentro de `test_invariantes.py`) |
| `policy.py` | Policy Engine e emissão de autorização | (dentro de `test_invariantes.py`) |
| `infra.py` | Idempotência e Capability Registry | (dentro de `test_invariantes.py`) |
| `connectors.py` | Contrato dos adaptadores (3 de 14 operações canônicas) + `SecretRef` | (dentro de `test_saga.py`) |
| `simulator.py` | Provider Simulator com falhas programáveis | (dentro de `test_saga.py`) |
| `saga.py` | Publicação multicanal e compensação | `test_saga.py` — 24 testes |
| `permissions.py` | RBAC (6 papéis) + ABAC, segregação de funções | `test_permissions.py` — 32 testes |
| `webhooks.py` | Assinatura HMAC, replay, dedupe | (dentro de `test_webhooks_outbox.py`) |
| `outbox.py` | Outbox/Inbox, dual write | `test_webhooks_outbox.py` — 23 testes |
| `reconciliation.py` | **B3** — reconciliador de divergência | `test_reconciliation.py` — 26 testes |
| `ai_gateway.py` | Seleção de provedor, custo, schema, fallback, circuit breaker, trava de credencial | `test_ai_gateway.py` — 42 testes |
| `ai_simulator.py` | Provedor de IA simulado com falhas programáveis | `test_ai_simulator.py` — 13 testes |
| `sanitizer.py` | Pseudonimização de PII (CPF, CNPJ, e-mail, telefone, cartão, CEP) | `test_sanitizer.py` — 19 testes |
| `agents.py` | 6 agentes como funções puras; nunca inventa contexto faltante | `test_agents.py` — 14 testes |
| `pacing.py` | **B5 (04/09)** — cálculo de ritmo de gasto vs. período orçamentário, com sugestão de teto diário ajustado | `test_pacing.py` — 14 testes |
| `optimizer.py` | **B5 (04/09)** — 4 regras de sugestão (F8.1); nunca executa, apenas emite `Recommendation` imutável com `ActionKind` que exige aprovação humana via `autonomy.py` | `test_optimizer.py` — 12 testes |
| `fiscal_handoff.py` | **FISC V2-16.5 (importado 19/09 por cherry-pick de `faabio3131/CampaIA`)** — boundary fail-closed para handoff fiscal de billing próprio da CampaIA; aceita somente um `SettledOwnBillingFact` já assentado por domínio autoritativo de billing (inexistente hoje); estado sempre `PENDING_CAPABILITY`; deliberadamente **não conectado** a campanha, orçamento ou gasto de mídia — nenhum provider, município, alíquota, homologação ou `PRODUCTION_APPROVED` | `test_fiscal_handoff.py` — 4 testes |

**Total domínio: ver contagem real confirmada na Etapa 8 da matriz de validação desta reconciliação (abaixo), não presumida a partir de somas de versões anteriores.**

## Código construído (`backend/api/` e `backend/tests_api/`)

| Arquivo | Papel | Alterado nesta sessão? |
|---|---|---|
| `api/main.py` | App Starlette, montagem de rotas, `create_app(db_path=...)` | Não |
| `api/deps.py` | Autenticação por token fixo (fixture local, não é credencial real), step-up, idempotência | Não |
| `api/state.py` | Estado da aplicação, `AppState(db_path=...)` | Não |
| `api/repositories.py` | Repositórios (memória ou SQLite via `_attach_persistence`/`_wrap_loaded`) | Não |
| `api/db.py` | Persistência SQLite opcional (stdlib apenas) | Não |
| `api/errors.py` | Taxonomia de erro canônica | **Sim (04/09)** — P-19: 3 entradas novas em `STATUS_BY_CODE` (`AUTH_EXPIRED`, `VALIDATION_REJECTED`, `PARTIAL_FAILURE`); 3500→4509 bytes |
| `api/models.py` | Schemas Pydantic | Não |
| `api/helpers.py` | Serializers | Não |
| `api/routes_*.py` (9 arquivos) | Rotas HTTP | Não |
| `tests_api/*.py` (5 arquivos, 72 testes) | Testes da camada HTTP + persistência | Não |
| `tests_api/test_errors_p19.py` | **(04/09)** — 8 testes provando a correção da P-19 de ponta a ponta via `from_domain_error()` | — |
| `tests_api/test_smoke_endpoints.py` | **Alterado (19/09, reconciliação)** — 1 teste novo: `test_budget_patch_accepts_contract_daily_cap_alias`, cobrindo o alias do Achado 18 (`daily_cap` literal do contrato) end-to-end via cliente HTTP real, cobertura que estava genuinamente ausente (toda a cobertura anterior usava `new_daily_cap`) | Novo nesta reconciliação |

**Total camada HTTP: ver contagem real confirmada na Etapa 8 da matriz de validação desta reconciliação (abaixo).** Construída sobre Starlette, não FastAPI —
`pypi.org` está fora da lista de permissão de rede do sandbox onde foi construída; ver
`docs/evidence/EVIDENCIA_BFF_API_20260827.md` para o desvio completo.

## Código construído (`backend/db/` — B7 novo nesta sessão)

| Arquivo | Papel | Verificação |
|---|---|---|
| `db/001_initial_schema.sql` | DDL do Postgres (migration única) para as 7 tabelas já persistidas hoje via `api/db.py`, com RLS por tenant, `CHECK` nos enums do contrato, FK real `approvals→campaigns`, chave composta em `idempotency`, `business_unit_id` sempre nullable (D-03 em aberto) | Aplicado e testado contra Postgres 16 real (não apenas sintaxe) |
| `db/verify_ddl_postgres.sh` | Script reproduzível que cria banco/papel de teste próprios, aplica a migration e prova com queries reais: schema aplica sem erro, RLS isola tenants (inclusive o caso "sem contexto = zero linhas", falha fechado), `CHECK` rejeita/aceita corretamente, FK rejeita referência inexistente, chave composta de `idempotency` rejeita duplicata | Executado com sucesso 2x seguidas (reprodutibilidade), zero rastro deixado no servidor após cada execução |

Não altera nenhum módulo de `campaia_core/` ou `api/` — é puramente SQL + shell novos. Ver
`docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` para a transcrição completa da verificação real.

## Contratos (`contracts/` — B9 fechado nesta sessão)

| Arquivo | Papel | Novo/alterado nesta sessão? |
|---|---|---|
| `contracts/event-envelope.schema.json` | Envelope canônico de eventos (JSON Schema draft 2020-12) | Não — apenas lido e reproduzido |
| `contracts/campaign-brief.schema.json`, `campaign-plan.schema.json`, `ai-gateway.schema.json` | Schemas de payload referenciados pela descrição do AsyncAPI | Não — apenas lidos para contexto |
| `contracts/connector-hub-e-eventos.md` | Fonte de verdade do catálogo de 24 eventos (Seção 2) | Não — apenas lido; usado para extrair o catálogo programaticamente |
| `contracts/events.asyncapi.yaml` | **Novo** — especificação AsyncAPI 3.0 formalizando os 24 eventos (24 `channels`/`operations`/`components.messages`), todos referenciando o `EventEnvelope` | Novo nesta sessão (B9) |
| `contracts/validate_events_asyncapi.py` | **Novo** — script de verificação reproduzível (sintaxe YAML, cobertura 1:1, integridade de `$ref`, fidelidade do schema, exemplo validável) | Novo nesta sessão (B9) |

---

## Blocos ainda construíveis sem PC

| # | Item | Estado |
|---|---|---|
| — | Camada BFF/API (HTTP) | **CONCLUÍDA** (27/08) |
| — | Testes automatizados para `ai_gateway.py`, `ai_simulator.py`, `sanitizer.py`, `agents.py` (P-12) | **CONCLUÍDA** (27/08) |
| — | Conferência campo a campo entre `api/` e o YAML literal + correção de todas as divergências (P-14) | **CONCLUÍDA** (28/08) |
| — | Persistência real (banco de dados) para os Stores hoje em memória | **CONCLUÍDA** (28/08) — SQLite opcional via `api/db.py`, 8 novos testes |
| B3 | Reconciliador de divergência | **CONCLUÍDO** (confirmado 27/08, 26 testes) |
| B9 | AsyncAPI do catálogo de eventos | **CONCLUÍDO** (29/08) — `contracts/events.asyncapi.yaml`, 24 eventos, ver evidência |
| B10 | Catálogo de erros em linguagem de usuário | **CONCLUÍDO** (03/09) — `docs/09_CATALOGO_ERROS_USUARIO.md`, atualizado para v1.1.0 em 04/09 após a correção da P-19, 21 códigos cobertos, ver evidência |
| — | Correção da P-19 (gap de mapeamento HTTP no Connector Hub) | **CONCLUÍDA** (04/09) — `api/errors.py`, 3 entradas novas + 8 testes, ver evidência |
| B5 | Motor de otimização e pacing | **CONCLUÍDO** nesta sessão (04/09) — `pacing.py` + `optimizer.py`, camada de sugestão apenas (F8.1); F8.2 fora de escopo por confirmação do Diretor; 26 testes; ver evidência |
| B7 | DDL e migrations do Postgres | **CONCLUÍDO** nesta sessão (04/09) — `db/001_initial_schema.sql` + `db/verify_ddl_postgres.sh`, verificado de fato contra um Postgres 16 real descoberto nesta sandbox (não apenas sintaxe); ver evidência |
| B8 | Especificação das telas do app | **CONCLUÍDO** (05/09) — `docs/product/13_ESPECIFICACAO_TELAS_APP.md`, cobrindo F1–F10 com pesquisa real de mercado de concorrentes e a especificação do Modo Manual/Automático de autonomia (decisão do Diretor de 05/09); ver `docs/product/DECISOES_DIRETOR.md` item 5 |
| C1 | Repositório Git + CI | **CONCLUÍDO E 100% OPERACIONAL** (05/09) — publicado em `https://github.com/faabio3131/CampaIA` (privado), histórico Git, `.gitignore`, `requirements.txt` (backend e contracts) e workflow do GitHub Actions (`.github/workflows/backend-tests.yml`) rodando e verde a cada push; dois defeitos de portabilidade corrigidos durante a construção + um erro real de dependência de CI (`httpx` ausente) corrigido após a primeira execução real no GitHub (ver evidência) |
| — | Achado 18 — `BudgetPatchRequest` (`api/models.py`) não aceitava o nome de campo `daily_cap` exigido pelo contrato (`bff-openapi.yaml`), só `new_daily_cap` | **CORRIGIDO** (05/09) — alias `daily_cap`/`new_daily_cap` com `populate_by_name=True`; ambos os nomes validam, `extra="forbid"` preservado; **teste de regressão end-to-end adicionado em 19/09** (cobertura que estava ausente) |
| B8-mobile | Implementação do app mobile (Fase 8: onboarding + fluxo de nova campanha) | **PARCIALMENTE IMPLEMENTADO, EM QUARENTENA ARQUITETURAL** (construído antes de 19/09, fora desta sessão) — `mobile/` presente, mas `flutter analyze`/`flutter test` nunca executados de fato (SDK ausente, confirmado novamente em 19/09); não certificado, não evoluído nesta fase; decisão de destino pendente do System Design Web; ver `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` |
| FISC | `FISC V2-16.5` — boundary fail-closed de billing próprio da CampaIA | **IMPLEMENTADO E IMPORTADO** (19/09, cherry-pick de `faabio3131/CampaIA`) — `fiscal_handoff.py` + 4 testes; **permanece formalmente bloqueado**: sem autoridade real de billing/pagamento próprio, não deve ser conectado a campanha/orçamento; ver `docs/evidence/V2_16_5_FISCAL_INTEGRATION_BLOCKER_20260913.md` |
| RECON | Reconciliação de repositórios (`faabio3131/CampaIA` → `faabio3131/f-m-tecnologia-campaia`) | **CONCLUÍDA** (19/09) — ADR-0015, bloco fiscal importado, fix `daily_cap` confirmado coerente + teste de regressão adicionado, mobile em quarentena formal; ver "Registro de blocos executados" |

**Recomendação de engenharia:** com a reconciliação concluída, o próximo bloco autorizado é o **System Design
da aplicação Web real (Ponto Zero Web)** — ainda não iniciado por instrução explícita desta reconciliação. A
decisão sobre o destino do app mobile (`mobile/`, em quarentena) deve ser tomada depois desse System Design,
não antes.

---

## Artefatos de documentação e contratos

| Artefato | Arquivo | Status |
|---|---|---|
| Diagnóstico inicial | `docs/00_DIAGNOSTICO_INICIAL.md` | CONCLUÍDO |
| Plano Mestre | `docs/02_PLANO_MESTRE.md` | CONCLUÍDO (v0.1) |
| ADRs | `docs/03_ADR_INICIAIS.md` | 3 aprovadas, 5 propostas (inclui ADR-0014, ainda não escrita como arquivo próprio) |
| ADR-0015 reconciliação de repositórios | `docs/13_ADR_0015_RECONCILIACAO_REPOSITORIO_CANONICO.md` | **APROVADA** (19/09) |
| Registro de quarentena do mobile | `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` | **CONCLUÍDO** (19/09) |
| Decisões do Diretor | `docs/04_DECISOES_DO_DIRETOR.md` | 4 resolvidas, 5 abertas |
| Arquitetura Mestra V2 | `docs/05_ARQUITETURA_V2.md` | PROPOSTA |
| Modelo lógico de dados | `docs/06_MODELO_DADOS.md` | PROPOSTA (v0.1) |
| Threat model | `docs/07_THREAT_MODEL.md` | **PARCIAL** (T-02 coberta por código) |
| Capability Matrix | `docs/08_CAPABILITY_MATRIX.md` | **PARCIAL** v0.2 |
| ADR-0013 credenciais | `docs/09_ADR_0013_...md` | PROPOSTA |
| Plano aqui vs PC | `docs/10_PLANO_AQUI_VS_PC.md` | Vivo |
| Contratos JSON Schema (4) | `contracts/*.schema.json` | Sintaxe validada |
| OpenAPI do BFF | `contracts/bff-openapi.yaml` | Rascunho (`1.0.0-draft`); implementação em `backend/api/` conferida campo a campo (P-14) |
| Connector Hub + eventos | `contracts/connector-hub-e-eventos.md` | PROPOSTA — corrigida em 28/08 (P-15); catálogo de eventos (Seção 2) agora também formalizado como AsyncAPI 3.0 (B9, 29/08) |
| **Catálogo de eventos AsyncAPI** | `contracts/events.asyncapi.yaml` | **CONCLUÍDO** (29/08) — 24 eventos, verificado por script próprio |
| **Catálogo de erros em linguagem de usuário** | `docs/09_CATALOGO_ERROS_USUARIO.md` | **CONCLUÍDO** (03/09, atualizado para v1.1.0 em 04/09) — 21 códigos cobertos, 10/10 valores de `ConnectorErrorCode` mapeados |
| Análise de lacunas reais do backend | `docs/evidence/GAP_ANALISE_BACKEND_CAMPAIA_20260827.md` | CONCLUÍDO |
| Evidência da camada BFF/API | `docs/evidence/EVIDENCIA_BFF_API_20260827.md` | CONCLUÍDO |
| Evidência do fechamento da P-12 | `docs/evidence/EVIDENCIA_P12_20260827.md` | CONCLUÍDO |
| Evidência do fechamento da P-14 | `docs/evidence/EVIDENCIA_P14_20260828.md` | CONCLUÍDO |
| Evidência do fechamento da P-15 | `docs/evidence/EVIDENCIA_P15_20260828.md` | CONCLUÍDO |
| Evidência do achado e remediação: código da P-14 nunca salvo no Drive (P-16) | `docs/evidence/EVIDENCIA_REMEDIACAO_P14_20260828.md` | CONCLUÍDO |
| Evidência do fechamento da persistência real (opção 1 do Diretor) | `docs/evidence/EVIDENCIA_PERSISTENCIA_20260828.md` | CONCLUÍDO |
| Evidência do fechamento do B9 (AsyncAPI) | `docs/evidence/EVIDENCIA_B9_ASYNCAPI_20260829.md` | CONCLUÍDO |
| Evidência do fechamento do B10 (catálogo de erros) | `docs/evidence/EVIDENCIA_B10_CATALOGO_ERROS_20260903.md` | CONCLUÍDO |
| Evidência do fechamento da P-19 (gap de mapeamento HTTP no Connector Hub) | `docs/evidence/EVIDENCIA_P19_FIX_20260904.md` | CONCLUÍDO |
| Evidência do fechamento do B5 (motor de otimização e pacing) | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` | CONCLUÍDO |
| Evidência do fechamento do B7 (DDL e migrations do Postgres) | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` | CONCLUÍDO |
| **Repositório Git + CI (C1)** | `https://github.com/faabio3131/CampaIA` (privado); cópias locais em `Desktop/CAMPAIA/campaia_repo.zip` e `Desktop/CAMPAIA/campaia.bundle` no PC do Diretor | **100% OPERACIONAL** (05/09) — CI (`.github/workflows/backend-tests.yml`) rodando e verde a cada push |
| Evidência da correção do CI (C1) | `docs/evidence/EVIDENCIA_C1_CI_HTTPX_FIX_20260905.md` | CONCLUÍDO (05/09) |
| **Especificação das telas do app (B8)** | `docs/product/13_ESPECIFICACAO_TELAS_APP.md` | **CONCLUÍDO** (05/09) — F1–F10, pesquisa de mercado de concorrentes, fluxo completo de nova campanha, Modo Manual/Automático de autonomia |
| Decisões do Diretor de 05/09 (autonomia Nível 2 no MVP) | `docs/product/DECISOES_DIRETOR.md` item 5 | CONCLUÍDO (05/09) — citações literais do Diretor, propagado para `CAMPAIA_PRODUCT_CHARTER.md` e `OUT_OF_SCOPE.md` |
| Decisões do Diretor de 27/08 (D-03, D-05, D-06, ADR-0010, marcos Google Ads/CNPJ) | `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md`, `DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md`, `PESQUISA_VALORES_EXATOS_GOOGLE_CLOUD_20260827.md`, `DIRETOR_DECISAO_ADR0010_WORKFLOW_20260827.md`, `DIRETOR_MARCO_GOOGLE_ADS_MANAGER_CRIADO_20260827.md`, `DIRETOR_ATUALIZACAO_CNPJ_FM_20260827.md` | CONCLUÍDO (27/08) — reconciliadas com este painel em 05/09 |

---

## Pendências técnicas abertas

| ID | Pendência | Efeito se confirmada |
|---|---|---|
| P-04 | Marca CAMPAIA: INPI, domínio, lojas | Bloqueia identidade visual e submissão às lojas |
| P-08 | Meta: Advantage+ Shopping/App não criáveis pela Marketing API desde a v25.0 (fonte secundária) | Remove tipos de campanha do conjunto oferecível |
| P-09 | WhatsApp: mudanças de preço em 01/08/2026 e 01/10/2026 | Preço vira dado versionado com data de vigência |
| P-10 | Documentação da Meta que exige login | Confirmação definitiva exige acesso autenticado |
| P-12 | ~~`ai_gateway.py`, `ai_simulator.py`, `sanitizer.py`, `agents.py` sem teste automatizado confirmado no Drive~~ | **FECHADA em 27/08** — 88 testes reais, `docs/evidence/EVIDENCIA_P12_20260827.md` |
| P-13 | Camada BFF/API construída sobre Starlette, não FastAPI (bloqueio de rede a `pypi.org` no sandbox) | Se FastAPI for exigido especificamente (ex.: docs OpenAPI automáticas), precisa de ambiente com acesso a índice de pacotes Python |
| P-14 | ~~Implementação da API seguiu paráfrase do contrato, não o YAML de `bff-openapi.yaml` linha a linha~~ | **FECHADA em 28/08** — 17 divergências encontradas e corrigidas, `docs/evidence/EVIDENCIA_P14_20260828.md` |
| P-15 | ~~`contracts/connector-hub-e-eventos.md` descrevia a interface do conector no presente, como se já implementada para 3 plataformas reais~~ | **FECHADA em 28/08** — corrigido para contrato-alvo + nota de status real, `docs/evidence/EVIDENCIA_P15_20260828.md` |
| P-16 | ~~O código corrigido da P-14 nunca foi de fato enviado ao Google Drive~~ | **FECHADA em 28/08** — 11+3 arquivos reenviados e byte a byte verificados; contagem de domínio corrigida (233→237); `docs/evidence/EVIDENCIA_REMEDIACAO_P14_20260828.md` |
| P-17 | ~~Catálogo de eventos caracterizado como tendo "22 eventos" em registros anteriores deste projeto (inclusive resumos de sessão); a tabela-fonte real (`connector-hub-e-eventos.md`, Seção 2) tem 23 linhas, uma das quais agrupa 2 eventos distintos, totalizando 24~~ | **FECHADA em 29/08**, descoberta durante a extração programática do catálogo para o B9 (AsyncAPI); nenhum evento foi adicionado/removido — apenas a contagem foi corrigida; `docs/evidence/EVIDENCIA_B9_ASYNCAPI_20260829.md` |
| P-18 | Tentativa de instalar `@asyncapi/cli` (npm) e de baixar o meta-schema JSON oficial do AsyncAPI 3.0 (GitHub raw) para validação de referência — ambas bloqueadas por `403 Forbidden` da política de rede do sandbox | Verificação do B9 feita por script de validação próprio (sintaxe YAML real, cobertura 1:1, integridade de `$ref`, fidelidade de schema, exemplo validável), não pela ferramenta de referência oficial; documentado com transparência em `docs/evidence/EVIDENCIA_B9_ASYNCAPI_20260829.md`. Não bloqueia o fechamento do bloco, mas fica registrado como limitação de ambiente |
| P-19 | ~~3 dos 10 códigos de `ConnectorErrorCode` (`campaia_core/connectors.py`) — `AUTH_EXPIRED`, `VALIDATION_REJECTED`, `PARTIAL_FAILURE` — não têm entrada em `STATUS_BY_CODE` (`api/errors.py`); achado durante o B10, confirmado que `VALIDATION_REJECTED` já é levantado por código real em `saga.py:191`~~ | **FECHADA em 04/09** — sob autorização do Diretor ("pode corrigir não vamos deixar nenhum erro para trás"): 3 entradas adicionadas a `STATUS_BY_CODE` (`AUTH_EXPIRED`→401, `VALIDATION_REJECTED`→422, `PARTIAL_FAILURE`→207), com racional documentado; 8 novos testes provam a correção via `from_domain_error()`; 237+80=317 testes, zero regressão; catálogo B10 atualizado para v1.1.0 em sincronia; `docs/evidence/EVIDENCIA_P19_FIX_20260904.md`. Anomalia não relacionada, documentada e não corrigida: discrepância de 1 byte em `api/routes_approvals.py` (metadado do Drive vs. conteúdo real), root-caused como externa a este trabalho |
| P-20 | ~~Upload do documento de evidência do B5 divergiu em 1 byte do original local (13344 vs. 13343); root-cause por download/diff programático revelou uma corrupção real de conteúdo (um "à" virou "a"), causada por um erro de transcrição meu ao reproduzir a string base64 na chamada da ferramenta de upload — não um comportamento do Drive~~ | **FECHADA em 04/09** — arquivo local corrigido, recodificado e reenviado; a versão corrigida foi verificada por download/diff byte a byte completo (não apenas contagem de tamanho) antes de ser aceita como correta; versão com erro trashada no Drive; `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md`. Reforça a disciplina já em vigor no projeto: contagem de bytes sozinha não basta — divergência de tamanho exige investigação por diff de conteúdo, nunca apenas reenvio |
| P-11 | Preço exato do Memorystore/Redis (Google Cloud) para a região São Paulo (`southamerica-east1`) — a página oficial de preços é renderizada por JavaScript com seletor de região; buscas e fetch de página só retornam a tabela da região padrão (Iowa) | Orçamento de infraestrutura (D-08) fica completo em todos os demais itens (Cloud SQL, Pub/Sub, Cloud Workflows, Secret Manager, Cloud Storage já confirmados — `docs/evidence/PESQUISA_VALORES_EXATOS_GOOGLE_CLOUD_20260827.md`), exceto este; não bloqueia nenhum bloco de construção, só o orçamento final |
| P-21 | Este painel (`v15` e anteriores) listava D-03, D-05, D-06, D-08 e D-09 como "Bloqueios" em aberto desde pelo menos 04/09/2026, quando na verdade o Diretor já as havia decidido em 27/08/2026 (evidências correspondentes existiam no Drive, mas o painel nunca foi atualizado para refletir isso) | **FECHADA em 05/09** — descoberto durante a reconstrução do repositório C1 (ao baixar `docs/evidence/` por completo, os 6 arquivos de decisão de 27/08 foram lidos na íntegra); comunicado ao Diretor com transparência; painel corrigido nesta versão (ver "Decisões registradas" e "Situação atual") |
| P-22 | App mobile (`mobile/`) nunca teve `flutter analyze`/`flutter test` executados de fato, em nenhum ambiente documentado até 19/09/2026 (SDK ausente, confirmado novamente nesta reconciliação) | Bloqueia qualquer declaração de prontidão do mobile; mobile permanece em quarentena arquitetural até validação real com SDK, conforme `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` |
| P-23 | Repositório canônico do CampaIA definido nesta reconciliação (`faabio3131/f-m-tecnologia-campaia`); `faabio3131/CampaIA` não deve receber mais nenhum commit a partir de 19/09/2026 | Risco: se alguém continuar commitando na fonte histórica por hábito, uma nova divergência se reabre; mitigação em ADR-0015 |
| P-24 | System Design da aplicação Web real (Ponto Zero Web) ainda não produzido — nem este repositório nem a fonte histórica têm hoje um frontend Web | Bloqueia o início de qualquer construção de frontend; é o próximo bloco recomendado, pendente de autorização humana |

---

## Dependências externas

| Dependência | Necessária para | Estado |
|---|---|---|
| Google Cloud project + OAuth client | Fase 5 | Não iniciada |
| Developer token Google Ads (Test → Explorer → Basic) | Fase 5 | Não iniciada — Basic: alvo de ~5 dias úteis |
| Meta App + Business portfolio + verificação | Fase 6 | Não iniciada |
| Meta: permissões + Marketing API Access Tier | Fase 6 produção | Exige ≥500 chamadas em 15 dias com erro <15% |
| WhatsApp Business Account + número + templates | Fase 7 | Não iniciada |
| Chaves OpenAI e Gemini | Fase 4 | D-06 resolvida (27/08 — modelo híbrido: franquia inclusa + créditos extras pagos); aquisição das chaves ainda não iniciada |
| Nuvem + orçamento de infraestrutura | Fase 2 | D-08 resolvida (27/08 — Google Cloud, São Paulo); orçamento exato pendente só do preço do Memorystore/Redis em São Paulo (P-11) |
| Apple Developer + Google Play | Fase 12 | Não iniciada |

Nenhum item acima foi solicitado, obtido ou simulado.

**Caminho crítico:** o tier da Meta exige histórico real de chamadas com erro baixo. A qualidade do adaptador
Meta é pré-requisito da aprovação, não refinamento posterior.

---

## Registro de blocos executados

| Data | Bloco | Fase | Resultado | Evidência |
|---|---|---|---|---|
| 25/08/2026 | Reconhecimento + Plano Mestre inicial | 0 → 1 | Diagnóstico, painel, plano, 6 ADRs, 7 decisões abertas | `docs/` |
| 25/08/2026 | Decisões D-02/D-04 + camada de arquitetura | 1 | Arquitetura V2, contratos, modelo de dados, threat model | `docs/`, `contracts/` |
| 25/08/2026 | OpenAPI do BFF + Capability Matrix v0.2 | 1 | ADR-0007 aprovada; API contratada e checada | checagens C1–C3 |
| 25/08/2026 | ADR-0013 + núcleo determinístico | 3 | 6 módulos; 40 testes | saída do unittest |
| 25/08/2026 | Provider Simulator + Saga multicanal | 3 | 9 módulos; 64 testes; D-07 resolvida | `10_PLANO_AQUI_VS_PC.md` |
| 25/08/2026 | Cópia para o Google Drive | — | 29 arquivos, tamanhos conferidos byte a byte | Pasta CAMPAIA |
| 26/08/2026 | B6 — permissões RBAC/ABAC | 3 | `permissions.py` + 32 testes; ADR-0014 | 96/96 aprovados |
| 26/08/2026 | B4 — webhooks, outbox e inbox | 3 | `webhooks.py`, `outbox.py` + 27 testes; T-02 coberta | 123/123 aprovados |
| 26/08/2026 | B2 — AI Gateway com provedor simulado | 3 → 4 | `ai_gateway.py`, `ai_simulator.py` + 31 testes | — |
| 26/08/2026 | B1 — agentes + sanitizador de PII | 4 | `sanitizer.py`, `agents.py` + 31 testes | — |
| 26/08/2026 | Sincronização com o Drive | — | 4 módulos + painel; política de salvamento por bloco adotada | Pasta CAMPAIA |
| 27/08/2026 | Auditoria de código: confirmação do B3 e mapeamento de lacunas reais | 3/4 | `reconciliation.py` confirmado completo (26 testes) | `docs/evidence/GAP_ANALISE_BACKEND_CAMPAIA_20260827.md` |
| 27/08/2026 | Decisão do Diretor: painel corrigido + BFF/API priorizado | — | Diretor: "sim siga sua sugestão eu aprovo" | `docs/evidence/GAP_ANALISE_BACKEND_CAMPAIA_20260827.md` |
| 27/08/2026 | Camada BFF/API construída e testada (Starlette) | 1 → 3 | 19 arquivos novos; 42 testes próprios; 145 testes de domínio confirmados inalterados | `docs/evidence/EVIDENCIA_BFF_API_20260827.md` |
| 27/08/2026 | Fechamento da P-12: testes de `ai_gateway`, `ai_simulator`, `sanitizer`, `agents` | 4 | 4 arquivos de teste novos; 88 testes; 233 testes de domínio no total | `docs/evidence/EVIDENCIA_P12_20260827.md` |
| 28/08/2026 | Decisão do Diretor: conferir API contra contrato literal | — | Diretor: "faça assim segundo a sua recomendação B" | `docs/evidence/EVIDENCIA_P14_20260828.md` |
| 28/08/2026 | Conferência campo a campo `api/` vs. YAML literal (P-14) | 3 | 15 divergências confirmadas por leitura direta do código e do YAML decodificado | `docs/evidence/EVIDENCIA_P14_20260828.md` |
| 28/08/2026 | Decisão do Diretor: corrigir tudo | — | Diretor: "corrigir tudo" | `docs/evidence/EVIDENCIA_P14_20260828.md` |
| 28/08/2026 | Correção das 15 divergências + 2 encontradas na reverificação independente | 3 | 64 testes de API (era 42); 233 testes de domínio confirmados inalterados | `docs/evidence/EVIDENCIA_P14_20260828.md` |
| 28/08/2026 | Decisão do Diretor: corrigir a P-15 antes de avançar, depois seguir para persistência e blocos pendentes | — | Diretor: "fazer essa correção primeiro antes de avançar e não deixar nada para tras, e depois na sequencia as opções 1 e a 2 pode executar dessa forma" | `docs/evidence/EVIDENCIA_P15_20260828.md` |
| 28/08/2026 | Fechamento da P-15: correção da documentação do Connector Hub | 1 | Achado real identificado (tempo presente na frase de abertura) e corrigido; nenhuma alteração de código | `docs/evidence/EVIDENCIA_P15_20260828.md` |
| 28/08/2026 | Início da opção 1 do Diretor (persistência real) via agente delegado; reverificação independente do resultado | 2/3 | Reverificação direta revelou que a base restaurada era pré-P-14 | — |
| 28/08/2026 | Achado P-16: código da P-14 nunca havia sido salvo no Drive | — | Prova forense por metadados de data do Drive; comunicado ao Diretor de forma transparente e imediata | `docs/evidence/EVIDENCIA_REMEDIACAO_P14_20260828.md` |
| 28/08/2026 | Remediação da P-16: reenvio dos 11+3 arquivos genuinamente corrigidos ao Drive | 3 | Todos byte a byte verificados; contagem de domínio corrigida de 233 para 237 | `docs/evidence/EVIDENCIA_REMEDIACAO_P14_20260828.md` |
| 28/08/2026 | Persistência real (opção 1) — segunda tentativa, sobre a base local já corrigida | 2/3 | Novo `api/db.py` integrado; nenhum arquivo de rota alterado; 8 novos testes; verificação independente completa | `docs/evidence/EVIDENCIA_PERSISTENCIA_20260828.md` |
| 28/08/2026 | Upload da persistência ao Drive, imediatamente após a verificação | 3 | `main.py`, `state.py`, `repositories.py` substituídos + `db.py`/`test_persistence.py` novos; baseline 237+72=309 testes | `docs/evidence/EVIDENCIA_PERSISTENCIA_20260828.md` |
| 28/08/2026 | Instrução de processo do Diretor: sempre apresentar recomendação marcada entre as opções | Diretor: "vc é o eng senior sempre de as opções com a marcação de recomendo na melhor entre as opções" | — |
| 28-29/08/2026 | Recomendação de engenharia: priorizar B9 (AsyncAPI) entre B5/B7/B8/B9/B10; pesquisa dos artefatos de contrato existentes | — | Download e decodificação de `event-envelope.schema.json`, `campaign-brief.schema.json`, `campaign-plan.schema.json`, `ai-gateway.schema.json`, `connector-hub-e-eventos.md` | `contracts_ref/` (local) |
| 29/08/2026 | Construção do AsyncAPI 3.0 (`contracts/events.asyncapi.yaml`); descoberta e correção da contagem 22→24 (P-17) durante extração programática do catálogo | 1/3 | 24 canais/operações/mensagens; envelope reproduzido campo a campo; tentativas de validação via AsyncAPI CLI e meta-schema oficial bloqueadas por política de rede (P-18) | `docs/evidence/EVIDENCIA_B9_ASYNCAPI_20260829.md` |
| 29/08/2026 | Verificação independente do B9 via script próprio; upload ao Drive; reconciliação de uma discrepância real de bytes (3 bytes) entre Drive e disco, investigada com `diff` antes de fechar | 3 | `events.asyncapi.yaml` (25480 bytes) e `validate_events_asyncapi.py` (7287 bytes) confirmados byte a byte; script reexecutado do zero após correção, `ALL CHECKS PASSED` | `docs/evidence/EVIDENCIA_B9_ASYNCAPI_20260829.md` |
| 03/09/2026 | Decisão do Diretor: aprovar B10 como próximo bloco | — | Diretor: "b10" | — |
| 03/09/2026 | Pesquisa da taxonomia real de erros: leitura direta de `campaia_core/errors.py`, `api/errors.py`, `campaia_core/connectors.py`, `campaia_core/permissions.py` no Drive | 3 | Confirmação de 18 códigos ativos, 8 erros de domínio, 3 `DenialCode`; descoberta do gap de 3 códigos de `ConnectorErrorCode` (P-19), com `VALIDATION_REJECTED` confirmado via `grep` como levantado de fato em `saga.py:191` | `docs/evidence/EVIDENCIA_B10_CATALOGO_ERROS_20260903.md` |
| 03/09/2026 | Construção e verificação independente de `docs/09_CATALOGO_ERROS_USUARIO.md` | 3 | 18 mensagens de erro em português; script Python confirmou 18/18 de cobertura exata e o gap de 3 códigos, sem diferença em relação ao documento | `docs/evidence/EVIDENCIA_B10_CATALOGO_ERROS_20260903.md` |
| 03/09/2026 | Upload ao Drive; detecção e correção de um erro real de transcrição (3 bytes a mais na 1ª tentativa, causado por um erro de digitação meu no parâmetro de upload, não no arquivo local) via verificação byte a byte | 3 | 1ª tentativa (`fileId 1w1O...`) trashada; upload final via `base64Content` bateu exatamente 12603=12603 | `docs/evidence/EVIDENCIA_B10_CATALOGO_ERROS_20260903.md` |
| 04/09/2026 | Decisão do Diretor: corrigir a P-19, sem deixar nenhuma inconsistência entre código e documentação | — | Diretor: "pode corrigir não vamos deixar nenhum erro para trás" | `docs/evidence/EVIDENCIA_P19_FIX_20260904.md` |
| 04/09/2026 | Restauração local dos 48 arquivos do backend a partir do Drive via agente delegado; reverificação independente do relatório do agente | 2/3 | Agente inicialmente interrompido por rate limit relatou de forma confusa; cobrado por relatório preciso, revelou que 10 de 48 arquivos ainda estavam byte-incorretos apesar de "prontos" reportado antes; corrigidos via decodificação programática | `docs/evidence/EVIDENCIA_P19_FIX_20260904.md` |
| 04/09/2026 | Confirmação independente da linha de base (execução direta, não apenas relato do agente) | — | 237 (domínio) + 72 (API/persistência) = 309 testes, 100% aprovados, antes de qualquer alteração | `docs/evidence/EVIDENCIA_P19_FIX_20260904.md` |
| 04/09/2026 | Correção da P-19 em `api/errors.py` (3 entradas em `STATUS_BY_CODE`) + 8 novos testes em `tests_api/test_errors_p19.py` provando a correção via `from_domain_error()` | 3 | 237+80=317 testes, 100% aprovados, zero regressão; anomalia de 1 byte em `routes_approvals.py` investigada e documentada como externa, não corrigida (fora do escopo) | `docs/evidence/EVIDENCIA_P19_FIX_20260904.md` |
| 04/09/2026 | Atualização do catálogo B10 (`docs/09_CATALOGO_ERROS_USUARIO.md`) para v1.1.0, refletindo a correção da P-19 em vez de descrevê-la como pendente | 3 | 12603→14668 bytes | `docs/evidence/EVIDENCIA_P19_FIX_20260904.md` |
| 04/09/2026 | Upload dos 3 artefatos ao Drive (`api/errors.py`, `tests_api/test_errors_p19.py`, catálogo v1.1.0), todos byte-verificados na primeira tentativa | 3 | 4509=4509, 3718=3718, 14668=14668 | `docs/evidence/EVIDENCIA_P19_FIX_20260904.md` |
| 04/09/2026 | Decisão do Diretor: construir B5, seguindo a recomendação apresentada ao final do fechamento da P-19 | — | Diretor: "siga sua recomendação" | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` |
| 04/09/2026 | Pesquisa de escopo antes de escrever código: descoberta de uma árvore de documentação de produto até então não consultada (`campaia/docs/product/`), revelando a distinção F8.1 (sugerir) vs. F8.2 (executar automaticamente, fora de escopo do MVP) já registrada na Fase 0 | — | `FUNCTIONAL_REQUIREMENTS.md`, `CAMPAIA_PRODUCT_CHARTER.md`, `OUT_OF_SCOPE.md` | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` |
| 04/09/2026 | Pergunta explícita ao Diretor sobre o escopo do B5, em vez de decisão unilateral, dado que um motor autoexecutável contrariaria uma decisão de escopo já registrada | — | Diretor: "Motor que só sugere/calcula (Recomendado)" | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` |
| 04/09/2026 | Construção de `pacing.py` e `optimizer.py`, após confirmar (leitura completa de `autonomy.py`, `policy.py`, `states.py`, `budget.py`) que não havia sobreposição com código existente | 3 | 2 módulos novos (7854 + 6927 bytes); 26 novos testes (14 pacing + 12 optimizer), incluindo prova real via `evaluate_autonomy()` de que nenhuma sugestão se autoexecuta | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` |
| 04/09/2026 | Re-execução completa da suíte (não apenas confiar no relato da sessão anterior) | — | 263 (domínio) + 80 (API/persistência) = 343 testes, 100% aprovados, zero regressão | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` |
| 04/09/2026 | Upload dos 4 artefatos do B5 ao Drive, todos byte-verificados | 3 | `pacing.py` 7854=7854, `optimizer.py` 6927=6927, `test_pacing.py` 5561=5561, `test_optimizer.py` 7888=7888 | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` |
| 04/09/2026 | Achado de processo, comunicado com transparência: 1ª tentativa de upload do documento de evidência do B5 divergiu em 1 byte (13344 local vs. 13343 no Drive); investigação por download/diff programático revelou uma corrupção real de conteúdo — um "à" (acento grave, crase) virou "a" — causada por um erro de transcrição meu ao reproduzir a string base64 na chamada da ferramenta, não um comportamento do Drive | — | Readback e diff byte a byte via Python confirmaram a causa exata antes de qualquer correção | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` |
| 04/09/2026 | Remediação: arquivo local corrigido, nova codificação, upload da versão corrigida verificado por download/diff completo (não apenas contagem de bytes) batendo exatamente; versão com erro trashada no Drive | 3 | Versão final 13349=13349, conteúdo idêntico byte a byte ao original local confirmado por diff | `docs/evidence/EVIDENCIA_B5_OTIMIZACAO_PACING_20260904.md` |
| 04/09/2026 | Decisão do Diretor: construir B7 (DDL e migrations do Postgres), aceitando a ressalva de verificação limitada dada ao final do fechamento do B5 | — | Diretor: "sim concordo" | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 04/09/2026 | Pesquisa de escopo delegada antes de escrever qualquer DDL: leitura completa de `campaia_core/`, `api/db.py`, `api/repositories.py`; busca por artefatos Postgres já existentes (nenhum encontrado); leitura de `campaia/docs/product/` e `TENANT_ISOLATION.md` | — | Achado: `docs/06_MODELO_DADOS.md` nunca foi de fato escrito; maioria dos módulos de domínio nunca foi persistida; saídas do B5 são cálculos puros, não geram tabela; D-03 segue condicionando o formato de multi-tenancy | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 04/09/2026 | Duas perguntas explícitas ao Diretor sobre o escopo do B7 (DDL completo vs. só do persistido; pausar por D-03 vs. construir extensível), em vez de decisão unilateral, dada a ambiguidade real de escopo encontrada na pesquisa | — | Diretor: "DDL apenas do que já é persistido (Recomendado)" + "Construir para o caso simples, deixando extensível (Recomendado)" | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 04/09/2026 | Construção de `db/001_initial_schema.sql` (7 tabelas, RLS, CHECK, FK, chave composta) e `db/verify_ddl_postgres.sh` | 3 | 2 arquivos novos; nenhuma alteração em `campaia_core/` ou `api/` | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 04/09/2026 | Verificação de disponibilidade de Postgres real nesta sandbox por investigação direta (`which pg_ctlcluster`, `pg_lsclusters`), em vez de aceitar como definitiva a própria ressalva dada ao Diretor antes de começar o bloco | — | Descoberta: Postgres 16 genuinamente instalado (`postgresql-16`, cluster `main`, porta 5432); iniciado via `service postgresql start`; achado comunicado ao Diretor com a mesma transparência de qualquer outro, como correção de uma ressalva própria, não como problema | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 04/09/2026 | Execução real do script de verificação contra o Postgres real: schema aplica sem erro, RLS isola tenant-a/tenant-b e nega acesso sem contexto (falha fechado), CHECK e FK rejeitam valores inválidos, chave composta de idempotency rejeita duplicata | 3 | `ALL CHECKS PASSED`; bug próprio encontrado e corrigido antes de aceitar o resultado (`psql -tAc` com múltiplas instruções retornava `"SET\n1"` em vez de `"1"`, corrigido com `| tail -n1`); script reexecutado 2x seguidas para reprodutibilidade, zero rastro deixado no servidor | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 04/09/2026 | Re-execução completa da suíte Python (B7 é puramente SQL/shell, sem alteração de código Python) | — | 263 (domínio) + 80 (API/persistência) = 343 testes, 100% aprovados, zero regressão | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 04/09/2026 | Correção de uma ressalva desatualizada no próprio comentário de cabeçalho de `001_initial_schema.sql` ("não há Postgres real disponível aqui", escrita antes da descoberta) antes do upload; reverificação completa (2 execuções adicionais do script) após a edição puramente textual, para não aceitar "é só um comentário" como dispensa de reverificação | 3 | Tamanho do arquivo mudou de 15402 para 15577 bytes; `ALL CHECKS PASSED` confirmado novamente | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 04/09/2026 | Criação da pasta `backend/db/` no Drive (não existia; irmã de `campaia_core/`, `api/`, `tests/`, `tests_api/`) e upload dos 2 artefatos de código + do documento de evidência, todos via `textContent` (não `base64Content`), cada um verificado por download completo + diff byte a byte (não apenas tamanho) | 3 | `001_initial_schema.sql` 15577=15577, `verify_ddl_postgres.sh` 5961=5961, evidência final 14494=14494 — todos com diff de conteúdo confirmando match exato | `docs/evidence/EVIDENCIA_B7_DDL_POSTGRES_20260904.md` |
| 05/09/2026 | Decisão do Diretor: construir C1 (repositório Git + CI) e, em sequência, resolver as decisões então listadas como bloqueio | Diretor: "faça a opção 1 e depois na sequencia a opção 2 para não ficar nada pendente para trás" | — |
| 05/09/2026 | Reconstrução do repositório completo a partir do Drive: `backend/` reconciliado arquivo a arquivo (achado real: `api/routes_approvals.py` tinha indentação incorreta em `create_approval` — 3 espaços em vez de 4 no `state.audit.append(...)`, mascarada porque Python não exige indentação dentro de parênteses; corrigida a partir da cópia do Drive), `contracts/` (8 arquivos) e `docs/` + `docs/evidence/` (38 arquivos) baixados e verificados byte a byte | 2 → 3 | 343/343 testes, zero regressão, após a correção; achado anterior (P-19, "anomalia de 1 byte... root-caused como externa") corrigido como o defeito real que era, não mais atribuído ao Drive | Commit inicial do repositório `campaia_repo/` |
| 05/09/2026 | Descoberta, durante a leitura completa de `docs/evidence/` para a reconstrução: 6 documentos de decisão do Diretor datados de 27/08/2026 (D-03, D-05, D-06, ADR-0010, marco do Google Ads, atualização do CNPJ) já resolviam a maior parte do que este painel listava como "Bloqueios" desde então, sem que o painel jamais tivesse sido corrigido para refletir isso (P-21) | — | Achado comunicado ao Diretor com a mesma transparência de qualquer outro | `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md` e demais |
| 05/09/2026 | Construção de `.gitignore`, `backend/requirements.txt`, `contracts/requirements.txt` e do workflow `.github/workflows/backend-tests.yml` (2 suítes de teste + validador AsyncAPI) | 2 | — | — |
| 05/09/2026 | Verificação do workflow de CI antes de aceitá-lo como correto: achado real de portabilidade em `contracts/validate_events_asyncapi.py` (caminhos absolutos hardcoded para `/home/claude/...`, que não existiriam num checkout limpo do GitHub Actions nem no PC do Diretor); corrigido para caminhos relativos ao próprio arquivo (`Path(__file__).resolve().parent`); revalidado (24/24 eventos, exit code 0) | 2 → 3 | Simulação do CI em venv limpa confirmou que o único obstáculo restante era o bloqueio de rede a `pypi.org` deste sandbox de teste (não um problema do repositório); versões fixadas de `pydantic==2.13.3` e `starlette==1.0.0` confirmadas como reais e publicadas via busca na web antes de aceitar o `requirements.txt` como correto | — |
| 05/09/2026 | `git init`, commit inicial (106 arquivos, mensagem detalhando os 2 defeitos corrigidos), `git bundle create --all` e `zip` do working tree; ambos verificados de fato (`git bundle verify`, clone de teste do bundle rodando as 343 verificações de teste de novo, `unzip -t` sem erros) antes de aceitar como corretos | 3 | `git fsck --full` sem erros; clone a partir do bundle reproduz exatamente os 106 arquivos rastreados e passa 343/343 | Commit `21faaab` |
| 05/09/2026 | Entrega ao PC do Diretor via ponte de dispositivo: `campaia_repo.zip` e `campaia.bundle` enviados e gravados em `Desktop/CAMPAIA/` (pasta nova — não confundir com `Desktop/F M TECNOLOGIA`, que é de outro projeto do Diretor, o app de comida) | 3 | Tamanhos conferidos após a gravação: 327399 e 312722 bytes, idênticos aos originais | `Desktop/CAMPAIA/campaia_repo.zip`, `Desktop/CAMPAIA/campaia.bundle` |
| 05/09/2026 | Reconciliação do painel (opção 2): D-03, D-05, D-06, D-08 e D-09 marcadas como resolvidas (com data e citação literal do Diretor de 27/08), P-11 e P-21 adicionadas às pendências técnicas, B8 marcada como desbloqueada | 1 | v16 substitui v15 no Drive | `01_PAINEL_EXECUCAO_v16_VIGENTE.md` |
| 05/09/2026 | Diretor cria o repositório GitHub e autentica `gh`/`git` na própria máquina (login por navegador, device code flow) — nenhuma credencial passou por mim; push do repositório completo confirmado com sucesso | — | `git push` retornou "Everything up-to-date" / branch main rastreando origin/main | Repositório `https://github.com/faabio3131/CampaIA` |
| 05/09/2026 | Diretor reporta erro real no CI ("erro de CI dependência e revalidação"); diagnóstico feito via `gh run view --log-failed` direto no terminal do Diretor (já autenticado), não por navegação visual no site | — | Log real do Actions aponta `ModuleNotFoundError: No module named 'httpx'` — dependência de `starlette.testclient` ausente de `backend/requirements.txt`, mascarada localmente porque a sandbox já tinha `httpx` instalado por outro motivo | `docs/evidence/EVIDENCIA_C1_CI_HTTPX_FIX_20260905.md` |
| 05/09/2026 | Confirmação da versão real do `httpx` no PyPI antes de fixar (0.28.1, mesma disciplina já aplicada a `pydantic`/`starlette`); correção de `backend/requirements.txt`; 343/343 testes re-executados localmente, zero regressão; commit e push direto do terminal do Diretor | 3 | `git push` bem-sucedido (`ab4173a..3f2c18d main -> main`) | `docs/evidence/EVIDENCIA_C1_CI_HTTPX_FIX_20260905.md` |
| 05/09/2026 | Confirmação de que a execução seguinte do CI no GitHub passou de fato, não apenas presumida | 3 | `gh run view --json status,conclusion` → `{"conclusion": "success", "status": "completed"}` | `docs/evidence/EVIDENCIA_C1_CI_HTTPX_FIX_20260905.md` |
| 05/09/2026 | Upload da correção ao Drive (trash do `requirements.txt` antigo + novo), verificado byte a byte (download + diff + SHA256) | 3 | SHA256 idêntico entre local e Drive | `backend/requirements.txt` (Drive) |
| 05/09/2026 | Diretor pede para seguir com B8; pesquisa real de mercado antes de fechar a especificação, a pedido explícito do Diretor ("Você como engenheiro Sênior?... Como que são os atuais concorrentes?") | — | Diretor: "importante agora no momento é a funcionalidade. Depois nós vamos dar aquele talento num visual premium final. Depois que tiver tudo pronto testado." | `docs/product/13_ESPECIFICACAO_TELAS_APP.md` |
| 05/09/2026 | Pesquisa de concorrentes reais via WebSearch/WebFetch (Madgicx, Revealbot, Smartly.io, AdCreative.ai, Meta Advantage+) e incorporação de 2 melhorias concretas na especificação (geração multi-formato de criativo já na etapa de criação; breakdown de métricas por variação individual) mais 1 insight de posicionamento (aprovação humana obrigatória como diferencial) | — | Fontes citadas no documento (Pipeboard, Get Ryze, Zeely, 1ClickReport) | `docs/product/13_ESPECIFICACAO_TELAS_APP.md` §0 |
| 05/09/2026 | Diretor introduz mudança de escopo: oferecer Modo Manual E Modo Automático (com limite definido pelo cliente) como diferencial competitivo | — | Diretor: "Sobre nós deixarmos tudo com, autorização humana... Mas também vamos ter a opção do cliente querer escolher deixar no automático... assim nos coloca à frente, está concorrente." | `docs/product/DECISOES_DIRETOR.md` item 5 |
| 05/09/2026 | Pergunta explícita ao Diretor antes de decidir unilateralmente, dado que isso reabre uma restrição já registrada em `OUT_OF_SCOPE.md` (Nível 2/3 de autonomia fora do MVP) | — | Diretor confirma trazer o Nível 2 para o MVP, com a salvaguarda de senha de administrador: "vamos colocar isso agora em funcionamento porém pensando na segurança... precisará ser validada por senha de adm... provaremos que ele inseriu a senha" | `docs/product/DECISOES_DIRETOR.md` item 5 |
| 05/09/2026 | Propagação da decisão de forma consistente por todos os documentos afetados, corrigindo contradições que uma edição isolada teria deixado (`CAMPAIA_PRODUCT_CHARTER.md` §9, `OUT_OF_SCOPE.md`, `13_ESPECIFICACAO_TELAS_APP.md` §1/§8/§9/§11) | 1/3 | Busca sistemática por "F8.2", "execução automática", "Fora de escopo" no documento B8 para não deixar nenhuma menção contraditória | `docs/product/CAMPAIA_PRODUCT_CHARTER.md`, `docs/product/OUT_OF_SCOPE.md`, `docs/product/13_ESPECIFICACAO_TELAS_APP.md` |
| 05/09/2026 | Pergunta de fechamento sobre a única ambiguidade restante: campanha nova também seria coberta pelo Modo Automático (senha + limite), ou continuaria sempre exigindo aprovação manual distinta? | — | Diretor escolhe "Campanha nova sempre manual (Recomendado)" — a senha + limite autorizam apenas otimização de campanhas já aprovadas, nunca a criação/publicação inicial | `docs/product/DECISOES_DIRETOR.md` item 5, seção "Esclarecimento adicional" |
| 05/09/2026 | Descoberta e correção de uma lacuna de processo: os 5 documentos de produto (`CAMPAIA_PRODUCT_CHARTER.md`, `FUNCTIONAL_REQUIREMENTS.md`, `OUT_OF_SCOPE.md`, `NON_FUNCTIONAL_REQUIREMENTS.md`, `DECISOES_DIRETOR.md`) existiam apenas no sandbox, nunca haviam sido persistidos no Google Drive | — | Achado comunicado com transparência; documentos criados na pasta `docs/product/` do Drive (fileId `1ydfjOmemNxYjEwLa_kQdaT1yLUfLcLnf`), com verificação byte a byte (SHA256) e correção de uma falha de corrupção de acentuação Unicode via `base64Content` (resolvida trocando para `textContent`) | Pasta `docs/product/` no Drive |
| 05/09/2026 | Upload das versões finais de `13_ESPECIFICACAO_TELAS_APP.md` e `DECISOES_DIRETOR.md` ao Drive (trash-old+create-new), verificados byte a byte (download completo + diff + SHA256, não apenas tamanho) | 3 | SHA256 idêntico entre local e Drive em ambos os arquivos | Pasta `docs/product/` no Drive |
| 05/09/2026 | Commit dos artefatos de produto no repositório Git local (`campaia_repo/`) | 3 | `docs: especificações de telas B8 e decisões do diretor` — 6 arquivos, 1707 inserções | Commit `59b8c0b` |
| 05/09/2026 | Inspeção das rotas HTTP reais (`backend/api/routes_*.py`, `main.py`) contra o contrato literal (`contracts/bff-openapi.yaml`), a pedido do Diretor, sem alterar nenhum arquivo nesta etapa | — | Nenhuma rota duplicada; cobertura 1:1 entre implementação e contrato, exceto `POST /approvals` (desvio já documentado em comentário no próprio código) | — |
| 05/09/2026 | Achado real (não documentado como "achado" no código): `BudgetPatchRequest` (`api/models.py`) declarava o campo como `new_daily_cap`, mas o contrato exige `daily_cap` — com `extra="forbid"`, um cliente seguindo o contrato literal seria rejeitado | — | Confirmado por leitura direta do YAML (`required: [daily_cap, approval_id]`) e do model; nenhum alias existente reconciliava os dois nomes | `contracts/bff-openapi.yaml`, `backend/api/models.py` |
| 05/09/2026 | Correção autorizada pelo Diretor: alias `daily_cap`→`new_daily_cap` com `populate_by_name=True`, documentado como achado 18 seguindo o padrão de comentários já usado no arquivo | 3 | 80/80 testes de API confirmados sem regressão (`unittest discover -s tests_api`); verificação manual adicional confirmando que ambos os nomes (`daily_cap` e `new_daily_cap`) validam e que `extra="forbid"` continua rejeitando campos desconhecidos | Commit `8eee393` — "fix(api): suporte a daily_cap no BudgetPatchRequest via alias" |
| 05/09/2026 | Criação de `.claude/commands/system-design.md` e `.claude/commands/task-manager.md` (skills customizadas de arquitetura e de execução anti-alucinação), com conteúdo exato fornecido pelo Diretor | — | Ambos os arquivos criados sem alteração de conteúdo em relação ao especificado | Commit `50fcdf0` — "chore(claude): adiciona skills customizadas de system design e task manager" |
| 05/09/2026 | Commits separados confirmados: `docs/product/` (`59b8c0b`) e `.claude/` (`50fcdf0`); árvore de trabalho conferida limpa via `git status` | 3 | `git status` → "nothing to commit, working tree clean" | Commits `59b8c0b`, `50fcdf0` |
| 19/09/2026 | Auditoria completa e somente leitura dos dois repositórios (`faabio3131/CampaIA` e `faabio3131/f-m-tecnologia-campaia`), comparando ancestralidade, commits, árvore de arquivos e diff byte a byte de todos os caminhos compartilhados | — | Ancestral comum confirmado (`21faaab`, `ab4173a`, SHAs idênticos); 106/107 arquivos compartilhados byte-idênticos; único arquivo divergente: `backend/api/models.py` (alias `daily_cap`) | Auditoria "CAMPAIA — CURRENT, Reconciliação e Definição do Ponto Zero Web", mesma sessão |
| 19/09/2026 | Decisão do Diretor: repositório canônico é `faabio3131/f-m-tecnologia-campaia`; `faabio3131/CampaIA` vira fonte histórica somente leitura | Diretor, prompt "RECONCILIAÇÃO CONTROLADA DO REPOSITÓRIO CANÔNICO" | — | ADR-0015 |
| 19/09/2026 | Pré-flight: HEADs de ambos os repositórios reconfirmados idênticos aos esperados antes de qualquer alteração (`f-m-tecnologia-campaia` @ `1fe8051`, `CampaIA` @ `fba7fcc`); worktrees limpas; ausência do bloco fiscal e presença do fix `daily_cap`/governança/`docs/product/` no canônico reconfirmadas | — | `git rev-parse HEAD` / `origin/main` em ambos os repositórios | — |
| 19/09/2026 | Criação da branch `reconciliation/campaia-ponto-zero-web` a partir da `main` canônica atualizada | — | — | — |
| 19/09/2026 | SHAs completos resolvidos e diffs completos inspecionados dos 3 commits do bloco fiscal antes de importar (`bb2b84d`, `55f5b95`, `bdebbc3`) — cada um altera exatamente 1 arquivo novo, sem escopo estranho; merge `fba7fcc` não introduz nada além disso | — | `git show --stat` de cada commit; `git diff bdebbc3 fba7fcc --stat` vazio | — |
| 19/09/2026 | Leitura integral de `fiscal_handoff.py` e confirmação de que nenhuma referência a ele existe em outro lugar do backend, antes de importar — confirma a natureza fail-closed e o desacoplamento de campanha/orçamento já declarados na PR de origem | — | `grep -rn "fiscal_handoff" backend/` sem resultados fora dos 2 arquivos próprios | — |
| 19/09/2026 | Importação do bloco fiscal por cherry-pick (não cópia manual), preservando autoria e histórico original | 3 | Cherry-pick limpo, sem conflitos; commits `e7f648d`, `05aab64`, `d940949` no repositório canônico, autoria `faabio3131` preservada | — |
| 19/09/2026 | Confirmação do fix `daily_cap` já presente e coerente no canônico (modelo, contrato, API); busca por lacuna de cobertura de teste antes de decidir se adicionava algo | — | Achado real: nenhum teste existente enviava o nome de campo literal do contrato (`daily_cap`) ao endpoint de patch de orçamento — toda a cobertura usava `new_daily_cap` | `backend/api/models.py`, `backend/tests_api/*.py` |
| 19/09/2026 | Adição do teste de regressão `test_budget_patch_accepts_contract_daily_cap_alias`, cobrindo exatamente a lacuna encontrada, via cliente HTTP real (não apenas unitário de modelo) | 3 | Teste executado isoladamente: OK | Commit `3a0f277` — "test(api): cover contract literal daily_cap alias on budget patch" |
| 19/09/2026 | Registro formal de quarentena arquitetural do app mobile — SDK Flutter/Dart confirmado ausente também neste ambiente (`which flutter dart`); SDK não instalado para forçar uma validação que esta reconciliação não pediu; registrado como NÃO VERIFICADO | — | `which flutter dart` → ambos ausentes | Commit `80b2f1e`; `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` |
| 19/09/2026 | Redação da ADR-0015, seguindo o padrão documental descoberto (arquivo próprio, como ADR-0013 — não reaproveitando o lote fechado de `docs/03_ADR_INICIAIS.md`); numeração verificada contra colisão antes de escrever | — | `ADR-0014` já reservada no painel v18 (linhas 55/210/295) para o tema de Autorização RBAC/ABAC, ainda não escrita; `ADR-0015` confirmada livre | Commit `577b51c`; correção de numeração no commit `4d99150` |
| 19/09/2026 | Redação desta versão do painel (v19), a partir de v18, confirmando que v19 é de fato a próxima versão antes de criá-la (nenhum `v19` pré-existente encontrado em nenhum lugar do repositório) | — | `grep -rl "v19"` vazio antes da criação deste arquivo | `01_PAINEL_EXECUCAO_v19_VIGENTE.md` |
