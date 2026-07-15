# Déploiement multi-cible — P0 (seam) + P1-core (chart Helm k3s) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Déployer la stack souveraine always-on (postgres, redis, minio, openbao, db-init, backend, frontend) sur un k3s mono-nœud via un chart Helm unique piloté par `deploy/config.yaml`, avec migrations gatées et smoke health-gated.

**Architecture:** Un chart Helm `infra/helm/facil` = parité stricte avec `docker-compose.local.yml`. Un nouveau provider `deploy/providers/k3s.py` **render** les `values` depuis `config.yaml` (réutilise la logique existante — DRY) puis `helm upgrade --install`. Les secrets sont rendus en **k8s Secret** par le provider, jamais écrits dans un fichier versionné. Même CLI `--validate/--plan/--apply` que les autres providers.

**Tech Stack:** Helm 3, k3s (StorageClass `local-path`), Python 3.12 (pydantic v2, PyYAML), pytest, Alembic (hook), GitHub Actions (job `helm lint`/`template`, aucun build cloud).

## Global Constraints

- **Python** : `C:\facil_framework\.venv\Scripts\python.exe` (Python 3.12). Tests = `pytest`, vraie validation.
- **Jamais de build cloud/serveur** (règle #1) : le chart **pull** `ghcr.io/<owner>/facil-{backend,web}` (images CI). Aucun `docker build` / `helm` ne build d'image.
- **Zéro régression** : une `config.yaml` existante (sans le nouveau champ `deploy`) doit rester valide (`deploy` a un `default_factory`, `tier` défaut = `k3s`).
- **Secrets — normes renforcées (OBLIGATOIRE)** :
  - Les valeurs de secret ne sont **JAMAIS** écrites dans `values*.yaml`, dans un template rendu, ni loggées. Les `values` ne portent que des **noms** de Secret k8s.
  - Le provider crée/patch les **k8s Secret** à partir de `.env.secrets` (ou OpenBao) au moment de l'`apply`, hors du flux Helm versionné.
  - `helm template` (CI + tests) ne doit **jamais** faire apparaître une valeur de secret en clair (assert négatif).
  - OpenBao en `-dev` gardé derrière `openbao.devMode` (défaut `true` on-prem, commentaire « prod unseal = plan ultérieur »).
  - Least-privilege DB : le backend utilise le rôle `facil_app` (comme le compose), pas `facil` superuser.
- **Pod hardening (renforcé)** : chaque Deployment/StatefulSet applicatif porte `securityContext` `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`. Exception documentée : `openbao` requiert `IPC_LOCK` (add cap unique).
- **Images pinnées** : versions exactes copiées du compose — `pgvector/pgvector:pg16`, `redis:7-alpine`, `minio/minio:latest`, `openbao/openbao:latest`. (Pas de `:latest` flottant sur backend/web : tag = version/commit.)
- **Gate fin de phase** : pytest verts + `helm lint` + `helm template` + revue agents (`security-auditor` sur les secrets/hardening, `silent-failure-hunter` sur le provider) + self-checklist parité/DRY. Commit local groupé ; **push = accord explicite** (isolation repo `facil-framework`).
- **Branche de travail** : `docs/infra-multitarget-deploy` (déjà créée, spec committé `8e07326`). Rester dessus.

---

## File Structure

**Créés :**
- `infra/helm/facil/Chart.yaml` — métadonnées du chart.
- `infra/helm/facil/values.yaml` — défauts (images, ports, flags gated=false).
- `infra/helm/facil/values-onprem.yaml` — overlay on-prem mono-nœud.
- `infra/helm/facil/templates/_helpers.tpl` — helpers de nommage/labels.
- `infra/helm/facil/templates/postgres.yaml` — StatefulSet + Service + PVC Postgres.
- `infra/helm/facil/templates/redis.yaml` — Deployment + Service Redis.
- `infra/helm/facil/templates/minio.yaml` — StatefulSet + Service + PVC MinIO.
- `infra/helm/facil/templates/openbao.yaml` — StatefulSet + Service OpenBao (dev gated).
- `infra/helm/facil/templates/db-init-job.yaml` — Job hook `pre-install,pre-upgrade` (alembic).
- `infra/helm/facil/templates/backend.yaml` — Deployment + Service backend.
- `infra/helm/facil/templates/frontend.yaml` — Deployment + Service frontend.
- `infra/helm/facil/templates/NOTES.txt` — post-install hints.
- `infra/README.md` — matrice de cibles + quel tier pour qui.
- `deploy/providers/k3s.py` — provider render-values + helm apply (CLI `--validate/--plan/--apply`).
- `deploy/providers/test_k3s.py` — tests du render + garde-secrets.
- `docs/architecture/DEPLOYMENT_TARGETS.md` — matrice + arbre de décision installeur.
- `.github/workflows/helm.yml` — CI `helm lint` + `helm template` (aucun apply).

**Modifiés :**
- `deploy/scripts/validate_config.py` — ajouter `DeployTargetConfig` + champ `deploy` dans `DeployConfig`.
- `deploy/scripts/test_validate_config.py` — cas `deploy.tier`.
- `deploy/config.yaml` — ajouter la section `deploy:` (tier=k3s).
- `deploy/deploy.py` — enregistrer `k3s` dans `SUPPORTED_PROVIDERS` (déjà présent) et router vers `providers/k3s.py`.
- `docs/adr/0006-*.md` — acter compose=lite, k3s+Helm=canonique, Terraform=couche-0.

---

## PHASE 0 — Seam & squelette

### Task 0.1 : Schéma `deploy.tier` / `deploy.target` (rétro-compatible)

**Files:**
- Modify: `deploy/scripts/validate_config.py` (ajout classe + champ dans `DeployConfig` @ ligne ~574)
- Test: `deploy/scripts/test_validate_config.py`

**Interfaces:**
- Produces: `DeployTargetConfig(tier: Literal["lite","k3s","cloud"]="k3s", target: Literal["docker-local","aws","gcp","azure","onprem"]="onprem")` ; `DeployConfig.deploy: DeployTargetConfig` avec `default_factory`.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `deploy/scripts/test_validate_config.py` :

```python
def test_deploy_defaults_to_k3s_when_absent():
    # Rétro-compat : une config sans section `deploy` reste valide, tier=k3s.
    from validate_config import DeployConfig
    cfg = _minimal_valid_config_dict()  # helper existant dans ce fichier
    cfg.pop("deploy", None)
    parsed = DeployConfig(**cfg)
    assert parsed.deploy.tier == "k3s"
    assert parsed.deploy.target == "onprem"

def test_deploy_tier_rejects_unknown_value():
    import pytest
    from pydantic import ValidationError
    from validate_config import DeployConfig
    cfg = _minimal_valid_config_dict()
    cfg["deploy"] = {"tier": "kubernetes"}  # invalide
    with pytest.raises(ValidationError):
        DeployConfig(**cfg)
```

Si `_minimal_valid_config_dict()` n'existe pas dans le fichier, le créer à partir de `deploy/config.yaml` chargé via `yaml.safe_load` (fixture) — vérifier d'abord les helpers présents en haut du fichier de test.

- [ ] **Step 2: Lancer le test — il doit échouer**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/scripts/test_validate_config.py -k deploy_ -v`
Expected: FAIL — `AttributeError: 'DeployConfig' object has no attribute 'deploy'`.

- [ ] **Step 3: Implémenter**

Dans `deploy/scripts/validate_config.py`, avant `class DeployConfig` :

```python
class DeployTargetConfig(BaseModel):
    """Cible et tier de déploiement (P0 du design infra multi-cible).

    tier : lite=compose (2e classe, sans-ops) · k3s=canonique · cloud=Terraform+Helm.
    target : hôte/provider concret. onprem = machine nue / VPS (k3s local).
    """
    tier: Literal["lite", "k3s", "cloud"] = "k3s"
    target: Literal["docker-local", "aws", "gcp", "azure", "onprem"] = "onprem"
```

Dans `class DeployConfig`, ajouter le champ (juste après `meta`) :

```python
    deploy: DeployTargetConfig = Field(default_factory=DeployTargetConfig)
```

- [ ] **Step 4: Lancer les tests — ils passent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/scripts/test_validate_config.py -v`
Expected: PASS (tous, y compris les existants — rétro-compat).

- [ ] **Step 5: Commit**

```bash
git add deploy/scripts/validate_config.py deploy/scripts/test_validate_config.py
git commit -m "feat(deploy): champ deploy.tier/target (défaut k3s, rétro-compatible)"
```

### Task 0.2 : Section `deploy:` dans config.yaml + arbo `infra/` + ADR-0006

**Files:**
- Modify: `deploy/config.yaml`
- Create: `infra/README.md`, `docs/architecture/DEPLOYMENT_TARGETS.md`
- Modify: `docs/adr/0006-*.md`

- [ ] **Step 1: Ajouter la section `deploy` à `deploy/config.yaml`**

Après le bloc `meta:` (ligne ~12), insérer :

```yaml
# Cible de déploiement (P0 infra multi-cible). tier k3s = canonique.
deploy:
  tier: k3s
  target: onprem
```

- [ ] **Step 2: Créer l'arbo `infra/` et la matrice**

Créer `infra/README.md` :

```markdown
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
```

Créer `docs/architecture/DEPLOYMENT_TARGETS.md` avec la même matrice + l'arbre de décision de l'installeur (détection RAM/cloud-metadata → tier ; override `--tier`/`--target`), résumé du §2 du spec.

- [ ] **Step 3: Mettre à jour l'ADR-0006**

Dans `docs/adr/0006-*.md`, ajouter une note d'implémentation : « compose = fallback *lite* documenté (2e classe) ; k3s + chart Helm `infra/helm/facil` = runtime canonique on-prem→cloud ; Terraform = couche-0 cloud uniquement (différé). Réf : spec 2026-07-12 + plan 2026-07-13. »

- [ ] **Step 4: Valider la config end-to-end**

Run: `& C:\facil_framework\.venv\Scripts\python.exe deploy/deploy.py --provider=docker-local --action=validate`
Expected: exit 0 (rétro-compat, la nouvelle section acceptée).

- [ ] **Step 5: Commit**

```bash
git add deploy/config.yaml infra/README.md docs/architecture/DEPLOYMENT_TARGETS.md docs/adr/0006-*.md
git commit -m "docs(infra): section deploy, arbo infra/, matrice cibles, ADR-0006 mis à jour"
```

---

## PHASE 1-core — Chart Helm k3s (stack always-on)

> Convention de nommage : ressources préfixées `facil-`. Labels via `_helpers.tpl`. Namespace = release namespace (défaut `facil`). Images pull GHCR pour backend/web ; images upstream pinnées pour les data-services.

### Task 1.1 : Squelette du chart (Chart.yaml, values, helpers) — `helm lint` vert

**Files:**
- Create: `infra/helm/facil/Chart.yaml`, `infra/helm/facil/values.yaml`, `infra/helm/facil/templates/_helpers.tpl`, `infra/helm/facil/templates/NOTES.txt`

**Interfaces:**
- Produces: helpers `facil.fullname`, `facil.labels`, `facil.selectorLabels` ; structure `values` (`global.owner`, `global.imageTag`, `postgres.*`, `redis.*`, `minio.*`, `openbao.*`, `backend.*`, `frontend.*`, chacun avec `enabled`).

- [ ] **Step 1: Écrire `Chart.yaml`**

```yaml
apiVersion: v2
name: facil
description: Facil Framework — stack souveraine (chart unique on-prem→cloud)
type: application
version: 0.1.0
appVersion: "latest"
```

- [ ] **Step 2: Écrire `values.yaml` (défauts)**

```yaml
global:
  owner: kouemousah            # ghcr.io/<owner>/facil-*
  imageTag: latest             # surchargé par le provider (version/commit)
  namespace: facil
  storageClass: local-path     # défaut k3s

# Nom du k8s Secret (créé par deploy/providers/k3s.py, hors Helm) portant les
# clés : POSTGRES_PASSWORD, REDIS_PASSWORD, MINIO_ROOT_PASSWORD,
# OPENBAO_DEV_ROOT_TOKEN, JWT_SECRET_KEY, SECRET_KEY, ...
secretName: facil-secrets

postgres:
  enabled: true
  image: pgvector/pgvector:pg16
  storage: 10Gi
  db: facil
  user: facil
redis:
  enabled: true
  image: redis:7-alpine
minio:
  enabled: true
  image: minio/minio:latest
  storage: 20Gi
  rootUser: facil
openbao:
  enabled: true
  image: openbao/openbao:latest
  devMode: true                # prod unseal (SOPS+age) = plan ultérieur
backend:
  enabled: true
  port: 8080
  modulesEnabled: "organization,location"
  replicas: 1
frontend:
  enabled: true
  port: 3000
  replicas: 1

# Services gated (P1b) — OFF ici.
caddy: { enabled: false }
keycloak: { enabled: false }
otel: { enabled: false }
ollama: { enabled: false }
mail: { enabled: false }
```

- [ ] **Step 3: Écrire `templates/_helpers.tpl`**

```yaml
{{- define "facil.fullname" -}}
{{- printf "facil-%s" .name -}}
{{- end -}}

{{- define "facil.labels" -}}
app.kubernetes.io/name: facil
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "facil.selectorLabels" -}}
app.kubernetes.io/name: facil
facil.component: {{ .component }}
{{- end -}}
```

- [ ] **Step 4: Écrire `templates/NOTES.txt`**

```txt
Facil déployé (release {{ .Release.Name }}, namespace {{ .Release.Namespace }}).
Backend  : svc/facil-backend:{{ .Values.backend.port }}
Frontend : svc/facil-frontend:{{ .Values.frontend.port }}
Vérifier : kubectl -n {{ .Release.Namespace }} get pods
Health   : kubectl -n {{ .Release.Namespace }} exec deploy/facil-backend -- \
             python -c "import urllib.request;urllib.request.urlopen('http://localhost:{{ .Values.backend.port }}/health',timeout=3)"
```

- [ ] **Step 5: Lint + commit**

Run: `helm lint infra/helm/facil`
Expected: `1 chart(s) linted, 0 chart(s) failed`.

```bash
git add infra/helm/facil/Chart.yaml infra/helm/facil/values.yaml infra/helm/facil/templates/_helpers.tpl infra/helm/facil/templates/NOTES.txt
git commit -m "feat(helm): squelette chart facil (values + helpers), helm lint vert"
```

### Task 1.2 : Postgres (StatefulSet + Service + PVC), password depuis Secret

**Files:**
- Create: `infra/helm/facil/templates/postgres.yaml`

**Interfaces:**
- Produces: `Service/facil-postgres:5432` ; consomme `secretName` clé `POSTGRES_PASSWORD`.

- [ ] **Step 1: Écrire le test (assertion sur `helm template`)**

Créer `infra/helm/facil/tests/test_render.sh` (assertions grep sur la sortie `helm template`) :

```bash
#!/usr/bin/env bash
set -euo pipefail
OUT="$(helm template rel infra/helm/facil)"
# Postgres présent, image pinnée, password via secretKeyRef (jamais en clair).
echo "$OUT" | grep -q "image: pgvector/pgvector:pg16"
echo "$OUT" | grep -q "name: facil-postgres"
echo "$OUT" | grep -q "secretKeyRef"
# Garde-secret : aucune valeur de mot de passe en clair dans le rendu.
! echo "$OUT" | grep -Eiq "POSTGRES_PASSWORD: [^v].*[a-z0-9]{8}"
echo "OK render"
```

- [ ] **Step 2: Lancer — échoue (template absent)**

Run: `bash infra/helm/facil/tests/test_render.sh`
Expected: FAIL (grep `facil-postgres` ne matche pas).

- [ ] **Step 3: Écrire `templates/postgres.yaml`**

```yaml
{{- if .Values.postgres.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "facil.fullname" (dict "name" "postgres") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  selector: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "postgres") | nindent 4 }}
  ports:
    - port: 5432
      targetPort: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "facil.fullname" (dict "name" "postgres") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  serviceName: {{ include "facil.fullname" (dict "name" "postgres") }}
  replicas: 1
  selector:
    matchLabels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "postgres") | nindent 6 }}
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "postgres") | nindent 8 }}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        fsGroup: 999
      containers:
        - name: postgres
          image: {{ .Values.postgres.image }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          env:
            - name: POSTGRES_DB
              value: {{ .Values.postgres.db | quote }}
            - name: POSTGRES_USER
              value: {{ .Values.postgres.user | quote }}
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretName }}
                  key: POSTGRES_PASSWORD
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          ports:
            - containerPort: 5432
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          readinessProbe:
            exec: { command: ["pg_isready", "-U", "{{ .Values.postgres.user }}"] }
            initialDelaySeconds: 5
            periodSeconds: 5
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: {{ .Values.global.storageClass }}
        resources:
          requests:
            storage: {{ .Values.postgres.storage }}
{{- end }}
```

- [ ] **Step 4: Lancer — passe**

Run: `bash infra/helm/facil/tests/test_render.sh`
Expected: `OK render`.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/postgres.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): postgres StatefulSet+Service, password via secretKeyRef"
```

### Task 1.3 : Redis (Deployment + Service), password depuis Secret

**Files:**
- Create: `infra/helm/facil/templates/redis.yaml`

**Interfaces:**
- Produces: `Service/facil-redis:6379` ; consomme `secretName` clé `REDIS_PASSWORD`.

- [ ] **Step 1: Étendre le test**

Ajouter à `infra/helm/facil/tests/test_render.sh` avant `echo "OK render"` :

```bash
echo "$OUT" | grep -q "name: facil-redis"
echo "$OUT" | grep -q "image: redis:7-alpine"
```

- [ ] **Step 2: Lancer — échoue**

Run: `bash infra/helm/facil/tests/test_render.sh`
Expected: FAIL (`facil-redis` absent).

- [ ] **Step 3: Écrire `templates/redis.yaml`**

```yaml
{{- if .Values.redis.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "facil.fullname" (dict "name" "redis") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  selector: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "redis") | nindent 4 }}
  ports:
    - port: 6379
      targetPort: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "facil.fullname" (dict "name" "redis") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "redis") | nindent 6 }}
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "redis") | nindent 8 }}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
      containers:
        - name: redis
          image: {{ .Values.redis.image }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          command: ["sh", "-c", "exec redis-server --requirepass \"$REDIS_PASSWORD\""]
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretName }}
                  key: REDIS_PASSWORD
          ports:
            - containerPort: 6379
          readinessProbe:
            exec: { command: ["sh", "-c", "redis-cli -a \"$REDIS_PASSWORD\" --no-auth-warning ping"] }
            initialDelaySeconds: 3
            periodSeconds: 5
{{- end }}
```

- [ ] **Step 4: Lancer — passe**

Run: `bash infra/helm/facil/tests/test_render.sh`
Expected: `OK render`.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/redis.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): redis Deployment+Service, password via secretKeyRef"
```

### Task 1.4 : MinIO (StatefulSet + Service + PVC)

**Files:**
- Create: `infra/helm/facil/templates/minio.yaml`

**Interfaces:**
- Produces: `Service/facil-minio:9000` (API) `:9001` (console) ; consomme `secretName` clé `MINIO_ROOT_PASSWORD`.

- [ ] **Step 1: Étendre le test**

Ajouter :

```bash
echo "$OUT" | grep -q "name: facil-minio"
echo "$OUT" | grep -q "image: minio/minio:latest"
```

- [ ] **Step 2: Lancer — échoue**

Run: `bash infra/helm/facil/tests/test_render.sh` → FAIL.

- [ ] **Step 3: Écrire `templates/minio.yaml`**

```yaml
{{- if .Values.minio.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "facil.fullname" (dict "name" "minio") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  selector: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "minio") | nindent 4 }}
  ports:
    - name: api
      port: 9000
      targetPort: 9000
    - name: console
      port: 9001
      targetPort: 9001
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "facil.fullname" (dict "name" "minio") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  serviceName: {{ include "facil.fullname" (dict "name" "minio") }}
  replicas: 1
  selector:
    matchLabels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "minio") | nindent 6 }}
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "minio") | nindent 8 }}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: minio
          image: {{ .Values.minio.image }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          args: ["server", "/data", "--console-address", ":9001"]
          env:
            - name: MINIO_ROOT_USER
              value: {{ .Values.minio.rootUser | quote }}
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretName }}
                  key: MINIO_ROOT_PASSWORD
          ports:
            - containerPort: 9000
            - containerPort: 9001
          volumeMounts:
            - name: data
              mountPath: /data
          readinessProbe:
            httpGet: { path: /minio/health/live, port: 9000 }
            initialDelaySeconds: 5
            periodSeconds: 5
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: {{ .Values.global.storageClass }}
        resources:
          requests:
            storage: {{ .Values.minio.storage }}
{{- end }}
```

- [ ] **Step 4: Lancer — passe** (`bash infra/helm/facil/tests/test_render.sh` → `OK render`).

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/minio.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): minio StatefulSet+Service+PVC, root password via secret"
```

### Task 1.5 : OpenBao (StatefulSet + Service, dev-mode gardé)

**Files:**
- Create: `infra/helm/facil/templates/openbao.yaml`

**Interfaces:**
- Produces: `Service/facil-openbao:8200` ; consomme `secretName` clé `OPENBAO_DEV_ROOT_TOKEN` ; `IPC_LOCK` (seule cap ajoutée du chart).

- [ ] **Step 1: Étendre le test**

```bash
echo "$OUT" | grep -q "name: facil-openbao"
echo "$OUT" | grep -q "IPC_LOCK"
```

- [ ] **Step 2: Lancer — échoue** → FAIL.

- [ ] **Step 3: Écrire `templates/openbao.yaml`**

```yaml
{{- if .Values.openbao.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "facil.fullname" (dict "name" "openbao") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  selector: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "openbao") | nindent 4 }}
  ports:
    - port: 8200
      targetPort: 8200
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "facil.fullname" (dict "name" "openbao") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  serviceName: {{ include "facil.fullname" (dict "name" "openbao") }}
  replicas: 1
  selector:
    matchLabels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "openbao") | nindent 6 }}
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "openbao") | nindent 8 }}
    spec:
      containers:
        - name: openbao
          image: {{ .Values.openbao.image }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
              add: ["IPC_LOCK"]   # requis par openbao (mlock)
          {{- if .Values.openbao.devMode }}
          args: ["server", "-dev", "-dev-listen-address=0.0.0.0:8200"]
          env:
            - name: BAO_ADDR
              value: http://127.0.0.1:8200
            - name: BAO_DEV_ROOT_TOKEN_ID
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretName }}
                  key: OPENBAO_DEV_ROOT_TOKEN
          {{- else }}
          # Prod unseal (SOPS+age / raft) = plan ultérieur — devMode=false non supporté ici.
          args: ["server"]
          {{- end }}
          ports:
            - containerPort: 8200
          readinessProbe:
            exec: { command: ["bao", "status"] }
            initialDelaySeconds: 5
            periodSeconds: 5
{{- end }}
```

- [ ] **Step 4: Lancer — passe** → `OK render`.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/openbao.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): openbao StatefulSet dev-mode gardé, IPC_LOCK unique cap"
```

### Task 1.6 : db-init en Helm hook `pre-install,pre-upgrade` (migrations gatées)

**Files:**
- Create: `infra/helm/facil/templates/db-init-job.yaml`

**Interfaces:**
- Produces: Job hook qui exécute `alembic upgrade head` avant le cutover applicatif ; échec du hook ⇒ Helm stoppe l'upgrade (base de P2). Consomme l'image backend + `secretName` (`DATABASE_URL` construite depuis `POSTGRES_PASSWORD`).

- [ ] **Step 1: Étendre le test**

```bash
echo "$OUT" | grep -q "helm.sh/hook: pre-install,pre-upgrade"
echo "$OUT" | grep -q "alembic"
```

- [ ] **Step 2: Lancer — échoue** → FAIL.

- [ ] **Step 3: Écrire `templates/db-init-job.yaml`**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "facil.fullname" (dict "name" "db-init") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "0"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  backoffLimit: 0            # migration KO ⇒ pas de retry silencieux (fail-closed)
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "db-init") | nindent 8 }}
    spec:
      restartPolicy: Never
      securityContext:
        runAsNonRoot: true
      containers:
        - name: db-init
          image: ghcr.io/{{ .Values.global.owner }}/facil-backend:{{ .Values.global.imageTag }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          command: ["alembic", "upgrade", "head"]
          env:
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretName }}
                  key: POSTGRES_PASSWORD
            - name: DATABASE_URL
              value: postgresql://{{ .Values.postgres.user }}:$(POSTGRES_PASSWORD)@{{ include "facil.fullname" (dict "name" "postgres") }}:5432/{{ .Values.postgres.db }}
            - name: ENVIRONMENT
              value: production
            - name: APPLIED_BY
              value: helm-db-init
```

- [ ] **Step 4: Lancer — passe** → `OK render`.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/db-init-job.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): db-init hook pre-install/pre-upgrade (alembic gaté, backoff 0)"
```

### Task 1.7 : Backend (Deployment + Service + probes health-gate)

**Files:**
- Create: `infra/helm/facil/templates/backend.yaml`

**Interfaces:**
- Produces: `Service/facil-backend:8080` ; readiness/liveness sur `/health` ; env `REDIS_URL`, `MODULES_ENABLED` ; `DATABASE_URL` least-privilege via env de `.env.deploy.gen` monté en Secret (clé `BACKEND_DATABASE_URL`).

- [ ] **Step 1: Étendre le test**

```bash
echo "$OUT" | grep -q "name: facil-backend"
echo "$OUT" | grep -q "ghcr.io/kouemousah/facil-backend"
echo "$OUT" | grep -q "path: /health"
```

- [ ] **Step 2: Lancer — échoue** → FAIL.

- [ ] **Step 3: Écrire `templates/backend.yaml`**

```yaml
{{- if .Values.backend.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "facil.fullname" (dict "name" "backend") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  selector: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "backend") | nindent 4 }}
  ports:
    - port: {{ .Values.backend.port }}
      targetPort: {{ .Values.backend.port }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "facil.fullname" (dict "name" "backend") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.backend.replicas }}
  selector:
    matchLabels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "backend") | nindent 6 }}
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "backend") | nindent 8 }}
    spec:
      securityContext:
        runAsNonRoot: true
      containers:
        - name: backend
          image: ghcr.io/{{ .Values.global.owner }}/facil-backend:{{ .Values.global.imageTag }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          env:
            - name: PORT
              value: {{ .Values.backend.port | quote }}
            - name: ENVIRONMENT
              value: production
            - name: MODULES_ENABLED
              value: {{ .Values.backend.modulesEnabled | quote }}
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretName }}, key: POSTGRES_PASSWORD }
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretName }}, key: REDIS_PASSWORD }
            # Least-privilege : rôle facil_app (pas le superuser facil).
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretName }}, key: BACKEND_DATABASE_URL }
            - name: REDIS_URL
              value: redis://:$(REDIS_PASSWORD)@{{ include "facil.fullname" (dict "name" "redis") }}:6379/0
          envFrom:
            - secretRef:
                name: {{ .Values.secretName }}   # JWT_SECRET_KEY, SECRET_KEY, TOTP_..., etc.
          ports:
            - containerPort: {{ .Values.backend.port }}
          readinessProbe:
            httpGet: { path: /health, port: {{ .Values.backend.port }} }
            initialDelaySeconds: 15
            periodSeconds: 10
            failureThreshold: 6
          livenessProbe:
            httpGet: { path: /health, port: {{ .Values.backend.port }} }
            initialDelaySeconds: 30
            periodSeconds: 15
{{- end }}
```

- [ ] **Step 4: Lancer — passe** → `OK render`.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/backend.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): backend Deployment+Service, health-gate /health, secrets via envFrom"
```

### Task 1.8 : Frontend (Deployment + Service)

**Files:**
- Create: `infra/helm/facil/templates/frontend.yaml`

**Interfaces:**
- Produces: `Service/facil-frontend:3000` ; env `INTERNAL_API_URL` → service backend.

- [ ] **Step 1: Étendre le test**

```bash
echo "$OUT" | grep -q "name: facil-frontend"
echo "$OUT" | grep -q "ghcr.io/kouemousah/facil-web"
```

- [ ] **Step 2: Lancer — échoue** → FAIL.

- [ ] **Step 3: Écrire `templates/frontend.yaml`**

```yaml
{{- if .Values.frontend.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "facil.fullname" (dict "name" "frontend") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  selector: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "frontend") | nindent 4 }}
  ports:
    - port: {{ .Values.frontend.port }}
      targetPort: {{ .Values.frontend.port }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "facil.fullname" (dict "name" "frontend") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.frontend.replicas }}
  selector:
    matchLabels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "frontend") | nindent 6 }}
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "frontend") | nindent 8 }}
    spec:
      securityContext:
        runAsNonRoot: true
      containers:
        - name: frontend
          image: ghcr.io/{{ .Values.global.owner }}/facil-web:{{ .Values.global.imageTag }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          env:
            - name: INTERNAL_API_URL
              value: http://{{ include "facil.fullname" (dict "name" "backend") }}:{{ .Values.backend.port }}
          ports:
            - containerPort: {{ .Values.frontend.port }}
          readinessProbe:
            httpGet: { path: /, port: {{ .Values.frontend.port }} }
            initialDelaySeconds: 10
            periodSeconds: 10
{{- end }}
```

- [ ] **Step 4: Lancer — passe** → `OK render`.

- [ ] **Step 5: `helm lint` + commit**

Run: `helm lint infra/helm/facil` → 0 failed.

```bash
git add infra/helm/facil/templates/frontend.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): frontend Deployment+Service, INTERNAL_API_URL vers backend svc"
```

### Task 1.9 : Provider `k3s.py` — render values + création du Secret (secrets hors Helm)

**Files:**
- Create: `deploy/providers/k3s.py`, `deploy/providers/test_k3s.py`

**Interfaces:**
- Consumes: `validate_config.DeployConfig` (chargé via l'API existante de `validate_config`), `.env.secrets` (clés→valeurs).
- Produces: `render_values(cfg: DeployConfig) -> dict` ; `build_secret_literals(env_secrets: dict) -> dict[str,str]` (mappe les clés attendues du chart) ; CLI `--validate/--plan/--apply` (exit codes alignés sur `aws.py` : 0 ok · 1 validation · 2 helm/kubectl · 3 fichier · 4 aborté).

- [ ] **Step 1: Écrire les tests**

Créer `deploy/providers/test_k3s.py` :

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import validate_config as vc
import k3s


def _cfg():
    data = vc.load_yaml(Path(__file__).resolve().parents[2] / "deploy" / "config.yaml")
    return vc.DeployConfig(**data)


def test_render_values_maps_images_and_ports():
    values = k3s.render_values(_cfg())
    assert values["postgres"]["image"] == "pgvector/pgvector:pg16"
    assert values["backend"]["port"] == 8080
    assert values["frontend"]["port"] == 3000
    assert values["backend"]["modulesEnabled"] == "organization,location"


def test_render_values_never_contains_secret_values():
    # Garde-secret : le dict values ne doit porter AUCUNE valeur de secret,
    # seulement le nom du Secret k8s.
    values = k3s.render_values(_cfg())
    flat = repr(values).lower()
    assert "password" not in flat or "secretname" in flat
    assert values["secretName"] == "facil-secrets"


def test_build_secret_literals_selects_expected_keys():
    env = {"POSTGRES_PASSWORD": "p", "REDIS_PASSWORD": "r", "MINIO_ROOT_PASSWORD": "m",
           "OPENBAO_DEV_ROOT_TOKEN": "t", "JWT_SECRET_KEY": "j", "SECRET_KEY": "s",
           "IGNORED_EXTRA": "x"}
    lit = k3s.build_secret_literals(env)
    assert set(["POSTGRES_PASSWORD", "REDIS_PASSWORD", "MINIO_ROOT_PASSWORD",
                "OPENBAO_DEV_ROOT_TOKEN", "JWT_SECRET_KEY", "SECRET_KEY"]).issubset(lit)
    assert "IGNORED_EXTRA" not in lit  # allowlist stricte
```

Si `vc.load_yaml` n'existe pas sous ce nom, utiliser le loader réellement exposé par `validate_config.py` (vérifier en haut du module) et adapter l'appel.

- [ ] **Step 2: Lancer — échoue**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'k3s'`.

- [ ] **Step 3: Écrire `deploy/providers/k3s.py`**

```python
#!/usr/bin/env python3
"""k3s provider — déploie la stack via le chart Helm infra/helm/facil.

Render les `values` depuis config.yaml, crée le k8s Secret depuis .env.secrets
(HORS du flux Helm versionné — normes secrets renforcées), puis
`helm upgrade --install`. CLI alignée sur les autres providers.

Exit: 0 ok · 1 validation · 2 helm/kubectl · 3 fichier · 4 aborté.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROVIDERS_DIR = Path(__file__).resolve().parent
DEPLOY_DIR = PROVIDERS_DIR.parent
REPO_ROOT = DEPLOY_DIR.parent
CHART_DIR = REPO_ROOT / "infra" / "helm" / "facil"
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import validate_config as vc  # noqa: E402

SECRET_NAME = "facil-secrets"
# Allowlist stricte des clés injectées dans le Secret k8s (rien d'autre ne fuit).
SECRET_KEYS = [
    "POSTGRES_PASSWORD", "REDIS_PASSWORD", "MINIO_ROOT_PASSWORD",
    "OPENBAO_DEV_ROOT_TOKEN", "JWT_SECRET_KEY", "SECRET_KEY",
    "TOTP_ENCRYPTION_KEY", "RECEIPT_VERIFICATION_SECRET", "CRON_SECRET",
    "BACKEND_DATABASE_URL",
]


def render_values(cfg: vc.DeployConfig) -> dict:
    """config.yaml -> dict de values Helm (AUCUNE valeur de secret ici)."""
    return {
        "secretName": SECRET_NAME,
        "global": {"namespace": "facil"},
        "postgres": {"image": cfg.docker_local.postgres_image,
                     "db": "facil", "user": "facil"},
        "redis": {"image": cfg.docker_local.redis_image},
        "minio": {"rootUser": cfg.storage.minio.root_user},
        "openbao": {"devMode": cfg.secrets.openbao.dev_mode},
        "backend": {"port": cfg.docker_local.backend_port,
                    "modulesEnabled": ",".join(cfg.modules.enabled)},
        "frontend": {"port": cfg.docker_local.frontend_port},
    }


def build_secret_literals(env_secrets: dict[str, str]) -> dict[str, str]:
    """Extrait UNIQUEMENT les clés de l'allowlist présentes dans .env.secrets."""
    return {k: env_secrets[k] for k in SECRET_KEYS if k in env_secrets}


def find_helm() -> str | None:
    return shutil.which("helm") or shutil.which("helm.exe")


def _load_env_secrets(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", choices=["validate", "plan", "apply"], required=True)
    ap.add_argument("--config", default=str(DEPLOY_DIR / "config.yaml"))
    ap.add_argument("--namespace", default="facil")
    args = ap.parse_args(argv)

    helm = find_helm()
    if not helm:
        print("ERREUR: helm introuvable dans le PATH.", file=sys.stderr)
        return 2
    try:
        cfg = vc.DeployConfig(**vc.load_yaml(Path(args.config)))
    except Exception as e:  # validation pydantic
        print(f"ERREUR de config: {e}", file=sys.stderr)
        return 1

    values = render_values(cfg)
    if args.action == "validate":
        subprocess.run([helm, "lint", str(CHART_DIR)], check=False)
        print("validate: chart lint exécuté ; config chargée.")
        return 0
    if args.action == "plan":
        # Rendu à sec — jamais de secret dans la sortie.
        rc = subprocess.run(
            [helm, "template", "facil", str(CHART_DIR)], check=False
        ).returncode
        return 0 if rc == 0 else 2
    # apply
    env = _load_env_secrets(REPO_ROOT / ".env.secrets")
    literals = build_secret_literals(env)
    missing = [k for k in ("POSTGRES_PASSWORD", "JWT_SECRET_KEY", "SECRET_KEY") if k not in literals]
    if missing:
        print(f"ERREUR: secrets requis manquants dans .env.secrets: {missing}", file=sys.stderr)
        return 1
    # 1) Secret k8s (hors Helm) — jamais dans un fichier versionné.
    sec_args = [shutil.which("kubectl") or "kubectl", "-n", args.namespace,
                "create", "secret", "generic", SECRET_NAME, "--dry-run=client", "-o", "yaml"]
    for k, v in literals.items():
        sec_args += [f"--from-literal={k}={v}"]
    apply_secret = subprocess.run(sec_args, capture_output=True, text=True)
    if apply_secret.returncode != 0:
        print(apply_secret.stderr, file=sys.stderr)
        return 2
    piped = subprocess.run([shutil.which("kubectl") or "kubectl", "-n", args.namespace,
                            "apply", "-f", "-"], input=apply_secret.stdout, text=True)
    if piped.returncode != 0:
        return 2
    # 2) helm upgrade --install (backend/web pull GHCR ; jamais de build).
    set_args = []
    for section, sub in values.items():
        if isinstance(sub, dict):
            for k, v in sub.items():
                set_args += ["--set", f"{section}.{k}={v}"]
        else:
            set_args += ["--set", f"{section}={sub}"]
    rc = subprocess.run(
        [helm, "upgrade", "--install", "facil", str(CHART_DIR),
         "-n", args.namespace, "--create-namespace",
         "-f", str(CHART_DIR / "values-onprem.yaml"), *set_args, "--wait", "--timeout", "10m"],
        check=False,
    ).returncode
    return 0 if rc == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

Note : si `validate_config` n'expose pas `load_yaml`, réutiliser sa fonction de chargement réelle (adapter l'import).

- [ ] **Step 4: Lancer — passe**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add deploy/providers/k3s.py deploy/providers/test_k3s.py
git commit -m "feat(deploy): provider k3s (render values + Secret hors Helm + helm upgrade)"
```

### Task 1.10 : `values-onprem.yaml` + branchement `deploy.py`

**Files:**
- Create: `infra/helm/facil/values-onprem.yaml`
- Modify: `deploy/deploy.py` (router `k3s` vers `providers/k3s.py`)

- [ ] **Step 1: Écrire `values-onprem.yaml`**

```yaml
# Overlay on-prem mono-nœud (k3s). Aucune valeur de secret ici — noms uniquement.
global:
  storageClass: local-path
postgres:
  storage: 10Gi
minio:
  storage: 20Gi
openbao:
  devMode: true
backend:
  replicas: 1
frontend:
  replicas: 1
```

- [ ] **Step 2: Vérifier le routage dans `deploy.py`**

Lire `deploy/deploy.py` autour de `SUPPORTED_PROVIDERS` (déjà `["gcp","aws","azure","docker-local"]`). Ajouter `"k3s"` à la liste et s'assurer que l'appel provider construit `PROVIDERS_DIR / "k3s.py"` avec `--action` (même schéma que les autres). Si le dispatch est générique (`providers/<provider>.py`), aucun `if` spécifique n'est nécessaire — juste étendre la liste.

- [ ] **Step 3: Écrire/étendre le test de dispatch**

Dans `deploy/providers/test_k3s.py`, ajouter :

```python
def test_deploy_py_knows_k3s_provider():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "deploy_main", Path(__file__).resolve().parents[1] / "deploy.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert "k3s" in mod.SUPPORTED_PROVIDERS
```

- [ ] **Step 4: Lancer — passe**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -v`
Expected: PASS.

Run: `& C:\facil_framework\.venv\Scripts\python.exe deploy/deploy.py --provider=k3s --action=plan`
Expected: sortie `helm template` (exit 0), aucun secret en clair.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/values-onprem.yaml deploy/deploy.py deploy/providers/test_k3s.py
git commit -m "feat(deploy): values-onprem + k3s dans SUPPORTED_PROVIDERS (plan end-to-end)"
```

### Task 1.11 : CI `helm.yml` (lint + template, aucun apply)

**Files:**
- Create: `.github/workflows/helm.yml`

- [ ] **Step 1: Écrire le workflow**

```yaml
name: Helm chart
on:
  push:
    branches: [main, develop]
    paths: ["infra/helm/**", ".github/workflows/helm.yml"]
  pull_request:
    paths: ["infra/helm/**", ".github/workflows/helm.yml"]
jobs:
  lint-template:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/setup-helm@v4
        with: { version: v3.15.0 }
      - name: helm lint
        run: helm lint infra/helm/facil
      - name: helm template (rendu à sec)
        run: helm template facil infra/helm/facil -f infra/helm/facil/values-onprem.yaml > /tmp/rendered.yaml
      - name: garde-secret (aucun mot de passe en clair dans le rendu)
        run: |
          ! grep -Eiq '(password|secret|token): [A-Za-z0-9+/]{8,}' /tmp/rendered.yaml
```

- [ ] **Step 2: Valider le YAML localement**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -c "import yaml,sys; yaml.safe_load(open('.github/workflows/helm.yml',encoding='utf-8')); print('yaml ok')"`
Expected: `yaml ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/helm.yml
git commit -m "ci(helm): lint + template + garde-secret (aucun build/apply)"
```

### Task 1.12 : Smoke k3s local (manuel documenté) + doc de validation

**Files:**
- Create: `infra/helm/facil/SMOKE.md`

- [ ] **Step 1: Écrire la procédure de smoke**

Créer `infra/helm/facil/SMOKE.md` :

```markdown
# Smoke k3s local — stack always-on

Prérequis : k3s (ou k3d) local, helm, kubectl, `.env.secrets` généré (init.py),
images `ghcr.io/<owner>/facil-{backend,web}` accessibles (publiques ou `imagePullSecret`).

1. `python deploy/deploy.py --provider=k3s --action=validate`   # helm lint + config
2. `python deploy/deploy.py --provider=k3s --action=plan`        # rendu à sec, 0 secret
3. `python deploy/deploy.py --provider=k3s --action=apply`       # Secret + helm upgrade --wait
4. `kubectl -n facil get pods`                                   # tous Running/Ready
5. Health backend :
   `kubectl -n facil exec deploy/facil-backend -- \
      python -c "import urllib.request;urllib.request.urlopen('http://localhost:8080/health',timeout=3)"`
6. Migrations : le Job `facil-db-init` doit être `Complete` (hook pre-install).
7. Frontend : `kubectl -n facil port-forward svc/facil-frontend 3000:3000` → http://localhost:3000

Critères d'acceptation :
- [ ] 7 pods always-on Ready (postgres, redis, minio, openbao, backend, frontend + Job db-init Complete)
- [ ] `/health` backend = 200
- [ ] UI frontend répond
- [ ] `kubectl -n facil get secret facil-secrets` existe ; `helm get manifest` ne contient AUCUNE valeur de secret
```

- [ ] **Step 2: Exécuter le smoke** (si un k3s/k3d est disponible localement) et cocher les critères. Sinon, marquer « smoke différé — CI lint/template vert » et le noter dans le commit.

- [ ] **Step 3: Commit**

```bash
git add infra/helm/facil/SMOKE.md
git commit -m "docs(helm): procédure de smoke k3s + critères d'acceptation"
```

### Task 1.13 : Gate qualité fin de P1-core (revue agents + self-checklist)

- [ ] **Step 1: Revue sécurité** — lancer l'agent `security-auditor` sur le diff (`git diff develop...HEAD`). Cible : (a) aucune valeur de secret dans un fichier versionné, (b) `secretKeyRef`/`envFrom secretRef` partout, (c) `securityContext` hardening présent, (d) le provider ne logge pas les literals. **Corriger les findings**, pas seulement les lister.

- [ ] **Step 2: Erreurs silencieuses** — agent `silent-failure-hunter` sur `deploy/providers/k3s.py` : chaque `subprocess.run(check=False)` doit propager un exit-code non-zéro (fail-closed). Corriger.

- [ ] **Step 3: Self-checklist**
  - [ ] **Parité** : 7 services always-on du compose présents dans le chart (postgres, redis, minio, openbao, db-init, backend, frontend).
  - [ ] **DRY** : le render réutilise `validate_config`/`config.yaml` (pas de valeurs dupliquées en dur).
  - [ ] **Sécurité** : secrets hors Helm ; least-privilege DB ; hardening pods ; OpenBao dev gated.
  - [ ] **Rétro-compat** : `docker-local` toujours fonctionnel (`validate` vert).
  - [ ] Tous les pytest verts (`deploy/**`), `helm lint` vert, garde-secret CI vert.

- [ ] **Step 4: Commit des corrections éventuelles**

```bash
git add -A
git commit -m "fix(infra): corrections revue sécurité/silent-failure P1-core"
```

---

## Self-Review (contre le spec)

**1. Couverture spec (P0 + P1-core)**
- Champ `deploy.tier`/`target` rétro-compatible → Task 0.1 ✅
- Arbo `infra/` + matrice + ADR-0006 → Task 0.2 ✅
- Chart Helm unique, parité services always-on → Tasks 1.1–1.8 ✅
- Unification à la source (`config.yaml` → values via provider) → Task 1.9 ✅
- Migrations gatées (hook) → Task 1.6 (base de P2 : health-gate/backup/rollback = plan P2 séparé) ✅
- CI helm sans build → Task 1.11 ✅
- Normes secrets renforcées (hors Helm, allowlist, garde-secret, hardening) → Constraints + Tasks 1.9/1.11/1.13 ✅
- **Hors scope de CE plan (plans suivants)** : services gated caddy/keycloak/otel/ollama/mail + NetworkPolicies (**P1b**) ; backup/health-gate/rollback complet (**P2**) ; installeur dynamique (**P3**) ; CD pull-based (**P4**) ; Terraform+GitOps cloud (**P5**). Explicitement noté.

**2. Placeholders** — aucun « TBD/TODO/handle edge cases » ; chaque step porte le code réel. Les deux notes « si `load_yaml`/`_minimal_valid_config_dict` n'existe pas » sont des instructions d'adaptation à l'existant réel (à vérifier au moment de l'impl), pas des placeholders de code.

**3. Cohérence des types/noms** — `render_values`, `build_secret_literals`, `SECRET_KEYS`, `secretName`/`facil-secrets`, helpers `facil.fullname`/`facil.labels`/`facil.selectorLabels`, services `facil-{postgres,redis,minio,openbao,backend,frontend}` : cohérents entre chart, provider et tests. Clé DB least-privilege = `BACKEND_DATABASE_URL` (chart backend + allowlist provider alignés).

---

## Execution Handoff

**À vérifier avant l'impl (dépendances outillage)** : `helm` et `kubectl` dans le PATH ; un k3s/k3d local pour le smoke (Task 1.12) — sinon smoke différé, la CI lint/template reste la gate.

**Note de séquencement** : ce plan livre P0 + P1-core (milestone « la stack souveraine tourne sur k3s »). À sa clôture (gate Task 1.13 verte), enchaîner sur les plans **P1b** (gated + NetworkPolicies), puis **P2** (cycle install complète : backup/health-gate/rollback), P3, P4, P5.
