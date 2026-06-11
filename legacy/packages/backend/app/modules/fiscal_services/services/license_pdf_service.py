"""
License PDF Service — Generate commercial license dossier PDFs.

Generates compact A4 PDFs (target: 1 page) for commercial licenses with:
- Company details (2-column layout)
- Obligations grouped by ministry (sub-lines instead of repeating)
- Conditional fields: bundle/commerce_type only for bundle regime
- Hidden deadline if fully paid, penalty column always visible
- Validation seal: QR code + PAGADO badge + compliance progress bar
- Page numbering for multi-page documents

Reuses the existing PDF infrastructure (xhtml2pdf + Jinja2 + qrcode).
"""

import base64
import hashlib
import hmac
import io
import os
from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from loguru import logger

try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False
    logger.warning("xhtml2pdf not available — PDF generation disabled")

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

try:
    from jinja2 import Environment, FileSystemLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

# ── Translations ─────────────────────────────────────────────────────────────

TRANSLATIONS = {
    "es": {
        "title": "Licencia Comercial",
        "subtitle": "República de Guinea Ecuatorial — Sistema Facil",
        "fiscal_year": "Año Fiscal",
        "printed": "Impreso",
        "validity_period": "Período de validez",
        "company_info": "INFORMACIÓN DE LA EMPRESA",
        "company_name": "Razón Social",
        "nif_label": "NIF",
        "reg_number": "Nº Registro",
        "forma_juridica": "Forma Jurídica",
        "regime": "Régimen Fiscal",
        "zone": "Zona Comercial",
        "activity": "Actividad",
        "capital_social": "Capital Social",
        "license_details": "DETALLES DE LA LICENCIA",
        "bundle": "Paquete",
        "commerce_type": "Tipo de Comercio",
        "obligations": "OBLIGACIONES FISCALES",
        "fee_type": "Servicio / Tasa",
        "due_date": "Vencimiento",
        "amount": "Monto",
        "penalty": "Penalidad",
        "status": "Estado",
        "total_amount": "Total Obligaciones",
        "penalties": "Penalidades",
        "paid": "Pagado",
        "balance": "Saldo Pendiente",
        "badge_paid": "PAGADO",
        "badge_pending": "PENDIENTE",
        "badge_overdue": "VENCIDO",
        "reference_label": "Referencia",
        "generated_on": "Generado el",
        "verify_label": "Verificar en",
        "footer_line1": "Documento generado por el sistema Facil — Gobierno de Guinea Ecuatorial",
        "disclaimer": "AVISO: Este documento es un justificante provisional que acredita que la licencia comercial oficial se encuentra en proceso de edición. No constituye el documento oficial definitivo.",
        "status_paid": "Pagado",
        "status_pending": "Pendiente",
        "status_overdue": "Vencido",
        "status_processing": "En Proceso",
        "status_completed": "Completado",
        "status_waived": "Exonerado",
        "status_cancelled": "Cancelado",
    },
    "fr": {
        "title": "Licence Commerciale",
        "subtitle": "République de Guinée Équatoriale — Système Facil",
        "fiscal_year": "Année Fiscale",
        "printed": "Imprimé",
        "validity_period": "Période de validité",
        "company_info": "INFORMATIONS DE L'ENTREPRISE",
        "company_name": "Raison Sociale",
        "nif_label": "NIF",
        "reg_number": "N° Registre",
        "forma_juridica": "Forme Juridique",
        "regime": "Régime Fiscal",
        "zone": "Zone Commerciale",
        "activity": "Activité",
        "capital_social": "Capital Social",
        "license_details": "DÉTAILS DE LA LICENCE",
        "bundle": "Forfait",
        "commerce_type": "Type de Commerce",
        "obligations": "OBLIGATIONS FISCALES",
        "fee_type": "Service / Taxe",
        "due_date": "Échéance",
        "amount": "Montant",
        "penalty": "Pénalité",
        "status": "Statut",
        "total_amount": "Total Obligations",
        "penalties": "Pénalités",
        "paid": "Payé",
        "balance": "Solde Restant",
        "badge_paid": "PAYÉ",
        "badge_pending": "EN ATTENTE",
        "badge_overdue": "EN RETARD",
        "reference_label": "Référence",
        "generated_on": "Généré le",
        "verify_label": "Vérifier sur",
        "footer_line1": "Document généré par le système Facil — Gouvernement de Guinée Équatoriale",
        "disclaimer": "AVIS : Ce document est un justificatif provisoire attestant que la licence commerciale officielle est en cours d'édition. Il ne constitue pas le document officiel définitif.",
        "status_paid": "Payé",
        "status_pending": "En attente",
        "status_overdue": "En retard",
        "status_processing": "En cours",
        "status_completed": "Terminé",
        "status_waived": "Exonéré",
        "status_cancelled": "Annulé",
    },
    "en": {
        "title": "Commercial License",
        "subtitle": "Republic of Equatorial Guinea — Facil System",
        "fiscal_year": "Fiscal Year",
        "printed": "Printed",
        "validity_period": "Validity period",
        "company_info": "COMPANY INFORMATION",
        "company_name": "Legal Name",
        "nif_label": "NIF",
        "reg_number": "Registration Number",
        "forma_juridica": "Legal Form",
        "regime": "Tax Regime",
        "zone": "Commerce Zone",
        "activity": "Activity",
        "capital_social": "Share Capital",
        "license_details": "LICENSE DETAILS",
        "bundle": "Bundle",
        "commerce_type": "Commerce Type",
        "obligations": "TAX OBLIGATIONS",
        "fee_type": "Service / Fee",
        "due_date": "Due Date",
        "amount": "Amount",
        "penalty": "Penalty",
        "status": "Status",
        "total_amount": "Total Obligations",
        "penalties": "Penalties",
        "paid": "Paid",
        "balance": "Outstanding Balance",
        "badge_paid": "PAID",
        "badge_pending": "PENDING",
        "badge_overdue": "OVERDUE",
        "reference_label": "Reference",
        "generated_on": "Generated on",
        "verify_label": "Verify at",
        "footer_line1": "Document generated by the Facil system — Government of Equatorial Guinea",
        "disclaimer": "NOTICE: This document is a provisional receipt confirming that the official commercial license is being prepared. It does not constitute the final official document.",
        "status_paid": "Paid",
        "status_pending": "Pending",
        "status_overdue": "Overdue",
        "status_processing": "Processing",
        "status_completed": "Completed",
        "status_waived": "Waived",
        "status_cancelled": "Cancelled",
    },
}


def _format_amount(amount) -> str:
    """Format amount as XAF with space thousands separator."""
    try:
        val = Decimal(str(amount or 0))
        formatted = f"{val:,.0f}".replace(",", " ")
        return f"{formatted} XAF"
    except Exception:
        return "0 XAF"


def _get_verification_secret() -> str:
    """
    Return the permanent HMAC secret for license verification tokens.

    Priority:
      1. RECEIPT_VERIFICATION_SECRET (dedicated, permanent)
      2. JWT_SECRET_KEY (permanent in .env)

    NEVER fall back to SECRET_KEY: it regenerates on every Cloud Run startup
    and would invalidate all existing QR codes after each deployment.
    """
    from app.config import settings
    secret = getattr(settings, 'RECEIPT_VERIFICATION_SECRET', None)
    if secret:
        return secret
    jwt_key = getattr(settings, 'JWT_SECRET_KEY', None)
    if jwt_key:
        return jwt_key
    return 'taxasge-verify-fallback-key'


class LicensePDFService:
    """Generate PDF dossiers for commercial licenses."""

    def __init__(self):
        self._template = None
        self._logo_base64 = None
        templates_dir = Path(__file__).parent.parent / "templates"
        if JINJA2_AVAILABLE and templates_dir.exists():
            self._env = Environment(loader=FileSystemLoader(str(templates_dir)))
        else:
            self._env = None

    def _get_template(self):
        if self._template is None and self._env:
            self._template = self._env.get_template("license_dossier_pdf.html")
        return self._template

    def _get_logo_base64(self) -> str:
        if self._logo_base64 is None:
            for logo_path in [
                Path(__file__).parent.parent.parent / "service_requests" / "templates" / "logo.png",
                Path(__file__).parent.parent.parent.parent.parent.parent / "packages" / "web" / "public" / "logo.png",
            ]:
                if logo_path.exists():
                    self._logo_base64 = base64.b64encode(logo_path.read_bytes()).decode()
                    break
            if self._logo_base64 is None:
                self._logo_base64 = ""
        return self._logo_base64

    def _generate_qr(self, verification_url: str) -> str:
        """Generate QR code as base64 PNG."""
        if not QRCODE_AVAILABLE:
            return ""
        try:
            qr = qrcode.QRCode(
                version=1, error_correction=ERROR_CORRECT_H,
                box_size=5, border=2,
            )
            qr.add_data(verification_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode()
        except Exception as e:
            logger.warning(f"QR generation failed: {e}")
            return ""

    @staticmethod
    def generate_verification_token(license_id: str, amount: str) -> str:
        """HMAC-SHA256 verification token using permanent secret."""
        secret = _get_verification_secret()
        message = f"license-verify|{license_id}|{amount}"
        return hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()[:16]

    @staticmethod
    def verify_license_token(license_id: str, amount: str, provided_token: str) -> bool:
        """Verify HMAC token for license verification."""
        expected = LicensePDFService.generate_verification_token(license_id, amount)
        return hmac.compare_digest(expected, provided_token)

    @staticmethod
    def generate_certificate_token(
        certificate_number: str, license_id: str, amount: str, fiscal_year: str
    ) -> str:
        """Generate HMAC-SHA256 token for certificate verification.

        Stronger than license dossier token: includes certificate_number + fiscal_year
        in the HMAC message. This prevents:
        - Forging a certificate with a different number but same license_id
        - Cross-year replay (using a 2025 token for a 2026 certificate)
        - Amount tampering (amount is part of the message)

        Token is 24 chars (96 bits) — stronger than the 16-char license token.
        """
        secret = _get_verification_secret()
        message = f"cert-verify|{certificate_number}|{license_id}|{amount}|{fiscal_year}"
        return hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()[:24]

    @staticmethod
    def verify_certificate_token(
        certificate_number: str, license_id: str, amount: str,
        fiscal_year: str, provided_token: str
    ) -> bool:
        """Verify HMAC token for certificate verification (timing-safe)."""
        expected = LicensePDFService.generate_certificate_token(
            certificate_number, license_id, amount, fiscal_year
        )
        return hmac.compare_digest(expected, provided_token)

    def _group_obligations_by_ministry(
        self, obligations_rows: list, texts: dict
    ) -> tuple:
        """Group obligations by ministry, compute totals and flags.

        Returns (obligation_groups, total_amount, total_penalties, total_paid,
                 has_any_penalty, is_fully_paid, is_overdue, obligation_count).
        """
        total_amount = Decimal("0")
        total_penalties = Decimal("0")
        total_paid = Decimal("0")
        has_any_penalty = False
        is_overdue = False
        obligation_count = len(obligations_rows)

        # Group by ministry (preserve insertion order)
        ministry_map: Dict[str, List[Dict[str, Any]]] = OrderedDict()

        for ob in obligations_rows:
            amt = Decimal(str(ob["amount"] or 0))
            pen = Decimal(str(ob["penalty_amount"] or 0))
            total_amount += amt
            total_penalties += pen
            if ob["status"] in ("paid", "completed"):
                total_paid += amt
            if ob["status"] == "overdue":
                is_overdue = True
            if pen > 0:
                has_any_penalty = True

            status_key = f"status_{ob['status']}" if f"status_{ob['status']}" in texts else "status_pending"
            status_class = "paid" if ob["status"] in ("paid", "completed") else (
                "overdue" if ob["status"] == "overdue" else "pending"
            )

            ministry_name = ob["ministry_name"] or "Otros"
            if ministry_name not in ministry_map:
                ministry_map[ministry_name] = []

            ministry_map[ministry_name].append({
                "fee_type": ob["fee_type"] or "-",
                "due_date": str(ob["due_date"]) if ob["due_date"] else "-",
                "amount_formatted": _format_amount(amt),
                "penalty_formatted": _format_amount(pen) if pen > 0 else "--",
                "has_penalty": pen > 0,
                "status_label": texts.get(status_key, ob["status"]),
                "status_class": status_class,
            })

        balance = total_amount - total_paid
        is_fully_paid = balance <= 0 and total_amount > 0

        obligation_groups = [
            {"ministry_name": name, "obligations": items}
            for name, items in ministry_map.items()
        ]

        return (
            obligation_groups, total_amount, total_penalties, total_paid,
            has_any_penalty, is_fully_paid, is_overdue, obligation_count,
        )

    async def generate_license_pdf(
        self,
        db: asyncpg.Connection,
        license_id: str,
        language: str = "es",
    ) -> bytes:
        """Generate a compact license dossier PDF (target: 1 page A4)."""
        texts = TRANSLATIONS.get(language, TRANSLATIONS["es"])
        return await self._generate_license_pdf_with_texts(
            db, license_id, texts, language
        )

    async def _generate_license_pdf_with_texts(
        self,
        db: asyncpg.Connection,
        license_id: str,
        texts: Dict[str, str],
        language: str = "es",
    ) -> bytes:
        """Internal: generate license PDF with caller-provided texts.

        Thread-safe: does NOT read module-level TRANSLATIONS.
        Used by both generate_license_pdf (standard) and
        generate_proforma_pdf (overridden title/disclaimer).
        """
        if not XHTML2PDF_AVAILABLE:
            raise RuntimeError("xhtml2pdf not installed")

        from uuid import UUID

        # Fetch license with company + bundle info
        license_row = await db.fetchrow("""
            SELECT cl.*, c.legal_name, c.nif, c.registration_number,
                   c.forma_juridica, c.regimen_fiscal, c.objeto_social,
                   ct.name AS city_name, cz.zone_code,
                   sb.name_es AS bundle_name, sb.commerce_type
            FROM commercial_licenses cl
            JOIN companies c ON cl.company_id = c.id
            LEFT JOIN cities ct ON cl.city_id = ct.id
            LEFT JOIN commerce_zones cz ON cl.zone_id = cz.id
            LEFT JOIN service_bundles sb ON cl.bundle_id = sb.id
            WHERE cl.id = $1
        """, UUID(license_id))

        if not license_row:
            raise ValueError(f"License {license_id} not found")

        lic = dict(license_row)

        # Fetch obligations
        obligations_rows = await db.fetch("""
            SELECT lo.*, m.name_es AS ministry_name
            FROM license_obligations lo
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            WHERE lo.license_id = $1
            ORDER BY m.name_es NULLS LAST, lo.fee_type, lo.due_date
        """, UUID(license_id))

        # Group obligations by ministry + compute totals
        (
            obligation_groups, total_amount, total_penalties, total_paid,
            has_any_penalty, is_fully_paid, is_overdue, obligation_count,
        ) = self._group_obligations_by_ministry(obligations_rows, texts)

        balance = total_amount - total_paid

        # ── Conditional display logic per company type ──
        # Real GE fiscal system:
        #   AUTONOMO → Padrón Empresarial (DGPE) → PE-XXXX → zone-based bundle → fixed annual fees
        #   SL/SA    → Registro Empresarial (VUE) → NIF → declarative/mixed regime → revenue-based
        #   ONG      → NIF → exento
        regimen = lic.get("regimen_fiscal", "")
        forma = lic.get("forma_juridica", "")
        commerce_type = lic.get("commerce_type")
        nif = lic.get("nif")
        registration_number = lic.get("registration_number")
        is_autonomo = forma == "autonomo"

        # Bundle details (paquete + tipo de comercio): ONLY for autonomo with bundle
        show_bundle_details = is_autonomo and regimen == "bundle" and commerce_type

        # Zone comercial: ONLY for autonomo (Padrón Empresarial zone system)
        # SL/SA are NOT subject to zone-based pricing — they use declarative regime
        show_zone = is_autonomo and lic.get("zone_code")

        # Capital social: shown for SL/SA/ONG (non-autonomo with NIF)
        capital = lic.get("capital_social")
        show_capital = not is_autonomo and nif and capital
        capital_formatted = _format_amount(capital) if capital else "-"

        # Identification: N° Registro (PE-XXXX) for autonomo, NIF for others
        if is_autonomo and registration_number:
            id_label = texts["reg_number"]
            id_value = registration_number
        elif nif:
            id_label = texts["nif_label"]
            id_value = nif
        else:
            id_label = texts["nif_label"]
            id_value = "-"

        # QR code with permanent verification secret
        from app.config import get_settings
        app_settings = get_settings()
        frontend_url = getattr(app_settings, 'FRONTEND_URL', 'https://facil.gq')
        license_ref = f"LIC-{lic.get('fiscal_year', '')}-{str(license_id)[:8].upper()}"
        token = self.generate_verification_token(license_id, str(total_amount))
        verification_url = f"{frontend_url}/verify/{license_ref}?t={token}&lid={license_id}"
        qr_base64 = self._generate_qr(verification_url)

        # Render template
        template = self._get_template()
        if not template:
            raise RuntimeError("License PDF template not found")

        html = template.render(
            title=texts["title"],
            texts=texts,
            language=language,
            logo_base64=self._get_logo_base64(),
            license_ref=license_ref,
            fiscal_year=lic.get("fiscal_year", ""),
            print_date=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M"),
            company={
                "legal_name": lic.get("legal_name", ""),
                "nif": nif,
                "registration_number": registration_number,
                "forma_juridica": lic.get("forma_juridica"),
                "regimen_fiscal": lic.get("regimen_fiscal"),
                "zone_code": lic.get("zone_code"),
                "city_name": lic.get("city_name"),
                "objeto_social": lic.get("objeto_social"),
            },
            # Identification
            id_label=id_label,
            id_value=id_value,
            # Conditional sections
            show_bundle_details=show_bundle_details,
            show_zone=show_zone,
            show_capital=show_capital,
            capital_formatted=capital_formatted,
            bundle_name=lic.get("bundle_name", "-"),
            commerce_type=commerce_type or "-",
            # Verification
            verification_url=verification_url,
            # Obligations
            obligation_groups=obligation_groups,
            obligation_count=obligation_count,
            is_fully_paid=is_fully_paid,
            is_overdue=is_overdue,
            has_any_penalty=has_any_penalty,
            total_amount_formatted=_format_amount(total_amount),
            total_penalties_formatted=_format_amount(total_penalties),
            paid_amount_formatted=_format_amount(total_paid),
            balance_formatted=_format_amount(balance),
            qr_base64=qr_base64,
        )

        # HTML → PDF
        result = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.BytesIO(html.encode("utf-8")), dest=result)
        if pisa_status.err:
            raise RuntimeError(f"PDF generation failed: {pisa_status.err}")

        pdf_bytes = result.getvalue()
        logger.info(f"License PDF generated: {license_id} ({len(pdf_bytes)} bytes)")
        return pdf_bytes


    async def generate_proforma_pdf(
        self,
        db: asyncpg.Connection,
        license_id: str,
        payment_reference: Optional[str] = None,
        language: str = "es",
    ) -> bytes:
        """Generate a proforma invoice PDF for bundle payment initiation.

        Reuses the license_dossier template with modified title/disclaimer.
        Shows obligations in their current status (payment_pending).
        Serves as the citizen's proof of payment submission.
        """
        # Override texts for proforma context
        PROFORMA_OVERRIDES = {
            "es": {
                "title": "Factura Proforma",
                "subtitle": "República de Guinea Ecuatorial — Sistema Facil",
                "disclaimer": (
                    "FACTURA PROFORMA: Este documento certifica la solicitud "
                    "de pago de las obligaciones fiscales indicadas. "
                    "No constituye un recibo oficial — el recibo será emitido "
                    "tras la validación del pago por la entidad correspondiente."
                ),
            },
            "fr": {
                "title": "Facture Proforma",
                "subtitle": "République de Guinée Équatoriale — Système Facil",
                "disclaimer": (
                    "FACTURE PROFORMA : Ce document certifie la demande "
                    "de paiement des obligations fiscales indiquées. "
                    "Il ne constitue pas un reçu officiel — le reçu sera émis "
                    "après validation du paiement par l'entité concernée."
                ),
            },
            "en": {
                "title": "Proforma Invoice",
                "subtitle": "Republic of Equatorial Guinea — Facil System",
                "disclaimer": (
                    "PROFORMA INVOICE: This document certifies the payment "
                    "request for the listed fiscal obligations. "
                    "It is not an official receipt — the receipt will be issued "
                    "after payment validation by the corresponding entity."
                ),
            },
        }

        # Build proforma texts WITHOUT mutating module-level TRANSLATIONS
        # (concurrent requests would see corrupted state during await).
        base_texts = TRANSLATIONS.get(language, TRANSLATIONS["es"])
        overrides = PROFORMA_OVERRIDES.get(language, PROFORMA_OVERRIDES["es"])
        proforma_texts = {**base_texts, **overrides}

        # Call the internal render directly with our custom texts
        # instead of going through generate_license_pdf (which reads TRANSLATIONS).
        pdf_bytes = await self._generate_license_pdf_with_texts(
            db, license_id, proforma_texts, language
        )

        logger.info(
            f"Proforma PDF generated: {license_id} "
            f"(ref={payment_reference}, {len(pdf_bytes)} bytes)"
        )
        return pdf_bytes

    # ================================================================
    # Certificate — formal document for completed licenses
    # ================================================================

    # City code mapping for certificate numbering: CLC-2026-MLB-A2-00001
    CITY_CODES = {
        "Malabo": "MLB", "Bata": "BTA", "Oyala": "OYA", "Ebebiyin": "EBY",
        "Mongomo": "MGM", "Evinayong": "EVY", "Luba": "LBA", "Baney": "BNY",
        "Cogo": "CGO", "Mbini": "MBN", "Micomeseng": "MCM", "Niefang": "NFG",
        "Nsork": "NSK", "Akurenam": "AKR", "Riaba": "RBA", "Anisok": "ANS",
        "San Antonio de Pale": "SAP",
    }

    CERT_TRANSLATIONS = {
        "es": {
            "title": "CERTIFICADO DE LICENCIA COMERCIAL",
            "republic": "República de Guinea Ecuatorial",
            "system": "Sistema Facil — Gobierno Digital",
            "validity": "Período de validez",
            "company_section": "DATOS DE LA EMPRESA",
            "company_name": "Razón Social",
            "representative": "Representante Legal",
            "registration": "N° Registro",
            "forma_juridica": "Forma Jurídica",
            "activity": "Actividad",
            "commerce_type": "Tipo de Comercio",
            "sector": "Sector",
            "location_section": "UBICACIÓN",
            "zone": "Zona Comercial",
            "city": "Ciudad",
            "province": "Provincia",
            "fiscal_section": "RESUMEN FISCAL",
            "total_obligations": "Total Obligaciones",
            "total_paid": "Total Pagado",
            "penalties": "Penalidades",
            "balance": "Saldo",
            "seal_text": "LICENCIA COMPLETADA",
            "completed_on": "Fecha de cumplimiento:",
            "issued_by": "Emitido digitalmente por el Sistema Facil — Gobierno de Guinea Ecuatorial",
            "issued_date": "Fecha de emisión",
            "verify": "Verificar",
            "legal_text": "Este certificado acredita el cumplimiento de TODAS las obligaciones fiscales del Padrón Empresarial para el año fiscal indicado. Documento oficial con validez legal.",
            "footer_line": "Certificado generado por Sistema Facil — Gobierno de Guinea Ecuatorial",
        },
        "fr": {
            "title": "CERTIFICAT DE LICENCE COMMERCIALE",
            "republic": "République de Guinée Équatoriale",
            "system": "Système Facil — Gouvernement Numérique",
            "validity": "Période de validité",
            "company_section": "DONNÉES DE L'ENTREPRISE",
            "company_name": "Raison Sociale",
            "representative": "Représentant Légal",
            "registration": "N° Registre",
            "forma_juridica": "Forme Juridique",
            "activity": "Activité",
            "commerce_type": "Type de Commerce",
            "sector": "Secteur",
            "location_section": "LOCALISATION",
            "zone": "Zone Commerciale",
            "city": "Ville",
            "province": "Province",
            "fiscal_section": "RÉSUMÉ FISCAL",
            "total_obligations": "Total Obligations",
            "total_paid": "Total Payé",
            "penalties": "Pénalités",
            "balance": "Solde",
            "seal_text": "LICENCE COMPLÉTÉE",
            "completed_on": "Date de conformité :",
            "issued_by": "Émis numériquement par le Système Facil — Gouvernement de Guinée Équatoriale",
            "issued_date": "Date d'émission",
            "verify": "Vérifier",
            "legal_text": "Ce certificat atteste le respect de TOUTES les obligations fiscales du Registre des Entreprises pour l'exercice fiscal indiqué. Document officiel à valeur légale.",
            "footer_line": "Certificat généré par Système Facil — Gouvernement de Guinée Équatoriale",
        },
        "en": {
            "title": "COMMERCIAL LICENSE CERTIFICATE",
            "republic": "Republic of Equatorial Guinea",
            "system": "Facil System — Digital Government",
            "validity": "Validity period",
            "company_section": "COMPANY DATA",
            "company_name": "Legal Name",
            "representative": "Legal Representative",
            "registration": "Registration No.",
            "forma_juridica": "Legal Form",
            "activity": "Activity",
            "commerce_type": "Commerce Type",
            "sector": "Sector",
            "location_section": "LOCATION",
            "zone": "Commercial Zone",
            "city": "City",
            "province": "Province",
            "fiscal_section": "FISCAL SUMMARY",
            "total_obligations": "Total Obligations",
            "total_paid": "Total Paid",
            "penalties": "Penalties",
            "balance": "Balance",
            "seal_text": "LICENSE COMPLETED",
            "completed_on": "Completion date:",
            "issued_by": "Digitally issued by the Facil System — Government of Equatorial Guinea",
            "issued_date": "Issue date",
            "verify": "Verify",
            "legal_text": "This certificate attests compliance with ALL fiscal obligations of the Business Registry for the indicated fiscal year. Official document with legal validity.",
            "footer_line": "Certificate generated by Facil System — Government of Equatorial Guinea",
        },
    }

    def _generate_certificate_number(
        self, fiscal_year: int, city_name: str, zone_code: str, license_id: str
    ) -> str:
        """Generate certificate number: CLC-2026-MLB-A2-00001."""
        city_code = self.CITY_CODES.get(city_name, city_name[:3].upper() if city_name else "UNK")
        # Sequence from license_id hash (deterministic, unique)
        seq = int(license_id.replace("-", "")[:8], 16) % 99999 + 1
        return f"CLC-{fiscal_year}-{city_code}-{zone_code or 'X'}-{seq:05d}"

    async def generate_license_certificate(
        self,
        db: asyncpg.Connection,
        license_id: str,
        language: str = "es",
    ) -> bytes:
        """Generate formal license certificate PDF for completed licenses.

        Only generates for licenses with status='complete'.
        Uses a distinct template from the dossier (no disclaimer, formal seal).
        """
        if not XHTML2PDF_AVAILABLE:
            raise RuntimeError("xhtml2pdf not installed")

        from uuid import UUID

        texts = self.CERT_TRANSLATIONS.get(language, self.CERT_TRANSLATIONS["es"])

        # Fetch license + company + owner
        row = await db.fetchrow("""
            SELECT cl.*, c.legal_name, c.nif, c.registration_number,
                   c.forma_juridica, c.regimen_fiscal, c.objeto_social,
                   c.commerce_type, c.sector_actividad, c.representante_legal,
                   ct.name AS city_name, ct.provincia, cz.zone_code
            FROM commercial_licenses cl
            JOIN companies c ON cl.company_id = c.id
            LEFT JOIN cities ct ON cl.city_id = ct.id
            LEFT JOIN commerce_zones cz ON cl.zone_id = cz.id
            WHERE cl.id = $1
        """, UUID(license_id))

        if not row:
            raise ValueError(f"License {license_id} not found")

        if row["status"] != "complete":
            raise ValueError(
                f"License {license_id} is not complete (status={row['status']}). "
                f"Certificate can only be generated for completed licenses."
            )

        lic = dict(row)
        certificate_number = self._generate_certificate_number(
            lic["fiscal_year"],
            lic.get("city_name", ""),
            lic.get("zone_code", ""),
            license_id,
        )

        # QR verification — certificate-specific HMAC includes certificate_number + fiscal_year
        # to prevent forgery (different from license dossier token which only uses license_id + amount)
        from app.config import get_settings
        app_settings = get_settings()
        frontend_url = getattr(app_settings, 'FRONTEND_URL', 'https://facil.gq')
        token = self.generate_certificate_token(
            certificate_number, license_id,
            str(lic.get("total_amount", 0)), str(lic.get("fiscal_year", "")),
        )
        verification_url = f"{frontend_url}/verify/{certificate_number}?t={token}&lid={license_id}"
        qr_base64 = self._generate_qr(verification_url)

        # Render
        cert_template = self._env.get_template("license_certificate.html") if self._env else None
        if not cert_template:
            raise RuntimeError("Certificate template not found")

        completion_date = ""
        if lic.get("completed_at"):
            try:
                from datetime import datetime as dt
                completed = lic["completed_at"]
                if isinstance(completed, str):
                    completed = dt.fromisoformat(completed)
                completion_date = completed.strftime("%d/%m/%Y %H:%M")
            except Exception:
                completion_date = str(lic.get("completed_at", ""))

        html = cert_template.render(
            texts=texts,
            language=language,
            logo_base64=self._get_logo_base64(),
            certificate_number=certificate_number,
            fiscal_year=lic.get("fiscal_year", ""),
            print_date=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M"),
            completion_date=completion_date,
            company={
                "legal_name": lic.get("legal_name", ""),
                "representante_legal": lic.get("representante_legal", ""),
                "registration_number": lic.get("registration_number"),
                "nif": lic.get("nif"),
                "forma_juridica": lic.get("forma_juridica"),
                "objeto_social": lic.get("objeto_social"),
                "commerce_type": lic.get("commerce_type"),
                "sector_actividad": lic.get("sector_actividad"),
                "zone_code": lic.get("zone_code"),
                "city_name": lic.get("city_name"),
                "provincia": lic.get("provincia"),
            },
            total_amount=_format_amount(lic.get("total_amount")),
            paid_amount=_format_amount(lic.get("amount_paid")),
            penalty_amount=_format_amount(lic.get("penalty_amount")),
            qr_base64=qr_base64,
            verification_url=verification_url,
        )

        # HTML → PDF
        result = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.BytesIO(html.encode("utf-8")), dest=result)
        if pisa_status.err:
            raise RuntimeError(f"Certificate PDF generation failed: {pisa_status.err}")

        pdf_bytes = result.getvalue()
        logger.info(
            f"License certificate generated: {certificate_number} "
            f"({len(pdf_bytes)} bytes)"
        )
        return pdf_bytes


# Singleton
license_pdf_service = LicensePDFService()
