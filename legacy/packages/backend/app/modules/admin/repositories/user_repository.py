"""User Repository - Data access for user management"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg

from app.modules.admin.models import (
    UserCreate,
    UserUpdate,
    UserRole,
    UserStatus,
)


# All user columns EXCEPT security secrets (password_hash, 2FA secrets, reset tokens)
# These columns are safe to return in API responses via Pydantic filtering.
_USER_SAFE_COLUMNS = """
    id, email, first_name, last_name, full_name, matricule,
    phone_number, document_type, document_number, role, status,
    preferred_language, email_notifications, push_notifications, sms_notifications,
    email_verified, phone_verified, last_login, failed_login_attempts,
    locked_until, address, city, avatar_url, two_factor_enabled,
    supervisor_id, department_id, specializations, max_concurrent_assignments,
    role_id, matricula_funcionario, funcionario_verified_at, funcionario_verified_by,
    created_at, updated_at
"""


class UserRepository:
    """Repository for user management (admin operations)"""

    async def create(
        self,
        conn: asyncpg.Connection,
        user: UserCreate,
        password_hash: str,
    ) -> Dict[str, Any]:
        """Create new user (admin only - cannot create citizen/business)"""
        # Prevent creation of citizen and business via admin
        if user.role in [UserRole.CITIZEN, UserRole.BUSINESS]:
            raise ValueError("Citizens and businesses must self-register via /api/auth/register")

        query = """
            INSERT INTO users (
                email, password_hash, first_name, last_name, phone_number,
                document_type, document_number, role, status, preferred_language,
                email_notifications, push_notifications, address, city,
                avatar_url, matricule, email_verified, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, NOW(), NOW())
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            user.email,
            password_hash,
            user.first_name,
            user.last_name,
            user.phone_number,
            user.document_type,
            user.document_number,
            user.role.value,
            user.status.value,
            user.preferred_language,
            user.email_notifications,
            user.push_notifications,
            user.address,
            user.city,
            user.avatar_url,
            user.matricule,
            True,  # Admin-created users are auto-verified
        )
        return dict(result)

    async def get_by_id(
        self,
        conn: asyncpg.Connection,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        query = f"SELECT {_USER_SAFE_COLUMNS} FROM users WHERE id = $1"
        result = await conn.fetchrow(query, user_id)
        return dict(result) if result else None

    async def get_by_email(
        self,
        conn: asyncpg.Connection,
        email: str,
    ) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        query = f"SELECT {_USER_SAFE_COLUMNS} FROM users WHERE email = $1"
        result = await conn.fetchrow(query, email)
        return dict(result) if result else None

    async def list(
        self,
        conn: asyncpg.Connection,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List users with filters"""
        where_clauses = []
        params = []
        param_idx = 1

        if role:
            where_clauses.append(f"role = ${param_idx}")
            params.append(role.value)
            param_idx += 1

        if status:
            where_clauses.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1

        if search:
            where_clauses.append(
                f"(email ILIKE ${param_idx} OR first_name ILIKE ${param_idx} OR last_name ILIKE ${param_idx} OR matricule ILIKE ${param_idx})"
            )
            params.append(f"%{search}%")
            param_idx += 1

        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM users WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Get data
        data_query = f"""
            SELECT {_USER_SAFE_COLUMNS} FROM users
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        results = await conn.fetch(data_query, *params)

        return [dict(r) for r in results], total

    async def update(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        update_data: UserUpdate,
    ) -> Optional[Dict[str, Any]]:
        """Update user"""
        updates = []
        params = [user_id]
        param_idx = 2

        for field, value in update_data.dict(exclude_unset=True).items():
            if value is not None:
                if field == "role" or field == "status":
                    value = value.value if hasattr(value, "value") else value
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_by_id(conn, user_id)

        updates.append(f"updated_at = ${param_idx}")
        params.append(datetime.now(timezone.utc))

        query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def delete(
        self,
        conn: asyncpg.Connection,
        user_id: str,
    ) -> bool:
        """Delete user (soft delete by setting status to deactivated)"""
        query = """
            UPDATE users
            SET status = 'deactivated',
                updated_at = NOW()
            WHERE id = $1
        """
        result = await conn.execute(query, user_id)
        return result == "UPDATE 1"

    async def hard_delete(
        self,
        conn: asyncpg.Connection,
        user_id: str,
    ) -> bool:
        """Permanently delete user (use with caution)"""
        query = """
            DELETE FROM users WHERE id = $1
        """
        result = await conn.execute(query, user_id)
        return result == "DELETE 1"

    async def get_stats(
        self,
        conn: asyncpg.Connection,
    ) -> Dict[str, Any]:
        """Get user statistics"""
        stats_query = """
            SELECT
                COUNT(*) as total_users,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_users,
                COUNT(CASE WHEN email_verified = true THEN 1 END) as verified_users,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as new_users_last_30_days,
                COUNT(CASE WHEN locked_until > NOW() THEN 1 END) as locked_users
            FROM users
        """
        stats = await conn.fetchrow(stats_query)

        # Count by role
        role_query = """
            SELECT role, COUNT(*) as count
            FROM users
            GROUP BY role
        """
        role_results = await conn.fetch(role_query)
        by_role = {r["role"]: r["count"] for r in role_results}

        # Count by status
        status_query = """
            SELECT status, COUNT(*) as count
            FROM users
            GROUP BY status
        """
        status_results = await conn.fetch(status_query)
        by_status = {r["status"]: r["count"] for r in status_results}

        return {
            "total_users": stats["total_users"],
            "active_users": stats["active_users"],
            "verified_users": stats["verified_users"],
            "new_users_last_30_days": stats["new_users_last_30_days"],
            "locked_users": stats["locked_users"],
            "by_role": by_role,
            "by_status": by_status,
        }

    async def reset_password(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        new_password_hash: str,
    ) -> bool:
        """Reset user password (admin operation)"""
        query = """
            UPDATE users
            SET password_hash = $2,
                updated_at = NOW()
            WHERE id = $1
        """
        result = await conn.execute(query, user_id, new_password_hash)
        return result == "UPDATE 1"

    async def unlock_account(
        self,
        conn: asyncpg.Connection,
        user_id: str,
    ) -> bool:
        """Unlock user account"""
        query = """
            UPDATE users
            SET locked_until = NULL,
                failed_login_attempts = 0,
                updated_at = NOW()
            WHERE id = $1
        """
        result = await conn.execute(query, user_id)
        return result == "UPDATE 1"

    async def bulk_update_status(
        self,
        conn: asyncpg.Connection,
        user_ids: List[str],
        new_status: UserStatus,
    ) -> int:
        """Bulk update user status"""
        query = """
            UPDATE users
            SET status = $2,
                updated_at = NOW()
            WHERE id = ANY($1)
        """
        result = await conn.execute(query, user_ids, new_status.value)
        count = int(result.split()[-1])
        return count

    async def search_users(
        self,
        conn: asyncpg.Connection,
        search_term: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search users by email, name, or matricule"""
        query = f"""
            SELECT {_USER_SAFE_COLUMNS} FROM users
            WHERE email ILIKE $1
               OR first_name ILIKE $1
               OR last_name ILIKE $1
               OR matricule ILIKE $1
               OR full_name ILIKE $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        results = await conn.fetch(query, f"%{search_term}%", limit)
        return [dict(r) for r in results]
