"""Filter Preset Repository — Data access for supervisor_filter_presets table."""

import logging
from typing import Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class FilterPresetRepository:
    """Data access for supervisor_filter_presets table."""

    # ============================================================
    # CREATE
    # ============================================================

    @staticmethod
    async def create(conn, user_id: UUID, data: Dict) -> Dict:
        """Insert a new filter preset.

        If is_default=true, first unset any existing default
        for this user+table_key combination (unique partial index
        enforces at most one default per user per table_key).
        """
        table_key = data["table_key"]

        # Unset existing default if this preset should be default
        if data.get("is_default"):
            await conn.execute("""
                UPDATE supervisor_filter_presets
                SET is_default = false, updated_at = NOW()
                WHERE user_id = $1
                  AND table_key = $2
                  AND is_default = true
            """, user_id, table_key)

        row = await conn.fetchrow("""
            INSERT INTO supervisor_filter_presets (
                user_id, preset_name, table_key,
                filters, column_visibility, sort_config,
                is_default
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """,
            user_id,
            data["preset_name"],
            table_key,
            __import__("json").dumps(data.get("filters", {})),
            data.get("column_visibility"),
            data.get("sort_config"),
            data.get("is_default", False),
        )
        return dict(row) if row else None

    # ============================================================
    # READ
    # ============================================================

    @staticmethod
    async def get_by_id(conn, preset_id: UUID) -> Optional[Dict]:
        """Get a single preset by ID."""
        row = await conn.fetchrow("""
            SELECT * FROM supervisor_filter_presets
            WHERE id = $1
        """, preset_id)
        return dict(row) if row else None

    @staticmethod
    async def list_by_user(
        conn,
        user_id: UUID,
        table_key: str = None,
    ) -> List[Dict]:
        """List presets for a user, optionally filtered by table_key.

        Ordered: defaults first, then alphabetical by preset_name.
        """
        conditions = ["user_id = $1"]
        params = [user_id]
        idx = 2

        if table_key:
            conditions.append(f"table_key = ${idx}")
            params.append(table_key)
            idx += 1

        where = " AND ".join(conditions)

        rows = await conn.fetch(f"""
            SELECT * FROM supervisor_filter_presets
            WHERE {where}
            ORDER BY is_default DESC, preset_name
        """, *params)

        return [dict(r) for r in rows]

    # ============================================================
    # UPDATE
    # ============================================================

    # Whitelist of columns allowed in updates (prevent SQL injection)
    UPDATABLE_COLUMNS = frozenset({
        "preset_name",
        "filters",
        "column_visibility",
        "sort_config",
        "is_default",
    })

    @staticmethod
    async def update(conn, preset_id: UUID, data: Dict) -> Optional[Dict]:
        """Update a preset (whitelist-protected).

        If is_default is being set to true, unsets any existing
        default for the same user+table_key first.
        """
        if not data:
            return await FilterPresetRepository.get_by_id(conn, preset_id)

        # Reject keys not in the whitelist
        invalid_keys = set(data.keys()) - FilterPresetRepository.UPDATABLE_COLUMNS
        if invalid_keys:
            raise ValueError(
                f"Invalid update columns: {invalid_keys}. "
                f"Allowed: {FilterPresetRepository.UPDATABLE_COLUMNS}"
            )

        # If setting as default, unset existing defaults first
        if data.get("is_default"):
            existing = await FilterPresetRepository.get_by_id(conn, preset_id)
            if existing:
                await conn.execute("""
                    UPDATE supervisor_filter_presets
                    SET is_default = false, updated_at = NOW()
                    WHERE user_id = $1
                      AND table_key = $2
                      AND is_default = true
                      AND id != $3
                """, existing["user_id"], existing["table_key"], preset_id)

        set_clauses = []
        params = []
        idx = 1

        for key, value in data.items():
            set_clauses.append(f"{key} = ${idx}")
            params.append(value)
            idx += 1

        set_clauses.append("updated_at = NOW()")
        params.append(preset_id)

        row = await conn.fetchrow(f"""
            UPDATE supervisor_filter_presets
            SET {', '.join(set_clauses)}
            WHERE id = ${idx}
            RETURNING *
        """, *params)

        return dict(row) if row else None

    # ============================================================
    # DELETE
    # ============================================================

    @staticmethod
    async def delete(conn, preset_id: UUID, user_id: UUID = None) -> bool:
        """Delete a preset. Defense-in-depth: user_id scoped if provided."""
        if user_id:
            result = await conn.execute("""
                DELETE FROM supervisor_filter_presets
                WHERE id = $1 AND user_id = $2
            """, preset_id, user_id)
        else:
            result = await conn.execute("""
                DELETE FROM supervisor_filter_presets
                WHERE id = $1
            """, preset_id)
        # asyncpg returns "DELETE N" where N is the number of rows deleted
        return result == "DELETE 1"
