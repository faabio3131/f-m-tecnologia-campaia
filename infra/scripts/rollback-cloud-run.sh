#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${REGION:=southamerica-east1}"
: "${SERVICE:?SERVICE is required}"
: "${REVISION:?REVISION is required}"

gcloud run services update-traffic "${SERVICE}"   --project="${PROJECT_ID}"   --region="${REGION}"   --to-revisions="${REVISION}=100"

echo "Traffic rolled back to ${REVISION}. Database rollback is intentionally separate."
echo "Use backend/scripts/migrate_postgres.py down only after compatibility review."
