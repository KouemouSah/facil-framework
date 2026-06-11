"""System Repository - Data access for system rules and configuration"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg
from datetime import date

from app.modules.admin.models import (
    SystemRuleCreate,
    SystemRuleUpdate,
    SystemRuleCategory,
)


class SystemRepository:
    """Repository for system rules and configuration"""

    # ========================================================================
    # SYSTEM RULES
    # ========================================================================

    async def create_rule(
        self,
        conn: asyncpg.Connection,
        rule: SystemRuleCreate,
    ) -> Dict[str, Any]:
        """Create system rule"""
        query = """
            INSERT INTO system_rules (
                rule_code, rule_category, name_es, name_fr, name_en,
                description, rule_value, value_type, applies_to,
                effective_from, effective_until, is_active, created_by,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            rule.rule_code,
            rule.rule_category.value,
            rule.name_es,
            rule.name_fr,
            rule.name_en,
            rule.description,
            rule.rule_value,
            rule.value_type.value,
            rule.applies_to,
            rule.effective_from,
            rule.effective_until,
            rule.is_active,
            rule.created_by,
        )
        return dict(result)

    async def get_rule_by_id(
        self,
        conn: asyncpg.Connection,
        rule_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Get system rule by ID"""
        query = """
            SELECT * FROM system_rules WHERE id = $1
        """
        result = await conn.fetchrow(query, rule_id)
        return dict(result) if result else None

    async def get_rule_by_code(
        self,
        conn: asyncpg.Connection,
        rule_code: str,
    ) -> Optional[Dict[str, Any]]:
        """Get active system rule by code"""
        query = """
            SELECT * FROM system_rules
            WHERE rule_code = $1
              AND is_active = true
              AND effective_from <= CURRENT_DATE
              AND (effective_until IS NULL OR effective_until >= CURRENT_DATE)
            ORDER BY effective_from DESC
            LIMIT 1
        """
        result = await conn.fetchrow(query, rule_code)
        return dict(result) if result else None

    async def list_rules(
        self,
        conn: asyncpg.Connection,
        category: Optional[SystemRuleCategory] = None,
        is_active: Optional[bool] = None,
        applies_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List system rules with filters"""
        where_clauses = []
        params = []
        param_idx = 1

        if category:
            where_clauses.append(f"rule_category = ${param_idx}")
            params.append(category.value)
            param_idx += 1

        if is_active is not None:
            where_clauses.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if applies_to:
            where_clauses.append(f"applies_to = ${param_idx}")
            params.append(applies_to)
            param_idx += 1

        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM system_rules WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Get data
        data_query = f"""
            SELECT * FROM system_rules
            WHERE {where_clause}
            ORDER BY rule_category, rule_code
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        results = await conn.fetch(data_query, *params)

        return [dict(r) for r in results], total

    async def update_rule(
        self,
        conn: asyncpg.Connection,
        rule_id: int,
        update_data: SystemRuleUpdate,
    ) -> Optional[Dict[str, Any]]:
        """Update system rule"""
        updates = []
        params = [rule_id]
        param_idx = 2

        for field, value in update_data.dict(exclude_unset=True).items():
            if value is not None:
                if field in ["rule_category", "value_type"]:
                    value = value.value if hasattr(value, "value") else value
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_rule_by_id(conn, rule_id)

        updates.append(f"updated_at = ${param_idx}")
        params.append("NOW()")

        query = f"""
            UPDATE system_rules
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def delete_rule(
        self,
        conn: asyncpg.Connection,
        rule_id: int,
    ) -> bool:
        """Soft delete system rule (set is_active = false)"""
        query = """
            UPDATE system_rules
            SET is_active = false,
                updated_at = NOW()
            WHERE id = $1
        """
        result = await conn.execute(query, rule_id)
        return result == "UPDATE 1"

    async def get_active_rules_by_category(
        self,
        conn: asyncpg.Connection,
        category: SystemRuleCategory,
    ) -> List[Dict[str, Any]]:
        """Get all active rules for a category"""
        query = """
            SELECT * FROM system_rules
            WHERE rule_category = $1
              AND is_active = true
              AND effective_from <= CURRENT_DATE
              AND (effective_until IS NULL OR effective_until >= CURRENT_DATE)
            ORDER BY rule_code
        """
        results = await conn.fetch(query, category.value)
        return [dict(r) for r in results]

    # ========================================================================
    # SYSTEM CONFIGURATION
    # ========================================================================

    async def get_system_info(
        self,
        conn: asyncpg.Connection,
    ) -> Dict[str, Any]:
        """Get system information and statistics"""
        # Count users
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")

        # Count declarations (if table exists)
        try:
            declarations_count = await conn.fetchval("SELECT COUNT(*) FROM tax_declarations")
        except:
            declarations_count = 0

        # Count service_payments (active payment system)
        try:
            payments_count = await conn.fetchval("SELECT COUNT(*) FROM service_payments")
        except Exception:
            payments_count = 0

        # Database size
        db_size = await conn.fetchval("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """)

        return {
            "total_users": users_count,
            "total_declarations": declarations_count,
            "total_payments": payments_count,
            "database_size": db_size,
            "database_name": await conn.fetchval("SELECT current_database()"),
        }

    async def execute_migration(
        self,
        conn: asyncpg.Connection,
        migration_sql: str,
    ) -> Dict[str, Any]:
        """Execute database migration (use with caution)"""
        try:
            result = await conn.execute(migration_sql)
            return {
                "success": True,
                "result": result,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            return {
                "success": False,
                "result": None,
                "error": str(e),
            }

    async def vacuum_analyze(
        self,
        conn: asyncpg.Connection,
    ) -> Dict[str, Any]:
        """Run VACUUM ANALYZE for database maintenance"""
        try:
            await conn.execute("VACUUM ANALYZE")
            return {
                "success": True,
                "message": "VACUUM ANALYZE completed successfully",
            }
        except Exception as e:
            logger.error(f"VACUUM ANALYZE failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_table_sizes(
        self,
        conn: asyncpg.Connection,
    ) -> List[Dict[str, Any]]:
        """Get sizes of all tables"""
        query = """
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY size_bytes DESC
            LIMIT 50
        """
        results = await conn.fetch(query)
        return [dict(r) for r in results]
