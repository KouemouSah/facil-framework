#!/usr/bin/env bash
set -euo pipefail
# Usage: test_render.sh [-f <values-file>]
# Sans argument : rendu par défaut (comportement historique, inchangé).
# Avec -f <values-file> : ajoute cet overlay au `helm template` (ex. values-onprem.yaml)
# et applique EXACTEMENT les mêmes assertions (garde-secret incluse, aucun skip).
VALUES_FILE=""
while getopts ":f:" opt; do
  case "$opt" in
    f) VALUES_FILE="$OPTARG" ;;
    \?) echo "Usage: $0 [-f <values-file>]" >&2; exit 2 ;;
    :) echo "Option -$OPTARG requiert un argument" >&2; exit 2 ;;
  esac
done

if [ -n "$VALUES_FILE" ]; then
  OUT="$(helm template rel infra/helm/facil -f "$VALUES_FILE")"
else
  OUT="$(helm template rel infra/helm/facil)"
fi
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
# Hardening : `runAsNonRoot: true` seul ne suffit PAS. Nos images déclarent leur
# USER par nom (`appuser`, `nextjs`) ; le kubelet ne résout pas les noms de l'image
# et refuse alors le pod (CreateContainerConfigError: "image has non-numeric user").
# Tout podSpec runAsNonRoot doit donc porter un runAsUser numérique — invariant que
# `helm template`/`helm lint` ne vérifient pas, d'où cette assertion.
NONROOT="$(echo "$OUT" | grep -c 'runAsNonRoot: true' || true)"
WITH_UID="$(echo "$OUT" | grep -A1 'runAsNonRoot: true' | grep -cE 'runAsUser: [0-9]+' || true)"
if [ "$NONROOT" -ne "$WITH_UID" ]; then
  echo "FAIL hardening: $((NONROOT - WITH_UID)) podSpec(s) runAsNonRoot sans runAsUser numérique" >&2
  exit 1
fi
# SEC-001 : le backend ne doit monter AUCUN bundle global (envFrom sur un Secret
# partage) — chaque pod ne voit que le Secret de son composant.
# NB : `! echo ... | grep -q ...` seul ne fait PAS echouer un script `set -e`
# (bash n'applique pas errexit a une commande dont le statut est inverse par
# `!`) -- gate explicite comme les autres verifications de ce fichier.
if echo "$OUT" | grep -q "envFrom"; then
  echo "FAIL garde-secret: envFrom detecte (bundle global partage) -- chaque pod doit monter uniquement le Secret de son composant" >&2
  exit 1
fi
# CWE-214 : le mdp applicatif du Job db-role ne doit JAMAIS transiter par l'argv
# de psql (lisible via /proc/<pid>/cmdline) -- il doit etre lu depuis l'env via
# `\getenv` (le SQL lui-meme -- ConfigMap rendu par pg_roles.py -- est hors du
# chart Helm, verifie par deploy/scripts/test_pg_roles.py + deploy/providers/
# test_k3s.py ; ici on garde seulement l'invariant du Job Helm rendu).
if echo "$OUT" | grep -q -- '-v app_pw='; then
  echo "FAIL garde-secret: mdp applicatif passe en argv psql (-v app_pw=...) -- CWE-214" >&2
  exit 1
fi
echo "OK render (${VALUES_FILE:-default})"
