<div align="center">

<img src=".github/assets/logo.png" alt="Facil Framework" width="320"/>

# Facil Framework

**Generic deployable framework for digital services platforms.**
Gov · Enterprise · SaaS · Banking · Telco · HR · Real estate · E-commerce

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Status](https://img.shields.io/badge/status-pre--bootstrap-orange)](ROADMAP.md)
[![CI](https://github.com/KouemouSah/facil-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/KouemouSah/facil-framework/actions/workflows/ci.yml)
[![Roadmap](https://img.shields.io/badge/roadmap-19_phases_A→N.5-purple)](ROADMAP.md)
[![Effort](https://img.shields.io/badge/effort-144--209_days-lightgrey)](ROADMAP.md)

[Vision](#vision) · [Architecture](#architecture) · [Profiles](#profiles) · [Roadmap](#roadmap) · [Documentation](#documentation) · [Contributing](#contribuer)

</div>

---

> <img src=".github/assets/icons/alert-triangle.svg" width="14" alt="warning"/> &nbsp;**Statut (2026-06-11) : socle infra & configuration EN COURS.** Le **data-plane souverain** est provisionné et durci (Postgres least-privilege · Redis auth · MinIO WORM + SA scopé · OpenBao kv/AppRole), via une **couche bootstrap idempotente mode-aware** et un **wizard de déploiement** multi-cibles (docker-local/vps/gcp/aws/azure) avec catalogue de providers pluggables (auth multi-méthodes par surface · multi-LLM par tâche · BD managée). **Tier applicatif** (backend/frontend, config-store admin, Module Loader) = **Phase D, à venir**. Lancement produit conditionné au go-live TaxasGE + équipe + trademark.

**Facil Framework** est un framework générique de plateformes de services digitaux, déployable sur n'importe quel cloud ou en local, **customisable sans code** par des utilisateurs non-techniques via un Customization Studio dédié.

---

## Table des matières

1. [Vision](#vision)
2. [Origine](#origine)
3. [Modèle économique](#modèle-économique-open-core)
4. [Architecture](#architecture)
5. [Profiles](#profiles)
6. [Quick start](#quick-start-futur)
7. [Documentation](#documentation)
8. [Roadmap](#roadmap)
9. [Pré-requis avant lancement](#pré-requis-avant-lancement-actif)
10. [Contribuer](#contribuer)
11. [License](#license)

---

## Vision

| Principe | Implementation |
|---|---|
| **Modulaire au boot** | Tous les modules backend inclus, activables via `MODULES_ENABLED` (Phase A.5) |
| **5 profiles pré-faits** | Pack `install.yaml` + seeds + workflows + branding par cible métier |
| **Studio sans code** | UI admin pour branding, langues, RBAC, taxonomies, catalogue, workflows, providers, documents, signature, KB |
| **Cloud-privé / on-prem par défaut** | Ollama + Postgres+pgvector + MinIO. Zéro dépendance Cloud externe requise |
| **Provider-agnostic** | LLM, Storage, Payment, Auth, Embedding, Signature : tous abstractions ABC pluggables |
| **18 améliorations vs TaxasGE** | Voir [docs/IMPROVEMENTS_OVER_TAXASGE.md](docs/IMPROVEMENTS_OVER_TAXASGE.md) |

## Origine

Cloné en snapshot du déploiement concret **TaxasGE** (Guinée Équatoriale gov digital services, repo séparé) en date du **2026-05-10**.

- Aucun lien Git, ni submodule, ni symlink avec TaxasGE
- Repos évoluent indépendamment
- Diffusion d'améliorations infrastructure : cherry-pick manuel via `tools/sync-from-taxasge.sh` (Phase A.5)

## Modèle économique (Open Core)

| Tier | License | Hosting | Status |
|---|---|---|---|
| **Facil Framework** (ce repo) | AGPL-3.0 | Self-hosted | Planned |
| **Facil Cloud** (`facil.io`) | Hosted SaaS | Managé | Future |
| **Facil Enterprise** | Commercial | Managé / on-prem | Future |

> **Pourquoi AGPL-3.0 et pas MIT** : empêche le fork hostile cloud (cf. Elastic vs OpenSearch / AWS). Tout SaaS hébergeur de modifications doit ouvrir son code source aussi.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Customization Studio (UI)                │
│   Branding · Langues · RBAC · Taxonomies · Catalog ·        │
│   Workflow Designer · Providers · Documents · Signature ·   │
│   Knowledge Base · Modules                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│             Module Loader (Phase A.5 — clé de voûte)        │
│              MODULES_ENABLED → conditional load             │
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

### Diagramme — état réel (2026-06-11)

> ✅ implémenté & testé · ◐ partiel (validate/plan) · ○ Phase D / planifié

```mermaid
flowchart TB
  subgraph install["Installation & Configuration — ✅ socle"]
    wiz["Wizard CLI · deploy/init.py<br/>provider + profile + catalogue providers"]
    cfg["config.yaml + .env.secrets<br/>(validés Pydantic)"]
    orch["deploy.py (validate · plan · apply)"]
    prov["Providers : docker-local ✅ · gcp ✅<br/>aws ◐ · azure ◐ (App Runner / Container Apps)"]
    boot["Bootstrap data-plane ✅<br/>idempotent · mode-aware"]
    wiz --> cfg --> orch --> prov --> boot
  end

  subgraph data["Data-plane souverain — ✅ provisionné & durci"]
    pg["Postgres · scram<br/>rôle facil_app least-priv"]
    rd["Redis · requirepass"]
    mi["MinIO · WORM/Object-Lock<br/>lifecycle · SA scopé"]
    ob["OpenBao · kv-v2 · AppRole<br/>secrets runtime centralisés"]
  end
  boot --> data

  subgraph catalog["Catalogue providers pluggables (seam ✅ · intégrations ○)"]
    au["Auth par surface, multi-méthodes<br/>native·keycloak·oauth·oidc·ldap·saml"]
    ai["LLM multi-provider par tâche<br/>ollama·openai_compat·gemini·vertex"]
    db["BD : local·supabase·cloud_sql·rds·neon"]
    stg["Storage · Secrets · Email · Payment"]
  end
  cfg --> catalog

  subgraph app["Tier applicatif — ○ Phase D"]
    be["Backend FastAPI"]
    fe["Frontend Next.js + panneau admin / installeur web"]
    cs["Config-store BD (settings éditables admin)<br/>+ registre providers runtime"]
    ml["Module Loader (A.5) → MODULES_ENABLED"]
  end
  data -.-> app
  catalog -.-> app
  ob -. AppRole / secrets .-> be

  subgraph studio["Customization Studio — ○ planifié"]
    st["Branding · RBAC · Workflows · Documents · KB"]
  end
  app -.-> studio
```

Voir [docs/architecture/DATAPLANE_BOOTSTRAP.md](docs/architecture/DATAPLANE_BOOTSTRAP.md) et [docs/architecture/DEPLOYMENT_WIZARD.md](docs/architecture/DEPLOYMENT_WIZARD.md) pour le socle fait, et [docs/BPMN.md](docs/BPMN.md) pour les processus détaillés.

## Profiles

> Légende : ● en place · ◐ en cours · ○ planifié

| Profile | Use case | Modules typiques | Status |
|---------|----------|------------------|:---:|
| `empty` | Démarrage from scratch | rbac · communications · audit_logs · dashboards | ○ |
| `private-services-company` | Plateforme B2B services (cible MVP) | + treasury · service_requests · chatbot · documents · verified_identifiers | ○ |
| `gov-emergent-country` | Services gov digitaux (port TaxasGE) | + declarations · bange_payment · permis · IVA | ○ |
| `saas-multitenant` | SaaS multi-tenant | + tenant_management · billing · onboarding | ○ |
| `banking` | KYC + lending | + kyc · loan_application · compliance | ○ |

> 1 déploiement = 1 profile actif. Profile changeable post-installation via Studio (avec migration).

## Quick start (futur)

> <img src=".github/assets/icons/construction.svg" width="14" alt="construction"/> &nbsp;**Pas encore exécutable** — Phase A.5 (Module Loader) doit être implémentée d'abord. Voir [ROADMAP.md](ROADMAP.md).

```bash
# 1. Clone (quand le repo deviendra public)
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

### Public (committé)

| Document | Audience | Contenu |
|----------|----------|---------|
| [PRD](docs/PRD.md) | Product / stakeholders | Product Requirements Document complet (12 sections) |
| [BPMN](docs/BPMN.md) | Devs / architects | 6 diagrammes de processus Mermaid |
| [REUSE_FROM_TAXASGE](docs/REUSE_FROM_TAXASGE.md) | Devs | Inventaire 60% reused / 25% adapted / 15% new |
| [IMPROVEMENTS_OVER_TAXASGE](docs/IMPROVEMENTS_OVER_TAXASGE.md) | Tech leaders | 18 pain points TaxasGE résolus par Voie B |
| [AGENTS_AND_SECRETS](docs/AGENTS_AND_SECRETS.md) | Maintainers | AI agents, secrets, costs, model alternatives |
| [ROADMAP](ROADMAP.md) | Public | Phases A → N.5, effort, statut |
| [CHANGELOG](CHANGELOG.md) | Tous | Notable changes per release |
| [CONTRIBUTING](CONTRIBUTING.md) | Contributors | Branching, conventional commits, dev setup |
| [SECURITY](SECURITY.md) | Security researchers | Disclosure policy + scope |
| [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md) | Tous | Contributor Covenant 2.1 |

### Interne (gitignored)

Plans détaillés au format **task-decomposition-expert** : `.claude/plans/phases/PHASE_*.md` × 19 phases. Format : Executive Summary · Goal Analysis · WBS 3 niveaux 8/80 · Dependency Graph · Parallelism Map · Risk Register · Validation Checkpoints · Agent Handoff Plan.

## Roadmap

> Voir [ROADMAP.md](ROADMAP.md) pour le détail.

**Total : 144-209 jours** de dev focalisé (~7-10 mois 1 FTE ou 4-6 mois 2 devs).

| Track | Phases | Effort cumulé |
|-------|--------|---------------|
| **Foundations** | A.5 · B · B.5 · B.6 · C | 49-71j |
| **Profiles + Studio** | D · E · F · G · H · H.5 · I · I.bis | 47-67j |
| **Auth + Apps** | J · K | 12-17j |
| **Documents** | N · N.5 | 21-31j |
| **Tests + Docs** | L · M | 14-20j |

Phase critique R&D : **H Workflow Designer** (15-25j drag-drop ReactFlow).
Phase la plus longue : **B.6 Embedding/RAG Abstraction** (32-45j).

## Pré-requis avant lancement actif

> Légende : ● en place · ◐ en cours · ○ pending

| # | Pré-requis | Status |
|---|------------|:---:|
| 1 | TaxasGE prod stable 1+ mois | ○ |
| 2 | Trademark "Facil" vérifié (USPTO / EUIPO / OAPI) | ○ |
| 3 | Équipe : 1 FTE 8 mois OU 2 devs 4-5 mois | ○ |
| 4 | Domaine `facil.io` acquis | ○ |
| 5 | Setup business (société, infra cloud) | ○ |
| 6 | Décisions stratégiques validées (PRD §11) | ○ |

## Contribuer

Le repo est en **mode privé** pendant la phase pré-bootstrap. Les contributions externes ouvriront avec la Phase A.5.

En attendant :

- Star pour notifications de release
- [Discussions](https://github.com/KouemouSah/facil-framework/discussions) pour idées et questions
- [Issues](https://github.com/KouemouSah/facil-framework/issues) pour bugs et feature requests
- [SECURITY.md](SECURITY.md) pour vulnérabilités

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour le guide complet (branching, conventional commits, dev setup).

## License

[GNU AGPL-3.0](LICENSE) (Affero GPL).

Tout SaaS hébergeur de modifications doit publier son code source sous AGPL également.

Pour un usage commercial sans contrainte AGPL, voir le tier **Facil Enterprise** (futur, contact : kouemou.sah@gmail.com).

---

<div align="center">

<sub>Made with care · 2026 · kouemou.sah@gmail.com</sub>

<sub><a href="https://github.com/KouemouSah/facil-framework/blob/main/ROADMAP.md">Roadmap</a> · <a href="https://github.com/KouemouSah/facil-framework/discussions">Discussions</a> · <a href="https://github.com/KouemouSah/facil-framework/issues">Issues</a> · <a href="https://github.com/KouemouSah/facil-framework/security/policy">Security</a></sub>

</div>
