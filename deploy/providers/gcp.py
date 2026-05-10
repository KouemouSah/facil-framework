#!/usr/bin/env python3
"""GCP provider — Phase A.5.3 of DEPLOY_SYSTEM_PLAN.

Drives a Cloud Run deployment of Facil from a validated config.yaml +
secrets manifest:

    1. Validate prerequisites (gcloud installed, ADC configured, project
       accessible, required APIs enabled).
    2. Cross-check the secrets manifest against `gcloud secrets list`.
       Report missing secrets (BLOCKER) and orphan secrets (info).
    3. Build the gcloud commands needed to deploy backend + frontend.
    4. Execute them (or print them in --plan mode).

Usage
-----
    # Just sanity-check prereqs and config alignment.
    python deploy/providers/gcp.py --config=deploy/config.yaml --validate

    # Show the gcloud commands without executing.
    python deploy/providers/gcp.py --config=deploy/config.yaml --plan

    # Run for real (interactive confirmations on destructive steps).
    python deploy/providers/gcp.py --config=deploy/config.yaml --apply

Exit codes
----------
0  All requested actions succeeded.
1  Validation error (prereqs missing, secrets mismatch, etc.).
2  Subprocess error (gcloud failed).
3  YAML / file error.
4  User aborted at a confirmation prompt.

Design notes
------------
- Pure Python, stdlib + pydantic + yaml. No bash.
- Subprocess calls are ALWAYS `gcloud ...` invoked through subprocess.run
  with check=False — this module reads the result and decides what to do.
- Destructive operations (deploy, secret create) require either --apply
  AND a confirmation prompt, OR --plan (in which case nothing runs).
- The script is idempotent in --apply mode: re-running on an already-deployed
  setup yields a no-op deploy.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Reuse validate_config + render_env from sibling deploy/scripts/.
PROVIDERS_DIR = Path(__file__).resolve().parent
DEPLOY_DIR = PROVIDERS_DIR.parent
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import render_env as re_mod  # noqa: E402
import validate_config as vc  # noqa: E402

DEFAULT_CONFIG = DEPLOY_DIR / "config.yaml"
DEFAULT_MANIFEST = DEPLOY_DIR / ".secrets-manifest.json"


# ---------------------------------------------------------------------------
# gcloud invocation helpers
# ---------------------------------------------------------------------------

def find_gcloud() -> str | None:
    """Return the gcloud executable path or None if not installed.

    On Windows, the Cloud SDK installer drops gcloud.cmd; on POSIX, just gcloud.
    """
    for candidate in ("gcloud", "gcloud.cmd"):
        path = shutil.which(candidate)
        if path:
            return path
    # Common Windows install path fallback.
    win_path = Path(r"C:/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd")
    if win_path.exists():
        return str(win_path)
    return None


def run_gcloud(args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    """Invoke gcloud with `args`. Raises RuntimeError if gcloud not on PATH."""
    exe = find_gcloud()
    if not exe:
        raise RuntimeError(
            "gcloud not found. Install Google Cloud SDK or fix PATH. "
            "https://cloud.google.com/sdk/docs/install"
        )
    cmd = [exe, *args]
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------
# Prereq + status checks
# ---------------------------------------------------------------------------

@dataclass
class PrereqResult:
    gcloud_present: bool = False
    gcloud_version: str = ""
    adc_configured: bool = False
    active_project: str = ""
    project_accessible: bool = False
    apis_required: list[str] = field(default_factory=list)
    apis_enabled: list[str] = field(default_factory=list)
    apis_missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.gcloud_present
            and self.adc_configured
            and self.project_accessible
            and not self.apis_missing
        )


REQUIRED_APIS: list[str] = [
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "containerregistry.googleapis.com",
]


def check_prereqs(project_id: str) -> PrereqResult:
    """Run a battery of read-only gcloud checks. Never modifies anything."""
    result = PrereqResult(apis_required=list(REQUIRED_APIS))

    exe = find_gcloud()
    if not exe:
        return result
    result.gcloud_present = True

    # gcloud --version
    proc = run_gcloud(["--version"])
    if proc.returncode == 0 and proc.stdout:
        result.gcloud_version = proc.stdout.splitlines()[0].strip()

    # ADC: try to print an access token (cheap proxy).
    proc = run_gcloud(["auth", "application-default", "print-access-token"])
    result.adc_configured = proc.returncode == 0

    # Active project
    proc = run_gcloud(["config", "get-value", "project"])
    if proc.returncode == 0:
        result.active_project = (proc.stdout or "").strip()

    # Project accessibility
    proc = run_gcloud(["projects", "describe", project_id, "--format=value(projectId)"])
    result.project_accessible = (
        proc.returncode == 0 and project_id in (proc.stdout or "")
    )

    # Required APIs
    proc = run_gcloud([
        "services", "list", "--enabled",
        f"--project={project_id}",
        "--format=value(config.name)",
    ])
    if proc.returncode == 0:
        result.apis_enabled = sorted(
            line.strip() for line in (proc.stdout or "").splitlines() if line.strip()
        )
        result.apis_missing = [
            api for api in REQUIRED_APIS if api not in result.apis_enabled
        ]
    else:
        # Could not list APIs — assume all missing.
        result.apis_missing = list(REQUIRED_APIS)

    return result


# ---------------------------------------------------------------------------
# Secret manifest cross-check
# ---------------------------------------------------------------------------

@dataclass
class SecretsCheckResult:
    expected: dict[str, str] = field(default_factory=dict)  # ENV_VAR -> secret_name
    present_in_gcp: set[str] = field(default_factory=set)
    missing_in_gcp: list[str] = field(default_factory=list)  # secret names from manifest
    orphans_in_gcp: list[str] = field(default_factory=list)  # secrets in GCP not in manifest

    @property
    def ok(self) -> bool:
        return not self.missing_in_gcp


def list_gcp_secrets(project_id: str) -> set[str]:
    proc = run_gcloud([
        "secrets", "list",
        f"--project={project_id}",
        "--format=value(name)",
    ])
    if proc.returncode != 0:
        return set()
    return {
        line.strip()
        for line in (proc.stdout or "").splitlines()
        if line.strip()
    }


def cross_check_secrets(
    manifest_path: Path,
    project_id: str,
) -> SecretsCheckResult:
    """Compare the secrets manifest with `gcloud secrets list`."""
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest not found: {manifest_path}. "
            f"Run `python deploy/scripts/render_env.py --target=both` first."
        )
    manifest: dict[str, str] = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_names = set(manifest.values())
    present = list_gcp_secrets(project_id)
    return SecretsCheckResult(
        expected=manifest,
        present_in_gcp=present,
        missing_in_gcp=sorted(expected_names - present),
        orphans_in_gcp=sorted(present - expected_names),
    )


# ---------------------------------------------------------------------------
# Deploy command planning
# ---------------------------------------------------------------------------

def build_set_secrets_arg(manifest: dict[str, str]) -> str:
    """Render the --set-secrets payload Cloud Run expects.

    Format: ENV_VAR=secret_name:latest,ENV_VAR2=secret_name2:latest
    """
    return ",".join(
        f"{env_var}={secret_name}:latest"
        for env_var, secret_name in sorted(manifest.items())
    )


def plan_backend_deploy(cfg: vc.DeployConfig, manifest: dict[str, str]) -> list[str]:
    """Return the gcloud command (as a list) that would deploy the backend."""
    return [
        "run", "deploy", cfg.gcp.backend_service_name,
        f"--project={cfg.gcp.project_id}",
        f"--region={cfg.gcp.region}",
        "--source=packages/backend",
        "--allow-unauthenticated",
        "--platform=managed",
        f"--port={cfg.server.port}",
        f"--set-env-vars=ENVIRONMENT={cfg.meta.environment}",
        f"--set-secrets={build_set_secrets_arg(manifest)}",
    ]


def plan_frontend_deploy(cfg: vc.DeployConfig) -> list[str]:
    """Return the gcloud command for the frontend (Next.js Cloud Run service)."""
    return [
        "run", "deploy", cfg.gcp.frontend_service_name,
        f"--project={cfg.gcp.project_id}",
        f"--region={cfg.gcp.region}",
        "--source=packages/web",
        "--allow-unauthenticated",
        "--platform=managed",
        f"--set-env-vars=NEXT_PUBLIC_API_URL={cfg.server.api_base_url}",
        f"--set-env-vars=NEXT_PUBLIC_SITE_URL={cfg.server.frontend_url}",
        f"--set-env-vars=NEXT_PUBLIC_ENVIRONMENT={cfg.meta.environment}",
    ]


# ---------------------------------------------------------------------------
# Pretty-printing helpers
# ---------------------------------------------------------------------------

def fmt_check(ok: bool) -> str:
    return "[OK]" if ok else "[FAIL]"


def print_prereqs(p: PrereqResult, project_id: str) -> None:
    print(f"{fmt_check(p.gcloud_present)} gcloud installed: {p.gcloud_version or 'n/a'}")
    print(f"{fmt_check(p.adc_configured)} Application Default Credentials")
    print(f"{fmt_check(p.project_accessible)} Project '{project_id}' accessible "
          f"(current: '{p.active_project}')")
    if p.apis_missing:
        print(f"[FAIL] Required APIs missing: {', '.join(p.apis_missing)}")
    else:
        print(f"[OK] All required APIs enabled "
              f"({len(p.apis_enabled)} total enabled)")


def print_secrets_check(s: SecretsCheckResult) -> None:
    print(f"Manifest: {len(s.expected)} expected secrets, "
          f"{len(s.present_in_gcp)} found in GCP")
    if s.missing_in_gcp:
        print(f"[FAIL] {len(s.missing_in_gcp)} secret(s) MISSING in GCP:")
        for name in s.missing_in_gcp:
            env_vars = [k for k, v in s.expected.items() if v == name]
            print(f"        - {name} (binds to: {', '.join(env_vars)})")
    else:
        print("[OK] All manifest secrets exist in GCP")
    if s.orphans_in_gcp:
        print(f"[INFO] {len(s.orphans_in_gcp)} secret(s) in GCP not referenced by "
              f"this deploy: {', '.join(s.orphans_in_gcp[:10])}"
              f"{'...' if len(s.orphans_in_gcp) > 10 else ''}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true",
                      help="Run prereq + secret cross-check only. No commands executed.")
    mode.add_argument("--plan", action="store_true",
                      help="Print the gcloud commands that would be run. No execution.")
    mode.add_argument("--apply", action="store_true",
                      help="Run the deploy. Prompts before each destructive step.")
    args = parser.parse_args(argv)

    # 1. Load + validate config
    raw = vc.load_yaml(args.config)
    try:
        cfg = vc.DeployConfig.model_validate(raw)
    except Exception as e:
        print(f"ERROR: config validation failed:\n{e}", file=sys.stderr)
        return 1

    if not cfg.gcp.project_id:
        print("ERROR: gcp.project_id is empty. Set it in deploy/config.yaml.",
              file=sys.stderr)
        return 1

    # 2. Prereqs
    print(f"=== Prerequisites for project '{cfg.gcp.project_id}' ===")
    prereqs = check_prereqs(cfg.gcp.project_id)
    print_prereqs(prereqs, cfg.gcp.project_id)
    if not prereqs.ok and not args.plan:
        print("\nFix the above before proceeding.", file=sys.stderr)
        return 1

    # 3. Secrets cross-check
    print(f"\n=== Secrets cross-check ===")
    try:
        secrets = cross_check_secrets(args.manifest, cfg.gcp.project_id)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    print_secrets_check(secrets)
    if not secrets.ok and not args.plan:
        print("\nMissing secrets must be created in GCP Secret Manager first.",
              file=sys.stderr)
        return 1

    if args.validate:
        print("\n[OK] Validation passed. Use --plan to see deploy commands.")
        return 0

    # 4. Plan deploy commands
    print("\n=== Planned deploy commands ===")
    backend_cmd = plan_backend_deploy(cfg, secrets.expected)
    frontend_cmd = plan_frontend_deploy(cfg)
    print("\n# Backend (Cloud Run service):")
    print("gcloud " + " ".join(backend_cmd))
    print("\n# Frontend (Cloud Run service):")
    print("gcloud " + " ".join(frontend_cmd))

    if args.plan:
        print("\n[OK] Plan complete. Re-run with --apply to execute.")
        return 0

    # 5. Apply
    confirm = input("\nProceed with deploy? Type 'yes' to confirm: ").strip()
    if confirm.lower() != "yes":
        print("Aborted by user.", file=sys.stderr)
        return 4

    print("\n=== Deploying backend ===")
    proc = run_gcloud(backend_cmd, capture=False)
    if proc.returncode != 0:
        print(f"ERROR: backend deploy failed (exit {proc.returncode})", file=sys.stderr)
        return 2

    print("\n=== Deploying frontend ===")
    proc = run_gcloud(frontend_cmd, capture=False)
    if proc.returncode != 0:
        print(f"ERROR: frontend deploy failed (exit {proc.returncode})", file=sys.stderr)
        return 2

    print("\n[OK] Deploy complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
