# CampaIA — RUNBOOK F4 — SUBIDA DO STAGING DO ZERO

**Data:** 01/10/2026  
**Gate relacionado:** G4  
**Status:** `EXTERNAL_INFRASTRUCTURE` até execução real  
**Região aprovada:** `southamerica-east1`  
**Runtime escolhido:** Cloud Run  
**Princípio:** nenhum segredo real no Git, tfvars ou output de chat.

Este runbook é a sequência reproduzível para provar G4. Não executar produção com este procedimento sem o gate correspondente e autorização expressa do Diretor.

## 1. Pré-condições externas

Confirmar:
- projeto GCP dedicado ao staging;
- billing ativo;
- operador autenticado com autoridade para bootstrap;
- nome globalmente único para bucket de Terraform state;
- GitHub repo canônico acessível;
- autorização expressa para criar infraestrutura/deploy staging.

Se qualquer item faltar, parar com `EXTERNAL_INFRASTRUCTURE` ou `EXTERNAL_APPROVAL`.

## 2. Bootstrap de state e OIDC

O bucket do backend é a única exceção de bootstrap: ele precisa existir antes de o Terraform poder usar GCS como backend. A criação deve ocorrer pelo script versionado e auditável, nunca por configuração manual escondida.

Preparar somente valores não secretos em shell:

```bash
export PROJECT_ID="campaia-staging"
export ENVIRONMENT="staging"
export REGION="southamerica-east1"
export STATE_BUCKET="<STATE_BUCKET_GLOBALMENTE_UNICO>"
```

Antes de qualquer mutação, validar que a VM/sessão atual possui Terraform executável:

```bash
terraform version
```

Em Cloud Shell, uma VM recriada pode não preservar pacotes instalados no sistema; se o comando falhar, reinstalar/reativar o Terraform antes de prosseguir.

Após autorização explícita para criar o primeiro recurso de staging, executar:

```bash
infra/scripts/bootstrap-terraform-backend.sh
```

O script:
- habilita as APIs mínimas de controle necessárias ao bootstrap (`serviceusage.googleapis.com`, `cloudresourcemanager.googleapis.com` e `storage.googleapis.com`);
- cria o bucket regional com uniform bucket-level access;
- aplica public access prevention e versionamento;
- inicializa o backend GCS em `campaia/bootstrap/<environment>`;
- importa o bucket para o próprio state Terraform remoto.

Depois criar um tfvars local ignorado pelo Git:

```bash
cp infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
```

Preencher:
- `project_id`;
- `environment = "staging"`;
- `state_bucket_name`.

Planejar o restante do bootstrap antes de qualquer apply:

```bash
terraform -chdir=infra/bootstrap plan -var-file=terraform.tfvars -out=bootstrap.plan
terraform -chdir=infra/bootstrap show -no-color bootstrap.plan
```

Somente após revisão e aprovação do plan:

```bash
terraform -chdir=infra/bootstrap apply bootstrap.plan
terraform -chdir=infra/bootstrap output
terraform -chdir=infra/bootstrap state list
```

Se o apply falhar depois de criar apenas parte dos recursos, não reutilizar o plan salvo. Primeiro reconciliar o state real, corrigir a causa raiz e gerar um novo `terraform plan` antes de qualquer nova tentativa de apply.

Evidência obrigatória:
- bucket de state criado e importado para o backend GCS;
- state do bootstrap presente no backend GCS;
- WIF provider criado;
- deployer service account criada;
- nenhum JSON key gerado.

## 3. Configurar remote state da foundation

```bash
terraform -chdir=infra/terraform init \
  -backend-config="bucket=<STATE_BUCKET>" \
  -backend-config="prefix=campaia/staging"
```

Copiar:

```bash
cp infra/terraform/staging.tfvars.example infra/terraform/staging.tfvars
```

Preencher somente IDs/config não secretos.

## 4. Plan antes de apply

```bash
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -var-file=staging.tfvars -out=staging.plan
```

Revisar no plan:
- região `southamerica-east1`;
- Cloud SQL sem IPv4 público;
- deletion protection;
- backups/PITR;
- KMS;
- Secret Manager sem secret values;
- Storage sem acesso público;
- service accounts separadas;
- IAM sem grants tenant-specific.

Salvar a saída do plan como evidência operacional; não versionar plan binário se contiver metadados sensíveis.

## 5. Apply autorizado

Somente após aprovação para staging:

```bash
terraform -chdir=infra/terraform apply staging.plan
```

Coletar outputs não secretos.

## 6. Inicializar DB secret sem Terraform state

Em shell seguro:

```bash
export PROJECT_ID="<staging-project>"
export ENVIRONMENT="staging"
infra/scripts/configure-platform-secrets.sh
unset PROJECT_ID ENVIRONMENT
```

Não capturar password/DSN em logs, tickets ou documentação.

Adicionar outras integrações externas como versões de Secret Manager somente quando seus WPs/credenciais existirem.

## 7. Configurar GitHub Environment staging

Criar/proteger o Environment `staging` e exigir reviewer humano.

Cadastrar variáveis não secretas:
- `GCP_PROJECT_ID`;
- `GCP_REGION=southamerica-east1`;
- `GCP_WORKLOAD_IDENTITY_PROVIDER`;
- `GCP_DEPLOY_SERVICE_ACCOUNT`;
- `GCP_BACKEND_SERVICE_ACCOUNT`;
- `GCP_WEB_SERVICE_ACCOUNT`;
- `GCP_VPC_NETWORK`;
- `GCP_VPC_SUBNET`;
- `GCP_CLOUD_RUN_MIN_INSTANCES=0`;
- `GCP_CLOUD_RUN_MAX_INSTANCES=3`;
- `CAMPAIA_DATABASE_URL_SECRET`;
- `CAMPAIA_VAULT_KMS_KEY_NAME`;
- `NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID`;
- `NEXT_PUBLIC_IDENTITY_PLATFORM_PUBLIC_API`.

O OIDC Terraform aceita apenas repo canônico + `main` + Environment `staging`.

## 8. Identity Platform/origens

A API `identitytoolkit.googleapis.com` faz parte da foundation gerenciada por Terraform.
A inicialização do Identity Platform é uma operação externa separada e de criação única;
não deve ser confundida com apenas habilitar a API. Antes da jornada real:

- registrar origem Web real do staging;
- registrar redirect URI aplicável;
- validar `FIREBASE_PROJECT_ID`;
- nunca usar fixture/test identity mode.

Custom domain/DNS/TLS, se adotado, deve ser configurado no ambiente e repetido na allowlist/origens do IdP.

## 8.1. Operação econômica do staging

O staging usa Cloud Run Direct VPC egress em uma sub-rede /26 e não provisiona
Serverless VPC Access Connector. Durante construção:

- Cloud Run deve permanecer com mínimo 0;
- o banco Cloud SQL deve ficar ligado somente durante janelas de integração/homologação;
- antes de release/migrations reais, abrir a janela com:

```bash
PROJECT_ID=campaia-staging ENVIRONMENT=staging infra/scripts/staging-runtime.sh start
```

- após concluir testes e coletar evidências, fechar a janela com:

```bash
PROJECT_ID=campaia-staging ENVIRONMENT=staging infra/scripts/staging-runtime.sh stop
```

- consultar a qualquer momento:

```bash
PROJECT_ID=campaia-staging ENVIRONMENT=staging infra/scripts/staging-runtime.sh status
```

Parar Cloud SQL suspende o compute da instância, mas não elimina cobrança residual de
armazenamento/IP. Produção não pode usar este script.

## 9. Release staging

No GitHub Actions:
- escolher **CAMPAIA Cloud Run Release**;
- `environment = staging`;
- aprovação do GitHub Environment;
- não usar confirmação de produção.

O workflow deve:
1. autenticar por OIDC;
2. build/push backend;
3. executar migrations via Cloud Run Job;
4. abortar se migrations falharem;
5. deploy backend;
6. readiness smoke;
7. build/push Web apontando para backend do staging;
8. deploy Web;
9. atualizar `CAMPAIA_ALLOWED_ORIGINS`;
10. smoke final.

## 10. Evidências para fechar G4

Coletar sem segredo:
- IDs/URLs dos recursos;
- Terraform plan/apply success;
- migration Job success;
- backend `/health/ready` = 200;
- Web = HTTP success;
- imagens identificadas por commit SHA;
- Cloud SQL private IP only;
- KMS/Secret Manager access audit logs existentes;
- backup/PITR configurados;
- CI do commit implantado verde.

## 11. Ensaio de rollback

Escolher uma revisão anterior conhecida em staging e executar o workflow **CAMPAIA Cloud Run Rollback**.

Confirmar:
- tráfego 100% na revisão escolhida;
- serviço volta saudável;
- nenhuma migration é revertida automaticamente.

Migration `down` só é ensaiada em caso especificamente compatível e controlado.

## 12. Critério G4

G4 só pode sair de `EXTERNAL_INFRASTRUCTURE` para `DONE_VERIFIED` quando:
- staging tiver sido criado a partir desse processo;
- não houver configuração manual não documentada por servidor;
- migration/deploy/rollback tiverem evidência reproduzível;
- segredos estiverem fora do repo;
- nenhum blocker crítico estiver escondido.

Até lá, Terraform/CI verdes são preparação certificada, não homologação de staging.
