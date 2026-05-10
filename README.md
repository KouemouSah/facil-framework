# Facil Framework

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Status: pre-bootstrap](https://img.shields.io/badge/status-pre--bootstrap-orange)](ROADMAP.md)
[![CI](https://github.com/KouemouSah/facil-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/KouemouSah/facil-framework/actions/workflows/ci.yml)
[![CodeQL](https://github.com/KouemouSah/facil-framework/actions/workflows/codeql.yml/badge.svg)](https://github.com/KouemouSah/facil-framework/actions/workflows/codeql.yml)

> ⚠️ **Statut : pré-bootstrap** — l'environnement est préparé, le développement actif n'a pas encore démarré. Le lancement est conditionné au go-live de [TaxasGE](https://github.com/KouemouSah/taxasge) (le déploiement de référence) + recrutement équipe + vérification trademark.

**Facil Framework** est un framework générique de plateformes de services digitaux (gov, entreprise privée, multi-tenant SaaS, banking, télécom, e-commerce, RH, immobilier...), déployable sur n'importe quel cloud ou en local, et **customisable sans code** par des utilisateurs non-techniques via un Customization Studio dédié.

---

## Table des matières

- [Vision](#vision)
- [Modèle économique](#modèle-économique-open-core)
- [Architecture](#architecture)
- [5 profiles pré-faits](#5-profiles-pré-faits)
- [Quick start (futur)](#quick-start-futur)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contribuer](#contribuer)
- [License](#license)

---

## Vision

- **Tous les modules** backend inclus, **activables/désactivables** au boot via config `MODULES_ENABLED` (cf. Phase A.5)
- **5 profiles pré-faits** sélectionnables au déploiement : un profile = 1 pack `install.yaml` + seeds + workflows + branding
- **Customization Studio** UI admin pour personnaliser sans code : branding, langues (auto-translate via LLM), RBAC, taxonomies, catalogue, workflows (drag-drop designer), providers (LLM / Storage / Payment / Auth), templates de documents, signature électronique, knowledge base
- **Default cloud-privé / on-prem** : Ollama local (LLM + embeddings), Postgres + pgvector, MinIO storage. Zéro dépendance cloud externe requise.
- **18 améliorations majeures** vs TaxasGE (cf. [docs/IMPROVEMENTS_OVER_TAXASGE.md](docs/IMPROVEMENTS_OVER_TAXASGE.md))

## Origine

Cloné en snapshot du déploiement concret **TaxasGE** (Guinée Équatoriale gov digital services, repo séparé) en date du 2026-05-10.

Aucun lien Git, ni submodule, ni symlink avec TaxasGE — les deux repos évoluent indépendamment. La diffusion d'améliorations infrastructure se fait par cherry-pick manuel via `tools/sync-from-taxasge.sh` (à créer Phase A.5).

## Modèle économique (Open Core)

| Tier | Description | License | Status |
|------|-------------|---------|--------|
| **Facil Framework** | Ce repo, self-hosted, AGPL-3.0 | AGPL-3.0 | 📋 Planned |
| **Facil Cloud** | SaaS managé sur `facil.io` | Hosted, payant | 📋 Future |
| **Facil Enterprise** | License commerciale (SSO SAML/AD, multi-tenant strict, SLA 24/7, support certifié) | Commercial | 📋 Future |

Choix AGPL-3.0 (et pas MIT) → empêche fork hostile cloud type Elastic vs OpenSearch / AWS. Tout SaaS hébergeur doit ouvrir ses modifications.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Customization Studio (UI)                │
│  Branding · Langues · RBAC · Taxonomies · Catalog ·         │
│  Workflow Designer · Providers · Documents · Signature · KB │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Module Loader (Phase A.5)                │
│              MODULES_ENABLED → conditional load              │
└──────────────────────────┬──────────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
   ┌───▼────┐        ┌─────▼─────┐       ┌────▼────┐
   │Backend │        │ Frontend  │       │ Mobile  │
   │FastAPI │        │ Next.js   │       │  Expo   │
   └───┬────┘        └─────┬─────┘       └────┬────┘
       │                   │                   │
       └─────────┬─────────┴────────┬──────────┘
                 │                  │
   ┌─────────────▼─────────┐  ┌─────▼──────────────┐
   │  Provider Abstractions │  │  Profile templates │
   │  LLM · Storage · Auth  │  │   gov / private /  │
   │  Payment · Signature   │  │  saas / banking /  │
   │   · Embedding/RAG      │  │       empty        │
   └────────────────────────┘  └────────────────────┘
                 │
   ┌─────────────▼─────────────────────────────────────┐
   │  Postgres + pgvector  ·  Redis  ·  Ollama  ·      │
   │  MinIO / S3 / Firebase  ·  Cloud LLM (optional)   │
   └────────────────────────────────────────────────────┘
```

Voir [docs/BPMN.md](docs/BPMN.md) pour les diagrammes de processus détaillés (déploiement, customization, workflow execution, module activation, migration, designer).

## 5 profiles pré-faits

| Profile | Use case | Modules typiques |
|---------|----------|-----------------|
| `empty` | Démarrage from scratch | rbac · communications · audit_logs · dashboards |
| `private-services-company` | Plateforme B2B services (cible MVP) | + treasury · service_requests · chatbot · documents · verified_identifiers |
| `gov-emergent-country` | Services gov digitaux (port TaxasGE) | + declarations · bange_payment · permis · IVA |
| `saas-multitenant` | SaaS multi-tenant | + tenant_management · billing · onboarding |
| `banking` | KYC + lending | + kyc · loan_application · compliance |

Un déploiement = 1 profile actif. Profile changeable post-installation via Studio (avec migration).

## Quick start (futur)

> 🚧 Pas encore exécutable — Phase A.5 (Module Loader) doit être implémentée d'abord.

```bash
# 1. Clone
git clone https://github.com/KouemouSah/facil-framework.git
cd facil-framework

# 2. Choisir un profile et déployer en local
cd deploy
python init.py --profile=private-services-company --non-interactive
docker compose up

# 3. Ouvrir le Studio
open http://localhost:3000/admin/studio
```

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour le setup de développement complet.

## Documentation

| Document | Audience | Contenu |
|----------|----------|---------|
| [PRD](docs/PRD.md) | Product / stakeholders | Product Requirements Document complet (12 sections) |
| [BPMN](docs/BPMN.md) | Devs / architects | 6 diagrammes de processus Mermaid |
| [REUSE_FROM_TAXASGE](docs/REUSE_FROM_TAXASGE.md) | Devs | Inventaire 60% reused / 25% adapted / 15% new |
| [IMPROVEMENTS_OVER_TAXASGE](docs/IMPROVEMENTS_OVER_TAXASGE.md) | Tech leaders | 18 pain points TaxasGE résolus par Voie B |
| [ROADMAP](ROADMAP.md) | Public | Phases A → N.5, effort, statut |
| [CHANGELOG](CHANGELOG.md) | Tous | Notable changes per release |
| [CONTRIBUTING](CONTRIBUTING.md) | Contributors | Branching, commits, dev setup |
| [SECURITY](SECURITY.md) | Security researchers | Disclosure policy + scope |
| [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md) | Tous | Contributor Covenant 2.1 |

Plans détaillés internes (gitignored, format task-decomposition-expert) — `.claude/plans/phases/PHASE_*.md` × 19 phases.

## Roadmap

Voir [ROADMAP.md](ROADMAP.md) pour le détail. Résumé :

- **Total** : 144-209 jours de dev focalisé (~7-10 mois 1 FTE ou 4-6 mois 2 devs)
- **Foundations** : A.5 Module Loader · B LLM · B.5 Payment · B.6 Embedding/RAG · C Storage
- **Studio** : D Profiles · E Backend · F Branding/Lang/RBAC · G Taxonomies/Catalog · H Workflow Designer ⭐ · H.5 Module Manager · I Providers · I.bis Knowledge Base
- **Auth & Apps** : J Auth Providers · K Mobile/Inspector
- **Documents** : N Designer + Schemas · N.5 Signature (LocalCA + Cloud)
- **Tests & Docs** : L E2E par profile · M Documentation

Phase critique R&D : **H Workflow Designer** (15-25j drag-drop ReactFlow).
Phase la plus longue : **B.6 Embedding/RAG Abstraction** (32-45j).

## Contribuer

Le repo est en **mode privé** pendant la phase pré-bootstrap. Les contributions externes ouvriront avec la Phase A.5.

En attendant :

- ⭐ Star pour notifications de release
- 💬 [Discussions](https://github.com/KouemouSah/facil-framework/discussions) pour idées et questions
- 🐛 [Issues](https://github.com/KouemouSah/facil-framework/issues) pour bugs et feature requests
- 🔒 [SECURITY.md](SECURITY.md) pour vulnérabilités

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour le guide complet.

## Pré-requis avant lancement actif

| Pré-requis | Status |
|------------|--------|
| TaxasGE prod stable 1+ mois | ⏳ |
| Trademark "Facil" vérifié (USPTO / EUIPO / OAPI) | ⏳ |
| Équipe : 1 FTE 8 mois OU 2 devs 4-5 mois | ⏳ |
| Domaine `facil.io` acquis | ⏳ |
| Setup business (société, infra cloud) | ⏳ |
| Décisions stratégiques validées (PRD §11) | ⏳ |

## License

[AGPL-3.0](LICENSE) (Affero GPL).

Tout SaaS hébergeur de modifications doit publier son code source sous AGPL également.

Pour un usage commercial sans contrainte AGPL, voir le tier **Facil Enterprise** (futur, contact : libressai@gmail.com).

---

<sub>Made with care · 2026 · libressai@gmail.com</sub>
