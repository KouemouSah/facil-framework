# Data-plane Bootstrap — provisioning idempotent du socle

> **Statut** : implémenté (2026-06-11), validé sur la stack docker-local.
> **Code** : `deploy/providers/bootstrap/` · **Launcher** : `deploy/providers/run_bootstrap.py`
> **Plan** : `.claude/plans/DATAPLANE_BOOTSTRAP_PLAN.md` (interne).

## 1. Problème résolu

`docker compose up` démarre 4 services data-plane (Postgres, Redis, MinIO,
OpenBao) **allumés mais vides** : aucun bucket, aucun engine de secrets, aucune
extension, aucun compte. Ils partagent un réseau mais n'ont **aucune
configuration croisée**, et `docker_local.py --apply` s'arrêtait à `up -d`.

De plus, en dev OpenBao (`server -dev`) tourne **en mémoire** : toute
configuration faite à la main est perdue au prochain redémarrage. La seule
réponse correcte (ISO/ITIL) est de **codifier le provisioning** en une couche
**idempotente** rejouée à chaque `up`.

## 2. Solution

Une couche de provisioning **idempotente** et **deployment-mode-aware** qui
transforme « containers up » en « data-plane utilisable ». Elle consomme le seam
de configuration déjà présent (`storage.provider`, `secrets.provider`,
`docker_local.database_mode`) : le même code sert on-prem / cloud / SaaS, c'est
la **config** qui décide ce qui s'exécute.

```
deploy/providers/bootstrap/
  __init__.py        dispatcher mode-aware + orchestrateur + CLI (--plan/--apply/--only)
  context.py         BootstrapContext (cfg, réseau, dry_run) injecté à chaque provisioner
  docker_helpers.py  résolution conteneur (par label compose) + wait-for-healthy + run_oneshot/exec_in
  state.py           ProvisionStep / BootstrapState -> deploy/.bootstrap-state.json
  env_secrets.py     lecteur dotenv minimal (.env.secrets)
  minio.py           bucket + versioning + policy privée + service account scopé
  openbao.py         kv-v2 + secrets de boot + policy + AppRole
  postgres.py        extensions infra (vector / pg_trgm / uuid-ossp)
```

### Flux

```
docker_local.py --apply
   ├─ render_env + génère docker-compose.local.yml
   ├─ docker compose up -d --build
   └─ run_bootstrap(cfg)                 ← NOUVEAU (sauf --no-bootstrap)
        ├─ wait-for-healthy(services applicables)
        ├─ dispatch selon storage/secrets/db_mode
        ├─ openbao → minio → postgres   (ordre déterministe)
        └─ merge + écrit .bootstrap-state.json
```

## 3. Ce que chaque provisioner fait (et pourquoi)

### MinIO (`storage.provider == "minio"`)
- **Bucket** `facil-documents` (`mc mb --ignore-existing`).
- **Versioning ON** — rétention long-terme, prérequis signatures PAdES (Phase N.5).
- **Accès anonyme = none** (privé par défaut).
- **Service account scopé** `facil-backend` : policy S3 inline limitée en rw au
  seul bucket. **Les credentials root ne sont jamais donnés au backend**
  (ISO 27001 / moindre privilège). Secret généré une fois, persisté, réutilisé.
- *Pourquoi `mc` et pas boto3 ?* `mc` est l'outil admin canonique MinIO et sait
  créer un service account scopé (ce que l'API S3 seule ne fait pas) ; exécuté en
  conteneur one-shot sur le réseau de la stack, zéro dépendance hôte.

### OpenBao (`secrets.provider == "openbao"`)
- **kv-v2** monté au path `facil/` (namespace secrets applicatif).
- **5 secrets de boot** copiés depuis `.env.secrets` vers `facil/boot`
  (écriture uniquement si différents). `.env.secrets` **reste le fallback
  runtime** — dégradation propre si OpenBao indisponible.
- **Policy `facil-backend`** en **lecture seule** sur `facil/data/*`.
- **AppRole** `facil-backend` : `role_id` stable + `secret_id` généré une fois et
  réutilisé via l'état (pas d'accumulation).
- **Hors scope** : PKI / mTLS interne (= P7/P8). Ici uniquement la *consommation*
  de secrets.

### Postgres (`docker_local.database_mode == "local"`)
- `CREATE EXTENSION IF NOT EXISTS` pour **vector** (RAG), **pg_trgm** (recherche
  floue), **uuid-ossp** (uuid). Capacités **infra** ; le **schéma applicatif**
  (tables) reste la propriété de `db-init`/migrations (Phase D), qui les
  ré-affirmera sans conflit.

## 3bis. Architecture de sécurité MinIO (durcissement S1–S5)

Au-delà du provisioning de base, le provisioner MinIO applique un durcissement
**config-driven** (champs `storage.minio.*`) et **idempotent** :

| Capacité | Détail | Config |
|---|---|---|
| **Bucket WORM** | `facil-compliance` créé `mc mb --with-lock` (Object-Lock ⇒ versioning auto), pour artefacts à valeur légale (PAdES/eIDAS, reçus, pistes d'audit). Object-Lock **uniquement à la création** ⇒ bucket séparé. | `compliance.enabled/bucket` |
| **Rétention** | rétention par défaut `GOVERNANCE` (bypass privilégié, dev-cleanable) ou `COMPLIANCE` (immuable même root). | `compliance.retention_mode/_days` |
| **Lifecycle** | expiration des **versions non-courantes** sur le bucket documents (versioning ON ⇒ sinon stockage non borné). Pas sur le bucket WORM (conflit rétention). Multipart incomplets : déjà auto-purgés par le serveur (`api.stale_uploads_expiry` 24h). | `lifecycle.expire_noncurrent_versions_days` |
| **Quotas** | quota dur par bucket (anti-runaway) ; `0` = non géré. | `quota_documents_gb`, `quota_compliance_gb` |
| **SA bucket-set** | le service account `facil-backend` couvre documents (rw complet) **+** compliance (read + write + set-retention, **sans DeleteObject** — write-once, défense en profondeur sur Object-Lock). Aucun accès aux autres buckets. Policy ré-appliquée à chaque run via `svcacct edit` (sans rotation du secret). | — |
| **Privé** | `anonymous set none` sur tous les buckets gérés. | — |

**Preuves live** : `mc rm --version-id` sur une version retenue ⇒ *« WORM protected
and cannot be overwritten »* ; avec les creds du SA : write compliance **OK**,
delete compliance **Access Denied**, créer un autre bucket **Access Denied**.

### Chiffrement at-rest — voir **ADR-0007**

Le chiffrement at-rest **n'utilise pas** le SSE-S3/KES de MinIO (`minio/kes`
**déprécié**, remplaçant **Enterprise** ⇒ incompatible AGPL souverain). Il se fait
au **niveau volume** : **LUKS + clé custodiée dans OpenBao**, déverrouillage au
boot — sujet **production VPS/k3s**, **no-op documenté** en dev Docker Desktop.
Détails et runbook : `docs/adr/0007-encryption-at-rest-luks-openbao.md`.

## 3ter. Durcissement auth data-plane (H1–H4)

Le data-plane tournait sur des **défauts faibles** (`localdev`, Redis sans auth,
`facilminio`) parce que docker compose interpole `${VAR}` depuis le shell/`.env`,
**jamais** depuis `.env.secrets` (qui n'est qu'un `env_file` des conteneurs).

| Durcissement | Détail |
|---|---|
| **Secrets forts** | `ensure_secrets.py` génère idempotemment `POSTGRES_PASSWORD` / `REDIS_PASSWORD` / `MINIO_ROOT_PASSWORD` forts dans `.env.secrets` (clés manquantes uniquement). `docker_local --apply` les passe en **env_extra** au `compose up` ⇒ `${VAR:-default}` résout la vraie valeur. |
| **Redis auth** | service `--requirepass`, healthcheck authentifié, `REDIS_URL` avec mot de passe (placeholder `${REDIS_PASSWORD}` gardé littéral dans le YAML). |
| **Rôle Postgres least-privilege** | le bootstrap crée `facil_app` **NOSUPERUSER** (CONNECT/USAGE/DML + `ALTER DEFAULT PRIVILEGES` pour les tables futures de db-init), **sans** DDL/CREATEDB/SUPERUSER. Le backend l'utilise ; le superuser reste réservé aux migrations. Password généré/réutilisé via state. |
| **Centralisation OpenBao** | `POSTGRES/REDIS/MINIO_ROOT_PASSWORD` mirrorés dans `facil/runtime` (lisibles par l'AppRole `facil-backend`). `.env.secrets` reste la source pour compose. |

**Preuves live** (recreate `down -v` + re-bootstrap) : Redis NOAUTH sans mot de
passe / PONG avec ; Postgres réseau rejette `localdev`, accepte le fort
(scram-sha-256) ; MinIO rejette `facilminio` ; `facil_app` connecté `superuser=off`,
CREATE DATABASE/TABLE **refusés** ; AppRole lit `facil/runtime` (200).

### Observabilité (seam — live différé Phase D)

Le seam OTLP existe (`observability.mode` = `disabled`/`local`/`cloud`). En
`mode=local`, le backend émettra vers `otel-lgtm:4317` (profil `observability`,
souverain self-hosted). **Aucun service ne tourne à vide** : le câblage
backend→OTLP sera activé et validé quand le backend sera porté (Phase D) — pas de
placeholder ici.

## 4. Garanties

| Propriété | Comment | Preuve |
|---|---|---|
| **Idempotence** | chaque opération est no-op si déjà appliquée ; secrets réutilisés via `.bootstrap-state.json` | re-run : « already mounted / up to date / secret reused / already present » |
| **Moindre privilège** | SA MinIO scopé au bucket ; AppRole OpenBao read-only | SA refuse de créer un autre bucket ; AppRole : read boot 200 / write 403 / sys 403 |
| **Non-fatal** | un provisioner en échec n'abat pas la stack | `_run_bootstrap` capture et avertit, l'opérateur rejoue |
| **Runs partiels sûrs** | `--only=X` préserve les credentials des autres (merge-on-write) | `full → only=postgres → full` réutilise les secrets |

## 5. Le fichier d'état `deploy/.bootstrap-state.json`

Gitignored (même niveau de confiance que `.env.secrets`). Enregistre **ce qui a
été provisionné** et les **credentials générés** (SA MinIO, AppRole OpenBao). Il
est le **pont vers le tier applicatif** : quand le backend sera porté (Phase D),
`render_env.py` le consommera pour câbler le backend (endpoint MinIO + clés,
`BAO_ADDR` + role_id/secret_id). Rien de généré n'est perdu.

## 6. Tutoriel

> Python du repo : `C:\facil_framework\.venv\Scripts\python.exe`.

```powershell
# Automatique : le bootstrap tourne après un up sain
python deploy/providers/docker_local.py --config=deploy/config.yaml --apply

# Opt-out (CI qui ne veut pas provisionner)
python deploy/providers/docker_local.py --config=deploy/config.yaml --apply --no-bootstrap

# Standalone (stack déjà up) — voir ce qui serait fait, sans rien muter
python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --plan

# Provisionner / re-provisionner (idempotent)
python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --apply

# Cibler un seul service (les autres credentials sont préservés)
python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --apply --only=minio
```

Codes de sortie : `0` succès / `1` config invalide / `2` provisioner en échec ou
timeout health.

## 6bis. Accès & méthodes de connexion (dev)

> Les **valeurs** vivent dans `.env.secrets` (mots de passe runtime) et
> `deploy/.bootstrap-state.json` (credentials générés) — **gitignored**, jamais
> committés. Ci-dessous : *où* les lire et *quelle méthode* utiliser.

| Service | Console/URL | Méthode & identifiant |
|---|---|---|
| **MinIO** | console `:9001` / API `:9000` | admin : user `facil` + `MINIO_ROOT_PASSWORD` (`.env.secrets`). Backend : **service account scopé** `facil-backend` + secret (`state.minio_secret_key`) — jamais le root |
| **OpenBao** | `:8200` | **admin/dev** : token racine `root` (dev in-memory). **Backend** : **AppRole** `facil-backend` (`role_id`+`secret_id` dans le state) → token court → lecture `facil/data/*` |
| **Postgres** | `:5432` | migrations/db-init : superuser `facil` + `POSTGRES_PASSWORD`. Backend : **rôle least-privilege** `facil_app` + `pg_app_password` (state) |
| **Redis** | `:6379` | auth obligatoire : `REDIS_PASSWORD` (`.env.secrets`) — `redis-cli -a $REDIS_PASSWORD` |

**Recommandation méthode OpenBao** : le **backend se connecte en AppRole**
(role_id + secret_id, token à TTL court, politique read-only `facil/data/*`) —
c'est la méthode retenue, pas le token racine. Le token `root` est réservé à
l'**admin/dev** (et n'existe qu'en dev in-memory ; en prod = unseal SOPS+age, P7,
token réel/OIDC). Les mots de passe runtime sont aussi lisibles centralement dans
OpenBao `facil/runtime` via cet AppRole.

## 7. Scope actuel & limitations (honnête)

- **Docker-local uniquement** pour l'instant : `mc` sur le réseau de la stack,
  `docker exec psql`, OpenBao sur `localhost:8200`. Le **seam est mode-aware**
  (le dispatcher lit `storage.provider`/`secrets.provider`), mais les
  **provisioners cloud** (bucket GCS/S3, Secret Manager, extensions Cloud SQL)
  **ne sont pas encore implémentés** — ils étendront le même dispatcher.
  `gcp.py` n'est donc **pas** câblé au bootstrap (éviter une fausse couverture).
- **OpenBao dev = en mémoire** : le provisioning est rejoué à chaque `up`. En
  prod (`dev_mode=false`, unseal SOPS+age, P7) le même provisioner s'appliquera
  une fois sur du stockage persistant.

## 8. Tests

`102 tests` verts (`deploy/providers/bootstrap/` 45 + `test_docker_local.py` 57),
runner = `.venv` du repo. Couverture : mécanique d'état + idempotence du merge,
dispatch par mode, gate de santé, chaque provisioner (création / reuse / rotation
/ dry-run / erreur), intégration docker-local (auto-run / opt-out / non-fatal).
Validation **live** sur la stack réelle pour MinIO, OpenBao et Postgres.
