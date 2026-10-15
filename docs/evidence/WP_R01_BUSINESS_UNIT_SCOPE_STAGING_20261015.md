# WP-R01 — escopo de unidade em staging

Data: 15/10/2026. Status: PARTIAL. Base inspecionada main@4d17f41c35d95ff473ab420be5164407c9166bb5; não é prova do SHA implantado.

Após controle positivo da leitura da campanha camp_000005_1ed30afd pelo VIEWER na unidade Principal (bu_000002_4e8fe763), foi reutilizada a unidade de homologação preexistente bu_000001_3f64ec55, 'Homologação G2 validada 20261014'. Google step-up real do proprietário foi confirmado antes das mutações.

Auditoria real observada no tenant A:
- BUSINESS_UNIT_ACTIVE em 15/10/2026 12:45:17, alvo bu_000001_3f64ec55.
- MEMBERSHIP_ACCESS_UPDATE em 12:46:29, alvo member_000001_5937138a: old_roles=[VIEWER], new_roles=[VIEWER], old_business_unit_id=bu_000002_4e8fe763, new_business_unit_id=bu_000001_3f64ec55.

Proprietário permanece OWNER na Principal, nenhuma ampliação de papel do usuário de teste. Campanha permanece DRAFT na Principal, sem publicação ou geração de IA. Conta B não alterada.

Próximas provas: atualizar endpoint da campanha na janela anônima com sessão antiga e capturar recusa; novo login com a mesma identidade, confirmar a nova unidade e VIEWER; tentar mesma campanha da Principal e observar negativa por unidade; conferir leitura da lista filtrada e manter evidência de auditoria. A mera troca registrada não certifica essas provas pendentes.

Último estado confirmado do banco nesta janela: RUNNABLE / ALWAYS. Desligar imediatamente ao terminar ou bloquear e obter STOPPED / NEVER. Nenhum merge, deploy, migration ou segredo real alterado. G2 continua PARTIAL.

## Resultados externos confirmados — 12:49 a 12:55

- Print image(20261015-154804).png ainda mostrava JSON anterior depois de F5; não usado como prova de uma consulta nova nem classificado como falha de revogação.
- Para distinguir nova navegação da resposta anterior, Diretor acessou o mesmo endpoint com query verificacao=g2-unidade-2. O handler não usa essa query para autorização. Print image(20261015-154919).png confirmou code UNAUTHENTICATED, message 'Sessao invalida ou expirada.' Nenhum dado da campanha retornou nessa consulta. Revogação por alteração de unidade observada.
- Após novo Google Login da mesma identidade na janela anônima, print image(20261015-155314).png confirmou membership member_000001_5937138a, tenant A original, nova unidade bu_000001_3f64ec55, papel VIEWER e 2 permissões.
- Nova consulta à mesma campanha da Principal com query verificacao=g2-nova-unidade, após relogin, produziu code NOT_FOUND e message 'Campaign not found.', sem dados da campanha. Screenshot image(20261015-155537).png inspecionado. Status HTTP não capturado no print.
- Controle positivo anterior na Principal e negativo após mudar de unidade foram realizados com a mesma identidade, mesmo tenant, mesmo recurso e mesmo papel. Escopo de unidade é a variável alterada; audit comprova a mutação.

## Encerramento da rodada

Cenários externos desta rodada observados: login e step-up; administração de unidade; convite/aceite; desativação e revogação; reativação e autoridade VIEWER; negativa MEMBER_VIEW na API; leitura própria positiva; leitura cross-tenant negativa; edição de unidade e revogação; novo login no escopo atualizado e leitura cross-unit negativa. Nenhum código alterado nem gasto em anúncios. Não generalizar essas provas para publicação real de canais, produção, todas as rotas/mutações, replay ou concorrência externos não executados.

Encerrada execução externa após o último print às 12:55. Próxima ação imediata: Diretor executar activationPolicy NEVER e confirmar STOPPED / NEVER. Banco não declarado desligado antes da resposta. O membership de teste fica ACTIVE / VIEWER na unidade de homologação, unidade também ACTIVE; proprietário permanece na Principal e rascunho permanece DRAFT, preservando dados de teste e auditoria. Isso evita mutações adicionais desnecessárias para limpeza.

G2 permanece PARTIAL neste commit, aguardando revisão da matriz/DoD e CI/documentação. O desligamento precede essa análise, que não requer banco ligado. PR #44 em Draft; nenhum merge/deploy/migration autorizado ou executado nesta rodada.

## Desligamento confirmado — 15/10/2026 13:00

Print image(20261015-160027).png inspecionado: patch activationPolicy NEVER concluído (done), instance campaia-staging-pg STATE STOPPED e ACTIVATION_POLICY NEVER. Janela externa encerrada. Não religar para revisão documental ou CI. Custos residuais de armazenamento/outros serviços não foram medidos e não são declarados zero.
