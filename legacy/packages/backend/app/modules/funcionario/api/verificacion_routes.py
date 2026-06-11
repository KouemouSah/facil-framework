"""
API routes for Funcionario Verification.

SESSION-BASED FLOW (Recommended - v2):
All data stored in cache until final validation. Sessions expire after 30 minutes.
- POST /verificacion-funcionario/session/start - Start new session (cache only)
- POST /verificacion-funcionario/session/{id}/preview - Preview document
- GET /verificacion-funcionario/session/{id}/form-review - Get auto-filled data
- GET /verificacion-funcionario/session/{id}/status - Get session status
- POST /verificacion-funcionario/session/{id}/validate-and-submit - Atomic validation + submission
- DELETE /verificacion-funcionario/session/{id} - Cancel session

LEGACY ENDPOINTS (Deprecated - v1):
Will be removed in future version. Use session-based flow instead.
- POST /verificacion-funcionario - Create verification (DB immediately)
- POST /verificacion-funcionario/{id}/documents/preview - Preview
- POST /verificacion-funcionario/{id}/documents/validate - Validate
- POST /verificacion-funcionario/{id}/submit - Submit

COMMON ENDPOINTS:
- GET /verificacion-funcionario/my-status - Get my verification status
- GET /verificacion-funcionario/document-requirements - Get required documents
- GET /verificacion-funcionario/proof-options - Get proof document types
- GET /verificacion-funcionario/form-review-config - Get form_review configuration

AGENT ENDPOINTS:
- GET /verificacion-funcionario/pending - List pending (agents only)
- GET /verificacion-funcionario/{id} - Get verification detail (agents only)
- POST /verificacion-funcionario/{id}/process - Approve/Reject (agents only)
- POST /verificacion-funcionario/batch-approve - Batch approve (agents only)
"""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Request
from loguru import logger
from app.core.errors import TranslatedException, ErrorCode

from app.modules.auth.dependencies import get_current_user, require_permissions
from ..models.verificacion import (
    VerificacionCreate,
    VerificacionResponse,
    VerificacionDetailResponse,
    VerificacionListResponse,
    VerificacionProcessRequest,
    BatchApproveRequest,
    BatchApproveResponse,
    MyVerificationStatusResponse,
    MyVerificationResponse,
    DocumentExtraction,
    ValidacionCruzada,
    DocumentoTipoPrueba,
)
from ..services.verificacion_service import verificacion_service
from ..services.verificacion_session_service import (
    verificacion_session_service,
    SessionError,
    SessionExpiredError,
    SessionNotFoundError,
    DocumentValidationError,
    SubmissionError,
    MatriculaAlreadyVerifiedError,
    MatriculaPendingOtherUserError,
)
from ..repositories.verificacion_repository import verificacion_repository

# Import preview cache for document preview flow (supports Redis/Upstash or in-memory)
from app.modules.service_requests.services.preview_cache import preview_cache

# Import Firebase Storage service for document upload
from app.modules.documents.services.storage_service import firebase_storage_service

# Preview cache TTL (30 minutes)
PREVIEW_CACHE_TTL_SECONDS = 1800

router = APIRouter(prefix="/verificacion-funcionario", tags=["Verificacion Funcionario"])


# =============================================================================
# SESSION-BASED FLOW (v2) - Recommended
# All data in cache until final validation. 30-minute expiration.
# =============================================================================

@router.post("/session/start", status_code=status.HTTP_201_CREATED)
async def start_session(
    matricula: str = Form(..., min_length=4, max_length=50, description="Matrícula del funcionario"),
    request: Request = None,
    current_user=Depends(get_current_user),
):
    """
    Start a new verification session.

    Creates a session in cache with 30-minute TTL.
    No database entry until validate-and-submit.

    **Flow:**
    1. POST /session/start → Get session_id
    2. POST /session/{id}/preview (×2) → Upload documents
    3. GET /session/{id}/form-review → Review data
    4. POST /session/{id}/validate-and-submit → Final submission

    **Returns:**
    - session_id: Unique session identifier
    - expires_at: Session expiration timestamp
    - ttl_seconds: Time to live (1800 = 30 minutes)
    - required_documents: List of documents to upload
    """
    logger.info(f"[Session] Starting session for user {current_user.id}, matricula={matricula}")

    try:
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None

        result = await verificacion_session_service.start_session(
            user_id=current_user.id,
            matricula=matricula,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(f"[Session] Session created: {result['session_id']}")
        return result

    except MatriculaAlreadyVerifiedError as e:
        # Matricula already verified for another user - this is a security issue
        logger.warning(f"[Session] Matricula fraud attempt: {e.code} - {e.message}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )
    except MatriculaPendingOtherUserError as e:
        # Matricula has pending request from another user - warning only
        logger.warning(f"[Session] Matricula pending for other user: {e.code} - {e.message}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )
    except SessionError as e:
        logger.warning(f"[Session] Start session error: {e.code} - {e.message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": e.code,
            "message": e.message,
        })
    except Exception as e:
        logger.error(f"[Session] Unexpected error starting session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear la sesión."
        )


@router.post("/session/{session_id}/preview")
async def preview_document_session(
    session_id: str,
    document_code: str = Form(..., description="Document type: dip, nombramiento, carnet_funcionario, contrato_funcionario"),
    file: UploadFile = File(..., description="Document file (PDF, JPG, PNG)"),
    current_user=Depends(get_current_user),
):
    """
    Preview document extraction in session.

    Extracts data using OCR and stores in session cache.
    Renews session TTL to 30 minutes.

    **Document codes:**
    - `dip` - Documento de Identidad Personal (required)
    - `nombramiento` - Nombramiento oficial
    - `carnet_funcionario` - Carnet de funcionario
    - `contrato_funcionario` - Contrato de funcionario

    **Note:** Provide DIP + ONE of the proof documents.
    """
    logger.info(f"[Session] Preview document: session={session_id}, doc={document_code}")

    try:
        # Read file content
        content = await file.read()
        if not content:
            raise DocumentValidationError("El archivo está vacío.", "EMPTY_FILE")

        result = await verificacion_session_service.preview_document(
            session_id=session_id,
            user_id=current_user.id,
            document_code=document_code,
            file_content=content,
            file_name=file.filename or "document",
            mime_type=file.content_type or "application/octet-stream",
        )

        logger.info(f"[Session] Preview complete: session={session_id}, confidence={result.get('confidence')}")
        return result

    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail={
            "code": e.code,
            "message": e.message,
        })
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "code": e.code,
            "message": e.message,
        })
    except DocumentValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": e.code,
            "message": e.message,
        })
    except SessionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": e.code,
            "message": e.message,
        })
    except Exception as e:
        logger.error(f"[Session] Preview error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar el documento."
        )


@router.get("/session/{session_id}/form-review")
async def get_form_review_session(
    session_id: str,
    current_user=Depends(get_current_user),
):
    """
    Get form review data from session.

    Returns auto-filled data from document extractions.
    Use this to display the review form before final submission.

    **Response includes:**
    - sections: Form sections with auto-filled fields
    - validacion_cruzada: Cross-validation results
    - ready_for_submit: Whether all required documents are present
    """
    logger.info(f"[Session] Get form_review: session={session_id}")

    try:
        result = await verificacion_session_service.get_form_review(
            session_id=session_id,
            user_id=current_user.id,
        )
        return result

    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail={
            "code": e.code,
            "message": e.message,
        })
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "code": e.code,
            "message": e.message,
        })
    except SessionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": e.code,
            "message": e.message,
        })
    except Exception as e:
        logger.error(f"[Session] Form review error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener datos del formulario."
        )


@router.get("/session/{session_id}/status")
async def get_session_status(
    session_id: str,
    current_user=Depends(get_current_user),
):
    """
    Get current session status.

    Lightweight endpoint to check:
    - Documents uploaded
    - Cross-validation status
    - Ready for submission
    - Time remaining
    """
    logger.info(f"[Session] Get status: session={session_id}")

    try:
        result = await verificacion_session_service.get_session_status(
            session_id=session_id,
            user_id=current_user.id,
        )
        return result

    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail={
            "code": e.code,
            "message": e.message,
        })
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "code": e.code,
            "message": e.message,
        })
    except SessionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": e.code,
            "message": e.message,
        })


@router.post("/session/{session_id}/validate-and-submit")
async def validate_and_submit_session(
    session_id: str,
    form_data: dict = {},
    force_submit: bool = False,
    current_user=Depends(get_current_user),
):
    """
    Validate and submit verification in atomic transaction.

    **ATOMIC OPERATION:**
    1. Validates all documents present
    2. Merges form_data with extractions
    3. Uploads documents to Firebase (parallel)
    4. Creates database entry
    5. Deletes session from cache

    If any step fails, nothing is persisted.

    **Request body:**
    ```json
    {
        "form_data": {"apellidos": "CORREGIDO", ...},
        "force_submit": false
    }
    ```

    **form_data:** User corrections (optional, merged with extracted data)
    **force_submit:** If true, submit despite validation warnings

    **Returns on success:**
    - verificacion_id: Database ID
    - reference: Human-readable reference (VF-XXXXXXXX)
    - status: "pendiente"
    - auto_validable: Whether agent can auto-approve

    **Returns if warnings:**
    - requires_confirmation: true
    - warnings: List of warnings
    - Call again with force_submit=true to proceed
    """
    logger.info(f"[Session] Validate and submit: session={session_id}, force={force_submit}")

    try:
        result = await verificacion_session_service.validate_and_submit(
            session_id=session_id,
            user_id=current_user.id,
            form_data=form_data,
            force_submit=force_submit,
        )

        if result.get("submitted"):
            logger.info(f"[Session] Submitted successfully: {result.get('verificacion_id')}")
        else:
            logger.info(f"[Session] Requires confirmation: {len(result.get('warnings', []))} warnings")

        return result

    except MatriculaAlreadyVerifiedError as e:
        # Matricula was verified for another user during the session
        logger.warning(f"[Session] Matricula verified during session: {e.code}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )
    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail={
            "code": e.code,
            "message": e.message,
        })
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "code": e.code,
            "message": e.message,
        })
    except SubmissionError as e:
        detail = {
            "code": e.code,
            "message": e.message,
        }
        if e.details:
            detail.update(e.details)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except SessionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": e.code,
            "message": e.message,
        })
    except Exception as e:
        logger.error(f"[Session] Submit error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al enviar la solicitud."
        )


@router.delete("/session/{session_id}")
async def cancel_session(
    session_id: str,
    current_user=Depends(get_current_user),
):
    """
    Cancel and delete a session.

    Use this if user wants to start over or abandon the process.
    """
    logger.info(f"[Session] Cancel: session={session_id}")

    try:
        result = await verificacion_session_service.cancel_session(
            session_id=session_id,
            user_id=current_user.id,
        )
        return result

    except SessionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": e.code,
            "message": e.message,
        })
    except Exception as e:
        logger.error(f"[Session] Cancel error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al cancelar la sesión."
        )


# =============================================================================
# LEGACY USER ENDPOINTS (v1) - DEPRECATED
# Use session-based flow instead
# =============================================================================

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, deprecated=True)
async def create_verificacion(
    data: VerificacionCreate,
    request: Request,
    current_user=Depends(get_current_user),
):
    """
    Create a new verification request.

    User must provide their matricula. Documents are uploaded separately.
    """
    try:
        logger.info(f"[Verificacion] Creating verification for user {current_user.id}, matricula: {data.matricula}")

        # Get client info for audit
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = await verificacion_service.create_verification(
            user_id=current_user.id,
            matricula=data.matricula,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(f"[Verificacion] Created verification {result['id']} for user {current_user.id}")

        return {
            "id": str(result["id"]),
            "matricula": result["matricula"],
            "status": result["status"],
            "message": "Solicitud creada. Ahora debe subir los documentos requeridos.",
        }

    except ValueError as e:
        logger.warning(f"[Verificacion] Validation error for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"[Verificacion] Error creating verification for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear la solicitud. Por favor, intente de nuevo."
        )


@router.get("/my-status", response_model=MyVerificationStatusResponse)
async def get_my_verification_status(
    current_user=Depends(get_current_user),
):
    """
    Get current user's verification status.

    Returns whether user is verified, has pending request, or can submit new.
    """
    result = await verificacion_service.get_my_status(current_user.id)
    return MyVerificationStatusResponse(**result)


@router.get("/my-verification", response_model=MyVerificationResponse)
async def get_my_verification(
    current_user=Depends(get_current_user),
):
    """
    Get current user's verification with full extraction data.

    Returns the user's pending/active verification with:
    - Document extraction data (for auto-fill in form_review)
    - Cross-validation results
    - File information

    This endpoint is used by the frontend wizard to:
    1. Resume an in-progress verification
    2. Auto-fill form fields with extracted data
    3. Display validation status
    """
    logger.info(f"[Verificacion] Getting user's verification data for user {current_user.id}")

    # Get user's latest verification
    verification = await verificacion_repository.get_by_user_id(current_user.id)

    if not verification:
        logger.debug(f"[Verificacion] No verification found for user {current_user.id}")
        raise HTTPException(
            status_code=404,
            detail="No tiene ninguna solicitud de verificación"
        )

    verification_data = verification.get("verification_data", {}) or {}

    # Determine proof document type
    tipo_prueba = None
    documento_prueba_data = None
    for t in DocumentoTipoPrueba:
        if t.value in verification_data:
            tipo_prueba = t
            doc_data = verification_data[t.value]
            documento_prueba_data = DocumentExtraction(
                file_id=doc_data.get("file_id"),
                file_name=doc_data.get("file_name"),
                file_url=doc_data.get("file_url"),
                mime_type=doc_data.get("mime_type"),
                extraction=doc_data.get("extraction", {}),
                extraction_confidence=doc_data.get("extraction_confidence"),
                processor=doc_data.get("processor"),
                uploaded_at=doc_data.get("uploaded_at"),
                risk_analysis=doc_data.get("risk_analysis"),
            )
            break

    # Get DIP extraction
    dip_data = verification_data.get("dip", {})
    dip_extraction = None
    if dip_data:
        dip_extraction = DocumentExtraction(
            file_id=dip_data.get("file_id"),
            file_name=dip_data.get("file_name"),
            file_url=dip_data.get("file_url"),
            mime_type=dip_data.get("mime_type"),
            extraction=dip_data.get("extraction", {}),
            extraction_confidence=dip_data.get("extraction_confidence"),
            processor=dip_data.get("processor"),
            uploaded_at=dip_data.get("uploaded_at"),
            risk_analysis=dip_data.get("risk_analysis"),
        )

    # Get cross-validation
    validacion = verification_data.get("validacion_cruzada", {})
    validacion_cruzada = ValidacionCruzada(**validacion) if validacion else None

    logger.debug(
        f"[Verificacion] Returning verification {verification['id']} for user {current_user.id}: "
        f"has_dip={dip_extraction is not None}, has_proof={documento_prueba_data is not None}"
    )

    return MyVerificationResponse(
        id=verification["id"],
        matricula=verification["matricula"],
        status=verification["status"],
        created_at=verification["created_at"],
        updated_at=verification["updated_at"],
        tipo_documento_prueba=tipo_prueba,
        tiene_dip=dip_extraction is not None,
        tiene_documento_prueba=documento_prueba_data is not None,
        validacion_cruzada=validacion_cruzada,
        dip=dip_extraction,
        documento_prueba=documento_prueba_data,
        processed_at=verification.get("processed_at"),
        rejection_reason=verification.get("rejection_reason"),
    )


@router.get("/{verificacion_id}/form-review")
async def get_form_review_data(
    verificacion_id: UUID,
    current_user=Depends(get_current_user),
):
    """
    Get structured form_review data for auto-fill.

    Returns extracted data organized by sections for the frontend wizard:
    - Datos Personales (from DIP) - 7 fields including numero_dip (critical)
    - Datos Funcionario (from proof document) - 6 fields including matricula (critical)
    - Validación Cruzada (cross-validation results) - readonly

    Uses FORM_REVIEW_CONFIG from verificacion_service for consistent structure.

    The frontend can use this to:
    1. Auto-fill form fields with extracted values
    2. Display validation warnings (name similarity, matricula mismatch)
    3. Allow user to review and correct data before submission
    """
    logger.info(f"[Verificacion] Getting form_review data for verificacion={verificacion_id}, user={current_user.id}")

    # Verify ownership
    verification = await verificacion_repository.get_by_id(verificacion_id)
    if not verification:
        raise TranslatedException(ErrorCode.NOT_FOUND)
    if str(verification["user_id"]) != str(current_user.id):
        raise TranslatedException(ErrorCode.UNAUTHORIZED)

    verification_data = verification.get("verification_data", {}) or {}

    # Delegate to service for consistent form_review structure
    form_review_data = verificacion_service.build_form_review_data(
        verificacion_id=verificacion_id,
        verification_data=verification_data,
        status=verification["status"],
    )

    logger.debug(
        f"[Verificacion] Form review built for {verificacion_id}: "
        f"sections={len(form_review_data.get('sections', []))}, "
        f"warnings={len(form_review_data.get('warnings', []))}, "
        f"auto_validable={form_review_data.get('auto_validable')}"
    )

    return form_review_data


@router.post("/{verificacion_id}/form-review")
async def save_form_review_data(
    verificacion_id: UUID,
    form_data: dict,
    current_user=Depends(get_current_user),
):
    """
    Save user-corrected form_review data.

    After the user reviews and corrects the auto-filled form_review data,
    this endpoint saves the corrected values.

    **IMPORTANT - Merge Behavior (like pasaporte):**
    The backend MERGES user corrections with extracted data:
    ```python
    final_data = {**extracted_from_documents, **user_corrections}
    ```
    This means:
    - You can send ONLY the fields the user modified
    - Unmodified extracted fields are preserved automatically
    - User corrections take precedence over extracted values

    **Request body (JSON) - can be partial:**
    ```json
    {
        "apellidos": "GARCIA LOPEZ CORRECTED",
        "matricula": "FP-12345-CORRECTED"
    }
    ```

    **Or complete:**
    ```json
    {
        "numero_dip": "12345678",
        "apellidos": "GARCIA LOPEZ",
        "nombres": "JUAN CARLOS",
        "matricula": "FP-12345",
        "cargo": "Técnico",
        ...
    }
    ```

    **Critical fields (required in merged data):**
    - `numero_dip` - DIP number (from extraction or user input)
    - `matricula` - Civil servant matricula (from extraction or user input)

    **Behavior:**
    1. Extracts all fields from DIP and proof document
    2. Merges with user corrections (user data takes precedence)
    3. Stores merged data in `verification_data["form_review_confirmed"]`
    4. If matricula changed, recalculates cross-validation
    5. Returns updated validation status

    **Response includes:**
    - `fields_saved`: Total fields in merged data
    - `user_modified_count`: Fields provided by user
    - `extracted_count`: Fields from document extraction
    """
    logger.info(f"[Verificacion] Save form_review request for verificacion={verificacion_id}, user={current_user.id}")

    try:
        result = await verificacion_service.save_form_review_data(
            verificacion_id=verificacion_id,
            user_id=current_user.id,
            form_data=form_data,
        )

        logger.info(
            f"[Verificacion] Form review saved for {verificacion_id}: "
            f"fields={result.get('fields_saved')}, matricula_updated={result.get('matricula_updated')}"
        )

        return result

    except ValueError as e:
        logger.warning(f"[Verificacion] Form review validation error for {verificacion_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Verificacion] Error saving form_review for {verificacion_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al guardar los datos. Por favor, intente de nuevo."
        )


@router.get("/form-review-config")
async def get_form_review_config():
    """
    Get the static form_review configuration.

    Returns the form_review structure without any data, useful for
    frontend initialization before documents are uploaded.

    Includes:
    - Step metadata (title, description)
    - Section definitions with field configurations
    - Field types, labels, required/editable flags
    """
    return verificacion_service.get_form_review_config()


@router.get("/document-requirements")
async def get_document_requirements(
    tipo_prueba: Optional[str] = Query(
        None,
        description="Tipo de documento de prueba: nombramiento, carnet_funcionario, contrato_funcionario"
    ),
):
    """
    Get required documents for funcionario verification.

    This endpoint provides:
    - List of required documents with schema keys for OCR extraction
    - Instructions for each document
    - Accepted formats and size limits
    - Configuration for frontend wizard

    If tipo_prueba is provided, returns specific requirements for that proof type.
    If not, returns all three proof document options as alternatives (user must provide ONE).

    Example response:
    ```json
    {
      "documents": [
        {
          "document_code": "dip",
          "document_name_es": "Documento de Identidad Personal (DIP)",
          "schema_key": "DIP_GQ_V2",
          "is_required": true,
          "instructions_es": "Escanee ambas caras de su DIP vigente...",
          "faces_required": ["recto", "verso"],
          "accepted_formats": ["pdf", "jpg", "jpeg", "png"],
          "max_size_mb": 10
        },
        ...
      ],
      "proof_options": [...]
    }
    ```
    """
    # Parse tipo_prueba if provided
    tipo_doc = None
    if tipo_prueba:
        try:
            tipo_doc = DocumentoTipoPrueba(tipo_prueba)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"tipo_prueba inválido. Valores permitidos: {[t.value for t in DocumentoTipoPrueba]}"
            )

    requirements = verificacion_service.get_required_documents(tipo_doc)
    proof_options = verificacion_service.get_proof_document_options()

    return {
        "documents": [req.to_dict() for req in requirements],
        "proof_options": proof_options,
        "total_required": len([r for r in requirements if r.is_required]),
    }


@router.get("/proof-options")
async def get_proof_document_options():
    """
    Get available proof document options for funcionario verification.

    Returns the three types of proof documents that can be submitted:
    - Acta de Nombramiento
    - Carnet de Funcionario
    - Contrato de Funcionario

    Each option includes the schema_key for OCR extraction.
    """
    return {
        "options": verificacion_service.get_proof_document_options()
    }


@router.post("/{verificacion_id}/documents/preview")
async def preview_document_extraction(
    verificacion_id: UUID,
    file: UploadFile = File(...),
    document_code: str = Form(..., description="dip, nombramiento, carnet_funcionario, or contrato_funcionario"),
    existing_extractions: Optional[str] = Form(None, description="JSON of existing extractions for cross-validation"),
    current_user=Depends(get_current_user),
):
    """
    Preview document extraction (Step 1 of 2).

    Upload document for OCR extraction. Returns preview with extracted data.
    Document is NOT yet saved to storage - use /validate to confirm and save.

    The file content is stored in cache (Redis/Upstash in production) until validation.
    """
    logger.info(f"[Verificacion] Preview request for verificacion={verificacion_id}, doc={document_code}, user={current_user.id}")

    # Verify ownership
    verification = await verificacion_repository.get_by_id(verificacion_id)
    if not verification:
        logger.warning(f"[Verificacion] Verification {verificacion_id} not found")
        raise TranslatedException(ErrorCode.NOT_FOUND)
    if str(verification["user_id"]) != str(current_user.id):
        logger.warning(f"[Verificacion] User {current_user.id} not authorized for verification {verificacion_id}")
        raise TranslatedException(ErrorCode.UNAUTHORIZED)
    if verification["status"] != "pendiente":
        logger.warning(f"[Verificacion] Verification {verificacion_id} already processed")
        raise TranslatedException(ErrorCode.ALREADY_PROCESSED)

    # Validate document code
    valid_codes = ["dip"] + [e.value for e in DocumentoTipoPrueba]
    if document_code not in valid_codes:
        raise HTTPException(
            status_code=400,
            detail=f"document_code inválido. Valores permitidos: {valid_codes}",
        )

    try:
        # Read file content
        content = await file.read()
        mime_type = file.content_type or "application/octet-stream"
        file_size = len(content)

        logger.debug(f"[Verificacion] File read: {file.filename}, size={file_size}, mime={mime_type}")

        # Parse existing extractions if provided (for cross-validation)
        existing_dip_extraction = None
        if existing_extractions:
            try:
                existing = json.loads(existing_extractions)
                existing_dip_extraction = existing.get("dip", {}).get("extraction")
                logger.debug(f"[Verificacion] Using existing DIP extraction for cross-validation")
            except json.JSONDecodeError:
                logger.warning(f"[Verificacion] Invalid existing_extractions JSON, ignoring")

        # Extract based on document type using Gemini
        logger.info(f"[Verificacion] Starting OCR extraction for {document_code}")

        if document_code == "dip":
            extraction_result = await verificacion_service.extract_dip(
                file_content=content,
                mime_type=mime_type,
                user_id=str(current_user.id),
            )
        else:
            tipo_documento = DocumentoTipoPrueba(document_code)
            extraction_result = await verificacion_service.extract_documento_prueba(
                file_content=content,
                mime_type=mime_type,
                tipo_documento=tipo_documento,
                user_id=str(current_user.id),
                existing_dip_extraction=existing_dip_extraction,
            )

        logger.info(f"[Verificacion] OCR extraction complete, confidence={extraction_result.get('confidence', 0)}")

        # Generate preview ID
        preview_id = f"vf_{verificacion_id}_{document_code}_{hashlib.sha256(content).hexdigest()[:12]}"

        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=PREVIEW_CACHE_TTL_SECONDS)

        # Store in preview cache with base64-encoded content
        # This allows the content to be safely serialized to Redis/JSON
        cache_data = {
            "verificacion_id": str(verificacion_id),
            "user_id": str(current_user.id),
            "document_code": document_code,
            "file_name": file.filename,
            "file_size": file_size,
            "mime_type": mime_type,
            "content_b64": base64.b64encode(content).decode("utf-8"),  # Base64 for safe serialization
            "extraction": extraction_result.get("extraction", {}),
            "confidence": extraction_result.get("confidence", 0),
            "processor": extraction_result.get("processor", "unknown"),
            "extraction_status": extraction_result.get("status", "error"),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        # Store in cache using correct method name: set()
        cache_success = await preview_cache.set(preview_id, cache_data, PREVIEW_CACHE_TTL_SECONDS)

        if not cache_success:
            logger.error(f"[Verificacion] Failed to store preview in cache for {verificacion_id}")
            raise HTTPException(
                status_code=500,
                detail="Error al guardar la vista previa. Por favor, intente de nuevo."
            )

        logger.info(f"[Verificacion] Preview stored in cache: {preview_id}, expires_at={expires_at}")

        return {
            "preview_id": preview_id,
            "document_code": document_code,
            "document_name": document_code.replace("_", " ").title(),
            "file_name": file.filename,
            "file_size": file_size,
            "mime_type": mime_type,
            "extraction": extraction_result.get("extraction", {}),
            "confidence": extraction_result.get("confidence", 0),
            "processor": extraction_result.get("processor", "unknown"),
            "extraction_status": extraction_result.get("status", "error"),
            "expires_at": expires_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Verificacion] Error in preview for {verificacion_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al procesar el documento. Por favor, verifique el archivo e intente de nuevo."
        )


@router.post("/{verificacion_id}/documents/validate")
async def validate_and_save_document(
    verificacion_id: UUID,
    preview_id: str = Form(...),
    confirmed_data: str = Form(..., description="JSON of confirmed/corrected extraction data"),
    current_user=Depends(get_current_user),
):
    """
    Validate and save document (Step 2 of 2).

    User confirms the extracted data. Document is uploaded to Firebase Storage
    and extraction saved to database in an atomic operation.

    If Firebase upload fails, no data is saved.
    If database save fails, the error is logged and reported to user.
    """
    logger.info(f"[Verificacion] Validate request for verificacion={verificacion_id}, preview={preview_id}, user={current_user.id}")

    # Verify ownership
    verification = await verificacion_repository.get_by_id(verificacion_id)
    if not verification:
        logger.warning(f"[Verificacion] Verification {verificacion_id} not found")
        raise TranslatedException(ErrorCode.NOT_FOUND)
    if str(verification["user_id"]) != str(current_user.id):
        logger.warning(f"[Verificacion] User {current_user.id} not authorized for verification {verificacion_id}")
        raise TranslatedException(ErrorCode.UNAUTHORIZED)
    if verification["status"] != "pendiente":
        logger.warning(f"[Verificacion] Verification {verificacion_id} already processed")
        raise TranslatedException(ErrorCode.ALREADY_PROCESSED)

    # Get preview from cache using correct method name: get()
    preview_data = await preview_cache.get(preview_id)
    if not preview_data:
        logger.warning(f"[Verificacion] Preview {preview_id} not found or expired")
        raise HTTPException(
            status_code=404,
            detail="La vista previa ha expirado. Por favor, suba el documento de nuevo."
        )

    # Verify preview belongs to this verification and user
    if preview_data.get("verificacion_id") != str(verificacion_id):
        logger.warning(f"[Verificacion] Preview {preview_id} does not match verification {verificacion_id}")
        raise HTTPException(status_code=400, detail="La vista previa no corresponde a esta verificación")
    if preview_data.get("user_id") != str(current_user.id):
        logger.warning(f"[Verificacion] Preview {preview_id} does not belong to user {current_user.id}")
        raise TranslatedException(ErrorCode.UNAUTHORIZED)

    # Parse confirmed data
    try:
        confirmed = json.loads(confirmed_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Los datos confirmados deben ser JSON válido")

    document_code = preview_data.get("document_code")
    file_name = preview_data.get("file_name", f"{document_code}.pdf")
    mime_type = preview_data.get("mime_type", "application/pdf")

    try:
        # ===================================================================
        # STEP 1: Decode file content from base64
        # ===================================================================
        content_b64 = preview_data.get("content_b64")
        if not content_b64:
            logger.error(f"[Verificacion] No content_b64 in preview {preview_id}")
            raise HTTPException(
                status_code=500,
                detail="Error interno: contenido del documento no encontrado en cache"
            )

        content = base64.b64decode(content_b64)
        logger.debug(f"[Verificacion] Decoded content: {len(content)} bytes")

        # ===================================================================
        # STEP 2: Upload to Firebase Storage FIRST (fail-fast pattern)
        # ===================================================================
        logger.info(f"[Verificacion] Uploading to Firebase Storage: verificacion={verificacion_id}, doc={document_code}")

        try:
            upload_result = await firebase_storage_service.upload_user_document(
                user_id=str(current_user.id),
                application_id=str(verificacion_id),
                file=content,  # bytes
                metadata={
                    "filename": file_name,
                    "mime_type": mime_type,
                    "document_code": document_code,
                    "verificacion_id": str(verificacion_id),
                    "document_type": "verificacion_funcionario",
                }
            )

            file_path = upload_result.file_path
            file_id = upload_result.file_id
            file_url = upload_result.file_url

            logger.info(f"[Verificacion] Firebase upload successful: {file_path}")

        except HTTPException as firebase_err:
            logger.error(f"[Verificacion] Firebase upload failed for {verificacion_id}: {firebase_err.detail}")
            raise HTTPException(
                status_code=502,
                detail="No se pudo guardar el documento. Por favor, intente de nuevo más tarde."
            )
        except Exception as firebase_err:
            logger.error(f"[Verificacion] Firebase upload error for {verificacion_id}: {firebase_err}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail="Error al subir el documento al almacenamiento. Por favor, intente de nuevo."
            )

        # ===================================================================
        # STEP 3: Save to database (after Firebase success)
        # ===================================================================
        logger.info(f"[Verificacion] Saving to database: verificacion={verificacion_id}, doc={document_code}")

        validated_at = datetime.now(timezone.utc).isoformat()

        # Build document data with Firebase info
        document_data = {
            "file_id": file_id,
            "file_name": file_name,
            "file_path": file_path,
            "file_url": file_url,
            "file_size": len(content),
            "mime_type": mime_type,
            "uploaded_at": validated_at,
            "extraction": confirmed,  # User-confirmed data
            "extraction_confidence": preview_data.get("confidence", 0),
            "processor": preview_data.get("processor", "unknown"),
            "storage": "firebase",
        }

        try:
            # Update verification with document data
            result = await verificacion_service.update_document_data(
                verificacion_id=verificacion_id,
                document_type=document_code,
                document_data=document_data,
            )

            logger.info(f"[Verificacion] Database save successful for {verificacion_id}")

        except Exception as db_err:
            # Firebase upload succeeded but DB failed
            # Log for manual cleanup if needed
            logger.error(
                f"[Verificacion] Database save failed for {verificacion_id} after Firebase upload. "
                f"Firebase path: {file_path}. Error: {db_err}",
                exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail="El documento se subió pero hubo un error al guardar los datos. Por favor, contacte soporte."
            )

        # ===================================================================
        # STEP 4: Delete preview from cache (cleanup)
        # ===================================================================
        await preview_cache.delete(preview_id)
        logger.debug(f"[Verificacion] Preview {preview_id} deleted from cache")

        # Get cross-validation result from updated verification
        validacion_cruzada = result.get("verification_data", {}).get("validacion_cruzada")

        logger.info(
            f"[Verificacion] Document validated successfully: verificacion={verificacion_id}, "
            f"doc={document_code}, firebase_path={file_path}"
        )

        return {
            "document_id": file_id,
            "document_code": document_code,
            "document_name": document_code.replace("_", " ").title(),
            "file_path": file_path,
            "file_url": file_url,
            "extraction_data": confirmed,
            "extraction_confidence": preview_data.get("confidence", 0),
            "is_validated": True,
            "validated_at": validated_at,
            "storage": "firebase",
            "validacion_cruzada": validacion_cruzada,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Verificacion] Unexpected error in validate for {verificacion_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error inesperado al validar el documento. Por favor, intente de nuevo."
        )


@router.post("/{verificacion_id}/submit")
async def submit_verificacion(
    verificacion_id: UUID,
    force_submit: bool = Query(
        False,
        description="Si True, envía la solicitud aunque haya advertencias de validación"
    ),
    current_user=Depends(get_current_user),
):
    """
    Submit verification for agent review.

    BLOCKING requirements (cannot proceed without):
    - DIP document must be uploaded and validated
    - Proof document (Nombramiento, Carnet, or Contrato) must be uploaded and validated
    - Cross-validation must have been calculated

    NON-BLOCKING warnings (can proceed with force_submit=True):
    - Name similarity < 85%
    - Matriculas don't match

    If warnings exist and force_submit=False, returns requires_confirmation=True
    with the warnings. Frontend should show these to user and call again with
    force_submit=True after user confirmation.
    """
    logger.info(
        f"[Verificacion] Submit request for verificacion={verificacion_id}, "
        f"user={current_user.id}, force_submit={force_submit}"
    )

    try:
        result = await verificacion_service.submit_verification(
            verificacion_id=verificacion_id,
            user_id=current_user.id,
            force_submit=force_submit,
        )

        # Check if submission requires confirmation (warnings present, not forced)
        if result.get("requires_confirmation"):
            logger.info(
                f"[Verificacion] Submission requires confirmation for {verificacion_id}, "
                f"warnings={len(result.get('warnings', []))}"
            )
            return {
                "success": False,
                "submitted": False,
                "requires_confirmation": True,
                "verificacion_id": str(verificacion_id),
                "warnings": result.get("warnings", []),
                "message": result.get("message", "Se encontraron advertencias de validación"),
                "validacion_cruzada": result.get("verification_data", {}).get("validacion_cruzada", {}),
            }

        # Submission successful
        validacion = result.get("verification_data", {}).get("validacion_cruzada", {})
        auto_validable = result.get("auto_validable", False)
        warnings = result.get("warnings", [])

        logger.info(
            f"[Verificacion] Submitted verification {verificacion_id}, "
            f"auto_validable={auto_validable}, warnings_acknowledged={len(warnings)}"
        )

        return {
            "success": True,
            "submitted": True,
            "verificacion_id": str(verificacion_id),
            "status": "pendiente",
            "message": "Solicitud enviada para revisión por el Ministerio de la Función Pública",
            "validacion_cruzada": validacion,
            "auto_validable": auto_validable,
            "warnings": warnings,
            "warnings_acknowledged": len(warnings) > 0,
        }

    except ValueError as e:
        logger.warning(f"[Verificacion] Submit validation error for {verificacion_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Verificacion] Error submitting {verificacion_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al enviar la solicitud. Por favor, intente de nuevo."
        )


# =============================================================================
# AGENT ENDPOINTS (Requires funcionario.verificacion permissions)
# =============================================================================

@router.get("/pending", response_model=VerificacionListResponse)
async def list_pending_verifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auto_validable_only: bool = Query(False, description="Only return auto-validable requests (cross-validation passed)"),
    pre_verified_only: bool = Query(False, description="Only return pre-verified requests (matricula in verified_identifiers)"),
    current_user=Depends(require_permissions(["funcionario.verificacion.read_all"])),
):
    """
    List pending verifications for agent dashboard.

    **Filters:**
    - `auto_validable_only`: Requests where cross-validation passed (name match + matricula match)
    - `pre_verified_only`: Requests where matricula exists in verified_identifiers (imported from SIGEF)

    Pre-verified requests can be approved faster as the matricula is already confirmed.

    Requires permission: funcionario.verificacion.read_all
    """
    result = await verificacion_service.list_pending(
        page=page,
        page_size=page_size,
        auto_validable_only=auto_validable_only,
        pre_verified_only=pre_verified_only,
    )

    # Transform items to response model
    items = []
    for item in result.get("items", []):
        verification_data = item.get("verification_data", {}) or {}
        validacion = verification_data.get("validacion_cruzada", {})

        # Determine proof document type
        tipo_prueba = None
        for t in DocumentoTipoPrueba:
            if t.value in verification_data:
                tipo_prueba = t
                break

        # Extract auto-verification result
        auto_verification = verification_data.get("auto_verification", {})
        pre_verified = auto_verification.get("pre_verified", False)
        pre_verified_source = auto_verification.get("source") if pre_verified else None

        items.append(VerificacionResponse(
            id=item["id"],
            user_id=item["user_id"],
            matricula=item["matricula"],
            status=item["status"],
            tipo_documento_prueba=tipo_prueba,
            tiene_dip="dip" in verification_data,
            tiene_documento_prueba=tipo_prueba is not None,
            validacion_cruzada=validacion if validacion else None,
            pre_verified=pre_verified,
            pre_verified_source=pre_verified_source,
            processed_by=item.get("processed_by"),
            processed_at=item.get("processed_at"),
            rejection_reason=item.get("rejection_reason"),
            notes=item.get("notes"),
            verificacion_matricula_existe=item.get("verificacion_matricula_existe", False),
            verificacion_nombre_coincide=item.get("verificacion_nombre_coincide", False),
            verificacion_dip_coincide=item.get("verificacion_dip_coincide", False),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        ))

    return VerificacionListResponse(
        items=items,
        total=result.get("total", 0),
        page=result.get("page", 1),
        page_size=result.get("page_size", 20),
        total_pages=result.get("total_pages", 0),
        pendientes=result.get("pendientes", 0),
        pendientes_auto_validables=result.get("pendientes_auto_validables", 0),
        pendientes_pre_verificados=result.get("pendientes_pre_verificados", 0),
        aprobadas=result.get("aprobadas", 0),
        rechazadas=result.get("rechazadas", 0),
    )


@router.get("/{verificacion_id}", response_model=VerificacionDetailResponse)
async def get_verification_detail(
    verificacion_id: UUID,
    current_user=Depends(require_permissions(["funcionario.verificacion.read_all"])),
):
    """
    Get detailed verification info for agent review.

    Includes full verification_data with extractions.
    Requires permission: funcionario.verificacion.read_all
    """
    verification = await verificacion_service.get_verification(verificacion_id)
    if not verification:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    verification_data = verification.get("verification_data", {}) or {}
    validacion = verification_data.get("validacion_cruzada", {})

    tipo_prueba = None
    for t in DocumentoTipoPrueba:
        if t.value in verification_data:
            tipo_prueba = t
            break

    # Extract auto-verification result
    auto_verification = verification_data.get("auto_verification", {})
    pre_verified = auto_verification.get("pre_verified", False)
    pre_verified_source = auto_verification.get("source") if pre_verified else None

    return VerificacionDetailResponse(
        id=verification["id"],
        user_id=verification["user_id"],
        matricula=verification["matricula"],
        status=verification["status"],
        tipo_documento_prueba=tipo_prueba,
        tiene_dip="dip" in verification_data,
        tiene_documento_prueba=tipo_prueba is not None,
        validacion_cruzada=validacion if validacion else None,
        pre_verified=pre_verified,
        pre_verified_source=pre_verified_source,
        processed_by=verification.get("processed_by"),
        processed_at=verification.get("processed_at"),
        rejection_reason=verification.get("rejection_reason"),
        notes=verification.get("notes"),
        verificacion_matricula_existe=verification.get("verificacion_matricula_existe", False),
        verificacion_nombre_coincide=verification.get("verificacion_nombre_coincide", False),
        verificacion_dip_coincide=verification.get("verificacion_dip_coincide", False),
        created_at=verification["created_at"],
        updated_at=verification["updated_at"],
        verification_data=verification_data,
        user_email=verification.get("user_email"),
        user_full_name=verification.get("user_full_name"),
        user_phone=verification.get("user_phone"),
    )


@router.post("/{verificacion_id}/process")
async def process_verification(
    verificacion_id: UUID,
    data: VerificacionProcessRequest,
    current_user=Depends(require_permissions(["funcionario.verificacion.process"])),
):
    """
    Process a verification (approve or reject).

    Requires permission: funcionario.verificacion.process
    """
    logger.info(
        f"[Verificacion] Process request: verificacion={verificacion_id}, "
        f"action={data.action}, agent={current_user.id}"
    )

    result = await verificacion_service.process_verification(
        verificacion_id=verificacion_id,
        agent_id=current_user.id,
        action=data.action,
        matricula_existe=data.matricula_existe,
        nombre_coincide=data.nombre_coincide,
        dip_coincide=data.dip_coincide,
        rejection_reason=data.rejection_reason,
        notes=data.notes,
    )

    if not result.get("success"):
        logger.warning(f"[Verificacion] Process failed for {verificacion_id}: {result.get('error')}")
        raise HTTPException(status_code=400, detail=result.get("error", "Error al procesar"))

    logger.info(f"[Verificacion] Processed {verificacion_id}: status={result.get('status')}")
    return result


@router.post("/batch-approve", response_model=BatchApproveResponse)
async def batch_approve_verifications(
    data: BatchApproveRequest,
    current_user=Depends(require_permissions(["funcionario.verificacion.process"])),
):
    """
    Batch approve multiple verifications.

    Only approves auto-validable verifications (cross-validation passed).
    Requires permission: funcionario.verificacion.process
    """
    logger.info(
        f"[Verificacion] Batch approve request: {len(data.verificacion_ids)} items, agent={current_user.id}"
    )

    result = await verificacion_service.batch_approve(
        verificacion_ids=data.verificacion_ids,
        agent_id=current_user.id,
        notes=data.notes,
    )

    logger.info(
        f"[Verificacion] Batch approve complete: approved={result.get('approved')}, "
        f"errors={result.get('errors')}"
    )

    return BatchApproveResponse(**result)
