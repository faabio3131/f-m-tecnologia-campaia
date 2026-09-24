# Evidência — adapter real do Gemini (item derivado de ADR-0021)

**Data:** 24/09/2026 · **HEAD de partida:** `main` (após PR #22, ADR-0022).

## O que foi construído

`campaia_core/gemini_provider.py` — implementa `AIProvider` (`ai_gateway.py`), substituindo
`SimulatedAIProvider` quando `GEMINI_API_KEY` está configurada no ambiente. Mesmo padrão de
`asaas_gateway.py` (`AsaasGateway`): config lida do ambiente (`GeminiConfig.from_env()`),
nenhuma credencial fixa em código, `transport` injetável para teste com
`httpx.MockTransport`, nunca rede real em teste.

**Endpoint:** `POST https://generativelanguage.googleapis.com/v1beta/interactions`,
autenticação via header `x-goog-api-key`. Confirmado contra a documentação oficial
(ai.google.dev, pesquisa de 24/09/2026): a Interactions API é a interface recomendada para
projetos novos desde junho/2026 — a antiga `generateContent` continua funcionando mas é
tratada como legado, por isso não foi usada aqui. `store: false` em toda requisição — cada
chamada do CampaIA é uma requisição isolada (um agente por vez, sem turno de conversa), sem
motivo para o Google reter histórico do lado dele.

**Modelo:** `gemini-3.8-flash` (padrão, decidido em ADR-0021), configurável via
`GEMINI_MODEL`.

## O que NÃO foi confirmado por chamada real (limitação registrada, não escondida)

O parâmetro exato de saída estruturada nativa da Interactions API (`response_format`/
`json_schema`) teve divergência entre fontes secundárias sobre o nome exato do campo — a
documentação oficial não pôde ser lida diretamente (`WebFetch` bloqueado pelo proxy de rede
deste ambiente para `ai.google.dev`, mesma limitação que os subagentes de pesquisa desta
sessão já haviam encontrado antes). Diante disso, **o adapter não aposta nesse parâmetro**:
em vez de confiar num campo não confirmado, instrui o modelo por prompt a responder só com
JSON contendo exatamente os campos exigidos, e deixa a validação de schema que **já existe e
é obrigatória** em `AIGateway.execute()` (`OutputSchema.validate()`) rejeitar qualquer saída
fora do contrato — exatamente o mesmo comportamento que já existiria com qualquer outro
provedor mal-comportado. Isso significa que o adapter é funcionalmente correto mesmo sem o
parâmetro nativo (mais tokens gastos em instrução de prompt, não uma lacuna de segurança).

Adicionar o parâmetro nativo de saída estruturada fica registrado como melhoria futura, a
fazer só depois de confirmar o campo certo contra uma chamada real com uma API key de
verdade — mesmo padrão já usado para o Asaas (construído primeiro contra a documentação,
"verificado contra o Sandbox real" aconteceu como um passo posterior e separado, ver
`docs/evidence/VERIFICACAO_REAL_ASAAS_SANDBOX_20260924.md`). Nenhuma API key real do Gemini
existe nesta sessão para fazer essa verificação agora.

## Desenho: por que `schemas` é injetado, não importado de `agents.py`

`AIProvider.generate(request)` só recebe `request.output_schema_id` (uma string), não o
`OutputSchema` inteiro — quem tem o catálogo completo de contratos de saída é
`campaia_core/agents.py` (`AGENTS`). Um adapter de infraestrutura genérico não deveria
importar o catálogo específico de agentes do produto (inverteria a direção de dependência
correta: agentes dependem do gateway, não o contrário). Por isso `GeminiProvider.schemas` é
um campo injetado — `api/state.py::_default_ai_provider()` monta esse dicionário a partir do
mesmo `AGENTS` que já alimenta `AIGateway.schemas`, e passa para o `GeminiProvider` na
construção. Um `output_schema_id` desconhecido nunca chega a fazer uma chamada de rede —
falha fechado antes, com `ProviderError` claro.

## Custo real vira `cost_units`

`ProviderResponse.cost_units` aqui é o custo real em USD da chamada (tokens de entrada ×
preço + tokens de saída × preço, valores de ADR-0021), não uma unidade abstrata — assim o
teto por tenant (`CostLedger`, `AIGateway`) significa dinheiro de verdade, não um número sem
relação com gasto real. Resposta sem `usage` utilizável falha fechado (nunca assume custo
zero, que esconderia gasto real do teto do tenant).

## Wiring em `api/state.py`

`_default_ai_provider()`: `GEMINI_API_KEY` ausente (padrão, e todo teste pré-existente) →
`SimulatedAIProvider` em memória, comportamento idêntico ao de antes desta mudança. Presente
→ `GeminiProvider` real, com o dicionário de schemas de todos os agentes já montado. Mesmo
padrão de `_default_billing_gateway` (Asaas).

## Testes

- `tests/test_gemini_provider.py` (13 testes): forma da requisição (`model`, `input`,
  `store: false`, header `x-goog-api-key`), parsing de `steps`/`model_output`/`usage`,
  cálculo de custo real a partir de tokens, rejeição de saída não-JSON (nunca "consertada"),
  `ModerationBlocked` em `status: blocked`, `ProviderTimeout`/`ProviderError` em
  timeout/429/5xx, `schema` desconhecido recusado antes de qualquer chamada de rede, config
  ausente falha fechado na construção. Tudo contra `httpx.MockTransport` — nunca rede real
  (nenhuma credencial real existe nesta sessão).
- `tests_api/test_ai_provider_wiring.py` (2 testes): `AppState()` sem `GEMINI_API_KEY` usa o
  simulador (comportamento padrão preservado); com a variável configurada, usa o
  `GeminiProvider` real com o catálogo completo de schemas já carregado.

## Testes executados neste HEAD

- `python3 -m unittest discover -s tests` → **356 testes, OK** (343 anteriores + 13 novos).
- `python3 -m unittest discover -s tests_api -t .` → **107 testes, OK** (105 anteriores + 2
  novos).

Nenhuma regressão nos testes pré-existentes.

## Verificação real (24/09/2026, sessão irmã `session_01BLt2GfDQr8w6czS56PpTqD`)

Diferente do que a seção anterior registrava, este adapter **já foi chamado contra a API real
do Gemini** — não a partir desta sessão (sem API key aqui), mas de uma sessão irmã com uma
credencial real do Google AI Studio configurada como "Credencial de API" do ambiente de nuvem
(mecanismo específico do Claude Code: injeta o cabeçalho de autenticação no proxy de rede da
sessão, para a chamada de saída ao host permitido — a chave nunca aparece como variável de
ambiente de processo, então `GeminiConfig.from_env()` não a enxerga; o teste usou um valor de
placeholder só para passar da checagem de "chave vazia").

Script isolado (fora do repositório, nunca commitado), instanciando `GeminiConfig`,
`GeminiProvider` com o schema `campaign-plan`, e chamando `.generate()` com um `AIRequest` de
teste para `PLAN_CAMPAIGN`. Resultado, reproduzido em 2 tentativas:

```
ProviderError: GEMINI: erro HTTP 503 — {"error":{"message":"gemini-3.8-flash is currently
experiencing high demand, spikes in demand are usually temporary. Please try again
later.","code":"service_unavailable"}}
```

**O que isso confirma:** a requisição saiu de verdade e chegou em
`generativelanguage.googleapis.com` — não foi erro de rede, TLS ou timeout. Não houve erro de
autenticação (401/403) nas duas tentativas, apesar do valor de `api_key` enviado pelo código
ser um placeholder inválido — consistente com o proxy da sessão substituindo a credencial real
no cabeçalho de saída. O erro recebido (`503 service_unavailable`) é um formato de erro real e
coerente da API pública do Gemini, tratado corretamente pelo adapter como `ProviderError`
(nunca virou uma exceção não tratada nem um resultado silenciosamente incorreto).

**O que ainda não foi confirmado:** uma resposta de **sucesso** (200), que validaria o parsing
de `steps`/`model_output`/`usage` contra o formato real — as duas tentativas encontraram o
modelo `gemini-3.8-flash` sobrecarregado do lado do Google (`503`, tipicamente transitório).

## Pendência explícita antes de uso real em produção

1. Confirmar o parsing de uma resposta de **sucesso** real (200) — pendente por causa do
   `503` transitório acima, não por falha do adapter; repetir a mesma verificação mais tarde
   deve resolver.
2. Considerar adicionar o parâmetro de saída estruturada nativa uma vez que o campo certo for
   confirmado contra a documentação oficial (`WebFetch` para `ai.google.dev` seguiu bloqueado
   nesta sessão).
3. Reconfirmar o preço por milhão de tokens contra `ai.google.dev/gemini-api/docs/pricing`
   antes de 31/12/2026 (a tarifa introdutória usada aqui muda nessa data, por documentação do
   próprio Google).
4. Em produção real, a credencial não pode depender do mecanismo de proxy de sessão do Claude
   Code (existe só para chamadas feitas por uma sessão de desenvolvimento) — precisa ser uma
   variável de ambiente/Secret Manager de verdade no processo do backend implantado, exatamente
   como `GeminiConfig.from_env()` já espera.
