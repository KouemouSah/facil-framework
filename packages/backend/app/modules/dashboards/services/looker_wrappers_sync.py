"""
Auto-sync Looker view wrappers above MVs at app boot.

Why this exists
---------------
Looker Studio JDBC PostgreSQL connector calls
DatabaseMetaData.getTables(types={"TABLE","VIEW"}) which filters out
relations with relkind='m' (MATERIALIZED VIEW). Even when looker_readonly
has SELECT grants, MVs are invisible in the JDBC table picker — only
plain views (relkind='v') and tables (relkind='r') show up.

Workaround: a thin wrapper VIEW above each MV that should be drag-drop
in Looker. The wrapper has relkind='v' so it appears in the picker;
the planner inlines `SELECT * FROM mv_xxx` so there's zero query cost
overhead and zero storage.

This module does the wrapper creation AUTOMATICALLY on every app boot.
No migration needed — when a developer adds a new MV and grants SELECT
to looker_readonly, the next backend deploy auto-creates the wrapper.

Convention
----------
- Source MV name `mv_xxx` → wrapper `vw_xxx` (drops the mv_ prefix)
- Source MV name `v_xxx` (legacy MVs that already start with v_) → `vw_xxx`
- Source MV name without prefix `xxx` → `vw_xxx`
- Wrapper has SELECT granted to looker_readonly (same as the source MV)

Whitelist
---------
The function only wraps MVs that **already have** SELECT granted to
looker_readonly. This is intentional: the grant is the explicit
"expose this to Looker" signal. MVs without that grant stay hidden.

Idempotent
----------
CREATE OR REPLACE VIEW is the safe primitive. Re-running the sync is
a no-op when the BD is already in the desired state. Logs INFO for
new wrappers, DEBUG for unchanged.

Failure modes
-------------
- looker_readonly role missing: the function logs a warning and exits
  (silent skip — the role doesn't exist yet so no wrapper would be
  consumable anyway).
- Schema drift on an existing wrapper (column rename in the MV):
  CREATE OR REPLACE may fail. The function catches per-wrapper and logs
  a warning so one bad MV doesn't block the others. Manual fix: DROP
  then re-run, or update the underlying MV in a migration.
"""

from __future__ import annotations

from typing import Optional

import asyncpg
from loguru import logger


def _wrapper_name(mv_name: str) -> str:
    """Compute the wrapper view name for a given MV name.

    Convention:
    - "mv_xxx"  → "vw_xxx"
    - "v_xxx"   → "vw_xxx" (legacy)
    - "xxx"     → "vw_xxx" (no prefix on the original)
    """
    if mv_name.startswith("mv_"):
        return f"vw_{mv_name[3:]}"
    if mv_name.startswith("v_"):
        return f"vw_{mv_name[2:]}"
    return f"vw_{mv_name}"


async def sync_looker_view_wrappers(
    conn: asyncpg.Connection,
    *,
    role_name: str = "looker_readonly",
) -> dict[str, list[str]]:
    """Create/refresh wrapper VIEWs above every MV granted to `role_name`.

    Returns:
        dict with keys:
        - "synced":    wrappers that were created or refreshed
        - "skipped":   wrappers that failed (logged as warnings)
        - "orphans":   vw_* views in BD pointing at no MV (informative)
    """
    result: dict[str, list[str]] = {"synced": [], "skipped": [], "orphans": []}

    # 1. Confirm the role exists. If not, the wrappers would be useless —
    #    silent skip is the right behavior.
    role_exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = $1)",
        role_name,
    )
    if not role_exists:
        logger.warning(
            f"looker_wrappers_sync: role '{role_name}' does not exist — skipping. "
            f"Run migration 315 (looker_readonly_role) first."
        )
        return result

    # 2. List MVs that the role can already SELECT from. The grant is the
    #    explicit "expose this to Looker" whitelist.
    rows = await conn.fetch(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'm'
          AND has_table_privilege($1, c.oid, 'SELECT')
        ORDER BY c.relname
        """,
        role_name,
    )
    mvs = [r["relname"] for r in rows]
    logger.info(
        f"looker_wrappers_sync: {len(mvs)} MV(s) granted to {role_name} — "
        f"computing wrappers"
    )

    # 3. Create or replace each wrapper + grant SELECT
    for mv in mvs:
        wrapper = _wrapper_name(mv)
        try:
            # CREATE OR REPLACE is the documented idempotent primitive.
            # Identifiers are SQL-injected via format strings here, but
            # they come exclusively from pg_class introspection (no user
            # input). Postgres rejects identifiers with whitespace, so
            # this is safe.
            await conn.execute(
                f'CREATE OR REPLACE VIEW "{wrapper}" '
                f'AS SELECT * FROM "{mv}"'
            )
            await conn.execute(
                f'GRANT SELECT ON "{wrapper}" TO {role_name}'
            )
            # Cheap doc comment so a curious DBA grepping pg_description
            # immediately sees why this view exists.
            await conn.execute(
                f'COMMENT ON VIEW "{wrapper}" IS '
                f'$$Auto-generated wrapper above {mv} so Looker Studio '
                f'JDBC sees it (relkind=v, not m). Maintained by '
                f'looker_wrappers_sync at app boot.$$'
            )
            result["synced"].append(wrapper)
        except Exception as exc:
            # One bad MV shouldn't poison the whole sync.
            logger.warning(
                f"looker_wrappers_sync: failed to create/grant {wrapper} → {mv}: {exc}"
            )
            result["skipped"].append(wrapper)

    # 4. Find orphan wrappers (vw_* views whose underlying MV no longer
    #    exists or is no longer granted). Informative only — DELETE
    #    behaviour is opt-in and not done here, mirroring the new
    #    non-destructive boot policy (see initialize_permissions).
    orphan_rows = await conn.fetch(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'v'
          AND c.relname LIKE 'vw_%'
          AND obj_description(c.oid, 'pg_class') LIKE 'Auto-generated wrapper%'
        """
    )
    expected_wrappers = {_wrapper_name(mv) for mv in mvs}
    for r in orphan_rows:
        if r["relname"] not in expected_wrappers:
            result["orphans"].append(r["relname"])

    if result["synced"]:
        logger.info(
            f"looker_wrappers_sync: synced {len(result['synced'])} wrapper view(s)"
        )
    if result["skipped"]:
        logger.warning(
            f"looker_wrappers_sync: {len(result['skipped'])} wrapper(s) failed: "
            f"{result['skipped']}"
        )
    if result["orphans"]:
        logger.info(
            f"looker_wrappers_sync: {len(result['orphans'])} orphan wrapper(s) "
            f"(MV granted state changed; not deleting): {result['orphans']}"
        )
    return result
