# WP-R01 — escopo de unidade em staging

Data: 15/10/2026. Status: PARTIAL. Base inspecionada main@4d17f41c35d95ff473ab420be5164407c9166bb5; não é prova do SHA implantado.

Após controle positivo da leitura da campanha camp_000005_1ed30afd pelo VIEWER na unidade Principal (bu_000002_4e8fe763), foi reutilizada a unidade de homologação preexistente bu_000001_3f64ec55, 'Homologação G2 validada 20261014'. Google step-up real do proprietário foi confirmado antes das mutações.

Auditoria real observada no tenant A:
- BUSINESS_UNIT_ACTIVE em 15/10/2026 12:45:17, alvo bu_000001_3f64ec55.
- MEMBERSHIP_ACCESS_UPDATE em 12:46:29, alvo member_000001_5937138a: old_roles=[VIEWER], new_roles=[VIEWER], old_business_unit_id=bu_000002_4e8fe763, new_business_unit_id=bu_000001_3f64ec55.

Proprietário permanece OWNER na Principal, nenhuma ampliação de papel do usuário de teste. Campanha permanece DRAFT na Principal, sem publicação ou geração de IA. Conta B não alterada.

Próximas provas: atualizar endpoint da campanha na janela anônima com sessão antiga e capturar recusa; novo login com a mesma identidade, confirmar a nova unidade e VIEWER; tentar mesma campanha da Principal e observar negativa por unidade; conferir leitura da lista filtrada e manter evidência de auditoria. A mera troca registrada não certifica essas provas pendentes.

Último estado confirmado do banco nesta janela: RUNNABLE / ALWAYS. Desligar imediatamente ao terminar ou bloquear e obter STOPPED / NEVER. Nenhum merge, deploy, migration ou segredo real alterado. G2 continua PARTIAL.
