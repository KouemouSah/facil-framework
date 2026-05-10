"""
Treasury Export Service - Complete Export Generation

Generates actual export files for Treasury module:
- CSV for SAGE X3 integration
- XLSX for Excel reports
- PDF for ministry reports
- XML for BEAC (Central Bank)

Uses pandas for data manipulation, xhtml2pdf for PDF generation.
Files are uploaded to Firebase Storage for persistence.
"""

import csv
import json
import hashlib
import tempfile
from io import BytesIO, StringIO
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List
import asyncpg
from loguru import logger
from jinja2 import Environment, FileSystemLoader

# Pandas for data export
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not installed. Export generation limited.")

# xhtml2pdf for PDF generation
try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False
    logger.warning("xhtml2pdf not installed. PDF generation disabled.")

# openpyxl for Excel generation (required by pandas)
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    logger.warning("openpyxl not installed. Excel generation will fallback to CSV.")

# lxml for XML generation
try:
    from lxml import etree
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False
    logger.warning("lxml not installed. XML generation disabled.")

# ReportLab for chart generation (PNG → base64 → embed in PDF)
try:
    import io
    import base64
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics import renderPM
    from reportlab.lib import colors as rl_colors
    REPORTLAB_CHARTS_AVAILABLE = True
except ImportError:
    REPORTLAB_CHARTS_AVAILABLE = False
    logger.warning("reportlab chart modules not available. Charts disabled in PDF reports.")

# Firebase Storage for cloud persistence
try:
    from app.modules.documents.services.storage_service import firebase_storage_service
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("Firebase Storage not available. Using local storage only.")


class TreasuryExportService:
    """Service for generating treasury export files."""

    # Export storage directory (cross-platform via tempfile)
    # Plan P2 hotfix: previously hardcoded "/tmp/treasury_exports" which broke
    # on Windows. Now uses platform's temp dir (Linux /tmp, Windows %TEMP%).
    EXPORT_DIR = Path(tempfile.gettempdir()) / "treasury_exports"

    # Chart color palette (professional navy/blue scale)
    CHART_COLORS = [
        "#3d7a35", "#1a365d", "#c53030", "#d69e2e",
        "#2b6cb0", "#9b2c2c", "#38a169", "#805ad5",
        "#dd6b20", "#319795", "#e53e3e", "#4299e1",
    ]

    # SAGE X3 CSV column mapping
    SAGE_X3_COLUMNS = [
        ("completed_at", "DATE", lambda x: x.strftime("%Y%m%d") if x else ""),
        ("payment_reference", "PIECE", lambda x: str(x).upper()[:20] if x else ""),
        ("journal_code", "JOURNAL", lambda x: "TRS"),
        ("account_debit", "COMPTE_D", lambda x: "411000"),  # Client account
        ("account_credit", "COMPTE_C", lambda x: "512000"),  # Bank account
        ("total_amount", "MONTANT", lambda x: f"{float(x):.2f}" if x else "0.00"),
        ("currency", "DEVISE", lambda x: x or "XAF"),
        ("service_name_es", "LIBELLE", lambda x: str(x)[:50] if x else ""),
        ("user_name", "TIERS", lambda x: str(x)[:35] if x else ""),
        ("workflow_code", "PIECE2", lambda x: str(x)[:20] if x else ""),
    ]

    # Reconciliation columns
    RECONCILIATION_COLUMNS = [
        "bank_reference",
        "payment_reference",
        "amount",
        "currency",
        "bank_transaction_date",
        "reconciled_at",
        "bank_code",
        "status",
        "user_name",
    ]

    def __init__(self):
        """Initialize the export service."""
        # Ensure export directory exists
        self.EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        # Template environment for PDF
        template_dir = Path(__file__).parent.parent / "templates"
        if template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=True
            )
        else:
            self.jinja_env = None
            logger.warning(f"Template directory not found: {template_dir}")

    async def _upload_to_firebase(
        self,
        content: bytes,
        filename: str,
        export_id: str,
        mime_type: str,
        admin_user_id: str,
    ) -> Optional[str]:
        """
        Upload export content to Firebase Storage.

        Args:
            content: File bytes
            filename: Original filename (e.g. "RPT_MIN_...pdf")
            export_id: Export ID for naming
            mime_type: File MIME type
            admin_user_id: User who requested the export

        Returns:
            Firebase Storage path (e.g., "treasury-exports/2026/01/...") or None on failure
        """
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available, export will regenerate on download")
            return None

        try:
            # Initialize Firebase if needed
            if not firebase_storage_service._initialized:
                await firebase_storage_service.initialize()

            # Generate storage path with date organization
            now = datetime.now()
            storage_path = f"treasury-exports/{now.year}/{now.month:02d}/{filename}"

            # Create blob and upload
            blob = firebase_storage_service.bucket.blob(storage_path)

            # Set metadata
            blob.metadata = {
                "uploadedBy": admin_user_id or "system",
                "uploadedAt": now.isoformat(),
                "exportId": export_id,
                "assetType": "treasury-export",
                "file_size": str(len(content)),
            }

            # Upload
            blob.upload_from_string(content, content_type=mime_type, timeout=300)

            logger.info(f"Export uploaded to Firebase: {storage_path}")
            return storage_path

        except Exception as e:
            logger.error(f"Firebase upload failed, export will regenerate on download: {e}")
            return None

    async def get_download_url(
        self,
        file_path: str,
        expiration_hours: int = 24,
    ) -> str:
        """
        Get signed download URL for an export file.

        Args:
            file_path: Firebase Storage path or local path
            expiration_hours: URL validity in hours

        Returns:
            Signed URL for download
        """
        if not FIREBASE_AVAILABLE or not file_path.startswith("treasury-exports/"):
            # Local file - return as-is (would need different handling)
            return file_path

        try:
            if not firebase_storage_service._initialized:
                await firebase_storage_service.initialize()

            blob = firebase_storage_service.bucket.blob(file_path)

            if not blob.exists():
                raise FileNotFoundError(f"Export file not found: {file_path}")

            # Generate signed URL
            signed_url = firebase_storage_service.generate_signed_url(
                blob,
                expiration=timedelta(hours=expiration_hours),
                method="GET"
            )

            return signed_url

        except Exception as e:
            logger.error(f"Failed to generate download URL: {e}")
            raise

    @staticmethod
    def _is_data_empty(data) -> bool:
        """Check if fetched export data is effectively empty (no records)."""
        if isinstance(data, list):
            return len(data) == 0
        if isinstance(data, dict):
            # Ministry/audit reports use total_count; others use details list
            total_count = data.get("total_count", None)
            if total_count is not None:
                return int(total_count) == 0
            details = data.get("details", data.get("rows", data.get("records", [])))
            return len(details) == 0
        return not data

    async def generate_export(
        self,
        db: asyncpg.Connection,
        export_id: str,
        export_type: str,
        export_format: str,
        period_start: date,
        period_end: date,
        filters: Optional[Dict[str, Any]] = None,
        requested_by: str = None,
    ) -> Dict[str, Any]:
        """
        Generate an export file.

        Args:
            db: Database connection
            export_id: Export record ID
            export_type: Type of export (sage_x3, ministry_report, etc.)
            export_format: File format (csv, xlsx, pdf)
            period_start: Start date of period
            period_end: End date of period
            filters: Optional filters
            requested_by: User ID who requested

        Returns:
            Dict with file_path, file_size, total_records, total_amount
        """
        try:
            # Update status to processing
            await db.execute("""
                UPDATE treasury_exports
                SET status = 'processing'::export_status_enum,
                    started_at = NOW(),
                    progress_percentage = 10
                WHERE id = $1::uuid
            """, export_id)

            # Resolve agent name for PDF footer
            generated_by_name = None
            if requested_by:
                generated_by_name = await db.fetchval(
                    "SELECT full_name FROM users WHERE id = $1", requested_by
                )

            # Fetch payment data based on export type
            if export_type == "sage_x3":
                data = await self._fetch_sage_x3_data(db, period_start, period_end, filters)
                result = await self._generate_sage_x3_export(data, export_format, export_id)
            elif export_type == "ministry_report":
                data = await self._fetch_ministry_data(db, period_start, period_end, filters)
                # Guard: warn if no data for the period
                if self._is_data_empty(data):
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=422,
                        detail=f"No hay datos de pagos para el periodo {period_start} - {period_end}. "
                               "Verifique los filtros o seleccione otro rango de fechas."
                    )
                result = await self._generate_ministry_report(
                    data, export_format, export_id, period_start, period_end,
                    generated_by_name=generated_by_name,
                )
            elif export_type == "reconciliation":
                data = await self._fetch_reconciliation_data(db, period_start, period_end, filters)
                if self._is_data_empty(data):
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=422,
                        detail=f"No hay datos de conciliación para el periodo {period_start} - {period_end}."
                    )
                result = await self._generate_reconciliation_export(data, export_format, export_id)
            elif export_type == "audit_report":
                data = await self._fetch_audit_data(db, period_start, period_end, filters)
                if self._is_data_empty(data):
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=422,
                        detail=f"No hay datos de auditoría para el periodo {period_start} - {period_end}."
                    )
                result = await self._generate_audit_report(data, export_format, export_id, period_start, period_end)
            elif export_type == "bank_central":
                data = await self._fetch_beac_data(db, period_start, period_end, filters)
                if self._is_data_empty(data):
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=422,
                        detail=f"No hay datos bancarios para el periodo {period_start} - {period_end}."
                    )
                result = await self._generate_beac_export(data, export_format, export_id, period_start, period_end)
            else:
                # Generic export (custom or unknown type)
                data = await self._fetch_generic_data(db, period_start, period_end, filters)
                if self._is_data_empty(data):
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=422,
                        detail=f"No hay datos para el periodo {period_start} - {period_end}."
                    )
                result = await self._generate_generic_export(
                    data, export_format, export_id, period_start, period_end,
                    generated_by_name=generated_by_name,
                )

            # Update progress
            await db.execute("""
                UPDATE treasury_exports
                SET progress_percentage = 90
                WHERE id = $1::uuid
            """, export_id)

            # result["file_content"] is bytes from in-memory generation
            file_content: bytes = result["file_content"]
            file_name = result.get("file_name", f"{export_id}.{export_format}")

            # Calculate checksum from in-memory content
            checksum = hashlib.sha256(file_content).hexdigest()

            # Try Firebase upload (optional cache for repeat downloads)
            firebase_path = await self._upload_to_firebase(
                content=file_content,
                filename=file_name,
                export_id=export_id,
                mime_type=result.get("mime_type", "application/octet-stream"),
                admin_user_id=requested_by,
            )

            # Update export record with results (file_path = Firebase path or NULL)
            await db.execute("""
                UPDATE treasury_exports
                SET status = 'completed'::export_status_enum,
                    completed_at = NOW(),
                    progress_percentage = 100,
                    file_path = $2,
                    file_size_bytes = $3,
                    file_checksum = $4,
                    total_records = $5,
                    total_amount = $6,
                    file_mime_type = $7
                WHERE id = $1::uuid
            """, export_id, firebase_path, result["file_size"],
                checksum, result["total_records"],
                result["total_amount"], result.get("mime_type"))

            logger.info(f"Export {export_id} completed: {result['total_records']} records")
            return result

        except Exception as e:
            logger.error(f"Export {export_id} failed: {str(e)}")
            # Update with error
            await db.execute("""
                UPDATE treasury_exports
                SET status = 'failed'::export_status_enum,
                    error_message = $2,
                    error_details = $3::jsonb
                WHERE id = $1::uuid
            """, export_id, str(e), json.dumps({"exception": type(e).__name__}))
            raise

    async def _fetch_sage_x3_data(
        self,
        db: asyncpg.Connection,
        period_start: date,
        period_end: date,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch payment data formatted for SAGE X3."""
        conditions = ["sp.workflow_status = 'completed'"]
        params = [period_start, period_end]
        param_idx = 3

        conditions.append("sp.paid_at >= $1::date")
        conditions.append("sp.paid_at < $2::date + INTERVAL '1 day'")

        if filters:
            if filters.get("entity_code"):
                conditions.append(f"sp.entity_code = ${param_idx}")
                params.append(filters["entity_code"])
                param_idx += 1
            if filters.get("payment_method"):
                conditions.append(f"sp.payment_method = ${param_idx}")
                params.append(filters["payment_method"])
                param_idx += 1

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                sp.payment_reference,
                sp.total_amount,
                sp.currency,
                sp.payment_method,
                sp.paid_at AS completed_at,
                sr.workflow_code,
                sr.reference as service_request_reference,
                INITCAP(REPLACE(sr.workflow_code, '_', ' ')) as service_name_es,
                u.full_name as user_name,
                e.name as entity_name,
                m.name_es as ministry_name
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            LEFT JOIN users u ON u.id = sr.user_id
            LEFT JOIN entities e ON e.code = sp.entity_code
            LEFT JOIN ministries m ON m.id = e.ministry_id
            WHERE {where_clause}
            ORDER BY sp.paid_at ASC
        """

        rows = await db.fetch(query, *params)
        return [dict(row) for row in rows]

    async def _fetch_ministry_data(
        self,
        db: asyncpg.Connection,
        period_start: date,
        period_end: date,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch aggregated data for ministry report using CTE (single scan)."""
        params: list = [period_start, period_end]

        entity_filter = ""
        if filters and filters.get("entity_code"):
            entity_filter = "AND sp.entity_code = $3"
            params.append(filters["entity_code"])

        # Single CTE scans service_payments+service_requests once,
        # then 5 aggregation queries read from the materialized CTE.
        query = f"""
            WITH base AS (
                SELECT
                    sp.payment_reference,
                    sp.total_amount,
                    sp.currency,
                    sp.payment_method,
                    sp.paid_at,
                    sp.entity_code,
                    sr.reference AS request_reference,
                    sr.workflow_code,
                    sr.user_id
                FROM service_payments sp
                JOIN service_requests sr ON sr.id = sp.service_request_id
                WHERE sp.workflow_status = 'completed'
                  AND sp.paid_at >= $1::date
                  AND sp.paid_at < $2::date + INTERVAL '1 day'
                  {entity_filter}
            ),
            agg_entity AS (
                SELECT
                    b.entity_code,
                    e.name AS entity_name,
                    e.ministry_id,
                    m.name_es AS ministry_name,
                    COUNT(*) AS payment_count,
                    SUM(b.total_amount) AS total_amount,
                    AVG(b.total_amount) AS avg_amount
                FROM base b
                LEFT JOIN entities e ON e.code = b.entity_code
                LEFT JOIN ministries m ON m.id = e.ministry_id
                GROUP BY b.entity_code, e.name, e.ministry_id, m.name_es
                ORDER BY total_amount DESC
            ),
            agg_method AS (
                SELECT
                    payment_method,
                    COUNT(*) AS payment_count,
                    SUM(total_amount) AS total_amount
                FROM base
                GROUP BY payment_method
                ORDER BY total_amount DESC
            ),
            agg_service AS (
                SELECT
                    INITCAP(REPLACE(workflow_code, '_', ' ')) AS service_name,
                    COUNT(*) AS payment_count,
                    SUM(total_amount) AS total_amount
                FROM base
                GROUP BY workflow_code
                ORDER BY total_amount DESC
                LIMIT 20
            ),
            agg_daily AS (
                SELECT
                    DATE(paid_at) AS date,
                    COUNT(*) AS count,
                    SUM(total_amount) AS amount
                FROM base
                GROUP BY DATE(paid_at)
                ORDER BY date ASC
            ),
            detail AS (
                SELECT
                    b.payment_reference,
                    b.total_amount,
                    b.currency,
                    b.payment_method,
                    b.paid_at AS completed_at,
                    b.request_reference,
                    INITCAP(REPLACE(b.workflow_code, '_', ' ')) AS service_name,
                    u.full_name AS user_name
                FROM base b
                LEFT JOIN users u ON u.id = b.user_id
                ORDER BY b.paid_at DESC
                LIMIT 100
            )
            SELECT
                'entity' AS _section, to_jsonb(array_agg(row_to_json(agg_entity))) AS data
            FROM agg_entity
            UNION ALL
            SELECT
                'method', to_jsonb(array_agg(row_to_json(agg_method)))
            FROM agg_method
            UNION ALL
            SELECT
                'service', to_jsonb(array_agg(row_to_json(agg_service)))
            FROM agg_service
            UNION ALL
            SELECT
                'daily', to_jsonb(array_agg(row_to_json(agg_daily)))
            FROM agg_daily
            UNION ALL
            SELECT
                'detail', to_jsonb(array_agg(row_to_json(detail)))
            FROM detail;
        """

        rows = await db.fetch(query, *params)

        # Parse CTE results by section
        sections: Dict[str, list] = {}
        for row in rows:
            section_name = row["_section"]
            data = row["data"]
            if data is None:
                sections[section_name] = []
            elif isinstance(data, str):
                sections[section_name] = json.loads(data)
            else:
                sections[section_name] = list(data)

        by_entity = sections.get("entity", [])
        by_method = sections.get("method", [])

        # Calculate totals from entity aggregation
        total_amount = sum(float(e.get("total_amount", 0) or 0) for e in by_entity)
        total_count = sum(int(e.get("payment_count", 0) or 0) for e in by_entity)

        return {
            "by_entity": by_entity,
            "by_method": by_method,
            "by_service": sections.get("service", []),
            "details": sections.get("detail", []),
            "daily_breakdown": sections.get("daily", []),
            "total_amount": total_amount,
            "total_count": total_count,
        }

    async def _fetch_reconciliation_data(
        self,
        db: asyncpg.Connection,
        period_start: date,
        period_end: date,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch reconciliation data."""
        query = """
            SELECT
                bt.bank_reference,
                sp.payment_reference,
                bt.amount,
                bt.currency,
                bt.bank_transaction_date,
                bt.reconciled_at,
                bt.bank_code,
                bt.status::text,
                u.full_name as user_name
            FROM bank_transactions bt
            LEFT JOIN service_payments sp ON sp.id = bt.service_payment_id
            LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
            LEFT JOIN users u ON u.id = sr.user_id
            WHERE bt.created_at >= $1::date
              AND bt.created_at < $2::date + INTERVAL '1 day'
            ORDER BY bt.created_at DESC
        """
        rows = await db.fetch(query, period_start, period_end)
        return [dict(row) for row in rows]

    async def _fetch_audit_data(
        self,
        db: asyncpg.Connection,
        period_start: date,
        period_end: date,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch audit log data."""
        # Use agent_user_id (UUID → users.id) — agent_id (integer) is legacy/always NULL
        query = """
            SELECT
                pva.payment_id::text,
                sp.payment_reference,
                pva.action::text,
                pva.from_status::text,
                pva.to_status::text,
                pva.comment,
                pva.created_at,
                pva.agent_user_id::text as agent_id,
                u.full_name as agent_name
            FROM payment_validation_audit pva
            JOIN service_payments sp ON sp.id = pva.payment_id
            LEFT JOIN users u ON u.id = pva.agent_user_id
            WHERE pva.created_at >= $1::date
              AND pva.created_at < $2::date + INTERVAL '1 day'
            ORDER BY pva.created_at DESC
        """
        rows = await db.fetch(query, period_start, period_end)
        return [dict(row) for row in rows]

    async def _fetch_generic_data(
        self,
        db: asyncpg.Connection,
        period_start: date,
        period_end: date,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch generic payment data."""
        query = """
            SELECT
                sp.payment_reference,
                sp.total_amount,
                sp.currency,
                sp.payment_method,
                sp.workflow_status::text,
                sp.created_at,
                sp.paid_at AS completed_at,
                sr.reference as request_reference,
                sr.workflow_code,
                INITCAP(REPLACE(sr.workflow_code, '_', ' ')) as service_name,
                agent.full_name as agent_name,
                e.name as entity_name,
                m.name_es as ministry_name
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            LEFT JOIN users agent ON agent.id = sp.validated_by_agent_id
            LEFT JOIN entities e ON e.code = sp.entity_code
            LEFT JOIN ministries m ON m.id = e.ministry_id
            WHERE sp.created_at >= $1::date
              AND sp.created_at < $2::date + INTERVAL '1 day'
            ORDER BY sp.created_at DESC
        """
        rows = await db.fetch(query, period_start, period_end)
        return [dict(row) for row in rows]

    async def _fetch_beac_data(
        self,
        db: asyncpg.Connection,
        period_start: date,
        period_end: date,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch data for BEAC (Banque des États de l'Afrique Centrale) report."""
        # Summary aggregations for central bank reporting
        summary_query = """
            SELECT
                DATE(sp.paid_at) as transaction_date,
                sp.payment_method,
                COUNT(*) as transaction_count,
                SUM(sp.total_amount) as total_amount,
                sp.currency
            FROM service_payments sp
            WHERE sp.workflow_status = 'completed'
              AND sp.paid_at >= $1::date
              AND sp.paid_at < $2::date + INTERVAL '1 day'
            GROUP BY DATE(sp.paid_at), sp.payment_method, sp.currency
            ORDER BY transaction_date, sp.payment_method
        """

        # Detailed transactions for compliance
        detail_query = """
            SELECT
                sp.payment_reference as reference_paiement,
                sp.total_amount as montant,
                sp.currency as devise,
                sp.payment_method as methode_paiement,
                sp.paid_at as date_execution,
                u.full_name as nom_payeur,
                u.phone_number as telephone_payeur,
                sr.reference as reference_dossier,
                sr.workflow_code as code_service,
                INITCAP(REPLACE(sr.workflow_code, '_', ' ')) as libelle_service,
                sp.entity_code as code_entite,
                e.name as nom_entite,
                m.ministry_code as code_ministere
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            LEFT JOIN users u ON u.id = sr.user_id
            LEFT JOIN entities e ON e.code = sp.entity_code
            LEFT JOIN ministries m ON m.id = e.ministry_id
            WHERE sp.workflow_status = 'completed'
              AND sp.paid_at >= $1::date
              AND sp.paid_at < $2::date + INTERVAL '1 day'
            ORDER BY sp.paid_at ASC
        """

        summary = await db.fetch(summary_query, period_start, period_end)
        details = await db.fetch(detail_query, period_start, period_end)

        total_amount = sum(float(row["total_amount"] or 0) for row in summary)
        total_count = sum(row["transaction_count"] for row in summary)

        return {
            "summary": [dict(row) for row in summary],
            "details": [dict(row) for row in details],
            "total_amount": total_amount,
            "total_count": total_count,
            "period_start": period_start,
            "period_end": period_end,
        }

    async def _generate_beac_export(
        self,
        data: Dict[str, Any],
        export_format: str,
        export_id: str,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Generate BEAC central bank report."""
        if export_format == "xml":
            return await self._write_beac_xml(data, export_id, period_start, period_end)
        elif export_format == "xlsx":
            return await self._write_beac_xlsx(data, export_id, period_start, period_end)
        else:
            # Default to XML for bank_central
            return await self._write_beac_xml(data, export_id, period_start, period_end)

    async def _write_beac_xml(
        self,
        data: Dict[str, Any],
        export_id: str,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Write BEAC XML format file."""
        if not LXML_AVAILABLE:
            # Fallback to JSON
            return await self._write_json(data.get("details", []), export_id, data.get("total_amount", 0))

        # Build XML structure in-memory following BEAC format standards
        root = etree.Element("RapportBEAC")
        root.set("version", "1.0")
        root.set("xmlns", "urn:beac:cemac:treasury:report")

        # Header
        header = etree.SubElement(root, "Entete")
        etree.SubElement(header, "CodePays").text = "GQ"
        etree.SubElement(header, "NomPays").text = "Guinea Ecuatorial"
        etree.SubElement(header, "CodeInstitution").text = "MINHAP"
        etree.SubElement(header, "NomInstitution").text = "Ministerio de Hacienda y Presupuestos"
        etree.SubElement(header, "DateDebut").text = period_start.strftime("%Y-%m-%d")
        etree.SubElement(header, "DateFin").text = period_end.strftime("%Y-%m-%d")
        etree.SubElement(header, "DateGeneration").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # Summary
        resume = etree.SubElement(root, "Resume")
        etree.SubElement(resume, "NombreTransactions").text = str(data.get("total_count", 0))
        etree.SubElement(resume, "MontantTotal").text = f"{data.get('total_amount', 0):.2f}"
        etree.SubElement(resume, "Devise").text = "XAF"

        # Daily summary
        synthese_jour = etree.SubElement(root, "SyntheseJournaliere")
        for row in data.get("summary", []):
            jour = etree.SubElement(synthese_jour, "Jour")
            etree.SubElement(jour, "Date").text = row["transaction_date"].strftime("%Y-%m-%d") if row.get("transaction_date") else ""
            etree.SubElement(jour, "MethodePaiement").text = str(row.get("payment_method", ""))
            etree.SubElement(jour, "NombreOperations").text = str(row.get("transaction_count", 0))
            etree.SubElement(jour, "Montant").text = f"{float(row.get('total_amount', 0)):.2f}"
            etree.SubElement(jour, "Devise").text = str(row.get("currency", "XAF"))

        # Transactions detail
        transactions = etree.SubElement(root, "Transactions")
        for row in data.get("details", []):
            tx = etree.SubElement(transactions, "Transaction")
            etree.SubElement(tx, "Reference").text = str(row.get("reference_paiement", ""))
            etree.SubElement(tx, "Montant").text = f"{float(row.get('montant', 0)):.2f}"
            etree.SubElement(tx, "Devise").text = str(row.get("devise", "XAF"))
            etree.SubElement(tx, "MethodePaiement").text = str(row.get("methode_paiement", ""))
            etree.SubElement(tx, "DateExecution").text = row["date_execution"].strftime("%Y-%m-%dT%H:%M:%S") if row.get("date_execution") else ""
            etree.SubElement(tx, "NomPayeur").text = str(row.get("nom_payeur", "") or "")
            etree.SubElement(tx, "ReferenceDossier").text = str(row.get("reference_dossier", ""))
            etree.SubElement(tx, "CodeService").text = str(row.get("code_service", ""))
            etree.SubElement(tx, "LibelleService").text = str(row.get("libelle_service", "") or "")[:100]
            etree.SubElement(tx, "CodeMinistere").text = str(row.get("code_ministere", "") or "")

        # Serialize to bytes in-memory
        file_content = etree.tostring(
            root, encoding="utf-8", xml_declaration=True, pretty_print=True
        )

        return {
            "file_content": file_content,
            "file_name": f"{export_id}.xml",
            "file_size": len(file_content),
            "total_records": data.get("total_count", 0),
            "total_amount": float(data.get("total_amount", 0)),
            "mime_type": "application/xml",
        }

    # ── Excel Professional Styling ─────────────────────────────────────

    def _xl_style(self):
        """Return openpyxl style constants (lazy import)."""
        from openpyxl.styles import (
            PatternFill, Font, Alignment, Border, Side, numbers
        )
        return PatternFill, Font, Alignment, Border, Side, numbers

    def _xl_apply_sheet_style(
        self,
        ws,
        title: str,
        subtitle: str,
        col_headers: List[str],
        rows_data: List[List[Any]],
        amount_col_indices: List[int],
        freeze_row: int = 4,
    ) -> None:
        """
        Apply professional styling to a worksheet.
        Row 1: merged title
        Row 2: merged subtitle
        Row 3: column headers (navy bg, white bold)
        Row 4+: data (alternating white / light-blue)
        """
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        num_cols = len(col_headers)
        if num_cols == 0:
            return

        last_col_letter = get_column_letter(num_cols)

        # --- Colour palette ---
        NAVY_FILL = PatternFill("solid", fgColor="1A3A5C")
        TITLE_FILL = PatternFill("solid", fgColor="0D2137")
        EVEN_FILL = PatternFill("solid", fgColor="EBF5FB")
        TOTAL_FILL = PatternFill("solid", fgColor="D4E6F1")

        WHITE_BOLD = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
        TITLE_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=14)
        SUB_FONT = Font(name="Calibri", color="FFFFFF", size=10)
        HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
        DATA_FONT = Font(name="Calibri", size=9)
        TOTAL_FONT = Font(name="Calibri", bold=True, size=9)

        CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
        LEFT = Alignment(horizontal="left", vertical="center")
        RIGHT = Alignment(horizontal="right", vertical="center")

        thin = Side(style="thin", color="CCCCCC")
        BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

        # --- Row 1: Title ---
        ws.row_dimensions[1].height = 28
        ws.merge_cells(f"A1:{last_col_letter}1")
        cell = ws["A1"]
        cell.value = title
        cell.font = TITLE_FONT
        cell.fill = TITLE_FILL
        cell.alignment = CENTER

        # --- Row 2: Subtitle ---
        ws.row_dimensions[2].height = 20
        ws.merge_cells(f"A2:{last_col_letter}2")
        cell = ws["A2"]
        cell.value = subtitle
        cell.font = SUB_FONT
        cell.fill = NAVY_FILL
        cell.alignment = CENTER

        # --- Row 3: Column headers ---
        ws.row_dimensions[3].height = 22
        for col_idx, header in enumerate(col_headers, start=1):
            cell = ws.cell(row=3, column=col_idx, value=header)
            cell.font = HEADER_FONT
            cell.fill = NAVY_FILL
            cell.alignment = CENTER
            cell.border = BORDER

        # --- Rows 4+: Data ---
        for row_idx, row_vals in enumerate(rows_data, start=4):
            ws.row_dimensions[row_idx].height = 15
            is_even = (row_idx % 2 == 0)
            row_fill = EVEN_FILL if is_even else None

            for col_idx, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = DATA_FONT
                cell.border = BORDER
                if row_fill:
                    cell.fill = row_fill
                # Align & format
                if col_idx in amount_col_indices:
                    cell.alignment = RIGHT
                    if isinstance(val, (int, float, Decimal)):
                        cell.number_format = '#,##0.00 "XAF"'
                elif isinstance(val, (int, float)) and col_idx not in amount_col_indices:
                    cell.alignment = RIGHT
                else:
                    cell.alignment = LEFT

        # --- Auto-size columns ---
        for col_idx in range(1, num_cols + 1):
            col_letter = get_column_letter(col_idx)
            max_len = len(str(col_headers[col_idx - 1]))
            for row_vals in rows_data:
                if col_idx - 1 < len(row_vals):
                    cell_val = row_vals[col_idx - 1]
                    max_len = max(max_len, len(str(cell_val or "")))
            ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 45)

        # --- Freeze panes below header ---
        ws.freeze_panes = ws.cell(row=freeze_row, column=1)

    def _xl_detect_amount_cols(self, col_headers: List[str]) -> List[int]:
        """Return 1-based column indices where the header looks like an amount."""
        amount_keywords = {"amount", "total", "monto", "montant", "importe", "recaudado", "saldo"}
        return [
            i + 1
            for i, h in enumerate(col_headers)
            if any(kw in h.lower() for kw in amount_keywords)
        ]

    async def _write_beac_xlsx(
        self,
        data: Dict[str, Any],
        export_id: str,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Write BEAC report as Excel with multiple sheets — professional design."""
        if not PANDAS_AVAILABLE or not OPENPYXL_AVAILABLE:
            return await self._write_json(data.get("details", []), export_id, data.get("total_amount", 0))

        import openpyxl

        period_label = (
            f"{period_start.strftime('%d/%m/%Y')} — {period_end.strftime('%d/%m/%Y')}"
        )
        now_label = datetime.now().strftime("%d/%m/%Y %H:%M")
        main_title = "BANCO DE LOS ESTADOS DE ÁFRICA CENTRAL (BEAC)"
        generated_by = f"Generado: {now_label}  |  Referencia: BEAC-{export_id[:8].upper()}"

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # remove default empty sheet

        # ── Sheet 1: Resumen ──────────────────────────────────────────
        ws_sum = wb.create_sheet("Resumen")
        summary_headers = ["Indicateur", "Valor"]
        summary_rows = [
            ["Período", period_label],
            ["Total Transacciones", data.get("total_count", 0)],
            ["Monto Total (XAF)", float(data.get("total_amount", 0))],
            ["Divisa", "XAF"],
            ["Fecha Generación", now_label],
            ["Referencia Reporte", f"BEAC-{export_id[:8].upper()}"],
        ]
        self._xl_apply_sheet_style(
            ws_sum,
            title=main_title,
            subtitle=f"RESUMEN DEL REPORTE  |  {period_label}",
            col_headers=summary_headers,
            rows_data=summary_rows,
            amount_col_indices=[2],
        )

        # ── Sheet 2: Síntesis Diaria ─────────────────────────────────
        if data.get("summary"):
            ws_daily = wb.create_sheet("Síntesis Diaria")
            daily_data = data["summary"]
            if daily_data:
                daily_headers = list(daily_data[0].keys())
                daily_rows = [[row.get(h) for h in daily_headers] for row in daily_data]
                amount_cols = self._xl_detect_amount_cols(daily_headers)
                self._xl_apply_sheet_style(
                    ws_daily,
                    title=main_title,
                    subtitle=f"SÍNTESIS DIARIA  |  {period_label}  |  {generated_by}",
                    col_headers=daily_headers,
                    rows_data=daily_rows,
                    amount_col_indices=amount_cols,
                )

        # ── Sheet 3: Transacciones Detalladas ─────────────────────────
        if data.get("details"):
            ws_det = wb.create_sheet("Transacciones")
            det_data = data["details"]
            if det_data:
                det_headers = list(det_data[0].keys())
                det_rows = [[row.get(h) for h in det_headers] for row in det_data]
                amount_cols = self._xl_detect_amount_cols(det_headers)
                self._xl_apply_sheet_style(
                    ws_det,
                    title=main_title,
                    subtitle=f"TRANSACCIONES DETALLADAS  |  {period_label}  |  {generated_by}",
                    col_headers=det_headers,
                    rows_data=det_rows,
                    amount_col_indices=amount_cols,
                )

        buffer = BytesIO()
        wb.save(buffer)
        file_content = buffer.getvalue()

        return {
            "file_content": file_content,
            "file_name": f"{export_id}.xlsx",
            "file_size": len(file_content),
            "total_records": data.get("total_count", 0),
            "total_amount": float(data.get("total_amount", 0)),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    async def _generate_sage_x3_export(
        self,
        data: List[Dict[str, Any]],
        export_format: str,
        export_id: str,
    ) -> Dict[str, Any]:
        """Generate SAGE X3 format export."""
        # Build rows with transformed columns
        rows = []
        total_amount = Decimal("0")

        for record in data:
            row = {}
            for source_col, target_col, transform in self.SAGE_X3_COLUMNS:
                value = record.get(source_col)
                row[target_col] = transform(value)
            rows.append(row)
            total_amount += Decimal(str(record.get("total_amount", 0) or 0))

        # Generate file
        if export_format == "csv":
            return await self._write_csv(rows, export_id, self.SAGE_X3_COLUMNS, total_amount)
        elif export_format == "xlsx":
            return await self._write_xlsx(rows, export_id, [c[1] for c in self.SAGE_X3_COLUMNS], total_amount)
        else:
            return await self._write_csv(rows, export_id, self.SAGE_X3_COLUMNS, total_amount)

    async def _generate_ministry_report(
        self,
        data: Dict[str, Any],
        export_format: str,
        export_id: str,
        period_start: date,
        period_end: date,
        generated_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate ministry report."""
        if export_format == "pdf":
            return await self._write_ministry_pdf(data, export_id, period_start, period_end, generated_by_name=generated_by_name)
        elif export_format == "xlsx":
            return await self._write_ministry_xlsx(data, export_id, period_start, period_end)
        else:
            # Default to detailed CSV
            return await self._write_csv(
                data["details"],
                export_id,
                [(k, k, lambda x: x) for k in data["details"][0].keys()] if data["details"] else [],
                data["total_amount"],
            )

    async def _generate_reconciliation_export(
        self,
        data: List[Dict[str, Any]],
        export_format: str,
        export_id: str,
    ) -> Dict[str, Any]:
        """Generate reconciliation export."""
        total_amount = sum(float(r.get("amount", 0) or 0) for r in data)

        if export_format == "xlsx":
            return await self._write_xlsx(
                data, export_id, self.RECONCILIATION_COLUMNS, total_amount
            )
        else:
            return await self._write_csv(
                data, export_id,
                [(c, c, lambda x: x) for c in self.RECONCILIATION_COLUMNS],
                total_amount,
            )

    async def _generate_audit_report(
        self,
        data: List[Dict[str, Any]],
        export_format: str,
        export_id: str,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Generate audit report."""
        if not data:
            columns = ["payment_reference", "action", "from_status", "to_status", "comment", "created_at", "agent_name"]
        else:
            columns = list(data[0].keys())

        if export_format == "xlsx":
            return await self._write_xlsx(data, export_id, columns, 0)
        else:
            return await self._write_csv(
                data, export_id, [(c, c, lambda x: x) for c in columns], 0
            )

    async def _generate_generic_export(
        self,
        data: List[Dict[str, Any]],
        export_format: str,
        export_id: str,
        period_start: date = None,
        period_end: date = None,
        generated_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate generic export."""
        # Total = only completed/validated payments (not expired/rejected)
        completed_statuses = {"completed", "validated", "approved"}
        total_amount = sum(
            float(r.get("total_amount", 0) or 0)
            for r in data
            if str(r.get("workflow_status", "")).lower() in completed_statuses
        )

        if not data:
            columns = ["payment_reference", "total_amount", "currency", "payment_method", "workflow_status"]
        else:
            columns = list(data[0].keys())

        if export_format == "pdf":
            return await self._write_generic_pdf(
                data, export_id, columns, total_amount,
                title="Exportación Personalizada",
                generated_by_name=generated_by_name,
                period_start=period_start,
                period_end=period_end,
            )
        elif export_format == "xlsx":
            return await self._write_xlsx(data, export_id, columns, total_amount)
        elif export_format == "json":
            return await self._write_json(data, export_id, total_amount)
        else:
            return await self._write_csv(
                data, export_id, [(c, c, lambda x: x) for c in columns], total_amount
            )

    async def _write_generic_pdf(
        self,
        data: List[Dict[str, Any]],
        export_id: str,
        columns: List[str],
        total_amount: float,
        title: str = "Reporte",
        period_start: date = None,
        period_end: date = None,
        generated_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write generic PDF using Jinja2 template (landscape A4)."""
        if not XHTML2PDF_AVAILABLE:
            # Fallback to CSV if xhtml2pdf not available
            return await self._write_csv(
                data, export_id, [(c, c, lambda x: x) for c in columns], total_amount
            )

        def format_xaf(amount):
            return f"{float(amount or 0):,.0f}"

        # Column labels: clean up snake_case → Title Case
        amount_keywords = {"amount", "total", "montant", "monto", "precio", "cost"}
        col_defs = []
        for col in columns:
            label = col.replace("_", " ").title()
            is_amount = any(kw in col.lower() for kw in amount_keywords)
            col_defs.append({"key": col, "label": label, "is_amount": is_amount})

        # Format row data with status color-coding
        formatted_rows = []
        status_class_map = {
            "expired": "status-expired",
            "cancelled": "status-expired",
            "rejected": "status-rejected",
            "rechazado": "status-rejected",
            "completed": "status-completed",
            "validated": "status-completed",
            "approved": "status-completed",
        }
        for row in data:
            formatted = {}
            for col in columns:
                val = row.get(col)
                if val is None:
                    formatted[col] = "-"
                elif isinstance(val, (datetime, date)):
                    formatted[col] = val.strftime("%d/%m/%Y %H:%M") if isinstance(val, datetime) else val.strftime("%d/%m/%Y")
                elif isinstance(val, (Decimal, float, int)) and any(kw in col.lower() for kw in amount_keywords):
                    formatted[col] = format_xaf(val)
                else:
                    formatted[col] = str(val)[:60]
            # Add status CSS class for color-coding
            ws = str(row.get("workflow_status", "")).lower()
            formatted["_status_class"] = status_class_map.get(ws, "")
            formatted_rows.append(formatted)

        p_start = period_start.strftime("%d/%m/%Y") if period_start else "-"
        p_end = period_end.strftime("%d/%m/%Y") if period_end else "-"
        now = datetime.now()

        # Load logo
        logo_b64 = None
        try:
            import base64 as _b64
            logo_path = Path(__file__).parent.parent / "templates" / "logo.png"
            if logo_path.exists():
                logo_b64 = _b64.b64encode(logo_path.read_bytes()).decode()
        except Exception:
            pass

        # Try Jinja2 template
        html_content = None
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("treasury_generic_report.html")
                html_content = template.render(
                    report_title=title,
                    period_start=p_start,
                    period_end=p_end,
                    report_ref=f"{now.strftime('%Y%m%d-%H%M%S')}",
                    generated_at=now.strftime("%d/%m/%Y %H:%M"),
                    total_records=f"{len(data):,}",
                    total_amount_formatted=format_xaf(total_amount),
                    columns=col_defs,
                    rows=formatted_rows,
                    show_total=total_amount > 0,
                    logo_base64=logo_b64,
                    generated_by_name=generated_by_name or "Sistema",
                )
            except Exception as e:
                logger.warning(f"Generic PDF template failed: {e}")

        if not html_content:
            # Minimal fallback
            html_content = f"<html><body><h1>{title}</h1><p>{len(data)} registros, {format_xaf(total_amount)} XAF</p></body></html>"

        buffer = BytesIO()
        pisa.CreatePDF(BytesIO(html_content.encode("utf-8")), dest=buffer)
        file_content = buffer.getvalue()

        return {
            "file_content": file_content,
            "file_name": f"{export_id}.pdf",
            "file_size": len(file_content),
            "total_records": len(data),
            "total_amount": float(total_amount),
            "mime_type": "application/pdf",
        }

    async def _write_csv(
        self,
        data: List[Dict[str, Any]],
        export_id: str,
        columns: List[tuple],
        total_amount: float,
    ) -> Dict[str, Any]:
        """Write CSV file in-memory."""
        output = StringIO()

        if columns:
            # Extract target column names
            header = [c[1] if isinstance(c, tuple) else c for c in columns]
            writer = csv.DictWriter(output, fieldnames=header, delimiter=";")
            writer.writeheader()

            for row in data:
                # Transform row if needed
                if isinstance(columns[0], tuple) and len(columns[0]) == 3:
                    transformed = {}
                    for source, target, transform in columns:
                        transformed[target] = self._format_value(row.get(source))
                    writer.writerow(transformed)
                else:
                    writer.writerow({k: self._format_value(row.get(k)) for k in header})

        file_content = output.getvalue().encode("utf-8-sig")

        return {
            "file_content": file_content,
            "file_name": f"{export_id}.csv",
            "file_size": len(file_content),
            "total_records": len(data),
            "total_amount": float(total_amount),
            "mime_type": "text/csv",
        }

    async def _write_xlsx(
        self,
        data: List[Dict[str, Any]],
        export_id: str,
        columns: List[str],
        total_amount: float,
    ) -> Dict[str, Any]:
        """Write XLSX file using pandas (in-memory)."""
        if not PANDAS_AVAILABLE:
            # Fallback to CSV
            return await self._write_csv(
                data, export_id, [(c, c, lambda x: x) for c in columns], total_amount
            )

        buffer = BytesIO()

        # Create DataFrame
        df = pd.DataFrame(data)

        # Write to Excel buffer
        df.to_excel(buffer, index=False, engine="openpyxl")
        file_content = buffer.getvalue()

        return {
            "file_content": file_content,
            "file_name": f"{export_id}.xlsx",
            "file_size": len(file_content),
            "total_records": len(data),
            "total_amount": float(total_amount),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    async def _write_json(
        self,
        data: List[Dict[str, Any]],
        export_id: str,
        total_amount: float,
    ) -> Dict[str, Any]:
        """Write JSON file in-memory."""
        # Convert datetime objects
        def json_serializer(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            return str(obj)

        export_data = {
            "generated_at": datetime.now().isoformat(),
            "total_records": len(data),
            "total_amount": float(total_amount),
            "records": data,
        }

        output = StringIO()
        json.dump(export_data, output, default=json_serializer, indent=2, ensure_ascii=False)
        file_content = output.getvalue().encode("utf-8")

        return {
            "file_content": file_content,
            "file_name": f"{export_id}.json",
            "file_size": len(file_content),
            "total_records": len(data),
            "total_amount": float(total_amount),
            "mime_type": "application/json",
        }

    async def _write_ministry_pdf(
        self,
        data: Dict[str, Any],
        export_id: str,
        period_start: date,
        period_end: date,
        generated_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write ministry report PDF (in-memory)."""
        if not XHTML2PDF_AVAILABLE:
            # Fallback to CSV
            return await self._write_csv(
                data.get("details", []),
                export_id,
                [(k, k, lambda x: x) for k in (data.get("details", [{}])[0].keys() if data.get("details") else [])],
                data.get("total_amount", 0),
            )

        # Generate HTML content
        html_content = self._generate_ministry_html(data, period_start, period_end, generated_by_name=generated_by_name)

        # Convert to PDF in-memory
        buffer = BytesIO()
        try:
            pisa.CreatePDF(BytesIO(html_content.encode("utf-8")), dest=buffer)
        except (ValueError, Exception) as e:
            logger.error(f"xhtml2pdf failed for ministry PDF: {e}")
            # Fallback: return CSV instead of crashing
            return await self._write_csv(
                data.get("details", []),
                export_id,
                [(k, k, lambda x: x) for k in (data.get("details", [{}])[0].keys() if data.get("details") else [])],
                data.get("total_amount", 0),
            )
        file_content = buffer.getvalue()

        return {
            "file_content": file_content,
            "file_name": f"{export_id}.pdf",
            "file_size": len(file_content),
            "total_records": data.get("total_count", 0),
            "total_amount": float(data.get("total_amount", 0)),
            "mime_type": "application/pdf",
        }

    async def _write_ministry_xlsx(
        self,
        data: Dict[str, Any],
        export_id: str,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Write ministry report XLSX with multiple styled sheets — professional design."""
        if not OPENPYXL_AVAILABLE:
            return await self._write_csv(
                data.get("details", []),
                export_id,
                [(k, k, lambda x: x) for k in (data.get("details", [{}])[0].keys() if data.get("details") else [])],
                data.get("total_amount", 0),
            )

        import openpyxl

        period_label = (
            f"{period_start.strftime('%d/%m/%Y')} — {period_end.strftime('%d/%m/%Y')}"
        )
        now_label = datetime.now().strftime("%d/%m/%Y %H:%M")
        report_ref = f"MIN-{export_id[:8].upper()}"
        main_title = "MINISTERIO DE TESORERÍA Y PATRIMONIO DEL ESTADO"
        generated_by = f"Generado: {now_label}  |  Ref: {report_ref}"

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        def _build_sheet(sheet_name: str, section_title: str, rows_source: List[Dict]):
            if not rows_source:
                return
            ws = wb.create_sheet(sheet_name)
            headers = list(rows_source[0].keys())
            rows_data = [[row.get(h) for h in headers] for row in rows_source]
            amount_cols = self._xl_detect_amount_cols(headers)
            self._xl_apply_sheet_style(
                ws,
                title=main_title,
                subtitle=f"{section_title}  |  {period_label}  |  {generated_by}",
                col_headers=headers,
                rows_data=rows_data,
                amount_col_indices=amount_cols,
            )

        # ── Sheet 1: Resumen Ejecutivo ────────────────────────────────
        ws_exec = wb.create_sheet("Resumen Ejecutivo")
        exec_headers = ["Concepto", "Valor"]
        exec_rows = [
            ["Período", period_label],
            ["Total Pagos Procesados", data.get("total_count", 0)],
            ["Monto Total Recaudado (XAF)", float(data.get("total_amount", 0))],
            ["Divisa", "XAF"],
            ["Referencia Reporte", report_ref],
            ["Fecha Generación", now_label],
        ]
        self._xl_apply_sheet_style(
            ws_exec,
            title=main_title,
            subtitle=f"RESUMEN EJECUTIVO  |  {period_label}",
            col_headers=exec_headers,
            rows_data=exec_rows,
            amount_col_indices=[2],
        )

        # ── Sheet 2–4: By entity / method / service ───────────────────
        _build_sheet("Por Entidad", "RECAUDACIÓN POR ENTIDAD", data.get("by_entity") or [])
        _build_sheet("Por Método Pago", "RECAUDACIÓN POR MÉTODO DE PAGO", data.get("by_method") or [])
        _build_sheet("Por Servicio", "RECAUDACIÓN POR SERVICIO", data.get("by_service") or [])

        # ── Sheet 5: Detalle ──────────────────────────────────────────
        _build_sheet("Detalle Transacciones", "DETALLE DE TRANSACCIONES", data.get("details") or [])

        buffer = BytesIO()
        wb.save(buffer)
        file_content = buffer.getvalue()

        return {
            "file_content": file_content,
            "file_name": f"{export_id}.xlsx",
            "file_size": len(file_content),
            "total_records": data.get("total_count", 0),
            "total_amount": float(data.get("total_amount", 0)),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    # ── Chart Generation Utilities ───────────────────────────────────

    def _chart_to_base64(self, drawing: "Drawing") -> str:
        """Render a ReportLab Drawing to PNG and return base64 string."""
        buf = io.BytesIO()
        renderPM.drawToFile(drawing, buf, fmt="PNG", dpi=150)
        return base64.b64encode(buf.getvalue()).decode()

    def _get_chart_colors(self, n: int) -> list:
        """Return list of n ReportLab color objects from the palette."""
        palette = self.CHART_COLORS
        result = []
        for i in range(n):
            hex_color = palette[i % len(palette)]
            result.append(rl_colors.HexColor(hex_color))
        return result

    def _generate_bar_chart(
        self,
        labels: List[str],
        values: List[float],
        title: str = "",
        width: int = 520,
        height: int = 260,
        value_suffix: str = "",
    ) -> str:
        """Generate vertical bar chart → base64 PNG."""
        d = Drawing(width, height)
        chart = VerticalBarChart()
        chart.x = 60
        chart.y = 40
        chart.width = width - 100
        chart.height = height - 80
        chart.data = [values]
        chart.categoryAxis.categoryNames = labels
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.angle = 30
        chart.categoryAxis.labels.dy = -5
        chart.valueAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0
        chart.valueAxis.labelTextFormat = "%s"

        bar_colors = self._get_chart_colors(len(values))
        for i, c in enumerate(bar_colors):
            chart.bars[0].fillColor = self._get_chart_colors(1)[0]
            if i < len(values):
                try:
                    chart.bars[(0, i)].fillColor = c
                except (IndexError, KeyError):
                    pass

        d.add(chart)

        if title:
            d.add(String(width / 2, height - 10, title,
                         fontSize=10, fontName="Helvetica-Bold",
                         fillColor=rl_colors.HexColor("#1a365d"),
                         textAnchor="middle"))

        return self._chart_to_base64(d)

    def _generate_pie_chart(
        self,
        labels: List[str],
        values: List[float],
        title: str = "",
        width: int = 420,
        height: int = 260,
    ) -> str:
        """Generate pie chart with legend → base64 PNG."""
        d = Drawing(width, height)
        pie = Pie()
        pie.x = 30
        pie.y = 30
        pie.width = 160
        pie.height = 160
        pie.data = values
        pie.labels = None  # We use legend instead
        pie.sideLabels = False

        pie_colors = self._get_chart_colors(len(values))
        for i, c in enumerate(pie_colors):
            pie.slices[i].fillColor = c
            pie.slices[i].strokeColor = rl_colors.white
            pie.slices[i].strokeWidth = 1

        d.add(pie)

        # Legend on the right
        legend = Legend()
        legend.x = 220
        legend.y = height - 60
        legend.columnMaximum = 10
        legend.fontSize = 8
        legend.fontName = "Helvetica"
        legend.dx = 8
        legend.dy = 8
        legend.dxTextSpace = 5
        legend.deltay = 12
        legend.alignment = "right"

        total = sum(values) if values else 1
        legend.colorNamePairs = [
            (pie_colors[i], f"{labels[i]} ({values[i] / total * 100:.1f}%)")
            for i in range(len(labels))
        ]
        d.add(legend)

        if title:
            d.add(String(width / 2, height - 10, title,
                         fontSize=10, fontName="Helvetica-Bold",
                         fillColor=rl_colors.HexColor("#1a365d"),
                         textAnchor="middle"))

        return self._chart_to_base64(d)

    def _generate_horizontal_bar_chart(
        self,
        labels: List[str],
        values: List[float],
        title: str = "",
        width: int = 520,
        height: int = 300,
    ) -> str:
        """Generate horizontal bar chart → base64 PNG. Good for long labels."""
        d = Drawing(width, height)
        chart = HorizontalBarChart()
        chart.x = 180
        chart.y = 30
        chart.width = width - 210
        chart.height = height - 70
        chart.data = [values[::-1]]  # Reverse so top = highest
        chart.categoryAxis.categoryNames = labels[::-1]
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.dx = -5
        chart.valueAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0

        bar_colors = self._get_chart_colors(len(values))
        chart.bars[0].fillColor = bar_colors[0]
        for i in range(len(values)):
            try:
                chart.bars[(0, i)].fillColor = bar_colors[i % len(bar_colors)]
            except (IndexError, KeyError):
                pass

        d.add(chart)

        if title:
            d.add(String(width / 2, height - 10, title,
                         fontSize=10, fontName="Helvetica-Bold",
                         fillColor=rl_colors.HexColor("#1a365d"),
                         textAnchor="middle"))

        return self._chart_to_base64(d)

    def _generate_line_chart(
        self,
        x_labels: List[str],
        data_series: List[List[float]],
        series_names: List[str],
        title: str = "",
        width: int = 520,
        height: int = 260,
    ) -> str:
        """Generate line chart (one or more series) → base64 PNG."""
        d = Drawing(width, height)
        chart = HorizontalLineChart()
        chart.x = 60
        chart.y = 40
        chart.width = width - 100
        chart.height = height - 90
        chart.data = data_series
        chart.categoryAxis.categoryNames = x_labels
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.angle = 30
        chart.categoryAxis.labels.dy = -5
        chart.valueAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0

        line_colors = self._get_chart_colors(len(data_series))
        for i, c in enumerate(line_colors):
            chart.lines[i].strokeColor = c
            chart.lines[i].strokeWidth = 2
            chart.lines[i].symbol = None

        d.add(chart)

        # Legend
        if len(data_series) > 1 or series_names:
            legend = Legend()
            legend.x = 70
            legend.y = height - 10
            legend.fontSize = 8
            legend.columnMaximum = 1
            legend.alignment = "right"
            legend.dx = 8
            legend.dy = 8
            legend.dxTextSpace = 5
            legend.colorNamePairs = [
                (line_colors[i], series_names[i])
                for i in range(len(series_names))
            ]
            d.add(legend)

        if title:
            d.add(String(width / 2, height - 10, title,
                         fontSize=10, fontName="Helvetica-Bold",
                         fillColor=rl_colors.HexColor("#1a365d"),
                         textAnchor="middle"))

        return self._chart_to_base64(d)

    def _generate_ministry_charts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Generate all charts for the ministry report. Returns dict of base64 PNGs."""
        charts = {}

        if not REPORTLAB_CHARTS_AVAILABLE:
            return charts

        try:
            total_amount = float(data.get("total_amount", 0) or 0)

            # Compact chart dimensions for 2x2 grid layout
            compact_w, compact_h = 380, 200

            # Chart 1: Revenue by Entity (vertical bar) — only if > 1 entity
            by_entity = data.get("by_entity", [])
            if by_entity and len(by_entity) > 1:
                entity_labels = [
                    (e.get("entity_name", "N/A") or "N/A")[:20]
                    for e in by_entity
                ]
                entity_values = [
                    float(e.get("total_amount", 0) or 0) / 1000  # In thousands
                    for e in by_entity
                ]
                charts["entity_bar"] = self._generate_bar_chart(
                    entity_labels, entity_values,
                    title="Recaudación por Entidad (miles XAF)",
                    width=compact_w, height=compact_h,
                )

            # Chart 2: Payment Method Distribution (pie) — only if > 1 method
            by_method = data.get("by_method", [])
            if by_method and len(by_method) > 1:
                method_labels_map = {
                    "mobile_money": "Mobile Money",
                    "card": "Tarjeta",
                    "bank_transfer": "Transferencia",
                    "cash": "Efectivo",
                    "check": "Cheque",
                    "bange_wallet": "BANGE Wallet",
                }
                method_labels = [
                    method_labels_map.get(m.get("payment_method", ""), m.get("payment_method", "N/A"))
                    for m in by_method
                ]
                method_values = [
                    float(m.get("total_amount", 0) or 0)
                    for m in by_method
                ]
                charts["method_pie"] = self._generate_pie_chart(
                    method_labels, method_values,
                    title="Distribución por Método de Pago",
                    width=compact_w, height=compact_h,
                )

            # Chart 3: Top 10 Services (horizontal bar) — only if > 1 service
            by_service = data.get("by_service", [])[:10]
            if by_service and len(by_service) > 1:
                svc_labels = [
                    (s.get("service_name", "N/A") or "N/A")[:35]
                    for s in by_service
                ]
                svc_values = [
                    float(s.get("total_amount", 0) or 0) / 1000
                    for s in by_service
                ]
                charts["service_hbar"] = self._generate_horizontal_bar_chart(
                    svc_labels, svc_values,
                    title="Top 10 Servicios por Recaudación (miles XAF)",
                    width=compact_w, height=compact_h,
                )

            # Chart 4: Daily Revenue Trend (line) — only if > 1 day
            daily = data.get("daily_breakdown", [])
            if daily and len(daily) > 1:
                day_labels = [
                    d.get("date", "").strftime("%d/%m") if hasattr(d.get("date", ""), "strftime")
                    else str(d.get("date", ""))[-5:]
                    for d in daily
                ]
                day_amounts = [
                    float(d.get("amount", 0) or 0) / 1000
                    for d in daily
                ]
                day_counts = [
                    float(d.get("count", 0) or 0)
                    for d in daily
                ]
                charts["daily_line"] = self._generate_line_chart(
                    day_labels,
                    [day_amounts],
                    ["Monto (miles XAF)"],
                    title="Evolución Diaria de Recaudación",
                    width=compact_w, height=compact_h,
                )
                # Also generate transaction count trend
                charts["daily_count_line"] = self._generate_line_chart(
                    day_labels,
                    [day_counts],
                    ["Nº Transacciones"],
                    title="Evolución Diaria de Transacciones",
                    width=compact_w, height=compact_h,
                )

            # Chart 5: Entity contribution pie (complementary to bar)
            if by_entity and len(by_entity) > 1:
                ent_pie_labels = [
                    (e.get("entity_name", "N/A") or "N/A")[:25]
                    for e in by_entity
                ]
                ent_pie_values = [
                    float(e.get("total_amount", 0) or 0)
                    for e in by_entity
                ]
                charts["entity_pie"] = self._generate_pie_chart(
                    ent_pie_labels, ent_pie_values,
                    title="Participación por Entidad (%)",
                    width=compact_w, height=compact_h,
                )

        except Exception as e:
            logger.warning(f"Chart generation failed (non-blocking): {e}")

        return charts

    # ── Ministry HTML Generation ──────────────────────────────────────

    def _generate_ministry_html(
        self,
        data: Dict[str, Any],
        period_start: date,
        period_end: date,
        generated_by_name: Optional[str] = None,
    ) -> str:
        """Generate HTML for ministry PDF report using Jinja2 template."""
        total_amount = float(data.get("total_amount", 0) or 0)
        total_count = int(data.get("total_count", 0) or 0)
        avg_amount = total_amount / total_count if total_count > 0 else 0

        def format_xaf(amount):
            return f"{float(amount or 0):,.0f}"

        def format_count(count):
            return f"{int(count or 0):,}"

        # Payment method labels
        method_labels = {
            "mobile_money": "Mobile Money",
            "card": "Tarjeta Bancaria",
            "bank_transfer": "Transferencia Bancaria",
            "cash": "Efectivo",
            "check": "Cheque",
            "bange_wallet": "BANGE Wallet",
        }

        # Prepare entity data with percentages
        by_entity = []
        for entity in data.get("by_entity", []):
            ent_amount = float(entity.get("total_amount", 0) or 0)
            by_entity.append({
                "entity_name": entity.get("entity_name", "N/A"),
                "payment_count_formatted": format_count(entity.get("payment_count", 0)),
                "total_amount_formatted": format_xaf(ent_amount),
                "percentage": f"{(ent_amount / total_amount * 100):.1f}" if total_amount > 0 else "0.0",
            })

        # Prepare method data with percentages
        by_method = []
        for method in data.get("by_method", []):
            meth_amount = float(method.get("total_amount", 0) or 0)
            raw_method = method.get("payment_method", "N/A")
            by_method.append({
                "payment_method_label": method_labels.get(raw_method, raw_method),
                "payment_count_formatted": format_count(method.get("payment_count", 0)),
                "total_amount_formatted": format_xaf(meth_amount),
                "percentage": f"{(meth_amount / total_amount * 100):.1f}" if total_amount > 0 else "0.0",
            })

        # Top services
        top_services = []
        for service in data.get("by_service", [])[:20]:
            top_services.append({
                "service_name": (service.get("service_name", "N/A") or "N/A")[:60],
                "payment_count_formatted": format_count(service.get("payment_count", 0)),
                "total_amount_formatted": format_xaf(service.get("total_amount", 0)),
            })

        # Prepare daily breakdown (dates may be date objects or ISO strings from CTE JSONB)
        daily_breakdown = []
        for day in data.get("daily_breakdown", []):
            raw_date = day.get("date", "")
            if hasattr(raw_date, "strftime"):
                date_str = raw_date.strftime("%d/%m/%Y")
            elif isinstance(raw_date, str) and len(raw_date) >= 10:
                # Parse ISO date string "2026-02-23" → "23/02/2026"
                try:
                    date_str = datetime.strptime(raw_date[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except ValueError:
                    date_str = raw_date
            else:
                date_str = str(raw_date)
            daily_breakdown.append({
                "date": date_str,
                "count_formatted": format_count(day.get("count", 0)),
                "amount_formatted": format_xaf(day.get("amount", 0)),
            })

        # Generate charts (base64 PNG images)
        charts = self._generate_ministry_charts(data)
        has_charts = bool(charts)

        # Top services totals
        top_svc_total_count = sum(
            int(s.get("payment_count", 0) or 0) for s in data.get("by_service", [])[:20]
        )
        top_svc_total_amount = sum(
            float(s.get("total_amount", 0) or 0) for s in data.get("by_service", [])[:20]
        )

        # Load logo for PDF header
        logo_b64 = None
        try:
            import base64 as _b64
            logo_path = Path(__file__).parent.parent / "templates" / "logo.png"
            if logo_path.exists():
                logo_b64 = _b64.b64encode(logo_path.read_bytes()).decode()
        except Exception:
            pass

        # Try Jinja2 template, fallback to inline
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("treasury_ministry_report.html")
                return template.render(
                    period_start=period_start.strftime("%d/%m/%Y"),
                    period_end=period_end.strftime("%d/%m/%Y"),
                    report_ref=f"{period_start.strftime('%Y%m')}-{datetime.now().strftime('%H%M%S')}",
                    generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
                    total_amount_formatted=format_xaf(total_amount),
                    total_count=format_count(total_count),
                    avg_amount_formatted=format_xaf(avg_amount),
                    success_rate="100",
                    by_entity=by_entity,
                    by_method=by_method,
                    top_services=top_services,
                    top_services_total_count=format_count(top_svc_total_count),
                    top_services_total_amount=format_xaf(top_svc_total_amount),
                    daily_breakdown=daily_breakdown if daily_breakdown else None,
                    charts=charts,
                    has_charts=has_charts,
                    logo_base64=logo_b64,
                    generated_by_name=generated_by_name or "Sistema",
                )
            except Exception as e:
                logger.warning(f"Jinja2 template rendering failed, using fallback: {e}")

        # Fallback inline HTML (minimal)
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
        <style>body{{font-family:Arial;font-size:11px;margin:20px}}
        h1{{color:#1a365d;font-size:16px;text-align:center}}
        table{{width:100%;border-collapse:collapse;margin:10px 0}}
        th{{background:#2d3748;color:white;padding:6px 8px;text-align:left}}
        td{{padding:5px 8px;border-bottom:1px solid #e2e8f0}}
        .amount{{text-align:right}}.total-row{{font-weight:bold;background:#ebf8ff}}</style>
        </head><body>
        <h1>INFORME DE RECAUDACIÓN - TESORERÍA</h1>
        <p style="text-align:center">Período: {period_start.strftime('%d/%m/%Y')} - {period_end.strftime('%d/%m/%Y')}</p>
        <p><strong>Total Recaudado:</strong> {format_xaf(total_amount)} XAF | <strong>Transacciones:</strong> {format_count(total_count)}</p>
        <p style="text-align:center;font-size:9px;color:#999;margin-top:20px">Generado por Facil - {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </body></html>"""
        return html

    def _format_value(self, value):
        """Format value for CSV export."""
        if value is None:
            return ""
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return str(value)


# Singleton instance
treasury_export_service = TreasuryExportService()
