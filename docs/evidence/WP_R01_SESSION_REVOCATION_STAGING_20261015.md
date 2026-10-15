# WP-R01 — revogação real de sessão por desativação

Data: 15/10/2026, America/Sao_Paulo. Status WP-R01/G2: PARTIAL.

## Contexto

Continuação autorizada pelo Diretor usando identidades Google sob seu controle, aplicação publicada em staging e Cloud SQL real. Base inspecionada main@4d17f41c35d95ff473ab420be5164407c9166bb5. Nenhuma implementação alterada. A implantação mantém revisões históricas; não atribuir a elas o SHA da main sem verificar imagens/digests.

O Diretor abriu nova janela de Cloud SQL. Print de 11:11 confirmou RUNNABLE / ALWAYS, com UPDATE ainda RUNNING na consulta imediatamente anterior. Não houve repetição do patch. Não há desligamento confirmado para esta nova janela até este checkpoint.

## Execução e observações

1. Sessão OWNER do tenant A acessou /settings/users no navegador do agente, isolado da janela anônima do Diretor.
2. Reautenticação Google real do proprietário confirmou step-up.
3. Convite VIEWER para a identidade A2 controlada pelo Diretor, unidade Principal. Audit MEMBER_INVITE_CREATE às 11:15:35.
4. Diretor abriu aceite na janela anônima e autenticou a identidade convidada. Audit MEMBER_INVITE_ACCEPT às 11:36:07; UI do proprietário confirmou VIEWER / ACTIVE. Nenhuma credencial ou token de convite incluído nesta evidência.
5. Após novo Google step-up do proprietário, desativado apenas o membership de teste. UI confirmou VIEWER / INACTIVE, preservando OWNER / ACTIVE. Audit MEMBER_DEACTIVATE às 11:37:53.
6. Diretor relatou que F5 na janela anônima exigiu login novamente. Print image(20261015-143933).png inspecionado confirma /login?next=%2Fdashboard e mensagem: 'Sua conta foi autenticada, mas está sem vínculo com nenhum tenant do CampaIA.' Formulário de onboarding foi apresentado; nenhum novo tenant foi criado como parte desta observação.

## Resultado e limites

Prova externa de revogação por desativação: sessão antiga deixou de acessar dashboard, conforme relato do operador e screenshot, correlacionados com desativação auditada. Ausência de vínculo ativo após identidade Google é consistente com o bloqueio esperado. Não foram capturados HAR/status HTTP do navegador do Diretor; não inferir códigos exatos.

Ainda pendentes: reativação/relogin e autoridade final; revogação por edição de papel/unidade; isolamento cross-tenant/business-unit; replay externo aplicável. Não promover G2. Não usar esta prova como certificação de produção.

## Segurança e continuidade

Conta A2 permanece INACTIVE neste checkpoint. Não alterar o proprietário. Não instruir criação de empresa como solução para o acesso revogado. Preparar próximos testes antes de prolongar a janela de custos. Ao concluir ou bloquear, Diretor deve executar desligamento e comprovar STOPPED / NEVER, conforme compromisso vigente. Nenhum merge, deploy, migration ou segredo alterado.
