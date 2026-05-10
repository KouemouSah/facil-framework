# Deploy System Audit (Phase A.5.0)

> **Statut** : Document temporaire. Sera intégré ou supprimé en fin de Phase A.5.1.
> **Date** : 2026-05-09
> **Source** : `packages/backend/app/config.py` + `.github/workflows/deploy-*-staging.yml`

---

## 1. Backend env vars — categorization

**Total** : 172 env-backed Field declarations dans `config.py`.

### 1.1 CRITICAL (10) — sans elles, l'app ne démarre pas

| ENV_VAR | Type | Notes |
|---|---|---|
| `ENVIRONMENT` | str | development/staging/production |
| `DATABASE_URL` | str | Postgres direct connection (asyncpg). Required. |
| `JWT_SECRET_KEY` | str | Auth tokens. **Never default in prod.** |
| `SECRET_KEY` | str | FastAPI session signing |
| `REDIS_URL` | str | Cache + rate limit + idempotency |
| `GOOGLE_CLOUD_PROJECT` | str | Vertex AI + Secret Manager namespace |
| `GEMINI_API_KEY` | str | OR Vertex AI ADC (one of the two required) |
| `FIREBASE_PROJECT_ID` | str | Push notifications + Storage |
| `FIREBASE_STORAGE_BUCKET` | str | File uploads (Supabase Storage alternative) |
| `CRON_SECRET` | str | Auth token for `/cron/*` endpoints |

### 1.2 STANDARD (~50) — defaults sensibles, mais souhaitables en config

#### Server
- `API_HOST`, `PORT`, `FRONTEND_URL`, `API_BASE_URL`
- `DEBUG`, `LOG_LEVEL`, `LOG_FILE`, `ENABLE_STRUCTURED_LOGGING`
- `MOBILE_DEEP_LINK_SCHEMES`

#### Auth
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
- `TOTP_ENCRYPTION_KEY` (Fernet key — **secret in prod**)
- `RECEIPT_VERIFICATION_SECRET` (HMAC for QR codes — **secret**)

#### Database connection pool
- `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`
- `DATABASE_MIN_CONNECTIONS`, `DATABASE_MAX_CONNECTIONS`

#### Supabase (alternative path)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`

#### Firebase
- `FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV` (admin SDK key — **secret**)
- `FIREBASE_ANDROID_APP_ID`

#### AI (Gemini models)
- `GEMINI_CHAT_MODEL`, `GEMINI_PRO_MODEL`, `GEMINI_EMBEDDING_MODEL`
- `GEMINI_MAX_OUTPUT_TOKENS`, `GEMINI_TEMPERATURE`, `GEMINI_TOP_P`, `GEMINI_TOP_K`
- `GOOGLE_CLOUD_LOCATION`

#### Payment providers (selon activation)
- BANGE: `BANGE_API_URL`, `BANGE_API_KEY`, `BANGE_MERCHANT_ID`, `BANGE_WEBHOOK_SECRET` (**secret**)
- ECOBANK: `ECOBANK_API_URL`, `ECOBANK_CLIENT_ID`, `ECOBANK_CLIENT_SECRET` (**secret**), `ECOBANK_WEBHOOK_SECRET` (**secret**), `ECOBANK_PRIMARY_METHODS`
- MPGS: `MPGS_API_URL`, `MPGS_MERCHANT_ID`, `MPGS_API_PASSWORD` (**secret**), `MPGS_API_VERSION`, `MPGS_WEBHOOK_SECRET` (**secret**), `MPGS_PRIMARY_METHODS`

#### SMTP
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_USE_TLS`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`
- `SMTP_PASSWORD` (Secret Manager: `smtp-password`)

#### Cache + Rate limiting
- `CACHE_TTL`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW`

#### Observability (optionnels)
- `SENTRY_DSN`, `SLACK_WEBHOOK_URL`, `SONAR_TOKEN`

#### Legal versioning
- `LEGAL_PRIVACY_VERSION`, `LEGAL_PRIVACY_LAST_UPDATED`
- `LEGAL_TERMS_VERSION`, `LEGAL_TERMS_LAST_UPDATED`
- `LEGAL_COOKIES_VERSION`, `LEGAL_COOKIES_LAST_UPDATED`

### 1.3 TUNABLES (~95) — defaults conservatives suffisent

Ne pas exposer dans `config.example.yaml` (pollue la lisibilité). Reste configurable via env vars pour les opérateurs avancés.

- **Outbox** (4) : `OUTBOX_*`
- **Agent Queue** (7) : `QUEUE_*`
- **Escalation** (5) : `ESCALATION_*` (sauf `ESCALATION_PREDICTIVE_*`)
- **Scheduler intervals** (8) : `SCHEDULER_*_INTERVAL`
- **Multi-criteria scoring** (~50) : `SCORING_*`, `SPECIALIZATION_*`, `ANOMALY_*`, `REBALANCE_*`, `LLM_ROUTING_*`, `QUALITY_SCORE_*`
- **RAG / Embedding** (12) : `EMBEDDING_*`, `RAG_*`, `SEMANTIC_*`, `PDF_CHUNK_*`, `MAX_CONTEXT_TOKENS`, `SUGGESTION_*`
- **Cleanup** (3) : `DRAFT_CLEANUP_MAX_HOURS`, `PREVIEW_EXPIRY_MINUTES`, `WIZARD_SESSION_TTL_SECONDS`
- **AI thresholds** (2) : `AI_MAX_TOKENS`, `AI_CONFIDENCE_THRESHOLD`
- **Reports** (3) : `REPORT_*_DAYS`, `REPORT_*_HOURS`

### 1.4 FEATURE FLAGS (8) — toggles boolean

- `SCHEDULER_ENABLED`
- `RATE_LIMIT_ENABLED`
- `ENABLE_METRICS`
- `ENABLE_STRUCTURED_LOGGING`
- `FEATURE_EXECUTIVE_TOOLS`
- `FEATURE_LLM_ROUTING_ENABLED`
- `PENALTIES_ENABLED`
- `SMTP_USE_TLS`

---

## 2. Frontend env vars (Next.js, build-time + runtime)

### Build-time (Docker `ARG`)
- `NEXT_PUBLIC_API_URL` — Backend API URL (baked into client bundle)
- `NEXT_PUBLIC_LOGROCKET_APP_ID` — LogRocket app id (optional)
- `NEXT_PUBLIC_BUILD_VERSION` — Git SHA, surfaced as Sentry/LogRocket release
- `NEXT_PUBLIC_SENTRY_DSN` — Sentry DSN (public)
- `NEXT_PUBLIC_ENVIRONMENT` — staging | production
- `SENTRY_AUTH_TOKEN` — Build-time only, for sourcemap upload (**secret**)

### Runtime (Cloud Run env)
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_SITE_URL`

---

## 3. Secret Manager references (current usage)

| Secret name | Purpose |
|---|---|
| `smtp-password` | SMTP authentication |
| `firebase-admin-key-dev` | Firebase Admin SDK (dev project) |
| `firebase-admin-key-pro` | Firebase Admin SDK (prod project) |
| `receipt-verification-secret` | HMAC for payment receipt QR codes |
| `grafana-sa-token` | Grafana Cloud OTLP token (audit log) |
| `looker-readonly-db-url` | Looker Studio JDBC connection (read-only DB) |

---

## 4. GCP services in use (deploy/staging workflows)

| Service | Usage | Provider primitive |
|---|---|---|
| Cloud Run (services) | Backend `taxasge-backend-staging` (us-central1) + Frontend `taxasge-frontend-staging` | `gcloud run deploy` |
| Cloud Run (jobs) | One-shot tasks: `populate-embeddings-staging`, init_database (futur) | `gcloud run jobs create/execute` |
| Cloud Build | Image builds (multi-stage Dockerfile) | `gcloud builds submit` |
| Container Registry (GCR) | Image storage `gcr.io/taxasge-dev/...` | `gcloud container images` |
| Secret Manager | All sensitive values | `gcloud secrets versions` |
| Cloud Run domain mapping | `api.facil.gq` etc. | `gcloud beta run domain-mappings` |

**External services** (not GCP-native):
- Supabase Postgres (DB primary) — alternative à Cloud SQL
- Upstash Redis (cache) — TLS connection
- Firebase Auth + Storage — partagé avec mobile
- Sentry, LogRocket, Grafana Cloud (observability)

---

## 5. Frontend deploy method confirmed

**Cloud Run** (pas Firebase Hosting). Service name `taxasge-frontend-staging`. Dockerfile multi-stage Node 20 alpine. Build args via `gcloud builds submit --substitutions=...`. Domain mapping vers `api.facil.gq` / domaine custom via `gcloud beta run domain-mappings`.

---

## 6. Implications pour `config.example.yaml` (Phase A.5.1)

### Sections à exposer
1. `meta` (project, environment, version)
2. `database` (host/port/name/user/ssl + secret refs for password)
3. `redis` (URL secret ref)
4. `auth` (token expiries + secret refs for JWT/SECRET/TOTP)
5. `firebase` (project_id, storage_bucket, service_account_secret)
6. `ai` (Gemini model names + secret refs for API key)
7. `payments.bange/.ecobank/.mpgs` (URL/IDs + webhook secrets)
8. `smtp` (host/port/from + password secret)
9. `observability` (Sentry DSN, LogRocket, Grafana endpoint)
10. `legal` (versions des 3 documents)
11. `gcp` (project, region, service names, cloud_sql_instance)
12. `aws` (placeholder pour P2)
13. `docker_local` (ports, volumes pour dev local)

### Sections NON exposées (defaults code)
- Tous les TUNABLES (95+) → restent en env vars pour opérateurs avancés
- Feature flags → à exposer dans une section `features:` simple boolean

### Total config.example.yaml estimé
- ~150 lignes annotées
- 13 sections principales
- 60-70 paramètres directement visibles (10 CRITICAL + ~50 STANDARD + 8 FEATURE)
- 95 paramètres masqués (TUNABLES) — overridables via `env_overrides:` section optionnelle

---

## 7. Risques identifiés

| Risque | Sévérité | Mitigation Phase A.5.x |
|---|---|---|
| Oublier d'exposer `TOTP_ENCRYPTION_KEY` (Fernet key) | 🔴 HIGH | Inclure dans `auth.totp_encryption_key_secret` |
| Mélanger 3 providers payment dans même section | 🟡 MED | Sous-sections séparées + flag `enabled: bool` |
| Confusion DATABASE_URL vs SUPABASE_URL | 🟡 MED | Doc claire : "DATABASE_URL = primary, SUPABASE_* = bridge fallback" |
| Frontend déployé Cloud Run, pas static — coût plus élevé | 🟢 LOW | Documenter alternative Firebase Hosting en P2 |
| 8 SECRETS implicites non listés dans Secret Manager | 🟡 MED | Phase A.5.1 : audit complet + provisioning script |

---

## 8. Décisions A.5.0 → A.5.1

- ✅ **Auditer-only** complet, pas de fichier code créé
- ✅ Catégorisation valide (10 CRITICAL / ~50 STANDARD / ~95 TUNABLES / 8 FEATURE)
- ✅ Frontend deploy = Cloud Run confirmé
- ✅ GCP services cartographiés (8 services)
- ⏭️ Phase A.5.1 démarrage : rédiger `config.example.yaml` (60-70 paramètres exposés) + Pydantic validator

**Cible structure config.example.yaml** : ~150 lignes annotées, 13 sections, lisible par un humain non-technique pour les valeurs simples (URLs, on/off), avec doc inline pour les valeurs sensibles.
