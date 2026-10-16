# WP-R03-03 — Marca selecionada no pipeline (16/10/2026)

## CURRENT e preservação
main@c1a1271866d8b6bd40858f840e691b86f43e310b. PR #67:
HEAD 52d6ac05ca17a165f7c5ebf9315bf7b8002da1fb; Backend 38847188726,
Frontend 38847188772, F4 38847188782 verdes. Pós-merge 38847407887,
38847407874 e 38847407907 verdes. Preservam-se transporte, worker restrito,
assets privados, quota/fences, histórico textual e todas as regras comerciais aprovadas.

Faltava escolher a marca da campanha e aplicar seu contexto. Não havia seleção:
_run_strategist recebia apenas objetivo/orçamento/público/região, e Brand Profile
permanecia separado. PolicyRequest.brand_restrictions é denylist literal (substring),
não intérprete das orientações livres cadastradas pelo usuário.

## Delta
BriefInput recebe brand_selection opcional, com brand_profile_id, expected_version
estrito e até 20 asset_ids únicos. Não aceita tenant, bucket, snapshot, caminhos,
geração ou conteúdo autoritativo do cliente. Sem escolha não aplica marca alguma.
A marca/perfil é compartilhada no tenant segundo o RBAC já existente; campanha
mantém a unidade de negócio autorizada.

Dentro da transação F3 que cria a campanha: confere perfil/versão/assets do tenant,
READY/namespace disponível e congela perfil + metadata pública dos arquivos em
brief.brand_snapshot_v1. IDs de asset referenciam manifesto/generation imutáveis.
Não expõe bucket/object path/token. Edição futura do perfil não muda o briefing;
versão alterada antes do commit gera 409. Não há nova migration ou novo cadastro.

Nonce de briefing vincula ator/unidade/corpo/seleção; respostas legadas só são lidas
para o mesmo briefing e recurso/ator/unidade autorizados. Validação/publicação
também autorizam o recurso antes de replay e recusam nonce de outra campanha.

Estratégia recebe texto da marca (tom, cores, diferenciais, restrições) e metadata
dos arquivos explicitamente selecionados. AgentRunner sanitiza antes do provider.
Não envia URL privada, bucket, credencial nem bytes de imagem para Gemini nesta etapa.
**Metadata de arquivo não significa visão de imagem ou aplicação visual do logo.**
A aplicação visual e geração de criativos continuam F7/WP-R04.

## Política e remoção
Orientações em linguagem natural passam ao Policy Engine como brand_guidance:
finding WARNING e revisão humana obrigatória, mesmo se outra regra de autonomia
permitisse execução. Não se finge que substring entende semântica. A denylist literal
brand_restrictions e seu bloqueio existente permanecem intactos.

Arquivo selecionado indisponível produz BLOCKING sem policy_decision_id. Há check
antes do provider, na entrega persistente e antes de publicação nova; não há débito
comercial por saída descartada nem efeito externo autorizado pelo texto da IA.
Snapshot histórico continua consultável. No fluxo atual, um arquivo removido exige
novo briefing com arquivo disponível; não se altera silenciosamente a campanha antiga.
Pause/kill continuam disponíveis. Remover arquivo não pausa anúncio já publicado;
a confirmação na Web explica esse impacto. Replays de fatos já entregues não redisparam.

## Web e contrato
Escolha sob demanda, padrão Sem Brand Kit, versão visível e checkboxes de arquivos
prontos. Snapshot no detalhe permite revisar tom/restrições/arquivos da versão usada.
Nenhum campo é atualizado automaticamente para uma marca posterior.
Briefing usa nonce/corpo estáveis em resultado incerto, com campos bloqueados até
conferir a mesma solicitação. Páginas remontam por tenant/usuário/unidade e campanha,
evitando estado visual antigo após troca de contexto; RBAC oculta nova criação.

OpenAPI agora declara a entrada BFF real BriefInput, sem confundi-la com o envelope
canônico campaign-brief.schema.json (que inclui campos autoritativos do servidor).
Tipos gerados devem corresponder à ferramenta na CI.

## Validação e limites
Testes: snapshot/versão/asset explícitos, corpo/ator/unidade/nonce, isolamento,
reinício, rollback, corrida com edição, contexto efetivamente recebido pelo provider
simulado, política determinística e arquivo removido antes de novo efeito.
Web: escolha explícita, nonce incerto, permissão, troca de tenant e snapshot legível.
E2E real API/SQLite/Next/worker: seleciona logo, cria campanha, edita marca depois,
gera estratégia com versão registrada, exige revisão de orientação, remove imagem
e prova bloqueio posterior. Storage e IA permanecem simulados explícitos nesse E2E.

CI do HEAD e pós-merge devem ser registradas após os workflows. Não certifica
GCS/Gemini real nesta etapa, aplicação visual, F6/G6 completo, F7/G7 ou produção.
Nenhum deploy/migration real/credencial/gasto/ativação de SQL/storage foi executado.
Antes de ativar, homologar os runtimes reais e planejar rollback que preserve leitura
e enforcement dos snapshots/regras; revisão anterior ao WP não entende esses campos.
