# Fondation backend — config-store + registre de providers (Phase D : D1 / D1.5 / D2)

> **Statut** : implémenté + validé live (2026-06-12). `packages/backend/`.
> **Plan** : `.claude/plans/PHASE_D_APP_FOUNDATION_PLAN.md` (interne).
> **Pré-requis** : socle data-plane provisionné (voir `DATAPLANE_BOOTSTRAP.md`).

## 1. Vue d'ensemble

Le tier applicatif démarre sur le data-plane souverain durci, autour de **deux
mécanismes dynamiques** :

1. **Config-store BD** — configuration applicative éditable à chaud par l'admin
   (étage DB), au-dessus des défauts/fichier/env.
2. **Registre de providers** — chaque capacité (secrets, storage, LLM, email,
   auth, payment) est un provider pluggable, sélectionnable et configurable au
   runtime.

Le backend est un **skeleton minimal neuf** (clean-slate ADR-0004), PAS un port
du legacy : il porte uniquement la fondation. Les 32 modules métier et les 150
tables legacy ne sont **pas** touchés (portage incrémental ultérieur).

```mermaid
flowchart TB
  subgraph deploy["Deploy (socle, déjà fait)"]
    boot["bootstrap -> .bootstrap-state.json<br/>facil_app · SA MinIO · AppRole OpenBao"]
    rbe["render_backend_env -> .env.deploy.gen"]
    boot --> rbe
  end
  subgraph backend["packages/backend (FastAPI)"]
    cfg["config-store: settings (DB) + resolver<br/>defauts -> config.yaml -> DB -> env"]
    reg["provider registry: provider_settings (DB)<br/>ABCs + factory + get_default"]
    api["API admin token-gated:<br/>/admin/settings · /admin/providers"]
  end
  rbe -. DATABASE_URL facil_app .-> backend
  reg --> opb["OpenBaoSecretsProvider (AppRole)"]
  reg --> mio["MinIOStorageProvider (SA scopé)"]
  opb -. lit .-> OB[(OpenBao facil/boot+runtime)]
  mio -. put/get .-> MN[(MinIO facil-documents)]
```

## 2. Structure (`packages/backend/app/`)

| Module | Rôle |
|---|---|
| `config.py` | Pydantic `BaseSettings` (env/.env) — bootstrap config (DATABASE_URL, ADMIN_TOKEN) ; normalise vers `postgresql+asyncpg://` |
| `db/{base,engine}.py` | `DeclarativeBase` + type JSON portable (JSONB/SQLite) ; engine async + session factory |
| `models/setting.py` | table `settings` (généralise `system_rules`) |
| `models/provider.py` | table `provider_settings` (généralise `communication_provider_settings`) |
| `config_store/{resolver,repository}.py` | résolveur en couches + CRUD settings |
| `core/providers/{base,registry,repository}.py` | ABCs + `ProviderRegistry` + CRUD provider_settings |
| `core/providers/{secrets_env,secrets_openbao,storage_minio}.py` | providers concrets |
| `security/admin_token.py` | garde token bootstrap (`X-Admin-Token`, fail-closed) |
| `api/{admin_settings,admin_providers,deps}.py` | routes admin |
| `main.py` | app + `/health` + lifespan (engine, resolver, registry) |
| `alembic/` | migrations (0001 settings, 0002 provider_settings) |

## 3. Config-store (étage DB éditable admin)

- Table **`settings`** : `key`, `value` (jsonb), `value_type`, `scope`,
  `secret_ref`, noms i18n, dates d'effet, `is_active`, audit.
- **Résolveur** (`config_store/resolver.py`) : précédence
  **env > DB > config.yaml > défauts**. L'app-config sans env → la **DB gagne**
  (éditable admin) ; l'infra-config a un env → l'**env gagne** (non runtime).
- **API** `/api/v1/admin/settings/` (CRUD, token-gated) ; un PUT/DELETE
  **rafraîchit** la couche DB du résolveur en mémoire (invalidation D1 ;
  fan-out EventBus/NOTIFY = ultérieur).

## 4. Registre de providers

- Table **`provider_settings`** : `capability`, `provider_code`, `config` (jsonb),
  `secret_ref`, `is_default`, `is_active`, rate/retry/timeout. Unicité (capability,
  provider_code).
- **ABCs** (`core/providers/base.py`) : `SecretsProvider`, `StorageProvider`,
  `LLMProvider`, `EmailProvider` + `healthcheck()`. Le métier dépend des
  interfaces, jamais d'un SDK vendeur.
- **`ProviderRegistry`** : `register(cap, code, factory)`, `build(cap, code, config)`,
  `get_default(cap, session)` (lit `is_default` en DB). Factories **lazy** (rien ne
  se connecte au build).
- **API** `/api/v1/admin/providers/` : CRUD + `POST .../{cap}/{code}/default`
  (un seul défaut/capacité) + `GET .../registered` + `POST .../{cap}/{code}/check`
  (healthcheck réel).

### Providers concrets (souverains, validés live)
- **`secrets/openbao`** : login **AppRole** (creds de l'env rendu) → lit kv-v2
  `facil/boot` + `facil/runtime` → `get_secret(name)`.
- **`storage/minio`** : S3 **put/get/delete** via le **SA scopé** (boto3 path-style,
  `asyncio.to_thread`).
- **`secrets/env`** : lit l'environnement (défaut dev).

## 5. Jonction deploy↔app (D1.5)

`docker_local --apply` est **staged** :
1. data-plane up → 2. **bootstrap** (mint facil_app/SA/AppRole → state) →
3. **`render_backend_env`** (state → `.env.deploy.gen` : `DATABASE_URL` facil_app,
   `MINIO_*`, `OPENBAO_*`) → 4. **db-init** = `alembic upgrade head` (superuser) +
   **backend** (facil_app). Frontend **profile-gaté** (`web`, OFF jusqu'à D5).

> **Migrations = superuser `facil`** (DDL) ; **backend = `facil_app`** (least-priv,
> DML). `facil_app` reçoit les grants via `ALTER DEFAULT PRIVILEGES` du bootstrap.

## 6. Accès & tutoriel

> Python : `C:\facil_framework\.venv\Scripts\python.exe`. Garde admin : `ADMIN_TOKEN`
> (généré par `ensure_secrets` dans `.env.secrets`).

```powershell
# Stack complète (data-plane + bootstrap + backend), frontend OFF :
python deploy/providers/docker_local.py --config=deploy/config.yaml --apply
# -> backend healthy http://localhost:8080/health

# Settings (config runtime)
curl -H "X-Admin-Token: $TOKEN" http://localhost:8080/api/v1/admin/settings/
curl -X PUT -H "X-Admin-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"value":"sendgrid","scope":"email"}' \
  http://localhost:8080/api/v1/admin/settings/email.provider

# Providers (registre)
curl -H "X-Admin-Token: $TOKEN" http://localhost:8080/api/v1/admin/providers/registered
curl -X POST -H "X-Admin-Token: $TOKEN" \
  http://localhost:8080/api/v1/admin/providers/secrets/openbao/check
```

**Ajouter un provider** = (1) classe qui implémente l'ABC de sa capacité,
(2) `registry.register(cap, code, factory)` dans `default_registry()`,
(3) éventuel `provider_settings` (config) via l'API admin. Le métier ne change pas.

### Gotchas
- `asyncpg` depuis le host Windows → port publié 5432 échoue (Docker Desktop) ;
  backend/alembic tournent **dans le réseau compose** (`postgres:5432`).
- Apply depuis un worktree → projet compose distinct (conflit de ports) ;
  utiliser `COMPOSE_PROJECT_NAME=facil_framework` ou nettoyer les orphelins.

## 7. Statut & limites (honnête)

- ✅ **Fait + live** : config-store, résolveur, registre, providers OpenBao secrets
  & MinIO storage, jonction `docker_local --apply`, Alembic.
- ⏳ **À venir** : providers LLM (Ollama/openai), email (SMTP), auth — réels mais
  non live-testables sans leur backing ; **D3** Module Loader · **D4** auth complète
  (remplace la garde token) · **D5** frontend (panneau admin + installeur web).
- Le legacy (150 tables, 32 modules) reste parqué — portage incrémental.
