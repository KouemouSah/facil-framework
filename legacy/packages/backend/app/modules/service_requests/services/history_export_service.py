"""
History Export Service - Export timeline data as CSV or PDF.

Provides:
- CSV export with all history entries
- PDF export with formatted timeline
"""

import csv
from io import BytesIO, StringIO
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from uuid import UUID
import asyncpg
from loguru import logger

# xhtml2pdf for PDF generation
try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False
    logger.warning("xhtml2pdf not installed. PDF generation disabled.")


class HistoryExportService:
    """Service for exporting history timeline data."""

    # CSV columns for history export
    HISTORY_COLUMNS = [
        ("performed_at", "Fecha/Hora"),
        ("action", "Acción"),
        ("previous_status", "Estado Anterior"),
        ("new_status", "Estado Nuevo"),
        ("performer_name", "Realizado Por"),
        ("performer_role", "Rol"),
        ("source", "Fuente"),
        ("comment", "Comentario"),
        ("document_code", "Código Documento"),
        ("document_name", "Nombre Documento"),
        ("extraction_confidence", "Confianza OCR"),
        ("agent_name", "Agente Asignado"),
        ("assignment_method", "Método Asignación"),
    ]

    # Action type labels
    ACTION_LABELS = {
        "status_change": "Cambio de Estado",
        "status_correction": "Corrección de Estado",
        "document_added": "Documento Agregado",
        "document_removed": "Documento Eliminado",
        "ocr_completed": "OCR Completado",
        "ocr_failed": "OCR Fallido",
        "assigned": "Asignado",
        "reassigned": "Reasignado",
        "cita_scheduled": "Cita Programada",
        "cita_rescheduled": "Cita Reprogramada",
        "cita_cancelled": "Cita Cancelada",
        "verification_updated": "Verificación Actualizada",
        "agent_action_taken": "Acción del Agente",
        "payment_initiated": "Pago Iniciado",
        "payment_received": "Pago Recibido",
        "payment_failed": "Pago Fallido",
        "comment_added": "Comentario Agregado",
    }

    def __init__(self):
        """Initialize the export service."""
        pass

    async def export_history_csv(
        self,
        entries: List[Dict[str, Any]],
        request_info: Dict[str, Any],
    ) -> bytes:
        """
        Generate CSV export of history entries.

        Args:
            entries: List of history entries
            request_info: Service request metadata

        Returns:
            CSV file content as bytes
        """
        output = StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        # Write header info
        writer.writerow(["# Historial de Solicitud"])
        writer.writerow(["Referencia", request_info.get("reference", "")])
        writer.writerow(["Tipo de Solicitud", request_info.get("workflow_code", "")])
        writer.writerow(["Ciudadano", request_info.get("citizen_name", "")])
        writer.writerow(["Estado Actual", request_info.get("current_status", "")])
        writer.writerow(["Exportado", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([])

        # Write column headers
        headers = [col[1] for col in self.HISTORY_COLUMNS]
        writer.writerow(headers)

        # Write entries
        for entry in entries:
            details = entry.get("details", {}) or {}
            row = [
                self._format_datetime(entry.get("performed_at")),
                self.ACTION_LABELS.get(entry.get("action"), entry.get("action", "")),
                entry.get("previous_status", ""),
                entry.get("new_status", ""),
                entry.get("performer_name", "Sistema" if not entry.get("performer_name") else entry.get("performer_name")),
                entry.get("performer_role", ""),
                entry.get("source", "history"),
                entry.get("comment", ""),
                details.get("document_code", ""),
                details.get("document_name", ""),
                f"{float(details.get('extraction_confidence', 0)) * 100:.0f}%" if details.get("extraction_confidence") else "",
                details.get("agent_name", ""),
                details.get("assignment_method", ""),
            ]
            writer.writerow(row)

        # Return as bytes with BOM for Excel compatibility
        content = output.getvalue()
        return b'\xef\xbb\xbf' + content.encode('utf-8')

    async def export_history_pdf(
        self,
        entries: List[Dict[str, Any]],
        request_info: Dict[str, Any],
    ) -> bytes:
        """
        Generate PDF export of history timeline.

        Args:
            entries: List of history entries
            request_info: Service request metadata

        Returns:
            PDF file content as bytes
        """
        if not XHTML2PDF_AVAILABLE:
            logger.error("xhtml2pdf not available for PDF generation")
            raise RuntimeError("PDF generation not available")

        html_content = self._generate_history_html(entries, request_info)

        output = BytesIO()
        pisa.CreatePDF(BytesIO(html_content.encode("utf-8")), dest=output)

        return output.getvalue()

    def _generate_history_html(
        self,
        entries: List[Dict[str, Any]],
        request_info: Dict[str, Any],
    ) -> str:
        """Generate HTML for PDF export."""
        reference = request_info.get("reference", "N/A")
        workflow = request_info.get("workflow_code", "N/A")
        citizen = request_info.get("citizen_name", "N/A")
        status = request_info.get("current_status", "N/A")
        total_entries = len(entries)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4;
                    margin: 1.5cm;
                }}
                body {{
                    font-family: Arial, sans-serif;
                    font-size: 10px;
                    line-height: 1.4;
                    color: #333;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 20px;
                    border-bottom: 2px solid #2563eb;
                    padding-bottom: 15px;
                }}
                .header h1 {{
                    color: #1e40af;
                    font-size: 16px;
                    margin: 0 0 5px 0;
                }}
                .header h2 {{
                    color: #3b82f6;
                    font-size: 12px;
                    margin: 0;
                    font-weight: normal;
                }}
                .meta-box {{
                    background: #f1f5f9;
                    padding: 10px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .meta-box table {{
                    width: 100%;
                }}
                .meta-box td {{
                    padding: 3px 5px;
                }}
                .meta-box .label {{
                    font-weight: bold;
                    width: 150px;
                    color: #475569;
                }}
                .meta-box .value {{
                    color: #1e293b;
                }}
                .timeline {{
                    margin: 20px 0;
                }}
                .timeline-entry {{
                    border-left: 3px solid #3b82f6;
                    padding-left: 15px;
                    margin-bottom: 15px;
                    position: relative;
                }}
                .timeline-entry::before {{
                    content: "";
                    position: absolute;
                    left: -6px;
                    top: 0;
                    width: 9px;
                    height: 9px;
                    border-radius: 50%;
                    background: #3b82f6;
                }}
                .timeline-entry.ocr {{
                    border-left-color: #14b8a6;
                }}
                .timeline-entry.ocr::before {{
                    background: #14b8a6;
                }}
                .timeline-entry.assignment {{
                    border-left-color: #8b5cf6;
                }}
                .timeline-entry.assignment::before {{
                    background: #8b5cf6;
                }}
                .timeline-entry.error {{
                    border-left-color: #ef4444;
                }}
                .timeline-entry.error::before {{
                    background: #ef4444;
                }}
                .entry-header {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 5px;
                }}
                .entry-action {{
                    font-weight: bold;
                    color: #1e40af;
                }}
                .entry-date {{
                    color: #64748b;
                    font-size: 9px;
                }}
                .entry-detail {{
                    color: #475569;
                    font-size: 9px;
                    margin-top: 3px;
                }}
                .entry-performer {{
                    color: #64748b;
                    font-size: 9px;
                    font-style: italic;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 8px;
                    font-weight: bold;
                }}
                .status-arrow {{
                    margin: 0 5px;
                    color: #94a3b8;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 10px;
                    border-top: 1px solid #e2e8f0;
                    color: #94a3b8;
                    font-size: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>HISTORIAL DE SOLICITUD</h1>
                <h2>Timeline de Acciones</h2>
            </div>

            <div class="meta-box">
                <table>
                    <tr>
                        <td class="label">Referencia:</td>
                        <td class="value">{reference}</td>
                        <td class="label">Estado Actual:</td>
                        <td class="value">{status}</td>
                    </tr>
                    <tr>
                        <td class="label">Tipo de Solicitud:</td>
                        <td class="value">{workflow}</td>
                        <td class="label">Total Acciones:</td>
                        <td class="value">{total_entries}</td>
                    </tr>
                    <tr>
                        <td class="label">Ciudadano:</td>
                        <td class="value" colspan="3">{citizen}</td>
                    </tr>
                </table>
            </div>

            <div class="timeline">
        """

        for entry in entries:
            action = entry.get("action", "")
            source = entry.get("source", "history")
            details = entry.get("details", {}) or {}

            # Determine CSS class based on source/action
            entry_class = ""
            if source == "ocr" or action in ["ocr_completed", "ocr_failed"]:
                entry_class = "ocr" if action != "ocr_failed" else "error"
            elif source == "assignment" or action in ["assigned", "reassigned"]:
                entry_class = "assignment"
            elif action in ["payment_failed", "ocr_failed"]:
                entry_class = "error"

            action_label = self.ACTION_LABELS.get(action, action)
            performed_at = self._format_datetime(entry.get("performed_at"))
            performer = entry.get("performer_name") or "Sistema"

            html += f"""
                <div class="timeline-entry {entry_class}">
                    <div class="entry-header">
                        <span class="entry-action">{action_label}</span>
                        <span class="entry-date">{performed_at}</span>
                    </div>
            """

            # Status change
            if action == "status_change":
                prev = entry.get("previous_status", "")
                new = entry.get("new_status", "")
                if prev or new:
                    html += f"""
                    <div class="entry-detail">
                        <span class="status-badge" style="background: #e2e8f0; color: #475569;">{prev}</span>
                        <span class="status-arrow">→</span>
                        <span class="status-badge" style="background: #dbeafe; color: #1e40af;">{new}</span>
                    </div>
                    """

            # OCR details
            if source == "ocr" or action in ["ocr_completed", "ocr_failed"]:
                doc_name = details.get("document_name") or details.get("document_code", "")
                confidence = details.get("extraction_confidence")
                if doc_name:
                    conf_str = f" (Confianza: {float(confidence) * 100:.0f}%)" if confidence else ""
                    html += f'<div class="entry-detail">Documento: {doc_name}{conf_str}</div>'

            # Assignment details
            if source == "assignment" or action in ["assigned", "reassigned"]:
                agent = details.get("agent_name", "")
                method = details.get("assignment_method", "")
                if agent:
                    html += f'<div class="entry-detail">Agente: {agent}'
                    if method:
                        html += f' ({method})'
                    html += '</div>'
                if action == "reassigned" and details.get("reassigned_to_name"):
                    html += f'<div class="entry-detail">Reasignado a: {details.get("reassigned_to_name")}</div>'

            # Comment
            if entry.get("comment"):
                html += f'<div class="entry-detail">{entry.get("comment")}</div>'

            html += f"""
                    <div class="entry-performer">Por: {performer}</div>
                </div>
            """

        html += f"""
            </div>

            <div class="footer">
                Generado por TaxasGE - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            </div>
        </body>
        </html>
        """

        return html

    def _format_datetime(self, dt) -> str:
        """Format datetime for display."""
        if dt is None:
            return ""
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except ValueError:
                return dt
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M")
        return str(dt)


# Singleton instance
history_export_service = HistoryExportService()
