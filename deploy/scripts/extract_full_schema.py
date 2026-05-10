#!/usr/bin/env python3
"""Extract a complete, executable SQL baseline from a live Postgres.

Phase D (Python alternative) of MIGRATIONS_BASELINE_REFACTOR_PLAN.

Replaces `pg_dump --schema-only` with an asyncpg-based extractor that
queries pg_catalog and uses Postgres's own `pg_get_*()` functions to
reconstruct DDL faithfully (no SQL parser needed):

  - pg_get_constraintdef(oid)  -> constraint definitions (PK, FK, CHECK, UNIQUE)
  - pg_get_indexdef(oid)       -> CREATE INDEX statements
  - pg_get_functiondef(oid)    -> CREATE FUNCTION statements (incl. body)
  - pg_get_triggerdef(oid)     -> CREATE TRIGGER statements
  - pg_get_viewdef(oid)        -> SELECT body of a view

Output ordering follows safe DDL replay rules:

  1. Extensions          (CREATE EXTENSION IF NOT EXISTS)
  2. Custom enums        (CREATE TYPE ... AS ENUM)
  3. Custom composite types (CREATE TYPE ... AS (...))
  4. Sequences           (CREATE SEQUENCE — needed before tables that reference them)
  5. Tables              (CREATE TABLE — columns + inline defaults, NO FK)
  6. Primary keys        (ALTER TABLE ADD CONSTRAINT — explicit)
  7. Unique constraints  (ALTER TABLE ADD CONSTRAINT)
  8. CHECK constraints   (ALTER TABLE ADD CONSTRAINT)
  9. Foreign keys        (ALTER TABLE ADD CONSTRAINT — last to avoid order issues)
 10. Indexes (non-PK, non-unique)
 11. Functions
 12. Triggers
 13. Views
 14. Materialized views

Supabase-specific objects (RLS policies, auth schema, storage schema,
realtime publications) are intentionally SKIPPED — TaxasGE uses
backend JWT for auth and Firebase Storage, so they aren't needed on
a vanilla Postgres deployment.

Usage
-----
    DATABASE_URL=postgresql://... python deploy/scripts/extract_full_schema.py

    # Custom output path
    python deploy/scripts/extract_full_schema.py \
        --output=packages/backend/database/baseline/000_baseline_2026_05_09.sql

Exit codes
----------
0  Schema extraction succeeded.
1  Configuration error.
2  Database error during extraction.
3  No connection.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("ERROR: asyncpg required. pip install asyncpg", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "packages" / "backend" / "database" / "baseline" / \
    f"000_baseline_{datetime.now(timezone.utc).strftime('%Y_%m_%d')}.sql"


# ---------------------------------------------------------------------------
# Constants — extensions and schemas to manage
# ---------------------------------------------------------------------------

# Common Postgres extensions our app might depend on. Extracted with
# CREATE EXTENSION IF NOT EXISTS so re-runs are safe.
RELEVANT_EXTENSIONS = {
    "uuid-ossp",     # uuid_generate_v4()
    "pgcrypto",      # gen_random_uuid(), encryption
    "pg_trgm",       # trigram search
    "pgvector",      # vector embeddings (RAG)
    "btree_gin",     # GIN index on btree types
    "btree_gist",    # GiST index on btree types
    "unaccent",      # accent-insensitive search
    "citext",        # case-insensitive text
}

# Schemas to extract from. We focus on `public` only — Supabase-specific
# (auth, storage, realtime, graphql, vault, supabase_functions) is skipped.
TARGET_SCHEMA = "public"


# ---------------------------------------------------------------------------
# Result accumulators
# ---------------------------------------------------------------------------

@dataclass
class SchemaExtraction:
    extensions: list[tuple[str, str]] = field(default_factory=list)  # (name, schema)
    enums: list[tuple[str, list[str]]] = field(default_factory=list)  # (name, labels)
    composite_types: list[tuple[str, str]] = field(default_factory=list)  # (name, definition)
    sequences: list[str] = field(default_factory=list)  # sequence names
    tables: list[tuple[str, str]] = field(default_factory=list)  # (name, create_sql)
    primary_keys: list[tuple[str, str, str]] = field(default_factory=list)  # (table, name, definition)
    unique_constraints: list[tuple[str, str, str]] = field(default_factory=list)
    check_constraints: list[tuple[str, str, str]] = field(default_factory=list)
    foreign_keys: list[tuple[str, str, str]] = field(default_factory=list)
    indexes: list[tuple[str, str]] = field(default_factory=list)  # (name, definition)
    functions: list[tuple[str, str]] = field(default_factory=list)  # (name, definition)
    triggers: list[tuple[str, str]] = field(default_factory=list)
    views: list[tuple[str, str]] = field(default_factory=list)  # (name, definition)
    materialized_views: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Extractors — each fetches one DDL category
# ---------------------------------------------------------------------------

async def fetch_extensions(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    rows = await conn.fetch("""
        SELECT extname, n.nspname AS schema
        FROM pg_extension e
        JOIN pg_namespace n ON n.oid = e.extnamespace
        WHERE extname = ANY($1::text[])
        ORDER BY extname
    """, list(RELEVANT_EXTENSIONS))
    return [(r["extname"], r["schema"]) for r in rows]


async def fetch_enums(conn: asyncpg.Connection) -> list[tuple[str, list[str]]]:
    rows = await conn.fetch("""
        SELECT t.typname AS enum_name,
               array_agg(e.enumlabel ORDER BY e.enumsortorder) AS labels
        FROM pg_type t
        JOIN pg_enum e ON e.enumtypid = t.oid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = $1
        GROUP BY t.typname
        ORDER BY t.typname
    """, TARGET_SCHEMA)
    return [(r["enum_name"], list(r["labels"])) for r in rows]


async def fetch_composite_types(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    """Composite types (NOT enums, NOT table-row types). Rare in our schema."""
    rows = await conn.fetch("""
        SELECT t.typname,
               pg_catalog.format_type(t.oid, NULL) AS rendered
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_class c ON c.oid = t.typrelid
        WHERE n.nspname = $1
          AND t.typtype = 'c'
          AND c.relkind = 'c'  -- composite, not table
        ORDER BY t.typname
    """, TARGET_SCHEMA)
    return [(r["typname"], r["rendered"]) for r in rows]


async def fetch_sequences(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch("""
        SELECT sequence_name
        FROM information_schema.sequences
        WHERE sequence_schema = $1
        ORDER BY sequence_name
    """, TARGET_SCHEMA)
    return [r["sequence_name"] for r in rows]


async def fetch_table_names(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = $1 AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """, TARGET_SCHEMA)
    return [r["table_name"] for r in rows]


async def render_create_table(conn: asyncpg.Connection, table: str) -> str:
    """Build a CREATE TABLE IF NOT EXISTS statement (without FKs/UNIQUE/CHECK).

    Includes column types, defaults, and NOT NULL inline. Constraints other
    than NOT NULL are added later via ALTER TABLE for clarity and order safety.
    """
    cols = await conn.fetch("""
        SELECT column_name,
               data_type,
               udt_schema,
               udt_name,
               character_maximum_length,
               numeric_precision,
               numeric_scale,
               is_nullable,
               column_default
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
    """, TARGET_SCHEMA, table)

    col_defs: list[str] = []
    for c in cols:
        name = c["column_name"]
        # Render the type with the right formatting.
        if c["data_type"] == "USER-DEFINED":
            # Enum or composite — use the udt_name, qualified by schema.
            col_type = f'"{c["udt_schema"]}"."{c["udt_name"]}"'
        elif c["data_type"] == "ARRAY":
            # ARRAY of <udt_name minus leading underscore>
            inner = c["udt_name"].lstrip("_")
            col_type = f"{inner}[]"
        elif c["data_type"] == "character varying":
            if c["character_maximum_length"]:
                col_type = f"varchar({c['character_maximum_length']})"
            else:
                col_type = "varchar"
        elif c["data_type"] == "character":
            if c["character_maximum_length"]:
                col_type = f"char({c['character_maximum_length']})"
            else:
                col_type = "char"
        elif c["data_type"] == "numeric" and c["numeric_precision"]:
            if c["numeric_scale"]:
                col_type = f"numeric({c['numeric_precision']},{c['numeric_scale']})"
            else:
                col_type = f"numeric({c['numeric_precision']})"
        else:
            col_type = c["data_type"]

        nullable = "" if c["is_nullable"] == "YES" else " NOT NULL"
        default = f" DEFAULT {c['column_default']}" if c["column_default"] else ""
        col_defs.append(f'    "{name}" {col_type}{nullable}{default}')

    body = ",\n".join(col_defs)
    return f'CREATE TABLE IF NOT EXISTS "{TARGET_SCHEMA}"."{table}" (\n{body}\n);'


async def fetch_constraints(
    conn: asyncpg.Connection,
    contype: str,
) -> list[tuple[str, str, str]]:
    """Return (table, name, ALTER-TABLE-line) for constraints of a given type.

    contype values: 'p' (primary key), 'u' (unique), 'c' (check), 'f' (foreign key).
    """
    rows = await conn.fetch(f"""
        SELECT c.relname AS table_name,
               con.conname AS constraint_name,
               pg_get_constraintdef(con.oid) AS definition
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = $1
          AND con.contype = '{contype}'::"char"
        ORDER BY c.relname, con.conname
    """, TARGET_SCHEMA)
    return [
        (r["table_name"], r["constraint_name"],
         f'ALTER TABLE "{TARGET_SCHEMA}"."{r["table_name"]}" '
         f'ADD CONSTRAINT "{r["constraint_name"]}" {r["definition"]};')
        for r in rows
    ]


async def fetch_indexes(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    """Indexes that are NOT backing a primary key or unique constraint."""
    rows = await conn.fetch("""
        SELECT i.indexname, i.indexdef
        FROM pg_indexes i
        WHERE i.schemaname = $1
          AND NOT EXISTS (
              SELECT 1 FROM pg_constraint con
              JOIN pg_class c ON c.oid = con.conindid
              WHERE c.relname = i.indexname
                AND con.contype IN ('p', 'u')
          )
        ORDER BY i.indexname
    """, TARGET_SCHEMA)
    return [(r["indexname"], r["indexdef"] + ";") for r in rows]


async def fetch_functions(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    """User-defined functions in the target schema (not built-ins)."""
    rows = await conn.fetch("""
        SELECT p.proname,
               pg_get_functiondef(p.oid) AS definition
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = $1
          AND p.prokind = 'f'  -- regular functions (not aggregates/windows)
        ORDER BY p.proname
    """, TARGET_SCHEMA)
    return [(r["proname"], r["definition"] + ";") for r in rows]


async def fetch_triggers(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    rows = await conn.fetch("""
        SELECT t.tgname,
               pg_get_triggerdef(t.oid) AS definition
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = $1
          AND NOT t.tgisinternal  -- skip system triggers
        ORDER BY t.tgname
    """, TARGET_SCHEMA)
    return [(r["tgname"], r["definition"] + ";") for r in rows]


async def fetch_views(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    rows = await conn.fetch("""
        SELECT c.relname AS view_name,
               pg_get_viewdef(c.oid, true) AS definition
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = $1 AND c.relkind = 'v'
        ORDER BY c.relname
    """, TARGET_SCHEMA)
    return [
        (r["view_name"],
         f'CREATE OR REPLACE VIEW "{TARGET_SCHEMA}"."{r["view_name"]}" AS\n'
         f'{r["definition"]}')
        for r in rows
    ]


async def fetch_materialized_views(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    rows = await conn.fetch("""
        SELECT c.relname AS mv_name,
               pg_get_viewdef(c.oid, true) AS definition
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = $1 AND c.relkind = 'm'
        ORDER BY c.relname
    """, TARGET_SCHEMA)
    return [
        (r["mv_name"],
         f'CREATE MATERIALIZED VIEW IF NOT EXISTS "{TARGET_SCHEMA}"."{r["mv_name"]}" AS\n'
         f'{r["definition"]}\nWITH NO DATA;')
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def extract_all(database_url: str) -> SchemaExtraction:
    extraction = SchemaExtraction()
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"ERROR: could not connect: {e}", file=sys.stderr)
        raise SystemExit(3)

    try:
        print("Extracting extensions...")
        extraction.extensions = await fetch_extensions(conn)
        print(f"  {len(extraction.extensions)} extension(s)")

        print("Extracting enums...")
        extraction.enums = await fetch_enums(conn)
        print(f"  {len(extraction.enums)} enum(s)")

        print("Extracting composite types...")
        extraction.composite_types = await fetch_composite_types(conn)
        print(f"  {len(extraction.composite_types)} composite type(s)")

        print("Extracting sequences...")
        extraction.sequences = await fetch_sequences(conn)
        print(f"  {len(extraction.sequences)} sequence(s)")

        print("Extracting tables (incl. columns + defaults)...")
        tables = await fetch_table_names(conn)
        for t in tables:
            create_sql = await render_create_table(conn, t)
            extraction.tables.append((t, create_sql))
        print(f"  {len(extraction.tables)} table(s)")

        print("Extracting constraints (PK/UNIQUE/CHECK/FK)...")
        extraction.primary_keys = await fetch_constraints(conn, "p")
        extraction.unique_constraints = await fetch_constraints(conn, "u")
        extraction.check_constraints = await fetch_constraints(conn, "c")
        extraction.foreign_keys = await fetch_constraints(conn, "f")
        print(f"  {len(extraction.primary_keys)} PK, "
              f"{len(extraction.unique_constraints)} UNIQUE, "
              f"{len(extraction.check_constraints)} CHECK, "
              f"{len(extraction.foreign_keys)} FK")

        print("Extracting indexes (non-PK, non-unique)...")
        extraction.indexes = await fetch_indexes(conn)
        print(f"  {len(extraction.indexes)} index(es)")

        print("Extracting functions...")
        extraction.functions = await fetch_functions(conn)
        print(f"  {len(extraction.functions)} function(s)")

        print("Extracting triggers...")
        extraction.triggers = await fetch_triggers(conn)
        print(f"  {len(extraction.triggers)} trigger(s)")

        print("Extracting views...")
        extraction.views = await fetch_views(conn)
        print(f"  {len(extraction.views)} view(s)")

        print("Extracting materialized views...")
        extraction.materialized_views = await fetch_materialized_views(conn)
        print(f"  {len(extraction.materialized_views)} materialized view(s)")
    finally:
        await conn.close()

    return extraction


# ---------------------------------------------------------------------------
# SQL rendering
# ---------------------------------------------------------------------------

def render_sql(extraction: SchemaExtraction) -> str:
    parts: list[str] = []
    now = datetime.now(timezone.utc).isoformat()

    parts.append(f"-- =============================================================")
    parts.append(f"-- Facil baseline schema — generated by extract_full_schema.py")
    parts.append(f"-- Source: {TARGET_SCHEMA} schema of the staging database")
    parts.append(f"-- Generated: {now}")
    parts.append(f"-- DO NOT EDIT MANUALLY. Re-run the extractor to regenerate.")
    parts.append(f"-- =============================================================")
    parts.append("")

    # 1. Extensions
    if extraction.extensions:
        parts.append("-- ---------- 1. Extensions ----------")
        for ext_name, _ in extraction.extensions:
            parts.append(f'CREATE EXTENSION IF NOT EXISTS "{ext_name}";')
        parts.append("")

    # 2. Enums
    if extraction.enums:
        parts.append("-- ---------- 2. Enums ----------")
        for name, labels in extraction.enums:
            quoted = ", ".join(f"'{label}'" for label in labels)
            parts.append(
                f'DO $$ BEGIN\n'
                f'    CREATE TYPE "{TARGET_SCHEMA}"."{name}" AS ENUM ({quoted});\n'
                f'EXCEPTION WHEN duplicate_object THEN NULL;\n'
                f'END $$;'
            )
        parts.append("")

    # 3. Composite types
    if extraction.composite_types:
        parts.append("-- ---------- 3. Composite types ----------")
        for name, rendered in extraction.composite_types:
            parts.append(f"-- (composite type {name}: {rendered}) — manual review may be required")
        parts.append("")

    # 4. Sequences (often auto-created by SERIAL/IDENTITY columns; we list
    # them as a safeguard for sequences not tied to a column)
    if extraction.sequences:
        parts.append("-- ---------- 4. Sequences ----------")
        for seq in extraction.sequences:
            parts.append(
                f'CREATE SEQUENCE IF NOT EXISTS "{TARGET_SCHEMA}"."{seq}";'
            )
        parts.append("")

    # 5. Tables
    parts.append("-- ---------- 5. Tables ----------")
    for _, create_sql in extraction.tables:
        parts.append(create_sql)
        parts.append("")

    # 6. Primary keys
    if extraction.primary_keys:
        parts.append("-- ---------- 6. Primary keys ----------")
        for _, _, alter_sql in extraction.primary_keys:
            parts.append(alter_sql)
        parts.append("")

    # 7. Unique constraints
    if extraction.unique_constraints:
        parts.append("-- ---------- 7. Unique constraints ----------")
        for _, _, alter_sql in extraction.unique_constraints:
            parts.append(alter_sql)
        parts.append("")

    # 8. CHECK constraints
    if extraction.check_constraints:
        parts.append("-- ---------- 8. CHECK constraints ----------")
        for _, _, alter_sql in extraction.check_constraints:
            parts.append(alter_sql)
        parts.append("")

    # 9. Foreign keys (LAST among constraints)
    if extraction.foreign_keys:
        parts.append("-- ---------- 9. Foreign keys ----------")
        for _, _, alter_sql in extraction.foreign_keys:
            parts.append(alter_sql)
        parts.append("")

    # 10. Indexes
    if extraction.indexes:
        parts.append("-- ---------- 10. Indexes ----------")
        for _, definition in extraction.indexes:
            parts.append(definition)
        parts.append("")

    # 11. Functions
    if extraction.functions:
        parts.append("-- ---------- 11. Functions ----------")
        for _, definition in extraction.functions:
            parts.append(definition)
            parts.append("")

    # 12. Triggers
    if extraction.triggers:
        parts.append("-- ---------- 12. Triggers ----------")
        for _, definition in extraction.triggers:
            parts.append(definition)
        parts.append("")

    # 13. Views
    if extraction.views:
        parts.append("-- ---------- 13. Views ----------")
        for _, definition in extraction.views:
            parts.append(definition + ";")
            parts.append("")

    # 14. Materialized views
    if extraction.materialized_views:
        parts.append("-- ---------- 14. Materialized views ----------")
        for _, definition in extraction.materialized_views:
            parts.append(definition)
            parts.append("")

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Path for the generated baseline SQL (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--supabase-extras", action="store_true",
        help="(NOT YET IMPLEMENTED) Also extract Supabase-specific objects "
             "(RLS policies, auth schema refs, realtime publications). The "
             "default 'vanilla' baseline is compatible with any standard "
             "Postgres 13+ and is what you want for Docker/local/AWS RDS. "
             "Use --supabase-extras only when targeting Supabase to keep "
             "RLS-protected behavior identical.",
    )
    args = parser.parse_args(argv)

    if args.supabase_extras:
        print(
            "WARNING: --supabase-extras requested but not yet implemented. "
            "Generating vanilla baseline only. Open an issue to prioritize "
            "the RLS/auth/realtime extractor.",
            file=sys.stderr,
        )

    if not args.database_url:
        print("ERROR: DATABASE_URL is required.", file=sys.stderr)
        return 1

    print(f"Extracting full schema from staging...")
    extraction = asyncio.run(extract_all(args.database_url))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sql = render_sql(extraction)
    args.output.write_text(sql, encoding="utf-8")

    line_count = sql.count("\n") + 1
    print(f"\n[OK] Wrote baseline to {args.output}")
    print(f"  {line_count} lines, {len(sql)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
