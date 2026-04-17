#!/usr/bin/env bash
# Deploy Pelotonia dashboard STAGING to Cloud Run (AlloyDB backend).
# Uses a separate service name so production is unaffected.
set -euo pipefail

PROJECT="pelotonia-dashboard"
REGION="us-central1"
SERVICE="pelotonia-dashboard-staging"
IMAGE="us-central1-docker.pkg.dev/${PROJECT}/pelotonia/dashboard-staging:latest"
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")" && pwd)}"

[[ -d "$HOME/google-cloud-sdk/bin" ]] && export PATH="$HOME/google-cloud-sdk/bin:$PATH"

echo "[$(date -Iseconds)] Starting staging deploy..."

cd "$REPO_DIR"

echo "[$(date -Iseconds)] Building image..."
gcloud builds submit \
  --tag "$IMAGE" \
  --project "$PROJECT" \
  --quiet

echo "[$(date -Iseconds)] Deploying to Cloud Run (staging)..."
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT" \
  --allow-unauthenticated \
  --memory 256Mi \
  --max-instances 2 \
  --port 8080 \
  --set-env-vars="ALLOYDB_DSN=${ALLOYDB_DSN:-}" \
  --quiet

echo "[$(date -Iseconds)] Staging deploy complete."
