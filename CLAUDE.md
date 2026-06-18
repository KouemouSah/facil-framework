# CLAUDE.md — Facil Framework

Guidance pour Claude Code quand il travaille dans ce repo. Ces instructions
**complètent** le global `~/.claude/CLAUDE.md` et le surchargent en cas de conflit.

## ⚠️ Isolation repo (CRITIQUE)

Ce repo (`C:\facil_framework`, remote `github.com/KouemouSah/facil-framework.git`)
est **distinct et frère** de `C:\taxasge` (le déploiement de référence).

- **JAMAIS** pousser, cherry-pick automatique, ou builder du code taxasge ici, et inversement.
- Avant tout `git push`, vérifier `git remote -v` → doit pointer sur `facil-framework`, jamais taxasge.
- La seule diffusion taxasge → facil = cherry-pick **manuel** documenté (`tools/sync-from-taxasge.sh`, ADR-0004 strangler).
- Branche de travail : **`develop`**. Push final → `origin develop` (après validation locale + accord explicite, règle #13).

## Project Overview

**Facil Framework** : framework générique de plateformes de services digitaux
(gov, enterprise, SaaS, banking, telco, HR…), déployable cloud ou **on-premise souverain**,
customisable **sans code** via un Customization Studio. License **AGPL-3.0** (Open Core).

- **Origine** : snapshot du déploiement concret TaxasGE (2026-05-10), zéro lien Git/submodule.
- **Statut produit** : pré-bootstrap **côté applicatif** (Phase A.5 Module Loader pas faite) ;
  **socle infra on-premise en cours** (Phase 0 → P14 du plan infra hybride).

## Critical Rules

1. **JAMAIS de build prod manuel** — build local Docker Desktop pour dev/test uniquement
   (`docker buildx` via Bash, PAS via MCP_DOCKER qui est cassé/inutile). Prod = CI GitHub Actions → GHCR → pull serveur.
2. **Toujours vérifier avant d'agir** — interroger la BD / lire le source / tester l'endpoint. Ne rien inventer, pas de placeholder, pas de champ fantôme.
3. **Challenger les suggestions** — être l'expert, critique, sans biais.
4. **Plans par phase** — plan → impl → test fin de phase → checklist → critique honnête → auto-correct → commit local groupé → phase suivante. Push sous validation explicite.
5. **Python** : `.venv` du repo (`C:\facil_framework\.venv`) ou `C:\Program Files\Odoo 17\python\python.exe`. Tests `pytest` = vraie validation, pas self-checklist.
6. **Zéro régression cloud** — le socle on-prem doit garder la config cloud existante valide (défauts rétro-compatibles dans le seam `deploy/config`).

## Standards d'implémentation (ERP-grade) — OBLIGATOIRE

Référence complète : **`docs/ENGINEERING_STANDARDS.md`** (à lire avant tout écran/API).
Résumé impératif (toujours appliquer, sans qu'on le redemande) :

- **Backend liste** : `limit`(≤200)/`offset`/`sort`(whitelist)/`filter` structuré + **total**
  renvoyé ; scope-filtré `visible_orgs` ; jamais non borné ni cap silencieux.
- **RBAC** : chaque endpoint déclare une permission ; lecture scope-filtrée, écriture
  `enforce` sur le scope **de la cible** ; le front *reflète*, le backend tranche.
- **Auth** : statut/`is_active` enforced partout (natif + fédéré) ; suspension → **révoque les sessions**.
- **Audit** : toute mutation sensible → `audit.record` (acteur + cible).
- **Concurrence optimiste** : `updated_at`/`version` + `If-Match` → 409 sur conflit.
- **Bulk** : endpoints transactionnels, scope-enforced par item, audités, bornés (≤500).
- **Idempotence** : seeds/migrations idempotents ; SQL Postgres **gardé par dialecte** ; build = CI.
- **Frontend DataGrid** : tri colonne + filtres colonne + pagination(total) + densité + sticky +
  virtualisation + états vide/load/erreur ; **composant générique réutilisable**.
- **Master-detail / split-view** pour la config riche (dialogs = create/confirm seulement) ; deep-linkable.
- **UI permission-driven** : masquer/désactiver nav **et actions** (`/me/permissions` + `hasPerm`).
- **Données/forme** : TanStack Query (optimistic+rollback) ; **react-hook-form + zod** ; toasts.
- **Création/édition = `RecordForm` réutilisable** (ENGINEERING_STANDARDS §11bis, **OBLIGATOIRE**) :
  pas de formulaire ad-hoc par page ; rendu **adaptatif** (slide-over simple / page riche) ; validation
  **client zod + serveur pydantic** ; **`If-Match`** (concurrence optimiste) ; **422→champ / 409→reload** ;
  Save / **Save & New** / Cancel + garde dirty ; pickers recherche-serveur + inline-create ; import CSV en masse.
- **A11y AA · i18n (toute chaîne = clé en/fr/es) · perf (RSC, budget <150KB/route, cache fetch serveur) ·
  thème via `branding.*` · coque fixe / seule la data défile**.
- **Parité backend ⇄ frontend (couverture intégrale)** : l'UI expose **tout** le contrat
  d'une ressource (CRUD + actions + transitions d'état + **tous** les champs lecture/écriture +
  tri/filtres/pagination + états/erreurs 401/403/404/409/422). **Aucune capacité backend
  orpheline**, **aucun champ d'API** non rendu/éditable sans raison, **aucune UI** vers un
  endpoint/champ inexistant. Exclusions **seulement délibérées et documentées** (break-glass,
  `/health`, métriques, SCIM IdP, internes/bulk). Tout ajout backend livre son UI **dans le même lot**.
- **Tests = vraie validation** (pytest/Vitest/Playwright, gate CI) ; **réutilisation d'abord / DRY**.

## Architecture (cible)

**Monolithe modulaire** (ADR-0001), 1 DB, surfaces citoyen/agent séparées.

```text
Customization Studio (UI sans code)
        │
Module Loader (Phase A.5, clé de voûte) — MODULES_ENABLED → conditional load
        │
Backend FastAPI · Frontend Next.js · Mobile Expo
        │
Provider Abstractions (ABC pluggables) : LLM · Embedding/RAG · Storage · Auth · Payment · Signature
        │
Profiles (install.yaml + seeds + workflows + branding) : empty / private-services-company / gov-emergent-country / saas-multitenant / banking
        │
Postgres+pgvector · Redis · Ollama · MinIO · (Cloud LLM optionnel)
```

- **Inférence pluggable** OpenAI-compatible : Ollama/DMR (dev) → vLLM/TGI (échelle) — ADR-0002. Défaut souverain : Ollama (`llama3.1:8b` + `nomic-embed-text`).
- **Secrets** : OpenBao + SOPS/age en couches (ADR-0003). PKI interne = OpenBao PKI ; CA signature documents = **séparée** (`LocalCAProvider`).
- **Storage** souverain défaut : MinIO (ADR-0005).
- **Orchestration prod on-prem** : **k3s mono-nœud**, même chart Helm que cluster (ADR-0006). `docker-compose.local.yml` = dev/démo uniquement.

## Socle infra — état réel (2026-06-11)

`docker-compose.local.yml` (généré par `deploy/providers/docker_local.py`, **ne pas éditer à la main**) :

**Toujours actifs** : `postgres` (pgvector pg16) · `redis` · `minio` · `openbao` (dev) · `db-init` (one-shot) · `backend` · `frontend`.
**Profile-gated (OFF par défaut, scaffold P14)** :
- `caddy` — profil `edge` (`docker compose --profile edge up`) → reverse-proxy single-origin :8090, anti-CORS.
- `keycloak` — profil `auth` → :8088, `start-dev` H2 in-memory (NON-PROD).
- `otel-lgtm` — profil `observability` → Grafana :3001 + OTLP 4317/4318 (télémétrie souveraine self-hosted).

**Bloquants connus avant de monter le tier applicatif** :
1. `packages/{backend,web}` sont **parkés dans `legacy/packages/`** (clean-slate, ADR-0004) → contextes de build absents à la racine. Portage = Phase D.
2. `.env.deploy.gen` (backend + web) **pas encore générés** (`deploy/scripts/render_env.py` non exécuté). Le compose les charge via `env_file`.

`.env.secrets` (P1, gitignored) : 5 secrets de boot générés ; intégrations externes (Gemini/Firebase/Supabase/Sentry…) vides = dégradation propre, pas de crash.

## Documentation & plans

- **Standards d'implémentation** : `docs/ENGINEERING_STANDARDS.md` (ERP-grade, backend + frontend — résumé dans Critical Rules ci-dessus).
- **ADRs** : `docs/adr/0001…0006` (architecture, inférence, secrets, strangler, storage, k3s+PKI).
- **Architecture** : `docs/architecture/{SOCLE_GE.md, PHASE_0_DEPLOYMENT_BACKBONE.md}`.
- **Notes** : `docs/architecture-notes/{KEYCLOAK_DECISION, EIDAS_ALTERNATIVES, HYPERLEDGER_ALTERNATIVES}.md`.
- **Plans (gitignored, internes)** : `.claude/plans/` — `INFRA_HYBRID_DEPLOY_PLAN.md` (P1→P15), `PHASE_0_FOUNDATION_CHECKLIST.md`, `PHASE_P7_P8_SECRETS_PKI.md`, `VOIE_B_FRAMEWORK_PLAN.md`, `LLM_ABSTRACTION_PLAN.md`, `EMBEDDING_RAG_ABSTRACTION_PLAN.md`, `TREASURY_CAPABILITIES_UPGRADE_PLAN.md`, `phases/`.
- **Agent** : `.claude/agents/task-decomposition-expert.md` — invocable pour décomposer une phase in situ.
- **Roadmap publique** : `ROADMAP.md` (phases A→N.5, 144-209j).

## Git Commit Convention

```text
<type>(<scope>): <subject>
Types: feat, fix, docs, style, refactor, test, chore
```
Commits locaux groupés sémantiques en fin de phase. **Push = accord explicite uniquement.**
