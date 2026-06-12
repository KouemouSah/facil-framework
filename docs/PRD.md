# Facil Framework — Product Requirements Document (PRD)

> **Version** : 0.1 (draft)
> **Date** : 2026-05-10
> **Statut** : pre-launch — environnement préparé, dev pas démarré
> **Auteur** : équipe stratégique TaxasGE / Voie B planning
> **Lecteurs cibles** : co-fondateurs, devs FTE, designers, marketing, investisseurs

---

## Résumé exécutif (1 page)

**Facil Framework** est un framework open-source de services digitaux structurés (gov, entreprise, SaaS, banking, télécom...), déployable sur n'importe quel cloud ou en local, et **personnalisable sans code** via une UI admin (Customization Studio).

### Problème

Les organisations qui veulent digitaliser leurs services (catalogues, workflows, demandes, paiements, validations documents) face à 3 choix mauvais :
1. **Développement custom** : 6-18 mois, 100k-500k€, risque échec
2. **SaaS verticaux fermés** (ServiceNow, Pega, Lemonway) : licence chère, vendor lock-in, pas de customization profonde
3. **Frameworks low-code** (Odoo, Mendix, OutSystems) : courbe d'apprentissage forte, dépendances propriétaires

### Solution

Un framework **open-source AGPL-3.0** pré-équipé avec :
- Tous les modules génériques (RBAC, workflows, catalogue, RAG chatbot, payments, communications, audit, dashboards)
- 5 profiles pré-configurés par domaine (gov, enterprise services, SaaS, banking, empty)
- **Customization Studio** UI pour personnaliser sans code (branding, langues, rôles, taxonomies, catalogue, workflows, providers IA/storage/payment)
- Apps mobile + inspector incluses, customisables par profile
- Déployable en 30 minutes (Docker local) ou sur n'importe quel cloud public/privé

### Modèle économique

**Open Core + Cloud SaaS hybride** :
- `Facil Framework` (AGPL-3.0, gratuit, self-hosted)
- `Facil Cloud` (SaaS payant ~10-30€/user/mois)
- `Facil Enterprise` (license commerciale, SSO SAML/AD, multi-tenant strict, support 24/7)

### Marché cible

- **Court terme** (an 1) : gov de pays émergents (modèle TaxasGE/Guinée Équatoriale réussit)
- **Moyen terme** (an 2-3) : entreprises de services privées (B2C/B2B), SaaS multi-tenant
- **Long terme** (an 3+) : banking, télécom, e-commerce, RH, immobilier

### Différenciation

- **Open-source réel** (pas demo crippled) avec license AGPL-3.0
- **Multi-domaine** par profile (vs verticaux fermés monodomaine)
- **AI native** : RAG chatbot inclus, LLM swappable (Gemini/Claude/Mistral/Ollama)
- **Cloud-agnostic** : tourne sur Postgres + Ollama local, sans dépendance Vertex AI
- **Mobile + inspector inclus** (vs frameworks web-only)

### Effort

**8 mois** 1 dev FTE OU 4-5 mois 2 devs (estimation basée sur expérience Strapi/N8N/Mattermost).

---

## 1. Vision produit

### 1.1 Mission

Démocratiser la création de plateformes digitales métier complexes (gov, enterprise, SaaS) en fournissant un framework open-source pré-équipé, personnalisable sans code, et déployable n'importe où.

### 1.2 Vision long terme (5 ans)

Devenir le **"Strapi des frameworks métier"** — la référence open-source pour quiconque veut bâtir une plateforme digitale gouvernementale, d'entreprise ou multi-tenant en quelques jours plutôt qu'en mois.

Indicateurs cibles fin année 2 :
- 1 000+ déploiements actifs (community edition)
- 50+ clients Cloud
- 5+ clients Enterprise
- 10k+ stars GitHub
- 50+ contributeurs

### 1.3 Principes directeurs

1. **Open par défaut** — code, doc, roadmap publics
2. **No code first, code escape hatch** — UI Studio pour 95% des cas, code Python/TypeScript pour les 5% restants
3. **Cloud-agnostic** — fonctionne en local, AWS, GCP, Azure, on-prem
4. **AI-native** — RAG chatbot, workflow assist, LLM swappable
5. **Mobile-ready** — apps Expo customisables par profile
6. **Standards-first** — Postgres + pgvector, OpenAPI, Docker, OAuth — pas de stack propriétaire

---

## 2. Marché et concurrence

### 2.1 Taille du marché

- **Marché global low-code/no-code** (2025) : ~50 G€, croissance 25%/an (Gartner)
- **Sous-segment "metier-specific frameworks"** : ~5 G€ accessible
- **Cible immédiate (gov digital services pays émergents)** : ~500 M€

### 2.2 Concurrents directs

| Concurrent | Position | Force | Faiblesse | Notre angle |
|---|---|---|---|---|
| **Strapi** | CMS headless OSS | Communauté forte, plugins | Pas mobile, pas workflow complexe | Multi-domaine + mobile + workflow designer |
| **N8N** | Workflow automation OSS | Workflow designer mature | Pas de catalogue/RBAC/UI app | Plateforme complète, pas juste workflows |
| **Odoo Community** | ERP modulaire OSS | 30+ apps modules, écosystème | Tech stack vieillissante (Python 2 héritage), dependency proprio | Stack moderne (Python 3.11+, FastAPI, Next.js, Expo), AI-native |
| **Mendix / OutSystems** | Low-code enterprise | Mature, gros clients | Cher, propriétaire, pas open | Open-source, déployable n'importe où |
| **Camunda Modeler** | BPM workflow | Workflow execution mature | Pas full stack, pas mobile | Plateforme intégrée |
| **Strapi + N8N + Camunda** combinés | DIY composition | Flexibilité | Aucun support unifié, intégration manuelle | Tout intégré + Studio unifié |

### 2.3 Risques concurrentiels

- **Strapi étend vers workflows** → notre USP "multi-domaine intégré" doit rester clair
- **Odoo modernise sa stack** → garder l'avance tech (AI native, k8s native)
- **Cloud providers (AWS/GCP) lancent du low-code natif** → notre force = open-source + multi-cloud

---

## 3. Personas

### 3.1 Persona Primaire — Marie, CTO d'un gouvernement émergent

- **Contexte** : pays africain/sud-américain, doit digitaliser 50+ services administratifs
- **Pain** : budget limité, équipe tech 5-10 devs, pas de framework adapté
- **Objectif** : déployer une plateforme citoyenne en 6 mois max
- **Decision criteria** : open-source, customizable, multi-langues, marche localement
- **Use case Facil** : profile `gov-emergent-country`, customise via Studio (logo, langues locales, taxonomies ministères)

### 3.2 Persona Secondaire — Karim, fondateur startup B2B services

- **Contexte** : startup 5 personnes, vend un service (ex: comptabilité externalisée)
- **Pain** : pas le temps de coder une plateforme client, mais SaaS standards trop chers
- **Objectif** : MVP en 1 mois pour démontrer aux investisseurs
- **Decision criteria** : déploiement rapide, white-labelable, Stripe payment intégré
- **Use case Facil** : profile `private-services-company`, déploiement Docker local + Stripe

### 3.3 Persona Tertiaire — Sandra, dev senior dans entreprise corporate

- **Contexte** : DSI d'une entreprise 1000+ employés, doit lancer un nouveau service interne
- **Pain** : Mendix/OutSystems trop chers, dev custom trop long
- **Objectif** : fonctionnel en 3 mois, fork si nécessaire
- **Decision criteria** : open-source, audit-friendly, modifiable
- **Use case Facil** : Enterprise license avec SSO SAML AD, déployé on-prem

### 3.4 Persona — Luis, agent IA marketing autonome

- **Contexte** : équipe marketing 100% IA, automatise SEO/content/community
- **Pain** : doit comprendre le produit pour communiquer, pas de docs UX-friendly
- **Objectif** : générer 10+ articles/mois, animer GitHub Discussions, répondre aux issues
- **Decision criteria** : doc structurée parsable, exemples clairs
- **Use case Facil** : alimente la doc avec son propre content, surveille adoption metrics

---

## 4. Architecture technique high-level

### 4.1 Stack

| Couche | Technologie | Justification |
|---|---|---|
| Backend | Python 3.11+ / FastAPI / asyncpg | Mature, performant, AI-friendly |
| Frontend Web | Next.js 14 / React 18 / TypeScript / Shadcn/UI | Standard 2026 |
| Mobile | Expo SDK 51 / React Native / TypeScript | Cross-platform, EAS Build |
| Inspector | Expo SDK 51 (offline-first) | Field agent app |
| Database | Postgres 14+ avec extension pgvector | Tourne partout, vector search natif |
| Cache | Redis 7 | Standard |
| LLM | Configurable (Gemini/Claude/Mistral/OpenAI/Ollama) | Cloud ou local |
| Embeddings | Configurable (Vertex/OpenAI/Ollama/SentenceTransformers) | Cloud ou local |
| Storage | Configurable (Firebase/S3/MinIO/Local/Supabase) | Cloud ou local |
| Auth | JWT (default) / OAuth / SAML / Magic links / OTP | Multi-provider |
| Container | Docker / Compose v2 | Standard |
| Orchestration cible | Cloud Run / ECS / k8s / Compose local | Multi-cloud |

### 4.2 Module loader (clé de voûte)

```text
app/main.py boot:
  enabled = settings.MODULES_ENABLED
  for module in enabled:
    importlib.import_module(f"app.modules.{module}.api...")
    app.include_router(...)
```

Sidebar web + écrans mobile filtrent dynamiquement selon `/api/v1/system/enabled-modules`.

### 4.3 Profile = pack config + seeds + workflows + branding

```yaml
modules:
  enabled: [rbac, treasury, verified_identifiers, ...]
seeds: [roles.sql, workflow_templates.json]
branding: { app_name, primary_color, ... }
mobile_enabled: true
llm_provider: ollama
storage_provider: minio
payment_gateway: stripe
```

### 4.4 Customization Studio

UI admin sous-domaine `/customize/*` :
- 11 pages (branding, languages, rbac, taxonomies, catalog, workflows, llm, storage, payment, auth, knowledge-base)
- 3 niveaux d'ingestion : profile templates / Excel bulk / UI granulaire
- Live preview, audit log, rollback, test mode

---

## 5. Roadmap (8 mois 1 FTE)

### Phase 1 — Fondations (mois 1-2)
- Bootstrap repo (✅ fait dans cette session de prep)
- Module Loader mechanism
- LLM Abstraction (sous-plan dédié, ~50j effort)
- Embedding/RAG Abstraction (sous-plan dédié, ~40j effort)
- Storage Abstraction
- Profile `private-services-company` MVP

### Phase 2 — Studio core (mois 3-4)
- Customization Studio backend (endpoints)
- Studio UI : Branding + Languages + RBAC
- Studio UI : Taxonomies + Catalog
- Tests E2E profile MVP

### Phase 3 — Workflow Designer (mois 5-6)
- Drag-drop workflow editor (ReactFlow ou similaire)
- DSL conditions
- Test mode
- JSON/YAML import/export
- Studio UI Workflow Designer

### Phase 4 — Providers + apps (mois 7)
- Studio UI : LLM, Storage, Payment, Auth, Knowledge Base
- Mobile/Inspector adaptations (branding, écrans conditionnels)
- 4 autres profiles (gov, saas, banking, empty)

### Phase 5 — Lancement (mois 8)
- Tests E2E par profile
- Documentation complète + tutoriels (5 par profile)
- Site marketing facil.io
- Lancement public + GitHub
- Setup Cloud SaaS

---

## 6. User stories par profile

### 6.1 Profile `private-services-company` (priority MVP)

- **Karim, fondateur startup** : "Je veux installer Facil sur mon serveur OVH, customiser le branding aux couleurs de ma startup, configurer mes 3 services (audit fiscal / paie / consulting RH), accepter Stripe payments — tout ça en 2 jours"
- **Marie, comptable de Karim** : "Je veux émettre des certificats à mes clients qui sont validés automatiquement par le système quand un client les présente"
- **Client B2B de Karim** : "Je veux demander un service via le portail web, payer en ligne, recevoir mes documents par email, suivre l'avancement"

### 6.2 Profile `gov-emergent-country` (TaxasGE actuel)

- **Marie, CTO gov** : "Je veux déployer Facil pour mon ministère des finances avec ses 11 ministères, ses 850 services fiscaux, 3 langues officielles, BANGE Mobile Money — en 2 mois"
- **Citoyen** : "Je veux faire ma demande de passeport en ligne, payer la tasa, télécharger mon récépissé"
- **Agent ministère** : "Je veux valider les paiements de la file d'attente avec SLA, gérer les escalations"

### 6.3 Profile `saas-multitenant`

- **Founder SaaS** : "Je veux offrir une plateforme white-label à 50 PME clientes, chacune avec son sous-domaine, ses workflows, ses langues, son branding"

### 6.4 Profile `banking`

- **Banque digital** : "Je veux digitaliser mes parcours d'ouverture compte / KYC / souscription crédit, intégrer mes scoring engines existants, respecter compliance"

### 6.5 Profile `empty`

- **Dev avancé** : "Je veux partir from-scratch avec juste l'infra (auth, RBAC, deploy) et coder mon métier au-dessus"

---

## 7. Critères de succès / KPIs

### 7.1 Technique

- ✅ Test coverage ≥ 80%
- ✅ E2E test passe pour chaque profile
- ✅ Déploiement Docker local : < 30 min from clone to functional
- ✅ Latence API p99 < 500ms (charges normales)
- ✅ Zero downtime deploy en prod

### 7.2 Adoption

| Métrique | Mois 6 | An 1 | An 2 |
|---|---|---|---|
| GitHub stars | 500 | 5,000 | 15,000 |
| Déploiements actifs | 50 | 1,000 | 10,000 |
| Contributors | 5 | 30 | 100 |
| Clients Cloud | 5 | 50 | 300 |
| Clients Enterprise | 0 | 5 | 30 |

### 7.3 Business

| Métrique | Mois 6 | An 1 | An 2 |
|---|---|---|---|
| MRR Cloud | 0 | 50k€ | 500k€ |
| ARR Enterprise | 0 | 100k€ | 1M€ |
| Burn rate | -20k€/mois | -50k€/mois | break-even |

---

## 8. Risques + mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| **Workflow Designer trop complexe** (Phase 3) | Élevée | Élevé | Quick win YAML import en MVP, drag-drop en V1.1 |
| **Adoption lente vs Strapi établi** | Moyenne | Élevé | Différenciation claire (multi-domaine, mobile, AI). Marketing fort |
| **Fork hostile cloud** | Moyenne | Moyen | License AGPL-3.0 (pas MIT) |
| **Trademark "Facil" non disponible** | Élevée (nom courant) | Moyen | Vérification USPTO/EUIPO/OAPI AVANT lancement public. Nom alternatif réservé |
| **Modèle Cloud SaaS overhead operational** | Moyenne | Moyen | Build sur PaaS (Cloud Run / Render) au début |
| **Burnout équipe sur Phase 3 R&D** | Élevée | Élevé | Workflow designer = 1 dev full-focus 2 mois, pas split |
| **Effort sous-estimé** | Moyenne | Moyen | Buffer 30% intégré (123-178j range) |
| **TaxasGE prod retardée par Voie B** | Élevée | Élevé | **Voie B démarre POST-go-live** strict, pas avant |

---

## 9. Modèle économique détaillé

### 9.1 Tier 1 — Facil Framework (gratuit)

- Tout le code (backend, web, mobile, inspector, deploy)
- Tous les modules génériques
- Studio basique (branding, languages, rbac, taxonomies, catalog, workflows YAML import)
- 5 profiles pré-faits
- License AGPL-3.0

### 9.2 Tier 2 — Facil Cloud (SaaS payant)

- Hébergé sur facil.io (AWS/GCP)
- Backup auto, monitoring, scaling
- Updates auto-appliqués
- 1-click deploy
- Support email
- **Pricing** : free 14 jours / 10€/user/mois (5+ users) / 30€/user/mois Enterprise plan

### 9.3 Tier 3 — Facil Enterprise (License commerciale)

- Modules Enterprise : SSO SAML, AD/LDAP, audit compliance avancé, multi-tenant strict, white-label complet
- Support 24/7 SLA 99.9%
- Account manager dédié
- Custom modules développés sur devis
- Possibilité on-prem ou cloud privé client
- **Pricing** : sur devis, ~50k-500k€/an selon taille

### 9.4 Mix revenus cibles an 2

- Cloud SaaS : 60% du revenu (recurring)
- Enterprise : 35% du revenu (gros tickets)
- Services pro / formation : 5%

---

## 10. Équipe attendue

### 10.1 Phase 1 (mois 1-2) — Bootstrap

- 1 **Dev fullstack senior** (backend Python + frontend Next.js) — lead tech
- 0.5 **Designer UI/UX** — Studio mockups + branding system
- 1 **Agent IA marketing** (configuré Claude Sonnet/GPT-4) — content, GitHub presence

### 10.2 Phase 2-3 (mois 3-6) — Core dev

- 2 **Dev fullstack** — l'un sur backend abstractions / l'autre sur Studio UI
- 1 **Dev frontend specialized** sur Workflow Designer (Phase 3)
- 1 **DevOps** part-time — CI/CD, multi-cloud testing
- 1 **Agent IA marketing** — community building

### 10.3 Phase 4-5 (mois 7-8) — Lancement

- + 1 **Dev mobile** — Expo apps adaptations
- + 1 **QA / Tester** — E2E par profile
- + 1 **Tech writer** ou **Agent IA docs** — tutoriels, vidéos, blog
- 1 **Sales / BD** part-time — premiers clients Enterprise

### 10.4 Coût équipe estimé

- Devs senior FTE Europe : ~80-120k€/an chacun
- Phase 1-3 (6 mois, 2-3 FTE) : ~150k€
- Phase 4-5 (2 mois, 5 FTE) : ~100k€
- **Total dev équipe** : ~250k€
- + Marketing / agents IA : ~30k€
- + Infra Cloud testing : ~10k€
- **Budget total an 1** : ~300k€

---

## 11. Décisions stratégiques à valider AVANT lancement

| # | Décision | Status | À valider par |
|---|---|---|---|
| 1 | Engagement temps : 8 mois 1 FTE OU 4-5 mois 2 devs | ✅ Validé user 2026-05-10 | — |
| 2 | Modèle économique : Open Core + Cloud + Enterprise | ✅ Validé | — |
| 3 | License : AGPL-3.0 | ✅ Validé | — |
| 4 | Brand "Facil Framework" : disponibilité trademark | ⏳ À vérifier | Avocat IP |
| 5 | Domain `facil.io` | ⏳ À acquérir | Founder |
| 6 | Société : nom légal, structure (SAS/Inc/Ltd) | ⏳ À créer | Founder + comptable |
| 7 | Capital initial : seed round ou bootstrap ? | ⏳ À décider | Founder |
| 8 | Stack tech : Python/Next.js/Expo confirmé | ✅ Hérité TaxasGE | — |
| 9 | TaxasGE en prod stable | ⏳ Pré-requis | Équipe TaxasGE |
| 10 | Équipe recrutée | ⏳ À sourcer | Founder + RH |

---

## 12. Annexes

### 12.1 Plans détaillés (internes, gitignored dans `.claude/plans/`)

- `VOIE_B_FRAMEWORK_PLAN.md` — plan parent technique 18 phases
- `LLM_ABSTRACTION_PLAN.md` — sous-plan LLM swap
- `EMBEDDING_RAG_ABSTRACTION_PLAN.md` — sous-plan RAG provider-agnostic

### 12.2 Origine

Ce framework est dérivé de **TaxasGE** (Guinée Équatoriale gov digital services), repo séparé sur disque (`C:\taxasge\`). Le snapshot a été pris le **2026-05-10**.

TaxasGE continuera comme **déploiement de référence** (profile `gov-emergent-country`) — toute amélioration TaxasGE peut être cherry-picked dans Facil Framework via `tools/sync-from-taxasge.sh`.

### 12.3 Contact + suivi

- **Repo principal** : `C:\facil_framework\` (à pousser sur GitHub futur)
- **Plans + mémoire** : `.claude/plans/` + `~/.claude/projects/C--facil-framework/memory/`
- **Documentation** : `docs/` (cf. ce PRD + futurs tutoriels)

---

**Fin du PRD v0.1**

Document vivant — sera mis à jour à chaque jalon majeur.
