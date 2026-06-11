#!/usr/bin/env python3
"""Data-plane bootstrap — idempotent, deployment-mode-aware provisioning.

Turns "containers up" into "data-plane usable": after the provider brings the
stack up, this layer creates the MinIO bucket + scoped service account, the
OpenBao kv mount + policy + AppRole, and the Postgres infra extensions — every
time, idempotently. It consumes the seam already present in the config
(``storage.provider`` / ``secrets.provider`` / ``database_mode``) so the SAME
code path serves on-prem, cloud and SaaS; only the config picks what runs.

Run standalone via the flat launcher added in Phase B5 (mirrors the
``docker_local.py`` script convention):

    python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --plan
    python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --apply
    python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --apply --only=minio

It is also called automatically by ``docker_local.py --apply`` after the stack
is healthy (wired in Phase B5).

Exit codes
----------
0  All applicable provisioners succeeded (or correctly skipped).
1  Config not found / invalid.
2  A provisioner failed (or the health-wait timed out).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from types import ModuleType

_THIS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _THIS_DIR.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import validate_config as vc  # noqa: E402

from . import minio, openbao, postgres  # noqa: E402
from .context import BootstrapContext  # noqa: E402
from .docker_helpers import (  # noqa: E402
    ContainerInfo,
    DockerError,
    wait_for_healthy,
)
from .state import BootstrapState  # noqa: E402

# Ordered registry. Order matters: openbao before minio so the MinIO service
# account can later be stored into OpenBao kv in the same run.
PROVISIONERS: list[ModuleType] = [openbao, minio, postgres]

# Provisioner NAME -> compose service whose health gates it.
SERVICE_FOR = {"openbao": "openbao", "minio": "minio", "postgres": "postgres"}

DEFAULT_NETWORK = "facil_framework_default"


# ---------------------------------------------------------------------------
# Dispatch (pure — no docker, unit-testable)
# ---------------------------------------------------------------------------

def select_provisioners(
    cfg: vc.DeployConfig, *, only: set[str] | None = None
) -> list[ModuleType]:
    """Return the provisioners applicable to this config, in run order.

    ``only`` (a set of NAMEs) further restricts the selection — used by
    ``--only=minio`` to re-run a single provisioner.
    """
    chosen = [p for p in PROVISIONERS if p.is_applicable(cfg)]
    if only is not None:
        chosen = [p for p in chosen if p.NAME in only]
    return chosen


def _resolve_network(containers: dict[str, ContainerInfo]) -> str:
    """Pick the docker network one-shot tool containers should attach to.

    Uses the network of any resolved stack container so ``minio:9000`` /
    ``openbao:8200`` resolve by service DNS. Falls back to the conventional
    default project network when nothing is resolved (e.g. dry-run with no
    live stack).
    """
    for info in containers.values():
        if info.network:
            return info.network
    return DEFAULT_NETWORK


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_bootstrap(
    cfg: vc.DeployConfig,
    *,
    dry_run: bool = False,
    only: set[str] | None = None,
    wait_timeout: int = 120,
    repo_root: Path | None = None,
    log=print,
    sleep=time.sleep,
    _wait=wait_for_healthy,
) -> BootstrapState:
    """Resolve services, gate on health, run each applicable provisioner.

    ``_wait`` is injectable so tests drive the orchestrator without a live
    stack. Provisioner failures are captured as failed steps (not exceptions)
    so one failing provisioner never aborts the others; the aggregate
    ``state.succeeded`` reflects the run.
    """
    selected = select_provisioners(cfg, only=only)
    state = BootstrapState(
        project=cfg.meta.project_name,
        storage_provider=cfg.storage.provider,
        secrets_provider=cfg.secrets.provider,
        database_mode=cfg.docker_local.database_mode,
    )

    if not selected:
        log("[bootstrap] no applicable provisioners for this config — nothing to do.")
        return state

    services = [SERVICE_FOR[p.NAME] for p in selected]
    containers: dict[str, ContainerInfo] = {}
    if not dry_run:
        log(f"[bootstrap] waiting for healthy: {', '.join(services)}")
        containers = _wait(services, timeout=wait_timeout, sleep=sleep)

    ctx_kwargs = dict(
        cfg=cfg,
        network=_resolve_network(containers),
        containers=containers,
        dry_run=dry_run,
        log=log,
    )
    if repo_root is not None:
        ctx_kwargs["repo_root"] = repo_root
    ctx = BootstrapContext(**ctx_kwargs)

    for p in selected:
        try:
            step = p.provision(ctx)
        except Exception as exc:  # provisioner crash → failed step, keep going
            from .state import ProvisionStep
            step = ProvisionStep(name=p.NAME).fail(f"unexpected error: {exc}")
        state.steps.append(step)

    if dry_run:
        log("[bootstrap] dry-run — state not written.")
    else:
        state.save(ctx.state_file)
        log(f"[bootstrap] state written → {ctx.state_file}")
    return state


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_config(path: Path) -> vc.DeployConfig:
    raw = vc.load_yaml(path)
    return vc.DeployConfig.model_validate(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path,
                        default=_THIS_DIR.parent.parent / "config.yaml")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true",
                      help="Show what would be provisioned (no mutation).")
    mode.add_argument("--apply", action="store_true",
                      help="Provision against the running stack.")
    parser.add_argument("--only", default=None,
                        help="Comma-separated provisioner names to restrict to "
                             "(e.g. --only=minio,openbao).")
    parser.add_argument("--wait-timeout", type=int, default=120)
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 1
    try:
        cfg = _load_config(args.config)
    except Exception as e:
        print(f"ERROR: config validation failed:\n{e}", file=sys.stderr)
        return 1

    only = {s.strip() for s in args.only.split(",")} if args.only else None

    if args.plan:
        selected = select_provisioners(cfg, only=only)
        print("=== bootstrap plan ===")
        print(f"storage={cfg.storage.provider} secrets={cfg.secrets.provider} "
              f"db_mode={cfg.docker_local.database_mode}")
        if not selected:
            print("  (no applicable provisioners)")
        for p in selected:
            print(f"  - {p.NAME}: {p.__doc__.splitlines()[0] if p.__doc__ else ''}")
        return 0

    try:
        state = run_bootstrap(cfg, only=only, wait_timeout=args.wait_timeout)
    except DockerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print("\n" + state.redacted_summary())
    return 0 if state.succeeded else 2


if __name__ == "__main__":
    sys.exit(main())
