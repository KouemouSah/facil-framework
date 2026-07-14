# P2 — Cycle de mise à jour sûr (backup · health-gate · rollback) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre le chart k3s **mettable à jour sans risque de perte de données**. Aujourd'hui il est déployable et prouvé, mais une migration Alembic destructive détruit les données d'un client **sans recours** : `--atomic` rollback les *manifestes*, jamais la *base*. La spec appelle ça une « gate on-prem souverain **non négociable** » — elle n'existe pas.

**Architecture:** Un Job Helm en hook **`pre-upgrade`** (weight `-2`, donc **avant** `db-role` à `-1` et `db-init` à `0`) sauvegarde Postgres (`pg_dump`) et les buckets MinIO (`mc mirror`) dans un **PVC dédié**, horodatés. Le Job est **fail-closed** : si la sauvegarde échoue, le hook échoue, `helm upgrade` avorte — **avant** la migration. Le provider `k3s.py` gagne une action `--rollback` (`helm rollback` + procédure de restauration DB documentée) et un **health-gate explicite** post-upgrade.

**Tech Stack:** Helm 3, k3s, Python 3.12 (pytest), Alembic, `pg_dump` (image `pgvector/pgvector:pg16` **déjà épinglée**), `mc` (présent dans l'image `minio/minio` **déjà épinglée** — vérifié : `/usr/bin/mc`). **Aucune image nouvelle**, donc aucun digest supplémentaire à épingler et aucune surface d'attaque ajoutée.

## Global Constraints

- **Python** : `C:\facil_framework\.venv\Scripts\python.exe` (3.12). Tests = pytest, vraie validation.
- **Répertoire de travail** : worktree `C:\facil-infra`. Branche depuis `origin/develop`.
- **Zéro régression** : `deploy.py --provider=docker-local --action=validate` → exit 0 ; `pytest deploy/ infra/helm/facil/tests/` vert **y compris sans `deploy/config.yaml`** (condition CI — le vérifier en le renommant).
- **Fail-closed, c'est le cœur du lot** : une sauvegarde qui échoue **doit** faire échouer l'upgrade **avant** la migration. Une sauvegarde silencieusement vide est **pire que pas de sauvegarde** — elle crée une fausse confiance. Le Job doit **vérifier que le dump n'est pas vide** et échouer sinon.
- **Moindre privilège (SEC-001)** : le Job de backup a besoin du **superuser Postgres** et du **root MinIO**. Il reçoit son **propre Secret** (`facil-backup-secret`), jamais celui du backend. Le backend ne doit **toujours** détenir aucun credential root — c'est vérifié par un test existant, ne le casse pas.
- **Aucun secret dans l'argv** (CWE-214) : ce projet a déjà fermé ce canal **trois fois** (`kubectl --from-literal`, `psql -v app_pw=`, `redis --requirepass`). `pg_dump` lit `PGPASSWORD` depuis l'environnement (jamais l'argv) ; `mc` utilise `MC_HOST_<alias>` (env) — **jamais** `mc alias set … <secret>` en ligne de commande. La garde `guard_secrets.py` refuse déjà tout flag à credential dans `command`/`args` : elle doit rester verte.
- **Assertions négatives en bash — JAMAIS `! cmd | grep -q`** : POSIX exempte d'`errexit` toute commande inversée par `!` → **assertion morte**. Toujours `if …; then echo "FAIL: …" >&2; exit 1; fi`.
- **Ne jamais piper un gros buffer dans un consommateur qui sort tôt** (`grep -q`, `head`, `awk … exit`) : course EPIPE **non déterministe** (bug réel vécu ici). `test_render.sh` matérialise déjà le rendu dans `$OUT_FILE` — lire ce fichier.
- **Preuve par mutation obligatoire** pour chaque garde : casser le code, voir le test rougir, restaurer, rapporter la sortie réelle. Ce projet a éliminé **onze** tests qui ne pouvaient pas échouer.
- **Header de commit ≤ 100 caractères. JAMAIS de `#<numéro>` dans le CORPS** d'un message (`conventional-commits-parser` le lit comme une référence → `footer-leading-blank` échoue). Scopes autorisés : `helm`, `deploy`, `infra`, `ci`, `security`…
- **Push = accord explicite.**

## Hors périmètre — décidé, pas oublié

- **« Seed de profil idempotent »** (listé par la spec comme livrable P2) : **retiré, sur prémisse fausse**. La spec dit « appliquer le seed du profil (`deploy/scripts/profiles.py`) », mais `profiles.py::apply_profile_defaults(cfg, profile)` remplit **un dict de config du wizard** — c'est de la configuration, **pas du seed de base**. Aucun mécanisme de seed de la BD n'existe dans le repo (`db-init` ne lance qu'`alembic upgrade head`). Le tenir supposerait d'**inventer** un mécanisme de seeding, ce qui n'a **aucun rapport** avec la sûreté des mises à jour — l'objet de P2. À traiter séparément si le besoin est réel.
- **Restauration automatique de la base** : on livre la **procédure** et le **script** de restauration, pas un `--restore` automatique. Restaurer une base par-dessus une release en cours est une opération destructive qui exige une décision humaine ; l'automatiser serait un pistolet chargé. La spec dit d'ailleurs « **note** de restauration DB ».
- **Chiffrement des sauvegardes at-rest** : les backups vivent sur le PVC, donc sur le disque du nœud. Le chiffrement relève du volume (LUKS + OpenBao), déjà tracé dans `reference_minio_encryption_at_rest`. **Documenter la limite**, ne pas la masquer.

---

## File Structure

**Créés :**
- `infra/helm/facil/templates/backup-pvc.yaml` — PVC dédié aux sauvegardes (taille configurable).
- `infra/helm/facil/templates/backup-job.yaml` — Job hook `pre-upgrade` (weight `-2`) : `pg_dump` + `mc mirror` + vérification de non-vacuité + rétention.
- `infra/helm/facil/tests/guard_backup.py` — garde parsée : le Job existe, tourne **avant** les migrations, est fail-closed, ne fuit aucun secret en argv.
- `infra/helm/facil/tests/test_guard_backup.py` — preuves par mutation.
- `deploy/scripts/restore_backup.py` — script de restauration **assisté** (liste les sauvegardes, restaure celle choisie, exige une confirmation explicite).
- `deploy/scripts/test_restore_backup.py`.
- `infra/helm/facil/RESTORE.md` — procédure de restauration + limites (pas de chiffrement at-rest).

**Modifiés :**
- `infra/helm/facil/values.yaml` — section `backup` (`enabled`, `storage`, `retain`, `secretNames.backup`).
- `deploy/providers/k3s.py` — Secret `facil-backup-secret`, action `--rollback`, health-gate explicite post-upgrade.
- `deploy/providers/test_k3s.py` — tests des trois ci-dessus.
- `infra/helm/facil/tests/test_render.sh` — appel de `guard_backup.py`.
- `.github/workflows/helm.yml` — rien à changer : il lance déjà `pytest infra/helm/facil/tests` (répertoire entier).

---

## PHASE A — Sauvegarde avant migration (le cœur)

### Task A1 : PVC de sauvegarde + Secret dédié (moindre privilège)

**Files:**
- Create: `infra/helm/facil/templates/backup-pvc.yaml`
- Modify: `infra/helm/facil/values.yaml`, `deploy/providers/k3s.py`
- Test: `deploy/providers/test_k3s.py`

**Interfaces:**
- Produces: `values.backup.{enabled,storage,retain}` · `values.secretNames.backup` (= `facil-backup-secret`) · dans `k3s.py`, l'entrée `"backup"` de `build_secret_literals()` (clés `POSTGRES_PASSWORD` + `MINIO_ROOT_PASSWORD`) et de `SECRET_NAMES`.

**Contexte moindre privilège (à ne pas contourner) :** le Job de backup a **légitimement** besoin du superuser Postgres (pour un `pg_dump` complet) et du root MinIO (pour lire tous les buckets). Ces credentials existent déjà, cloisonnés par composant. **Ne réutilise PAS le Secret du backend** — un test existant (`test_backend_never_receives_infrastructure_root_credentials`) garantit que le backend n'a aucun credential root, et il doit rester vert.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `deploy/providers/test_k3s.py` :

```python
def test_backup_secret_holds_only_what_the_backup_job_needs():
    # Le Job de backup a besoin du superuser PG (dump complet) et du root MinIO
    # (lire tous les buckets) -- mais de RIEN d'autre. Un Secret dedie, jamais
    # celui du backend (SEC-001 : une RCE dans le backend ne doit pas livrer le
    # data-plane, et ce test-la doit rester vert).
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    assert set(lit["backup"]) == {"POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD"}
    assert k3s.SECRET_NAMES["backup"] == "facil-backup-secret"


def test_backend_still_has_no_root_credentials_after_adding_backup():
    # Garde-fou explicite : l'ajout du composant "backup" ne doit pas rouvrir le
    # blast radius qu'on a ferme.
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    backend = lit["backend"]
    assert "POSTGRES_PASSWORD" not in backend
    assert "MINIO_ROOT_PASSWORD" not in backend
    assert "OPENBAO_DEV_ROOT_TOKEN" not in backend
```

- [ ] **Step 2: Lancer — échouent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -k backup -v`
Expected: FAIL — `KeyError: 'backup'`.

- [ ] **Step 3: Implémenter**

Dans `deploy/providers/k3s.py`, ajouter à `SECRET_NAMES` :

```python
    "backup": "facil-backup-secret",
```

et dans `build_secret_literals()`, avant le `return` :

```python
    # Le Job de backup (hook pre-upgrade) : dump Postgres complet (superuser) +
    # mirror des buckets MinIO (root). Ses propres credentials, cloisonnes --
    # jamais ceux du backend.
    out["backup"] = pick("POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD")
```

Dans `infra/helm/facil/values.yaml`, ajouter à `secretNames` :

```yaml
  backup: facil-backup-secret
```

…et une section `backup` :

```yaml
# Sauvegarde AVANT migration (hook pre-upgrade). Sans elle, une migration Alembic
# destructive detruit les donnees sans recours : `--atomic` rollback les manifestes,
# JAMAIS la base. La spec appelle ca une gate "non negociable".
backup:
  enabled: true
  storage: 10Gi       # dimensionner selon la taille de la base + des buckets
  retain: 5           # nombre de sauvegardes horodatees conservees
```

- [ ] **Step 4: Écrire `templates/backup-pvc.yaml`**

```yaml
{{- if .Values.backup.enabled }}
{{/*
PVC dedie aux sauvegardes. PAS un volumeClaimTemplate : le Job de backup est un
hook ephemere, il ne possede pas de StatefulSet -- le volume doit lui SURVIVRE
(c'est tout l'interet). D'ou un PersistentVolumeClaim autonome, conserve entre
les releases (annotation helm.sh/resource-policy: keep : un `helm uninstall` ne
doit PAS emporter les sauvegardes avec lui).
*/}}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "facil.fullname" (dict "name" "backups") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
  annotations:
    "helm.sh/resource-policy": keep
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: {{ .Values.global.storageClass }}
  resources:
    requests:
      storage: {{ .Values.backup.storage }}
{{- end }}
```

- [ ] **Step 5: Lancer — passent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/ -q` puis `helm lint infra/helm/facil`
Expected: PASS / 0 failed.

- [ ] **Step 6: Commit**

```bash
git add infra/helm/facil/values.yaml infra/helm/facil/templates/backup-pvc.yaml deploy/providers/k3s.py deploy/providers/test_k3s.py
git commit -m "feat(helm): PVC de sauvegarde + Secret backup dedie (moindre privilege)"
```

### Task A2 : Job de sauvegarde `pre-upgrade` — fail-closed, avant les migrations

**Files:**
- Create: `infra/helm/facil/templates/backup-job.yaml`
- Test: `infra/helm/facil/tests/test_render.sh`

**Interfaces:**
- Produces: Job `facil-backup`, hook `pre-upgrade`, `hook-weight: "-2"` (donc **avant** `db-role` à `-1` et `db-init` à `0`).

**Décisions de conception (ne pas re-débattre) :**
- **`pre-upgrade` SEULEMENT**, pas `post-install` : à une première installation il n'y a **rien à sauvegarder**. ⚠️ **Mais attention** : `k3s.py --apply` fait **deux `helm upgrade`** au premier install (la danse `backend.replicas=0` qui règle le deadlock). La **2ᵉ passe est un upgrade**, donc les hooks `pre-upgrade` **se déclencheront** — sur une base qui vient de naître. C'est inoffensif (le dump sera minuscule) mais **il faut que le Job le tolère** : une base vide n'est pas une erreur. La vérification de non-vacuité porte sur le **fichier de dump**, pas sur le nombre de lignes métier.
- **Deux images, aucune nouvelle** : `pg_dump` vient de `pgvector/pgvector:pg16` (déjà épinglée, déjà utilisée par les initContainers), `mc` vient de `minio/minio` (déjà épinglée — vérifié : `mc` est à `/usr/bin/mc`). Le Job utilise le **premier en initContainer** (dump) et le **second en container** (mirror + rétention), tous deux montant le PVC.
- **Aucun secret dans l'argv** : `pg_dump` lit `PGPASSWORD` depuis l'environnement. `mc` utilise **`MC_HOST_facil`** (variable d'environnement de la forme `http://user:pass@host:9000`) — **jamais** `mc alias set` en ligne de commande, qui exposerait le secret dans `/proc/<pid>/cmdline`.

- [ ] **Step 1: Étendre le test de rendu**

Ajouter à `infra/helm/facil/tests/test_render.sh` (avant l'appel des gardes parsées) :

```bash
# P2 : la sauvegarde doit tourner AVANT les migrations, sinon elle ne protege rien.
assert_job_hook "backup" "facil/templates/backup-job.yaml" "-2"
```

(la fonction `assert_job_hook` existe déjà et est scopée **par Job** — la réutiliser, ne pas en écrire une autre.)

- [ ] **Step 2: Lancer — échoue**

Run: `bash infra/helm/facil/tests/test_render.sh`
Expected: FAIL — le Job `facil-backup` n'existe pas.

- [ ] **Step 3: Écrire `templates/backup-job.yaml`**

```yaml
{{- if and .Values.backup.enabled .Values.postgres.enabled }}
{{/*
Sauvegarde AVANT migration. C'est la seule chose qui separe un client d'une perte
de donnees irreversible : `--atomic` rollback les MANIFESTES, jamais la BASE. Une
migration Alembic destructive (DROP COLUMN, DROP TABLE) est irrattrapable sans ce
dump.

hook `pre-upgrade` SEULEMENT (rien a sauvegarder a la 1ere installation) et
hook-weight -2 : avant db-role (-1) et db-init (0). L'ordre est l'invariant.

FAIL-CLOSED : si le dump echoue OU s'il est vide, le Job echoue -> le hook echoue
-> `helm upgrade` avorte AVANT la migration. Une sauvegarde silencieusement vide
serait PIRE que pas de sauvegarde : elle cree une fausse confiance.

Aucune image nouvelle : pg_dump vient de l'image postgres deja epinglee, mc de
l'image minio deja epinglee (/usr/bin/mc).
*/}}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "facil.fullname" (dict "name" "backup") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
  annotations:
    helm.sh/hook: pre-upgrade
    helm.sh/hook-weight: "-2"
    helm.sh/hook-delete-policy: before-hook-creation
spec:
  backoffLimit: 1        # une sauvegarde ratee ne doit pas etre retentee indefiniment
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "backup") | nindent 8 }}
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      {{- include "facil.imagePullSecrets" . | nindent 6 }}
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        fsGroup: 999
        seccompProfile: { type: RuntimeDefault }
      initContainers:
        - name: dump-postgres
          image: {{ .Values.postgres.image }}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          # PGPASSWORD est lu depuis l'ENVIRONNEMENT par pg_dump -- jamais passe en
          # argv (CWE-214 : /proc/<pid>/cmdline est lisible). Ce projet a deja ferme
          # ce canal trois fois.
          env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretNames.backup }}
                  key: POSTGRES_PASSWORD
            - name: PGHOST
              value: {{ include "facil.fullname" (dict "name" "postgres") }}
            - name: PGUSER
              value: {{ .Values.postgres.user | quote }}
            - name: PGDATABASE
              value: {{ .Values.postgres.db | quote }}
          command: ["sh", "-c"]
          args:
            - |
              set -eu
              TS="$(date -u +%Y%m%dT%H%M%SZ)"
              DEST="/backups/${TS}"
              mkdir -p "$DEST"
              echo "sauvegarde Postgres -> ${DEST}/postgres.dump" >&2
              # -Fc = format custom (compresse, restaurable selectivement par pg_restore)
              pg_dump -Fc -f "${DEST}/postgres.dump"
              # FAIL-CLOSED : un dump vide est pire que pas de dump (fausse confiance).
              # NB : une base neuve produit un dump PETIT mais jamais VIDE (en-tete +
              # schema) -- ce test tolere donc la 2e passe du premier `--apply`.
              if [ ! -s "${DEST}/postgres.dump" ]; then
                echo "FAIL: le dump Postgres est vide -- upgrade avorte AVANT migration." >&2
                exit 1
              fi
              echo "$TS" > /backups/.latest
          volumeMounts:
            - { name: backups, mountPath: /backups }
            - { name: tmp, mountPath: /tmp }
          resources: {{- toYaml .Values.resources.small | nindent 12 }}
      containers:
        - name: mirror-minio
          image: {{ .Values.minio.image }}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          # MC_HOST_facil : mc lit l'alias depuis l'ENVIRONNEMENT. On n'utilise PAS
          # `mc alias set <url-avec-mdp>`, qui exposerait le secret dans l'argv.
          env:
            - name: MINIO_ROOT_USER
              value: {{ .Values.minio.rootUser | quote }}
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretNames.backup }}
                  key: MINIO_ROOT_PASSWORD
            - name: MINIO_ENDPOINT
              value: http://{{ include "facil.fullname" (dict "name" "minio") }}:9000
            - name: RETAIN
              value: {{ .Values.backup.retain | quote }}
          command: ["sh", "-c"]
          args:
            - |
              set -eu
              export MC_HOST_facil="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@${MINIO_ENDPOINT#http://}"
              TS="$(cat /backups/.latest)"
              DEST="/backups/${TS}/minio"
              mkdir -p "$DEST"
              echo "mirror MinIO -> ${DEST}" >&2
              mc mirror --quiet facil "$DEST" || {
                echo "FAIL: le mirror MinIO a echoue -- upgrade avorte AVANT migration." >&2
                exit 1
              }
              # Retention : on garde les N sauvegardes les plus recentes.
              cd /backups
              COUNT="$(ls -1d 2*Z 2>/dev/null | wc -l)"
              if [ "$COUNT" -gt "$RETAIN" ]; then
                ls -1d 2*Z | sort | head -n "$((COUNT - RETAIN))" | while read -r old; do
                  echo "purge de la sauvegarde ${old}" >&2
                  rm -rf "$old"
                done
              fi
              echo "sauvegarde ${TS} terminee." >&2
          volumeMounts:
            - { name: backups, mountPath: /backups }
            - { name: tmp, mountPath: /tmp }
          resources: {{- toYaml .Values.resources.small | nindent 12 }}
      volumes:
        - name: backups
          persistentVolumeClaim:
            claimName: {{ include "facil.fullname" (dict "name" "backups") }}
        - name: tmp
          emptyDir: {}
{{- end }}
```

- [ ] **Step 4: Lancer — passe**

Run: `bash infra/helm/facil/tests/test_render.sh` puis `bash infra/helm/facil/tests/test_render.sh -f infra/helm/facil/values-onprem.yaml`
Expected: `OK render` ×2. Puis `helm lint infra/helm/facil` → 0 failed.

**Vérifier aussi** : `guard_secrets.py` (qui refuse tout flag à credential dans `command`/`args`) doit rester **vert** — c'est la preuve qu'aucun secret ne fuit dans l'argv.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/backup-job.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): sauvegarde pg_dump + MinIO avant migration, fail-closed (hook pre-upgrade)"
```

### Task A3 : garde parsée `guard_backup.py` (l'ordre est l'invariant)

**Files:**
- Create: `infra/helm/facil/tests/guard_backup.py`, `infra/helm/facil/tests/test_guard_backup.py`
- Modify: `infra/helm/facil/tests/test_render.sh`

**Contexte :** un `grep -q "kind: Job"` ne prouve **rien**. Ce qui compte est l'**invariant d'ordre** : la sauvegarde **doit** tourner **avant** les migrations. Si un jour quelqu'un met le poids du backup à `1`, le Job existera toujours, le rendu passera toujours, et **la protection aura disparu** en silence. C'est exactement la classe de défaut que ce projet traque.

- [ ] **Step 1: Écrire la garde**

Créer `infra/helm/facil/tests/guard_backup.py`, sur le modèle **exact** des gardes existantes (`guard_secrets.py`, `guard_resources.py`, `guard_networkpolicy.py`, `guard_ingress.py`) : lire le rendu `helm template` sur **stdin**, parser le YAML, vérifier des invariants **structurels**, sortir 1 avec un message précis en cas de violation. Invariants :

1. Le Job `facil-backup` existe (si `backup.enabled`), avec le hook **`pre-upgrade`**.
2. **Son `hook-weight` est STRICTEMENT INFÉRIEUR** à celui de `facil-db-role` **et** de `facil-db-init` — c'est l'invariant qui protège réellement. Le comparer **numériquement**, pas textuellement (`"-2" < "-1"` en tri lexicographique est un piège).
3. Il est **fail-closed** : `restartPolicy: Never` et `backoffLimit` borné (pas d'`Always`, pas de retry infini).
4. Aucun credential dans `command`/`args` (`guard_secrets.py` le couvre déjà globalement — ne pas dupliquer, mais **vérifier** que le Job y est bien soumis).

- [ ] **Step 2: Preuves par mutation (obligatoires)**

Chacune, exécutée pour de vrai, sortie réelle rapportée :
- passer le `hook-weight` du backup à `1` → la garde doit **rougir** en nommant l'inversion d'ordre ;
- retirer le hook `pre-upgrade` → rougir ;
- passer `backoffLimit` à une valeur non bornée / `restartPolicy: OnFailure` → rougir ;
- rendu réel non muté → **vert**.

- [ ] **Step 3: Brancher dans `test_render.sh`**

```bash
python infra/helm/facil/tests/guard_backup.py < "$OUT_FILE"
```

(⚠️ lire `"$OUT_FILE"`, **jamais** `echo "$OUT" | python …` — course EPIPE, bug réel vécu ici.)

- [ ] **Step 4: Lancer** — `pytest infra/helm/facil/tests -q` vert (la CI lance ce répertoire entier).

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/tests/guard_backup.py infra/helm/facil/tests/test_guard_backup.py infra/helm/facil/tests/test_render.sh
git commit -m "test(helm): garde parsee sur la sauvegarde (l'ordre avant migration est l'invariant)"
```

---

## PHASE B — Rollback & restauration

### Task B1 : action `--rollback` dans le provider

**Files:**
- Modify: `deploy/providers/k3s.py`
- Test: `deploy/providers/test_k3s.py`

**Interfaces:**
- Produces: CLI `--rollback` (+ `--revision N` optionnel, défaut = révision précédente) → `helm rollback facil [N] -n <ns> --wait`. Affiche `helm history` avant, et **imprime la marche à suivre pour la base** après.

**Le point crucial, à écrire noir sur blanc dans la sortie :** `helm rollback` **ne restaure pas la base**. Si la migration était destructive, le code revient en arrière sur un schéma qui, lui, ne revient pas. L'opérateur **doit** être averti, à l'écran, avec le chemin de la sauvegarde.

- [ ] **Step 1: Écrire les tests**

```python
def test_rollback_invokes_helm_rollback_in_the_target_namespace(monkeypatch):
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    assert k3s.main(["--rollback", "--yes", "--namespace", "custom-ns"]) == 0
    rb = next(c for c in calls if "rollback" in c)
    assert rb[rb.index("-n") + 1] == "custom-ns"


def test_rollback_warns_that_the_database_is_NOT_restored(monkeypatch, capsys):
    # Le piege mortel : helm rollback rend les MANIFESTES, jamais la BASE. Si la
    # migration etait destructive, l'operateur doit le savoir, a l'ecran.
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    k3s.main(["--rollback", "--yes"])
    out = capsys.readouterr().out.lower()
    assert "base" in out and ("pas restaur" in out or "non restaur" in out)
    assert "restore_backup" in out   # on pointe vers l'outil, pas juste un avertissement
```

- [ ] **Step 2: Lancer — échouent** (`--rollback` n'existe pas).

- [ ] **Step 3: Implémenter** dans `k3s.py` — ajouter au groupe mutuellement exclusif :

```python
    mode.add_argument("--rollback", action="store_true",
                      help="`helm rollback` vers la revision precedente. NE RESTAURE PAS "
                           "la base : voir deploy/scripts/restore_backup.py.")
    parser.add_argument("--revision", type=int, default=None,
                        help="Revision Helm cible (defaut : la precedente).")
```

…et la branche correspondante, qui **affiche l'historique**, effectue le rollback, puis **avertit sans ambiguïté** :

```python
    if args.rollback:
        subprocess.run([helm, "history", "facil", "-n", args.namespace], check=False)
        rb = [helm, "rollback", "facil"]
        if args.revision is not None:
            rb.append(str(args.revision))
        rb += ["-n", args.namespace, "--wait", "--timeout", "10m"]
        rc = subprocess.run(rb, check=False).returncode
        if rc != 0:
            print("ERREUR: `helm rollback` a echoue.", file=sys.stderr)
            return 2
        print(
            "\n*** ATTENTION : la BASE DE DONNEES n'est PAS restauree. ***\n"
            "`helm rollback` rend les MANIFESTES a leur etat anterieur -- jamais les\n"
            "donnees. Si la migration etait destructive (DROP COLUMN/TABLE), le schema\n"
            "reste casse et le code rollbacke tournera dessus.\n"
            "Pour restaurer la base depuis la sauvegarde pre-upgrade :\n"
            "    python deploy/scripts/restore_backup.py --list\n"
            "    python deploy/scripts/restore_backup.py --restore <horodatage>\n")
        return 0
```

- [ ] **Step 4: Lancer — passent.** `pytest deploy/ -q` vert.

- [ ] **Step 5: Commit**

```bash
git add deploy/providers/k3s.py deploy/providers/test_k3s.py
git commit -m "feat(deploy): action --rollback (avertit que la base n'est PAS restauree)"
```

### Task B2 : `restore_backup.py` — restauration assistée, jamais automatique

**Files:**
- Create: `deploy/scripts/restore_backup.py`, `deploy/scripts/test_restore_backup.py`, `infra/helm/facil/RESTORE.md`

**Interfaces:**
- Produces: `--list` (liste les sauvegardes horodatées du PVC) · `--restore <horodatage>` (restaure Postgres via `pg_restore` et MinIO via `mc mirror`, **après une confirmation explicite**).

**Décision assumée :** **pas de restauration automatique.** Écraser une base en cours d'exploitation est une opération destructive qui exige une décision humaine. Un `--restore` déclenché par un script au milieu d'un rollback serait un pistolet chargé. On outille l'opérateur, on ne décide pas à sa place. La confirmation doit exiger de **retaper l'horodatage** (pas un simple `y/N` — trop facile à valider par réflexe).

- [ ] **Step 1: Écrire les tests** — `--list` parse la sortie de `kubectl exec`/`ls` ; `--restore` **refuse** sans confirmation exacte ; le mot de passe ne transite **jamais** par l'argv (`PGPASSWORD` en env, `MC_HOST_*` en env).

- [ ] **Step 2 → 4 : rouge → implémentation → vert.** Écrire `RESTORE.md` avec la procédure **et ses limites** (les sauvegardes ne sont **pas chiffrées at-rest** — elles vivent sur le disque du nœud ; le chiffrement relève du volume, cf. LUKS + OpenBao).

- [ ] **Step 5: Commit**

```bash
git add deploy/scripts/restore_backup.py deploy/scripts/test_restore_backup.py infra/helm/facil/RESTORE.md
git commit -m "feat(deploy): restauration assistee depuis la sauvegarde pre-upgrade"
```

---

## PHASE C — Health-gate explicite

### Task C1 : vérifier `/health` après l'upgrade, pas seulement la readiness

**Files:**
- Modify: `deploy/providers/k3s.py`
- Test: `deploy/providers/test_k3s.py`

**Honnêteté sur ce que ça apporte :** `helm upgrade --wait` attend déjà que les pods soient `Ready`, et la readinessProbe du backend **est** `/health`. Le gain d'un health-gate explicite est donc **incrémental**, pas fondamental — il faut le dire, pas le survendre. Ce qu'il ajoute réellement : une vérification **après** que Helm ait déclaré la release réussie, qui distingue « les pods répondent » de « **l'application** répond », et qui produit un **message d'échec exploitable** au lieu d'un timeout Helm opaque.

- [ ] **Step 1: Écrire le test** — après un `--apply` réussi, le provider exécute une vérification `/health` sur le backend ; si elle échoue, l'exit code est non-zéro **et** le message nomme le pod fautif.
- [ ] **Step 2 → 4 : rouge → implémentation → vert.** Implémenter via `kubectl -n <ns> exec deploy/facil-backend -- python -c "…urlopen('http://localhost:<port>/health')…"`, avec quelques tentatives espacées.
- [ ] **Step 5: Commit** — `feat(deploy): health-gate explicite apres upgrade (message exploitable)`

---

## PHASE D — Tier *lite* (compose) : équivalent best-effort

### Task D1 : sauvegarde avant `docker compose up`

**Files:**
- Modify: `deploy/providers/docker_local.py` (ou le script d'update du tier lite — **vérifier l'existant avant d'écrire**)

**Contexte :** la spec assume explicitement que le tier *lite* est **de 2ᵉ classe** (best-effort, pas de rolling-update). Mais un client on-prem sans ops **utilisera** ce tier, et perdre ses données serait aussi grave. Un `pg_dump` scripté avant `up -d` est peu coûteux et ferme le même trou.

- [ ] **Step 1: Lire l'existant** — `deploy/providers/docker_local.py` génère le compose ; y a-t-il déjà une action d'update ? **Ne pas inventer une commande qui n'existe pas.** Si le chemin d'update lite n'existe pas encore, **le dire** et proposer le plus petit ajout utile.
- [ ] **Step 2 → 5 : TDD, puis commit.**

---

## PHASE E — Preuve réelle (la seule qui compte)

### Task E1 : smoke k3d — prouver que la sauvegarde protège vraiment

**Contexte :** `helm lint`, `helm template` et des centaines de tests unitaires **étaient tous verts** sur un chart qui ne démarrait pas. Ce projet en a tiré une règle : **seul un apply réel prouve un chart.** Ici, la question n'est pas « le Job est-il rendu ? » mais « **la sauvegarde protège-t-elle réellement des données ?** ».

- [ ] **Step 1:** Créer un cluster k3d, déployer, **insérer des données réelles** (une organisation via l'API, un objet dans MinIO).
- [ ] **Step 2:** Faire un `--apply` (upgrade) → vérifier que le Job `facil-backup` s'exécute **avant** `db-role`/`db-init` (`kubectl get jobs`, ordre des `startTime`), et que le PVC contient bien un dump **non vide** + le mirror MinIO.
- [ ] **Step 3 — LE test qui compte :** **simuler une migration destructive** (par ex. `DROP TABLE` sur une table métier), puis :
  - `--rollback` → constater que le code revient en arrière **mais que la table reste détruite** (c'est le piège qu'on documente) ;
  - `restore_backup.py --restore <ts>` → constater que **les données reviennent**.
  **Si les données ne reviennent pas, tout ce lot n'a servi à rien.** C'est le seul critère d'acceptation qui compte.
- [ ] **Step 4:** Vérifier le **fail-closed** : casser volontairement l'accès Postgres du Job de backup → l'`upgrade` doit **avorter AVANT** la migration (le Job `db-init` ne doit **jamais** démarrer).
- [ ] **Step 5:** `k3d cluster delete` + `docker system prune -f` (rendre la RAM et le disque).
- [ ] **Step 6:** Écrire les **résultats réellement observés** dans `infra/helm/facil/RESTORE.md` — pas les résultats espérés.

### Task E2 : gate finale

- [ ] Revue `security-auditor` sur le diff (le Job de backup manipule le **superuser** et le **root MinIO** — c'est le composant le plus privilégié du chart).
- [ ] Revue `silent-failure-hunter` sur `restore_backup.py` et la branche `--rollback` (un `check=False` non propagé y serait catastrophique).
- [ ] Self-checklist : sauvegarde **prouvée** par restauration réelle · fail-closed **prouvé** · backend toujours sans credential root · zéro régression compose · gardes prouvées par mutation · CI verte.

---

## Self-Review (contre la spec)

**Couverture des livrables P2 de la spec :** migrations gatées ✅ (déjà livré en P1 : hook bloquant) · backup-avant-update → Phase A · health-gate → Phase C (avec une note d'honnêteté sur son gain réel) · rollback → Phase B · compose *lite* → Phase D · **seed profil → RETIRÉ, sur prémisse fausse, justifié en tête de plan** (`profiles.py` fait de la config, pas du seed ; aucun mécanisme de seed de BD n'existe).

**Placeholders :** aucun. Les deux endroits qui demandent de **lire l'existant avant d'écrire** (Task D1 sur le chemin d'update lite ; Task B2 sur la forme exacte de la confirmation) sont des instructions d'adaptation au réel, pas des trous.

**Cohérence des noms :** `values.backup.{enabled,storage,retain}` · `values.secretNames.backup` ↔ `k3s.SECRET_NAMES["backup"]` ↔ clé `"backup"` de `build_secret_literals()` · Job `facil-backup` (poids `-2`) ↔ `facil-db-role` (`-1`) ↔ `facil-db-init` (`0`) ↔ `guard_backup.py` · PVC `facil-backups` ↔ `claimName` du Job ↔ `restore_backup.py`.

**Le risque principal :** que la sauvegarde **paraisse** fonctionner sans protéger. C'est pour ça que Task E1 Step 3 (destruction réelle → restauration réelle) est **le** critère d'acceptation, et que le Job est fail-closed sur un dump vide.
