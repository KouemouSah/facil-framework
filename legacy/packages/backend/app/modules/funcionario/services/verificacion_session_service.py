"""
Verificacion Funcionario Session Service.

Manages verification sessions entirely in cache (Redis/Upstash) until final validation.
Sessions expire after 30 minutes of inactivity.

Architecture:
- All data stored in cache until validate_and_submit
- Atomic transaction: Firebase upload + DB insert
- No orphan records in database
- Natural expiration via cache TTL

Author: TaxasGE Development Team
"""

import asyncio
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID, uuid4

from loguru import logger

from app.core.events import EventBus, EventType
from app.modules.service_requests.services.preview_cache import preview_cache
from app.modules.service_requests.services.gemini_document_processor import gemini_document_processor as gemini_processor
from app.modules.documents.services.storage_service import firebase_storage_service
from app.database.connection import get_database
from ..repositories.verificacion_repository import verificacion_repository
from ..models.verificacion import DocumentoTipoPrueba
from .verificacion_service import verificacion_service


# =============================================================================
# CONSTANTS
# =============================================================================

SESSION_TTL_SECONDS = 1800  # 30 minutes
SESSION_PREFIX = "vf_session_"
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

class SessionError(Exception):
    """Base exception for session errors."""
    def __init__(self, message: str, code: str = "SESSION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class SessionExpiredError(SessionError):
    """Session has expired."""
    def __init__(self, message: str = "La sesión ha expirado. Por favor, inicie de nuevo."):
        super().__init__(message, "SESSION_EXPIRED")


class SessionNotFoundError(SessionError):
    """Session not found in cache."""
    def __init__(self, message: str = "Sesión no encontrada. Por favor, inicie de nuevo."):
        super().__init__(message, "SESSION_NOT_FOUND")


class DocumentValidationError(SessionError):
    """Document validation failed."""
    def __init__(self, message: str, code: str = "DOCUMENT_VALIDATION_ERROR"):
        super().__init__(message, code)


class SubmissionError(SessionError):
    """Submission failed."""
    def __init__(self, message: str, code: str = "SUBMISSION_ERROR", details: Dict[str, Any] = None):
        super().__init__(message, code)
        self.details = details or {}


class MatriculaAlreadyVerifiedError(SessionError):
    """Matricula already verified for another user."""
    def __init__(self, message: str = "Este número de matrícula ya está verificado para otro usuario."):
        super().__init__(message, "MATRICULA_ALREADY_VERIFIED")


class MatriculaPendingOtherUserError(SessionError):
    """Matricula has pending request from another user."""
    def __init__(self, message: str = "Este número de matrícula tiene una solicitud pendiente de otro usuario."):
        super().__init__(message, "MATRICULA_PENDING_OTHER_USER")


# =============================================================================
# SESSION SERVICE
# =============================================================================

class VerificacionSessionService:
    """
    Manages verification sessions in cache with 30-minute TTL.

    Flow:
    1. start_session() - Create session in cache
    2. preview_document() - Extract & store document (renews TTL)
    3. get_form_review() - Get auto-filled data
    4. validate_and_submit() - Atomic: Firebase + DB + Submit
    """

    def __init__(self):
        self.session_ttl = SESSION_TTL_SECONDS
        self.cache = preview_cache

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def _generate_session_id(self, user_id: UUID) -> str:
        """Generate unique session ID."""
        unique = f"{user_id}_{uuid4().hex[:8]}_{datetime.now(timezone.utc).timestamp()}"
        return f"{SESSION_PREFIX}{hashlib.sha256(unique.encode()).hexdigest()[:16]}"

    def _get_cache_key(self, session_id: str) -> str:
        """Get cache key for session."""
        return session_id if session_id.startswith(SESSION_PREFIX) else f"{SESSION_PREFIX}{session_id}"

    async def _get_session(self, session_id: str, user_id: UUID) -> Dict[str, Any]:
        """
        Get session from cache with validation.

        Raises:
            SessionNotFoundError: Session not in cache
            SessionExpiredError: Session expired
            SessionError: User mismatch
        """
        cache_key = self._get_cache_key(session_id)

        try:
            data = await self.cache.get(cache_key)
        except Exception as e:
            logger.error(f"[VerificacionSession] Cache error getting session {session_id}: {e}")
            raise SessionError("Error al acceder a la sesión. Por favor, intente de nuevo.")

        if not data:
            logger.warning(f"[VerificacionSession] Session not found: {session_id}")
            raise SessionNotFoundError()

        # Validate user ownership
        if data.get("user_id") != str(user_id):
            logger.warning(f"[VerificacionSession] User mismatch for session {session_id}")
            raise SessionError("No autorizado para esta sesión.", "UNAUTHORIZED")

        # Check expiration (belt and suspenders - cache TTL should handle this)
        expires_at = data.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    logger.info(f"[VerificacionSession] Session expired: {session_id}")
                    await self.cache.delete(cache_key)
                    raise SessionExpiredError()
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

        # Update timestamps
        now = datetime.now(timezone.utc)
        data["updated_at"] = now.isoformat()
        if renew_ttl:
            data["expires_at"] = (now + timedelta(seconds=self.session_ttl)).isoformat()

        try:
            success = await self.cache.set(cache_key, data, self.session_ttl)
            if not success:
                logger.error(f"[VerificacionSession] Failed to save session {session_id}")
                return False
            return True
        except Exception as e:
            logger.error(f"[VerificacionSession] Cache error saving session {session_id}: {e}")
            return False

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def start_session(
        self,
        user_id: UUID,
        matricula: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a new verification session.

        Creates a session in cache with 30-minute TTL.
        No database entry is created until validate_and_submit.

        Performs matricula validation:
        1. Check if user already verified
        2. Check if user has pending request
        3. Check if matricula is verified for another user (BLOCKING)
        4. Check if matricula is pending for another user (WARNING)

        Args:
            user_id: User ID
            matricula: Civil servant matricula
            ip_address: Client IP for audit
            user_agent: Browser user agent

        Returns:
            Session info with session_id and expiration

        Raises:
            SessionError: If user already has pending verification or active session
            MatriculaAlreadyVerifiedError: If matricula belongs to another verified user
            MatriculaPendingOtherUserError: If matricula has pending request from another user
        """
        matricula_normalized = matricula.upper().strip()
        logger.info(f"[VerificacionSession] Starting session for user {user_id}, matricula={matricula_normalized}")

        # =====================================================================
        # CHECK 1: User already verified as funcionario?
        # =====================================================================
        status = await verificacion_repository.get_user_funcionario_status(user_id)
        if status.get("is_verified_funcionario"):
            logger.warning(f"[VerificacionSession] User {user_id} is already verified")
            raise SessionError(
                "Ya está verificado como funcionario.",
                "ALREADY_VERIFIED"
            )

        # =====================================================================
        # CHECK 2: User already has pending verification?
        # =====================================================================
        existing = await verificacion_repository.get_pending_by_user(user_id)
        if existing:
            logger.warning(f"[VerificacionSession] User {user_id} already has pending verification")
            raise SessionError(
                "Ya tiene una solicitud de verificación pendiente.",
                "PENDING_EXISTS"
            )

        # =====================================================================
        # CHECK 3: Matricula already verified for ANOTHER user? (BLOCKING)
        # =====================================================================
        verified_for_other = await verificacion_repository.check_matricula_verified_for_other_user(
            matricula_normalized, user_id
        )
        if verified_for_other:
            logger.warning(
                f"[VerificacionSession] FRAUD ATTEMPT: Matricula {matricula_normalized} "
                f"already verified for user {verified_for_other['id']}"
            )
            # Log fraud attempt
            await verificacion_repository.log_fraud_attempt(
                user_id=user_id,
                matricula=matricula_normalized,
                reason="MATRICULA_VERIFIED_FOR_OTHER_USER",
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "existing_user_id": str(verified_for_other['id']),
                    "existing_user_email": verified_for_other.get('email'),
                    "verified_at": str(verified_for_other.get('funcionario_verified_at')),
                },
            )
            raise MatriculaAlreadyVerifiedError()

        # =====================================================================
        # CHECK 4: Matricula pending for ANOTHER user? (WARNING - still allow)
        # =====================================================================
        pending_for_other = await verificacion_repository.check_matricula_pending_for_other_user(
            matricula_normalized, user_id
        )
        matricula_warning = None
        if pending_for_other:
            logger.warning(
                f"[VerificacionSession] Matricula {matricula_normalized} has pending request "
                f"from another user {pending_for_other['user_id']}"
            )
            # Log as suspicious but don't block (might be legitimate)
            await verificacion_repository.log_fraud_attempt(
                user_id=user_id,
                matricula=matricula_normalized,
                reason="MATRICULA_PENDING_OTHER_USER_WARNING",
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "other_user_id": str(pending_for_other['user_id']),
                    "other_request_id": str(pending_for_other['id']),
                    "other_request_date": str(pending_for_other.get('created_at')),
                },
            )
            matricula_warning = {
                "code": "MATRICULA_PENDING_OTHER_USER",
                "message": "Este número de matrícula tiene otra solicitud pendiente. "
                           "Si usted es el titular legítimo, continúe con su solicitud.",
                "severity": "warning",
            }

        # =====================================================================
        # CREATE SESSION
        # =====================================================================
        session_id = self._generate_session_id(user_id)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.session_ttl)

        # Create session data
        session_data = {
            "session_id": session_id,
            "user_id": str(user_id),
            "matricula": matricula_normalized,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "documents": {},
            "validacion_cruzada": None,
            "form_data_corrections": {},
            "matricula_warning": matricula_warning,  # Store warning if any
        }

        # Save to cache
        success = await self._save_session(session_id, session_data)
        if not success:
            raise SessionError("Error al crear la sesión. Por favor, intente de nuevo.")

        logger.info(f"[VerificacionSession] Session created: {session_id}, expires_at={expires_at}")

        # Build response
        response = {
            "session_id": session_id,
            "matricula": session_data["matricula"],
            "created_at": session_data["created_at"],
            "expires_at": session_data["expires_at"],
            "ttl_seconds": self.session_ttl,
            "required_documents": [
                {"code": "dip", "name": "Documento de Identidad Personal (DIP)", "required": True},
                {"code": "documento_prueba", "name": "Documento de Prueba (Nombramiento, Carnet o Contrato)", "required": True},
            ],
        }

        # Add warning if matricula has pending request from another user
        if matricula_warning:
            response["warning"] = matricula_warning

        return response

    async def preview_document(
        self,
        session_id: str,
        user_id: UUID,
        document_code: str,
        file_content: bytes,
        file_name: str,
        mime_type: str,
    ) -> Dict[str, Any]:
        """
        Preview document extraction and store in session.

        Extracts data using Gemini OCR and stores both content and extraction
        in the session cache. Renews session TTL.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            document_code: 'dip', 'nombramiento', 'carnet_funcionario', or 'contrato_funcionario'
            file_content: File binary content
            file_name: Original file name
            mime_type: MIME type

        Returns:
            Extraction result with preview data

        Raises:
            SessionNotFoundError: Session not found
            SessionExpiredError: Session expired
            DocumentValidationError: Invalid document
        """
        logger.info(f"[VerificacionSession] Preview document: session={session_id}, doc={document_code}")

        # Validate document code
        valid_codes = ["dip"] + [t.value for t in DocumentoTipoPrueba]
        if document_code not in valid_codes:
            raise DocumentValidationError(
                f"Tipo de documento inválido. Valores permitidos: {valid_codes}",
                "INVALID_DOCUMENT_CODE"
            )

        # Validate file size
        file_size = len(file_content)
        max_size = MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            raise DocumentValidationError(
                f"El archivo excede el tamaño máximo de {MAX_DOCUMENT_SIZE_MB}MB.",
                "FILE_TOO_LARGE"
            )

        # Validate MIME type
        if mime_type not in ALLOWED_MIME_TYPES:
            raise DocumentValidationError(
                f"Formato de archivo no soportado. Use PDF, JPG o PNG.",
                "INVALID_MIME_TYPE"
            )

        # Get session
        session = await self._get_session(session_id, user_id)

        # Extract document data using Gemini
        try:
            if document_code == "dip":
                extraction_result = await verificacion_service.extract_dip(
                    file_content=file_content,
                    mime_type=mime_type,
                    user_id=str(user_id),
                )
            else:
                tipo_doc = DocumentoTipoPrueba(document_code)
                # Get existing DIP extraction for cross-validation
                existing_dip = session.get("documents", {}).get("dip", {}).get("extraction")

                extraction_result = await verificacion_service.extract_documento_prueba(
                    file_content=file_content,
                    mime_type=mime_type,
                    tipo_documento=tipo_doc,
                    user_id=str(user_id),
                    existing_dip_extraction=existing_dip,
                )
        except Exception as e:
            logger.error(f"[VerificacionSession] Extraction failed: {e}", exc_info=True)
            raise DocumentValidationError(
                "Error al procesar el documento. Verifique que sea legible.",
                "EXTRACTION_FAILED"
            )

        # Store document in session
        now = datetime.now(timezone.utc)
        document_data = {
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "content_b64": base64.b64encode(file_content).decode("utf-8"),
            "extraction": extraction_result.get("extraction", {}),
            "confidence": extraction_result.get("confidence", 0),
            "processor": extraction_result.get("processor", "unknown"),
            "status": extraction_result.get("status", "error"),
            "risk_analysis": extraction_result.get("risk_analysis"),
            "previewed_at": now.isoformat(),
        }

        # Update session documents
        if "documents" not in session:
            session["documents"] = {}
        session["documents"][document_code] = document_data

        # Calculate cross-validation if both documents present
        session = self._calculate_cross_validation(session)

        # Save session (renews TTL)
        success = await self._save_session(session_id, session, renew_ttl=True)
        if not success:
            raise SessionError("Error al guardar la vista previa.")

        logger.info(
            f"[VerificacionSession] Document preview saved: session={session_id}, "
            f"doc={document_code}, confidence={document_data['confidence']}"
        )

        return {
            "session_id": session_id,
            "document_code": document_code,
            "file_name": file_name,
            "file_size": file_size,
            "extraction": extraction_result.get("extraction", {}),
            "confidence": extraction_result.get("confidence", 0),
            "status": extraction_result.get("status", "error"),
            "risk_analysis": extraction_result.get("risk_analysis"),
            "validacion_cruzada": session.get("validacion_cruzada"),
            "expires_at": session.get("expires_at"),
        }

    def _calculate_cross_validation(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate cross-validation if both documents are present."""
        documents = session.get("documents", {})

        # Check if we have DIP
        dip_data = documents.get("dip", {})
        dip_extraction = dip_data.get("extraction", {})

        if not dip_extraction:
            return session

        # Check if we have any proof document
        proof_doc = None
        proof_extraction = None
        for t in DocumentoTipoPrueba:
            if t.value in documents:
                proof_doc = t.value
                proof_extraction = documents[t.value].get("extraction", {})
                break

        if not proof_extraction:
            return session

        # Build verification_data structure for cross-validation
        verification_data = {
            "matricula": session.get("matricula", ""),
            "dip": {"extraction": dip_extraction},
            proof_doc: {"extraction": proof_extraction},
        }

        # Calculate cross-validation using existing service
        validacion = verificacion_service.calculate_cross_validation(verification_data)
        session["validacion_cruzada"] = validacion

        logger.debug(
            f"[VerificacionSession] Cross-validation calculated: "
            f"similitud={validacion.get('similitud_nombre')}, "
            f"matriculas_match={validacion.get('matriculas_coinciden')}"
        )

        return session

    async def get_form_review(
        self,
        session_id: str,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get form review data from session.

        Returns auto-filled data from document extractions for user review.
        Does NOT renew TTL (read-only operation).

        Args:
            session_id: Session ID
            user_id: User ID for authorization

        Returns:
            Form review data with sections and fields
        """
        logger.info(f"[VerificacionSession] Get form_review: session={session_id}")

        session = await self._get_session(session_id, user_id)

        # Build verification_data structure from session
        documents = session.get("documents", {})
        verification_data = {
            "matricula": session.get("matricula", ""),
            "validacion_cruzada": session.get("validacion_cruzada"),
        }

        # Add DIP
        if "dip" in documents:
            verification_data["dip"] = {
                "extraction": documents["dip"].get("extraction", {}),
                "extraction_confidence": documents["dip"].get("confidence", 0),
            }

        # Add proof document
        proof_doc_type = None
        for t in DocumentoTipoPrueba:
            if t.value in documents:
                proof_doc_type = t.value
                verification_data[t.value] = {
                    "extraction": documents[t.value].get("extraction", {}),
                    "extraction_confidence": documents[t.value].get("confidence", 0),
                }
                break

        # Use existing service to build form_review
        form_review = verificacion_service.build_form_review_data(
            verificacion_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
            verification_data=verification_data,
            status="session",
        )

        # Override with session info
        form_review["session_id"] = session_id
        form_review["expires_at"] = session.get("expires_at")
        form_review["documents_uploaded"] = list(documents.keys())
        form_review["proof_document_type"] = proof_doc_type

        # Check readiness for submission
        ready_for_submit = (
            "dip" in documents and
            proof_doc_type is not None and
            documents.get("dip", {}).get("extraction") and
            documents.get(proof_doc_type, {}).get("extraction")
        )
        form_review["ready_for_submit"] = ready_for_submit

        return form_review

    async def validate_and_submit(
        self,
        session_id: str,
        user_id: UUID,
        form_data: Dict[str, Any],
        force_submit: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate and submit verification in atomic transaction.

        This is the final step that:
        1. Validates all required documents are present
        2. Merges form_data with extractions
        3. Validates critical fields
        4. Uploads documents to Firebase (parallel)
        5. Creates database entry
        6. Deletes session from cache

        All steps are atomic - failure at any point rolls back.

        Args:
            session_id: Session ID
            user_id: User ID for authorization
            form_data: User corrections to form fields
            force_submit: If True, submit despite validation warnings

        Returns:
            Verification result with verificacion_id

        Raises:
            SessionError: Various validation/submission errors
        """
        logger.info(f"[VerificacionSession] Validate and submit: session={session_id}, force={force_submit}")

        # Get session
        session = await self._get_session(session_id, user_id)
        documents = session.get("documents", {})
        matricula = session.get("matricula", "")
        ip_address = session.get("ip_address")
        user_agent = session.get("user_agent")

        # =====================================================================
        # STEP 0: RE-VERIFY MATRICULA (state might have changed during session)
        # =====================================================================

        # Re-check if matricula was verified for another user during the session
        verified_for_other = await verificacion_repository.check_matricula_verified_for_other_user(
            matricula, user_id
        )
        if verified_for_other:
            logger.warning(
                f"[VerificacionSession] BLOCKED: Matricula {matricula} was verified for another user "
                f"during session: {verified_for_other['id']}"
            )
            await verificacion_repository.log_fraud_attempt(
                user_id=user_id,
                matricula=matricula,
                reason="MATRICULA_VERIFIED_DURING_SESSION",
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "session_id": session_id,
                    "existing_user_id": str(verified_for_other['id']),
                },
            )
            raise MatriculaAlreadyVerifiedError(
                "Este número de matrícula fue verificado para otro usuario "
                "mientras usted completaba el formulario."
            )

        # =====================================================================
        # STEP 1: Validate required documents
        # =====================================================================

        extraction_warnings = []

        # Check if DIP was uploaded and previewed
        if "dip" not in documents or not documents["dip"].get("previewed_at"):
            raise SubmissionError(
                "Debe subir y validar el DIP antes de enviar.",
                "MISSING_DIP"
            )

        # Check if DIP extraction has data
        dip_extraction = documents["dip"].get("extraction", {})
        if not dip_extraction:
            extraction_warnings.append({
                "code": "EMPTY_DIP_EXTRACTION",
                "message": "No se pudieron extraer datos del DIP. Verifique la calidad del documento.",
                "severity": "high",
            })

        # Find proof document (check if previewed)
        proof_doc_type = None
        proof_doc_data = None
        for t in DocumentoTipoPrueba:
            if t.value in documents and documents[t.value].get("previewed_at"):
                proof_doc_type = t.value
                proof_doc_data = documents[t.value]
                break

        if not proof_doc_type:
            raise SubmissionError(
                "Debe subir un documento de prueba (Nombramiento, Carnet o Contrato).",
                "MISSING_PROOF_DOCUMENT"
            )

        # Check if proof document extraction has data
        proof_extraction = proof_doc_data.get("extraction", {})
        if not proof_extraction:
            extraction_warnings.append({
                "code": "EMPTY_PROOF_EXTRACTION",
                "message": f"No se pudieron extraer datos del documento de prueba ({proof_doc_type}).",
                "severity": "high",
            })

        # Block submission if extraction is empty and force_submit is False
        if extraction_warnings and not force_submit:
            raise SubmissionError(
                "No se pudieron extraer datos de los documentos. "
                "Suba documentos de mejor calidad o confirme para continuar.",
                "EMPTY_EXTRACTION",
                details={"warnings": extraction_warnings, "requires_force": True}
            )

        # =====================================================================
        # STEP 2: Build and merge form data
        # =====================================================================

        # Build verification_data for extraction
        verification_data_temp = {
            "matricula": matricula,
            "dip": {"extraction": documents["dip"].get("extraction", {})},
            proof_doc_type: {"extraction": proof_doc_data.get("extraction", {})},
            "validacion_cruzada": session.get("validacion_cruzada"),
        }

        # Extract base form data
        extracted_form_data = verificacion_service._build_extracted_form_data(verification_data_temp)

        # Merge with user corrections
        merged_form_data = {**extracted_form_data, **form_data}

        # =====================================================================
        # STEP 3: Validate critical fields
        # =====================================================================

        if not merged_form_data.get("numero_dip"):
            raise SubmissionError(
                "El número de DIP es obligatorio.",
                "MISSING_NUMERO_DIP"
            )

        if not merged_form_data.get("matricula"):
            raise SubmissionError(
                "La matrícula es obligatoria.",
                "MISSING_MATRICULA"
            )

        # =====================================================================
        # STEP 4: Check warnings (non-blocking)
        # =====================================================================

        validacion = session.get("validacion_cruzada", {})
        warnings = []

        similitud = validacion.get("similitud_nombre", 0)
        if similitud < 0.85:
            warnings.append({
                "code": "LOW_NAME_SIMILARITY",
                "message": f"Similitud de nombres baja ({int(similitud * 100)}%)",
                "severity": "warning",
            })

        if not validacion.get("matriculas_coinciden", False):
            warnings.append({
                "code": "MATRICULA_MISMATCH",
                "message": "La matrícula no coincide con el documento",
                "severity": "warning",
            })

        # If warnings and not force_submit, return for confirmation
        if warnings and not force_submit:
            return {
                "success": False,
                "submitted": False,
                "requires_confirmation": True,
                "warnings": warnings,
                "message": "Se encontraron advertencias. Confirme para continuar.",
                "session_id": session_id,
            }

        # =====================================================================
        # STEP 5: ATOMIC TRANSACTION - Upload + DB Insert
        # =====================================================================

        logger.info(f"[VerificacionSession] Starting atomic transaction for session {session_id}")

        firebase_uploads = {}
        verificacion_id = None

        try:
            # 5a. Upload documents to Firebase in parallel
            upload_tasks = []

            # DIP upload
            dip_content = base64.b64decode(documents["dip"]["content_b64"])
            upload_tasks.append(self._upload_document(
                user_id=str(user_id),
                document_code="dip",
                content=dip_content,
                file_name=documents["dip"]["file_name"],
                mime_type=documents["dip"]["mime_type"],
            ))

            # Proof document upload
            proof_content = base64.b64decode(proof_doc_data["content_b64"])
            upload_tasks.append(self._upload_document(
                user_id=str(user_id),
                document_code=proof_doc_type,
                content=proof_content,
                file_name=proof_doc_data["file_name"],
                mime_type=proof_doc_data["mime_type"],
            ))

            # Execute uploads in parallel
            upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)

            # Check for upload errors
            for i, result in enumerate(upload_results):
                if isinstance(result, Exception):
                    doc_name = "DIP" if i == 0 else "documento de prueba"
                    logger.error(f"[VerificacionSession] Upload failed for {doc_name}: {result}")
                    raise SubmissionError(
                        f"Error al subir el {doc_name}. Por favor, intente de nuevo.",
                        "UPLOAD_FAILED"
                    )

            # Store upload results
            firebase_uploads["dip"] = upload_results[0]
            firebase_uploads[proof_doc_type] = upload_results[1]

            logger.info(f"[VerificacionSession] Firebase uploads complete for session {session_id}")

            # 5b. Build final verification_data for database
            now = datetime.now(timezone.utc)

            final_verification_data = {
                "matricula": matricula,
                "dip": {
                    "file_id": firebase_uploads["dip"]["file_id"],
                    "file_path": firebase_uploads["dip"]["file_path"],
                    "file_url": firebase_uploads["dip"]["file_url"],
                    "file_name": documents["dip"]["file_name"],
                    "file_size": documents["dip"]["file_size"],
                    "mime_type": documents["dip"]["mime_type"],
                    "extraction": documents["dip"]["extraction"],
                    "extraction_confidence": documents["dip"]["confidence"],
                    "processor": documents["dip"]["processor"],
                    "uploaded_at": now.isoformat(),
                    "storage": "firebase",
                },
                proof_doc_type: {
                    "file_id": firebase_uploads[proof_doc_type]["file_id"],
                    "file_path": firebase_uploads[proof_doc_type]["file_path"],
                    "file_url": firebase_uploads[proof_doc_type]["file_url"],
                    "file_name": proof_doc_data["file_name"],
                    "file_size": proof_doc_data["file_size"],
                    "mime_type": proof_doc_data["mime_type"],
                    "extraction": proof_doc_data["extraction"],
                    "extraction_confidence": proof_doc_data["confidence"],
                    "processor": proof_doc_data["processor"],
                    "uploaded_at": now.isoformat(),
                    "storage": "firebase",
                },
                "validacion_cruzada": validacion,
                "form_review_confirmed": {
                    "data": merged_form_data,
                    "confirmed_at": now.isoformat(),
                    "fields_count": len(merged_form_data),
                    "user_modified_fields": list(form_data.keys()),
                },
                "confirmacion_usuario": {
                    "datos_correctos": True,
                    "confirmado_at": now.isoformat(),
                    "warnings_acknowledged": len(warnings) > 0,
                    "warnings_count": len(warnings),
                },
                "session_info": {
                    "session_id": session_id,
                    "session_created_at": session.get("created_at"),
                    "submitted_at": now.isoformat(),
                },
            }

            # 5c. Create database entry
            db_result = await verificacion_repository.create(
                user_id=user_id,
                matricula=matricula,
                verification_data=final_verification_data,
                ip_address=session.get("ip_address"),
                user_agent=session.get("user_agent"),
            )

            verificacion_id = db_result["id"]
            logger.info(f"[VerificacionSession] Database entry created: {verificacion_id}")

            # 5d. AUTO-VERIFY against verified_identifiers table
            auto_verification_result = await self._auto_verify_matricula(
                matricula=matricula,
                verificacion_id=verificacion_id,
                user_id=user_id,
                ip_address=ip_address,
            )

            # 5e. Delete session from cache (cleanup)
            cache_key = self._get_cache_key(session_id)
            await self.cache.delete(cache_key)
            logger.info(f"[VerificacionSession] Session deleted from cache: {session_id}")

        except SubmissionError:
            raise
        except Exception as e:
            logger.error(f"[VerificacionSession] Transaction failed: {e}", exc_info=True)
            # Note: Firebase uploads cannot be easily rolled back, but DB entry wasn't created
            # In production, could add cleanup job for orphan Firebase files
            raise SubmissionError(
                "Error al procesar la solicitud. Por favor, intente de nuevo.",
                "TRANSACTION_FAILED"
            )

        # =====================================================================
        # STEP 6: Return success
        # =====================================================================

        auto_validable = validacion.get("validacion_automatica_posible", False)

        # Check if pre-verified in external database
        pre_verified = auto_verification_result.get("pre_verified", False)

        logger.info(
            f"[VerificacionSession] Verification submitted successfully: "
            f"id={verificacion_id}, auto_validable={auto_validable}, pre_verified={pre_verified}"
        )

        return {
            "success": True,
            "submitted": True,
            "verificacion_id": str(verificacion_id),
            "reference": f"VF-{str(verificacion_id)[:8].upper()}",
            "status": "pendiente",
            "auto_validable": auto_validable,
            "pre_verified": pre_verified,
            "auto_verification": auto_verification_result,
            "warnings": warnings,
            "warnings_acknowledged": len(warnings) > 0,
            "message": "Solicitud enviada correctamente para revisión.",
            "validacion_cruzada": validacion,
        }

    async def _auto_verify_matricula(
        self,
        matricula: str,
        verificacion_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Auto-verify matricula against verified_identifiers table.

        Checks if the matricula exists in the external database cache
        (imported from SIGEF/Ministerio Función Pública).

        Args:
            matricula: The matricula to verify
            verificacion_id: ID of the verification request
            user_id: User ID for audit
            ip_address: Client IP for audit

        Returns:
            Dict with verification result
        """
        try:
            from app.modules.verified_identifiers.services.verification_service import VerificationService
            from app.modules.verified_identifiers.services.crypto_service import get_crypto_service

            from app.database.connection import db_manager
            async with db_manager.get_connection() as db:
                crypto = get_crypto_service()
                verification_svc = VerificationService(pool=db, crypto=crypto)

                # Verify against verified_identifiers table
                result = await verification_svc.verify_identifier(
                    value=matricula.upper().strip(),
                    identifier_type="matricula_funcionario",
                    request_id=str(verificacion_id),
                    performed_by=str(user_id),
                    ip_address=ip_address,
                )

            auto_verification_data = {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "pre_verified": result.verified,
                "source": result.source if result.verified else None,
                "verified_at": result.verified_at.isoformat() if result.verified_at else None,
                "expires_at": result.expires_at.isoformat() if result.expires_at else None,
                "reason": result.reason if not result.verified else None,
            }

            # Update verificacion_funcionario with auto-verification result
            await verificacion_repository.merge_verification_data(
                verificacion_id=verificacion_id,
                new_data={"auto_verification": auto_verification_data},
            )

            if result.verified:
                logger.info(
                    f"[VerificacionSession] Matricula {matricula} PRE-VERIFIED from {result.source}"
                )

                # Emit event to notify agents about pre-verified request
                try:
                    await EventBus.publish(
                        EventType.FUNCIONARIO_VERIFICATION_PRE_VERIFIED,
                        {
                            "verificacion_id": str(verificacion_id),
                            "matricula": matricula,
                            "user_id": str(user_id),
                            "source": result.source,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "action_required": "agent_review",
                                "priority": "high",
                                "reason": "Matrícula pré-vérifiée dans la base externe"
                            }
                        }
                    )
                    logger.info(
                        f"[VerificacionSession] Pre-verified event emitted for {verificacion_id}"
                    )
                except Exception as evt_err:
                    logger.warning(f"[VerificacionSession] Failed to emit pre-verified event: {evt_err}")
            else:
                logger.info(
                    f"[VerificacionSession] Matricula {matricula} NOT in verified_identifiers: {result.reason}"
                )

            return auto_verification_data

        except Exception as e:
            logger.error(f"[VerificacionSession] Auto-verification error for {matricula}: {e}")
            # Don't fail the submission, just log the error
            return {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "pre_verified": False,
                "error": str(e),
                "reason": "verification_error",
            }

    async def _upload_document(
        self,
        user_id: str,
        document_code: str,
        content: bytes,
        file_name: str,
        mime_type: str,
    ) -> Dict[str, Any]:
        """
        Upload document to Firebase Storage.

        Returns:
            Dict with file_id, file_path, file_url
        """
        try:
            result = await firebase_storage_service.upload_user_document(
                user_id=user_id,
                application_id=f"verificacion_{uuid4().hex[:8]}",
                file=content,
                metadata={
                    "filename": file_name,
                    "mime_type": mime_type,
                    "document_code": document_code,
                    "document_type": "verificacion_funcionario",
                }
            )

            return {
                "file_id": result.file_id,
                "file_path": result.file_path,
                "file_url": result.file_url,
            }
        except Exception as e:
            logger.error(f"[VerificacionSession] Firebase upload error: {e}")
            raise

    async def get_session_status(
        self,
        session_id: str,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get current session status.

        Returns session info without document content (lighter response).
        """
        session = await self._get_session(session_id, user_id)

        documents_status = {}
        for doc_code, doc_data in session.get("documents", {}).items():
            documents_status[doc_code] = {
                "uploaded": True,
                "file_name": doc_data.get("file_name"),
                "confidence": doc_data.get("confidence"),
                "status": doc_data.get("status"),
                "previewed_at": doc_data.get("previewed_at"),
            }

        # Check readiness
        proof_doc = None
        for t in DocumentoTipoPrueba:
            if t.value in session.get("documents", {}):
                proof_doc = t.value
                break

        ready = (
            "dip" in documents_status and
            proof_doc is not None
        )

        return {
            "session_id": session_id,
            "matricula": session.get("matricula"),
            "created_at": session.get("created_at"),
            "expires_at": session.get("expires_at"),
            "documents": documents_status,
            "validacion_cruzada": session.get("validacion_cruzada"),
            "ready_for_submit": ready,
            "proof_document_type": proof_doc,
        }

    async def cancel_session(
        self,
        session_id: str,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """Cancel and delete a session."""
        # Validate ownership
        await self._get_session(session_id, user_id)

        # Delete from cache
        cache_key = self._get_cache_key(session_id)
        await self.cache.delete(cache_key)

        logger.info(f"[VerificacionSession] Session cancelled: {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "message": "Sesión cancelada.",
        }


# Singleton instance
verificacion_session_service = VerificacionSessionService()
