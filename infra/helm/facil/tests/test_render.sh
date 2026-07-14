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

# Le rendu est écrit UNE FOIS dans un fichier, et toutes les assertions lisent ce
# fichier -- jamais `echo "$OUT" | grep -q ...`.
#
# Pourquoi : `grep -q` (comme `awk ... exit`) sort dès la première correspondance et
# ferme le tuyau. L'`echo` en amont, qui n'a pas fini d'écrire, reçoit alors un EPIPE
# ("write error: Broken pipe"), et sous `set -euo pipefail` le pipeline entier est
# déclaré en échec. Le déclenchement dépend de la taille des tampons et du timing :
# le test échouait donc AU HASARD (vert sur la PR, rouge sur develop). Lire un fichier
# supprime l'écrivain, donc la course. Un test qui échoue aléatoirement finit par être
# relancé sans réfléchir -- il ne garde plus rien.
OUT_FILE="$(mktemp)"
trap 'rm -f "$OUT_FILE"' EXIT
printf '%s\n' "$OUT" > "$OUT_FILE"
# Postgres présent, image pinnée, password via secretKeyRef (jamais en clair).
grep -q "image: pgvector/pgvector:pg16" "$OUT_FILE"
grep -q "name: facil-postgres" "$OUT_FILE"
grep -q "secretKeyRef" "$OUT_FILE"
# Garde-secret PARSEE (SEC-009) : l'ancienne version en grep ne couvrait que 4
# cles figees, ratait les connection strings (DATABASE_URL/REDIS_URL rendent en
# `value:` avec interpolation $(VAR) -- jamais verifiees), ne regardait qu'UNE
# ligne apres `- name:` (`grep -A1`, contournable par un commentaire YAML
# intercale) et ne matchait pas le style flow (`{name: X, value: y}`) que le
# chart utilise deja ailleurs. Remplacee par un parseur YAML reel qui verifie
# des invariants structurels sur TOUS les conteneurs (init inclus) de TOUS les
# manifests. Voir infra/helm/facil/tests/guard_secrets.py +
# tests/test_guard_secrets.py (preuve par mutation de chaque invariant).
python infra/helm/facil/tests/guard_secrets.py < "$OUT_FILE"
grep -q "name: facil-redis" "$OUT_FILE"
grep -q "image: redis:7-alpine" "$OUT_FILE"
grep -q "name: facil-minio" "$OUT_FILE"
# SEC-014 : le coffre-fort et le stockage objet ne doivent pas suivre un tag
# mutable -- un push amont compromis se propagerait au prochain restart de pod,
# sans trace ni rollback possible.
grep -q "minio/minio@sha256:" "$OUT_FILE"
grep -q "name: facil-openbao" "$OUT_FILE"
grep -q "openbao/openbao@sha256:" "$OUT_FILE"
grep -q "IPC_LOCK" "$OUT_FILE"
grep -q "alembic" "$OUT_FILE"
grep -q "name: facil-backend" "$OUT_FILE"
grep -q "ghcr.io/kouemousah/facil-backend" "$OUT_FILE"
grep -q "path: /health" "$OUT_FILE"
grep -q "name: facil-frontend" "$OUT_FILE"
grep -q "ghcr.io/kouemousah/facil-web" "$OUT_FILE"
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
python infra/helm/facil/tests/guard_resources.py < "$OUT_FILE"
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
  # Lit le FICHIER, pas un pipe : `exit` dans l'action awk ferme l'entrée dès le
  # premier bloc trouvé -- un `printf ... | awk` en amont se prendrait un EPIPE
  # (même course que `echo | grep -q`, cf. le commentaire en tête de fichier).
  awk -v RS='\n---\n' -v src="# Source: ${source_path}" '
    index($0, src) == 1 { print; exit }
  ' "$OUT_FILE"
}

assert_job_hook() {
  # $4/$5 sont optionnels (retro-compatibles : les deux anciens appels ci-dessous
  # n'en passent que 3) -- ajoutes pour le Job de sauvegarde (P2/A2), qui n'est PAS
  # un post-install (rien a sauvegarder a la 1ere install, decision de conception
  # verrouillee) et n'a PAS besoin d'attendre Postgres (il tourne en pre-upgrade,
  # sur une release deja etablie ou Postgres tourne forcement deja -- contrairement
  # a db-role/db-init qui peuvent s'executer en post-install, juste apres que
  # Postgres vient de demarrer).
  local label="$1" source_path="$2" expected_weight="$3"
  local expected_hook="${4:-post-install,pre-upgrade}"
  local require_wait_postgres="${5:-true}"
  local block
  block="$(extract_job_block "$source_path")"
  if [ -z "$block" ]; then
    echo "FAIL hook($label): Job introuvable dans le rendu (source: $source_path)" >&2
    exit 1
  fi
  if [ "$require_wait_postgres" = "true" ] && ! echo "$block" | grep -q "wait-postgres"; then
    echo "FAIL hook($label): initContainer wait-postgres absent -- migration/role tenterait avant que Postgres soit pret" >&2
    exit 1
  fi
  if ! echo "$block" | grep -q "helm.sh/hook: ${expected_hook}"; then
    echo "FAIL hook($label): annotation helm.sh/hook=${expected_hook} absente ou mal formee" >&2
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
# P2 : la sauvegarde doit tourner AVANT les migrations, sinon elle ne protege rien.
assert_job_hook "backup" "facil/templates/backup-job.yaml" "-2" "pre-upgrade" "false"
# P2/A3 : les assertions grep ci-dessus ne comparent que des POIDS ATTENDUS en
# dur (litteraux "-2"/"-1"/"0") -- elles ne prouvent pas l'ORDRE relatif entre
# les Jobs, et une comparaison textuelle serait de toute facon un piege
# ("-2" < "-1" est FAUX en tri lexicographique). Garde parsee dediee : compare
# les hook-weight NUMERIQUEMENT (backup strictement < db-role ET db-init) et
# verifie le fail-closed (restartPolicy: Never, backoffLimit borne, aucun
# `|| true`). Voir infra/helm/facil/tests/guard_backup.py +
# tests/test_guard_backup.py (preuve par mutation de chaque invariant).
python infra/helm/facil/tests/guard_backup.py < "$OUT_FILE"

# B1 : l'ancienne garde negative ICI etait un grep GLOBAL sur tout le rendu
# (`grep -qE '"?helm\.sh/hook"?: pre-install' "$OUT_FILE"`) -- elle ne
# distinguait pas un Job (qui EXIGE Postgres deja debout -- APPLY-002) d'une
# simple ressource sans pod consommateur (ex. un PersistentVolumeClaim, pour
# qui pre-install est legitime), et se declenchait donc en FAUX POSITIF des
# qu'une telle ressource existait dans le chart. Remplacee par l'invariant 0
# de guard_backup.py (deja invoque plus haut dans ce fichier) : PAR KIND,
# aucun `kind: Job` ne porte `pre-install`, quelle que soit la forme de
# l'annotation (quotee ou non, YAML le normalise avant meme le parsing).
# Hardening : `runAsNonRoot: true` seul ne suffit PAS (nos images déclarent leur
# USER par nom -- le kubelet ne résout pas, CreateContainerConfigError) + SEC-018
# (spec.selector.matchLabels doit porter app.kubernetes.io/instance, sinon deux
# releases dans le meme namespace se volent leurs pods). Les DEUX anciennes
# assertions ici etaient des COMPTAGES GLOBAUX ("autant de X que de Y dans tout
# le rendu" / "un match n'importe ou apres un matchLabels:") -- exactement le
# biais tautologique deja tue 8 fois sur ce projet (guard_secrets.py,
# guard_networkpolicy.py, guard_ingress.py, et le premier invariant de
# guard_resources.py ci-dessus) : un seul workload fautif parmi plusieurs se
# fait compenser/masquer par les autres. Remplacees par les memes invariants,
# desormais verifies PAR WORKLOAD DANS guard_resources.py (deja invoque plus
# haut dans ce fichier -- SELECTOR_CHECKED_KINDS + runAsNonRoot/runAsUser,
# meme appel `python .../guard_resources.py`, < "$OUT_FILE" pas de 2e passe).
# Preuve par mutation : test_guard_resources.py.
# SEC-001 : le backend ne doit monter AUCUN bundle global (envFrom sur un Secret
# partage) — chaque pod ne voit que le Secret de son composant.
# NB : `! echo ... | grep -q ...` seul ne fait PAS echouer un script `set -e`
# (bash n'applique pas errexit a une commande dont le statut est inverse par
# `!`) -- gate explicite comme les autres verifications de ce fichier.
if grep -q "envFrom" "$OUT_FILE"; then
  echo "FAIL garde-secret: envFrom detecte (bundle global partage) -- chaque pod doit monter uniquement le Secret de son composant" >&2
  exit 1
fi
# CWE-214 : le mdp applicatif du Job db-role ne doit JAMAIS transiter par l'argv
# de psql (lisible via /proc/<pid>/cmdline) -- il doit etre lu depuis l'env via
# `\getenv` (le SQL lui-meme -- ConfigMap rendu par pg_roles.py -- est hors du
# chart Helm, verifie par deploy/scripts/test_pg_roles.py + deploy/providers/
# test_k3s.py ; ici on garde seulement l'invariant du Job Helm rendu).
if grep -q -- '-v app_pw=' "$OUT_FILE"; then
  echo "FAIL garde-secret: mdp applicatif passe en argv psql (-v app_pw=...) -- CWE-214" >&2
  exit 1
fi
# SEC-012 : NetworkPolicy default-deny (ingress) + allow explicites par
# composant. k3s embarque le controleur NetworkPolicy de kube-router (compile
# dans le process serveur k3s, pas un pod separe) -> les NetworkPolicy sont
# REELLEMENT appliquees -- VERIFIE EMPIRIQUEMENT le 2026-07-14 sur un cluster
# k3d jetable (ECONNREFUSED pour un pod non-autorise, connexion normale pour
# un pod facil.component=backend ; detail dans SMOKE.md, section Risque 1).
# `grep -q "kind: NetworkPolicy"` ne prouve rien sur le ciblage :
# un podSelector qui ne matche aucun pod reel est une policy inerte. Remplace
# par un parseur YAML reel (meme convention que guard_secrets.py /
# guard_resources.py ci-dessus) qui verifie : (1) une policy default-deny
# (podSelector: {}) avec policyTypes == [Ingress] SEULEMENT (jamais Egress --
# casserait le DNS vers kube-dns, hors du namespace de la release) ; (2) tout
# podSelector cible/peer matche au moins un pod-template REELLEMENT rendu.
# Voir infra/helm/facil/tests/guard_networkpolicy.py +
# tests/test_guard_networkpolicy.py (preuve par mutation de chaque invariant).
grep -q "kind: NetworkPolicy" "$OUT_FILE"
grep -q "policyTypes" "$OUT_FILE"
python infra/helm/facil/tests/guard_networkpolicy.py < "$OUT_FILE"
# SEC-024 : Ingress Traefik single-origin ("/" -> frontend, "/api" -> backend).
# `grep -q "kind: Ingress"` + `grep -q "ingressClassName: traefik"` ne prouvent
# RIEN sur le ROUTAGE (un backend/port errone rend toujours ces deux chaines).
# Meme convention que les gardes ci-dessus : parseur YAML reel qui verifie le
# Service + port resolus PAR PREFIXE. Voir infra/helm/facil/tests/guard_ingress.py
# + tests/test_guard_ingress.py (preuve par mutation : /api reroute vers le
# Service frontend).
grep -q "kind: Ingress" "$OUT_FILE"
grep -q "ingressClassName: traefik" "$OUT_FILE"
python infra/helm/facil/tests/guard_ingress.py < "$OUT_FILE"
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
