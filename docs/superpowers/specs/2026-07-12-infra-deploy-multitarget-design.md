# Design — Déploiement multi-cible unifié (installeur « type Odoo »)

> **Statut** : proposé · **Date** : 2026-07-12 · **Auteur** : Claude (expert infra) + KouemouSah
> **Portée** : P0→P5 spécifiées finement. Centre de gravité near-term = **P0→P3** (on-prem end-to-end).
> **ADR liés** : 0001 (monolithe modulaire), 0003 (secrets OpenBao+SOPS/age), 0005 (storage MinIO),
> **0006 (k3s mono-nœud + chart Helm)** — ce design *implémente* l'ADR-0006, resté à l'état d'intention.
> **Règles projet** : jamais de build cloud manuel (CI/GHCR only) ; zéro régression cloud ; tests = vraie validation.

---

## 1. Contexte & problème

### 1.1 Ce qui existe (vérifié dans le repo, 2026-07-12)

| Brique | Fichier | État |
|--------|---------|------|
| Wizard config | `deploy/init.py` | ✅ génère `config.yaml` + `.env.secrets` (CLI, comme `npm init`) |
| Orchestrateur | `deploy/deploy.py` | ✅ cycle `validate → render → plan → apply` par provider |
| Renderer compose | `deploy/providers/docker_local.py` | ✅ génère `docker-compose.local.yml` depuis `config.yaml` |
| Providers cloud | `deploy/providers/{gcp,aws,azure}.py` | ⚠️ wrappers **CLI** (`gcloud`/`aws`/`az`), **pas Terraform** ; `apply` **EXPERIMENTAL non validé live** |
| Bootstrap data-plane | `deploy/providers/bootstrap/*` | ✅ idempotent : postgres, minio, openbao, keycloak |
| Renderers env | `deploy/scripts/render_{env,backend_env,web_env}.py` | ✅ génèrent `.env.deploy.gen` |
| CI images | `.github/workflows/release-images.yml` | ✅ build+push `ghcr.io/<owner>/facil-{backend,web}` sur `main`/`develop` |
| Migrations | `packages/backend/alembic.ini` | ✅ Alembic (central) |

**Services de la stack** (compose généré) : `postgres` (pgvector pg16), `redis`, `minio`, `openbao`,
`db-init` (one-shot), `backend`, `frontend`. **Profile-gated** : `caddy` (edge), `keycloak` (auth),
`otel-lgtm` (observability).

### 1.2 Les trous (ce qui bloque une « installation complète » multi-cible)

1. **Aucun chart Helm** — l'ADR-0006 (k3s + chart) est une intention. Seul `deploy/k8s/networkpolicies.yaml` existe.
2. **Aucune CD** — le `ci.yml` teste, `release-images.yml` publie ; **rien ne déploie**. Mise à jour serveur = `docker pull` manuel (`tools/refresh-local.sh`, local-only).
3. **Aucun cycle de mise à jour** — pas de migrations gatées au déploiement, pas de health-gated cutover, pas de rollback, pas de backup-avant-update.
4. **Cloud non déployable** — `apply` AWS/Azure/GCP = wrappers CLI sans state, marqués EXPERIMENTAL.
5. **Aucun installeur unifié** — le wizard ne fait que la config ; il n'existe pas de porte d'entrée « une commande » qui détecte l'environnement et pose toute la stack.

### 1.3 Besoin métier

Servir **deux familles de clients à venir** : (a) **on-prem / VPS mono-nœud souverain** (dont des clients
**sans ops**), et (b) **cloud managé à l'échelle** (cible « millions d'utilisateurs / 100+ agents »). Exigence
formulée : *« installation en une fois »* et *« même déploiement des instances »* selon l'environnement.

---

## 2. Décision d'architecture

### 2.1 Principe directeur

> **Un artefact, un modèle d'instances, plusieurs installeurs fins.** (Le vrai modèle Odoo : un code, plusieurs
> *packagings* — pas « une version on-prem » vs « une version cloud ».)

- **Runtime canonique = k3s + un chart Helm unique.** Il réalise « même déploiement des instances » sur tout le
  continuum **on-prem mono-nœud → cloud multi-nœud** (mêmes pods, même chart, seules les `values` changent).
- **compose = tier *lite* de seconde classe**, **généré** depuis la même `config.yaml` (nature actuelle de
  `docker_local.py`). Réservé à : dev/démo + client on-prem **sans ops** refusant k3s. **Best-effort** (pas de
  rolling-update ni health-gated cutover natif) — documenté comme tel, **pas maintenu à parité**.
- **Point d'unification = `config.yaml` + le moteur `deploy.py`**, *pas* le moteur de templating (Helm ≠ compose,
  on ne le prétend pas). On unifie **un cran au-dessus** : une source de vérité → le renderer émet la cible du tier.
- **Cloud = Terraform (couche 0 uniquement : VPC/DB/DNS/cluster) + le MÊME chart Helm (+ GitOps).** Conçu et testé
  **à vide** maintenant ; premier `apply` **live** différé au premier client cloud (pas de budget brûlé sans cible).

### 2.2 Compromis assumé (honnêteté)

Le tier *lite* (compose) **échange l'identité-d'instance contre la simplicité**. Un update en tier *lite* est
best-effort (recreate, pas rolling). C'est un choix **délibéré et documenté**, pas un oubli. Le tier k3s reste la
recommandation par défaut, y compris pour la plupart des clients « sans ops » (k3s = binaire unique, l'installeur
masque entièrement kubectl).

### 2.3 Schéma cible

```text
SOURCE UNIQUE      config.yaml   (généré par init.py — wizard existant)
   │               .env.secrets  (secrets de boot, gitignored)
   ▼
MOTEUR DEPLOY      deploy.py :  render → provision → secrets → migrate(gated) → health-gate → seed → (rollback/backup)
   │
   ├── tier LITE   → renderer compose (docker_local.py)     [dev/démo · on-prem sans-ops · 2e classe]
   ├── tier K3S    → chart Helm unique  ────────────────────  [CANONIQUE : on-prem mono-nœud == cloud]
   └── tier CLOUD  → Terraform couche-0 + MÊME chart Helm + GitOps (ArgoCD)   [différé, seam conçu now]
   ▲
INSTALLEUR         install.sh / install.ps1 :
DYNAMIQUE          détecte OS + RAM + cloud-metadata → choisit le tier (override --tier/--target) →
(porte d'entrée)   installe les prérequis (k3s | docker) → appelle deploy.py.   « installation en une fois »
```

---

## 3. Objectifs / non-objectifs

**Objectifs**
- Une commande unique installe la stack complète sur on-prem/VPS (k3s défaut, compose *lite* en option).
- Chart Helm unique atteignant la **parité stricte** avec la stack compose actuelle (7 services + 3 gated).
- Cycle de mise à jour **sûr** : migrations gatées, backup-avant-update, health-gate, rollback.
- CD GitHub qui met à jour une cible on-prem après publication d'image (pull-based, health-gated, auto-rollback).
- Seam cloud (Terraform + values + GitOps) **prêt et testé à vide**.

**Non-objectifs (YAGNI / différé)**
- `terraform apply` **live** contre un compte cloud réel (attendre le 1er client cloud).
- Multi-région / multi-cluster fédéré, autoscaling avancé, service mesh.
- Migration du dev-loop quotidien hors de compose (compose reste le confort dev).
- Remplacer les providers CLI existants tant que le tier cloud n'est pas activé (ils restent en fallback documenté).

---

## 4. Conception fine par phase

> Convention commune à chaque phase : **livrables** · **arbo/fichiers** · **interfaces** · **tests** · **checklist de validation**.
> Chaque phase se termine par la gate qualité projet (pytest verts + revue agents sur le diff + self-checklist parité/DRY/sécu).

### Phase 0 — Cadre & squelette `infra/` (faible coût, zéro régression)

**But** : poser la structure et les décisions sans casser le runtime existant.

**Livrables**
- Arborescence `infra/` (vide mais structurée) :
  ```text
  infra/
    helm/facil/            # chart (rempli en P1)
      Chart.yaml
      values.yaml          # défauts
      values-onprem.yaml
      values-cloud.yaml
      templates/           # (P1)
    terraform/             # (P5) modules aws/ gcp/ azure/ + shared/
    installers/            # (P3) install.sh, install.ps1, lib/
    gitops/                # (P5) argocd app-of-apps
    README.md              # matrice cible + quel tier pour qui
  ```
- **Mise à jour ADR-0006** : acter « compose = fallback *lite* documenté ; k3s+Helm = canonique ; Terraform = couche-0 cloud only ». Ajouter la **matrice de cibles** (tier × provisioning × deploy × update × gitops).
- **Doc** `docs/architecture/DEPLOYMENT_TARGETS.md` : la matrice + l'arbre de décision de l'installeur.
- `deploy/config.yaml` : ajouter un champ **`deploy.tier`** (`lite` | `k3s` | `cloud`, défaut `k3s`) + `deploy.target` (provider) — étendre le schéma `validate_config.py`.

**Interfaces** : `config.yaml` gagne `deploy.tier`/`deploy.target` ; `validate_config.py` les valide (whitelist).

**Tests** : `deploy/scripts/test_validate_config.py` étendu (tier valide/invalide, défaut `k3s`, rétro-compat des configs existantes sans le champ).

**Checklist validation**
- [ ] `python deploy/deploy.py --provider=docker-local --action=validate` passe (rétro-compat).
- [ ] Une `config.yaml` sans `deploy.tier` vaut `k3s` par défaut, sans erreur.
- [ ] ADR-0006 mis à jour ; matrice documentée ; arbo `infra/` créée.
- [ ] pytest `test_validate_config.py` vert.

---

### Phase 1 — Chart Helm unique sur k3s (**cœur du chantier**)

**But** : déployer sur un k3s mono-nœud une stack **strictement équivalente** au `docker-compose.local.yml` généré.

**Livrables**
- **Chart `infra/helm/facil`** couvrant, en parité avec le compose :
  - **Stateful** : `postgres` (StatefulSet + PVC, image pgvector pg16), `redis` (Deployment ou StatefulSet + PVC), `minio` (StatefulSet + PVC), `openbao` (StatefulSet + PVC, mode dev gardé par flag `values`).
  - **One-shot** : `db-init` → **Helm hook** `post-install`/`pre-upgrade` (Job) — équivaut au service one-shot compose.
  - **App** : `backend` (Deployment + Service + readiness/liveness sur l'endpoint health existant), `frontend`/`web` (Deployment + Service).
  - **Gated (via `values`)** : `caddy`/ingress (profil edge), `keycloak` (profil auth), `otel-lgtm` (profil observability) — `enabled: false` par défaut, alignés sur les profils compose.
  - **Réseau** : porter `deploy/k8s/networkpolicies.yaml` dans `templates/networkpolicy.yaml` (gardé par flag).
- **Mapping `config.yaml` → `values`** : un module `deploy/providers/k3s.py` (nouveau provider) qui **render** un
  `values-<env>.yaml` depuis `config.yaml` (réutilise la logique de `render_env.py` / `docker_local.py` — DRY), puis
  `helm upgrade --install`. Même CLI que les autres providers (`--validate/--plan/--apply`).
- **Secrets** (ADR-0003) : les 5 secrets de boot (issus de `.env.secrets` / OpenBao) rendus en **k8s Secret** par le
  provider (jamais en clair dans les `values` versionnées). Intégrations externes vides = dégradation propre.
- **Storage** : PVC via la StorageClass par défaut de k3s (`local-path`).

**Interfaces**
- Nouveau provider : `deploy/providers/k3s.py` (`--validate` = prérequis helm/kubectl/cluster joignable ; `--plan` =
  `helm template` + diff ; `--apply` = `helm upgrade --install`).
- `helm template infra/helm/facil -f values-onprem.yaml` doit produire des manifests valides sans cluster.

**Tests**
- `deploy/providers/test_k3s.py` : le render `config.yaml → values` (mêmes images/ports/env que le compose).
- **`helm lint infra/helm/facil`** + **`helm template`** en CI (job dédié, sans cluster).
- **Smoke k3s local** : `helm upgrade --install` sur un k3s local → tous les pods `Ready`, `/health` backend vert,
  frontend répond, migrations passées. (Manuel documenté + optionnel en CI via `k3d`.)

**Checklist validation**
- [ ] Parité services : les 7 services + 3 gated présents et configurables comme en compose.
- [ ] `helm lint` + `helm template` verts en CI.
- [ ] Smoke k3s local : pods Ready, `/health` OK, login/UI OK, migrations appliquées.
- [ ] Secrets jamais en clair dans un fichier versionné (revue `security-auditor` sur le diff).
- [ ] `deploy.py --provider=k3s --action=plan` affiche le plan sans muter.
- [ ] pytest `test_k3s.py` vert.

---

### Phase 2 — Cycle « installation complète » (update sûr)

**But** : transformer un `helm upgrade` brut en **procédure d'installation/mise à jour de niveau produit**.

**Livrables**
- **Migrations gatées** : Job Helm **hook `pre-upgrade`** exécutant `alembic upgrade head` (image backend). Le
  cutover applicatif ne se fait **que si la migration réussit** (hook bloquant). Idempotent (Alembic).
- **Backup-avant-update** : hook `pre-upgrade` (avant migration) → `pg_dump` Postgres + snapshot bucket MinIO
  (config/branding), déposés dans un PVC/volume `backups` horodaté. **Gate on-prem souverain non négociable.**
- **Health-gate** : readiness probes strictes + une étape post-upgrade qui **attend** `/health` vert sur backend et
  web avant de marquer le release réussi.
- **Rollback** : `helm rollback` natif sur échec (migration KO, health-gate KO) — exposé via
  `deploy.py --provider=k3s --action=rollback` (+ note de restauration DB depuis le backup si migration destructive).
- **Seed profil** : après health-gate, appliquer le seed du profil (`deploy/scripts/profiles.py`) de façon idempotente.
- **Compose tier *lite*** : équivalent **best-effort** documenté — `migrate` via un `docker compose run` one-shot
  avant `up -d`, backup via `pg_dump` scripté ; pas de rolling-update (recreate). Explicitement 2e classe.

**Interfaces**
- `deploy.py` gagne l'action **`rollback`** et une étape **`backup`** intégrée au pipeline `apply`.
- Ordre du pipeline `apply` (k3s) : `backup → migrate(gated) → helm upgrade → health-gate → seed` ; sur échec à
  toute étape ≥ migrate → `rollback` auto + exit non-zéro.

**Tests**
- Tests unitaires du pipeline (mock helm/alembic) : ordre des étapes, court-circuit sur échec, appel rollback.
- Smoke : provoquer une migration en échec → vérifier rollback + backup présent.
- Test idempotence : `apply` deux fois de suite → pas de dérive, seed non dupliqué.

**Checklist validation**
- [ ] Migration échouée ⇒ pas de cutover, rollback auto, backup présent.
- [ ] `/health` rouge ⇒ release marqué échoué, version précédente conservée.
- [ ] `apply` idempotent (2× = no-op).
- [ ] Backup horodaté vérifiable ; procédure de restauration documentée.
- [ ] Gate qualité : `silent-failure-hunter` sur les hooks (pas d'échec avalé).

---

### Phase 3 — Installeur dynamique (« installation en une fois »)

**But** : une porte d'entrée unique qui détecte l'environnement, choisit le tier, pose les prérequis, appelle le moteur.

**Livrables**
- **`infra/installers/install.sh`** (Linux/macOS) et **`infra/installers/install.ps1`** (Windows) — **portes fines**,
  zéro logique métier de déploiement (elle vit dans `deploy.py`) :
  1. **Détection** : OS, RAM/CPU, présence de métadonnées cloud (169.254.169.254 / env), `kubectl`/`docker` présents,
     flags `--tier {lite|k3s|cloud}` / `--target {aws|gcp|azure}` (override).
  2. **Sélection de tier** (arbre de décision, défaut **k3s**) :
     - `--tier` explicite → respecté.
     - cloud-metadata détecté + `--target` → `cloud`.
     - RAM < seuil OU `--lite`/`--no-ops` → `lite` (compose).
     - sinon → `k3s`.
  3. **Prérequis** : tier k3s → installe k3s (`get.k3s.io`) + helm si absents ; tier lite → installe/vérifie docker ;
     tier cloud → vérifie CLI provider + terraform.
  4. **Config** : lance `deploy/init.py` (interactif) **ou** `--non-interactive` (variables d'env) pour produire
     `config.yaml` + `.env.secrets`.
  5. **Déploiement** : appelle `python deploy/deploy.py --provider=<tier> --action=apply`.
- **Lib partagée** `infra/installers/lib/` (fonctions de détection communes documentées, testables).
- **Doc** `infra/installers/README.md` : matrice de détection, exemples one-liner par environnement.

**Interfaces**
- One-liner cible : `curl -sfL https://<repo>/install.sh | sh -s -- --tier k3s` (ou `--lite`, `--target aws`).
- L'installeur n'appelle QUE `init.py` + `deploy.py` — aucune duplication de logique.

**Tests**
- Tests de la logique de détection/sélection (bash via `bats` **ou** portée en Python testable + fin wrapper shell).
  Cas : RAM basse → lite ; cloud-metadata → cloud ; défaut → k3s ; override `--tier` prioritaire.
- Smoke : `install.sh --tier k3s --non-interactive` sur une VM propre → stack Ready de bout en bout.

**Checklist validation**
- [ ] Détection correcte sur ≥3 environnements simulés (VM nue, low-RAM, cloud-metadata).
- [ ] Override `--tier`/`--target` toujours prioritaire sur la détection.
- [ ] Installe les prérequis manquants sans intervention (k3s/docker/helm).
- [ ] Aucune logique de déploiement dupliquée dans les scripts shell (revue).
- [ ] Smoke end-to-end vert sur VM propre (k3s + lite).

---

### Phase 4 — CD GitHub (mise à jour on-prem, **pull-based**)

**But** : mettre à jour une cible on-prem **après** `release-images` — sans build sur le serveur, sans SSH entrant depuis la CI.

**Décision** : **pull-based par défaut** (souverain, pas d'inbound). Un agent léger sur la box interroge GHCR et
applique. SSH-push proposé en **option** pour les cibles cloud/VM gérées.

**Livrables**
- **Agent `facil-agent`** (systemd timer / cron on-prem) : poll GHCR pour un nouveau digest de
  `ghcr.io/<owner>/facil-{backend,web}` sur le tag suivi (`develop`/`main`/`vX.Y.Z`) → si nouveau →
  `deploy.py --provider=<tier> --action=apply` (qui enchaîne backup→migrate→upgrade→health-gate ; **rollback auto** P2).
- **Workflow `.github/workflows/deploy.yml`** : déclenché sur succès de `release-images` (ou `workflow_dispatch`).
  - Mode **pull** : ne fait que publier un « channel/manifest » (tag + digest attendus) que l'agent lit ; **ne pousse rien**.
  - Mode **push** (option cloud) : `helm upgrade` distant via runner + kubeconfig secret, health-gated.
- **Rollback CI-visible** : si l'agent/`deploy.py` retourne un échec, le statut du release est marqué et un rollback
  est enregistré (audit).
- **Doc** `infra/README.md` : enrôler un serveur (installer l'agent, choisir le channel).

**Interfaces**
- L'agent ne fait qu'appeler `deploy.py` (réutilise tout le pipeline P2). Zéro nouvelle logique de déploiement.
- Le workflow **ne build jamais** (règle #1) — il orchestre uniquement.

**Tests**
- Tests de l'agent : détection nouveau digest (mock registry), déclenchement `apply`, non-déclenchement si inchangé,
  comportement sur échec (rollback + non-avancement du channel).
- Smoke : publier une nouvelle image de test → l'agent met à jour la box → health-gate → OK ; puis image cassée →
  rollback auto.

**Checklist validation**
- [ ] Nouveau digest ⇒ update auto ; digest inchangé ⇒ no-op.
- [ ] Image cassée ⇒ rollback auto, version précédente servie, statut d'échec visible.
- [ ] Aucun build sur le serveur ; aucun inbound SSH requis en mode pull.
- [ ] Audit de chaque déploiement (acteur = agent, cible = release).
- [ ] Revue `security-auditor` (secrets registry en lecture seule, pas de fuite de creds).

---

### Phase 5 — Seam cloud (Terraform + GitOps, **conçu & testé à vide**)

**But** : rendre le tier cloud **prêt** sans exécuter d'`apply` live (attendre le 1er client cloud).

**Livrables**
- **Modules Terraform** `infra/terraform/{aws,gcp,azure}/` + `shared/` — **couche 0 uniquement** :
  réseau (VPC/subnets), **Postgres managé** (RDS/Cloud SQL/Azure DB), DNS, **cluster** (EKS/GKE/AKS **ou** VM k3s),
  bucket objet (S3/GCS/Azure Blob) mappé sur l'abstraction storage existante, secret manager (déjà supporté côté app :
  `AwsSecretsManagerProvider`). Backend de **state distant** (S3+DynamoDB / GCS / Azure Storage) — paramétré, non créé live.
- **`values-cloud.yaml`** : le **même** chart Helm P1, valeurs adaptées (ingress cloud, storage class managée, replicas,
  Postgres externe au lieu du StatefulSet in-cluster).
- **GitOps** `infra/gitops/` : app-of-apps **ArgoCD** pointant le chart + `values-cloud.yaml` (réconciliation
  `develop`→cluster). Alternative Flux documentée.
- **CI de validation à vide** : job `terraform validate` + `terraform plan` (contre un backend factice / `-refresh=false`)
  + `helm template -f values-cloud.yaml` — **jamais `apply`**.

**Interfaces**
- `deploy.py --provider=<cloud> --action=plan` → `terraform plan` + `helm template` (read-only).
- `--action=apply` cloud reste **gardé** (confirmation explicite + garde « pas de client cloud actif »).

**Tests**
- `terraform validate` + `plan` (dry) verts en CI pour les 3 providers.
- `helm template -f values-cloud.yaml` valide (mêmes manifests structurels que on-prem, deltas attendus seulement).
- Revue architecture (`architecture-critic`) : pas de sur-ingénierie, modules minimaux.

**Checklist validation**
- [ ] `terraform validate`/`plan` verts (aws/gcp/azure) sans toucher de ressource réelle.
- [ ] `helm template` cloud valide ; deltas vs on-prem documentés.
- [ ] `apply` live impossible sans confirmation + flag client-cloud.
- [ ] ArgoCD app-of-apps rendue et lintée (pas déployée).
- [ ] Les providers CLI existants (`aws.py`/`azure.py`/`gcp.py`) restent en fallback documenté, non supprimés.

---

## 5. Flux de données

**Flux d'installation (on-prem, tier k3s)**
```text
install.sh → détecte env → tier=k3s → installe k3s+helm → init.py (config.yaml + .env.secrets)
          → deploy.py apply : render values ← config.yaml
                              → backup (pré) → migrate(gated) → helm upgrade --install
                              → health-gate (/health) → seed profil → OK
```

**Flux de mise à jour (CD pull-based)**
```text
push develop → CI release-images → GHCR (nouveau digest) → deploy.yml publie le channel
   → facil-agent (box) détecte le digest → deploy.py apply (backup→migrate→upgrade→health-gate)
   → succès : channel avancé, audit | échec : rollback auto, channel figé, statut KO
```

---

## 6. Gestion d'erreurs, backup, rollback

- **Fail-closed** : toute étape ≥ `migrate` qui échoue **stoppe le cutover** et déclenche `rollback` ; jamais d'échec
  silencieux (gate `silent-failure-hunter`).
- **Backup** systématique avant migration (pg_dump + snapshot config MinIO), horodaté, restauration documentée.
- **Rollback** : `helm rollback` (app) ; DB = restauration backup si migration destructive (documenté, semi-manuel
  car dépend de la nature de la migration).
- **Idempotence** : `apply` répétable sans dérive ; seeds/migrations idempotents (règle existante).
- **Dégradation propre** : intégrations externes vides (Gemini/Firebase/…) = pas de crash (comportement actuel conservé).

---

## 7. Stratégie de tests (gate = vraie validation)

| Niveau | Portée | Où |
|--------|--------|----|
| Unitaire | render config→values/compose, détection tier, ordre pipeline, agent CD | pytest `deploy/**/test_*.py`, bats/py pour installeurs |
| Statique | `helm lint`, `helm template`, `terraform validate/plan` (dry) | jobs CI dédiés |
| Smoke k3s | pods Ready, `/health`, login/UI, migrations, rollback | k3s local (+ k3d optionnel en CI) |
| Smoke lite | compose up, migrate, backup best-effort | docker local |
| Sécurité | secrets jamais en clair, registry RO, pas d'inbound | `security-auditor` sur chaque diff |

CI : nouveaux jobs `helm` (lint+template) et `terraform` (validate+plan) **sans build cloud** (règle #1).

---

## 8. Sécurité (rappels enforced)

- Secrets de boot rendus en k8s Secret / `.env` par le moteur, **jamais** dans un fichier versionné ; GitOps →
  SOPS/age (ADR-0003) pour les valeurs sensibles.
- CD pull-based → **pas d'inbound SSH** on-prem ; l'agent lit GHCR en lecture seule.
- `terraform apply` cloud gardé (confirmation + flag) ; state distant chiffré.
- NetworkPolicies portées dans le chart (défense en profondeur).
- Audit de chaque déploiement (acteur + release), cohérent avec `audit.record`.

---

## 9. Risques & mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Bascule compose→Helm sous-estimée (P1) | Retard | P1 = parité stricte scope-figée sur le compose actuel ; smoke obligatoire |
| Divergence compose *lite* vs k3s | Dette | *lite* explicitement 2e classe, généré depuis la même `config.yaml`, non maintenu à parité |
| Migration destructive + rollback DB | Perte données | Backup pré-migration non négociable ; restauration documentée ; migrations idempotentes |
| Complexité k8s pour client sans ops | Adoption | Installeur masque kubectl ; tier *lite* compose en filet |
| Sur-ingénierie cloud prématurée | Budget | P5 conçu/testé **à vide** ; `apply` live différé au 1er client cloud |
| OOM build Next local | Blocage dev | Build = CI/GHCR (règle #1) ; local = pull (`refresh-local.sh`) |

---

## 10. Questions ouvertes (à trancher avant/pendant l'implémentation)

1. **CI smoke k3s** : intégrer `k3d` dans la CI (couverture++, coût runner) ou garder le smoke k3s **manuel documenté** ? (Reco : manuel d'abord, k3d plus tard.)
2. **Redis** en Deployment (simple) ou StatefulSet (persistance) sur k3s ? (Reco : Deployment, cache éphémère.)
3. **Tests installeurs** : `bats` (shell natif) ou logique de détection portée en **Python testé** + fin wrapper shell ? (Reco : Python testable — DRY avec le reste, moins de dette shell.)
4. **Channel CD** : format du manifeste que l'agent lit (tag GHCR seul, ou fichier signé dans le repo) ? (À spécifier en P4.)
5. **OpenBao en k3s** : mode dev (flag) pour on-prem simple, ou exiger un unseal réel ? (Aligner sur l'état actuel : dev par défaut, prod = knob.)

---

## 11. Séquencement & attentes

- **Centre de gravité near-term : P0 → P3** = installation complète on-prem de bout en bout (k3s défaut + *lite*).
- **P4** comble le trou CD réel (aujourd'hui : `docker pull` manuel).
- **P5** rend le cloud **prêt** sans dépense live.
- **Chantier pluri-semaines** ; **P1 = la vraie bascule** (compose→Helm/k3s), coût incontournable de la vision unifiée.
- Chaque phase : plan → impl → tests → gate agents → checklist → commit local groupé → **validation explicite avant la suivante** (règle #4). Push = accord explicite (règle #13 / isolation repo).
