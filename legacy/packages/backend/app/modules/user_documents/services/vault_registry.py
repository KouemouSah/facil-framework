"""
Vault Registry — Centralized document registration in user_documents.

Every generated document (PDF, receipt, certificate, etc.) should be
registered here so it appears in the citizen's "Mes Documents" vault.

Usage:
    from app.modules.user_documents.services.vault_registry import register_document_in_vault

    await register_document_in_vault(
        conn, user_id=owner_id,
        file_path="licenses/xxx/certificate_LIC-ABCD.pdf",
        file_name="certificate_LIC-ABCD.pdf",
        document_type="LICENSE_CERTIFICATE",
        document_category="fiscal",
        source_request_id=sr_id,
        document_number="CLC-2026-MLB-A2-00001",
        holder_name="Juan Ndong",
        expiry_date=date(2026, 12, 31),
    )

Idempotent: ON CONFLICT (user_id, document_type, document_number)
skips duplicate registrations (safe for event replays).
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


async def register_document_in_vault(
    conn,
    user_id: UUID,
    file_path: str,
    file_name: str,
    document_type: str,
    document_category: str = "fiscal",
    source_request_id: Optional[UUID] = None,
    source_document_id: Optional[UUID] = None,
    document_number: Optional[str] = None,
    holder_name: Optional[str] = None,
    issue_date: Optional[date] = None,
    expiry_date: Optional[date] = None,
    verification_code: Optional[str] = None,
    issuing_authority: str = "Sistema Facil",
    mime_type: str = "application/pdf",
    file_size: int = 0,
    title_es: Optional[str] = None,
    title_fr: Optional[str] = None,
    title_en: Optional[str] = None,
) -> Optional[UUID]:
    """Register a generated document in the user's vault (user_documents).

    Idempotent: if a document with the same (user_id, document_type,
    document_number) already exists, the insert is skipped.

    Args:
        conn: Database connection
        user_id: Owner of the document
        file_path: Firebase Storage path
        file_name: Display filename
        document_type: e.g. LICENSE_CERTIFICATE, PROFORMA_INVOICE, PAYMENT_RECEIPT
        document_category: e.g. fiscal, payments, inspections, identity
        source_request_id: Links document to a service_request (for grouping)
        document_number: Unique identifier (CLC-2026-..., RCP-2026-...)
        holder_name: Name on the document (representante_legal, citizen name)
        issue_date: When the document was issued
        expiry_date: When it expires (e.g. 31/12/fiscal_year for licenses)
        verification_code: HMAC token for QR verification

    Returns:
        UUID of the created document, or None if duplicate.
    """
    doc_id = uuid4()
    today = issue_date or date.today()

    # Title defaults from document_type
    type_titles = {
        "LICENSE_CERTIFICATE": ("Certificado Licencia Comercial", "Certificat Licence Commerciale", "Commercial License Certificate"),
        "PROFORMA_INVOICE": ("Factura Proforma", "Facture Proforma", "Proforma Invoice"),
        "PAYMENT_RECEIPT": ("Recibo de Pago", "Reçu de Paiement", "Payment Receipt"),
        "LICENSE_DOSSIER": ("Expediente de Licencia", "Dossier de Licence", "License Dossier"),
        "VALIDATION_CERTIFICATE": ("Certificado de Validación", "Certificat de Validation", "Validation Certificate"),
        "CITIZEN_SUMMARY": ("Ficha de Solicitud", "Fiche de Demande", "Request Summary"),
        "MISE_EN_DEMEURE": ("Mise en Demeure", "Mise en Demeure", "Formal Notice"),
        "SEAL_ORDER": ("Orden de Scellé", "Ordre de Scellé", "Seal Order"),
        "INSPECTION_REPORT": ("Informe de Inspección", "Rapport d'Inspection", "Inspection Report"),
    }
    defaults = type_titles.get(document_type, (document_type, document_type, document_type))
    t_es = title_es or defaults[0]
    t_fr = title_fr or defaults[1]
    t_en = title_en or defaults[2]

    try:
        row = await conn.fetchrow("""
            INSERT INTO user_documents (
                id, user_id, source, source_request_id, source_document_id,
                generation_type, document_type, document_category,
                file_path, file_name, file_size_bytes, mime_type,
                document_number, holder_name,
                issue_date, expiry_date,
                issuing_authority, verification_code,
                title_es, title_fr, title_en,
                status, is_verified,
                created_at, updated_at
            )
            VALUES (
                $1, $2, 'system_generated', $3, $4,
                'auto', $5, $6,
                $7, $8, $9, $10,
                $11, $12,
                $13, $14,
                $15, $16,
                $17, $18, $19,
                'active', true,
                NOW(), NOW()
            )
            ON CONFLICT DO NOTHING
            RETURNING id
        """,
            doc_id, user_id, source_request_id, source_document_id,
            document_type, document_category,
            file_path, file_name, file_size, mime_type,
            document_number, holder_name,
            today, expiry_date,
            issuing_authority, verification_code,
            t_es, t_fr, t_en,
        )

        if row:
            logger.info(
                "Vault: registered %s %s for user %s (sr=%s)",
                document_type, document_number or doc_id, user_id, source_request_id,
            )
            return row["id"]
        else:
            logger.debug("Vault: duplicate skipped %s %s", document_type, document_number)
            return None

    except Exception as e:
        logger.warning("Vault registration failed for %s: %s", document_type, e)
        return None
