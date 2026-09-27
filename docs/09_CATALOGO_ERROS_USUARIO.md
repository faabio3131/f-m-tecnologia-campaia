# CAMPAIA — CATÁLOGO DE ERROS EM LINGUAGEM DE USUÁRIO

**Versão:** 1.1.0 — 04/09/2026 (v1.0.0 de 29/08/2026 + correção da P-19 em 04/09/2026)
**Bloco:** B10, recomendado e executado sob autorização do Diretor ("b10"); P-19 corrigida sob autorização do
Diretor ("pode corrigir não vamos deixar nenhum erro para trás").

## Propósito e escopo

Este catálogo traduz a taxonomia técnica de erros do CAMPAIA — hoje expressa apenas como códigos de máquina
(`code`, HTTP status) no corpo JSON `{code, message, details, assisted_flow_url}` devolvido pela API — em
mensagens que um usuário final (marketer, aprovador, financeiro) entende, sem jargão de engenharia. O
catálogo não substitui o `code` técnico (que o app continua recebendo e pode logar/depurar); ele acrescenta,
para cada código, um texto de exibição e uma ação sugerida.

Fonte de verdade: os 21 códigos efetivamente presentes em `api/errors.py` (`STATUS_BY_CODE`), verificados por
leitura direta do arquivo real no Drive (não de memória). Os 3 últimos (`AUTH_EXPIRED`, `VALIDATION_REJECTED`,
`PARTIAL_FAILURE`) foram um achado desta formalização em 29/08 — descobertos sem mapeamento HTTP — e
corrigidos em código em 04/09 (P-19); ver Seção 3 para o histórico completo do achado e da correção.

## 1. Catálogo de mensagens (21 códigos ativos)

| Código técnico | HTTP | Título para o usuário | Mensagem | Ação sugerida |
|---|---|---|---|---|
| `UNAUTHENTICATED` | 401 | Sessão não identificada | Não foi possível confirmar quem você é. | Faça login novamente. |
| `PERMISSION_DENIED` | 403 | Sem permissão para esta ação | Seu perfil de acesso não permite fazer isso. | Peça a um administrador da conta para revisar suas permissões, ou solicite a ação a alguém com o papel adequado. |
| `STEP_UP_REQUIRED` | 403 | Confirme sua identidade novamente | Esta ação é sensível e exige uma confirmação de identidade recente. | Confirme sua senha ou segundo fator novamente e tente de novo. |
| `MFA_REQUIRED` | 403 | Ative a verificação em duas etapas | Esta ação só é permitida com verificação em duas etapas ativada no seu perfil. | Ative a verificação em duas etapas nas configurações da sua conta. |
| `VALUE_CEILING` | 403 | Valor acima do que você pode aprovar sozinho | O valor desta ação passa do limite que seu papel pode autorizar sem apoio. | Peça para alguém com um papel de maior alçada (ex.: Financeiro ou Owner) aprovar, ou reduza o valor. |
| `SEPARATION_OF_DUTIES` | 403 | Quem propôs não pode aprovar | Por regra de segurança, a pessoa que criou esta solicitação não pode ser quem a aprova. | Peça para outra pessoa com permissão de aprovação revisar. |
| `APPROVAL_REQUIRED` | 403 | Aguardando aprovação | Esta ação exige aprovação de outra pessoa antes de acontecer. | Acompanhe o status da aprovação na tela de Aprovações; nenhuma ação sua é necessária agora. |
| `VALIDATION_FAILED` | 422 | Alguns dados precisam de ajuste | As informações enviadas não estão completas ou têm um formato inválido. | Revise os campos destacados e tente novamente. |
| `INVALID_STATE` | 409 | Esta ação não é possível agora | A campanha ou o recurso está em um estado que não permite esta operação no momento. | Verifique o status atual do item antes de tentar de novo (ex.: uma campanha pausada pode precisar ser retomada primeiro). |
| `CAPABILITY_UNSUPPORTED` | 422 | Recurso não disponível para esta conta | Esta ação não é suportada para a conta ou plataforma conectada. | Use o fluxo assistido indicado (quando disponível) ou entre em contato com o suporte para verificar alternativas. |
| `BUDGET_LIMIT` | 422 | Orçamento insuficiente | O valor solicitado excede o orçamento disponível ou o teto diário configurado. | Ajuste o valor solicitado ou aumente o orçamento da campanha antes de tentar novamente. |
| `RATE_LIMITED` | 429 | Muitas tentativas em pouco tempo | O sistema está temporariamente limitando esta operação para proteger sua conta. | Aguarde alguns instantes e tente novamente; não é necessário repetir a ação imediatamente. |
| `QUOTA_EXHAUSTED` | 429 | Limite diário atingido | A cota diária de operações desta conta na plataforma externa foi esgotada. | Aguarde a renovação da cota (geralmente no dia seguinte) ou reduza a frequência de operações. |
| `POLICY_VIOLATION` | 422 | Conteúdo ou ação bloqueados por política | Esta campanha ou criativo contraria uma política de publicidade e precisa de revisão. | Revise o conteúdo apontado e ajuste conforme a orientação exibida, ou solicite revisão humana. |
| `KILL_SWITCH_ACTIVE` | 409 | Pausado por segurança | Um botão de emergência (kill switch) está ativo neste escopo, pausando novas ações. | Aguarde a desativação do kill switch por um administrador, ou contate o responsável pela conta. |
| `NOT_FOUND` | 404 | Não encontrado | O item que você está tentando acessar não existe ou você não tem acesso a ele. | Confira se o link ou identificador está correto; se o problema persistir, contate o suporte. |
| `TRANSIENT` | 503 | Falha temporária, tente novamente | Uma instabilidade temporária impediu a conclusão da ação. | Tente novamente em alguns instantes. Se persistir, contate o suporte. |
| `UNKNOWN` | 500 | Algo deu errado | Ocorreu um erro inesperado que ainda não tem uma explicação específica. | Tente novamente; se o problema continuar, contate o suporte informando o horário aproximado. |
| `AUTH_EXPIRED` | 401 | Conexão com a plataforma expirou | O acesso autorizado à sua conta do Google Ads/Meta/WhatsApp não é mais válido. | Reconecte a conta na tela de Conexões. |
| `VALIDATION_REJECTED` | 422 | Conteúdo recusado pela plataforma | A plataforma de anúncios recusou o conteúdo ou configuração enviada. | Revise o criativo ou configuração apontados e reenvie; evite repetir exatamente a mesma tentativa. |
| `PARTIAL_FAILURE` | 207 | Publicação parcialmente concluída | Parte da publicação em múltiplos canais teve sucesso; outra parte falhou. | Veja o detalhamento por canal; o sistema pode pausar tudo, manter o que funcionou, ou escalar para revisão humana, conforme a política configurada para esta conta. |

### Notas de aplicação

- **`assisted_flow_url`**: quando presente no corpo do erro (hoje usado por `CAPABILITY_UNSUPPORTED` e por
  falhas de conector, conforme `campaia_core/connectors.py` e `ConnectorError.assisted_flow_url`), a
  interface deve mostrar um link ou botão levando a esse fluxo assistido, além da mensagem acima — nunca
  apenas o texto genérico.
- Nenhuma mensagem deste catálogo tenta explicar como "consertar sozinho" um `POLICY_VIOLATION` ou
  `CAPABILITY_UNSUPPORTED` com um passo técnico específico, porque o motivo exato (`details`, já presente no
  corpo do erro) varia por caso — a mensagem aponta a direção (revisar conteúdo, contatar suporte), e o
  `details` técnico complementa quando a interface optar por exibi-lo.
- `KILL_SWITCH_ACTIVE` é deliberadamente neutro quanto à causa: o usuário final não precisa (e não deve) ver
  o escopo interno do kill switch (`CAMPAIGN`/`ACCOUNT`/`TENANT`/`PLATFORM`/`GLOBAL`) — isso é informação de
  auditoria/operação, não de experiência do usuário.
- `PARTIAL_FAILURE` usa HTTP 207 (Multi-Status), não 422, porque é genuinamente um resultado misto (parte da
  publicação multicanal teve sucesso, parte falhou) — tratá-lo como falha total (422) esconderia do cliente
  que algo já foi publicado de fato.

## 2. Cobertura verificada

Os 21 códigos acima foram extraídos programaticamente de `api/errors.py` (`STATUS_BY_CODE`, o mapa real que a
API usa para toda tradução `code → status HTTP`), lido diretamente do Drive nesta sessão — não de memória ou
de uma listagem anterior. Confirmei que cada um dos 8 códigos de domínio definidos em
`campaia_core/errors.py` (`CampaiaError` e suas subclasses: `InvalidStateTransition`, `GuardFailed`,
`ApprovalRequired`, `BudgetLimitExceeded`, `PolicyViolation`, `CapabilityUnsupported`, `KillSwitchActive`,
`TenantIsolationViolation`) mapeia para um dos códigos cobertos, que os 3 códigos de `DenialCode`
(`campaia_core/permissions.py`: `MFA_REQUIRED`, `VALUE_CEILING`, `SEPARATION_OF_DUTIES`) — usados pela função
`authorize()`/`can_approve()` do módulo de permissões — também estão cobertos, exatamente como o comentário
do próprio `api/errors.py` já apontava ("DenialCode values not already covered above by name"), e que os 10
códigos de `ConnectorErrorCode` (`campaia_core/connectors.py`) estão, desde a correção da P-19 (Seção 3),
também 100% cobertos.

## 3. Achado e correção: 3 códigos do Connector Hub sem mapeamento HTTP (P-19)

**Achado (29/08/2026):** ao cruzar `STATUS_BY_CODE` (api/errors.py) contra `ConnectorErrorCode`
(campaia_core/connectors.py) — comparação feita programaticamente, não de memória — encontrei que **3 dos 10
códigos de erro do Connector Hub não tinham entrada em `STATUS_BY_CODE`**:

| Código | Onde é levantado | O que acontecia se cruzasse a fronteira HTTP (antes da correção) |
|---|---|---|
| `AUTH_EXPIRED` | `campaia_core/connectors.py` (`NON_RETRYABLE`); `campaia_core/simulator.py` pode ser programado para levantá-lo via `scripted_failures` | `from_domain_error()` (api/errors.py) fazia `code not in STATUS_BY_CODE` → substituía por `UNKNOWN`, status 500 |
| `VALIDATION_REJECTED` | `campaia_core/connectors.py` (`NON_RETRYABLE`); levantado de fato em `campaia_core/saga.py:191`; `simulator.py` também pode programá-lo | Mesmo colapso: virava `UNKNOWN`/500 |
| `PARTIAL_FAILURE` | `campaia_core/connectors.py` (`ConnectorErrorCode`), usado pela Saga para decidir compensação | Mesmo colapso: virava `UNKNOWN`/500 |

Isto não era um bug latente teórico: `VALIDATION_REJECTED` já é levantado por código real em `saga.py:191`
durante o fluxo de publicação multicanal, e `simulator.py` (o único `AdsConnector` real hoje, usado em testes)
aceita todos os 10 códigos como `scripted_failures`, incluindo os 3 sem mapeamento.

**Correção (04/09/2026), sob autorização do Diretor ("pode corrigir não vamos deixar nenhum erro para
trás"):** adicionadas as 3 entradas faltantes a `STATUS_BY_CODE` em `api/errors.py`, com o mesmo raciocínio já
usado nos demais códigos:

- `AUTH_EXPIRED` → **401**, espelhando `UNAUTHENTICATED` — a credencial do lado da plataforma externa não é
  mais válida.
- `VALIDATION_REJECTED` → **422**, espelhando `VALIDATION_FAILED` — a plataforma externa recusou o conteúdo
  ou configuração enviados.
- `PARTIAL_FAILURE` → **207** (Multi-Status) — é um resultado genuinamente misto (parte publicada, parte não),
  não uma falha total; usar 422 esconderia do cliente que algo já foi publicado de fato.

A correção foi verificada com 8 testes novos e reais em `tests_api/test_errors_p19.py` (não apenas "a suíte
antiga continua passando"): confirmam que os 10 códigos de `ConnectorErrorCode` estão cobertos, que cada um
dos 3 códigos mapeia para o HTTP correto, que `from_domain_error()` agora preserva o código original em vez
de colapsar para `UNKNOWN` (testado construindo um `ConnectorError` real para cada um dos 3 códigos), e um
teste de regressão que reproduz deliberadamente o comportamento antigo (removendo os 3 códigos de uma cópia
do mapa) para provar que o mecanismo de colapso realmente existia e que a correção o evita agora. Toda a
suíte foi re-executada após a mudança: **237 testes de domínio + 80 testes de API/persistência (72 já
existentes + 8 novos da P-19), todos aprovados, zero regressão.**

Mensagens de usuário para os 3 códigos (já haviam sido propostas em 29/08, mantidas sem alteração de texto,
apenas movidas para a tabela principal da Seção 1 agora que o código as suporta de fato):

| Código técnico | HTTP (agora real) | Título para o usuário | Mensagem | Ação sugerida |
|---|---|---|---|---|
| `AUTH_EXPIRED` | 401 | Conexão com a plataforma expirou | O acesso autorizado à sua conta do Google Ads/Meta/WhatsApp não é mais válido. | Reconecte a conta na tela de Conexões. |
| `VALIDATION_REJECTED` | 422 | Conteúdo recusado pela plataforma | A plataforma de anúncios recusou o conteúdo ou configuração enviada. | Revise o criativo ou configuração apontados e reenvie; evite repetir exatamente a mesma tentativa. |
| `PARTIAL_FAILURE` | 207 | Publicação parcialmente concluída | Parte da publicação em múltiplos canais teve sucesso; outra parte falhou. | Veja o detalhamento por canal; o sistema pode pausar tudo, manter o que funcionou, ou escalar para revisão humana, conforme a política configurada para esta conta. |

## 4. Limitações e pendências desta formalização

- O tom e a cobertura fina por segmento de cliente (ex.: linguagem diferente para agências vs. anunciantes
  diretos) dependem de D-03 (segmento/MVP), ainda em aberto — as mensagens acima usam um tom neutro e
  profissional que serve qualquer segmento, sem assumir uma decisão de produto ainda não tomada.
  Recomendo revisar o tom quando D-03 for decidida, mas isto não bloqueia o uso do catálogo hoje.
- Nenhuma mensagem foi testada com usuários reais (não há usuários reais nesta fase do projeto) — a
  formalização segue a mesma disciplina de honestidade do restante do projeto: não inventa validação que não
  aconteceu.
- O achado da Seção 3 (3 códigos de conector sem mapeamento HTTP) foi corrigido em código em 04/09/2026 —
  ver Seção 3 para a correção completa, os testes que a comprovam e os números da suíte re-executada.

## 5. Resumo

Catalogadas as 21 mensagens de erro efetivamente ativas na API (`STATUS_BY_CODE` de `api/errors.py`), cruzadas
e confirmadas contra os 8 códigos de domínio (`campaia_core/errors.py`), os 3 `DenialCode` de autorização
(`campaia_core/permissions.py`) e os 10 códigos do Connector Hub (`campaia_core/connectors.py`) que as
alimentam — toda extração feita por leitura direta dos arquivos reais no Drive, não de memória. Um gap real de
3 códigos do Connector Hub (`AUTH_EXPIRED`, `VALIDATION_REJECTED`, `PARTIAL_FAILURE`) sem mapeamento em
`STATUS_BY_CODE`, identificado em 29/08/2026 e confirmado como code-reachable (`VALIDATION_REJECTED` já
levantado em produção por `saga.py`), foi corrigido em código em 04/09/2026 (P-19), com 8 testes novos e reais
provando a correção (não apenas a ausência de regressão) e a suíte completa (237 domínio + 80 API/persistência)
re-executada e aprovada sem falhas.
