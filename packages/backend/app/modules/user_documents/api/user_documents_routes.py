"""
User Documents API Routes — Coffre-fort documentaire endpoints.

Personal document vault for citizens: upload, classification (Gemini AI),
expiry tracking, workflow readiness checks, alerts, and generated documents.

All endpoints enforce user_id ownership (OWASP A01).
"""

import asyncio
import uuid as uuid_mod

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Path,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
import asyncpg
import base64
import hashlib
from loguru import logger

from app.database.connection import get_database, get_db_pool
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.core.cache import check_rate_limit
from app.core.cron_auth import verify_cron_auth
from app.modules.users.models import UserResponse

from ..models.user_document import (
    # Type aliases
    AlertSeverity,
    DocumentCategory,
    DocumentSource,
    DocumentStatus,
    ExpiryStatus,
    GenerationType,
    # Constants
    ALLOWED_MIME_TYPES,
    MAX_BULK_UPLOAD,
    MAX_FILE_SIZE_BYTES,
    SIGNED_URL_EXPIRY_SECONDS,
    VAULT_QUOTA_BYTES,
    # Request models
    UserDocumentBulkAction,
    UserDocumentUpdate,
    # Response models
    AlertResponse,
    DuplicateInfo,
    GeneratedDocumentResponse,
    ReadinessResult,
    UploadResult,
    UserDocumentListItem,
    UserDocumentListResponse,
    UserDocumentResponse,
    UserDocumentStats,
)
from ..repositories.user_documents_repository import user_documents_repository
from ..services.user_documents_service import validate_file_integrity


router = APIRouter()


# =============================================================================
# HELPER: Extract client info for audit
# =============================================================================

def _get_client_info(request: Request) -> tuple:
    """Extract IP address and user agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


# =============================================================================
# HELPER: Build UserDocumentResponse from DB row
# =============================================================================

def _build_document_response(row: Dict[str, Any]) -> UserDocumentResponse:
    """Convert a repository dict to a UserDocumentResponse with computed fields."""
    expiry_date = row.get("expiry_date")
    days_until_expiry = None
    expiry_status: str = "no_expiry"

    if expiry_date is not None:
        from datetime import date as date_type
        today = date_type.today()
        if hasattr(expiry_date, "date"):
            expiry_date_val = expiry_date.date()
        else:
            expiry_date_val = expiry_date
        delta = (expiry_date_val - today).days
        days_until_expiry = delta
        if delta < 0:
            expiry_status = "expired"
        elif delta <= 90:
            expiry_status = "expiring_soon"
        else:
            expiry_status = "valid"

    # Workflow tags are fetched separately; default to empty if not present
    workflow_tags = row.get("workflow_tags", [])
    if workflow_tags is None:
        workflow_tags = []

    return UserDocumentResponse(
        id=row["id"],
        user_id=row["user_id"],
        document_type=row.get("document_type", "unknown"),
        category=row.get("document_category", "other"),
        source=row.get("source", "personal"),
        status=row.get("status", "active"),
        file_name=row.get("file_name", ""),
        display_name=row.get("display_name"),
        file_size_bytes=row.get("file_size_bytes", 0),
        mime_type=row.get("mime_type", "application/octet-stream"),
        file_hash=row.get("file_hash", ""),
        thumbnail_path=row.get("thumbnail_path"),
        classification_method=row.get("classification_method"),
        classification_confidence=row.get("classification_confidence"),
        extraction_status=row.get("extraction_status", "pending"),
        extraction_confidence=row.get("extraction_confidence"),
        extracted_data=row.get("extraction_data"),
        holder_name=row.get("holder_name"),
        document_number=row.get("document_number"),
        issuing_authority=row.get("issuing_authority"),
        expiry_date=row.get("expiry_date"),
        issue_date=row.get("issue_date"),
        notes=row.get("notes"),
        color_label=row.get("color_label"),
        is_verified=row.get("is_verified", False),
        source_request_id=row.get("source_request_id"),
        days_until_expiry=days_until_expiry,
        expiry_status=expiry_status,
        workflow_tags=workflow_tags,
        created_at=row.get("created_at", datetime.now(timezone.utc)),
        updated_at=row.get("updated_at"),
    )


def _build_list_item(row: Dict[str, Any]) -> UserDocumentListItem:
    """Convert a repository dict to a lightweight UserDocumentListItem."""
    expiry_date = row.get("expiry_date")
    days_until_expiry = None
    expiry_status: str = "no_expiry"

    if expiry_date is not None:
        from datetime import date as date_type
        today = date_type.today()
        if hasattr(expiry_date, "date"):
            expiry_date_val = expiry_date.date()
        else:
            expiry_date_val = expiry_date
        delta = (expiry_date_val - today).days
        days_until_expiry = delta
        if delta < 0:
            expiry_status = "expired"
        elif delta <= 90:
            expiry_status = "expiring_soon"
        else:
            expiry_status = "valid"

    return UserDocumentListItem(
        id=row["id"],
        document_type=row.get("document_type", "unknown"),
        category=row.get("document_category", "other"),
        file_name=row.get("file_name", ""),
        display_name=row.get("display_name"),
        expiry_date=row.get("expiry_date"),
        days_until_expiry=days_until_expiry,
        expiry_status=expiry_status,
        status=row.get("status", "active"),
        source=row.get("source", "personal"),
        is_verified=row.get("is_verified", False),
        workflow_tags=row.get("workflow_tags", []) or [],
        thumbnail_path=row.get("thumbnail_path"),
        mime_type=row.get("mime_type", "application/octet-stream"),
        file_size_bytes=row.get("file_size_bytes", 0),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
    )


def _parse_cursor(cursor: Optional[str]) -> tuple:
    """Decode a base64 cursor into (created_at, id).

    Cursor format: base64("created_at_iso|uuid")
    Returns (None, None) if cursor is invalid or None.
    """
    if not cursor:
        return None, None
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        parts = decoded.split("|", 1)
        if len(parts) != 2:
            return None, None
        created_at = datetime.fromisoformat(parts[0])
        doc_id = UUID(parts[1])
        return created_at, doc_id
    except (ValueError, TypeError):
        return None, None


def _encode_cursor(created_at: datetime, doc_id: UUID) -> str:
    """Encode (created_at, id) into a base64 cursor string."""
    raw = f"{created_at.isoformat()}|{str(doc_id)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


# =============================================================================
# UPLOAD — Single document
# =============================================================================

@router.post(
    "/upload",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a personal document to the vault",
    description="""
    Upload a single document to the user's personal document vault.

    **Processing pipeline:**
    1. Validate file size (max 10 MB) and MIME type (PDF, JPG, PNG, WebP)
    2. Check user storage quota (100 MB)
    3. Compute SHA-256 hash for deduplication
    4. Store file in Supabase Storage
    5. Create DB record
    6. Trigger async Gemini classification + extraction

    **Deduplication:** If an identical file (same SHA-256 hash) already exists
    in the vault, the existing document is returned with status='duplicate'
    and HTTP 200. No new file is stored — zero Firebase/DB overhead.
    """,
)
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(..., description="Document file (PDF, JPG, PNG, WebP)"),
    document_type_hint: Optional[str] = Query(
        None,
        max_length=100,
        description="Optional hint for document type (e.g. 'passport'). "
                    "Gemini will classify if omitted.",
    ),
    notes: Optional[str] = Query(
        None,
        max_length=1000,
        description="Free-text notes for the document.",
    ),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Upload a personal document to the user vault."""
    # Rate limit: 10 uploads per minute per user
    is_allowed, remaining = await check_rate_limit(
        str(current_user.id), "/user-documents/upload", max_requests=10, window_seconds=60
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after": 60},
        )

    ip_address, user_agent = _get_client_info(request)

    # --- Validate MIME type ---
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Unsupported file type: {mime_type}",
                "code": "INVALID_FILE_TYPE",
                "allowed_types": ALLOWED_MIME_TYPES,
            },
        )

    # --- Read file content ---
    file_content = await file.read()
    file_size = len(file_content)

    # --- Validate file size ---
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "message": f"File too large: {file_size} bytes. Maximum is {MAX_FILE_SIZE_BYTES} bytes (10 MB).",
                "code": "FILE_TOO_LARGE",
                "max_size_bytes": MAX_FILE_SIZE_BYTES,
            },
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Empty file.", "code": "EMPTY_FILE"},
        )

    # --- Validate file integrity (OWASP A08: magic bytes) ---
    file_name = file.filename or "document"
    is_valid, integrity_error = validate_file_integrity(
        file_content, file_name, mime_type
    )
    if not is_valid:
        logger.warning(
            f"[UserDocuments] File integrity check failed for "
            f"'{file_name}': {integrity_error}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": integrity_error,
                "code": "FILE_INTEGRITY_FAILED",
            },
        )

    # --- Check quota ---
    quota_used = await user_documents_repository.get_quota_used(db, current_user.id)
    if quota_used + file_size > VAULT_QUOTA_BYTES:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail={
                "message": "Storage quota exceeded.",
                "code": "QUOTA_EXCEEDED",
                "quota_used_bytes": quota_used,
                "quota_max_bytes": VAULT_QUOTA_BYTES,
                "file_size_bytes": file_size,
            },
        )

    # --- Compute file hash ---
    file_hash = hashlib.sha256(file_content).hexdigest()

    # --- Duplicate detection — BLOCK true duplicates (Phase 1 dedup) ---
    existing = await user_documents_repository.find_duplicate(db, current_user.id, file_hash)
    if existing:
        # Same file already in vault → return existing doc, NO new Firebase upload
        logger.info(
            f"[UserDocuments] Duplicate blocked: hash={file_hash[:12]}, "
            f"existing_id={existing['id']}, user={current_user.id}"
        )
        try:
            await user_documents_repository.log_access(
                db=db,
                doc_id=existing["id"],
                accessed_by=current_user.id,
                access_type="duplicate_detected",
                access_context="vault_upload_dedup",
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception:
            pass

        response.status_code = status.HTTP_200_OK
        return UploadResult(
            id=existing["id"],
            status="duplicate",
            file_name=existing.get("file_name", file_name),
            file_size_bytes=existing.get("file_size_bytes", file_size),
            duplicate=DuplicateInfo(existing_document_id=existing["id"]),
            archived_count=0,
        )

    # --- Store file (no duplicate — proceed with upload) ---
    file_path = f"user-documents/{current_user.id}/{file_hash[:12]}_{file_name}"

    try:
        from app.modules.documents.services.storage_service import firebase_storage_service
        upload_result = await firebase_storage_service.upload_user_document(
            user_id=str(current_user.id),
            application_id=file_hash[:12],
            file=file_content,
            metadata={"source": "vault", "document_type_hint": document_type_hint or ""},
        )
        file_path = upload_result.file_path
    except Exception as e:
        logger.error(f"[UserDocuments] Storage upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to upload file to storage.", "code": "STORAGE_ERROR"},
        )

    # --- Create DB record ---
    doc_type = document_type_hint or "unknown"
    category = _infer_category(doc_type)

    try:
        row = await user_documents_repository.create_document(
            db=db,
            user_id=current_user.id,
            source="personal",
            document_type=doc_type,
            document_category=category,
            file_path=file_path,
            file_name=file_name,
            file_size_bytes=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            display_name=notes and file_name or None,
            notes=notes,
        )
    except asyncpg.UniqueViolationError:
        # Race condition: another concurrent upload of the same file won the insert.
        # Recover gracefully: return the existing document as duplicate.
        logger.info(
            f"[UserDocuments] Race condition caught: hash={file_hash[:12]}, "
            f"user={current_user.id}. Returning existing document."
        )
        existing = await user_documents_repository.find_duplicate(
            db, current_user.id, file_hash
        )
        if existing:
            response.status_code = status.HTTP_200_OK
            return UploadResult(
                id=existing["id"],
                status="duplicate",
                file_name=existing.get("file_name", file_name),
                file_size_bytes=existing.get("file_size_bytes", file_size),
                duplicate=DuplicateInfo(existing_document_id=existing["id"]),
                archived_count=0,
            )
        # Shouldn't happen — but fallback to generic error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Concurrent upload conflict.", "code": "RACE_CONDITION"},
        )
    except Exception as e:
        logger.error(f"[UserDocuments] DB insert failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to create document record.", "code": "DB_ERROR"},
        )

    doc_id = row["id"]

    # --- Auto-archive older versions of same document type ---
    archived_count = 0
    if doc_type and doc_type != "unknown":
        try:
            archived_result = await db.execute(
                """
                UPDATE user_documents
                SET status = 'archived', archived_at = NOW(),
                    replaces_document_id = $1, updated_at = NOW()
                WHERE user_id = $2 AND document_type = $3
                  AND id != $1 AND status = 'active' AND deleted_at IS NULL
                """,
                doc_id, current_user.id, doc_type,
            )
            if archived_result and "UPDATE" in str(archived_result):
                parts = str(archived_result).split()
                archived_count = int(parts[-1]) if parts[-1].isdigit() else 0
                if archived_count > 0:
                    logger.info(
                        f"[UserDocuments] Auto-archived {archived_count} older {doc_type} "
                        f"document(s) for user {current_user.id}"
                    )
        except Exception as e:
            logger.debug(f"[UserDocuments] Auto-archive failed (non-critical): {e}")

    # --- Log access ---
    try:
        await user_documents_repository.log_access(
            db=db,
            doc_id=doc_id,
            accessed_by=current_user.id,
            access_type="upload",
            access_context="vault_upload",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.warning(f"[UserDocuments] Access log failed (non-blocking): {e}")

    logger.info(
        f"[UserDocuments] Document uploaded: id={doc_id}, "
        f"user={current_user.id}, type={doc_type}, size={file_size}"
    )

    # --- Auto-classify hook (Phase 6) ---
    # If the user uploaded without a type hint AND has the auto_classify
    # permission active AND is within their hourly rate limit, spawn a
    # fire-and-forget background task that calls Gemini to tag the
    # document. Never blocks the upload response.
    if not document_type_hint:
        try:
            from app.modules.user_documents.services.auto_classify_service import (
                should_spawn_classify,
                auto_classify_background,
            )
            if await should_spawn_classify(db, current_user.id):
                pool = await get_db_pool()
                asyncio.create_task(
                    auto_classify_background(
                        doc_id=doc_id,
                        user_id=current_user.id,
                        content=file_content,
                        mime_type=mime_type,
                        file_name=file_name,
                        db_pool=pool,
                    )
                )
                logger.info(
                    f"[UserDocuments] Auto-classify task spawned for doc={doc_id}"
                )
        except Exception as exc:
            logger.debug(
                f"[UserDocuments] Auto-classify spawn failed (non-critical): {exc}"
            )

    return UploadResult(
        id=doc_id,
        status="processing",
        file_name=file_name,
        file_size_bytes=file_size,
        duplicate=duplicate_info,
        archived_count=archived_count,
    )


# =============================================================================
# UPLOAD — Bulk (max 5)
# =============================================================================

@router.post(
    "/bulk-upload",
    response_model=List[UploadResult],
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple documents (max 5)",
    description="""
    Upload up to 5 documents at once. Each file is validated individually.
    If one file fails validation, the others still proceed.
    """,
)
async def bulk_upload_documents(
    request: Request,
    files: List[UploadFile] = File(..., description="Up to 5 document files"),
    document_type_hint: Optional[str] = Query(
        None,
        max_length=100,
        description="Optional type hint applied to all files.",
    ),
    notes: Optional[str] = Query(
        None,
        max_length=1000,
        description="Notes applied to all files.",
    ),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Upload multiple documents in a single request."""
    # Rate limit: 3 bulk uploads per minute per user
    is_allowed, remaining = await check_rate_limit(
        str(current_user.id), "/user-documents/bulk-upload", max_requests=3, window_seconds=60
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after": 60},
        )

    if len(files) > MAX_BULK_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Too many files. Maximum is {MAX_BULK_UPLOAD}.",
                "code": "TOO_MANY_FILES",
                "max_files": MAX_BULK_UPLOAD,
            },
        )

    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "No files provided.", "code": "NO_FILES"},
        )

    ip_address, user_agent = _get_client_info(request)
    quota_used = await user_documents_repository.get_quota_used(db, current_user.id)
    results: List[UploadResult] = []

    for file in files:
        mime_type = file.content_type or "application/octet-stream"
        if mime_type not in ALLOWED_MIME_TYPES:
            logger.warning(f"[UserDocuments] Bulk upload: skipping {file.filename}, bad type {mime_type}")
            continue

        file_content = await file.read()
        file_size = len(file_content)

        if file_size == 0 or file_size > MAX_FILE_SIZE_BYTES:
            logger.warning(
                f"[UserDocuments] Bulk upload: skipping {file.filename}, "
                f"size={file_size} (limit={MAX_FILE_SIZE_BYTES})"
            )
            continue

        # --- Validate file integrity (OWASP A08: magic bytes) ---
        file_name_bulk = file.filename or "document"
        is_valid, integrity_error = validate_file_integrity(
            file_content, file_name_bulk, mime_type
        )
        if not is_valid:
            logger.warning(
                f"[UserDocuments] Bulk upload: skipping {file_name_bulk}, "
                f"integrity check failed: {integrity_error}"
            )
            continue

        if quota_used + file_size > VAULT_QUOTA_BYTES:
            logger.warning(f"[UserDocuments] Bulk upload: quota exceeded, stopping at {file.filename}")
            break

        file_hash = hashlib.sha256(file_content).hexdigest()

        # --- Duplicate detection — BLOCK true duplicates (Phase 1 dedup) ---
        existing = await user_documents_repository.find_duplicate(db, current_user.id, file_hash)
        if existing:
            logger.info(
                f"[UserDocuments] Bulk dedup: hash={file_hash[:12]}, "
                f"existing_id={existing['id']}, user={current_user.id}"
            )
            results.append(UploadResult(
                id=existing["id"],
                status="duplicate",
                file_name=file.filename or "document",
                file_size_bytes=file_size,
                duplicate=DuplicateInfo(existing_document_id=existing["id"]),
            ))
            continue

        file_name = file.filename or "document"
        file_path = f"user-documents/{current_user.id}/{file_hash[:12]}_{file_name}"

        try:
            from app.modules.documents.services.storage_service import firebase_storage_service
            upload_result = await firebase_storage_service.upload_user_document(
                user_id=str(current_user.id),
                application_id=file_hash[:12],
                file=file_content,
                metadata={"source": "vault_bulk"},
            )
            file_path = upload_result.file_path
        except Exception as e:
            logger.error(f"[UserDocuments] Bulk storage upload failed for {file_name}: {e}")
            continue

        doc_type = document_type_hint or "unknown"
        category = _infer_category(doc_type)

        try:
            row = await user_documents_repository.create_document(
                db=db,
                user_id=current_user.id,
                source="personal",
                document_type=doc_type,
                document_category=category,
                file_path=file_path,
                file_name=file_name,
                file_size_bytes=file_size,
                mime_type=mime_type,
                file_hash=file_hash,
                notes=notes,
            )
        except Exception as e:
            logger.error(f"[UserDocuments] Bulk DB insert failed for {file_name}: {e}")
            continue

        quota_used += file_size

        try:
            await user_documents_repository.log_access(
                db=db,
                doc_id=row["id"],
                accessed_by=current_user.id,
                access_type="upload",
                access_context="vault_bulk_upload",
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception:
            pass

        results.append(UploadResult(
            id=row["id"],
            status="processing",
            file_name=file_name,
            file_size_bytes=file_size,
        ))

    logger.info(
        f"[UserDocuments] Bulk upload completed: {len(results)}/{len(files)} files, "
        f"user={current_user.id}"
    )

    return results


# =============================================================================
# CHECK-HASH — Quick duplicate check by SHA-256 (Phase 1 dedup)
# =============================================================================


class HashCheckResponse(BaseModel):
    """Response for the hash check endpoint."""
    exists: bool = Field(..., description="True if a document with this hash exists in the vault.")
    document: Optional[Dict[str, Any]] = Field(
        None,
        description="Basic info about the existing document (id, display_name, file_name, expiry_date, status).",
    )


@router.get(
    "/check-hash/{file_hash}",
    response_model=HashCheckResponse,
    summary="Check if a file already exists in vault by SHA-256 hash",
    description="""
    Quick pre-upload check: given a SHA-256 hash computed client-side,
    determine if this exact file already exists in the user's vault.

    Returns the existing document's basic info if found, enabling
    the frontend to skip the upload entirely and reuse the vault copy.
    """,
)
async def check_hash(
    file_hash: str = Path(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 hex digest of the file (64 lowercase hex chars).",
    ),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Check if a document with the given SHA-256 hash exists in the user's vault."""
    # Rate limit: 30 checks per minute per user
    is_allowed, _ = await check_rate_limit(
        str(current_user.id), "/user-documents/check-hash", max_requests=30, window_seconds=60
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after": 60},
        )

    existing = await user_documents_repository.find_duplicate(
        db, current_user.id, file_hash
    )

    if not existing:
        return HashCheckResponse(exists=False, document=None)

    # Return lightweight info — enough for the frontend to decide
    expiry_status = None
    if existing.get("expiry_date"):
        from datetime import date as date_type
        exp = existing["expiry_date"]
        if isinstance(exp, date_type):
            today = date_type.today()
            if exp < today:
                expiry_status = "expired"
            elif (exp - today).days <= 30:
                expiry_status = "expiring_soon"
            else:
                expiry_status = "valid"

    return HashCheckResponse(
        exists=True,
        document={
            "id": str(existing["id"]),
            "display_name": existing.get("display_name") or existing.get("file_name", ""),
            "file_name": existing.get("file_name", ""),
            "document_type": existing.get("document_type", ""),
            "expiry_date": str(existing["expiry_date"]) if existing.get("expiry_date") else None,
            "expiry_status": expiry_status,
            "status": existing.get("status", "active"),
        },
    )


# =============================================================================
# LIST — User documents (cursor-based pagination)
# =============================================================================

@router.get(
    "/",
    response_model=UserDocumentListResponse,
    summary="List user documents with filtering and pagination",
    description="""
    List documents in the user's vault with cursor-based pagination.

    **Filters:**
    - `source`: personal, wizard_import, platform_generated
    - `category`: identity, vehicle, legal, financial, etc.
    - `status`: active, archived, expired
    - `expiry_status`: valid, expiring_soon, expired, no_expiry
    - `search`: Full-text search across display_name, file_name, notes, holder_name, document_number

    **Pagination:** Cursor-based (stable under concurrent inserts).
    Pass the `next_cursor` from a previous response to get the next page.
    """,
)
async def list_user_documents(
    source: Optional[DocumentSource] = Query(None, description="Filter by source"),
    category: Optional[DocumentCategory] = Query(None, description="Filter by category"),
    status_filter: Optional[DocumentStatus] = Query(
        None, alias="status", description="Filter by status"
    ),
    expiry_status: Optional[ExpiryStatus] = Query(None, description="Filter by expiry status"),
    search: Optional[str] = Query(None, max_length=200, description="Full-text search query"),
    cursor: Optional[str] = Query(None, description="Pagination cursor from previous response"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """List user documents with cursor-based pagination."""
    cursor_created_at, cursor_id = _parse_cursor(cursor)

    rows = await user_documents_repository.find_by_user(
        db=db,
        user_id=current_user.id,
        source=source,
        category=category,
        status=status_filter,
        expiry_status=expiry_status,
        search_query=search,
        cursor_created_at=cursor_created_at,
        cursor_id=cursor_id,
        limit=limit + 1,  # Fetch one extra to determine if there's a next page
    )

    has_next = len(rows) > limit
    if has_next:
        rows = rows[:limit]

    items = [_build_list_item(row) for row in rows]

    next_cursor = None
    if has_next and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last["created_at"], last["id"])

    # Get total count with SAME filters as list query
    count_conditions = ["user_id = $1", "deleted_at IS NULL", "status != 'deleted'"]
    count_params: list = [current_user.id]
    idx = 2
    if source:
        count_conditions.append(f"source = ${idx}")
        count_params.append(source)
        idx += 1
    if category:
        count_conditions.append(f"document_category = ${idx}")
        count_params.append(category)
        idx += 1
    if status_filter:
        count_conditions.append(f"status = ${idx}")
        count_params.append(status_filter)
        idx += 1
    count_where = " AND ".join(count_conditions)
    total_count_row = await db.fetchrow(
        f"SELECT COUNT(*) AS cnt FROM user_documents WHERE {count_where}",
        *count_params,
    )
    total_count = total_count_row["cnt"] if total_count_row else 0

    quota_used = await user_documents_repository.get_quota_used(db, current_user.id)

    return UserDocumentListResponse(
        items=items,
        next_cursor=next_cursor,
        total_count=total_count,
        quota_used_bytes=quota_used,
        quota_max_bytes=VAULT_QUOTA_BYTES,
    )


# =============================================================================
# LIST — Generated documents
# =============================================================================

@router.get(
    "/generated",
    response_model=List[GeneratedDocumentResponse],
    summary="List generated documents (receipts, certificates, etc.)",
)
async def list_generated_documents(
    generation_type: Optional[GenerationType] = Query(
        None, description="Filter by generation type"
    ),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """List platform-generated documents (receipts, certificates, attestations)."""
    cursor_created_at, cursor_id = _parse_cursor(cursor)

    rows = await user_documents_repository.find_generated(
        db=db,
        user_id=current_user.id,
        generation_type=generation_type,
        cursor_created_at=cursor_created_at,
        cursor_id=cursor_id,
        limit=limit,
    )

    results = []
    for row in rows:
        title_es = row.get("title_es") or row.get("display_name") or row.get("file_name", "")
        results.append(GeneratedDocumentResponse(
            id=row["id"],
            generation_type=row.get("generation_type", "receipt"),
            title=title_es,
            title_es=title_es,
            title_fr=row.get("title_fr"),
            title_en=row.get("title_en"),
            reference_number=row.get("reference_number"),
            file_name=row.get("file_name", ""),
            created_at=row.get("created_at", datetime.now(timezone.utc)),
            service_request_id=row.get("source_request_id"),
            verification_code=row.get("verification_code"),
        ))

    return results


# =============================================================================
# STATS — Vault statistics and quota
# =============================================================================

@router.get(
    "/stats",
    response_model=UserDocumentStats,
    summary="Get vault statistics and quota usage",
)
async def get_vault_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Get aggregate statistics for the user's document vault."""
    stats = await user_documents_repository.get_stats(db, current_user.id)

    total_size = stats.get("total_size_bytes", 0)
    quota_pct = round((total_size / VAULT_QUOTA_BYTES) * 100, 2) if VAULT_QUOTA_BYTES > 0 else 0.0

    return UserDocumentStats(
        total_active=stats.get("total_active", 0),
        personal_count=stats.get("personal_count", 0),
        wizard_count=stats.get("wizard_count", 0),
        generated_count=stats.get("generated_count", 0),
        quota_used_bytes=total_size,
        quota_max_bytes=VAULT_QUOTA_BYTES,
        quota_percentage=min(quota_pct, 100.0),
        expired_count=stats.get("expired_count", 0),
        expiring_count=stats.get("expiring_soon_count", 0),
    )


# =============================================================================
# READINESS — All popular workflows
# =============================================================================

@router.get(
    "/readiness",
    response_model=List[ReadinessResult],
    summary="Check document readiness for all popular workflows",
    description="""
    Returns readiness scores for the most common workflows.
    Tells the user which documents they already have, which are missing,
    and which are about to expire.
    """,
)
async def get_readiness_all(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Check document readiness for all popular workflows."""
    popular_workflows = await db.fetch(
        """SELECT DISTINCT wdr.workflow_code AS code,
               COALESCE(w.name_es, wdr.workflow_code) AS name_es
           FROM workflow_document_requirements wdr
           LEFT JOIN workflows w ON w.code = wdr.workflow_code
           WHERE wdr.is_active = TRUE
           ORDER BY wdr.workflow_code
           LIMIT 20"""
    )

    # Pre-fetch user's active documents ONCE to avoid N+1 queries
    user_doc_map = await _build_user_doc_map(db, current_user.id)

    results: List[ReadinessResult] = []
    for wf in popular_workflows:
        result = await _compute_readiness(db, current_user.id, wf["code"], user_doc_map=user_doc_map)
        results.append(result)

    return results


# =============================================================================
# READINESS — Specific workflow
# =============================================================================

@router.get(
    "/readiness/{workflow_code}",
    response_model=ReadinessResult,
    summary="Check document readiness for a specific workflow",
)
async def get_readiness_for_workflow(
    workflow_code: str = Path(..., description="Workflow code (e.g. PASAPORTE_BIOMETRICO)"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Check document readiness for a specific workflow."""
    result = await _compute_readiness(db, current_user.id, workflow_code)
    return result


# =============================================================================
# FOR-WORKFLOW — Documents matching a workflow
# =============================================================================

@router.get(
    "/for-workflow/{workflow_code}",
    response_model=List[UserDocumentResponse],
    summary="Get documents matching a specific workflow",
)
async def get_documents_for_workflow(
    workflow_code: str = Path(..., description="Workflow code"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Get user documents tagged for a specific workflow, sorted by relevance."""
    rows = await user_documents_repository.find_for_workflow(
        db=db,
        user_id=current_user.id,
        workflow_code=workflow_code,
    )

    return [_build_document_response(row) for row in rows]


# =============================================================================
# SEARCH — Full-text search
# =============================================================================

@router.get(
    "/search",
    response_model=List[UserDocumentListItem],
    summary="Full-text search across vault documents",
)
async def search_documents(
    q: str = Query(..., min_length=2, max_length=200, description="Search query"),
    category: Optional[DocumentCategory] = Query(None, description="Filter by category"),
    expiry_status: Optional[ExpiryStatus] = Query(None, description="Filter by expiry status"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Full-text search across document names, notes, holder names, and document numbers."""
    rows = await user_documents_repository.find_by_user(
        db=db,
        user_id=current_user.id,
        category=category,
        expiry_status=expiry_status,
        search_query=q,
        limit=limit,
    )

    return [_build_list_item(row) for row in rows]


# =============================================================================
# ALERTS — Active alerts
# =============================================================================

@router.get(
    "/alerts",
    response_model=List[AlertResponse],
    summary="Get active document alerts (expiry warnings, renewal suggestions)",
)
async def get_alerts(
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(20, ge=1, le=100, description="Maximum alerts"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Get active document alerts for the user."""
    conditions: List[str] = [
        "a.user_id = $1",
        "a.is_dismissed = FALSE",
    ]
    params: list = [current_user.id]
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
    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT a.* FROM user_document_alerts a
        WHERE {where_clause}
        ORDER BY
            CASE a.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
            a.created_at DESC
        LIMIT ${idx}
    """

    rows = await db.fetch(query, *params)

    results = []
    for row in rows:
        results.append(AlertResponse(
            id=row["id"],
            alert_type=row["alert_type"],
            severity=row["severity"],
            title=row.get("title_es", ""),
            title_es=row.get("title_es"),
            title_fr=row.get("title_fr"),
            title_en=row.get("title_en"),
            message=row.get("message_es", ""),
            message_es=row.get("message_es"),
            message_fr=row.get("message_fr"),
            message_en=row.get("message_en"),
            suggested_action=row.get("suggested_action"),
            action_params=row.get("action_params"),
            is_read=row.get("is_read", False),
            is_dismissed=row.get("is_dismissed", False),
            trigger_date=row.get("trigger_date"),
            created_at=row["created_at"],
        ))

    return results


# =============================================================================
# GET — Single document detail
# =============================================================================

@router.get(
    "/{document_id}",
    response_model=UserDocumentResponse,
    summary="Get document details",
)
async def get_document(
    request: Request,
    document_id: UUID = Path(..., description="Document UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Get full document details by ID. Enforces user ownership."""
    row = await user_documents_repository.find_by_id(db, document_id, current_user.id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found.", "code": "DOCUMENT_NOT_FOUND"},
        )

    # Fetch workflow tags
    tags_rows = await db.fetch(
        """SELECT workflow_code FROM user_document_workflow_tags
           WHERE user_document_id = $1
           ORDER BY relevance_score DESC""",
        document_id,
    )
    row["workflow_tags"] = [t["workflow_code"] for t in tags_rows]

    # Log access (non-blocking)
    ip_address, user_agent = _get_client_info(request)
    try:
        await user_documents_repository.log_access(
            db=db,
            doc_id=document_id,
            accessed_by=current_user.id,
            access_type="view",
            access_context="vault_detail",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.warning(f"[UserDocuments] Access log failed (non-blocking): {e}")

    return _build_document_response(row)


# =============================================================================
# DOWNLOAD — Signed URL
# =============================================================================

@router.get(
    "/{document_id}/download",
    response_model=Dict[str, Any],
    summary="Get a signed download URL for the document",
)
async def get_download_url(
    request: Request,
    document_id: UUID = Path(..., description="Document UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Generate a temporary signed URL for document download."""
    # Rate limit: 100 downloads per hour per user
    is_allowed, remaining = await check_rate_limit(
        str(current_user.id), "/user-documents/download", max_requests=100, window_seconds=3600
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after": 3600},
        )

    row = await user_documents_repository.find_by_id(db, document_id, current_user.id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found.", "code": "DOCUMENT_NOT_FOUND"},
        )

    file_path = row.get("file_path", "")
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "File path not available.", "code": "NO_FILE_PATH"},
        )

    try:
        from app.modules.documents.services.storage_service import firebase_storage_service
        signed_url = await firebase_storage_service.get_signed_url(
            file_path=file_path,
            expiration_hours=SIGNED_URL_EXPIRY_SECONDS / 3600,
        )
    except Exception as e:
        logger.error(f"[UserDocuments] Signed URL generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to generate download URL.", "code": "STORAGE_ERROR"},
        )

    # Log download access
    ip_address, user_agent = _get_client_info(request)
    try:
        await user_documents_repository.log_access(
            db=db,
            doc_id=document_id,
            accessed_by=current_user.id,
            access_type="download",
            access_context="vault_download",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass

    return {
        "url": signed_url,
        "expires_in_seconds": SIGNED_URL_EXPIRY_SECONDS,
        "file_name": row.get("file_name", "document"),
        "mime_type": row.get("mime_type", "application/octet-stream"),
    }


# =============================================================================
# THUMBNAIL — Get thumbnail
# =============================================================================

@router.get(
    "/{document_id}/thumbnail",
    response_model=Dict[str, Any],
    summary="Get thumbnail URL for the document",
)
async def get_thumbnail(
    document_id: UUID = Path(..., description="Document UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Get the thumbnail URL for a document. Returns signed URL if thumbnail exists."""
    row = await user_documents_repository.find_by_id(db, document_id, current_user.id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found.", "code": "DOCUMENT_NOT_FOUND"},
        )

    thumbnail_path = row.get("thumbnail_path")
    if not thumbnail_path:
        return {
            "url": None,
            "available": False,
            "message": "No thumbnail generated for this document.",
        }

    try:
        from app.modules.documents.services.storage_service import firebase_storage_service
        signed_url = await firebase_storage_service.get_signed_url(
            file_path=thumbnail_path,
            expiration_hours=SIGNED_URL_EXPIRY_SECONDS / 3600,
        )
    except Exception as e:
        logger.error(f"[UserDocuments] Thumbnail URL generation failed: {e}")
        return {
            "url": None,
            "available": False,
            "message": "Failed to generate thumbnail URL.",
        }

    return {
        "url": signed_url,
        "available": True,
        "expires_in_seconds": SIGNED_URL_EXPIRY_SECONDS,
    }


# =============================================================================
# SSE — Stream document processing status
# =============================================================================

@router.get(
    "/{document_id}/processing-status",
    summary="Stream document processing status (SSE)",
)
async def stream_processing_status(
    document_id: UUID = Path(...),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Stream real-time processing status as Server-Sent Events.

    After uploading a document, the frontend can subscribe to this endpoint
    to receive live updates on Gemini classification/extraction progress.

    Polls every 2 seconds for up to 2 minutes. Sends 'done' event when
    extraction reaches a terminal state (completed/failed).
    """
    import json as _json
    from fastapi.responses import StreamingResponse
    from app.database.connection import get_db_pool

    db_pool = await get_db_pool()

    async def event_stream():
        max_polls = 60  # Max 2 minutes (60 * 2s)
        poll_count = 0

        while poll_count < max_polls:
            async with db_pool.acquire() as conn:
                doc = await conn.fetchrow(
                    """SELECT extraction_status, extraction_confidence, document_type,
                              document_category, thumbnail_path
                       FROM user_documents WHERE id = $1 AND user_id = $2""",
                    document_id, current_user.id,
                )

            if not doc:
                yield f"data: {_json.dumps({'type': 'error', 'message': 'Document not found'})}\n\n"
                break

            status_data = {
                "type": "status",
                "extraction_status": doc["extraction_status"],
                "confidence": float(doc["extraction_confidence"] or 0),
                "document_type": doc["document_type"],
                "category": doc["document_category"],
                "has_thumbnail": bool(doc.get("thumbnail_path")),
            }
            yield f"data: {_json.dumps(status_data)}\n\n"

            # If terminal state, send done and stop
            if doc["extraction_status"] in ("completed", "failed"):
                yield f"data: {_json.dumps({'type': 'done', **status_data})}\n\n"
                break

            poll_count += 1
            await asyncio.sleep(2)

        # Timeout
        if poll_count >= max_polls:
            yield f"data: {_json.dumps({'type': 'timeout'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# =============================================================================
# VERSIONS — Document version history
# =============================================================================

@router.get(
    "/{document_id}/versions",
    response_model=List[UserDocumentListItem],
    summary="Get version history for a document type",
)
async def get_document_versions(
    document_id: UUID = Path(..., description="Document UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Get all versions (same document_type) for this document's type.

    Returns all documents of the same type for the user,
    ordered by creation date (newest first). Useful for tracking
    renewals (e.g. passport v1, passport v2).
    """
    row = await user_documents_repository.find_by_id(db, document_id, current_user.id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found.", "code": "DOCUMENT_NOT_FOUND"},
        )

    document_type = row.get("document_type", "unknown")
    versions = await user_documents_repository.find_versions(
        db=db,
        user_id=current_user.id,
        document_type=document_type,
    )

    return [_build_list_item(v) for v in versions]


# =============================================================================
# UPDATE — Metadata
# =============================================================================

@router.put(
    "/{document_id}",
    response_model=UserDocumentResponse,
    summary="Update document metadata",
)
async def update_document(
    document_id: UUID = Path(..., description="Document UUID"),
    body: UserDocumentUpdate = ...,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Update user-editable metadata (display_name, notes, color_label, category)."""
    updated = await user_documents_repository.update_metadata(
        db=db,
        doc_id=document_id,
        user_id=current_user.id,
        display_name=body.display_name,
        notes=body.notes,
        color_label=body.color_label,
        document_category=body.category,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found.", "code": "DOCUMENT_NOT_FOUND"},
        )

    return _build_document_response(updated)


# =============================================================================
# RECLASSIFY — Re-classify with Gemini
# =============================================================================

@router.put(
    "/{document_id}/reclassify",
    response_model=UserDocumentResponse,
    summary="Re-classify document using Gemini AI",
    description="""
    Trigger a fresh Gemini AI classification and extraction for this document.
    Useful when the initial classification was incorrect or when extraction
    data needs to be refreshed.
    """,
)
async def reclassify_document(
    request: Request,
    document_id: UUID = Path(..., description="Document UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Re-run Gemini classification and extraction on a document."""
    # Rate limit: 5 reclassifications per minute per user
    is_allowed, remaining = await check_rate_limit(
        str(current_user.id), "/user-documents/reclassify", max_requests=5, window_seconds=60
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after": 60},
        )

    from ..services.user_documents_service import user_documents_service
    from app.database.connection import get_db_pool

    row = await user_documents_repository.find_by_id(db, document_id, current_user.id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found.", "code": "DOCUMENT_NOT_FOUND"},
        )

    # Launch reclassification via service (downloads file + re-runs Gemini)
    db_pool = await get_db_pool()
    try:
        await user_documents_service.reclassify_document(
            db=db,
            doc_id=document_id,
            user_id=current_user.id,
            db_pool=db_pool,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "code": "RECLASSIFY_ERROR"},
        )

    # Fetch updated row (extraction_status will be 'processing')
    updated = await user_documents_repository.find_by_id(db, document_id, current_user.id)

    ip_address, user_agent = _get_client_info(request)
    try:
        await user_documents_repository.log_access(
            db=db,
            doc_id=document_id,
            accessed_by=current_user.id,
            access_type="reclassify",
            access_context="vault_reclassify",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass

    logger.info(
        f"[UserDocuments] Reclassification triggered: doc={document_id}, user={current_user.id}"
    )

    return _build_document_response(updated or row)


# =============================================================================
# ARCHIVE — Archive a document
# =============================================================================

@router.put(
    "/{document_id}/archive",
    response_model=Dict[str, Any],
    summary="Archive a document",
)
async def archive_document(
    request: Request,
    document_id: UUID = Path(..., description="Document UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Archive a document. It remains accessible but is hidden from the default list."""
    success = await user_documents_repository.archive_document(db, document_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found or already archived.", "code": "DOCUMENT_NOT_FOUND"},
        )

    # Audit log
    ip_address, user_agent = _get_client_info(request)
    try:
        await user_documents_repository.log_access(
            db=db,
            doc_id=document_id,
            accessed_by=current_user.id,
            access_type="archive",
            access_context="vault_archive",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass

    logger.info(f"[UserDocuments] Document archived: doc={document_id}, user={current_user.id}")
    return {"success": True, "document_id": str(document_id), "status": "archived"}


# =============================================================================
# ALERTS — Mark as read
# =============================================================================

@router.put(
    "/alerts/{alert_id}/read",
    response_model=Dict[str, Any],
    summary="Mark an alert as read",
)
async def mark_alert_read(
    alert_id: UUID = Path(..., description="Alert UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Mark a document alert as read."""
    result = await db.execute(
        """UPDATE user_document_alerts
           SET is_read = TRUE, updated_at = NOW()
           WHERE id = $1 AND user_id = $2""",
        alert_id,
        current_user.id,
    )

    if "UPDATE 0" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Alert not found.", "code": "ALERT_NOT_FOUND"},
        )

    return {"success": True, "alert_id": str(alert_id), "is_read": True}


# =============================================================================
# ALERTS — Dismiss
# =============================================================================

@router.put(
    "/alerts/{alert_id}/dismiss",
    response_model=Dict[str, Any],
    summary="Dismiss an alert",
)
async def dismiss_alert(
    alert_id: UUID = Path(..., description="Alert UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Dismiss a document alert permanently."""
    result = await db.execute(
        """UPDATE user_document_alerts
           SET is_dismissed = TRUE, dismissed_at = NOW(), updated_at = NOW()
           WHERE id = $1 AND user_id = $2""",
        alert_id,
        current_user.id,
    )

    if "UPDATE 0" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Alert not found.", "code": "ALERT_NOT_FOUND"},
        )

    return {"success": True, "alert_id": str(alert_id), "is_dismissed": True}


# =============================================================================
# DELETE — Soft delete
# =============================================================================

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a document",
)
async def delete_document(
    request: Request,
    document_id: UUID = Path(..., description="Document UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Soft-delete a document from the vault. The file is retained for audit purposes."""
    success = await user_documents_repository.soft_delete(db, document_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found.", "code": "DOCUMENT_NOT_FOUND"},
        )

    # Audit log for soft delete
    ip_address, user_agent = _get_client_info(request)
    try:
        await user_documents_repository.log_access(
            db=db,
            doc_id=document_id,
            accessed_by=current_user.id,
            access_type="delete",
            access_context="vault_soft_delete",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass

    logger.info(f"[UserDocuments] Document soft-deleted: doc={document_id}, user={current_user.id}")
    return None


# =============================================================================
# PERMANENT DELETE — RGPD right to erasure
# =============================================================================

@router.delete(
    "/{document_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a document (RGPD right to erasure)",
    description="""
    Permanently delete a document from the vault: removes the file from
    Firebase Storage, the thumbnail, and all associated DB records
    (workflow tags, access log, alerts). This action is irreversible.

    **RGPD Article 17:** Right to erasure ('right to be forgotten').
    """,
)
async def permanent_delete_document(
    request: Request,
    document_id: UUID = Path(..., description="Document UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Permanently delete document: Firebase file + all DB records."""
    # Find document with ownership check
    doc = await db.fetchrow(
        "SELECT id, file_path, thumbnail_path FROM user_documents WHERE id = $1 AND user_id = $2",
        document_id, current_user.id,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Document not found", "code": "NOT_FOUND"},
        )

    # Delete from Firebase Storage
    try:
        from app.modules.documents.services.storage_service import firebase_storage_service
        if doc["file_path"]:
            blob = firebase_storage_service.bucket.blob(doc["file_path"])
            if blob.exists():
                blob.delete()
        if doc.get("thumbnail_path"):
            blob = firebase_storage_service.bucket.blob(doc["thumbnail_path"])
            if blob.exists():
                blob.delete()
    except Exception as e:
        logger.warning(f"[RGPD] Firebase deletion failed (continuing): {e}")

    # Hard delete from DB (order matters for FK constraints)
    await db.execute(
        "DELETE FROM user_document_workflow_tags WHERE user_document_id = $1",
        document_id,
    )
    await db.execute(
        "DELETE FROM user_document_access_log WHERE user_document_id = $1",
        document_id,
    )
    await db.execute(
        "DELETE FROM user_document_alerts WHERE user_document_id = $1",
        document_id,
    )
    await db.execute(
        "DELETE FROM user_documents WHERE id = $1 AND user_id = $2",
        document_id, current_user.id,
    )

    # Audit log
    logger.info(f"[RGPD] Permanent delete: doc={document_id}, user={current_user.id}")

    # Invalidate cache
    try:
        from app.core.cache import get_cache
        cache = get_cache()
        if cache:
            await cache.delete(f"user_docs_stats:{current_user.id}")
    except Exception:
        pass

    return None


# =============================================================================
# BULK ACTION — Archive, delete, or download multiple documents
# =============================================================================

@router.post(
    "/bulk-action",
    response_model=Dict[str, Any],
    summary="Perform bulk operation on multiple documents",
    description="""
    Perform a bulk operation on up to 50 documents at once.

    **Supported actions:**
    - `archive`: Archive all specified documents
    - `delete`: Soft-delete all specified documents
    - `download`: Returns a list of signed download URLs

    Returns a summary with success/failure counts.
    """,
)
async def bulk_action(
    body: UserDocumentBulkAction,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Perform a bulk operation on multiple documents."""
    ip_address, user_agent = _get_client_info(request)
    succeeded = 0
    failed = 0
    download_urls: List[Dict[str, Any]] = []

    for doc_id in body.document_ids:
        try:
            if body.action == "archive":
                ok = await user_documents_repository.archive_document(db, doc_id, current_user.id)
                if ok:
                    succeeded += 1
                else:
                    failed += 1

            elif body.action == "delete":
                ok = await user_documents_repository.soft_delete(db, doc_id, current_user.id)
                if ok:
                    succeeded += 1
                else:
                    failed += 1

            elif body.action == "download":
                row = await user_documents_repository.find_by_id(db, doc_id, current_user.id)
                if row and row.get("file_path"):
                    try:
                        from app.modules.documents.services.storage_service import firebase_storage_service
                        signed_url = await firebase_storage_service.get_signed_url(
                            file_path=row["file_path"],
                            expiration_hours=SIGNED_URL_EXPIRY_SECONDS / 3600,
                        )
                        download_urls.append({
                            "document_id": str(doc_id),
                            "url": signed_url,
                            "file_name": row.get("file_name", "document"),
                        })
                        succeeded += 1
                    except Exception:
                        failed += 1
                else:
                    failed += 1

        except Exception as e:
            logger.warning(f"[UserDocuments] Bulk {body.action} failed for {doc_id}: {e}")
            failed += 1

    # Log bulk action
    try:
        for doc_id in body.document_ids:
            await user_documents_repository.log_access(
                db=db,
                doc_id=doc_id,
                accessed_by=current_user.id,
                access_type=f"bulk_{body.action}",
                access_context="vault_bulk_action",
                ip_address=ip_address,
                user_agent=user_agent,
            )
    except Exception:
        pass

    logger.info(
        f"[UserDocuments] Bulk {body.action}: {succeeded} succeeded, {failed} failed, "
        f"user={current_user.id}"
    )

    result: Dict[str, Any] = {
        "action": body.action,
        "total": len(body.document_ids),
        "succeeded": succeeded,
        "failed": failed,
    }
    if body.action == "download":
        result["download_urls"] = download_urls
        result["expires_in_seconds"] = SIGNED_URL_EXPIRY_SECONDS

    return result


# =============================================================================
# EXPORT — Start async ZIP export (background task)
# =============================================================================

@router.post(
    "/export",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Start an async export of vault documents as ZIP",
    description="""
    Initiate an asynchronous export of the user's documents.

    **Pipeline:**
    1. Validates that the user has documents to export
    2. Generates an `export_id` and launches a background task
    3. The background task downloads all files from Firebase, creates a ZIP
       archive organized by category folders, includes a `metadata.json`
       manifest, and uploads the ZIP back to Firebase
    4. Status is tracked in Redis cache (1-hour TTL)

    **Usage:**
    - Call this endpoint to start the export
    - Poll `GET /export/{export_id}/status` until `status == "completed"`
    - Then call `GET /export/{export_id}/download` to get a signed URL (1h expiry)

    **Rate limit:** 2 exports per 5 minutes per user.
    """,
)
async def start_export(
    request: Request,
    category: Optional[DocumentCategory] = Query(
        None, description="Export only documents in this category"
    ),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Start an async ZIP export of vault documents."""
    from ..services.export_service import export_service

    # Rate limit: 2 exports per 5 minutes per user
    is_allowed, remaining = await check_rate_limit(
        str(current_user.id), "/user-documents/export", max_requests=2, window_seconds=300
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after": 300},
        )

    export_id = str(uuid_mod.uuid4())

    # Count documents to export
    if category:
        count_row = await db.fetchrow(
            """SELECT COUNT(*) AS cnt FROM user_documents
               WHERE user_id = $1 AND document_category = $2
                 AND status = 'active' AND deleted_at IS NULL""",
            current_user.id,
            category,
        )
    else:
        count_row = await db.fetchrow(
            """SELECT COUNT(*) AS cnt FROM user_documents
               WHERE user_id = $1 AND status = 'active' AND deleted_at IS NULL""",
            current_user.id,
        )

    total_documents = count_row["cnt"] if count_row else 0

    if total_documents == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "No documents to export.", "code": "NO_DOCUMENTS"},
        )

    # Get the connection pool for the background task
    pool = await get_db_pool()

    # Launch background task (non-blocking)
    asyncio.create_task(
        export_service.generate_export(
            user_id=current_user.id,
            export_id=export_id,
            category=category,
            db_pool=pool,
        )
    )

    logger.info(
        f"[UserDocuments] Export started: export_id={export_id}, "
        f"user={current_user.id}, documents={total_documents}, category={category}"
    )

    return {
        "export_id": export_id,
        "status": "processing",
        "total_documents": total_documents,
        "category": category,
        "message": "Export started. Poll /export/{export_id}/status for progress.",
    }


# =============================================================================
# EXPORT — Check export status
# =============================================================================

@router.get(
    "/export/{export_id}/status",
    response_model=Dict[str, Any],
    summary="Check async export status",
    description="""
    Check the status of an async ZIP export.

    **Statuses:**
    - `processing` — Export is in progress
    - `completed` — ZIP is ready for download
    - `failed` — Export failed (see `error` field)

    Status is stored in Redis with a 1-hour TTL.
    If the export_id is not found, returns 404.
    """,
)
async def get_export_status(
    export_id: str = Path(..., description="Export ID returned by POST /export"),
    current_user: UserResponse = Depends(get_current_user),
):
    """Check status of an async vault export."""
    from ..services.export_service import export_service

    status_data = await export_service.get_export_status(export_id)

    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Export not found or expired.",
                "code": "EXPORT_NOT_FOUND",
            },
        )

    # Ownership check (OWASP A01)
    if status_data.get("user_id") != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Export not found or expired.",
                "code": "EXPORT_NOT_FOUND",
            },
        )

    return {
        "export_id": status_data.get("export_id"),
        "status": status_data.get("status"),
        "document_count": status_data.get("document_count"),
        "file_size": status_data.get("file_size"),
        "error": status_data.get("error"),
        "updated_at": status_data.get("updated_at"),
    }


# =============================================================================
# EXPORT — Download completed export
# =============================================================================

@router.get(
    "/export/{export_id}/download",
    response_model=Dict[str, Any],
    summary="Get download URL for completed export",
    description="""
    Get a signed download URL for a completed ZIP export.

    **Prerequisites:**
    - Export must be in `completed` status
    - Only the user who started the export can download

    **URL expiry:** 1 hour from generation.

    Returns 404 if export not found, 400 if not yet completed.
    """,
)
async def download_export(
    export_id: str = Path(..., description="Export ID returned by POST /export"),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a signed download URL for a completed vault export."""
    from ..services.export_service import export_service

    # First check status to give a useful error
    status_data = await export_service.get_export_status(export_id)

    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Export not found or expired.",
                "code": "EXPORT_NOT_FOUND",
            },
        )

    # Ownership check (OWASP A01)
    if status_data.get("user_id") != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Export not found or expired.",
                "code": "EXPORT_NOT_FOUND",
            },
        )

    current_status = status_data.get("status")

    if current_status == "processing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Export is still processing. Please wait.",
                "code": "EXPORT_PROCESSING",
                "status": "processing",
            },
        )

    if current_status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Export failed: {status_data.get('error', 'Unknown error')}",
                "code": "EXPORT_FAILED",
                "error": status_data.get("error"),
            },
        )

    # Generate signed URL
    download_url = await export_service.get_export_download_url(
        export_id=export_id,
        user_id=str(current_user.id),
    )

    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to generate download URL.",
                "code": "URL_GENERATION_FAILED",
            },
        )

    return {
        "export_id": export_id,
        "download_url": download_url,
        "expires_in_seconds": 3600,
        "file_size": status_data.get("file_size"),
        "document_count": status_data.get("document_count"),
    }


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

# NOTE: The previous local `_infer_category` helper was extracted during
# Phase 6 hardening into `app/modules/user_documents/utils/category_inference.py`
# so auto_classify_service.py can share the exact same mapping.
from app.modules.user_documents.utils.category_inference import (
    infer_category as _infer_category,
)


class _VaultDocInfo:
    """Lightweight container for vault document info used by readiness checks."""
    __slots__ = ("days", "doc_id", "display_name", "file_name")

    def __init__(self, days, doc_id, display_name, file_name):
        self.days = days
        self.doc_id = doc_id
        self.display_name = display_name
        self.file_name = file_name


async def _build_user_doc_map(
    db: asyncpg.Connection,
    user_id: UUID,
) -> Dict[str, "_VaultDocInfo"]:
    """Pre-fetch user's active vault documents and build a type -> best match map.

    Uses idx_ud_user_active partial index (status='active' AND deleted_at IS NULL).
    Called once and reused across multiple readiness checks to avoid N+1 queries.

    Returns a dict mapping document_type -> _VaultDocInfo with:
    - days: days until expiry (None if no expiry)
    - doc_id: UUID of the best matching vault document
    - display_name: human-readable name
    - file_name: original file name
    """
    from datetime import date as date_type

    user_docs = await db.fetch(
        """SELECT id, document_type, expiry_date, display_name, file_name
           FROM user_documents
           WHERE user_id = $1 AND status = 'active' AND deleted_at IS NULL""",
        user_id,
    )

    user_doc_map: Dict[str, _VaultDocInfo] = {}
    today = date_type.today()
    for doc in user_docs:
        doc_type = doc["document_type"]
        expiry = doc["expiry_date"]
        days = None
        if expiry is not None:
            if hasattr(expiry, "date"):
                expiry = expiry.date()
            days = (expiry - today).days

        info = _VaultDocInfo(
            days=days,
            doc_id=doc["id"],
            display_name=doc["display_name"] or doc["file_name"],
            file_name=doc["file_name"],
        )

        # Keep the best (longest expiry) for each type
        if doc_type not in user_doc_map or (
            days is not None and (
                user_doc_map[doc_type].days is None
                or days > user_doc_map[doc_type].days
            )
        ):
            user_doc_map[doc_type] = info

    return user_doc_map


async def _compute_readiness(
    db: asyncpg.Connection,
    user_id: UUID,
    workflow_code: str,
    user_doc_map: Optional[Dict[str, Optional[int]]] = None,
) -> ReadinessResult:
    """Compute document readiness for a specific workflow.

    Checks which required documents the user has in their vault,
    compares against the workflow's document requirements,
    and returns a readiness score.

    If user_doc_map is provided, skips the per-user DB query (N+1 optimization).
    """
    from ..models.user_document import ReadinessItem
    from app.core.cache import get_cache

    # Cache workflow requirements (1 hour TTL — rarely changes)
    cache = get_cache()
    cache_key = f"wf_requirements:{workflow_code}"

    required_docs = None
    if cache:
        cached_docs = await cache.get(cache_key)
        if cached_docs is not None:
            required_docs = cached_docs

    if not required_docs:
        # Get required documents for this workflow from service_document_assignments
        # joined with document_templates for human-readable names
        required_docs_rows = await db.fetch(
            """SELECT
                   wdr.document_code AS code,
                   COALESCE(wdr.document_name_es, wdr.document_code) AS name,
                   wdr.is_required
               FROM workflow_document_requirements wdr
               WHERE wdr.workflow_code = $1 AND wdr.is_active = TRUE
               ORDER BY wdr.display_order, wdr.document_code""",
            workflow_code,
        )
        required_docs = [dict(r) for r in required_docs_rows]

        # If no requirements found, try matching via workflow tags
        if not required_docs:
            required_docs_rows = await db.fetch(
                """SELECT DISTINCT
                       dt.template_code AS code,
                       COALESCE(dt.document_name_es, dt.template_code) AS name,
                       TRUE AS is_required
                   FROM user_document_workflow_tags wt
                   JOIN user_documents ud ON ud.id = wt.user_document_id
                   JOIN document_templates dt ON dt.template_code = ud.document_type
                   WHERE wt.workflow_code = $1
                   GROUP BY dt.template_code, dt.document_name_es
                   LIMIT 20""",
                workflow_code,
            )
            required_docs = [dict(r) for r in required_docs_rows]

        # Cache the result for 1 hour (workflow requirements rarely change)
        if cache and required_docs:
            await cache.set(cache_key, required_docs, ttl=3600)

    # Build user doc map if not pre-fetched (single-workflow call)
    if user_doc_map is None:
        user_doc_map = await _build_user_doc_map(db, user_id)

    ready_items: List[ReadinessItem] = []
    missing_items: List[ReadinessItem] = []
    expiring_items: List[ReadinessItem] = []

    total_required = len(required_docs)

    for req in required_docs:
        code = req["code"]
        name = req["name"]

        if code in user_doc_map:
            info = user_doc_map[code]
            vault_kwargs = {
                "vault_document_id": info.doc_id,
                "vault_display_name": info.display_name,
                "vault_file_name": info.file_name,
            }
            if info.days is not None and info.days <= 30:
                expiring_items.append(ReadinessItem(
                    code=code, name=name, status="expiring",
                    days_until_expiry=info.days,
                    **vault_kwargs,
                ))
            else:
                ready_items.append(ReadinessItem(
                    code=code, name=name, status="ready",
                    days_until_expiry=info.days,
                    **vault_kwargs,
                ))
        else:
            missing_items.append(ReadinessItem(
                code=code, name=name, status="missing",
                days_until_expiry=None,
            ))

    available = len(ready_items) + len(expiring_items)
    missing_count = len(missing_items)
    score = round((available / total_required) * 100, 1) if total_required > 0 else 100.0

    return ReadinessResult(
        workflow_code=workflow_code,
        readiness_score=score,
        total_required=total_required,
        available=available,
        missing_count=missing_count,
        ready=ready_items,
        missing=missing_items,
        expiring=expiring_items,
        can_start=missing_count == 0,
    )


# =============================================================================
# PYDANTIC MODELS — Agent Permissions
# =============================================================================

class AgentPermissionGrant(BaseModel):
    """Request body for granting an agent permission."""

    permission_type: str = Field(
        ...,
        description=(
            "Permission type to grant: 'prepare_renewal', 'prepare_request', "
            "'suggest_appointments', 'proactive_alerts', 'auto_classify'"
        ),
    )
    scope: Optional[str] = Field(
        None,
        max_length=100,
        description="Workflow code scope (e.g. 'PASAPORTE_BIOMETRICO') or None for all.",
    )
    level: int = Field(
        1,
        ge=1,
        le=2,
        description="Permission level: 1 = preparatory (suggestions only), 2 = proactive (auto-actions).",
    )


class AgentPermissionResponse(BaseModel):
    """Response model for an agent permission."""

    id: UUID
    permission_type: str
    scope: Optional[str] = None
    level: int = 1
    usage_count: int = 0
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    granted_at: datetime


class AgentMemoryResponse(BaseModel):
    """Response model for an agent memory entry (transparency)."""

    id: UUID
    memory_type: str
    content: str
    content_key: Optional[str] = None
    confidence: float = 0.5
    confirmation_count: int = 0
    rejection_count: int = 0
    learned_from: str
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# AGENT PERMISSIONS — List user's agent permissions
# =============================================================================

VALID_PERMISSION_TYPES = {
    "prepare_renewal",
    "prepare_request",
    "suggest_appointments",
    "proactive_alerts",
    "auto_classify",
}


# =============================================================================
# AGENT PERMISSIONS — Catalog (source of truth for frontend)
# =============================================================================

@router.get(
    "/agent/permission-catalog",
    response_model=Dict[str, Any],
    summary="List the authoritative agent permission catalog",
    description="""
    Return the authoritative catalog of agent permissions.

    This endpoint is the single source of truth consumed by the frontend
    `AgentSettingsPanel`. Each entry carries a `status` flag
    (`available` | `coming_soon`) so the UI renders disabled toggles with a
    clear "coming soon" badge for features whose backend tool is not wired
    yet — avoiding dead toggles that erode user trust.

    Derived from the BD CHECK constraint on `user_agent_permissions.permission_type`
    (migration 287_user_documents_vault.sql). Level 3 executive tools use a
    separate confirmation_code mechanism (Phase 5) and are NOT listed here.
    """,
)
async def get_agent_permission_catalog(
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Return the static agent permission catalog.

    Backed by `AGENT_PERMISSION_CATALOG` in chatbot_tools_authenticated so
    there is no duplication between frontend and backend. Cached at the
    CDN/HTTP layer via standard response headers (the catalog is static
    per release).
    """
    from app.modules.chatbot.services.chatbot_tools_authenticated import (
        AGENT_PERMISSION_CATALOG,
    )

    return {
        "catalog": AGENT_PERMISSION_CATALOG,
        "total": len(AGENT_PERMISSION_CATALOG),
    }


@router.get(
    "/agent/permissions",
    response_model=List[AgentPermissionResponse],
    summary="List user's agent permissions",
    description="""
    List all agent permissions granted by the current user.
    Shows what the AI assistant is allowed to do on behalf of the user.
    """,
)
async def list_agent_permissions(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """List user's active agent permissions."""
    rows = await db.fetch(
        """
        SELECT id, permission_type, scope, level, usage_count,
               last_used_at, is_active, granted_at
        FROM user_agent_permissions
        WHERE user_id = $1 AND is_active = TRUE
        ORDER BY granted_at DESC
        """,
        current_user.id,
    )

    return [
        AgentPermissionResponse(
            id=row["id"],
            permission_type=row["permission_type"],
            scope=row["scope"],
            level=row["level"],
            usage_count=row["usage_count"],
            last_used_at=row["last_used_at"],
            is_active=row["is_active"],
            granted_at=row["granted_at"],
        )
        for row in rows
    ]


# =============================================================================
# AGENT PERMISSIONS — Grant a new permission
# =============================================================================

@router.post(
    "/agent/permissions",
    response_model=AgentPermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant a new permission to the agent",
    description="""
    Grant a new autonomy permission to the AI assistant.

    **Permission types:**
    - `prepare_renewal`: Agent can prepare document renewal workflows
    - `prepare_request`: Agent can pre-fill service request forms
    - `suggest_appointments`: Agent can suggest available appointment slots
    - `proactive_alerts`: Agent can create proactive document alerts
    - `auto_classify`: Agent can auto-classify uploaded documents

    **Levels:**
    - Level 1 (preparatory): Agent suggests actions, user confirms
    - Level 2 (proactive): Agent acts autonomously within scope
    """,
)
async def grant_agent_permission(
    body: AgentPermissionGrant,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Grant a new permission to the agent. Upserts on conflict."""
    # Validate permission_type against allowed values
    if body.permission_type not in VALID_PERMISSION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Invalid permission type: {body.permission_type}",
                "code": "INVALID_PERMISSION_TYPE",
                "allowed_types": sorted(VALID_PERMISSION_TYPES),
            },
        )

    # Upsert: INSERT with ON CONFLICT DO UPDATE
    # IMPORTANT: the unique index idx_uap_unique is PARTIAL —
    #   CREATE UNIQUE INDEX ... WHERE (is_active = TRUE)
    # PostgreSQL requires the ON CONFLICT clause to repeat the partial
    # index's WHERE predicate to infer the right index. Without it,
    # the INSERT raises `InvalidColumnReference: no unique or exclusion
    # constraint matching the ON CONFLICT specification` and every
    # grantPermission request fails silently at the backend.
    # This was a pre-existing bug — confirmed by direct DB query showing
    # zero rows in user_agent_permissions since migration 287 shipped.
    row = await db.fetchrow(
        """
        INSERT INTO user_agent_permissions (
            user_id, permission_type, scope, level, is_active, granted_at
        )
        VALUES ($1, $2, $3, $4, TRUE, NOW())
        ON CONFLICT (user_id, permission_type, COALESCE(scope, '__null__'))
            WHERE is_active = TRUE
        DO UPDATE SET
            level = EXCLUDED.level,
            is_active = TRUE,
            revoked_at = NULL,
            granted_at = NOW()
        RETURNING id, permission_type, scope, level, usage_count,
                  last_used_at, is_active, granted_at
        """,
        current_user.id,
        body.permission_type,
        body.scope,
        body.level,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to grant permission.", "code": "GRANT_FAILED"},
        )

    logger.info(
        f"[UserDocuments] Agent permission granted: user={current_user.id}, "
        f"type={body.permission_type}, scope={body.scope}, level={body.level}"
    )

    return AgentPermissionResponse(
        id=row["id"],
        permission_type=row["permission_type"],
        scope=row["scope"],
        level=row["level"],
        usage_count=row["usage_count"],
        last_used_at=row["last_used_at"],
        is_active=row["is_active"],
        granted_at=row["granted_at"],
    )


# =============================================================================
# AGENT PERMISSIONS — Revoke a permission
# =============================================================================

@router.delete(
    "/agent/permissions/{permission_id}",
    response_model=Dict[str, Any],
    summary="Revoke an agent permission",
    description="Revoke a previously granted agent permission. Soft-revoke with timestamp.",
)
async def revoke_agent_permission(
    permission_id: UUID = Path(..., description="Permission UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Revoke an agent permission. Sets is_active=FALSE and records revoked_at."""
    result = await db.execute(
        """
        UPDATE user_agent_permissions
        SET is_active = FALSE, revoked_at = NOW()
        WHERE id = $1 AND user_id = $2 AND is_active = TRUE
        """,
        permission_id,
        current_user.id,
    )

    if "UPDATE 0" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Permission not found or already revoked.",
                "code": "PERMISSION_NOT_FOUND",
            },
        )

    logger.info(
        f"[UserDocuments] Agent permission revoked: user={current_user.id}, "
        f"permission={permission_id}"
    )

    return {
        "success": True,
        "permission_id": str(permission_id),
        "is_active": False,
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# AGENT MEMORY — List what the agent knows (transparency)
# =============================================================================

@router.get(
    "/agent/memory",
    response_model=List[AgentMemoryResponse],
    summary="List what the agent has learned about the user",
    description="""
    Transparency endpoint: shows all active agent memories for the current user.
    Memories are learned from user interactions, preferences, and behavioral patterns.
    Users can review and delete any memory they disagree with.
    """,
)
async def list_agent_memories(
    memory_type: Optional[str] = Query(
        None,
        description="Filter by memory type: preference, behavioral, correction, capability, context",
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum memories to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """List what the agent has learned about the user (active memories only)."""
    conditions = ["m.user_id = $1", "m.is_active = TRUE"]
    params: list = [current_user.id]
    idx = 2

    if memory_type is not None:
        valid_types = {"preference", "behavioral", "correction", "capability", "context"}
        if memory_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": f"Invalid memory type: {memory_type}",
                    "code": "INVALID_MEMORY_TYPE",
                    "allowed_types": sorted(valid_types),
                },
            )
        conditions.append(f"m.memory_type = ${idx}")
        params.append(memory_type)
        idx += 1

    params.append(limit)
    where_clause = " AND ".join(conditions)

    rows = await db.fetch(
        f"""
        SELECT m.id, m.memory_type, m.content, m.content_key,
               m.confidence, m.confirmation_count, m.rejection_count,
               m.learned_from, m.is_active, m.last_used_at,
               m.created_at, m.updated_at
        FROM user_agent_memory m
        WHERE {where_clause}
        ORDER BY m.confidence DESC, m.updated_at DESC
        LIMIT ${idx}
        """,
        *params,
    )

    return [
        AgentMemoryResponse(
            id=row["id"],
            memory_type=row["memory_type"],
            content=row["content"],
            content_key=row["content_key"],
            confidence=float(row["confidence"]) if row["confidence"] is not None else 0.5,
            confirmation_count=row["confirmation_count"],
            rejection_count=row["rejection_count"],
            learned_from=row["learned_from"],
            is_active=row["is_active"],
            last_used_at=row["last_used_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


# =============================================================================
# AGENT MEMORY — Delete a specific memory
# =============================================================================

@router.delete(
    "/agent/memory/{memory_id}",
    response_model=Dict[str, Any],
    summary="Delete a specific agent memory",
    description="Delete a specific memory the agent has learned. Soft-delete (deactivation).",
)
async def delete_agent_memory(
    memory_id: UUID = Path(..., description="Memory UUID"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Delete a specific agent memory. Sets is_active=FALSE."""
    result = await db.execute(
        """
        UPDATE user_agent_memory
        SET is_active = FALSE, updated_at = NOW()
        WHERE id = $1 AND user_id = $2 AND is_active = TRUE
        """,
        memory_id,
        current_user.id,
    )

    if "UPDATE 0" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Memory not found or already deleted.",
                "code": "MEMORY_NOT_FOUND",
            },
        )

    logger.info(
        f"[UserDocuments] Agent memory deleted: user={current_user.id}, memory={memory_id}"
    )

    return {
        "success": True,
        "memory_id": str(memory_id),
        "is_active": False,
    }


# =============================================================================
# AGENT MEMORY — Reset all memories
# =============================================================================

@router.delete(
    "/agent/memory",
    response_model=Dict[str, Any],
    summary="Reset all agent memories for this user",
    description="""
    Reset all agent memories. This is a 'forget everything' action.
    All active memories will be deactivated. This cannot be undone.
    The agent will start learning from scratch.
    """,
)
async def reset_agent_memories(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Reset all agent memories for this user. Deactivates all active memories."""
    result = await db.execute(
        """
        UPDATE user_agent_memory
        SET is_active = FALSE, updated_at = NOW()
        WHERE user_id = $1 AND is_active = TRUE
        """,
        current_user.id,
    )

    # Parse "UPDATE N"
    count = 0
    if result and result.startswith("UPDATE"):
        try:
            count = int(result.split()[-1])
        except (ValueError, IndexError):
            pass

    logger.info(
        f"[UserDocuments] Agent memories reset: user={current_user.id}, "
        f"deactivated={count}"
    )

    return {
        "success": True,
        "memories_deactivated": count,
        "message": f"All {count} agent memories have been reset.",
    }


# =============================================================================
# CRON ENDPOINT — Daily document scan
# =============================================================================

@router.post(
    "/internal/cron/document-scan",
    response_model=Dict[str, Any],
    summary="CRON: Daily document expiry scan",
    description="""
    Internal CRON endpoint for daily document expiry scanning.
    Called by Cloud Scheduler at 06:00 UTC daily.

    **Actions performed:**
    1. Create expiry alerts (90d, 60d, 30d, 7d, expired)
    2. Create proactive preparations for Level 2 users
    3. Mark newly expired documents
    4. Purge soft-deleted documents older than 30 days
    5. Deactivate stale agent memories

    **Security:** Requires X-Cron-Secret header authentication.
    """,
)
async def cron_document_scan(
    _auth: bool = Depends(verify_cron_auth),
    db: asyncpg.Connection = Depends(get_database),
):
    """CRON endpoint for daily document expiry scan. Called by Cloud Scheduler."""
    from ..services.proactive_agent_service import proactive_agent_service

    logger.info("[UserDocuments] CRON document scan started")

    try:
        results = await proactive_agent_service.daily_scan(db)
    except Exception as e:
        logger.error(f"[UserDocuments] CRON document scan failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Document scan failed: {str(e)}",
                "code": "CRON_SCAN_FAILED",
            },
        )

    logger.info(f"[UserDocuments] CRON document scan completed: {results}")

    return {
        "success": True,
        "scan_results": results,
    }
