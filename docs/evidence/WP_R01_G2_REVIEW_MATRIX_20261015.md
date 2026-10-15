# WP-R01 / G2 — revisão da matriz externa

Data: 15/10/2026. Status da integração/certificação: PARTIAL. Produção: não autorizada.

## CURRENT e critério

Main confirmada em 4d17f41c35d95ff473ab420be5164407c9166bb5. PR #43 (AGENTS reconciliado) e PR #44 (evidências desta rodada) abertas em Draft, não mergeadas. Branch desta revisão: docs/wp-r01-staging-diagnostic-20261014. Nenhuma alteração funcional nesta PR.

Cronograma Mestre, G2: administração integral pelo produto, sem editar seed/diretório interno. O handoff WP-R01 e o Controle Mestre restringem o delta externo a Google real -> step-up -> criar/alterar unidade ou membership/role -> autoridade/revogação -> isolamento -> auditoria. Core IAM e guardrails de ownership já construídos não foram reimplementados.

## Matriz das provas externas observadas

| Critério do delta | Evidência | Resultado no escopo executado |
|---|---|---|
| Google Login real OWNER | Dashboard da conta A com tenant/unidade e OWNER | DONE_VERIFIED |
| Step-up real administrativo | Google reautenticação; UI bloqueada antes e habilitada após | DONE_VERIFIED |
| Administrar unidade pelo produto | Criar, renomear, desativar em 14/10; reativar em 15/10; auditoria | DONE_VERIFIED |
| Convite/aceite real | MEMBER_INVITE_CREATE e MEMBER_INVITE_ACCEPT; VIEWER ACTIVE | DONE_VERIFIED |
| Revogar sessão por desativação | MEMBER_DEACTIVATE; relato do F5 e screenshot de recusa de acesso após identidade Google | DONE_VERIFIED |
| Reativar e recompor autoridade | UI ACTIVE; novo login do mesmo membership, VIEWER / 2 permissões, tenant original | DONE_VERIFIED |
| RBAC aplicado na API | /memberships retorna PERMISSION_DENIED / ausência MEMBER_VIEW, sem lista | DONE_VERIFIED |
| Leitura cross-tenant negativa | OWNER de B recebe NOT_FOUND no recurso existente de A | DONE_VERIFIED |
| Controle positivo do recurso | VIEWER de A/Principal recebe JSON do DRAFT no mesmo endpoint/ID | DONE_VERIFIED |
| Mudança de unidade revoga sessão | MEMBERSHIP_ACCESS_UPDATE; nova requisição retorna UNAUTHENTICATED | DONE_VERIFIED |
| Autoridade após relogin | Mesmo membership/tenant, VIEWER, nova unidade bu_000001_3f64ec55 | DONE_VERIFIED |
| Leitura cross-unit negativa | Mesmo recurso da Principal retorna NOT_FOUND para a nova unidade | DONE_VERIFIED |
| Auditabilidade | Eventos reais de criação, aceite, lifecycle e alteração de escopo correlacionados | DONE_VERIFIED |
| Encerrar janela de custos | Print final Cloud SQL STOPPED / NEVER em 15/10 às 13:00 | DONE_VERIFIED |

DONE_VERIFIED nesta tabela aplica-se somente à observação/cenário identificado. Não substitui o status global da fase nem certifica todas as superfícies do SaaS.

## Referências versionadas

- WP_R01_STAGING_DIAGNOSTIC_20261014.md: diagnóstico inicial e 30 testes locais focados em organization_admin, organization_persistence e step_up_security, base main citada, OK.
- WP_R01_STAGING_PARTIAL_SUCCESS_20261014.md: Google, step-up e unidades em staging.
- WP_R01_SESSION_REVOCATION_STAGING_20261015.md: convite, desativação, reativação, autoridade e RBAC API.
- WP_R01_CROSS_TENANT_READ_STAGING_20261015.md: negativo B e controle positivo A.
- WP_R01_BUSINESS_UNIT_SCOPE_STAGING_20261015.md: alteração de unidade, revogação, relogin, negativo por unidade e desligamento.
- Evidências históricas F2/F3/F4: core, guardrails, idempotência, isolamento de mutações e runtime previamente implementados/certificados; não tratados como testes externos desta rodada.

## Limites e tratamento dos gaps

- Prints e UI comprovam os corpos e estados descritos; não foram capturados status HTTP/Har do navegador do Diretor. Não inventar códigos HTTP.
- Implantação permanece nas revisões históricas observadas backend 00002-pjr / Web 00001-lst. Não atribuir-lhes o SHA atual da main sem digest/image. Divergências de texto do dashboard/raiz já corrigidas na main continuam visíveis no staging antigo; não redesenvolver e não fazer deploy silencioso.
- Replay exato de mutações, concorrência, cross-tenant write, ownership transfer e todos os papéis possuem provas internas/históricas, mas não foram repetidos externamente nesta rodada. A matriz externa não é pentest completo nem homologação de canais.
- Sem geração IA, publicação de anúncios, pagamento, merge, migration ou deploy nesta rodada. DRAFT planejado 10 BRL não é gasto em anúncio; JSON mostrou spent_to_date 0 e external_resources vazio.
- Estado final dos fixtures comerciais: A2 ACTIVE / VIEWER na unidade de homologação ACTIVE; proprietário A na Principal; empresa B separada com OWNER; rascunho A na Principal em DRAFT. Preservar para eventual auditoria, não excluir silenciosamente.

## Decisão de engenharia e gate remanescente

O delta externo específico do WP-R01 foi exercitado; a antiga pendência genérica 'não houve Google/step-up/revogação/isolamento reais' está SUPERSEDED pelas provas acima. Não exigir repetir os mesmos testes por esquecimento documental.

F2/G2 continuam PARTIAL na integração até CI do HEAD documental final e revisão/inclusão autorizada das evidências no SSOT. Esta PR propõe fechar a pendência externa específica; não promove main, produção ou G20 por inferência. Se a revisão determinar requisito externo adicional, listar o cenário exato antes de abrir nova janela.

Após eventual merge autorizado, conferir CI pós-merge e promover status somente com o resultado real. WP-R02 continua condicionado ao fechamento do gate e às decisões comerciais reais; nada de plano/preço/Asaas de produção foi aprovado nesta rodada.

## Infraestrutura

Cloud SQL campaia-staging-pg confirmado STOPPED / NEVER no print image(20261015-160027).png, 15/10/2026 às 13:00. Revisão e CI independem de religar banco. Persistem possíveis custos residuais de storage/outros serviços, não medidos aqui.

## Adendo de integração — 15/10/2026

O estado de integração PARTIAL descrito acima é SUPERSEDED: PR #43 integrada em
0ef88d6651e8f3e415d802883269963d269ec5a6 e PR #44 integrada em
356f35448abf6b71b91c00a44a7ccc1db4e4906e, após autorização expressa do Diretor.
Consulta GitHub Actions confirmou as três execuções push do HEAD final concluídas em success:

- Backend #241: https://github.com/faabio3131/f-m-tecnologia-campaia/actions/runs/38767919126
- Frontend #179: https://github.com/faabio3131/f-m-tecnologia-campaia/actions/runs/38767919073
- F4 #75: https://github.com/faabio3131/f-m-tecnologia-campaia/actions/runs/38767919365

F2/G2: DONE_VERIFIED no critério do gate documentado nesta matriz. As limitações das
observações externas e os gates finais de segurança/UAT/produção continuam aplicáveis.
WP-R02 pode avançar em engenharia; decisões comerciais reais permanecem HUMAN_DECISION.
Nenhum novo teste de staging nem religamento do banco foi necessário para esta reconciliação.
