# ADR-0006 — Orchestration on-prem (k3s mono-nœud) & PKI interne (OpenBao)

- **Status** : Accepted
- **Date** : 2026-06-11
- **Related** : ADR-0001 (architecture applicative), ADR-0003 (secrets & cloud), `docs/architecture/PHASE_0_DEPLOYMENT_BACKBONE.md`, `docs/architecture/SOCLE_GE.md`, `.claude/plans/INFRA_HYBRID_DEPLOY_PLAN.md` (P5/P7/P8), `.claude/plans/PHASE_P7_P8_SECRETS_PKI.md`

## Context

Un déployeur souverain installe sur **un** serveur physique aujourd'hui et doit pouvoir absorber
la croissance (objectif « millions simultanés » au niveau framework générique) **sans réécriture**.
Le plan infra opposait initialement `docker-compose.prod` (single-node) et Helm/k8s (cluster), ce
qui crée une **rupture** au passage à l'échelle. Par ailleurs la PKI interne (mTLS inter-services)
restait indécise entre `step-ca` et le moteur PKI d'OpenBao, et la relation avec la **CA de
signature documentaire** (eIDAS/PAdES, `LocalCAProvider`) n'était pas tranchée.

## Decision

1. **Orchestration on-prem prod = k3s mono-nœud.** k3s (k8s certifié CNCF, single-binary) sur le
   serveur physique souverain, faisant tourner **les mêmes charts Helm** que le cluster. La montée
   en charge = ajout de serveurs physiques (`kubectl join`) + HPA, **zéro réécriture**.
   `docker-compose` est réservé au **dev/démo** et à la validation d'images. *Honnêteté : k3s
   mono-nœud ne sert pas des millions simultanés (plafond physique) ; il supprime la rupture
   mono→cluster.*

2. **PKI interne = moteur `secrets/pki` d'OpenBao** (root + intermediate CA, émission + rotation +
   révocation), renouvellement auto via `cert-manager` (issuer OpenBao) en k3s. **step-ca écarté** :
   réutiliser OpenBao (déjà retenu pour les secrets, ADR-0003) = un seul outil souverain à opérer.

3. **CA de signature documentaire SÉPARÉE.** `LocalCAProvider` (chaîne eIDAS/PAdES) garde sa
   **propre racine** + clé privée chiffrée AES-256-GCM. **Pas de mutualisation** avec la PKI mTLS :
   la compromission de l'une n'expose pas l'autre, et la contrainte eIDAS n'est pas imposée à
   l'infra mTLS. Deux racines, deux cycles de vie.

## Consequences

**Positives** : continuité d'échelle mono→cluster sans réécriture (parité on-prem↔cloud via le même
chart) ; un seul outil secrets+PKI souverain (OpenBao) ; isolation de sécurité forte entre mTLS et
signature documentaire ; « k8s sur serveur local » répond à l'objectif souverain.

**Négatives / risques** : k3s ajoute une complexité ops vs compose nu (mitigée par le single-binary
et l'écosystème k8s) ; OpenBao scellé après reboot doit être auto-unseal (amorçage SOPS+age, cf
ADR-0003 / `PHASE_P7_P8_SECRETS_PKI.md`) ; opérer deux racines PKI distinctes.

## Alternatives — rejetées

- **`docker-compose.prod` comme cible prod single-node** — *rejeté* : cul-de-sac, migration vers
  k8s = rupture au passage à l'échelle.
- **EKS/cloud k8s d'emblée** — *rejeté* comme défaut on-prem : dépendance cloud, contraire à la
  souveraineté (conservé comme cible cloud, ADR-0003).
- **step-ca pour la PKI interne** — *rejeté* : 2e brique à opérer alors qu'OpenBao fournit déjà un
  moteur PKI.
- **Mutualiser CA signature documentaire et PKI mTLS** — *rejeté* : couplage de sécurité +
  contrainte de conformité eIDAS étendue indûment à toute l'infra.
