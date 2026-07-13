# Correction P1-core + Durcissement P1b (chart Helm k3s) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre le chart `infra/helm/facil` réellement déployable sur k3s (4 bloquants apply), fermer 2 failles de conception (blast radius des secrets, canal argv), réparer les 2 gardes de test décoratives, puis durcir (NetworkPolicies, Ingress, readOnlyRootFS, seccomp, resources, digests) — le tout **prouvé par un smoke k3d réel**, pas par `helm template`.

**Architecture:** Les secrets passent d'**un bundle unique** (`facil-secrets`, déversé au backend via `envFrom`) à **des Secrets par composant** (`facil-{postgres,redis,minio,openbao,backend}-secret`), chacun monté uniquement par son consommateur. Le provider `k3s.py` construit les manifests Secret **en Python** (base64) et les pipe sur `kubectl apply -f -` — plus aucune valeur dans l'argv. Le rôle least-privilege `facil_app` est créé par un **Job Helm** (le SQL est extrait de `bootstrap/postgres.py`, dont le transport `docker exec` n'est PAS portable sur k3s), et `BACKEND_DATABASE_URL` est **dérivé** d'un `FACIL_APP_PASSWORD` généré par `ensure_secrets.py`.

**Tech Stack:** Helm 3, k3s/k3d (Traefik + kube-router embarqués → Ingress et NetworkPolicy natifs), Python 3.12 (pydantic v2, PyYAML), pytest, Alembic, GitHub Actions.

## Global Constraints

- **Python** : `C:\facil_framework\.venv\Scripts\python.exe` (3.12). Tests = `pytest`, vraie validation.
- **Jamais de build** (règle #1) : le chart **pull** `ghcr.io/<owner>/facil-{backend,web}`. Aucun `docker build` ici.
- **Zéro régression** : le chemin `docker-local` (compose) doit rester intégralement valide. `deploy.py --provider=docker-local --action=validate` vert à chaque phase.
- **Secrets** : aucune valeur de secret dans un fichier versionné, dans un `values*.yaml`, dans un rendu `helm template`, **ni dans l'argv d'un process**. Un secret ne quitte `.env.secrets` que vers **stdin** de `kubectl`.
- **Moindre privilège** : chaque pod ne reçoit que les secrets qu'il consomme réellement. Le backend n'a **jamais** le superuser Postgres, le root MinIO ni le root token OpenBao.
- **Immutabilité k8s** : `spec.selector` d'un Deployment/StatefulSet est **immutable après création**. Toute modification des `selectorLabels` (Task H4) doit être faite **avant le premier apply** — sinon `helm upgrade` échoue définitivement.
- **Branche** : `docs/infra-multitarget-deploy`. **Push = accord explicite** (isolation repo `facil-framework`).
- **Gate de fin** : le smoke k3d (Task V1) est la **seule** preuve acceptable. `helm lint`/`helm template` ne prouvent rien sur le comportement du kubelet — c'est la leçon des 4 bloquants.

## Ordre d'exécution (corrigé au pre-flight)

Le découpage initial portait deux défauts, corrigés ici :
1. **R2 utilisait `apply_manifest` / `build_configmap_manifest`, définies seulement en S2** — une
   dépendance vers l'avant : l'implémenteur de R2 aurait codé contre des fonctions inexistantes.
   → **S2 est absorbée par R1** (c'est de la plomberie `kubectl`, et `ensure_namespace` en a besoin
   de toute façon).
2. **R2 créait `db-role-job.yaml` qui référence `.Values.secretNames.dbRole`, défini seulement en S1.**
   → **S1 passe AVANT R2** : le chart déclare d'abord ses `secretNames` et son cloisonnement, puis R2
   remplit la case manquante (`BACKEND_DATABASE_URL`) et ajoute le Job du rôle.

**Ordre définitif — 12 tâches :**
`R1` (plomberie kubectl : namespace + manifest builders + stdin + `--atomic` + `-n`) →
**`S1`** (Secrets par composant, suppression `envFrom`) →
**`R2`** (rôle `facil_app` + `BACKEND_DATABASE_URL` + Job db-role) →
`R3` (hook order) → `S3` (garde OpenBao) → `G1` → `G2` → `H1` → `H2` → `H3` → `H4` → `V1` → `V2`.

⚠️ Conséquence pour l'implémenteur de **S1** : `BACKEND_DATABASE_URL` est **produit par R2**, pas par
S1. S1 câble la **clé** (`secretKeyRef` vers `secretNames.backend`) et cloisonne les secrets ; les
assertions sur la **valeur** de l'URL vivent en R2. Entre S1 et R2 le chart reste temporairement
non-déployable — sans conséquence : aucun `apply` n'a lieu avant la Task V1.

## File Structure

**Créés :**
- `deploy/scripts/pg_roles.py` — SQL partagé (CREATE ROLE + grants least-privilege), extrait de `bootstrap/postgres.py` pour être réutilisable hors Docker.
- `deploy/scripts/test_pg_roles.py` — tests du SQL généré.
- `infra/helm/facil/templates/db-role-job.yaml` — Job hook créant `facil_app` (weight avant db-init).
- `infra/helm/facil/templates/networkpolicy.yaml` — default-deny + allow ciblés.
- `infra/helm/facil/templates/ingress.yaml` — Ingress Traefik (gated).
- `infra/helm/facil/tests/guard_secrets.py` — garde-secret **parsée** (remplace le grep contournable).
- `infra/helm/facil/SMOKE.md` — procédure + critères d'acceptation du smoke k3d.

**Modifiés :**
- `deploy/providers/k3s.py` — Secrets par composant, manifests en Python/stdin, namespace-first, `--atomic`, `--set-string`, dérivation `BACKEND_DATABASE_URL`.
- `deploy/providers/test_k3s.py` — réparation du test vacuité + tests des nouveaux comportements.
- `deploy/scripts/ensure_secrets.py` — ajout `FACIL_APP_PASSWORD`, `SECRET_KEY`, `RECEIPT_VERIFICATION_SECRET`, `CRON_SECRET`.
- `infra/helm/facil/values.yaml` — `secretNames.*`, `resources`, `ingress`, `networkPolicy`, digests, suppression de `global.namespace` (valeur morte).
- `infra/helm/facil/templates/{postgres,redis,minio,openbao,backend,frontend,db-init-job}.yaml` — Secret dédié, hardening, resources.
- `infra/helm/facil/templates/_helpers.tpl` — `facil.imagePullSecrets` (fait), `app.kubernetes.io/instance` dans les selectors.
- `infra/helm/facil/tests/test_render.sh` — appel de la garde parsée.
- `.github/workflows/helm.yml` — garde parsée + `gitleaks` sur `infra/**`.

---

## PHASE R — Réparer les bloquants apply

> Sans cette phase, **aucun** `--apply` ne peut aboutir. Ordre imposé : R1 (namespace) → R2 (rôle+URL) → R3 (hook).

### Task R1 : plomberie kubectl — namespace d'abord, manifests via stdin, `--plan` fidèle, rollback auto

> **Absorbe l'ancienne Task S2** (voir « Ordre d'exécution corrigé ») : les constructeurs de
> manifests sont de la plomberie dont `ensure_namespace` a besoin, et sur laquelle R2 s'appuie.

**Files:**
- Modify: `deploy/providers/k3s.py:188-246`
- Test: `deploy/providers/test_k3s.py`

**Interfaces:**
- Produces: `ensure_namespace(kubectl, ns) -> int` · `build_secret_manifest(name, literals) -> str`
  (YAML `kind: Secret`, valeurs base64) · `build_configmap_manifest(name, data) -> str` ·
  `apply_manifest(kubectl, ns, manifest) -> int` (pipe sur **stdin**). Exit 0 = ok, 2 = échec kubectl.

**Contexte SEC-006 (CWE-214) :** `kubectl create secret --from-literal=K=V` place les **valeurs en
clair dans l'argv** — lisibles via `ps -ef` / `/proc/<pid>/cmdline`, capturées par tout auditd/EDR.
Le test sentinelle existant ne couvre que stdout/stderr, jamais l'argv. On construit donc les
manifests **en Python** et on les pipe sur stdin : aucune valeur ne touche une ligne de commande.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `deploy/providers/test_k3s.py` :

```python
def test_apply_creates_namespace_before_secret(monkeypatch, tmp_path):
    # APPLY-004 : sur un cluster neuf le namespace n'existe pas ; appliquer le
    # Secret avant sa creation echoue ("namespaces \"facil\" not found").
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    k3s.main(["--apply", "--yes"])

    joined = [" ".join(c) for c in calls]
    ns_idx = next(i for i, c in enumerate(joined) if "create namespace" in c or "namespace facil" in c)
    sec_idx = next(i for i, c in enumerate(joined) if "apply" in c and "-f" in c)
    assert ns_idx < sec_idx, "le namespace doit etre cree AVANT le Secret"


def test_plan_renders_in_the_target_namespace(monkeypatch):
    # SEC-019 : `helm template` sans -n rend avec .Release.Namespace = "default",
    # donc le plan ne reflete pas l'apply.
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    k3s.main(["--plan", "--namespace", "facil"])
    assert ["-n", "facil"] == [x for x in calls[0] if x in ("-n", "facil")][:2]


def test_apply_uses_atomic_for_auto_rollback(monkeypatch):
    # SEC-022 : sans --atomic une release en echec reste en place, pods casses.
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    k3s.main(["--apply", "--yes"])
    upgrade = next(c for c in calls if "upgrade" in c)
    assert "--atomic" in upgrade


def test_secret_values_never_appear_in_any_process_argv(monkeypatch):
    # SEC-006 (CWE-214) : `kubectl create secret --from-literal=K=V` expose les valeurs
    # dans l'argv (ps -ef, /proc/<pid>/cmdline, auditd). On construit le manifest en
    # Python et on le pipe sur stdin : rien ne transite par une ligne de commande.
    MARKER = "s3nt1nel-p4ssw0rd-marker"
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets",
                        lambda p: {**_FULL_SECRETS, "POSTGRES_PASSWORD": MARKER})
    k3s.main(["--apply", "--yes", "--allow-dev-vault"])

    b64 = base64.b64encode(MARKER.encode()).decode()
    for cmd in calls:
        for arg in cmd:
            assert MARKER not in arg, f"secret en clair dans l'argv: {cmd[0]}"
            assert b64 not in arg, f"secret base64 dans l'argv: {cmd[0]}"


def test_build_secret_manifest_base64_encodes_values():
    m = k3s.build_secret_manifest("facil-postgres-secret", {"POSTGRES_PASSWORD": "pw"})
    assert "kind: Secret" in m
    assert base64.b64encode(b"pw").decode() in m
    assert "POSTGRES_PASSWORD: pw" not in m  # jamais en clair
```

Note : `--allow-dev-vault` n'existe qu'à partir de la Task S3. **Jusque-là, l'omettre** de l'appel
`k3s.main([...])` dans ce test — et l'ajouter quand S3 introduit le flag.

Ajouter en tête du fichier (`import base64`, `import subprocess`, fixture partagée) :

```python
import subprocess

_FULL_SECRETS = {
    "POSTGRES_PASSWORD": "pg-pw", "REDIS_PASSWORD": "redis-pw",
    "MINIO_ROOT_PASSWORD": "minio-pw", "OPENBAO_DEV_ROOT_TOKEN": "bao-tok",
    "JWT_SECRET_KEY": "jwt", "SECRET_KEY": "app", "TOTP_ENCRYPTION_KEY": "totp",
    "RECEIPT_VERIFICATION_SECRET": "receipt", "CRON_SECRET": "cron",
    "FACIL_APP_PASSWORD": "app-role-pw",
}
```

- [ ] **Step 2: Lancer — échouent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -k "namespace or atomic or plan_renders" -v`
Expected: FAIL (namespace jamais créé ; `--atomic` absent ; `-n` absent du template).

- [ ] **Step 3: Implémenter dans `deploy/providers/k3s.py`**

Ajouter la fonction (après `find_kubectl`) :

```python
def ensure_namespace(kubectl: str, ns: str) -> int:
    """Cree le namespace si absent (idempotent, sans erreur s'il existe deja).

    APPLY-004 : sur un cluster neuf, `kubectl -n <ns> apply` du Secret echoue
    tant que le namespace n'existe pas — et Helm ne le cree qu'a l'upgrade
    (--create-namespace), donc APRES. On le cree explicitement en etape 0.
    """
    dry = subprocess.run(
        [kubectl, "create", "namespace", ns, "--dry-run=client", "-o", "yaml"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if dry.returncode != 0:
        print(f"ERREUR: impossible de rendre le namespace '{ns}'.", file=sys.stderr)
        return 2
    applied = subprocess.run([kubectl, "apply", "-f", "-"], input=dry.stdout,
                             text=True, encoding="utf-8", errors="replace")
    return 0 if applied.returncode == 0 else 2
```

Dans `main()`, brancher `--plan` sur le namespace (remplacer le bloc `if args.plan:` existant) :

```python
    if args.plan:
        print(f"=== k3s plan (namespace={args.namespace}) — helm template, lecture seule ===")
        proc = subprocess.run(
            [helm, "template", "facil", str(CHART_DIR),
             "-n", args.namespace,          # SEC-019 : sinon .Release.Namespace = "default"
             "-f", str(VALUES_ONPREM), *_set_args(values)],
            check=False,
        )
        return 0 if proc.returncode == 0 else 2
```

Dans le bloc `--apply`, **avant** la création du Secret (juste après la confirmation `--yes`) :

```python
    rc_ns = ensure_namespace(kubectl, args.namespace)
    if rc_ns != 0:
        return rc_ns
```

Et sur le `helm upgrade`, ajouter `--atomic` :

```python
    rc = subprocess.run(
        [helm, "upgrade", "--install", "facil", str(CHART_DIR),
         "-n", args.namespace, "--create-namespace",
         "-f", str(VALUES_ONPREM),
         *_set_args(values),
         "--atomic",                       # SEC-022 : rollback auto si le deploiement echoue
         "--wait", "--timeout", "10m"],
        check=False,
    ).returncode
```

- [ ] **Step 3bis: Constructeurs de manifests (Python) + stdin — plus jamais d'argv**

Ajouter `import base64` en tête, puis (avant `ensure_namespace`) :

```python
def build_secret_manifest(name: str, literals: dict[str, str]) -> str:
    """Manifest `kind: Secret` (valeurs base64) — construit EN PYTHON.

    SEC-006 : on n'utilise PAS `kubectl create secret --from-literal=K=V`, qui place
    les valeurs en clair dans l'argv du process (visible via `ps -ef` et
    /proc/<pid>/cmdline, capture par auditd/EDR — CWE-214). Le manifest part sur
    stdin de `kubectl apply -f -` : aucune valeur ne touche une ligne de commande.
    """
    lines = ["apiVersion: v1", "kind: Secret", "type: Opaque",
             "metadata:", f"  name: {name}", "data:"]
    for k in sorted(literals):
        b64 = base64.b64encode(literals[k].encode("utf-8")).decode("ascii")
        lines.append(f"  {k}: {b64}")
    return "\n".join(lines) + "\n"


def build_configmap_manifest(name: str, data: dict[str, str]) -> str:
    """ConfigMap (donnees NON secretes — le SQL du role). Meme chemin stdin : DRY."""
    lines = ["apiVersion: v1", "kind: ConfigMap",
             "metadata:", f"  name: {name}", "data:"]
    for k in sorted(data):
        lines.append(f"  {k}: |")
        lines.extend(f"    {line}" for line in data[k].splitlines())
    return "\n".join(lines) + "\n"


def apply_manifest(kubectl: str, ns: str, manifest: str) -> int:
    """`kubectl apply -f -` sur stdin. N'imprime JAMAIS le manifest ni le stderr brut
    de kubectl (SEC-016 : kubectl reemet parfois ses entrees dans ses messages d'erreur)."""
    proc = subprocess.run(
        [kubectl, "-n", ns, "apply", "-f", "-"],
        input=manifest, text=True, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        # Message generique : le stderr peut contenir des fragments du manifest.
        print(f"ERREUR: `kubectl apply` a echoue (code {proc.returncode}). Verifier "
              f"l'acces au cluster et le namespace '{ns}'.", file=sys.stderr)
        return 2
    return 0
```

Remplacer **tout** le bloc « 1) Secret k8s » de `main()` (les lignes `kubectl create secret
--dry-run` + le pipe) par un appel unique — la répartition par composant arrive en R2, ici on
garde le Secret unique existant mais **construit en Python** :

```python
    rc = apply_manifest(kubectl, args.namespace,
                        build_secret_manifest(SECRET_NAME, literals))
    if rc != 0:
        return rc
```

- [ ] **Step 4: Lancer — passent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -v`
Expected: PASS (tous).

- [ ] **Step 5: Commit**

```bash
git add deploy/providers/k3s.py deploy/providers/test_k3s.py
git commit -m "fix(deploy): namespace avant Secret, -n dans --plan, --atomic (APPLY-004/SEC-019/SEC-022)"
```

### Task R2 : rôle `facil_app` + `BACKEND_DATABASE_URL` (APPLY-003, cible least-privilege)

**Files:**
- Create: `deploy/scripts/pg_roles.py`, `deploy/scripts/test_pg_roles.py`
- Create: `infra/helm/facil/templates/db-role-job.yaml`
- Modify: `deploy/scripts/ensure_secrets.py:36-49`, `deploy/providers/k3s.py`

**Interfaces:**
- Produces: `pg_roles.app_role_name(project: str) -> str` ; `pg_roles.create_role_sql(role: str, db: str) -> list[str]` (CREATE ROLE idempotent + grants + default privileges) ; `k3s.backend_database_url(cfg, app_pw: str) -> str`.
- Consumes: `FACIL_APP_PASSWORD` depuis `.env.secrets` (généré par `ensure_secrets`).

**Contexte (à ne pas re-débattre) :** `deploy/providers/bootstrap/postgres.py:71-124` crée déjà ce rôle — mais via `docker exec` (`exec_in`), **non portable sur k3s**. Seul le **SQL** est réutilisable : on l'extrait dans `pg_roles.py`, consommé par les deux chemins.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `deploy/scripts/test_pg_roles.py` :

```python
import pg_roles


def test_app_role_name_is_derived_from_project():
    assert pg_roles.app_role_name("facil") == "facil_app"


def test_create_role_sql_is_least_privilege_and_idempotent():
    sql = pg_roles.create_role_sql("facil_app", "facil")
    joined = " ".join(sql)
    # Le role applicatif ne doit JAMAIS pouvoir creer des roles/bases ni etre superuser.
    assert "NOSUPERUSER" in joined and "NOCREATEDB" in joined and "NOCREATEROLE" in joined
    # Idempotent : un re-run (helm upgrade) ne doit pas echouer sur "role already exists".
    assert any("DO $$" in s or "IF NOT EXISTS" in s for s in sql)
    # Les tables creees PLUS TARD par alembic (superuser) doivent etre auto-grantees.
    assert "ALTER DEFAULT PRIVILEGES" in joined
    # Aucun DROP/GRANT ALL : moindre privilege strict.
    assert "GRANT ALL" not in joined and "DROP" not in joined


def test_create_role_sql_never_embeds_a_password():
    # Le mot de passe est passe par psql -v (variable), jamais concatene dans le SQL
    # (sinon il finirait dans les logs Postgres — CWE-532).
    sql = " ".join(pg_roles.create_role_sql("facil_app", "facil"))
    assert "PASSWORD '" not in sql
    assert ":'app_pw'" in sql  # placeholder psql
```

Ajouter à `deploy/providers/test_k3s.py` :

```python
def test_backend_database_url_uses_the_app_role_not_the_superuser():
    # APPLY-003 / cible (e) : le backend se connecte en facil_app, jamais en superuser.
    url = k3s.backend_database_url(_cfg(), "app-role-pw")
    assert url.startswith("postgresql+asyncpg://facil_app:")
    assert "@facil-postgres:5432/facil" in url
    assert "facil:" not in url.split("@")[0].replace("facil_app:", "")


def test_build_secret_literals_derives_backend_database_url():
    # BACKEND_DATABASE_URL n'est PAS lu de .env.secrets (aucun script ne l'ecrit) :
    # il est DERIVE de FACIL_APP_PASSWORD. Sans cette derivation, le secretKeyRef
    # non-optionnel de backend.yaml -> CreateContainerConfigError.
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    assert lit["backend"]["BACKEND_DATABASE_URL"].startswith("postgresql+asyncpg://facil_app:")


def test_apply_fails_closed_when_app_role_password_missing():
    lit = k3s.build_secret_literals({"POSTGRES_PASSWORD": "x"}, cfg=_cfg())
    assert "BACKEND_DATABASE_URL" not in lit.get("backend", {})
```

- [ ] **Step 2: Lancer — échouent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/scripts/test_pg_roles.py deploy/providers/test_k3s.py -k "role or database_url" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pg_roles'`.

- [ ] **Step 3: Créer `deploy/scripts/pg_roles.py`**

```python
#!/usr/bin/env python3
"""SQL du role applicatif moindre-privilege — partage docker-local <-> k3s.

`deploy/providers/bootstrap/postgres.py` cree deja ce role, mais via `docker exec`
(transport non portable sur k3s). Ce module n'expose que le **SQL**, que les deux
chemins executent avec leur propre transport (docker exec / Job Helm psql).

Le mot de passe n'est JAMAIS concatene dans le SQL : il est passe a psql via
`-v app_pw=...` et reference par `:'app_pw'` (quoting psql), sinon il finirait en
clair dans les logs Postgres (CWE-532).
"""
from __future__ import annotations


def app_role_name(project: str) -> str:
    """Nom du role applicatif — meme convention que bootstrap/postgres.py:93."""
    return f"{project}_app"


def create_role_sql(role: str, db: str) -> list[str]:
    """CREATE ROLE idempotent + grants moindre-privilege.

    Idempotent car rejoue a CHAQUE `helm upgrade` (hook pre-upgrade) : un
    `CREATE ROLE` nu echouerait avec "role already exists" des le 2e deploiement.
    ALTER ROLE reaffirme le mot de passe courant (rotation supportee).
    """
    return [
        f"""DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
    CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END
$$""",
        f"ALTER ROLE {role} WITH LOGIN PASSWORD :'app_pw'",
        f"GRANT CONNECT ON DATABASE {db} TO {role}",
        f"GRANT USAGE ON SCHEMA public TO {role}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}",
        # Les tables creees ENSUITE par alembic (superuser) sont auto-grantees au
        # role applicatif — sinon chaque migration exigerait un re-grant manuel.
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {role}",
    ]
```

- [ ] **Step 4: Générer `FACIL_APP_PASSWORD` + les secrets manquants**

Dans `deploy/scripts/ensure_secrets.py`, étendre `RUNTIME_SECRETS` (ligne 36-49) — ajouter avant la parenthèse fermante :

```python
                   # Mot de passe du role applicatif moindre-privilege facil_app.
                   # BACKEND_DATABASE_URL en est DERIVE par le provider k3s : sans
                   # lui le backend n'a aucune URL de connexion (APPLY-003).
                   "FACIL_APP_PASSWORD",
                   # SEC-011 : k3s.py::REQUIRED_APPLY_SECRETS les exige, mais seul
                   # le wizard (deploy/init.py) les generait -> --apply cassait hors
                   # wizard. Fail-closed correct, mais inutilisable : on les genere.
                   "SECRET_KEY", "RECEIPT_VERIFICATION_SECRET", "CRON_SECRET")
```

(retirer la parenthèse fermante de la ligne `"OPENBAO_DEV_ROOT_TOKEN")` → `"OPENBAO_DEV_ROOT_TOKEN",`)

- [ ] **Step 5: Dériver `BACKEND_DATABASE_URL` dans `k3s.py`**

Ajouter dans `deploy/providers/k3s.py` :

```python
sys.path.insert(0, str(SCRIPTS_DIR))
import pg_roles  # noqa: E402


def backend_database_url(cfg: vc.DeployConfig, app_pw: str) -> str:
    """URL de connexion du backend — role applicatif, JAMAIS le superuser.

    Format aligne sur deploy/scripts/render_backend_env.py:53 (SQLAlchemy async).
    L'hote est le Service k8s du chart (facil-postgres), pas le conteneur compose.
    """
    role = pg_roles.app_role_name(cfg.meta.project_name)
    db = cfg.meta.project_name
    return f"postgresql+asyncpg://{role}:{app_pw}@facil-postgres:5432/{db}"
```

**Étendre** (ne PAS réécrire) la fonction cloisonnée introduite en Task S1 — ajouter juste avant son `return` :

```python
    # L'URL de connexion du backend est DERIVEE de FACIL_APP_PASSWORD : aucun script du
    # repo n'ecrit BACKEND_DATABASE_URL dans .env.secrets (APPLY-003), et le secretKeyRef
    # de backend.yaml n'est pas `optional` -> sans cette derivation, le pod backend reste
    # bloque en CreateContainerConfigError pendant les 10 min du --wait.
    if (app_pw := env_secrets.get("FACIL_APP_PASSWORD")):
        out["backend"]["BACKEND_DATABASE_URL"] = backend_database_url(cfg, app_pw)
    # Le Job db-role a besoin du superuser (pour CREATE ROLE) ET du mdp applicatif.
    out["db-role"] = pick("POSTGRES_PASSWORD", "FACIL_APP_PASSWORD")
```

…et ajouter l'entrée correspondante au dict `SECRET_NAMES` (défini en S1) :

```python
    "db-role": "facil-db-role-secret",
```

Mettre à jour `REQUIRED_APPLY_SECRETS` :

```python
# Secrets sans lesquels la stack ne peut pas demarrer (fail-closed sur --apply).
# FACIL_APP_PASSWORD : sans lui, pas de BACKEND_DATABASE_URL -> le backend reste
# en CreateContainerConfigError pendant les 10 min du --wait (APPLY-003).
REQUIRED_APPLY_SECRETS = ("POSTGRES_PASSWORD", "JWT_SECRET_KEY", "SECRET_KEY",
                          "FACIL_APP_PASSWORD")
```

- [ ] **Step 6: Créer le Job Helm `db-role-job.yaml`**

Créer `infra/helm/facil/templates/db-role-job.yaml` :

```yaml
{{- if .Values.postgres.enabled }}
{{/*
Cree le role applicatif moindre-privilege AVANT les migrations (hook-weight -1
vs 0 pour db-init) : alembic tourne en superuser et cree les tables, que les
ALTER DEFAULT PRIVILEGES de ce Job auto-grantent ensuite au role applicatif.
post-install : a la 1ere install, Postgres n'existe pas encore au moment des
hooks pre-install (APPLY-002) — d'ou l'initContainer d'attente ci-dessous.
*/}}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "facil.fullname" (dict "name" "db-role") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
  annotations:
    "helm.sh/hook": post-install,pre-upgrade
    "helm.sh/hook-weight": "-1"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  backoffLimit: 2
  template:
    metadata:
      labels: {{- include "facil.selectorLabels" (dict "Release" .Release "component" "db-role") | nindent 8 }}
    spec:
      restartPolicy: Never
      {{- include "facil.imagePullSecrets" . | nindent 6 }}
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        seccompProfile: { type: RuntimeDefault }
      initContainers:
        - name: wait-postgres
          image: {{ .Values.postgres.image }}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          command: ["sh", "-c"]
          args:
            - |
              until pg_isready -h {{ include "facil.fullname" (dict "name" "postgres") }} -U {{ .Values.postgres.user }}; do
                echo "postgres pas pret, attente..." >&2
                sleep 2
              done
          resources: {{- toYaml .Values.resources.small | nindent 12 }}
      containers:
        - name: db-role
          image: {{ .Values.postgres.image }}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          # Le mot de passe applicatif est passe a psql par -v (variable psql,
          # citee par :'app_pw'), jamais concatene dans le SQL -> il n'apparait
          # pas dans les logs Postgres (CWE-532).
          command: ["sh", "-c"]
          args:
            - |
              set -e
              psql -h {{ include "facil.fullname" (dict "name" "postgres") }} \
                   -U {{ .Values.postgres.user }} -d {{ .Values.postgres.db }} \
                   -v ON_ERROR_STOP=1 -v app_pw="$FACIL_APP_PASSWORD" \
                   -f /sql/role.sql
          env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretNames.dbRole }}
                  key: POSTGRES_PASSWORD
            - name: FACIL_APP_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secretNames.dbRole }}
                  key: FACIL_APP_PASSWORD
          volumeMounts:
            - name: sql
              mountPath: /sql
              readOnly: true
            - name: tmp
              mountPath: /tmp
          resources: {{- toYaml .Values.resources.small | nindent 12 }}
      volumes:
        - name: sql
          configMap:
            name: {{ include "facil.fullname" (dict "name" "db-role-sql") }}
        - name: tmp
          emptyDir: {}
{{- end }}
```

Le SQL est monté depuis une ConfigMap rendue par le provider (source unique = `pg_roles.create_role_sql`, zéro duplication du SQL dans le chart). Ajouter dans `k3s.py` :

```python
def render_role_sql(cfg: vc.DeployConfig) -> str:
    """SQL du role applicatif, rendu depuis pg_roles (source unique)."""
    role = pg_roles.app_role_name(cfg.meta.project_name)
    return ";\n".join(pg_roles.create_role_sql(role, cfg.meta.project_name)) + ";\n"
```

…et créer la ConfigMap dans `--apply`, juste après `ensure_namespace` :

```python
    rc_cm = apply_manifest(kubectl, args.namespace, build_configmap_manifest(
        f"facil-db-role-sql", {"role.sql": render_role_sql(cfg)}))
    if rc_cm != 0:
        return rc_cm
```

(`apply_manifest` / `build_configmap_manifest` sont définis en Task S2 — le SQL n'est pas un secret, mais il passe par le même chemin stdin, DRY.)

- [ ] **Step 7: Lancer — passent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/ -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add deploy/scripts/pg_roles.py deploy/scripts/test_pg_roles.py deploy/scripts/ensure_secrets.py deploy/providers/k3s.py deploy/providers/test_k3s.py infra/helm/facil/templates/db-role-job.yaml
git commit -m "fix(deploy): role facil_app + BACKEND_DATABASE_URL derivee (APPLY-003, least-privilege reel)"
```

### Task R3 : hook `db-init` en `post-install` + attente Postgres (APPLY-002)

**Files:**
- Modify: `infra/helm/facil/templates/db-init-job.yaml:6-11`
- Test: `infra/helm/facil/tests/test_render.sh`

**Contexte :** Helm exécute les hooks `pre-install` **avant toute ressource de la release**. À la première install, ni le Service ni le StatefulSet Postgres n'existent → `alembic upgrade head` échoue sur DNS, `backoffLimit: 0` → aucun retry → `helm install` avorte. **Vérifié** : `/health` (`packages/backend/app/main.py:229-235`) ne fait qu'un `SELECT 1` sans dépendance au schéma → le backend devient Ready dès que Postgres répond, donc `post-install` ne deadlock **pas** avec `--wait`.

- [ ] **Step 1: Étendre le test**

Ajouter à `infra/helm/facil/tests/test_render.sh`, avant l'assertion de hardening :

```bash
# APPLY-002 : les hooks pre-install s'executent AVANT les ressources de la release
# (donc avant Postgres) -> la migration echouerait a la 1ere install. post-install
# + initContainer d'attente = le seul ordonnancement qui marche install ET upgrade.
echo "$OUT" | grep -q "helm.sh/hook: post-install,pre-upgrade"
! echo "$OUT" | grep -q "helm.sh/hook: pre-install"
echo "$OUT" | grep -q "wait-postgres"
```

- [ ] **Step 2: Lancer — échoue**

Run: `bash infra/helm/facil/tests/test_render.sh`
Expected: FAIL (le rendu contient encore `pre-install`).

- [ ] **Step 3: Corriger `db-init-job.yaml`**

Remplacer le bloc `annotations` :

```yaml
  annotations:
    # post-install (PAS pre-install) : a la 1ere install, les hooks pre-install
    # tournent avant que Postgres n'existe -> alembic echoue sur DNS et, avec
    # backoffLimit 0, helm install avorte (APPLY-002). En pre-upgrade Postgres
    # tourne deja, donc l'ordre migration-avant-cutover est preserve.
    "helm.sh/hook": post-install,pre-upgrade
    "helm.sh/hook-weight": "0"   # apres db-role (-1) qui cree facil_app
    "helm.sh/hook-delete-policy": before-hook-creation
```

Et ajouter l'initContainer d'attente dans `spec.template.spec` (avant `containers:`) :

```yaml
      initContainers:
        - name: wait-postgres
          image: {{ .Values.postgres.image }}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          command: ["sh", "-c"]
          args:
            - |
              until pg_isready -h {{ include "facil.fullname" (dict "name" "postgres") }} -U {{ .Values.postgres.user }}; do
                echo "postgres pas pret, attente..." >&2
                sleep 2
              done
          resources: {{- toYaml .Values.resources.small | nindent 12 }}
```

Passer `backoffLimit: 0` → `backoffLimit: 2` (l'initContainer gère l'attente, mais un retry couvre un redémarrage transitoire de Postgres ; la migration reste fail-closed après 2 échecs).

- [ ] **Step 4: Lancer — passe**

Run: `bash infra/helm/facil/tests/test_render.sh`
Expected: `OK render (default)`.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/db-init-job.yaml infra/helm/facil/tests/test_render.sh
git commit -m "fix(helm): db-init en post-install + attente Postgres (APPLY-002, 1ere install)"
```

---

## PHASE S — Fermer les failles de conception

### Task S1 : Secrets par composant, suppression de `envFrom` (SEC-001, SEC-013)

**Files:**
- Modify: `infra/helm/facil/values.yaml`, `templates/{postgres,redis,minio,openbao,backend}.yaml`, `templates/db-init-job.yaml`
- Modify: `deploy/providers/k3s.py` (déjà refondu en R2 Step 5)
- Test: `infra/helm/facil/tests/test_render.sh`, `deploy/providers/test_k3s.py`

**Interfaces:**
- Produces: `values.secretNames.{postgres,redis,minio,openbao,backend,dbRole}` (noms de Secret k8s, jamais de valeur).

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à `deploy/providers/test_k3s.py` :

```python
def test_backend_never_receives_infrastructure_root_credentials():
    # SEC-001 (blast radius) : une RCE/SSRF dans le backend — seule surface HTTP
    # exposee — ne doit PAS livrer le superuser Postgres, le root MinIO ni le root
    # token OpenBao. Le backend n'en a aucun usage (config.py: extra="ignore").
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    backend = lit["backend"]
    assert "POSTGRES_PASSWORD" not in backend
    assert "MINIO_ROOT_PASSWORD" not in backend
    assert "OPENBAO_DEV_ROOT_TOKEN" not in backend
    # ...mais il garde ce qu'il consomme reellement. (BACKEND_DATABASE_URL est ajoute
    # par la Task R2, qui le DERIVE de FACIL_APP_PASSWORD — pas assere ici.)
    assert {"JWT_SECRET_KEY", "SECRET_KEY", "REDIS_PASSWORD"} <= set(backend)


def test_each_component_secret_holds_only_its_own_credential():
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    assert set(lit["postgres"]) == {"POSTGRES_PASSWORD"}
    assert set(lit["minio"]) == {"MINIO_ROOT_PASSWORD"}
    assert set(lit["openbao"]) == {"OPENBAO_DEV_ROOT_TOKEN"}
```

Ajouter à `infra/helm/facil/tests/test_render.sh` :

```bash
# SEC-001 : le backend ne doit monter AUCUN bundle global (envFrom sur un Secret
# partage) — chaque pod ne voit que le Secret de son composant.
! echo "$OUT" | grep -q "envFrom"
```

- [ ] **Step 2: Lancer — échouent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -k "blast or component" -v` puis `bash infra/helm/facil/tests/test_render.sh`
Expected: FAIL (les deux : `envFrom` présent, secrets non cloisonnés).

- [ ] **Step 2bis: Cloisonner `build_secret_literals` par composant (provider)**

Dans `deploy/providers/k3s.py`, remplacer `build_secret_literals` (qui retournait un dict plat) :

```python
def build_secret_literals(env_secrets: dict[str, str], *, cfg: vc.DeployConfig
                          ) -> dict[str, dict[str, str]]:
    """Repartit les secrets PAR COMPOSANT (SEC-001) — chaque pod ne recoit que ce qu'il
    consomme. Le backend n'a JAMAIS le superuser Postgres, le root MinIO ni le root token
    OpenBao : une RCE dans le backend (seule surface HTTP exposee) ne doit pas livrer le
    data-plane entier. Sa config (packages/backend/app/config.py, extra="ignore") n'en lit
    d'ailleurs aucun — ils n'etaient la que par accident de conception (`envFrom`).

    Retourne {composant: {CLE: valeur}} ; un composant sans secret disponible est omis.
    La Task R2 etendra le bloc "backend" avec BACKEND_DATABASE_URL (derivee) et ajoutera
    le composant "db-role".
    """
    def pick(*keys: str) -> dict[str, str]:
        return {k: env_secrets[k] for k in keys if k in env_secrets}

    out: dict[str, dict[str, str]] = {
        "postgres": pick("POSTGRES_PASSWORD"),
        "redis": pick("REDIS_PASSWORD"),
        "minio": pick("MINIO_ROOT_PASSWORD"),
        "openbao": pick("OPENBAO_DEV_ROOT_TOKEN"),
        # REDIS_PASSWORD : le backend est CLIENT de Redis, il en a besoin. Pas de
        # POSTGRES_PASSWORD (superuser) : il se connectera via BACKEND_DATABASE_URL (R2).
        "backend": pick("JWT_SECRET_KEY", "SECRET_KEY", "TOTP_ENCRYPTION_KEY",
                        "RECEIPT_VERIFICATION_SECRET", "CRON_SECRET", "REDIS_PASSWORD"),
    }
    return {k: v for k, v in out.items() if v}


# Nom du Secret k8s par composant — doit matcher values.yaml::secretNames.*
SECRET_NAMES = {
    "postgres": "facil-postgres-secret", "redis": "facil-redis-secret",
    "minio": "facil-minio-secret", "openbao": "facil-openbao-secret",
    "backend": "facil-backend-secret",
}
```

(supprimer la constante `SECRET_NAME` et la liste plate `SECRET_KEYS`, devenues mortes)

Dans `main()`, remplacer l'appel unique introduit en R1 par une boucle :

```python
    for component, lits in literals.items():
        rc = apply_manifest(kubectl, args.namespace,
                            build_secret_manifest(SECRET_NAMES[component], lits))
        if rc != 0:
            return rc
```

…et adapter le fail-closed (les literals sont désormais imbriqués) :

```python
    flat = {k for comp in literals.values() for k in comp}
    missing = [k for k in REQUIRED_APPLY_SECRETS if k not in flat]
    if missing:
        print(f"ERREUR: secrets requis absents de .env.secrets: {missing}\n"
              f"Lancer: python deploy/scripts/ensure_secrets.py", file=sys.stderr)
        return 1
```

- [ ] **Step 3: Remplacer `secretName` par `secretNames` dans `values.yaml`**

```yaml
# Noms des k8s Secret (crees par deploy/providers/k3s.py, HORS Helm). Un Secret
# PAR COMPOSANT : chaque pod ne monte que ses propres credentials (SEC-001).
# Ce sont des NOMS, jamais des valeurs.
secretNames:
  postgres: facil-postgres-secret
  redis: facil-redis-secret
  minio: facil-minio-secret
  openbao: facil-openbao-secret
  backend: facil-backend-secret
  dbRole: facil-db-role-secret
```

(supprimer l'ancienne clé `secretName: facil-secrets`)

- [ ] **Step 4: Recâbler chaque template sur son Secret**

Dans chaque template, remplacer `{{ .Values.secretName }}` par le Secret du composant :
- `postgres.yaml` → `{{ .Values.secretNames.postgres }}`
- `redis.yaml` → `{{ .Values.secretNames.redis }}`
- `minio.yaml` → `{{ .Values.secretNames.minio }}`
- `openbao.yaml` → `{{ .Values.secretNames.openbao }}`
- `db-init-job.yaml` → `{{ .Values.secretNames.dbRole }}` (il migre en superuser)

Dans `backend.yaml`, **supprimer entièrement** le bloc `envFrom` (lignes 54-56) et le `POSTGRES_PASSWORD` (lignes 42-44), puis déclarer explicitement :

```yaml
          env:
            - name: PORT
              value: {{ .Values.backend.port | quote }}
            - name: ENVIRONMENT
              value: production
            - name: MODULES_ENABLED
              value: {{ .Values.backend.modulesEnabled | quote }}
            # Role applicatif moindre-privilege (JAMAIS le superuser facil).
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretNames.backend }}, key: BACKEND_DATABASE_URL }
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretNames.backend }}, key: REDIS_PASSWORD }
            - name: REDIS_URL
              value: redis://:$(REDIS_PASSWORD)@{{ include "facil.fullname" (dict "name" "redis") }}:6379/0
            - name: JWT_SECRET_KEY
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretNames.backend }}, key: JWT_SECRET_KEY }
            - name: SECRET_KEY
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretNames.backend }}, key: SECRET_KEY }
            - name: TOTP_ENCRYPTION_KEY
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretNames.backend }}, key: TOTP_ENCRYPTION_KEY, optional: true }
            - name: RECEIPT_VERIFICATION_SECRET
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretNames.backend }}, key: RECEIPT_VERIFICATION_SECRET, optional: true }
            - name: CRON_SECRET
              valueFrom:
                secretKeyRef: { name: {{ .Values.secretNames.backend }}, key: CRON_SECRET, optional: true }
```

- [ ] **Step 5: Lancer — passent**

Run: `bash infra/helm/facil/tests/test_render.sh && & C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add infra/helm/facil/values.yaml infra/helm/facil/templates/ infra/helm/facil/tests/test_render.sh deploy/providers/
git commit -m "fix(helm): Secret par composant, suppression envFrom (SEC-001, blast radius)"
```

### Task S2 — ⛔ ABSORBÉE PAR R1, NE PAS EXÉCUTER

> Voir « Ordre d'exécution (corrigé au pre-flight) » : les constructeurs de manifests
> (`build_secret_manifest` / `build_configmap_manifest` / `apply_manifest`) sont de la plomberie
> dont `ensure_namespace` (R1) a besoin, et sur laquelle S1 et R2 s'appuient. Les laisser en S2
> aurait créé une dépendance vers l'avant. Le contenu ci-dessous est **conservé pour référence
> uniquement** — il est déjà implémenté par R1 Step 3bis.

<details><summary>Contenu historique (implémenté en R1)</summary>

#### (ancien) Task S2 : Secrets construits en Python → stdin (SEC-006, SEC-016)

**Files:**
- Modify: `deploy/providers/k3s.py`
- Test: `deploy/providers/test_k3s.py`

**Interfaces:**
- Produces: `build_secret_manifest(name: str, literals: dict[str,str]) -> str` (YAML `kind: Secret`, valeurs base64) ; `build_configmap_manifest(name: str, data: dict[str,str]) -> str` ; `apply_manifest(kubectl: str, ns: str, manifest: str) -> int`.

**Contexte :** `kubectl create secret --from-literal=K=V` place les **valeurs en clair dans l'argv** — lisibles par `ps -ef` / `/proc/<pid>/cmdline` pendant l'exécution, et capturées par tout auditd/EDR (CWE-214). Le test sentinelle actuel ne couvre que stdout/stderr.

- [ ] **Step 1: Écrire le test qui échoue**

```python
def test_secret_values_never_appear_in_any_process_argv(monkeypatch):
    # SEC-006 (CWE-214) : `kubectl create secret --from-literal=K=V` expose les
    # valeurs dans l'argv (ps -ef, /proc/<pid>/cmdline, auditd). On construit le
    # manifest en Python et on le pipe sur stdin : rien ne transite par l'argv.
    MARKER = "s3nt1nel-p4ssw0rd-marker"
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets",
                        lambda p: {**_FULL_SECRETS, "POSTGRES_PASSWORD": MARKER})
    k3s.main(["--apply", "--yes"])

    for cmd in calls:
        for arg in cmd:
            assert MARKER not in arg, f"secret dans l'argv: {cmd[0]}"
            # et jamais en base64 non plus
            assert base64.b64encode(MARKER.encode()).decode() not in arg


def test_build_secret_manifest_base64_encodes_values():
    m = k3s.build_secret_manifest("facil-postgres-secret", {"POSTGRES_PASSWORD": "pw"})
    assert "kind: Secret" in m
    assert base64.b64encode(b"pw").decode() in m
    assert "POSTGRES_PASSWORD: pw" not in m  # jamais en clair
```

- [ ] **Step 2: Lancer — échoue**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -k argv -v`
Expected: FAIL (le marker apparaît dans l'argv du `--from-literal`).

- [ ] **Step 3: Implémenter**

Dans `deploy/providers/k3s.py`, ajouter `import base64` et remplacer le bloc de création du Secret :

```python
def build_secret_manifest(name: str, literals: dict[str, str]) -> str:
    """Manifest `kind: Secret` (valeurs base64) — construit EN PYTHON.

    SEC-006 : on n'utilise PAS `kubectl create secret --from-literal=K=V`, qui
    place les valeurs en clair dans l'argv du process (visible via `ps -ef` et
    /proc/<pid>/cmdline, capture par auditd/EDR — CWE-214). Le manifest part sur
    stdin de `kubectl apply -f -` : aucune valeur ne touche une ligne de commande.
    """
    lines = ["apiVersion: v1", "kind: Secret", "type: Opaque",
             "metadata:", f"  name: {name}", "data:"]
    for k in sorted(literals):
        b64 = base64.b64encode(literals[k].encode("utf-8")).decode("ascii")
        lines.append(f"  {k}: {b64}")
    return "\n".join(lines) + "\n"


def build_configmap_manifest(name: str, data: dict[str, str]) -> str:
    """ConfigMap (donnees NON secretes : le SQL du role). Meme chemin stdin — DRY."""
    lines = ["apiVersion: v1", "kind: ConfigMap",
             "metadata:", f"  name: {name}", "data:"]
    for k in sorted(data):
        lines.append(f"  {k}: |")
        lines.extend(f"    {line}" for line in data[k].splitlines())
    return "\n".join(lines) + "\n"


def apply_manifest(kubectl: str, ns: str, manifest: str) -> int:
    """`kubectl apply -f -` sur stdin. N'imprime JAMAIS le manifest ni le stderr
    brut de kubectl (SEC-016 : kubectl reemet parfois ses entrees en erreur)."""
    proc = subprocess.run(
        [kubectl, "-n", ns, "apply", "-f", "-"],
        input=manifest, text=True, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        # Message generique : le stderr peut contenir des fragments du manifest.
        print(f"ERREUR: `kubectl apply` a echoue (code {proc.returncode}). "
              f"Verifier l'acces au cluster et le namespace '{ns}'.", file=sys.stderr)
        return 2
    return 0
```

Dans `main()`, remplacer tout le bloc « 1) Secret k8s » par :

```python
    # 1) Un Secret PAR COMPOSANT (SEC-001), chacun pipe sur stdin (SEC-006).
    secret_names = {
        "postgres": "facil-postgres-secret", "redis": "facil-redis-secret",
        "minio": "facil-minio-secret", "openbao": "facil-openbao-secret",
        "backend": "facil-backend-secret", "db-role": "facil-db-role-secret",
    }
    for component, lits in literals.items():
        rc = apply_manifest(kubectl, args.namespace,
                            build_secret_manifest(secret_names[component], lits))
        if rc != 0:
            return rc
```

Adapter le fail-closed (les literals sont maintenant imbriqués) :

```python
    flat = {k for comp in literals.values() for k in comp}
    missing = [k for k in REQUIRED_APPLY_SECRETS if k not in flat and k != "FACIL_APP_PASSWORD"]
    if "FACIL_APP_PASSWORD" not in env:
        missing.append("FACIL_APP_PASSWORD")
    if missing:
        print(f"ERREUR: secrets requis absents de .env.secrets: {missing}\n"
              f"Lancer: python deploy/scripts/ensure_secrets.py", file=sys.stderr)
        return 1
```

- [ ] **Step 4: Lancer — passent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add deploy/providers/k3s.py deploy/providers/test_k3s.py
git commit -m "fix(deploy): manifests Secret construits en Python + stdin (SEC-006, plus d'argv)"
```

</details>

### Task S3 : garde fail-closed sur OpenBao dev-mode (SEC-002)

**Files:**
- Modify: `deploy/providers/k3s.py`, `infra/helm/facil/templates/openbao.yaml`
- Test: `deploy/providers/test_k3s.py`

**Contexte :** `values-onprem.yaml` est l'overlay **de production on-prem** et il force `openbao.devMode: true` → stockage in-memory (tous les secrets perdus au moindre restart de pod), auto-unseal, root token en env, **HTTP en clair**. Le mode scellé (raft + unseal SOPS/age + TLS) appartient au plan P7/P8 existant — **hors périmètre ici**. Ce qu'on livre : une garde qui **refuse** l'apply en dev-mode sauf opt-in explicite, pour qu'on ne déploie pas un coffre jetable en prod par accident.

- [ ] **Step 1: Écrire le test qui échoue**

```python
def test_apply_refuses_openbao_dev_mode_without_explicit_optin(monkeypatch, capsys):
    # SEC-002 : bao -dev = stockage in-memory (secrets perdus au restart), auto-unseal,
    # root token en env, HTTP en clair. Acceptable pour un smoke, JAMAIS en prod.
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    rc = k3s.main(["--apply", "--yes"])   # config.yaml a openbao.dev_mode = true
    assert rc == 1
    assert "dev-mode" in capsys.readouterr().err.lower()


def test_apply_allows_openbao_dev_mode_with_explicit_flag(monkeypatch):
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    assert k3s.main(["--apply", "--yes", "--allow-dev-vault"]) == 0
```

- [ ] **Step 2: Lancer — échouent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -k dev_vault -v`
Expected: FAIL (l'apply passe sans broncher aujourd'hui).

- [ ] **Step 3: Implémenter**

Ajouter l'argument :

```python
    parser.add_argument("--allow-dev-vault", action="store_true",
                        help="Autorise OpenBao en dev-mode (stockage in-memory, HTTP "
                             "en clair). SMOKE/DEV UNIQUEMENT — jamais en production.")
```

Et la garde, dans `--apply`, avant tout appel au cluster :

```python
    if cfg.secrets.openbao.dev_mode and not args.allow_dev_vault:
        print(
            "ERREUR: OpenBao est en dev-mode (stockage in-memory : TOUS les secrets\n"
            "sont perdus au moindre redemarrage du pod ; ecoute HTTP en clair ;\n"
            "root token en variable d'environnement). Interdit pour un deploiement\n"
            "reel. Options :\n"
            "  - smoke/dev  : relancer avec --allow-dev-vault (assume le risque)\n"
            "  - production : passer secrets.openbao.dev_mode=false dans config.yaml\n"
            "                 (mode scelle : voir .claude/plans/PHASE_P7_P8_SECRETS_PKI.md)",
            file=sys.stderr)
        return 1
```

- [ ] **Step 4: Faire échouer explicitement la branche `devMode: false` du chart (SEC-023)**

Dans `openbao.yaml`, remplacer la branche `{{- else }}` (qui rend un pod jamais Ready : pas de `BAO_ADDR`, probe `bao status` sur HTTPS par défaut) :

```yaml
          {{- else }}
          {{- fail "openbao.devMode=false : le mode scelle (raft + unseal SOPS/age + TLS) n'est pas encore implemente dans ce chart. Voir .claude/plans/PHASE_P7_P8_SECRETS_PKI.md. Ne PAS deployer OpenBao en prod via ce chart." }}
          {{- end }}
```

- [ ] **Step 5: Lancer — passent**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -v && bash infra/helm/facil/tests/test_render.sh`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add deploy/providers/k3s.py deploy/providers/test_k3s.py infra/helm/facil/templates/openbao.yaml
git commit -m "fix(deploy): garde fail-closed OpenBao dev-mode + fail explicite devMode=false (SEC-002/023)"
```

---

## PHASE G — Réparer les gardes (anti-récidive)

> Ces gardes existaient et étaient **vertes**. Elles ne pouvaient pas échouer. C'est pire que rien : elles produisaient de la confiance.

### Task G1 : réparer le test vacuité (SEC-010)

**Files:**
- Modify: `deploy/providers/test_k3s.py:35-41`

**Contexte :** `assert "password" not in flat or "secretname" in flat` — `values["secretName"]` existe **toujours**, donc `"secretname" in flat` est **toujours vrai**, donc la disjonction est **toujours vraie**. Ce test ne peut littéralement pas échouer, même si `render_values()` retournait `{"postgres": {"password": "hunter2"}}`.

- [ ] **Step 1: Écrire le test de mutation (il doit attraper un faux `render_values`)**

Remplacer `test_render_values_never_contains_secret_values` par :

```python
def _flatten(d, prefix=""):
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            yield from _flatten(v, key)
        else:
            yield key, v


def test_render_values_never_contains_secret_values():
    # SEC-010 : l'ancienne assertion (`"password" not in flat or "secretname" in flat`)
    # etait une VACUITE LOGIQUE — `secretName` est toujours present, donc la
    # disjonction etait toujours vraie et le test ne pouvait jamais echouer.
    # Ici on assere la FORME EXACTE : aucune cle secrete, aucune valeur suspecte.
    values = k3s.render_values(_cfg())
    flat = dict(_flatten(values))
    for key, val in flat.items():
        assert not re.search(r"(password|secret|token|credential)", key, re.I) or \
            key.startswith("secretNames."), f"cle secrete dans les values: {key}"
        # Les values ne portent que des noms/images/ports/booleens — jamais un blob
        # aleatoire (marqueur d'un secret ayant fuite dans le rendu).
        assert not re.fullmatch(r"[A-Za-z0-9+/=_-]{24,}", str(val)), \
            f"valeur suspecte (ressemble a un secret) sous {key}: {val!r}"


def test_render_values_mutation_guard_catches_a_leaked_secret(monkeypatch):
    # Preuve que la garde ci-dessus PEUT echouer (anti-vacuite) : on injecte un
    # faux secret dans les values et on verifie que l'assertion le rejette.
    values = k3s.render_values(_cfg())
    values["postgres"]["password"] = "hunter2hunter2hunter2hunter2"
    flat = dict(_flatten(values))
    leaked = [k for k in flat if re.search(r"(password|secret|token)", k, re.I)
              and not k.startswith("secretNames.")]
    assert leaked == ["postgres.password"]
```

(ajouter `import re` en tête du fichier)

- [ ] **Step 2: Lancer — le nouveau test doit passer, et le mutation-guard prouver qu'il mord**

Run: `& C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/providers/test_k3s.py -k "never_contains or mutation" -v`
Expected: PASS (2 tests).

- [ ] **Step 3: Commit**

```bash
git add deploy/providers/test_k3s.py
git commit -m "test(deploy): reparer la garde-secret vacuite logique + mutation guard (SEC-010)"
```

### Task G2 : garde-secret **parsée** sur le rendu Helm (SEC-009)

**Files:**
- Create: `infra/helm/facil/tests/guard_secrets.py`
- Modify: `infra/helm/facil/tests/test_render.sh`, `.github/workflows/helm.yml`

**Contexte :** la garde bash actuelle a des faux négatifs exploitables : elle ne couvre que 4 clés (ni `JWT_SECRET_KEY`, ni `SECRET_KEY`…), rate les **connection strings** (`DATABASE_URL`/`REDIS_URL` sont rendus en `value:` — une régression y inlinant le mot de passe passerait en **vert**), ne voit qu'**une** ligne après `- name:` (un commentaire YAML intercalé la contourne), et ignore le style flow (`{name: X, value: y}`) que le chart utilise pourtant déjà.

- [ ] **Step 1: Écrire la garde parsée**

Créer `infra/helm/facil/tests/guard_secrets.py` :

```python
#!/usr/bin/env python3
"""Garde-secret PARSEE sur le rendu `helm template` (remplace un grep contournable).

Invariants verifies sur TOUS les conteneurs (init inclus) de TOUS les manifests :
  1. toute env var dont le nom evoque un credential DOIT venir de `valueFrom`
     (secretKeyRef), jamais d'un `value:` litteral ;
  2. aucune URL ne porte de credential inline (`scheme://user:pass@host`), sauf
     interpolation k8s `$(VAR)` — qui, elle, resout depuis un secretKeyRef ;
  3. le chart ne definit AUCUN `kind: Secret` (les Secrets sont crees hors Helm
     par deploy/providers/k3s.py — sinon les valeurs finiraient versionnees).

Usage : helm template ... | python guard_secrets.py
Exit 0 = propre, 1 = fuite.
"""
from __future__ import annotations

import re
import sys

import yaml

# Un nom d'env var qui evoque un credential. Suffisamment large pour couvrir les
# ajouts futurs (le point aveugle de l'ancienne garde : une liste de 4 cles figee).
CREDENTIAL_RE = re.compile(
    r"(PASSWORD|PASSWD|SECRET|TOKEN|_KEY$|APIKEY|API_KEY|CREDENTIAL|_URL$|_DSN$)",
    re.I,
)
# Env vars a `value:` litteral autorisees malgre leur nom : ce sont des NOMS/URLs
# sans credential. Toute addition ici doit etre justifiee en revue.
ALLOWED_LITERAL = {
    "INTERNAL_API_URL",   # http://facil-backend:8080 — pas de credential
    "BAO_ADDR",           # http://127.0.0.1:8200
    "OPENBAO_ADDR",
}
# credential inline dans une URL : scheme://user:pass@host (hors interpolation $(VAR))
INLINE_CRED_RE = re.compile(r"://[^/\s:]+:(?!\$\()[^/\s@]+@")


def iter_containers(doc: dict):
    spec = (doc.get("spec") or {})
    tmpl = (spec.get("template") or {}).get("spec") or spec
    for key in ("containers", "initContainers"):
        for c in (tmpl.get(key) or []):
            yield c


def check(stream: str) -> list[str]:
    problems: list[str] = []
    for doc in yaml.safe_load_all(stream):
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind", "")
        name = (doc.get("metadata") or {}).get("name", "?")

        if kind == "Secret":
            problems.append(
                f"{name}: le chart definit un `kind: Secret` — interdit. Les Secrets "
                f"sont crees hors Helm par deploy/providers/k3s.py.")

        for c in iter_containers(doc):
            for env in (c.get("env") or []):
                ename, val = env.get("name", ""), env.get("value")
                if val is None:
                    continue  # valueFrom -> conforme
                val = str(val)
                if CREDENTIAL_RE.search(ename) and ename not in ALLOWED_LITERAL:
                    if not INLINE_CRED_RE.search(val) and "$(" not in val:
                        problems.append(
                            f"{name}/{c.get('name')}: env `{ename}` a un `value:` "
                            f"litteral alors que son nom evoque un credential.")
                if INLINE_CRED_RE.search(val):
                    problems.append(
                        f"{name}/{c.get('name')}: credential inline dans l'URL de "
                        f"`{ename}` (attendu : $(VAR) resolue depuis un secretKeyRef).")
    return problems


if __name__ == "__main__":
    found = check(sys.stdin.read())
    if found:
        print("FAIL garde-secret (parsee) :", file=sys.stderr)
        for p in found:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)
    print("OK garde-secret (parsee)")
```

- [ ] **Step 2: Prouver que la garde mord (mutation)**

Run:
```bash
helm template rel infra/helm/facil \
  --set backend.modulesEnabled=organization \
  | sed 's|redis://:\$(REDIS_PASSWORD)@|redis://:hunter2@|' \
  | python infra/helm/facil/tests/guard_secrets.py
```
Expected: **FAIL** — `credential inline dans l'URL de REDIS_URL`. (Si ça passe, la garde est inutile : la corriger.)

Puis sur le rendu réel :
```bash
helm template rel infra/helm/facil | python infra/helm/facil/tests/guard_secrets.py
```
Expected: `OK garde-secret (parsee)`.

- [ ] **Step 3: Brancher dans `test_render.sh`** — remplacer le bloc grep (lignes 25-41) par :

```bash
# Garde-secret PARSEE (SEC-009) : l'ancienne version en grep ratait les connection
# strings (DATABASE_URL/REDIS_URL rendus en `value:`), ne couvrait que 4 cles et
# se contournait avec un commentaire YAML intercale. Voir tests/guard_secrets.py.
echo "$OUT" | python infra/helm/facil/tests/guard_secrets.py
```

- [ ] **Step 4: Brancher dans la CI** — dans `.github/workflows/helm.yml`, ajouter avant les étapes de rendu :

```yaml
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install pyyaml
```

- [ ] **Step 5: Lancer la suite complète**

Run: `bash infra/helm/facil/tests/test_render.sh && bash infra/helm/facil/tests/test_render.sh -f infra/helm/facil/values-onprem.yaml`
Expected: `OK render` ×2.

- [ ] **Step 6: Commit**

```bash
git add infra/helm/facil/tests/guard_secrets.py infra/helm/facil/tests/test_render.sh .github/workflows/helm.yml
git commit -m "test(helm): garde-secret parsee (yaml) remplace le grep contournable (SEC-009)"
```

---

## PHASE H — Durcissement P1b

### Task H1 : `resources`, seccomp, `readOnlyRootFilesystem`, `automountServiceAccountToken` (SEC-015)

**Files:**
- Modify: `infra/helm/facil/values.yaml`, tous les `templates/*.yaml`
- Test: `infra/helm/facil/tests/test_render.sh`

**Contexte :** sur un **mono-nœud**, un pod sans `limits` peut OOM-killer le nœud entier — DoS trivial. `readOnlyRootFilesystem` exige un `emptyDir` pour chaque chemin réellement écrit : `/tmp` partout, **plus** `/app/.next/cache` pour Next (ISR) et `/var/run/postgresql` (socket) pour Postgres. Ne pas deviner : le smoke (V1) tranche.

- [ ] **Step 1: Étendre le test**

```bash
# SEC-015 : sur mono-noeud, un pod sans limits peut OOM-killer le noeud entier.
WORKLOADS=$(echo "$OUT" | grep -cE '^kind: (Deployment|StatefulSet|Job)')
LIMITS=$(echo "$OUT" | grep -c 'limits:')
[ "$LIMITS" -ge "$WORKLOADS" ] || { echo "FAIL: workload(s) sans resources.limits" >&2; exit 1; }
echo "$OUT" | grep -q "seccompProfile"
echo "$OUT" | grep -q "automountServiceAccountToken: false"
echo "$OUT" | grep -q "readOnlyRootFilesystem: true"
```

- [ ] **Step 2: Lancer — échoue** (`bash infra/helm/facil/tests/test_render.sh` → FAIL).

- [ ] **Step 3: Ajouter les profils de resources à `values.yaml`**

```yaml
# Profils de ressources (mono-noeud : sans limits, un pod peut OOM-killer le noeud).
# Surchargeables par l'overlay ; dimensionnes pour un k3s 4 Go de smoke.
resources:
  small:      # jobs, sidecars d'attente
    requests: { cpu: 10m, memory: 32Mi }
    limits:   { cpu: 200m, memory: 128Mi }
  data:       # postgres, minio
    requests: { cpu: 100m, memory: 256Mi }
    limits:   { cpu: 1000m, memory: 1Gi }
  cache:      # redis, openbao
    requests: { cpu: 25m, memory: 64Mi }
    limits:   { cpu: 300m, memory: 256Mi }
  app:        # backend, frontend
    requests: { cpu: 100m, memory: 256Mi }
    limits:   { cpu: 1000m, memory: 1Gi }
```

- [ ] **Step 4: Appliquer sur chaque workload**

Dans **chaque** `templates/*.yaml`, au niveau `spec.template.spec` :

```yaml
      automountServiceAccountToken: false   # aucun pod n'appelle l'API k8s
      securityContext:
        runAsNonRoot: true
        runAsUser: <UID du composant>
        seccompProfile: { type: RuntimeDefault }   # requis par le profil PSS restricted
```

…et sur **chaque** conteneur :

```yaml
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources: {{- toYaml .Values.resources.<profil> | nindent 12 }}
```

`readOnlyRootFilesystem` impose ces `emptyDir` (chemins réellement écrits) :
- **postgres** : `/tmp`, `/var/run/postgresql` (socket).
- **redis** : `/tmp`, `/data`.
- **minio** : `/tmp` (les données sont sur le PVC).
- **openbao** : `/tmp` (dev-mode = in-memory).
- **backend** : `/tmp`.
- **frontend** : `/tmp` **et `/app/.next/cache`** — Next standalone y écrit le cache ISR ; sans cet `emptyDir`, le serveur crashe au premier rendu.

Exemple (frontend) :

```yaml
          volumeMounts:
            - { name: tmp, mountPath: /tmp }
            - { name: next-cache, mountPath: /app/.next/cache }
      volumes:
        - { name: tmp, emptyDir: {} }
        - { name: next-cache, emptyDir: {} }
```

**Exception documentée** : `openbao` garde `capabilities.add: ["IPC_LOCK"]` (mlock).

- [ ] **Step 5: Lancer — passe** (`bash infra/helm/facil/tests/test_render.sh` → `OK render`).

- [ ] **Step 6: Commit**

```bash
git add infra/helm/facil/values.yaml infra/helm/facil/templates/ infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): resources limits, seccomp, readOnlyRootFS, no SA token (SEC-015)"
```

### Task H2 : NetworkPolicies default-deny (SEC-012)

**Files:**
- Create: `infra/helm/facil/templates/networkpolicy.yaml`
- Modify: `infra/helm/facil/values.yaml`

**Contexte :** k3s embarque **kube-router** pour les NetworkPolicy → elles sont **appliquées nativement**, pas ignorées (contrairement à un cluster flannel nu). Aujourd'hui, Postgres/Redis/MinIO/OpenBao sont joignables par **n'importe quel pod** du cluster.

- [ ] **Step 1: Étendre le test**

```bash
echo "$OUT" | grep -q "kind: NetworkPolicy"
echo "$OUT" | grep -q "policyTypes"
```

- [ ] **Step 2: Lancer — échoue** → FAIL.

- [ ] **Step 3: Écrire `templates/networkpolicy.yaml`**

```yaml
{{- if .Values.networkPolicy.enabled }}
{{/*
Default-deny sur tout le namespace, puis allow explicites. k3s applique les
NetworkPolicy nativement (kube-router embarque). Sans ca, tout pod du cluster
joint Postgres:5432 / Redis:6379 / MinIO:9000 / OpenBao:8200 en direct.
*/}}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "facil.fullname" (dict "name" "default-deny") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  podSelector: {}          # tous les pods du namespace
  policyTypes: [Ingress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "facil.fullname" (dict "name" "allow-datastores-from-backend") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  # Les datastores n'acceptent QUE le backend et les Jobs de migration.
  podSelector:
    matchExpressions:
      - key: facil.component
        operator: In
        values: [postgres, redis, minio, openbao]
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchExpressions:
              - key: facil.component
                operator: In
                values: [backend, db-init, db-role]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "facil.fullname" (dict "name" "allow-backend-from-frontend") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      facil.component: backend
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              facil.component: frontend
        {{- if .Values.ingress.enabled }}
        # Traefik (ingress controller de k3s) vit dans kube-system.
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
        {{- end }}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "facil.fullname" (dict "name" "allow-frontend-from-ingress") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      facil.component: frontend
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
{{- end }}
```

Dans `values.yaml` :

```yaml
networkPolicy:
  enabled: true   # k3s applique les NetworkPolicy nativement (kube-router)
```

- [ ] **Step 4: Lancer — passe** → `OK render`.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/networkpolicy.yaml infra/helm/facil/values.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): NetworkPolicies default-deny + allow cibles (SEC-012)"
```

### Task H3 : Ingress Traefik — rendre la stack joignable (SEC-024)

**Files:**
- Create: `infra/helm/facil/templates/ingress.yaml`
- Modify: `infra/helm/facil/values.yaml`, `values-onprem.yaml`

**Contexte :** aujourd'hui, une fois déployée, la stack n'est joignable **de nulle part** (aucun Ingress, aucun NodePort ; `caddy.enabled: false`). Seul un `port-forward` y accède. k3s embarque **Traefik** → `ingressClassName: traefik`.

- [ ] **Step 1: Étendre le test**

```bash
echo "$OUT" | grep -q "kind: Ingress"
echo "$OUT" | grep -q "ingressClassName: traefik"
```

- [ ] **Step 2: Lancer — échoue** → FAIL.

- [ ] **Step 3: Écrire `templates/ingress.yaml`**

```yaml
{{- if .Values.ingress.enabled }}
{{/*
Single-origin (anti-CORS) : "/" -> frontend, "/api" -> backend, sur le meme hote.
Traefik est l'ingress controller embarque de k3s. TLS = P2 (cert-manager /
OpenBao PKI) ; ici on expose en HTTP sur le reseau local du noeud.
*/}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "facil.fullname" (dict "name" "ingress") }}
  labels: {{- include "facil.labels" . | nindent 4 }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  rules:
    - host: {{ .Values.ingress.host | quote }}
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: {{ include "facil.fullname" (dict "name" "backend") }}
                port:
                  number: {{ .Values.backend.port }}
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ include "facil.fullname" (dict "name" "frontend") }}
                port:
                  number: {{ .Values.frontend.port }}
{{- end }}
```

Dans `values.yaml` :

```yaml
ingress:
  enabled: true
  className: traefik      # ingress controller embarque de k3s
  host: facil.local       # surcharger par l'overlay / --set pour un vrai domaine
```

- [ ] **Step 4: Lancer — passe** → `OK render`.

- [ ] **Step 5: Commit**

```bash
git add infra/helm/facil/templates/ingress.yaml infra/helm/facil/values.yaml infra/helm/facil/tests/test_render.sh
git commit -m "feat(helm): Ingress Traefik single-origin (/ -> web, /api -> backend) (SEC-024)"
```

### Task H4 : digests d'images, `--set-string`, selector `instance`, values morte (SEC-014/017/018/020, SEC-008)

**Files:**
- Modify: `infra/helm/facil/values.yaml`, `templates/_helpers.tpl`, `deploy/providers/k3s.py`

**⚠️ Ordre critique :** `spec.selector` est **immutable après création**. Le changement de selector (SEC-018) doit être fait **avant le premier apply** — donc **avant** le smoke V1. Ne pas repousser cette tâche après V1.

- [ ] **Step 1: Étendre le test**

```bash
# SEC-018 : sans app.kubernetes.io/instance dans le selector, deux releases dans le
# meme namespace se volent leurs pods (les Services selectionnent ceux de l'autre).
echo "$OUT" | grep -A3 "matchLabels:" | grep -q "app.kubernetes.io/instance"
# SEC-014 : le coffre-fort et le stockage objet ne doivent pas suivre un tag mutable.
echo "$OUT" | grep -q "minio/minio@sha256:"
echo "$OUT" | grep -q "openbao/openbao@sha256:"
# SEC-020 : global.namespace n'etait reference par aucun template (valeur morte).
! grep -q "namespace: facil" infra/helm/facil/values.yaml
```

- [ ] **Step 2: Lancer — échoue** → FAIL.

- [ ] **Step 3: Selector avec `instance` (`_helpers.tpl`)**

```yaml
{{- define "facil.selectorLabels" -}}
app.kubernetes.io/name: facil
app.kubernetes.io/instance: {{ .Release.Name }}
facil.component: {{ .component }}
{{- end -}}
```

Les appels passent déjà `.Release` (`dict "Release" .Release "component" "..."`) — aucun call-site à changer.

- [ ] **Step 4: Pinner MinIO et OpenBao par digest**

Résoudre les digests réels (ne pas inventer) :

```bash
docker buildx imagetools inspect minio/minio:latest   --format '{{.Manifest.Digest}}'
docker buildx imagetools inspect openbao/openbao:latest --format '{{.Manifest.Digest}}'
```

Reporter dans `values.yaml` (remplacer les `:latest`), en gardant le tag en commentaire pour la traçabilité :

```yaml
minio:
  # Pinne par digest (SEC-014) : `:latest` sur le stockage objet = un push amont
  # compromis se propage au prochain restart de pod, sans trace ni rollback.
  image: minio/minio@sha256:<DIGEST_REEL>   # ~ :latest au 2026-07-13
openbao:
  image: openbao/openbao@sha256:<DIGEST_REEL>   # ~ :latest au 2026-07-13
```

Supprimer `global.namespace` (valeur morte, SEC-020).

- [ ] **Step 5: `--set-string` pour les valeurs textuelles (SEC-017)**

Dans `k3s.py`, `_set_args` coerce les types (`--set` de Helm parse `0123` en `123`, ce qui casse un `imageTag` numérique). Remplacer :

```python
# Cles dont la valeur DOIT rester une chaine : `--set` de Helm coerce les types
# (strconv.ParseInt), donc meta.version="0123" deviendrait le tag 123 (SEC-017).
_STRING_KEYS = {"global.imageTag", "postgres.image", "postgres.db", "postgres.user",
                "redis.image", "minio.rootUser", "backend.modulesEnabled",
                "secretNames.postgres", "secretNames.redis", "secretNames.minio",
                "secretNames.openbao", "secretNames.backend", "secretNames.dbRole"}


def _set_args(values: dict) -> list[str]:
    """Traduit le dict de values (SANS secret) en `--set`/`--set-string`."""
    args: list[str] = []
    for section, sub in values.items():
        items = sub.items() if isinstance(sub, dict) else [(None, sub)]
        for k, v in items:
            path = f"{section}.{k}" if k is not None else section
            flag = "--set-string" if path in _STRING_KEYS else "--set"
            args += [flag, f"{path}={_escape_set_value(v)}"]
    return args
```

- [ ] **Step 6: Brancher `imagePullSecrets`** (SEC-008 — le helper `facil.imagePullSecrets` existe déjà dans `_helpers.tpl`) dans `backend.yaml`, `frontend.yaml`, `db-init-job.yaml`, au niveau `spec.template.spec` :

```yaml
      {{- include "facil.imagePullSecrets" . | nindent 6 }}
```

(Vérifié le 2026-07-13 : `ghcr.io/kouemousah/facil-{backend,web}` sont **publics** — pull anonyme HTTP 200. Le champ reste vide par défaut ; il existe pour le cas registre privé, qui est la norme en on-prem souverain.)

- [ ] **Step 7: Lancer — passent**

Run: `bash infra/helm/facil/tests/test_render.sh && & C:\facil_framework\.venv\Scripts\python.exe -m pytest deploy/ -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add infra/helm/facil/ deploy/providers/k3s.py
git commit -m "fix(helm): digests minio/openbao, selector instance, --set-string, imagePullSecrets (SEC-008/014/017/018/020)"
```

---

## PHASE V — Valider pour de vrai

### Task V1 : smoke k3d (la seule preuve qui compte)

**Files:**
- Create: `infra/helm/facil/SMOKE.md`

**Contexte :** `helm lint` + `helm template` + 103 pytest étaient **tous verts** alors que le chart ne pouvait pas démarrer (4 bloquants). Cette tâche est la gate réelle.

- [ ] **Step 1: Installer k3d et créer un cluster jetable**

```bash
# k3d = k3s dans Docker. Cluster ephemere : `k3d cluster delete` rend la RAM et le disque.
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
k3d cluster create facil --agents 0 --wait
kubectl config use-context k3d-facil
kubectl get nodes    # Expected: 1 noeud Ready
```

- [ ] **Step 2: Générer les secrets manquants**

Run: `& C:\facil_framework\.venv\Scripts\python.exe deploy/scripts/ensure_secrets.py`
Expected: génère `FACIL_APP_PASSWORD`, `SECRET_KEY`, `RECEIPT_VERIFICATION_SECRET`, `CRON_SECRET` (les autres existent déjà).

- [ ] **Step 3: validate → plan → apply**

```bash
python deploy/deploy.py --provider=k3s --action=validate
python deploy/deploy.py --provider=k3s --action=plan | python infra/helm/facil/tests/guard_secrets.py
python deploy/providers/k3s.py --apply --yes --allow-dev-vault
```
Expected: exit 0 sur les trois. Le `--apply` crée le namespace, 6 Secrets, la ConfigMap SQL, puis `helm upgrade --atomic --wait`.

- [ ] **Step 4: Vérifier les critères d'acceptation**

```bash
kubectl -n facil get pods              # 6 pods Running/Ready
kubectl -n facil get jobs              # facil-db-role + facil-db-init : Complete
kubectl -n facil exec deploy/facil-backend -- \
  python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8080/health',timeout=3).status)"
# Expected: 200

# Le backend se connecte-t-il bien en facil_app (et PAS en superuser) ?
kubectl -n facil exec sts/facil-postgres -- \
  psql -U facil -d facil -tAc \
  "SELECT usename FROM pg_stat_activity WHERE datname='facil' AND usename<>'facil'"
# Expected: facil_app

# Le backend a-t-il vraiment perdu les creds root ? (SEC-001)
kubectl -n facil exec deploy/facil-backend -- printenv | \
  grep -E "POSTGRES_PASSWORD|MINIO_ROOT_PASSWORD|OPENBAO_DEV_ROOT_TOKEN"
# Expected: AUCUNE sortie (exit 1)

# Aucun secret dans le manifest Helm versionne
helm -n facil get manifest facil | python infra/helm/facil/tests/guard_secrets.py
# Expected: OK

# La stack est-elle joignable ? (Ingress)
kubectl -n facil get ingress
curl -H "Host: facil.local" http://localhost:8080/    # via le port mappe par k3d
```

- [ ] **Step 5: Écrire `SMOKE.md`** avec la procédure ci-dessus **et les résultats réellement observés** (pas les résultats espérés). Si un critère échoue : ouvrir un finding, corriger, re-smoker.

- [ ] **Step 6: Libérer les ressources**

```bash
k3d cluster delete facil        # rend la RAM (~2-3 Go) et supprime les images du cluster
docker system prune -f
```
(Le `docker_data.vhdx` de WSL ne rétrécit pas seul : `compact vdisk` si besoin — cf. mémoire `reference_docker_disk_reclaim`.)

- [ ] **Step 7: Commit**

```bash
git add infra/helm/facil/SMOKE.md
git commit -m "docs(helm): smoke k3d reel — procedure + resultats observes"
```

### Task V2 : gate finale

- [ ] **Step 1: Re-revue sécurité** — relancer l'agent `security-auditor` sur `git diff develop...HEAD`, en lui donnant le rapport précédent : vérifier que **chaque** finding est fermé ou explicitement différé avec justification.
- [ ] **Step 2: `silent-failure-hunter`** sur `deploy/providers/k3s.py` : chaque `subprocess.run(check=False)` propage-t-il un exit-code non-zéro ?
- [ ] **Step 3: Self-checklist**
  - [ ] Les 4 bloquants apply sont fermés **et prouvés par le smoke** (pas par `helm template`).
  - [ ] Le backend ne détient **aucun** credential root (vérifié par `printenv` sur le pod réel).
  - [ ] Les gardes **peuvent échouer** (mutation testée sur les deux).
  - [ ] `docker-local` (compose) toujours valide — zéro régression.
  - [ ] Différés documentés : OpenBao mode scellé (plan P7/P8), TLS Ingress (P2), services gated keycloak/otel/ollama/mail (P1b services).
- [ ] **Step 4: Commit des corrections + demander l'accord de push.**

---

## Self-Review (contre les findings)

**1. Couverture.** APPLY-001 ✅ (déjà corrigé + test) · APPLY-002 → R3 · APPLY-003 → R2 · APPLY-004 → R1 · SEC-001 → S1 · SEC-002 → S3 · SEC-006 → S2 · SEC-008 → H4 · SEC-009 → G2 · SEC-010 → G1 · SEC-011 → R2 · SEC-012 → H2 · SEC-013 → S1 (le backend perd le root MinIO ; le **câblage** d'un SA MinIO dépend du bootstrap data-plane → **différé, documenté**) · SEC-014/017/018/020 → H4 · SEC-015 → H1 · SEC-016 → S2 · SEC-019/022 → R1 · SEC-021 (redis `--requirepass` en argv) → **différé** (exige un `redis.conf` monté ; déjà TODO'd dans le code) · SEC-023 → S3 · SEC-024 → H3.

**2. Placeholders.** Deux valeurs sont à **résoudre à l'exécution, pas à inventer** : les digests d'images (H4 Step 4 donne la commande exacte) et les résultats du smoke (V1 Step 5 exige les résultats *observés*). Tout le reste porte le code réel.

**3. Cohérence des noms.** `secretNames.{postgres,redis,minio,openbao,backend,dbRole}` ↔ `build_secret_literals()` (clés `postgres/redis/minio/openbao/backend/db-role`) ↔ `secret_names` dans `main()`. `pg_roles.app_role_name()` / `create_role_sql()` ↔ `k3s.backend_database_url()` / `render_role_sql()`. Composants du selector (`facil.component`) ↔ NetworkPolicies (`postgres, redis, minio, openbao, backend, frontend, db-init, db-role`).

**4. Risque assumé.** `readOnlyRootFilesystem` (H1) est la tâche la plus susceptible de casser au smoke : les chemins écrits sont déduits des Dockerfiles, pas observés. V1 tranche — et c'est exactement le rôle du smoke.
