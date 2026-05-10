"""
Repository for Verificacion Funcionario database operations.
Uses asyncpg with parameterized queries ($1, $2, etc).
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from loguru import logger

from app.database.connection import get_db_connection


class VerificacionRepository:
    """Repository for verificacion_funcionario table operations."""

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(
        self,
        user_id: UUID,
        matricula: str,
        verification_data: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new verification request.

        Args:
            user_id: User requesting verification
            matricula: Civil servant matricula
            verification_data: Document data and extractions
            ip_address: Request IP
            user_agent: Browser user agent

        Returns:
            Created verification record
        """
        db = await get_db_connection()

        query = """
            INSERT INTO verificacion_funcionario (
                user_id, matricula, verification_data, ip_address, user_agent
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """

        row = await db.fetchrow(
            query,
            user_id,
            matricula.upper().strip(),
            json.dumps(verification_data),
            ip_address,
            user_agent,
        )

        return dict(row) if row else None

    # =========================================================================
    # READ
    # =========================================================================

    async def get_by_id(self, verificacion_id: UUID) -> Optional[Dict[str, Any]]:
        """Get verification by ID."""
        db = await get_db_connection()

        query = """
            SELECT vf.*, u.email as user_email, u.full_name as user_full_name, u.phone_number as user_phone
            FROM verificacion_funcionario vf
            JOIN users u ON vf.user_id = u.id
            WHERE vf.id = $1
        """

        row = await db.fetchrow(query, verificacion_id)
        return dict(row) if row else None

    async def get_by_user_id(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get the latest verification for a user."""
        db = await get_db_connection()

        query = """
            SELECT *
            FROM verificacion_funcionario
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        row = await db.fetchrow(query, user_id)
        return dict(row) if row else None

    async def get_pending_by_user(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get pending verification for a user (if any)."""
        db = await get_db_connection()

        query = """
            SELECT *
            FROM verificacion_funcionario
            WHERE user_id = $1 AND status = 'pendiente'
            ORDER BY created_at DESC
            LIMIT 1
        """

        row = await db.fetchrow(query, user_id)
        return dict(row) if row else None

    async def list_pending(
        self,
        page: int = 1,
        page_size: int = 20,
        auto_validable_only: bool = False,
        pre_verified_only: bool = False,
    ) -> Dict[str, Any]:
        """
        List pending verifications for agent dashboard.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            auto_validable_only: Only return auto-validable requests (cross-validation passed)
            pre_verified_only: Only return pre-verified requests (matricula in verified_identifiers)

        Returns:
            Dict with items, total, pagination info
        """
        db = await get_db_connection()
        offset = (page - 1) * page_size

        # Build WHERE clause
        where_clause = "vf.status = 'pendiente'"
        if auto_validable_only:
            where_clause += " AND (vf.verification_data->'validacion_cruzada'->>'validacion_automatica_posible')::boolean = true"
        if pre_verified_only:
            where_clause += " AND (vf.verification_data->'auto_verification'->>'pre_verified')::boolean = true"

        # Count query
        count_query = f"""
            SELECT COUNT(*)
            FROM verificacion_funcionario vf
            WHERE {where_clause}
        """
        total = await db.fetchval(count_query)

        # Data query with user info
        # Priority order: pre_verified first, then auto_validable, then by created_at
        data_query = f"""
            SELECT
                vf.*,
                u.email as user_email,
                u.full_name as user_full_name,
                u.phone_number as user_phone
            FROM verificacion_funcionario vf
            JOIN users u ON vf.user_id = u.id
            WHERE {where_clause}
            ORDER BY
                (vf.verification_data->'auto_verification'->>'pre_verified')::boolean DESC NULLS LAST,
                (vf.verification_data->'validacion_cruzada'->>'validacion_automatica_posible')::boolean DESC NULLS LAST,
                vf.created_at ASC
            LIMIT $1 OFFSET $2
        """

        rows = await db.fetch(data_query, page_size, offset)

        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get verification statistics."""
        db = await get_db_connection()

        query = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pendiente') AS pendientes,
                COUNT(*) FILTER (WHERE status = 'pendiente'
                    AND (verification_data->'validacion_cruzada'->>'validacion_automatica_posible')::boolean = true
                ) AS pendientes_auto_validables,
                COUNT(*) FILTER (WHERE status = 'pendiente'
                    AND (verification_data->'auto_verification'->>'pre_verified')::boolean = true
                ) AS pendientes_pre_verificados,
                COUNT(*) FILTER (WHERE status = 'aprobado') AS aprobadas,
                COUNT(*) FILTER (WHERE status = 'rechazado') AS rechazadas,
                COUNT(*) AS total
            FROM verificacion_funcionario
        """

        row = await db.fetchrow(query)
        return dict(row) if row else {}

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update_verification_data(
        self,
        verificacion_id: UUID,
        verification_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update verification_data for a verification."""
        db = await get_db_connection()

        query = """
            UPDATE verificacion_funcionario
            SET verification_data = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """

        row = await db.fetchrow(query, verificacion_id, json.dumps(verification_data))
        return dict(row) if row else None

    async def merge_verification_data(
        self,
        verificacion_id: UUID,
        new_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Merge new data into existing verification_data."""
        db = await get_db_connection()

        query = """
            UPDATE verificacion_funcionario
            SET verification_data = verification_data || $2::jsonb, updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """

        row = await db.fetchrow(query, verificacion_id, json.dumps(new_data))
        return dict(row) if row else None

    # =========================================================================
    # PROCESS (Approve/Reject)
    # =========================================================================

    async def process(
        self,
        verificacion_id: UUID,
        agent_id: UUID,
        action: str,
        matricula_existe: bool = False,
        nombre_coincide: bool = False,
        dip_coincide: bool = False,
        rejection_reason: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a verification (approve or reject).
        Uses the PostgreSQL function process_verificacion_funcionario.

        Returns:
            Result dict with success, status, user_id, etc.
        """
        db = await get_db_connection()

        query = """
            SELECT process_verificacion_funcionario(
                $1, $2, $3, $4, $5, $6, $7, $8
            ) as result
        """

        row = await db.fetchrow(
            query,
            verificacion_id,
            agent_id,
            action,
            matricula_existe,
            nombre_coincide,
            dip_coincide,
            rejection_reason,
            notes,
        )

        if row and row["result"]:
            return json.loads(row["result"]) if isinstance(row["result"], str) else row["result"]
        return {"success": False, "error": "No result from function"}

    async def batch_approve(
        self,
        verificacion_ids: List[UUID],
        agent_id: UUID,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Batch approve multiple verifications.
        Uses the PostgreSQL function batch_approve_verificaciones.

        Returns:
            Result dict with success count, errors, etc.
        """
        db = await get_db_connection()

        query = """
            SELECT batch_approve_verificaciones($1, $2, $3) as result
        """

        row = await db.fetchrow(query, verificacion_ids, agent_id, notes)

        if row and row["result"]:
            return json.loads(row["result"]) if isinstance(row["result"], str) else row["result"]
        return {"success": False, "error": "No result from function"}

    # =========================================================================
    # MATRICULA VALIDATION
    # =========================================================================

    async def check_matricula_verified_for_other_user(
        self,
        matricula: str,
        user_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if matricula is already verified for ANOTHER user.

        Args:
            matricula: The matricula to check
            user_id: Current user ID (to exclude from check)

        Returns:
            Dict with existing user info if found, None otherwise
        """
        db = await get_db_connection()

        query = """
            SELECT u.id, u.email, u.full_name, u.matricula_funcionario, u.funcionario_verified_at
            FROM users u
            WHERE UPPER(TRIM(u.matricula_funcionario)) = UPPER(TRIM($1))
            AND u.id != $2
            LIMIT 1
        """

        row = await db.fetchrow(query, matricula, user_id)

        if row:
            logger.warning(
                f"[VerificacionRepo] Matricula {matricula} already verified for user {row['id']}"
            )

        return dict(row) if row else None

    async def check_matricula_pending_for_other_user(
        self,
        matricula: str,
        user_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if matricula has a PENDING request from ANOTHER user.

        Args:
            matricula: The matricula to check
            user_id: Current user ID (to exclude from check)

        Returns:
            Dict with pending request info if found, None otherwise
        """
        db = await get_db_connection()

        query = """
            SELECT vf.id, vf.user_id, vf.matricula, vf.created_at, u.email, u.full_name
            FROM verificacion_funcionario vf
            JOIN users u ON vf.user_id = u.id
            WHERE UPPER(TRIM(vf.matricula)) = UPPER(TRIM($1))
            AND vf.status = 'pendiente'
            AND vf.user_id != $2
            ORDER BY vf.created_at DESC
            LIMIT 1
        """

        row = await db.fetchrow(query, matricula, user_id)

        if row:
            logger.warning(
                f"[VerificacionRepo] Matricula {matricula} has pending request "
                f"from user {row['user_id']} (created: {row['created_at']})"
            )

        return dict(row) if row else None

    async def check_matricula_approved_exists(
        self,
        matricula: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if matricula has an APPROVED verification (any user).

        Args:
            matricula: The matricula to check

        Returns:
            Dict with approved verification info if found, None otherwise
        """
        db = await get_db_connection()

        query = """
            SELECT vf.id, vf.user_id, vf.matricula, vf.created_at, vf.processed_at,
                   u.email, u.full_name
            FROM verificacion_funcionario vf
            JOIN users u ON vf.user_id = u.id
            WHERE UPPER(TRIM(vf.matricula)) = UPPER(TRIM($1))
            AND vf.status = 'aprobado'
            ORDER BY vf.processed_at DESC
            LIMIT 1
        """

        row = await db.fetchrow(query, matricula)
        return dict(row) if row else None

    async def log_fraud_attempt(
        self,
        user_id: Optional[UUID],
        matricula: str,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Log a suspicious/fraudulent verification attempt.

        Args:
            user_id: User attempting the verification (if known)
            matricula: The matricula being used
            reason: Reason code for the fraud attempt
            ip_address: Client IP
            user_agent: Browser user agent
            details: Additional details as JSON

        Returns:
            True if logged successfully
        """
        db = await get_db_connection()

        query = """
            INSERT INTO verificacion_fraud_log (
                user_id, matricula, reason, ip_address, user_agent, details
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """

        try:
            row = await db.fetchrow(
                query,
                user_id,
                matricula.upper().strip(),
                reason,
                ip_address,
                user_agent,
                json.dumps(details) if details else None,
            )

            logger.warning(
                f"[VerificacionRepo] Fraud attempt logged: user={user_id}, "
                f"matricula={matricula}, reason={reason}, log_id={row['id'] if row else 'N/A'}"
            )

            return row is not None
        except Exception as e:
            logger.error(f"[VerificacionRepo] Failed to log fraud attempt: {e}")
            return False

    # =========================================================================
    # USER STATUS
    # =========================================================================

    async def get_user_funcionario_status(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get a user's funcionario verification status.

        Returns:
            Dict with verification status and user's funcionario info
        """
        db = await get_db_connection()

        # Get user's funcionario fields
        user_query = """
            SELECT
                id,
                matricula_funcionario,
                funcionario_verified_at,
                funcionario_verified_by
            FROM users
            WHERE id = $1
        """
        user_row = await db.fetchrow(user_query, user_id)

        # Get latest verification
        verif_query = """
            SELECT id, matricula, status, created_at, processed_at, rejection_reason
            FROM verificacion_funcionario
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """
        verif_row = await db.fetchrow(verif_query, user_id)

        result = {
            "has_verification": verif_row is not None,
            "is_verified_funcionario": False,
            "can_submit_new": True,
        }

        if user_row:
            if user_row["matricula_funcionario"]:
                result["is_verified_funcionario"] = True
                result["matricula"] = user_row["matricula_funcionario"]
                result["funcionario_verified_at"] = user_row["funcionario_verified_at"]
                result["can_submit_new"] = False
                result["message"] = "Ya está verificado como funcionario"

        if verif_row:
            result["status"] = verif_row["status"]
            result["matricula"] = verif_row["matricula"]
            result["submitted_at"] = verif_row["created_at"]
            result["processed_at"] = verif_row["processed_at"]
            result["rejection_reason"] = verif_row["rejection_reason"]

            if verif_row["status"] == "pendiente":
                result["can_submit_new"] = False
                result["message"] = "Tiene una solicitud pendiente de verificación"
            elif verif_row["status"] == "rechazado":
                result["can_submit_new"] = True
                result["message"] = f"Solicitud rechazada: {verif_row['rejection_reason']}"

        return result


# Singleton instance
verificacion_repository = VerificacionRepository()
