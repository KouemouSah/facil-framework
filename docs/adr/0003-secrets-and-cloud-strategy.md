# ADR-0003 — Stratégie secrets (OpenBao+SOPS) & cloud (EKS/ECS, registries, proxy)

- **Status** : Accepted
- **Date** : 2026-06-11
- **Related** : `.claude/plans/INFRA_HYBRID_DEPLOY_PLAN.md` (P7/P8/P9), ISO/IEC 27001

## Context

En cloud, les secrets vivent dans GCP Secret Manager / GitHub Secrets. En **on-premise souverain**,
il faut un équivalent **local**. Le cloud doit être **librement configurable à l'installation**
(pas verrouillé GCP). Reverse-proxy et registries doivent être tranchés.

## Decision

- **Secrets — OpenBao + SOPS en couches** (abstraction `SecretsProvider`) :
  - `SOPS+age` : secrets chiffrés au repos dans Git (GitOps, zéro service), **amorce** les
    unseal keys d'OpenBao.
  - `OpenBao` (fork OSS de Vault) : service de secrets dynamiques + rotation + audit ; son
    **moteur PKI sert la gestion de certificats** (P8).
  - **Tiered** : single-node → SOPS seul ; cluster souverain → OpenBao (+ SOPS bootstrap).
  - Backends cloud conservés : `gcp_secret_manager`, `aws_secrets_manager`, `azure_key_vault`.
- **Cloud AWS — EKS primaire** (réutilise le chart Helm = parité on-prem/AKS) + **ECS/Fargate**
  en option *low-ops* pour la strate single-node. Cloud librement configurable à l'install
  (`gcp` | `aws` | `azure` | `k8s` générique).
- **Reverse-proxy — Caddy** (déclaratif, TLS auto ACME *ou* CA interne) ; **Nginx Proxy Manager
  écarté** (GUI non-IaC). Au bord haute charge : **LB L4 redondant** (keepalived/VRRP ou LB cloud).
- **Registries — GHCR + Artifact Registry** (les deux), via une abstraction registry.

## Consequences

**Positives**
- Souveraineté des secrets et des certificats (OpenBao PKI), sans renoncer aux backends cloud.
- Un seul artefact d'orchestration (Helm) pour on-prem + EKS + AKS.
- TLS automatisé et infra-as-code (Caddy), pas d'admin manuelle.

**Négatives / risques**
- OpenBao est un service à opérer (unseal, HA) → réservé aux strates qui le justifient.
- EKS coûte plus à opérer qu'ECS pour de petites installs → d'où l'option ECS/Fargate.

## Alternatives

- **GCP-only** — *rejeté* (exigence multi-cloud souveraine).
- **Vault Enterprise** — non retenu par défaut (licence) au profit d'**OpenBao** (OSS).
- **Traefik / Nginx Proxy Manager** — Traefik possible si besoins avancés ; NPM écarté (non-IaC).
