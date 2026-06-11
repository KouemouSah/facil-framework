# Architecture Decision Records (ADR)

Ce dossier consigne les **décisions d'architecture** du framework Facil, conformément à
**ISO/IEC/IEEE 42010:2022** (*Architecture description*). Chaque décision significative
(structurante, coûteuse à inverser, ou transverse) fait l'objet d'un ADR immuable.

## Format

Format **MADR** (Markdown Any Decision Record) simplifié :

- **Status** : `Proposed` | `Accepted` | `Superseded by ADR-XXXX` | `Deprecated`
- **Context** : forces en présence, contraintes, problème à résoudre.
- **Decision** : la décision prise (au présent, à la voix active).
- **Consequences** : conséquences positives **et** négatives assumées.
- **Alternatives** : options écartées + raison du rejet.
- **Related** : liens vers plan, autres ADR, issues.

## Règles

1. **Immuable** : un ADR accepté ne se modifie pas. On le *supersède* par un nouvel ADR.
2. **Numérotation** : `NNNN-titre-kebab.md`, incrémentale, jamais réutilisée.
3. **Traçabilité** : tout ADR référence le plan/issue d'origine ; le code et les
   plans référencent l'ADR (`cf ADR-0001`).

## Index

| ADR | Titre | Statut | Date |
|-----|-------|--------|------|
| [0001](0001-application-architecture.md) | Architecture applicative : monolithe modulaire + split de surfaces | Accepted | 2026-06-11 |
| [0002](0002-inference-engine.md) | Moteur d'inférence LLM pluggable (OpenAI-compatible) | Accepted | 2026-06-11 |
| [0003](0003-secrets-and-cloud-strategy.md) | Stratégie secrets (OpenBao+SOPS) & cloud (EKS/ECS, registries) | Accepted | 2026-06-11 |
| [0004](0004-strangler-incremental-rewrite.md) | Refonte incrémentale par Strangler Fig (legacy tracké + .dockerignore) | Accepted | 2026-06-11 |
| [0005](0005-storage-provider-minio.md) | Stockage : abstraction S3 + MinIO souverain (compression + dédup) | Accepted | 2026-06-11 |
| [0006](0006-onprem-orchestration-k3s-and-internal-pki.md) | Orchestration on-prem (k3s mono-nœud) & PKI interne (OpenBao) + CA signature séparée | Accepted | 2026-06-11 |

> Plan d'exécution détaillé (working, local) : `.claude/plans/INFRA_HYBRID_DEPLOY_PLAN.md`.
> Roadmap publique : `docs/roadmap/INFRA_ROADMAP.md`. Process : `docs/governance/PROJECT_GOVERNANCE.md`.
