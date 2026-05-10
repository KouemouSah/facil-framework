#!/usr/bin/env python3
"""Optional CLI to remove BD permissions not present in any *_permissions.py.

Boot is non-destructive (cleanup_obsolete=False default since 2026-05-04).
This CLI is the explicit, opt-in way to clean up drift when an admin is
sure that obsolete permissions can be deleted.

Usage:
    python scripts/cleanup_obsolete_permissions.py --dry-run   # default
    python scripts/cleanup_obsolete_permissions.py --apply

Memory ref: project_looker_e1_2026_05_04.md, MEMORY rule #36.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env.local")


async def amain(apply_changes: bool) -> int:
    import asyncpg
    from app.modules.permissions.services.permission_registry import (
        PermissionRegistry,
        cleanup_obsolete_permissions,
    )
    # Trigger discovery of all *_permissions.py
    from app.modules.permissions import module_permissions  # noqa: F401

    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            backend_perms = set(PermissionRegistry.get_all_permission_names())
            db_rows = await conn.fetch("SELECT name FROM permissions")
            db_perms = {r['name'] for r in db_rows}
            obsolete = sorted(db_perms - backend_perms)

            logger.info(f"Code registry: {len(backend_perms)} permissions")
            logger.info(f"BD: {len(db_perms)} permissions")
            logger.info(f"Drift (in BD, not in code): {len(obsolete)} permissions")

            if not obsolete:
                logger.success("No drift — nothing to clean up.")
                return 0

            print()
            for name in obsolete:
                print(f"  - {name}")
            print()

            if not apply_changes:
                logger.info(
                    "DRY-RUN: nothing deleted. Re-run with --apply to actually remove "
                    "these permissions and their role/user_permissions assignments."
                )
                return 0

            logger.warning(
                f"⚠️ APPLYING — deleting {len(obsolete)} permissions and CASCADE-removing "
                "their role_permissions / user_permissions / permission_audit_log entries."
            )

            # Set audit context (required by trg_audit_role_permissions)
            admin_row = await conn.fetchrow(
                "SELECT id::text FROM users WHERE role::text IN ('admin','super_admin') "
                "ORDER BY created_at LIMIT 1"
            )
            if admin_row:
                await conn.execute(
                    "SELECT set_config('app.current_user_id', $1, false)",
                    admin_row['id'],
                )

            result = await cleanup_obsolete_permissions(conn)
            logger.success(
                f"Deleted {result['deleted_count']} permissions, "
                f"{result.get('role_permissions_removed', 0)} role assignments removed."
            )
    finally:
        await pool.close()
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Cleanup permissions in BD that aren't in the code registry."
    )
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="Actually delete (destructive).")
    g.add_argument("--dry-run", action="store_true", help="Default — list only, do not delete.")
    args = parser.parse_args()

    return asyncio.run(amain(apply_changes=args.apply))


if __name__ == "__main__":
    sys.exit(main())
