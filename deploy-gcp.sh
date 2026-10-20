#!/usr/bin/env bash
# Build the container (frontend + Flask app + baked-in SQLite DB) with Cloud Build
# and deploy it to Cloud Run. Run it after a scrape has committed, so the image
# carries fresh data (cron chains scrape && deploy for exactly this reason).
#
# Configuration (environment, or a .env file next to this script):
#   GCP_PROJECT            GCP project ID           (default: pelotonia-dashboard)
#   GCP_REGION             Cloud Run region         (default: us-central1)
#   PELOTONIA_GCP_ACCOUNT  gcloud account to deploy as (optional, recommended)
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")" && pwd)}"

# Pick up deploy settings from .env when run from cron, which has no shell profile.
if [[ -f "$REPO_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$REPO_DIR/.env"
  set +a
fi

PROJECT="${GCP_PROJECT:-pelotonia-dashboard}"
REGION="${GCP_REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/pelotonia/dashboard:latest"

# Add gcloud to PATH if installed in home directory
[[ -d "$HOME/google-cloud-sdk/bin" ]] && export PATH="$HOME/google-cloud-sdk/bin:$PATH"

# Pin the gcloud identity when one is configured. Without it the script inherits
# whatever gcloud configuration was last activated on the machine; on 2026-09-07
# a switch to another project's configuration made every deploy fail with
# "user is forbidden from accessing the bucket" and froze the live site for a day.
if [[ -n "${PELOTONIA_GCP_ACCOUNT:-}" ]]; then
  export CLOUDSDK_CORE_ACCOUNT="$PELOTONIA_GCP_ACCOUNT"
fi

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
