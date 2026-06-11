#!/usr/bin/env python3
"""Postgres provisioner — ensure infra-level extensions.

Scope (decision D2): the bootstrap owns *infra capabilities* the application
assumes — the pgvector / pg_trgm / uuid-ossp extensions — NOT the application
schema (tables stay the property of db-init / migrations, Phase D). Running
``CREATE EXTENSION IF NOT EXISTS`` here is idempotent and lets db-init later
re-affirm the same extensions without conflict, while making the DB RAG-ready
immediately.

Only applies in ``database_mode == "local"`` (we own the container). In
``external`` / managed-cloud mode the extension lifecycle belongs to the managed
provider + db-init, so this provisioner skips and says so.
"""

from __future__ import annotations

from .context import BootstrapContext, vc
from .state import ProvisionStep

NAME = "postgres"

# Infra-level extensions assumed by the platform. pgvector is mandatory for RAG
# (vector columns); pg_trgm powers fuzzy search; uuid-ossp for uuid defaults.
EXTENSIONS = ("vector", "pg_trgm", "uuid-ossp")


def is_applicable(cfg: vc.DeployConfig) -> bool:
    return cfg.docker_local.database_mode == "local"


def provision(ctx: BootstrapContext) -> ProvisionStep:  # pragma: no cover - B4
    """Implemented in Phase B4. B1 ships the stub so dispatch is wired."""
    return ProvisionStep(name=NAME, detail="postgres provisioner pending (B4)")
