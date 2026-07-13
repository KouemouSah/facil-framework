# infra/ — Déploiement multi-cible Facil

Voir le spec : `docs/superpowers/specs/2026-07-12-infra-deploy-multitarget-design.md`.

| Tier | Runtime | Provisioning | Update | Pour qui |
|------|---------|--------------|--------|----------|
| lite | docker-compose | — | best-effort (recreate) | dev/démo · on-prem SANS ops |
| k3s (défaut) | k3s + chart Helm `helm/facil` | — (bare-metal/VPS) | helm upgrade health-gated | on-prem/VPS mono-nœud |
| cloud (différé) | k8s managé + même chart | Terraform couche-0 | GitOps ArgoCD | cloud à l'échelle |

- `helm/facil/` — chart unique (P1).
- `terraform/` — modules couche-0 cloud (P5, différé).
- `installers/` — install.sh/.ps1 (P3).
- `gitops/` — ArgoCD app-of-apps (P5).

## État actuel (P0)

Cette arborescence est un **squelette** (Phase 0 du design multi-cible) : aucun sous-répertoire
n'est encore peuplé. Le runtime actif reste `docker-compose.local.yml` (généré par
`deploy/providers/docker_local.py`) — rien ne change de comportement à ce stade. Les sous-dossiers
listés ci-dessus se remplissent phase par phase (P1 = chart Helm, P3 = installeurs, P5 = Terraform +
GitOps), chacun avec sa propre gate qualité (tests + revue) avant de passer à la phase suivante.

Le champ `deploy.tier`/`deploy.target` dans `deploy/config.yaml` (schéma
`deploy/scripts/validate_config.py::DeployTargetConfig`) sélectionne la cible ; défaut `k3s`/`onprem`,
rétro-compatible avec les configs existantes qui ne déclarent pas cette section.
