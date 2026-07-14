# Smoke k3d réel — chart `infra/helm/facil`

> **Statut : PASS** (après 2 bugs bloquants trouvés et corrigés en cours de route).
> `helm lint` + `helm template` + 542 tests unitaires étaient déjà tous verts
> **avant** ce smoke — aucun des deux bugs ci-dessous n'était détectable par
> ces outils. Seul un `apply` réel sur un vrai kubelet les a révélés.

Date : 2026-07-13/14. Cluster : k3d (k3s v1.35.5+k3s1 dans Docker), 1 nœud,
`--agents 0`. Commits produits par ce smoke : `77165af`, `8dc8370` (branche
`docs/infra-multitarget-deploy`).

> **Complément 2026-07-14 (revue finale de branche)** : le risque 1
> (NetworkPolicy) ci-dessous était noté "INCONCLUANT" sur une méthodologie
> erronée — corrigé avec un test décisif sur un second cluster k3d jetable,
> voir la section mise à jour.

## Procédure

```bash
# 1. Cluster jetable
curl -s https://ghcr.io/... # (k3d installé via binaire GitHub release, pas de package manager Windows)
k3d cluster create facil --agents 0 --port "18080:80@loadbalancer" --wait
kubectl config use-context k3d-facil

# 2. Secrets manquants
python deploy/scripts/ensure_secrets.py

# 3. validate -> plan -> apply
python deploy/deploy.py --provider=k3s --action=validate
python deploy/deploy.py --provider=k3s --action=plan | python infra/helm/facil/tests/guard_secrets.py
python deploy/providers/k3s.py --apply --yes --allow-dev-vault

# 4. Vérification des critères d'acceptation (voir tableau ci-dessous)

# 5. Nettoyage
k3d cluster delete facil
docker system prune -f
```

**Écart config nécessaire (pas un bug)** : `deploy/config.yaml` avait
`meta.version: latest`. La CI (`release-images.yml`) ne publie **jamais** de
tag `:latest` sur GHCR — seulement `develop` et `sha-<commit>`. Corrigé
localement en `version: develop` (fichier gitignored, config de smoke
manuelle, pas un fichier versionné). Sans ce changement, le premier `--apply`
tournait en `ImagePullBackOff` pendant 10 minutes (`ghcr.io/kouemousah/facil-backend:latest: not found`).

## Bugs trouvés et corrigés (avant que le smoke ne passe)

### Bug 1 — `deploy.py --action=plan` casse le pipe `guard_secrets.py` (commit `77165af`)

**Symptôme** : `deploy/deploy.py --provider=k3s --action=plan | guard_secrets.py`
levait `yaml.ParserError: expected '<document start>', but found '<scalar>'`.

**Cause** : `run_step()` imprimait ses bannières `"Step N/4"` sur **stdout**, et
les étapes 1-3 (capture=False) laissaient passer directement le stdout des
sous-scripts (`validate_config.py`, `render_env.py`, `k3s.py --validate` — ex.
`"[OK] Config valid..."`) **avant** le rendu `helm template` de l'étape 4.
`guard_secrets.py` (`yaml.safe_load_all`) ne tolère aucune prose non-YAML en
tête de flux. Même défaut, plus profond, dans `k3s.py --plan` lui-même (bannière
`"=== k3s plan ... ==="` imprimée sur stdout avant le `helm template`).

**Fix** : toute la prose de l'orchestrateur (bannières + stdout/stderr
capturés des étapes 1-3) part sur **stderr** ; seule l'étape 4 (le
`--plan`/`--apply` réel du provider) garde un stdout non capturé — c'est
l'unique flux réel, pipeable tel quel. Même correction sur la bannière de
`k3s.py --plan`.

**Vérifié** : `deploy/deploy.py --provider=k3s --action=plan | guard_secrets.py`
→ `OK garde-secret (parsee)`, exit 0. 48 tests `test_deploy.py` +
`test_k3s.py` toujours verts (aucune régression : rien n'assertait sur
`capture_output`).

### Bug 2 — deadlock réel entre `helm --wait` et les hooks `post-install` db-role/db-init (commit `8dc8370`)

**Symptôme** : `helm upgrade --atomic --wait --timeout 10m` expirait
**systématiquement** au 1er install (`Error: release facil failed ... context
deadline exceeded`), sans qu'AUCUN Job (`facil-db-role`/`facil-db-init`) ne
soit jamais créé (`kubectl -n facil get jobs` → vide pendant toute la fenêtre
de 10 min). Le backend restart-loopait sur `password authentication failed
for user "facil_app"`.

**Cause racine** : `db-role`/`db-init` sont des hooks `post-install,pre-upgrade`
— nécessaire, car ils exigent Postgres déjà démarré (impossible en
pre-install au 1er install, où rien n'existe encore) et parce que SEC-001
interdit de les fondre dans un initContainer du backend (qui ne doit **jamais**
voir le superuser Postgres). Or Helm n'exécute les hooks post-install **qu'après**
que `--wait` ait vu **toutes** les ressources non-hook prêtes — dont le
Deployment backend. Le `readinessProbe` du backend (`/health`) exige la BD
(`SELECT 1`), qui n'existe pas tant que ces mêmes hooks n'ont pas tourné.
Deadlock garanti, 100% reproductible, pas un cas limite.

**Fix** : `--apply` fait désormais **deux passes** `helm upgrade --install` :
1. 1ère passe avec `--set backend.replicas=0` — le Deployment est trivialement
   `Available` (0 pod à attendre), `--wait` (5 min) passe vite, Postgres est
   déjà debout → les hooks tournent normalement (rôle + migrations).
2. 2ème passe sans cet override (replicas=1 par défaut du chart) — le rôle/schéma
   existent désormais, `/health` répond 200 dès le 1er cycle de probe,
   `--wait` (10 min) converge normalement.

Idempotent par construction : `create_role_sql` = `CREATE`-si-absent + `ALTER`
(commentaire du fichier source), `alembic upgrade head` est un no-op si déjà
à jour — donc rejouer les hooks au `pre-upgrade` de la 2e passe (observé en
conditions réelles : `facil-db-role` et `facil-db-init` se sont bien
ré-exécutés, en quelques secondes chacun) est sans effet de bord.

**Vérifié en conditions réelles** (voir séquence d'événements ci-dessous) :
passe 1 → postgres/redis/minio/openbao/frontend Ready + hooks `Complete` en
~30s ; passe 2 → backend scale 0→1, hooks rejoués (idempotents, ~15s), backend
`/health` → 200 dès la première readinessProbe réussie. `helm -n facil
history facil` : révision 1 `superseded` (passe 1), révision 2 `deployed`
(passe 2). 38 tests `test_k3s.py` + 542 tests globaux toujours verts.

## Critères d'acceptation — résultats RÉELLEMENT observés

| # | Critère | Résultat |
|---|---|---|
| 1 | 6 pods always-on Running/Ready | **PASS** — `postgres` 1/1, `redis` 1/1, `minio` 1/1, `openbao` 1/1, `backend` 1/1, `frontend` 1/1 (tous `Running`) |
| 2 | Jobs `facil-db-role` + `facil-db-init` Complete | **PASS** — `facil-db-role` `1/1 Complete` (9s), `facil-db-init` `1/1 Complete` (15s) |
| 3 | `/health` backend → 200 | **PASS** — `kubectl exec ... urlopen('http://localhost:8080/health')` → `200` ; corps JSON : `{"status":"ok","database":true,"config_db":true,"cache":"redis",...}` |
| 4 | Backend connecté en `facil_app`, pas en superuser | **PASS** — `SELECT usename FROM pg_stat_activity WHERE datname='facil' AND usename<>'facil'` → `facil_app` (uniquement) |
| 5 | Backend sans AUCUN credential root en env | **PASS** — `printenv \| grep -E "POSTGRES_PASSWORD\|MINIO_ROOT_PASSWORD\|OPENBAO_DEV_ROOT_TOKEN"` → aucune sortie, exit 1 |
| 6 | Aucun secret dans le manifest Helm | **PASS** — `helm -n facil get manifest facil \| guard_secrets.py` → `OK garde-secret (parsee)`, exit 0 |
| 7 | Stack joignable via l'Ingress | **PASS** — `/` (Host: facil.local) → `307` vers `/install` (Next.js, headers CSP/Next réels) → `/install` → `200` ; `/api/v1/system/branding` → `200` ; `/api/v1/system/install-status` → `200` |

**Les 7 critères passent**, après correction des 2 bugs ci-dessus.

## Verdict sur les 3 risques identifiés

### Risque 1 — NetworkPolicy réellement appliquée ou inerte ?

**PASS — VÉRIFIÉ EMPIRIQUEMENT le 2026-07-14** (revue finale de branche,
cluster k3d jetable séparé `facil-netpol`, k3s v1.35.5+k3s1, agents 0).

**La conclusion "INCONCLUANT" ci-dessus (smoke initial du 2026-07-13) reposait
sur une méthodologie erronée**, relevée en revue finale : elle déduisait
« Flannel sans enforcement » de l'absence d'un pod/DaemonSet de contrôleur de
policy dans `kube-system`. Or **le contrôleur NetworkPolicy de k3s (kube-router)
est compilé DANS le process serveur k3s lui-même — ce n'est pas un pod
séparé**. Son absence de la liste des pods de `kube-system` ne prouve donc
rien, ni dans un sens ni dans l'autre ; il fallait un test de connectivité
réel, pas une recherche de pod.

**Procédure (test décisif)** :

```bash
k3d cluster create facil-netpol --agents 0 --wait
kubectl config use-context k3d-facil-netpol
python deploy/providers/k3s.py --apply --yes --allow-dev-vault

# Pod SANS label facil.component (identité non autorisée)
kubectl -n facil run rogue --restart=Never --image=python:3.12-alpine --command -- sleep 3600
kubectl -n facil exec rogue -- python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(5)
s.connect(('facil-postgres', 5432))"

# Pod AVEC label facil.component=backend (identité autorisée par
# allow-datastores-from-backend), pour prouver qu'on n'a pas juste tout cassé
kubectl -n facil apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata: {name: authorized-test, labels: {facil.component: backend}}
spec: {containers: [{name: probe, image: python:3.12-alpine, command: ["sleep","3600"]}]}
YAML
kubectl -n facil exec authorized-test -- python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(5)
s.connect(('facil-postgres', 5432))"

k3d cluster delete facil-netpol
docker system prune -f
```

**Résultat brut observé** :

```text
# rogue (aucun label facil.component) -> facil-postgres:5432
ConnectionRefusedError: [Errno 111] Connection refused (after 0.00s)
# rogue -> facil-redis:6379
ConnectionRefusedError: [Errno 111] Connection refused (after 0.00s)
# rogue -> kube-dns.kube-system.svc.cluster.local:53 (référence : service NON
# ciblé par les policies du chart, doit rester joignable)
CONNECTED in 0.00s

# authorized-test (facil.component=backend) -> facil-postgres:5432
CONNECTED in 0.02s
# authorized-test (facil.component=backend) -> facil-redis:6379
CONNECTED in 0.00s
```

Confirmation mécanique (pas seulement comportementale) : `docker exec
k3d-facil-netpol-server-0 iptables -L -n` montre les chaînes `KUBE-ROUTER-INPUT`
/ `KUBE-ROUTER-FORWARD` / `KUBE-ROUTER-OUTPUT` actives aux côtés de
`FLANNEL-FWD` — le contrôleur netpol de kube-router tourne bien, intégré au
process serveur.

**Verdict** : les 4 `NetworkPolicy` du chart (`facil-default-deny` + 3
`allow-*`) sont **réellement appliquées** sur k3s (via kube-router, embarqué).
Un pod sans l'identité (`facil.component`) autorisée reçoit un `ECONNREFUSED`
instantané sur les datastores ; un pod avec l'identité autorisée s'y connecte
normalement — la même stack, sans changement, sauf le label du pod appelant.
Les 4 fichiers qui affirmaient ce comportement (`networkpolicy.yaml`,
`values.yaml`, `guard_networkpolicy.py`, `test_render.sh`) l'affirmaient déjà
correctement, mais **sans preuve** avant ce test ; ils référencent désormais
cette section pour la preuve.

**Portée de la garantie** : ceci vaut pour **k3s avec son CNI/contrôleur netpol
par défaut** (le seul chemin de ce chart, ADR-0006). Un opérateur qui
désactiverait explicitement le réseau par défaut de k3s (`--flannel-backend=none`
sans installer de CNI alternatif appliquant les NetworkPolicy, ou
`--disable-network-policy`) perdrait cette isolation silencieusement — hors
scope de ce chart, qui ne pose aucune garde contre une telle désactivation au
niveau du serveur k3s lui-même (config server, pas Helm).

### Risque 2 — `readOnlyRootFilesystem` sur OpenBao, chemin d'écriture caché

**PASS.** `facil-openbao-0` : `0` restart sur toute la durée du smoke (~20
min), logs propres (aucune erreur de permission/read-only filesystem), dev
mode démarré et déverrouillé normalement (`core: vault is unsealed`). Aucun
autre chemin d'écriture caché détecté au-delà des deux déjà corrigés
(`emptyDir` sur `$HOME`, `fsGroup`).

### Risque 3 — résolution DNS (egress resté ouvert, jamais vérifié en vrai)

**PASS, vérifié en vrai.** Depuis `deploy/facil-backend` :
- DNS interne : `socket.gethostbyname('facil-postgres')` → `10.43.214.90` (ClusterIP résolu via CoreDNS).
- DNS externe : `socket.gethostbyname('ghcr.io')` → `140.82.121.33`.
- Egress HTTPS réel : `urlopen('https://ghcr.io')` → `200`.

Cohérent avec le chart : `facil-default-deny` a `policyTypes: [Ingress]`
uniquement — l'egress n'est jamais restreint, et ceci est maintenant vérifié
empiriquement (pas seulement lu dans le YAML).

## Observation annexe (hors périmètre des critères, notée pour mémoire)

`/health` renvoie `"secrets_source": "env-only", "secrets_provider":
"env-fallback"` alors qu'OpenBao tourne (`facil-openbao-0` Ready, dev mode).
Le backend ne résout donc pas ses secrets via OpenBao dans cette
configuration de smoke — probablement une variable d'environnement de
sélection du provider non câblée par le chart (`SECRETS_PROVIDER` ou
équivalent absent de `backend.yaml`/`values.yaml`). Non bloquant pour les 7
critères d'acceptation (aucun n'exige le câblage OpenBao runtime), mais à
creuser avant de considérer OpenBao « intégré de bout en bout » — dégradation
silencieuse à surveiller (cf. commentaire du code source lui-même sur
`secrets_source`, qui existe précisément pour rendre ce genre de repli
observable).

## Autre observation : restarts transitoires du backend (environnement, pas le chart)

Le pod `facil-backend` a subi 4 redémarrages (`Killing ... failed liveness
probe`) pendant la 2e passe, avec des événements `connection refused` /
`context deadline exceeded` corrélés à `docker stats` montrant le conteneur
`k3d-facil-server-0` à **885% CPU** — cette machine fait tourner en parallèle
la stack complète `facil_framework` (docker-compose : backend/frontend/
postgres/redis/openbao/keycloak/minio) ET le cluster k3d (qui redéploie
essentiellement la même stack). Conclusion : contention CPU de l'hôte de
développement, pas un défaut du chart — le pod s'est stabilisé (`1/1 Ready`)
une fois la charge de calcul des Jobs (alembic, psql) retombée. À noter pour
un smoke futur : éteindre la stack `docker-compose` sœur avant de lancer ce
test, pour un signal plus propre sur les probes.

## Nettoyage

```bash
k3d cluster delete facil
docker system prune -f
```

Exécuté en fin de smoke — cluster détruit, RAM (~2-3 Go) et images du cluster
libérées, confirmé par `k3d cluster list` (vide) et `docker ps` (plus aucun
conteneur `k3d-facil-*`).
