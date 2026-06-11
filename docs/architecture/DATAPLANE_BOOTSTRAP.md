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
