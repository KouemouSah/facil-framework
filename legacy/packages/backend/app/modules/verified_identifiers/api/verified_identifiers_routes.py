"""
API Routes for Verified Identifiers

Endpoints for:
- Batch importing verified identifiers (admin)
- Statistics and monitoring (admin)
- Manual verification by agents
- Re-verification triggers
- Identity verification page for agents (CNEDOGE)

Last updated: 2026-01-28 10:02 - Force redeploy to fix 422/func error
"""

from datetime import datetime
from typing import Optional, List
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from pydantic import BaseModel, Field
from loguru import logger

from app.database.connection import get_db_pool
from app.modules.auth.dependencies import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.users.models.user import UserResponse as User
from app.modules.documents.services.storage_service import firebase_storage_service, ensure_storage_initialized

from ..services.verification_service import VerificationService
from ..services.batch_import_service import BatchImportService, BatchImportError
from ..services.crypto_service import get_crypto_service
from ..repositories.verified_identifiers_repository import VerifiedIdentifiersRepository
from ..models.verified_identifier import (
    BatchImportResult,
    ManualVerificationRequest,
    ReVerificationRequest,
    VerificationStatsResponse,
    VerificationQueueStats,
    VerificationConfigResponse,
    ServiceRequestVerificationResult,
    IdentifierType,
    VerificationSource,
)

router = APIRouter(prefix="/verified-identifiers", tags=["Verified Identifiers"])


# =============================================================================
# DEBUG ENDPOINT - Test if router is working
# =============================================================================

# =============================================================================
# DEPENDENCIES
# =============================================================================

async def get_verification_service() -> VerificationService:
    """Get verification service instance."""
    pool = await get_db_pool()
    return VerificationService(pool)


async def get_batch_import_service() -> BatchImportService:
    """Get batch import service instance."""
    pool = await get_db_pool()
    return BatchImportService(pool)


async def get_repository() -> VerifiedIdentifiersRepository:
    """Get repository instance."""
    pool = await get_db_pool()
    return VerifiedIdentifiersRepository(pool)


# =============================================================================
# ACCESS CONTROL HELPERS
# =============================================================================

# Statuts où les vérifications sont pertinentes (après paiement, en traitement)
VERIFICATION_ELIGIBLE_STATUSES = [
    'PAID', 'IN_PROGRESS', 'CITA_SCHEDULED', 'UNDER_REVIEW',
    'SUBMITTED', 'DOSSIER_VALIDE', 'PENDING_APPOINTMENT'
]

# Statuts à exclure (brouillon, annulé, terminé, paiement en attente)
VERIFICATION_EXCLUDED_STATUSES = [
    'DRAFT', 'PAYMENT_PENDING', 'PAYMENT_PROCESSING', 'PAYMENT_FAILED',
    'COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED'
]


async def check_user_has_view_all_permission(conn, user_id: UUID) -> bool:
    """
    Check if user has 'service_request.view_all' permission (supervisor).

    Schema uses:
    - users.role_id -> roles.id (direct reference, not user_roles table)
    - role_permissions -> permissions
    - user_permissions -> permissions (direct user overrides)
    """
    result = await conn.fetchval("""
        SELECT EXISTS (
            -- Check direct user permission override
            SELECT 1 FROM user_permissions up
            JOIN permissions p ON p.id = up.permission_id
            WHERE up.user_id = $1 AND p.name = 'service_request.view_all' AND up.granted = true
            UNION
            -- Check permission via role (users.role_id -> roles -> role_permissions -> permissions)
            SELECT 1 FROM users u
            JOIN role_permissions rp ON rp.role_id = u.role_id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE u.id = $1 AND p.name = 'service_request.view_all' AND rp.granted = true
        )
    """, user_id)
    return result or False


async def get_user_entity_code(conn, user_id: UUID) -> Optional[str]:
    """
    Get the entity code for a user via their agent_profile.
    """
    result = await conn.fetchval("""
        SELECT e.code
        FROM agent_profiles ap
        JOIN entities e ON e.id = ap.entity_id
        WHERE ap.user_id = $1 AND ap.is_active = true
        LIMIT 1
    """, user_id)
    return result


async def check_verification_access(
    conn,
    request_id: UUID,
    user_id: UUID,
    has_view_all: bool
) -> bool:
    """
    Check if user has access to verify a specific service request.

    - Agent normal: must be assigned to the request
    - Supervisor (has_view_all): request must be in their entity

    Returns True if access granted, False otherwise.
    """
    if has_view_all:
        # Supervisor: check if request is in their entity
        user_entity_code = await get_user_entity_code(conn, user_id)
        if not user_entity_code:
            return False

        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM service_requests sr
                JOIN entities e ON e.code = sr.entity_code OR sr.workflow_code = ANY(e.workflow_codes)
                WHERE sr.id = $1 AND e.code = $2
            )
        """, request_id, user_entity_code)
        return result or False
    else:
        # Agent: must be assigned to this request
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM service_requests
                WHERE id = $1 AND assigned_to = $2
            )
        """, request_id, user_id)
        return result or False


def build_access_filter_sql(has_view_all: bool, user_entity_code: Optional[str], user_id: UUID) -> tuple:
    """
    Build SQL WHERE clause for filtering verifications by access.

    Returns (sql_fragment, params_dict)
    """
    if has_view_all and user_entity_code:
        # Supervisor: see all verifications in their entity
        return (
            "AND (sr.entity_code = ${{entity_param}} OR sr.workflow_code = ANY("
            "SELECT unnest(workflow_codes) FROM entities WHERE code = ${{entity_param}}"
            "))",
            {"entity_code": user_entity_code}
        )
    else:
        # Agent: see only their assigned requests
        return (
            "AND sr.assigned_to = ${{user_param}}",
            {"user_id": user_id}
        )


# =============================================================================
# BATCH IMPORT ENDPOINTS (Admin only)
# =============================================================================

@router.post(
    "/import",
    response_model=BatchImportResult,
    dependencies=[Depends(permission_required("identifiers.import"))],
    summary="Import verified identifiers from file"
)
async def import_batch(
    file: UploadFile = File(..., description="CSV or JSON file with identifiers"),
    source: str = Form(..., description="Source: cnedoge, trafico, hacienda, ornc, registro_civil"),
    identifier_type: str = Form(..., description="Type: dni, pasaporte, permiso_residencia, nif, cuve, etc."),
    current_user: User = Depends(get_current_user),
    service: BatchImportService = Depends(get_batch_import_service)
):
    """
    Import batch of verified identifiers from external sources.

    **Admin only** - Requires `identifiers.import` permission.

    Supported formats:
    - **CSV**: `identifier,expires_at,metadata`
    - **JSON**: `{"identifiers": [{"identifier": "...", "expires_at": "...", "metadata": {...}}]}`

    Sources: cnedoge, trafico, hacienda, ornc, registro_civil, ministerio_funcion_publica

    Identifier types: dni, pasaporte, permiso_residencia, nif, cuve, matricula_vehiculo,
    certificado_conducir, registro_civil, contrato_ornc
    """
    content = await file.read()

    # Determine format from filename
    filename = file.filename or ""
    if filename.endswith(".csv"):
        file_format = "csv"
    elif filename.endswith(".json"):
        file_format = "json"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be .csv or .json"
        )

    try:
        result = await service.import_batch(
            file_content=content,
            file_format=file_format,
            source=source,
            identifier_type=identifier_type,
            imported_by=str(current_user.id)
        )
        return result

    except BatchImportError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Batch import failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import failed. Check file format and try again."
        )


@router.post(
    "/import/validate",
    dependencies=[Depends(permission_required("identifiers.import"))],
    summary="Validate import file without importing"
)
async def validate_import_file(
    file: UploadFile = File(..., description="CSV or JSON file to validate"),
    service: BatchImportService = Depends(get_batch_import_service)
):
    """
    Validate an import file without actually importing.

    Returns record count, sample records, and any parse errors.
    """
    content = await file.read()
    filename = file.filename or ""

    if filename.endswith(".csv"):
        file_format = "csv"
    elif filename.endswith(".json"):
        file_format = "json"
    else:
        return {"valid": False, "error": "File must be .csv or .json"}

    return await service.validate_file(content, file_format)


# =============================================================================
# STATISTICS ENDPOINTS (Admin only)
# =============================================================================

@router.get(
    "/stats",
    response_model=VerificationStatsResponse,
    dependencies=[Depends(permission_required("identifiers.stats"))],
    summary="Get verified identifiers statistics"
)
async def get_stats(
    repo: VerifiedIdentifiersRepository = Depends(get_repository)
):
    """
    Get statistics about verified identifiers.

    No sensitive data is exposed - only counts by type and source.
    """
    stats = await repo.get_stats()
    return VerificationStatsResponse(
        total_identifiers=stats["total_identifiers"],
        by_type=stats["by_type"],
        by_source=stats["by_source"],
        active_count=stats["active_count"],
        expired_count=stats["expired_count"],
        expiring_soon=stats["expiring_soon"]
    )


@router.get(
    "/queue/stats",
    response_model=VerificationQueueStats,
    dependencies=[Depends(permission_required("identifiers.stats"))],
    summary="Get verification queue statistics"
)
async def get_queue_stats(
    repo: VerifiedIdentifiersRepository = Depends(get_repository)
):
    """
    Get statistics about the verification queue.
    """
    stats = await repo.get_queue_stats()
    return VerificationQueueStats(**stats)


# =============================================================================
# CONFIGURATION ENDPOINTS (Admin only)
# =============================================================================

@router.get(
    "/config",
    response_model=List[VerificationConfigResponse],
    dependencies=[Depends(permission_required("identifiers.config"))],
    summary="Get document verification configurations"
)
async def get_verification_configs(
    active_only: bool = Query(True, description="Only return active configurations"),
    repo: VerifiedIdentifiersRepository = Depends(get_repository)
):
    """
    Get all document verification configurations.

    Shows which document types are verified and how identifiers are extracted.
    """
    configs = await repo.get_active_configs()
    return [VerificationConfigResponse(
        id=str(c["id"]),
        document_code=c["document_code"],
        identifier_type=c["identifier_type"],
        extraction_paths=c["extraction_paths"],
        source=c["source"],
        is_required=c["is_required"],
        normalization_regex=c.get("normalization_regex"),
        is_active=c["is_active"]
    ) for c in configs]


# =============================================================================
# AGENT VERIFICATION QUEUE ENDPOINTS
# =============================================================================


class ExtractedIdentifier(BaseModel):
    """Single extracted identifier with verification status"""
    identifier_type: str
    value: str
    document_code: str
    document_name: str
    confidence: Optional[float] = None
    expires_at: Optional[str] = None
    status: str = "pending"  # pending, verified, verified_manually, rejected, fraud
    verified_at: Optional[str] = None
    source: Optional[str] = None


class PendingVerificationItem(BaseModel):
    """Item in the pending verification list"""
    id: str
    reference: str
    workflow_code: str
    solicitud_type: str
    status: str
    verification_status: str
    citizen_name: str
    submitted_at: Optional[str] = None
    identifiers: List[ExtractedIdentifier] = []
    pending_count: int = 0
    verified_count: int = 0
    documents_count: int = 0


class PendingVerificationListResponse(BaseModel):
    """Response for pending verification list"""
    items: List[PendingVerificationItem]
    total: int
    page: int
    page_size: int


# =============================================================================
# VERIFICATION DETAIL MODELS
# =============================================================================

class DocumentInfo(BaseModel):
    """Document information for verification detail"""
    id: str
    document_code: str
    document_name: str
    file_path: str
    file_name: str
    file_url: Optional[str] = None  # Signed URL for document access
    mime_type: Optional[str] = None
    extraction_data: Optional[dict] = None
    extraction_confidence: Optional[float] = None
    extraction_status: Optional[str] = None


class VerificationDetailResponse(BaseModel):
    """Detailed verification info for a service request"""
    id: str
    reference: str
    workflow_code: str
    solicitud_type: str
    status: str
    verification_status: str
    citizen_name: str
    citizen_email: Optional[str] = None
    submitted_at: Optional[str] = None
    documents: List[DocumentInfo] = []
    identifiers: List[ExtractedIdentifier] = []
    verification_details: Optional[dict] = None
    previous_id: Optional[str] = None
    next_id: Optional[str] = None


# =============================================================================
# VERIFICATION ACTION MODELS
# =============================================================================

class VerifyIdentifierRequest(BaseModel):
    """Request to verify a single identifier"""
    identifier_type: str = Field(..., description="Type: dni, pasaporte, registro_civil, etc.")
    identifier_value: str = Field(..., description="The identifier value to verify")
    expires_at: Optional[str] = Field(None, description="Expiration date from document (ISO format)")
    notes: Optional[str] = Field(None, max_length=500, description="Agent notes")


class VerifyIdentifierResponse(BaseModel):
    """Response after verifying an identifier"""
    verified_identifier_id: str
    identifier_type: str
    status: str  # verified_manually
    all_verified: bool  # True if all identifiers are now verified
    request_verification_status: str  # Updated status of the service request


class VerifyBatchRequest(BaseModel):
    """Request to verify multiple identifiers at once"""
    identifiers: List[VerifyIdentifierRequest]
    notes: Optional[str] = Field(None, max_length=500, description="Common notes for all")


class VerifyBatchResponse(BaseModel):
    """Response after batch verification"""
    verified_count: int
    failed_count: int
    results: List[dict]  # Details per identifier
    all_verified: bool
    request_verification_status: str


class RejectIdentifierRequest(BaseModel):
    """Request to reject an identifier"""
    identifier_type: str = Field(..., description="Type: dni, pasaporte, etc.")
    identifier_value: str = Field(..., description="The identifier value to reject")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for rejection")
    is_fraud: bool = Field(False, description="Mark as fraud (deactivates in cache)")


@router.get(
    "/pending",
    response_model=PendingVerificationListResponse,
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="List service requests pending identity verification"
)
async def list_pending_verifications(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    verification_status: str = Query("pending", description="Filter by verification status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    List service requests that need identity verification for a specific entity.

    ACCESS CONTROL:
    - Supervisor (has service_request.view_all): sees all verifications in their entity
    - Agent: sees only verifications for requests assigned to them

    FILTERING:
    - Only shows requests after payment (excludes DRAFT, PAYMENT_PENDING, etc.)
    - Only shows requests with matching verification_status
    """
    pool = await get_db_pool()
    crypto = get_crypto_service()

    async with pool.acquire() as conn:
        # Check user access level
        user_id = UUID(str(current_user.id))
        has_view_all = await check_user_has_view_all_permission(conn, user_id)

        logger.info(f"User {current_user.email} listing verifications (supervisor={has_view_all})")

        # Get entity's workflow codes
        entity = await conn.fetchrow("""
            SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
        """, entity_code)

        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_code} not found"
            )

        # Parse workflow_codes from JSONB
        workflow_codes = entity['workflow_codes']
        if isinstance(workflow_codes, str):
            workflow_codes = json.loads(workflow_codes)
        if not workflow_codes:
            workflow_codes = []
        workflow_codes = [str(wf) for wf in workflow_codes] if workflow_codes else []

        if not workflow_codes:
            return PendingVerificationListResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size
            )

        # Get document_verification_config for this entity's source
        configs = await conn.fetch("""
            SELECT document_code, identifier_type, extraction_paths, source
            FROM document_verification_config
            WHERE is_active = true
        """)
        config_map = {c['document_code']: dict(c) for c in configs}

        # Build access filter based on user role
        # Supervisor: can see all in entity; Agent: only their assigned requests
        if has_view_all:
            # Supervisor sees all verifications (no assignment filter)
            access_filter = ""
            access_params = [workflow_codes, verification_status]
        else:
            # Agent sees only their assigned requests
            access_filter = "AND sr.assigned_to = $3"
            access_params = [workflow_codes, verification_status, user_id]

        # Status filter: exclude drafts, payment pending, completed, cancelled
        status_filter = "AND sr.status::text NOT IN ('DRAFT', 'PAYMENT_PENDING', 'PAYMENT_PROCESSING', 'PAYMENT_FAILED', 'COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED')"

        # Get total count with access control
        count_query = f"""
            SELECT COUNT(*) as total
            FROM service_requests sr
            WHERE sr.workflow_code = ANY($1)
              {status_filter}
              AND sr.verification_status = $2
              {access_filter}
        """
        total_row = await conn.fetchrow(count_query, *access_params)
        total = total_row['total'] if total_row else 0

        # Get paginated items with citizen name, documents and extraction data
        offset = (page - 1) * page_size

        # Add pagination params
        if has_view_all:
            query_params = [workflow_codes, verification_status, page_size, offset]
            limit_placeholder = "$3"
            offset_placeholder = "$4"
        else:
            query_params = [workflow_codes, verification_status, user_id, page_size, offset]
            limit_placeholder = "$4"
            offset_placeholder = "$5"

        query = f"""
            SELECT
                sr.id,
                sr.reference,
                sr.workflow_code,
                sr.solicitud_type,
                sr.status::text as status,
                sr.verification_status,
                sr.verification_details,
                sr.submitted_at,
                sr.form_data,
                COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as citizen_name
            FROM service_requests sr
            JOIN users u ON u.id = sr.user_id
            WHERE sr.workflow_code = ANY($1)
              {status_filter}
              AND sr.verification_status = $2
              {access_filter}
            ORDER BY sr.submitted_at ASC NULLS LAST
            LIMIT {limit_placeholder} OFFSET {offset_placeholder}
        """
        rows = await conn.fetch(query, *query_params)

        items = []
        for row in rows:
            # Get documents with extraction data
            docs = await conn.fetch("""
                SELECT id, document_code, document_name, extraction_data,
                       extraction_confidence, extraction_status
                FROM service_request_documents
                WHERE service_request_id = $1
            """, row['id'])

            # Parse verification_details to check individual identifier status
            verification_details = row['verification_details'] or {}
            if isinstance(verification_details, str):
                verification_details = json.loads(verification_details)

            # Extract identifiers from documents
            identifiers = []
            for doc in docs:
                doc_code = doc['document_code']
                config = config_map.get(doc_code)
                if not config:
                    continue

                extraction_data = doc['extraction_data'] or {}
                if isinstance(extraction_data, str):
                    extraction_data = json.loads(extraction_data)

                if not extraction_data:
                    continue

                identifier_type = config['identifier_type']
                extraction_paths = config['extraction_paths']

                # Try each path to find the identifier value
                identifier_value = None
                expires_at = None
                for path in extraction_paths:
                    keys = path.split('.')
                    value = extraction_data
                    for key in keys:
                        if isinstance(value, dict) and key in value:
                            value = value[key]
                        else:
                            value = None
                            break
                    if value:
                        identifier_value = str(value)
                        break

                # Look for expiration date in common paths
                for exp_path in ['fecha_expiracion', 'expires_at', 'expiry_date']:
                    if exp_path in extraction_data:
                        expires_at = extraction_data[exp_path]
                        break

                if identifier_value:
                    # Check individual identifier status in verification_details
                    id_status = verification_details.get(identifier_type, {}).get('status', 'pending')

                    # If not in verification_details, check against cache
                    verified_at = None
                    source = None
                    if id_status == 'pending':
                        try:
                            blind_index = crypto.compute_blind_index(identifier_value, identifier_type)
                            cache_check = await conn.fetchrow("""
                                SELECT id, is_active, verified_at, source, expires_at
                                FROM verified_identifiers
                                WHERE blind_index = $1 AND identifier_type = $2
                            """, blind_index, identifier_type)
                            if cache_check:
                                if cache_check['is_active']:
                                    id_status = 'verified'
                                    verified_at = cache_check['verified_at'].isoformat() if cache_check['verified_at'] else None
                                    source = cache_check['source']
                                else:
                                    id_status = 'fraud'  # Deactivated in cache
                        except Exception as e:
                            logger.warning(f"Cache check failed for {identifier_type}: {e}")

                    identifiers.append(ExtractedIdentifier(
                        identifier_type=identifier_type,
                        value=identifier_value,
                        document_code=doc_code,
                        document_name=doc['document_name'] or doc_code,
                        confidence=float(doc['extraction_confidence']) if doc['extraction_confidence'] else None,
                        expires_at=expires_at,
                        status=id_status,
                        verified_at=verified_at,
                        source=source
                    ))

            # Also extract from form_data for common identifiers
            form_data = row['form_data'] or {}
            if isinstance(form_data, str):
                form_data = json.loads(form_data)

            # Check form_data for dni/passport (common structure)
            for section_key in ['dip', 'pasaporte_antiguo', 'certificado_nacimiento']:
                section = form_data.get(section_key, {})
                if isinstance(section, dict):
                    for field_key, id_type in [('numero_dip', 'dni'), ('numero_pasaporte', 'pasaporte')]:
                        if field_key in section and section[field_key]:
                            # Check if already extracted from documents
                            existing = [i for i in identifiers if i.identifier_type == id_type and i.value == section[field_key]]
                            if not existing:
                                id_status = 'pending'
                                try:
                                    blind_index = crypto.compute_blind_index(section[field_key], id_type)
                                    cache_check = await conn.fetchrow("""
                                        SELECT id, is_active, verified_at, source
                                        FROM verified_identifiers
                                        WHERE blind_index = $1 AND identifier_type = $2
                                    """, blind_index, id_type)
                                    if cache_check:
                                        id_status = 'verified' if cache_check['is_active'] else 'fraud'
                                except Exception:
                                    pass

                                identifiers.append(ExtractedIdentifier(
                                    identifier_type=id_type,
                                    value=section[field_key],
                                    document_code=section_key,
                                    document_name=section_key.replace('_', ' ').title(),
                                    confidence=None,
                                    expires_at=section.get('fecha_expiracion'),
                                    status=id_status
                                ))

            # Count pending vs verified
            pending_count = len([i for i in identifiers if i.status == 'pending'])
            verified_count = len([i for i in identifiers if i.status in ('verified', 'verified_manually')])

            # Safely extract values, handling None cases
            citizen_name_raw = row['citizen_name']
            citizen_name = (citizen_name_raw.strip() if citizen_name_raw else 'N/A') or 'N/A'

            items.append(PendingVerificationItem(
                id=str(row['id']),
                reference=row['reference'] or '',
                workflow_code=row['workflow_code'] or '',
                solicitud_type=row['solicitud_type'] or '',
                status=str(row['status']) if row['status'] else 'submitted',
                verification_status=row['verification_status'] or 'pending',
                citizen_name=citizen_name,
                submitted_at=row['submitted_at'].isoformat() if row['submitted_at'] else None,
                identifiers=identifiers,
                pending_count=pending_count,
                verified_count=verified_count,
                documents_count=len(docs)
            ))

        return PendingVerificationListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )


# =============================================================================
# MANUAL VERIFICATION ENDPOINTS (Agents)
# =============================================================================

@router.post(
    "/requests/{request_id}/verify-manually",
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="Manually verify a service request"
)
async def verify_manually(
    request_id: str,
    body: ManualVerificationRequest,
    current_user: User = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service)
):
    """
    Agent manually marks a service request as verified.

    Use this when:
    - The identifier is valid but not in the external database yet
    - External verification is not available
    - Agent has confirmed authenticity through other means
    """
    try:
        await service.manual_verification(
            request_id=request_id,
            verified_by=str(current_user.id),
            notes=body.notes,
            identifier_types=body.identifier_types
        )
        return {"status": "verified_manually", "request_id": request_id}

    except Exception as e:
        logger.error(f"Manual verification failed for {request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {e}"
        )


@router.post(
    "/requests/{request_id}/re-verify",
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="Trigger re-verification of a service request"
)
async def re_verify(
    request_id: str,
    body: Optional[ReVerificationRequest] = None,
    current_user: User = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service)
):
    """
    Agent triggers re-verification of a service request.

    Use this when:
    - External data has been updated
    - Previous verification failed due to technical issues
    - Manual verification needs to be replaced with automatic
    """
    try:
        queue_id = await service.queue_for_verification(request_id)
        return {
            "status": "queued",
            "queue_id": queue_id,
            "request_id": request_id,
            "message": "Re-verification queued successfully"
        }

    except Exception as e:
        logger.error(f"Re-verification failed for {request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Re-verification failed: {e}"
        )


@router.get(
    "/requests/{request_id}/verification-status",
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="Get verification status for a service request"
)
async def get_verification_status(
    request_id: str,
    service: VerificationService = Depends(get_verification_service)
):
    """
    Get the current verification status and details for a service request.
    """
    query = """
        SELECT verification_status, verification_details, updated_at
        FROM service_requests
        WHERE id = $1
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, request_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found"
        )

    return {
        "request_id": request_id,
        "status": row["verification_status"],
        "details": row["verification_details"],
        "updated_at": row["updated_at"]
    }


# =============================================================================
# TRIGGER VERIFICATION (Internal/Background)
# =============================================================================

@router.post(
    "/requests/{request_id}/verify",
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="Trigger verification for a service request"
)
async def trigger_verification(
    request_id: str,
    current_user: User = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service)
):
    """
    Manually trigger verification for a service request.

    This runs the verification immediately (synchronous).
    For background processing, use /re-verify instead.
    """
    try:
        result = await service.verify_service_request(
            request_id=request_id,
            performed_by=str(current_user.id)
        )
        return {
            "request_id": request_id,
            "status": result.status.value,
            "results": {k: v.model_dump() for k, v in result.results.items()},
            "errors": result.errors
        }

    except Exception as e:
        logger.error(f"Verification failed for {request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {e}"
        )


# =============================================================================
# IDENTITY VERIFICATION PAGE ENDPOINTS (Agent CNEDOGE)
# =============================================================================

@router.get(
    "/requests/{request_id}/verification-details",
    response_model=VerificationDetailResponse,
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="Get detailed verification info with navigation"
)
async def get_verification_details(
    request_id: str,
    entity_code: str = Query(..., description="Entity code for navigation context"),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed verification information for a service request.

    ACCESS CONTROL:
    - Supervisor (has service_request.view_all): can access any request in their entity
    - Agent: can only access requests assigned to them

    Includes:
    - Request details (reference, citizen, status)
    - All documents with URLs and extraction data
    - All extracted identifiers with individual status
    - Navigation to previous/next pending request
    """
    pool = await get_db_pool()
    crypto = get_crypto_service()

    async with pool.acquire() as conn:
        # Check user access
        user_id = UUID(str(current_user.id))
        has_view_all = await check_user_has_view_all_permission(conn, user_id)

        # Verify access to this specific request
        has_access = await check_verification_access(conn, UUID(request_id), user_id, has_view_all)
        if not has_access:
            logger.warning(f"User {current_user.email} denied access to verification {request_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this verification. Request must be assigned to you."
            )

        # Get entity's workflow codes for navigation
        entity = await conn.fetchrow("""
            SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
        """, entity_code)

        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_code} not found"
            )

        workflow_codes = entity['workflow_codes']
        if isinstance(workflow_codes, str):
            workflow_codes = json.loads(workflow_codes)
        workflow_codes = [str(wf) for wf in workflow_codes] if workflow_codes else []

        # Get the service request
        sr = await conn.fetchrow("""
            SELECT
                sr.id, sr.reference, sr.workflow_code, sr.solicitud_type,
                sr.status, sr.verification_status, sr.verification_details,
                sr.submitted_at, sr.form_data,
                u.first_name, u.last_name, u.email
            FROM service_requests sr
            JOIN users u ON u.id = sr.user_id
            WHERE sr.id = $1
        """, UUID(request_id))

        if not sr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        # Get document_verification_config
        configs = await conn.fetch("""
            SELECT document_code, identifier_type, extraction_paths, source
            FROM document_verification_config
            WHERE is_active = true
        """)
        config_map = {c['document_code']: dict(c) for c in configs}

        # Get only documents that have a verification config (filter out photos, etc.)
        docs_rows = await conn.fetch("""
            SELECT srd.id, srd.document_code, srd.document_name, srd.file_path, srd.file_name,
                   srd.mime_type, srd.extraction_data, srd.extraction_confidence, srd.extraction_status
            FROM service_request_documents srd
            INNER JOIN document_verification_config dvc
                ON dvc.document_code = srd.document_code AND dvc.is_active = true
            WHERE srd.service_request_id = $1
            ORDER BY srd.created_at
        """, UUID(request_id))

        documents = []
        identifiers = []
        verification_details = sr['verification_details'] or {}
        if isinstance(verification_details, str):
            verification_details = json.loads(verification_details)

        # Initialize Firebase Storage for signed URLs
        storage_available = False
        try:
            await ensure_storage_initialized()
            storage_available = True
        except Exception as e:
            logger.warning(f"Firebase Storage not available, documents will have no file_url: {e}")

        for doc in docs_rows:
            extraction_data = doc['extraction_data'] or {}
            if isinstance(extraction_data, str):
                extraction_data = json.loads(extraction_data)

            # Generate signed URL for document access
            file_url = None
            if storage_available and doc['file_path']:
                try:
                    file_url = await firebase_storage_service.get_signed_url(
                        file_path=doc['file_path'],
                        expiration_hours=24
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate signed URL for {doc['file_path']}: {e}")

            documents.append(DocumentInfo(
                id=str(doc['id']),
                document_code=doc['document_code'],
                document_name=doc['document_name'] or doc['document_code'],
                file_path=doc['file_path'],
                file_name=doc['file_name'],
                file_url=file_url,
                mime_type=doc['mime_type'],
                extraction_data=extraction_data,
                extraction_confidence=float(doc['extraction_confidence']) if doc['extraction_confidence'] else None,
                extraction_status=doc['extraction_status']
            ))

            # Extract identifiers from this document
            config = config_map.get(doc['document_code'])
            if config and extraction_data:
                identifier_type = config['identifier_type']
                extraction_paths = config['extraction_paths']

                identifier_value = None
                for path in extraction_paths:
                    keys = path.split('.')
                    value = extraction_data
                    for key in keys:
                        if isinstance(value, dict) and key in value:
                            value = value[key]
                        else:
                            value = None
                            break
                    if value:
                        identifier_value = str(value)
                        break

                expires_at = None
                for exp_path in ['fecha_expiracion', 'expires_at', 'expiry_date']:
                    if exp_path in extraction_data:
                        expires_at = extraction_data[exp_path]
                        break

                if identifier_value:
                    # Check status
                    id_status = verification_details.get(identifier_type, {}).get('status', 'pending')
                    verified_at = None
                    source = None

                    if id_status == 'pending':
                        try:
                            blind_index = crypto.compute_blind_index(identifier_value, identifier_type)
                            cache_check = await conn.fetchrow("""
                                SELECT id, is_active, verified_at, source
                                FROM verified_identifiers
                                WHERE blind_index = $1 AND identifier_type = $2
                            """, blind_index, identifier_type)
                            if cache_check:
                                if cache_check['is_active']:
                                    id_status = 'verified'
                                    verified_at = cache_check['verified_at'].isoformat() if cache_check['verified_at'] else None
                                    source = cache_check['source']
                                else:
                                    id_status = 'fraud'
                        except Exception as e:
                            logger.warning(f"Cache check failed: {e}")

                    identifiers.append(ExtractedIdentifier(
                        identifier_type=identifier_type,
                        value=identifier_value,
                        document_code=doc['document_code'],
                        document_name=doc['document_name'] or doc['document_code'],
                        confidence=float(doc['extraction_confidence']) if doc['extraction_confidence'] else None,
                        expires_at=expires_at,
                        status=id_status,
                        verified_at=verified_at,
                        source=source
                    ))

        # Also check form_data for identifiers
        form_data = sr['form_data'] or {}
        if isinstance(form_data, str):
            form_data = json.loads(form_data)

        for section_key in ['dip', 'pasaporte_antiguo', 'certificado_nacimiento']:
            section = form_data.get(section_key, {})
            if isinstance(section, dict):
                for field_key, id_type in [('numero_dip', 'dni'), ('numero_pasaporte', 'pasaporte')]:
                    if field_key in section and section[field_key]:
                        existing = [i for i in identifiers if i.identifier_type == id_type and i.value == section[field_key]]
                        if not existing:
                            id_status = 'pending'
                            verified_at = None
                            source = None
                            try:
                                blind_index = crypto.compute_blind_index(section[field_key], id_type)
                                cache_check = await conn.fetchrow("""
                                    SELECT id, is_active, verified_at, source
                                    FROM verified_identifiers
                                    WHERE blind_index = $1 AND identifier_type = $2
                                """, blind_index, id_type)
                                if cache_check:
                                    if cache_check['is_active']:
                                        id_status = 'verified'
                                        verified_at = cache_check['verified_at'].isoformat() if cache_check['verified_at'] else None
                                        source = cache_check['source']
                                    else:
                                        id_status = 'fraud'
                            except Exception:
                                pass

                            identifiers.append(ExtractedIdentifier(
                                identifier_type=id_type,
                                value=section[field_key],
                                document_code=section_key,
                                document_name=section_key.replace('_', ' ').title(),
                                confidence=None,
                                expires_at=section.get('fecha_expiracion'),
                                status=id_status,
                                verified_at=verified_at,
                                source=source
                            ))

        # Get previous and next request IDs for navigation
        prev_next_query = """
            WITH ordered AS (
                SELECT id, submitted_at,
                    LAG(id) OVER (ORDER BY submitted_at ASC NULLS LAST, id) as prev_id,
                    LEAD(id) OVER (ORDER BY submitted_at ASC NULLS LAST, id) as next_id
                FROM service_requests
                WHERE workflow_code = ANY($1)
                  AND status::text NOT IN ('DRAFT', 'COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED')
                  AND verification_status = 'pending'
            )
            SELECT prev_id, next_id FROM ordered WHERE id = $2
        """
        nav = await conn.fetchrow(prev_next_query, workflow_codes, UUID(request_id))
        previous_id = str(nav['prev_id']) if nav and nav['prev_id'] else None
        next_id = str(nav['next_id']) if nav and nav['next_id'] else None

        citizen_name = f"{sr['first_name'] or ''} {sr['last_name'] or ''}".strip() or 'N/A'

        return VerificationDetailResponse(
            id=str(sr['id']),
            reference=sr['reference'] or '',
            workflow_code=sr['workflow_code'],
            solicitud_type=sr['solicitud_type'] or '',
            status=sr['status'],
            verification_status=sr['verification_status'] or 'pending',
            citizen_name=citizen_name,
            citizen_email=sr['email'],
            submitted_at=sr['submitted_at'].isoformat() if sr['submitted_at'] else None,
            documents=documents,
            identifiers=identifiers,
            verification_details=verification_details,
            previous_id=previous_id,
            next_id=next_id
        )


@router.post(
    "/requests/{request_id}/verify-identifier",
    response_model=VerifyIdentifierResponse,
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="Verify a single identifier and store in cache"
)
async def verify_identifier(
    request_id: str,
    body: VerifyIdentifierRequest,
    current_user: User = Depends(get_current_user),
    repo: VerifiedIdentifiersRepository = Depends(get_repository)
):
    """
    Verify a single identifier and store it in the verified_identifiers cache.

    ACCESS CONTROL:
    - Supervisor (has service_request.view_all): can verify any request in their entity
    - Agent: can only verify requests assigned to them

    When an agent manually verifies an identifier:
    1. The identifier is encrypted and stored in verified_identifiers
    2. The service_request.verification_details is updated
    3. If all identifiers are verified, verification_status becomes 'verified_manually'
    4. Other pending requests with the same identifier are auto-updated (propagation)

    Future requests with the same identifier will be auto-verified.
    """
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        # Check user access
        user_id = UUID(str(current_user.id))
        has_view_all = await check_user_has_view_all_permission(conn, user_id)

        # Verify access to this specific request
        has_access = await check_verification_access(conn, UUID(request_id), user_id, has_view_all)
        if not has_access:
            logger.warning(f"User {current_user.email} denied verify access to {request_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to verify this request. Request must be assigned to you."
            )

        # Check service request exists
        sr = await conn.fetchrow("""
            SELECT id, user_id, verification_details, verification_status
            FROM service_requests WHERE id = $1
        """, UUID(request_id))

        if not sr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        # Parse expiration date if provided
        expires_at = None
        if body.expires_at:
            try:
                expires_at = datetime.fromisoformat(body.expires_at.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Invalid expires_at format: {body.expires_at}")

        # Insert into verified_identifiers cache
        verified_id = await repo.upsert(
            value=body.identifier_value,
            identifier_type=body.identifier_type,
            source='agent_manual',
            expires_at=expires_at,
            metadata={'notes': body.notes} if body.notes else None,
            verified_by=str(current_user.id),
            user_id=str(sr['user_id']) if sr['user_id'] else None,
            verification_request_id=request_id
        )

        # Update verification_details in service_request
        verification_details = sr['verification_details'] or {}
        if isinstance(verification_details, str):
            verification_details = json.loads(verification_details)

        verification_details[body.identifier_type] = {
            'status': 'verified_manually',
            'verified_at': datetime.now().isoformat(),
            'verified_by': str(current_user.id),
            'notes': body.notes
        }

        # Check if all identifiers are now verified
        # Get all identifier types from documents
        docs = await conn.fetch("""
            SELECT DISTINCT dvc.identifier_type
            FROM service_request_documents srd
            JOIN document_verification_config dvc ON dvc.document_code = srd.document_code
            WHERE srd.service_request_id = $1 AND dvc.is_active = true
        """, UUID(request_id))

        all_types = [d['identifier_type'] for d in docs]
        all_verified = all(
            verification_details.get(t, {}).get('status') in ('verified', 'verified_manually')
            for t in all_types
        ) if all_types else True

        new_status = 'verified_manually' if all_verified else sr['verification_status']

        # Update service_request
        await conn.execute("""
            UPDATE service_requests
            SET verification_details = $1,
                verification_status = $2,
                updated_at = NOW()
            WHERE id = $3
        """, json.dumps(verification_details), new_status, UUID(request_id))

        logger.info(f"Identifier {body.identifier_type} verified manually for request {request_id} by {current_user.id}")

        # =============================================================================
        # PROPAGATION: Auto-verify other pending requests with same identifier
        # =============================================================================
        crypto = get_crypto_service()
        blind_index = crypto.compute_blind_index(body.identifier_value, body.identifier_type)

        # Find other pending requests with the same identifier type in their documents
        other_requests = await conn.fetch("""
            SELECT DISTINCT sr.id, sr.verification_details, sr.verification_status
            FROM service_requests sr
            JOIN service_request_documents srd ON srd.service_request_id = sr.id
            JOIN document_verification_config dvc ON dvc.document_code = srd.document_code
            WHERE sr.id != $1
              AND sr.verification_status IN ('pending', 'partial')
              AND dvc.identifier_type = $2
              AND dvc.is_active = true
        """, UUID(request_id), body.identifier_type)

        propagated_count = 0
        for other_sr in other_requests:
            # Get extraction data for this request to check if identifier matches
            extraction = await conn.fetchrow("""
                SELECT srd.extraction_data
                FROM service_request_documents srd
                JOIN document_verification_config dvc ON dvc.document_code = srd.document_code
                WHERE srd.service_request_id = $1
                  AND dvc.identifier_type = $2
                  AND srd.extraction_data IS NOT NULL
            """, other_sr['id'], body.identifier_type)

            if not extraction or not extraction['extraction_data']:
                continue

            extraction_data = extraction['extraction_data']
            if isinstance(extraction_data, str):
                extraction_data = json.loads(extraction_data)

            # Get identifier value from extraction using config paths
            config = await conn.fetchrow("""
                SELECT extraction_paths FROM document_verification_config
                WHERE identifier_type = $1 AND is_active = true LIMIT 1
            """, body.identifier_type)

            if not config:
                continue

            extracted_value = None
            for path in config['extraction_paths']:
                keys = path.split('.')
                value = extraction_data
                for key in keys:
                    if isinstance(value, dict) and key in value:
                        value = value[key]
                    else:
                        value = None
                        break
                if value:
                    extracted_value = str(value)
                    break

            if not extracted_value:
                continue

            # Check if this identifier matches the one we just verified (compare blind indexes)
            other_blind_index = crypto.compute_blind_index(extracted_value, body.identifier_type)
            if other_blind_index != blind_index:
                continue

            # Match found! Update this request's verification_details
            other_details = other_sr['verification_details'] or {}
            if isinstance(other_details, str):
                other_details = json.loads(other_details)

            other_details[body.identifier_type] = {
                'status': 'verified',  # Auto-verified from cache
                'verified_at': datetime.now().isoformat(),
                'propagated_from': request_id,
                'notes': 'Auto-verified: same identifier verified in another request'
            }

            # Check if all identifiers for this request are now verified
            other_docs = await conn.fetch("""
                SELECT DISTINCT dvc.identifier_type
                FROM service_request_documents srd
                JOIN document_verification_config dvc ON dvc.document_code = srd.document_code
                WHERE srd.service_request_id = $1 AND dvc.is_active = true
            """, other_sr['id'])

            other_all_types = [d['identifier_type'] for d in other_docs]

            # For unverified types, check if they exist in cache
            for otype in other_all_types:
                if other_details.get(otype, {}).get('status') in ('verified', 'verified_manually'):
                    continue

                # Check cache for this identifier
                other_extraction = await conn.fetchrow("""
                    SELECT srd.extraction_data
                    FROM service_request_documents srd
                    JOIN document_verification_config dvc ON dvc.document_code = srd.document_code
                    WHERE srd.service_request_id = $1
                      AND dvc.identifier_type = $2
                      AND srd.extraction_data IS NOT NULL
                """, other_sr['id'], otype)

                if other_extraction and other_extraction['extraction_data']:
                    oext_data = other_extraction['extraction_data']
                    if isinstance(oext_data, str):
                        oext_data = json.loads(oext_data)

                    oconfig = await conn.fetchrow("""
                        SELECT extraction_paths FROM document_verification_config
                        WHERE identifier_type = $1 AND is_active = true LIMIT 1
                    """, otype)

                    if oconfig:
                        oval = None
                        for path in oconfig['extraction_paths']:
                            keys = path.split('.')
                            value = oext_data
                            for key in keys:
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    value = None
                                    break
                            if value:
                                oval = str(value)
                                break

                        if oval:
                            obi = crypto.compute_blind_index(oval, otype)
                            cache_hit = await conn.fetchrow("""
                                SELECT is_active FROM verified_identifiers
                                WHERE blind_index = $1 AND identifier_type = $2
                            """, obi, otype)
                            if cache_hit and cache_hit['is_active']:
                                other_details[otype] = {
                                    'status': 'verified',
                                    'verified_at': datetime.now().isoformat(),
                                    'notes': 'Auto-verified from cache'
                                }

            other_all_verified = all(
                other_details.get(t, {}).get('status') in ('verified', 'verified_manually')
                for t in other_all_types
            ) if other_all_types else True

            other_new_status = 'verified' if other_all_verified else 'partial'

            await conn.execute("""
                UPDATE service_requests
                SET verification_details = $1,
                    verification_status = $2,
                    updated_at = NOW()
                WHERE id = $3
            """, json.dumps(other_details), other_new_status, other_sr['id'])

            propagated_count += 1
            logger.info(f"Propagated verification to request {other_sr['id']}, new status: {other_new_status}")

        if propagated_count > 0:
            logger.info(f"Auto-verified {propagated_count} other request(s) with same identifier")

        return VerifyIdentifierResponse(
            verified_identifier_id=verified_id,
            identifier_type=body.identifier_type,
            status='verified_manually',
            all_verified=all_verified,
            request_verification_status=new_status
        )


@router.post(
    "/requests/{request_id}/verify-batch",
    response_model=VerifyBatchResponse,
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="Verify all pending identifiers at once"
)
async def verify_batch(
    request_id: str,
    body: VerifyBatchRequest,
    current_user: User = Depends(get_current_user),
    repo: VerifiedIdentifiersRepository = Depends(get_repository)
):
    """
    Verify multiple identifiers at once and store all in the cache.

    ACCESS CONTROL:
    - Supervisor (has service_request.view_all): can verify any request in their entity
    - Agent: can only verify requests assigned to them

    Useful for validating all pending identifiers in a single click.
    All operations are performed in a single transaction.
    """
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        # ACCESS CONTROL CHECK
        user_id = UUID(str(current_user.id))
        has_view_all = await check_user_has_view_all_permission(conn, user_id)
        has_access = await check_verification_access(conn, UUID(request_id), user_id, has_view_all)
        if not has_access:
            logger.warning(f"User {current_user.email} denied batch verify access to {request_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to verify this request. Request must be assigned to you."
            )

        # Check service request exists
        sr = await conn.fetchrow("""
            SELECT id, user_id, verification_details, verification_status
            FROM service_requests WHERE id = $1
        """, UUID(request_id))

        if not sr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        verification_details = sr['verification_details'] or {}
        if isinstance(verification_details, str):
            verification_details = json.loads(verification_details)

        results = []
        verified_count = 0
        failed_count = 0

        # Process each identifier in transaction
        async with conn.transaction():
            for identifier in body.identifiers:
                try:
                    # Parse expiration date
                    expires_at = None
                    if identifier.expires_at:
                        try:
                            expires_at = datetime.fromisoformat(identifier.expires_at.replace('Z', '+00:00'))
                        except ValueError:
                            pass

                    # Insert into cache
                    verified_id = await repo.upsert(
                        value=identifier.identifier_value,
                        identifier_type=identifier.identifier_type,
                        source='agent_manual',
                        expires_at=expires_at,
                        metadata={'notes': body.notes or identifier.notes} if (body.notes or identifier.notes) else None,
                        verified_by=str(current_user.id),
                        user_id=str(sr['user_id']) if sr['user_id'] else None,
                        verification_request_id=request_id
                    )

                    # Update verification_details
                    verification_details[identifier.identifier_type] = {
                        'status': 'verified_manually',
                        'verified_at': datetime.now().isoformat(),
                        'verified_by': str(current_user.id),
                        'notes': body.notes or identifier.notes
                    }

                    verified_count += 1
                    results.append({
                        'identifier_type': identifier.identifier_type,
                        'status': 'verified_manually',
                        'verified_identifier_id': verified_id
                    })

                except Exception as e:
                    failed_count += 1
                    results.append({
                        'identifier_type': identifier.identifier_type,
                        'status': 'failed',
                        'error': str(e)
                    })
                    logger.error(f"Failed to verify {identifier.identifier_type}: {e}")

            # Check if all identifiers are verified
            docs = await conn.fetch("""
                SELECT DISTINCT dvc.identifier_type
                FROM service_request_documents srd
                JOIN document_verification_config dvc ON dvc.document_code = srd.document_code
                WHERE srd.service_request_id = $1 AND dvc.is_active = true
            """, UUID(request_id))

            all_types = [d['identifier_type'] for d in docs]
            all_verified = all(
                verification_details.get(t, {}).get('status') in ('verified', 'verified_manually')
                for t in all_types
            ) if all_types else True

            new_status = 'verified_manually' if all_verified else sr['verification_status']

            # Update service_request
            await conn.execute("""
                UPDATE service_requests
                SET verification_details = $1,
                    verification_status = $2,
                    updated_at = NOW()
                WHERE id = $3
            """, json.dumps(verification_details), new_status, UUID(request_id))

        logger.info(f"Batch verification: {verified_count} verified, {failed_count} failed for request {request_id}")

        return VerifyBatchResponse(
            verified_count=verified_count,
            failed_count=failed_count,
            results=results,
            all_verified=all_verified,
            request_verification_status=new_status
        )


@router.post(
    "/requests/{request_id}/reject-identifier",
    dependencies=[Depends(permission_required("service_request.verify_manually"))],
    summary="Reject an identifier with optional fraud marking"
)
async def reject_identifier(
    request_id: str,
    body: RejectIdentifierRequest,
    current_user: User = Depends(get_current_user),
    repo: VerifiedIdentifiersRepository = Depends(get_repository)
):
    """
    Reject an identifier.

    ACCESS CONTROL:
    - Supervisor (has service_request.view_all): can reject for any request in their entity
    - Agent: can only reject for requests assigned to them

    Options:
    - Normal rejection: Mark as rejected in verification_details
    - Fraud marking: Also store with is_active=false in cache to block future use

    When marked as fraud, the identifier is stored in verified_identifiers with
    is_active=false, causing automatic rejection in future requests.
    """
    pool = await get_db_pool()
    crypto = get_crypto_service()

    async with pool.acquire() as conn:
        # ACCESS CONTROL CHECK
        user_id = UUID(str(current_user.id))
        has_view_all = await check_user_has_view_all_permission(conn, user_id)
        has_access = await check_verification_access(conn, UUID(request_id), user_id, has_view_all)
        if not has_access:
            logger.warning(f"User {current_user.email} denied reject access to {request_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to reject identifiers for this request. Request must be assigned to you."
            )

        # Check service request exists
        sr = await conn.fetchrow("""
            SELECT id, user_id, verification_details, verification_status
            FROM service_requests WHERE id = $1
        """, UUID(request_id))

        if not sr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found"
            )

        verification_details = sr['verification_details'] or {}
        if isinstance(verification_details, str):
            verification_details = json.loads(verification_details)

        # If fraud, store in cache with is_active=false
        if body.is_fraud:
            # First, try to insert/update with is_active = false
            blind_index = crypto.compute_blind_index(body.identifier_value, body.identifier_type)
            encrypted_value = crypto.encrypt_value(body.identifier_value)
            encrypted_metadata = crypto.encrypt_value(json.dumps({
                'reason': body.reason,
                'marked_as_fraud': True,
                'marked_by': str(current_user.id),
                'marked_at': datetime.now().isoformat()
            }))

            await conn.execute("""
                INSERT INTO verified_identifiers (
                    blind_index, encrypted_value, identifier_type, source,
                    verified_at, is_active, encrypted_metadata,
                    verified_by, verification_request_id
                ) VALUES ($1, $2, $3, 'agent_manual', NOW(), FALSE, $4, $5, $6)
                ON CONFLICT (blind_index, identifier_type) DO UPDATE SET
                    is_active = FALSE,
                    encrypted_metadata = EXCLUDED.encrypted_metadata,
                    verified_by = EXCLUDED.verified_by,
                    updated_at = NOW()
            """, blind_index, encrypted_value, body.identifier_type,
                encrypted_metadata, UUID(str(current_user.id)), UUID(request_id))

            logger.warning(f"Identifier {body.identifier_type} marked as FRAUD for request {request_id} by {current_user.id}")

        # Update verification_details
        verification_details[body.identifier_type] = {
            'status': 'fraud' if body.is_fraud else 'rejected',
            'rejected_at': datetime.now().isoformat(),
            'rejected_by': str(current_user.id),
            'reason': body.reason,
            'is_fraud': body.is_fraud
        }

        # Update service request
        # If any identifier is rejected/fraud, the overall status reflects that
        new_status = 'verification_failed' if body.is_fraud else sr['verification_status']

        await conn.execute("""
            UPDATE service_requests
            SET verification_details = $1,
                verification_status = $2,
                updated_at = NOW()
            WHERE id = $3
        """, json.dumps(verification_details), new_status, UUID(request_id))

        return {
            'status': 'fraud' if body.is_fraud else 'rejected',
            'identifier_type': body.identifier_type,
            'reason': body.reason,
            'request_verification_status': new_status,
            'message': 'Identifier marked as fraud and blocked for future use' if body.is_fraud else 'Identifier rejected'
        }
