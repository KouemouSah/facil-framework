#!/usr/bin/env python3
"""Postgres provisioner — ensure infra-level extensions.

Scope (decision D2): the bootstrap owns *infra capabilities* the application
assumes — the pgvector / pg_trgm / uuid-ossp extensions — NOT the application
schema (tables stay the property of db-init / migrations, Phase D). Running
``CREATE EXTENSION IF NOT EXISTS`` here is idempotent and lets db-init later
re-affirm the same extensions without conflict, while making the DB RAG-ready
immediately.

Only applies in ``database_mode == "local"`` (we own the container, so we drive
``psql`` via ``docker exec``). In ``external`` / managed-cloud mode the extension
lifecycle belongs to the managed provider + db-init, so this provisioner skips.
"""

from __future__ import annotations

from .context import BootstrapContext, vc
from .docker_helpers import DockerError, exec_in
from .state import ProvisionStep

NAME = "postgres"

# Infra-level extensions assumed by the platform. pgvector is mandatory for RAG
# (vector columns); pg_trgm powers fuzzy search; uuid-ossp for uuid defaults.
EXTENSIONS = ("vector", "pg_trgm", "uuid-ossp")


def is_applicable(cfg: vc.DeployConfig) -> bool:
    return cfg.docker_local.database_mode == "local"


def _psql(container, user, db, sql, *, check=True):
    """Run a single SQL statement via ``docker exec ... psql`` (no shell).

    ``-tAc`` = tuples-only, unaligned, single command; ``ON_ERROR_STOP=1`` makes
    psql exit non-zero on SQL errors so ``exec_in`` surfaces them.
    """
    return exec_in(
        container,
        ["psql", "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1", "-tAc", sql],
        check=check,
    )


def _existing_extensions(container, user, db) -> set[str]:
    out = _psql(container, user, db, "SELECT extname FROM pg_extension").stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def provision(ctx: BootstrapContext) -> ProvisionStep:
    cfg = ctx.cfg
    # docker_local generates the container with POSTGRES_USER/DB = project_name.
    user = db = cfg.meta.project_name
    step = ProvisionStep(name=NAME)

    if ctx.dry_run:
        step.actions = [f'CREATE EXTENSION IF NOT EXISTS "{e}"' for e in EXTENSIONS]
        return step.skip("dry-run: would ensure Postgres extensions")

    info = ctx.containers.get("postgres")
    if info is None:
        return step.fail("postgres container not resolved (is the stack up?)")

    try:
        existing = _existing_extensions(info.name, user, db)
        for ext in EXTENSIONS:
            if ext in existing:
                step.actions.append(f"extension '{ext}' already present")
                continue
            _psql(info.name, user, db, f'CREATE EXTENSION IF NOT EXISTS "{ext}"')
            step.actions.append(f"extension '{ext}' created")
    except DockerError as exc:
        return step.fail(f"psql operation failed: {exc}")

    return step.ok(f"extensions ensured: {', '.join(EXTENSIONS)}")
