# EVIDÊNCIA — F4 INFRAESTRUTURA, SEGREDOS, AMBIENTES E CI/CD / G4 — 01/10/2026

**WP:** WP-F04-01  
**Fase:** F4 — Infraestrutura, Configuração, Segredos e CI/CD  
**Status da fase:** `PARTIAL`  
**Status da tranche interna/repositório:** `DONE_VERIFIED`  
**Gate G4:** `EXTERNAL_INFRASTRUCTURE` — aberto até staging real subir do zero pelo processo documentado  
**Repositório:** `faabio3131/f-m-tecnologia-campaia`  
**Branch:** `reconciliation/campaia-final-takeover`  
**PR:** #31, Draft, não mergeada  
**HEAD funcional certificado:** `c62c48302ff827c806425f59d91e5e6a8c274247`

## 1. CURRENT confirmado antes da execução

Entrada F4:
- PR #31 aberta, Draft, não mergeada e mergeable;
- HEAD de entrada: `11e3e35f2bffd255d16881d2ca8c7f02b9809bbc`;
- Backend #162 = `success`;
- Frontend #100 = `success`;
- G3 = `DONE_VERIFIED`;
- não existia `infra/`, Dockerfile nem workflow de deploy;
- runtime PostgreSQL/migrations já existiam por F3, mas não havia infraestrutura gerenciada codificada;
- Vault de tenant ainda aceitava uma única Fernet root key via `CAMPAIA_VAULT_KEY`;
- nenhuma infraestrutura Google Cloud real foi assumida como existente.

A decisão primária D-08 já aprova Google Cloud e a região `southamerica-east1`. F4 não reabriu essa decisão.

## 2. Problema

O CURRENT tinha runtime de aplicação suficiente para G3, mas ainda faltava a camada operacional reproduzível exigida por F4:

- imagens de produção;
- IaC de staging/produção;
- Cloud SQL/Secret Manager/KMS/Storage/PubSub/rede/IAM modelados;
- substituição da root key permanente do Vault;
- pipeline de validação de infraestrutura;
- migration gate;
- release/rollback governados;
- secret scanning/SAST de plataforma;
- runbook de criação do staging.

Sem esses itens, qualquer servidor/ambiente dependeria de configuração artesanal e G4 não poderia sequer ser testado honestamente.

## 3. TARGET

Fechar tudo que é executável internamente no repositório para que um ambiente externo possa ser criado de forma repetível, preservando:

- Google Cloud / São Paulo;
- separação staging/production;
- PLATFORM config separada de TENANT config;
- zero segredo real no Git/Terraform;
- Cloud SQL privado;
- KMS envelope encryption;
- service accounts dedicadas e least privilege;
- GitHub OIDC sem JSON key;
- migrations antes da nova revisão;
- aprovação humana antes de qualquer deploy;
- rollback explícito;
- CI bloqueante.

## 4. Fora de escopo desta tranche

Não foram executados:

- criação de projeto GCP ou associação de billing;
- `terraform apply`;
- criação real de VPC/Cloud SQL/KMS/Secret Manager/Storage/PubSub/Artifact Registry;
- configuração real de GitHub Environments/reviewers;
- deploy de staging;
- deploy de produção;
- DNS/custom domain/TLS/redirect URI reais;
- smoke em Cloud Run real;
- rollback real;
- restore real/RPO/RTO;
- conexão real Google/Meta/WhatsApp;
- jobs de reconciliação sem workload real definido.

Esses pontos dependem de infraestrutura/credenciais/aprovação externa e não são fabricados.

## 5. Serviço de container

**Escolha técnica:** Cloud Run.

Motivos:
- alinhado à direção Google Cloud já aprovada;
- executa as imagens OCI produzidas pelo repositório;
- não introduz operação de cluster Kubernetes antes de existir necessidade;
- permite Cloud Run Jobs para migration gate;
- permite service account por serviço e acesso privado à VPC;
- é reversível: a aplicação continua containerizada e o domínio não depende de APIs do Cloud Run.

A escolha não é prova de deploy; nenhum serviço Cloud Run foi criado nesta tranche.

## 6. Containers e probes

Foram adicionados:

- `backend/Dockerfile`;
- `web/Dockerfile`;
- `.dockerignore` separados;
- execução non-root em backend e Web;
- Next.js `output: "standalone"`;
- `/health/live` para liveness sem dependência externa;
- `/health/ready` para readiness que falha quando o banco configurado está indisponível.

A F4 Platform CI não apenas constrói as imagens: ela inicia os containers de produção e executa smoke HTTP real contra backend e Web.

## 7. Persistência gerenciada codificada

`infra/terraform` modela:

- Artifact Registry;
- VPC dedicada;
- private service networking;
- sub-rede regional /26 para Cloud Run Direct VPC egress;
- Cloud SQL PostgreSQL 16;
- private IP only;
- conexão criptografada;
- SSD e autoresize;
- produção REGIONAL; staging ZONAL;
- managed backups;
- point-in-time recovery;
- retenção de transaction log;
- banco `campaia`;
- deletion protection.

O código existe e passa `terraform validate`, mas nenhum recurso real foi provisionado. Logo Cloud SQL real continua `EXTERNAL_INFRASTRUCTURE`.

## 8. Segredos — root key removida do TARGET de produção

### 8.1 Tenant Vault

Foi criado `api.kms_vault.KmsEnvelopeCredentialCipher`.

Por credencial de tenant:
1. um DEK Fernet novo é gerado;
2. o payload é cifrado localmente pelo DEK;
3. Cloud KMS cifra somente o DEK;
4. o banco armazena o envelope versionado, nunca segredo em claro;
5. o objeto de domínio continua referenciando `SecretRef`.

`CAMPAIA_VAULT_KEY` legado:
- permitido somente em `test` / `dev-local`;
- rejeitado fail-closed em staging/production;
- staging/production usam `CAMPAIA_VAULT_KMS_KEY_NAME`.

### 8.2 KMS e rotação

Terraform cria:
- key ring separado por ambiente;
- CryptoKey `tenant-credentials`;
- rotação de versão primária a cada 90 dias;
- `prevent_destroy`;
- backend recebe somente `roles/cloudkms.cryptoKeyEncrypterDecrypter` naquela chave.

Versões históricas da mesma CryptoKey devem permanecer habilitadas enquanto houver envelopes dependentes delas. Troca de CryptoKey exige rewrap governado; nunca se apaga uma versão antiga antes da migração dos envelopes.

### 8.3 Secret Manager

Terraform cria containers de segredos PLATFORM, sem valores:
- database-url;
- asaas-api-key;
- asaas-webhook-token;
- gemini-api-key.

Valores não entram no Terraform state. O script `configure-platform-secrets.sh` cria/rotaciona o usuário do banco e adiciona a DSN diretamente como nova versão do Secret Manager.

Credenciais de tenant não viram env vars nem secrets Terraform: permanecem no Vault multi-tenant cifrado por envelope KMS.

### 8.4 Auditoria de acesso

Terraform habilita Data Access audit logs para:
- Secret Manager;
- Cloud KMS;
- DATA_READ;
- DATA_WRITE.

Isso fecha a preparação de auditoria de acesso; a evidência de logs reais só existirá depois do `terraform apply` no projeto externo.

## 9. Separação de ambientes

Arquitetura operacional:
- projeto GCP dedicado por ambiente;
- state bucket Terraform dedicado;
- service accounts dedicadas;
- Cloud SQL dedicado;
- KMS/key ring dedicado;
- Secret Manager namespace dedicado;
- Storage dedicado;
- GitHub Environment correspondente.

`dev-local` permanece fora dessa infraestrutura e pode usar fixtures locais. Nenhum tenant exige projeto, deploy, env var ou código próprio.

## 10. IAM e rede

- Cloud SQL usa private IP;
- backend e migration job acessam a rede privada por Cloud Run Direct VPC egress;
- backend e Web têm service accounts diferentes;
- backend recebe acesso específico a KMS, secrets, assets e Pub/Sub;
- Web não recebe acesso aos secrets do backend;
- deployer recebe somente papéis necessários ao release modelado;
- GitHub autentica por Workload Identity Federation/OIDC, não por service-account JSON key;
- trust OIDC exige:
  - repositório canônico;
  - branch `main`;
  - GitHub Environment igual ao ambiente GCP correspondente.

A aplicação continua sendo responsável por tenancy/RBAC; IAM cloud não substitui isolamento de tenant.

## 11. Cloud Storage, Pub/Sub e jobs

F4 provisiona a fundação de Storage:
- regional;
- uniform bucket-level access;
- public access prevention;
- versioning;
- backend com `storage.objectUser`.

Também provisiona o topic de domínio Pub/Sub.

Cloud Workflows/Cloud Scheduler não foram criados sem um workload concreto. O Cronograma diz “quando necessário”; reconciliação/publicação real surgem em F9/F12. Criar workflow ocioso agora seria infraestrutura sem contrato operacional. A fundação permanece preparada para o WP que possuir a Saga/reconciliação real.

## 12. CI/CD

### F4 Platform CI

Novo workflow bloqueante:
- Terraform fmt;
- bootstrap `init -backend=false` + validate;
- foundation `init -backend=false` + validate;
- backend image build;
- backend container boot + liveness smoke;
- Web image build;
- Web container boot + HTTP smoke;
- secret scan;
- Bandit high-severity SAST.

Dependências continuam auditadas pelos pipelines existentes:
- `pip-audit`;
- `npm audit --audit-level=high`.

### Release

`cloud-run-release.yml` é apenas `workflow_dispatch`:
- usa GitHub Environment;
- usa OIDC;
- publica imagem imutável com SHA;
- executa Cloud Run migration Job;
- **migration deve terminar com sucesso antes do deploy do backend**;
- faz readiness smoke;
- build/deploy da Web;
- fixa `CAMPAIA_ALLOWED_ORIGINS` na URL Web do ambiente;
- faz smoke final.

Produção exige confirmação textual adicional no workflow e continua subordinada à autorização expressa do Diretor.

Nenhum workflow de release foi executado.

### Rollback

`cloud-run-rollback.yml` move tráfego para uma revisão conhecida.

Rollback de banco é deliberadamente separado: `migrate_postgres.py down` só pode ser usado após verificação de compatibilidade. Rollback de aplicação nunca executa rollback destrutivo de schema automaticamente.

## 13. Bootstrap repetível

`infra/bootstrap` modela:
- bucket GCS de state, versionado e não destrutível;
- Workload Identity Pool/Provider;
- deploy service account;
- trust restrito ao repo/main/GitHub Environment.

O processo completo está em:
- `infra/README.md`;
- `docs/runbooks/F4_STAGING_BOOTSTRAP_RUNBOOK_20261001.md`.

## 14. Testes e CI funcional

**HEAD funcional certificado:** `c62c48302ff827c806425f59d91e5e6a8c274247`.

### Backend #170 = `success`

- 377 testes de domínio: PASS;
- 286 testes API: PASS;
- 14 testes PostgreSQL 16: PASS;
- KMS envelope round-trip: PASS;
- ciphertext sem plaintext: PASS;
- envelope corrompido: fail-closed;
- KMS metadata incorreta: fail-closed;
- root key legado em production: rejeitado;
- root key legado em test: compatível;
- `pip-audit`: nenhuma vulnerabilidade conhecida;
- AsyncAPI: 24/24.

### Frontend #108 = `success`

- npm audit: 0 vulnerabilidades;
- lint: PASS;
- typecheck: PASS;
- contract drift: PASS;
- security boundary: PASS;
- 21 arquivos / 72 Vitest: PASS;
- production build: PASS;
- 4 smoke E2E: PASS;
- 27 E2E cross-stack: PASS.

### F4 Platform CI #4 = `success`

- Terraform format: PASS;
- bootstrap validate: PASS;
- foundation validate: PASS;
- backend Docker build: PASS;
- backend production-image boot smoke: PASS;
- Web Docker build: PASS;
- Web production-image boot smoke: PASS;
- secret scan: PASS;
- Bandit high severity: PASS.

O primeiro Platform CI detectou formatação Terraform e falhou corretamente; a formatação foi corrigida antes da certificação. O gate não foi enfraquecido.

## 15. Blockers reais para G4

G4 exige **staging real subir do zero**. Ainda faltam evidências externas:

1. projeto GCP staging real com billing/acesso;
2. apply do bootstrap;
3. remote state GCS real;
4. WIF/deployer real;
5. GitHub Environment `staging` com aprovação/reviewer;
6. apply da foundation;
7. Cloud SQL/KMS/Secret Manager/Storage/PubSub/VPC/Artifact Registry reais;
8. valores de Secret Manager inseridos fora do Git;
9. Identity Platform/origins/redirect URIs reais;
10. execução autorizada do release staging;
11. smoke do Cloud Run real;
12. domínio/DNS/TLS/redirect URIs do ambiente quando definidos;
13. ensaio real de rollback de aplicação e migration compatível;
14. evidência de backup/PITR no recurso real.

Restore real e RPO/RTO medidos continuam F17.

## 16. Status

**F4:** `PARTIAL`.  
**Tranche interna/repositório:** `DONE_VERIFIED`.  
**G4:** `EXTERNAL_INFRASTRUCTURE`.

A base necessária para provisionar e operar staging está codificada e certificada por CI. O Gate não é promovido porque não houve `terraform apply`, deploy ou staging real.

Nenhum merge, deploy, staging ou produção foi executado.


## 17. Atualização operacional — staging econômico/on-demand — 01/10/2026

Após o bootstrap real de staging ter sido criado e reconciliado sem drift, o Diretor
aprovou a estratégia de construção com custo mínimo sem empurrar G4 para a pré-estreia.

TARGET atualizado:
- remover Serverless VPC Access Connector e seu custo-base de VMs;
- usar Cloud Run Direct VPC egress em sub-rede dedicada /26;
- manter Cloud Run staging com mínimo 0 e limite inicial conservador;
- operar Cloud SQL staging por janelas explícitas de start/stop;
- manter state, IAM, KMS, Secret Manager, Storage e demais fundações persistentes;
- ligar staging nos checkpoints que exigem OAuth/webhook/publicação/migrations/smoke;
- manter G4 aberto até foundation, deploy, migrations, smoke e rollback reais.

O bootstrap externo já comprovado permanece válido. A foundation anterior de 41 recursos
foi apenas planejada e NÃO foi aplicada; ela fica `SUPERSEDED` pela variante econômica.
Nenhum Serverless VPC Access Connector chegou a ser criado.

Status:
- F4: `PARTIAL`;
- preparação interna: `DONE_VERIFIED` somente após a nova CI;
- G4: `EXTERNAL_INFRASTRUCTURE` até o staging econômico real completar o gate.


## 18. Evidência externa real — staging econômico — 01/10/2026

Após a atualização da estratégia econômica, foram executadas e verificadas as seguintes
etapas externas no projeto GCP `campaia-staging`:

- bootstrap Terraform real aplicado e reconciliado em backend GCS remoto;
- state bucket regional com public access prevention, uniform bucket-level access e versionamento;
- Workload Identity Pool/Provider e deploy service account reais;
- foundation econômica real aplicada com Direct VPC egress, sem Serverless VPC Access Connector;
- drift check da foundation: `No changes`, `TERRAFORM_EXIT_CODE=0`;
- Cloud SQL PostgreSQL 16 privado criado;
- KMS, Secret Manager, Storage, Pub/Sub, Artifact Registry, service accounts e IAM criados;
- usuário PostgreSQL `campaia_app` criado;
- secret `campaia-staging-database-url` com versão habilitada no Secret Manager;
- GitHub Environment `staging` criado com variáveis não secretas de infraestrutura;
- `identitytoolkit.googleapis.com` incorporada à foundation Terraform e aplicada;
- Identity Platform inicializado no projeto;
- Browser API key criada automaticamente pelo Firebase/Identity Platform e registrada como
  `NEXT_PUBLIC_IDENTITY_PLATFORM_PUBLIC_API` no Environment `staging`;
- OAuth client Web `CampaIA Staging Web` criado no Google Auth Platform;
- provider `google.com` do Identity Platform verificado com `enabled=true`,
  `clientId` presente e `hasClientSecret=true`;
- origem Cloud Run staging adicionada a `authorizedDomains` e verificada com
  `domainPresent=true`;
- `NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID` registrada no GitHub Environment;
- o Diretor informou que adicionou o usuário de teste do OAuth; a prova funcional desse
  usuário ocorrerá no login real do staging.

Nenhum Client Secret foi versionado no repositório, no Terraform ou em documentação.
O Client Secret foi usado somente na configuração do provider e removido da sessão shell
após a operação.

### CURRENT reconciliado

- HEAD de código antes desta atualização documental:
  `784cd8d8c1c468b65be43a19e88fa7f0ef5ba272`;
- Backend #180 = `success`;
- Frontend #118 = `success`;
- F4 Platform CI #14 = `success`;
- PR #31 continua Draft, aberta, mergeable e não mergeada;
- `main` ainda não contém o workflow de release;
- o WIF continua corretamente restrito a `refs/heads/main` + Environment correspondente.

### Blockers restantes para G4

Restam, no mínimo:

1. revisão final da PR #31 para promoção à `main`;
2. autorização expressa do Diretor para merge;
3. merge sem regressão e CI da `main` verde;
4. primeiro release real de staging via GitHub OIDC;
5. migration Job real concluído com sucesso;
6. backend `/health/ready` real = 200;
7. Web real = HTTP success;
8. login Google real do usuário de teste;
9. evidência de backup/PITR do Cloud SQL real;
10. ensaio real de rollback de revisão de aplicação;
11. hibernação controlada do Cloud SQL após a janela de homologação.

Status permanece:
- F4: `PARTIAL`;
- G4: `EXTERNAL_INFRASTRUCTURE`.

A infraestrutura base real já existe; o Gate não é promovido antes do release, smoke,
login e rollback reais.
