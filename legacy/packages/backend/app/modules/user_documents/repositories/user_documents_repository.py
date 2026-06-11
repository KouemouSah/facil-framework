"""
Repository for user_documents table.
Data access layer for the user document vault (Mes Documents).
OWASP A01: All queries enforce user_id ownership.
"""
import asyncpg
import json
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime


class UserDocumentsRepository:
    """Data access layer for user_documents table and related tables."""

    # ─────────────────────────────────────────────
    # CREATE
    # ─────────────────────────────────────────────

    async def create_document(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        source: str,
        document_type: str,
        document_category: str,
        file_path: str,
        file_name: str,
        file_size_bytes: int,
        mime_type: str,
        file_hash: str,
        template_code: Optional[str] = None,
        source_request_id: Optional[UUID] = None,
        source_document_id: Optional[UUID] = None,
        generation_type: Optional[str] = None,
        display_name: Optional[str] = None,
        notes: Optional[str] = None,
        document_number: Optional[str] = None,
        holder_name: Optional[str] = None,
        issue_date=None,
        expiry_date=None,
        issuing_authority: Optional[str] = None,
        title_es: Optional[str] = None,
        title_fr: Optional[str] = None,
        title_en: Optional[str] = None,
        reference_number: Optional[str] = None,
        verification_code: Optional[str] = None,
        valid_until: Optional[datetime] = None,
        replaces_document_id: Optional[UUID] = None,
    ) -> Dict:
        """
        Insert a new document into the user vault.
        Returns the full inserted row as a dict.
        """
        query = """
            INSERT INTO user_documents (
                user_id, source, document_type, document_category,
                file_path, file_name, file_size_bytes, mime_type, file_hash,
                template_code, source_request_id, source_document_id,
                generation_type, display_name, notes,
                document_number, holder_name, issue_date, expiry_date,
                issuing_authority, title_es, title_fr, title_en,
                reference_number, verification_code, valid_until,
                replaces_document_id
            )
            VALUES (
                $1, $2, $3, $4,
                $5, $6, $7, $8, $9,
                $10, $11, $12,
                $13, $14, $15,
                $16, $17, $18, $19,
                $20, $21, $22, $23,
                $24, $25, $26,
                $27
            )
            RETURNING *
        """
        row = await db.fetchrow(
            query,
            user_id, source, document_type, document_category,
            file_path, file_name, file_size_bytes, mime_type, file_hash,
            template_code, source_request_id, source_document_id,
            generation_type, display_name, notes,
            document_number, holder_name, issue_date, expiry_date,
            issuing_authority, title_es, title_fr, title_en,
            reference_number, verification_code, valid_until,
            replaces_document_id,
        )
        return self._row_to_dict(row)

    # ─────────────────────────────────────────────
    # UPDATE — Extraction results
    # ─────────────────────────────────────────────

    async def update_extraction(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        extraction_data: Dict,
        extraction_confidence: float,
        extraction_status: str,
        document_number: Optional[str] = None,
        holder_name: Optional[str] = None,
        issue_date=None,
        expiry_date=None,
        classification_method: Optional[str] = None,
        classification_confidence: Optional[float] = None,
        document_category: Optional[str] = None,
    ) -> None:
        """
        Update extraction results for a document after OCR/Gemini processing.
        Uses json.dumps() + ::jsonb cast to properly store the dict as JSONB.
        """
        json_str = json.dumps(extraction_data) if extraction_data else '{}'
        await db.execute(
            """UPDATE user_documents
               SET extraction_data = $2::jsonb,
                   extraction_confidence = $3,
                   extraction_status = $4,
                   document_number = COALESCE($5, document_number),
                   holder_name = COALESCE($6, holder_name),
                   issue_date = COALESCE($7, issue_date),
                   expiry_date = COALESCE($8, expiry_date),
                   classification_method = COALESCE($9, classification_method),
                   classification_confidence = COALESCE($10, classification_confidence),
                   document_category = COALESCE($11, document_category),
                   updated_at = NOW()
               WHERE id = $1""",
            doc_id,
            json_str,
            extraction_confidence,
            extraction_status,
            document_number,
            holder_name,
            issue_date,
            expiry_date,
            classification_method,
            classification_confidence,
            document_category,
        )

    # ─────────────────────────────────────────────
    # UPDATE — User metadata (display_name, notes, etc.)
    # ─────────────────────────────────────────────

    async def update_metadata(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
        display_name: Optional[str] = None,
        notes: Optional[str] = None,
        color_label: Optional[str] = None,
        document_category: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Update user-editable metadata fields.
        Only updates non-None fields. Checks user_id ownership (OWASP A01).
        Returns updated row or None if not found / not owned.
        """
        # Build SET clause dynamically for non-None fields only
        sets: List[str] = []
        params: list = [doc_id, user_id]  # $1 = doc_id, $2 = user_id
        idx = 3

        if display_name is not None:
            sets.append(f"display_name = ${idx}")
            params.append(display_name)
            idx += 1
        if notes is not None:
            sets.append(f"notes = ${idx}")
            params.append(notes)
            idx += 1
        if color_label is not None:
            sets.append(f"color_label = ${idx}")
            params.append(color_label)
            idx += 1
        if document_category is not None:
            sets.append(f"document_category = ${idx}")
            params.append(document_category)
            idx += 1

        if not sets:
            # Nothing to update, just return the current doc
            return await self.find_by_id(db, doc_id, user_id)

        sets.append("updated_at = NOW()")

        query = f"""
            UPDATE user_documents
            SET {', '.join(sets)}
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
            RETURNING *
        """
        row = await db.fetchrow(query, *params)
        return self._row_to_dict(row) if row else None

    # ─────────────────────────────────────────────
    # READ — Single document
    # ─────────────────────────────────────────────

    async def find_by_id(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
    ) -> Optional[Dict]:
        """
        Find document by ID with user_id ownership check (OWASP A01).
        Only returns non-deleted documents.
        """
        row = await db.fetchrow(
            """SELECT * FROM user_documents
               WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL""",
            doc_id,
            user_id,
        )
        return self._row_to_dict(row) if row else None

    # ─────────────────────────────────────────────
    # READ — User listing with cursor pagination
    # ─────────────────────────────────────────────

    async def find_by_user(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        source: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        expiry_status: Optional[str] = None,
        search_query: Optional[str] = None,
        cursor_created_at: Optional[datetime] = None,
        cursor_id: Optional[UUID] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """
        List documents for a user with optional filters and cursor-based pagination.

        Cursor pagination uses (created_at DESC, id) for stable ordering.
        expiry_status: 'valid' (>90d or NULL), 'expiring_soon' (0-90d), 'expired' (<0d)
        search_query: full-text search using to_tsvector/to_tsquery('spanish', ...)
        """
        conditions: List[str] = ["user_id = $1", "deleted_at IS NULL"]
        params: list = [user_id]
        idx = 2

        # Optional filters
        if source is not None:
            conditions.append(f"source = ${idx}")
            params.append(source)
            idx += 1

        if category is not None:
            conditions.append(f"document_category = ${idx}")
            params.append(category)
            idx += 1

        if status is not None:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        else:
            # Default: exclude deleted status (soft-deleted but not yet cleaned)
            conditions.append("status != 'deleted'")

        # Expiry status filter
        if expiry_status == 'valid':
            conditions.append(
                "(expiry_date IS NULL OR expiry_date > NOW() + INTERVAL '90 days')"
            )
        elif expiry_status == 'expiring_soon':
            conditions.append(
                "expiry_date IS NOT NULL AND expiry_date > NOW() "
                "AND expiry_date <= NOW() + INTERVAL '90 days'"
            )
        elif expiry_status == 'expired':
            conditions.append(
                "expiry_date IS NOT NULL AND expiry_date <= NOW()"
            )

        # Full-text search
        if search_query:
            conditions.append(f"""
                to_tsvector('spanish',
                    COALESCE(display_name, '') || ' ' ||
                    COALESCE(file_name, '') || ' ' ||
                    COALESCE(notes, '') || ' ' ||
                    COALESCE(holder_name, '') || ' ' ||
                    COALESCE(document_number, '')
                ) @@ plainto_tsquery('spanish', ${idx})
            """)
            params.append(search_query)
            idx += 1

        # Cursor-based pagination: WHERE (created_at, id) < ($cursor_at, $cursor_id)
        if cursor_created_at is not None and cursor_id is not None:
            conditions.append(
                f"(created_at, id) < (${idx}, ${idx + 1})"
            )
            params.append(cursor_created_at)
            params.append(cursor_id)
            idx += 2

        # Limit
        params.append(limit)
        limit_placeholder = f"${idx}"

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT * FROM user_documents
            WHERE {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT {limit_placeholder}
        """
        rows = await db.fetch(query, *params)
        return [self._row_to_dict(row) for row in rows]

    # ─────────────────────────────────────────────
    # READ — Generated documents
    # ─────────────────────────────────────────────

    async def find_generated(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        generation_type: Optional[str] = None,
        cursor_created_at: Optional[datetime] = None,
        cursor_id: Optional[UUID] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Find platform-generated documents for a user.
        Optionally filter by generation_type (e.g. 'payment_receipt', 'certificate').
        """
        conditions: List[str] = [
            "user_id = $1",
            "source = 'platform_generated'",
            "deleted_at IS NULL",
            "status != 'deleted'",
        ]
        params: list = [user_id]
        idx = 2

        if generation_type is not None:
            conditions.append(f"generation_type = ${idx}")
            params.append(generation_type)
            idx += 1

        if cursor_created_at is not None and cursor_id is not None:
            conditions.append(f"(created_at, id) < (${idx}, ${idx + 1})")
            params.append(cursor_created_at)
            params.append(cursor_id)
            idx += 2

        params.append(limit)
        limit_placeholder = f"${idx}"

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT * FROM user_documents
            WHERE {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT {limit_placeholder}
        """
        rows = await db.fetch(query, *params)
        return [self._row_to_dict(row) for row in rows]

    # ─────────────────────────────────────────────
    # READ — Documents matching a workflow
    # ─────────────────────────────────────────────

    async def find_for_workflow(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        workflow_code: str,
    ) -> List[Dict]:
        """
        Find active user documents tagged for a specific workflow.
        JOIN user_document_workflow_tags to filter by workflow_code.
        """
        query = """
            SELECT ud.* FROM user_documents ud
            JOIN user_document_workflow_tags wt ON wt.user_document_id = ud.id
            WHERE ud.user_id = $1
              AND wt.workflow_code = $2
              AND ud.status = 'active'
              AND ud.deleted_at IS NULL
            ORDER BY wt.relevance_score DESC, ud.created_at DESC
        """
        rows = await db.fetch(query, user_id, workflow_code)
        return [self._row_to_dict(row) for row in rows]

    # ─────────────────────────────────────────────
    # READ — Duplicate detection
    # ─────────────────────────────────────────────

    async def find_duplicate(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        file_hash: str,
    ) -> Optional[Dict]:
        """
        Find an existing ACTIVE document with the same file_hash for this user.
        Only active documents block re-upload — archived/expired can be re-uploaded.
        """
        row = await db.fetchrow(
            """SELECT * FROM user_documents
               WHERE user_id = $1 AND file_hash = $2
                 AND status = 'active' AND deleted_at IS NULL
               LIMIT 1""",
            user_id,
            file_hash,
        )
        return self._row_to_dict(row) if row else None

    # ─────────────────────────────────────────────
    # READ — Stats (aggregates)
    # ─────────────────────────────────────────────

    async def get_stats(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
    ) -> Dict:
        """
        Get document vault statistics for a user in a single query.
        Returns counts by source, status, expiry, and total storage used.
        """
        query = """
            SELECT
                COUNT(*) FILTER (WHERE deleted_at IS NULL) AS total_active,
                COUNT(*) FILTER (WHERE source = 'personal' AND deleted_at IS NULL) AS personal_count,
                COUNT(*) FILTER (WHERE source = 'wizard_import' AND deleted_at IS NULL) AS wizard_count,
                COUNT(*) FILTER (WHERE source = 'platform_generated' AND deleted_at IS NULL) AS generated_count,
                COUNT(*) FILTER (WHERE status = 'active' AND deleted_at IS NULL) AS active_count,
                COUNT(*) FILTER (WHERE status = 'archived' AND deleted_at IS NULL) AS archived_count,
                COUNT(*) FILTER (
                    WHERE expiry_date IS NOT NULL
                      AND expiry_date <= NOW()
                      AND deleted_at IS NULL
                      AND status = 'active'
                ) AS expired_count,
                COUNT(*) FILTER (
                    WHERE expiry_date IS NOT NULL
                      AND expiry_date > NOW()
                      AND expiry_date <= NOW() + INTERVAL '90 days'
                      AND deleted_at IS NULL
                      AND status = 'active'
                ) AS expiring_soon_count,
                COALESCE(SUM(file_size_bytes) FILTER (WHERE deleted_at IS NULL), 0) AS total_size_bytes,
                COALESCE(SUM(file_size_bytes) FILTER (
                    WHERE source = 'personal' AND deleted_at IS NULL
                ), 0) AS personal_size_bytes
            FROM user_documents
            WHERE user_id = $1
        """
        row = await db.fetchrow(query, user_id)
        return dict(row) if row else {
            "total_active": 0,
            "personal_count": 0,
            "wizard_count": 0,
            "generated_count": 0,
            "active_count": 0,
            "archived_count": 0,
            "expired_count": 0,
            "expiring_soon_count": 0,
            "total_size_bytes": 0,
            "personal_size_bytes": 0,
        }

    # ─────────────────────────────────────────────
    # UPDATE — Archive
    # ─────────────────────────────────────────────

    async def archive_document(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Archive a document. Checks user_id ownership (OWASP A01).
        Returns True if the document was archived, False if not found/not owned.
        """
        result = await db.execute(
            """UPDATE user_documents
               SET status = 'archived', archived_at = NOW(), updated_at = NOW()
               WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
                 AND status = 'active'""",
            doc_id,
            user_id,
        )
        return "UPDATE 1" in result

    # ─────────────────────────────────────────────
    # UPDATE — Soft delete
    # ─────────────────────────────────────────────

    async def soft_delete(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Soft-delete a document. Checks user_id ownership (OWASP A01).
        Returns True if the document was deleted, False if not found/not owned.
        """
        result = await db.execute(
            """UPDATE user_documents
               SET status = 'deleted', deleted_at = NOW(), updated_at = NOW()
               WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL""",
            doc_id,
            user_id,
        )
        return "UPDATE 1" in result

    # ─────────────────────────────────────────────
    # READ — Quota
    # ─────────────────────────────────────────────

    async def get_quota_used(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
    ) -> int:
        """
        Get total storage used by personal uploads (in bytes) for a user.
        Only counts non-deleted personal documents.
        """
        row = await db.fetchrow(
            """SELECT COALESCE(SUM(file_size_bytes), 0) AS used
               FROM user_documents
               WHERE user_id = $1 AND source = 'personal' AND deleted_at IS NULL""",
            user_id,
        )
        return row["used"]

    # ─────────────────────────────────────────────
    # AUDIT — Access log
    # ─────────────────────────────────────────────

    async def log_access(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        accessed_by: UUID,
        access_type: str,
        access_context: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Insert an entry into user_document_access_log (OWASP A09 audit trail).
        ip_address is cast to INET in PostgreSQL.
        """
        await db.execute(
            """INSERT INTO user_document_access_log (
                   user_document_id, accessed_by, access_type,
                   access_context, ip_address, user_agent
               )
               VALUES ($1, $2, $3, $4, $5::inet, $6)""",
            doc_id,
            accessed_by,
            access_type,
            access_context,
            ip_address,
            user_agent,
        )

    # ─────────────────────────────────────────────
    # WORKFLOW TAGS — Batch create
    # ─────────────────────────────────────────────

    async def create_workflow_tags(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        tags: List[Dict],
    ) -> None:
        """
        Batch insert workflow tags for a document.
        Each tag dict must have: workflow_code, document_code.
        Optional: is_auto_tagged (default True), relevance_score (default 1.0).
        Uses ON CONFLICT DO NOTHING to avoid duplicates.
        """
        if not tags:
            return

        # Build batch VALUES for a single INSERT
        values_parts: List[str] = []
        params: list = []
        idx = 1

        for tag in tags:
            workflow_code = tag["workflow_code"]
            document_code = tag["document_code"]
            is_auto_tagged = tag.get("is_auto_tagged", True)
            relevance_score = tag.get("relevance_score", 1.0)

            values_parts.append(
                f"(${idx}, ${idx + 1}, ${idx + 2}, ${idx + 3}, ${idx + 4})"
            )
            params.extend([
                doc_id, workflow_code, document_code,
                is_auto_tagged, relevance_score,
            ])
            idx += 5

        query = f"""
            INSERT INTO user_document_workflow_tags (
                user_document_id, workflow_code, document_code,
                is_auto_tagged, relevance_score
            )
            VALUES {', '.join(values_parts)}
            ON CONFLICT (user_document_id, workflow_code, document_code) DO NOTHING
        """
        await db.execute(query, *params)

    # ─────────────────────────────────────────────
    # READ — Version history
    # ─────────────────────────────────────────────

    async def find_versions(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        document_type: str,
    ) -> List[Dict]:
        """
        Find all documents of the same type for a user (version history).
        Includes archived and active documents, ordered newest first.
        """
        query = """
            SELECT * FROM user_documents
            WHERE user_id = $1
              AND document_type = $2
              AND deleted_at IS NULL
            ORDER BY created_at DESC
        """
        rows = await db.fetch(query, user_id, document_type)
        return [self._row_to_dict(row) for row in rows]

    # ─────────────────────────────────────────────
    # INTERNAL — Row conversion
    # ─────────────────────────────────────────────

    def _row_to_dict(self, row: asyncpg.Record) -> Optional[Dict]:
        """
        Convert asyncpg Record to dict with proper JSON parsing.
        asyncpg may return JSONB as str in some configurations;
        this ensures consistent dict output.
        Returns None if row is None (not found).
        """
        if not row:
            return None
        result = dict(row)
        # Parse JSONB fields that might come back as strings
        for field in ("extraction_data",):
            if field in result and isinstance(result[field], str):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return result


# Singleton instance
user_documents_repository = UserDocumentsRepository()
