# WP-R04-03 — Revisão humana de materiais e ajustes

CURRENT: main@baba73a3e3c3965ff6ee4207eb4dd561ce834ad8, PR #70 e pós-merge verdes.
Status: PARTIAL / em validação.

## Delta
Revisor consulta estratégia/textos/públicos da campanha e a versão do pedido.
Solicitar ajustes/rejeitar usa o endpoint existente; motivo persistente é exposto no DTO.
A Web deve reutilizar a reautenticação administrativa Google e respeitar permissões/escopo.

Corrige rearmamento: após APPROVED/REJECTED/CHANGES_REQUESTED/APPLIED, nova decisão é recusada.
Uma aprovação APPLIED não volta APPROVED por voto de outro usuário e não autoriza outra verba.
PENDING com revisão dupla ainda admite o segundo ator distinto. Política atual reforça flag
legada incompleta antes de um novo voto. Replay da mesma operação devolve o fato histórico,
sem desfazer APPLIED nem criar outra decisão.

Novas escritas vinculam nonce a ator/unidade/corpo/alvo; respostas legadas só permitem
leitura histórica restrita, sem novo efeito. Autoridade e sessão são relidas dentro de F3;
verificação de ID token permanece fora da transação. Status/motivo/cache/auditoria são atômicos.
JSON das escritas protegidas tem limite de corpo/tempo; motivos continuam limitados a 1000.
A trilha de auditoria existente preserva a justificativa de cada decisão.

## Verificação exigida
Rearmamento de budget consumido, estados terminais, dois votos distintos, concorrência,
rollback, restart, replay/rebind, tenant/unidade, revogação, Unicode e limites de corpo.
API/PostgreSQL/Web/E2E, CI completa no HEAD e pós-merge antes de avançar.
A CI de desenvolvimento confirmou rearmamento bloqueado em PostgreSQL e ciclo de ajustes/
duas pessoas na UI. Corrigidos resets de React por chave/versão, fixture Unicode escapada
e expectativas antigas de clicar em autoaprovação: a UI agora desabilita, e os E2E mantêm
uma tentativa direta autenticada para provar 403/SoD no servidor, além do gate de step-up.

## Limites
Sem deploy, migration, credencial ou custo real. Não amplia autoridade da IA.
Não certifica imagem/preview nativo, qualidade comercial, Google/Meta/WhatsApp reais ou G7.
