"""Inspection Export Service — CSV and PDF export for field inspections.

Pattern: Same architecture as TreasuryExportService / HistoryExportService.
CSV uses io.StringIO + csv.writer with UTF-8 BOM for Excel compatibility.
PDF uses xhtml2pdf (pisa) with inline HTML.
"""

import base64
import csv
import hashlib
import hmac as hmac_mod
import io
import logging
from datetime import date, datetime
from decimal import Decimal
from html import escape as html_escape
from typing import Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# QR code for document verification (graceful degradation)
try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

# xhtml2pdf for PDF generation (graceful degradation)
try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    pisa = None
    XHTML2PDF_AVAILABLE = False
    logger.warning("xhtml2pdf not available — PDF export disabled")


class InspectionExportService:
    """Export inspections data as CSV or PDF."""

    # ============================================================
    # CSV — Inspections list
    # ============================================================

    @staticmethod
    async def export_inspections_csv(
        conn,
        entity_id: UUID,
        filters: Dict,
    ) -> bytes:
        """Export filtered inspections as CSV.

        Args:
            conn: asyncpg connection
            entity_id: Entity to scope the export
            filters: Dict with optional keys: date_from, date_to, agent_id,
                     zone_code, result, status, has_payment, has_med,
                     has_seal, search

        Returns:
            CSV file bytes with UTF-8 BOM for Excel compatibility
        """
        conditions = ["fi.entity_id = $1"]
        params: list = [entity_id]
        idx = 2

        # Exclude cancelled unless explicitly requested
        if not filters.get("status"):
            conditions.append("fi.status != 'cancelled'")

        # --- Date range ---
        if filters.get("date_from"):
            conditions.append(f"fi.inspection_date >= ${idx}")
            params.append(filters["date_from"])
            idx += 1

        if filters.get("date_to"):
            conditions.append(f"fi.inspection_date <= ${idx}")
            params.append(filters["date_to"])
            idx += 1

        # --- Agent ---
        if filters.get("agent_id"):
            conditions.append(f"fi.agent_id = ${idx}")
            params.append(filters["agent_id"])
            idx += 1

        # --- Zone ---
        if filters.get("zone_code"):
            conditions.append(f"cz.zone_code = ${idx}")
            params.append(filters["zone_code"])
            idx += 1

        # --- Result ---
        if filters.get("result"):
            conditions.append(f"fi.result = ${idx}")
            params.append(filters["result"])
            idx += 1

        # --- Status ---
        if filters.get("status"):
            conditions.append(f"fi.status = ${idx}")
            params.append(filters["status"])
            idx += 1

        # --- Boolean flags ---
        if filters.get("has_payment") is not None:
            conditions.append(f"fi.payment_collected = ${idx}")
            params.append(bool(filters["has_payment"]))
            idx += 1

        if filters.get("has_med") is not None:
            conditions.append(f"fi.mise_en_demeure_issued = ${idx}")
            params.append(bool(filters["has_med"]))
            idx += 1

        if filters.get("has_seal") is not None:
            conditions.append(f"fi.seal_applied = ${idx}")
            params.append(bool(filters["has_seal"]))
            idx += 1

        # --- Free-text search (company name or NIF) ---
        if filters.get("search"):
            conditions.append(
                f"(c.legal_name ILIKE ${idx} "
                f"OR COALESCE(c.nif, c.registration_number) ILIKE ${idx})"
            )
            params.append(f"%{filters['search']}%")
            idx += 1

        where = " AND ".join(conditions)

        rows = await conn.fetch(f"""
            SELECT
                fi.inspection_date,
                u.full_name AS agent_name,
                c.legal_name AS company_name,
                COALESCE(c.nif, c.registration_number) AS company_nif,
                cz.zone_code,
                fi.result,
                fi.status,
                COALESCE(fi.payment_amount, 0) AS payment_amount,
                fi.mise_en_demeure_issued,
                fi.seal_applied,
                fi.duration_minutes,
                fi.notes
            FROM field_inspections fi
            JOIN companies c ON c.id = fi.company_id
            JOIN users u ON u.id = fi.agent_id
            JOIN entities e ON e.id = fi.entity_id
            LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id
            WHERE {where}
            ORDER BY fi.inspection_date DESC, fi.created_at DESC
            LIMIT 10000
        """, *params)

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        # Header row
        writer.writerow([
            "Fecha", "Agente", "Empresa", "NIF", "Zona",
            "Resultado", "Estado", "Monto Cobrado",
            "MED", "Scellé", "Duración (min)", "Notas",
        ])

        for r in rows:
            writer.writerow([
                r["inspection_date"].isoformat() if r["inspection_date"] else "",
                r["agent_name"] or "",
                r["company_name"] or "",
                r["company_nif"] or "",
                r["zone_code"] or "",
                r["result"] or "",
                r["status"] or "",
                f"{float(r['payment_amount']):.0f}" if r["payment_amount"] else "0",
                "Sí" if r["mise_en_demeure_issued"] else "No",
                "Sí" if r["seal_applied"] else "No",
                str(r["duration_minutes"]) if r["duration_minutes"] else "",
                (r["notes"] or "").replace("\n", " "),
            ])

        content = output.getvalue()
        return b'\xef\xbb\xbf' + content.encode("utf-8")

    # ============================================================
    # CSV — Agent performance
    # ============================================================

    @staticmethod
    async def export_agents_csv(
        conn,
        entity_id: UUID,
        date_from: date,
        date_to: date,
    ) -> bytes:
        """Export agent performance aggregates as CSV.

        Args:
            conn: asyncpg connection
            entity_id: Entity scope
            date_from: Start of period (inclusive)
            date_to: End of period (inclusive)

        Returns:
            CSV file bytes with UTF-8 BOM
        """
        rows = await conn.fetch("""
            SELECT
                u.full_name AS agent_name,
                COUNT(*) AS total_inspections,
                COUNT(*) FILTER (WHERE fi.result = 'conforme') AS conforme,
                COUNT(*) FILTER (WHERE fi.result = 'non_conforme') AS non_conforme,
                CASE
                    WHEN COUNT(*) > 0
                    THEN ROUND(
                        COUNT(*) FILTER (WHERE fi.result = 'conforme') * 100.0
                        / COUNT(*), 1
                    )
                    ELSE 0
                END AS tasa_conformidad,
                COUNT(*) FILTER (WHERE fi.payment_collected = true) AS cobros,
                COALESCE(
                    SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected = true),
                    0
                ) AS monto_cobrado,
                COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued = true) AS med_count,
                COUNT(*) FILTER (WHERE fi.seal_applied = true) AS seal_count,
                COALESCE(
                    ROUND(AVG(fi.duration_minutes) FILTER (WHERE fi.duration_minutes IS NOT NULL)),
                    0
                ) AS duracion_prom,
                COUNT(DISTINCT cz.zone_code)
                    FILTER (WHERE cz.zone_code IS NOT NULL) AS zonas,
                COUNT(DISTINCT fi.inspection_date) AS dias_activos
            FROM field_inspections fi
            JOIN users u ON u.id = fi.agent_id
            LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id
            WHERE fi.entity_id = $1
              AND fi.inspection_date >= $2
              AND fi.inspection_date <= $3
              AND fi.status != 'cancelled'
            GROUP BY u.id, u.full_name
            ORDER BY total_inspections DESC
        """, entity_id, date_from, date_to)

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        writer.writerow([
            "Agente", "Inspecciones Total", "Conformes", "No Conformes",
            "Tasa Conformidad", "Cobros", "Monto Cobrado",
            "MED", "Scellés", "Duración Prom",
            "Zonas", "Días Activos",
        ])

        for r in rows:
            writer.writerow([
                r["agent_name"] or "",
                r["total_inspections"],
                r["conforme"],
                r["non_conforme"],
                f"{float(r['tasa_conformidad']):.1f}%",
                r["cobros"],
                f"{float(r['monto_cobrado']):.0f}",
                r["med_count"],
                r["seal_count"],
                r["duracion_prom"],
                r["zonas"],
                r["dias_activos"],
            ])

        content = output.getvalue()
        return b'\xef\xbb\xbf' + content.encode("utf-8")

    # ============================================================
    # PDF — Inspections report
    # ============================================================

    @staticmethod
    async def export_inspections_pdf(
        conn,
        entity_id: UUID,
        filters: Dict,
        entity_code: str,
        supervisor_name: str = "",
        supervisor_signature: Optional[str] = None,
    ) -> bytes:
        """Export inspections as a formatted PDF report.

        Args:
            conn: asyncpg connection
            entity_id: Entity scope
            filters: Same filter dict as export_inspections_csv
            entity_code: Entity code for the report header
            supervisor_name: Name of the supervisor generating the report
            supervisor_signature: Base64 data URL of supervisor's digital signature
                (from their most recent field_inspection.agent_signature)

        Returns:
            PDF file bytes

        Raises:
            RuntimeError: If xhtml2pdf is not installed
        """
        if not XHTML2PDF_AVAILABLE:
            logger.error("xhtml2pdf not available for PDF generation")
            raise RuntimeError("PDF generation not available — xhtml2pdf not installed")

        # -- Build dynamic WHERE clause (same logic as CSV) --
        conditions = ["fi.entity_id = $1"]
        params: list = [entity_id]
        idx = 2

        if filters.get("date_from"):
            conditions.append(f"fi.inspection_date >= ${idx}")
            params.append(filters["date_from"])
            idx += 1

        if filters.get("date_to"):
            conditions.append(f"fi.inspection_date <= ${idx}")
            params.append(filters["date_to"])
            idx += 1

        if filters.get("agent_id"):
            conditions.append(f"fi.agent_id = ${idx}")
            params.append(filters["agent_id"])
            idx += 1

        if filters.get("zone_code"):
            conditions.append(f"cz.zone_code = ${idx}")
            params.append(filters["zone_code"])
            idx += 1

        if filters.get("result"):
            conditions.append(f"fi.result = ${idx}")
            params.append(filters["result"])
            idx += 1

        if filters.get("status"):
            conditions.append(f"fi.status = ${idx}")
            params.append(filters["status"])
            idx += 1

        if filters.get("has_payment") is not None:
            conditions.append(f"fi.payment_collected = ${idx}")
            params.append(bool(filters["has_payment"]))
            idx += 1

        if filters.get("has_med") is not None:
            conditions.append(f"fi.mise_en_demeure_issued = ${idx}")
            params.append(bool(filters["has_med"]))
            idx += 1

        if filters.get("has_seal") is not None:
            conditions.append(f"fi.seal_applied = ${idx}")
            params.append(bool(filters["has_seal"]))
            idx += 1

        if filters.get("search"):
            conditions.append(
                f"(c.legal_name ILIKE ${idx} "
                f"OR COALESCE(c.nif, c.registration_number) ILIKE ${idx})"
            )
            params.append(f"%{filters['search']}%")
            idx += 1

        where = " AND ".join(conditions)

        # -- Fetch data --
        rows = await conn.fetch(f"""
            SELECT
                fi.inspection_date,
                u.full_name AS agent_name,
                c.legal_name AS company_name,
                COALESCE(c.nif, c.registration_number) AS company_nif,
                cz.zone_code,
                fi.result,
                fi.status,
                COALESCE(fi.payment_amount, 0) AS payment_amount,
                fi.mise_en_demeure_issued,
                fi.seal_applied,
                fi.duration_minutes,
                fi.notes
            FROM field_inspections fi
            JOIN companies c ON c.id = fi.company_id
            JOIN users u ON u.id = fi.agent_id
            JOIN entities e ON e.id = fi.entity_id
            LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id
            WHERE {where}
            ORDER BY fi.inspection_date DESC, fi.created_at DESC
            LIMIT 10000
        """, *params)

        # -- Compute summary stats --
        total = len(rows)
        conforme = sum(1 for r in rows if r["result"] == "conforme")
        non_conforme = sum(1 for r in rows if r["result"] == "non_conforme")
        total_collected = sum(
            float(r["payment_amount"]) for r in rows if r["payment_amount"]
        )

        date_range_label = ""
        if filters.get("date_from") or filters.get("date_to"):
            d_from = filters.get("date_from", "...")
            d_to = filters.get("date_to", "...")
            date_range_label = f"{d_from} — {d_to}"
        else:
            date_range_label = "Todas las fechas"

        # -- Generate QR verification code (same pattern as InspectionPdfService) --
        report_fingerprint = hashlib.sha256(
            f"export|{entity_id}|{date_range_label}|{total}".encode()
        ).hexdigest()[:12]
        qr_base64 = _generate_verification_qr(
            doc_type="export_report",
            doc_id=report_fingerprint,
        )

        # -- Extract supervisor signature base64 (same as InspectionPdfService) --
        sig_base64 = ""
        if supervisor_signature:
            if supervisor_signature.startswith("data:"):
                parts = supervisor_signature.split(",", 1)
                sig_base64 = parts[1] if len(parts) == 2 else ""
            else:
                sig_base64 = supervisor_signature

        # -- Build HTML --
        html = _build_inspections_pdf_html(
            entity_code=entity_code,
            date_range=date_range_label,
            total=total,
            conforme=conforme,
            non_conforme=non_conforme,
            total_collected=total_collected,
            rows=rows,
            qr_base64=qr_base64,
            supervisor_name=supervisor_name,
            supervisor_signature_base64=sig_base64,
        )

        # -- Convert to PDF --
        output = io.BytesIO()
        pisa.CreatePDF(
            io.BytesIO(html.encode("utf-8")),
            dest=output,
        )
        return output.getvalue()


# ================================================================
# QR code verification — same HMAC pattern as InspectionPdfService
# ================================================================

def _get_verification_secret() -> str:
    """Get HMAC secret — OWASP A02: No hardcoded fallback in production."""
    try:
        from app.core.secrets import get_secret
        secret = get_secret("VERIFICATION_SECRET")
        if secret:
            return secret
    except Exception:
        pass
    from app.config import get_settings
    settings = get_settings()
    env = getattr(settings, "ENVIRONMENT", "development")
    if env == "production":
        logger.error("VERIFICATION_SECRET not configured in production!")
        raise RuntimeError("VERIFICATION_SECRET must be set in production")
    return "dev-only-inspection-verify-not-for-production"


def _generate_verification_qr(doc_type: str, doc_id: str) -> str:
    """Generate QR code with HMAC-signed verification URL.

    Same algorithm as InspectionPdfService._generate_verification_token
    so both individual and batch reports are verifiable through the same
    /verify endpoint family.
    """
    if not QRCODE_AVAILABLE:
        return ""
    try:
        # HMAC token (same as inspection_pdf_service.py)
        secret = _get_verification_secret()
        msg = f"inspect-verify|{doc_type}|{doc_id}"
        token = hmac_mod.new(
            secret.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()[:16]

        # Build verification URL — NEVER hardcode base URL
        from app.config import get_settings
        settings = get_settings()
        base_url = settings.FRONTEND_URL

        qr_url = f"{base_url}/verify/{doc_type}/{doc_id}?t={token}"

        # Generate QR image → base64
        qr = qrcode.QRCode(
            version=1, error_correction=ERROR_CORRECT_H,
            box_size=5, border=2,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        logger.warning(f"QR generation failed for export report: {e}")
        return ""


# ================================================================
# Private helper — HTML template for PDF
# ================================================================

def _load_logo_base64() -> str:
    """Load Facil logo as base64 (same paths as InspectionPdfService)."""
    from pathlib import Path
    for path in [
        Path(__file__).parent.parent.parent / "service_requests" / "templates" / "logo.png",
        Path(__file__).parent.parent.parent.parent / "service_requests" / "templates" / "logo.png",
        Path(__file__).parent.parent.parent.parent.parent.parent / "packages" / "web" / "public" / "logo.png",
    ]:
        if path.exists():
            return base64.b64encode(path.read_bytes()).decode()
    return ""


def _build_inspections_pdf_html(
    entity_code: str,
    date_range: str,
    total: int,
    conforme: int,
    non_conforme: int,
    total_collected: float,
    rows: List,
    qr_base64: str = "",
    supervisor_name: str = "",
    supervisor_signature_base64: str = "",
) -> str:
    """Build the HTML string for the inspections PDF report."""

    # Table rows
    table_rows = ""
    for r in rows:
        insp_date = (
            r["inspection_date"].isoformat() if r["inspection_date"] else ""
        )
        med_label = "Sí" if r["mise_en_demeure_issued"] else "No"
        seal_label = "Sí" if r["seal_applied"] else "No"
        amount = f"{float(r['payment_amount']):,.0f}" if r["payment_amount"] else "0"
        duration = str(r["duration_minutes"]) if r["duration_minutes"] else "-"
        notes = (r["notes"] or "")[:80].replace("\n", " ")

        # Result colour — aligned with inspection_report.html design system
        result_val = r["result"] or ""
        if result_val == "conforme":
            result_style = "color: #155724; font-weight: bold;"  # same as .conforme
        elif result_val == "non_conforme":
            result_style = "color: #b33a3a; font-weight: bold;"  # same as .non_conforme
        else:
            result_style = "color: #856404;"  # same as .pending

        table_rows += f"""
            <tr>
                <td>{html_escape(insp_date)}</td>
                <td>{html_escape(r['agent_name'] or '')}</td>
                <td>{html_escape(r['company_name'] or '')}</td>
                <td>{html_escape(r['company_nif'] or '')}</td>
                <td>{html_escape(r['zone_code'] or '')}</td>
                <td style="{result_style}">{html_escape(result_val)}</td>
                <td>{html_escape(r['status'] or '')}</td>
                <td style="text-align:right;">{html_escape(amount)}</td>
                <td>{html_escape(med_label)}</td>
                <td>{html_escape(seal_label)}</td>
                <td style="text-align:right;">{html_escape(duration)}</td>
                <td>{html_escape(notes)}</td>
            </tr>
        """

    conformity_rate = f"{conforme * 100 / total:.1f}" if total > 0 else "0.0"
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    logo_b64 = _load_logo_base64()

    # Empty state message
    if total == 0:
        data_section = """
        <div class="section">
            <div class="section-title">DETALLE DE INSPECCIONES</div>
            <p style="text-align:center; color:#666; padding:20px 0;">
                No se encontraron inspecciones para el per&iacute;odo y filtros seleccionados.
            </p>
        </div>"""
    else:
        data_section = f"""
        <div class="section">
            <div class="section-title">DETALLE DE INSPECCIONES ({total} registros)</div>
            <table>
                <thead>
                    <tr>
                        <th>Fecha</th>
                        <th>Agente</th>
                        <th>Empresa</th>
                        <th>NIF</th>
                        <th>Zona</th>
                        <th>Resultado</th>
                        <th>Estado</th>
                        <th style="text-align:right">Monto</th>
                        <th>MED</th>
                        <th>Scell&eacute;</th>
                        <th style="text-align:right">Dur.</th>
                        <th>Notas</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>"""

    # Supervisor signature section
    sig_section = ""
    if supervisor_signature_base64:
        sig_section = f"""
        <div class="section">
            <div class="section-title">FIRMA DEL SUPERVISOR</div>
            <img src="data:image/png;base64,{supervisor_signature_base64}"
                 style="max-width:200px; max-height:80px; border-bottom:1px solid #999;">
            <div class="label">{html_escape(supervisor_name)} &mdash; {generated_at}</div>
        </div>"""

    # QR cell at LEFT (uses <table> layout — xhtml2pdf doesn't support display:inline-block)
    qr_cell = ""
    if qr_base64:
        qr_cell = f"""
            <td style="width:80px; text-align:left; vertical-align:top; border:none; padding-right:10px;">
                <img src="data:image/png;base64,{qr_base64}" width="70" height="70">
            </td>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4 landscape; margin: 1.5cm 1.2cm 2cm 1.2cm; }}
            body {{ font-family: Arial, sans-serif; font-size: 9pt; color: #222; line-height: 1.4; }}
            .header {{ text-align: center; border-bottom: 2px solid #2d5a03; padding-bottom: 8px; margin-bottom: 12px; }}
            .republic {{ font-size: 8pt; color: #666; margin-bottom: 4px; }}
            .header img {{ height: 50px; }}
            .header h1 {{ font-size: 14pt; color: #3a7a0a; margin: 4px 0; }}
            .header h2 {{ font-size: 10pt; color: #555; margin: 2px 0; font-weight: normal; }}
            .section {{ margin-bottom: 10px; }}
            .section-title {{ font-size: 10pt; font-weight: bold; color: #3a7a0a; border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-bottom: 6px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; }}
            th, td {{ padding: 4px 6px; text-align: left; font-size: 8pt; }}
            th {{ background: #f0f0f0; font-weight: bold; border-bottom: 1px solid #999; }}
            td {{ border-bottom: 1px solid #ddd; }}
            .label {{ color: #666; font-size: 8pt; }}
            .value {{ font-weight: bold; }}
            .amount-red {{ color: #dc3545; font-weight: bold; }}
            .amount-green {{ color: #28a745; font-weight: bold; }}
            .summary-table {{ width: auto; margin-bottom: 12px; }}
            .summary-table td {{ border: none; padding: 4px 14px 4px 0; }}
            .summary-label {{ color: #666; font-size: 7pt; text-transform: uppercase; }}
            .summary-value {{ font-size: 12pt; font-weight: bold; }}
            .stamp {{ border: 2px solid #3a7a0a; padding: 6px; margin-top: 10px; font-size: 8pt; }}
            .footer {{ position: fixed; bottom: 0; left: 0; right: 0; text-align: center; font-size: 7pt; color: #999; border-top: 1px solid #ddd; padding-top: 4px; }}
        </style>
    </head>
    <body>
        <!-- Header — same design as inspection_report.html -->
        <div class="header">
            <div class="republic">REP&Uacute;BLICA DE GUINEA ECUATORIAL</div>
            {"" if not logo_b64 else f'<img src="data:image/png;base64,{logo_b64}" alt="Facil">'}
            <h1>INFORME DE INSPECCIONES &mdash; {html_escape(entity_code)}</h1>
            <h2>Control Terrain &mdash; Obligaciones Fiscales &mdash; {html_escape(date_range)}</h2>
        </div>

        <!-- Summary KPIs -->
        <div class="section">
            <div class="section-title">RESUMEN</div>
            <table class="summary-table">
                <tr>
                    <td>
                        <span class="summary-label">Total Inspecciones</span><br/>
                        <span class="summary-value">{total}</span>
                    </td>
                    <td>
                        <span class="summary-label">Conformes</span><br/>
                        <span class="summary-value amount-green">{conforme}</span>
                    </td>
                    <td>
                        <span class="summary-label">No Conformes</span><br/>
                        <span class="summary-value amount-red">{non_conforme}</span>
                    </td>
                    <td>
                        <span class="summary-label">Tasa Conformidad</span><br/>
                        <span class="summary-value">{conformity_rate}%</span>
                    </td>
                    <td>
                        <span class="summary-label">Monto Recaudado</span><br/>
                        <span class="summary-value" style="color:#3a7a0a;">{total_collected:,.0f} XAF</span>
                    </td>
                </tr>
            </table>
        </div>

        <!-- Data table or empty state -->
        {data_section}

        <!-- Supervisor Signature -->
        {sig_section}

        <!-- QR (left) + Stamp (right) — uses <table> layout for xhtml2pdf compat -->
        <div class="stamp">
            <table style="width:100%; margin:0;">
                <tr>
                    {qr_cell}
                    <td style="text-align:left; vertical-align:top; border:none;">
                        <strong>SELLO DIGITAL</strong><br>
                        Este documento ha sido generado electr&oacute;nicamente por la plataforma Facil.<br>
                        <span class="label">{html_escape(entity_code)} &mdash; {generated_at}</span>
                    </td>
                </tr>
            </table>
        </div>

        <div class="footer">
            Facil &mdash; Plataforma Digital de Guinea Ecuatorial &mdash; Generado el {generated_at} &mdash; P&aacute;gina <pdf:pagenumber> de <pdf:pagecount>
        </div>
    </body>
    </html>
    """
