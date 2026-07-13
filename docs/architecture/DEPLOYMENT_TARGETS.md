# Cibles de déploiement multi-tier (P0 — squelette)

> Statut : **SPEC — Phase 0 (squelette)** · Date : 2026-07-13
> Réf. : ADR-0006 (`docs/adr/0006-onprem-orchestration-k3s-and-internal-pki.md`) ·
> spec complète `docs/superpowers/specs/2026-07-12-infra-deploy-multitarget-design.md` ·
> schéma `deploy/scripts/validate_config.py::DeployTargetConfig`.

## 1. Principe directeur

> **Un artefact, un modèle d'instances, plusieurs installeurs fins.**

Le runtime canonique est **k3s + un chart Helm unique**, qui couvre tout le continuum
on-prem mono-nœud → cloud multi-nœud (mêmes pods, même chart, seules les `values` changent).
`docker-compose` reste un tier de **seconde classe** (dev/démo + client on-prem sans ops),
généré depuis la **même** `deploy/config.yaml` par `deploy/providers/docker_local.py`
(comportement actuel, inchangé par ce P0). Le cloud (Terraform couche-0 + même chart + GitOps)
est conçu et testé à vide ; le premier `apply` live est différé au premier client cloud.

## 2. Matrice des cibles

| Tier | Runtime | Provisioning | Update | Pour qui |
|------|---------|--------------|--------|----------|
| `lite` | docker-compose | — | best-effort (recreate) | dev/démo · on-prem SANS ops |
| `k3s` (défaut) | k3s + chart Helm `infra/helm/facil` | — (bare-metal/VPS) | `helm upgrade` health-gated | on-prem/VPS mono-nœud |
| `cloud` (différé) | k8s managé (EKS/GKE/AKS) + même chart | Terraform couche-0 (VPC/DB/DNS/cluster) | GitOps ArgoCD | cloud à l'échelle |

`deploy.target` (provider concret consommé par le tier) : `docker-local` · `aws` · `gcp` ·
`azure` · `onprem` (défaut — machine nue/VPS pour le tier `k3s` ou `lite`).

## 3. Arbre de décision de l'installeur (P3, différé)

L'installeur unique (`infra/installers/install.sh` / `install.ps1`, Phase 3) détectera
l'environnement et choisira le tier :

```text
--tier explicite fourni ?
  ├── oui → respecté (override prioritaire)
  └── non
      ├── cloud-metadata détecté (169.254.169.254 / env) + --target fourni → tier = cloud
      ├── RAM < seuil OU --lite/--no-ops → tier = lite (compose)
      └── sinon → tier = k3s (défaut)
```

L'installeur n'est qu'une porte fine : il installe les prérequis (k3s+helm | docker | CLI cloud
+ terraform) puis délègue tout à `deploy/init.py` (config) et `deploy/deploy.py` (apply) — zéro
logique de déploiement dupliquée.

## 4. Ce qui existe vs ce qui est scaffold à ce stade (P0)

- **Existe et fonctionne** : `deploy/config.yaml` (+ `deploy.tier`/`deploy.target`, ce P0),
  `deploy/deploy.py` (validate/render/plan/apply par provider), `deploy/providers/docker_local.py`
  (tier `lite` de fait, sans le nom), providers cloud CLI (`aws.py`/`azure.py`/`gcp.py`, wrappers
  sans state, `apply` EXPERIMENTAL).
- **Squelette seulement (vide)** : `infra/helm/facil` (chart, P1), `infra/terraform/*` (P5),
  `infra/installers/*` (P3), `infra/gitops/*` (P5). Aucun de ces répertoires n'est peuplé par ce P0.
- **Zéro changement de comportement** : le champ `deploy.*` est un défaut rétro-compatible
  (`default_factory`) — les configs existantes sans section `deploy` valident toujours,
  tier `k3s` par défaut sans que rien ne soit déployé en k3s aujourd'hui (le provider `k3s` arrive
  en Phase 1).

## 5. Suite

Voir le spec complet (`docs/superpowers/specs/2026-07-12-infra-deploy-multitarget-design.md`,
§4) pour le détail phase par phase (P1 chart Helm → P2 cycle update sûr → P3 installeur →
P4 CD pull-based → P5 seam cloud à vide).
