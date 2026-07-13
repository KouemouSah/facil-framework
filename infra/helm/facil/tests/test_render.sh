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
echo "OK render"
