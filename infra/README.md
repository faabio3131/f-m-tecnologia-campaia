# CampaIA F4 — Google Cloud foundation

This directory codifies the F4 target approved by D-08: Google Cloud in
`southamerica-east1`, with one isolated project per cloud environment.

## What is code-owned here

- Artifact Registry for immutable backend/web container images.
- Private VPC + Cloud Run Direct VPC egress through a dedicated /26 subnet; no always-on connector VMs.
- Cloud SQL PostgreSQL 16, private IP only, encrypted connections, PITR and managed backups.
- Secret Manager secret containers; **secret values are never Terraform literals**.
- Cloud KMS key ring + symmetric key with 90-day primary-version rotation.
- Cloud Storage assets bucket, uniform access and public access prevention.
- Pub/Sub domain-event topic.
- Dedicated backend and web runtime service accounts.
- Least-privilege grants for KMS, Secret Manager, Storage and Pub/Sub.
- Bootstrap stack for GCS Terraform state and GitHub OIDC / Workload Identity Federation.

Cloud Run is the chosen container runtime for CampaIA. Runtime services are deployed by
the release workflow only *after* the migration job succeeds, avoiding a new revision
starting against an old schema.

## Environment isolation

Staging and production use separate GCP projects, state buckets, service accounts,
databases, KMS keys and Secret Manager namespaces. Tenant configuration is never encoded
as Terraform or environment-specific application code.

## Bootstrap (external infrastructure step)

1. Create/choose the GCP project, attach billing and authenticate a human platform admin.
2. Apply `infra/bootstrap` with local state. This creates only the remote-state bucket,
   GitHub OIDC trust and deploy service account.
3. Configure the foundation remote backend:

   `terraform -chdir=infra/terraform init -backend-config="bucket=<state-bucket>" -backend-config="prefix=campaia/<environment>"`

4. Apply `infra/terraform` with the matching tfvars.
5. Run `infra/scripts/configure-platform-secrets.sh` once to create/update the DB user
   and add the database DSN as a Secret Manager version.
6. Configure GitHub Environment variables from Terraform/bootstrap outputs:
   `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`,
   `GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_BACKEND_SERVICE_ACCOUNT`,
   `GCP_WEB_SERVICE_ACCOUNT`, `GCP_VPC_NETWORK`, `GCP_VPC_SUBNET`,
   `GCP_CLOUD_RUN_MIN_INSTANCES`, `GCP_CLOUD_RUN_MAX_INSTANCES`, `CAMPAIA_DATABASE_URL_SECRET`,
   `CAMPAIA_VAULT_KMS_KEY_NAME`.
7. Configure public Identity Platform values for the Web environment before homologation.
8. Invoke the deployment workflow. GitHub Environment approval is an external gate.

## Secrets

Production/staging never use `CAMPAIA_VAULT_KEY`. Tenant provider credentials use
per-record envelope encryption: a fresh DEK encrypts the payload locally and Cloud KMS
wraps only that DEK. KMS primary-key rotation affects new records without invalidating
old records; old key versions must remain enabled until retention/rewrap policy allows
retirement.

The database password is generated outside Terraform state by the configuration script,
then only the DSN secret version is placed in Secret Manager.

## Rollback

Application rollback moves Cloud Run traffic to a known previous revision using
`infra/scripts/rollback-cloud-run.sh`. Database rollback is intentionally not coupled to
traffic rollback; the versioned migration runner rolls back one migration only after a
compatibility decision.

For staging, set `GCP_CLOUD_RUN_MIN_INSTANCES=0` and a conservative
`GCP_CLOUD_RUN_MAX_INSTANCES` (initially 3). Cloud Run and Direct VPC egress can then
scale to zero when idle. Cloud SQL is the principal persistent compute cost; use
`infra/scripts/staging-runtime.sh start|stop|status` to open and close controlled
staging windows. Stopping staging Cloud SQL is an operational cost control and does not
replace the G4 requirement to prove a real deploy, migration, smoke and rollback.

A real staging foundation apply, rollback rehearsal, DNS/TLS delegation and restore
exercise remain external evidence required before G4/F17 can be promoted.
