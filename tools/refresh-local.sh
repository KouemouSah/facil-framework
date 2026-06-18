#!/usr/bin/env bash
# Phase C — refresh the local stack from the latest GHCR images (no manual build).
#
# Prod/dev images are built ONLY by CI (.github/workflows/release-images.yml) and
# pushed to GHCR. This script pulls them and (re)creates the backend + frontend
# containers on top of the generated compose, leaving the third-party services
# (postgres/redis/minio/openbao…) untouched.
#
# Usage:
#   tools/refresh-local.sh                 # owner=kouemousah, tag=develop
#   FACIL_IMAGE_TAG=latest tools/refresh-local.sh
#   FACIL_IMAGE_OWNER=acme FACIL_IMAGE_TAG=sha-<...> tools/refresh-local.sh
set -euo pipefail

cd "$(dirname "$0")/.."

OWNER="${FACIL_IMAGE_OWNER:-kouemousah}"
TAG="${FACIL_IMAGE_TAG:-develop}"
export FACIL_IMAGE_OWNER="$OWNER" FACIL_IMAGE_TAG="$TAG"

BACKEND_IMG="ghcr.io/$OWNER/facil-backend:$TAG"
WEB_IMG="ghcr.io/$OWNER/facil-web:$TAG"
COMPOSE=(docker compose -f docker-compose.local.yml -f deploy/compose.images.yml --profile web)

echo "→ Refreshing from GHCR (owner=$OWNER, tag=$TAG)"

# GHCR packages are private by default: log in with the gh token if a pull fails.
if ! docker pull "$BACKEND_IMG" >/dev/null 2>&1; then
  echo "  ghcr.io auth needed — logging in via gh…"
  if command -v gh >/dev/null 2>&1; then
    gh auth token | docker login ghcr.io -u "$(gh api user --jq .login)" --password-stdin
  else
    echo "  ! 'gh' not found. Run: docker login ghcr.io   (PAT with read:packages)" >&2
    exit 1
  fi
fi

echo "→ Pulling images"
"${COMPOSE[@]}" pull db-init backend frontend

echo "→ Recreating backend + frontend (no local build)"
"${COMPOSE[@]}" up -d --no-build backend frontend

echo "✓ Done.  Frontend → http://localhost:3000   ·   Backend → http://localhost:8080"
echo "  Images: $BACKEND_IMG , $WEB_IMG"
