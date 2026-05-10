"""
Permission Simulator — Phase 3.4 RBAC Engine Core

Simulates the impact of RBAC changes BEFORE applying them.
Answers: "If I grant/revoke permission X to role Y, who is affected?"

Usage:
    POST /permissions/simulate
    {
        "action": "grant",
        "target_type": "role",
        "target_id": "role-uuid",
        "permission_names": ["service_requests.approve"]
    }
    →
    {
        "affected_users": [...],
        "permissions_before": {...},
        "permissions_after": {...},
        "diff": {added: [...], removed: [...]}
    }
"""
from typing import List, Dict, Any, Optional, Set
from loguru import logger
import asyncpg


class PermissionSimulator:
    """Simulates RBAC changes without applying them."""

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def simulate_role_permission_change(
        self,
        role_id: str,
        permission_names: List[str],
        action: str,  # "grant" or "revoke"
    ) -> Dict[str, Any]:
        """
        Simulate granting/revoking permissions on a role.

        Returns list of affected users with before/after permission diffs.
        """
        # 1. Find all active users with this role (direct or via hierarchy)
        affected_users = await self.db.fetch("""
            WITH RECURSIVE role_tree AS (
                SELECT id FROM roles WHERE id = $1::uuid
                UNION ALL
                SELECT r.id FROM roles r JOIN role_tree rt ON r.parent_role_id = rt.id
            )
            SELECT u.id, u.email, u.full_name, r.code as role_code
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.role_id IN (SELECT id FROM role_tree)
              AND u.status != 'deactivated'
            ORDER BY u.full_name
        """, role_id)

        if not affected_users:
            return {
                "affected_users_count": 0,
                "affected_users": [],
                "action": action,
                "permission_names": permission_names,
            }

        # 2. Batch-fetch current permissions for all affected users (1 query instead of N)
        user_ids = [str(u["id"]) for u in affected_users]
        all_perms = await self._get_effective_permissions_batch(user_ids)

        results = []
        for user in affected_users:
            user_id = str(user["id"])
            current_perms = all_perms.get(user_id, set())

            # Simulate the change
            if action == "grant":
                after_perms = current_perms | set(permission_names)
            elif action == "revoke":
                after_perms = current_perms - set(permission_names)
            else:
                after_perms = current_perms

            added = sorted(after_perms - current_perms)
            removed = sorted(current_perms - after_perms)

            if added or removed:
                results.append({
                    "user_id": user_id,
                    "email": user["email"],
                    "full_name": user["full_name"],
                    "role_code": user["role_code"],
                    "added": added,
                    "removed": removed,
                    "total_before": len(current_perms),
                    "total_after": len(after_perms),
                })

        return {
            "action": action,
            "permission_names": permission_names,
            "role_id": role_id,
            "affected_users_count": len(results),
            "affected_users": results,
        }

    async def simulate_user_role_change(
        self,
        user_id: str,
        new_role_id: str,
    ) -> Dict[str, Any]:
        """
        Simulate changing a user's role.

        Returns before/after permission diff for that user.
        """
        # Current permissions
        current_perms = await self._get_effective_permissions(user_id)

        # Permissions from new role (recursive hierarchy)
        new_role_perms_rows = await self.db.fetch("""
            WITH RECURSIVE role_chain AS (
                SELECT id, parent_role_id FROM roles WHERE id = $1::uuid
                UNION ALL
                SELECT parent.id, parent.parent_role_id
                FROM roles parent
                JOIN role_chain child ON child.parent_role_id = parent.id
            )
            SELECT DISTINCT p.name
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            WHERE rp.role_id IN (SELECT id FROM role_chain)
              AND rp.granted = TRUE
        """, new_role_id)
        new_role_perms = {r["name"] for r in new_role_perms_rows}

        # User-specific overrides remain (grants added, denies removed)
        user_grants = await self.db.fetch("""
            SELECT p.name FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = $1::uuid AND up.granted = TRUE
              AND (up.expires_at IS NULL OR up.expires_at >= NOW())
        """, user_id)
        user_denies = await self.db.fetch("""
            SELECT p.name FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = $1::uuid AND up.granted = FALSE
              AND (up.expires_at IS NULL OR up.expires_at >= NOW())
        """, user_id)

        grant_names = {r["name"] for r in user_grants}
        deny_names = {r["name"] for r in user_denies}

        after_perms = (new_role_perms - deny_names) | grant_names

        # Get user info
        user_info = await self.db.fetchrow(
            "SELECT email, full_name FROM users WHERE id = $1::uuid", user_id
        )

        # Get role info
        new_role = await self.db.fetchrow(
            "SELECT code, name FROM roles WHERE id = $1::uuid", new_role_id
        )

        added = sorted(after_perms - current_perms)
        removed = sorted(current_perms - after_perms)

        return {
            "action": "role_change",
            "user_id": user_id,
            "email": user_info["email"] if user_info else None,
            "full_name": user_info["full_name"] if user_info else None,
            "new_role": {
                "id": new_role_id,
                "code": new_role["code"] if new_role else None,
                "name": new_role["name"] if new_role else None,
            },
            "added": added,
            "removed": removed,
            "total_before": len(current_perms),
            "total_after": len(after_perms),
            "unchanged": len(current_perms & after_perms),
        }

    async def _get_effective_permissions_batch(self, user_ids: List[str]) -> Dict[str, Set[str]]:
        """Get effective permissions for multiple users in 1 query (uses materialized view with CTE fallback)."""
        # Try materialized view first (O(1) per user)
        try:
            rows = await self.db.fetch("""
                SELECT user_id::text, permission_name
                FROM effective_permissions_mv
                WHERE user_id = ANY($1::uuid[])
            """, user_ids)
            result: Dict[str, Set[str]] = {}
            for row in rows:
                uid = row["user_id"]
                if uid not in result:
                    result[uid] = set()
                result[uid].add(row["permission_name"])
            return result
        except Exception:
            # MV doesn't exist yet — fall back to per-user CTE
            result = {}
            for uid in user_ids:
                result[uid] = await self._get_effective_permissions(uid)
            return result

    async def _get_effective_permissions(self, user_id: str) -> Set[str]:
        """Get the effective permission set for a user (role hierarchy + overrides)."""
        rows = await self.db.fetch("""
            WITH RECURSIVE role_chain AS MATERIALIZED (
                SELECT r.id, r.parent_role_id
                FROM users u JOIN roles r ON r.id = u.role_id
                WHERE u.id = $1::uuid AND u.status != 'deactivated'
                UNION ALL
                SELECT parent.id, parent.parent_role_id
                FROM roles parent
                JOIN role_chain child ON child.parent_role_id = parent.id
            ),
            role_perms AS MATERIALIZED (
                SELECT DISTINCT p.name
                FROM role_permissions rp
                JOIN permissions p ON rp.permission_id = p.id
                WHERE rp.role_id IN (SELECT id FROM role_chain)
                  AND rp.granted = TRUE
            ),
            user_denies AS MATERIALIZED (
                SELECT p.name FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = $1::uuid AND up.granted = FALSE
                  AND (up.expires_at IS NULL OR up.expires_at >= NOW())
            ),
            user_grants AS MATERIALIZED (
                SELECT p.name FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = $1::uuid AND up.granted = TRUE
                  AND (up.expires_at IS NULL OR up.expires_at >= NOW())
            )
            SELECT name FROM role_perms
            WHERE name NOT IN (SELECT name FROM user_denies)
            UNION
            SELECT name FROM user_grants
        """, user_id)
        return {r["name"] for r in rows}
