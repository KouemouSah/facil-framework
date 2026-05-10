"""
Repository for Verified Identifiers.

Handles all database operations for the verified_identifiers table
and related tables (document_verification_config, verification_queue).
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

import asyncpg
from loguru import logger

from ..services.crypto_service import CryptoService, get_crypto_service


class VerifiedIdentifiersRepository:
    """
    Repository for verified identifiers with encrypted storage.

    Uses blind indexes for search without exposing plaintext values.
    """

    def __init__(self, pool: asyncpg.Pool, crypto: Optional[CryptoService] = None):
        """
        Initialize repository.

        Args:
            pool: asyncpg connection pool
            crypto: CryptoService instance (uses singleton if not provided)
        """
        self.pool = pool
        self.crypto = crypto or get_crypto_service()

    # =========================================================================
    # VERIFIED IDENTIFIERS CRUD
    # =========================================================================

    async def find_by_blind_index(
        self,
        blind_index: bytes,
        identifier_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a verified identifier by its blind index.

        Args:
            blind_index: HMAC-SHA256 of the normalized value
            identifier_type: Type of identifier (dni, pasaporte, etc.)

        Returns:
            Identifier record if found, None otherwise
        """
        query = """
            SELECT id, identifier_type, source, verified_at, expires_at, is_active,
                   encrypted_metadata, user_id, verification_request_id
            FROM verified_identifiers
            WHERE blind_index = $1 AND identifier_type = $2
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, blind_index, identifier_type)
            if row:
                return dict(row)
            return None

    async def upsert(
        self,
        value: str,
        identifier_type: str,
        source: str,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        verified_by: Optional[str] = None,
        user_id: Optional[str] = None,
        verification_request_id: Optional[str] = None
    ) -> str:
        """
        Insert or update a verified identifier.

        Args:
            value: The plaintext identifier value
            identifier_type: Type of identifier
            source: Source of verification
            expires_at: Optional expiration date
            metadata: Optional additional metadata (will be encrypted)
            verified_by: UUID of user who verified
            user_id: UUID of user this identifier belongs to
            verification_request_id: UUID of verification request

        Returns:
            UUID of the inserted/updated record
        """
        import json

        # Compute blind index and encrypt value
        blind_index = self.crypto.compute_blind_index(value, identifier_type)
        encrypted_value = self.crypto.encrypt_value(value)

        # Encrypt metadata if provided
        encrypted_metadata = None
        if metadata:
            encrypted_metadata = self.crypto.encrypt_value(json.dumps(metadata))

        query = """
            INSERT INTO verified_identifiers (
                blind_index, encrypted_value, identifier_type, source,
                verified_at, expires_at, is_active, encrypted_metadata,
                user_id, verified_by, verification_request_id
            ) VALUES (
                $1, $2, $3, $4, NOW(), $5, TRUE, $6, $7, $8, $9
            )
            ON CONFLICT (blind_index, identifier_type) DO UPDATE SET
                encrypted_value = EXCLUDED.encrypted_value,
                source = EXCLUDED.source,
                verified_at = NOW(),
                expires_at = EXCLUDED.expires_at,
                is_active = TRUE,
                encrypted_metadata = EXCLUDED.encrypted_metadata,
                verified_by = EXCLUDED.verified_by,
                updated_at = NOW()
            RETURNING id
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                blind_index,
                encrypted_value,
                identifier_type,
                source,
                expires_at,
                encrypted_metadata,
                UUID(user_id) if user_id else None,
                UUID(verified_by) if verified_by else None,
                UUID(verification_request_id) if verification_request_id else None
            )
            return str(row["id"])

    async def deactivate(
        self,
        blind_index: bytes,
        identifier_type: str
    ) -> bool:
        """
        Deactivate a verified identifier.

        Args:
            blind_index: HMAC-SHA256 of the value
            identifier_type: Type of identifier

        Returns:
            True if record was deactivated
        """
        query = """
            UPDATE verified_identifiers
            SET is_active = FALSE, updated_at = NOW()
            WHERE blind_index = $1 AND identifier_type = $2
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, blind_index, identifier_type)
            return row is not None

    async def log_search(
        self,
        blind_index: bytes,
        identifier_type: str,
        found: bool,
        request_id: Optional[str] = None,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log a search attempt for audit purposes.

        Args:
            blind_index: HMAC-SHA256 of the searched value
            identifier_type: Type of identifier
            found: Whether the search found a match
            request_id: Optional service request ID
            performed_by: Optional user ID who performed search
            ip_address: Optional IP address
            user_agent: Optional user agent string
        """
        query = """
            INSERT INTO verified_identifiers_audit (
                blind_index, identifier_type, operation, search_found,
                performed_by, request_id, ip_address, user_agent
            ) VALUES (
                $1, $2, 'SEARCH', $3, $4, $5, $6::inet, $7
            )
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    blind_index,
                    identifier_type,
                    found,
                    UUID(performed_by) if performed_by else None,
                    UUID(request_id) if request_id else None,
                    ip_address,
                    user_agent
                )
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            logger.error(f"Failed to log search audit: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about verified identifiers.

        Returns:
            Dictionary with various statistics
        """
        query = """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE is_active) AS active,
                COUNT(*) FILTER (WHERE NOT is_active) AS inactive,
                COUNT(*) FILTER (WHERE expires_at < NOW()) AS expired,
                COUNT(*) FILTER (WHERE expires_at BETWEEN NOW() AND NOW() + INTERVAL '30 days') AS expiring_soon
            FROM verified_identifiers
        """
        by_type_query = """
            SELECT identifier_type, COUNT(*) AS count
            FROM verified_identifiers
            WHERE is_active = TRUE
            GROUP BY identifier_type
        """
        by_source_query = """
            SELECT source, COUNT(*) AS count
            FROM verified_identifiers
            WHERE is_active = TRUE
            GROUP BY source
        """

        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow(query)
            by_type = await conn.fetch(by_type_query)
            by_source = await conn.fetch(by_source_query)

            return {
                "total_identifiers": stats["total"],
                "active_count": stats["active"],
                "inactive_count": stats["inactive"],
                "expired_count": stats["expired"],
                "expiring_soon": stats["expiring_soon"],
                "by_type": {row["identifier_type"]: row["count"] for row in by_type},
                "by_source": {row["source"]: row["count"] for row in by_source}
            }

    # =========================================================================
    # VERIFICATION CONFIG
    # =========================================================================

    async def get_active_configs(self) -> List[Dict[str, Any]]:
        """
        Get all active document verification configurations.

        Returns:
            List of configuration dictionaries
        """
        query = """
            SELECT id, document_code, identifier_type, extraction_paths,
                   source, is_required, normalization_regex, is_active
            FROM document_verification_config
            WHERE is_active = TRUE
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]

    async def get_config_by_document_code(self, document_code: str) -> Optional[Dict[str, Any]]:
        """
        Get verification config for a specific document code.

        Args:
            document_code: The document code (e.g., "dip_gq")

        Returns:
            Configuration dictionary if found
        """
        query = """
            SELECT id, document_code, identifier_type, extraction_paths,
                   source, is_required, normalization_regex, is_active
            FROM document_verification_config
            WHERE document_code = $1 AND is_active = TRUE
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, document_code)
            if row:
                return dict(row)
            return None

    async def upsert_config(
        self,
        document_code: str,
        identifier_type: str,
        extraction_paths: List[str],
        source: str,
        is_required: bool = True,
        normalization_regex: Optional[str] = None
    ) -> str:
        """
        Insert or update a verification configuration.

        Returns:
            UUID of the config record
        """
        query = """
            INSERT INTO document_verification_config (
                document_code, identifier_type, extraction_paths, source,
                is_required, normalization_regex, is_active
            ) VALUES ($1, $2, $3, $4, $5, $6, TRUE)
            ON CONFLICT (document_code, identifier_type) DO UPDATE SET
                extraction_paths = EXCLUDED.extraction_paths,
                source = EXCLUDED.source,
                is_required = EXCLUDED.is_required,
                normalization_regex = EXCLUDED.normalization_regex,
                is_active = TRUE,
                updated_at = NOW()
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                document_code,
                identifier_type,
                extraction_paths,
                source,
                is_required,
                normalization_regex
            )
            return str(row["id"])

    # =========================================================================
    # VERIFICATION QUEUE
    # =========================================================================

    async def queue_verification(self, service_request_id: str) -> str:
        """
        Add a service request to the verification queue.

        Args:
            service_request_id: UUID of the service request

        Returns:
            UUID of the queue item
        """
        query = "SELECT queue_verification($1)"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, UUID(service_request_id))
            return str(row[0])

    async def get_pending_verifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get pending verification items for processing.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of queue items with FOR UPDATE SKIP LOCKED
        """
        query = "SELECT * FROM get_pending_verifications($1)"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
            return [dict(row) for row in rows]

    async def mark_verification_result(
        self,
        queue_id: str,
        status: str,
        error_message: Optional[str] = None,
        partial_results: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update verification queue item status.

        Args:
            queue_id: UUID of the queue item
            status: New status (processing, completed, failed)
            error_message: Error message if failed
            partial_results: Partial results to preserve
        """
        import json

        query = "SELECT mark_verification_result($1, $2, $3, $4)"
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                UUID(queue_id),
                status,
                error_message,
                json.dumps(partial_results) if partial_results else None
            )

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the verification queue.

        Returns:
            Dictionary with queue statistics
        """
        query = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'processing') AS processing,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                AVG(retry_count) AS avg_retry_count
            FROM verification_queue
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query)
            return {
                "pending": row["pending"],
                "processing": row["processing"],
                "completed": row["completed"],
                "failed": row["failed"],
                "avg_retry_count": float(row["avg_retry_count"] or 0)
            }
