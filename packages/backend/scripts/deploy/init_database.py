#!/usr/bin/env python3
"""
Database initialization orchestrator — Phase A of MIGRATIONS_BASELINE_REFACTOR_PLAN.

Applies SQL migrations from `database/migrations/` to a Postgres database with:
  - Tracking via `schema_migrations` table (created auto if absent)
  - SHA-256 checksum per file (warn on edits to applied migrations)
  - Postgres advisory lock (prevent concurrent applies in parallel deploys)
  - Multiple modes (hybrid, strict, legacy-compat) for safe rollout

Modes
-----
auto         Same as hybrid for now (Phase A). Will detect baseline vs
             migration application in a future Phase D (pg_dump baseline).
hybrid       Default. Uses schema_migrations if present (skip applied).
             Falls back to legacy "replay-all with already-exists skip"
             for entries that error on first apply (smooth rollout).
             For a FRESH DB this is the recommended mode: applies all
             319 migrations + 9 TIER_0 seeds in one shot.
strict       Errors out on any unexpected SQL exception. No legacy fallback.
             Use only after Phase G validation has confirmed all migrations
             apply cleanly on a fresh DB.
legacy-compat Replays every .sql, swallowing 'already exists'/'duplicate'
             errors. Equivalent to the inline Python in the legacy
             deploy-backend-staging.yml (rollback safety).
seeds-only    Apply only files in database/seeds/. Useful when reseeding
             after manual schema changes or restoring from a partial backup.
migrations-only Apply only DDL migrations, skip seeds.

Fresh DB workflow
-----------------
For a brand-new Postgres DB (new env, fork install, dev local):

    DATABASE_URL=postgresql://... \
      python scripts/deploy/init_database.py --mode=hybrid

This applies (in order):
  1. The 319 migrations in database/migrations/   (idempotent skip on
     re-runs once schema_migrations is populated)
  2. The 9 TIER_0 seeds in database/seeds/        (ON CONFLICT DO UPDATE)

After this, the boot of the FastAPI app calls initialize_permissions()
which auto-syncs any new permissions added in code since the last run.

Usage
-----
    python scripts/deploy/init_database.py --mode=hybrid
    python scripts/deploy/init_database.py --mode=auto
    python scripts/deploy/init_database.py --mode=legacy-compat  # rollback path

Environment
-----------
DATABASE_URL  Required. Postgres connection string (asyncpg-compatible).
APPLIED_BY    Optional. Identifier (default: 'init-database-script').

Exit codes
----------
0  All migrations applied or already up-to-date.
1  Configuration error (missing env, missing migration dir, etc.).
2  At least one migration failed in strict mode.
3  Could not acquire advisory lock within timeout (concurrent deploy).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import asyncpg

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Stable advisory-lock id derived from a fixed string. Stays constant across
# Python interpreter restarts (Python's hash() is randomized, so do NOT use it).
# `taxasge_init` → arbitrary 8-byte id; collisions with other locks unlikely.
ADVISORY_LOCK_ID: int = 0x7461_7861_7367_6569  # "taxasgei" in hex (8 bytes)

# Acquire timeout (seconds) before we give up — protects deadlocked deploys.
ADVISORY_LOCK_TIMEOUT_SEC: float = 60.0

# Repo layout (resolved at import time relative to this file).
REPO_ROOT: Path = Path(__file__).resolve().parents[2]  # packages/backend/
MIGRATIONS_DIR: Path = REPO_ROOT / "database" / "migrations"
SEEDS_DIR: Path = REPO_ROOT / "database" / "seeds"        # idempotent DML
BASELINE_DIR: Path = REPO_ROOT / "database" / "baseline"  # consolidated DDL


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MigrationFile:
    """In-memory representation of a SQL file pending application."""

    path: Path
    version: str       # filename stem (e.g. "336_create_schema_migrations")
    filename: str      # filename with extension
    checksum: str      # SHA-256 hex of file content
    filetype: str      # 'migration' | 'baseline' | 'seed'

    @classmethod
    def from_path(cls, path: Path, filetype: str = "migration") -> "MigrationFile":
        content = path.read_bytes()
        return cls(
            path=path,
            version=path.stem,
            filename=path.name,
            checksum=hashlib.sha256(content).hexdigest(),
            filetype=filetype,
        )


@dataclass
class ApplyResult:
    applied: int = 0
    skipped: int = 0
    warned_checksum_mismatch: int = 0
    failed: int = 0
    legacy_fallback_count: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(level: str, msg: str) -> None:
    """Minimal logger (stdout). Avoids hard dependency on loguru in CI."""
    print(f"[{level}] {msg}", flush=True)


def discover_files(directory: Path, filetype: str) -> list[MigrationFile]:
    """Return migrations sorted by filename (lexicographic = numeric prefix order)."""
    if not directory.exists():
        return []
    sql_files = sorted(directory.glob("*.sql"))
    return [MigrationFile.from_path(p, filetype=filetype) for p in sql_files]


async def schema_migrations_exists(conn: asyncpg.Connection) -> bool:
    row = await conn.fetchrow(
        "SELECT to_regclass('public.schema_migrations') AS oid"
    )
    return row is not None and row["oid"] is not None


async def is_database_empty(conn: asyncpg.Connection) -> bool:
    """True if the `public` schema has no user-defined tables.

    schema_migrations itself is excluded from the count — it gets created
    by ensure_schema_migrations_table() before this function is called,
    and we don't want it to mark the DB as 'not empty'.
    """
    count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
          AND table_name != 'schema_migrations'
        """
    )
    return count == 0


async def ensure_schema_migrations_table(conn: asyncpg.Connection) -> None:
    """Idempotent CREATE for first-run on a DB that doesn't have mig 336 yet."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(64) PRIMARY KEY,
            checksum VARCHAR(64) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            applied_by VARCHAR(128) NOT NULL DEFAULT 'init-database-script',
            execution_time_ms INTEGER,
            filename TEXT NOT NULL,
            filetype VARCHAR(16) NOT NULL DEFAULT 'migration'
                CHECK (filetype IN ('migration', 'baseline', 'seed'))
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at "
        "ON schema_migrations(applied_at DESC)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schema_migrations_filetype "
        "ON schema_migrations(filetype)"
    )


async def fetch_applied_versions(conn: asyncpg.Connection) -> dict[str, str]:
    """Return {version: checksum} for all applied migrations."""
    rows = await conn.fetch("SELECT version, checksum FROM schema_migrations")
    return {row["version"]: row["checksum"] for row in rows}


async def acquire_lock(conn: asyncpg.Connection) -> bool:
    """Try to acquire pg_advisory_lock with a soft timeout via polling.

    Returns True on success, False on timeout. Lock is released automatically
    when the connection closes (using session-scoped lock).
    """
    deadline = time.monotonic() + ADVISORY_LOCK_TIMEOUT_SEC
    while time.monotonic() < deadline:
        # pg_try_advisory_lock returns True if acquired, False otherwise.
        got = await conn.fetchval("SELECT pg_try_advisory_lock($1)", ADVISORY_LOCK_ID)
        if got:
            return True
        await asyncio.sleep(1.0)
    return False


async def release_lock(conn: asyncpg.Connection) -> None:
    try:
        await conn.fetchval("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_ID)
    except Exception as e:
        log("WARN", f"Could not release advisory lock cleanly: {e}")


def split_statements(sql: str) -> list[str]:
    """Naive split on `;`. Identical to legacy workflow logic.

    Limitations: does NOT handle DO $$ ... $$ blocks containing ';' inside.
    Files using such blocks must be wrapped in BEGIN; ... COMMIT; and applied
    via execute() of the full file content (set use_full_file=True flag —
    Phase A.2 enhancement, not in scope here).
    """
    return [
        s.strip()
        for s in sql.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]


def is_already_exists_error(exc: Exception) -> bool:
    """Heuristic kept identical to the legacy workflow logic."""
    msg = str(exc).lower()
    return "already exists" in msg or "duplicate" in msg


# ---------------------------------------------------------------------------
# Apply logic
# ---------------------------------------------------------------------------

async def apply_one_file(
    conn: asyncpg.Connection,
    mig: MigrationFile,
    *,
    mode: str,
    applied_by: str,
    result: ApplyResult,
) -> None:
    """Apply a single migration file according to the requested mode."""
    sql = mig.path.read_text(encoding="utf-8")
    stmts = split_statements(sql)
    started = time.monotonic()

    legacy_fallback_used = False

    for stmt in stmts:
        if not stmt:
            continue
        try:
            await conn.execute(stmt)
        except Exception as e:
            if mode in ("hybrid", "legacy-compat") and is_already_exists_error(e):
                # Idempotent re-apply: skip silently, mark fallback usage.
                legacy_fallback_used = True
                continue
            log("ERROR", f"  {mig.filename}: {str(e)[:200]}")
            result.failed += 1
            if mode == "strict":
                raise
            # In hybrid/legacy modes, abort this file but continue overall.
            break
    else:
        # Loop completed without break -> success (with or without fallback).
        elapsed_ms = int((time.monotonic() - started) * 1000)
        await conn.execute(
            """
            INSERT INTO schema_migrations
                (version, checksum, applied_at, applied_by, execution_time_ms,
                 filename, filetype)
            VALUES ($1, $2, NOW(), $3, $4, $5, $6)
            ON CONFLICT (version) DO UPDATE
                SET checksum = EXCLUDED.checksum,
                    applied_at = EXCLUDED.applied_at,
                    applied_by = EXCLUDED.applied_by,
                    execution_time_ms = EXCLUDED.execution_time_ms
            """,
            mig.version,
            mig.checksum,
            applied_by,
            elapsed_ms,
            mig.filename,
            mig.filetype,
        )
        result.applied += 1
        if legacy_fallback_used:
            result.legacy_fallback_count += 1
            log("INFO", f"  ✔ {mig.filename} ({elapsed_ms} ms, fallback used)")
        else:
            log("INFO", f"  ✔ {mig.filename} ({elapsed_ms} ms)")


async def apply_directory(
    conn: asyncpg.Connection,
    files: list[MigrationFile],
    *,
    mode: str,
    applied_by: str,
    applied_versions: dict[str, str],
    result: ApplyResult,
) -> None:
    """Apply all files, skipping those already in schema_migrations."""
    for mig in files:
        existing_checksum = applied_versions.get(mig.version)

        if existing_checksum is not None:
            if existing_checksum == mig.checksum:
                result.skipped += 1
                continue
            # Checksum mismatch: file edited after apply. Warn (Phase A:
            # warn-only; Phase F: configurable error).
            log("WARN",
                f"  ! {mig.filename}: checksum mismatch with applied version "
                f"(applied={existing_checksum[:12]}, file={mig.checksum[:12]})")
            result.warned_checksum_mismatch += 1
            continue

        await apply_one_file(
            conn, mig, mode=mode, applied_by=applied_by, result=result
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--mode",
        choices=["auto", "hybrid", "strict", "legacy-compat",
                 "migrations-only", "seeds-only"],
        default="hybrid",
        help="Application mode (see module docstring).",
    )
    parser.add_argument(
        "--applied-by",
        default=os.environ.get("APPLIED_BY", "init-database-script"),
        help="Identifier recorded in schema_migrations.applied_by.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL (overrides DATABASE_URL env var).",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        log("ERROR", "DATABASE_URL is required (env or --database-url).")
        return 1

    if not MIGRATIONS_DIR.exists():
        log("ERROR", f"Missing migrations dir: {MIGRATIONS_DIR}")
        return 1

    conn = await asyncpg.connect(args.database_url)
    try:
        log("INFO", f"Mode: {args.mode}")
        log("INFO", "Acquiring advisory lock...")
        if not await acquire_lock(conn):
            log("ERROR",
                f"Could not acquire advisory lock within "
                f"{ADVISORY_LOCK_TIMEOUT_SEC}s. Another deploy may be running.")
            return 3

        try:
            await ensure_schema_migrations_table(conn)
            applied_versions = await fetch_applied_versions(conn)
            log("INFO",
                f"schema_migrations: {len(applied_versions)} versions already "
                f"recorded.")

            result = ApplyResult()

            # ---- Baseline-first detection (auto / hybrid only) ----
            # If the DB is empty AND a baseline/*.sql exists, prefer it
            # over replaying the 319 incremental migrations (≈30s vs ≈4min
            # on a fresh DB). Falls back to migrations otherwise.
            applied_baseline = False
            if args.mode in ("auto", "hybrid") and BASELINE_DIR.exists():
                baselines = discover_files(BASELINE_DIR, filetype="baseline")
                if baselines and await is_database_empty(conn):
                    log("INFO",
                        f"Empty DB detected — applying {len(baselines)} "
                        f"baseline file(s) from "
                        f"{BASELINE_DIR.relative_to(REPO_ROOT)}")
                    await apply_directory(
                        conn, baselines,
                        mode=args.mode,
                        applied_by=args.applied_by,
                        applied_versions=applied_versions,
                        result=result,
                    )
                    applied_baseline = True
                    # Mark every existing migration as applied (so future
                    # `--mode=hybrid` runs skip them — they're already
                    # captured by the baseline).
                    pending_migs = discover_files(
                        MIGRATIONS_DIR, filetype="migration"
                    )
                    log("INFO",
                        f"Marking {len(pending_migs)} legacy migration(s) "
                        f"as applied via baseline (no replay needed).")
                    for mig in pending_migs:
                        await conn.execute(
                            """
                            INSERT INTO schema_migrations
                                (version, checksum, applied_by, filename, filetype)
                            VALUES ($1, $2, $3, $4, 'migration')
                            ON CONFLICT (version) DO NOTHING
                            """,
                            mig.version, mig.checksum,
                            f"{args.applied_by}:via-baseline",
                            mig.filename,
                        )

            if not applied_baseline and args.mode != "seeds-only":
                migs = discover_files(MIGRATIONS_DIR, filetype="migration")
                log("INFO",
                    f"Discovered {len(migs)} migration files "
                    f"(baseline {'absent' if not BASELINE_DIR.exists() else 'skipped'}).")
                await apply_directory(
                    conn, migs,
                    mode=args.mode,
                    applied_by=args.applied_by,
                    applied_versions=applied_versions,
                    result=result,
                )

            if args.mode in ("auto", "hybrid", "strict", "seeds-only"):
                # Apply TIER_0 seeds (RBAC + communication templates).
                # Idempotent ON CONFLICT DO UPDATE — safe to re-apply.
                if SEEDS_DIR.exists():
                    seeds = discover_files(SEEDS_DIR, filetype="seed")
                    if seeds:
                        log("INFO",
                            f"Applying {len(seeds)} seed files from "
                            f"{SEEDS_DIR.relative_to(REPO_ROOT)}")
                        await apply_directory(
                            conn, seeds,
                            mode=args.mode,
                            applied_by=args.applied_by,
                            applied_versions=applied_versions,
                            result=result,
                        )
                    else:
                        log("INFO",
                            f"No seed files in {SEEDS_DIR.relative_to(REPO_ROOT)} "
                            f"— skipping seeds step.")
                else:
                    log("INFO",
                        "No seeds/ directory found — skipping seeds step. "
                        "(Generate with deploy/scripts/extract_seeds.py)")

            log("INFO",
                f"Summary: applied={result.applied} skipped={result.skipped} "
                f"checksum_warn={result.warned_checksum_mismatch} "
                f"failed={result.failed} fallback_used={result.legacy_fallback_count}")

            if result.failed and args.mode == "strict":
                return 2
            return 0
        finally:
            await release_lock(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
