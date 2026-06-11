"""
Batch Requests API Routes — Phase 1 CRUD + Phase 2 Sessions.

Endpoints for creating and managing batch service requests
(N identical requests for N beneficiaries).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File, Form, Body, status as http_status
from typing import Optional, List, Dict, Any
from uuid import UUID
import json

import asyncpg
from loguru import logger

from app.core.events.event_bus import EventBus
from app.core.events.event_types import EventType
from app.database.connection import get_database
from app.modules.auth.dependencies import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.service_requests.models.enums import WorkflowCode

from ..models.batch_request import (
    BatchRequestCreate,
    BatchRequestUpdate,
    BatchRequestItemCreate,
    BatchRequestItemUpdate,
    BatchItemsBulkCreate,
    BatchRequestResponse,
    BatchRequestDetailResponse,
    BatchRequestListResponse,
    BatchRequestItemResponse,
    AgentBatchDetailResponse,
    BulkDecisionRequest,
    BulkDecisionResponse,
    CITIZEN_ALLOWED_STATUS_TRANSITIONS,
)
from ..repositories.batch_repository import batch_repository
from ..services.batch_session_service import (
    batch_session_service,
    BatchSessionError,
    BatchSessionNotFoundError,
)
from ..services.document_classifier import batch_document_classifier
from ..services.batch_persist_service import (
    batch_persist_service,
    BatchPersistError,
)

router = APIRouter(prefix="/batch-requests", tags=["Batch Requests"])

# Mutable batch statuses (citizen can only modify in these states)
_MUTABLE_STATUSES = {"DRAFT", "UPLOADING", "REVIEW"}

# Valid workflow codes (from enum)
_VALID_WORKFLOW_CODES = {wc.value for wc in WorkflowCode}


def _validate_workflow_code(workflow_code: str) -> None:
    """Validate that workflow_code exists in WorkflowCode enum."""
    if workflow_code not in _VALID_WORKFLOW_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Código de trámite '{workflow_code}' no reconocido. "
                   f"Utilice uno de los códigos válidos del sistema."
        )


async def _get_batch_or_404(
    db: asyncpg.Connection,
    batch_id: UUID,
    user_id: UUID,
) -> dict:
    """Fetch batch, check existence and ownership."""
    batch = await batch_repository.find_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if batch["submitted_by"] != user_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return batch


# =============================================================================
# WORKFLOW METADATA (F-005/F-006/F-007)
# =============================================================================


@router.get(
    "/workflows",
    status_code=200,
    summary="Get available workflows for batch requests",
)
async def get_batch_workflows(
    current_user=Depends(get_current_user),
):
    """
    Return all registered workflows with solicitud types and document requirements.
    Used by WorkflowSelection, BeneficiaryForm, and SharedDocuments components.
    """
    from app.modules.service_requests.services.workflow_engine import workflow_engine
    from app.modules.service_requests.models.enums import SolicitudType
    from app.modules.service_requests.workflows.workflow_interface import StepType

    workflows = workflow_engine.get_available_workflows()

    # Enrich each workflow with document requirements + selection fields
    result = []
    for wf_info in workflows:
        code = wf_info["code"]
        workflow = workflow_engine.get_workflow_by_string(code)
        if not workflow:
            continue

        # Get document requirements for each allowed solicitud type
        docs_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for sol_type_str in wf_info.get("allowed_solicitud_types", []):
            try:
                sol_type = SolicitudType(sol_type_str)
                docs = workflow.get_document_requirements(
                    solicitud_type=sol_type,
                    motivo=None,
                    context=None,
                )
                docs_by_type[sol_type_str] = [
                    {
                        "code": d.document_code,
                        "name_es": d.document_name_es,
                        "is_required": d.is_required,
                        "display_order": d.display_order,
                        "instructions_es": d.instructions_es,
                        "accepted_formats": d.accepted_formats,
                    }
                    for d in docs
                ]
            except (ValueError, Exception) as e:
                logger.debug(f"Skip docs for {code}/{sol_type_str}: {e}")

        # F-018: Extract SELECTION step fields (condition fields per beneficiary)
        selection_fields: List[Dict[str, Any]] = []
        try:
            for step in workflow.get_steps():
                if step.step_type != StepType.SELECTION:
                    continue
                cfg = step.config or {}
                sel_key = cfg.get("selection_type", "")
                if not sel_key:
                    continue
                options = cfg.get("options", [])
                # Build condition field descriptor
                field_desc: Dict[str, Any] = {
                    "key": sel_key,
                    "label_es": step.title_es,
                    "type": "radio" if len(options) <= 4 else "select",
                    "options": [
                        {
                            "value": str(opt.get("value", opt.get("id", ""))),
                            "label_es": opt.get("label_es", str(opt.get("value", ""))),
                        }
                        for opt in options
                    ],
                }
                # Include condition (only show this field if parent condition met)
                step_condition = cfg.get("condition")
                if step_condition:
                    field_desc["condition"] = step_condition
                selection_fields.append(field_desc)
        except Exception as e:
            logger.debug(f"Skip selection fields for {code}: {e}")

        result.append({
            "code": code,
            "all_workflow_codes": wf_info.get("all_workflow_codes", [code]),
            "category": wf_info.get("category", "OTROS"),
            "service_name_es": wf_info.get("service_name_es", code),
            "allowed_solicitud_types": wf_info.get("allowed_solicitud_types", []),
            "allowed_sub_types": wf_info.get("allowed_sub_types", []),
            "requires_appointment": wf_info.get("requires_appointment", False),
            "documents_by_solicitud_type": docs_by_type,
            "selection_fields": selection_fields,
        })

    return {"workflows": result, "count": len(result)}


# =============================================================================
# BATCH CRUD
# =============================================================================

@router.post(
    "/",
    response_model=BatchRequestResponse,
    status_code=201,
    summary="Create a new batch request",
)
async def create_batch(
    data: BatchRequestCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Create a new batch request for a given workflow."""
    _validate_workflow_code(data.workflow_code)

    result = await batch_repository.create_batch(
        db=db,
        submitted_by=current_user.id,
        workflow_code=data.workflow_code,
        solicitud_type=data.solicitud_type,
        company_id=data.company_id,
        entity_code=data.entity_code,
        notes=data.notes,
    )
    if not result:
        raise HTTPException(status_code=500, detail="Error al crear el lote")

    logger.info(
        f"Batch created: {result.get('reference')} by user {current_user.id} "
        f"(workflow={data.workflow_code})"
    )
    return result


@router.get(
    "/",
    response_model=BatchRequestListResponse,
    summary="List my batch requests",
)
async def list_batches(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.read")),
):
    """List batch requests for the current user."""
    return await batch_repository.list_batches_by_user(
        db=db,
        user_id=current_user.id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{batch_id}",
    response_model=BatchRequestDetailResponse,
    summary="Get batch request detail with items",
)
async def get_batch(
    batch_id: UUID = Path(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.read")),
):
    """Get a batch request with all its beneficiary items."""
    batch = await _get_batch_or_404(db, batch_id, current_user.id)
    items = await batch_repository.list_items(db, batch_id)
    batch["items"] = items
    return batch


@router.patch(
    "/{batch_id}",
    response_model=BatchRequestResponse,
    summary="Update batch request",
)
async def update_batch(
    data: BatchRequestUpdate,
    batch_id: UUID = Path(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Update batch fields (notes, entity_code). Status changes not allowed via PATCH."""
    batch = await _get_batch_or_404(db, batch_id, current_user.id)

    if batch["status"] not in _MUTABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede modificar un lote en estado {batch['status']}."
        )

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return batch

    result = await batch_repository.update_batch(db, batch_id, **update_data)
    return result


@router.patch(
    "/{batch_id}/status",
    response_model=BatchRequestResponse,
    summary="Advance batch status",
)
async def advance_batch_status(
    batch_id: UUID = Path(...),
    target_status: str = Query(..., alias="status"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Advance batch status with transition validation."""
    batch = await _get_batch_or_404(db, batch_id, current_user.id)
    current_status = batch["status"]

    allowed = CITIZEN_ALLOWED_STATUS_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Transición de estado no permitida: {current_status} → {target_status}. "
                   f"Transiciones válidas: {allowed}"
        )

    result = await batch_repository.update_batch_status(db, batch_id, target_status)
    if not result:
        raise HTTPException(status_code=500, detail="Error al actualizar el estado")

    logger.info(f"Batch {batch.get('reference')} status: {current_status} → {target_status}")
    return result


@router.delete(
    "/{batch_id}",
    status_code=204,
    summary="Delete a batch request",
)
async def delete_batch(
    batch_id: UUID = Path(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Delete a batch request. Only allowed for DRAFT/UPLOADING/REVIEW batches."""
    batch = await _get_batch_or_404(db, batch_id, current_user.id)

    if batch["status"] not in _MUTABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar un lote en estado {batch['status']}. "
                   "Solo DRAFT/UPLOADING/REVIEW."
        )

    deleted = await batch_repository.delete_batch(db, batch_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Error al eliminar el lote")
    logger.info(f"Batch {batch.get('reference')} deleted by user {current_user.id}")


# =============================================================================
# BATCH ITEMS (Beneficiaries) CRUD
# =============================================================================

@router.get(
    "/{batch_id}/items",
    response_model=list[BatchRequestItemResponse],
    summary="List beneficiaries for a batch",
)
async def list_items(
    batch_id: UUID = Path(...),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.read")),
):
    """List all beneficiary items for a batch."""
    await _get_batch_or_404(db, batch_id, current_user.id)
    return await batch_repository.list_items(db, batch_id, status=status_filter)


@router.post(
    "/{batch_id}/items",
    response_model=BatchRequestItemResponse,
    status_code=201,
    summary="Add a beneficiary to a batch",
)
async def add_item(
    data: BatchRequestItemCreate,
    batch_id: UUID = Path(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Add a single beneficiary to the batch."""
    batch = await _get_batch_or_404(db, batch_id, current_user.id)

    if batch["status"] not in _MUTABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"No se pueden agregar beneficiarios a un lote en estado {batch['status']}"
        )

    try:
        return await batch_repository.add_item(
            db=db,
            batch_id=batch_id,
            beneficiary_name=data.beneficiary_name,
            beneficiary_identifier=data.beneficiary_identifier,
            beneficiary_identifier_type=data.beneficiary_identifier_type,
            beneficiary_email=data.beneficiary_email,
            beneficiary_phone=data.beneficiary_phone,
            conditions=data.conditions,
            item_order=data.item_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{batch_id}/items/bulk",
    response_model=list[BatchRequestItemResponse],
    status_code=201,
    summary="Add multiple beneficiaries at once",
)
async def add_items_bulk(
    data: BatchItemsBulkCreate,
    batch_id: UUID = Path(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Add multiple beneficiaries to the batch in one call."""
    batch = await _get_batch_or_404(db, batch_id, current_user.id)

    if batch["status"] not in _MUTABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"No se pueden agregar beneficiarios a un lote en estado {batch['status']}"
        )

    try:
        items_dicts = [item.model_dump() for item in data.items]
        return await batch_repository.add_items_bulk(db, batch_id, items_dicts)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put(
    "/{batch_id}/items/{item_id}",
    response_model=BatchRequestItemResponse,
    summary="Update a beneficiary item",
)
async def update_item(
    data: BatchRequestItemUpdate,
    batch_id: UUID = Path(...),
    item_id: UUID = Path(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Update a beneficiary's details."""
    batch = await _get_batch_or_404(db, batch_id, current_user.id)

    if batch["status"] not in _MUTABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede modificar un lote en estado {batch['status']}"
        )

    item = await batch_repository.find_item_by_id(db, item_id)
    if not item or item["batch_id"] != batch_id:
        raise HTTPException(status_code=404, detail="Beneficiario no encontrado en este lote")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return item

    result = await batch_repository.update_item(db, item_id, **update_data)
    return result


@router.delete(
    "/{batch_id}/items/{item_id}",
    status_code=204,
    summary="Remove a beneficiary from a batch",
)
async def delete_item(
    batch_id: UUID = Path(...),
    item_id: UUID = Path(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Remove a beneficiary from the batch."""
    batch = await _get_batch_or_404(db, batch_id, current_user.id)

    if batch["status"] not in _MUTABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"No se pueden eliminar beneficiarios de un lote en estado {batch['status']}"
        )

    deleted = await batch_repository.delete_item(db, item_id, batch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Beneficiario no encontrado en este lote")
    logger.info(f"Item {item_id} removed from batch {batch.get('reference')}")


# =============================================================================
# SESSION ENDPOINTS (Phase 2 — Redis metadata sessions)
# =============================================================================

def _handle_session_error(e: BatchSessionError):
    """Convert BatchSessionError to HTTPException."""
    if isinstance(e, BatchSessionNotFoundError):
        raise HTTPException(status_code=404, detail=e.message)
    if e.code == "UNAUTHORIZED":
        raise HTTPException(status_code=403, detail=e.message)
    raise HTTPException(status_code=400, detail=e.message)


@router.post(
    "/sessions",
    status_code=201,
    summary="Start a new batch session",
)
async def start_session(
    data: BatchRequestCreate,
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Start a new batch session in Redis.
    No DB writes — session lives in cache with 2h TTL.
    """
    _validate_workflow_code(data.workflow_code)

    try:
        session = await batch_session_service.start_session(
            user_id=current_user.id,
            workflow_code=data.workflow_code,
            solicitud_type=data.solicitud_type,
            company_id=data.company_id,
        )
        return session
    except BatchSessionError as e:
        _handle_session_error(e)


@router.get(
    "/sessions/{session_id}",
    summary="Get batch session state",
)
async def get_session(
    session_id: str = Path(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.read")),
):
    """Get the current state of a batch session."""
    try:
        return await batch_session_service.get_session(session_id, current_user.id)
    except BatchSessionError as e:
        _handle_session_error(e)


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    summary="Cancel batch session",
)
async def cancel_session(
    session_id: str = Path(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Cancel/delete a batch session from cache."""
    try:
        await batch_session_service.delete_session(session_id, current_user.id)
    except BatchSessionError as e:
        _handle_session_error(e)


# =============================================================================
# SESSION BENEFICIARIES
# =============================================================================

@router.post(
    "/sessions/{session_id}/beneficiaries",
    status_code=201,
    summary="Add a beneficiary to session",
)
async def session_add_beneficiary(
    session_id: str = Path(...),
    data: BatchRequestItemCreate = ...,
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Add a single beneficiary to the batch session."""
    try:
        return await batch_session_service.add_beneficiary(
            session_id=session_id,
            user_id=current_user.id,
            name=data.beneficiary_name,
            identifier=data.beneficiary_identifier,
            identifier_type=data.beneficiary_identifier_type,
            email=data.beneficiary_email,
            phone=data.beneficiary_phone,
            conditions=data.conditions,
        )
    except BatchSessionError as e:
        _handle_session_error(e)


@router.post(
    "/sessions/{session_id}/beneficiaries/import",
    summary="Import beneficiaries from CSV",
)
async def session_import_csv(
    session_id: str = Path(...),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Import beneficiaries from a CSV file.

    Expected columns (flexible names):
    - name/nombre/beneficiary_name (required)
    - identifier/numero/passport/dip (optional)
    - identifier_type/tipo (optional)
    - email/correo (optional)
    - phone/telefono (optional)
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CSV (.csv)")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB max
        raise HTTPException(status_code=400, detail="Archivo CSV demasiado grande (max 5MB)")

    try:
        return await batch_session_service.import_beneficiaries_csv(
            session_id=session_id,
            user_id=current_user.id,
            csv_content=content,
        )
    except BatchSessionError as e:
        _handle_session_error(e)


@router.put(
    "/sessions/{session_id}/beneficiaries/{beneficiary_id}",
    summary="Update a beneficiary in session",
)
async def session_update_beneficiary(
    session_id: str = Path(...),
    beneficiary_id: str = Path(...),
    data: BatchRequestItemUpdate = ...,
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Update a beneficiary's details in the session."""
    try:
        updates = data.model_dump(exclude_unset=True)
        # Map model field names to session field names
        field_mapping = {
            "beneficiary_name": "name",
            "beneficiary_identifier": "identifier",
            "beneficiary_identifier_type": "identifier_type",
            "beneficiary_email": "email",
            "beneficiary_phone": "phone",
        }
        mapped = {}
        for key, val in updates.items():
            mapped_key = field_mapping.get(key, key)
            mapped[mapped_key] = val

        return await batch_session_service.update_beneficiary(
            session_id=session_id,
            user_id=current_user.id,
            beneficiary_id=beneficiary_id,
            updates=mapped,
        )
    except BatchSessionError as e:
        _handle_session_error(e)


@router.delete(
    "/sessions/{session_id}/beneficiaries/{beneficiary_id}",
    status_code=204,
    summary="Remove a beneficiary from session",
)
async def session_remove_beneficiary(
    session_id: str = Path(...),
    beneficiary_id: str = Path(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Remove a beneficiary from the session."""
    try:
        await batch_session_service.remove_beneficiary(
            session_id=session_id,
            user_id=current_user.id,
            beneficiary_id=beneficiary_id,
        )
    except BatchSessionError as e:
        _handle_session_error(e)


@router.post(
    "/sessions/{session_id}/beneficiaries/{beneficiary_id}/reorder",
    status_code=200,
    summary="Move a beneficiary up or down (F-022)",
)
async def session_reorder_beneficiary(
    session_id: str = Path(...),
    beneficiary_id: str = Path(...),
    direction: str = Query(..., regex="^(up|down)$"),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Move a beneficiary up or down in the list."""
    try:
        bens = await batch_session_service.reorder_beneficiary(
            session_id=session_id,
            user_id=current_user.id,
            beneficiary_id=beneficiary_id,
            direction=direction,
        )
        return {"beneficiaries": bens}
    except BatchSessionError as e:
        _handle_session_error(e)


# =============================================================================
# SESSION SHARED DOCUMENTS
# =============================================================================

@router.post(
    "/sessions/{session_id}/shared-documents",
    status_code=201,
    summary="Upload a shared document",
)
async def session_upload_shared_document(
    session_id: str = Path(...),
    file: UploadFile = File(...),
    document_code: str = Form(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Upload a shared document to Firebase and register it in the session.
    Shared documents apply to all beneficiaries (e.g., company NIF, power of attorney).
    """
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB max
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (max 50MB)")

    try:
        # Validate ownership
        await batch_session_service.get_session(session_id, current_user.id)

        # Upload to Firebase directly (no base64 in Redis)
        from app.modules.documents.services.storage_service import firebase_storage_service
        upload_result = await firebase_storage_service.upload_user_document(
            user_id=str(current_user.id),
            application_id=f"batch_{session_id}",
            file=content,
            metadata={
                "document_type": document_code,
                "original_filename": file.filename,
                "batch_session_id": session_id,
                "uploadedBy": str(current_user.id),
            },
        )

        # Register metadata reference in session (not the file content)
        doc_ref = await batch_session_service.add_shared_document(
            session_id=session_id,
            user_id=current_user.id,
            document_code=document_code,
            file_path=upload_result.file_path,
            file_name=file.filename or "document",
            file_size=upload_result.file_size,
            mime_type=upload_result.mime_type,
        )
        return doc_ref
    except BatchSessionError as e:
        _handle_session_error(e)


@router.delete(
    "/sessions/{session_id}/shared-documents/{document_code}",
    status_code=204,
    summary="Remove a shared document from session",
)
async def session_remove_shared_document(
    session_id: str = Path(...),
    document_code: str = Path(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """Remove a shared document reference from the session."""
    try:
        await batch_session_service.remove_shared_document(
            session_id=session_id,
            user_id=current_user.id,
            document_code=document_code,
        )
    except BatchSessionError as e:
        _handle_session_error(e)


# =============================================================================
# PHASE 3: CLASSIFICATION AI + MATCHING
# =============================================================================

@router.post(
    "/sessions/{session_id}/classify",
    summary="Upload documents in bulk and classify them",
)
async def session_classify_documents(
    session_id: str = Path(...),
    files: List[UploadFile] = File(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Upload multiple documents, classify them via Gemini Flash,
    and match them to beneficiaries.

    Returns classifications + assignments for user review.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Suba al menos un documento.")

    # Rate limit: max 5 classify calls per user per 10 minutes (Gemini is expensive)
    from app.core.cache import check_rate_limit
    is_allowed, remaining = await check_rate_limit(
        str(current_user.id), "batch_classify", max_requests=5, window_seconds=600
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas solicitudes de clasificación. Intente en unos minutos.",
        )

    MAX_FILES = 200
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
    ALLOWED_MIME_TYPES = {
        "application/pdf", "image/jpeg", "image/png", "image/webp",
        "image/tiff", "image/bmp", "image/gif",
    }

    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_FILES} archivos por llamada.",
        )

    try:
        # Validate session ownership
        session = await batch_session_service.get_session(session_id, current_user.id)

        # Upload to Firebase + prepare for classification
        from app.modules.documents.services.storage_service import firebase_storage_service

        uploaded_docs = []
        for f in files:
            # Validate file type (S-007)
            if f.content_type and f.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tipo de archivo no permitido: '{f.filename}' ({f.content_type}). Solo PDF e imágenes.",
                )

            content = await f.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"Archivo '{f.filename}' excede el límite de 50MB.",
                )

            # Upload to Firebase
            upload_result = await firebase_storage_service.upload_user_document(
                user_id=str(current_user.id),
                application_id=f"batch_{session_id}",
                file=content,
                metadata={
                    "document_type": "batch_individual",
                    "original_filename": f.filename,
                    "batch_session_id": session_id,
                    "uploadedBy": str(current_user.id),
                },
            )

            uploaded_docs.append({
                "content": content,
                "mime_type": upload_result.mime_type,
                "file_path": upload_result.file_path,
                "file_name": f.filename or "document",
            })

        # Run classify + match pipeline
        result = await batch_document_classifier.classify_and_match(
            session_id=session_id,
            user_id=current_user.id,
            uploaded_docs=uploaded_docs,
        )

        logger.info(
            f"[BatchRoutes] classify: session={session_id}, "
            f"docs={len(uploaded_docs)}, stats={result.get('stats')}"
        )
        return result

    except BatchSessionError as e:
        _handle_session_error(e)


@router.put(
    "/sessions/{session_id}/assignments",
    summary="Confirm or modify document-to-beneficiary assignments",
)
async def session_confirm_assignments(
    session_id: str = Path(...),
    assignments: List[Dict[str, Any]] = Body(
        ...,
        description="List of {file_path, document_type, beneficiary_id}",
    ),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Confirm or modify the document-to-beneficiary assignments
    that were proposed by the classifier.

    Each assignment maps a file to a beneficiary and document type.
    """
    if not assignments:
        raise HTTPException(status_code=400, detail="Proporcione al menos una asignación.")

    try:
        result = await batch_document_classifier.confirm_assignments(
            session_id=session_id,
            user_id=current_user.id,
            assignments=assignments,
        )
        return result
    except BatchSessionError as e:
        _handle_session_error(e)


@router.post(
    "/sessions/{session_id}/extract",
    summary="Run full extraction on assigned documents",
)
async def session_extract_documents(
    session_id: str = Path(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Run full OCR extraction on all assigned documents.
    Uses existing GeminiDocumentProcessor with schema validation.

    This should be called after assignments are confirmed.
    """
    try:
        result = await batch_document_classifier.extract_documents(
            session_id=session_id,
            user_id=current_user.id,
        )
        return result
    except BatchSessionError as e:
        _handle_session_error(e)


# =============================================================================
# FORM CONFIG + FORM DATA (DataGrid support)
# =============================================================================

@router.get(
    "/sessions/{session_id}/form-config",
    summary="Get form configuration for DataGrid columns",
)
async def session_get_form_config(
    session_id: str = Path(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.read")),
):
    """
    Get the form configuration for the batch workflow.
    Returns sections and fields that define the DataGrid columns.

    Uses the same form_config as the individual wizard, aggregating
    all form_review steps into a flat list of sections.
    """
    from app.modules.service_requests.services.workflow_engine import workflow_engine
    from app.modules.service_requests.workflows.workflow_interface import (
        WorkflowContext,
        WorkflowCode as WfCode,
    )
    from app.modules.service_requests.models.enums import SolicitudType

    try:
        session = await batch_session_service.get_session(session_id, current_user.id)
        workflow_code = session["workflow_code"]
        solicitud_type = session.get("solicitud_type", "expedicion")

        workflow = workflow_engine.get_workflow_by_string(workflow_code)
        if not workflow:
            raise HTTPException(
                status_code=400,
                detail=f"Workflow '{workflow_code}' no encontrado.",
            )

        # Build a minimal context for form config
        context = WorkflowContext(
            service_request_id=UUID("00000000-0000-0000-0000-000000000000"),
            user_id=current_user.id,
            workflow_code=WfCode(workflow_code),
            solicitud_type=SolicitudType(solicitud_type),
            form_data=session.get("form_data_grid", {}).get("__global__", {}),
        )

        # Aggregate form configs from all form_review steps
        all_sections = []
        seen_section_ids = set()

        steps = workflow.get_steps()
        for step in steps:
            if step.step_type.value == "form_review":
                try:
                    form_config = workflow.get_form_config(step.step_id, context)
                    for section in form_config.sections:
                        if section.id not in seen_section_ids:
                            seen_section_ids.add(section.id)
                            all_sections.append({
                                "id": section.id,
                                "title_es": section.title_es,
                                "source_document": section.source_document,
                                "fields": [
                                    {
                                        "key": f.key,
                                        "label_es": f.label_es,
                                        "type": f.type,
                                        "required": f.required,
                                        "readonly": f.readonly,
                                        "options": f.options,
                                        "placeholder_es": f.placeholder_es,
                                        "validation": f.validation,
                                    }
                                    for f in section.fields
                                ],
                            })
                except Exception as e:
                    logger.warning(
                        f"[BatchRoutes] form-config skip step {step.step_id}: {e}"
                    )

        # Also get form_mapping for extraction→field resolution
        form_mapping = {}
        try:
            form_mapping = workflow.get_form_mapping(context)
        except Exception:
            pass

        return {
            "workflow_code": workflow_code,
            "solicitud_type": solicitud_type,
            "sections": all_sections,
            "form_mapping": form_mapping,
            "total_fields": sum(len(s["fields"]) for s in all_sections),
        }

    except BatchSessionError as e:
        _handle_session_error(e)


@router.put(
    "/sessions/{session_id}/form-data",
    summary="Save batch form data (DataGrid)",
)
async def session_save_form_data(
    session_id: str = Path(...),
    form_data_grid: Dict[str, Dict[str, Any]] = Body(
        ...,
        description='Form data per beneficiary: {"beneficiary_id": {"field": "value", ...}}',
    ),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Save form data for all beneficiaries at once.
    This is called from the DataGrid component when the user saves edits.

    Format: {"beneficiary_id": {"field_key": "value", ...}, ...}
    """
    if not form_data_grid:
        raise HTTPException(status_code=400, detail="Proporcione datos del formulario.")

    try:
        # Validate beneficiary IDs exist
        session = await batch_session_service.get_session(session_id, current_user.id)
        ben_ids = {b["id"] for b in session.get("beneficiaries", [])}

        invalid_ids = set(form_data_grid.keys()) - ben_ids
        if invalid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Beneficiarios no encontrados: {list(invalid_ids)[:5]}",
            )

        await batch_session_service.update_form_data(
            session_id=session_id,
            user_id=current_user.id,
            form_data_grid=form_data_grid,
        )

        return {
            "saved": True,
            "beneficiaries_updated": len(form_data_grid),
        }

    except BatchSessionError as e:
        _handle_session_error(e)


# =============================================================================
# PHASE 4: PAYMENT + ATOMIC SUBMIT
# =============================================================================

@router.post(
    "/sessions/{session_id}/prepare-payment",
    summary="Calculate tariff and determine ready items",
)
async def session_prepare_payment(
    session_id: str = Path(...),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Calculate per-item tariff, identify ready vs excluded beneficiaries,
    and compute total amount.

    Must be called before submit. Stores tariff in session.
    """
    try:
        return await batch_persist_service.prepare_payment(
            session_id=session_id,
            user_id=current_user.id,
        )
    except BatchSessionError as e:
        _handle_session_error(e)


@router.post(
    "/sessions/{session_id}/submit",
    summary="Submit batch: atomic persist + payment",
)
async def session_submit_batch(
    session_id: str = Path(...),
    payment_method: str = Body(..., embed=True),
    phone_number: Optional[str] = Body(None, embed=True),
    user_email: Optional[str] = Body(None, embed=True),
    user_phone: Optional[str] = Body(None, embed=True),
    user_name: Optional[str] = Body(None, embed=True),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("batch_requests.create")),
):
    """
    Atomically submit the batch:
    1. Create batch_request in DB
    2. Create N service_requests (one per ready beneficiary)
    3. Create N*M document records (individual + shared)
    4. Create N service_payments
    5. Initiate 1 payment processor call for total amount

    If anything fails, the entire transaction is rolled back.

    Returns batch details + payment instructions (redirect_url for BANGE,
    action_type for manual/cash payments).
    """
    try:
        result = await batch_persist_service.submit_batch(
            session_id=session_id,
            user_id=current_user.id,
            db=db,
            payment_method=payment_method,
            phone_number=phone_number,
            user_email=user_email,
            user_phone=user_phone,
            user_name=user_name,
        )

        logger.info(
            f"[BatchRoutes] submit: batch={result.get('batch_reference')}, "
            f"requests={result.get('service_requests_created')}, "
            f"payment={result.get('payment_id')}"
        )
        return result

    except BatchPersistError as e:
        status_code = 422 if e.code in {
            "PAYMENT_FAILED", "INVALID_PAYMENT_METHOD", "PHONE_REQUIRED",
            "NO_READY_ITEMS", "NO_PAYMENT_REQUIRED", "NOT_READY", "NO_TARIFF",
        } else 500
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": e.message,
                "code": e.code,
                "details": e.details,
            }
        )
    except BatchSessionError as e:
        _handle_session_error(e)


# =============================================================================
# AGENT BATCH ENDPOINTS
# =============================================================================

async def _get_entity_workflows(db: asyncpg.Connection, entity_code: str) -> list[str]:
    """Get workflow_codes for an entity, raise 404 if not found."""
    entity = await db.fetchrow(
        "SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true",
        entity_code,
    )
    if not entity:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_code} not found",
        )
    workflows = entity["workflow_codes"]
    if isinstance(workflows, str):
        try:
            workflows = json.loads(workflows)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Invalid workflow_codes JSON for entity {entity_code}")
            workflows = []
    return [str(wf) for wf in (workflows or [])]


@router.get(
    "/agent/entity/{entity_code}",
    response_model=BatchRequestListResponse,
    summary="[Agent] List batches for entity",
)
async def agent_list_entity_batches(
    entity_code: str = Path(...),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("service_request.view")),
):
    """List submitted batches whose workflow_code matches the entity."""
    entity_workflows = await _get_entity_workflows(db, entity_code)
    if not entity_workflows:
        return {"batches": [], "total": 0, "page": 1, "page_size": page_size, "total_pages": 0}

    return await batch_repository.list_batches_by_entity(
        db=db,
        entity_workflows=entity_workflows,
        status=status_filter,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/agent/entity/{entity_code}/{batch_id}",
    response_model=AgentBatchDetailResponse,
    summary="[Agent] Get batch detail with live SR statuses",
)
async def agent_get_batch_detail(
    entity_code: str = Path(...),
    batch_id: UUID = Path(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("service_request.view")),
):
    """Get batch detail with items joined to service_requests for live status."""
    entity_workflows = await _get_entity_workflows(db, entity_code)

    batch = await batch_repository.get_batch_detail_for_agent(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    # Verify batch belongs to entity
    if batch["workflow_code"] not in entity_workflows:
        raise HTTPException(status_code=403, detail="Este lote no pertenece a esta entidad")

    return batch


@router.post(
    "/agent/entity/{entity_code}/{batch_id}/bulk-decision",
    response_model=BulkDecisionResponse,
    summary="[Agent] Bulk approve/reject items in a batch",
)
async def agent_bulk_decision(
    entity_code: str = Path(...),
    batch_id: UUID = Path(...),
    body: BulkDecisionRequest = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user), _=Depends(permission_required("service_request.process")),
):
    """
    Bulk approve or reject service requests in a batch.
    If item_ids is None, applies to all pending items.
    """
    entity_workflows = await _get_entity_workflows(db, entity_code)

    batch = await batch_repository.find_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if batch["workflow_code"] not in entity_workflows:
        raise HTTPException(status_code=403, detail="Este lote no pertenece a esta entidad")

    if body.decision == "reject" and not body.rejection_reason:
        raise HTTPException(status_code=400, detail="Motivo de rechazo obligatorio")

    # Get eligible service_request_ids from batch items
    if body.item_ids:
        items = await db.fetch("""
            SELECT bi.id, bi.service_request_id, bi.beneficiary_name
            FROM batch_request_items bi
            WHERE bi.batch_id = $1 AND bi.id = ANY($2::uuid[])
            AND bi.service_request_id IS NOT NULL
        """, batch_id, body.item_ids)
    else:
        # All pending items (SR status = submitted/pending_review)
        items = await db.fetch("""
            SELECT bi.id, bi.service_request_id, bi.beneficiary_name
            FROM batch_request_items bi
            JOIN service_requests sr ON sr.id = bi.service_request_id
            WHERE bi.batch_id = $1
            AND bi.service_request_id IS NOT NULL
            AND sr.status::text IN ('submitted', 'pending_review', 'SUBMITTED', 'PENDING_REVIEW')
        """, batch_id)

    processed = 0
    failed = 0
    errors = []

    for item in items:
        sr_id = item["service_request_id"]
        try:
            if body.decision == "approve":
                await db.execute("""
                    UPDATE service_requests
                    SET status = 'DOSSIER_VALIDE',
                        agent_decision = 'approved',
                        agent_comments = $2,
                        validated_by = $3,
                        validated_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                """, sr_id, body.comments, str(current_user.id))
            else:
                await db.execute("""
                    UPDATE service_requests
                    SET status = 'REJECTED',
                        agent_decision = 'rejected',
                        rejection_reason = $2,
                        agent_comments = $3,
                        validated_by = $4,
                        validated_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                """, sr_id, body.rejection_reason, body.comments, str(current_user.id))

            # Insert history entry for audit trail (B-011 fix)
            await db.execute("""
                INSERT INTO service_request_history
                (service_request_id, action, performed_by, details)
                VALUES ($1, $2, $3, $4::jsonb)
            """,
                sr_id,
                "batch_" + body.decision,
                current_user.id,
                json.dumps({
                    "batch_id": str(batch_id),
                    "batch_reference": batch.get("reference"),
                    "decision": body.decision,
                    "comments": body.comments,
                    "rejection_reason": body.rejection_reason,
                }),
            )

            # Complete agent_work_queue item if exists
            await db.execute("""
                UPDATE agent_work_queue
                SET status = 'completed',
                    result_status = $2,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE item_id = $1::text
                AND item_type = 'service_request'
                AND status IN ('assigned', 'pending')
            """, str(sr_id), "approved" if body.decision == "approve" else "rejected")

            processed += 1
        except Exception as e:
            failed += 1
            errors.append({
                "item_id": str(item["id"]),
                "beneficiary": item["beneficiary_name"],
                "error": str(e),
            })

    # Check if batch is now complete
    batch_completed = False
    if processed > 0:
        batch_completed = await batch_repository.check_and_complete_batch(db, batch_id)
        if batch_completed:
            logger.info(f"Batch {batch.get('reference')} auto-completed after bulk decision")
            # Publish BATCH_COMPLETED event for notification email
            try:
                batch_detail = await db.fetchrow("""
                    SELECT br.reference, br.workflow_code, br.total_items,
                           br.total_amount, br.currency, br.submitted_by,
                           u.email, u.full_name
                    FROM batch_requests br
                    LEFT JOIN users u ON u.id = br.submitted_by
                    WHERE br.id = $1
                """, batch_id)
                if batch_detail:
                    EventBus.publish_nowait(EventType.BATCH_COMPLETED, {
                        "batch_id": str(batch_id),
                        "batch_reference": batch_detail["reference"],
                        "user_id": str(batch_detail["submitted_by"]),
                        "user_email": batch_detail["email"],
                        "user_name": batch_detail["full_name"] or "",
                        "workflow_code": batch_detail["workflow_code"],
                        "total_items": batch_detail["total_items"],
                        "amount": float(batch_detail["total_amount"] or 0),
                        "currency": batch_detail["currency"] or "XAF",
                        "preferred_language": "es",
                    })
            except Exception as e:
                logger.error(f"Failed to publish BATCH_COMPLETED for bulk-decision {batch_id}: {e}")

    logger.info(
        f"[AgentBatch] bulk-decision: batch={batch.get('reference')}, "
        f"decision={body.decision}, processed={processed}, failed={failed}"
    )

    return BulkDecisionResponse(
        processed=processed,
        failed=failed,
        errors=errors,
        batch_completed=batch_completed,
    )


# =========================================================================
# B-022: Cron cleanup for expired batch sessions
# =========================================================================

@router.post("/cron/cleanup-expired-sessions", status_code=200)
async def cleanup_expired_batch_sessions():
    """
    Cron endpoint to clean up expired batch sessions from Redis.
    Called by Cloud Scheduler (no auth — secured by IAM).

    Redis TTL already expires keys, but this proactively scans for
    sessions stuck in intermediate states (CLASSIFYING, SUBMITTING)
    that may have orphaned Firebase uploads.
    """
    from app.core.cache import get_cache

    cache = get_cache()
    cleaned = 0

    try:
        from ..services.batch_session_service import BATCH_SESSION_PREFIX, BATCH_SESSION_TTL
        redis_client = await cache._backend._get_client()
        cursor = 0
        pattern = f"{BATCH_SESSION_PREFIX}*"

        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            for key in keys:
                ttl = await redis_client.ttl(key)
                if ttl == -1:
                    # Key exists but has no TTL (shouldn't happen, but fix it)
                    await redis_client.expire(key, BATCH_SESSION_TTL)
                    cleaned += 1
            if cursor == 0:
                break

    except Exception as e:
        logger.warning(f"[BatchCleanup] Redis scan failed (non-critical): {e}")

    logger.info(f"[BatchCleanup] Scanned sessions, fixed {cleaned} missing TTLs")
    return {"cleaned": cleaned}
