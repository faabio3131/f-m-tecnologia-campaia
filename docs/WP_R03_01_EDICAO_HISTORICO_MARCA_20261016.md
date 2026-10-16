# WP-R03-01 — Edição e histórico textual do Brand Kit
Data: 16/10/2026. CURRENT main@fcf7ac2788886acba6196e066fc94757f56888cf.
F6 permanece PARTIAL. Cloud SQL desligado; nenhum storage foi provisionado/contatado.

## Evidência preservada
PR #63 HEAD 925a0d49c17592da51bce7e6b7e748323725301a:
Backend 38839602384, Frontend 38839602379, F4 38839602372 verdes.
Pós-merge main@fcf7ac2788886acba6196e066fc94757f56888cf:
Backend 38839959261, Frontend 38839959196, F4 38839959204 verdes.
450 domínio, 496 API (23 PostgreSQL no job próprio), contrato, navegador e containers.
F5/G5 segue PARTIAL: custo real/tarifa/câmbio, fiscal, credenciais, ativação de jobs e
homologação externa não foram certificados por simulador/CI.
Migrações 006/007 continuam apenas em fonte/CI, sem aplicação real.

## Lacuna comprovada
routes_brand.py só tinha GET-list/POST-create. A Web dizia que podia editar e já alimentava
IA, mas não tinha edição nem seleção/aplicação ao pipeline. Não reconstruímos cadastro.
A descrição da tela agora informa apenas a definição de dados de marca.

## Comportamento
GET /brand-profiles/{id}, PUT com expected_version e GET /.../versions completam a edição
textual/histórico. BRAND_MANAGE é autoridade de escrita; CAMPAIGN_VIEW permite consulta.
Tenant deriva da sessão; não há tenant/autor/versão nova arbitrários vindos do cliente.
O nonce fica vinculado ao ator, unidade, recurso e corpo, inclusive na criação. Compatibilidade
de respostas antigas de criação é preservada sem alocar outro profile.

PUT substitui os campos revisados e exige a versão atual. Duas edições concorrentes têm
um vencedor; a outra recebe BRAND_VERSION_CHANGED e preserva o rascunho para nova revisão.
Identidade e created_at permanecem, version cresce e updated_at é registrado.
Snapshots anterior/novo, profile atual, auditoria e resposta são uma transação F3.
Falha reverte tudo. Auditoria contém números de versão, não cópias do texto privado.

Versões usam snapshots imutáveis no store F3 existente, com lookup direto e paginação
decrescente de 50 versões. GET não fabrica gravação histórica: um profile legado v1 sem
snapshot é exibido como baseline atual; sua primeira edição congela esse baseline, sem
inventar autor/data de edição. Lacuna ou divergência de histórico exige conferência.
Dados legados longos continuam legíveis; limites de entrada protegem novas gravações.

## Web
Permissões governam cadastro/edição, mantendo consulta/histórico para quem pode ler.
Formulário carrega versão explícita, não sobrescreve rascunho após conflito e permite
recarregar dados antes de revisar. Incerteza mantém o mesmo nonce/payload e bloqueia
alterações até consultar a mesma solicitação, sem versão otimista ou criação duplicada.
Mudança de tenant/usuário/unidade remonta o conteúdo, descarta rascunhos e ignora resposta
tardia do contexto anterior. Leitura atrasada não substitui lista mais recente.
Histórico mostra conteúdo e datas efetivamente conhecidas, sem expor IDs pessoais do editor.

Contrato separa entrada limitada de saída histórica: additionalProperties e metadados
de saída não conflitam por allOf. O ID é string, coerente com os IDs bp_* reais.
Campos novos version/updated_at são aditivos e opcionais no contrato de leitura.

## Persistência e rollout
brand_v1 isola campos novos do construtor legado; dados antigos assumem versão baseline 1.
Não há nova tabela ou migration neste WP. Writers antigos não podem regravar profiles
versionados: drenar/bloquear mutação de marca antes de rollback sem esse formato.
Histórico não será apagado ou corrigido silenciosamente.

## Validação
CI completa no HEAD exato e pós-merge obrigatórias antes de DONE_VERIFIED.
Servidor de comandos local indisponível; validação em GitHub Actions.
API: identidade/created_at/histórico, concorrência, replay de criação/edição, ator/unidade/
corpo/recurso, RBAC/cross-tenant, rollback, legado, divergência, limites e paginação.
PostgreSQL: duas conexões/edições simultâneas, snapshots e auditoria atômicos, isolamento
e rollback visível pelo outro worker. Web: edição, conflito, retry da mesma criação/edição,
leitura sem edição e troca de organização durante resposta pendente.
Navegador: cenário L existente ampliado com edição real, duas abas, conflito e histórico,
mantendo o fluxo de conexão posterior. Não equivale a homologação externa de provider.

## Próximo
Upload privado de logos/assets, metadados, acesso isolado e lifecycle/delete/retenção;
depois seleção explícita da versão do Brand Kit e aplicação ao pipeline IA/policy.
Nenhuma geração de imagem, upload real, credencial, migration real, deploy, job ou custo
externo ocorreu. Não houve revisão de segurança independente.
