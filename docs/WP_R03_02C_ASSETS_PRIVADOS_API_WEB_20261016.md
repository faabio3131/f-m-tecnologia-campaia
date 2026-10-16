# WP-R03-02C — Assets privados API/Web (16/10/2026)

## CURRENT
main@45a1ad6fd838d579ad7f1b094a13014eacefb550. PR #66:
HEAD 5266f4cfc4f682d535b0b9759e9b7db41073f679, Backend 38845017144,
Frontend 38845017224 e F4 38845017201 verdes; pós-merge Backend 38845209623,
Frontend 38845209667 e F4 38845209676 verdes. PR #65 e Brand Kit textual preservados.

Faltava ligar transporte + decoder à persistência e ao usuário. Este WP implementa
essa ligação em fonte; não ativa bucket, credenciais, SQL ou rollout real.

## Fluxo e autoridade
GET /brand-profiles/{id}/assets lista página de 50 e capacidade efetiva.
POST no mesmo caminho recebe bytes (application/octet-stream), kind LOGO/REFERENCE
explícito e Idempotency-Key. CAMPAIGN_VIEW consulta; BRAND_MANAGE envia/confere/remove.
Profile/tenant/principal e CSRF são conferidos antes do body, decoder ou credencial.
Não aceita tenant_id, bucket, caminho, URL ou generation do cliente.

Body 5 MiB, timeout de leitura 15s, dois slots por processo, rate 30/h por tenant
(compartilhado entre workers em PostgreSQL; fallback SQLite/test local em memória).
Normalizer restrito da PR #66 é executado fora do event loop.

F3 grava reserva/manifesto imutável/contexto ator+unidade+perfil+hash da entrada+tipo,
quota e intenção antes de qualquer upload. Quota operacional vem de configuração
explícita, vale por organização e soma pendentes/prontos/exclusão incerta. Nenhuma
nova franquia comercial por plano. Limite de bytes ativos não é teto de custo cloud:
versioning/soft delete/retention e tráfego podem continuar gerando custo real.

Namespace congela hash do bucket; trocar configuração não migra silenciosamente o
arquivo para outro storage. Somente a primeira claim faz POST externo; respostas
perdidas/crash/5xx mantêm reserva e retries só observam por GET. 404 sozinho não
libera reserva de upload nem permite novo POST. READY exige metadados verificados.

GET /.../assets/{assetId}/content exige arquivo READY e autoridade atual. Geração fixada,
checksum dos bytes, Cache-Control private/no-store, nosniff e CSP restritiva. Reconfere
tombstone após leitura. URL é relativa/autenticada; sem signed URL ou endereço público.

DELETE /.../assets/{assetId} grava tombstone antes do efeito. Geração e precondição
vêm do servidor; DELETE único, recuperação só GET. Quota só é liberada após ausência
da geração conhecida. Arquivo pendente de upload exige conferência antes da remoção.
DELETED significa acesso removido/geração não observada, não apagamento permanente
nem expiração de retenção. Metadata é preservada; regras jurídicas finais são F16.

POST /.../assets/{assetId}/reconcile requer BRAND_MANAGE/CSRF/nonce, faz somente GET
externo e finalização idempotente da metadata. Não dá ao cliente autoridade para
declarar upload/exclusão concluídos.

## Persistência e Web
Migração 008 somente fonte/CI: brand_assets com guard de tenant, manifesto/contexto
imutáveis, generation escrita uma vez e transições legais. Nenhuma migration real.
Commit/audit são atômicos; falha após efeito externo preserva fence para recuperação.

Painel sob demanda por Brand Kit: upload binário com nonce/file estáveis em erro de
rede, estados pendentes honestos, preview privado, paginação e confirmação de remoção.
Permissões escondem mutações; backend continua autoridade. Troca de tenant remonta a
página. Imagem só aparece após READY; nunca um preview local que finja upload concluído.
Cliente HTTP central preserva CSRF, cookies, 401 e timeout para binário.

## Testes e limites de certificação
Testes API/SQLite: RBAC/cross-tenant antes do decoder, replay/contexto/nonce,
concorrência/quota, restart, resposta perdida, crash pré-dispatch, falha de commit,
tombstone, DELETE incerto sem repetição, storage namespace e corrupção.
PostgreSQL dedicado: persistência/fence/quota entre instâncias, concorrência, guards
de tenant/metadata/generation/FSM e up/down/up da migration.
Web: permissão, upload binário, nonce em incerteza, pending sem imagem, remoção e página.
E2E com sessão/cookie/CSRF, API + SQLite + decoder + Next reais; cloud bytes usam
TestOnlyAssetStorage explícito do harness, rotulado SIMULATOR. Nunca fallback automático.
CI completa do HEAD exato e pós-merge devem ser registradas após os workflows.

Não certifica bucket/IAM/ADC/Cloud Run real, gasto, retenção final, pentest ou G6.
Antes da ativação real: migration/rollout/configuração autorizados, orçamento explícito,
credencial já existente e homologação GCS/runtimes. Cloud SQL permanece desligado.
Próximo delta: aplicação explícita da versão/assets selecionados ao pipeline; não
seleciona automaticamente o primeiro Brand Kit/logo nem muda campanha já criada.
F6 permanece PARTIAL até a prova externa e integração ao pipeline.

## Correção necessária revelada pelo E2E persistente
O harness passou de memória a SQLite para provar metadata durável. O cenário K então
revelou que PersistentSessionStore.switch_principal tentava mudar tenant_id por UPDATE,
corretamente bloqueado pelo guard F3 (403). Não se relaxou o guard nem a expectativa.
A sessão só muda para um vínculo capturado da mesma identidade; troca de tenant faz
delete+insert explícito na mesma transação, preservando cookie/CSRF/subject/expiração.
Lock por session_id serializa switch com logout/revogação; falha no INSERT restaura
a linha anterior. Testes SQLite e PostgreSQL provam rollback, alvo forjado negado,
guard geral intacto e ausência de ressurreição na concorrência com revogação.

A asserção de isolamento da sessão testa RecordTable: a migration 002 já exclui
sessions do trigger SQL por serem identidade pré-tenant. Não se adicionou nem removeu
guard SQL de sessão. A suite também revelou teste de fechamento financeiro dependente
de timing: uma segunda réplica pode corretamente receber BILLING_DISPATCH_PENDING
enquanto a primeira ainda emite. O teste agora força essa janela com eventos, exige
503 específico, libera o único dispatch e exige convergência ao MESMO invoice (um POST).
Nenhuma regra de cobrança foi alterada nem houve rerun para esconder falha.
