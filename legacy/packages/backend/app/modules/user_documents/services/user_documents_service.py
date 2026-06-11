"""
Service layer for user_documents module (Coffre-fort documentaire).

Orchestrates document uploads, Gemini AI classification/extraction,
quota enforcement, workflow readiness checks, and access audit logging.

OWASP A01: All operations enforce user_id ownership via repository layer.
OWASP A08: File integrity validation via magic bytes (Software and Data Integrity).
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

import asyncpg
from loguru import logger

from app.core.cache import get_cache
from app.modules.user_documents.repositories.user_documents_repository import (
    user_documents_repository,
)
from app.modules.user_documents.models.user_document import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    SIGNED_URL_EXPIRY_SECONDS,
    VAULT_QUOTA_BYTES,
)


# =============================================================================
# OWASP A08 — File Integrity: Magic Bytes Validation
# =============================================================================

# Dangerous file extensions that must never be uploaded
DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".scr", ".pif", ".com", ".vbs", ".js",
    ".ps1", ".sh", ".msi", ".dll", ".sys", ".cpl", ".inf", ".reg",
}

# Set of allowed MIME types for fast lookup
ALLOWED_MIME_TYPES_SET: Set[str] = set(ALLOWED_MIME_TYPES)


def validate_file_integrity(
    content: bytes, filename: str, declared_mime: str
) -> Tuple[bool, str]:
    """
    Validate file integrity via magic bytes + extension blacklist.

    Returns (is_valid, error_message).

    OWASP A08: Software and Data Integrity Failures — prevents uploading
    files with spoofed Content-Type headers or dangerous extensions.

    Checks performed:
    1. Dangerous extension blacklist (.exe, .bat, .dll, etc.)
    2. Minimum file size (at least 4 bytes for magic byte detection)
    3. Magic bytes detection: compares actual file signature against
       the declared MIME type to catch Content-Type spoofing
    4. Declared MIME type must be in the allowed set

    Args:
        content: Raw file bytes
        filename: Original filename (used for extension check)
        declared_mime: The Content-Type declared by the client

    Returns:
        Tuple of (is_valid: bool, error_message: str).
        error_message is empty string when is_valid is True.
    """
    # 1. Check dangerous extensions
    ext = Path(filename).suffix.lower()
    if ext in DANGEROUS_EXTENSIONS:
        return False, f"File extension '{ext}' is not allowed"

    # 2. Check file is not empty / too small for magic byte detection
    if len(content) < 4:
        return False, "File is too small to be valid"

    # 3. Detect actual MIME from magic bytes
    detected_mime: Optional[str] = None
    header = content[:12]

    if header[:4] == b"%PDF":
        detected_mime = "application/pdf"
    elif header[:3] == b"\xff\xd8\xff":
        detected_mime = "image/jpeg"
    elif header[:8] == b"\x89PNG\r\n\x1a\n":
        detected_mime = "image/png"
    elif header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        detected_mime = "image/webp"

    # 4. If we could detect, verify it matches declared type
    if detected_mime:
        # Normalize common variations (image/jpg -> image/jpeg)
        declared_normalized = declared_mime.lower().replace("jpg", "jpeg")
        if detected_mime != declared_normalized:
            return (
                False,
                f"File content ({detected_mime}) does not match "
                f"declared type ({declared_mime})",
            )

    # 5. If we couldn't detect magic bytes, at least verify declared is allowed
    # Normalize before checking (image/jpg -> image/jpeg)
    declared_for_check = declared_mime.lower().replace("jpg", "jpeg")
    if declared_for_check not in ALLOWED_MIME_TYPES_SET:
        return False, f"MIME type '{declared_mime}' is not allowed"

    return True, ""


class UserDocumentsService:
    """
    Business logic layer for the user document vault (Mes Documents).

    Responsibilities:
    - File validation (size, MIME type, quota)
    - Deduplication via SHA-256 hash
    - Firebase Storage upload orchestration
    - Async Gemini AI classification + extraction (fire-and-forget)
    - Cursor-based paginated listing with filters
    - Audit trail (view/download access logging)
    - Workflow readiness scoring
    - Auto-import from wizard sessions and platform-generated documents
    - Alert management (expiry warnings, renewal suggestions)
    """

    # ─────────────────────────────────────────────
    # 1. UPLOAD
    # ─────────────────────────────────────────────

    async def upload_personal_document(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        file_content: bytes,
        file_name: str,
        mime_type: str,
        document_type_hint: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict:
        """
        Upload a personal document to the user vault.

        Steps:
        1. Validate file (size, MIME type)
        2. Check storage quota
        3. Compute SHA-256 hash for deduplication
        4. Check for existing duplicate
        5. Upload to Firebase Storage
        6. Create DB record (status='active', extraction_status='processing')
        7. Launch async Gemini classification + extraction
        8. Return UploadResult-compatible dict

        Args:
            db: asyncpg connection (for DB operations)
            user_id: Owner user ID
            file_content: Raw file bytes
            file_name: Original file name
            mime_type: MIME type of the file
            document_type_hint: Optional hint (e.g. 'passport', 'national_id')
            notes: Optional user notes

        Returns:
            Dict with id, status, file_name, file_size_bytes, duplicate info

        Raises:
            ValueError: File too large, unsupported MIME type, or quota exceeded
        """
        # --- Validate file size ---
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File too large: {file_size} bytes exceeds maximum "
                f"{MAX_FILE_SIZE_BYTES} bytes ({MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB)"
            )

        # --- Validate MIME type ---
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(
                f"Unsupported file type: {mime_type}. "
                f"Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
            )

        # --- Validate file integrity (OWASP A08: magic bytes) ---
        is_valid, integrity_error = validate_file_integrity(
            file_content, file_name, mime_type
        )
        if not is_valid:
            logger.warning(
                f"[UserDocuments] File integrity check failed for "
                f"'{file_name}': {integrity_error}"
            )
            raise ValueError(f"File integrity check failed: {integrity_error}")

        # --- Check storage quota ---
        quota_used = await user_documents_repository.get_quota_used(db, user_id)
        if quota_used + file_size > VAULT_QUOTA_BYTES:
            remaining = VAULT_QUOTA_BYTES - quota_used
            raise ValueError(
                f"Storage quota exceeded. Used: {quota_used} bytes, "
                f"remaining: {remaining} bytes, file: {file_size} bytes. "
                f"Quota: {VAULT_QUOTA_BYTES // (1024 * 1024)} MB"
            )

        # --- Compute SHA-256 hash ---
        file_hash = hashlib.sha256(file_content).hexdigest()

        # --- Check for duplicate ---
        duplicate_doc = await user_documents_repository.find_duplicate(
            db, user_id, file_hash
        )
        duplicate_info = None
        if duplicate_doc:
            duplicate_info = {"existing_document_id": duplicate_doc["id"]}

        # --- Upload to Firebase Storage ---
        from app.modules.documents.services.storage_service import (
            firebase_storage_service,
            ensure_storage_initialized,
        )

        await ensure_storage_initialized()

        # Create a temporary doc_id for the storage path
        # We use gen_random_uuid() from DB, but for the path we need it before INSERT.
        # Generate a UUID locally to match the storage path.
        import uuid as uuid_mod

        doc_id = uuid_mod.uuid4()
        storage_path = f"user-documents/{user_id}/personal/{doc_id}/{file_name}"

        # Upload raw bytes via GCS blob
        blob = firebase_storage_service.bucket.blob(storage_path)
        blob.metadata = {
            "uploadedBy": str(user_id),
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "source": "personal",
            "fileHash": file_hash,
        }
        blob.upload_from_string(file_content, content_type=mime_type, timeout=300)

        logger.info(
            f"Vault upload: {storage_path} ({file_size} bytes, hash={file_hash[:12]})"
        )

        # --- Determine initial document_type and category ---
        document_type = document_type_hint or "unknown"
        document_category = "other"

        # --- Create DB record ---
        doc_record = await user_documents_repository.create_document(
            db=db,
            user_id=user_id,
            source="personal",
            document_type=document_type,
            document_category=document_category,
            file_path=storage_path,
            file_name=file_name,
            file_size_bytes=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            display_name=None,
            notes=notes,
        )

        created_doc_id = doc_record["id"]

        # Set extraction_status to 'processing' immediately
        await user_documents_repository.update_extraction(
            db=db,
            doc_id=created_doc_id,
            extraction_data={},
            extraction_confidence=0.0,
            extraction_status="processing",
        )

        # --- Launch async Gemini processing (fire-and-forget) ---
        from app.database.connection import get_db_pool

        db_pool = await get_db_pool()
        asyncio.create_task(
            self._process_document_async(
                doc_id=created_doc_id,
                user_id=user_id,
                content=file_content,
                mime_type=mime_type,
                document_code=document_type,
                db_pool=db_pool,
            )
        )

        # --- Invalidate caches ---
        await self._invalidate_user_cache(user_id)

        # --- Return UploadResult ---
        return {
            "id": created_doc_id,
            "status": "processing",
            "file_name": file_name,
            "file_size_bytes": file_size,
            "duplicate": duplicate_info,
        }

    # ─────────────────────────────────────────────
    # 2. ASYNC GEMINI PROCESSING
    # ─────────────────────────────────────────────

    async def _process_document_async(
        self,
        doc_id: UUID,
        user_id: UUID,
        content: bytes,
        mime_type: str,
        document_code: str,
        db_pool: asyncpg.Pool,
    ) -> None:
        """
        Background task: Gemini AI classification + data extraction.

        Lazy-imports GeminiDocumentProcessor to avoid circular imports.
        Acquires a fresh DB connection from the pool (the request connection
        may be closed by the time this runs).

        On success: updates extraction_data, extraction_status='completed'.
        On failure: sets extraction_status='failed'.
        """
        try:
            # Lazy import to avoid circular dependency
            from app.modules.service_requests.services.gemini_document_processor import (
                GeminiDocumentProcessor,
            )

            processor = GeminiDocumentProcessor()

            # Run Gemini classification + extraction
            result = await processor.process(
                content=content,
                mime_type=mime_type,
                document_code=document_code,
                user_id=str(user_id),
            )

            async with db_pool.acquire() as conn:
                # Extract classification metadata from result
                extraction_data = result.get("extracted_data", {})
                extraction_confidence = result.get("confidence", 0.0)
                classified_type = result.get("document_type", document_code)
                classification_method = result.get("classification_method", "gemini")
                classification_confidence = result.get(
                    "classification_confidence", extraction_confidence
                )
                document_category = result.get("document_category")

                # Extract identity fields if present
                document_number = extraction_data.get("document_number")
                holder_name = extraction_data.get("holder_name") or extraction_data.get(
                    "full_name"
                )
                issue_date_str = extraction_data.get("issue_date")
                expiry_date_str = extraction_data.get("expiry_date")

                # Parse date strings safely
                issue_date = self._parse_date_safe(issue_date_str)
                expiry_date = self._parse_date_safe(expiry_date_str)

                # Update document with extraction results
                await user_documents_repository.update_extraction(
                    db=conn,
                    doc_id=doc_id,
                    extraction_data=extraction_data,
                    extraction_confidence=extraction_confidence,
                    extraction_status="completed",
                    document_number=document_number,
                    holder_name=holder_name,
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                    classification_method=classification_method,
                    classification_confidence=classification_confidence,
                    document_category=document_category,
                )

                # If the document type was classified differently, update it
                if classified_type and classified_type != document_code:
                    await conn.execute(
                        """UPDATE user_documents
                           SET document_type = $2, updated_at = NOW()
                           WHERE id = $1""",
                        doc_id,
                        classified_type,
                    )

                # Create workflow tags based on classification
                workflow_tags = self._build_workflow_tags(
                    classified_type or document_code, result
                )
                if workflow_tags:
                    await user_documents_repository.create_workflow_tags(
                        db=conn, doc_id=doc_id, tags=workflow_tags
                    )

            # After extraction update, generate thumbnail (non-critical)
            try:
                thumbnail_path = await self._generate_and_upload_thumbnail(
                    content, mime_type, str(user_id), str(doc_id), db_pool
                )
                if thumbnail_path:
                    async with db_pool.acquire() as conn2:
                        await conn2.execute(
                            "UPDATE user_documents SET thumbnail_path = $1, updated_at = NOW() WHERE id = $2",
                            thumbnail_path, doc_id,
                        )
            except Exception as thumb_err:
                logger.debug(f"Thumbnail generation failed (non-critical): {thumb_err}")

            # Async antivirus scan (fire-and-forget)
            try:
                asyncio.create_task(self._scan_file_async(doc_id, db_pool))
            except Exception:
                pass

            logger.info(
                f"Vault Gemini processing complete: doc_id={doc_id}, "
                f"type={classified_type}, confidence={extraction_confidence:.2f}"
            )

        except Exception as e:
            logger.error(
                f"Vault Gemini processing failed: doc_id={doc_id}, error={e}"
            )
            try:
                async with db_pool.acquire() as conn:
                    await user_documents_repository.update_extraction(
                        db=conn,
                        doc_id=doc_id,
                        extraction_data={"error": str(e)},
                        extraction_confidence=0.0,
                        extraction_status="failed",
                    )
            except Exception as db_err:
                logger.error(
                    f"Failed to update extraction_status to 'failed': "
                    f"doc_id={doc_id}, error={db_err}"
                )

    # ─────────────────────────────────────────────
    # 2b. ASYNC ANTIVIRUS SCAN (VirusTotal hash lookup)
    # ─────────────────────────────────────────────

    async def _scan_file_async(self, doc_id: UUID, db_pool: asyncpg.Pool) -> None:
        """
        Async file scan via SHA-256 hash lookup (VirusTotal API).
        Does NOT upload the file — only checks the hash against known malware.
        Flags document in DB if malicious/suspicious.

        Non-blocking, non-critical: failures are silently logged.
        """
        try:
            import httpx
            from app.config import settings

            vt_api_key = getattr(settings, "VIRUSTOTAL_API_KEY", None)
            if not vt_api_key:
                logger.debug("VirusTotal API key not configured, skipping scan")
                return

            # Fetch file_hash from DB
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT file_hash FROM user_documents WHERE id = $1", doc_id
                )
                if not row or not row["file_hash"]:
                    return
                file_hash = row["file_hash"]

            # VirusTotal file report by hash (free tier: 4 req/min)
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    f"https://www.virustotal.com/api/v3/files/{file_hash}",
                    headers={"x-apikey": vt_api_key},
                )

            if response.status_code == 200:
                data = response.json()
                stats = data.get("data", {}).get("attributes", {}).get(
                    "last_analysis_stats", {}
                )
                malicious = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)

                if malicious > 0 or suspicious > 0:
                    logger.warning(
                        f"[SECURITY] Suspicious file detected: doc_id={doc_id}, "
                        f"hash={file_hash}, malicious={malicious}, suspicious={suspicious}"
                    )
                    # Flag the document in DB
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE user_documents
                            SET notes = COALESCE(notes, '') || ' [SECURITY: flagged by antivirus scan]',
                                updated_at = NOW()
                            WHERE id = $1
                            """,
                            doc_id,
                        )
                else:
                    logger.debug(f"File scan clean: doc_id={doc_id}")

            elif response.status_code == 404:
                # Hash not found in VirusTotal — file is unknown (likely safe, custom document)
                logger.debug(f"File hash not in VirusTotal: {file_hash[:16]}...")
            else:
                logger.debug(f"VirusTotal API error: {response.status_code}")

        except Exception as e:
            logger.debug(f"Antivirus scan failed (non-critical): {e}")

    # ─────────────────────────────────────────────
    # 3. LIST DOCUMENTS
    # ─────────────────────────────────────────────

    async def list_documents(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        source: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        expiry_status: Optional[str] = None,
        search: Optional[str] = None,
        cursor_created_at: Optional[datetime] = None,
        cursor_id: Optional[UUID] = None,
        limit: int = 20,
    ) -> Dict:
        """
        List user documents with cursor-based pagination and filters.

        Returns a dict compatible with UserDocumentListResponse:
        - items: list of document dicts
        - next_cursor: opaque cursor string or None
        - total_count: total active documents
        - quota_used_bytes / quota_max_bytes: storage info
        """
        items = await user_documents_repository.find_by_user(
            db=db,
            user_id=user_id,
            source=source,
            category=category,
            status=status,
            expiry_status=expiry_status,
            search_query=search,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
            limit=limit,
        )

        # Build next_cursor from the last item if page is full
        next_cursor = None
        if len(items) == limit and items:
            last = items[-1]
            # Encode cursor as ISO timestamp + UUID separated by '|'
            cursor_ts = last["created_at"]
            if isinstance(cursor_ts, datetime):
                cursor_ts = cursor_ts.isoformat()
            next_cursor = f"{cursor_ts}|{last['id']}"

        # Get stats for quota info
        stats = await user_documents_repository.get_stats(db, user_id)

        return {
            "items": items,
            "next_cursor": next_cursor,
            "total_count": stats.get("total_active", 0),
            "quota_used_bytes": stats.get("personal_size_bytes", 0),
            "quota_max_bytes": VAULT_QUOTA_BYTES,
        }

    # ─────────────────────────────────────────────
    # 4. GET SINGLE DOCUMENT
    # ─────────────────────────────────────────────

    async def get_document(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get a single document with ownership check.
        Logs access (view) for audit trail.
        Loads associated workflow tags.
        """
        doc = await user_documents_repository.find_by_id(db, doc_id, user_id)
        if not doc:
            return None

        # Log access
        await user_documents_repository.log_access(
            db=db,
            doc_id=doc_id,
            accessed_by=user_id,
            access_type="view",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Load workflow tags
        tags = await self._load_workflow_tags(db, doc_id)
        doc["workflow_tags"] = tags

        return doc

    # ─────────────────────────────────────────────
    # 5. GET DOWNLOAD URL (signed)
    # ─────────────────────────────────────────────

    async def get_download_url(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        Generate a signed download URL (15 min expiry) for a document.
        Verifies ownership and logs download access.

        Returns:
            Signed URL string

        Raises:
            ValueError: Document not found or not owned
        """
        doc = await user_documents_repository.find_by_id(db, doc_id, user_id)
        if not doc:
            raise ValueError("Document not found or access denied")

        # Log download access
        await user_documents_repository.log_access(
            db=db,
            doc_id=doc_id,
            accessed_by=user_id,
            access_type="download",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Generate signed URL via Firebase Storage
        from app.modules.documents.services.storage_service import (
            firebase_storage_service,
            ensure_storage_initialized,
        )

        await ensure_storage_initialized()

        expiry_minutes = SIGNED_URL_EXPIRY_SECONDS // 60
        signed_url = await firebase_storage_service.get_signed_url(
            file_path=doc["file_path"],
            expiration_hours=expiry_minutes / 60,
        )

        return signed_url

    # ─────────────────────────────────────────────
    # 6. UPDATE METADATA
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
        Update user-editable metadata on a document.
        Delegates to repository (ownership check included).
        """
        return await user_documents_repository.update_metadata(
            db=db,
            doc_id=doc_id,
            user_id=user_id,
            display_name=display_name,
            notes=notes,
            color_label=color_label,
            document_category=document_category,
        )

    # ─────────────────────────────────────────────
    # 7. ARCHIVE
    # ─────────────────────────────────────────────

    async def archive_document(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Archive a document. Returns True if successful."""
        result = await user_documents_repository.archive_document(db, doc_id, user_id)
        if result:
            await self._invalidate_user_cache(user_id)
        return result

    # ─────────────────────────────────────────────
    # 8. DELETE (soft)
    # ─────────────────────────────────────────────

    async def delete_document(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Soft-delete a document. Returns True if successful."""
        result = await user_documents_repository.soft_delete(db, doc_id, user_id)
        if result:
            await self._invalidate_user_cache(user_id)
        return result

    # ─────────────────────────────────────────────
    # 9. RECLASSIFY (re-run Gemini)
    # ─────────────────────────────────────────────

    async def reclassify_document(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
        user_id: UUID,
        db_pool: asyncpg.Pool,
    ) -> Dict:
        """
        Re-run Gemini AI classification + extraction on an existing document.

        Downloads the file from Firebase, re-processes it, and updates the DB.
        Returns the updated document dict.

        Raises:
            ValueError: Document not found or access denied
        """
        doc = await user_documents_repository.find_by_id(db, doc_id, user_id)
        if not doc:
            raise ValueError("Document not found or access denied")

        # Mark as processing
        await user_documents_repository.update_extraction(
            db=db,
            doc_id=doc_id,
            extraction_data={},
            extraction_confidence=0.0,
            extraction_status="processing",
        )

        # Download file from Firebase
        from app.modules.documents.services.storage_service import (
            firebase_storage_service,
            ensure_storage_initialized,
        )

        await ensure_storage_initialized()

        download_result = await firebase_storage_service.download_file(
            file_path=doc["file_path"],
        )

        # Launch async Gemini re-processing
        asyncio.create_task(
            self._process_document_async(
                doc_id=doc_id,
                user_id=user_id,
                content=download_result.content,
                mime_type=doc["mime_type"],
                document_code=doc["document_type"],
                db_pool=db_pool,
            )
        )

        return {
            "id": doc_id,
            "status": "processing",
            "message": "Document reclassification started",
        }

    # ─────────────────────────────────────────────
    # 10. STATS
    # ─────────────────────────────────────────────

    async def get_stats(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
    ) -> Dict:
        """
        Get vault statistics including quota calculation.

        Returns a dict compatible with UserDocumentStats model.
        Uses cache with 30s TTL to reduce DB load on frequent dashboard calls.
        """
        cache = get_cache()
        cache_key = f"user_docs_stats:{user_id}"

        # Check cache first
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        raw_stats = await user_documents_repository.get_stats(db, user_id)

        personal_size = raw_stats.get("personal_size_bytes", 0)
        quota_percentage = (
            (personal_size / VAULT_QUOTA_BYTES * 100) if VAULT_QUOTA_BYTES > 0 else 0.0
        )

        result = {
            "total_active": raw_stats.get("total_active", 0),
            "personal_count": raw_stats.get("personal_count", 0),
            "wizard_count": raw_stats.get("wizard_count", 0),
            "generated_count": raw_stats.get("generated_count", 0),
            "quota_used_bytes": personal_size,
            "quota_max_bytes": VAULT_QUOTA_BYTES,
            "quota_percentage": round(min(quota_percentage, 100.0), 2),
            "expired_count": raw_stats.get("expired_count", 0),
            "expiring_count": raw_stats.get("expiring_soon_count", 0),
        }

        # Cache for 30 seconds
        await cache.set(cache_key, result, ttl=30)
        return result

    # ─────────────────────────────────────────────
    # 11. WORKFLOW READINESS
    # ─────────────────────────────────────────────

    async def get_readiness(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        workflow_code: str,
    ) -> Dict:
        """
        Check document readiness for a specific workflow.

        Compares workflow_document_requirements against user vault documents
        tagged for this workflow. Returns a ReadinessResult-compatible dict.
        Uses cache with 60s TTL per user+workflow combination.
        """
        cache = get_cache()
        cache_key = f"user_docs_readiness:{user_id}:{workflow_code}"

        # Check cache first
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        # 1. Get required documents for this workflow
        requirements = await db.fetch(
            """SELECT document_code, document_name_es, is_required, condition_type
               FROM workflow_document_requirements
               WHERE workflow_code = $1 AND is_active = TRUE
               ORDER BY display_order""",
            workflow_code,
        )

        if not requirements:
            return {
                "workflow_code": workflow_code,
                "readiness_score": 100.0,
                "total_required": 0,
                "available": 0,
                "missing_count": 0,
                "ready": [],
                "missing": [],
                "expiring": [],
                "can_start": True,
            }

        # 2. Get user's vault documents tagged for this workflow
        vault_docs = await user_documents_repository.find_for_workflow(
            db, user_id, workflow_code
        )

        # Index vault docs by document_type for fast lookup
        vault_by_type: Dict[str, Dict] = {}
        for doc in vault_docs:
            doc_type = doc.get("document_type", "")
            # Keep the most recent (first in list, sorted by relevance/date)
            if doc_type not in vault_by_type:
                vault_by_type[doc_type] = doc

        # Also index by template_code if available
        for doc in vault_docs:
            tpl = doc.get("template_code")
            if tpl and tpl not in vault_by_type:
                vault_by_type[tpl] = doc

        # 3. Compare requirements against vault
        ready_items: List[Dict] = []
        missing_items: List[Dict] = []
        expiring_items: List[Dict] = []

        for req in requirements:
            code = req["document_code"]
            name = req["document_name_es"]
            is_required = req["is_required"]

            matched_doc = vault_by_type.get(code)
            if matched_doc:
                expiry = matched_doc.get("expiry_date")
                days_until = None
                if expiry:
                    if isinstance(expiry, datetime):
                        days_until = (expiry.date() - datetime.now(timezone.utc).date()).days
                    else:
                        days_until = (expiry - datetime.now(timezone.utc).date()).days

                if days_until is not None and days_until <= 30:
                    expiring_items.append({
                        "code": code,
                        "name": name,
                        "status": "expiring",
                        "days_until_expiry": days_until,
                    })
                else:
                    ready_items.append({
                        "code": code,
                        "name": name,
                        "status": "ready",
                        "days_until_expiry": days_until,
                    })
            elif is_required:
                missing_items.append({
                    "code": code,
                    "name": name,
                    "status": "missing",
                    "days_until_expiry": None,
                })

        total_required = len([r for r in requirements if r["is_required"]])
        available = len(ready_items) + len(expiring_items)
        readiness_score = (
            (available / total_required * 100) if total_required > 0 else 100.0
        )

        result = {
            "workflow_code": workflow_code,
            "readiness_score": round(readiness_score, 1),
            "total_required": total_required,
            "available": available,
            "missing_count": len(missing_items),
            "ready": ready_items,
            "missing": missing_items,
            "expiring": expiring_items,
            "can_start": len(missing_items) == 0,
        }

        # Cache for 60 seconds
        await cache.set(cache_key, result, ttl=60)
        return result

    # ─────────────────────────────────────────────
    # 12. ALL READINESS (multiple workflows)
    # ─────────────────────────────────────────────

    async def get_all_readiness(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
    ) -> List[Dict]:
        """
        Check readiness for the user's most relevant workflows.

        Gets workflows from the user's service_requests history (most popular)
        and computes readiness for each.
        """
        # Get distinct workflow codes from user's past requests
        rows = await db.fetch(
            """SELECT DISTINCT fs.workflow_code
               FROM service_requests sr
               JOIN fiscal_services fs ON fs.id = sr.service_id
               WHERE sr.user_id = $1
                 AND fs.workflow_code IS NOT NULL
               ORDER BY fs.workflow_code
               LIMIT 10""",
            user_id,
        )

        workflow_codes = [r["workflow_code"] for r in rows if r["workflow_code"]]

        # If no history, get popular workflows
        if not workflow_codes:
            rows = await db.fetch(
                """SELECT DISTINCT workflow_code
                   FROM workflow_document_requirements
                   WHERE is_active = TRUE
                   ORDER BY workflow_code
                   LIMIT 5"""
            )
            workflow_codes = [r["workflow_code"] for r in rows]

        results = []
        for wf_code in workflow_codes:
            readiness = await self.get_readiness(db, user_id, wf_code)
            results.append(readiness)

        return results

    # ─────────────────────────────────────────────
    # 13. AUTO-IMPORT FROM WIZARD
    # ─────────────────────────────────────────────

    async def auto_import_from_wizard(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        service_request_id: UUID,
        documents: List[Dict],
    ) -> List[UUID]:
        """
        Auto-import documents from a completed wizard session into the vault.

        For each wizard document:
        - Skip if source_document_id already exists (idempotent)
        - Create user_documents entry with source='wizard_import'
        - Reference the same file_path (no file duplication)
        - Run post_process_for_vault for workflow tagging

        Args:
            db: asyncpg connection
            user_id: Owner user ID
            service_request_id: The service request that produced these documents
            documents: List of dicts with keys:
                - id (UUID): source document ID (from uploaded_files)
                - file_path (str): Firebase storage path
                - file_name (str): Original file name
                - file_size_bytes (int): File size
                - mime_type (str): MIME type
                - document_code (str): Document type code
                - template_code (str, optional): Template code
                - file_hash (str, optional): SHA-256 hash

        Returns:
            List of created user_document IDs
        """
        created_ids: List[UUID] = []

        for doc_info in documents:
            source_doc_id = doc_info.get("id")

            # Idempotency: skip if already imported (by source_document_id)
            if source_doc_id:
                existing = await db.fetchrow(
                    """SELECT id FROM user_documents
                       WHERE user_id = $1
                         AND source_document_id = $2
                         AND deleted_at IS NULL""",
                    user_id,
                    source_doc_id,
                )
                if existing:
                    created_ids.append(existing["id"])
                    continue

            # Content-based deduplication (3-level):
            # Level 1: SHA-256 hash match (100% reliable — same content)
            # Level 2: document_type + file_name (fallback when hash unavailable)
            # Level 3: source_document_id (already checked above — per-SR idempotence)
            document_code = doc_info.get("document_code", "unknown")
            file_hash = doc_info.get("file_hash", "")

            # If hash not in doc_info, try to fetch from uploaded_files table
            if not file_hash and source_doc_id:
                try:
                    stored_hash = await db.fetchval(
                        "SELECT file_hash FROM uploaded_files WHERE id = $1",
                        source_doc_id,
                    )
                    if stored_hash and len(stored_hash) == 64:
                        file_hash = stored_hash
                except Exception:
                    pass

            # Level 1: hash-based dedup (strongest)
            if file_hash and len(file_hash) == 64:  # Valid SHA-256
                hash_dup = await db.fetchrow(
                    """SELECT id FROM user_documents
                       WHERE user_id = $1 AND file_hash = $2
                         AND status = 'active' AND deleted_at IS NULL
                       LIMIT 1""",
                    user_id, file_hash,
                )
                if hash_dup:
                    created_ids.append(hash_dup["id"])
                    continue

            # Level 2: name-based dedup (fallback)
            name_dup = await db.fetchrow(
                """SELECT id FROM user_documents
                   WHERE user_id = $1 AND document_type = $2 AND file_name = $3
                     AND status = 'active' AND deleted_at IS NULL
                   LIMIT 1""",
                user_id, document_code, doc_info.get("file_name", ""),
            )
            if name_dup:
                created_ids.append(name_dup["id"])
                continue

            # No hash provided and download failed → generate placeholder from path
            if not file_hash:
                file_hash = hashlib.sha256(
                    doc_info.get("file_path", "").encode()
                ).hexdigest()

            record = await user_documents_repository.create_document(
                db=db,
                user_id=user_id,
                source="wizard_import",
                document_type=document_code,
                document_category="other",
                file_path=doc_info.get("file_path", ""),
                file_name=doc_info.get("file_name", "unknown"),
                file_size_bytes=doc_info.get("file_size_bytes", 0),
                mime_type=doc_info.get("mime_type", "application/octet-stream"),
                file_hash=file_hash,
                template_code=doc_info.get("template_code"),
                source_request_id=service_request_id,
                source_document_id=source_doc_id,
            )

            created_ids.append(record["id"])

            # Build and save workflow tags for readiness scoring
            workflow_tags = self._build_workflow_tags(document_code, {})
            if workflow_tags:
                try:
                    await user_documents_repository.create_workflow_tags(
                        db=db, doc_id=record["id"], tags=workflow_tags
                    )
                except Exception:
                    pass  # Non-blocking — tags are best-effort

        if created_ids:
            await self._invalidate_user_cache(user_id)

        return created_ids

    # ─────────────────────────────────────────────
    # 14. AUTO-IMPORT GENERATED DOCUMENT
    # ─────────────────────────────────────────────

    async def auto_import_generated(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        generation_type: str,
        file_path: str,
        file_name: str,
        file_size_bytes: int,
        mime_type: str,
        title_es: Optional[str] = None,
        title_fr: Optional[str] = None,
        title_en: Optional[str] = None,
        reference_number: Optional[str] = None,
        service_request_id: Optional[UUID] = None,
        verification_code: Optional[str] = None,
    ) -> UUID:
        """
        Import a platform-generated document (receipt, certificate, etc.)
        into the user vault.

        Returns the created document ID.
        """
        file_hash = hashlib.sha256(file_path.encode()).hexdigest()

        record = await user_documents_repository.create_document(
            db=db,
            user_id=user_id,
            source="platform_generated",
            document_type=generation_type,
            document_category="administrative",
            file_path=file_path,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            file_hash=file_hash,
            generation_type=generation_type,
            source_request_id=service_request_id,
            title_es=title_es,
            title_fr=title_fr,
            title_en=title_en,
            reference_number=reference_number,
            verification_code=verification_code,
        )

        await self._invalidate_user_cache(user_id)
        return record["id"]

    # ─────────────────────────────────────────────
    # 15. ALERTS — List
    # ─────────────────────────────────────────────

    async def get_alerts(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        severity: Optional[str] = None,
        is_read: Optional[bool] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Get document alerts for a user (expiry warnings, renewal suggestions, etc.).
        Uses cache with 60s TTL. Cache key includes filters for correctness.
        """
        cache = get_cache()
        cache_key = f"user_docs_alerts:{user_id}:{severity}:{is_read}:{limit}"

        # Check cache first
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        conditions = ["a.user_id = $1", "a.is_dismissed = FALSE"]
        params: list = [user_id]
        idx = 2

        if severity is not None:
            conditions.append(f"a.severity = ${idx}")
            params.append(severity)
            idx += 1

        if is_read is not None:
            conditions.append(f"a.is_read = ${idx}")
            params.append(is_read)
            idx += 1

        params.append(limit)
        limit_placeholder = f"${idx}"

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT a.* FROM user_document_alerts a
            WHERE {where_clause}
            ORDER BY
                CASE a.severity
                    WHEN 'critical' THEN 1
                    WHEN 'warning' THEN 2
                    WHEN 'info' THEN 3
                END,
                a.created_at DESC
            LIMIT {limit_placeholder}
        """
        rows = await db.fetch(query, *params)
        result = [dict(row) for row in rows]

        # Cache for 60 seconds
        await cache.set(cache_key, result, ttl=60)
        return result

    # ─────────────────────────────────────────────
    # 16. ALERTS — Mark read
    # ─────────────────────────────────────────────

    async def mark_alert_read(
        self,
        db: asyncpg.Connection,
        alert_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Mark an alert as read. Returns True if updated."""
        result = await db.execute(
            """UPDATE user_document_alerts
               SET is_read = TRUE, updated_at = NOW()
               WHERE id = $1 AND user_id = $2""",
            alert_id,
            user_id,
        )
        updated = "UPDATE 1" in result
        if updated:
            await self._invalidate_user_cache(user_id)
        return updated

    # ─────────────────────────────────────────────
    # 17. ALERTS — Dismiss
    # ─────────────────────────────────────────────

    async def dismiss_alert(
        self,
        db: asyncpg.Connection,
        alert_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Dismiss an alert. Returns True if updated."""
        result = await db.execute(
            """UPDATE user_document_alerts
               SET is_dismissed = TRUE, dismissed_at = NOW(), updated_at = NOW()
               WHERE id = $1 AND user_id = $2""",
            alert_id,
            user_id,
        )
        updated = "UPDATE 1" in result
        if updated:
            await self._invalidate_user_cache(user_id)
        return updated

    # ─────────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────────

    async def _invalidate_user_cache(self, user_id: UUID) -> None:
        """Invalidate all vault caches for a user.

        Called after any mutation that affects stats, readiness, or alerts:
        upload, delete, archive, auto-import, mark_alert_read, dismiss_alert.
        """
        cache = get_cache()
        try:
            await cache.delete(f"user_docs_stats:{user_id}")
            await cache.delete_pattern(f"user_docs_readiness:{user_id}:")
            await cache.delete_pattern(f"user_docs_alerts:{user_id}:")
            logger.debug(f"Invalidated user_documents cache for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate user_documents cache for user {user_id}: {e}")

    def _parse_date_safe(self, date_str: Optional[str]):
        """
        Parse a date string from extraction results.
        Handles multiple formats. Returns None on failure.
        """
        if not date_str or not isinstance(date_str, str):
            return None

        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%d %b %Y",
            "%d %B %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except (ValueError, AttributeError):
                continue
        return None

    # Mapping: wizard document_code → Gemini classified type
    # Used to normalize document codes from wizard to classification types
    WIZARD_CODE_TO_TYPE = {
        "dip": "national_id",
        "dip_ge": "national_id",
        "dip_ge_v1": "national_id",
        "documento_identidad": "national_id",
        "pasaporte_antiguo": "passport",
        "pasaporte": "passport",
        "passport": "passport",
        "partida_nacimiento": "birth_certificate",
        "certificado_nacimiento": "birth_certificate",
        "carnet_conducir": "driving_license",
        "permiso_conduccion": "driving_license",
        "permiso_residencia": "residence_permit",
        "tarjeta_residencia": "residence_permit",
        "photo_carnet": "photo",
        "fotografias": "photo",
        "foto_carnet": "photo",
        "certificado_medico": "medical_certificate",
        "examen_medico": "medical_certificate",
        "certificado_penales": "criminal_record",
        "antecedentes_penales": "criminal_record",
        "tarjeta_circulacion": "vehicle_registration",
        "permiso_circulacion": "vehicle_registration",
        "certificado_solvencia": "financial_certificate",
        "autorizacion_parental": "parental_authorization",
        "documento_representante_1": "legal_representative",
        "documento_representante_2": "legal_representative",
    }

    def _build_workflow_tags(
        self, document_code: str, gemini_result: Dict
    ) -> List[Dict]:
        """
        Build workflow tags based on document type classification.

        Maps common document types to the workflows that use them.
        Normalizes wizard document codes to Gemini classification types.
        Returns a list of tag dicts for create_workflow_tags().
        """
        # Normalize wizard codes to classification types
        normalized_code = self.WIZARD_CODE_TO_TYPE.get(
            document_code.lower(), document_code
        )

        # Mapping: document_type -> list of (workflow_code, relevance_score)
        type_to_workflows = {
            "passport": [
                ("PASAPORTE_BIOMETRICO", 1.0),
                ("PASAPORTE_NUEVO", 1.0),
                ("PASAPORTE_RENOVACION", 1.0),
            ],
            "national_id": [
                ("PASAPORTE_BIOMETRICO", 0.9),
                ("PASAPORTE_NUEVO", 0.9),
                ("RESIDENCIA", 0.9),
                ("CARNET_CONDUCIR", 0.9),
                ("CONTRATO_ONRC", 0.8),
            ],
            "birth_certificate": [
                ("PASAPORTE_BIOMETRICO", 0.9),
                ("PASAPORTE_NUEVO", 0.9),
                ("RESIDENCIA", 0.8),
            ],
            "driving_license": [
                ("CARNET_CONDUCIR", 1.0),
                ("MATRICULACION_DGT", 0.7),
            ],
            "residence_permit": [
                ("RESIDENCIA", 1.0),
            ],
            "photo": [
                ("PASAPORTE_BIOMETRICO", 0.8),
                ("PASAPORTE_NUEVO", 0.8),
                ("RESIDENCIA", 0.8),
                ("CARNET_CONDUCIR", 0.8),
                ("CARNET_FUNCIONARIO", 0.8),
            ],
            "vehicle_registration": [
                ("MATRICULACION_DGT", 1.0),
                ("INSPECCION_ITVE", 0.8),
                ("DUPLICADO_VEHICULO_DGT", 0.9),
            ],
            "medical_certificate": [
                ("CARNET_CONDUCIR", 0.8),
                ("RESIDENCIA", 0.5),
            ],
            "criminal_record": [
                ("RESIDENCIA", 0.9),
                ("PASAPORTE_BIOMETRICO", 0.7),
            ],
        }

        workflow_entries = type_to_workflows.get(normalized_code, [])

        # Also check Gemini result for additional workflow suggestions
        suggested_workflows = gemini_result.get("suggested_workflows", [])
        for wf in suggested_workflows:
            if isinstance(wf, dict):
                wf_code = wf.get("workflow_code")
                score = wf.get("relevance_score", 0.7)
                if wf_code:
                    workflow_entries.append((wf_code, score))
            elif isinstance(wf, str):
                workflow_entries.append((wf, 0.7))

        # Deduplicate by workflow_code (keep highest score)
        best_scores: Dict[str, float] = {}
        for wf_code, score in workflow_entries:
            if wf_code not in best_scores or score > best_scores[wf_code]:
                best_scores[wf_code] = score

        tags = []
        for wf_code, score in best_scores.items():
            tags.append({
                "workflow_code": wf_code,
                "document_code": document_code,
                "is_auto_tagged": True,
                "relevance_score": score,
            })

        return tags

    async def _load_workflow_tags(
        self,
        db: asyncpg.Connection,
        doc_id: UUID,
    ) -> List[str]:
        """Load workflow tag codes for a document."""
        rows = await db.fetch(
            """SELECT workflow_code FROM user_document_workflow_tags
               WHERE user_document_id = $1
               ORDER BY relevance_score DESC""",
            doc_id,
        )
        return [r["workflow_code"] for r in rows]

    # ─────────────────────────────────────────────
    # THUMBNAIL GENERATION
    # ─────────────────────────────────────────────

    async def _generate_and_upload_thumbnail(
        self,
        content: bytes,
        mime_type: str,
        user_id: str,
        doc_id: str,
        db_pool,
    ) -> Optional[str]:
        """Generate a thumbnail and upload to Firebase Storage.

        Supports JPEG/PNG/WebP images (direct resize) and PDF files
        (first page conversion via pdf2image). Returns the Firebase
        Storage path on success, or None if generation fails or
        dependencies are missing.

        The uploaded thumbnail gets CDN cache headers (30 days) for
        optimal delivery performance.
        """
        import io

        try:
            from PIL import Image
        except ImportError:
            logger.debug("Pillow not available, skipping thumbnail")
            return None

        try:
            thumb_image = None

            if mime_type in ("image/jpeg", "image/png", "image/webp"):
                # Image files — resize directly
                img = Image.open(io.BytesIO(content))
                img.thumbnail((200, 280), Image.Resampling.LANCZOS)
                thumb_image = img

            elif mime_type == "application/pdf":
                # PDF files — convert first page to image
                try:
                    from pdf2image import convert_from_bytes
                    images = convert_from_bytes(
                        content, first_page=1, last_page=1, dpi=72
                    )
                    if images:
                        images[0].thumbnail((200, 280), Image.Resampling.LANCZOS)
                        thumb_image = images[0]
                except Exception as pdf_err:
                    logger.debug(f"PDF thumbnail failed: {pdf_err}")
                    return None

            if not thumb_image:
                return None

            # Convert to JPEG bytes
            thumb_buffer = io.BytesIO()
            if thumb_image.mode in ("RGBA", "LA", "P"):
                thumb_image = thumb_image.convert("RGB")
            thumb_image.save(
                thumb_buffer, format="JPEG", quality=75, optimize=True
            )
            thumb_bytes = thumb_buffer.getvalue()

            # Upload to Firebase Storage
            from app.modules.documents.services.storage_service import (
                firebase_storage_service,
            )
            if not firebase_storage_service._initialized:
                await firebase_storage_service.initialize()

            thumb_path = f"user-documents/{user_id}/thumbnails/{doc_id}.jpg"
            blob = firebase_storage_service.bucket.blob(thumb_path)
            blob.metadata = {
                "uploadedBy": user_id,
                "uploadedAt": datetime.now(timezone.utc).isoformat(),
                "assetType": "thumbnail",
            }
            # Set cache-control for CDN (30 days)
            blob.cache_control = "public, max-age=2592000"
            blob.upload_from_string(
                thumb_bytes, content_type="image/jpeg", timeout=30
            )

            logger.info(
                f"Thumbnail generated: {thumb_path} ({len(thumb_bytes)} bytes)"
            )
            return thumb_path

        except Exception as e:
            logger.debug(f"Thumbnail generation error: {e}")
            return None


# Singleton instance
user_documents_service = UserDocumentsService()
