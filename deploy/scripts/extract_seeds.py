#!/usr/bin/env python3
"""Extract seed data from a live Postgres into idempotent SQL files.

Phase D-alt of the MIGRATIONS_BASELINE_REFACTOR_PLAN. Replaces the
classic `pg_dump --data-only --table=...` workflow with a Python-based
extractor that:

  - Connects via asyncpg (no pg_dump binary required).
  - Generates `INSERT INTO ... ON CONFLICT (pk) DO UPDATE SET ...` —
    idempotent by design, safe to apply on a populated DB.
  - Auto-detects the primary key from pg_constraint.
  - Falls back to `ON CONFLICT DO NOTHING` for tables without a PK.

Default table set (TIER_0): the **universal** seeds — RBAC + communication
templates. Reusable across any deployment of Facil (any country / org).
Permissions are also auto-synced at boot by `initialize_permissions()`
(see MEMORY.md rule #37); seeding them here is defense-in-depth.

TIER_1 is **deployment-specific** (TaxasGE Guinea-Ecuatorial taxonomies,
fiscal services, cities, etc.). NOT reusable across countries. See the
TIER_1_TABLES docstring inside this module for details.

Usage
-----
    # Extract the TIER_0 default set to database/seeds/
    python deploy/scripts/extract_seeds.py

    # Extend with TIER_1 reference data (fiscal_services, templates, etc.).
    python deploy/scripts/extract_seeds.py --tier=1

    # Extract a specific table.
    python deploy/scripts/extract_seeds.py --tables=cities,ministries

    # Custom output dir.
    python deploy/scripts/extract_seeds.py --output-dir=/tmp/seeds

Environment
-----------
DATABASE_URL  Required. Source DB to read from. NEVER mutated (read-only queries only).

Exit codes
----------
0  Extraction succeeded for all requested tables.
1  Configuration error (missing env, bad table name, etc.).
2  Database error during extraction.
3  No connection.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("ERROR: asyncpg required. Install: pip install asyncpg", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "packages" / "backend" / "database" / "seeds"


# ---------------------------------------------------------------------------
# Tiered table definitions
# ---------------------------------------------------------------------------

# TIER_0 — strict minimum requested by the user (2026-05-09):
#   roles, permissions, role_permissions, communication templates.
# Without these, the app can't sign up users (no roles) or send any
# transactional notification (no templates).
#
# Note: permissions are also auto-synced at boot by
# initialize_permissions() (see MEMORY.md rule #37). Including them in
# the seed is defense-in-depth — idempotent (ON CONFLICT DO UPDATE), no
# conflict with the boot sync. role_permissions are NOT auto-created by
# the boot, so the seed is the only way to provision them on a fresh DB.
TIER_0_TABLES: list[str] = [
    # Auth / RBAC
    "roles",
    "permissions",
    "role_permissions",
    # Communication templates
    "email_templates",
    "sms_templates",
    "push_templates",
    "notification_templates",
    "ussd_configurations",
    "communication_provider_settings",
]

# TIER_1 — DEPLOYMENT-SPECIFIC data. WARNING: this set is **NOT universal**.
# It contains tables whose content is bound to a specific country / state /
# institution (TaxasGE Guinea-Ecuatorial: Spanish ministries, local cities,
# country-specific fiscal services and tariffs, etc.).
#
# A new deployer in another country (e.g. Cameroon, Senegal) MUST NOT
# re-use this seed as-is — they should:
#   1. Skip TIER_1 on first deploy.
#   2. Configure their own taxonomies (ministries, sectors, categories,
#      cities, fiscal_services, etc.) via the admin UI.
#   3. Optionally re-run extract_seeds.py against THEIR DB to capture
#      their own TIER_1 for backups / disaster recovery.
#
# Use TIER_1 ONLY when re-bootstrapping an environment of the SAME
# deployment (e.g. setting up a staging clone of TaxasGE production).
TIER_1_TABLES: list[str] = TIER_0_TABLES + [
    # Country-specific taxonomies
    "categories",
    "ministries",
    "sectors",
    "cities",
    "entities",
    "entity_locations",
    # Country-specific catalog
    "fiscal_services",
    "service_keywords",
    "service_document_assignments",
    "service_procedure_assignments",
    "procedure_templates",
    "procedure_template_steps",
    "document_templates",
    "service_bundles",
    "service_bundle_items",
    "workflow_document_requirements",
    "workflow_tariffs",
    "workflow_supplement_config",
    "workflow_display_config",
    "tariff_supplements",
    # Country-specific i18n strings
    "translations",
    "entity_translations",
    # Country-specific scheduling
    "appointment_delay_rules",
    "appointment_slot_configs",
    # Mostly universal, but country-specific in practice (workflow names,
    # menu labels, etc.)
    "valid_workflow_codes",
    "system_rules",
    "workflow_menu_mapping",
    "workflows",
    "dashboard_registrations",
    "export_templates",
]


# ---------------------------------------------------------------------------
# SQL literal formatting
# ---------------------------------------------------------------------------

def to_sql_literal(value: Any) -> str:
    """Render a Python value as an inline Postgres literal.

    Handles: None, bool, int/float/Decimal, str, bytes, datetime/date/time,
    UUID, dict/list (JSONB), set, asyncpg Range types passthrough.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, str):
        # Escape single quotes by doubling them. PG-style.
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, bytes):
        return "'\\x" + value.hex() + "'::bytea"
    if isinstance(value, UUID):
        return f"'{value}'::uuid"
    if isinstance(value, datetime):
        return f"'{value.isoformat()}'::timestamptz"
    if isinstance(value, date):
        return f"'{value.isoformat()}'::date"
    if isinstance(value, time):
        return f"'{value.isoformat()}'::time"
    if isinstance(value, (dict, list)):
        # JSONB. json.dumps escapes properly; then Postgres quote escape.
        as_json = json.dumps(value, default=str, ensure_ascii=False)
        return "'" + as_json.replace("'", "''") + "'::jsonb"
    if isinstance(value, set):
        # Postgres array literal — coerce to sorted list for determinism.
        items = sorted(str(v) for v in value)
        inner = ",".join(f'"{v}"' for v in items)
        return "'{" + inner + "}'"
    # Fallback: stringify and quote.
    return "'" + str(value).replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------

@dataclass
class TableInfo:
    name: str
    columns: list[str]
    pk_columns: list[str]  # empty = no PK, will use ON CONFLICT DO NOTHING

    @property
    def has_pk(self) -> bool:
        return bool(self.pk_columns)


async def fetch_columns(conn: asyncpg.Connection, table: str) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )
    return [r["column_name"] for r in rows]


async def fetch_pk_columns(conn: asyncpg.Connection, table: str) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT a.attname AS column_name
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = $1::regclass AND i.indisprimary
        ORDER BY array_position(i.indkey, a.attnum)
        """,
        f"public.{table}",
    )
    return [r["column_name"] for r in rows]


async def table_exists(conn: asyncpg.Connection, table: str) -> bool:
    return bool(await conn.fetchval(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table,
    ))


async def fetch_table_info(conn: asyncpg.Connection, table: str) -> TableInfo:
    cols = await fetch_columns(conn, table)
    pk = await fetch_pk_columns(conn, table)
    return TableInfo(name=table, columns=cols, pk_columns=pk)


# ---------------------------------------------------------------------------
# Seed file generation
# ---------------------------------------------------------------------------

def render_seed_sql(info: TableInfo, rows: list[asyncpg.Record]) -> str:
    """Build the full .sql content for one table."""
    if not info.columns:
        return f"-- Table {info.name}: no columns introspected, skipping.\n"
    header = [
        f"-- Generated by deploy/scripts/extract_seeds.py — DO NOT EDIT",
        f"-- Table: public.{info.name}",
        f"-- Rows:  {len(rows)}",
        f"-- Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "BEGIN;",
        "",
    ]
    body: list[str] = []

    if not rows:
        body.append(f"-- (empty — no rows to insert)")
    else:
        col_list = ", ".join(f'"{c}"' for c in info.columns)
        for row in rows:
            values = ", ".join(to_sql_literal(row[c]) for c in info.columns)
            stmt = f'INSERT INTO public."{info.name}" ({col_list})\n  VALUES ({values})'
            if info.has_pk:
                pk_list = ", ".join(f'"{c}"' for c in info.pk_columns)
                non_pk = [c for c in info.columns if c not in info.pk_columns]
                if non_pk:
                    set_clause = ", ".join(
                        f'"{c}" = EXCLUDED."{c}"' for c in non_pk
                    )
                    stmt += f"\n  ON CONFLICT ({pk_list}) DO UPDATE SET {set_clause}"
                else:
                    stmt += f"\n  ON CONFLICT ({pk_list}) DO NOTHING"
            else:
                stmt += "\n  ON CONFLICT DO NOTHING"
            body.append(stmt + ";")

    return "\n".join(header) + "\n".join(body) + "\n\nCOMMIT;\n"


# ---------------------------------------------------------------------------
# Extraction orchestrator
# ---------------------------------------------------------------------------

@dataclass
class ExtractResult:
    table: str
    rows_extracted: int
    output_path: Path
    skipped_reason: str = ""


async def extract_table(
    conn: asyncpg.Connection,
    table: str,
    output_dir: Path,
    seed_index: int,
) -> ExtractResult:
    if not await table_exists(conn, table):
        return ExtractResult(
            table=table, rows_extracted=0,
            output_path=Path("/dev/null"),
            skipped_reason="table not found in public schema",
        )
    info = await fetch_table_info(conn, table)
    rows = await conn.fetch(f'SELECT * FROM public."{table}"')
    sql = render_seed_sql(info, rows)
    out_file = output_dir / f"{seed_index:03d}_{table}.sql"
    out_file.write_text(sql, encoding="utf-8")
    return ExtractResult(
        table=table,
        rows_extracted=len(rows),
        output_path=out_file,
    )


async def main_async(
    database_url: str,
    tables: list[str],
    output_dir: Path,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"ERROR: could not connect to database: {e}", file=sys.stderr)
        return 3

    rc = 0
    try:
        results: list[ExtractResult] = []
        for idx, table in enumerate(tables, start=1):
            try:
                result = await extract_table(conn, table, output_dir, idx)
            except Exception as e:
                print(f"ERROR extracting {table}: {e}", file=sys.stderr)
                rc = 2
                continue
            results.append(result)
            if result.skipped_reason:
                print(f"  - {table}: SKIPPED ({result.skipped_reason})")
            else:
                print(f"  + {table}: {result.rows_extracted} rows -> "
                      f"{result.output_path.name}")
        print(f"\n[OK] Extracted {len(results)} tables to {output_dir}")
        total_rows = sum(r.rows_extracted for r in results)
        print(f"  Total rows: {total_rows}")
    finally:
        await conn.close()
    return rc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_tables_arg(value: str | None, tier: int) -> list[str]:
    if value:
        return [t.strip() for t in value.split(",") if t.strip()]
    if tier == 1:
        return TIER_1_TABLES
    return TIER_0_TABLES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL (default: $DATABASE_URL).",
    )
    parser.add_argument(
        "--tier", type=int, choices=[0, 1], default=0,
        help="Preset table set: 0=minimum (default), 1=full reference data.",
    )
    parser.add_argument(
        "--tables", default=None,
        help="Comma-separated table names (overrides --tier).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT,
        help=f"Directory for generated SQL (default: {DEFAULT_OUTPUT}).",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        print("ERROR: DATABASE_URL is required (env or --database-url).",
              file=sys.stderr)
        return 1

    tables = parse_tables_arg(args.tables, args.tier)
    if not tables:
        print("ERROR: no tables to extract.", file=sys.stderr)
        return 1

    print(f"Extracting {len(tables)} tables to {args.output_dir}")
    print(f"Tables: {', '.join(tables)}")
    return asyncio.run(main_async(args.database_url, tables, args.output_dir))


if __name__ == "__main__":
    sys.exit(main())
