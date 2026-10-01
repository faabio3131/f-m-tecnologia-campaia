#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${ENVIRONMENT:?ENVIRONMENT is required}"
: "${REGION:?REGION is required}"
: "${STATE_BUCKET:?STATE_BUCKET is required}"

if [[ "${ENVIRONMENT}" != "staging" && "${ENVIRONMENT}" != "production" ]]; then
  echo "ENVIRONMENT must be staging or production." >&2
  exit 2
fi

if [[ "${REGION}" != "southamerica-east1" ]]; then
  echo "REGION must be southamerica-east1 for the current approved CampaIA baseline." >&2
  exit 2
fi

TERRAFORM_BIN="${TERRAFORM_BIN:-terraform}"
BACKEND_PREFIX="campaia/bootstrap/${ENVIRONMENT}"
BUCKET_URI="gs://${STATE_BUCKET}"

if [[ "${TERRAFORM_BIN}" == */* ]]; then
  if [[ ! -x "${TERRAFORM_BIN}" ]]; then
    echo "Terraform executable '${TERRAFORM_BIN}' does not exist or is not executable." >&2
    exit 5
  fi
else
  RESOLVED_TERRAFORM_BIN="$(command -v "${TERRAFORM_BIN}" || true)"
  if [[ -z "${RESOLVED_TERRAFORM_BIN}" ]]; then
    echo "Terraform executable '${TERRAFORM_BIN}' was not found in PATH." >&2
    exit 5
  fi
  TERRAFORM_BIN="${RESOLVED_TERRAFORM_BIN}"
fi

if ! "${TERRAFORM_BIN}" version >/dev/null 2>&1; then
  echo "Terraform executable '${TERRAFORM_BIN}' is present but did not run successfully." >&2
  exit 5
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI was not found in PATH." >&2
  exit 6
fi

echo "Project: ${PROJECT_ID}"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "State bucket: ${STATE_BUCKET}"

ACTIVE_PROJECT="$(gcloud config get-value project 2>/dev/null)"
if [[ "${ACTIVE_PROJECT}" != "${PROJECT_ID}" ]]; then
  echo "Active gcloud project is '${ACTIVE_PROJECT}', expected '${PROJECT_ID}'." >&2
  exit 3
fi

BILLING_ENABLED="$(gcloud billing projects describe "${PROJECT_ID}" --format='value(billingEnabled)')"
if [[ "${BILLING_ENABLED}" != "True" && "${BILLING_ENABLED}" != "true" ]]; then
  echo "Billing is not enabled for ${PROJECT_ID}." >&2
  exit 4
fi

gcloud services enable storage.googleapis.com --project="${PROJECT_ID}" --quiet

if gcloud storage buckets describe "${BUCKET_URI}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "State bucket already exists and is accessible; reusing it."
else
  gcloud storage buckets create "${BUCKET_URI}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
fi

gcloud storage buckets update "${BUCKET_URI}" --public-access-prevention
gcloud storage buckets update "${BUCKET_URI}" --versioning

"${TERRAFORM_BIN}" -chdir=infra/bootstrap init -reconfigure \
  -backend-config="bucket=${STATE_BUCKET}" \
  -backend-config="prefix=${BACKEND_PREFIX}"

if ! "${TERRAFORM_BIN}" -chdir=infra/bootstrap state show google_storage_bucket.terraform_state >/dev/null 2>&1; then
  "${TERRAFORM_BIN}" -chdir=infra/bootstrap import \
    -var="project_id=${PROJECT_ID}" \
    -var="region=${REGION}" \
    -var="environment=${ENVIRONMENT}" \
    -var="state_bucket_name=${STATE_BUCKET}" \
    google_storage_bucket.terraform_state "${STATE_BUCKET}"
fi

echo "Bootstrap backend is ready and the state bucket is Terraform-managed."
"${TERRAFORM_BIN}" -chdir=infra/bootstrap state list
