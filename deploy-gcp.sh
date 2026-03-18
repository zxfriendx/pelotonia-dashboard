#!/usr/bin/env bash
# Deploy Pelotonia dashboard to Cloud Run after scraper updates the DB.
# Called by pelotonia-deploy.service (chained after scraper).
set -euo pipefail

PROJECT="pelotonia-dashboard"
REGION="us-central1"
IMAGE="us-central1-docker.pkg.dev/${PROJECT}/pelotonia/dashboard:latest"
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")" && pwd)}"

# Add gcloud to PATH if installed in home directory
[[ -d "$HOME/google-cloud-sdk/bin" ]] && export PATH="$HOME/google-cloud-sdk/bin:$PATH"

echo "[$(date -Iseconds)] Starting GCP deploy..."

cd "$REPO_DIR"

# Build and push via Cloud Build
echo "[$(date -Iseconds)] Building image..."
gcloud builds submit \
  --tag "$IMAGE" \
  --project "$PROJECT" \
  --quiet

# Deploy to Cloud Run
echo "[$(date -Iseconds)] Deploying to Cloud Run..."
gcloud run deploy pelotonia-dashboard \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT" \
  --allow-unauthenticated \
  --memory 256Mi \
  --max-instances 2 \
  --port 8080 \
  --quiet

echo "[$(date -Iseconds)] Deploy complete."
