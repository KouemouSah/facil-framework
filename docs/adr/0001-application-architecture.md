# ADR-0001 — Architecture applicative : monolithe modulaire + split de surfaces

- **Status** : Accepted
- **Date** : 2026-06-11
- **Deciders** : Architecte / Product owner
- **Related** : `.claude/plans/INFRA_HYBRID_DEPLOY_PLAN.md` (P12), ADR-0002

## Context

Facil cible un déploiement **hybride on-premise / cloud**, multi-usage (gov, banque, SaaS,
services privés), avec une exigence de **millions d'utilisateurs simultanés** côté citoyen et
**100+ agents** d'entités côté back-office. Le code hérité (TaxasGE) est un **monolithe modulaire**
FastAPI (31 modules `api/services/repositories/models`) avec des transactions critiques mono-base
(ex. *lock-ordering* d'un paiement groupé : `commercial_licenses → service_requests →
license_obligations → service_payments` en une transaction `FOR UPDATE`).

Question posée : faut-il découper en microservices (`frontend`, `services_users`,
`services_agents`, `service_llm`) ?

## Decision

On **conserve le monolithe modulaire** comme cœur applicatif (users + agents + métier, **une base
de données**). L'isolation citoyen / agent est obtenue par un **split de surfaces** : **deux
déploiements de la même image**, avec des profils de routes/modules distincts, sur des réseaux
séparés (citoyen internet-facing ; agent intranet/VPN + mTLS). Le **frontend** (Next.js) et le
**moteur d'inférence** (cf ADR-0002) sont déjà des services séparés. L'extraction d'un module en
service est **réactive** (« monolith first »), déclenchée par un goulot prouvé (ex. worker AI
async, OCR), pas a priori.

## Consequences

**Positives**
- Intégrité transactionnelle préservée (pas de saga distribuée fragile pour le lock-ordering).
- Empreinte ressources minimale (1 runtime, 1 pool DB partagé) — décisif sur serveur souverain.
- Isolation sécurité citoyen/agent réelle (2 déploiements, défense en profondeur) sans coût microservices.
- Scaling indépendant des surfaces (réplicas publics vs agents) sans split de code.

**Négatives / risques**
- Discipline de frontières de modules requise (mitigée par le module loader, `PHASE_A5`).
- Le déploiement « 2 surfaces » impose une config de routage/modules par profil (P12).

## Alternatives

- **4 microservices (users/agents/llm/frontend)** — *rejeté* : multiplie runtime/RAM/pools DB,
  casse les transactions partagées (users et agents opèrent les mêmes tables), ajoute service
  discovery + tracing distribué + APIs versionnées, pour une équipe réduite. Bénéfices réels
  (frontend, inférence) déjà obtenus par séparation existante.
