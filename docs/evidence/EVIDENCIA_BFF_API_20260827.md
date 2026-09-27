# CAMPAIA — Implementação da camada BFF/API (HTTP) sobre o domínio testado

**Data:** 27/08/2026
**Autorização:** Diretor Fábio Aluizio da Silva — *"sim siga sua sugestão eu aprovo"*, em resposta à recomendação de corrigir o painel e priorizar a camada BFF/API como próximo passo, no sandbox, sem depender de credencial ou infraestrutura externa.
**Local:** construído e testado em `/home/claude/campaia_verify/` (sandbox local desta sessão), depois copiado para o Google Drive em `backend/api/` e `backend/tests_api/`, como novos irmãos de `backend/campaia_core/` e `backend/tests/` (que **não foram alterados**).

## O que foi construído

Uma camada HTTP nova, cobrindo os 24 endpoints descritos em `contracts/bff-openapi.yaml` (`/me`, `/brand-profiles`, `/connections*`, `/briefs`, `/campaigns/*`, `/approvals/*`, `/autonomy`, `/kill-switch`, `/campaigns/{id}/insights`, `/audit-events`), implementada como adaptador fino sobre os módulos já testados de `campaia_core` (states, budget, policy, saga, permissions, autonomy, infra, agents, ai_simulator). Nenhuma regra de negócio foi duplicada ou reimplementada nesta camada — ela chama o domínio existente.

15 arquivos em `api/` + 4 em `tests_api/` (19 no total). Todos copiados ao Drive em `backend/api/` (`1uYWRfiT5xiRegazwIoRMBG_mPkodfk0n`) e `backend/tests_api/` (`1TqhOFH7Aoza98lcm_8rMZbOQhdJMwp0a`), com tamanho em bytes conferido um a um contra o arquivo local.

## Testes — executados e confirmados por mim, não apenas relatados

```
cd /home/claude/campaia_verify && python3 -m unittest discover -s tests -t .       → 145 testes, 145 aprovados (domínio, inalterado)
cd /home/claude/campaia_verify && python3 -m unittest discover -s tests_api -t .   → 42 testes, 42 aprovados (camada nova)
```

Os testes novos cobrem especificamente os invariantes do contrato: `tenant_id` do corpo da requisição é ignorado (só vem do token); `Idempotency-Key` ausente barra mutação externa; repetir a mesma chave não duplica campanha nem publicação; `X-Step-Up-Token` ausente barra operação sensível (403); publicar sem `policy_decision_id`/`approval_id` é barrado; acesso a campanha de outro tenant devolve 404 (não vaza dado); e um caminho feliz completo (brief → validação → publicação via simulador → campanha ACTIVE com `external_resource_id`).

## Desvio relevante — não é FastAPI, é Starlette

`pip install fastapi` falhou: `pypi.org` está fora da lista de permissão de rede deste sandbox (confirmado por erro 403 direto). Como Starlette (o framework ASGI que o FastAPI usa por baixo), Uvicorn, Pydantic e httpx já estavam instalados, a camada foi construída diretamente sobre Starlette, com roteamento e dependências (auth, step-up, idempotência) escritos à mão no mesmo formato que o FastAPI teria gerado. É uma aplicação real, rodando e testada — não uma simulação — só que tecnicamente não é FastAPI. Se for importante ter FastAPI especificamente (por exemplo, para gerar a documentação OpenAPI automática), isso exigirá acesso de rede a um índice de pacotes Python que este sandbox não tem hoje.

## O que é real e o que é simulado, explicitamente

**Chama o domínio real:** `states.Campaign.transition_to`/`apply_kill_switch`, `budget.BudgetEngine`, `policy.PolicyEngine.evaluate`, `saga.PublicationSaga.run` (com `simulator.ProviderSimulator`), `permissions.authorize`/`can_approve`/`dual_approval_complete`, `autonomy.AutonomySettings`, `infra.IdempotencyStore`/`CapabilityRegistry`, `agents.AgentRunner` + `ai_simulator.SimulatedAIProvider`.

**Simulado, e identificado como tal no próprio código:** URL de autorização OAuth (domínio `*.invalid`, nenhuma chamada de rede real); tokens de portador e cabeçalho de step-up (dicionário em memória com strings de teste, formato claramente não-JWT, nunca persistido); todo efeito em plataforma de anúncios passa por `ProviderSimulator` (nunca uma API real do Google/Meta/WhatsApp).

**Lacuna honesta, não maquiada:** `GET /campaigns/{id}/insights` devolve `points: []` — não existe camada de analytics no domínio, então a API não inventa métricas.

## Decisões de engenharia tomadas onde o contrato era ambíguo

1. Não existe `contracts/bff-openapi.yaml` como arquivo baixado no ambiente onde a implementação rodou — a implementação seguiu a paráfrase do contrato transmitida nesta tarefa (que eu havia lido diretamente do Drive antes de delegar). Recomendo, numa próxima sessão, comparar a implementação contra o YAML original campo a campo antes de considerar o contrato "atendido" formalmente.
2. Foi adicionado `POST /approvals` (não listado explicitamente no contrato) — necessário porque publicar/alterar orçamento exigem uma aprovação "já registrada", mas nenhum endpoint do contrato cria essa aprovação.
3. `validate` compara o valor pedido contra `daily_cap` (não `total_amount`), consistente com `BudgetEngine.available_today`.
4. `publish` avança a campanha por VALIDATED→AWAITING_APPROVAL→APPROVED usando a aprovação já decidida, já que o contrato não especifica um endpoint separado de "submeter para aprovação".
5. Um bug real foi encontrado e corrigido pelos próprios testes do invariante: idempotência em `/publish` agora é checada antes de qualquer mutação de estado, para que repetir a chave devolva a campanha já ativa em vez de esbarrar na guarda "precisa estar APPROVED".

## O que isso muda no quadro de lacunas

Do item 3 da síntese em `GAP_ANALISE_BACKEND_CAMPAIA_20260827.md` ("Camada HTTP / BFF — zero código"): deixa de ser verdade. Existe agora uma implementação real, testada, rodando sobre o domínio verificado. Continua valendo que não há persistência real, adaptadores reais de provedor, app mobile, cofre de segredos real, fila durável real nem camada de analytics — nenhum desses itens foi tocado por este trabalho.
