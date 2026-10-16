# WP-R03-02A — Transporte privado de assets (16/10/2026)

## CURRENT confirmado
Repositório faabio3131/f-m-tecnologia-campaia, main@c8590ee00b3e16b45c3990fcd850760e59271ca0.
Nenhuma PR aberta antes desta etapa. WP-R03-01 integrado na PR #64; CI da PR
(38842133292, 38842133367, 38842133413) e pós-merge (38842353104, 38842353200,
38842353361) verdes. Edição textual, concorrência e histórico preservados.

A infraestrutura existente já declara bucket privado, uniform bucket-level access,
public access prevention enforced, versioning, prevent_destroy e storage.objectUser
para o backend. Não há lacuna que justifique reprovisionamento. Não houve acesso ao
bucket, credenciais ou SQL real nesta etapa.

## Delta implementado
Contrato interno PrivateAssetStorage, manifestos imutáveis com tamanho/SHA-256/checksum
MD5 de transporte e identidade do objeto derivada de tenant + perfil + UUID de asset.
IDs de tenant/perfil são hashes no caminho; não há filename, URL ou caminho escolhido
pelo navegador. MD5 não é usado como identidade de segurança.

Adaptador GCS JSON por httpx, host HTTPS fixo, sem redirects/proxies do ambiente.
Upload multipart com metadados e bytes, ifGenerationMatch=0, sem ACL de objeto.
Confere bucket, nome, tipo, tamanho, SHA-256 esperado nos tags, MD5, cache e geração.
Leitura confere metadados e bytes da geração exata. DELETE usa geração + precondição.
Cada método de mutação emite uma única requisição; timeout/5xx/429 não repetem escrita.
Recuperação usa GET de um manifesto previamente persistido pelo futuro chamador.

Respostas limitadas em bytes (metadados 64 KiB, mídia no tamanho esperado), sem
descompressão de conteúdo codificado. Token/ADC somente na operação habilitada;
construção/import não descobrem credenciais. Erros não expõem corpo, token ou exceção
do provedor. O comportamento padrão é DisabledAssetStorage.

Configuração fonte: CAMPAIA_ASSET_STORAGE_ENABLED=true, CAMPAIA_ASSET_BUCKET com o
bucket existente e CAMPAIA_ASSET_MAX_ACTIVE_BYTES positivo explícito. O limite configura
o futuro orçamento operacional; esta etapa só limita o tamanho de cada objeto.
**Quota acumulada, concorrência e autorização não são fornecidas pelo adaptador.**
Nenhuma variável foi definida em ambiente real.

## Limites e próximo delta
F6 continua PARTIAL. Este é transporte interno, não fluxo de upload certificado.
A assinatura PNG é apenas um invariante de transporte, NÃO validação de imagem.
Antes de conectar qualquer endpoint: decoder isolado/normalização, RBAC/isolation
antes de ADC, manifesto/fence transacional, quota atômica de ativos pendentes/prontos,
replay/contexto do ator, leitura autenticada e tombstone antes de DELETE. Depois,
contrato API/Web e testes PostgreSQL/E2E. Sem esses controles não ativar o adaptador.

Ausência 404 é somente uma observação, não prova de que upload não ocorreu nem licença
para redispatch. Sucesso DELETE não significa apagamento permanente: versioning,
soft delete e retenção do bucket podem manter bytes. Não foi inventado prazo jurídico
ou alterada política do bucket. Não há URL pública ou assinatura de acesso nesta etapa.

## Verificação
Novos testes unitários cobrem transporte com httpx.MockTransport (sem rede real):
isolamento de identidade, replay por observação após resposta perdida, precondições,
conflito/timeout/status não confiável, ausência de redirects, corrupção/substituição,
limites de resposta, credenciais lazy e ausência de ADC quando desabilitado.
Suítes completas Backend/PostgreSQL/Frontend/F4 executadas na CI da PR; evidência
definitiva no HEAD e pós-merge deve ser registrada após aprovação dos workflows.

A validação simulada não certifica armazenamento real, segurança final F16, retenção,
margem de custo ou G6. Nenhum deploy/migration/credencial/gasto/ativação foi executado.

## Referências primárias conferidas em 16/10/2026
- https://docs.cloud.google.com/storage/docs/json_api/v1/objects/insert
- https://docs.cloud.google.com/storage/docs/json_api/v1/objects/get
- https://docs.cloud.google.com/storage/docs/json_api/v1/objects/delete
- https://google-auth.readthedocs.io/en/latest/reference/google.auth.html
