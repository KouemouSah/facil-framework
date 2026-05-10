#!/usr/bin/env python3
"""End-to-end deploy orchestrator — Phase A.5.4 of DEPLOY_SYSTEM_PLAN.

Chains the per-step scripts of the deploy pipeline:

    1. validate_config.py  — schema check on deploy/config.yaml
    2. render_env.py       — render .env.deploy.gen + secrets manifest
    3. providers/<provider>.py --validate  — prereqs + secrets cross-check
    4. providers/<provider>.py --plan      — show planned commands
    5. (--apply only) providers/<provider>.py --apply  — execute deploy

Usage
-----
    # Validate everything end-to-end without touching cloud resources.
    python deploy/deploy.py --provider=gcp --action=validate

    # Show the deploy plan (read-only).
    python deploy/deploy.py --provider=gcp --action=plan

    # Run the real deploy (interactive confirmation prompts).
    python deploy/deploy.py --provider=gcp --action=apply

Exit codes
----------
0  All requested actions succeeded.
1  Validation/render error.
2  Provider step failed.
3  Config or template file not found.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
PROVIDERS_DIR = DEPLOY_DIR / "providers"
DEFAULT_CONFIG = DEPLOY_DIR / "config.yaml"
PYTHON = sys.executable

SUPPORTED_PROVIDERS = ["gcp", "docker-local"]
SUPPORTED_ACTIONS = ["validate", "plan", "apply"]


def run_step(name: str, cmd: list[str], *, capture: bool = False) -> int:
    """Run a sub-step and return its exit code. Prints a clear header."""
    print(f"\n{'=' * 70}")
    print(f"==  {name}")
    print(f"{'=' * 70}")
    proc = subprocess.run(
        cmd,
        text=True,
        capture_output=capture,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if capture and proc.stdout:
        print(proc.stdout)
    if capture and proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="Path to config.yaml (default: deploy/config.yaml).")
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, required=True)
    parser.add_argument("--action", choices=SUPPORTED_ACTIONS, required=True,
                        help="validate=read-only, plan=show commands, apply=execute.")
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"ERROR: config file not found: {args.config}", file=sys.stderr)
        print(f"       Copy {DEPLOY_DIR / 'config.example.yaml'} to {args.config} "
              f"and fill it in.", file=sys.stderr)
        return 3

    provider_script = PROVIDERS_DIR / f"{args.provider.replace('-', '_')}.py"
    if not provider_script.exists():
        print(f"ERROR: provider script not found: {provider_script}", file=sys.stderr)
        print(f"       Provider '{args.provider}' is not implemented yet.",
              file=sys.stderr)
        return 3

    # 1. validate_config.py
    rc = run_step(
        "Step 1/4 — Schema validation",
        [PYTHON, str(SCRIPTS_DIR / "validate_config.py"),
         str(args.config), f"--provider={args.provider}"],
    )
    if rc != 0:
        print(f"\nERROR: schema validation failed (exit {rc})", file=sys.stderr)
        return 1

    # 2. render_env.py
    rc = run_step(
        "Step 2/4 — Render env templates + secrets manifest",
        [PYTHON, str(SCRIPTS_DIR / "render_env.py"),
         f"--config={args.config}", "--target=both"],
    )
    if rc != 0:
        print(f"\nERROR: render_env failed (exit {rc})", file=sys.stderr)
        return 1

    # 3. Provider --validate
    rc = run_step(
        f"Step 3/4 — {args.provider} prereqs + secrets cross-check",
        [PYTHON, str(provider_script),
         f"--config={args.config}", "--validate"],
    )
    if rc != 0:
        print(f"\nERROR: provider validate failed (exit {rc})", file=sys.stderr)
        return 2

    if args.action == "validate":
        print("\n[OK] All validation steps passed. Use --action=plan to see "
              "the deploy plan.")
        return 0

    # 4. Provider --plan or --apply
    provider_action = "--plan" if args.action == "plan" else "--apply"
    rc = run_step(
        f"Step 4/4 — {args.provider} {provider_action}",
        [PYTHON, str(provider_script),
         f"--config={args.config}", provider_action],
    )
    if rc != 0:
        print(f"\nERROR: provider {provider_action} failed (exit {rc})",
              file=sys.stderr)
        return 2

    print("\n[OK] Deploy pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
