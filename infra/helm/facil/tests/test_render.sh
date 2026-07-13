#!/usr/bin/env bash
set -euo pipefail
OUT="$(helm template rel infra/helm/facil)"
# Postgres présent, image pinnée, password via secretKeyRef (jamais en clair).
echo "$OUT" | grep -q "image: pgvector/pgvector:pg16"
echo "$OUT" | grep -q "name: facil-postgres"
echo "$OUT" | grep -q "secretKeyRef"
# Garde-secret (réel) : chaque credential est câblé via secretKeyRef, jamais
# en littéral. Le check précédent (`grep "POSTGRES_PASSWORD: [^v]..."`) ne
# pouvait jamais matcher un manifest k8s (les env vars rendent en liste
# `- name: X` / `valueFrom:`, pas en `X: <literal>`) — no-op structurel.
for key in POSTGRES_PASSWORD REDIS_PASSWORD MINIO_ROOT_PASSWORD OPENBAO_DEV_ROOT_TOKEN; do
  CTX="$(echo "$OUT" | grep -B2 -E "key: ${key}\b" || true)"
  if ! echo "$CTX" | grep -q "secretKeyRef"; then
    echo "FAIL garde-secret: ${key} n'est pas câblé via secretKeyRef" >&2
    exit 1
  fi
done
# ... et aucune de ces variables n'est jamais inlinée en `value:` littéral.
INLINED="$(echo "$OUT" | grep -A1 -E '^[[:space:]]*- name: (POSTGRES_PASSWORD|REDIS_PASSWORD|MINIO_ROOT_PASSWORD|OPENBAO_DEV_ROOT_TOKEN)[[:space:]]*$' | grep -E '^[[:space:]]*value:[[:space:]]' || true)"
if [ -n "$INLINED" ]; then
  echo "FAIL garde-secret: credential inliné en clair -> $INLINED" >&2
  exit 1
fi
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
