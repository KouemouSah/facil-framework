"""
Verification Routes - Public Receipt & Service Request Verification

Public endpoints to verify payment receipts (HMAC-signed) and
service request status (by reference number).
No authentication required.
"""

from fastapi import APIRouter, HTTPException, status, Query, Path
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
import hmac as hmac_lib
import hashlib
from loguru import logger

from app.database.connection import db_manager
from app.config import settings
from app.modules.payments.services.receipt_service import receipt_service


def _get_verification_secret() -> str:
    """
    Return the permanent HMAC secret for QR/verification tokens.

    Priority:
      1. RECEIPT_VERIFICATION_SECRET (dedicated, recommended)
      2. JWT_SECRET_KEY (permanent in .env — never ephemeral)

    NEVER fall back to SECRET_KEY: it regenerates on every Cloud Run startup
    and would invalidate all existing QR codes after each deployment.
    """
    secret = settings.RECEIPT_VERIFICATION_SECRET
    if secret:
        return secret
    # JWT_SECRET_KEY is always set permanently in .env / Cloud Run env
    jwt_key = getattr(settings, 'JWT_SECRET_KEY', None)
    if jwt_key:
        return jwt_key
    # Hard fallback — should never happen in practice
    return 'taxasge-verify-fallback-key'


def _verify_sr_token(reference: str, provided_token: str) -> bool:
    """
    Verify HMAC-SHA256 token for service request verification.
    Must match the generation logic in SummaryPDFService._generate_sr_verification_token().
    """
    secret_key = _get_verification_secret()
    message = f"sr-verify|{reference}"
    expected = hmac_lib.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:16]
    return hmac_lib.compare_digest(expected, provided_token)

router = APIRouter(tags=["Verification"])


class ReceiptVerificationResponse(BaseModel):
    """Response model for receipt verification"""
    valid: bool
    receipt_number: str
    message: str
    verification_type: Literal["receipt"] = "receipt"
    # Only included if valid
    payment_date: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    payer_name: Optional[str] = None
    workflow_code: Optional[str] = None
    entity_code: Optional[str] = None
    solicitud_type: Optional[str] = None
    service_request_reference: Optional[str] = None
    validated_by: Optional[str] = None
    validated_at: Optional[str] = None


class ServiceRequestVerificationResponse(BaseModel):
    """Response model for service request verification"""
    valid: bool
    reference: str
    message: str
    verification_type: Literal["service_request"] = "service_request"
    # Only included if valid
    workflow_name: Optional[str] = None
    solicitud_type: Optional[str] = None
    entity_code: Optional[str] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    created_at: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_location: Optional[str] = None
    payment_status: Optional[str] = None
    payment_amount: Optional[float] = None
    currency: Optional[str] = None


# ================================================================
# SERVICE REQUEST VERIFICATION (by SRV-... reference)
# ================================================================

@router.get(
    "/request/{reference}",
    response_model=ServiceRequestVerificationResponse,
    summary="Verify service request status (PUBLIC)",
)
async def verify_service_request(
    reference: str = Path(..., description="Service request reference (e.g., SRV-2026-00011)"),
    t: str = Query(..., description="HMAC verification token (from QR code)"),
):
    """
    Verify service request status by reference number (PUBLIC - no authentication).
    Requires a valid HMAC token (generated in QR code) to prevent enumeration.

    Returns basic request information: workflow, status, appointment, payment.
    Used by QR code on citizen summary PDF.
    """
    # Verify HMAC token before any DB access
    if not _verify_sr_token(reference, t):
        logger.warning(f"Service request verification failed: invalid token for {reference}")
        return ServiceRequestVerificationResponse(
            valid=False,
            reference=reference,
            message="Token de verificacion invalido / Invalid verification token"
        )

    async with db_manager.get_connection() as db:
        try:
            query = """
                SELECT
                    sr.reference, sr.workflow_code, sr.solicitud_type,
                    sr.entity_code, sr.status, sr.created_at,
                    sr.cita_date, sr.cita_time, sr.entity_location_id,
                    sr.payment_status
                FROM service_requests sr
                WHERE sr.reference = $1
            """
            request = await db.fetchrow(query, reference)

            if not request:
                return ServiceRequestVerificationResponse(
                    valid=False,
                    reference=reference,
                    message="Solicitud no encontrada / Request not found"
                )

            # Workflow display name — built dynamically from the registered workflow engine
            # so any new workflow added to the codebase is automatically picked up.
            try:
                from app.modules.service_requests.services.workflow_engine import workflow_engine
                wf_labels: dict = {}
                for code, wf in workflow_engine.get_all_workflows().items():
                    try:
                        wf_labels[code.value] = wf.service_name_es
                    except Exception:
                        wf_labels[code.value] = code.value.replace("_", " ").title()
            except Exception as e:
                logger.warning(f"Could not load workflow labels from engine: {e}")
                wf_labels = {}
            raw_code = request["workflow_code"] or ""
            workflow_name = wf_labels.get(raw_code, raw_code.replace("_", " ").title())

            # Status display label
            status_labels = {
                "DRAFT": "Borrador",
                "SUBMITTED": "Enviada",
                "UNDER_REVIEW": "En revision",
                "DOSSIER_VALIDE": "Dossier validado",
                "PAYMENT_PENDING": "Pago pendiente",
                "PAID": "Pagado",
                "CITA_SCHEDULED": "Cita programada",
                "IN_PROGRESS": "En proceso",
                "COMPLETED": "Completada",
                "REJECTED": "Rechazada",
                "CANCELLED": "Cancelada",
            }
            req_status = request["status"]
            status_label = status_labels.get(req_status, req_status)

            # Appointment location name
            appointment_location = None
            if request["entity_location_id"]:
                loc_query = """
                    SELECT location_name FROM entity_locations
                    WHERE id = $1
                """
                loc = await db.fetchrow(loc_query, request["entity_location_id"])
                if loc:
                    appointment_location = loc["location_name"]

            # Payment amount from service_payments
            payment_amount = None
            currency = None
            if request["payment_status"]:
                pay_query = """
                    SELECT total_amount, currency
                    FROM service_payments
                    WHERE service_request_id = (
                        SELECT id FROM service_requests WHERE reference = $1
                    )
                    ORDER BY created_at DESC LIMIT 1
                """
                pay = await db.fetchrow(pay_query, reference)
                if pay:
                    payment_amount = float(pay["total_amount"]) if pay["total_amount"] else None
                    currency = pay["currency"]

            # Format dates
            created_str = request["created_at"].strftime("%d/%m/%Y") if request["created_at"] else None
            appt_date_str = request["cita_date"].strftime("%d/%m/%Y") if request["cita_date"] else None
            appt_time_str = request["cita_time"].strftime("%H:%M") if request["cita_time"] else None

            logger.info(f"Service request {reference} verified successfully")

            return ServiceRequestVerificationResponse(
                valid=True,
                reference=reference,
                message="Solicitud verificada / Request verified",
                workflow_name=workflow_name,
                solicitud_type=request["solicitud_type"],
                entity_code=request["entity_code"],
                status=req_status,
                status_label=status_label,
                created_at=created_str,
                appointment_date=appt_date_str,
                appointment_time=appt_time_str,
                appointment_location=appointment_location,
                payment_status=request["payment_status"],
                payment_amount=payment_amount,
                currency=currency,
            )

        except Exception as e:
            logger.error(f"Service request verification error for {reference}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de verificacion / Verification error"
            )


# ================================================================
# RECEIPT VERIFICATION (by REC-... with HMAC token)
# ================================================================

@router.get("/{receipt_number}", response_model=ReceiptVerificationResponse)
async def verify_receipt(
    receipt_number: str,
    t: str = Query(..., description="Verification token (from QR code)")
):
    """
    Verify payment receipt authenticity (PUBLIC - no authentication)

    This endpoint validates the HMAC token in the QR code and returns
    receipt details if valid. Used for anti-fraud verification.

    Args:
        receipt_number: The receipt number (e.g., REC-2025-000001)
        t: The HMAC verification token (16 hex characters)

    Returns:
        ReceiptVerificationResponse with validity status and receipt details
    """
    async with db_manager.get_connection() as db:
        try:
            # 1. Look up the payment by receipt number
            query = """
                SELECT
                    sp.id, sp.receipt_number, sp.payment_reference,
                    sp.total_amount, sp.currency, sp.payment_method,
                    sp.paid_at, sp.validated_by_agent_id, sp.validated_at,
                    sp.service_request_id, sp.user_id
                FROM service_payments sp
                WHERE sp.receipt_number = $1
            """
            payment = await db.fetchrow(query, receipt_number)

            if not payment:
                logger.warning(f"Receipt verification failed: {receipt_number} not found")
                return ReceiptVerificationResponse(
                    valid=False,
                    receipt_number=receipt_number,
                    message="Recibo no encontrado / Receipt not found"
                )

            # 2. Verify the HMAC token
            paid_at = payment["paid_at"]
            amount = float(payment["total_amount"]) if payment["total_amount"] else 0

            is_valid = receipt_service.verify_receipt_token(
                receipt_number=receipt_number,
                amount=amount,
                paid_at=paid_at,
                provided_token=t
            )

            if not is_valid:
                logger.warning(f"Receipt verification failed: invalid token for {receipt_number}")
                return ReceiptVerificationResponse(
                    valid=False,
                    receipt_number=receipt_number,
                    message="Token de verificacion invalido / Invalid verification token"
                )

            # 3. Get additional data for valid receipt
            # User data
            user_query = "SELECT first_name, last_name FROM users WHERE id = $1"
            user_data = await db.fetchrow(user_query, payment["user_id"])
            payer_name = None
            if user_data:
                payer_name = f"{user_data['first_name'] or ''} {user_data['last_name'] or ''}".strip()

            # Service request data
            workflow_code = None
            entity_code = None
            solicitud_type = None
            service_request_reference = None

            if payment["service_request_id"]:
                sr_query = """
                    SELECT reference, workflow_code, entity_code, solicitud_type
                    FROM service_requests WHERE id = $1
                """
                sr_data = await db.fetchrow(sr_query, payment["service_request_id"])
                if sr_data:
                    workflow_code = sr_data["workflow_code"]
                    entity_code = sr_data["entity_code"]
                    solicitud_type = sr_data["solicitud_type"]
                    service_request_reference = sr_data["reference"]

            # Agent data (if manually validated)
            validated_by_name = None
            if payment["validated_by_agent_id"]:
                agent_query = """
                    SELECT u.first_name, u.last_name
                    FROM users u
                    JOIN agent_profiles ap ON ap.user_id = u.id
                    WHERE u.id = $1
                """
                agent_data = await db.fetchrow(agent_query, payment["validated_by_agent_id"])
                if agent_data:
                    validated_by_name = f"{agent_data['first_name'] or ''} {agent_data['last_name'] or ''}".strip()

            # Format dates
            payment_date_str = paid_at.strftime("%d/%m/%Y %H:%M") if paid_at else None
            validated_at_str = None
            if payment["validated_at"]:
                validated_at_str = payment["validated_at"].strftime("%d/%m/%Y %H:%M")

            logger.info(f"Receipt {receipt_number} verified successfully")

            return ReceiptVerificationResponse(
                valid=True,
                receipt_number=receipt_number,
                message="Recibo valido / Valid receipt",
                payment_date=payment_date_str,
                amount=amount,
                currency=payment["currency"],
                payment_method=payment["payment_method"],
                payer_name=payer_name,
                workflow_code=workflow_code,
                entity_code=entity_code,
                solicitud_type=solicitud_type,
                service_request_reference=service_request_reference,
                validated_by=validated_by_name,
                validated_at=validated_at_str
            )

        except Exception as e:
            logger.error(f"Receipt verification error for {receipt_number}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de verificacion / Verification error"
            )


# ================================================================
# LICENSE VERIFICATION (by LIC-... with HMAC token)
# ================================================================

class LicenseVerificationResponse(BaseModel):
    """Response model for license verification"""
    valid: bool
    license_ref: str
    message: str
    verification_type: Literal["license"] = "license"
    # Only included if valid
    company_name: Optional[str] = None
    nif: Optional[str] = None
    regimen_fiscal: Optional[str] = None
    bundle_name: Optional[str] = None
    commerce_type: Optional[str] = None
    fiscal_year: Optional[int] = None
    status: Optional[str] = None
    total_amount: Optional[float] = None
    amount_paid: Optional[float] = None
    obligations_total: Optional[int] = None
    obligations_paid: Optional[int] = None
    compliance_score: Optional[float] = None
    currency: str = "XAF"


@router.get(
    "/license/{license_ref}",
    response_model=LicenseVerificationResponse,
    summary="Verify commercial license (PUBLIC)",
)
async def verify_license(
    license_ref: str = Path(..., description="License reference (e.g., LIC-2026-A1B2C3D4)"),
    t: str = Query(..., description="HMAC verification token"),
    lid: str = Query(..., description="License UUID"),
):
    """
    Verify commercial license authenticity (PUBLIC - no authentication).
    Validates HMAC token from QR code on printed license PDF.
    """
    from uuid import UUID
    from app.modules.fiscal_services.services.license_pdf_service import LicensePDFService

    # Validate UUID format
    try:
        license_uuid = UUID(lid)
    except (ValueError, AttributeError):
        return LicenseVerificationResponse(
            valid=False, license_ref=license_ref,
            message="Formato de licencia invalido / Invalid license format",
        )

    async with db_manager.get_connection() as db:
        try:
            # Fetch license + company
            row = await db.fetchrow("""
                SELECT cl.id, cl.fiscal_year, cl.status,
                       cl.total_amount, cl.amount_paid,
                       cl.obligations_total, cl.obligations_paid,
                       cl.compliance_score,
                       c.legal_name, c.nif, c.regimen_fiscal,
                       sb.name_es AS bundle_name, sb.commerce_type
                FROM commercial_licenses cl
                JOIN companies c ON cl.company_id = c.id
                LEFT JOIN service_bundles sb ON cl.bundle_id = sb.id
                WHERE cl.id = $1
            """, license_uuid)

            if not row:
                return LicenseVerificationResponse(
                    valid=False, license_ref=license_ref,
                    message="Licencia no encontrada / License not found",
                )

            # Verify HMAC token
            total_str = str(row["total_amount"] or 0)
            if not LicensePDFService.verify_license_token(lid, total_str, t):
                logger.warning(f"License verification failed: invalid token for {license_ref}")
                return LicenseVerificationResponse(
                    valid=False, license_ref=license_ref,
                    message="Token de verificacion invalido / Invalid verification token",
                )

            logger.info(f"License {license_ref} verified successfully")

            return LicenseVerificationResponse(
                valid=True,
                license_ref=license_ref,
                message="Licencia verificada / License verified",
                company_name=row["legal_name"],
                nif=row["nif"],
                regimen_fiscal=row["regimen_fiscal"],
                bundle_name=row["bundle_name"],
                commerce_type=row["commerce_type"],
                fiscal_year=row["fiscal_year"],
                status=row["status"],
                total_amount=float(row["total_amount"]) if row["total_amount"] else None,
                amount_paid=float(row["amount_paid"]) if row["amount_paid"] else None,
                obligations_total=row["obligations_total"],
                obligations_paid=row["obligations_paid"],
                compliance_score=float(row["compliance_score"]) if row["compliance_score"] else None,
            )

        except Exception as e:
            logger.error(f"License verification error for {license_ref}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de verificacion / Verification error"
            )


# =============================================================================
# Certificate Verification (PUBLIC — no authentication)
# =============================================================================

class CertificateVerificationResponse(BaseModel):
    """Public certificate verification result."""
    valid: bool
    certificate_number: str
    message: str
    company_name: Optional[str] = None
    representante_legal: Optional[str] = None
    registration_number: Optional[str] = None
    commerce_type: Optional[str] = None
    zone_code: Optional[str] = None
    city_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    total_amount: Optional[float] = None
    amount_paid: Optional[float] = None
    completed_at: Optional[str] = None


@router.get(
    "/certificate/{certificate_number}",
    response_model=CertificateVerificationResponse,
    summary="Verify commercial license certificate (PUBLIC)",
)
async def verify_certificate(
    certificate_number: str = Path(...),
    t: str = Query(..., description="HMAC token (24 chars)"),
    lid: str = Query(..., description="License UUID"),
):
    """
    Verify certificate authenticity (PUBLIC - no auth).
    Certificate HMAC includes: certificate_number + license_id + amount + fiscal_year.
    """
    from uuid import UUID
    from app.modules.fiscal_services.services.license_pdf_service import LicensePDFService

    try:
        license_uuid = UUID(lid)
    except (ValueError, AttributeError):
        return CertificateVerificationResponse(
            valid=False, certificate_number=certificate_number,
            message="Formato invalido / Invalid format",
        )

    async with db_manager.get_connection() as db:
        try:
            row = await db.fetchrow("""
                SELECT cl.id, cl.fiscal_year, cl.status,
                       cl.total_amount, cl.amount_paid, cl.completed_at,
                       c.legal_name, c.representante_legal,
                       c.registration_number, c.commerce_type,
                       cz.zone_code, ct.name AS city_name
                FROM commercial_licenses cl
                JOIN companies c ON cl.company_id = c.id
                LEFT JOIN commerce_zones cz ON cl.zone_id = cz.id
                LEFT JOIN cities ct ON cl.city_id = ct.id
                WHERE cl.id = $1
            """, license_uuid)

            if not row:
                return CertificateVerificationResponse(
                    valid=False, certificate_number=certificate_number,
                    message="Certificado no encontrado / Certificate not found",
                )

            if row["status"] != "complete":
                return CertificateVerificationResponse(
                    valid=False, certificate_number=certificate_number,
                    message="Licencia no completada / License not complete",
                )

            # Verify certificate-specific HMAC (stronger than license dossier)
            total_str = str(row["total_amount"] or 0)
            year_str = str(row["fiscal_year"] or "")
            if not LicensePDFService.verify_certificate_token(
                certificate_number, lid, total_str, year_str, t
            ):
                logger.warning(f"Certificate verification FAILED: {certificate_number}")
                return CertificateVerificationResponse(
                    valid=False, certificate_number=certificate_number,
                    message="Token invalido — documento posiblemente falsificado / Invalid token — possibly forged",
                )

            logger.info(f"Certificate {certificate_number} verified OK")

            completed_str = None
            if row["completed_at"]:
                try:
                    completed_str = row["completed_at"].strftime("%d/%m/%Y")
                except Exception:
                    completed_str = str(row["completed_at"])

            return CertificateVerificationResponse(
                valid=True,
                certificate_number=certificate_number,
                message="Certificado autentico y valido / Authentic and valid certificate",
                company_name=row["legal_name"],
                representante_legal=row["representante_legal"],
                registration_number=row["registration_number"],
                commerce_type=row["commerce_type"],
                zone_code=row["zone_code"],
                city_name=row["city_name"],
                fiscal_year=row["fiscal_year"],
                total_amount=float(row["total_amount"]) if row["total_amount"] else None,
                amount_paid=float(row["amount_paid"]) if row["amount_paid"] else None,
                completed_at=completed_str,
            )

        except Exception as e:
            logger.error(f"Certificate verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de verificacion / Verification error"
            )
