# WP-R02-06 — Estratégia com reserva, entrega e limites do contrato

**Status:** PARTIAL — candidato interno; G5 não encerrado.
**Base:** main@f0849f118661d23e2c95ee82f1880025448cc9c6, PR #49 integrada.
**Branch:** feat/wp-r02-metered-strategy-limits.

## CURRENT e aceite

PR #49: ciclo, franquia e consentimento integrados. Pós-merge verde em Backend 38808857688,
Frontend 38808857581 e F4 38808857689. A geração de estratégia ainda executava dentro da
transação HTTP de idempotência, sem reserva comercial. Uma chamada externa não pode ficar
nessa transação: rollback apagaria a reserva após execução/custo externo já ocorrido.

Critérios deste bloco: débito revisado antes da estratégia; reserva durável ANTES da chamada;
entrega/versão/resultado de replay e liquidação atômicos; falha conhecida/policy sem débito;
resultado incerto pendente sem redispatch; tenant/unidade autorizados antes de replay;
limites aplicados nos comandos de usuários e publicação/retomada.

## Implementação e fronteiras

- GET /campaigns/{id}/plan/quote exige CAMPAIGN_EDIT e acesso ao recurso/unidade. Não exige
  acesso às faturas para que o operador possa revisar o débito da ação permitida. Mostra
  custo, franquia disponível e excedente estimado calculados no servidor; não executa IA.
- Contrato com credit_policy exige confirmação de ciclo, versão, peso e estimativa máxima.
  Mudança que aumente o excedente exige nova revisão antes da execução. Excedente continua
  dependendo do consentimento/teto OWNER/FINANCE previamente registrado.
- A tabela F3 de idempotência existente guarda o claim de dispatch, fingerprint de contexto
  e resultado da entrega. Não existe outro banco ou fila como autoridade paralela. A reserva
  e o claim são commitados juntos. A chamada ao AgentRunner acontece fora de transação/lock.
- Um worker ganha o dispatch. Outro recebe resultado já durável ou indicação de pendência,
  nunca inicia outra chamada. Após restart, uma execução incerta permanece reservada.
- Versão da estratégia, entrega recuperável, auditoria e SETTLE são commitados juntos.
  A entrega tem referência lógica única. Mesmo resultado recuperado não é cobrado novamente.
- Output inválido, rejeição pelo Policy Engine existente ou campanha alterada durante a
  geração: sem entrega disponibilizada, RELEASE explícito. Timeout/erro externo incerto:
  permanece reservado e exige reconciliação; retries/fallback internos continuam custo FM.
- O check de conteúdo não concede autorização de publicação: aprovação e PolicyDecision
  de publicação continuam no fluxo existente. Vínculo completo do Brand Kit permanece F6.
- Web consulta a cotação e pede confirmação antes de iniciar a estratégia comercial. Em
  resposta incerta, mantém corpo e chave para recuperar a mesma operação. Voltar/revisar
  é uma solicitação nova; nenhuma nova tentativa externa é presumida em background.
- Contratos legados preservam o comportamento anterior, identificado como LEGACY com valores
  de crédito nulos, não uma oferta comercial gratuita ou franquia inventada.

## Limites e autoridade

Assinatura contratada é a autoridade dos novos contratos; mapa de catálogo do onboarding
continua somente como compatibilidade legada. Trial usa seus limites próprios. Contrato
vigente não recebe um limite inferior por alteração posterior do catálogo.

Convite reserva vaga; reativação respeita ocupação/convites. Aceite de convite revalida
capacidade no tenant sob o mesmo lock F3 das mutações tenant, inclusive para identidades
públicas distintas. Falha reverte aceite/vínculo e preserva o convite sem emitir sessão.

Campanhas PUBLISHING/ACTIVE/OPTIMIZING ocupam vaga por campanha interna, somando unidades.
Publicação/retomada verificam capacidade dentro da transação. Fim de créditos não pausa
anúncios nem bloqueia leitura ou kill switch. Pausa, retomada e controles de segurança
não debitam créditos. A operação paga nova ainda depende do acesso comercial vigente.

## Testes e evidência

- Reserva visível a outro worker antes de entrar no provider, fora de transação.
- Entrega válida consome uma vez; replay recupera resultado e versão.
- Cotação ausente/alterada e franquia insuficiente não chamam provider.
- Falha conhecida e policy bloqueada liberam; timeout permanece pendente após restart.
- Dois workers disputando a mesma operação: uma chamada, segundo pendente, replay recuperável.
- Outro tenant/unidade não recupera resultado por chave de idempotência.
- Campanha alterada durante geração não recebe nem paga entrega obsoleta.
- Limite de campanhas impede expansão; kill switch continua acessível com franquia esgotada.
- Organização criada pela API: trial bloqueia convite novo e aceite anterior acima do teto,
  preservando contador e convite após rollback.
- PostgreSQL acrescenta dispatch concorrente e entrega única ao cenário de dois workers.
- Web: revisão prévia, nenhuma chamada antes da confirmação, corpo/chave estáveis no retry,
  quota negada sem geração, compatibilidade do fluxo legado e strict types/contratos.

Resultados finais serão registrados na PR no HEAD exato. Simulador/IdP determinístico e
PostgreSQL de CI são evidência de engenharia, não homologação financeira ou IA de produção.

## Rollback e pendências

Não há migration nova neste bloco; usa os stores F3 e journal 005 existentes. Rollback que
remova claims/medição não pode reabrir dispatch incerto: drenar operações e bloquear novas
gerações comerciais antes de trocar a versão. Não limpar journal/idempotência para retry.

Próximos deltas F5: lifecycle na próxima vigência, cancelamento/reativação e dívida, scheduler
único/checkout completo, ajustes pós-fechamento/refunds/mínimo gateway, custos/homologação real.
Reconciliação operacional de dispatch incerto precisa estar disponível antes do lançamento;
este bloco não reexecuta sozinho uma chamada cujo resultado foi perdido. Apenas estratégia
está ligada ao débito; copy/audience/performance/imagem entram com suas entregas reais em F7,
sem anunciar consumo ou capacidades ainda não implementados.

Nenhuma credencial, cobrança externa, migration real, deploy ou religamento Cloud SQL.
