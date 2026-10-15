# WP-R01 — prova externa parcial de IAM em staging

Data local: 14/10/2026. Status: PARTIAL. Base de código inspecionada: main@4d17f41c35d95ff473ab420be5164407c9166bb5. Não é prova de que esse SHA estava implantado.

## Novas evidências que complementam o diagnóstico

- Print do Diretor no Cloud Shell confirmou Cloud SQL campaia-staging-pg STOPPED / activationPolicy NEVER. Backend: campaia-backend-staging-00002-pjr, tráfego 100%; Web: campaia-web-staging-00001-lst, tráfego 100%.
- Diretor autorizou ligar exclusivamente staging para os testes e exigiu desligamento assim que terminassem, inclusive em caso de bloqueio.
- Diretor executou o patch activationPolicy ALWAYS. O CLI excedeu sua espera; consulta posterior mostrou operação UPDATE ainda RUNNING e instância RUNNABLE / ALWAYS. Não se repetiu a mutação.
- GET /api/campaia/health/ready retornou primeiro 503, depois 200. A recuperação após ativar o banco é observada; não há log correlacionado que prove causa exclusiva do 500 anterior.
- Google Login real com a identidade de homologação abriu /dashboard com sessão OWNER e MFA indicado como sim.
- Em /settings/organization, ações sensíveis estavam desabilitadas antes da reautenticação.
- Novo Google step-up mostrou 'Identidade revalidada. A próxima operação sensível pode continuar.'
- Criação real da unidade 'Homologação G2 20261014' confirmada como ACTIVE.
- Renomeação para 'Homologação G2 validada 20261014' confirmada.
- Desativação dessa unidade de teste confirmada como INACTIVE. Unidade Principal permaneceu ACTIVE; nenhum papel foi alterado.
- /audit confirmou BUSINESS_UNIT_CREATE (22:56:48), BUSINESS_UNIT_RENAME (22:57:06) e BUSINESS_UNIT_INACTIVE (22:57:19), no horário de São Paulo, para o mesmo recurso/ator da sessão. Sem tokens ou credenciais coletados.

## Limites

G2 continua PARTIAL: revogação de sessão por alteração de membership, autoridade após relogin, isolamento cross-tenant/business-unit e replay externo não foram homologados nesta rodada. As 30 provas locais já documentadas não substituem essas evidências externas. A navegação mostrou apenas uma identidade/tenant disponível; a matriz de atores para as próximas provas deve ser preparada antes de reabrir janela onerosa.

## Encerramento da janela

Testes encerrados após conferir auditoria. Solicitada imediatamente ao Diretor a execução do patch activationPolicy NEVER e describe. O print image(20261015-015936).png recebido e inspecionado em 14/10/2026 às 22:59 (São Paulo) confirma: patch done, instância campaia-staging-pg STOPPED e activationPolicy NEVER. Janela de processamento encerrada conforme a autorização. Não houve religamento posterior nesta execução. Armazenamento e outros recursos podem manter custos residuais; o desligamento não significa custo total zero.

## Governança

Nenhum deploy, merge, migration, alteração de papel, convite de terceiro, segredo ou configuração de produção. Alterações feitas somente pela UI normal de staging e somente na unidade explicitamente criada para homologação. O recurso de teste foi desativado, preservando histórico. PR #44 contém apenas documentação; CI da nova revisão ainda pendente.

## Pausa solicitada pelo Diretor — 14/10/2026, 23:04 (São Paulo)

Diretor encerrou a sessão e pretende retomar em 15/10/2026. Não é solicitação de automação nem autorização para religar infraestrutura durante a ausência.

Ponto exato de retomada: WP-R01 / G2 PARTIAL. Preservar as provas reais de login, step-up e administração de unidade já obtidas. Cloud SQL foi confirmado STOPPED / NEVER antes da pausa. Não repetir essas provas como se fossem funcionalidades ausentes.

Próxima sequência:
1. Confirmar CURRENT, main/HEAD, PRs #43/#44 e CI; não presumir merge ou aprovação.
2. Preparar com o Diretor contas Google válidas sob seu controle para os papéis de proprietário A, usuário A e proprietário B, podendo reutilizar atores existentes conforme CURRENT. Nomes de empresas podem ser fictícios; identidades não devem ser simuladas nesta homologação. Não coletar senhas/tokens no chat.
3. Usar somente onboarding/convites normais do produto, sem seed ou inclusão manual no banco. Convites/envios e concessões sensíveis exigem alvo e autorização específicos; nenhum convite foi enviado nesta sessão.
4. Preparar matriz de revogação por mudança de acesso, relogin/autoridade final, isolamento entre tenants e unidades e replay externo aplicável, com trilha de auditoria. Usar sessões separadas por identidade para provar que a sessão antiga foi invalidada.
5. Antes de nova janela onerosa, confirmar autorização do Diretor para ligar staging exclusivamente durante os testes. O compromisso vigente é desligar imediatamente ao terminar ou encontrar bloqueio e comprovar STOPPED / NEVER.
6. Executar o delta externo, registrar resultados reproduzíveis e manter G2 PARTIAL se qualquer prova obrigatória faltar. Não iniciar WP-R02 nem promover G2 prematuramente.

Nenhum merge/deploy/migration ou produção autorizado por esta pausa.
