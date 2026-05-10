# Réutilisation depuis TaxasGE — Inventaire

> **Objectif** : tracer explicitement ce qui est **réutilisé directement** depuis le snapshot TaxasGE vs ce qui doit être **adapté** ou **réécrit** pour Facil Framework.

---

## Principe directeur

**Réutiliser au maximum. Adapter ce qui est gov-spécifique. Réécrire ce qui est conceptuellement différent.**

Le code TaxasGE est mature, testé en production, avec audit gov compliance. Le réécrire from-scratch serait du gaspillage massif. La stratégie Facil Framework :

1. **Garder l'architecture** (3-tiers backend, modules pattern, deploy system)
2. **Abstraire les couplages spécifiques** (Vertex AI → LLMClient, Firebase Storage → StorageClient, etc.)
3. **Rendre les données configurables** (catalogue, taxonomies, branding)
4. **Activer/désactiver par module** (MODULES_ENABLED config)

---

## CATÉGORIE 1 — Réutilisé tel quel (zero changement)

Code générique fonctionnel partout, copy-paste direct.

### Backend

| Path | Description | Pourquoi réutilisable |
|---|---|---|
| `app/core/cache.py` | HybridCache Redis + in-memory fallback | Standard cache, agnostique métier |
| `app/core/rate_limit.py` | Rate limiting Redis-based | Standard |
| `app/core/secrets.py` | Secret Manager + .env fallback | Multi-cloud OK |
| `app/core/scheduler.py` | Cron scheduler | Standard |
| `app/core/idempotency.py` | Idempotency keys | Standard |
| `app/core/jsonb.py` | JSONB helpers asyncpg | Tech-only |
| `app/core/ws_manager.py` | WebSocket manager | Standard |
| `app/core/request_telemetry_middleware.py` | Request telemetry | Generic observability |
| `app/core/otel_user_middleware.py` | OpenTelemetry middleware | Generic |
| `app/core/user_agent_parser.py` | UA parser | Generic |
| `app/core/geoip.py` | MaxMind GeoIP | Generic (license MaxMind à fournir par chaque déployeur) |
| `app/database/connection.py` | asyncpg connection pool | Generic |
| `app/repositories/base.py` | Repository pattern base | Generic |
| `app/utils/*` | helpers, validators, date_utils, email_validator | Generic |
| `tests/conftest.py` | Pytest fixtures | Generic |

### Frontend Web

| Path | Description |
|---|---|
| `src/components/ui/*` | Shadcn/UI components (Button, Card, Form, Table, etc.) |
| `src/core/api/client.ts` | Axios client + interceptors |
| `src/lib/utils.ts` | cn() + helpers Tailwind |
| `src/i18n/*` | i18n setup (next-intl) |
| `tailwind.config.ts` | Tailwind config |
| `tsconfig.json` | TypeScript config |
| `next.config.mjs` | Next.js config (sera adapté pour SSR INTERNAL_API_URL) |

### Mobile + Inspector

| Path | Description |
|---|---|
| `app/_layout.tsx` | Expo router setup |
| `src/lib/api.ts` | API client |
| `src/lib/storage.ts` | AsyncStorage |
| Auth flows base | JWT login (à étendre pour OAuth/OTP/SAML en Phase J) |

### Deploy system

✅ **TOUT le `deploy/` est réutilisé** — c'est le travail de cette session :
- `deploy/init.py` (wizard CLI)
- `deploy/deploy.py` (orchestrateur)
- `deploy/scripts/validate_config.py`
- `deploy/scripts/render_env.py`
- `deploy/scripts/extract_seeds.py`
- `deploy/scripts/extract_full_schema.py`
- `deploy/scripts/classify_migrations.py`
- `deploy/providers/gcp.py`
- `deploy/providers/docker_local.py`
- `deploy/templates/`
- `deploy/.env.secrets.example`
- `deploy/config.example.yaml`

Tests `deploy/test_*.py` aussi (175+ tests).

### CI/CD workflows

| Path | Statut |
|---|---|
| `.github/workflows/ci.yml` | À adapter (nom org GitHub différent) |
| `.github/workflows/deploy-backend-staging.yml` | À adapter (project_id, secrets) |
| `.github/workflows/deploy-frontend-staging.yml` | À adapter |
| `.github/workflows/db-migrate-auto.yml` | À adapter |
| `.github/dependabot.yml` | À adapter (org name) |
| `.github/CODEOWNERS` | À réécrire (équipe différente) |
| `.github/ISSUE_TEMPLATE/*` | Réutiliser tels quels |
| `.github/PULL_REQUEST_TEMPLATE/*` | Réutiliser tel quel |

---

## CATÉGORIE 2 — Réutilisé avec ADAPTATION (modules génériques, à enrichir)

Modules métier conceptuellement génériques, mais qui contiennent des assomptions TaxasGE à généraliser.

### Backend modules

| Module | Adaptations nécessaires |
|---|---|
| `auth/` | Ajouter providers OAuth/SAML/OTP (Phase J) en plus de JWT |
| `permissions/` (RBAC) | Catalogue permissions étendu via Studio (pas hardcoded list) |
| `users/` | Champ profile-driven (gov utilise DNI, banque utilise CIN, etc.) |
| `companies/` | Renommer en `organizations/` ou similaire (concept générique) |
| `communications/` | Templates dynamiques (pas TaxasGE-specific email contents) |
| `documents/` | Storage abstraction (Phase C) — pas hardcoded Firebase |
| `audit_logs/` | Generic, juste enrichir filters via Studio |
| `chatbot/` | LLM Abstraction (Phase B) — swap Gemini/Claude/Mistral |
| `treasury/` | Caisse paiements générique — labels via i18n + branding |
| `verified_identifiers/` | Validation docs émis — generic (KYC banque, certificats école, attestations RH...) |
| `service_requests/` | Workflow demandes service — workflow designer (Phase H) drive |
| `inspections/` | Audit terrain générique (auditeur qualité, technicien, livreur) |
| `dashboards/` | Dashboards cards configurables via Studio |
| `webhooks/` | Generic |
| `support/` | Ticket system generic |

### Backend modules POTENTIELLEMENT à sortir en Enterprise

| Module | Raison |
|---|---|
| `assignment/` (auto-routing complex) | Algorithme avancé scoring multi-critères → potentiellement Enterprise feature |
| `agents/` (admin assistant LLM-based) | Cher en LLM tokens → potentiellement Enterprise |
| `enrichment/` (LLM-based) | Idem |
| `batch_requests/document_classifier` (LLM) | Idem |

→ **Décision V1 OSS** : tous inclus, gratuits. **V2** : modules cher en LLM peuvent être badgés Enterprise (avec activation par license key).

### Backend modules TaxasGE-specific (à inclure mais désactivés par défaut sauf profile gov)

| Module | Profile activé |
|---|---|
| `declarations_iva/` | gov-emergent-country uniquement |
| `bange_payment/`, `ecobank_payment/`, `mpgs_payment/` | gov-emergent-country (ou banking si pertinent) |
| Modules workflow gov régaliens (passeport bundle, residencia, etc.) | gov-emergent-country |

→ Ces modules **sont dans le code** mais le profile détermine s'ils sont activés. Un déployeur enterprise n'aura pas IVA.

---

## CATÉGORIE 3 — RÉÉCRIT from scratch

Vrais nouveaux modules / systèmes non existants dans TaxasGE.

| Composant | Pourquoi réécrit |
|---|---|
| **Module Loader** (`app/core/module_loader.py`) | TaxasGE charge tous modules en dur dans `main.py`. Voie B doit charger conditionnellement. Phase A.5 |
| **LLMClient ABC + 6 impls** | TaxasGE utilise GenerativeModel direct. Voie B abstrait. Phase B (sous-plan dédié) |
| **EmbeddingClient ABC + 6 impls** | Idem pour embeddings. Phase B.6 (sous-plan dédié) |
| **PaymentGateway ABC + impls** | TaxasGE a 3 gateways en dur. Voie B abstrait + Stripe/PayPal/etc. Phase B.5 |
| **StorageClient ABC + impls** | Phase C |
| **AuthProvider ABC + impls** | Phase J (OAuth/SAML/Magic/OTP) |
| **Customization Studio backend** | Endpoints `/api/v1/customize/*`. Phase E (n'existe pas TaxasGE) |
| **Customization Studio UI** | 11 pages dédiées. Phases F-G-H-I |
| **Workflow Designer** (drag-drop) | Phase H — le plus gros R&D |
| **Profile system** (`profiles/`) | Profiles avec install.yaml, seeds, workflows. Phase D |
| **`init_modules.py`** | Au boot, lit `MODULES_ENABLED` et load. Phase A.5 |
| **`tools/sync-from-taxasge.sh`** | Script cherry-pick infra fixes |

---

## CATÉGORIE 4 — Données SUPPRIMÉES (TaxasGE-specific)

Données réelles TaxasGE qui ne doivent PAS être livrées dans Facil Framework par défaut.

| Donnée | Action |
|---|---|
| Catalogue 850+ fiscal_services GE | **Retirer** des seeds par défaut. Reste dans profile `gov-emergent-country/seeds/` |
| 21 ministères Guinée Équatoriale | Idem |
| 17 sectors GE | Idem |
| 17 cities GE | Idem |
| Spanish translations + entity_translations (FR/EN/ES TaxasGE-specific) | Retirer. Profile fournira ses propres translations |
| 20 entities GE | Idem |
| 11 templates communications avec branding TaxasGE | Retirer. Profiles fournissent leurs propres templates |
| Workflows TaxasGE (passeport, residencia, conducir, IVA, IRPF) | Retirer du seed par défaut. Profile gov les fournit |
| Tests E2E ciblés sur TaxasGE features | Adapter en tests génériques |

---

## CATÉGORIE 5 — Documents TaxasGE → Templates pour Facil Framework

| TaxasGE | Facil Framework |
|---|---|
| `DEPLOYMENT.md` | À adapter — retirer mentions TaxasGE, généraliser |
| `README.md` (taxasge) | Réécrit (déjà fait pour facil_framework) |
| `CLAUDE.md` (taxasge) | À adapter — retirer mentions TaxasGE-specific |
| `docs/local-deployment-tutorial.md` | À adapter — généraliser exemples |
| `Documentations/PROJECT_CONTEXT.md` | NE PAS copier — gov-specific |
| `.github/docs-internal/` | NE PAS copier — internal TaxasGE |

---

## CATÉGORIE 6 — Tests réutilisés

| Type | Statut |
|---|---|
| Tests unitaires backend (pytest) | Réutilisés tels quels (fonctions pures testables) |
| Tests unitaires frontend (jest) | Réutilisés tels quels |
| Tests deploy/ (175+) | Réutilisés tels quels |
| Tests E2E TaxasGE-specific | À réécrire en tests génériques par profile |
| Tests d'intégration BD | Réutilisés (après adaptation modèles génériques) |

---

## Plan de divergence (sync-from-taxasge.sh)

Le script `tools/sync-from-taxasge.sh` permettra de **cherry-pick** des améliorations infrastructure de TaxasGE vers Facil Framework :

```bash
# Apply a specific commit from taxasge to facil_framework
./tools/sync-from-taxasge.sh <taxasge-commit-sha>
```

Bonnes pratiques :
- ✅ Sync auth fixes, deploy/ improvements, infra security patches
- ❌ NE PAS sync : modules métier TaxasGE-specific, gov data, branding TaxasGE
- 📋 Toujours code-review avant apply

---

## Métriques de réutilisation estimées

Sur ~100% du code Facil Framework :
- **~60% réutilisé tel quel** (Catégorie 1)
- **~25% adapté** (Catégorie 2)
- **~15% nouveau code** (Catégorie 3)

→ **75% gain de temps** vs développement from scratch.

C'est l'argument économique majeur : Facil Framework = TaxasGE généralisé, pas un projet from-scratch. Effort 8 mois 1 FTE crédible précisément parce qu'on capitalise sur le code existant.
