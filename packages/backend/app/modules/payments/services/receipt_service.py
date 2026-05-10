"""
Receipt Service - PDF Receipt Generation & Storage

Generates official payment receipts with:
- Itemized tariff breakdown (TariffBreakdown)
- QR code for mobile verification
- Official Treasury formatting
- Firebase Storage upload
- Email delivery via EventBus

Table: payment_receipts
"""

from typing import Dict, Any, Optional, List
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import base64
import json
import hmac
import hashlib
import asyncpg

from loguru import logger
from jinja2 import Environment, FileSystemLoader

from app.config import settings

# QR Code generation
try:
    import qrcode
    from qrcode.image.pure import PyPNGImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    logger.warning("qrcode not installed. QR code generation will be disabled.")

# PDF generation
try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False
    logger.warning("xhtml2pdf not installed. PDF generation will be disabled.")


# ============================================================================
# TRANSLATIONS
# ============================================================================

RECEIPT_TRANSLATIONS = {
    "es": {
        "receipt_title": "Recibo de Pago",
        "payment_date": "Fecha de Pago",
        "payment_method": "Metodo de Pago",
        "reference": "Referencia",
        "status": "Estado",
        "status_completed": "Pagado",
        "status_pending": "Pendiente",
        "payer_info": "Datos del Pagador",
        "payer_name": "Nombre Completo",
        "payer_dni": "Numero DIP/NIF",
        "payer_email": "Correo Electronico",
        "payer_phone": "Telefono",
        "service_info": "Informacion del Servicio",
        "workflow_code": "Codigo de Tramite",
        "entity_code": "Entidad",
        "request_reference": "Referencia de Solicitud",
        "solicitud_type": "Tipo de Solicitud",
        "payment_breakdown": "Desglose del Pago",
        "concept": "Concepto",
        "quantity": "Cant.",
        "unit_price": "P. Unitario",
        "subtotal": "Subtotal",
        "base_tariff": "Tarifa Base",
        "penalties": "Recargos",
        "total": "TOTAL PAGADO",
        "validated_by": "Validado por",
        "digital_stamp": "Sello Digital",
        "validation_code": "Codigo de Validacion",
        "receipt_number": "No. Recibo",
        "generated_on": "Generado",
        "verification_url": "Verificar en: taxasge.emacsah.com/verify",
        "scan_to_verify": "Escanear para verificar",
        "legal_disclaimer": "Este recibo es valido como comprobante de pago oficial.",
        "legal_notice": "Documento oficial emitido por el Tesoro Publico de la Republica de Guinea Ecuatorial. "
                       "La falsificacion de este documento esta penada por la ley. "
                       "Para verificar la autenticidad, escanee el codigo QR o visite taxasge.emacsah.com/verify",
        # Payment method labels
        "method_cash": "Efectivo",
        "method_check": "Cheque",
        "method_mobile_money": "Mobile Money",
        "method_card": "Tarjeta Bancaria",
        "method_bank_transfer": "Transferencia Bancaria",
        # Solicitud types
        "expedicion": "Nueva Expedicion",
        "renovacion": "Renovacion",
        "duplicado": "Duplicado",
        "NUEVO": "Nuevo",
        "RENOVACION": "Renovacion",
        "PERDIDA": "Por Perdida",
        "ROBO": "Por Robo",
        "DETERIORO": "Por Deterioro",
    },
    "fr": {
        "receipt_title": "Recu de Paiement",
        "payment_date": "Date de Paiement",
        "payment_method": "Mode de Paiement",
        "reference": "Reference",
        "status": "Statut",
        "status_completed": "Paye",
        "status_pending": "En attente",
        "payer_info": "Informations du Payeur",
        "payer_name": "Nom Complet",
        "payer_dni": "Numero DIP/NIF",
        "payer_email": "Email",
        "payer_phone": "Telephone",
        "service_info": "Information du Service",
        "workflow_code": "Code de Procedure",
        "entity_code": "Entite",
        "request_reference": "Reference de Demande",
        "solicitud_type": "Type de Demande",
        "payment_breakdown": "Detail du Paiement",
        "concept": "Concept",
        "quantity": "Qte",
        "unit_price": "P. Unitaire",
        "subtotal": "Sous-total",
        "base_tariff": "Tarif de Base",
        "penalties": "Penalites",
        "total": "TOTAL PAYE",
        "validated_by": "Valide par",
        "digital_stamp": "Cachet Numerique",
        "validation_code": "Code de Validation",
        "receipt_number": "No. Recu",
        "generated_on": "Genere le",
        "verification_url": "Verifier sur: taxasge.emacsah.com/verify",
        "scan_to_verify": "Scanner pour verifier",
        "legal_disclaimer": "Ce recu est valide comme preuve de paiement officielle.",
        "legal_notice": "Document officiel emis par le Tresor Public de la Republique de Guinee Equatoriale. "
                       "La falsification de ce document est punie par la loi. "
                       "Pour verifier l'authenticite, scannez le code QR ou visitez taxasge.emacsah.com/verify",
        # Payment method labels
        "method_cash": "Especes",
        "method_check": "Cheque",
        "method_mobile_money": "Mobile Money",
        "method_card": "Carte Bancaire",
        "method_bank_transfer": "Virement Bancaire",
        # Solicitud types
        "expedicion": "Nouvelle Emission",
        "renovacion": "Renouvellement",
        "duplicado": "Duplicata",
        "NUEVO": "Nouveau",
        "RENOVACION": "Renouvellement",
        "PERDIDA": "Pour Perte",
        "ROBO": "Pour Vol",
        "DETERIORO": "Pour Deterioration",
    },
    "en": {
        "receipt_title": "Payment Receipt",
        "payment_date": "Payment Date",
        "payment_method": "Payment Method",
        "reference": "Reference",
        "status": "Status",
        "status_completed": "Paid",
        "status_pending": "Pending",
        "payer_info": "Payer Information",
        "payer_name": "Full Name",
        "payer_dni": "DIP/NIF Number",
        "payer_email": "Email",
        "payer_phone": "Phone",
        "service_info": "Service Information",
        "workflow_code": "Procedure Code",
        "entity_code": "Entity",
        "request_reference": "Request Reference",
        "solicitud_type": "Request Type",
        "payment_breakdown": "Payment Breakdown",
        "concept": "Concept",
        "quantity": "Qty",
        "unit_price": "Unit Price",
        "subtotal": "Subtotal",
        "base_tariff": "Base Fee",
        "penalties": "Penalties",
        "total": "TOTAL PAID",
        "validated_by": "Validated by",
        "digital_stamp": "Digital Stamp",
        "validation_code": "Validation Code",
        "receipt_number": "Receipt No.",
        "generated_on": "Generated on",
        "verification_url": "Verify at: taxasge.emacsah.com/verify",
        "scan_to_verify": "Scan to verify",
        "legal_disclaimer": "This receipt is valid as official proof of payment.",
        "legal_notice": "Official document issued by the Public Treasury of the Republic of Equatorial Guinea. "
                       "Falsification of this document is punishable by law. "
                       "To verify authenticity, scan the QR code or visit taxasge.emacsah.com/verify",
        # Payment method labels
        "method_cash": "Cash",
        "method_check": "Check",
        "method_mobile_money": "Mobile Money",
        "method_card": "Bank Card",
        "method_bank_transfer": "Bank Transfer",
        # Solicitud types
        "expedicion": "New Issuance",
        "renovacion": "Renewal",
        "duplicado": "Duplicate",
        "NUEVO": "New",
        "RENOVACION": "Renewal",
        "PERDIDA": "For Loss",
        "ROBO": "For Theft",
        "DETERIORO": "For Damage",
    },
}


# ============================================================================
# RECEIPT SERVICE
# ============================================================================

class ReceiptService:
    """
    Service for payment receipt generation.

    Supports:
    - Itemized receipts with tariff breakdown
    - QR code for verification
    - PDF generation with xhtml2pdf
    - Firebase Storage upload
    - Email delivery
    """

    # Template directory
    TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

    # Treasury information (fallback when no location data available)
    TREASURY_INFO_DEFAULT = {
        "name": "Tesoro Publico",
        "ministry": "Ministerio de Hacienda, Economia y Planificacion",
        "address": "Malabo, Guinea Ecuatorial",
        "phone": "+240 333 09 XX XX",
        "nif": "GE-MHEP-001",
    }

    def _get_treasury_info(
        self,
        service_data: Optional[Dict[str, Any]] = None,
        agent_location: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Build treasury info from agent's entity + site.

        For multi-entity support (TESORO / AYUNTAMIENTO / CAMARA_COMERCIO),
        the header uses the entity's human-readable name from
        `agent_location['entity_name']` (e.g. 'Cámara de Comercio') instead
        of the hardcoded 'Tesoro Publico'. Falls back to 'Tesoro Publico'
        for legacy callers that don't pass entity_name.
        """
        info = dict(self.TREASURY_INFO_DEFAULT)
        if agent_location and (agent_location.get("city") or agent_location.get("location_name")):
            entity_name = agent_location.get("entity_name") or "Tesoro Publico"
            site_label = agent_location.get("city") or agent_location.get("location_name", "")
            info["name"] = f"{entity_name} - {site_label}"
            if agent_location.get("location_address"):
                info["address"] = agent_location["location_address"]
            elif agent_location.get("city"):
                info["address"] = f"{agent_location['city']}, Guinea Ecuatorial"
        elif service_data:
            city = service_data.get("city")
            location_address = service_data.get("location_address")
            if location_address:
                info["address"] = location_address
            elif city:
                info["address"] = f"{city}, Guinea Ecuatorial"
        return info

    def _get_logo_base64(self) -> Optional[str]:
        """Load FACIL logo as base64 for PDF embedding."""
        import base64
        # Try multiple possible logo locations
        logo_candidates = [
            Path(__file__).parent.parent / "templates" / "logo.png",
            Path(__file__).parents[4] / "packages" / "web" / "public" / "logo.png",
        ]
        for logo_path in logo_candidates:
            if logo_path.exists():
                try:
                    with open(logo_path, "rb") as f:
                        return base64.b64encode(f.read()).decode("utf-8")
                except Exception:
                    pass
        return None

    # Verification URL base - resolved dynamically from settings
    @property
    def VERIFICATION_URL_BASE(self) -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/verify"

    def __init__(self):
        """Initialize the receipt service with Jinja2 environment"""
        self.env = Environment(
            loader=FileSystemLoader(str(self.TEMPLATES_DIR)),
            autoescape=True
        )

    def _generate_receipt_number(self, payment_date: datetime = None) -> str:
        """Generate unique receipt number. Format: REC-YYYYMMDD-XXXXX"""
        date = payment_date or datetime.now(timezone.utc)
        date_str = date.strftime("%Y%m%d")
        import random
        suffix = str(random.randint(10000, 99999))
        return f"REC-{date_str}-{suffix}"

    async def generate_receipt_number_from_db(self, db: asyncpg.Connection) -> str:
        """Generate unique receipt number using database sequence.

        Uses pg_advisory_xact_lock to prevent race conditions where two
        concurrent calls could generate the same receipt number.
        """
        year = datetime.now(timezone.utc).year
        # Acquire advisory lock to serialize receipt number generation
        await db.execute("SELECT pg_advisory_xact_lock(hashtext('receipt_seq'))")
        result = await db.fetchrow(
            """
            SELECT COALESCE(
                MAX(CAST(SUBSTRING(receipt_number FROM 'REC-\\d{4}-(\\d+)') AS INTEGER)),
                0
            ) + 1 AS next_num
            FROM service_payments
            WHERE receipt_number IS NOT NULL
            AND EXTRACT(YEAR FROM paid_at) = $1
            """,
            year,
        )
        next_num = result["next_num"] if result else 1
        return f"REC-{year}-{next_num:06d}"

    def _generate_verification_token(
        self,
        receipt_number: str,
        amount: float,
        paid_at: datetime
    ) -> str:
        """
        Generate HMAC-SHA256 verification token for receipt authenticity.

        The token is created from receipt data and a secret key, ensuring
        that the receipt cannot be forged without the secret.

        Args:
            receipt_number: Unique receipt number
            amount: Payment amount
            paid_at: Payment timestamp

        Returns:
            Hex-encoded HMAC-SHA256 token (first 16 chars for shorter URLs)
        """
        # Use dedicated permanent secret — never fall back to SECRET_KEY (ephemeral,
        # regenerated on every Cloud Run startup → all old QR tokens become invalid).
        # Fallback order: RECEIPT_VERIFICATION_SECRET → JWT_SECRET_KEY (both permanent).
        secret_key = settings.RECEIPT_VERIFICATION_SECRET
        if not secret_key:
            secret_key = getattr(settings, 'JWT_SECRET_KEY', 'taxasge-receipt-hmac-fallback')

        # Normalize paid_at to UTC-naive to ensure consistency
        # between token generation (RETURNING *) and verification (SELECT)
        if paid_at and paid_at.tzinfo is not None:
            paid_at = paid_at.astimezone(timezone.utc).replace(tzinfo=None)

        # Create message to sign: receipt_number|amount|date
        date_str = paid_at.strftime("%Y%m%d") if paid_at else datetime.now(timezone.utc).strftime("%Y%m%d")
        message = f"{receipt_number}|{amount:.2f}|{date_str}"

        # Generate HMAC-SHA256
        signature = hmac.new(
            secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Return first 16 characters (64 bits of security, sufficient for verification)
        return signature[:16]

    def _generate_verification_url(
        self,
        receipt_number: str,
        amount: float,
        paid_at: datetime
    ) -> str:
        """
        Generate secure verification URL with HMAC token.

        When scanned, this URL takes the user to a verification page
        that validates the token and displays receipt details.

        Args:
            receipt_number: Unique receipt number
            amount: Payment amount
            paid_at: Payment timestamp

        Returns:
            Full verification URL with token
        """
        token = self._generate_verification_token(receipt_number, amount, paid_at)
        return f"{self.VERIFICATION_URL_BASE}/{receipt_number}?t={token}"

    def verify_receipt_token(
        self,
        receipt_number: str,
        amount: float,
        paid_at: datetime,
        provided_token: str
    ) -> bool:
        """
        Verify if a provided token is valid for the given receipt.

        Used by the verification endpoint to confirm receipt authenticity.

        Args:
            receipt_number: Receipt number from URL
            amount: Amount from database
            paid_at: Payment date from database
            provided_token: Token from URL query parameter

        Returns:
            True if token is valid, False otherwise
        """
        expected_token = self._generate_verification_token(receipt_number, amount, paid_at)
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_token, provided_token)

    def _generate_qr_code(self, data: str) -> str:
        """Generate QR code as base64 PNG image."""
        if not QRCODE_AVAILABLE:
            return ""

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=2,
            )
            qr.add_data(data)
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            return base64.b64encode(buffer.read()).decode("utf-8")

        except Exception as e:
            logger.error(f"QR code generation failed: {e}")
            return ""

    def _format_amount(self, amount: Any, currency: str = "XAF") -> str:
        """Format amount with thousands separator."""
        try:
            num = float(amount) if amount else 0
            return f"{int(num):,} {currency}".replace(",", " ")
        except (ValueError, TypeError):
            return f"0 {currency}"

    def _get_payment_method_label(self, method: str, language: str) -> str:
        """Get localized payment method label."""
        texts = RECEIPT_TRANSLATIONS.get(language, RECEIPT_TRANSLATIONS["es"])
        method_map = {
            "cash": texts["method_cash"],
            "check": texts["method_check"],
            "mobile_money": texts["method_mobile_money"],
            "card": texts["method_card"],
            "bank_transfer": texts["method_bank_transfer"],
        }
        return method_map.get(method, method.replace("_", " ").title())

    def _parse_calculation_details(
        self,
        calculation_details: Optional[Dict[str, Any]],
        currency: str = "XAF"
    ) -> Dict[str, Any]:
        """Parse calculation_details (TariffBreakdown) for receipt display."""
        if not calculation_details:
            return {
                "has_breakdown": False,
                "base_amount": 0,
                "base_description": "",
                "base_amount_formatted": self._format_amount(0, currency),
                "supplements": [],
                "supplements_total": 0,
                "supplements_total_formatted": self._format_amount(0, currency),
                "penalties_amount": 0,
                "penalty_reason": None,
                "penalties_formatted": self._format_amount(0, currency),
                "total_amount": 0,
                "total_formatted": self._format_amount(0, currency),
                "currency": currency,
            }

        # Bundle payment detection (P8.2 X8 fix).
        # Bundle calc_details has a different shape than the legacy
        # TariffBreakdown: {obligations:[...], target_entity, processing_mode,
        # license_id} instead of {base_amount, supplements, total_amount, ...}.
        # Without this branch every bundle receipt PDF rendered every amount
        # as 0 XAF because legacy keys do not exist — the user observed
        # recibo_REC-2026-000011 showing 0 for a 353 250 XAF validated split,
        # which is a legal risk (false official document). We preserve the
        # legacy path untouched for non-bundle workflows.
        is_bundle = (
            "obligations" in calculation_details
            and "target_entity" in calculation_details
        )

        if is_bundle:
            obligations = calculation_details.get("obligations") or []
            target_entity = calculation_details.get("target_entity") or ""

            base_total = sum(float(ob.get("amount", 0) or 0) for ob in obligations)
            penalties_total = sum(float(ob.get("penalty", 0) or 0) for ob in obligations)
            grand_total = base_total + penalties_total

            # Human-readable fee_type fallback for obligations without a
            # resolved fiscal_service name (legacy calc_details).
            fee_type_labels = {
                "tesoro": "Obligacion al Tesoro",
                "municipal": "Tasa Municipal (Ayuntamiento)",
                "chamber": "Cuota Camara de Comercio",
            }

            supplements_list: List[Dict[str, Any]] = []
            for ob in obligations:
                amt = float(ob.get("amount", 0) or 0)
                fee_type = (ob.get("fee_type") or "").lower()
                ob_id = str(ob.get("id") or "")
                # Prefer the fiscal_service name snapshotted at bundle creation
                # (P8.2-X8 follow-up). Fall back to the fee_type label so older
                # bundle calc_details generated before the snapshot still render
                # a meaningful row instead of a bare "Obligacion" string.
                ob_name = ob.get("name")
                if not ob_name:
                    ob_name = fee_type_labels.get(fee_type) or "Obligacion"
                # Decode raw unicode escapes from legacy BD data (e.g.
                # 'abacer\\u00edas' stored literally instead of 'abacerías')
                if ob_name and "\\u00" in ob_name:
                    try:
                        ob_name = ob_name.encode("utf-8").decode("unicode_escape")
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        pass
                code = ob.get("code") or (ob_id[:8] if ob_id else "")
                supplements_list.append({
                    "code": code,
                    "name_es": ob_name,
                    "unit_price": amt,
                    "unit_price_formatted": self._format_amount(amt, currency),
                    "quantity": 1,
                    "subtotal": amt,
                    "subtotal_formatted": self._format_amount(amt, currency),
                })

            return {
                "has_breakdown": True,
                # Section header row: show a label but empty amount cell so it
                # acts visually as a section heading above the itemized list.
                "base_amount": 0,
                "base_description": (
                    f"Paquete fiscal - {target_entity} ({len(obligations)} items)"
                    if target_entity
                    else f"Paquete de obligaciones fiscales ({len(obligations)} items)"
                ),
                "base_amount_formatted": "",
                "supplements": supplements_list,
                "supplements_total": base_total,
                "supplements_total_formatted": self._format_amount(base_total, currency),
                "penalties_amount": penalties_total,
                "penalty_reason": "Recargos" if penalties_total > 0 else None,
                "penalties_formatted": self._format_amount(penalties_total, currency),
                "total_amount": grand_total,
                "total_formatted": self._format_amount(grand_total, currency),
                "currency": currency,
                "tariff_type": "BUNDLE",
                "workflow_code": "BUNDLE_PAYMENT",
                "solicitud_type": None,
            }

        base_amount = calculation_details.get("base_amount", 0)
        supplements = calculation_details.get("supplements", [])
        supplements_total = calculation_details.get("supplements_total", 0)
        penalties_amount = calculation_details.get("penalties_amount", 0)
        total_amount = calculation_details.get("total_amount", 0)

        return {
            "has_breakdown": True,
            "base_amount": base_amount,
            "base_description": calculation_details.get("base_description", ""),
            "base_amount_formatted": self._format_amount(base_amount, currency),
            "supplements": [
                {
                    "code": s.get("code", ""),
                    "name_es": s.get("name_es", s.get("name", "")),
                    "unit_price": s.get("unit_price", 0),
                    "unit_price_formatted": self._format_amount(s.get("unit_price", 0), currency),
                    "quantity": s.get("quantity", 1),
                    "subtotal": s.get("subtotal", 0),
                    "subtotal_formatted": self._format_amount(s.get("subtotal", 0), currency),
                }
                for s in supplements
            ],
            "supplements_total": supplements_total,
            "supplements_total_formatted": self._format_amount(supplements_total, currency),
            "penalties_amount": penalties_amount,
            "penalty_reason": calculation_details.get("penalty_reason"),
            "penalties_formatted": self._format_amount(penalties_amount, currency),
            "total_amount": total_amount,
            "total_formatted": self._format_amount(total_amount, currency),
            "currency": currency,
            "tariff_type": calculation_details.get("tariff_type", "FIXED"),
            "workflow_code": calculation_details.get("workflow_code"),
            "solicitud_type": calculation_details.get("solicitud_type"),
        }

    async def generate_receipt_pdf(
        self,
        receipt_number: str,
        payment_data: Dict[str, Any],
        user_data: Dict[str, Any],
        service_data: Optional[Dict[str, Any]] = None,
        validated_by: Optional[str] = None,
        validated_by_name: Optional[str] = None,
        validated_at: Optional[datetime] = None,
        language: str = "es",
        agent_location: Optional[Dict[str, str]] = None,
    ) -> bytes:
        """
        Generate a PDF receipt for a completed payment.

        Args:
            receipt_number: Unique receipt number
            payment_data: Payment information (from service_payments)
            user_data: Payer information
            service_data: Service/workflow information
            validated_by: Agent ID who validated (for manual payments)
            validated_by_name: Agent name
            validated_at: Validation timestamp
            language: Language for the receipt (es, fr, en)

        Returns:
            PDF bytes
        """
        if not XHTML2PDF_AVAILABLE:
            raise RuntimeError("xhtml2pdf is not installed. Cannot generate PDF.")

        # Get translations
        texts = RECEIPT_TRANSLATIONS.get(language, RECEIPT_TRANSLATIONS["es"])

        # Parse calculation details
        calculation_details = payment_data.get("calculation_details")
        if isinstance(calculation_details, str):
            try:
                calculation_details = json.loads(calculation_details)
            except json.JSONDecodeError:
                calculation_details = None

        currency = payment_data.get("currency", "XAF")
        breakdown = self._parse_calculation_details(calculation_details, currency)

        # If no breakdown, create simple one from payment amounts
        if not breakdown["has_breakdown"]:
            total = payment_data.get("total_amount", 0)
            breakdown = {
                "has_breakdown": False,
                "base_amount": total,
                "base_description": texts["base_tariff"],
                "base_amount_formatted": self._format_amount(total, currency),
                "supplements": [],
                "supplements_total": 0,
                "supplements_total_formatted": self._format_amount(0, currency),
                "penalties_amount": 0,
                "penalty_reason": None,
                "penalties_formatted": self._format_amount(0, currency),
                "total_amount": total,
                "total_formatted": self._format_amount(total, currency),
                "currency": currency,
            }

        # Prepare payer data
        first_name = user_data.get("first_name", "")
        last_name = user_data.get("last_name", "")
        payer = {
            "name": f"{first_name} {last_name}".strip() or user_data.get("email", "N/A"),
            "email": user_data.get("email"),
            "phone": user_data.get("phone"),
            "dni": user_data.get("document_number") or user_data.get("dni") or user_data.get("nif"),
        }

        # Payment method label
        payment_method = payment_data.get("payment_method", "cash")
        payment_method_label = self._get_payment_method_label(payment_method, language)

        # Service information (workflow_code, solicitud_type, entity_code)
        service_request_reference = None
        solicitud_type = None
        solicitud_type_label = None
        workflow_code = None
        entity_code = None

        if service_data:
            service_request_reference = service_data.get("reference") or service_data.get("request_number")
            solicitud_type = service_data.get("solicitud_type")
            workflow_code = service_data.get("workflow_code")
            entity_code = service_data.get("entity_code")
            if solicitud_type:
                solicitud_type_label = texts.get(solicitud_type, solicitud_type)

        # For bundle splits, prefer the payment's own entity_code over the SR's
        # primary entity. A CAMARA_COMERCIO split receipt should show
        # "Entidad: Cámara de Comercio", not "Entidad: TESORO" (the SR primary).
        if payment_data.get("entity_code"):
            entity_code = payment_data["entity_code"]

        # Resolve raw entity_code to human-readable name when agent_location
        # carries the entity_name (populated by the validate_payment caller).
        if entity_code and agent_location and agent_location.get("entity_name"):
            entity_code = agent_location["entity_name"]

        # Payment date
        paid_at = payment_data.get("paid_at") or payment_data.get("created_at") or datetime.now(timezone.utc)
        if isinstance(paid_at, str):
            try:
                paid_at = datetime.fromisoformat(paid_at.replace("Z", "+00:00"))
            except ValueError:
                paid_at = datetime.now(timezone.utc)
        payment_date = paid_at.strftime("%d/%m/%Y %H:%M")

        # Generate secure verification URL for QR code (HMAC-signed)
        # Use payment_data["total_amount"] (DB column) to match verification endpoint
        # which also reads from sp.total_amount — NOT breakdown which comes from calculation_details JSON
        db_amount = payment_data.get("total_amount")
        receipt_amount = float(db_amount if db_amount is not None else breakdown["total_amount"])
        verification_url = self._generate_verification_url(
            receipt_number=receipt_number,
            amount=receipt_amount,
            paid_at=paid_at
        )
        qr_code_base64 = self._generate_qr_code(verification_url)

        # Validation info
        validated_at_str = None
        if validated_at:
            if isinstance(validated_at, str):
                validated_at_str = validated_at
            else:
                validated_at_str = validated_at.strftime("%d/%m/%Y %H:%M")

        # Render template
        template = self.env.get_template("payment_receipt.html")
        html_content = template.render(
            language=language,
            texts=texts,
            receipt_number=receipt_number,
            payment_date=payment_date,
            payment_reference=payment_data.get("payment_reference", "-"),
            payment_method=payment_method,
            payment_method_label=payment_method_label,
            payer=payer,
            breakdown=breakdown,
            # Service info: workflow_code, solicitud_type, entity_code (no service_name)
            service_request_reference=service_request_reference,
            solicitud_type=solicitud_type,
            solicitud_type_label=solicitud_type_label,
            workflow_code=workflow_code,
            entity_code=entity_code,
            # Validation info (digital stamp for all payment types)
            validated_by=validated_by,
            validated_by_name=validated_by_name,
            validated_at=validated_at_str,
            treasury=self._get_treasury_info(service_data, agent_location),
            # Logo for PDF header
            logo_base64=self._get_logo_base64(),
            # QR code with secure verification URL
            verification_url=verification_url,
            qr_code_base64=qr_code_base64,
            generated_at=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        )

        # Convert HTML to PDF
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(
            src=html_content,
            dest=pdf_buffer,
            encoding="utf-8"
        )

        if pisa_status.err:
            logger.error(f"PDF generation error: {pisa_status.err}")
            raise RuntimeError(f"Failed to generate PDF: {pisa_status.err}")

        pdf_buffer.seek(0)
        pdf_bytes = pdf_buffer.read()

        logger.info(f"Generated receipt PDF {receipt_number} ({len(pdf_bytes)} bytes)")

        return pdf_bytes

    async def generate_and_store_receipt(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        user_id: str,
        payment_data: Dict[str, Any],
        user_data: Dict[str, Any],
        service_data: Optional[Dict[str, Any]] = None,
        validated_by: Optional[str] = None,
        validated_by_name: Optional[str] = None,
        validated_at: Optional[datetime] = None,
        language: str = "es",
        agent_location: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate receipt PDF and store in Firebase Storage.

        Args:
            db: Database connection
            payment_id: Payment ID
            user_id: User ID (for storage path)
            payment_data: Payment information
            user_data: Payer information
            service_data: Service/workflow information
            validated_by: Agent ID who validated
            validated_by_name: Agent name
            validated_at: Validation timestamp
            language: Language for the receipt
            agent_location: Agent's treasury office location (from entity_locations)

        Returns:
            Dict with receipt_number, receipt_url, file_path
        """
        from app.modules.documents.services.storage_service import firebase_storage_service

        # Generate receipt number
        receipt_number = await self.generate_receipt_number_from_db(db)

        # Generate PDF
        pdf_bytes = await self.generate_receipt_pdf(
            receipt_number=receipt_number,
            payment_data=payment_data,
            user_data=user_data,
            service_data=service_data,
            validated_by=validated_by,
            validated_by_name=validated_by_name,
            validated_at=validated_at,
            language=language,
            agent_location=agent_location,
        )

        # Upload to Firebase Storage
        service_request_id = payment_data.get("service_request_id", payment_id)
        filename = f"receipt_{receipt_number}.pdf"

        try:
            upload_result = await firebase_storage_service.upload_tax_attachment(
                application_id=str(service_request_id),
                file=pdf_bytes,
                allowed_users=[user_id],
                metadata={
                    "filename": filename,
                    "mime_type": "application/pdf",
                    "document_type": "payment_receipt",
                    "receipt_number": receipt_number,
                    "payment_id": payment_id,
                }
            )
            receipt_url = upload_result.file_url
            file_path = upload_result.file_path
        except Exception as e:
            logger.error(f"Failed to upload receipt to storage: {e}")
            # Continue without storage - receipt was generated
            receipt_url = None
            file_path = None

        # Update payment with receipt info
        update_query = """
            UPDATE service_payments
            SET receipt_number = $1, receipt_url = $2, updated_at = NOW()
            WHERE id = $3
        """
        await db.execute(update_query, receipt_number, receipt_url, payment_id)

        # Store in payment_receipts table for audit trail
        try:
            import uuid
            insert_query = """
                INSERT INTO payment_receipts (
                    id, service_payment_id, receipt_number, file_path,
                    file_size_bytes, qr_code_data, generated_at, generated_by
                ) VALUES ($1, $2::uuid, $3, $4, $5, $6, NOW(), $7)
                ON CONFLICT (receipt_number) DO NOTHING
            """
            await db.execute(
                insert_query,
                str(uuid.uuid4()), payment_id, receipt_number,
                receipt_url, 0, None, None,
            )
        except Exception as e:
            logger.warning(f"Could not insert into payment_receipts: {e}")

        # Register in user's vault (Mes Documents)
        if receipt_url:
            try:
                from uuid import UUID as _UUID
                from app.modules.user_documents.services.vault_registry import register_document_in_vault
                await register_document_in_vault(
                    db,
                    user_id=_UUID(user_id),
                    file_path=receipt_url,
                    file_name=filename,
                    document_type="PAYMENT_RECEIPT",
                    document_category="payments",
                    source_request_id=_UUID(str(service_request_id)) if service_request_id else None,
                    document_number=receipt_number,
                    holder_name=user_data.get("full_name") or user_data.get("name") or "",
                )
            except Exception as vault_err:
                logger.warning(f"Vault registration failed for receipt {receipt_number}: {vault_err}")

        logger.info(f"Receipt {receipt_number} generated and stored for payment {payment_id}")

        # Auto-register in user vault (Documents > Generados tab)
        if file_path and user_id:
            try:
                from uuid import UUID as _UUID
                from app.modules.user_documents.services.user_documents_service import (
                    user_documents_service,
                )
                # Regenerate the verification token for vault metadata
                db_amount = float(payment_data.get("total_amount") or 0)
                paid_at_val = payment_data.get("paid_at") or validated_at
                vault_token = self._generate_verification_token(
                    receipt_number, db_amount, paid_at_val
                )
                await user_documents_service.auto_import_generated(
                    db=db,
                    user_id=_UUID(str(user_id)),
                    generation_type="payment_receipt",
                    file_path=file_path,
                    file_name=filename,
                    file_size_bytes=len(pdf_bytes),
                    mime_type="application/pdf",
                    title_es="Recibo de Pago",
                    title_fr="Recu de Paiement",
                    title_en="Payment Receipt",
                    reference_number=receipt_number,
                    service_request_id=(
                        _UUID(str(service_request_id)) if service_request_id else None
                    ),
                    verification_code=vault_token,
                )
                logger.info(
                    f"Receipt {receipt_number} registered in user vault for {user_id}"
                )
            except Exception as e:
                logger.warning(f"Could not register receipt in user vault: {e}")

        return {
            "receipt_number": receipt_number,
            "receipt_url": receipt_url,
            "file_path": file_path,
            "pdf_size_bytes": len(pdf_bytes),
            "pdf_bytes": pdf_bytes,
        }

    async def get_receipt_download_url(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        user_id: str,
    ) -> Optional[str]:
        """Get download URL for existing receipt."""
        from app.modules.documents.services.storage_service import firebase_storage_service

        # Get receipt info from database
        query = """
            SELECT receipt_number, receipt_url
            FROM service_payments
            WHERE id = $1
        """
        result = await db.fetchrow(query, payment_id)

        if not result or not result["receipt_url"]:
            return None

        # Generate fresh signed URL if needed
        # The stored URL may have expired
        try:
            # For now, return stored URL
            # TODO: Regenerate signed URL if expired
            return result["receipt_url"]
        except Exception as e:
            logger.error(f"Failed to get receipt URL: {e}")
            return None


# Singleton instance
receipt_service = ReceiptService()
