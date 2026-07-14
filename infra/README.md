# infra/ — Déploiement multi-cible Facil

Voir le spec : `docs/superpowers/specs/2026-07-12-infra-deploy-multitarget-design.md`.

| Tier | Runtime | Provisioning | Update | Pour qui |
|------|---------|--------------|--------|----------|
| lite | docker-compose | — | best-effort (recreate) | dev/démo · on-prem SANS ops |
| k3s (défaut) | k3s + chart Helm `infra/helm/facil` | — (bare-metal/VPS) | helm upgrade health-gated | on-prem/VPS mono-nœud |
| cloud (différé) | k8s managé + même chart | Terraform couche-0 | GitOps ArgoCD | cloud à l'échelle |

- `helm/facil/` — chart Helm **peuplé** (P1, cette branche : `deploy/providers/k3s.py` +
  `--validate/--plan/--apply`, voir `SMOKE.md`).
- `terraform/` — modules couche-0 cloud (P5, différé — squelette vide).
- `installers/` — install.sh/.ps1 (P3, différé — squelette vide).
- `gitops/` — ArgoCD app-of-apps (P5, différé — squelette vide).

## État actuel

Le chart Helm (`helm/facil/`, tier `k3s`) est **peuplé et smoke-testé** (P1 du design multi-cible —
voir `SMOKE.md` pour les résultats observés sur un cluster k3d réel). `terraform/`, `installers/` et
`gitops/` restent des squelettes vides (P3/P5, différé). Le runtime `docker-compose.local.yml`
(tier `lite`, généré par `deploy/providers/docker_local.py`) reste le chemin dev/démo par défaut —
les deux tiers coexistent, sélectionnés par `deploy.tier`/`deploy.target` (voir ci-dessous).

Le champ `deploy.tier`/`deploy.target` dans `deploy/config.yaml` (schéma
`deploy/scripts/validate_config.py::DeployTargetConfig`) sélectionne la cible ; défaut `k3s`/`onprem`,
rétro-compatible avec les configs existantes qui ne déclarent pas cette section.
