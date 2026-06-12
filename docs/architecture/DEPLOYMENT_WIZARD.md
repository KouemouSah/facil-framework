# Wizard de déploiement & configuration

> **Statut** : implémenté (2026-06-11). `deploy/init.py` (wizard) → `deploy/deploy.py`
> (orchestrateur) → `deploy/providers/<provider>.py`.
> **Plan** : `.claude/plans/DEPLOY_WIZARD_V2_PLAN.md` (interne).

## 1. Flux

```bash
python deploy/init.py                 # wizard interactif (ou --non-interactive via WIZ_*)
   └─> deploy/config.yaml + .env.secrets   (validés Pydantic)

python deploy/deploy.py --provider=<P> --action=validate|plan|apply
   ├─ validate_config.py        schéma + secrets référencés
   ├─ render_env.py             .env.deploy.gen + manifest
   └─ providers/<P>.py          validate (prérequis) -> plan (commandes) -> apply
```

Le wizard **demande explicitement** tout ce qui détermine une config correcte,
avec des **défauts intelligents** (selon provider + profile) que l'opérateur
confirme ou écrase. Tout reste éditable dans `config.yaml` ensuite.

## 2. Matrice providers (modèle serverless-container homogène)

| Cible | Compute | Images | Secrets | Object store | Postgres |
|---|---|---|---|---|---|
| **docker-local** / **vps** (souverain) | conteneurs locaux / k3s | GHCR (pull) | **OpenBao** | **MinIO** | conteneur / externe |
| **gcp** | **Cloud Run** | Artifact Registry | Secret Manager | GCS | Cloud SQL |
| **aws** | **App Runner** (ou ECS Fargate) | ECR | Secrets Manager | S3 | RDS |
| **azure** | **Container Apps** | ACR | Key Vault | Azure Blob | Postgres Flexible |

Le **provider** pilote les défauts d'infra (storage/secrets) ; le **profile**
pilote les défauts applicatifs (modules/branding). Mappings : `deploy/init.py`
(`_STORAGE_DEFAULT`/`_SECRETS_DEFAULT`).

### Statut d'implémentation (honnête)
- **docker-local** : complet (génère le compose + bootstrap data-plane). Voir `DATAPLANE_BOOTSTRAP.md`.
- **gcp** : `validate`/`plan`/`apply` (Cloud Run via `gcloud`).
- **aws** / **azure** : `validate`/`plan` **réels et testés** (prérequis + commandes).
  **`apply` est authoré depuis la spec mais NON validé contre un compte réel** —
  il affiche un bandeau « EXPERIMENTAL » + le plan et défère l'exécution live à
  l'opérateur disposant d'un compte. Le `--apply` complet sera validé quand une
  cible réelle existera.

## 3. Profiles (`deploy/scripts/profiles.py`)

Sélectionnés au wizard ; appliquent des defaults cohérents. Le **contenu détaillé**
(seeds, écrans, workflows) se complète avec la **phase Modules** — ici on pose la
**liste d'activation** (`modules.enabled`, le contrat lu par le Module Loader / Phase A.5)
et le branding minimal.

| Profile | Modules par défaut | Feature |
|---|---|---|
| `empty` | rbac | — |
| `private-services-company` | rbac, treasury, chatbot, document_designer | executive_tools |
| `gov-emergent-country` | rbac, treasury, chatbot, verified_identifiers, document_designer, signature | penalties |
| `saas-multitenant` | rbac, billing, multitenancy, chatbot | llm_routing |
| `banking` | rbac, treasury, kyc, signature, document_designer | executive_tools, penalties |

> Les noms de modules proviennent du design framework documenté ; leur **code**
> arrive avec la phase Modules. La config est le **contrat** qu'ils consommeront.

## 4. Exemples

```powershell
# Souverain on-prem (dev) — défauts MinIO + OpenBao
python deploy/init.py            # profile=empty, provider=docker-local

# SaaS sur Azure (non-interactif)
$env:WIZ_PROVIDER="azure"; $env:WIZ_PROFILE="saas-multitenant"
$env:WIZ_AZURE_SUB="<sub>"; $env:WIZ_AZURE_ACR="<acr>"; $env:WIZ_GEMINI_API_KEY="<key>"
python deploy/init.py --non-interactive --force

# Voir le plan AWS (App Runner) sans rien exécuter
python deploy/deploy.py --provider=aws --action=plan
```

## 5. Sécurité

- `.env.secrets` (gitignored) : secrets ; le wizard génère les clés auth + les
  mots de passe runtime forts (Postgres/Redis/MinIO) pour le stack local.
- Jamais de secret dans `config.yaml` (références par nom uniquement).
- Voir `DATAPLANE_BOOTSTRAP.md` §6bis pour les méthodes de connexion (AppRole, SA scopé…).
