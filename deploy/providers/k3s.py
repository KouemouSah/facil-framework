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

DEFAULT_CONFIG = DEPLOY_DIR / "config.yaml"

# Doit matcher infra/helm/facil/values.yaml::secretName (secretKeyRef partout).
SECRET_NAME = "facil-secrets"

# Allowlist stricte des cles injectees dans le Secret k8s — rien d'autre ne
# fuit de .env.secrets, meme si ce fichier contient d'autres cles (GEMINI_API_KEY,
# RESEND_API_KEY, SCIM_TOKEN, KEYCLOAK_ADMIN_PASSWORD, ...). Couvre : les 4
# creds infra generees par ensure_secrets.py (Postgres/Redis/MinIO/OpenBao),
# les 4 noms de secret references par deploy/config.yaml (auth.jwt_secret_name,
# auth.app_secret_name, auth.totp_encryption_secret,
# auth.receipt_verification_secret, cron.secret_name), et BACKEND_DATABASE_URL
# (role applicatif moindre-privilege attendu par backend.yaml — voir NOTE
# apply ci-dessous : pas encore produit par .env.secrets, gap documente).
SECRET_KEYS = [
    "POSTGRES_PASSWORD", "REDIS_PASSWORD", "MINIO_ROOT_PASSWORD",
    "OPENBAO_DEV_ROOT_TOKEN", "JWT_SECRET_KEY", "SECRET_KEY",
    "TOTP_ENCRYPTION_KEY", "RECEIPT_VERIFICATION_SECRET", "CRON_SECRET",
    "BACKEND_DATABASE_URL",
]

# Secrets sans lesquels le backend ne demarre pas (fail-closed sur --apply).
REQUIRED_APPLY_SECRETS = ("POSTGRES_PASSWORD", "JWT_SECRET_KEY", "SECRET_KEY")


def render_values(cfg: vc.DeployConfig) -> dict:
    """config.yaml -> dict de values Helm. AUCUNE valeur de secret ici —
    seul le nom du k8s Secret (cree hors Helm) est reference."""
    return {
        "secretName": SECRET_NAME,
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


def build_secret_literals(env_secrets: dict[str, str]) -> dict[str, str]:
    """Extrait UNIQUEMENT les cles de l'allowlist SECRET_KEYS presentes dans
    .env.secrets — allowlist stricte, jamais un passthrough du fichier entier."""
    return {k: env_secrets[k] for k in SECRET_KEYS if k in env_secrets}


def find_helm() -> str | None:
    return shutil.which("helm") or shutil.which("helm.exe")


def find_kubectl() -> str | None:
    return shutil.which("kubectl") or shutil.which("kubectl.exe")


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


def _set_args(values: dict) -> list[str]:
    """Traduit le dict de values (SANS secret) en `--set section.key=val`
    repetes, pour surcharger infra/helm/facil/values.yaml a l'upgrade."""
    args: list[str] = []
    for section, sub in values.items():
        if isinstance(sub, dict):
            for k, v in sub.items():
                args += ["--set", f"{section}.{k}={_escape_set_value(v)}"]
        else:
            args += ["--set", f"{section}={_escape_set_value(sub)}"]
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
            [helm, "template", "facil", str(CHART_DIR),
             "-f", str(VALUES_ONPREM), *_set_args(values)],
            check=False,
        )
        return 0 if proc.returncode == 0 else 2

    # --apply
    kubectl = find_kubectl()
    if not kubectl:
        print("ERREUR: kubectl introuvable dans le PATH.", file=sys.stderr)
        return 2

    env = _load_env_secrets(REPO_ROOT / ".env.secrets")
    literals = build_secret_literals(env)
    missing = [k for k in REQUIRED_APPLY_SECRETS if k not in literals]
    if missing:
        print(f"ERREUR: secrets requis absents de .env.secrets: {missing}", file=sys.stderr)
        return 1

    print(f"Sur le point de creer/mettre a jour le Secret '{SECRET_NAME}' et de faire "
          f"`helm upgrade --install facil` dans le namespace '{args.namespace}'.")
    if not args.yes:
        ans = input("Continuer ? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Annule.")
            return 4

    # 1) Secret k8s (hors Helm) — valeurs jamais ecrites dans un fichier,
    #    jamais imprimees/loggees (dry_run.stdout n'est jamais print()e).
    sec_args = [kubectl, "-n", args.namespace, "create", "secret", "generic",
                SECRET_NAME, "--dry-run=client", "-o", "yaml"]
    for k, v in literals.items():
        sec_args.append(f"--from-literal={k}={v}")
    dry_run = subprocess.run(sec_args, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    if dry_run.returncode != 0:
        print("ERREUR: kubectl create secret --dry-run a echoue.", file=sys.stderr)
        print(dry_run.stderr, file=sys.stderr)
        return 2
    applied = subprocess.run(
        [kubectl, "-n", args.namespace, "apply", "-f", "-"],
        input=dry_run.stdout, text=True, encoding="utf-8", errors="replace",
    )
    if applied.returncode != 0:
        print("ERREUR: kubectl apply du Secret a echoue.", file=sys.stderr)
        return 2

    # 2) helm upgrade --install (backend/web pullent GHCR ; jamais de build ici).
    rc = subprocess.run(
        [helm, "upgrade", "--install", "facil", str(CHART_DIR),
         "-n", args.namespace, "--create-namespace",
         "-f", str(VALUES_ONPREM),
         *_set_args(values), "--wait", "--timeout", "10m"],
        check=False,
    ).returncode
    return 0 if rc == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
