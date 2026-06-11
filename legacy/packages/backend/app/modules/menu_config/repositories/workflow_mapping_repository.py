"""
Workflow Menu Mapping Repository - Database operations for workflow menu mappings (asyncpg version)
"""
from typing import List, Optional, Dict, Any
import asyncpg

from app.modules.menu_config.models.menu_config import (
    WorkflowMenuMappingCreate,
    WorkflowMenuMappingUpdate,
)


def _row_to_dict(record: asyncpg.Record) -> Optional[Dict[str, Any]]:
    """Convert asyncpg Record to dict."""
    if record is None:
        return None
    return dict(record)


class WorkflowMappingRepository:
    """Repository for workflow menu mapping CRUD operations using asyncpg"""

    def __init__(self, db_connection: asyncpg.Connection):
        """
        Initialize repository with database connection

        Args:
            db_connection: asyncpg connection object
        """
        self.db = db_connection

    async def get_by_id(self, mapping_id: int) -> Optional[Dict[str, Any]]:
        """
        Get workflow mapping by ID

        Args:
            mapping_id: Mapping ID

        Returns:
            Mapping dict or None if not found
        """
        result = await self.db.fetchrow("""
            SELECT id, workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                   display_order, include_pending, include_validation,
                   include_appointments, include_history, include_escalation, include_batch,
                   custom_sub_items, permission_prefix, is_active, created_at, updated_at
            FROM workflow_menu_mapping
            WHERE id = $1
        """, mapping_id)

        return _row_to_dict(result)

    async def get_by_pattern(self, workflow_pattern: str) -> Optional[Dict[str, Any]]:
        """
        Get workflow mapping by pattern

        Args:
            workflow_pattern: Workflow pattern (e.g., 'PASAPORTE_%')

        Returns:
            Mapping dict or None if not found
        """
        result = await self.db.fetchrow("""
            SELECT id, workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                   display_order, include_pending, include_validation,
                   include_appointments, include_history, include_escalation, include_batch,
                   custom_sub_items, permission_prefix, is_active, created_at, updated_at
            FROM workflow_menu_mapping
            WHERE workflow_pattern = $1
        """, workflow_pattern)

        return _row_to_dict(result)

    async def get_all(
        self,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all workflow mappings with optional filters

        Args:
            is_active: Filter by active status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of mapping dicts
        """
        if is_active is not None:
            query = """
                SELECT id, workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                       display_order, include_pending, include_validation,
                       include_appointments, include_history, include_escalation, include_batch,
                       custom_sub_items, permission_prefix,
                       is_active, created_at, updated_at
                FROM workflow_menu_mapping
                WHERE is_active = $1
                ORDER BY display_order, workflow_pattern
                LIMIT $2 OFFSET $3
            """
            results = await self.db.fetch(query, is_active, limit, offset)
        else:
            query = """
                SELECT id, workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                       display_order, include_pending, include_validation,
                       include_appointments, include_history, include_escalation, include_batch,
                       custom_sub_items, permission_prefix,
                       is_active, created_at, updated_at
                FROM workflow_menu_mapping
                ORDER BY display_order, workflow_pattern
                LIMIT $1 OFFSET $2
            """
            results = await self.db.fetch(query, limit, offset)

        return [_row_to_dict(row) for row in results]

    async def get_active_mappings(self) -> List[Dict[str, Any]]:
        """
        Get all active workflow mappings ordered by display order

        Returns:
            List of active mapping dicts
        """
        results = await self.db.fetch("""
            SELECT id, workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                   display_order, include_pending, include_validation,
                   include_appointments, include_history, include_escalation, include_batch,
                   custom_sub_items, permission_prefix, is_active, created_at, updated_at
            FROM workflow_menu_mapping
            WHERE is_active = true
            ORDER BY display_order, workflow_pattern
        """)

        return [_row_to_dict(row) for row in results]

    async def count(self, is_active: Optional[bool] = None) -> int:
        """
        Count workflow mappings

        Args:
            is_active: Filter by active status

        Returns:
            Count of mappings
        """
        if is_active is not None:
            result = await self.db.fetchval(
                "SELECT COUNT(*) FROM workflow_menu_mapping WHERE is_active = $1",
                is_active
            )
        else:
            result = await self.db.fetchval(
                "SELECT COUNT(*) FROM workflow_menu_mapping"
            )

        return result or 0

    async def create(self, mapping: WorkflowMenuMappingCreate) -> Dict[str, Any]:
        """
        Create a new workflow mapping

        Args:
            mapping: Mapping data

        Returns:
            Created mapping dict
        """
        import json
        custom_sub_items_json = json.dumps(
            [item.model_dump() for item in mapping.custom_sub_items]
        ) if mapping.custom_sub_items else '[]'

        result = await self.db.fetchrow("""
            INSERT INTO workflow_menu_mapping (
                workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                display_order, include_pending, include_validation,
                include_appointments, include_history, include_escalation,
                include_batch, custom_sub_items, permission_prefix
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13)
            RETURNING id, workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                      display_order, include_pending, include_validation,
                      include_appointments, include_history, include_escalation, include_batch,
                      custom_sub_items, permission_prefix, is_active, created_at, updated_at
        """,
            mapping.workflow_pattern,
            mapping.menu_group_id,
            mapping.menu_title_key,
            mapping.menu_icon,
            mapping.display_order,
            mapping.include_pending,
            mapping.include_validation,
            mapping.include_appointments,
            mapping.include_history,
            mapping.include_escalation,
            mapping.include_batch,
            custom_sub_items_json,
            mapping.permission_prefix
        )

        return _row_to_dict(result)

    async def update(
        self,
        mapping_id: int,
        mapping: WorkflowMenuMappingUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing workflow mapping

        Args:
            mapping_id: Mapping ID
            mapping: Updated mapping data

        Returns:
            Updated mapping dict or None if not found
        """
        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 0

        if mapping.menu_title_key is not None:
            param_count += 1
            update_fields.append(f"menu_title_key = ${param_count}")
            params.append(mapping.menu_title_key)

        if mapping.menu_icon is not None:
            param_count += 1
            update_fields.append(f"menu_icon = ${param_count}")
            params.append(mapping.menu_icon)

        if mapping.display_order is not None:
            param_count += 1
            update_fields.append(f"display_order = ${param_count}")
            params.append(mapping.display_order)

        if mapping.include_pending is not None:
            param_count += 1
            update_fields.append(f"include_pending = ${param_count}")
            params.append(mapping.include_pending)

        if mapping.include_validation is not None:
            param_count += 1
            update_fields.append(f"include_validation = ${param_count}")
            params.append(mapping.include_validation)

        if mapping.include_appointments is not None:
            param_count += 1
            update_fields.append(f"include_appointments = ${param_count}")
            params.append(mapping.include_appointments)

        if mapping.include_history is not None:
            param_count += 1
            update_fields.append(f"include_history = ${param_count}")
            params.append(mapping.include_history)

        if mapping.include_escalation is not None:
            param_count += 1
            update_fields.append(f"include_escalation = ${param_count}")
            params.append(mapping.include_escalation)

        if mapping.include_batch is not None:
            param_count += 1
            update_fields.append(f"include_batch = ${param_count}")
            params.append(mapping.include_batch)

        if mapping.custom_sub_items is not None:
            import json
            param_count += 1
            update_fields.append(f"custom_sub_items = ${param_count}::jsonb")
            params.append(json.dumps(
                [item.model_dump() for item in mapping.custom_sub_items]
            ))

        if mapping.permission_prefix is not None:
            param_count += 1
            update_fields.append(f"permission_prefix = ${param_count}")
            params.append(mapping.permission_prefix)

        if mapping.is_active is not None:
            param_count += 1
            update_fields.append(f"is_active = ${param_count}")
            params.append(mapping.is_active)

        if not update_fields:
            return await self.get_by_id(mapping_id)

        param_count += 1
        params.append(mapping_id)

        query = f"""
            UPDATE workflow_menu_mapping
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_count}
            RETURNING id, workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                      display_order, include_pending, include_validation,
                      include_appointments, include_history, include_escalation, include_batch,
                      custom_sub_items, permission_prefix, is_active, created_at, updated_at
        """

        result = await self.db.fetchrow(query, *params)
        return _row_to_dict(result)

    async def delete(self, mapping_id: int) -> bool:
        """
        Delete a workflow mapping

        Args:
            mapping_id: Mapping ID

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute("""
            DELETE FROM workflow_menu_mapping
            WHERE id = $1
        """, mapping_id)

        return "DELETE 1" in result

