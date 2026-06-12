# Gouvernance projet — Facil Framework

Document de référence pour le pilotage **production** du framework : standards, process agile,
critères de qualité, traçabilité. Source de vérité pour « comment on travaille ».

## 1. Alignement normatif (cibles)

> Cibles d'alignement — **pas** une déclaration de certification. Servent de grille de conception
> et d'audit.

| Domaine | Norme / référentiel | Application dans Facil |
|---------|---------------------|------------------------|
| Qualité logicielle | **ISO/IEC 25010** | Critères non-fonctionnels (perf, sécurité, maintenabilité) dans la DoD |
| Sécurité de l'information | **ISO/IEC 27001** | Gestion des secrets (ADR-0003), RBAC, audit, contrôle d'accès |
| Sécurité cloud / vie privée | **ISO/IEC 27017 / 27018** | Multi-cloud configurable, souveraineté des données |
| Description d'architecture | **ISO/IEC/IEEE 42010** | ADR (`docs/adr/`) |
| Continuité d'activité | **ISO 22301** | Sauvegarde/PITR/DR (plan P13) |
| Sécurité applicative | **OWASP ASVS** | Surfaces séparées, WAF, validation entrées (P11/P12) |
| Méthodologie build | **12-Factor App** | Config par env, stateless, logs, build/release/run |
| Versioning | **SemVer** + **Conventional Commits** | `release-please`, `commitlint` (déjà en place) |

## 2. Process agile

**Modèle** : Kanban à flux continu + jalons itératifs (hybride). Le travail est découpé en
**phases = epics** (cf roadmap), chacune livrée incrémentalement.

**Cycle d'une phase** (gate obligatoire avant la suivante) :

```text
Plan de phase -> Implémentation -> Tests -> Checklist de validation
   -> Rapport critique honnête -> Auto-correction -> Validation -> Phase suivante
```

**Definition of Ready (DoR)** — une tâche est prête si : objectif clair, dépendances connues,
critères d'acceptation définis, données/schéma BD vérifiés.

**Definition of Done (DoD)** — une tâche est terminée si :
1. Code implémenté + revu (cohérence routes/endpoints/permissions vérifiée sur l'existant).
2. Tests verts (unitaires + pertinents : pydantic/back, type-check/front).
3. Sécurité : pas de secret en clair, entrées validées, scan images sans HIGH/CRITICAL (P4).
4. Docs à jour (ADR si décision, roadmap, README de module si applicable).
5. Checklist de phase cochée + **rapport critique** écrit (gaps assumés).
6. Build **via CI** (jamais manuel) vert.

## 3. Branches, commits, CI/CD

- Branche d'intégration : `develop`. Features : `feature/**`.
- **Commits** : Conventional Commits (`feat|fix|docs|refactor|test|chore(scope): sujet`).
- **Build & déploiement** : **uniquement via GitHub Actions** — aucun build manuel (gcloud/docker).
- **Push** : sous validation explicite ; commit local par phase validée.
- Qualité en CI : lint, type-check, SAST (Semgrep/Bandit), scan images + SBOM (P4).

## 4. Traçabilité

```text
Décision  -> docs/adr/NNNN
Roadmap   -> docs/roadmap/INFRA_ROADMAP.md (phases/epics, statut)
Exécution -> .claude/plans/INFRA_HYBRID_DEPLOY_PLAN.md (checklists working)
Suivi     -> tableau de tâches (board) + milestones par phase
```

Chaque commit/PR référence l'epic (phase) et, le cas échéant, l'ADR concerné.

## 5. Rôles & cadence

- Revue de phase à chaque gate ; rapport critique archivé.
- Rétro légère en fin d'epic (ce qui a marché / dette créée / ajustements).
