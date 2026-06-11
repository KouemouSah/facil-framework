"""Bundle Workflow API routes.

Endpoints for the BUNDLE_PAYMENT workflow (citizen-facing):
  GET  /bundle-workflow/my-companies       — User's companies + obligation status
  GET  /bundle-workflow/search-company     — Search eligible companies
  POST /bundle-workflow/initiate           — Verify/create license, return obligations
  POST /bundle-workflow/validate-selection — Validate mode + selection before payment
  POST /bundle-workflow/initiate-payment   — Create SR + payment + link obligations (atomic)
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database.connection import get_database
from app.core.rate_limit import rate_limit_dep
from app.modules.auth.dependencies import get_current_user
from app.modules.fiscal_services.services.bundle_workflow_service import (
    BundleWorkflowService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bundle-workflow", tags=["bundle-workflow"])


# ================================================================
# Post-commit: generate summary PDF → vault + email (non-blocking)
# ================================================================

async def _post_commit_bundle_pdf(
    db, result: dict, user_id: UUID, current_user, license_id: str, obligation_ids: list,
):
    """Generate bundle solicitud PDF, store in vault, attach to email.

    Mirrors wizard_session_service._generate_summary_pdf_attachment() for
    non-bundle workflows. Called AFTER the transaction commits so the SR
    and obligations exist in the DB.
    """
    from app.modules.service_requests.services.summary_pdf_service import summary_pdf_service
    from app.modules.user_documents.services.vault_registry import register_document_in_vault
    from app.core.events import EventBus, EventType

    sr_id = result.get("service_request_id")
    reference = await db.fetchval(
        "SELECT reference FROM service_requests WHERE id = $1::uuid", sr_id,
    )
    if not reference:
        return

    # Fetch bundle details for the PDF
    lic_id = UUID(license_id)
    bd_rows = await db.fetch("""
        SELECT sp.entity_code, sp.total_amount, sp.workflow_status,
               ent.name AS entity_name
        FROM service_payments sp
        LEFT JOIN entities ent ON ent.code = sp.entity_code
        WHERE sp.service_request_id = $1::uuid
        ORDER BY sp.entity_code
    """, sr_id)
    obl_rows = await db.fetch("""
        SELECT lo.fee_type, lo.amount, lo.status,
               fs.name_es AS service_name
        FROM license_obligations lo
        LEFT JOIN fiscal_services fs ON fs.id = lo.fiscal_service_id
        WHERE lo.license_id = $1
          AND lo.id = ANY($2::uuid[])
        ORDER BY lo.fee_type, fs.name_es
    """, lic_id, obligation_ids)
    comp_row = await db.fetchrow("""
        SELECT c.legal_name, c.registration_number
        FROM companies c JOIN commercial_licenses cl ON cl.company_id = c.id
        WHERE cl.id = $1
    """, lic_id)

    bundle_details = {
        "company_name": comp_row["legal_name"] if comp_row else None,
        "registration_number": comp_row["registration_number"] if comp_row else None,
        "splits": [
            {"entity_code": r["entity_code"], "entity_name": r["entity_name"],
             "amount": float(r["total_amount"]), "status": r["workflow_status"]}
            for r in bd_rows
        ],
        "obligations": [
            {"service_name": r["service_name"] or r["fee_type"],
             "amount": float(r["amount"]), "status": r["status"], "fee_type": r["fee_type"]}
            for r in obl_rows
        ],
        "total_amount": sum(float(r["total_amount"]) for r in bd_rows),
    }

    # Generate PDF with obligations
    pdf_bytes = await summary_pdf_service.generate_summary_pdf(
        request_number=reference,
        workflow_name="Licencia Comercial - Paquete Fiscal",
        solicitud_type="expedicion",
        documents=[],
        tariff={"base_amount": bundle_details["total_amount"],
                "additional_fees": [], "total_amount": bundle_details["total_amount"]},
        data_sections=[],
        language="es",
        payment_status="processing",
        bundle_details=bundle_details,
    )
    pdf_name = f"solicitud_{reference}.pdf"

    # Store in Firebase
    try:
        from app.modules.documents.services.storage_service import firebase_storage_service
        summary_url = await firebase_storage_service.upload_bytes(
            pdf_bytes, f"summaries/{sr_id}/{pdf_name}", content_type="application/pdf",
        )
    except Exception as store_err:
        logger.warning(f"Bundle summary Firebase upload failed: {store_err}")
        summary_url = None

    # Register in vault ("Mes Documents")
    if summary_url:
        try:
            await register_document_in_vault(
                db, user_id=user_id,
                file_path=summary_url, file_name=pdf_name,
                document_type="CITIZEN_SUMMARY", document_category="fiscal",
                source_request_id=UUID(sr_id),
            )
        except Exception as vault_err:
            logger.warning(f"Bundle summary vault registration failed: {vault_err}")

    # Publish REQUEST_SUBMITTED with PDF attachment → email
    user_email = getattr(current_user, 'email', None) or (
        await db.fetchval("SELECT email FROM users WHERE id = $1", user_id)
    )
    user_name = getattr(current_user, 'full_name', None) or (
        await db.fetchval("SELECT first_name || ' ' || last_name FROM users WHERE id = $1", user_id)
    )
    user_phone = getattr(current_user, 'phone_number', None) or (
        await db.fetchval("SELECT phone_number FROM users WHERE id = $1", user_id)
    )

    EventBus.publish_nowait(EventType.REQUEST_SUBMITTED, {
        "request_id": sr_id,
        "user_id": str(user_id),
        "user_email": user_email,
        "user_phone": user_phone,
        "user_name": user_name,
        "workflow_code": "BUNDLE_PAYMENT",
        "reference": reference,
        "attachments": [(pdf_name, pdf_bytes, "application/pdf")],
    })


# ================================================================
# Pydantic Request/Response Models
# ================================================================


class BundleInitiateRequest(BaseModel):
    company_id: str = Field(..., description="UUID of the company")
    fiscal_year: Optional[int] = Field(None, description="Defaults to current year", ge=2020, le=2050)


class ClassifyPreviewRequest(BaseModel):
    extraction: Dict[str, Any] = Field(
        ..., description="GeminiDocumentProcessor extraction output",
    )
    zone_id: Optional[str] = Field(
        None, description="User-selected zone override (UUID). When provided, categories are fetched for this zone.",
    )


class BundleInitiateFromUploadRequest(BaseModel):
    extraction: Dict[str, Any] = Field(
        ..., description="GeminiDocumentProcessor extraction output (nested dict)",
        max_length=100,  # Max 100 top-level keys
    )
    fiscal_year: Optional[int] = Field(None, description="Defaults to current year", ge=2020, le=2050)
    zone_id: Optional[str] = Field(None, description="Override zone (if auto-resolution failed)")
    commerce_type: Optional[str] = Field(None, description="Override commerce type (if auto-classification failed)")


class BundleValidateSelectionRequest(BaseModel):
    license_id: str = Field(..., description="UUID of the license")
    processing_mode: str = Field(..., description="per_line or consolidated")
    selected_obligation_ids: Optional[List[str]] = Field(
        None, description="Required for per_line mode"
    )


class BundleInitiatePaymentRequest(BaseModel):
    license_id: str = Field(..., description="UUID of the license")
    processing_mode: str = Field(..., description="per_line or consolidated")
    payment_method: str = Field(..., description="mobile_money, cash, card, etc.")
    selected_obligation_ids: List[str] = Field(
        ..., description="Obligation UUIDs to pay"
    )
    phone_number: Optional[str] = Field(
        None, description="Required for mobile_money"
    )
    wizard_session_id: Optional[str] = Field(
        None, description="Wizard session ID for document persistence (Firebase)"
    )


# ================================================================
# Endpoints
# ================================================================


@router.get("/my-companies")
async def get_my_companies_status(
    fiscal_year: Optional[int] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get user's companies with pending obligation counts.

    Returns max 5 companies sorted by urgency.
    No special permission required — scoped to authenticated user.
    """
    from loguru import logger
    user_id = UUID(current_user.id if hasattr(current_user, 'id') else current_user.get("sub"))
    try:
        result = await BundleWorkflowService.my_companies_status(
            db, user_id, fiscal_year
        )
        return {"companies": result}
    except Exception as e:
        logger.error(f"[BundleWorkflow] my_companies_status failed: {e}", exc_info=True)
        raise


@router.get("/my-companies/{company_id}")
async def get_my_company_detail(
    company_id: str,
    fiscal_year: Optional[int] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get detailed company info with license + obligations for citizen."""
    user_id = UUID(current_user.id if hasattr(current_user, 'id') else current_user.get("sub"))
    try:
        result = await BundleWorkflowService.my_company_detail(
            db, user_id, UUID(company_id), fiscal_year
        )
        return result
    except ValueError as e:
        code = str(e)
        if code == "COMPANY_NOT_OWNED":
            raise HTTPException(status_code=403, detail="You don't have access to this company")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/my-companies/{company_id}/payments")
async def get_my_company_payments(
    company_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get payment history for a citizen's company."""
    user_id = UUID(current_user.id if hasattr(current_user, 'id') else current_user.get("sub"))
    try:
        result = await BundleWorkflowService.my_company_payments(
            db, user_id, UUID(company_id), page, page_size
        )
        return result
    except ValueError as e:
        code = str(e)
        if code == "COMPANY_NOT_OWNED":
            raise HTTPException(status_code=403, detail="You don't have access to this company")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/my-companies/{company_id}/license-pdf")
async def download_my_license_pdf(
    company_id: str,
    language: str = Query("es", pattern="^(es|fr|en)$"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Download license PDF for citizen's own company (no agent permission needed).

    Verifies ownership via user_company_roles before generating PDF.
    """
    from fastapi.responses import Response
    from app.modules.fiscal_services.services.license_pdf_service import license_pdf_service

    user_id = UUID(current_user.id if hasattr(current_user, 'id') else current_user.get("sub"))

    # Verify citizen owns this company
    ownership = await db.fetchval(
        "SELECT 1 FROM user_company_roles WHERE user_id = $1 AND company_id = $2",
        user_id, UUID(company_id),
    )
    if not ownership:
        raise HTTPException(status_code=403, detail="You don't have access to this company")

    # Find active license for this company
    license_id = await db.fetchval("""
        SELECT id FROM commercial_licenses
        WHERE company_id = $1 AND status != 'cancelled'
        ORDER BY fiscal_year DESC LIMIT 1
    """, UUID(company_id))
    if not license_id:
        raise HTTPException(status_code=404, detail="No license found for this company")

    try:
        pdf_bytes = await license_pdf_service.generate_license_pdf(
            db, str(license_id), language
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="license-{company_id}.pdf"',
        },
    )


@router.get("/search-company")
async def search_eligible_company(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Search companies eligible for bundle payment.

    Filters: regimen_fiscal='bundle', is_active=true.
    No special permission required — any authenticated user can search.
    """
    from loguru import logger
    user_id = UUID(current_user.id if hasattr(current_user, 'id') else current_user.get("sub"))
    try:
        results = await BundleWorkflowService.search_eligible_companies(
            db, q, user_id, limit
        )
        return {"companies": results, "total": len(results)}
    except Exception as e:
        logger.error(f"[BundleWorkflow] search_eligible_companies failed for q='{q}': {e}", exc_info=True)
        raise


@router.post(
    "/initiate",
    dependencies=[rate_limit_dep(
        endpoint="bundle_initiate",
        user_max=20, user_window=60, ip_max=60, ip_window=60,
    )],
)
async def initiate_bundle_workflow(
    body: BundleInitiateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Verify company, find/create license, return obligations for review.

    Main entry point after company selection (Step 0 → Step 2).
    """
    user_id = UUID(current_user.id if hasattr(current_user, 'id') else current_user.get("sub"))
    try:
        result = await BundleWorkflowService.initiate(
            db,
            company_id=UUID(body.company_id),
            user_id=user_id,
            fiscal_year=body.fiscal_year,
        )
        return result
    except ValueError as e:
        error_code = str(e).split(":")[0]
        raise HTTPException(
            status_code=_error_status(error_code),
            detail=_error_detail(error_code),
        )


@router.post(
    "/classify-preview",
    dependencies=[rate_limit_dep(
        endpoint="bundle_classify_preview",
        user_max=20, user_window=60, ip_max=60, ip_window=60,
    )],
)
async def classify_preview(
    body: ClassifyPreviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Preview classification WITHOUT creating company/license.

    Returns extracted data, resolved zone (or available zones if unresolved),
    and classification result. Frontend uses this to confirm or manually
    select zone/category before calling initiate-from-upload.
    """
    try:
        result = await BundleWorkflowService.preview_classification(
            db, extraction=body.extraction,
            override_zone_id=body.zone_id,
        )
        return result
    except ValueError as e:
        error_code = str(e).split(":")[0]
        raise HTTPException(
            status_code=_error_status(error_code),
            detail=_error_detail(error_code),
        )


@router.post(
    "/initiate-from-upload",
    dependencies=[rate_limit_dep(
        endpoint="bundle_initiate_from_upload",
        user_max=10, user_window=60, ip_max=30, ip_window=60,
    )],
)
async def initiate_from_upload(
    body: BundleInitiateFromUploadRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Create company from OCR extraction, classify, then initiate workflow.

    Reuses: map_gemini_extraction_to_company_data + CompanyRepository.create
    + ClassificationAgent.classify_company + BundleWorkflowService.initiate.
    """
    user_id = UUID(current_user.id if hasattr(current_user, 'id') else current_user.get("sub"))
    try:
        result = await BundleWorkflowService.initiate_from_upload(
            db,
            extraction=body.extraction,
            user_id=user_id,
            fiscal_year=body.fiscal_year,
            zone_id=UUID(body.zone_id) if body.zone_id else None,
            commerce_type=body.commerce_type,
        )
        return result
    except ValueError as e:
        error_code = str(e).split(":")[0]
        raise HTTPException(
            status_code=_error_status(error_code),
            detail=_error_detail(error_code),
        )


@router.post("/validate-selection")
async def validate_bundle_selection(
    body: BundleValidateSelectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Validate mode + obligation selection before payment."""
    try:
        obligation_uuids = (
            [UUID(oid) for oid in body.selected_obligation_ids]
            if body.selected_obligation_ids
            else None
        )
        result = await BundleWorkflowService.validate_selection(
            db,
            license_id=UUID(body.license_id),
            processing_mode=body.processing_mode,
            selected_obligation_ids=obligation_uuids,
        )
        return result
    except ValueError as e:
        error_code = str(e).split(":")[0]
        raise HTTPException(
            status_code=_error_status(error_code),
            detail=_error_detail(error_code),
        )


@router.post(
    "/initiate-payment",
    dependencies=[rate_limit_dep(
        endpoint="bundle_initiate_payment",
        user_max=10, user_window=60, ip_max=30, ip_window=60,
    )],
)
async def initiate_bundle_payment(
    body: BundleInitiatePaymentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Create service_request + service_payment + link obligations.

    Atomic transaction — all-or-nothing.
    For mobile_money: returns redirect_url (BANGE).
    For cash: returns payment reference for agent validation.
    """
    user_id = UUID(current_user.id if hasattr(current_user, 'id') else current_user.get("sub"))

    # Validate phone for mobile_money
    if body.payment_method == "mobile_money":
        if not body.phone_number:
            raise HTTPException(status_code=422, detail=_error_detail("PHONE_REQUIRED"))
        import re
        phone_clean = re.sub(r"[\s\-\(\)]", "", body.phone_number)
        if not re.match(r"^\+?240?\d{9}$", phone_clean):
            raise HTTPException(
                status_code=422,
                detail=_error_detail("PHONE_REQUIRED"),
            )

    try:
        obligation_uuids = [UUID(oid) for oid in body.selected_obligation_ids]

        async with db.transaction():
            result = await BundleWorkflowService.initiate_payment(
                conn=db,
                license_id=UUID(body.license_id),
                processing_mode=body.processing_mode,
                payment_method=body.payment_method,
                selected_obligation_ids=obligation_uuids,
                user_id=user_id,
                phone_number=body.phone_number,
                wizard_session_id=body.wizard_session_id,
            )

        # Post-commit: generate summary PDF → vault + email (non-blocking)
        try:
            await _post_commit_bundle_pdf(
                db, result, user_id, current_user, body.license_id, obligation_uuids,
            )
        except Exception as pdf_err:
            logger.warning(f"[BundleWorkflow] Post-commit PDF failed (non-blocking): {pdf_err}")

        return result

    except ValueError as e:
        parts = str(e).split(":")
        error_code = parts[0]
        detail = _error_detail(error_code)
        # For PAYMENT_ALREADY_IN_PROGRESS, include existing SR info
        # so the frontend can redirect instead of showing a generic error
        if error_code == "PAYMENT_ALREADY_IN_PROGRESS" and len(parts) >= 3:
            detail["existing_request_id"] = parts[1]
            detail["existing_reference"] = parts[2]
        raise HTTPException(
            status_code=_error_status(error_code),
            detail=detail,
        )


# ================================================================
# Error messages (Spanish)
# ================================================================

_error_messages = {
    "COMPANY_NOT_FOUND": {
        "es": "Empresa no encontrada",
        "fr": "Entreprise non trouvée",
        "en": "Company not found",
    },
    "COMPANY_INACTIVE": {
        "es": "La empresa está inactiva",
        "fr": "L'entreprise est inactive",
        "en": "The company is inactive",
    },
    "COMPANY_NOT_AUTONOMO": {
        "es": "Este flujo es solo para empresas autónomas del Padrón Empresarial",
        "fr": "Ce flux est réservé aux entreprises autonomes du Registre des Entreprises",
        "en": "This flow is only for autonomous companies registered in the Business Registry",
    },
    "COMPANY_NO_ZONE": {
        "es": "La empresa no tiene una zona asignada",
        "fr": "L'entreprise n'a pas de zone assignée",
        "en": "The company has no assigned zone",
    },
    "COMPANY_NO_COMMERCE_TYPE": {
        "es": "La empresa no tiene un tipo de comercio asignado. Solicite una reclasificación",
        "fr": "L'entreprise n'a pas de type de commerce assigné. Demandez une reclassification",
        "en": "The company has no commerce type assigned. Request a reclassification",
    },
    "NO_BUNDLE_FOR_COMMERCE_TYPE": {
        "es": "No hay un paquete de obligaciones configurado para este tipo de comercio",
        "fr": "Aucun forfait d'obligations configuré pour ce type de commerce",
        "en": "No obligation bundle configured for this commerce type",
    },
    "LICENSE_NOT_FOUND": {
        "es": "Licencia no encontrada",
        "fr": "Licence non trouvée",
        "en": "License not found",
    },
    "LICENSE_SUSPENDED": {
        "es": "Licencia suspendida — contacte la administración",
        "fr": "Licence suspendue — contactez l'administration",
        "en": "License suspended — contact administration",
    },
    "LICENSE_ALREADY_COMPLETE": {
        "es": "Todas las obligaciones ya están pagadas para este año fiscal",
        "fr": "Toutes les obligations sont déjà payées pour cette année fiscale",
        "en": "All obligations are already paid for this fiscal year",
    },
    "LICENSE_NOT_PAYABLE": {
        "es": "Licencia no disponible para pago",
        "fr": "Licence non disponible pour paiement",
        "en": "License not available for payment",
    },
    "NO_PAYABLE_OBLIGATIONS": {
        "es": "No hay obligaciones pendientes de pago",
        "fr": "Aucune obligation en attente de paiement",
        "en": "No pending obligations to pay",
    },
    "NO_OBLIGATIONS_SELECTED": {
        "es": "Seleccione al menos una obligación en Modo A",
        "fr": "Sélectionnez au moins une obligation en Mode A",
        "en": "Select at least one obligation in Mode A",
    },
    "OBLIGATION_NOT_PAYABLE": {
        "es": "Una o más obligaciones ya no están disponibles",
        "fr": "Une ou plusieurs obligations ne sont plus disponibles",
        "en": "One or more obligations are no longer available",
    },
    "OBLIGATION_RACE_CONDITION": {
        "es": "Una o más obligaciones ya están en proceso de pago por otro usuario",
        "fr": "Une ou plusieurs obligations sont déjà en cours de paiement par un autre utilisateur",
        "en": "One or more obligations are already being paid by another user",
    },
    "INVALID_PROCESSING_MODE": {
        "es": "Modo de pago inválido (per_line o consolidated)",
        "fr": "Mode de paiement invalide (per_line ou consolidated)",
        "en": "Invalid payment mode (per_line or consolidated)",
    },
    "INVALID_PAYMENT_METHOD": {
        "es": "Método de pago no soportado",
        "fr": "Méthode de paiement non supportée",
        "en": "Unsupported payment method",
    },
    "PAYMENT_INITIATION_FAILED": {
        "es": "Error al conectar con la pasarela de pago",
        "fr": "Erreur de connexion avec la passerelle de paiement",
        "en": "Error connecting to payment gateway",
    },
    "PHONE_REQUIRED": {
        "es": "Número de teléfono requerido para Mobile Money",
        "fr": "Numéro de téléphone requis pour Mobile Money",
        "en": "Phone number required for Mobile Money",
    },
    "EXTRACTION_MISSING_LEGAL_NAME": {
        "es": "El documento no contiene el nombre de la empresa",
        "fr": "Le document ne contient pas le nom de l'entreprise",
        "en": "The document does not contain the company name",
    },
    "PAYMENT_ALREADY_IN_PROGRESS": {
        "es": "Ya existe un pago en curso para esta licencia",
        "fr": "Un paiement est déjà en cours pour cette licence",
        "en": "A payment is already in progress for this license",
    },
    "INITIATE_AFTER_UPLOAD_FAILED": {
        "es": "La empresa fue registrada pero no se pudo iniciar el flujo de pago",
        "fr": "L'entreprise a été enregistrée mais le flux de paiement n'a pas pu être initié",
        "en": "The company was registered but the payment flow could not be initiated",
    },
    "BUNDLE_SR_MISSING_LICENSE_ID": {
        "es": "Error interno: la solicitud del paquete no está vinculada a una licencia",
        "fr": "Erreur interne : la demande du forfait n'est pas liée à une licence",
        "en": "Internal error: bundle request is not linked to a license",
    },
    "BUNDLE_SR_MISSING_FISCAL_YEAR": {
        "es": "Error interno: falta el año fiscal en la solicitud del paquete",
        "fr": "Erreur interne : année fiscale manquante dans la demande du forfait",
        "en": "Internal error: fiscal year missing from bundle request",
    },
    "BUNDLE_INTEGRITY_ERROR": {
        "es": "La solicitud del paquete no cumple con las reglas de integridad. Contacte el soporte",
        "fr": "La demande du forfait ne respecte pas les règles d'intégrité. Contactez le support",
        "en": "Bundle request does not meet integrity rules. Contact support",
    },
    "DATABASE_CONSTRAINT_VIOLATION": {
        "es": "La operación viola una regla de la base de datos",
        "fr": "L'opération viole une règle de la base de données",
        "en": "The operation violates a database rule",
    },
}


def _error_detail(code: str) -> Dict[str, Any]:
    """Build trilingual error detail from error code."""
    msgs = _error_messages.get(code, {
        "es": "Error desconocido",
        "fr": "Erreur inconnue",
        "en": "Unknown error",
    })
    return {
        "code": code,
        "message_es": msgs["es"],
        "message_fr": msgs["fr"],
        "message_en": msgs["en"],
    }


def _error_status(code: str) -> int:
    """Map error code to HTTP status."""
    if code in ("COMPANY_NOT_FOUND", "LICENSE_NOT_FOUND"):
        return 404
    if code in ("LICENSE_SUSPENDED",):
        return 403
    if code.endswith("RACE_CONDITION") or code == "PAYMENT_ALREADY_IN_PROGRESS":
        return 409
    if code in ("LICENSE_ALREADY_COMPLETE",):
        return 409
    if code == "PAYMENT_INITIATION_FAILED":
        return 503
    # Bundle integrity issues = server-side bugs (missing link at creation time).
    # Surface as 500 so Sentry/Cloud Error Reporting picks them up for alerting,
    # but the body still carries a clean metier code + trilingual message.
    if code in ("BUNDLE_SR_MISSING_LICENSE_ID",
                "BUNDLE_SR_MISSING_FISCAL_YEAR",
                "BUNDLE_INTEGRITY_ERROR",
                "DATABASE_CONSTRAINT_VIOLATION"):
        return 500
    return 422
