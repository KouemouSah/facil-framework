"""
Agent Profile Repository - Data access for agent_profiles table

Uses the new agent_profiles table instead of ministry_agents.
Supports both ministry_agent and entity_agent types.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from loguru import logger
import asyncpg
import json

from app.modules.agents.models.agent_profile import (
    AgentProfileCreate,
    AgentProfileUpdate,
    AgentListFilters,
)


class AgentProfileRepository:
    """Repository for agent profiles"""

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    _AGENT_SORT_MAP = {
        "user_full_name": "u.full_name", "user_email": "u.email",
        "entity_name": "e.name", "agent_type": "ap.agent_type",
        "is_active": "ap.is_active", "is_supervisor": "ap.is_supervisor",
        "availability": "aw.availability", "current_assignments": "aw.current_assignments",
        "created_at": "ap.created_at",
    }

    def _resolve_agent_sort(self, sort_by: str | None, sort_order: str) -> str:
        col = self._AGENT_SORT_MAP.get(sort_by or "", "ap.created_at")
        d = "ASC" if sort_order == "asc" else "DESC"
        return f"{col} {d}, ap.created_at DESC"

    def _process_jsonb_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process JSONB and array fields for Pydantic compatibility.

        Converts:
        - specializations: JSONB → List[str]
        - working_days: INTEGER[] → List[int]
        - agent_type: ensure string for enum conversion
        """
        # Process specializations JSONB field
        if 'specializations' in data:
            specs = data['specializations']
            if specs is None:
                data['specializations'] = []
            elif isinstance(specs, str):
                data['specializations'] = json.loads(specs)
            else:
                data['specializations'] = list(specs) if specs else []

        # Process working_days array field
        if 'working_days' in data:
            days = data['working_days']
            if days is None:
                data['working_days'] = [1, 2, 3, 4, 5]
            elif isinstance(days, str):
                data['working_days'] = json.loads(days)
            else:
                data['working_days'] = list(days) if days else [1, 2, 3, 4, 5]

        # Ensure agent_type is a string for enum conversion
        if 'agent_type' in data and data['agent_type'] is not None:
            data['agent_type'] = str(data['agent_type'])

        return data

    # ========================================================================
    # CRUD OPERATIONS
    # ========================================================================

    async def create(
        self,
        conn: asyncpg.Connection,
        profile: AgentProfileCreate,
    ) -> Dict[str, Any]:
        """Create new agent profile"""
        query = """
            INSERT INTO agent_profiles (
                user_id, agent_type, is_supervisor, entity_id, entity_location_id,
                ministry_id,
                can_approve_unlimited, max_approval_amount,
                can_escalate, can_assign_tasks, can_reassign,
                specializations, working_hours_start, working_hours_end,
                working_days, assigned_by, assigned_at, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, NOW(), NOW(), NOW()
            )
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            str(profile.user_id),
            profile.agent_type.value if hasattr(profile.agent_type, 'value') else profile.agent_type,
            profile.is_supervisor,
            str(profile.entity_id) if profile.entity_id else None,
            str(profile.entity_location_id) if profile.entity_location_id else None,
            profile.ministry_id,
            profile.can_approve_unlimited,
            profile.max_approval_amount,
            profile.can_escalate,
            profile.can_assign_tasks,
            profile.can_reassign,
            json.dumps(profile.specializations) if profile.specializations else '[]',
            profile.working_hours_start,
            profile.working_hours_end,
            profile.working_days,
            str(profile.assigned_by) if profile.assigned_by else None,
        )
        data = dict(result)
        return self._process_jsonb_fields(data)

    async def get_by_id(
        self,
        conn: asyncpg.Connection,
        profile_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Get agent profile by ID"""
        query = """
            SELECT * FROM agent_profiles WHERE id = $1
        """
        result = await conn.fetchrow(query, str(profile_id))
        if not result:
            return None
        data = dict(result)
        return self._process_jsonb_fields(data)

    async def get_by_user_id(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        active_only: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Get agent profile by user ID"""
        query = """
            SELECT * FROM agent_profiles
            WHERE user_id = $1
        """
        if active_only:
            query += " AND is_active = true"

        result = await conn.fetchrow(query, str(user_id))
        if not result:
            return None
        data = dict(result)
        return self._process_jsonb_fields(data)

    async def get_with_details(
        self,
        conn: asyncpg.Connection,
        profile_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get agent profile with user, entity, ministry details and available workflows.

        Args:
            conn: Database connection
            profile_id: Agent profile UUID (optional)
            user_id: User UUID to lookup profile by (optional)

        One of profile_id or user_id must be provided.

        Returns agent profile with:
        - User details (email, full_name, phone)
        - Entity details (code, name, type, parent info)
        - Ministry details (code, name)
        - Available workflows (inherited from entity or explicit specializations)
        """
        base_query = """
            SELECT
                ap.*,
                u.email as user_email,
                COALESCE(u.full_name, u.first_name || ' ' || u.last_name) as user_full_name,
                u.phone_number as user_phone,
                e.code as entity_code,
                e.name as entity_name,
                e.entity_type::text as entity_type,
                e.parent_entity_id,
                pe.code as parent_entity_code,
                pe.name as parent_entity_name,
                m.ministry_code,
                m.name_es as ministry_name,
                -- Agent category: use entity code dynamically (lowercase)
                -- No hardcoded values - entity.code is the source of truth
                CASE
                    WHEN e.code IS NOT NULL THEN LOWER(e.code)
                    WHEN ap.agent_type = 'ministry_agent' THEN 'ministry'
                    ELSE 'general'
                END as agent_category,
                aw.current_assignments,
                aw.capacity_percentage,
                aw.workload_status::text,
                aw.availability::text,
                -- Available workflows: specializations if set, otherwise entity workflows
                CASE
                    WHEN ap.specializations IS NOT NULL AND jsonb_array_length(ap.specializations) > 0
                    THEN ap.specializations
                    WHEN e.workflow_codes IS NOT NULL AND jsonb_array_length(e.workflow_codes) > 0
                    THEN e.workflow_codes
                    WHEN pe.workflow_codes IS NOT NULL AND jsonb_array_length(pe.workflow_codes) > 0
                    THEN pe.workflow_codes
                    ELSE '[]'::jsonb
                END as available_workflows_jsonb,
                -- Child entity codes (for parent entities like CNEDOGE)
                ARRAY(
                    SELECT ce.code FROM entities ce
                    WHERE ce.parent_entity_id = e.id AND ce.is_active = true
                ) as child_entity_codes,
                -- Ministry entities (all entities under the same ministry)
                ARRAY(
                    SELECT me.code FROM entities me
                    WHERE me.ministry_id = COALESCE(e.ministry_id, ap.ministry_id)
                    AND me.is_active = true
                ) as ministry_entities,
                el.location_name,
                el.city as location_city,
                el.region as location_region,
                COALESCE(el.is_main_office, false) as is_main_office
            FROM agent_profiles ap
            JOIN users u ON ap.user_id = u.id
            LEFT JOIN entities e ON ap.entity_id = e.id
            LEFT JOIN entities pe ON e.parent_entity_id = pe.id
            -- Ministry: prefer entity's ministry over direct assignment (entity is source of truth)
            LEFT JOIN ministries m ON COALESCE(e.ministry_id, ap.ministry_id) = m.id
            LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
            LEFT JOIN entity_locations el ON ap.entity_location_id = el.id
        """

        if profile_id:
            query = base_query + " WHERE ap.id = $1"
            result = await conn.fetchrow(query, str(profile_id))
        elif user_id:
            query = base_query + " WHERE ap.user_id = $1 AND ap.is_active = true"
            result = await conn.fetchrow(query, str(user_id))
        else:
            raise ValueError("Either profile_id or user_id must be provided")

        if not result:
            return None

        # Convert to dict and process JSONB/array fields
        data = dict(result)

        # Process available_workflows (specific to get_with_details)
        workflows_jsonb = data.pop('available_workflows_jsonb', None)
        if workflows_jsonb:
            if isinstance(workflows_jsonb, str):
                data['available_workflows'] = json.loads(workflows_jsonb)
            elif isinstance(workflows_jsonb, list):
                data['available_workflows'] = workflows_jsonb
            else:
                data['available_workflows'] = list(workflows_jsonb) if workflows_jsonb else []
        else:
            data['available_workflows'] = []

        # Process common JSONB/array fields
        return self._process_jsonb_fields(data)

    async def update(
        self,
        conn: asyncpg.Connection,
        profile_id: UUID,
        update_data: AgentProfileUpdate,
    ) -> Optional[Dict[str, Any]]:
        """Update agent profile"""
        updates = ["updated_at = NOW()"]
        params = [str(profile_id)]
        param_idx = 2

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                if field == 'agent_type' and hasattr(value, 'value'):
                    value = value.value
                elif field == 'specializations':
                    value = json.dumps(value)
                elif field in ['entity_id', 'entity_location_id', 'backup_for_profile_id'] and value:
                    value = str(value)

                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if len(updates) == 1:  # Only updated_at
            return await self.get_by_id(conn, profile_id)

        query = f"""
            UPDATE agent_profiles
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, *params)
        if not result:
            return None

        # Convert to dict and process JSONB/array fields
        data = dict(result)
        return self._process_jsonb_fields(data)

    async def deactivate(
        self,
        conn: asyncpg.Connection,
        profile_id: UUID,
        deactivated_by: UUID,
        reason: Optional[str] = None,
    ) -> bool:
        """Deactivate agent profile"""
        query = """
            UPDATE agent_profiles
            SET is_active = false,
                deactivated_at = NOW(),
                deactivated_by = $2,
                deactivation_reason = $3,
                updated_at = NOW()
            WHERE id = $1
        """
        result = await conn.execute(
            query, str(profile_id), str(deactivated_by), reason
        )
        return result == "UPDATE 1"

    async def reactivate(
        self,
        conn: asyncpg.Connection,
        profile_id: UUID,
    ) -> bool:
        """Reactivate agent profile"""
        query = """
            UPDATE agent_profiles
            SET is_active = true,
                deactivated_at = NULL,
                deactivated_by = NULL,
                deactivation_reason = NULL,
                updated_at = NOW()
            WHERE id = $1
        """
        result = await conn.execute(query, str(profile_id))
        return result == "UPDATE 1"

    # ========================================================================
    # LIST & SEARCH
    # ========================================================================

    async def list_agents(
        self,
        conn: asyncpg.Connection,
        filters: AgentListFilters,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List agent profiles with filters"""
        where_conditions = []
        params = []
        param_idx = 1

        if filters.agent_type:
            where_conditions.append(f"ap.agent_type = ${param_idx}")
            params.append(filters.agent_type.value if hasattr(filters.agent_type, 'value') else filters.agent_type)
            param_idx += 1

        if filters.is_supervisor is not None:
            where_conditions.append(f"ap.is_supervisor = ${param_idx}")
            params.append(filters.is_supervisor)
            param_idx += 1

        if filters.ministry_id:
            where_conditions.append(f"ap.ministry_id = ${param_idx}")
            params.append(filters.ministry_id)
            param_idx += 1

        if filters.entity_id:
            where_conditions.append(f"ap.entity_id = ${param_idx}")
            params.append(str(filters.entity_id))
            param_idx += 1

        if filters.entity_code:
            where_conditions.append(f"e.code = ${param_idx}")
            params.append(filters.entity_code)
            param_idx += 1

        if filters.entity_location_id:
            where_conditions.append(f"ap.entity_location_id = ${param_idx}")
            params.append(str(filters.entity_location_id))
            param_idx += 1

        if filters.is_active is not None:
            where_conditions.append(f"ap.is_active = ${param_idx}")
            params.append(filters.is_active)
            param_idx += 1

        if filters.agent_category:
            category_condition = self._get_category_condition(filters.agent_category, param_idx)
            if category_condition:
                where_conditions.append(category_condition[0])
                params.extend(category_condition[1])
                param_idx += len(category_condition[1])

        if filters.availability:
            where_conditions.append(f"aw.availability::text = ${param_idx}")
            params.append(filters.availability)
            param_idx += 1

        if filters.search:
            # Escape LIKE special characters to prevent pattern injection
            escaped = filters.search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            search_pattern = f"%{escaped}%"
            where_conditions.append(
                f"(u.email ILIKE ${param_idx} OR u.full_name ILIKE ${param_idx})"
            )
            params.append(search_pattern)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # Count query - must include all joins referenced by WHERE conditions
        count_query = f"""
            SELECT COUNT(*)
            FROM agent_profiles ap
            JOIN users u ON ap.user_id = u.id
            LEFT JOIN entities e ON ap.entity_id = e.id
            LEFT JOIN entity_locations el ON ap.entity_location_id = el.id
            LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
            LEFT JOIN ministries m ON COALESCE(e.ministry_id, ap.ministry_id) = m.id
            {where_clause}
        """
        total = await conn.fetchval(count_query, *params)

        # Data query with joins
        params.extend([filters.limit, filters.offset])
        data_query = f"""
            SELECT
                ap.*,
                u.email as user_email,
                u.full_name as user_full_name,
                e.code as entity_code,
                e.name as entity_name,
                el.location_name as location_name,
                el.city as location_city,
                el.region as location_region,
                COALESCE(el.is_main_office, false) as is_main_office,
                m.ministry_code,
                m.name_es as ministry_name,
                -- Agent category: use entity code dynamically (lowercase)
                CASE
                    WHEN e.code IS NOT NULL THEN LOWER(e.code)
                    WHEN ap.agent_type = 'ministry_agent' THEN 'ministry'
                    ELSE 'general'
                END as agent_category,
                aw.current_assignments,
                aw.capacity_percentage,
                aw.workload_status::text,
                aw.availability::text
            FROM agent_profiles ap
            JOIN users u ON ap.user_id = u.id
            LEFT JOIN entities e ON ap.entity_id = e.id
            LEFT JOIN entity_locations el ON ap.entity_location_id = el.id
            LEFT JOIN ministries m ON COALESCE(ap.ministry_id, e.ministry_id) = m.id
            LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
            {where_clause}
            ORDER BY {self._resolve_agent_sort(filters.sort_by, filters.sort_order)}
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """

        results = await conn.fetch(data_query, *params)

        # Process results to handle JSONB fields properly
        processed_results = []
        for row in results:
            data = dict(row)
            # Process common JSONB/array fields
            data = self._process_jsonb_fields(data)
            # Provide default for available_workflows (not returned by this query)
            data['available_workflows'] = []
            processed_results.append(data)

        return processed_results, total

    def _get_category_condition(
        self,
        category: str,
        param_idx: int
    ) -> Optional[tuple[str, list]]:
        """
        Get SQL condition for agent category filter.

        Uses entity_code dynamically - no hardcoded values.
        Entity is the source of truth - ministries can be reorganized.

        Categories:
        - Any entity code (lowercase): Filters by LOWER(e.code) = category
        - 'entity': Agents assigned to any entity
        - 'ministry': Ministry agents without specific entity assignment
        """
        if category == 'entity':
            # All agents with an entity assignment
            return ("e.code IS NOT NULL", [])
        elif category == 'ministry':
            # Ministry agents without direct entity assignment
            return ("ap.agent_type = 'ministry_agent' AND e.code IS NULL", [])
        elif category == 'general':
            # Agents without entity or ministry
            return ("e.code IS NULL AND ap.agent_type != 'ministry_agent'", [])
        else:
            # Dynamic entity code filter (case-insensitive)
            return (f"LOWER(e.code) = LOWER(${param_idx})", [category])

    # ========================================================================
    # ASSIGNMENT & AVAILABILITY
    # ========================================================================

    async def get_available_agents(
        self,
        conn: asyncpg.Connection,
        ministry_id: Optional[int] = None,
        entity_id: Optional[UUID] = None,
        min_approval_amount: Optional[float] = None,
        exclude_overloaded: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get available agents for assignment"""
        where_conditions = [
            "ap.is_active = true",
            "(aw.availability = 'available' OR aw.availability IS NULL)",
        ]
        params = []
        param_idx = 1

        if exclude_overloaded:
            where_conditions.append(
                "(aw.workload_status != 'overloaded' OR aw.workload_status IS NULL)"
            )

        if ministry_id:
            where_conditions.append(f"ap.ministry_id = ${param_idx}")
            params.append(ministry_id)
            param_idx += 1

        if entity_id:
            where_conditions.append(f"ap.entity_id = ${param_idx}")
            params.append(str(entity_id))
            param_idx += 1

        if min_approval_amount is not None:
            where_conditions.append(
                f"(ap.can_approve_unlimited = true OR ap.max_approval_amount >= ${param_idx})"
            )
            params.append(min_approval_amount)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(where_conditions)}"

        query = f"""
            SELECT
                ap.*,
                u.full_name as user_full_name,
                u.email as user_email,
                aw.current_assignments,
                aw.capacity_percentage,
                aw.workload_status::text,
                aw.availability::text,
                m.ministry_code,
                m.name_es as ministry_name,
                e.code as entity_code,
                e.name as entity_name
            FROM agent_profiles ap
            JOIN users u ON ap.user_id = u.id
            LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
            LEFT JOIN ministries m ON ap.ministry_id = m.id
            LEFT JOIN entities e ON ap.entity_id = e.id
            {where_clause}
            ORDER BY
                aw.capacity_percentage ASC NULLS FIRST,
                ap.created_at ASC
        """

        results = await conn.fetch(query, *params)
        return [dict(r) for r in results]

    async def get_supervisors(
        self,
        conn: asyncpg.Connection,
        ministry_id: Optional[int] = None,
        entity_id: Optional[UUID] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get supervisor agents"""
        where_conditions = ["ap.is_supervisor = true"]
        params = []
        param_idx = 1

        if active_only:
            where_conditions.append("ap.is_active = true")

        if ministry_id:
            where_conditions.append(f"ap.ministry_id = ${param_idx}")
            params.append(ministry_id)
            param_idx += 1

        if entity_id:
            where_conditions.append(f"ap.entity_id = ${param_idx}")
            params.append(str(entity_id))
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(where_conditions)}"

        query = f"""
            SELECT
                ap.*,
                u.full_name as user_full_name,
                u.email as user_email,
                m.ministry_code,
                m.name_es as ministry_name,
                e.code as entity_code,
                e.name as entity_name
            FROM agent_profiles ap
            JOIN users u ON ap.user_id = u.id
            LEFT JOIN ministries m ON ap.ministry_id = m.id
            LEFT JOIN entities e ON ap.entity_id = e.id
            {where_clause}
            ORDER BY ap.created_at ASC
        """

        results = await conn.fetch(query, *params)
        return [dict(r) for r in results]

    async def get_backup_agents(
        self,
        conn: asyncpg.Connection,
        primary_profile_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get backup agents for a primary agent"""
        query = """
            SELECT
                ap.*,
                u.full_name as user_full_name,
                u.email as user_email
            FROM agent_profiles ap
            JOIN users u ON ap.user_id = u.id
            WHERE ap.backup_for_profile_id = $1
              AND ap.is_active = true
            ORDER BY ap.created_at ASC
        """
        results = await conn.fetch(query, str(primary_profile_id))
        return [dict(r) for r in results]

    # ========================================================================
    # STATISTICS
    # ========================================================================

    async def count_by_ministry(
        self,
        conn: asyncpg.Connection,
        ministry_id: int,
        active_only: bool = True,
    ) -> Dict[str, int]:
        """Count agents by ministry with breakdown"""
        where_clause = "WHERE ministry_id = $1"
        if active_only:
            where_clause += " AND is_active = true"

        query = f"""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_supervisor = true) as supervisors,
                COUNT(*) FILTER (WHERE is_supervisor = false) as agents
            FROM agent_profiles
            {where_clause}
        """
        result = await conn.fetchrow(query, ministry_id)
        return dict(result) if result else {"total": 0, "supervisors": 0, "agents": 0}

    async def count_by_entity(
        self,
        conn: asyncpg.Connection,
        entity_id: UUID,
        active_only: bool = True,
    ) -> Dict[str, int]:
        """Count agents by entity with breakdown"""
        where_clause = "WHERE entity_id = $1"
        if active_only:
            where_clause += " AND is_active = true"

        query = f"""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_supervisor = true) as supervisors,
                COUNT(*) FILTER (WHERE is_supervisor = false) as agents
            FROM agent_profiles
            {where_clause}
        """
        result = await conn.fetchrow(query, str(entity_id))
        return dict(result) if result else {"total": 0, "supervisors": 0, "agents": 0}


    # ========================================================================
    # CONVENIENCE ALIASES
    # ========================================================================

    async def list_with_details(
        self,
        conn: asyncpg.Connection,
        filters: AgentListFilters,
    ) -> List[Dict[str, Any]]:
        """Alias for list_agents that returns just the data (not total count)"""
        data, _ = await self.list_agents(conn, filters)
        return data

    async def list_available_by_ministry(
        self,
        conn: asyncpg.Connection,
        ministry_id: int,
    ) -> List[Dict[str, Any]]:
        """Get available agents for a ministry"""
        return await self.get_available_agents(conn, ministry_id=ministry_id)

    async def list_available_by_entity(
        self,
        conn: asyncpg.Connection,
        entity_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get available agents for an entity"""
        return await self.get_available_agents(conn, entity_id=entity_id)


# Singleton instance
agent_profile_repository = AgentProfileRepository()
