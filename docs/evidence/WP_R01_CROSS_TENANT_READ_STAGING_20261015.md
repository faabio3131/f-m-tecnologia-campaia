# WP-R01 — consulta cross-tenant real em staging

Data: 15/10/2026. Status: PARTIAL; G2 permanece PARTIAL.

## Pré-condições observadas

- Empresa A: tenant_000001_6fede697, unidade bu_000002_4e8fe763. Proprietário no navegador do agente; usuário VIEWER reativado na janela anônima do Diretor.
- Após orientação de usar a terceira conta controlada pelo Diretor, screenshot image(20261015-152054).png confirma sessão separada OWNER com 17 permissões em tenant_000001_3e5fd60a, unidade bu_000002_dd44fe1b e membership member_000003_44cc6ec4. E-mail não é exibido no dashboard: associação à conta escolhida depende do operador; IDs/papéis foram observados diretamente.
- Pela UI normal da empresa A foi criado um único briefing 'Homologação isolamento A 20261015', produto 'Recurso de teste G2 — sem publicação', público 'Equipe interna de homologação', orçamento planejado 10 BRL e teto planejado 1 BRL. UI confirmou DRAFT e link /campaigns/camp_000005_1ed30afd. Não foi chamada geração de IA, aprovação ou publicação, nem efetuado gasto em anúncios.

## Negativo observado

Diretor consultou na janela normal da empresa B:
GET /api/campaia/campaigns/camp_000005_1ed30afd

Screenshot image(20261015-152500).png inspecionado: corpo code NOT_FOUND; message 'Campaign not found.'; details vazio e assisted_flow_url null. Nenhum conteúdo da campanha de A foi exibido. Print não inclui status HTTP; não inferir 404 apenas do código de domínio.

## Controles e limites

Existência do rascunho em A comprovada pela listagem UI DRAFT. Controle positivo do mesmo endpoint no tenant A ainda pendente neste checkpoint. Tentativa de navegação do agente diretamente para a API no seu navegador retornou net::ERR_BLOCKED_BY_CLIENT; isso é limite do cliente, não resposta do CampaIA, nem evidência de bloqueio por bots. Controle positivo será executado pelo Diretor na janela anônima de A, que já acessou a API de memberships.

Ainda pendentes: isolamento entre unidades, mutações cross-tenant, replay externo aplicável e revogação por alteração de papel/unidade conforme matriz. Não generalizar um GET bloqueado para certificação de todas as superfícies. Nenhum merge/deploy/migration. Cloud SQL com última confirmação RUNNABLE / ALWAYS nesta janela; desligar ao término ou bloqueio e comprovar STOPPED / NEVER.
