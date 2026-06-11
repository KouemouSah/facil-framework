"""
Declaration Repository - Data access layer for tax declarations

CRUD operations for tax_declarations table.
Supports 28 declaration types with polymorphic detail tables.

Tables:
- tax_declarations (main)
- declaration_iva_details (IVA - 90% volume)
- declaration_irpf_data (IRPF - 5% volume)
- declaration_petroliferos_details (Pétrolifères - 4% volume)
- declaration_retencion_details (Retenciones)
- declaration_other_details (7 autres types - <1% volume)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from loguru import logger
import asyncpg

from app.modules.declarations.models.declaration import (
    DeclarationCreate,
    DeclarationUpdate,
    DeclarationResponse,
    DeclarationStatus,
    DeclarationType,
)


class DeclarationRepository:
    """Repository for tax declarations with polymorphic detail tables"""

    async def create(
        self,
        conn: asyncpg.Connection,
        declaration: DeclarationCreate,
    ) -> Dict[str, Any]:
        """
        Create new tax declaration

        Returns:
            Dict with declaration data including generated UUID
        """
        try:
            query = """
                INSERT INTO tax_declarations (
                    user_id,
                    company_id,
                    declaration_type,
                    fiscal_period_start,
                    fiscal_period_end,
                    tax_year,
                    total_income,
                    total_deductions,
                    taxable_amount,
                    tax_rate,
                    calculated_tax,
                    status,
                    source_document_id,
                    ocr_confidence_score,
                    metadata,
                    agent_notes,
                    rejection_reason,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, NOW(), NOW())
                RETURNING
                    id, user_id, company_id, declaration_type,
                    fiscal_period_start, fiscal_period_end, tax_year,
                    total_income, total_deductions, taxable_amount,
                    tax_rate, calculated_tax, status,
                    source_document_id, ocr_confidence_score, metadata,
                    agent_notes, rejection_reason,
                    created_at, updated_at
            """

            result = await conn.fetchrow(
                query,
                str(declaration.user_id),
                str(declaration.company_id) if declaration.company_id else None,
                declaration.declaration_type.value,
                declaration.fiscal_period_start,
                declaration.fiscal_period_end,
                declaration.tax_year,
                declaration.total_income,
                declaration.total_deductions,
                declaration.taxable_amount,
                declaration.tax_rate,
                declaration.calculated_tax,
                declaration.status.value,
                str(declaration.source_document_id) if declaration.source_document_id else None,
                declaration.ocr_confidence_score,
                declaration.metadata,
                declaration.agent_notes,
                declaration.rejection_reason,
            )

            logger.info(f"Created declaration {result['id']} for user {declaration.user_id}")
            return dict(result)

        except Exception as e:
            logger.error(f"Error creating declaration: {str(e)}")
            raise

    async def get_by_id(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get declaration by ID

        Args:
            conn: Database connection
            declaration_id: Declaration UUID

        Returns:
            Declaration data or None if not found
        """
        try:
            query = """
                SELECT
                    d.*,
                    u.email as user_email,
                    c.legal_name as company_name,
                    p.id as payment_id,
                    p.status as payment_status
                FROM tax_declarations d
                LEFT JOIN users u ON d.user_id = u.id
                LEFT JOIN companies c ON d.company_id = c.id
                LEFT JOIN payments p ON p.tax_declaration_id = d.id
                WHERE d.id = $1
            """

            result = await conn.fetchrow(query, declaration_id)

            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error fetching declaration {declaration_id}: {str(e)}")
            raise

    async def list_by_user(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        status: Optional[DeclarationStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List declarations for a user with pagination

        Args:
            conn: Database connection
            user_id: User UUID
            status: Optional status filter
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (declarations list, total count)
        """
        try:
            # Build WHERE clause
            where_conditions = ["d.user_id = $1"]
            params = [user_id]

            if status:
                where_conditions.append(f"d.status = ${len(params) + 1}")
                params.append(status.value)

            where_clause = " AND ".join(where_conditions)

            # Count query
            count_query = f"""
                SELECT COUNT(*)
                FROM tax_declarations d
                WHERE {where_clause}
            """
            total = await conn.fetchval(count_query, *params)

            # Data query
            params.extend([limit, offset])
            data_query = f"""
                SELECT
                    d.*,
                    u.email as user_email,
                    c.legal_name as company_name,
                    p.id as payment_id,
                    p.status as payment_status
                FROM tax_declarations d
                LEFT JOIN users u ON d.user_id = u.id
                LEFT JOIN companies c ON d.company_id = c.id
                LEFT JOIN payments p ON p.tax_declaration_id = d.id
                WHERE {where_clause}
                ORDER BY d.created_at DESC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """

            results = await conn.fetch(data_query, *params)

            declarations = [dict(row) for row in results]

            return declarations, total

        except Exception as e:
            logger.error(f"Error listing declarations for user {user_id}: {str(e)}")
            raise

    async def update(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
        update_data: DeclarationUpdate,
    ) -> Optional[Dict[str, Any]]:
        """
        Update declaration

        Args:
            conn: Database connection
            declaration_id: Declaration UUID
            update_data: Update data

        Returns:
            Updated declaration or None if not found
        """
        try:
            # Build SET clause dynamically
            updates = []
            params = [declaration_id]
            param_idx = 2

            update_dict = update_data.dict(exclude_unset=True)

            for field, value in update_dict.items():
                if value is not None:
                    updates.append(f"{field} = ${param_idx}")
                    # Convert enum to value
                    if isinstance(value, DeclarationStatus):
                        params.append(value.value)
                    else:
                        params.append(value)
                    param_idx += 1

            if not updates:
                # No updates provided
                return await self.get_by_id(conn, declaration_id)

            updates.append(f"updated_at = ${param_idx}")
            params.append(datetime.now(timezone.utc))

            set_clause = ", ".join(updates)

            query = f"""
                UPDATE tax_declarations
                SET {set_clause}
                WHERE id = $1
                RETURNING *
            """

            result = await conn.fetchrow(query, *params)

            if result:
                logger.info(f"Updated declaration {declaration_id}")
                return dict(result)

            return None

        except Exception as e:
            logger.error(f"Error updating declaration {declaration_id}: {str(e)}")
            raise

    async def delete(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
    ) -> bool:
        """
        Delete declaration (soft delete by setting status to cancelled)

        Args:
            conn: Database connection
            declaration_id: Declaration UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            query = """
                UPDATE tax_declarations
                SET
                    status = 'cancelled',
                    updated_at = NOW()
                WHERE id = $1
                RETURNING id
            """

            result = await conn.fetchrow(query, declaration_id)

            if result:
                logger.info(f"Deleted (soft) declaration {declaration_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting declaration {declaration_id}: {str(e)}")
            raise

    async def submit(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Submit declaration (change status from draft to submitted)

        Args:
            conn: Database connection
            declaration_id: Declaration UUID

        Returns:
            Updated declaration or None if not found
        """
        try:
            query = """
                UPDATE tax_declarations
                SET
                    status = 'submitted',
                    submitted_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1 AND status = 'draft'
                RETURNING *
            """

            result = await conn.fetchrow(query, declaration_id)

            if result:
                logger.info(f"Submitted declaration {declaration_id}")
                return dict(result)

            return None

        except Exception as e:
            logger.error(f"Error submitting declaration {declaration_id}: {str(e)}")
            raise

    # ========================================================================
    # METHODS USING DATABASE VIEWS - Optimized queries with pre-joined data
    # ========================================================================

    async def get_complete_by_id(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete declaration details using v_declarations_complete view

        This view includes:
        - All declaration fields
        - User info (email, name, phone)
        - Payment info (amount_paid, amount_due)
        - Type-specific details (IVA, IRPF, Petroliferos, Retencion)
        - Agent assignment info

        Args:
            conn: Database connection
            declaration_id: Declaration UUID

        Returns:
            Complete declaration data or None if not found
        """
        try:
            query = """
                SELECT * FROM v_declarations_complete
                WHERE id = $1
            """

            result = await conn.fetchrow(query, declaration_id)
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error fetching complete declaration {declaration_id}: {str(e)}")
            raise

    async def list_complete_by_user(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        status: Optional[DeclarationStatus] = None,
        declaration_type: Optional[DeclarationType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List complete declarations for a user using v_declarations_complete view

        Args:
            conn: Database connection
            user_id: User UUID
            status: Optional status filter
            declaration_type: Optional type filter
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (declarations list, total count)
        """
        try:
            # Build WHERE clause
            where_conditions = ["user_id = $1"]
            params = [user_id]

            if status:
                # Cast enum to text for comparison
                where_conditions.append(f"status::text = ${len(params) + 1}")
                params.append(status.value)

            if declaration_type:
                # Cast enum to text for comparison
                where_conditions.append(f"declaration_type::text = ${len(params) + 1}")
                params.append(declaration_type.value)

            where_clause = " AND ".join(where_conditions)

            # Count query
            count_query = f"""
                SELECT COUNT(*) FROM v_declarations_complete
                WHERE {where_clause}
            """
            total = await conn.fetchval(count_query, *params)

            # Data query
            params.extend([limit, offset])
            data_query = f"""
                SELECT * FROM v_declarations_complete
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """

            results = await conn.fetch(data_query, *params)
            declarations = [dict(r) for r in results]

            return declarations, total

        except Exception as e:
            logger.error(f"Error listing complete declarations for user {user_id}: {str(e)}")
            raise

    async def list_pending_review(
        self,
        conn: asyncpg.Connection,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List declarations pending review using v_declarations_pending_review view

        This view includes priority calculation and SLA tracking.

        Args:
            conn: Database connection
            priority: Optional priority filter (HIGH, MEDIUM, LOW)
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (declarations list, total count)
        """
        try:
            where_clause = ""
            params = []

            if priority:
                where_clause = "WHERE priority = $1"
                params.append(priority)

            # Count query
            count_query = f"""
                SELECT COUNT(*) FROM v_declarations_pending_review
                {where_clause}
            """
            total = await conn.fetchval(count_query, *params)

            # Data query
            params.extend([limit, offset])
            data_query = f"""
                SELECT * FROM v_declarations_pending_review
                {where_clause}
                ORDER BY priority, submitted_at ASC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """

            results = await conn.fetch(data_query, *params)
            declarations = [dict(r) for r in results]

            return declarations, total

        except Exception as e:
            logger.error(f"Error listing pending review declarations: {str(e)}")
            raise

    # ========================================================================
    # BUSINESS LOGIC METHODS - Workflow and operations
    # ========================================================================

    async def find_by_declaration_number(
        self,
        conn: asyncpg.Connection,
        declaration_number: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find declaration by declaration number

        Args:
            conn: Database connection
            declaration_number: Declaration number (unique identifier)

        Returns:
            Declaration data or None if not found
        """
        try:
            query = """
                SELECT * FROM tax_declarations
                WHERE declaration_number = $1
            """
            result = await conn.fetchrow(query, declaration_number)
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error finding declaration by number {declaration_number}: {str(e)}")
            raise

    async def assign_to_agent(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
        agent_id: str,
    ) -> bool:
        """
        Assign declaration to an agent

        Args:
            conn: Database connection
            declaration_id: Declaration UUID
            agent_id: Agent UUID

        Returns:
            True if assigned successfully
        """
        try:
            query = """
                UPDATE tax_declarations
                SET
                    assigned_agent_id = $2,
                    assigned_at = NOW(),
                    status = 'in_review',
                    updated_at = NOW()
                WHERE id = $1
                RETURNING id
            """
            result = await conn.fetchrow(query, declaration_id, agent_id)

            if result:
                logger.info(f"Assigned declaration {declaration_id} to agent {agent_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error assigning declaration {declaration_id}: {str(e)}")
            raise

    async def approve_declaration(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
        agent_id: str,
        agent_notes: Optional[str] = None,
    ) -> bool:
        """
        Approve declaration

        Args:
            conn: Database connection
            declaration_id: Declaration UUID
            agent_id: Agent who approved
            agent_notes: Optional approval notes

        Returns:
            True if approved successfully
        """
        try:
            query = """
                UPDATE tax_declarations
                SET
                    status = 'approved',
                    approved_at = NOW(),
                    approved_by = $2,
                    agent_notes = COALESCE($3, agent_notes),
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_review'
                RETURNING id
            """
            result = await conn.fetchrow(query, declaration_id, agent_id, agent_notes)

            if result:
                logger.info(f"Approved declaration {declaration_id} by agent {agent_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error approving declaration {declaration_id}: {str(e)}")
            raise

    async def reject_declaration(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
        agent_id: str,
        rejection_reason: str,
    ) -> bool:
        """
        Reject declaration

        Args:
            conn: Database connection
            declaration_id: Declaration UUID
            agent_id: Agent who rejected
            rejection_reason: Reason for rejection

        Returns:
            True if rejected successfully
        """
        try:
            query = """
                UPDATE tax_declarations
                SET
                    status = 'rejected',
                    rejected_at = NOW(),
                    rejected_by = $2,
                    rejection_reason = $3,
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_review'
                RETURNING id
            """
            result = await conn.fetchrow(query, declaration_id, agent_id, rejection_reason)

            if result:
                logger.info(f"Rejected declaration {declaration_id} by agent {agent_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error rejecting declaration {declaration_id}: {str(e)}")
            raise

    async def get_stats(
        self,
        conn: asyncpg.Connection,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get declaration statistics

        Args:
            conn: Database connection
            user_id: Optional user filter (None for global stats)

        Returns:
            Statistics dictionary
        """
        try:
            where_clause = "WHERE user_id = $1" if user_id else ""
            params = [user_id] if user_id else []

            # Total count
            count_query = f"SELECT COUNT(*) FROM tax_declarations {where_clause}"
            total = await conn.fetchval(count_query, *params)

            # By status
            status_query = f"""
                SELECT status, COUNT(*) as count
                FROM tax_declarations
                {where_clause}
                GROUP BY status
            """
            status_results = await conn.fetch(status_query, *params)
            by_status = {row['status']: row['count'] for row in status_results}

            # By type
            type_query = f"""
                SELECT declaration_type, COUNT(*) as count
                FROM tax_declarations
                {where_clause}
                GROUP BY declaration_type
            """
            type_results = await conn.fetch(type_query, *params)
            by_type = {row['declaration_type']: row['count'] for row in type_results}

            # Average processing time (hours)
            avg_query = f"""
                SELECT AVG(EXTRACT(EPOCH FROM (approved_at - submitted_at))/3600) as avg_hours
                FROM tax_declarations
                {where_clause}
                AND submitted_at IS NOT NULL
                AND approved_at IS NOT NULL
            """
            avg_hours = await conn.fetchval(avg_query, *params)

            return {
                "total": total,
                "by_status": by_status,
                "by_type": by_type,
                "average_processing_hours": float(avg_hours) if avg_hours else 0,
            }

        except Exception as e:
            logger.error(f"Error getting declaration stats: {str(e)}")
            raise

    async def search(
        self,
        conn: asyncpg.Connection,
        search_term: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[DeclarationStatus] = None,
        declaration_type: Optional[DeclarationType] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Advanced search for declarations

        Args:
            conn: Database connection
            search_term: Optional text search
            user_id: Optional user filter
            status: Optional status filter
            declaration_type: Optional type filter
            date_from: Optional start date
            date_to: Optional end date
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (declarations list, total count)
        """
        try:
            # Build WHERE conditions
            where_conditions = []
            params = []

            if user_id:
                where_conditions.append(f"d.user_id = ${len(params) + 1}")
                params.append(user_id)

            if status:
                # Cast enum to text for comparison
                where_conditions.append(f"d.status::text = ${len(params) + 1}")
                params.append(status.value)

            if declaration_type:
                # Cast enum to text for comparison
                where_conditions.append(f"d.declaration_type::text = ${len(params) + 1}")
                params.append(declaration_type.value)

            if date_from:
                where_conditions.append(f"d.created_at >= ${len(params) + 1}")
                params.append(date_from)

            if date_to:
                where_conditions.append(f"d.created_at <= ${len(params) + 1}")
                params.append(date_to)

            if search_term:
                where_conditions.append(f"(d.metadata::text ILIKE ${len(params) + 1} OR d.agent_notes ILIKE ${len(params) + 1})")
                params.append(f"%{search_term}%")

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            # Count query
            count_query = f"""
                SELECT COUNT(*) FROM tax_declarations d
                {where_clause}
            """
            total = await conn.fetchval(count_query, *params)

            # Data query
            params.extend([limit, offset])
            data_query = f"""
                SELECT
                    d.*,
                    u.email as user_email,
                    c.name as company_name
                FROM tax_declarations d
                LEFT JOIN users u ON d.user_id = u.id
                LEFT JOIN companies c ON d.company_id = c.id
                {where_clause}
                ORDER BY d.created_at DESC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """

            results = await conn.fetch(data_query, *params)
            declarations = [dict(r) for r in results]

            return declarations, total

        except Exception as e:
            logger.error(f"Error searching declarations: {str(e)}")
            raise

    # ========================================================================
    # AUDIT TRAIL - Activity logging
    # ========================================================================

    async def log_activity(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        action: str,
        entity_id: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Log declaration activity to audit_logs table

        Args:
            conn: Database connection
            user_id: User performing the action
            action: Action performed (created, updated, submitted, approved, rejected, etc.)
            entity_id: Declaration ID (UUID)
            old_values: Previous values (for updates)
            new_values: New values (for updates/creates)
            ip_address: Client IP address
            user_agent: Client user agent

        Business Rules:
            - Uses generic audit_logs table (entity_type='declaration')
            - Stores old/new values as JSONB for complete audit trail
            - Records timestamp, IP, and user agent for security

        Example:
            await repo.log_activity(
                conn=conn,
                user_id="user-uuid",
                action="submitted",
                entity_id="decl-uuid",
                new_values={"status": "submitted", "submitted_at": "2025-11-22T10:00:00Z"}
            )
        """
        try:
            query = """
                INSERT INTO audit_logs (
                    user_id,
                    entity_type,
                    entity_id,
                    action,
                    old_values,
                    new_values,
                    ip_address,
                    user_agent,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            """

            # Convert dicts to JSON (asyncpg handles JSONB automatically)
            await conn.execute(
                query,
                user_id,
                "declaration",  # entity_type
                entity_id,
                action,
                old_values,  # JSONB
                new_values,  # JSONB
                ip_address,
                user_agent,
            )

            logger.debug(f"Audit log created: user={user_id}, action={action}, entity={entity_id}")

        except Exception as e:
            # Log but don't fail the operation if audit logging fails
            logger.error(f"Error logging declaration activity: {str(e)}")
            # Don't re-raise - audit logging should not break business operations
