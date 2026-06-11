#!/usr/bin/env python3
"""Azure provider — Container Apps (serverless containers, the Cloud Run analog).

    1. --validate : az CLI present, logged in, subscription accessible. RO.
    2. --plan     : print the az commands (ACR ensure, Key Vault cross-check,
                    Container Apps create/update) WITHOUT executing.
    3. --apply    : EXPERIMENTAL — authored from spec, NOT validated against a
                    live Azure subscription; requires confirmation.

Mirrors providers/gcp.py + providers/aws.py. Images built+pushed by CI into ACR
(<acr>.azurecr.io/<repo>); this module only deploys.

Exit codes
----------
0 success · 1 validation error · 2 az CLI error · 3 file error · 4 aborted.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROVIDERS_DIR = Path(__file__).resolve().parent
DEPLOY_DIR = PROVIDERS_DIR.parent
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_config as vc  # noqa: E402

DEFAULT_CONFIG = DEPLOY_DIR / "config.yaml"
DEFAULT_MANIFEST = DEPLOY_DIR / ".secrets-manifest.json"


def find_az() -> str | None:
    for c in ("az", "az.cmd"):
        if shutil.which(c):
            return shutil.which(c)
    return None


def run_az(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    exe = find_az()
    if not exe:
        raise RuntimeError("az CLI not found. Install the Azure CLI or fix PATH.")
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          check=check, encoding="utf-8", errors="replace")


def check_prereqs(cfg: vc.DeployConfig) -> list[str]:
    problems: list[str] = []
    if not find_az():
        return ["az CLI not found on PATH (install the Azure CLI)"]
    proc = run_az(["account", "show", "--output", "json"])
    if proc.returncode != 0:
        return ["az not logged in (run `az login`)"]
    try:
        sub = json.loads(proc.stdout).get("id", "")
    except json.JSONDecodeError:
        sub = ""
    want = cfg.azure.subscription_id
    if want and sub and want != sub:
        problems.append(
            f"active subscription {sub} != config azure.subscription_id {want}")
    if not cfg.azure.subscription_id:
        problems.append("azure.subscription_id is empty (required)")
    if not cfg.azure.acr_registry:
        problems.append("azure.acr_registry is empty (required to address images)")
    return problems


def acr_image(cfg: vc.DeployConfig, component: str) -> str:
    return (f"{cfg.azure.acr_registry}.azurecr.io/"
            f"facil-{component}:{cfg.meta.version}")


def build_plan(cfg: vc.DeployConfig, manifest: dict) -> list[str]:
    z = cfg.azure
    rg = ["--resource-group", z.resource_group]
    plan: list[str] = []
    # 1. ACR (idempotent).
    plan.append(
        f"az acr show --name {z.acr_registry} {' '.join(rg)} "
        f"|| az acr create --name {z.acr_registry} --sku Basic {' '.join(rg)}")
    # 2. Container Apps environment.
    plan.append(
        f"az containerapp env show --name {z.containerapp_env} {' '.join(rg)} "
        f"|| az containerapp env create --name {z.containerapp_env} "
        f"--location {z.location} {' '.join(rg)}")
    # 3. Key Vault cross-check for each referenced secret.
    if z.keyvault_name:
        for name in sorted(manifest):
            plan.append(
                f"az keyvault secret show --vault-name {z.keyvault_name} "
                f"--name {name}  # must exist (set out of band)")
    # 4. Container Apps (backend + frontend).
    for comp, app in (("backend", z.backend_app_name), ("frontend", z.frontend_app_name)):
        plan.append(
            f"az containerapp create --name {app} --environment {z.containerapp_env} "
            f"--image {acr_image(cfg, comp)} {' '.join(rg)}  "
            f"# (az containerapp update if it already exists)")
    return plan


def _load(config: Path) -> vc.DeployConfig:
    return vc.DeployConfig.model_validate(vc.load_yaml(config))


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true")
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm the EXPERIMENTAL apply non-interactively.")
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 3
    try:
        cfg = _load(args.config)
    except Exception as e:
        print(f"ERROR: config invalid:\n{e}", file=sys.stderr)
        return 1
    manifest = _load_manifest(args.manifest)

    if args.validate:
        problems = check_prereqs(cfg)
        if problems:
            for p in problems:
                print(f"[FAIL] {p}", file=sys.stderr)
            return 1
        print("[OK] Azure prereqs validated (CLI, login, subscription).")
        return 0

    if args.plan:
        print(f"=== Azure plan (rg={cfg.azure.resource_group}, "
              f"location={cfg.azure.location}) ===")
        for cmd in build_plan(cfg, manifest):
            print(f"  {cmd}")
        return 0

    # --apply
    print("=" * 70)
    print("[EXPERIMENTAL] Azure apply is authored from spec and NOT yet validated")
    print("against a live Azure subscription. Review the plan before proceeding.")
    print("=" * 70)
    for cmd in build_plan(cfg, manifest):
        print(f"  {cmd}")
    if not args.yes:
        ans = input("\nExecute these against your subscription? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Aborted.")
            return 4
    print("\n[INFO] Live Azure execution is intentionally left to the operator with a "
          "validated subscription — run the commands above (or wire CI). See "
          "docs DEPLOYMENT_WIZARD.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
