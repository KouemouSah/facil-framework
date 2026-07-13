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
# Garde-secret PARSEE (SEC-009) : l'ancienne version en grep ne couvrait que 4
# cles figees, ratait les connection strings (DATABASE_URL/REDIS_URL rendent en
# `value:` avec interpolation $(VAR) -- jamais verifiees), ne regardait qu'UNE
# ligne apres `- name:` (`grep -A1`, contournable par un commentaire YAML
# intercale) et ne matchait pas le style flow (`{name: X, value: y}`) que le
# chart utilise deja ailleurs. Remplacee par un parseur YAML reel qui verifie
# des invariants structurels sur TOUS les conteneurs (init inclus) de TOUS les
# manifests. Voir infra/helm/facil/tests/guard_secrets.py +
# tests/test_guard_secrets.py (preuve par mutation de chaque invariant).
echo "$OUT" | python infra/helm/facil/tests/guard_secrets.py
echo "$OUT" | grep -q "name: facil-redis"
echo "$OUT" | grep -q "image: redis:7-alpine"
echo "$OUT" | grep -q "name: facil-minio"
# SEC-014 : le coffre-fort et le stockage objet ne doivent pas suivre un tag
# mutable -- un push amont compromis se propagerait au prochain restart de pod,
# sans trace ni rollback possible.
echo "$OUT" | grep -q "minio/minio@sha256:"
echo "$OUT" | grep -q "name: facil-openbao"
echo "$OUT" | grep -q "openbao/openbao@sha256:"
echo "$OUT" | grep -q "IPC_LOCK"
echo "$OUT" | grep -q "alembic"
echo "$OUT" | grep -q "name: facil-backend"
echo "$OUT" | grep -q "ghcr.io/kouemousah/facil-backend"
echo "$OUT" | grep -q "path: /health"
echo "$OUT" | grep -q "name: facil-frontend"
echo "$OUT" | grep -q "ghcr.io/kouemousah/facil-web"
# SEC-015 : resources.limits/requests, seccompProfile, readOnlyRootFilesystem,
# automountServiceAccountToken=false. Un comptage global (ex. "autant de
# `limits:` que de workloads") est une assertion TAUTOLOGIQUE : plusieurs
# conteneurs d'UN workload peuvent porter assez de `limits:` pour compenser
# qu'UN SEUL container d'un AUTRE workload n'en ait pas -- exactement le biais
# documente plus haut dans ce fichier (sept occurrences passees sur ce projet).
# Remplace par un parseur YAML reel qui verifie l'invariant PAR CONTENEUR
# (containers + initContainers) DE CHAQUE workload -- meme convention que
# guard_secrets.py ci-dessus (DRY). Preuve par mutation : guard_resources.py +
# test_guard_resources.py.
echo "$OUT" | python infra/helm/facil/tests/guard_resources.py
# APPLY-002 : les hooks pre-install s'executent AVANT les ressources de la release
# (donc avant Postgres) -> la migration echouerait a la 1ere install. post-install
# + initContainer d'attente = le seul ordonnancement qui marche install ET upgrade.
#
# Garde scopee PAR JOB (et non sur tout le rendu) : `db-role-job.yaml` fournit
# deja son propre `wait-postgres` -- une assertion globale `grep -q wait-postgres`
# passe donc meme si celui de db-init disparaissait (verifie : elle passait deja
# avant que db-init n'en ait un -- non-regressive de facto). On extrait chaque
# Job de hook via son marqueur `# Source: ...` (unique par fichier de template,
# stable quel que soit l'overlay -f) et on asserte DEDANS.
extract_job_block() {
  local source_path="$1"
  printf '%s' "$OUT" | awk -v RS='\n---\n' -v src="# Source: ${source_path}" '
    index($0, src) == 1 { print; exit }
  '
}

assert_job_hook() {
  local label="$1" source_path="$2" expected_weight="$3"
  local block
  block="$(extract_job_block "$source_path")"
  if [ -z "$block" ]; then
    echo "FAIL hook($label): Job introuvable dans le rendu (source: $source_path)" >&2
    exit 1
  fi
  if ! echo "$block" | grep -q "wait-postgres"; then
    echo "FAIL hook($label): initContainer wait-postgres absent -- migration/role tenterait avant que Postgres soit pret" >&2
    exit 1
  fi
  if ! echo "$block" | grep -q "helm.sh/hook: post-install,pre-upgrade"; then
    echo "FAIL hook($label): annotation helm.sh/hook=post-install,pre-upgrade absente ou mal formee" >&2
    exit 1
  fi
  if ! echo "$block" | grep -q "helm.sh/hook-weight: \"${expected_weight}\""; then
    echo "FAIL hook($label): helm.sh/hook-weight attendu \"${expected_weight}\" absent" >&2
    exit 1
  fi
  # ATTENTION : `! cmd | grep -q ...` est une assertion MORTE sous `set -e` — POSIX
  # exempte d'errexit toute commande dont le statut est inverse par `!`. Toujours
  # un if/exit explicite pour une assertion negative.
  if echo "$block" | grep -qE '"?helm\.sh/hook"?: pre-install'; then
    echo "FAIL hook($label): hook pre-install encore present -- il s'execute AVANT que Postgres existe" >&2
    exit 1
  fi
}

assert_job_hook "db-role" "facil/templates/db-role-job.yaml" "-1"
assert_job_hook "db-init" "facil/templates/db-init-job.yaml" "0"

# Garde negative globale (style d'annotation normalise non-quote sur les deux
# Jobs -- cf. commentaire ci-dessus) : aucun `pre-install` nulle part dans le
# rendu, quelle que soit la forme de la cle (quotee ou non -- couvre une
# regression qui reintroduirait le style quote).
if echo "$OUT" | grep -qE '"?helm\.sh/hook"?: pre-install'; then
  echo "FAIL: hook pre-install detecte dans le rendu complet -- il s'execute AVANT que Postgres existe" >&2
  exit 1
fi
# Hardening : `runAsNonRoot: true` seul ne suffit PAS. Nos images déclarent leur
# USER par nom (`appuser`, `nextjs`) ; le kubelet ne résout pas les noms de l'image
# et refuse alors le pod (CreateContainerConfigError: "image has non-numeric user").
# Tout podSpec runAsNonRoot doit donc porter un runAsUser numérique — invariant que
# `helm template`/`helm lint` ne vérifient pas, d'où cette assertion.
# SEC-018 : sans app.kubernetes.io/instance dans le selector, deux releases dans
# le meme namespace se volent leurs pods (les Service de l'une selectionnent
# aussi ceux de l'autre, puisque le seul discriminant restant serait
# facil.component, identique entre releases). Verifie sur un `matchLabels:`
# (Deployment/StatefulSet.spec.selector) reellement rendu.
echo "$OUT" | grep -A3 "matchLabels:" | grep -q "app.kubernetes.io/instance"
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
# SEC-012 : NetworkPolicy default-deny (ingress) + allow explicites par
# composant. k3s embarque kube-router -> les NetworkPolicy sont REELLEMENT
# appliquees, contrairement a un cluster flannel nu ou elles seraient
# ignorees. `grep -q "kind: NetworkPolicy"` ne prouve rien sur le ciblage :
# un podSelector qui ne matche aucun pod reel est une policy inerte. Remplace
# par un parseur YAML reel (meme convention que guard_secrets.py /
# guard_resources.py ci-dessus) qui verifie : (1) une policy default-deny
# (podSelector: {}) avec policyTypes == [Ingress] SEULEMENT (jamais Egress --
# casserait le DNS vers kube-dns, hors du namespace de la release) ; (2) tout
# podSelector cible/peer matche au moins un pod-template REELLEMENT rendu.
# Voir infra/helm/facil/tests/guard_networkpolicy.py +
# tests/test_guard_networkpolicy.py (preuve par mutation de chaque invariant).
echo "$OUT" | grep -q "kind: NetworkPolicy"
echo "$OUT" | grep -q "policyTypes"
echo "$OUT" | python infra/helm/facil/tests/guard_networkpolicy.py
# SEC-024 : Ingress Traefik single-origin ("/" -> frontend, "/api" -> backend).
# `grep -q "kind: Ingress"` + `grep -q "ingressClassName: traefik"` ne prouvent
# RIEN sur le ROUTAGE (un backend/port errone rend toujours ces deux chaines).
# Meme convention que les gardes ci-dessus : parseur YAML reel qui verifie le
# Service + port resolus PAR PREFIXE. Voir infra/helm/facil/tests/guard_ingress.py
# + tests/test_guard_ingress.py (preuve par mutation : /api reroute vers le
# Service frontend).
echo "$OUT" | grep -q "kind: Ingress"
echo "$OUT" | grep -q "ingressClassName: traefik"
echo "$OUT" | python infra/helm/facil/tests/guard_ingress.py
# SEC-020 : global.namespace n'etait reference par aucun template (valeur
# morte -- le vrai namespace vient de `helm ... -n <ns>` / .Release.Namespace).
# `! grep -q ... ` est une assertion MORTE sous `set -e` (POSIX exempte
# d'errexit toute commande inversee par `!`) -- if/exit explicite comme
# ailleurs dans ce fichier.
if grep -q "namespace: facil" infra/helm/facil/values.yaml; then
  echo "FAIL: global.namespace (valeur morte) encore present dans values.yaml" >&2
  exit 1
fi
echo "OK render (${VALUES_FILE:-default})"
