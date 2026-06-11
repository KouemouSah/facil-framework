#!/usr/bin/env python3
"""AWS provider — App Runner (serverless containers, the Cloud Run analog).

Drives an App Runner deployment of Facil from a validated config.yaml:

    1. --validate : check prereqs (aws CLI, caller identity, account match). RO.
    2. --plan     : print the aws commands (ECR ensure, Secrets Manager
                    cross-check, App Runner create/update) WITHOUT executing.
    3. --apply    : execute them. EXPERIMENTAL — authored from spec, NOT yet
                    validated against a live AWS account; requires confirmation.

Mirrors providers/gcp.py (same CLI shape + exit codes). Images are expected to be
built+pushed by CI (no manual cloud build) into ECR
(<account>.dkr.ecr.<region>.amazonaws.com/<repo>) — this module only deploys.

Exit codes
----------
0 success · 1 validation error · 2 aws CLI error · 3 file error · 4 aborted.
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


# ---------------------------------------------------------------------------
# aws CLI
# ---------------------------------------------------------------------------

def find_aws() -> str | None:
    for c in ("aws", "aws.cmd", "aws.exe"):
        if shutil.which(c):
            return shutil.which(c)
    return None


def run_aws(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    exe = find_aws()
    if not exe:
        raise RuntimeError("aws CLI not found. Install the AWS CLI v2 or fix PATH.")
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          check=check, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Prereqs (read-only)
# ---------------------------------------------------------------------------

def check_prereqs(cfg: vc.DeployConfig) -> list[str]:
    """Return a list of problems (empty = OK). Never mutates anything."""
    problems: list[str] = []
    if not find_aws():
        return ["aws CLI not found on PATH (install AWS CLI v2)"]
    proc = run_aws(["sts", "get-caller-identity", "--output", "json"])
    if proc.returncode != 0:
        problems.append("aws not authenticated (run `aws configure` / SSO login)")
        return problems
    try:
        ident = json.loads(proc.stdout)
        account = ident.get("Account", "")
    except json.JSONDecodeError:
        account = ""
    want = cfg.aws.account_id
    if want and account and want != account:
        problems.append(
            f"authenticated account {account} != config aws.account_id {want}")
    if not cfg.aws.account_id:
        problems.append("aws.account_id is empty (required to address ECR/App Runner)")
    return problems


# ---------------------------------------------------------------------------
# Plan (command strings — real aws invocations, not executed in --plan)
# ---------------------------------------------------------------------------

def ecr_image_uri(cfg: vc.DeployConfig, component: str) -> str:
    a, r = cfg.aws.account_id or "<account>", cfg.aws.region
    return (f"{a}.dkr.ecr.{r}.amazonaws.com/"
            f"{cfg.aws.ecr_repository}-{component}:{cfg.meta.version}")


def build_plan(cfg: vc.DeployConfig, manifest: dict) -> list[str]:
    a = cfg.aws
    region = ["--region", a.region]
    plan: list[str] = []
    # 1. ECR repositories (idempotent: create only if absent).
    for comp in ("backend", "frontend"):
        repo = f"{a.ecr_repository}-{comp}"
        plan.append(
            f"aws ecr describe-repositories --repository-names {repo} {' '.join(region)} "
            f"|| aws ecr create-repository --repository-name {repo} {' '.join(region)}")
    # 2. Secrets Manager: ensure each referenced secret exists under the prefix.
    for name in sorted(manifest):
        plan.append(
            f"aws secretsmanager describe-secret --secret-id {a.secrets_manager_prefix}{name} "
            f"{' '.join(region)}  # must exist (create/put-secret-value out of band)")
    # 3. Compute: App Runner (default) or ECS Fargate.
    if a.runtime == "app_runner":
        for comp in ("backend", "frontend"):
            plan.append(
                f"aws apprunner create-service --service-name {a.ecr_repository}-{comp} "
                f"--source-configuration ImageRepository={{ImageIdentifier={ecr_image_uri(cfg, comp)},"
                f"ImageRepositoryType=ECR}} {' '.join(region)}  "
                f"# (update-service if it already exists)")
    else:  # ecs_fargate
        plan.append(
            f"aws ecs register-task-definition ... && aws ecs update-service "
            f"--cluster {a.backend_cluster} --service {a.backend_service_name} "
            f"--force-new-deployment {' '.join(region)}")
    return plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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
        print("[OK] AWS prereqs validated (CLI, identity, account).")
        return 0

    if args.plan:
        print(f"=== AWS plan (runtime={cfg.aws.runtime}, region={cfg.aws.region}) ===")
        for cmd in build_plan(cfg, manifest):
            print(f"  {cmd}")
        return 0

    # --apply
    print("=" * 70)
    print("[EXPERIMENTAL] AWS apply is authored from spec and NOT yet validated")
    print("against a live AWS account. Review the plan before proceeding.")
    print("=" * 70)
    for cmd in build_plan(cfg, manifest):
        print(f"  {cmd}")
    if not args.yes:
        ans = input("\nExecute these against your AWS account? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Aborted.")
            return 4
    print("\n[INFO] Live AWS execution is intentionally left to the operator with a "
          "validated account — run the commands above (or wire CI). See "
          "docs DEPLOYMENT_WIZARD.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
