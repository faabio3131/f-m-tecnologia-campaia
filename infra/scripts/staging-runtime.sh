#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
: "${PROJECT_ID:?PROJECT_ID is required}"

ENVIRONMENT="${ENVIRONMENT:-staging}"
INSTANCE="${CLOUD_SQL_INSTANCE:-campaia-${ENVIRONMENT}-pg}"

if [[ "${ENVIRONMENT}" != "staging" ]]; then
  echo "This cost-control script is restricted to staging." >&2
  exit 2
fi

if [[ "${ACTION}" != "start" && "${ACTION}" != "stop" && "${ACTION}" != "status" ]]; then
  echo "Usage: PROJECT_ID=<project> ENVIRONMENT=staging $0 {start|stop|status}" >&2
  exit 2
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI was not found in PATH." >&2
  exit 3
fi

ACTIVE_PROJECT="$(gcloud config get-value project 2>/dev/null)"
if [[ "${ACTIVE_PROJECT}" != "${PROJECT_ID}" ]]; then
  echo "Active gcloud project is '${ACTIVE_PROJECT}', expected '${PROJECT_ID}'." >&2
  exit 4
fi

show_status() {
  gcloud sql instances describe "${INSTANCE}" \
    --project="${PROJECT_ID}" \
    --format='table(name,state,settings.activationPolicy,region,settings.tier)'
}

case "${ACTION}" in
  status)
    show_status
    ;;
  start)
    echo "Starting staging Cloud SQL instance ${INSTANCE}..."
    gcloud sql instances patch "${INSTANCE}" \
      --project="${PROJECT_ID}" \
      --activation-policy=ALWAYS \
      --quiet
    show_status
    ;;
  stop)
    echo "Stopping staging Cloud SQL instance ${INSTANCE}..."
    gcloud sql instances patch "${INSTANCE}" \
      --project="${PROJECT_ID}" \
      --activation-policy=NEVER \
      --quiet
    show_status
    ;;
esac
