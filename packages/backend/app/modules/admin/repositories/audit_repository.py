"""Audit Repository - Data access for audit logs"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg
from datetime import datetime

from app.modules.admin.models import AuditLogCreate


class AuditRepository:
    """Repository for audit logs"""

    async def create(
        self,
        conn: asyncpg.Connection,
        audit_log: AuditLogCreate,
    ) -> Dict[str, Any]:
        """Create audit log entry"""
        query = """
            INSERT INTO audit_logs (
                user_id, entity_type, entity_id, action,
                old_values, new_values, ip_address, user_agent,
                created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            audit_log.user_id,
            audit_log.entity_type,
            audit_log.entity_id,
            audit_log.action,
            audit_log.old_values,
            audit_log.new_values,
            audit_log.ip_address,
            audit_log.user_agent,
        )
        return dict(result)

    async def get_by_id(
        self,
        conn: asyncpg.Connection,
        audit_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get audit log by ID"""
        query = """
            SELECT id::text, user_id::text, entity_type, entity_id,
                   action, old_values, new_values,
                   ip_address, user_agent, created_at
            FROM audit_logs WHERE id::text = $1
        """
        result = await conn.fetchrow(query, audit_id)
        return dict(result) if result else None

    async def list(
        self,
        conn: asyncpg.Connection,
        user_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List audit logs with filters"""
        where_clauses = []
        params = []
        param_idx = 1

        if user_id:
            where_clauses.append(f"user_id = ${param_idx}")
            params.append(user_id)
            param_idx += 1

        if entity_type:
            where_clauses.append(f"entity_type = ${param_idx}")
            params.append(entity_type)
            param_idx += 1

        if entity_id:
            where_clauses.append(f"entity_id = ${param_idx}")
            params.append(entity_id)
            param_idx += 1

        if action:
            where_clauses.append(f"action = ${param_idx}")
            params.append(action)
            param_idx += 1

        if start_date:
            where_clauses.append(f"created_at >= ${param_idx}")
            params.append(start_date)
            param_idx += 1

        if end_date:
            where_clauses.append(f"created_at <= ${param_idx}")
            params.append(end_date)
            param_idx += 1

        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Get data with explicit columns (avoid extra columns breaking Pydantic)
        data_query = f"""
            SELECT id::text, user_id::text, entity_type, entity_id,
                   action, old_values, new_values,
                   ip_address, user_agent, created_at
            FROM audit_logs
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        results = await conn.fetch(data_query, *params)

        return [dict(r) for r in results], total

    async def get_by_entity(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all audit logs for a specific entity"""
        query = """
            SELECT id::text, user_id::text, entity_type, entity_id,
                   action, old_values, new_values,
                   ip_address, user_agent, created_at
            FROM audit_logs
            WHERE entity_type = $1 AND entity_id = $2
            ORDER BY created_at DESC
            LIMIT $3
        """
        results = await conn.fetch(query, entity_type, entity_id, limit)
        return [dict(r) for r in results]

    async def get_by_user(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all audit logs for a user"""
        query = """
            SELECT id::text, user_id::text, entity_type, entity_id,
                   action, old_values, new_values,
                   ip_address, user_agent, created_at
            FROM audit_logs
            WHERE user_id::text = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        results = await conn.fetch(query, user_id, limit)
        return [dict(r) for r in results]

    async def get_recent_activity(
        self,
        conn: asyncpg.Connection,
        hours: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent audit activity"""
        query = """
            SELECT id::text, user_id::text, entity_type, entity_id,
                   action, old_values, new_values,
                   ip_address, user_agent, created_at
            FROM audit_logs
            WHERE created_at >= NOW() - MAKE_INTERVAL(hours => $1)
            ORDER BY created_at DESC
            LIMIT $2
        """
        results = await conn.fetch(query, hours, limit)
        return [dict(r) for r in results]

    async def get_stats(
        self,
        conn: asyncpg.Connection,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get audit log statistics"""
        where_clause = "TRUE"
        params = []

        if start_date or end_date:
            conditions = []
            param_idx = 1
            if start_date:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(start_date)
                param_idx += 1
            if end_date:
                conditions.append(f"created_at <= ${param_idx}")
                params.append(end_date)
            where_clause = " AND ".join(conditions)

        # Count by action
        action_query = f"""
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE {where_clause}
            GROUP BY action
            ORDER BY count DESC
        """
        action_results = await conn.fetch(action_query, *params)
        by_action = {(r["action"] or "unknown"): r["count"] for r in action_results}

        # Count by entity type
        entity_query = f"""
            SELECT entity_type, COUNT(*) as count
            FROM audit_logs
            WHERE {where_clause}
            GROUP BY entity_type
            ORDER BY count DESC
        """
        entity_results = await conn.fetch(entity_query, *params)
        by_entity_type = {(r["entity_type"] or "unknown"): r["count"] for r in entity_results}

        # Total count
        total_query = f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"
        total = await conn.fetchval(total_query, *params)

        return {
            "total_logs": total,
            "by_action": by_action,
            "by_entity_type": by_entity_type,
        }

    async def cleanup_old_logs(
        self,
        conn: asyncpg.Connection,
        days: int = 90,
    ) -> int:
        """Delete audit logs older than specified days"""
        query = """
            DELETE FROM audit_logs
            WHERE created_at < NOW() - MAKE_INTERVAL(days => $1)
        """
        result = await conn.execute(query, days)
        count = int(result.split()[-1])
        logger.info(f"Deleted {count} audit logs older than {days} days")
        return count
