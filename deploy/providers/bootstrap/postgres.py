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

import secrets as _secrets

from .context import BootstrapContext, vc
from .docker_helpers import DockerError, exec_in
from .state import BootstrapState, ProvisionStep

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


# Least-privilege grants for the application role. The superuser (POSTGRES_USER)
# stays reserved for migrations / db-init; the backend connects as this role.
def _grants(role: str, db: str) -> list[str]:
    return [
        f"GRANT CONNECT ON DATABASE {db} TO {role}",
        f"GRANT USAGE ON SCHEMA public TO {role}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}",
        # Tables/sequences created LATER by db-init (running as superuser) are
        # auto-granted to the app role — covers Phase D schema without re-running.
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {role}",
    ]


def _ensure_app_role(ctx, container, user, db, step) -> tuple[str, str]:
    """Create / reuse the least-privilege app role. Returns (role, password).

    NB: the password travels in the psql ``-c`` argv of a transient
    ``docker exec`` (dev-acceptable; a managed/prod path would inject it via a
    secret mount). Generated once, reused from the bootstrap state on re-run.
    """
    role = f"{ctx.cfg.meta.project_name}_app"
    exists = _psql(container, user, db,
                   f"SELECT 1 FROM pg_roles WHERE rolname='{role}'").stdout.strip() == "1"

    prior_pw = ""
    prior = BootstrapState.load(ctx.state_file)
    if prior and (ps := prior.step(NAME)):
        prior_pw = ps.secrets.get("pg_app_password", "")

    if exists and prior_pw:
        pw = prior_pw
        step.actions.append(f"app role '{role}' present — password reused")
    else:
        pw = _secrets.token_urlsafe(24)
        if exists:
            _psql(container, user, db,
                  f"ALTER ROLE {role} WITH LOGIN PASSWORD '{pw}'")
            step.actions.append(f"app role '{role}' password rotated (unknown prior)")
        else:
            _psql(container, user, db,
                  f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB "
                  f"NOCREATEROLE PASSWORD '{pw}'")
            step.actions.append(f"app role '{role}' created (NOSUPERUSER, least-privilege)")

    for g in _grants(role, db):
        _psql(container, user, db, g)
    step.actions.append(f"least-privilege grants applied to '{role}' (incl. default privileges)")
    return role, pw


def provision(ctx: BootstrapContext) -> ProvisionStep:
    cfg = ctx.cfg
    # docker_local generates the container with POSTGRES_USER/DB = project_name.
    user = db = cfg.meta.project_name
    step = ProvisionStep(name=NAME)

    if ctx.dry_run:
        step.actions = [f'CREATE EXTENSION IF NOT EXISTS "{e}"' for e in EXTENSIONS]
        step.actions.append(
            f"CREATE ROLE {cfg.meta.project_name}_app (NOSUPERUSER) + least-privilege grants")
        return step.skip("dry-run: would ensure Postgres extensions + app role")

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
        role, pw = _ensure_app_role(ctx, info.name, user, db, step)
    except DockerError as exc:
        return step.fail(f"psql operation failed: {exc}")

    step.secrets = {
        "pg_app_role": role,
        "pg_app_password": pw,
        "pg_app_db": db,
        "pg_app_host": "postgres",
    }
    return step.ok(
        f"extensions ensured: {', '.join(EXTENSIONS)} ; least-privilege role '{role}'")
