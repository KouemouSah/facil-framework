"""
Wizard Session Service - Cache-First Architecture.

Manages service request wizard sessions entirely in cache (Redis/Upstash)
until payment is initiated. Sessions expire after 30 minutes of inactivity.

Architecture:
- All data stored in cache until persist_to_db()
- Atomic transaction: Firebase upload + DB insert
- No orphan records in database
- Natural expiration via cache TTL

Flow:
1. start_session() - Create session in cache
2. preview_document() - Extract & store document (renews TTL)
3. confirm_document() - User confirms extraction data
4. save_form_data() - Save form review data
5. prepare_for_payment() - Validate & calculate tariff
6. persist_to_db() - Atomic: Firebase + DB (called by payment processor)

@since v2.0 - Cache-first wizard migration
@see .claude/plans/CACHE_FIRST_WIZARD_MIGRATION_PLAN.md
"""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID, uuid4

from loguru import logger
import asyncpg

from app.core.events import EventBus, EventType
from .preview_cache import preview_cache
from .gemini_document_processor import gemini_document_processor
from .tariff_calculator import tariff_calculator
from .workflow_engine import workflow_engine, resolve_workflow_code
from ..repositories.service_request_repository import service_request_repository
from ..repositories.document_repository import document_repository
from ..models.wizard_session import (
    WizardSessionData,
    WizardSessionStatus,
    SessionDocumentData,
    WizardSessionResponse,
    WizardDocumentPreviewResponse,
    WizardPreparePaymentResponse,
    WizardPersistResult,
    WizardInitiatePaymentResponse,
)
from ..models.enums import ServiceRequestStatus, SolicitudType, WorkflowCode


# =============================================================================
# CONSTANTS
# =============================================================================

# Wizard session TTL — configurable via settings.WIZARD_SESSION_TTL_SECONDS
# (default 1800s = 30 min). Plan P2 — externalized from hardcoded constant.
from app.config import get_settings as _get_settings
WIZARD_SESSION_TTL_SECONDS = _get_settings().WIZARD_SESSION_TTL_SECONDS
WIZARD_SESSION_PREFIX = "wizard_session_"
MAX_DOCUMENT_SIZE_MB = 10
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class WizardSessionError(Exception):
    """Base exception for wizard session errors."""
    def __init__(self, message: str, code: str = "WIZARD_SESSION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class WizardSessionExpiredError(WizardSessionError):
    """Session has expired."""
    def __init__(self, message: str = "La sesión ha expirado. Por favor, inicie de nuevo."):
        super().__init__(message, "WIZARD_SESSION_EXPIRED")


class WizardSessionNotFoundError(WizardSessionError):
    """Session not found in cache."""
    def __init__(self, message: str = "Sesión no encontrada. Por favor, inicie de nuevo."):
        super().__init__(message, "WIZARD_SESSION_NOT_FOUND")


class WizardDocumentValidationError(WizardSessionError):
    """Document validation failed."""
    def __init__(self, message: str, code: str = "DOCUMENT_VALIDATION_ERROR"):
        super().__init__(message, code)


class WizardPersistError(WizardSessionError):
    """Persist to DB failed."""
    def __init__(self, message: str, code: str = "PERSIST_ERROR", details: Dict[str, Any] = None):
        super().__init__(message, code)
        self.details = details or {}


# =============================================================================
# WIZARD SESSION SERVICE
# =============================================================================

class WizardSessionService:
    """
    Manages wizard sessions in cache with 30-minute TTL.

    Key features:
    - No DB writes until payment is initiated
    - All documents stored in cache (base64)
    - Atomic persist: Firebase upload + DB insert
    - Natural cleanup via TTL (no orphan records)
    """

    def __init__(self):
        self.session_ttl = WIZARD_SESSION_TTL_SECONDS
        self.cache = preview_cache
        # Warn if cache backend is in-memory (sessions won't survive across instances)
        backend = self.cache._get_backend()
        from .preview_cache import InMemoryCache
        if isinstance(backend, InMemoryCache):
            logger.critical(
                "[WizardSession] ⚠️ CRITICAL: Using InMemoryCache! "
                "Wizard sessions will NOT work on multi-instance deployments (Cloud Run). "
                "Set REDIS_URL environment variable to fix this."
            )

    # =========================================================================
    # SESSION MANAGEMENT (Private)
    # =========================================================================

    def _generate_session_id(self, user_id: UUID, workflow_code: str) -> str:
        """Generate unique session ID."""
        unique = f"{user_id}_{workflow_code}_{uuid4().hex[:8]}_{datetime.now(timezone.utc).timestamp()}"
        return f"{WIZARD_SESSION_PREFIX}{hashlib.sha256(unique.encode()).hexdigest()[:16]}"

    def _get_cache_key(self, session_id: str) -> str:
        """Get cache key for session."""
        if session_id.startswith(WIZARD_SESSION_PREFIX):
            return session_id
        return f"{WIZARD_SESSION_PREFIX}{session_id}"

    async def _get_session(self, session_id: str, user_id: UUID) -> Dict[str, Any]:
        """
        Get session from cache with validation.

        Raises:
            WizardSessionNotFoundError: Session not in cache
            WizardSessionExpiredError: Session expired
            WizardSessionError: User mismatch
        """
        cache_key = self._get_cache_key(session_id)

        try:
            data = await self.cache.get(cache_key)
        except Exception as e:
            logger.error(f"[WizardSession] Cache error getting session {session_id}: {e}")
            raise WizardSessionError("Error al acceder a la sesión. Por favor, intente de nuevo.")

        if not data:
            logger.warning(f"[WizardSession] Session not found: {session_id}")
            raise WizardSessionNotFoundError()

        # Validate user ownership
        if data.get("user_id") != str(user_id):
            logger.warning(f"[WizardSession] User mismatch for session {session_id}")
            raise WizardSessionError("No autorizado para esta sesión.", "UNAUTHORIZED")

        # Check expiration (belt and suspenders - cache TTL should handle this)
        expires_at = data.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    logger.info(f"[WizardSession] Session expired: {session_id}")
                    await self.cache.delete(cache_key)
                    raise WizardSessionExpiredError()
            except (ValueError, TypeError):
                pass  # If can't parse, let cache TTL handle it

        return data

    async def _save_session(self, session_id: str, data: Dict[str, Any], renew_ttl: bool = True) -> bool:
        """
        Save session to cache with TTL.

        Args:
            session_id: Session ID
            data: Session data
            renew_ttl: If True, reset TTL to full duration
        """
        cache_key = self._get_cache_key(session_id)

        # Update timestamps (Z suffix = UTC, required for correct JS Date parsing)
        now = datetime.now(timezone.utc)
        data["updated_at"] = now.isoformat()
        if renew_ttl:
            data["expires_at"] = (now + timedelta(seconds=self.session_ttl)).isoformat()

        try:
            success = await self.cache.set(cache_key, data, self.session_ttl)
            if not success:
                logger.error(f"[WizardSession] Failed to save session {session_id}")
                return False
            return True
        except Exception as e:
            logger.error(f"[WizardSession] Cache error saving session {session_id}: {e}")
            return False

    def _build_context(self, session: Dict[str, Any]) -> "WorkflowContext":
        """
        Build WorkflowContext from session data (V2 architecture).

        All context parameters (solicitud_type, motivo, is_minor) are set
        as explicit fields — NOT injected into form_data.
        """
        from ..workflows.workflow_interface import WorkflowContext, RenovacionMotivo

        # Coerce is_minor from session (RadioGroup stores strings)
        is_minor_raw = session.get("is_minor", False)
        is_minor = is_minor_raw is True or is_minor_raw == "true"

        # Parse motivo
        motivo = None
        if session.get("motivo"):
            try:
                motivo = RenovacionMotivo(session["motivo"])
            except ValueError:
                pass

        # Build documents_uploaded from session cache data.
        # In cache-first mode there are no DB record UUIDs yet,
        # so we use placeholder UUIDs (only the keys matter for validation).
        documents = session.get("documents", {})
        documents_uploaded = {
            code: uuid4() for code in documents.keys()
        }

        try:
            wf_code = WorkflowCode(session["workflow_code"])
        except ValueError:
            from ..workflows.generic_workflow import _GenericCode
            wf_code = _GenericCode(session["workflow_code"])

        return WorkflowContext(
            service_request_id=uuid4(),
            user_id=UUID(session["user_id"]),
            workflow_code=wf_code,
            solicitud_type=SolicitudType(session.get("solicitud_type", "expedicion")),
            sub_type=session.get("sub_type"),
            motivo=motivo,
            is_minor=is_minor,
            form_data=session.get("form_data", {}),
            extracted_data=session.get("extracted_data", {}),
            documents_uploaded=documents_uploaded,
        )

    def _get_doc_requirements(self, workflow, context) -> List:
        """
        Get document requirements using V2 architecture.

        V2 (PredefinedWorkflow): get_document_requirements(solicitud_type, motivo, context)
        V1 (BaseWorkflow):       get_document_requirements(sub_type) — legacy only
        """
        if not hasattr(workflow, "get_document_requirements"):
            return []

        from ..workflows.workflow_interface import PredefinedWorkflow
        if isinstance(workflow, PredefinedWorkflow):
            return workflow.get_document_requirements(
                context.solicitud_type, context.motivo, context
            )

        # V1 fallback (GenericWorkflow only)
        return workflow.get_document_requirements(context.sub_type)

    def _session_to_response(self, session: Dict[str, Any], workflow=None) -> WizardSessionResponse:
        """Convert session dict to response model."""
        documents = session.get("documents", {})

        # Get required documents from workflow if available
        required_documents = []
        if workflow:
            try:
                context = self._build_context(session)
                doc_reqs = self._get_doc_requirements(workflow, context)
                if doc_reqs:
                    for doc in doc_reqs:
                        if doc.should_show(context):
                            required_documents.append({
                                "code": doc.document_code,
                                "name_es": doc.document_name_es,
                                "is_required": doc.is_required,
                                "uploaded": doc.document_code in documents,
                            })
            except Exception as e:
                logger.warning(f"[WizardSession] Error getting required documents: {e}")

        # Calculate remaining TTL
        ttl_seconds = self.session_ttl
        expires_at_str = session.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
                ttl_seconds = max(0, int(remaining))
            except (ValueError, TypeError):
                pass

        # Determine workflow capabilities
        requires_appointment = False
        # entity_code priority: site_selection > appointment_data > session default
        site_sel = session.get("site_selection")
        appt_data = session.get("appointment_data")
        if site_sel and site_sel.get("entity_code"):
            entity_code = site_sel["entity_code"]
        elif appt_data and appt_data.get("entity_location_id"):
            entity_code = session.get("entity_code")  # will be resolved at persist
        else:
            entity_code = session.get("entity_code")
        if workflow:
            try:
                requires_appointment = getattr(workflow, "requires_appointment", False)
            except Exception:
                pass

        return WizardSessionResponse(
            session_id=session["session_id"],
            workflow_code=session["workflow_code"],
            solicitud_type=session.get("solicitud_type", "expedicion"),
            sub_type=session.get("sub_type"),
            motivo=session.get("motivo"),
            is_minor=session.get("is_minor", False),
            status=WizardSessionStatus(session.get("status", "active")),
            current_step=session.get("current_step", 1),
            current_step_id=session.get("current_step_id"),
            documents_count=len(documents),
            documents_uploaded=list(documents.keys()),
            form_data=session.get("form_data", {}),
            extracted_data=session.get("extracted_data", {}),
            tariff=session.get("tariff"),
            created_at=datetime.fromisoformat(session["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(session["updated_at"].replace("Z", "+00:00")),
            expires_at=datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00")),
            ttl_seconds=ttl_seconds,
            required_documents=required_documents,
            requires_appointment=requires_appointment,
            entity_code=entity_code,
            appointment_data=session.get("appointment_data"),
            site_selection=session.get("site_selection"),
        )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def start_session(
        self,
        user_id: UUID,
        workflow_code: str,
        solicitud_type: str = "expedicion",
        sub_type: Optional[str] = None,
        motivo: Optional[str] = None,
        is_minor: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        auto_fill_vault: bool = False,
        db=None,
    ) -> WizardSessionResponse:
        """
        Start a new wizard session in cache.

        No database entry is created - all data stays in Redis until payment.

        Args:
            user_id: User ID
            workflow_code: Workflow code (e.g., "PASAPORTE")
            solicitud_type: expedicion, renovacion, or duplicado
            sub_type: Workflow-specific sub-type
            motivo: Reason for renovacion (if applicable)
            is_minor: Is the applicant a minor
            ip_address: Client IP for audit
            user_agent: Browser user agent

        Returns:
            WizardSessionResponse with session_id and details

        Raises:
            WizardSessionError: If workflow is invalid or user has existing session
        """
        logger.info(
            f"[WizardSession] Starting session: user={user_id}, "
            f"workflow={workflow_code}, type={solicitud_type}"
        )

        # Validate workflow
        workflow = workflow_engine.get_workflow_by_string(workflow_code.upper())
        if not workflow:
            raise WizardSessionError(
                f"Flujo de trabajo no encontrado: {workflow_code}",
                "INVALID_WORKFLOW"
            )

        # Get entity code from workflow
        entity_code = workflow.entity_code.value if hasattr(workflow.entity_code, 'value') else str(workflow.entity_code)

        # Create session
        session_id = self._generate_session_id(user_id, workflow_code)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.session_ttl)

        session_data = {
            "session_id": session_id,
            "user_id": str(user_id),
            "workflow_code": workflow_code.upper(),
            "solicitud_type": solicitud_type,
            "sub_type": sub_type,
            "motivo": motivo,
            "entity_code": entity_code,
            "status": WizardSessionStatus.ACTIVE.value,
            "is_minor": is_minor,
            "documents": {},
            "extracted_data": {},
            "form_data": {},
            "current_step": 1,
            "current_step_id": None,
            "tariff": None,
            "validation_results": None,
            "has_errors": False,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        # Save to cache
        success = await self._save_session(session_id, session_data)
        if not success:
            raise WizardSessionError("Error al crear la sesión. Por favor, intente de nuevo.")

        logger.info(f"[WizardSession] Session created: {session_id}, expires_at={expires_at}")

        # Phase 2: auto-fill vault documents if requested and DB available
        if auto_fill_vault and db:
            try:
                await self._auto_fill_from_vault(
                    session_id, session_data, user_id, workflow_code.upper(), db
                )
                # Reload session after modifications
                session_data = await self._get_session(session_id, user_id)
            except Exception as e:
                logger.warning(
                    f"[WizardSession] Auto-fill vault failed (non-blocking): {e}"
                )

        return self._session_to_response(session_data, workflow)

    async def _auto_fill_from_vault(
        self,
        session_id: str,
        session_data: Dict,
        user_id: UUID,
        workflow_code: str,
        db,
    ) -> None:
        """Auto-fill wizard session with matching vault documents.

        Queries workflow_document_requirements + user_documents to find
        active, non-expired vault docs that match the workflow's requirements.
        Each match is loaded into the session via the same logic as use_vault_document.
        """
        # Get required documents for this workflow
        required_docs = await db.fetch(
            """SELECT document_code
               FROM workflow_document_requirements
               WHERE workflow_code = $1 AND is_active = TRUE
               ORDER BY display_order""",
            workflow_code,
        )
        if not required_docs:
            return

        from datetime import date as date_type
        today = date_type.today()

        filled_count = 0
        for req in required_docs:
            doc_code = req["document_code"]

            # Find the best active vault document for this code
            vault_doc = await db.fetchrow(
                """SELECT id, file_path, file_name, file_size_bytes, mime_type,
                          file_hash, extraction_data, extraction_confidence,
                          extraction_status, display_name, document_type,
                          expiry_date, holder_name, document_number
                   FROM user_documents
                   WHERE user_id = $1
                     AND document_type = $2
                     AND status = 'active'
                     AND deleted_at IS NULL
                     AND (expiry_date IS NULL OR expiry_date > $3)
                   ORDER BY
                     CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END,
                     expiry_date DESC
                   LIMIT 1""",
                user_id, doc_code, today,
            )

            if not vault_doc:
                continue

            # Load into session (same logic as use_vault_document but inline)
            now = datetime.now(timezone.utc)
            extraction = {}
            if vault_doc["extraction_data"]:
                import json as _json
                raw = vault_doc["extraction_data"]
                extraction = _json.loads(raw) if isinstance(raw, str) else raw

            document_data = {
                "document_code": doc_code,
                "file_name": vault_doc["file_name"],
                "file_size": vault_doc["file_size_bytes"],
                "mime_type": vault_doc["mime_type"],
                "vault_document_id": str(vault_doc["id"]),
                "vault_file_path": vault_doc["file_path"],
                "extraction": extraction,
                "confidence": float(vault_doc["extraction_confidence"] or 0),
                "processor": "vault_reuse",
                "extraction_status": vault_doc["extraction_status"] or "completed",
                "risk_analysis": None,
                "doc_hash": vault_doc["file_hash"],
                "previewed_at": now.isoformat(),
                "confirmed_at": now.isoformat(),
                "user_corrections": None,
            }

            if "documents" not in session_data:
                session_data["documents"] = {}
            session_data["documents"][doc_code] = document_data

            if "extracted_data" not in session_data:
                session_data["extracted_data"] = {}
            session_data["extracted_data"][doc_code] = extraction

            filled_count += 1

        if filled_count > 0:
            await self._save_session(session_id, session_data, renew_ttl=False)
            logger.info(
                f"[WizardSession] Auto-filled {filled_count} vault docs "
                f"for session {session_id}"
            )

    async def get_session(
        self,
        session_id: str,
        user_id: UUID,
    ) -> WizardSessionResponse:
        """
        Get existing wizard session.

        Args:
            session_id: Session ID
            user_id: User ID for authorization

        Returns:
            WizardSessionResponse with current session state
        """
        session = await self._get_session(session_id, user_id)
        workflow = workflow_engine.get_workflow_by_string(session["workflow_code"])
        return self._session_to_response(session, workflow)

    async def preview_document(
        self,
        session_id: str,
        user_id: UUID,
        document_code: str,
        file_content: bytes,
        file_name: str,
        mime_type: str,
    ) -> WizardDocumentPreviewResponse:
        """
        Preview document extraction and store in session.

        Extracts data using Gemini OCR and stores both content and extraction
        in the session cache. Renews session TTL.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            document_code: Document code (e.g., 'dip', 'pasaporte_antiguo')
            file_content: File binary content
            file_name: Original file name
            mime_type: MIME type

        Returns:
            WizardDocumentPreviewResponse with extraction results

        Raises:
            WizardSessionNotFoundError: Session not found
            WizardSessionExpiredError: Session expired
            WizardDocumentValidationError: Invalid document
        """
        logger.info(f"[WizardSession] Preview document: session={session_id}, doc={document_code}")

        # Validate file size
        file_size = len(file_content)
        max_size = MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            raise WizardDocumentValidationError(
                f"El archivo excede el tamaño máximo de {MAX_DOCUMENT_SIZE_MB}MB.",
                "FILE_TOO_LARGE"
            )

        # Validate MIME type
        if mime_type not in ALLOWED_MIME_TYPES:
            raise WizardDocumentValidationError(
                f"Formato de archivo no soportado. Use PDF, JPG o PNG.",
                "INVALID_MIME_TYPE"
            )

        # Validate file integrity (OWASP A08: magic bytes — Phase 5)
        from app.modules.user_documents.services.user_documents_service import (
            validate_file_integrity,
        )
        is_valid, integrity_error = validate_file_integrity(
            file_content, file_name, mime_type
        )
        if not is_valid:
            logger.warning(
                f"[WizardSession] File integrity check failed for "
                f"'{file_name}': {integrity_error}"
            )
            raise WizardDocumentValidationError(
                f"Archivo rechazado: {integrity_error}",
                "FILE_INTEGRITY_FAILED",
            )

        # Get session
        session = await self._get_session(session_id, user_id)

        # Get workflow for document validation and schema
        workflow = workflow_engine.get_workflow_by_string(session["workflow_code"])
        if not workflow:
            raise WizardSessionError(f"Workflow not found: {session['workflow_code']}")

        # Get extraction schema key for this document
        extraction_schema_key = None
        context = self._build_context(session)
        doc_reqs = self._get_doc_requirements(workflow, context)
        for doc_req in doc_reqs:
            if doc_req.document_code == document_code:
                extraction_schema_key = doc_req.schema_key
                break

        # Get existing extractions for cross-validation
        existing_documents = session.get("extracted_data", {})

        # Skip OCR for photo documents (no schema = nothing to extract)
        is_photo = extraction_schema_key is None and "photo" in document_code.lower()
        if is_photo:
            logger.info(f"[WizardSession] Photo document, skipping OCR: {document_code}")
            # Compute SHA-256 hash even for photos (Phase 1 dedup)
            import hashlib as _hashlib
            photo_hash = _hashlib.sha256(file_content).hexdigest()
            extraction_result = {
                "extraction": {},
                "confidence": 1.0,
                "processor": "photo_validation",
                "status": "success",
                "document_type": document_code,
                "doc_hash": photo_hash,
            }
        else:
            # Extract document data using Gemini
            try:
                extraction_result = await gemini_document_processor.process(
                    content=file_content,
                    mime_type=mime_type,
                    document_code=document_code,
                    user_id=str(user_id),
                    existing_documents=existing_documents,
                    extraction_schema_key=extraction_schema_key,
                    workflow_code=session["workflow_code"],
                )
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                logger.error(
                    f"[WizardSession] Extraction failed: {e}\n"
                    f"Traceback:\n{tb}"
                )
                raise WizardDocumentValidationError(
                    "Error al procesar el documento. Verifique que sea legible.",
                    "EXTRACTION_FAILED"
                )

        # Store document in session (including base64 content)
        now = datetime.now(timezone.utc)
        document_data = {
            "document_code": document_code,
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "content_b64": base64.b64encode(file_content).decode("utf-8"),
            "extraction": extraction_result.get("extraction", {}),
            "confidence": extraction_result.get("confidence", 0),
            "processor": extraction_result.get("processor", "unknown"),
            "extraction_status": extraction_result.get("status", "pending"),
            "risk_analysis": extraction_result.get("risk_analysis"),
            "doc_hash": extraction_result.get("doc_hash"),
            "previewed_at": now.isoformat(),
            "confirmed_at": None,
            "user_corrections": None,
        }

        # Update session documents
        if "documents" not in session:
            session["documents"] = {}
        session["documents"][document_code] = document_data

        # Merge extraction into extracted_data
        if "extracted_data" not in session:
            session["extracted_data"] = {}
        session["extracted_data"][document_code] = extraction_result.get("extraction", {})

        # Save session (renews TTL)
        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise WizardSessionError("Error al guardar la vista previa.")

        logger.info(
            f"[WizardSession] Document preview saved: session={session_id}, "
            f"doc={document_code}, confidence={document_data['confidence']}"
        )

        # Calculate remaining TTL
        ttl_seconds = self.session_ttl
        expires_at_str = session.get("expires_at")
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.session_ttl)
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
                ttl_seconds = max(0, int(remaining))
            except (ValueError, TypeError):
                pass

        return WizardDocumentPreviewResponse(
            session_id=session_id,
            document_code=document_code,
            file_name=file_name,
            file_size=file_size,
            extraction=extraction_result.get("extraction", {}),
            confidence=extraction_result.get("confidence", 0),
            processor=extraction_result.get("processor", "unknown"),
            extraction_status=extraction_result.get("status", "pending"),
            needs_correction=extraction_result.get("confidence", 0) < 0.7,
            risk_analysis=extraction_result.get("risk_analysis"),
            cross_validation=extraction_result.get("cross_validation"),
            expires_at=expires_at,
            ttl_seconds=ttl_seconds,
        )

    async def confirm_document(
        self,
        session_id: str,
        user_id: UUID,
        document_code: str,
        confirmed_data: Dict[str, Any],
        user_notes: Optional[str] = None,
    ) -> WizardSessionResponse:
        """
        Confirm document extraction with optional corrections.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            document_code: Document code to confirm
            confirmed_data: User-confirmed (or corrected) extraction data
            user_notes: Optional user notes

        Returns:
            Updated WizardSessionResponse
        """
        logger.info(f"[WizardSession] Confirm document: session={session_id}, doc={document_code}")

        session = await self._get_session(session_id, user_id)

        # Verify document exists in session
        if document_code not in session.get("documents", {}):
            raise WizardSessionError(
                f"Documento no encontrado en sesión: {document_code}",
                "DOCUMENT_NOT_FOUND"
            )

        # Defensive contract: extracted_data MUST be a dict-of-dicts so
        # downstream identity-comparison code (gemini_document_processor)
        # can call `.get()` on each entry. Reject non-dict input here at
        # the boundary instead of letting bad data propagate into the
        # session cache and crash the next preview call.
        if not isinstance(confirmed_data, dict):
            logger.warning(
                f"[WizardSession] confirm_document rejecting non-dict "
                f"confirmed_data ({type(confirmed_data).__name__}) for "
                f"{document_code} — coercing to empty dict"
            )
            confirmed_data = {}

        now = datetime.now(timezone.utc)

        # Update document with confirmed data
        session["documents"][document_code]["confirmed_at"] = now.isoformat()
        session["documents"][document_code]["user_corrections"] = confirmed_data
        if user_notes:
            session["documents"][document_code]["user_notes"] = user_notes

        # Update extracted_data with confirmed values
        session["extracted_data"][document_code] = confirmed_data

        # Save session
        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise WizardSessionError("Error al confirmar el documento.")

        logger.info(f"[WizardSession] Document confirmed: session={session_id}, doc={document_code}")

        workflow = workflow_engine.get_workflow_by_string(session["workflow_code"])
        return self._session_to_response(session, workflow)

    async def delete_document(
        self,
        session_id: str,
        user_id: UUID,
        document_code: str,
    ) -> WizardSessionResponse:
        """
        Delete a document from the wizard session.

        Removes the document data, extraction data and resets the uploaded
        status so the user can re-upload.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            document_code: Document code to delete (e.g., 'dip', 'pasaporte_antiguo')

        Returns:
            Updated WizardSessionResponse
        """
        logger.info(f"[WizardSession] Delete document: session={session_id}, doc={document_code}")

        session = await self._get_session(session_id, user_id)

        # Verify document exists in session
        if document_code not in session.get("documents", {}):
            raise WizardSessionError(
                f"Documento no encontrado en sesión: {document_code}",
                "DOCUMENT_NOT_FOUND"
            )

        # Remove document data
        del session["documents"][document_code]

        # Remove extraction data
        if document_code in session.get("extracted_data", {}):
            del session["extracted_data"][document_code]

        # Save session
        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise WizardSessionError("Error al eliminar el documento.")

        logger.info(f"[WizardSession] Document deleted: session={session_id}, doc={document_code}")

        workflow = workflow_engine.get_workflow_by_string(session["workflow_code"])
        return self._session_to_response(session, workflow)

    async def use_vault_document(
        self,
        session_id: str,
        user_id: UUID,
        document_code: str,
        vault_document_id: str,
        db,
    ) -> WizardSessionResponse:
        """
        Use an existing vault document in the wizard session.

        Instead of uploading a file, copies the vault document's metadata
        and extraction data into the session. On persist, the vault's
        file_path will be reused (no Firebase re-upload).

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            document_code: Document code to fill (e.g., 'dip')
            vault_document_id: UUID string of the vault document
            db: asyncpg connection

        Returns:
            Updated WizardSessionResponse
        """
        logger.info(
            f"[WizardSession] Use vault document: session={session_id}, "
            f"doc={document_code}, vault_id={vault_document_id}"
        )

        session = await self._get_session(session_id, user_id)

        # Validate vault document ownership and existence
        vault_doc = await db.fetchrow(
            """SELECT id, file_path, file_name, file_size_bytes, mime_type,
                      file_hash, extraction_data, extraction_confidence,
                      extraction_status, display_name, document_type,
                      expiry_date, holder_name, document_number
               FROM user_documents
               WHERE id = $1 AND user_id = $2
                 AND status = 'active' AND deleted_at IS NULL""",
            UUID(vault_document_id),
            user_id,
        )

        if not vault_doc:
            raise WizardSessionError(
                "Documento no encontrado en el cofre.",
                "VAULT_DOCUMENT_NOT_FOUND",
            )

        # Build document data compatible with session format
        now = datetime.now(timezone.utc)
        extraction = {}
        if vault_doc["extraction_data"]:
            import json as _json
            raw = vault_doc["extraction_data"]
            extraction = _json.loads(raw) if isinstance(raw, str) else raw

        vault_confidence = float(vault_doc["extraction_confidence"] or 0)
        # Only auto-confirm if vault extraction had high confidence
        # Low confidence docs need manual review in form_review step
        auto_confirmed = vault_confidence >= 0.85

        document_data = {
            "document_code": document_code,
            "file_name": vault_doc["file_name"],
            "file_size": vault_doc["file_size_bytes"],
            "mime_type": vault_doc["mime_type"],
            # NO content_b64 — persist will detect vault_document_id and skip Firebase
            "vault_document_id": vault_document_id,
            "vault_file_path": vault_doc["file_path"],
            "extraction": extraction,
            "confidence": vault_confidence,
            "processor": "vault_reuse",
            "extraction_status": vault_doc["extraction_status"] or "completed",
            "risk_analysis": None,  # Not re-computed for vault docs (already validated at upload)
            "doc_hash": vault_doc["file_hash"],
            "previewed_at": now.isoformat(),
            "confirmed_at": now.isoformat() if auto_confirmed else None,
            "user_corrections": None,
            # Preserve identity fields for downstream cross-validation
            "holder_name": vault_doc["holder_name"],
            "document_number": vault_doc["document_number"],
        }

        # Update session documents
        if "documents" not in session:
            session["documents"] = {}
        session["documents"][document_code] = document_data

        # Merge extraction into extracted_data
        if "extracted_data" not in session:
            session["extracted_data"] = {}
        session["extracted_data"][document_code] = extraction

        # Save session (renews TTL)
        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise WizardSessionError("Error al guardar el documento del cofre.")

        # Audit trail: log vault document selection (OWASP A09 — Phase 5)
        try:
            from app.modules.user_documents.repositories.user_documents_repository import (
                user_documents_repository,
            )
            await user_documents_repository.log_access(
                db=db,
                doc_id=UUID(vault_document_id),
                accessed_by=user_id,
                access_type="vault_selection",
                access_context=f"wizard_session:{session_id}",
            )
        except Exception as e:
            logger.debug(f"[WizardSession] Vault selection audit log failed (non-blocking): {e}")

        logger.info(
            f"[WizardSession] Vault document linked: session={session_id}, "
            f"doc={document_code}, vault_file={vault_doc['file_name']}"
        )

        workflow = workflow_engine.get_workflow_by_string(session["workflow_code"])
        return self._session_to_response(session, workflow)

    async def save_form_data(
        self,
        session_id: str,
        user_id: UUID,
        form_data: Dict[str, Any],
        step_id: Optional[str] = None,
        step_number: Optional[int] = None,
    ) -> WizardSessionResponse:
        """
        Save form data to session.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            form_data: Form data to save (merged with existing)
            step_id: Current step ID
            step_number: Current step number

        Returns:
            Updated WizardSessionResponse
        """
        logger.info(f"[WizardSession] Save form data: session={session_id}, step={step_id}")

        session = await self._get_session(session_id, user_id)

        # Merge form data (user edits take precedence)
        existing_form_data = session.get("form_data", {})
        session["form_data"] = {**existing_form_data, **form_data}

        # Promote SELECTION fields to session level when present in form_data.
        # These fields control document requirements filtering and tariff calculation.
        # The frontend sends them after SELECTION step completion.
        selection_promotable = {
            "solicitud_type": str,
            "motivo": str,
            "is_minor": lambda v: v is True or v == "true",
            "sub_type": str,
        }
        for key, coerce in selection_promotable.items():
            if key in form_data and form_data[key] is not None:
                if key == "is_minor":
                    session[key] = coerce(form_data[key])
                else:
                    val = form_data[key]
                    # Normalize to lowercase for solicitud_type (enum expects lowercase)
                    if key == "solicitud_type" and isinstance(val, str):
                        val = val.lower()
                    session[key] = val
                logger.info(f"[WizardSession] Promoted {key}={session[key]} to session level")

        # Update step tracking
        if step_id:
            session["current_step_id"] = step_id
        if step_number:
            session["current_step"] = step_number

        # Save session
        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise WizardSessionError("Error al guardar los datos del formulario.")

        logger.info(f"[WizardSession] Form data saved: session={session_id}")

        workflow = workflow_engine.get_workflow_by_string(session["workflow_code"])
        return self._session_to_response(session, workflow)

    async def save_appointment_data(
        self,
        session_id: str,
        user_id: UUID,
        appointment_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save appointment selection data to session cache.

        This stores the user's appointment choice (location, date, time)
        WITHOUT creating a real hold. The actual hold is created atomically
        during payment via initiate_payment().

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            appointment_data: Appointment selection data

        Returns:
            Saved appointment data dict
        """
        session = await self._get_session(session_id, user_id)

        session["appointment_data"] = appointment_data

        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise WizardSessionError("Error al guardar la selección de cita.")

        logger.info(
            f"[WizardSession] Appointment data saved: session={session_id}, "
            f"location={appointment_data.get('location_name')}, "
            f"date={appointment_data.get('appointment_date')}, "
            f"time={appointment_data.get('appointment_time')}"
        )

        return appointment_data

    async def save_site_selection(
        self,
        session_id: str,
        user_id: UUID,
        site_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save site selection to session cache (for non-appointment workflows).

        Stores entity_location_id + metadata so _persist_session_to_db()
        can derive entity_code from it.
        """
        session = await self._get_session(session_id, user_id)

        session["site_selection"] = site_data

        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise WizardSessionError("Error al guardar la selección del sitio.")

        logger.info(
            f"[WizardSession] Site selection saved: session={session_id}, "
            f"location={site_data.get('location_name')}, "
            f"city={site_data.get('city')}"
        )

        return site_data

    async def get_form_config(
        self,
        session_id: str,
        user_id: UUID,
        step_id: str,
    ):
        """
        Get dynamic form configuration for a session step.

        Builds a WorkflowContext from the session cache and calls
        workflow.get_form_config() to get sections filtered by conditions.
        Values are pre-filled from extracted_data + form_data.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            step_id: The form_review step ID (e.g., 'form_review_1')

        Returns:
            FormConfigResponse with sections, fields, and pre-filled values
        """
        from ..models.form_config import FormConfigResponse, FormFieldResponse, FormSectionResponse

        logger.info(f"[WizardSession] Get form config: session={session_id}, step={step_id}")

        session = await self._get_session(session_id, user_id)

        workflow = workflow_engine.get_workflow_by_string(session["workflow_code"])
        if not workflow:
            raise WizardSessionError(f"Workflow not found: {session['workflow_code']}")

        context = self._build_context(session)

        # Get form configuration (sections filtered by conditions)
        try:
            form_config = workflow.get_form_config(step_id, context)
        except ValueError as e:
            raise WizardSessionError(str(e))

        # Get form mapping to resolve values
        form_mapping = workflow.get_form_mapping(context)

        form_data = session.get("form_data", {})
        extracted_data = session.get("extracted_data", {})

        # Build response with pre-filled values
        sections_response = []
        for section in form_config.sections:
            fields_response = []
            for field in section.fields:
                # Resolve current value from form_data or extracted_data
                current_value = self._resolve_field_value(
                    field.key, form_mapping, form_data, extracted_data
                )
                fields_response.append(FormFieldResponse(
                    key=field.key,
                    label_es=field.label_es,
                    type=field.type,
                    required=field.required,
                    options=field.options,
                    readonly=field.readonly,
                    placeholder_es=field.placeholder_es,
                    validation=field.validation,
                    current_value=current_value,
                ))
            sections_response.append(FormSectionResponse(
                id=section.id,
                title_es=section.title_es,
                fields=fields_response,
                source_document=section.source_document,
                description_es=section.description_es,
            ))

        return FormConfigResponse(
            step_id=form_config.step_id,
            title_es=form_config.title_es,
            description_es=form_config.description_es,
            sections=sections_response,
        )

    @staticmethod
    def _resolve_field_value(
        field_key: str,
        form_mapping: dict,
        form_data: dict,
        extracted_data: dict,
    ):
        """Resolve a field value from form_data or extracted_data.

        Supports both nested paths ("dip.titular.apellidos") and flat
        Gemini extraction structures ({"apellidos": "GARCIA"}).
        Tries nested navigation first, then falls back to flat field lookup.
        """
        # Priority 1: Check form_data for user edits
        if field_key in form_data:
            return form_data[field_key]

        # Priority 2: Resolve from extracted_data using mapping
        extraction_path = form_mapping.get(field_key)
        if not extraction_path:
            return None

        # Literal values (e.g. "_literal:DIP" → "DIP")
        if extraction_path.startswith("_literal:"):
            return extraction_path[9:]

        # Form data values (e.g. "_form:sub_type" → form_data["sub_type"])
        if extraction_path.startswith("_form:"):
            form_key = extraction_path[6:]
            return form_data.get(form_key)

        # Parse path like "dip.titular.apellidos"
        parts = extraction_path.split(".")
        if len(parts) < 2:
            return None

        # First part is document code
        doc_code = parts[0]
        if doc_code not in extracted_data:
            return None

        doc_data = extracted_data[doc_code]

        # Try nested path first: "dip.titular.apellidos" → doc["titular"]["apellidos"]
        value = doc_data
        for part in parts[1:]:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break

        if value is not None:
            return value

        # Fallback: flat field lookup using last segment only
        # Gemini returns flat extraction {"apellidos": "GARCIA"} not nested
        # {"titular": {"apellidos": "GARCIA"}}
        flat_key = parts[-1]
        if isinstance(doc_data, dict) and flat_key in doc_data:
            return doc_data[flat_key]

        return None

    async def prepare_for_payment(
        self,
        session_id: str,
        user_id: UUID,
        db: asyncpg.Connection,
    ) -> WizardPreparePaymentResponse:
        """
        Prepare session for payment.

        Validates all documents are uploaded, runs cross-validation,
        and calculates tariff. Does NOT persist to DB yet.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            db: Database connection (for tariff lookup)

        Returns:
            WizardPreparePaymentResponse with tariff and validation status
        """
        logger.info(f"[WizardSession] Prepare for payment: session={session_id}")

        session = await self._get_session(session_id, user_id)

        workflow = workflow_engine.get_workflow_by_string(session["workflow_code"])
        if not workflow:
            raise WizardSessionError(f"Workflow not found: {session['workflow_code']}")

        # Build context for validation and tariff
        context = self._build_context(session)

        # Diagnostic logging for payment validation
        uploaded_docs = list(session.get("documents", {}).keys())
        logger.info(
            f"[WizardSession] Payment context: solicitud_type={context.solicitud_type.value}, "
            f"motivo={context.motivo}, is_minor={context.is_minor}, "
            f"uploaded_docs={uploaded_docs}, docs_in_context={list(context.documents_uploaded.keys())}"
        )

        # Check required documents
        missing_documents = []
        doc_reqs = self._get_doc_requirements(workflow, context)
        for doc_req in doc_reqs:
            if doc_req.should_show(context) and doc_req.is_required:
                if doc_req.document_code not in session.get("documents", {}):
                    missing_documents.append(doc_req.document_code)

        # Run validation
        errors = []
        warnings = []
        if hasattr(workflow, 'validate_documents'):
            validation_results = workflow.validate_documents(context)
            for result in validation_results:
                if hasattr(result, 'is_error') and result.is_error:
                    errors.append({
                        "rule_id": result.rule_id,
                        "message_es": result.message_es,
                        "field": getattr(result, 'field', None),
                    })
                elif hasattr(result, 'is_warning') and result.is_warning:
                    warnings.append({
                        "rule_id": result.rule_id,
                        "message_es": result.message_es,
                        "field": getattr(result, 'field', None),
                    })

        # Validate required form fields across all form_review steps
        form_data = session.get("form_data", {})
        if hasattr(workflow, 'get_form_config'):
            # Check each form_review step
            step_num = 1
            while True:
                step_id = f"form_review_{step_num}"
                try:
                    form_config = workflow.get_form_config(step_id, context)
                    for section in form_config.sections:
                        for field in section.fields:
                            if field.required:
                                value = form_data.get(field.key)
                                if value is None or value == "" or value == []:
                                    errors.append({
                                        "rule_id": f"required_field_{field.key}",
                                        "message_es": f"Campo obligatorio: {field.label_es}",
                                        "field": field.key,
                                    })
                    step_num += 1
                except (ValueError, AttributeError):
                    break  # No more form_review steps

        # Calculate tariff
        tariff = await tariff_calculator.calculate(db, workflow, context)

        # Update session
        session["tariff"] = tariff
        session["validation_results"] = errors + warnings
        session["has_errors"] = len(errors) > 0 or len(missing_documents) > 0

        if not session["has_errors"] and not missing_documents:
            session["status"] = WizardSessionStatus.READY_FOR_PAYMENT.value

        # Save session
        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise WizardSessionError("Error al preparar el pago.")

        ready_for_payment = not session["has_errors"] and not missing_documents

        if not ready_for_payment:
            error_details = [e.get("message_es", e.get("rule_id")) for e in errors]
            logger.warning(
                f"[WizardSession] Payment NOT ready: session={session_id}, "
                f"missing_docs={missing_documents}, errors={error_details}"
            )
        else:
            logger.info(
                f"[WizardSession] Prepare payment complete: session={session_id}, "
                f"ready=True, amount={tariff.get('total_amount', 0)}"
            )

        # Load available payment methods
        from app.modules.payments.services.processors import payment_processor_registry
        from app.modules.service_requests.models.wizard_session import PaymentMethodInfoResponse

        methods_info = payment_processor_registry.get_methods_info()
        payment_methods = [
            PaymentMethodInfoResponse(**m) for m in methods_info
        ]
        default_method = "mobile_money" if any(
            m.code == "mobile_money" for m in payment_methods
        ) else None

        return WizardPreparePaymentResponse(
            session_id=session_id,
            ready_for_payment=ready_for_payment,
            tariff=tariff,
            total_amount=tariff.get("total_amount", 0),
            currency=tariff.get("currency", "XAF"),
            validation_passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            all_documents_uploaded=len(missing_documents) == 0,
            missing_documents=missing_documents,
            payment_methods=payment_methods,
            default_payment_method=default_method,
        )

    # =========================================================================
    # PRIVATE: Shared persist logic (used by persist_to_db + initiate_payment)
    # =========================================================================

    async def _persist_session_data(
        self,
        db: asyncpg.Connection,
        session: Dict[str, Any],
        status_comment: str = "Cache-first wizard: payment initiated",
    ) -> tuple:
        """
        Create service_request + upload documents to Firebase + create doc records.

        Must be called inside an active ``db.transaction()``.

        Args:
            db: Database connection (inside transaction)
            session: Session data dict from cache
            status_comment: Comment for the status transition audit

        Returns:
            (service_request_id, reference, uploaded_files) — uploaded_files is a
            list of Firebase paths for rollback if needed.
        """
        from app.modules.documents.services.storage_service import firebase_storage_service

        workflow_code = resolve_workflow_code(session)
        user_id_uuid = UUID(session["user_id"])
        uploaded_files: List[str] = []

        # Resolve entity_location_id for site-based routing
        # Source: appointment_data (RDV workflows) or site_selection (non-RDV workflows)
        # Strict: entity_location_id MUST be set — no silent fallback to enum
        entity_location_id = None
        appointment_data = session.get("appointment_data")
        if appointment_data and appointment_data.get("entity_location_id"):
            try:
                entity_location_id = UUID(appointment_data["entity_location_id"])
            except (ValueError, TypeError):
                pass
        if not entity_location_id:
            # site_selection or form_data may carry entity_location_id
            site_loc = session.get("site_selection", {}).get("entity_location_id")
            if not site_loc:
                site_loc = session.get("form_data", {}).get("entity_location_id")
            if site_loc:
                try:
                    entity_location_id = UUID(site_loc)
                except (ValueError, TypeError):
                    pass

        if not entity_location_id:
            raise WizardSessionError(
                "Debe seleccionar un sitio de tramitación antes de continuar.",
                "MISSING_SITE_SELECTION",
            )

        # Derive entity_code from entity_location_id (strict, single PK lookup)
        from .workflow_engine import resolve_entity_code_from_location
        try:
            entity_code = await resolve_entity_code_from_location(db, entity_location_id)
        except ValueError as e:
            raise WizardSessionError(str(e), "INVALID_SITE_SELECTION")

        # 1. Create service_request record (reference auto-generated by DB trigger)
        request_data = await service_request_repository.create(
            db=db,
            user_id=user_id_uuid,
            workflow_code=workflow_code,
            solicitud_type=session.get("solicitud_type", "expedicion"),
            form_data=session.get("form_data", {}),
            entity_code=entity_code,
            entity_location_id=entity_location_id,
        )
        service_request_id = request_data["id"]
        reference = request_data["reference"]

        # Update status to PAYMENT_PENDING (create() defaults to DRAFT)
        await service_request_repository.update_status(
            db=db,
            request_id=service_request_id,
            new_status=ServiceRequestStatus.PAYMENT_PENDING.value,
            performed_by=user_id_uuid,
            comment=status_comment,
        )

        # 1b. Store tariff amounts so GET /summary and PDF endpoints can read them
        tariff = session.get("tariff", {})
        if tariff.get("total_amount"):
            await service_request_repository.update_amounts(
                db=db,
                request_id=service_request_id,
                base_amount=float(tariff.get("base_amount", 0)),
                supplements_amount=float(tariff.get("supplements_total", 0)),
                penalties_amount=0.0,
                total_amount=float(tariff["total_amount"]),
            )

        # 2. Upload documents to Firebase and create document records
        #    Phase 1 dedup: if file already in vault → reuse file_path, skip Firebase
        #    Phase 2 vault-reuse: if vault_document_id present → use vault_file_path directly
        for doc_code, doc_data in session.get("documents", {}).items():
            doc_hash = doc_data.get("doc_hash")

            # Phase 2: vault document selected via use-vault endpoint
            if doc_data.get("vault_document_id") and doc_data.get("vault_file_path"):
                file_path = doc_data["vault_file_path"]
                logger.info(
                    f"[WizardSession] Using vault doc for {doc_code}: "
                    f"vault_id={doc_data['vault_document_id']}, path={file_path}"
                )
            elif doc_data.get("content_b64"):
                file_content = base64.b64decode(doc_data["content_b64"])

                # Phase 1: check if hash matches existing vault doc
                vault_match = None
                if doc_hash and len(doc_hash) == 64:
                    vault_match = await db.fetchrow(
                        """SELECT file_path FROM user_documents
                           WHERE user_id = $1 AND file_hash = $2
                             AND status = 'active' AND deleted_at IS NULL
                           LIMIT 1""",
                        user_id_uuid, doc_hash,
                    )

                if vault_match:
                    # Reuse existing Firebase file — zero storage cost
                    file_path = vault_match["file_path"]
                    logger.info(
                        f"[WizardSession] Reusing vault file for {doc_code}: "
                        f"hash={doc_hash[:12]}, path={file_path}"
                    )
                else:
                    upload_result = await firebase_storage_service.upload_user_document(
                        user_id=str(user_id_uuid),
                        application_id=str(service_request_id),
                        file=file_content,
                        metadata={
                            "filename": doc_data["file_name"],
                            "mime_type": doc_data["mime_type"],
                            "document_code": doc_code,
                            "document_name": doc_data.get("document_name") or doc_code,
                        }
                    )
                    file_path = upload_result.file_path
                    uploaded_files.append(file_path)
            else:
                logger.warning(
                    f"[WizardSession] Document {doc_code} has no content or vault ref, skipping"
                )
                continue

            doc_record = await document_repository.add_document(
                db=db,
                service_request_id=service_request_id,
                document_code=doc_code,
                document_name=doc_data.get("document_name") or doc_code,
                file_path=file_path,
                file_name=doc_data["file_name"],
                file_size=doc_data["file_size"],
                mime_type=doc_data["mime_type"],
                uploaded_by=user_id_uuid,
                source="cache_first_wizard",
                file_hash=doc_data.get("doc_hash"),
            )

            # Update extraction data (include risk_analysis for agent review)
            extraction_data = doc_data.get("user_corrections") or doc_data.get("extraction", {})
            risk_analysis = doc_data.get("risk_analysis")
            if risk_analysis:
                extraction_data["_risk_analysis"] = risk_analysis
            await document_repository.update_extraction(
                db=db,
                document_id=doc_record["id"],
                extraction_data=extraction_data,
                extraction_confidence=doc_data.get("confidence", 0),
                extraction_status="success" if doc_data.get("confirmed_at") else "pending",
            )

            # Validate if user confirmed extraction
            if doc_data.get("confirmed_at"):
                await document_repository.validate_document(
                    db=db,
                    document_id=doc_record["id"],
                    is_valid=True,
                    validation_errors=[],
                    validated_by=user_id_uuid,
                )

        return service_request_id, reference, uploaded_files

    async def _rollback_firebase_uploads(self, uploaded_files: List[str]) -> None:
        """
        Best-effort cleanup of Firebase uploads after a failed transaction.

        DB rollback is automatic; this handles the non-transactional Firebase side.
        """
        if not uploaded_files:
            return
        try:
            from app.modules.documents.services.storage_service import firebase_storage_service
            for file_path in uploaded_files:
                try:
                    await firebase_storage_service.delete_file(file_path)
                    logger.info(f"[WizardSession] Rollback: deleted {file_path}")
                except Exception as del_err:
                    logger.warning(f"[WizardSession] Rollback failed for {file_path}: {del_err}")
        except Exception:
            pass  # Import failure — nothing to do

    # =========================================================================
    # PRIVATE: generate PDF attachment for email notification
    # =========================================================================

    async def _generate_summary_pdf_attachment(
        self,
        session: Dict[str, Any],
        reference: str,
        workflow: Any,
        appointment_data: Optional[Dict[str, Any]] = None,
        db: Optional[asyncpg.Connection] = None,
        user_id: Optional[UUID] = None,
        service_request_id: Optional[UUID] = None,
    ) -> Optional[List[Tuple[str, bytes, str]]]:
        """Generate citizen summary PDF for email attachment. Returns None on failure.

        If db, user_id, and service_request_id are provided, also uploads the PDF
        to Firebase Storage and registers it in the user's document vault.
        """
        try:
            from .summary_pdf_service import summary_pdf_service
            from ..workflows.workflow_interface import PredefinedWorkflow

            workflow_code = session.get("workflow_code", "")
            workflow_name = workflow.service_name_es if workflow else workflow_code
            form_data = session.get("form_data", {})

            # Build dynamic data sections from workflow form_review configs
            data_sections = []
            if workflow and isinstance(workflow, PredefinedWorkflow):
                context = self._build_context(session)
                data_sections = workflow.get_pdf_data_sections(context)

            documents = [
                {
                    "name": doc_data.get("document_name") or doc_code,
                    "confidence": (doc_data.get("confidence") or 0) * 100,
                    "validation_status": "verified" if doc_data.get("confirmed_at") else "pending",
                }
                for doc_code, doc_data in session.get("documents", {}).items()
            ]
            tariff = session.get("tariff", {})
            tariff_for_pdf = {
                "base_amount": tariff.get("base_amount", 0),
                "additional_fees": [
                    {"name": s.get("label_es", "Suplemento"), "amount": s.get("amount", 0)}
                    for s in tariff.get("supplements", [])
                ],
                "total_amount": tariff.get("total_amount", 0),
            }
            appointment_for_pdf = None
            if appointment_data:
                appointment_for_pdf = {
                    "date": appointment_data.get("appointment_date", "-"),
                    "time": appointment_data.get("appointment_time", "-"),
                    "location": appointment_data.get("location_name", "-"),
                }
            solicitud_type = session.get("solicitud_type", "expedicion")

            # Fetch citizen photo from session documents (photo_carnet)
            photo_url = None
            photo_codes = ("photo_carnet", "fotografias", "foto_carnet")
            for doc_code, doc_data in session.get("documents", {}).items():
                if doc_code in photo_codes and doc_data.get("content_b64"):
                    # Photo is stored as base64 in session — build data URI directly
                    mime = doc_data.get("mime_type", "image/jpeg")
                    photo_url = f"data:{mime};base64,{doc_data['content_b64']}"
                    break

            pdf_bytes = await summary_pdf_service.generate_summary_pdf(
                request_number=reference,
                workflow_name=workflow_name,
                solicitud_type=solicitud_type,
                documents=documents,
                tariff=tariff_for_pdf,
                data_sections=data_sections,
                appointment=appointment_for_pdf,
                language="es",
                photo_url=photo_url,
            )
            filename = f"solicitud_{reference}.pdf"
            logger.info(f"[WizardSession] Generated summary PDF for {reference} ({len(pdf_bytes)} bytes)")

            # Upload to Firebase + register in user vault (non-blocking)
            if db and user_id and service_request_id:
                try:
                    from app.modules.documents.services.storage_service import (
                        firebase_storage_service,
                    )
                    from app.modules.user_documents.services.user_documents_service import (
                        user_documents_service,
                    )
                    upload_result = await firebase_storage_service.upload_tax_attachment(
                        application_id=str(service_request_id),
                        file=pdf_bytes,
                        allowed_users=[str(user_id)],
                        metadata={
                            "filename": filename,
                            "mime_type": "application/pdf",
                            "document_type": "request_summary",
                            "reference": reference,
                        },
                    )
                    sr_token = summary_pdf_service._generate_sr_verification_token(reference)
                    await user_documents_service.auto_import_generated(
                        db=db,
                        user_id=user_id,
                        generation_type="request_summary",
                        file_path=upload_result.file_path,
                        file_name=filename,
                        file_size_bytes=len(pdf_bytes),
                        mime_type="application/pdf",
                        title_es="Solicitud de Tramite",
                        title_fr="Demande de Service",
                        title_en="Service Request",
                        reference_number=reference,
                        service_request_id=service_request_id,
                        verification_code=sr_token,
                    )
                    logger.info(f"[WizardSession] Solicitud PDF registered in user vault for {reference}")
                except Exception as vault_err:
                    logger.warning(f"[WizardSession] Vault registration failed (non-blocking): {vault_err}")

            return [(filename, pdf_bytes, "application/pdf")]
        except Exception as e:
            logger.warning(f"[WizardSession] PDF generation failed (non-blocking): {e}")
            return None

    # =========================================================================
    # PUBLIC: persist_to_db (free services / legacy)
    # =========================================================================

    async def persist_to_db(
        self,
        session_id: str,
        user_id: UUID,
        db: asyncpg.Connection,
        payment_id: Optional[str] = None,
    ) -> WizardPersistResult:
        """
        Persist session data to database (atomic transaction).

        Used for free services (amount=0) or legacy callers.
        For paid services, use initiate_payment() instead.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            db: Database connection
            payment_id: Payment ID if payment was created

        Returns:
            WizardPersistResult with service_request_id and reference

        Raises:
            WizardPersistError: If any step fails (rollback performed)
        """
        logger.info(f"[WizardSession] Persist to DB: session={session_id}")

        session = await self._get_session(session_id, user_id)

        # Verify session is ready
        if session.get("status") != WizardSessionStatus.READY_FOR_PAYMENT.value:
            if session.get("has_errors"):
                raise WizardPersistError(
                    "No se puede procesar: hay errores de validación pendientes.",
                    "VALIDATION_ERRORS"
                )
            # Allow even if not explicitly ready (tariff calculated)

        # Mark session as persisting
        session["status"] = WizardSessionStatus.PAYMENT_INITIATED.value
        await self._save_session(session_id, session, renew_ttl=False)

        uploaded_files: List[str] = []

        try:
            async with db.transaction():
                service_request_id, reference, uploaded_files = \
                    await self._persist_session_data(
                        db, session, "Cache-first wizard: payment initiated"
                    )

            # Post-commit: delete session from cache
            session["status"] = WizardSessionStatus.PERSISTED.value
            cache_key = self._get_cache_key(session_id)
            await self.cache.delete(cache_key)

            logger.info(
                f"[WizardSession] Persist complete: session={session_id}, "
                f"request_id={service_request_id}, reference={reference}"
            )

            # Auto-import wizard documents into user vault (non-blocking)
            try:
                from app.modules.user_documents.services.user_documents_service import (
                    user_documents_service,
                )
                # Build document list from service_request_documents
                sr_docs = await db.fetch(
                    """SELECT id, document_code, file_path, file_name,
                              file_size, mime_type, file_hash
                       FROM service_request_documents
                       WHERE service_request_id = $1""",
                    service_request_id,
                )
                if sr_docs:
                    docs_for_import = [
                        {
                            "id": doc["id"],
                            "document_code": doc["document_code"],
                            "file_path": doc["file_path"],
                            "file_name": doc["file_name"],
                            "file_size_bytes": doc["file_size"] or 0,
                            "mime_type": doc["mime_type"] or "application/octet-stream",
                            "file_hash": doc["file_hash"] or "",
                        }
                        for doc in sr_docs
                    ]
                    imported = await user_documents_service.auto_import_from_wizard(
                        db=db,
                        user_id=user_id,
                        service_request_id=service_request_id,
                        documents=docs_for_import,
                    )
                    if imported:
                        logger.info(
                            f"[WizardSession] Auto-imported {len(imported)} wizard docs "
                            f"into vault for user {user_id}"
                        )
            except Exception as import_err:
                logger.warning(
                    f"[WizardSession] Vault auto-import failed (non-blocking): {import_err}"
                )

            # Generate PDF attachment for email notification + vault registration
            workflow = workflow_engine.get_workflow_by_string(session.get("workflow_code", ""))
            pdf_attachment = await self._generate_summary_pdf_attachment(
                session, reference, workflow, session.get("appointment_data"),
                db=db, user_id=user_id, service_request_id=service_request_id,
            )

            # Store summary PDF in Firebase + vault (non-blocking)
            if pdf_attachment:
                try:
                    from app.modules.documents.services.storage_service import storage_service
                    from app.modules.user_documents.services.vault_registry import register_document_in_vault

                    pdf_name, pdf_bytes_att, _ = pdf_attachment[0]
                    summary_url = await storage_service.upload_bytes(
                        pdf_bytes_att,
                        f"summaries/{service_request_id}/{pdf_name}",
                        content_type="application/pdf",
                    )
                    if summary_url:
                        await register_document_in_vault(
                            db,
                            user_id=user_id,
                            file_path=summary_url,
                            file_name=pdf_name,
                            document_type="CITIZEN_SUMMARY",
                            document_category="fiscal",
                            source_request_id=service_request_id,
                        )
                except Exception as vault_err:
                    logger.warning(f"Summary vault storage failed: {vault_err}")

            # Fetch user info for email notification
            user_email = None
            user_name = None
            user_phone = None
            try:
                user_row = await db.fetchrow(
                    "SELECT email, first_name, last_name, phone_number FROM users WHERE id = $1",
                    user_id,
                )
                if user_row:
                    user_email = user_row["email"]
                    user_name = f"{user_row['first_name'] or ''} {user_row['last_name'] or ''}".strip()
                    user_phone = user_row.get("phone_number")
            except Exception:
                pass  # Non-blocking

            # Publish event (include user info for email notification)
            try:
                EventBus.publish_nowait(EventType.REQUEST_SUBMITTED, {
                    "request_id": str(service_request_id),
                    "user_id": str(user_id),
                    "user_email": user_email,
                    "user_phone": user_phone,
                    "user_name": user_name,
                    "workflow_code": session["workflow_code"],
                    "reference": reference,
                    "attachments": pdf_attachment,
                })
            except Exception:
                pass  # Non-blocking

            return WizardPersistResult(
                success=True,
                service_request_id=service_request_id,
                reference=reference,
                payment_id=payment_id,
            )

        except Exception as e:
            logger.error(f"[WizardSession] Persist failed: {e}", exc_info=True)
            await self._rollback_firebase_uploads(uploaded_files)
            session["status"] = WizardSessionStatus.READY_FOR_PAYMENT.value
            await self._save_session(session_id, session, renew_ttl=True)
            raise WizardPersistError(
                f"Error al guardar la solicitud: {str(e)}",
                "PERSIST_FAILED",
                {"original_error": str(e)}
            )

    # =========================================================================
    # PUBLIC: initiate_payment (atomic persist + pay)
    # =========================================================================

    async def initiate_payment(
        self,
        session_id: str,
        user_id: UUID,
        db: asyncpg.Connection,
        payment_method: str,
        phone_number: Optional[str] = None,
        user_email: Optional[str] = None,
        user_phone: Optional[str] = None,
        user_name: Optional[str] = None,
        treasury_location_id: Optional[str] = None,
        return_url: Optional[str] = None,
    ) -> WizardInitiatePaymentResponse:
        """
        Atomically persist session to database AND initiate payment.

        Combines _persist_session_data() + payment processor in a single
        DB transaction. If anything fails, everything is rolled back:
        - DB: automatic transaction rollback
        - Firebase: uploaded files are cleaned up
        - Cache: session restored to READY_FOR_PAYMENT

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            db: Database connection
            payment_method: Payment method code (mobile_money, card, bank_transfer, cash, check)
            phone_number: Phone number (required for mobile_money)
            user_email: User email for payment context
            user_phone: User phone for payment context
            user_name: User name for payment context

        Returns:
            WizardInitiatePaymentResponse with service_request_id + payment details

        Raises:
            WizardSessionError: Validation errors (session untouched)
            WizardPersistError: Transaction or payment failure (rolled back)
        """
        logger.info(
            f"[WizardSession] Initiate payment: session={session_id}, "
            f"method={payment_method}"
        )

        session = await self._get_session(session_id, user_id)

        # Validate session is ready
        if session.get("status") != WizardSessionStatus.READY_FOR_PAYMENT.value:
            if session.get("has_errors"):
                raise WizardPersistError(
                    "No se puede procesar: hay errores de validación pendientes.",
                    "VALIDATION_ERRORS"
                )
            if not session.get("tariff"):
                raise WizardSessionError(
                    "Debe preparar el pago primero (prepare-payment).",
                    "NOT_READY_FOR_PAYMENT"
                )

        # Validate payment method
        from app.modules.payments.models.payment import PaymentMethod as PM
        try:
            payment_method_enum = PM(payment_method)
        except ValueError:
            raise WizardSessionError(
                f"Método de pago no válido: {payment_method}",
                "INVALID_PAYMENT_METHOD"
            )

        # Validate phone for mobile money
        if payment_method_enum == PM.MOBILE_MONEY and not phone_number:
            raise WizardSessionError(
                "Número de teléfono requerido para Mobile Money.",
                "PHONE_REQUIRED"
            )

        # Validate tariff
        tariff = session.get("tariff")
        if not tariff:
            raise WizardSessionError(
                "Tarifa no calculada. Ejecute prepare-payment primero.",
                "NO_TARIFF"
            )
        total_amount = tariff.get("total_amount", 0)
        if total_amount <= 0:
            raise WizardSessionError(
                "No se requiere pago para esta solicitud.",
                "NO_PAYMENT_REQUIRED"
            )

        # Anti double-click: mark session as PAYMENT_INITIATED
        session["status"] = WizardSessionStatus.PAYMENT_INITIATED.value
        await self._save_session(session_id, session, renew_ttl=False)

        uploaded_files: List[str] = []

        try:
            from app.modules.payments.services.processors import payment_processor_registry
            from app.modules.payments.services.processors.base import PaymentContext
            from decimal import Decimal

            workflow_code = session["workflow_code"]
            user_id_uuid = UUID(session["user_id"])

            # Get workflow for capabilities
            workflow = workflow_engine.get_workflow_by_string(workflow_code)
            requires_appointment = getattr(workflow, "requires_appointment", False) if workflow else False

            # Read appointment data from session (selected before payment)
            appointment_data = session.get("appointment_data")
            appointment_confirmed = False
            appt_date_str = None
            appt_time_str = None
            appt_location_str = None

            # Fail early: appointment required but no data selected
            if requires_appointment and not appointment_data:
                raise WizardPersistError(
                    "Se requiere una cita para este trámite. Seleccione una cita antes de pagar.",
                    "APPOINTMENT_REQUIRED",
                )

            async with db.transaction():
                # Steps A+B: create service_request + upload docs (shared logic)
                service_request_id, reference, uploaded_files = \
                    await self._persist_session_data(
                        db, session, f"Atomic wizard payment: {payment_method}"
                    )
                logger.info(
                    f"[WizardSession] Step A+B complete: request={service_request_id}, "
                    f"ref={reference}, files={len(uploaded_files)}"
                )

                # Step A2: Hold + confirm appointment atomically (if selected)
                if appointment_data and requires_appointment:
                    from ..services.appointment_service import appointment_service
                    from datetime import date as date_type, time as time_type

                    # Validate required fields before parsing
                    required_appt_keys = ["entity_location_id", "appointment_date", "appointment_time"]
                    missing_keys = [k for k in required_appt_keys if not appointment_data.get(k)]
                    if missing_keys:
                        raise WizardPersistError(
                            f"Datos de cita incompletos: faltan {', '.join(missing_keys)}",
                            "INCOMPLETE_APPOINTMENT_DATA",
                            {"missing_keys": missing_keys}
                        )

                    appt_loc_id = UUID(appointment_data["entity_location_id"])
                    appt_date = date_type.fromisoformat(appointment_data["appointment_date"])
                    appt_time = time_type.fromisoformat(appointment_data["appointment_time"])
                    slot_config_id = (
                        UUID(appointment_data["slot_config_id"])
                        if appointment_data.get("slot_config_id")
                        else None
                    )

                    hold_result = await appointment_service.hold_slot(
                        db, service_request_id, appt_loc_id,
                        appt_date, appt_time, slot_config_id
                    )
                    if not hold_result.success:
                        raise WizardPersistError(
                            f"El horario seleccionado ya no está disponible: {hold_result.error}",
                            "APPOINTMENT_SLOT_TAKEN",
                            {"appointment_error": hold_result.error}
                        )

                    confirm_result = await appointment_service.confirm_hold(
                        db, service_request_id
                    )
                    if confirm_result.success:
                        appointment_confirmed = True
                        appt_date_str = appointment_data["appointment_date"]
                        appt_time_str = appointment_data["appointment_time"]
                        appt_location_str = appointment_data.get("location_name")
                        logger.info(
                            f"[WizardSession] Appointment confirmed atomically: "
                            f"request={service_request_id}, date={appt_date_str}, "
                            f"time={appt_time_str}, location={appt_location_str}"
                        )

                logger.info(
                    f"[WizardSession] Step A2 complete (appointment): "
                    f"confirmed={appointment_confirmed}, has_data={bool(appointment_data)}, "
                    f"requires={requires_appointment}"
                )

                # Step C: Build PaymentContext and call processor
                logger.info(f"[WizardSession] Step C: initiating {payment_method} payment...")
                payment_metadata = {}
                if treasury_location_id:
                    payment_metadata["treasury_location_id"] = treasury_location_id

                payment_context = PaymentContext(
                    service_request_id=str(service_request_id),
                    user_id=str(user_id_uuid),
                    amount=Decimal(str(total_amount)),
                    currency=tariff.get("currency", "XAF"),
                    payment_method=payment_method_enum,
                    tariff_breakdown=tariff,
                    user_email=user_email,
                    user_phone=phone_number or user_phone,
                    user_name=user_name,
                    workflow_code=workflow_code,
                    service_name=workflow.service_name_es if workflow else None,
                    reference_number=reference,
                    metadata=payment_metadata,
                    return_url=return_url,
                )

                payment_result = await payment_processor_registry.initiate_payment(db, payment_context)
                logger.info(
                    f"[WizardSession] Step C result: success={payment_result.success}, "
                    f"payment_id={payment_result.payment_id}, status={payment_result.status}, "
                    f"error={payment_result.error}"
                )

                if not payment_result.success:
                    raise WizardPersistError(
                        payment_result.error or "Error al iniciar el pago.",
                        "PAYMENT_FAILED",
                        {"payment_error": payment_result.error}
                    )

            # Post-commit: delete session from cache
            session["status"] = WizardSessionStatus.PERSISTED.value
            cache_key = self._get_cache_key(session_id)
            await self.cache.delete(cache_key)

            logger.info(
                f"[WizardSession] Atomic payment complete: session={session_id}, "
                f"request_id={service_request_id}, reference={reference}, "
                f"payment_id={payment_result.payment_id}"
            )

            # Generate PDF attachment for email notification + vault registration
            pdf_attachment = await self._generate_summary_pdf_attachment(
                session, reference, workflow, appointment_data,
                db=db, user_id=user_id, service_request_id=service_request_id,
            )

            # Publish event (include user info for email notification)
            try:
                EventBus.publish_nowait(EventType.REQUEST_SUBMITTED, {
                    "request_id": str(service_request_id),
                    "user_id": str(user_id),
                    "user_email": user_email,
                    "user_phone": user_phone,
                    "user_name": user_name,
                    "workflow_code": workflow_code,
                    "reference": reference,
                    "payment_id": payment_result.payment_id,
                    "attachments": pdf_attachment,
                })
            except Exception:
                pass  # Non-blocking

            return WizardInitiatePaymentResponse(
                success=True,
                service_request_id=service_request_id,
                reference=reference,
                payment_id=payment_result.payment_id,
                payment_reference=payment_result.external_reference,
                payment_status=payment_result.status.value if hasattr(payment_result.status, "value") else str(payment_result.status),
                redirect_url=payment_result.redirect_url,
                requires_action=payment_result.requires_action,
                action_type=payment_result.action_type,
                message_es=payment_result.message_es,
                expires_at=payment_result.expires_at,
                requires_appointment=requires_appointment,
                appointment_confirmed=appointment_confirmed,
                appointment_date=appt_date_str,
                appointment_time=appt_time_str,
                appointment_location=appt_location_str,
            )

        except WizardPersistError as wpe:
            logger.error(
                f"[WizardSession] Atomic payment WizardPersistError: "
                f"code={wpe.code}, message={wpe.message}, details={wpe.details}"
            )
            await self._rollback_firebase_uploads(uploaded_files)
            session["status"] = WizardSessionStatus.READY_FOR_PAYMENT.value
            await self._save_session(session_id, session, renew_ttl=True)
            raise

        except Exception as e:
            logger.error(f"[WizardSession] Atomic payment failed: {e}", exc_info=True)
            await self._rollback_firebase_uploads(uploaded_files)
            session["status"] = WizardSessionStatus.READY_FOR_PAYMENT.value
            await self._save_session(session_id, session, renew_ttl=True)
            raise WizardPersistError(
                f"Error al procesar el pago: {str(e)}",
                "PAYMENT_PERSIST_FAILED",
                {"original_error": str(e)}
            )

    async def cancel_session(
        self,
        session_id: str,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Cancel and delete a wizard session.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            reason: Optional cancellation reason (for logging)

        Returns:
            True if cancelled successfully
        """
        logger.info(f"[WizardSession] Cancel session: {session_id}, reason={reason}")

        # Verify ownership before deleting
        session = await self._get_session(session_id, user_id)

        # Delete from cache
        cache_key = self._get_cache_key(session_id)
        success = await self.cache.delete(cache_key)

        if success:
            logger.info(f"[WizardSession] Session cancelled: {session_id}")
        else:
            logger.warning(f"[WizardSession] Failed to delete session: {session_id}")

        return success


# =============================================================================
# SINGLETON
# =============================================================================

wizard_session_service = WizardSessionService()
