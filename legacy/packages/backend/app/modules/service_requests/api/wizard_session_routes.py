"""
API Routes for Wizard Sessions (Cache-First Architecture).

These endpoints manage wizard sessions entirely in Redis cache until payment.
No database writes occur until payment is initiated.

@since v2.0 - Cache-first wizard migration
@see .claude/plans/CACHE_FIRST_WIZARD_MIGRATION_PLAN.md
"""
from fastapi import APIRouter, Depends, File, UploadFile, Query, Path, Body, Request
from fastapi import HTTPException, status
from typing import Optional, List
from uuid import UUID
from datetime import date, timedelta
import asyncpg
from loguru import logger

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user

from ..models.wizard_session import (
    WizardSessionCreate,
    WizardSessionResponse,
    WizardDocumentPreviewResponse,
    WizardDocumentConfirmRequest,
    WizardFormDataSaveRequest,
    WizardPreparePaymentResponse,
    WizardPersistResult,
    WizardInitiatePaymentRequest,
    WizardInitiatePaymentResponse,
    SiteSelectionRequest,
    AppointmentSelectionRequest,
)
from ..models.form_config import FormConfigResponse
from ..models.appointments import (
    EntityLocationResponse,
    AvailableSlotResponse,
    AvailableDayResponse,
    AvailableDaysListResponse,
    AppointmentLocationsListResponse,
    AppointmentSlotsListResponse,
)
from ..services.appointment_service import appointment_service
from ..services.wizard_session_service import (
    wizard_session_service,
    WizardSessionError,
    WizardSessionExpiredError,
    WizardSessionNotFoundError,
    WizardDocumentValidationError,
    WizardPersistError,
)


router = APIRouter(prefix="/wizard-sessions", tags=["Wizard Sessions (Cache-First)"])


# =============================================================================
# HELPER: Extract client info for audit
# =============================================================================

def _get_client_info(request: Request) -> tuple:
    """Extract IP address and user agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


# =============================================================================
# HELPER: Handle service exceptions
# =============================================================================

def _handle_session_error(e: WizardSessionError):
    """Convert service exceptions to HTTP exceptions."""
    if isinstance(e, WizardSessionNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": e.message, "code": e.code}
        )
    elif isinstance(e, WizardSessionExpiredError):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"message": e.message, "code": e.code}
        )
    elif isinstance(e, WizardDocumentValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "code": e.code}
        )
    elif isinstance(e, WizardPersistError):
        # User-actionable errors return 422, truly unexpected errors return 500
        user_actionable_codes = {
            "APPOINTMENT_SLOT_TAKEN", "APPOINTMENT_REQUIRED",
            "PAYMENT_FAILED", "VALIDATION_ERRORS",
            "INCOMPLETE_APPOINTMENT_DATA",
            "MISSING_SITE_SELECTION", "INVALID_SITE_SELECTION",
        }
        http_status = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if e.code in user_actionable_codes
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(
            status_code=http_status,
            detail={"message": e.message, "code": e.code, "details": e.details}
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "code": e.code}
        )


# =============================================================================
# START SESSION
# =============================================================================

@router.post(
    "",
    response_model=WizardSessionResponse,
    status_code=201,
    summary="Start a new wizard session",
    description="""
    Start a new wizard session in cache.

    **Cache-First Architecture:**
    - NO database record is created
    - All data stays in Redis cache with 30-minute TTL
    - Session expires after 30 minutes of inactivity
    - Data is persisted to DB only when payment is initiated

    **Required fields:**
    - `workflow_code`: The workflow code (e.g., "PASAPORTE", "RESIDENCIA")

    **Optional fields:**
    - `solicitud_type`: expedicion (default), renovacion, or duplicado
    - `sub_type`: Workflow-specific sub-type
    - `motivo`: Reason for renovacion (VENCIMIENTO, PERDIDA, ROBO, DETERIORO)
    - `is_minor`: True if applicant is a minor
    """,
)
async def start_wizard_session(
    data: WizardSessionCreate,
    request: Request,
    current_user=Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Start a new wizard session."""
    ip_address, user_agent = _get_client_info(request)

    try:
        result = await wizard_session_service.start_session(
            user_id=current_user.id,
            workflow_code=data.workflow_code,
            solicitud_type=data.solicitud_type,
            sub_type=data.sub_type,
            motivo=data.motivo,
            is_minor=data.is_minor,
            ip_address=ip_address,
            user_agent=user_agent,
            auto_fill_vault=data.auto_fill_vault,
            db=db if data.auto_fill_vault else None,
        )

        logger.info(
            f"[WizardAPI] Session started: {result.session_id} "
            f"for user {current_user.id}, workflow={data.workflow_code}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# GET SESSION
# =============================================================================

@router.get(
    "/{session_id}",
    response_model=WizardSessionResponse,
    summary="Get wizard session",
    description="""
    Get the current state of a wizard session.

    Returns:
    - Session status and metadata
    - List of uploaded documents
    - Current form data
    - Tariff (if calculated)
    - Time remaining before expiration

    **Note:** Each call does NOT renew the TTL. Only actions
    (document upload, form save) renew the session.
    """,
)
async def get_wizard_session(
    session_id: str = Path(..., description="The wizard session ID"),
    current_user=Depends(get_current_user),
):
    """Get wizard session details."""
    try:
        return await wizard_session_service.get_session(
            session_id=session_id,
            user_id=current_user.id,
        )
    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# PREVIEW DOCUMENT
# =============================================================================

@router.post(
    "/{session_id}/documents/preview",
    response_model=WizardDocumentPreviewResponse,
    summary="Preview document extraction",
    description="""
    Upload a document for extraction preview.

    **What happens:**
    1. File is validated (size, type)
    2. Document is extracted using Gemini AI
    3. Extraction results are stored in session cache
    4. File content (base64) is stored in session for later Firebase upload
    5. Session TTL is renewed

    **Response includes:**
    - Extracted data fields
    - Confidence score
    - Risk analysis (if applicable)
    - Cross-document validation results

    **Supported formats:** PDF, JPG, PNG, WebP
    **Max file size:** 10MB
    """,
)
async def preview_document(
    session_id: str = Path(..., description="The wizard session ID"),
    document_code: str = Query(..., description="Document code (e.g., dip, pasaporte_antiguo)"),
    file: UploadFile = File(..., description="The document file"),
    current_user=Depends(get_current_user),
):
    """Preview document extraction and store in session."""
    try:
        # Read file content
        file_content = await file.read()

        result = await wizard_session_service.preview_document(
            session_id=session_id,
            user_id=current_user.id,
            document_code=document_code,
            file_content=file_content,
            file_name=file.filename or "document",
            mime_type=file.content_type or "application/octet-stream",
        )

        logger.info(
            f"[WizardAPI] Document preview: session={session_id}, "
            f"doc={document_code}, confidence={result.confidence}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# CONFIRM DOCUMENT
# =============================================================================

@router.post(
    "/{session_id}/documents/confirm",
    response_model=WizardSessionResponse,
    summary="Confirm document extraction",
    description="""
    Confirm document extraction data (with optional corrections).

    After previewing a document, the user can:
    - Confirm the extracted data as-is
    - Provide corrections for any fields

    **Required fields:**
    - `document_code`: The document to confirm
    - `confirmed_data`: The user-confirmed (or corrected) extraction data

    **Effect:**
    - Document is marked as confirmed in session
    - Extracted data is updated with user corrections
    - Session TTL is renewed
    """,
)
async def confirm_document(
    session_id: str = Path(..., description="The wizard session ID"),
    data: WizardDocumentConfirmRequest = Body(...),
    current_user=Depends(get_current_user),
):
    """Confirm document extraction with optional corrections."""
    try:
        result = await wizard_session_service.confirm_document(
            session_id=session_id,
            user_id=current_user.id,
            document_code=data.document_code,
            confirmed_data=data.confirmed_data,
            user_notes=data.user_notes,
        )

        logger.info(
            f"[WizardAPI] Document confirmed: session={session_id}, "
            f"doc={data.document_code}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# DELETE DOCUMENT
# =============================================================================

@router.delete(
    "/{session_id}/documents/{document_code}",
    response_model=WizardSessionResponse,
    summary="Delete a document from wizard session",
    description="""
    Delete a specific document from the wizard session.

    **Effect:**
    - Document data (content, extraction) is removed from session
    - Extracted data for that document is cleared
    - User can re-upload a replacement document
    - Session TTL is renewed

    **Use case:** User wants to replace a document they already uploaded.
    """,
)
async def delete_wizard_document(
    session_id: str = Path(..., description="The wizard session ID"),
    document_code: str = Path(..., description="Document code to delete (e.g., dip, pasaporte_antiguo)"),
    current_user=Depends(get_current_user),
):
    """Delete a document from wizard session."""
    try:
        result = await wizard_session_service.delete_document(
            session_id=session_id,
            user_id=current_user.id,
            document_code=document_code,
        )

        logger.info(
            f"[WizardAPI] Document deleted: session={session_id}, "
            f"doc={document_code}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# USE VAULT DOCUMENT (Phase 2 — auto-fill from vault)
# =============================================================================

from pydantic import BaseModel, Field as PydField


class UseVaultDocumentRequest(BaseModel):
    """Request body for selecting a vault document for a wizard step."""
    document_code: str = PydField(
        ..., description="Document code to fill (e.g. 'dip', 'pasaporte_antiguo')"
    )
    vault_document_id: str = PydField(
        ..., description="ID of the vault document to use (UUID string)"
    )


@router.post(
    "/{session_id}/documents/use-vault",
    response_model=WizardSessionResponse,
    summary="Select a vault document for the wizard",
    description="""
    Use an existing document from the user's vault instead of uploading.

    **Flow:**
    1. Validates that the vault document belongs to the authenticated user
    2. Copies extraction data from vault to wizard session
    3. Marks the document as "uploaded" in the session
    4. No file re-upload needed — persist will reuse the vault file path

    **Use case:** User already has a valid DIP in their vault.
    Instead of re-uploading, they select it from the vault picker.
    """,
)
async def use_vault_document(
    session_id: str = Path(..., description="The wizard session ID"),
    body: UseVaultDocumentRequest = Body(...),
    current_user=Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Select a vault document for use in a wizard session."""
    try:
        result = await wizard_session_service.use_vault_document(
            session_id=session_id,
            user_id=current_user.id,
            document_code=body.document_code,
            vault_document_id=body.vault_document_id,
            db=db,
        )

        logger.info(
            f"[WizardAPI] Vault document used: session={session_id}, "
            f"doc={body.document_code}, vault_id={body.vault_document_id}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# SAVE FORM DATA
# =============================================================================

@router.put(
    "/{session_id}/form-data",
    response_model=WizardSessionResponse,
    summary="Save form data",
    description="""
    Save form data to the wizard session.

    Form data is merged with existing data (user edits take precedence).
    This is called when the user edits fields in the form review step.

    **Effect:**
    - Form data is merged into session
    - Current step is updated (if provided)
    - Session TTL is renewed
    """,
)
async def save_form_data(
    session_id: str = Path(..., description="The wizard session ID"),
    data: WizardFormDataSaveRequest = Body(...),
    current_user=Depends(get_current_user),
):
    """Save form data to session."""
    try:
        result = await wizard_session_service.save_form_data(
            session_id=session_id,
            user_id=current_user.id,
            form_data=data.form_data,
            step_id=data.step_id,
        )

        logger.info(
            f"[WizardAPI] Form data saved: session={session_id}, "
            f"step={data.step_id}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# FORM CONFIG (Dynamic form rendering)
# =============================================================================

@router.get(
    "/{session_id}/form-config/{step_id}",
    response_model=FormConfigResponse,
    summary="Get dynamic form configuration for a session step",
    description="""
    Returns the form configuration for a specific workflow step.

    The configuration includes:
    - Sections filtered by conditions (solicitud_type, motivo, is_minor, etc.)
    - Fields with pre-filled values from document extraction + form edits
    - Validation rules and field metadata

    This enables the frontend to render forms dynamically using DynamicFormRenderer.

    **Condition evaluation**: Sections with conditions are evaluated
    against the session context. Only matching sections are returned.

    **Value pre-filling**: Field values are resolved using:
    1. form_data (user edits) - highest priority
    2. extracted_data (OCR results via form_mapping) - fallback
    """,
)
async def get_session_form_config(
    session_id: str = Path(..., description="The wizard session ID"),
    step_id: str = Path(..., description="The workflow step ID (e.g., 'form_review_1')"),
    current_user=Depends(get_current_user),
) -> FormConfigResponse:
    """Get dynamic form configuration with pre-filled values for a session."""
    try:
        result = await wizard_session_service.get_form_config(
            session_id=session_id,
            user_id=current_user.id,
            step_id=step_id,
        )

        logger.info(
            f"[WizardAPI] Form config: session={session_id}, "
            f"step={step_id}, sections={len(result.sections)}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# PREPARE FOR PAYMENT
# =============================================================================

@router.post(
    "/{session_id}/prepare-payment",
    response_model=WizardPreparePaymentResponse,
    summary="Prepare session for payment",
    description="""
    Validate session and calculate tariff for payment.

    **What happens:**
    1. Verify all required documents are uploaded
    2. Run cross-document validation
    3. Calculate tariff based on workflow and options
    4. Update session status to READY_FOR_PAYMENT (if valid)

    **Response includes:**
    - `ready_for_payment`: True if session can proceed to payment
    - `tariff`: Complete tariff breakdown
    - `errors`: Blocking validation errors
    - `warnings`: Non-blocking warnings
    - `missing_documents`: Documents still required

    **Note:** This does NOT persist to database. That happens when
    payment is initiated.
    """,
)
async def prepare_for_payment(
    session_id: str = Path(..., description="The wizard session ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Prepare session for payment."""
    try:
        result = await wizard_session_service.prepare_for_payment(
            session_id=session_id,
            user_id=current_user.id,
            db=db,
        )

        logger.info(
            f"[WizardAPI] Prepare payment: session={session_id}, "
            f"ready={result.ready_for_payment}, amount={result.total_amount}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# PERSIST TO DB (Called by payment processor)
# =============================================================================

@router.post(
    "/{session_id}/persist",
    response_model=WizardPersistResult,
    summary="Persist session to database",
    description="""
    Persist wizard session to database (atomic transaction).

    **IMPORTANT:** This endpoint is typically called by the payment processor
    when payment is initiated, not directly by the frontend.

    **What happens (atomic):**
    1. Create service_request record in database
    2. Upload all documents to Firebase Storage
    3. Create service_request_documents records
    4. Delete session from cache

    **If any step fails:**
    - All Firebase uploads are rolled back
    - Session remains in cache
    - Error is returned

    **Response includes:**
    - `service_request_id`: The created service request ID
    - `reference`: The reference number (e.g., PAS-2026-00001)
    """,
)
async def persist_session(
    session_id: str = Path(..., description="The wizard session ID"),
    payment_id: Optional[str] = Query(None, description="Payment ID if already created"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Persist session to database."""
    try:
        result = await wizard_session_service.persist_to_db(
            session_id=session_id,
            user_id=current_user.id,
            db=db,
            payment_id=payment_id,
        )

        logger.info(
            f"[WizardAPI] Session persisted: session={session_id}, "
            f"request_id={result.service_request_id}, ref={result.reference}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# INITIATE PAYMENT (Atomic: persist + pay)
# =============================================================================

@router.post(
    "/{session_id}/initiate-payment",
    response_model=WizardInitiatePaymentResponse,
    summary="Atomically persist session and initiate payment",
    description="""
    Single atomic endpoint that combines:
    1. Persist session to database (create service_request + upload documents to Firebase)
    2. Initiate payment (create service_payment + call payment processor)

    All operations run in a single database transaction. If any step fails,
    everything is rolled back:
    - Database: automatic transaction rollback
    - Firebase: uploaded files are cleaned up
    - Cache: session restored to READY_FOR_PAYMENT for retry

    **Payment methods:**
    - `mobile_money`: Returns `redirect_url` to BANGE payment gateway
    - `card`: Returns `redirect_url` to BANGE card gateway
    - `bank_transfer`: Returns `redirect_url` to BANGE transfer page
    - `cash`: Requires agent validation (`action_type='agent_validation'`)
    - `check`: Requires agent validation (`action_type='agent_validation'`)

    **Post-payment navigation:**
    - `requires_appointment=true`: Frontend should advance to appointment step
    - `redirect_url` set: Frontend should redirect to payment gateway
    - Otherwise: Frontend should navigate to service request detail page
    """,
)
async def initiate_session_payment(
    session_id: str = Path(..., description="The wizard session ID"),
    body: WizardInitiatePaymentRequest = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Atomically persist session and initiate payment."""
    try:
        result = await wizard_session_service.initiate_payment(
            session_id=session_id,
            user_id=current_user.id,
            db=db,
            payment_method=body.payment_method,
            phone_number=body.phone_number,
            user_email=current_user.email,
            user_phone=getattr(current_user, "phone_number", None),
            user_name=f"{getattr(current_user, 'first_name', '') or ''} {getattr(current_user, 'last_name', '') or ''}".strip(),
            treasury_location_id=body.treasury_location_id,
            return_url=body.return_url,
        )

        logger.info(
            f"[WizardAPI] Atomic payment: session={session_id}, "
            f"request_id={result.service_request_id}, "
            f"payment_id={result.payment_id}, "
            f"status={result.payment_status}, "
            f"requires_appointment={result.requires_appointment}"
        )

        return result

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# SITE SELECTION (for ALL workflows, before payment)
# =============================================================================

@router.get(
    "/{session_id}/available-sites",
    summary="Get available processing sites for this workflow",
    description="Returns entity_locations grouped by city for the session's workflow.",
)
async def get_session_available_sites(
    session_id: str = Path(..., description="The wizard session ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get available sites for a workflow via entities.workflow_codes."""
    try:
        session = await wizard_session_service._get_session(session_id, current_user.id)
    except WizardSessionError as e:
        _handle_session_error(e)

    workflow_code = session["workflow_code"]

    from ..services.workflow_engine import resolve_workflow_sites

    try:
        sites = await resolve_workflow_sites(db, workflow_code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Group by city for frontend
    cities: dict = {}
    for site in sites:
        city = site["city"] or "Sin ciudad"
        if city not in cities:
            cities[city] = []
        cities[city].append({
            "id": str(site["id"]),
            "entity_code": site["entity_code"],
            "city": city,
            "location_name": site["location_name"],
            "location_address": site.get("location_address"),
            "is_main_office": site.get("is_main_office", False),
        })

    return {
        "workflow_code": workflow_code,
        "sites": [
            {"id": str(s["id"]), "entity_code": s["entity_code"],
             "city": s["city"] or "Sin ciudad",
             "location_name": s["location_name"],
             "location_address": s.get("location_address"),
             "is_main_office": s.get("is_main_office", False)}
            for s in sites
        ],
        "cities": cities,
        "count": len(sites),
    }


@router.post(
    "/{session_id}/select-site",
    summary="Save site selection to session cache",
    description="Stores the user's site choice for non-appointment workflows.",
)
async def save_session_site_selection(
    session_id: str = Path(..., description="The wizard session ID"),
    body: SiteSelectionRequest = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Save site selection in wizard session cache.

    Validates that the entity_location_id exists, is active, and belongs
    to an entity that handles the session's workflow.
    """
    try:
        # Validate location exists and is active
        location = await db.fetchrow(
            "SELECT entity_code, location_name, city "
            "FROM entity_locations WHERE id = $1 AND is_active = TRUE",
            body.entity_location_id,
        )
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity location not found or inactive.",
            )

        # Validate the location's entity handles this workflow
        session = await wizard_session_service._get_session(session_id, current_user.id)
        workflow_code = session["workflow_code"]
        handles_workflow = await db.fetchval(
            "SELECT 1 FROM entities "
            "WHERE code = $1 AND is_active = TRUE "
            "AND workflow_codes @> to_jsonb($2::text)",
            location["entity_code"], workflow_code,
        )
        if not handles_workflow:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Location entity '{location['entity_code']}' does not handle workflow '{workflow_code}'.",
            )

        site_data = {
            "entity_location_id": str(body.entity_location_id),
            "location_name": body.location_name or location["location_name"],
            "city": body.city or location["city"],
            "entity_code": body.entity_code or location["entity_code"],
        }

        result = await wizard_session_service.save_site_selection(
            session_id=session_id,
            user_id=current_user.id,
            site_data=site_data,
        )

        return {"success": True, "site_selection": result}

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# APPOINTMENT SELECTION (session-based, before payment)
# =============================================================================

@router.get(
    "/{session_id}/appointments/locations",
    response_model=AppointmentLocationsListResponse,
    summary="Get appointment locations for wizard session",
    description="Get available locations based on session's workflow entity code.",
)
async def get_session_appointment_locations(
    session_id: str = Path(..., description="The wizard session ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get appointment locations for a wizard session (before payment)."""
    try:
        session = await wizard_session_service._get_session(session_id, current_user.id)
    except WizardSessionError as e:
        _handle_session_error(e)

    workflow_code = session["workflow_code"]

    # Resolve entity_code for this workflow
    entity_code = await appointment_service.get_entity_code_for_workflow(db, workflow_code)
    if not entity_code:
        return AppointmentLocationsListResponse(
            entity_code=workflow_code,
            locations=[],
            count=0,
        )

    # Get locations with active slot configs
    rows = await db.fetch("""
        SELECT DISTINCT ON (el.city, el.location_name)
            el.id,
            el.entity_code,
            el.location_name,
            el.location_address,
            el.city,
            el.region,
            el.phone,
            el.email,
            el.is_main_office
        FROM entity_locations el
        INNER JOIN appointment_slot_configs asc_cfg ON asc_cfg.entity_location_id = el.id
        WHERE el.entity_code = $1
        AND el.is_active = TRUE
        AND asc_cfg.is_active = TRUE
        ORDER BY el.city, el.location_name, el.id
    """, entity_code)

    locations = [
        EntityLocationResponse(
            id=row['id'],
            entity_code=row['entity_code'],
            location_code=f"{row['entity_code']}_{row['city']}".upper(),
            location_name=row['location_name'],
            city=row['city'],
            province=row['city'],
            region=row['region'],
            address=row['location_address'],
            phone=row['phone'],
            email=row['email'],
            is_main_office=row['is_main_office'] or (row['city'] == 'Malabo'),
        )
        for row in rows
    ]

    return AppointmentLocationsListResponse(
        entity_code=entity_code,
        locations=locations,
        count=len(locations),
    )


@router.get(
    "/{session_id}/appointments/available-days",
    response_model=AvailableDaysListResponse,
    summary="Get days with available slots for calendar view (session-based)",
)
async def get_session_available_days(
    session_id: str = Path(..., description="The wizard session ID"),
    entity_location_id: UUID = Query(..., description="FK to entity_locations table"),
    from_date: Optional[date] = Query(None, description="Start of range"),
    to_date: Optional[date] = Query(None, description="End of range"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get available days for calendar rendering (session-based, before payment)."""
    try:
        await wizard_session_service._get_session(session_id, current_user.id)
    except WizardSessionError as e:
        _handle_session_error(e)

    # Verify location exists
    location = await db.fetchrow("""
        SELECT entity_code, location_name, city
        FROM entity_locations
        WHERE id = $1 AND is_active = TRUE
    """, entity_location_id)

    if not location:
        raise HTTPException(status_code=404, detail="Entity location not found or inactive")

    # Get all slots in range
    slots = await appointment_service.get_available_slots(
        db=db,
        entity_location_id=entity_location_id,
        from_date=from_date,
        limit=500,
    )

    # Group by date
    days_map: dict = {}
    for slot in slots:
        d = slot.slot_date
        if d not in days_map:
            days_map[d] = {"time_slot_count": 0, "total_slots_remaining": 0}
        days_map[d]["time_slot_count"] += 1
        days_map[d]["total_slots_remaining"] += slot.slots_remaining

    if to_date:
        days_map = {d: v for d, v in days_map.items() if d <= to_date}

    days = sorted([
        AvailableDayResponse(slot_date=d, **v) for d, v in days_map.items()
    ], key=lambda x: x.slot_date)

    min_date = slots[0].slot_date if slots else None
    effective_from = from_date or (min_date or date.today())
    effective_to = to_date or (effective_from + timedelta(days=59))

    return AvailableDaysListResponse(
        entity_code=location['entity_code'],
        location_name=location['location_name'],
        from_date=effective_from,
        to_date=effective_to,
        days=days,
        count=len(days),
        min_date=min_date,
    )


@router.get(
    "/{session_id}/appointments/available-slots",
    response_model=AppointmentSlotsListResponse,
    summary="Get available time slots for a location (session-based)",
)
async def get_session_available_slots(
    session_id: str = Path(..., description="The wizard session ID"),
    entity_location_id: UUID = Query(..., description="FK to entity_locations table"),
    from_date: Optional[date] = Query(None, description="Start date"),
    limit: int = Query(20, ge=1, le=100, description="Max slots to return"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get available time slots (session-based, before payment)."""
    try:
        await wizard_session_service._get_session(session_id, current_user.id)
    except WizardSessionError as e:
        _handle_session_error(e)

    # Verify location exists
    location = await db.fetchrow("""
        SELECT entity_code, location_name, city
        FROM entity_locations
        WHERE id = $1 AND is_active = TRUE
    """, entity_location_id)

    if not location:
        raise HTTPException(status_code=404, detail="Entity location not found or inactive")

    slots = await appointment_service.get_available_slots(
        db=db,
        entity_location_id=entity_location_id,
        from_date=from_date,
        limit=limit,
    )

    slot_responses = [
        AvailableSlotResponse(
            slot_date=slot.slot_date,
            slot_time=slot.slot_time,
            location_name=slot.location_name,
            location_address=slot.location_address,
            slots_remaining=slot.slots_remaining,
            city=slot.city or location['city'],
        )
        for slot in slots
    ]

    return AppointmentSlotsListResponse(
        entity_code=location['entity_code'],
        location_name=location['location_name'],
        from_date=from_date or date.today(),
        slots=slot_responses,
        count=len(slot_responses),
        has_availability=len(slot_responses) > 0,
    )


@router.post(
    "/{session_id}/appointments/select",
    summary="Save appointment selection to session cache",
    description="Stores the user's appointment choice without creating a real hold.",
)
async def save_session_appointment_selection(
    session_id: str = Path(..., description="The wizard session ID"),
    body: AppointmentSelectionRequest = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Save appointment selection in wizard session cache (no real hold).

    Validates that entity_location_id exists and is active.
    """
    try:
        # Validate location exists
        location = await db.fetchrow(
            "SELECT entity_code, location_name, city "
            "FROM entity_locations WHERE id = $1 AND is_active = TRUE",
            body.entity_location_id,
        )
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity location not found or inactive.",
            )

        appointment_data = {
            "entity_location_id": str(body.entity_location_id),
            "location_name": body.location_name or location["location_name"],
            "city": body.city or location["city"],
            "appointment_date": str(body.appointment_date),
            "appointment_time": str(body.appointment_time),
            "slot_config_id": str(body.slot_config_id) if body.slot_config_id else None,
        }

        result = await wizard_session_service.save_appointment_data(
            session_id=session_id,
            user_id=current_user.id,
            appointment_data=appointment_data,
        )

        return {"success": True, "appointment_data": result}

    except WizardSessionError as e:
        _handle_session_error(e)


# =============================================================================
# CANCEL SESSION
# =============================================================================

@router.delete(
    "/{session_id}",
    status_code=204,
    summary="Cancel wizard session",
    description="""
    Cancel and delete a wizard session.

    **Effect:**
    - Session is deleted from cache
    - All uploaded documents (in cache) are discarded
    - No database cleanup needed (nothing was persisted)

    **Note:** This is a clean operation since no database records exist.
    """,
)
async def cancel_wizard_session(
    session_id: str = Path(..., description="The wizard session ID"),
    reason: Optional[str] = Query(None, description="Cancellation reason (for logging)"),
    current_user=Depends(get_current_user),
):
    """Cancel and delete wizard session."""
    try:
        await wizard_session_service.cancel_session(
            session_id=session_id,
            user_id=current_user.id,
            reason=reason,
        )

        logger.info(
            f"[WizardAPI] Session cancelled: session={session_id}, "
            f"reason={reason}"
        )

        return None

    except WizardSessionError as e:
        _handle_session_error(e)
