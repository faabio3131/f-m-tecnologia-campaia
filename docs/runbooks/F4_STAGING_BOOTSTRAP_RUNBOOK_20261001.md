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

Copiar somente valores não secretos para um tfvars local ignorado pelo Git:

```bash
cp infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
```

Preencher:
- `project_id`;
- `environment = "staging"`;
- `state_bucket_name`.

Executar o primeiro bootstrap com state local somente até o bucket remoto existir:

```bash
terraform -chdir=infra/bootstrap init -backend=false
terraform -chdir=infra/bootstrap plan -out=bootstrap.plan
terraform -chdir=infra/bootstrap apply bootstrap.plan
terraform -chdir=infra/bootstrap output
```

Imediatamente após o bucket existir, migrar o próprio state do bootstrap para GCS:

```bash
terraform -chdir=infra/bootstrap init -migrate-state -force-copy \
  -backend-config="bucket=<STATE_BUCKET>" \
  -backend-config="prefix=campaia/bootstrap/staging"
terraform -chdir=infra/bootstrap state list
```

Não prosseguir para a foundation se a migração do state do bootstrap falhar. O arquivo local `terraform.tfstate` deixa de ser a fonte de verdade após a migração.

Evidência obrigatória:
- bucket de state criado;
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
- `GCP_VPC_CONNECTOR`;
- `CAMPAIA_DATABASE_URL_SECRET`;
- `CAMPAIA_VAULT_KMS_KEY_NAME`;
- `NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID`;
- `NEXT_PUBLIC_IDENTITY_PLATFORM_PUBLIC_API`.

O OIDC Terraform aceita apenas repo canônico + `main` + Environment `staging`.

## 8. Identity Platform/origens

Antes da jornada real:
- registrar origem Web real do staging;
- registrar redirect URI aplicável;
- validar `FIREBASE_PROJECT_ID`;
- nunca usar fixture/test identity mode.

Custom domain/DNS/TLS, se adotado, deve ser configurado no ambiente e repetido na allowlist/origens do IdP.

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
