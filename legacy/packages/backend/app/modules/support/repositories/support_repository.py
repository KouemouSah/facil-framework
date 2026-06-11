"""
Support Repository

Data access layer for support module (tickets, categories, messages)
"""

import asyncpg
from typing import Optional, List, Tuple
from datetime import datetime
from uuid import UUID
from loguru import logger


class SupportRepository:
    """
    Repository for support module database operations.

    Handles CRUD for:
    - support_categories
    - support_tickets
    - support_messages
    - support_attachments
    """

    # ===========================================================================
    # CATEGORY OPERATIONS
    # ===========================================================================

    async def create_category(
        self,
        db: asyncpg.Connection,
        code: str,
        name_es: str,
        name_fr: Optional[str],
        name_en: Optional[str],
        description_es: Optional[str],
        description_fr: Optional[str],
        description_en: Optional[str],
        target_role: str,
        icon: Optional[str],
        is_active: bool,
        sort_order: int
    ) -> dict:
        """Create a new support category"""
        query = """
            INSERT INTO support_categories (
                code, name_es, name_fr, name_en,
                description_es, description_fr, description_en,
                target_role, icon, is_active, sort_order
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
        """
        row = await db.fetchrow(
            query, code, name_es, name_fr, name_en,
            description_es, description_fr, description_en,
            target_role, icon, is_active, sort_order
        )
        return dict(row) if row else None

    async def get_category_by_id(self, db: asyncpg.Connection, category_id: int) -> Optional[dict]:
        """Get category by ID"""
        query = "SELECT * FROM support_categories WHERE id = $1"
        row = await db.fetchrow(query, category_id)
        return dict(row) if row else None

    async def get_category_by_code(self, db: asyncpg.Connection, code: str) -> Optional[dict]:
        """Get category by code"""
        query = "SELECT * FROM support_categories WHERE code = $1"
        row = await db.fetchrow(query, code)
        return dict(row) if row else None

    async def list_categories(
        self,
        db: asyncpg.Connection,
        is_active: Optional[bool] = None,
        target_role: Optional[str] = None
    ) -> List[dict]:
        """List all categories with optional filters"""
        query = "SELECT * FROM support_categories WHERE 1=1"
        params = []
        param_idx = 1

        if is_active is not None:
            query += f" AND is_active = ${param_idx}"
            params.append(is_active)
            param_idx += 1

        if target_role:
            query += f" AND (target_role = ${param_idx} OR target_role = 'all')"
            params.append(target_role)
            param_idx += 1

        query += " ORDER BY sort_order, name_es"
        rows = await db.fetch(query, *params)
        return [dict(row) for row in rows]

    async def update_category(
        self,
        db: asyncpg.Connection,
        category_id: int,
        updates: dict
    ) -> Optional[dict]:
        """Update a category"""
        if not updates:
            return await self.get_category_by_id(db, category_id)

        set_clauses = []
        params = []
        param_idx = 1

        for key, value in updates.items():
            if value is not None:
                set_clauses.append(f"{key} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not set_clauses:
            return await self.get_category_by_id(db, category_id)

        params.append(category_id)
        query = f"""
            UPDATE support_categories
            SET {', '.join(set_clauses)}
            WHERE id = ${param_idx}
            RETURNING *
        """
        row = await db.fetchrow(query, *params)
        return dict(row) if row else None

    async def delete_category(self, db: asyncpg.Connection, category_id: int) -> bool:
        """Delete a category"""
        query = "DELETE FROM support_categories WHERE id = $1"
        result = await db.execute(query, category_id)
        return result == "DELETE 1"

    # ===========================================================================
    # TICKET OPERATIONS
    # ===========================================================================

    async def generate_ticket_number(self, db: asyncpg.Connection) -> str:
        """Generate unique ticket number: SUP-YYYYMMDD-XXXX"""
        today = datetime.now().strftime("%Y%m%d")
        query = """
            SELECT COUNT(*) + 1 as next_num
            FROM support_tickets
            WHERE ticket_number LIKE $1
        """
        row = await db.fetchrow(query, f"SUP-{today}-%")
        next_num = row['next_num'] if row else 1
        return f"SUP-{today}-{str(next_num).zfill(4)}"

    async def create_ticket(
        self,
        db: asyncpg.Connection,
        ticket_number: str,
        category_id: int,
        subject: str,
        description: str,
        priority: str,
        created_by: UUID
    ) -> dict:
        """Create a new support ticket"""
        query = """
            INSERT INTO support_tickets (
                ticket_number, category_id, subject, description,
                priority, status, created_by
            )
            VALUES ($1, $2, $3, $4, $5, 'open', $6)
            RETURNING *
        """
        row = await db.fetchrow(
            query, ticket_number, category_id, subject,
            description, priority, created_by
        )
        return dict(row) if row else None

    async def get_ticket_by_id(self, db: asyncpg.Connection, ticket_id: int) -> Optional[dict]:
        """Get ticket by ID with category and user info"""
        query = """
            SELECT
                t.*,
                c.name_es as category_name,
                u1.full_name as created_by_name,
                u2.full_name as assigned_to_name,
                (SELECT COUNT(*) FROM support_messages WHERE ticket_id = t.id) as message_count
            FROM support_tickets t
            LEFT JOIN support_categories c ON t.category_id = c.id
            LEFT JOIN users u1 ON t.created_by = u1.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE t.id = $1
        """
        row = await db.fetchrow(query, ticket_id)
        return dict(row) if row else None

    async def get_ticket_by_number(self, db: asyncpg.Connection, ticket_number: str) -> Optional[dict]:
        """Get ticket by ticket number"""
        query = """
            SELECT
                t.*,
                c.name_es as category_name,
                u1.full_name as created_by_name,
                u2.full_name as assigned_to_name,
                (SELECT COUNT(*) FROM support_messages WHERE ticket_id = t.id) as message_count
            FROM support_tickets t
            LEFT JOIN support_categories c ON t.category_id = c.id
            LEFT JOIN users u1 ON t.created_by = u1.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE t.ticket_number = $1
        """
        row = await db.fetchrow(query, ticket_number)
        return dict(row) if row else None

    async def list_tickets(
        self,
        db: asyncpg.Connection,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category_id: Optional[int] = None,
        created_by: Optional[UUID] = None,
        assigned_to: Optional[UUID] = None,
        search: Optional[str] = None
    ) -> Tuple[List[dict], int]:
        """List tickets with pagination and filters"""
        # Build WHERE clause
        where_clauses = ["1=1"]
        params = []
        param_idx = 1

        if status:
            where_clauses.append(f"t.status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if priority:
            where_clauses.append(f"t.priority = ${param_idx}")
            params.append(priority)
            param_idx += 1

        if category_id:
            where_clauses.append(f"t.category_id = ${param_idx}")
            params.append(category_id)
            param_idx += 1

        if created_by:
            where_clauses.append(f"t.created_by = ${param_idx}")
            params.append(created_by)
            param_idx += 1

        if assigned_to:
            where_clauses.append(f"t.assigned_to = ${param_idx}")
            params.append(assigned_to)
            param_idx += 1

        if search:
            where_clauses.append(
                f"(t.ticket_number ILIKE ${param_idx} OR t.subject ILIKE ${param_idx} OR t.description ILIKE ${param_idx})"
            )
            params.append(f"%{search}%")
            param_idx += 1

        where_sql = " AND ".join(where_clauses)

        # Count query
        count_query = f"SELECT COUNT(*) FROM support_tickets t WHERE {where_sql}"
        count_row = await db.fetchrow(count_query, *params)
        total = count_row['count'] if count_row else 0

        # Data query with pagination
        offset = (page - 1) * page_size
        data_query = f"""
            SELECT
                t.*,
                c.name_es as category_name,
                u1.full_name as created_by_name,
                u2.full_name as assigned_to_name,
                (SELECT COUNT(*) FROM support_messages WHERE ticket_id = t.id) as message_count
            FROM support_tickets t
            LEFT JOIN support_categories c ON t.category_id = c.id
            LEFT JOIN users u1 ON t.created_by = u1.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE {where_sql}
            ORDER BY
                CASE t.priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'normal' THEN 3
                    WHEN 'low' THEN 4
                END,
                t.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await db.fetch(data_query, *params)
        return [dict(row) for row in rows], total

    async def update_ticket(
        self,
        db: asyncpg.Connection,
        ticket_id: int,
        updates: dict
    ) -> Optional[dict]:
        """Update a ticket"""
        if not updates:
            return await self.get_ticket_by_id(db, ticket_id)

        set_clauses = ["updated_at = NOW()"]
        params = []
        param_idx = 1

        for key, value in updates.items():
            if value is not None:
                set_clauses.append(f"{key} = ${param_idx}")
                params.append(value)
                param_idx += 1

        # Handle status transitions
        if 'status' in updates:
            if updates['status'] == 'resolved':
                set_clauses.append(f"resolved_at = NOW()")
            elif updates['status'] == 'closed':
                set_clauses.append(f"closed_at = NOW()")

        params.append(ticket_id)
        query = f"""
            UPDATE support_tickets
            SET {', '.join(set_clauses)}
            WHERE id = ${param_idx}
            RETURNING *
        """
        row = await db.fetchrow(query, *params)
        return dict(row) if row else None

    async def delete_ticket(self, db: asyncpg.Connection, ticket_id: int) -> bool:
        """Delete a ticket and all associated messages/attachments"""
        query = "DELETE FROM support_tickets WHERE id = $1"
        result = await db.execute(query, ticket_id)
        return result == "DELETE 1"

    # ===========================================================================
    # MESSAGE OPERATIONS
    # ===========================================================================

    async def create_message(
        self,
        db: asyncpg.Connection,
        ticket_id: int,
        sender_id: UUID,
        content: str,
        is_internal: bool = False
    ) -> dict:
        """Create a new message in a ticket"""
        query = """
            INSERT INTO support_messages (ticket_id, sender_id, content, is_internal)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """
        row = await db.fetchrow(query, ticket_id, sender_id, content, is_internal)
        return dict(row) if row else None

    async def get_message_by_id(self, db: asyncpg.Connection, message_id: int) -> Optional[dict]:
        """Get message by ID"""
        query = """
            SELECT
                m.*,
                u.full_name as sender_name,
                u.role as sender_role
            FROM support_messages m
            LEFT JOIN users u ON m.sender_id = u.id
            WHERE m.id = $1
        """
        row = await db.fetchrow(query, message_id)
        return dict(row) if row else None

    async def list_messages(
        self,
        db: asyncpg.Connection,
        ticket_id: int,
        include_internal: bool = False
    ) -> List[dict]:
        """List all messages for a ticket"""
        query = """
            SELECT
                m.*,
                u.full_name as sender_name,
                u.role as sender_role
            FROM support_messages m
            LEFT JOIN users u ON m.sender_id = u.id
            WHERE m.ticket_id = $1
        """
        if not include_internal:
            query += " AND m.is_internal = FALSE"
        query += " ORDER BY m.created_at ASC"

        rows = await db.fetch(query, ticket_id)
        return [dict(row) for row in rows]

    # ===========================================================================
    # ATTACHMENT OPERATIONS
    # ===========================================================================

    async def create_attachment(
        self,
        db: asyncpg.Connection,
        message_id: int,
        file_name: str,
        file_path: str,
        file_size: Optional[int],
        mime_type: Optional[str]
    ) -> dict:
        """Create a new attachment"""
        query = """
            INSERT INTO support_attachments (message_id, file_name, file_path, file_size, mime_type)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        row = await db.fetchrow(query, message_id, file_name, file_path, file_size, mime_type)
        return dict(row) if row else None

    async def list_attachments(self, db: asyncpg.Connection, message_id: int) -> List[dict]:
        """List all attachments for a message"""
        query = "SELECT * FROM support_attachments WHERE message_id = $1"
        rows = await db.fetch(query, message_id)
        return [dict(row) for row in rows]

    # ===========================================================================
    # STATISTICS
    # ===========================================================================

    async def get_stats(self, db: asyncpg.Connection) -> dict:
        """Get support statistics"""
        # Total tickets by status
        status_query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'open') as open_tickets,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_tickets,
                COUNT(*) FILTER (WHERE status = 'resolved') as resolved_tickets,
                COUNT(*) FILTER (WHERE status = 'closed') as closed_tickets
            FROM support_tickets
        """
        status_row = await db.fetchrow(status_query)

        # Tickets by priority
        priority_query = """
            SELECT priority, COUNT(*) as count
            FROM support_tickets
            GROUP BY priority
        """
        priority_rows = await db.fetch(priority_query)
        priority_stats = {row['priority']: row['count'] for row in priority_rows}

        # Tickets by category
        category_query = """
            SELECT c.code, COUNT(t.id) as count
            FROM support_categories c
            LEFT JOIN support_tickets t ON c.id = t.category_id
            GROUP BY c.code
        """
        category_rows = await db.fetch(category_query)
        category_stats = {row['code']: row['count'] for row in category_rows}

        # Average resolution time
        resolution_query = """
            SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600) as avg_hours
            FROM support_tickets
            WHERE resolved_at IS NOT NULL
        """
        resolution_row = await db.fetchrow(resolution_query)

        return {
            "total_tickets": status_row['total'] if status_row else 0,
            "open_tickets": status_row['open_tickets'] if status_row else 0,
            "in_progress_tickets": status_row['in_progress_tickets'] if status_row else 0,
            "resolved_tickets": status_row['resolved_tickets'] if status_row else 0,
            "closed_tickets": status_row['closed_tickets'] if status_row else 0,
            "tickets_by_priority": priority_stats,
            "tickets_by_category": category_stats,
            "average_resolution_time_hours": round(resolution_row['avg_hours'], 2) if resolution_row and resolution_row['avg_hours'] else None
        }
