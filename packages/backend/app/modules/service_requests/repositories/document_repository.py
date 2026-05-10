"""
Repository for service_request_documents table.
Data access layer for document management.
"""
import asyncpg
from typing import Optional, List, Dict
from uuid import UUID
import json


class DocumentRepository:
    """Data access layer for service_request_documents table"""

    async def add_document(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        document_code: str,
        document_name: str,
        file_path: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        uploaded_by: UUID,
        source: str = "user_upload",
        file_hash: Optional[str] = None
    ) -> Dict:
        """
        Add a document to a service request.
        Uses UPSERT to replace existing document with same code.
        """
        query = """
            INSERT INTO service_request_documents (
                service_request_id, document_code, document_name,
                file_path, file_name, file_size, mime_type,
                uploaded_by, source, file_hash
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (service_request_id, document_code)
            DO UPDATE SET
                file_path = EXCLUDED.file_path,
                file_name = EXCLUDED.file_name,
                file_size = EXCLUDED.file_size,
                mime_type = EXCLUDED.mime_type,
                file_hash = EXCLUDED.file_hash,
                extraction_status = 'pending',
                extraction_data = '{}',
                extraction_confidence = NULL,
                is_valid = NULL,
                validation_errors = '[]',
                updated_at = NOW()
            RETURNING *
        """
        row = await db.fetchrow(
            query,
            service_request_id, document_code, document_name,
            file_path, file_name, file_size, mime_type,
            uploaded_by, source, file_hash
        )
        return self._row_to_dict(row)

    async def update_extraction(
        self,
        db: asyncpg.Connection,
        document_id: UUID,
        extraction_data: Dict,
        extraction_confidence: float,
        extraction_status: str
    ) -> None:
        """Update extraction results for a document.

        Note: We use json.dumps() + ::jsonb cast to properly store the dict as JSONB.
        This ensures the data is stored as a JSON object, not as a JSON string.
        When reading back, asyncpg returns a dict (parsed JSON).
        """
        # Serialize dict to JSON string, then cast to jsonb in PostgreSQL
        # This prevents double-encoding issues
        json_str = json.dumps(extraction_data) if extraction_data else '{}'
        await db.execute(
            """UPDATE service_request_documents
               SET extraction_data = $2::jsonb, extraction_confidence = $3,
                   extraction_status = $4, updated_at = NOW()
               WHERE id = $1""",
            document_id,
            json_str,
            extraction_confidence,
            extraction_status
        )

    async def validate_document(
        self,
        db: asyncpg.Connection,
        document_id: UUID,
        is_valid: bool,
        validation_errors: List[str],
        validated_by: UUID
    ) -> None:
        """Mark document as validated or invalid"""
        await db.execute(
            """UPDATE service_request_documents
               SET is_valid = $2, validation_errors = $3::jsonb,
                   validated_by = $4, validated_at = NOW(),
                   updated_at = NOW()
               WHERE id = $1""",
            document_id,
            is_valid,
            json.dumps(validation_errors),
            validated_by
        )

    async def find_by_hash(
        self,
        db: asyncpg.Connection,
        file_hash: str,
        exclude_request_id: Optional[UUID] = None
    ) -> List[Dict]:
        """Find documents with matching file hash for duplicate detection.

        Returns up to 5 matching documents from OTHER requests,
        joined with service_requests to get user_id.
        """
        if exclude_request_id:
            query = """
                SELECT srd.id, srd.service_request_id, srd.document_code,
                       srd.created_at, sr.user_id
                FROM service_request_documents srd
                JOIN service_requests sr ON sr.id = srd.service_request_id
                WHERE srd.file_hash = $1
                  AND srd.service_request_id != $2
                ORDER BY srd.created_at ASC
                LIMIT 5
            """
            rows = await db.fetch(query, file_hash, exclude_request_id)
        else:
            query = """
                SELECT srd.id, srd.service_request_id, srd.document_code,
                       srd.created_at, sr.user_id
                FROM service_request_documents srd
                JOIN service_requests sr ON sr.id = srd.service_request_id
                WHERE srd.file_hash = $1
                ORDER BY srd.created_at ASC
                LIMIT 5
            """
            rows = await db.fetch(query, file_hash)
        return [dict(row) for row in rows]

    async def find_by_id(
        self,
        db: asyncpg.Connection,
        document_id: UUID
    ) -> Optional[Dict]:
        """Find document by ID"""
        row = await db.fetchrow(
            "SELECT * FROM service_request_documents WHERE id = $1",
            document_id
        )
        return self._row_to_dict(row) if row else None

    async def find_by_request(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID
    ) -> List[Dict]:
        """Find all documents for a service request"""
        query = """
            SELECT * FROM service_request_documents
            WHERE service_request_id = $1
            ORDER BY created_at
        """
        rows = await db.fetch(query, service_request_id)
        return [self._row_to_dict(row) for row in rows]

    async def find_by_code(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        document_code: str
    ) -> Optional[Dict]:
        """Find specific document by code for a request"""
        query = """
            SELECT * FROM service_request_documents
            WHERE service_request_id = $1 AND document_code = $2
        """
        row = await db.fetchrow(query, service_request_id, document_code)
        return self._row_to_dict(row) if row else None

    async def find_pending_extraction(
        self,
        db: asyncpg.Connection,
        limit: int = 100
    ) -> List[Dict]:
        """Find documents pending extraction"""
        query = """
            SELECT srd.*, sr.workflow_code
            FROM service_request_documents srd
            JOIN service_requests sr ON sr.id = srd.service_request_id
            WHERE srd.extraction_status = 'pending'
            ORDER BY srd.created_at
            LIMIT $1
        """
        rows = await db.fetch(query, limit)
        return [self._row_to_dict(row) for row in rows]

    async def find_needing_review(
        self,
        db: asyncpg.Connection,
        limit: int = 100
    ) -> List[Dict]:
        """Find documents needing manual review"""
        query = """
            SELECT srd.*, sr.workflow_code, sr.reference
            FROM service_request_documents srd
            JOIN service_requests sr ON sr.id = srd.service_request_id
            WHERE srd.extraction_status = 'manual_review'
            ORDER BY srd.created_at
            LIMIT $1
        """
        rows = await db.fetch(query, limit)
        return [self._row_to_dict(row) for row in rows]

    async def delete_document(
        self,
        db: asyncpg.Connection,
        document_id: UUID
    ) -> bool:
        """Delete a document"""
        result = await db.execute(
            "DELETE FROM service_request_documents WHERE id = $1",
            document_id
        )
        return "DELETE 1" in result

    async def count_by_request(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID
    ) -> int:
        """Count documents for a request"""
        row = await db.fetchrow(
            "SELECT COUNT(*) FROM service_request_documents WHERE service_request_id = $1",
            service_request_id
        )
        return row["count"]

    def _row_to_dict(self, row: asyncpg.Record) -> Dict:
        """Convert asyncpg Record to dict with proper JSON parsing"""
        if not row:
            return {}
        result = dict(row)
        # Parse JSONB fields
        for field in ["extraction_data", "validation_errors"]:
            if field in result and isinstance(result[field], str):
                result[field] = json.loads(result[field])
        return result


# Singleton instance
document_repository = DocumentRepository()
