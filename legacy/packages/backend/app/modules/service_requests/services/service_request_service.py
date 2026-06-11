"""
Main Service Request Service.
Orchestrates the complete workflow for service requests.

NEW FLOW (User validation before Firebase upload):
1. preview_document_extraction() - Extract data, return to user for validation
2. validate_document() - User confirms, then upload to Firebase
"""
import asyncpg
import json
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from fastapi import HTTPException, UploadFile, status
from datetime import datetime, timedelta, timezone
import logging
import base64
import hashlib

from ..repositories.service_request_repository import service_request_repository
from ..repositories.document_repository import document_repository
from ..models.service_request import (
    ServiceRequestCreate,
    ServiceRequestResponse,
    RequiredDocument,
    ProvidedDocument,
    TariffBreakdown,
    DocumentUploadResponse,
    DocumentExtractionPreview,
    DocumentValidationRequest,
    DocumentValidationResponse,
    FieldIndicator,
    RiskAnalysisResult
)
from ..models.enums import ServiceRequestStatus, SolicitudType, WorkflowCode
from ..workflows.workflow_interface import WorkflowContext, RenovacionMotivo
from .tariff_service import tariff_service
from .tariff_calculator import tariff_calculator
from .schema_loader import schema_loader
from .gemini_document_processor import gemini_document_processor
from .workflow_engine import workflow_engine
from .agent_queue_service import agent_queue_service
from app.modules.assignment.services.auto_assignment_service import AutoAssignmentService

logger = logging.getLogger(__name__)

# File upload constraints
ALLOWED_MIME_TYPES = {
    "image/png", "image/jpeg", "image/jpg",
    "image/webp", "application/pdf"
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Magic bytes for file integrity validation (prevents corrupt/malicious uploads)
FILE_MAGIC_BYTES = {
    b'%PDF': 'application/pdf',
    b'\xff\xd8\xff': 'image/jpeg',       # JPEG/JPG
    b'\x89PNG': 'image/png',
    b'RIFF': 'image/webp',               # WebP starts with RIFF
}

# Preview expiry time — configurable via settings.PREVIEW_EXPIRY_MINUTES
# (default 30 min). Plan P2 — externalized from hardcoded constant.
from app.config import get_settings as _get_settings
PREVIEW_EXPIRY_MINUTES = _get_settings().PREVIEW_EXPIRY_MINUTES
PREVIEW_EXPIRY_SECONDS = PREVIEW_EXPIRY_MINUTES * 60

# Import preview cache (supports Redis or in-memory)
from .preview_cache import preview_cache


def _parse_jsonb_field(value: Any, field_name: str = "field") -> Dict:
    """
    Safely parse a JSONB field that might be stored as a double-encoded string.

    Handles legacy data where json.dumps() was used without ::jsonb cast,
    causing the dict to be stored as a JSON string instead of a JSON object.

    Args:
        value: The value from the database (could be dict, str, or None)
        field_name: Name of the field for logging purposes

    Returns:
        A dictionary (empty dict if parsing fails)
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            # Handle double-encoding (string within string)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            if isinstance(parsed, dict):
                return parsed
            logger.warning(f"Parsed {field_name} is not a dict: {type(parsed)}")
            return {}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse {field_name} as JSON")
            return {}
    logger.warning(f"Unexpected type for {field_name}: {type(value)}")
    return {}


class ServiceRequestService:
    """
    Main orchestration service for service requests.

    Handles:
    - Creation of service requests
    - Document uploads with processing
    - Status transitions
    - Tariff calculations
    """

    # ═══════════════════════════════════════════════════════════════
    # CREATE
    # ═══════════════════════════════════════════════════════════════

    async def create_request(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        data: ServiceRequestCreate
    ) -> ServiceRequestResponse:
        """
        Create a new service request.

        Args:
            db: Database connection
            user_id: The requesting user's ID
            data: Request creation data

        Returns:
            Complete service request response
        """
        # Get required documents for workflow with context
        form_data = data.form_data or {}
        required_docs = await self._get_required_documents(
            db,
            data.workflow_code,
            solicitud_type=data.solicitud_type.value if data.solicitud_type else "expedicion",
            motivo=form_data.get("motivo") if isinstance(form_data, dict) else None,
            form_data=form_data
        )

        if not required_docs:
            logger.warning(f"No document requirements found for workflow: {data.workflow_code}")

        # Create the request
        request = await service_request_repository.create(
            db=db,
            user_id=user_id,
            workflow_code=data.workflow_code,
            solicitud_type=data.solicitud_type.value,
            fiscal_service_id=data.fiscal_service_id,
            priority=data.priority.value,
            form_data=data.form_data
        )

        logger.info(f"Created service request: {request['reference']}")

        return await self._build_response(db, request, required_docs)

    # ═══════════════════════════════════════════════════════════════
    # DOCUMENT UPLOAD
    # ═══════════════════════════════════════════════════════════════

    async def upload_document(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID,
        document_code: str,
        file: UploadFile
    ) -> DocumentUploadResponse:
        """
        Upload and process a document for a service request.

        Args:
            db: Database connection
            request_id: The service request ID
            user_id: The uploading user's ID
            document_code: Code identifying the document type
            file: The uploaded file

        Returns:
            Document upload response with extraction results
        """
        # Verify request exists and belongs to user
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        if str(request["user_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Check status allows document upload
        allowed_statuses = [
            ServiceRequestStatus.DRAFT.value,
            ServiceRequestStatus.DOCUMENTS_REQUIRED.value
        ]
        if request["status"] not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot upload documents in status: {request['status']}"
            )

        # Validate file type
        self._validate_file(file)

        # Read file content
        content = await file.read()

        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Validate file integrity (magic bytes vs declared MIME)
        self._validate_file_integrity(content, file.content_type or '')

        # Import storage service (avoid circular import)
        try:
            from app.modules.documents.services.storage_service import firebase_storage_service
            # Upload to Firebase Storage
            file_path = await firebase_storage_service.upload_user_document(
                file_content=content,
                filename=file.filename,
                content_type=file.content_type,
                user_id=str(user_id),
                folder=f"service-requests/{request_id}"
            )
        except ImportError:
            # Fallback if storage_service not available
            logger.warning("storage_service not available, using placeholder path")
            file_path = f"service-requests/{request_id}/{file.filename}"

        # Get document name and extraction_schema_key from requirements
        params = self._extract_workflow_params(request)
        required_docs = await self._get_required_documents(db, request["workflow_code"], **params)
        doc_name = document_code
        extraction_schema_key = None
        for req_doc in required_docs:
            if req_doc.document_code == document_code:
                doc_name = req_doc.document_name
                extraction_schema_key = req_doc.extraction_schema_key
                # Note: document_constraints not needed here (validate path has no full risk analysis)
                break

        # Save document record
        doc = await document_repository.add_document(
            db=db,
            service_request_id=request_id,
            document_code=document_code,
            document_name=doc_name,
            file_path=file_path,
            file_name=file.filename,
            file_size=len(content),
            mime_type=file.content_type,
            uploaded_by=user_id
        )

        # Process document (extraction) with schema key
        processing_result = await self._process_document(
            content=content,
            mime_type=file.content_type,
            document_code=document_code,
            extraction_schema_key=extraction_schema_key
        )

        # Update extraction results
        await document_repository.update_extraction(
            db=db,
            document_id=doc["id"],
            extraction_data=processing_result["extraction"],
            extraction_confidence=processing_result["confidence"],
            extraction_status=processing_result["status"]
        )

        # NOTE: Gemini processing is now logged centrally in
        # gemini_document_processor.process() via _log_to_audit()

        # Check if all documents are now provided
        await self._check_completion(db, request_id, user_id)

        logger.info(
            f"Document uploaded: {document_code} for request {request['reference']} "
            f"(confidence: {processing_result['confidence']:.2%})"
        )

        return DocumentUploadResponse(
            document_id=doc["id"],
            document_code=document_code,
            extraction=processing_result["extraction"],
            confidence=processing_result["confidence"],
            processor=processing_result["processor"],
            status=processing_result["status"],
            needs_review=processing_result["status"] == "manual_review"
        )

    # ═══════════════════════════════════════════════════════════════
    # NEW FLOW: PREVIEW + VALIDATE
    # ═══════════════════════════════════════════════════════════════

    async def preview_document_extraction(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID,
        document_code: str,
        file: UploadFile,
        frontend_extractions: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> DocumentExtractionPreview:
        """
        STEP 1: Extract document data WITHOUT uploading to Firebase.

        The file content is stored temporarily in memory.
        User must call validate_document() to confirm and finalize upload.

        Args:
            db: Database connection
            request_id: The service request ID
            user_id: The user ID
            document_code: Document type code
            file: The uploaded file
            frontend_extractions: Optional dict of existing document extractions from
                                  frontend preview cache for cross-document risk analysis.
                                  Format: {doc_code: {extraction: {...}, confidence: float}}

        Returns:
            DocumentExtractionPreview with extracted data for user validation
        """
        # Verify request exists and belongs to user
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        if str(request["user_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Check status allows document upload
        allowed_statuses = [
            ServiceRequestStatus.DRAFT.value,
            ServiceRequestStatus.DOCUMENTS_REQUIRED.value
        ]
        if request["status"] not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot upload documents in status: {request['status']}"
            )

        # Validate file
        self._validate_file(file)

        # Read file content
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Validate file integrity (magic bytes vs declared MIME)
        self._validate_file_integrity(content, file.content_type or '')

        # Get document name, extraction_schema_key, and workflow constraints from requirements
        params = self._extract_workflow_params(request)
        required_docs = await self._get_required_documents(db, request["workflow_code"], **params)
        doc_name = document_code
        extraction_schema_key = None
        document_constraints = None
        for req_doc in required_docs:
            if req_doc.document_code == document_code:
                doc_name = req_doc.document_name
                extraction_schema_key = req_doc.extraction_schema_key
                # Extract workflow-specific constraints from config (e.g., required_tipo_certificado)
                if req_doc.config:
                    constraint_keys = [k for k in req_doc.config if k.startswith("required_")]
                    if constraint_keys:
                        document_constraints = {k: req_doc.config[k] for k in constraint_keys}
                break

        # Get existing documents for identity consistency checks
        # Merge DB documents with frontend preview cache for cross-document validation
        existing_docs_raw = await document_repository.find_by_request(db, request_id)
        existing_documents = {
            d["document_code"]: {
                "extraction": d.get("extraction_data", {}),
                "confidence": d.get("extraction_confidence", 0)
            }
            for d in existing_docs_raw
        }

        # Merge frontend preview extractions (prioritize frontend for unsaved previews)
        # This enables cross-document risk analysis even before documents are saved to DB
        if frontend_extractions:
            for doc_code, doc_data in frontend_extractions.items():
                # Only add if not already in DB (DB documents take precedence)
                if doc_code not in existing_documents:
                    existing_documents[doc_code] = {
                        "extraction": doc_data.get("extraction", doc_data),
                        "confidence": doc_data.get("confidence", 0.5)
                    }
            logger.info(
                f"Merged {len(frontend_extractions)} frontend previews for cross-document validation. "
                f"Total documents for comparison: {list(existing_documents.keys())}"
            )

        # Get form data and workflow code from request
        form_data = request.get("form_data", {})
        workflow_code = request.get("workflow_code", "")

        # Process document with Gemini/Tesseract + Risk Analysis (NO Firebase upload yet)
        # Pass extraction_schema_key for proper schema lookup
        # Pass workflow_code for identity verification config
        # Pass document_constraints for workflow-specific field requirements
        processing_result = await self._process_document(
            content=content,
            mime_type=file.content_type,
            document_code=document_code,
            request_id=str(request_id),
            user_id=str(user_id),
            existing_documents=existing_documents if existing_documents else None,
            form_data=form_data if form_data else None,
            extraction_schema_key=extraction_schema_key,
            workflow_code=workflow_code,
            document_constraints=document_constraints
        )

        # Generate preview ID (unique for this extraction session)
        preview_id = f"prev_{hashlib.sha256(f'{request_id}{document_code}{datetime.now(timezone.utc).isoformat()}'.encode()).hexdigest()[:16]}"

        # Calculate expiry time
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=PREVIEW_EXPIRY_MINUTES)

        # Get risk analysis
        risk_analysis = processing_result.get("risk_analysis", {})

        # Build field-level indicators for UI
        field_indicators = self._build_field_indicators(
            extraction=processing_result["extraction"],
            confidence=processing_result["confidence"],
            risk_analysis=risk_analysis,
            document_code=document_code,
            extraction_schema_key=extraction_schema_key
        )

        # Store in cache (supports Redis or in-memory)
        cache_data = {
            "request_id": str(request_id),
            "user_id": str(user_id),
            "document_code": document_code,
            "document_name": doc_name,
            "file_name": file.filename,
            "file_size": len(content),
            "mime_type": file.content_type,
            "content_b64": base64.b64encode(content).decode("utf-8"),
            "extraction": processing_result["extraction"],
            "confidence": processing_result["confidence"],
            "processor": processing_result["processor"],
            "risk_analysis": risk_analysis,
            "detected_type": processing_result.get("document_type", document_code),
            "expires_at": expires_at.isoformat(),
            "extraction_schema_key": extraction_schema_key
        }
        await preview_cache.set(preview_id, cache_data, PREVIEW_EXPIRY_SECONDS)

        # Get expected fields from schema for frontend form
        expected_fields = self._get_expected_fields(document_code, extraction_schema_key)

        # Determine status and if user needs to review
        extraction_status = processing_result.get("status", "pending_validation")
        needs_correction = (
            processing_result["confidence"] < 0.7 or
            risk_analysis.get("requires_review", False)
        )

        # Check document type match
        detected_type = processing_result.get("document_type", document_code)
        doc_type_match = not any(
            f["code"] == "DOC_TYPE_MISMATCH"
            for f in risk_analysis.get("risk_factors", [])
        )

        # Build risk analysis response model
        risk_result = None
        if risk_analysis:
            risk_result = RiskAnalysisResult(
                risk_level=risk_analysis.get("risk_level", "low"),
                risk_score=risk_analysis.get("risk_score", 0),
                risk_factors=risk_analysis.get("risk_factors", []),
                recommendations=risk_analysis.get("recommendations", []),
                requires_rejection=risk_analysis.get("requires_rejection", False),
                requires_review=risk_analysis.get("requires_review", False),
                factors_count=risk_analysis.get("factors_count", {}),
                # Identity mismatch fields for cross-document validation
                identity_mismatches=risk_analysis.get("identity_mismatches", []),
                has_blocking_mismatches=risk_analysis.get("has_blocking_mismatches", False)
            )

            # Log if blocking mismatches were detected
            if risk_result.has_blocking_mismatches:
                logger.warning(
                    f"BLOCKING identity mismatches detected for {document_code}: "
                    f"{len(risk_result.identity_mismatches)} mismatches"
                )

        logger.info(
            f"Document preview created: {document_code} for request {request['reference']} "
            f"(preview_id: {preview_id}, confidence: {processing_result['confidence']:.2%}, "
            f"risk: {risk_analysis.get('risk_level', 'unknown')})"
        )

        return DocumentExtractionPreview(
            preview_id=preview_id,
            document_code=document_code,
            document_name=doc_name,
            file_name=file.filename,
            file_size=len(content),
            mime_type=file.content_type,
            extraction=processing_result["extraction"],
            confidence=processing_result["confidence"],
            processor=processing_result["processor"],
            field_indicators=field_indicators,
            risk_analysis=risk_result,
            extraction_status=extraction_status,
            needs_correction=needs_correction,
            detected_document_type=detected_type,
            document_type_match=doc_type_match,
            expected_fields=expected_fields,
            expires_at=expires_at,
            processing_time_ms=processing_result.get("processing_time_ms")
        )

    async def validate_document(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID,
        validation: DocumentValidationRequest
    ) -> DocumentValidationResponse:
        """
        STEP 2: User validates extraction and document is uploaded to Firebase.

        Args:
            db: Database connection
            request_id: The service request ID
            user_id: The user ID
            validation: User's validation with confirmed/corrected data

        Returns:
            DocumentValidationResponse with final document info
        """
        # Get preview from cache
        preview = await preview_cache.get(validation.preview_id)
        if not preview:
            # Preview not found - likely expired (30 min TTL) or server instance changed
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PREVIEW_EXPIRED",
                    "message_en": f"Document preview session expired (max {PREVIEW_EXPIRY_MINUTES} minutes). Please re-upload the document.",
                    "message_es": f"La sesión de vista previa del documento ha expirado (máximo {PREVIEW_EXPIRY_MINUTES} minutos). Por favor, vuelva a cargar el documento.",
                    "message_fr": f"La session de prévisualisation du document a expiré (max {PREVIEW_EXPIRY_MINUTES} minutes). Veuillez recharger le document.",
                }
            )

        # Verify preview belongs to this request and user
        if preview["request_id"] != str(request_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Preview does not match this request"
            )
        if preview["user_id"] != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Check if preview has expired (cache handles TTL but double-check)
        expires_at = datetime.fromisoformat(preview["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            await preview_cache.delete(validation.preview_id)
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "code": "PREVIEW_EXPIRED",
                    "message_en": f"Document preview session expired (max {PREVIEW_EXPIRY_MINUTES} minutes). Please re-upload the document.",
                    "message_es": f"La sesión de vista previa del documento ha expirado (máximo {PREVIEW_EXPIRY_MINUTES} minutos). Por favor, vuelva a cargar el documento.",
                    "message_fr": f"La session de prévisualisation du document a expiré (max {PREVIEW_EXPIRY_MINUTES} minutes). Veuillez recharger le document.",
                }
            )

        # Verify request still exists and is in valid state
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        allowed_statuses = [
            ServiceRequestStatus.DRAFT.value,
            ServiceRequestStatus.DOCUMENTS_REQUIRED.value
        ]
        if request["status"] not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot upload documents in status: {request['status']}"
            )

        # Decode file content
        content = base64.b64decode(preview["content_b64"])

        # Upload to Firebase Storage FIRST - fail fast if storage fails
        # This ensures we don't save DB records pointing to non-existent files
        try:
            from app.modules.documents.services.storage_service import firebase_storage_service
            upload_result = await firebase_storage_service.upload_user_document(
                user_id=str(user_id),
                application_id=str(request_id),
                file=content,  # bytes from decoded base64
                metadata={
                    "filename": preview["file_name"],
                    "mime_type": preview["mime_type"],
                    "document_code": preview["document_code"],
                    "document_name": preview["document_name"]
                }
            )
            file_path = upload_result.file_path
            logger.info(f"Document uploaded to Firebase: {file_path}")
        except ImportError as import_err:
            # storage_service not available - this is a configuration error
            logger.error(f"storage_service module not available: {import_err}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document storage service is not available. Please contact support."
            )
        except Exception as storage_err:
            # Firebase upload failed - don't proceed with DB save
            logger.error(f"Firebase upload failed for {preview['document_code']}: {storage_err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to upload document to storage. Please try again. Error: {str(storage_err)}"
            )

        # Use transaction to ensure atomicity - all DB operations succeed or none
        validated_at = datetime.now(timezone.utc)
        doc = None

        async with db.transaction():
            # Save document record with USER-VALIDATED extraction data
            doc = await document_repository.add_document(
                db=db,
                service_request_id=request_id,
                document_code=preview["document_code"],
                document_name=preview["document_name"],
                file_path=file_path,
                file_name=preview["file_name"],
                file_size=preview["file_size"],
                mime_type=preview["mime_type"],
                uploaded_by=user_id
            )

            # Update with user-validated extraction data
            await document_repository.update_extraction(
                db=db,
                document_id=doc["id"],
                extraction_data=validation.confirmed_data,  # User's confirmed data!
                extraction_confidence=preview["confidence"],
                extraction_status="validated"
            )

            # Mark document as validated by user
            await document_repository.validate_document(
                db=db,
                document_id=doc["id"],
                is_valid=True,
                validation_errors=[],
                validated_by=user_id
            )

            # NOTE: Gemini processing is now logged centrally in
            # gemini_document_processor.process() via _log_to_audit()

            # Check if all documents are now provided (within transaction)
            await self._check_completion(db, request_id, user_id)

        # Only delete preview from cache AFTER transaction commits successfully
        await preview_cache.delete(validation.preview_id)

        logger.info(
            f"Document validated and uploaded: {preview['document_code']} "
            f"for request {request['reference']}"
        )

        return DocumentValidationResponse(
            document_id=doc["id"],
            document_code=preview["document_code"],
            document_name=preview["document_name"],
            file_path=file_path,
            extraction_data=validation.confirmed_data,
            extraction_confidence=preview["confidence"],
            is_validated=True,
            validated_at=validated_at
        )

    async def cleanup_expired_previews(self) -> int:
        """
        Manually trigger cleanup of expired previews.

        Note: Redis handles TTL automatically. This is mainly for in-memory cache
        or when you need to force cleanup.

        Returns:
            Number of expired entries removed
        """
        return await preview_cache.cleanup_expired()

    async def cleanup_abandoned_requests(
        self,
        db: asyncpg.Connection,
        max_age_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Clean up abandoned service requests that have been in DRAFT status
        for longer than the threshold.

        Bundle workflows (BUNDLE_PAYMENT, FIELD_INSPECTION) and licence-linked
        requests are ALWAYS excluded (Plan P2 — INSPECTION_BUNDLE_P2_DETAIL.md).
        Triple exclusion (defense in depth):
          1. workflow_code NOT IN ('BUNDLE_PAYMENT', 'FIELD_INSPECTION')
          2. source NOT IN ('field_inspection', 'admin_import')
          3. commercial_license_id IS NULL

        Plus a paranoid safety check verifies no commercial_license references
        the candidate IDs before deletion.

        Args:
            db: Database connection
            max_age_hours: Optional override. If None, uses
                settings.DRAFT_CLEANUP_MAX_HOURS (default 2h).

        Returns:
            Dict with cleanup statistics:
            - deleted_requests: Number of SRs deleted
            - deleted_documents: Number of documents deleted
            - deleted_files: Number of files deleted from storage
            - skipped_bundle: Number of bundle DRAFTs found and protected
            - max_age_hours: Effective threshold used (from param or settings)
            - errors: List of any errors encountered
        """
        # Read from settings if not explicitly provided (Plan P2 — D3)
        effective_hours = (
            max_age_hours
            if max_age_hours is not None
            else _get_settings().DRAFT_CLEANUP_MAX_HOURS
        )

        stats: Dict[str, Any] = {
            "deleted_requests": 0,
            "deleted_documents": 0,
            "deleted_files": 0,
            "skipped_bundle": 0,
            "max_age_hours": effective_hours,
            "errors": [],
        }

        try:
            # Use timezone-aware UTC to avoid mismatch with TIMESTAMPTZ columns
            # (naive datetime would be interpreted as client local time by asyncpg,
            # causing timezone-related off-by-1h bugs in cleanup windows).
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=effective_hours)

            # Count bundle DRAFT candidates (for metrics/anomaly detection).
            # These are NEVER deleted — just reported.
            skipped_bundle = await db.fetchval(
                """
                SELECT COUNT(*)
                FROM service_requests sr
                WHERE sr.status = 'DRAFT'
                  AND sr.created_at < $1
                  AND (
                      sr.workflow_code IN ('BUNDLE_PAYMENT', 'FIELD_INSPECTION')
                      OR sr.source IN ('field_inspection', 'admin_import')
                      OR sr.commercial_license_id IS NOT NULL
                  )
                """,
                cutoff_time,
            )
            stats["skipped_bundle"] = int(skipped_bundle or 0)

            # Find abandoned non-bundle DRAFTs (Plan P2 — D1 triple exclusion)
            query = """
                SELECT sr.id, sr.reference, sr.user_id, sr.created_at
                FROM service_requests sr
                WHERE sr.status = 'DRAFT'
                  AND sr.created_at < $1
                  AND sr.workflow_code NOT IN ('BUNDLE_PAYMENT', 'FIELD_INSPECTION')
                  AND sr.source NOT IN ('field_inspection', 'admin_import')
                  AND sr.commercial_license_id IS NULL
                ORDER BY sr.created_at ASC
            """
            abandoned_requests = await db.fetch(query, cutoff_time)

            logger.info(
                "Cleanup found %d abandoned DRAFT requests (bundle protected: %d, threshold: %dh)",
                len(abandoned_requests), stats["skipped_bundle"], effective_hours,
            )

            # Paranoid safety check (Plan P2 — D5): verify no commercial_license
            # references any of the candidates. This is belt-and-suspenders on
            # top of the WHERE filter above — if both diverge due to a bug, we
            # abort rather than silently destroy data.
            if abandoned_requests:
                candidate_ids = [r["id"] for r in abandoned_requests]
                linked_count = await db.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM commercial_licenses
                    WHERE service_request_id = ANY($1::uuid[])
                    """,
                    candidate_ids,
                )
                if linked_count and linked_count > 0:
                    msg = (
                        f"Cleanup safety check FAILED: {linked_count} commercial_licenses "
                        f"reference {len(candidate_ids)} candidate SRs. Aborting cleanup to "
                        f"prevent data loss. Investigate filter/link inconsistency."
                    )
                    logger.error(msg)
                    raise RuntimeError(msg)

            for request in abandoned_requests:
                request_id = request["id"]
                reference = request["reference"]

                try:
                    # Get documents for this request
                    docs = await document_repository.find_by_request(db, request_id)

                    # Delete files from storage
                    for doc in docs:
                        if doc.get("file_path"):
                            try:
                                from app.modules.documents.services.storage_service import firebase_storage_service
                                await firebase_storage_service.delete_file(doc["file_path"])
                                stats["deleted_files"] += 1
                            except Exception as e:
                                stats["errors"].append(f"Failed to delete file for doc {doc['id']}: {str(e)}")

                    # Delete documents from database
                    await db.execute(
                        "DELETE FROM service_request_documents WHERE service_request_id = $1",
                        request_id
                    )
                    stats["deleted_documents"] += len(docs)

                    # Delete the service request
                    await db.execute(
                        "DELETE FROM service_requests WHERE id = $1",
                        request_id
                    )
                    stats["deleted_requests"] += 1

                    logger.info(f"Cleaned up abandoned request {reference} ({len(docs)} docs)")

                except Exception as e:
                    error_msg = f"Failed to cleanup request {reference}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

        except RuntimeError:
            # Safety check aborted cleanup — re-raise to signal the operator
            raise
        except Exception as e:
            error_msg = f"Cleanup job failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            stats["errors"].append(error_msg)

        logger.info(
            "Cleanup completed: deleted=%d docs=%d files=%d skipped_bundle=%d max_age_hours=%d errors=%d",
            stats["deleted_requests"], stats["deleted_documents"], stats["deleted_files"],
            stats["skipped_bundle"], stats["max_age_hours"], len(stats["errors"]),
        )
        return stats

    def _get_expected_fields(
        self,
        document_code: str,
        extraction_schema_key: Optional[str] = None
    ) -> List[Dict]:
        """Get expected fields from schema for frontend form generation"""
        schema = schema_loader.get_schema_for_document(document_code, extraction_schema_key)
        if not schema:
            return []

        fields = []
        # Use "extraction" key (not "blocs")
        extraction = schema.get("extraction", {})
        for bloc_name, bloc in extraction.items():
            if not isinstance(bloc, dict) or "fields" not in bloc:
                continue
            for field_name, config in bloc.get("fields", {}).items():
                fields.append({
                    "field_name": field_name,
                    "label": config.get("field_label", config.get("label", field_name)),
                    "type": config.get("type", "text"),
                    "required": config.get("required", False),
                    "bloc": bloc_name,
                    "hint": config.get("description", ""),
                    "pattern": config.get("pattern"),
                    "pii": config.get("pii", False)
                })
        return fields

    # ═══════════════════════════════════════════════════════════════
    # GET / LIST
    # ═══════════════════════════════════════════════════════════════

    async def get_request(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID,
        is_agent: bool = False
    ) -> ServiceRequestResponse:
        """Get a service request by ID"""
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        # Agents bypass ownership check (they access via assignment, not ownership)
        if not is_agent and str(request["user_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        params = self._extract_workflow_params(request)
        required_docs = await self._get_required_documents(db, request["workflow_code"], **params)
        return await self._build_response(db, request, required_docs)

    async def list_requests(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        status_filter: Optional[str] = None,
        workflow_code: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        language: str = "es",
    ):
        """List service requests for a user with server-side pagination and filters.

        Args:
            language: ISO 639-1 language code (es/fr/en) for translated entity names.
                      Currently unused — reserved for future entity name translation.
        """
        import math
        from ..models.service_request import ServiceRequestListResponse

        offset = (page - 1) * page_size

        # Count total with same filters
        total = await service_request_repository.count_by_user(
            db=db, user_id=user_id, status=status_filter,
            workflow_code=workflow_code, category=category,
            search=search, date_from=date_from, date_to=date_to,
        )

        # Fetch current page
        requests = await service_request_repository.find_by_user(
            db=db, user_id=user_id, status=status_filter,
            workflow_code=workflow_code, category=category,
            search=search, date_from=date_from, date_to=date_to,
            limit=page_size, offset=offset,
        )

        # Build lightweight responses for list view (no document loading = no N+1)
        results = [self._build_list_item_response(req) for req in requests]

        return ServiceRequestListResponse(
            requests=results,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total > 0 else 0,
        )

    # ═══════════════════════════════════════════════════════════════
    # UPDATE / DELETE / SUBMIT / CANCEL
    # ═══════════════════════════════════════════════════════════════

    async def update_request(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID,
        form_data: Optional[Dict] = None,
        notes: Optional[str] = None
    ) -> ServiceRequestResponse:
        """
        Update a service request (only allowed in DRAFT status).

        Args:
            db: Database connection
            request_id: The service request ID
            user_id: The requesting user's ID
            form_data: Updated form data
            notes: Optional notes

        Returns:
            Updated service request response
        """
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        if str(request["user_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Only allow updates in DRAFT status
        if request["status"] != ServiceRequestStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update request in status: {request['status']}"
            )

        # Build update data
        update_fields = []
        update_values = []

        if form_data is not None:
            update_fields.append("form_data = $1::jsonb")
            update_values.append(json.dumps(form_data))

            # Also update solicitud_type if present in form_data
            if "solicitud_type" in form_data:
                solicitud_type_value = form_data["solicitud_type"]
                # Normalize to lowercase for database
                if isinstance(solicitud_type_value, str):
                    solicitud_type_value = solicitud_type_value.lower()
                update_fields.append(f"solicitud_type = ${len(update_values) + 1}")
                update_values.append(solicitud_type_value)

        if notes is not None:
            update_fields.append(f"notes = ${len(update_values) + 1}")
            update_values.append(notes)

        if not update_fields:
            # Nothing to update
            params = self._extract_workflow_params(request)
            required_docs = await self._get_required_documents(db, request["workflow_code"], **params)
            return await self._build_response(db, request, required_docs)

        # Add updated_at
        update_fields.append(f"updated_at = ${len(update_values) + 1}")
        update_values.append(datetime.now(timezone.utc))

        # Add request_id as last parameter
        update_values.append(request_id)

        query = f"""
            UPDATE service_requests
            SET {', '.join(update_fields)}
            WHERE id = ${len(update_values)}
            RETURNING *
        """
        updated = await db.fetchrow(query, *update_values)

        logger.info(f"Updated service request: {request['reference']}")

        params = self._extract_workflow_params(dict(updated))
        required_docs = await self._get_required_documents(db, updated["workflow_code"], **params)
        return await self._build_response(db, dict(updated), required_docs)

    async def delete_request(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Delete a service request (only allowed in DRAFT status).

        Args:
            db: Database connection
            request_id: The service request ID
            user_id: The requesting user's ID

        Returns:
            True if deleted successfully
        """
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        if str(request["user_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Only allow deletion in DRAFT status
        if request["status"] != ServiceRequestStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete request in status: {request['status']}. Only DRAFT requests can be deleted."
            )

        # Delete associated documents first
        await db.execute(
            "DELETE FROM service_request_documents WHERE service_request_id = $1",
            request_id
        )

        # Delete the request
        await db.execute(
            "DELETE FROM service_requests WHERE id = $1",
            request_id
        )

        logger.info(f"Deleted service request: {request['reference']}")
        return True

    async def submit_request(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID
    ) -> ServiceRequestResponse:
        """
        Submit a service request for processing.

        Validates that all required documents are provided before submission.

        Args:
            db: Database connection
            request_id: The service request ID
            user_id: The requesting user's ID

        Returns:
            Updated service request response
        """
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        if str(request["user_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Only allow submission from DRAFT or DOCUMENTS_REQUIRED status
        allowed_statuses = [
            ServiceRequestStatus.DRAFT.value,
            ServiceRequestStatus.DOCUMENTS_REQUIRED.value
        ]
        if request["status"] not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot submit request in status: {request['status']}"
            )

        # Check all required documents are provided (with context)
        params = self._extract_workflow_params(request)
        required_docs = await self._get_required_documents(db, request["workflow_code"], **params)
        provided_docs = await document_repository.find_by_request(db, request_id)

        required_codes = {d.document_code for d in required_docs if d.is_required}
        provided_codes = {d["document_code"] for d in provided_docs}

        missing = required_codes - provided_codes
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required documents: {', '.join(missing)}"
            )

        # Calculate tariff
        tariff = await tariff_service.calculate(
            db=db,
            workflow_code=request["workflow_code"],
            solicitud_type=request["solicitud_type"]
        )

        await service_request_repository.update_amounts(
            db=db,
            request_id=request_id,
            base_amount=tariff["base_amount"],
            supplements_amount=tariff["supplements_total"],
            penalties_amount=tariff["penalties_amount"],
            total_amount=tariff["total_amount"]
        )

        # Update status to SUBMITTED
        await service_request_repository.update_status(
            db=db,
            request_id=request_id,
            new_status=ServiceRequestStatus.SUBMITTED.value,
            performed_by=user_id,
            comment="User submitted request"
        )

        # === AUTO-ASSIGNMENT TRIGGER ===
        # Add to agent work queue for visibility and SLA tracking
        workflow_code = request["workflow_code"]
        entity_code = request.get("entity_code")

        if workflow_code and entity_code:
            try:
                # 1. Add to agent work queue (for queue management and SLA)
                queue_item = await agent_queue_service.add_to_queue(
                    db=db,
                    service_request_id=request_id,
                    workflow_code=workflow_code,
                    entity_code=entity_code,
                    priority_boost=0
                )
                logger.info(
                    f"Service request {request['reference']} added to agent queue. "
                    f"Queue ID: {queue_item.get('id')}, Priority: {queue_item.get('priority_score')}"
                )

                # 2. Auto-assignment (only if not already assigned — re-submission
                # after DOCUMENTS_REQUIRED keeps the same agent)
                existing_assigned = request.get("assigned_to")
                if existing_assigned:
                    logger.info(
                        f"Service request {request['reference']} already assigned to "
                        f"{existing_assigned} (re-submission). Skipping auto-assign."
                    )
                else:
                    # First-time submission: auto-assign to best agent
                    auto_assignment_service = AutoAssignmentService()
                    sr_location_id = request.get("entity_location_id")
                    if sr_location_id and not isinstance(sr_location_id, UUID):
                        try:
                            sr_location_id = UUID(str(sr_location_id))
                        except (ValueError, TypeError):
                            sr_location_id = None
                    assignment = await auto_assignment_service.auto_assign_item(
                        db=db,
                        item_id=request_id,
                        item_type="service_request",
                        item_data={
                            "workflow_code": workflow_code,
                            "entity_code": entity_code,
                            "solicitud_type": request.get("solicitud_type", "expedicion"),
                            "priority": request.get("priority", "NORMAL"),
                        },
                        entity_type="entity",
                        entity_id=None,
                        priority_level=5,
                        entity_code=entity_code,
                        workflow_code=workflow_code,
                        entity_location_id=sr_location_id,
                    )

                    if assignment:
                        agent_user_id = await db.fetchval(
                            "SELECT user_id FROM agent_profiles WHERE id = $1",
                            assignment.agent_profile_id
                        )
                        if agent_user_id:
                            await db.execute("""
                                UPDATE service_requests
                                SET assigned_to = $1, assigned_at = NOW(), updated_at = NOW()
                                WHERE id = $2
                            """, agent_user_id, request_id)
                            # Sync agent_work_queue.assigned_to
                            await db.execute("""
                                UPDATE agent_work_queue
                                SET assigned_to = $1, assigned_at = NOW(),
                                    status = 'assigned', updated_at = NOW()
                                WHERE item_id = $2
                                  AND item_type = 'service_request'
                                  AND assigned_to IS NULL
                            """, agent_user_id, request_id)

                        logger.info(
                            f"Service request {request['reference']} auto-assigned to agent "
                            f"{assignment.agent_profile_id} (user {agent_user_id})"
                        )
                    else:
                        logger.warning(
                            f"Service request {request['reference']} could not be auto-assigned. "
                            "No agent available or no matching rules."
                        )

            except Exception as e:
                # Log error but don't fail the submission
                logger.error(
                    f"Auto-assignment failed for {request['reference']}: {e}",
                    exc_info=True
                )
        else:
            logger.warning(
                f"Service request {request['reference']} missing workflow_code or entity_code. "
                f"Skipping auto-assignment. workflow_code={workflow_code}, entity_code={entity_code}"
            )

        # Refresh request data
        updated = await service_request_repository.find_by_id(db, request_id)
        logger.info(f"Service request submitted: {request['reference']}")

        return await self._build_response(db, updated, required_docs)

    async def prepare_for_payment(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID
    ) -> ServiceRequestResponse:
        """
        Prepare a service request for payment.

        This validates documents and calculates tariff, but does NOT change status.
        Status will change to PAYMENT_PENDING only when payment is actually initiated
        and recorded in service_payments table.

        Flow: DRAFT (validate docs, calc tariff) → initiate_payment() → PAYMENT_PENDING

        Requirements:
        - Request must be in DRAFT status
        - All required documents must be uploaded and validated
        - Tariff will be calculated if not already done

        Args:
            db: Database connection
            request_id: The service request ID
            user_id: The requesting user's ID

        Returns:
            Service request response (status remains DRAFT)
        """
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        if str(request["user_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Only allow from DRAFT status
        if request["status"] != ServiceRequestStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot prepare for payment in status: {request['status']}"
            )

        # Check all required documents are provided and validated (with context)
        params = self._extract_workflow_params(request)
        required_docs = await self._get_required_documents(db, request["workflow_code"], **params)
        provided_docs = await document_repository.find_by_request(db, request_id)

        required_codes = {doc.document_code for doc in required_docs if doc.is_required}
        provided_codes = {doc["document_code"] for doc in provided_docs if doc.get("is_valid")}

        missing_docs = required_codes - provided_codes
        if missing_docs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Missing required documents",
                    "missing": list(missing_docs),
                    "message_es": f"Faltan documentos requeridos: {', '.join(missing_docs)}",
                    "message_fr": f"Documents requis manquants: {', '.join(missing_docs)}"
                }
            )

        # Calculate tariff if not already calculated
        if not request.get("total_amount") or request["total_amount"] == 0:
            tariff = await self._calculate_tariff(db, request)
            if tariff:
                await service_request_repository.update_amounts(
                    db=db,
                    request_id=request_id,
                    base_amount=tariff["base_amount"],
                    supplements_amount=tariff["supplements_total"],
                    penalties_amount=tariff["penalties_amount"],
                    total_amount=tariff["total_amount"]
                )

        # NOTE: Status remains DRAFT - will change to PAYMENT_PENDING only after
        # successful payment initiation in initiate_payment() endpoint

        # Refresh request data
        updated = await service_request_repository.find_by_id(db, request_id)
        logger.info(f"Service request prepared for payment (DRAFT): {request['reference']}")

        return await self._build_response(db, updated, required_docs)

    async def cancel_request(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> ServiceRequestResponse:
        """
        Cancel a service request.

        Allowed from DRAFT, SUBMITTED, DOCUMENTS_REQUIRED, or PAYMENT_PENDING status.
        Releases held appointments and publishes REQUEST_CANCELLED event.

        Args:
            db: Database connection
            request_id: The service request ID
            user_id: The requesting user's ID
            reason: Optional cancellation reason

        Returns:
            Updated service request response
        """
        request = await service_request_repository.find_by_id(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        if str(request["user_id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Only allow cancellation from certain statuses
        cancellable_statuses = [
            ServiceRequestStatus.DRAFT.value,
            ServiceRequestStatus.SUBMITTED.value,
            ServiceRequestStatus.DOCUMENTS_REQUIRED.value,
            ServiceRequestStatus.PAYMENT_PENDING.value
        ]
        if request["status"] not in cancellable_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel request in status: {request['status']}"
            )

        cancel_reason = reason or "User cancelled request"

        # Update status to CANCELLED
        await service_request_repository.update_status(
            db=db,
            request_id=request_id,
            new_status=ServiceRequestStatus.CANCELLED.value,
            performed_by=user_id,
            comment=cancel_reason
        )

        # Release any held appointment
        await db.execute("""
            UPDATE appointment_holds
            SET status = 'released', released_at = NOW()
            WHERE service_request_id = $1 AND status = 'held'
        """, request_id)

        # Publish REQUEST_CANCELLED event for notifications
        try:
            from app.core.events import EventBus, EventType
            user = await db.fetchrow(
                "SELECT email, phone_number, first_name, last_name, preferred_language FROM users WHERE id = $1",
                user_id
            )
            EventBus.publish_nowait(
                EventType.REQUEST_CANCELLED,
                {
                    "request_id": str(request_id),
                    "user_id": str(user_id),
                    "user_email": user["email"] if user else None,
                    "user_phone": user["phone_number"] if user else None,
                    "user_name": f"{user['first_name'] or ''} {user['last_name'] or ''}".strip() if user else "",
                    "preferred_language": user["preferred_language"] if user else "es",
                    "workflow_code": request["workflow_code"],
                    "reference": request["reference"],
                    "reason": cancel_reason,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.info(f"REQUEST_CANCELLED event published for request {request_id}")
        except Exception as e:
            logger.error(f"Failed to publish REQUEST_CANCELLED event: {e}")

        # Refresh request data
        updated = await service_request_repository.find_by_id(db, request_id)
        params = self._extract_workflow_params(updated)
        required_docs = await self._get_required_documents(db, updated["workflow_code"], **params)

        logger.info(f"Service request cancelled: {request['reference']}")

        return await self._build_response(db, updated, required_docs)

    # ═══════════════════════════════════════════════════════════════
    # PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file (MIME type check)"""
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Accepted: {', '.join(ALLOWED_MIME_TYPES)}"
            )

    @staticmethod
    def _validate_file_integrity(file_content: bytes, declared_mime: str) -> None:
        """
        Validate file integrity via magic bytes.
        Prevents corrupt files and MIME type spoofing from causing
        OCR retry loops or processing resource waste.
        """
        if len(file_content) < 12:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is too small or empty"
            )

        # Detect actual file type from magic bytes
        detected_mime = None
        header = file_content[:12]

        if header[:4] == b'%PDF':
            detected_mime = 'application/pdf'
        elif header[:3] == b'\xff\xd8\xff':
            detected_mime = 'image/jpeg'
        elif header[:4] == b'\x89PNG':
            detected_mime = 'image/png'
        elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            detected_mime = 'image/webp'

        if not detected_mime:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File format not recognized. Upload PDF, JPG, PNG or WebP files."
            )

        # Verify detected type matches declared MIME (allow jpeg/jpg alias)
        declared_normalized = declared_mime.replace('image/jpg', 'image/jpeg')
        if detected_mime != declared_normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File content ({detected_mime}) does not match declared type ({declared_mime})"
            )

    async def _get_required_documents(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str = "expedicion",
        motivo: Optional[str] = None,
        form_data: Optional[Dict[str, Any]] = None
    ) -> List[RequiredDocument]:
        """
        Get required documents for a workflow with dynamic context.

        Strategy (OPTIMIZED):
        1. FIRST, try workflow class (predefined/hardcoded workflows)
           - Passes full context (form_data) for dynamic document requirements
           - Handles is_minor, representante_unico, motivo, etc.
        2. FALLBACK to database if no workflow class found

        Args:
            db: Database connection
            workflow_code: Code du workflow (ex: pasaporte_nuevo)
            solicitud_type: Type de sollicitude (expedicion, renovacion)
            motivo: Motif pour RENOVACION (vencimiento, perdida, robo, deterioro)
            form_data: Données du formulaire (is_minor, representante_unico, etc.)

        Returns:
            List of required documents based on context
        """
        # 1. PRIORITIZE workflow class (for predefined/hardcoded workflows)
        workflow = workflow_engine.get_workflow_by_string(workflow_code)
        if workflow:
            logger.info(f"Using workflow class for document requirements: {workflow_code}")

            # Convert solicitud_type string to enum
            try:
                solicitud_enum = SolicitudType(solicitud_type) if solicitud_type else SolicitudType.EXPEDICION
            except ValueError:
                solicitud_enum = SolicitudType.EXPEDICION

            # Convert motivo string to enum (if applicable)
            motivo_enum = None
            if motivo:
                try:
                    motivo_enum = RenovacionMotivo(motivo)
                except ValueError:
                    motivo_enum = None

            # Create WorkflowContext with form_data for dynamic requirements
            # WorkflowContext requires: service_request_id, user_id, workflow_code, solicitud_type
            # We use placeholder UUIDs since we're just checking document requirements
            context = None
            if form_data:
                try:
                    wf_code_enum = WorkflowCode(workflow_code) if workflow_code else WorkflowCode.PASAPORTE_NUEVO
                except ValueError:
                    from ..workflows.generic_workflow import _GenericCode
                    wf_code_enum = _GenericCode(workflow_code)

                context = WorkflowContext(
                    service_request_id=uuid4(),  # Placeholder for requirements check
                    user_id=uuid4(),  # Placeholder for requirements check
                    workflow_code=wf_code_enum,
                    solicitud_type=solicitud_enum,
                    form_data=form_data
                )

            # Call workflow's get_document_requirements with proper parameters
            try:
                doc_requirements = workflow.get_document_requirements(
                    solicitud_type=solicitud_enum,
                    motivo=motivo_enum,
                    context=context
                )
            except TypeError:
                # Fallback for workflows that don't support the new signature
                logger.warning(f"Workflow {workflow_code} doesn't support context-aware signature, using legacy")
                doc_requirements = workflow.get_document_requirements(solicitud_type or "")

            return [
                RequiredDocument(
                    document_code=doc.document_code,
                    document_name=doc.document_name_es,
                    is_required=doc.is_required,
                    display_order=doc.display_order,
                    extraction_schema_key=doc.schema_key,
                    instructions=doc.instructions_es,
                    accepted_formats=doc.accepted_formats,
                    max_size_mb=doc.max_size_mb
                )
                for doc in doc_requirements
            ]

        # 2. FALLBACK to database configuration (for generic workflows)
        query = """
            SELECT document_code,
                   document_name_es,
                   is_required,
                   display_order,
                   extraction_schema_key,
                   instructions_es
            FROM workflow_document_requirements
            WHERE workflow_code = $1 AND is_active = TRUE
            ORDER BY display_order
        """
        rows = await db.fetch(query, workflow_code)

        if rows:
            logger.info(f"Using database config for document requirements: {workflow_code}")
            return [
                RequiredDocument(
                    document_code=row["document_code"],
                    document_name=row["document_name_es"],
                    is_required=row["is_required"] if row["is_required"] is not None else True,
                    display_order=row["display_order"] or 0,
                    extraction_schema_key=row["extraction_schema_key"],
                    instructions=row["instructions_es"]
                )
                for row in rows
            ]

        logger.warning(f"No document requirements found for workflow: {workflow_code}")
        return []

    def _extract_workflow_params(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract workflow parameters from a service request record.

        Helper method to avoid repetition when calling _get_required_documents.

        Args:
            request: Service request dict from database

        Returns:
            Dict with solicitud_type, motivo, and form_data
        """
        form_data = request.get("form_data") or {}
        # Handle case where form_data might be a string (JSONB parsing issue)
        if isinstance(form_data, str):
            try:
                form_data = json.loads(form_data)
            except (json.JSONDecodeError, TypeError):
                form_data = {}

        return {
            "solicitud_type": request.get("solicitud_type", "expedicion"),
            "motivo": form_data.get("motivo"),
            "form_data": form_data
        }

    def _get_extraction_schema_key(
        self,
        document_code: str,
        required_docs: List[RequiredDocument]
    ) -> Optional[str]:
        """Get extraction_schema_key for a document from required documents list"""
        for doc in required_docs:
            if doc.document_code == document_code:
                return doc.extraction_schema_key
        return None

    async def _process_document(
        self,
        content: bytes,
        mime_type: str,
        document_code: str,
        request_id: str = "",
        user_id: str = "",
        existing_documents: Optional[Dict[str, Dict]] = None,
        form_data: Optional[Dict] = None,
        extraction_schema_key: Optional[str] = None,
        workflow_code: Optional[str] = None,
        document_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """
        Process document for extraction + risk analysis using Gemini + Tesseract fallback.

        Pipeline:
        1. Gemini AI (primary) - 70% confidence threshold + fraud detection
        2. Tesseract OCR (fallback) - 60% confidence threshold
        3. Manual review if both fail
        4. Comprehensive risk analysis with identity mismatch detection

        Args:
            content: Document file bytes
            mime_type: MIME type (image/*, application/pdf)
            document_code: Expected document type code
            request_id: Service request ID for duplication tracking
            user_id: User ID for duplication tracking
            existing_documents: Previously uploaded documents for consistency checks
            form_data: User form data for consistency checks
            extraction_schema_key: Database key for schema lookup (e.g., 'DIP_GQ_V1')
            workflow_code: Workflow code for identity verification config (e.g., 'PASAPORTE_NUEVO')
            document_constraints: Workflow-specific constraints from DocumentRequirement.config
                (e.g., {"required_tipo_certificado": "APTITUD", "required_resultado": ["SANO", "APTO"]})

        Returns:
            Dict with extraction, confidence, processor, status, risk_analysis including identity_mismatches
        """
        try:
            # Use the production Gemini document processor with full risk analysis
            result = await gemini_document_processor.process(
                content=content,
                mime_type=mime_type,
                document_code=document_code,
                request_id=request_id,
                user_id=user_id,
                existing_documents=existing_documents,
                form_data=form_data,
                extraction_schema_key=extraction_schema_key,
                workflow_code=workflow_code,
                document_constraints=document_constraints
            )

            # Log summary
            risk = result.get("risk_analysis", {})
            logger.info(
                f"Document processed: {document_code} | "
                f"Processor: {result['processor']} | "
                f"Confidence: {result['confidence']:.2%} | "
                f"Status: {result['status']} | "
                f"Risk: {risk.get('risk_level', 'unknown')} ({risk.get('risk_score', 0)})"
            )

            return result

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return {
                "extraction": {},
                "confidence": 0.0,
                "processor": "error",
                "status": "error",
                "document_type": document_code,
                "has_error": True,
                "error_message": str(e),
                "risk_analysis": {
                    "risk_level": "critical",
                    "risk_score": 100,
                    "risk_factors": [{
                        "code": "PROCESSING_ERROR",
                        "severity": "critical",
                        "message": f"Processing error: {str(e)}",
                        "action": "review"
                    }],
                    "recommendations": ["Manual review required due to processing error"],
                    "requires_rejection": False,
                    "requires_review": True,
                    "factors_count": {"critical": 1, "high": 0, "medium": 0, "low": 0}
                }
            }

    def _build_field_indicators(
        self,
        extraction: Dict,
        confidence: float,
        risk_analysis: Dict,
        document_code: str,
        extraction_schema_key: Optional[str] = None
    ) -> List[FieldIndicator]:
        """
        Build per-field indicators for UI display.

        Args:
            extraction: Extracted data
            confidence: Overall confidence
            risk_analysis: Risk analysis result
            document_code: Document type code
            extraction_schema_key: Database key for schema lookup

        Returns:
            List of FieldIndicator with status and risk info
        """
        indicators = []

        # Get schema for field metadata (use extraction_schema_key if available)
        schema = schema_loader.get_schema_for_document(document_code, extraction_schema_key)
        expected_fields = set()
        field_metadata = {}

        if schema:
            # Use "extraction" key (not "blocs")
            extraction_section = schema.get("extraction", {})
            for bloc_name, bloc in extraction_section.items():
                if not isinstance(bloc, dict) or "fields" not in bloc:
                    continue
                for field_name, config in bloc.get("fields", {}).items():
                    expected_fields.add(field_name)
                    field_metadata[field_name] = {
                        "label": config.get("field_label", config.get("label", field_name)),
                        "required": config.get("required", False)
                    }

        # Build risk factors by field
        field_risks = {}
        for factor in risk_analysis.get("risk_factors", []):
            detail = factor.get("detail", {})
            related_field = detail.get("field")
            if related_field:
                if related_field not in field_risks:
                    field_risks[related_field] = []
                field_risks[related_field].append(factor)

        # Create indicators for each extracted field
        for field_name, value in extraction.items():
            if field_name.startswith("_"):
                continue

            # Base confidence (use overall if no per-field data)
            field_confidence = confidence

            # Determine status
            if value is None or value == "":
                status = "missing" if field_metadata.get(field_name, {}).get("required") else "ok"
            elif field_name in field_risks:
                # Has risk factors
                highest_severity = max(
                    (r["severity"] for r in field_risks[field_name]),
                    key=lambda s: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(s, 0)
                )
                status = "error" if highest_severity in ["critical", "high"] else "warning"
            elif field_confidence < 0.5:
                status = "warning"
            else:
                status = "ok"

            # Get risk info if exists
            risk_level = None
            risk_message = None
            suggestion = None
            requires_attention = False

            if field_name in field_risks:
                factors = field_risks[field_name]
                highest_factor = max(
                    factors,
                    key=lambda f: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(f["severity"], 0)
                )
                risk_level = highest_factor["severity"]
                risk_message = highest_factor["message"]
                requires_attention = True

                # Build suggestion
                action = highest_factor.get("action")
                if action == "reject":
                    suggestion = "This field has critical issues - document may be rejected"
                elif action == "review":
                    suggestion = "Please verify this field carefully"
                elif action == "warn":
                    suggestion = "Consider reviewing this value"

            # Low confidence warning
            if field_confidence < 0.6 and not requires_attention:
                requires_attention = True
                risk_level = risk_level or "low"
                risk_message = risk_message or "Low extraction confidence - please verify"
                suggestion = suggestion or "Double-check this value against the document"

            indicators.append(FieldIndicator(
                field_name=field_name,
                value=value,
                confidence=field_confidence,
                status=status,
                risk_level=risk_level,
                risk_message=risk_message,
                requires_attention=requires_attention,
                suggestion=suggestion
            ))

        # Add indicators for missing required fields
        for field_name in expected_fields:
            if field_name not in extraction:
                meta = field_metadata.get(field_name, {})
                if meta.get("required"):
                    indicators.append(FieldIndicator(
                        field_name=field_name,
                        value=None,
                        confidence=0.0,
                        status="missing",
                        risk_level="medium",
                        risk_message="Required field not found in document",
                        requires_attention=True,
                        suggestion=f"Please enter {meta.get('label', field_name)} manually"
                    ))

        return indicators

    async def _check_completion(
        self,
        db: asyncpg.Connection,
        request_id: UUID,
        user_id: UUID
    ) -> None:
        """
        Check if all required documents are provided and calculate tariff.

        NOTE: This does NOT set status to SUBMITTED.
        SUBMITTED can only be set through the proper workflow confirmation step
        after ALL required steps (document upload, form review, validation) are completed.
        """
        request = await service_request_repository.find_by_id(db, request_id)
        params = self._extract_workflow_params(request)
        required = await self._get_required_documents(db, request["workflow_code"], **params)
        provided = await document_repository.find_by_request(db, request_id)

        required_codes = {d.document_code for d in required if d.is_required}
        provided_codes = {d["document_code"] for d in provided}

        if required_codes <= provided_codes:
            # All required documents provided - calculate tariff for display
            # but DO NOT change status - user must complete all wizard steps

            # Use tariff_calculator for unified tariff calculation
            # This handles both PredefinedWorkflows (hardcoded) and GenericWorkflows (DB)
            context = await workflow_engine.load_context_from_db(db, request_id)
            workflow = workflow_engine.get_workflow(request["workflow_code"])

            if context and workflow:
                tariff = await tariff_calculator.calculate(db, workflow, context)
            else:
                # Fallback to tariff_service for legacy workflows
                tariff = await tariff_service.calculate(
                    db=db,
                    workflow_code=request["workflow_code"],
                    solicitud_type=request["solicitud_type"]
                )

            await service_request_repository.update_amounts(
                db=db,
                request_id=request_id,
                base_amount=tariff["base_amount"],
                supplements_amount=tariff["supplements_total"],
                penalties_amount=tariff["penalties_amount"],
                total_amount=tariff["total_amount"]
            )

            # Status stays DRAFT - user must complete form review, validation,
            # and confirmation steps before request can be SUBMITTED
            logger.info(f"Request {request['reference']} has all documents, tariff calculated: {tariff['total_amount']} XAF. Status remains {request['status']}")

    def _build_list_item_response(self, request: Dict) -> ServiceRequestResponse:
        """Build lightweight response for list views.
        Skips document loading (no extra DB queries) since list pages only
        use: id, reference, workflow_code, status, created_at, tariff fields."""
        tariff = None
        if request.get("total_amount"):
            tariff = TariffBreakdown(
                base_amount=float(request["base_amount"] or 0),
                supplements=[],
                supplements_total=float(request["supplements_amount"] or 0),
                penalties_amount=float(request["penalties_amount"] or 0),
                total_amount=float(request["total_amount"])
            )

        return ServiceRequestResponse(
            id=request["id"],
            reference=request["reference"],
            user_id=request["user_id"],
            workflow_code=request["workflow_code"],
            solicitud_type=request["solicitud_type"],
            fiscal_service_id=request.get("fiscal_service_id"),
            status=request["status"],
            priority=request["priority"],
            required_documents=[],
            provided_documents=[],
            missing_documents=[],
            documents_progress="0/0",
            form_data={},
            extracted_data={},
            extraction_confidence=None,
            validations={},
            tariff=tariff,
            assigned_to=request.get("assigned_to"),
            assigned_at=request.get("assigned_at"),
            entity_code=request.get("entity_code"),
            payment_id=request.get("payment_id"),
            payment_status=request.get("payment_status"),
            paid_at=request.get("paid_at"),
            cita_date=request.get("cita_date"),
            cita_time=request.get("cita_time"),
            cita_location=request.get("cita_location"),
            created_at=request["created_at"],
            updated_at=request.get("updated_at"),
            submitted_at=request.get("submitted_at"),
            validated_at=request.get("validated_at"),
            completed_at=request.get("completed_at"),
            expires_at=request.get("expires_at"),
            notes=request.get("notes"),
            rejection_reason=request.get("rejection_reason"),
            created_by=request.get("created_by"),
        )

    async def _build_response(
        self,
        db: asyncpg.Connection,
        request: Dict,
        required_docs: List[RequiredDocument]
    ) -> ServiceRequestResponse:
        """Build complete response with documents and tariff"""
        provided = await document_repository.find_by_request(db, request["id"])
        provided_codes = {d["document_code"] for d in provided}

        missing = [d for d in required_docs if d.document_code not in provided_codes]

        # Build tariff if amounts exist
        tariff = None
        if request.get("total_amount"):
            tariff = TariffBreakdown(
                base_amount=float(request["base_amount"] or 0),
                supplements=[],
                supplements_total=float(request["supplements_amount"] or 0),
                penalties_amount=float(request["penalties_amount"] or 0),
                total_amount=float(request["total_amount"])
            )

        return ServiceRequestResponse(
            id=request["id"],
            reference=request["reference"],
            user_id=request["user_id"],
            workflow_code=request["workflow_code"],
            solicitud_type=request["solicitud_type"],
            fiscal_service_id=request.get("fiscal_service_id"),
            status=request["status"],
            priority=request["priority"],
            required_documents=required_docs,
            provided_documents=[
                ProvidedDocument(
                    id=d["id"],
                    document_code=d["document_code"],
                    document_name=d["document_name"],
                    file_path=d["file_path"],
                    file_name=d["file_name"],
                    file_size=d.get("file_size"),
                    mime_type=d.get("mime_type"),
                    extraction_data=_parse_jsonb_field(d.get("extraction_data"), "extraction_data"),
                    extraction_confidence=d.get("extraction_confidence"),
                    extraction_status=d.get("extraction_status", "pending"),
                    is_valid=d.get("is_valid"),
                    validation_errors=d.get("validation_errors") if isinstance(d.get("validation_errors"), list) else [],
                    validated_by=d.get("validated_by"),
                    validated_at=d.get("validated_at"),
                    source=d.get("source", "user_upload"),
                    uploaded_by=d.get("uploaded_by"),
                    created_at=d["created_at"],
                    updated_at=d.get("updated_at")
                )
                for d in provided
            ],
            missing_documents=missing,
            documents_progress=f"{len(provided)}/{len(required_docs)}",
            form_data=_parse_jsonb_field(request.get("form_data"), "form_data"),
            extracted_data=_parse_jsonb_field(request.get("extracted_data"), "extracted_data"),
            extraction_confidence=request.get("extraction_confidence"),
            validations=_parse_jsonb_field(request.get("validations"), "validations"),
            tariff=tariff,
            assigned_to=request.get("assigned_to"),
            assigned_at=request.get("assigned_at"),
            entity_code=request.get("entity_code"),
            payment_id=request.get("payment_id"),
            payment_status=request.get("payment_status"),
            paid_at=request.get("paid_at"),
            cita_date=request.get("cita_date"),
            cita_time=request.get("cita_time"),
            cita_location=request.get("cita_location"),
            created_at=request["created_at"],
            updated_at=request.get("updated_at"),
            submitted_at=request.get("submitted_at"),
            validated_at=request.get("validated_at"),
            completed_at=request.get("completed_at"),
            expires_at=request.get("expires_at"),
            notes=request.get("notes"),
            rejection_reason=request.get("rejection_reason"),
            created_by=request.get("created_by")
        )


# Singleton instance
service_request_service = ServiceRequestService()
