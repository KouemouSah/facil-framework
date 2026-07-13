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

SUPPORTED_PROVIDERS = ["gcp", "aws", "azure", "docker-local", "k3s"]
SUPPORTED_ACTIONS = ["validate", "plan", "apply"]


def run_step(name: str, cmd: list[str], *, capture: bool = False) -> int:
    """Run a sub-step and return its exit code. Prints a clear header.

    Everything this orchestrator prints about ITSELF (headers, and — when
    `capture=True` — the sub-step's own stdout/stderr) goes to **stderr**,
    never real stdout. Real stdout must stay pure for `--action=plan`/`apply`:
    it is meant to be piped straight into
    `infra/helm/facil/tests/guard_secrets.py` (see task-V1 brief). Found by
    running that exact pipe for real: the old code printed step banners AND
    steps 1-3's own "[OK] Config valid..." chatter to stdout, which
    `yaml.safe_load_all` then choked on before ever reaching the actual `helm
    template` render — a bug `helm lint`/`template`/pytest alone could never
    catch (nothing exercises the orchestrator's stdout contract).
    """
    print(f"\n{'=' * 70}", file=sys.stderr)
    print(f"==  {name}", file=sys.stderr)
    print(f"{'=' * 70}", file=sys.stderr)
    proc = subprocess.run(
        cmd,
        text=True,
        capture_output=capture,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if capture and proc.stdout:
        print(proc.stdout, file=sys.stderr)
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
    # capture=True on steps 1-3: their own stdout is prose ("[OK] Config
    # valid..."), never the payload — must not leak onto real stdout ahead of
    # step 4's `helm template`/`helm upgrade` output (see run_step docstring).
    rc = run_step(
        "Step 1/4 — Schema validation",
        [PYTHON, str(SCRIPTS_DIR / "validate_config.py"),
         str(args.config), f"--provider={args.provider}"],
        capture=True,
    )
    if rc != 0:
        print(f"\nERROR: schema validation failed (exit {rc})", file=sys.stderr)
        return 1

    # 2. render_env.py
    rc = run_step(
        "Step 2/4 — Render env templates + secrets manifest",
        [PYTHON, str(SCRIPTS_DIR / "render_env.py"),
         f"--config={args.config}", "--target=both"],
        capture=True,
    )
    if rc != 0:
        print(f"\nERROR: render_env failed (exit {rc})", file=sys.stderr)
        return 1

    # 3. Provider --validate
    rc = run_step(
        f"Step 3/4 — {args.provider} prereqs + secrets cross-check",
        [PYTHON, str(provider_script),
         f"--config={args.config}", "--validate"],
        capture=True,
    )
    if rc != 0:
        print(f"\nERROR: provider validate failed (exit {rc})", file=sys.stderr)
        return 2

    if args.action == "validate":
        print("\n[OK] All validation steps passed. Use --action=plan to see "
              "the deploy plan.", file=sys.stderr)
        return 0

    # 4. Provider --plan or --apply — capture=False (default): this step's
    # stdout IS the payload (helm template render for `plan`; helm
    # upgrade/kubectl output for `apply`), streamed live to real stdout so it
    # can be piped (e.g. into guard_secrets.py) or watched interactively.
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

    print("\n[OK] Deploy pipeline complete.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
