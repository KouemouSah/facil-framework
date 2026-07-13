#!/usr/bin/env bash
set -euo pipefail
OUT="$(helm template rel infra/helm/facil)"
# Postgres présent, image pinnée, password via secretKeyRef (jamais en clair).
echo "$OUT" | grep -q "image: pgvector/pgvector:pg16"
echo "$OUT" | grep -q "name: facil-postgres"
echo "$OUT" | grep -q "secretKeyRef"
# Garde-secret : aucune valeur de mot de passe en clair dans le rendu.
! echo "$OUT" | grep -Eiq "POSTGRES_PASSWORD: [^v].*[a-z0-9]{8}"
echo "$OUT" | grep -q "name: facil-redis"
echo "$OUT" | grep -q "image: redis:7-alpine"
echo "$OUT" | grep -q "name: facil-minio"
echo "$OUT" | grep -q "image: minio/minio:latest"
echo "$OUT" | grep -q "name: facil-openbao"
echo "$OUT" | grep -q "IPC_LOCK"
echo "$OUT" | grep -q "helm.sh/hook: pre-install,pre-upgrade"
echo "$OUT" | grep -q "alembic"
echo "$OUT" | grep -q "name: facil-backend"
echo "$OUT" | grep -q "ghcr.io/kouemousah/facil-backend"
echo "$OUT" | grep -q "path: /health"
echo "$OUT" | grep -q "name: facil-frontend"
echo "$OUT" | grep -q "ghcr.io/kouemousah/facil-web"
echo "OK render"
