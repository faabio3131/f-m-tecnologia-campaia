#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${ENVIRONMENT:?ENVIRONMENT is required}"
: "${TF_DIR:=infra/terraform}"

if [[ "${ENVIRONMENT}" != "staging" && "${ENVIRONMENT}" != "production" ]]; then
  echo "ENVIRONMENT must be staging or production" >&2
  exit 2
fi

INSTANCE_NAME="$(terraform -chdir="${TF_DIR}" output -raw cloud_sql_instance_name)"
PRIVATE_IP="$(terraform -chdir="${TF_DIR}" output -raw cloud_sql_private_ip)"
DATABASE_SECRET="$(terraform -chdir="${TF_DIR}" output -raw database_url_secret_name)"
DB_USER="${CAMPAIA_DB_USER:-campaia_app}"
DB_PASSWORD="${CAMPAIA_DB_PASSWORD:-$(openssl rand -hex 32)}"

if gcloud sql users list --project="${PROJECT_ID}" --instance="${INSTANCE_NAME}"   --format='value(name)' | grep -Fxq "${DB_USER}"; then
  gcloud sql users set-password "${DB_USER}"     --project="${PROJECT_ID}"     --instance="${INSTANCE_NAME}"     --password="${DB_PASSWORD}" >/dev/null
else
  gcloud sql users create "${DB_USER}"     --project="${PROJECT_ID}"     --instance="${INSTANCE_NAME}"     --password="${DB_PASSWORD}" >/dev/null
fi

DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${PRIVATE_IP}:5432/campaia?sslmode=require"
printf '%s' "${DATABASE_URL}" | gcloud secrets versions add "${DATABASE_SECRET}"   --project="${PROJECT_ID}"   --data-file=- >/dev/null

unset DB_PASSWORD DATABASE_URL CAMPAIA_DB_PASSWORD
echo "Database user and Secret Manager DATABASE_URL version configured for ${ENVIRONMENT}."
echo "No credential value was written to the repository or Terraform configuration."
