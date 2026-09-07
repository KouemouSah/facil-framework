#!/usr/bin/env python3
"""k3s provider — deploie la stack via le chart Helm infra/helm/facil.

Rend les `values` Helm depuis deploy/config.yaml, cree le k8s Secret depuis
.env.secrets HORS du flux Helm versionne (les valeurs de secrets ne
transitent JAMAIS par un fichier `values.yaml` ni par `helm --set` — normes
secrets renforcees), puis `helm upgrade --install`. CLI alignee sur les
providers freres (deploy/providers/aws.py, gcp.py, azure.py) :
`--validate/--plan/--apply`, memes exit codes.

Usage
-----
    python deploy/providers/k3s.py --config=deploy/config.yaml --validate
    python deploy/providers/k3s.py --config=deploy/config.yaml --plan
    python deploy/providers/k3s.py --config=deploy/config.yaml --apply
    python deploy/providers/k3s.py --rollback [--revision N] [--namespace ns]

`--rollback` n'affecte QUE les manifestes Helm (`helm rollback`) -- jamais la
base de donnees. Voir deploy/scripts/restore_backup.py pour restaurer les
donnees depuis la sauvegarde pre-upgrade (jamais automatique -- decision
humaine requise).

Exit codes
----------
0  Success.
1  Validation error (config invalide, secrets requis absents de .env.secrets).
2  helm/kubectl introuvable ou invocation echouee.
3  Fichier de config introuvable.
4  Utilisateur a annule la confirmation --apply.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROVIDERS_DIR = Path(__file__).resolve().parent
DEPLOY_DIR = PROVIDERS_DIR.parent
REPO_ROOT = DEPLOY_DIR.parent
CHART_DIR = REPO_ROOT / "infra" / "helm" / "facil"
# Overlay on-prem mono-noeud (tailles/replicas/storageClass — aucun secret).
# Applique via `-f` avant les `--set` de render_values() (helm applique les
# `--set` en dernier, donc les deux coexistent sans conflit d'ordre).
VALUES_ONPREM = CHART_DIR / "values-onprem.yaml"
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import validate_config as vc  # noqa: E402
import pg_roles  # noqa: E402

DEFAULT_CONFIG = DEPLOY_DIR / "config.yaml"

# Secrets sans lesquels la stack ne peut pas demarrer (fail-closed sur --apply).
# FACIL_APP_PASSWORD : sans lui, pas de BACKEND_DATABASE_URL -> le backend reste
# en CreateContainerConfigError pendant les 10 min du --wait (APPLY-003).
REQUIRED_APPLY_SECRETS = ("POSTGRES_PASSWORD", "JWT_SECRET_KEY", "SECRET_KEY",
                          "FACIL_APP_PASSWORD")

# Nom du Secret k8s par composant — doit matcher values.yaml::secretNames.*
SECRET_NAMES = {
    "postgres": "facil-postgres-secret", "redis": "facil-redis-secret",
    "minio": "facil-minio-secret", "openbao": "facil-openbao-secret",
    "backend": "facil-backend-secret",
    "db-role": "facil-db-role-secret",
    "backup": "facil-backup-secret",
}


def backend_database_url(cfg: vc.DeployConfig, app_pw: str) -> str:
    """URL de connexion du backend — role applicatif, JAMAIS le superuser.

    Format aligne sur deploy/scripts/render_backend_env.py:53 (SQLAlchemy async).
    L'hote est le Service k8s du chart (facil-postgres), pas le conteneur compose.
    """
    role = pg_roles.app_role_name(cfg.meta.project_name)
    db = cfg.meta.project_name
    return f"postgresql+asyncpg://{role}:{app_pw}@facil-postgres:5432/{db}"


def render_role_sql(cfg: vc.DeployConfig) -> str:
    """SQL du role applicatif, rendu depuis pg_roles (source unique)."""
    role = pg_roles.app_role_name(cfg.meta.project_name)
    return pg_roles.render_sql(role, cfg.meta.project_name)


def render_values(cfg: vc.DeployConfig) -> dict:
    """config.yaml -> dict de values Helm. AUCUNE valeur de secret ici —
    seuls les noms des k8s Secret (crees hors Helm, un par composant — SEC-001)
    sont references, et ils matchent deja les defauts de values.yaml::secretNames
    donc aucun --set n'est necessaire pour eux."""
    return {
        "global": {"imageTag": cfg.meta.version},
        "postgres": {
            "image": cfg.docker_local.postgres_image,
            # Derives from project_name (B2) -- same convention as
            # docker_local.py:181-182 (POSTGRES_DB/POSTGRES_USER) and
            # backend_database_url()/render_role_sql() just above: a hardcoded
            # "facil" here meant the chart always created database `facil`
            # while db-role-job's GRANT CONNECT ON DATABASE <project_name>
            # targeted whatever the operator actually named their project --
            # a mismatched name broke the Job (and --atomic aborted the release).
            "db": cfg.meta.project_name,
            "user": cfg.meta.project_name,
        },
        "redis": {"image": cfg.docker_local.redis_image},
        "minio": {"rootUser": cfg.storage.minio.root_user},
        "openbao": {"devMode": cfg.secrets.openbao.dev_mode},
        "backend": {
            "port": cfg.docker_local.backend_port,
            "modulesEnabled": ",".join(cfg.modules.enabled),
        },
        "frontend": {"port": cfg.docker_local.frontend_port},
    }


def build_secret_literals(env_secrets: dict[str, str], *, cfg: vc.DeployConfig
                          ) -> dict[str, dict[str, str]]:
    """Repartit les secrets PAR COMPOSANT (SEC-001) — chaque pod ne recoit que ce qu'il
    consomme. Le backend n'a JAMAIS le superuser Postgres, le root MinIO ni le root token
    OpenBao : une RCE dans le backend (seule surface HTTP exposee) ne doit pas livrer le
    data-plane entier. Sa config (packages/backend/app/config.py, extra="ignore") n'en lit
    d'ailleurs aucun — ils n'etaient la que par accident de conception (`envFrom`).

    Retourne {composant: {CLE: valeur}} ; un composant sans secret disponible est omis.
    """
    def pick(*keys: str) -> dict[str, str]:
        return {k: env_secrets[k] for k in keys if k in env_secrets}

    out: dict[str, dict[str, str]] = {
        "postgres": pick("POSTGRES_PASSWORD"),
        "redis": pick("REDIS_PASSWORD"),
        "minio": pick("MINIO_ROOT_PASSWORD"),
        "openbao": pick("OPENBAO_DEV_ROOT_TOKEN"),
        # REDIS_PASSWORD : le backend est CLIENT de Redis, il en a besoin. Pas de
        # POSTGRES_PASSWORD (superuser) : il se connecte via BACKEND_DATABASE_URL.
        "backend": pick("JWT_SECRET_KEY", "SECRET_KEY", "TOTP_ENCRYPTION_KEY",
                        "RECEIPT_VERIFICATION_SECRET", "CRON_SECRET", "REDIS_PASSWORD"),
    }
    # L'URL de connexion du backend est DERIVEE de FACIL_APP_PASSWORD : aucun script du
    # repo n'ecrit BACKEND_DATABASE_URL dans .env.secrets (APPLY-003), et le secretKeyRef
    # de backend.yaml n'est pas `optional` -> sans cette derivation, le pod backend reste
    # bloque en CreateContainerConfigError pendant les 10 min du --wait.
    if (app_pw := env_secrets.get("FACIL_APP_PASSWORD")):
        out["backend"]["BACKEND_DATABASE_URL"] = backend_database_url(cfg, app_pw)
    # Le Job db-role a besoin du superuser (pour CREATE ROLE) ET du mdp applicatif.
    out["db-role"] = pick("POSTGRES_PASSWORD", "FACIL_APP_PASSWORD")
    # Le Job de backup (hook pre-upgrade) : dump Postgres complet (superuser) +
    # mirror des buckets MinIO (root). Ses propres credentials, cloisonnes --
    # jamais ceux du backend.
    out["backup"] = pick("POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD")
    return {k: v for k, v in out.items() if v}


def find_helm() -> str | None:
    return shutil.which("helm") or shutil.which("helm.exe")


def find_kubectl() -> str | None:
    return shutil.which("kubectl") or shutil.which("kubectl.exe")


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


def build_pvc_manifest(name: str, storage_class: str, storage: str) -> str:
    """PVC des sauvegardes (B2) — construit HORS Helm, applique via `kubectl
    apply -f -` (meme chemin stdin que build_secret_manifest/
    build_configmap_manifest ci-dessus, DRY), idempotent.

    Ce PVC vivait auparavant DANS le chart (infra/helm/facil/templates/
    backup-pvc.yaml), porte par un hook `pre-install` SEUL (jamais
    `pre-upgrade` — un hook de ce type est recree a CHAQUE upgrade, ce qui
    aurait soit echoue "already exists", soit DETRUIT le volume de sauvegardes
    lui-meme). Mais Helm n'execute un hook `pre-install` QUE lors du tout
    premier `helm install` d'une release — donc sur un `helm upgrade` d'une
    release DEJA installee (exactement la population que P2 protege : un
    client qui tourne deja avec des donnees), ce PVC n'etait JAMAIS cree. Le
    Job `facil-backup` (qui le monte) restait alors `Pending`
    ("persistentvolumeclaim not found") indefiniment -> le hook `pre-upgrade`
    ne se completait jamais -> timeout `--wait` (10 min) -> rollback
    `--atomic` -> ECHEC SYSTEMATIQUE, a chaque tentative (B2). En le creant ICI
    (avant `helm upgrade --install`, independamment du cycle de vie de la
    release), il existe deja au moment ou le Job de sauvegarde en a besoin,
    qu'il s'agisse d'un premier install ou d'un upgrade ulterieur.

    JAMAIS supprime par ce provider (aucun `kubectl delete` correspondant) :
    les sauvegardes doivent survivre a tout `helm uninstall` — ce PVC n'etant
    plus une ressource du chart, `helm uninstall` ne peut de toute facon plus
    y toucher.
    """
    return (
        "apiVersion: v1\n"
        "kind: PersistentVolumeClaim\n"
        "metadata:\n"
        f"  name: {name}\n"
        "spec:\n"
        '  accessModes: ["ReadWriteOnce"]\n'
        f"  storageClassName: {storage_class}\n"
        "  resources:\n"
        "    requests:\n"
        f"      storage: {storage}\n"
    )


def chart_pvc_defaults() -> tuple[str, str]:
    """(storageClass, storage) pour le PVC des sauvegardes — lus depuis les
    values DEJA versionnees du chart (infra/helm/facil/values.yaml + l'overlay
    values-onprem.yaml, les DEUX memes sources que `--plan`/`--apply`
    utilisent deja pour tout le reste), jamais un litteral duplique ici qui
    pourrait silencieusement diverger du chart.
    """
    base = vc.load_yaml(CHART_DIR / "values.yaml")
    overlay = vc.load_yaml(VALUES_ONPREM)
    storage_class = ((overlay.get("global") or {}).get("storageClass")
                     or base["global"]["storageClass"])
    storage = (overlay.get("backup") or {}).get("storage") or base["backup"]["storage"]
    return storage_class, storage


def backup_is_enabled() -> bool:
    """`backup.enabled` ET `postgres.enabled` effectifs — memes sources que
    `chart_pvc_defaults()` (values.yaml + overlay values-onprem.yaml), jamais un
    litteral duplique ici qui pourrait diverger du chart en silence.

    Sert au garde-fou de `--apply` : le Job `facil-backup` est gate par
    `{{- if and .Values.backup.enabled .Values.postgres.enabled }}`. Desactiver
    l'un ou l'autre supprime la sauvegarde -- et `helm upgrade` migrait quand
    meme, en silence, en sortant 0, TOUTES les gardes restant vertes (elles
    verifient l'ORDRE du Job, pas son EXISTENCE).
    """
    base = vc.load_yaml(CHART_DIR / "values.yaml")
    overlay = vc.load_yaml(VALUES_ONPREM)
    merged = {}
    for section in ("backup", "postgres"):
        merged[section] = {**(base.get(section) or {}),
                           **((overlay.get(section) or {}))}
    return (bool(merged["backup"].get("enabled", True))
            and bool(merged["postgres"].get("enabled", True)))


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


def release_exists(helm: str, namespace: str) -> bool:
    """True si une revision `facil` **deployee avec succes** existe deja.

    Lecture seule (`helm status -o json`, aucun effet de bord). Determine si
    --apply doit faire la danse deux-passes a 0 replica (A1 : SEULEMENT au 1er
    install reussi) ou une simple mise a jour a une passe (release existante :
    les hooks pre-upgrade tournent AVANT que --wait n'evalue le Deployment,
    donc aucun deadlock a contourner -- voir le commentaire du bloc appelant
    dans main() pour le detail du deadlock reel que la danse deux-passes resout).

    BUG REEL CORRIGE (smoke k3d task-E1, 2026-07-14) : `helm status` renvoie
    returncode==0 pour une release au statut "failed" (ex. un --apply
    precedent qui a echoue AVANT meme d'atteindre --atomic, donc sans
    rollback -- comme un pre-install hook bloque). L'ancienne version de cette
    fonction traitait alors une release jamais reellement installee comme
    "deja existante" -> --apply suivant prenait le chemin une-passe (single-
    pass --atomic), backend a son replica REEL des le depart, sur un cluster
    vierge sans role/migration -> EXACTEMENT le deadlock original (task-V1)
    que la danse deux-passes existe pour eviter. Un statut "failed" ou
    "pending-*" doit redeclencher la danse deux-passes comme un vrai 1er
    install (idempotent : reprendre a 0 replica ne fait de mal a rien).
    """
    proc = subprocess.run(
        [helm, "status", "facil", "-n", namespace, "-o", "json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        return False
    try:
        status = json.loads(proc.stdout).get("info", {}).get("status")
    except (json.JSONDecodeError, AttributeError):
        return False
    return status == "deployed"


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


def _load_env_secrets(path: Path) -> dict[str, str]:
    """Parse .env.secrets (KEY=VALUE par ligne). Ne log/print jamais son
    contenu — seules les valeurs allowlistees par build_secret_literals()
    quittent ce dict, et uniquement vers kubectl (stdin), jamais un fichier."""
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


def _escape_set_value(v: object) -> str:
    """Echappe les caracteres speciaux du mini-langage `--set` de Helm
    (virgule = separateur entre affectations ; ex. modulesEnabled=
    "organization,location" serait sinon coupe en `modulesEnabled=organization`
    + une cle `location` sans valeur -> `helm template`/`upgrade` en erreur)."""
    s = str(v)
    return s.replace(",", "\\,")


# Cles dont la valeur DOIT rester une chaine : `--set` de Helm coerce les types
# (strconv.ParseInt), donc meta.version="0123" deviendrait le tag 123 (SEC-017).
# `secretNames.*` n'est aujourd'hui jamais emis par render_values() (S1 les a
# retires), mais reste liste ici en anticipation defensive : si un futur appel
# venait a les rendre, ils ne doivent jamais glisser sur `--set` non plus (ce
# sont des noms de Secret k8s, pas des nombres, mais un nom purement numerique
# resterait tout aussi coercible).
_STRING_KEYS = {"global.imageTag", "postgres.image", "postgres.db", "postgres.user",
                "redis.image", "minio.rootUser", "backend.modulesEnabled",
                "secretNames.postgres", "secretNames.redis", "secretNames.minio",
                "secretNames.openbao", "secretNames.backend", "secretNames.dbRole"}


def _set_args(values: dict) -> list[str]:
    """Traduit le dict de values (SANS secret) en `--set`/`--set-string`
    repetes, pour surcharger infra/helm/facil/values.yaml a l'upgrade.

    `--set-string` pour les cles de `_STRING_KEYS` (SEC-017) : `--set` de Helm
    parse la valeur via `strconv.ParseInt`/`ParseBool` avant de l'ecrire dans
    values -- un `imageTag`/tag de version "0123" deviendrait silencieusement
    l'entier 123 (perte du zero de tete), et une image dont le tag ne serait
    QUE des chiffres casserait la reference d'image rendue.
    """
    args: list[str] = []
    for section, sub in values.items():
        items = sub.items() if isinstance(sub, dict) else [(None, sub)]
        for k, v in items:
            path = f"{section}.{k}" if k is not None else section
            flag = "--set-string" if path in _STRING_KEYS else "--set"
            args += [flag, f"{path}={_escape_set_value(v)}"]
    return args


def health_gate(kubectl: str, namespace: str, port: int, *,
                 deployment: str = "deploy/facil-backend",
                 attempts: int = 5, delay_seconds: float = 2.0) -> int:
    """Verifie `/health` APRES que Helm ait deja declare la release reussie.

    Honnetete sur ce que ca apporte (a ne pas perdre en cours de route) :
    `helm upgrade --wait` attend DEJA que les pods soient Ready, et la
    readinessProbe du backend EST DEJA `/health` (infra/helm/facil/templates/
    backend.yaml). Ce gate n'ajoute donc PAS une garantie fondamentale nouvelle
    -- il est INCREMENTAL. Ce qu'il ajoute reellement :
      1. Une verification APRES le retour de `helm upgrade`, distincte de la
         readinessProbe (qui peut avoir menti, ou dont la fenetre suivante
         n'a pas encore tourne juste apres --wait) -- "le pod est Ready" et
         "l'application repond" ne sont pas rigoureusement la meme assertion.
      2. Un message d'ECHEC EXPLOITABLE (namespace + Deployment + dernier
         diagnostic reel) au lieu d'un timeout Helm opaque ("context deadline
         exceeded") qui ne dit pas OU chercher.

    `kubectl exec` (pas de port-forward, pas de dependance HTTP externe au
    cluster) -- ce process Python tourne DANS le pod backend, via l'image deja
    presente (aucune image nouvelle). Tentatives espacees (defaut 5x2s) pour
    absorber une latence transitoire juste apres --wait.
    """
    probe = ("import urllib.request; "
             f"urllib.request.urlopen('http://localhost:{port}/health', timeout=3)")
    last_diag = ""
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(
            [kubectl, "-n", namespace, "exec", deployment, "--", "python", "-c", probe],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            return 0
        last_diag = (proc.stderr or proc.stdout or "").strip()
        if attempt < attempts:
            time.sleep(delay_seconds)
    # "L'application est cassee" et "je n'ai pas pu lui demander" ne sont PAS la
    # meme conclusion. La premiere pousse l'operateur vers --rollback -- justement
    # l'operation la plus risquee du provider (elle ne restaure pas la base). Le
    # gate accusait l'application dans les DEUX cas : un `kubectl exec` qui echoue
    # pour lui-meme (pod en cours de terminaison en fin de rolling update, RBAC,
    # skew kubectl) etait rapporte comme une panne applicative.
    #
    # La sonde est un `python -c` : si l'application REPOND non-200, urllib leve
    # une HTTPError/URLError et sa trace remonte ici. Si `kubectl exec` n'a pas pu
    # s'executer, c'est kubectl qui parle ("Error from server", "unable to...").
    app_answered = any(marker in last_diag for marker in
                       ("HTTPError", "URLError", "urllib", "Connection refused"))
    if app_answered:
        print(
            f"ERREUR: health-gate post-upgrade a echoue -- '{deployment}' (namespace "
            f"'{namespace}') ne repond pas sur /health apres {attempts} tentative(s).\n"
            f"Helm a pourtant declare la release reussie (--wait) : c'est donc "
            f"l'APPLICATION, pas seulement le pod, qui est en cause.\n"
            f"Dernier diagnostic : {last_diag or '(aucune sortie)'}\n"
            f"Inspecter : kubectl -n {namespace} logs {deployment}",
            file=sys.stderr,
        )
    else:
        print(
            f"ERREUR: health-gate post-upgrade NON CONCLUANT -- `kubectl exec` n'a pas "
            f"pu interroger '{deployment}' (namespace '{namespace}') en {attempts} "
            f"tentative(s).\n"
            f"Ce n'est PAS la preuve que l'application est en panne : la sonde n'a "
            f"jamais pu etre posee (pod en cours de terminaison, RBAC, kubectl "
            f"incompatible...). N'en deduisez PAS qu'il faut rollbacker -- verifiez "
            f"d'abord l'etat reel.\n"
            f"Dernier diagnostic : {last_diag or '(aucune sortie)'}\n"
            f"Inspecter : kubectl -n {namespace} get pods && kubectl -n {namespace} "
            f"logs {deployment}",
            file=sys.stderr,
        )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--namespace", default="facil")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true",
                      help="Verifie helm/kubectl + chart lint + config. Lecture seule.")
    mode.add_argument("--plan", action="store_true",
                      help="`helm template` (lecture seule) — n'imprime jamais de secret.")
    mode.add_argument("--apply", action="store_true",
                      help="Cree le Secret k8s (hors Helm) puis `helm upgrade --install`.")
    mode.add_argument("--rollback", action="store_true",
                      help="`helm rollback` vers la revision precedente. NE RESTAURE PAS "
                           "la base : voir deploy/scripts/restore_backup.py.")
    parser.add_argument("--revision", type=int, default=None,
                        help="Revision Helm cible (defaut : la precedente).")
    parser.add_argument("--yes", action="store_true",
                        help="Confirme --apply sans prompt interactif. NE COUVRE PAS "
                             "--rollback, qui exige toujours une confirmation humaine "
                             "(il ne restaure pas la base).")
    parser.add_argument("--no-backup", action="store_true",
                        help="Assume EXPLICITEMENT de migrer une release existante sans "
                             "sauvegarde pre-upgrade (backup.enabled=false). Sans ce "
                             "drapeau, --apply refuse : une migration destructive sur une "
                             "base non sauvegardee est sans recours.")
    parser.add_argument("--allow-dev-vault", action="store_true",
                        help="Autorise OpenBao en dev-mode (stockage in-memory, HTTP "
                             "en clair). SMOKE/DEV UNIQUEMENT — jamais en production.")
    args = parser.parse_args(argv)

    helm = find_helm()
    if not helm:
        print("ERREUR: helm introuvable dans le PATH. Installer Helm v3.", file=sys.stderr)
        return 2

    # --rollback n'a besoin d'aucune config applicative (deploy/config.yaml) :
    # traite AVANT la lecture de la config pour rester utilisable meme quand ce
    # fichier est absent (poste fraichement clone, CI) -- exactement le meme
    # constat que pour --validate/--plan/--apply, mais ceux-la ont besoin du
    # rendu des values, --rollback non.
    if args.rollback:
        # A4 : l'avertissement doit venir AVANT l'action (pas apres coup), et
        # exiger une confirmation -- coherent avec --apply, qui prompte deja.
        # L'ancien ordre (rollback d'abord, avertissement ensuite) laissait
        # l'operateur decouvrir "la base n'est pas restauree" APRES avoir deja
        # declenche l'operation, sans jamais avoir eu a en decider en connaissance
        # de cause.
        print(
            "\n*** ATTENTION : `helm rollback` NE RESTAURE PAS la BASE DE DONNEES. ***\n"
            "Il rend les MANIFESTES a leur etat anterieur -- jamais les donnees. Si la\n"
            "migration etait destructive (DROP COLUMN/TABLE), le schema restera casse et\n"
            "le code rollbacke tournera dessus.\n"
            "Pour restaurer la base depuis la sauvegarde pre-upgrade (operation SEPAREE,\n"
            "JAMAIS automatique) :\n"
            "    python deploy/scripts/restore_backup.py --list\n"
            "    python deploy/scripts/restore_backup.py --restore <horodatage>\n")
        # `--yes` ne couvre PAS --rollback (arbitrage explicite, revue E2). Il est
        # documente comme "confirme --apply", et --rollback est l'operation la
        # plus risquee du provider : il rend les manifestes SANS restaurer la
        # base. L'avertissement A4 ci-dessus ne sert a rien si un pipeline le
        # court-circuite -- or c'est precisement dans un pipeline que personne ne
        # le lit. Un rollback reste donc une decision humaine, toujours.
        ans = input("Continuer le rollback des manifestes ? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Annule.")
            return 4
        # Le returncode de `helm history` etait jete : sur une release/namespace
        # inexistant, l'operateur ne voyait RIEN s'afficher, puis `helm rollback`
        # echouait derriere. On s'arrete ici, avec la cause.
        hist = subprocess.run([helm, "history", "facil", "-n", args.namespace], check=False)
        if hist.returncode != 0:
            print(f"ERREUR: `helm history facil -n {args.namespace}` a echoue "
                  f"(code {hist.returncode}) -- aucune release 'facil' deployee dans "
                  f"ce namespace ? Rollback AVORTE : rien n'a ete touche.",
                  file=sys.stderr)
            return 2
        rb = [helm, "rollback", "facil"]
        if args.revision is not None:
            rb.append(str(args.revision))
        rb += ["-n", args.namespace, "--wait", "--timeout", "10m"]
        rc = subprocess.run(rb, check=False).returncode
        if rc != 0:
            print("ERREUR: `helm rollback` a echoue.", file=sys.stderr)
            return 2
        print(
            "[OK] `helm rollback` termine. RAPPEL : la base de donnees n'a PAS ete\n"
            "restauree (voir l'avertissement ci-dessus) -- utiliser\n"
            "deploy/scripts/restore_backup.py si besoin.")
        return 0

    if not args.config.exists():
        print(f"ERREUR: fichier de config introuvable: {args.config}", file=sys.stderr)
        return 3

    try:
        cfg = vc.DeployConfig.model_validate(vc.load_yaml(args.config))
    except Exception as e:  # validation pydantic
        print(f"ERREUR: config invalide:\n{e}", file=sys.stderr)
        return 1

    values = render_values(cfg)

    if args.validate:
        kubectl = find_kubectl()
        if not kubectl:
            print("ERREUR: kubectl introuvable dans le PATH.", file=sys.stderr)
            return 2
        proc = subprocess.run([helm, "lint", str(CHART_DIR)], check=False)
        if proc.returncode != 0:
            return 2
        print(f"[OK] k3s: helm+kubectl presents, chart lint OK, config valide "
              f"pour le projet '{cfg.meta.project_name}'.")
        return 0

    if args.plan:
        # Banner -> stderr : le stdout de `--plan` EST le rendu `helm template`,
        # destine a etre pipe tel quel dans guard_secrets.py (contrat documente
        # par son propre docstring : "helm template ... | python guard_secrets.py").
        # Une ligne de prose avant le premier `---` casse yaml.safe_load_all
        # (verifie en conditions reelles, task-V1 : ParserError sur le smoke).
        print(f"=== k3s plan (namespace={args.namespace}) — helm template, lecture seule ===",
              file=sys.stderr)
        proc = subprocess.run(
            [helm, "template",
             "-n", args.namespace,          # SEC-019 : sinon .Release.Namespace = "default"
             "facil", str(CHART_DIR),
             "-f", str(VALUES_ONPREM), *_set_args(values)],
            check=False,
        )
        return 0 if proc.returncode == 0 else 2

    # --apply
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

    kubectl = find_kubectl()
    if not kubectl:
        print("ERREUR: kubectl introuvable dans le PATH.", file=sys.stderr)
        return 2

    env = _load_env_secrets(REPO_ROOT / ".env.secrets")
    literals = build_secret_literals(env, cfg=cfg)
    flat = {k for comp in literals.values() for k in comp}
    missing = [k for k in REQUIRED_APPLY_SECRETS if k not in flat]
    if missing:
        print(f"ERREUR: secrets requis absents de .env.secrets: {missing}\n"
              f"Lancer: python deploy/scripts/ensure_secrets.py", file=sys.stderr)
        return 1

    # GARDE-FOU : migrer une release EXISTANTE sans sauvegarde possible. Le Job
    # facil-backup est gate par `backup.enabled` ET `postgres.enabled` ; un
    # `--set`, un overlay ou une regression sur values-onprem.yaml le fait
    # disparaitre -- et `helm upgrade` lancait alors `alembic upgrade head` sur
    # une base de production sans le moindre dump, EN SILENCE, en sortant 0.
    # Toutes les gardes restaient vertes : elles verifient l'ORDRE du Job, pas
    # son EXISTENCE. Un [WARN] ne suffit pas ici -- dans un pipeline, il se lit
    # apres la perte de donnees. On refuse, et l'operateur qui assume le risque
    # le declare : --no-backup. (Une PREMIERE installation ne protege rien : pas
    # de garde-fou, rien a perdre.)
    if not backup_is_enabled() and not args.no_backup and release_exists(helm, args.namespace):
        print("ERREUR: la sauvegarde pre-upgrade est DESACTIVEE (backup.enabled=false "
              "ou postgres.enabled=false) sur une release deja deployee.\n"
              "`helm upgrade` lancerait la migration Alembic sans aucune sauvegarde : "
              "une migration destructive (DROP COLUMN/TABLE) detruirait les donnees "
              "SANS RECOURS.\n"
              "  - reactiver backup.enabled dans values-onprem.yaml, OU\n"
              "  - assumer explicitement le risque : --no-backup\n"
              "Update AVORTE : rien n'a ete touche.", file=sys.stderr)
        return 1

    print(f"Sur le point de creer/mettre a jour {len(literals)} Secret(s) k8s (un par "
          f"composant, SEC-001) et de faire `helm upgrade --install facil` dans le "
          f"namespace '{args.namespace}'.")
    if not args.yes:
        ans = input("Continuer ? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Annule.")
            return 4

    # 0) Namespace d'abord (APPLY-004) : sur un cluster neuf, `kubectl apply`
    #    du Secret echoue tant que le namespace n'existe pas.
    rc_ns = ensure_namespace(kubectl, args.namespace)
    if rc_ns != 0:
        return rc_ns

    # 0bis) ConfigMap du SQL du role applicatif (source unique = pg_roles.py) —
    # le Job db-role-job.yaml la monte en volume. Pas un secret : meme chemin
    # stdin que le Secret (DRY), mais build_configmap_manifest (pas de base64).
    rc_cm = apply_manifest(kubectl, args.namespace, build_configmap_manifest(
        "facil-db-role-sql", {"role.sql": render_role_sql(cfg)}))
    if rc_cm != 0:
        return rc_cm

    # 0ter) PVC des sauvegardes (B2), HORS Helm — voir build_pvc_manifest() pour le
    # deadlock reel que ce chemin resout (un upgrade sur une release deja installee
    # n'execute jamais un hook `pre-install`). Cree/mis a jour AVANT `helm upgrade
    # --install`, pour que le Job facil-backup (pre-upgrade) le trouve toujours deja
    # existant, premier install comme upgrade suivant.
    storage_class, backup_storage = chart_pvc_defaults()
    rc_pvc = apply_manifest(kubectl, args.namespace, build_pvc_manifest(
        "facil-backups", storage_class, backup_storage))
    if rc_pvc != 0:
        return rc_pvc

    # 1) Secrets k8s (hors Helm), UN PAR COMPOSANT (SEC-001) — manifestes construits
    #    en Python, jamais ecrits dans un fichier, pipes sur stdin (SEC-006 : jamais
    #    dans l'argv).
    for component, lits in literals.items():
        rc = apply_manifest(kubectl, args.namespace,
                            build_secret_manifest(SECRET_NAMES[component], lits))
        if rc != 0:
            return rc

    # 2) helm upgrade --install (backend/web pullent GHCR ; jamais de build ici).
    base_helm_args = [
        helm, "upgrade", "--install", "facil", str(CHART_DIR),
        "-n", args.namespace, "--create-namespace",
        "-f", str(VALUES_ONPREM),
        *_set_args(values),
    ]

    if not release_exists(helm, args.namespace):
        # DEUX PASSES -- resout un DEADLOCK REEL trouve en smokant sur un vrai cluster
        # (task-V1, jamais vu par helm lint/template/pytest), et SEULEMENT au 1er
        # install (A1) : db-role/db-init sont des hooks `post-install,pre-upgrade`
        # (ils exigent Postgres deja demarre -> impossible en pre-install au 1er
        # install ; et SEC-001 interdit de les fondre dans un initContainer du
        # backend, qui ne doit JAMAIS voir le superuser Postgres). Or Helm n'execute
        # les hooks post-install QU'APRES que `--wait` ait vu TOUTES les ressources
        # non-hook pretes -- dont le Deployment backend. Le readinessProbe du backend
        # (`/health`) exige la BD, qui n'existe pas tant que ces memes hooks n'ont pas
        # tourne : deadlock garanti au 1er install. Verifie en conditions reelles :
        # `helm upgrade --atomic --wait` a systematiquement expire au bout de 10 min
        # sans qu'un seul Job soit jamais cree ("Error: release facil failed ...
        # context deadline exceeded"), le backend restart-loopant sur `password
        # authentication failed for user "facil_app"` (le role que le hook bloque
        # devait justement creer).
        #
        # Sur une release DEJA installee, ce deadlock n'existe PAS : les hooks
        # pre-upgrade tournent AVANT que Helm n'evalue le Deployment pour --wait --
        # donc pas de deux-passes a chaque `--apply` suivant (ca coupait le backend
        # -- 502 cote frontend -- a chaque upgrade, pour rien).
        #
        # Fix (1er install seulement) : 1re passe avec `backend.replicas=0` -- le
        # Deployment est alors trivialement "Available" (0 pod a attendre), `--wait`
        # passe vite, Postgres est deja debout -> les hooks tournent normalement
        # (creation du role + migrations). PAS de --atomic sur cette 1re passe : elle
        # n'a rien a proteger (un scale-to-0 qui rate laisse juste... rien), et
        # --atomic y ferait justement rollback vers un etat 0-replica si la 2e passe
        # echouait. 2e passe (--atomic ICI) qui remonte le replica reel (valeurs par
        # defaut du chart) : le role/schema existent desormais, `/health` repond 200
        # des le 1er cycle de probe. Les deux hooks sont idempotents (create_role_sql
        # = CREATE-si-absent + ALTER ; `alembic upgrade head` ne fait rien si deja a
        # jour) donc les rejouer au pre-upgrade de la 2e passe est sans effet de bord.
        rc = subprocess.run(
            [*base_helm_args, "--set", "backend.replicas=0",
             "--wait", "--timeout", "5m"],
            check=False,
        ).returncode
        if rc != 0:
            print("ERREUR: passe 1/2 (datastores + hooks db-role/db-init, backend a 0 "
                  "replica) a echoue.", file=sys.stderr)
            return 2

        rc = subprocess.run(
            [*base_helm_args, "--atomic", "--wait", "--timeout", "10m"],
            check=False,
        ).returncode
        if rc != 0:
            print(
                "ERREUR: passe 2/2 (remontee du backend a son replica reel) a echoue.\n"
                "Le backend est reste a 0 replica : --atomic n'a pu faire rollback QUE\n"
                "vers l'etat de la passe 1 (0 replica), pas vers la derniere release\n"
                "saine (il n'y en avait pas encore, c'est le 1er install).\n"
                "Options : relancer `--apply` (idempotent), ou `helm uninstall facil "
                f"-n {args.namespace}` pour repartir de zero.",
                file=sys.stderr)
            return 2
        return health_gate(kubectl, args.namespace, cfg.docker_local.backend_port)

    # Release deja installee : PAS de deadlock (les hooks pre-upgrade tournent avant
    # --wait), donc une seule passe -- rolling update normal, zero coupure backend --
    # avec --atomic protegeant ce qu'il doit reellement proteger : un rollback vers la
    # DERNIERE RELEASE SAINE si cet upgrade echoue (pas vers un etat 0-replica bidon).
    rc = subprocess.run(
        [*base_helm_args, "--atomic", "--wait", "--timeout", "10m"],
        check=False,
    ).returncode
    if rc != 0:
        print(
            "ERREUR: `helm upgrade` a echoue -- rollback automatique (--atomic) vers "
            "la derniere release saine.", file=sys.stderr)
        return 2
    return health_gate(kubectl, args.namespace, cfg.docker_local.backend_port)


if __name__ == "__main__":
    raise SystemExit(main())
