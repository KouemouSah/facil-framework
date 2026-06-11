# ADR-0004 — Refonte incrémentale par Strangler Fig (legacy tracké + .dockerignore)

- **Status** : Accepted
- **Date** : 2026-06-11
- **Related** : ADR-0001 (monolithe modulaire), `PHASE_A5_MODULE_LOADER.md`

## Context

Le code est hérité de TaxasGE et fera l'objet d'une **refonte importante** vers le framework
multi-usage Facil. On veut **builder/valider étape par étape**, sans traîner ni rebuilder tout le
legacy d'un coup, et **sans dette**. Proposition initiale : déplacer `packages/` dans un dossier
**gitignored** non-buildé.

## Decision (affinée 2026-06-11 — reconstruction propre)

On applique le pattern **Strangler Fig en reconstruction propre** :

1. **TOUT `packages/` (backend, web, mobile, inspector) est déplacé dans `legacy/`** — **tracké**
   (git, historique préservé) mais **jamais buildé ni importé** (hors des contextes de build
   `./packages/*`). `legacy/` = **référence** consultable.
2. On **reconstruit un `packages/` neuf et minimal**, en **intégrant progressivement** depuis
   `legacy/`, module par module, **avec revue/optimisation du code ET du schéma de base de
   données** — la BD est **redessinée**, pas réutilisée telle quelle.
3. **Cœur minimal de départ** : un backend qui boote (`/health` + config + pool DB), puis
   intégration de `auth + users` (+ deps dures `permissions`/`communications`/`translations`,
   cf analyse de couplage), chacun revu/optimisé.
4. Chaque intégration : conçue (informée par legacy) -> implémentée -> testée -> validée -> commit.
   Le module-loader (Phase A.5) + profils pilotent l'activation.

## Consequences

**Positives**
- On ne builde que ce qui est nécessaire (`.dockerignore`), **sans** perdre le contrôle de version.
- Refonte incrémentale traçable, réversible (git), validée pièce par pièce -> zéro dette.

**Négatives / risques**
- **Ampleur** : reconstruction majeure (réf. VOIE_B, ~144-209 j). Pas un re-config, un re-build.
- La **BD est redessinée** : les migrations/baseline héritées deviennent *référence*, pas vérité.
  Risque de régression fonctionnelle si une subtilité métier du legacy est perdue -> revue par module.
- Extraire/réintégrer depuis un monolithe couplé exige l'**analyse de couplage** (faite :
  `auth` -> `permissions`/`communications`/`translations` en dur). Sous-estimer = boot cassé.
- Le module-loader (A.5) n'est pas encore implémenté ; un registre minimal peut être requis.

## Alternatives — rejetées

- **Déplacer `packages/` dans un dossier gitignored** — *rejeté* : perte du contrôle de version
  pendant l'activité la plus risquée (refonte) ; casse CI/deploy/profils ; le code n'est plus dans
  le repo.
- **Tout builder, ne rien déplacer** — *rejeté* : traîne tout le legacy dans chaque image et build.
