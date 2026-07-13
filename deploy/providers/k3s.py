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
import shutil
import subprocess
import sys
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
            "db": "facil",
            "user": "facil",
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
    parser.add_argument("--yes", action="store_true",
                        help="Confirme --apply sans prompt interactif.")
    parser.add_argument("--allow-dev-vault", action="store_true",
                        help="Autorise OpenBao en dev-mode (stockage in-memory, HTTP "
                             "en clair). SMOKE/DEV UNIQUEMENT — jamais en production.")
    args = parser.parse_args(argv)

    helm = find_helm()
    if not helm:
        print("ERREUR: helm introuvable dans le PATH. Installer Helm v3.", file=sys.stderr)
        return 2

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
        print(f"=== k3s plan (namespace={args.namespace}) — helm template, lecture seule ===")
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

    # 1) Secrets k8s (hors Helm), UN PAR COMPOSANT (SEC-001) — manifestes construits
    #    en Python, jamais ecrits dans un fichier, pipes sur stdin (SEC-006 : jamais
    #    dans l'argv).
    for component, lits in literals.items():
        rc = apply_manifest(kubectl, args.namespace,
                            build_secret_manifest(SECRET_NAMES[component], lits))
        if rc != 0:
            return rc

    # 2) helm upgrade --install (backend/web pullent GHCR ; jamais de build ici).
    rc = subprocess.run(
        [helm, "upgrade", "--install", "facil", str(CHART_DIR),
         "-n", args.namespace, "--create-namespace",
         "-f", str(VALUES_ONPREM),
         *_set_args(values),
         "--atomic",                       # SEC-022 : rollback auto si le deploiement echoue
         "--wait", "--timeout", "10m"],
        check=False,
    ).returncode
    return 0 if rc == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
