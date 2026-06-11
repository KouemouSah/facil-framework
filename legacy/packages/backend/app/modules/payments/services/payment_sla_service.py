"""
Payment SLA Service
====================
Monitors cash/check payments pending agent validation and handles:
1. 48h warning → Email with HTML table to treasury agents
2. 5-day escalation → Email with HTML table to supervisors
3. 15-day expiration → Expire payment + service request, email citizen

Called by cron endpoint: POST /api/v1/internal/cron/payment-sla-check

Architecture:
- 3 batch SQL queries (UPDATE...WHERE...RETURNING) - O(1) regardless of row count
- Partial index on service_payments for fast lookups
- HTML table format emails (1 consolidated email per recipient, not per payment)
- CommunicationService for email delivery
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from loguru import logger

from app.modules.communications.services.communication_service import CommunicationService
from app.modules.communications.models.communication import CommunicationType


# =============================================================================
# SLA THRESHOLDS (configurable)
# =============================================================================

SLA_WARNING_HOURS = 48        # 48h → send warning to treasury agent
SLA_ESCALATION_DAYS = 5       # 5 days → escalate to supervisor
SLA_EXPIRATION_DAYS = 15      # 15 days → expire payment + request


# =============================================================================
# WORKFLOW LABELS (for readable emails)
# =============================================================================

WORKFLOW_LABELS = {
    "PASAPORTE": "Pasaporte",
    "CONDUCIR": "Permiso de Conducir",
    "CONTRATO": "Contrato ONRC",
    "RESIDENCIA": "Tarjeta de Residencia",
    "MATRICULACION": "Matriculacion de Vehiculo",
    "INSPECCION_TECNICA": "Inspeccion Tecnica (ITVE)",
    "DUPLICADO_VEHICULO": "Duplicado Vehiculo",
    "PROMOCION_ADMINISTRATIVA": "Promocion Administrativa",
    "CARNET_FUNCIONARIO": "Carnet de Funcionario",
    "VERIFICACION_FUNCIONARIO": "Verificacion de Funcionario",
    "PRORROGA_VISADO": "Prorroga de Visado",
    "VISADO_ALTERNATIVO": "Visado Alternativo",
    "PERMISO_PERMANENCIA": "Permiso de Permanencia",
    "SALIDA_VISADO_VENCIDO": "Salida con Visado Vencido",
    "PERMISO_EXTRAORDINARIO": "Permiso Extraordinario",
    "CERTIFICADO_ADMINISTRATIVO": "Certificado Administrativo",
}


class PaymentSLAService:
    """Handles SLA monitoring for cash/check payments pending agent validation."""

    def __init__(self):
        self.communication_service = CommunicationService()

    async def run_sla_check(self, db) -> Dict[str, Any]:
        """
        Run all 3 SLA checks in sequence.
        Returns summary of actions taken.
        """
        results = {
            "warnings_sent": 0,
            "escalations_sent": 0,
            "expirations_processed": 0,
            "errors": [],
        }

        # 1. 48h warning → treasury agents
        try:
            warned = await self._process_warnings(db)
            results["warnings_sent"] = warned
        except Exception as e:
            logger.error(f"SLA warning check failed: {e}")
            results["errors"].append(f"warnings: {str(e)}")

        # 2. 5-day escalation → supervisors
        try:
            escalated = await self._process_escalations(db)
            results["escalations_sent"] = escalated
        except Exception as e:
            logger.error(f"SLA escalation check failed: {e}")
            results["errors"].append(f"escalations: {str(e)}")

        # 3. 15-day expiration → citizens
        try:
            expired = await self._process_expirations(db)
            results["expirations_processed"] = expired
        except Exception as e:
            logger.error(f"SLA expiration check failed: {e}")
            results["errors"].append(f"expirations: {str(e)}")

        return results

    # =========================================================================
    # STEP 1: 48h WARNING → TREASURY AGENTS
    # =========================================================================

    async def _process_warnings(self, db) -> int:
        """
        Find cash payments pending > 48h that haven't been warned yet.
        Send 1 consolidated email per treasury agent with HTML table.
        Mark sla_warning_sent = true.
        """
        # Compute threshold in Python, pass as parameterized $1
        warning_threshold = datetime.now(timezone.utc) - timedelta(hours=SLA_WARNING_HOURS)

        # Batch mark + return in one atomic query
        warned_payments = await db.fetch("""
            UPDATE service_payments sp
            SET sla_warning_sent = true
            FROM service_requests sr
            JOIN users u ON u.id = sr.user_id
            LEFT JOIN entity_locations el ON el.id = sr.entity_location_id
            WHERE sp.service_request_id = sr.id
              AND sp.payment_method IN ('cash', 'check')
              AND sp.status = 'pending'
              AND sp.workflow_status = 'pending_agent_review'
              AND sp.validated_at IS NULL
              AND sp.sla_warning_sent = false
              AND sp.created_at < $1
            RETURNING
                sp.id, sp.payment_reference, sp.total_amount, sp.currency,
                sp.payment_method, sp.created_at,
                sr.reference as sr_reference, sr.workflow_code,
                u.first_name as citizen_first_name, u.last_name as citizen_last_name,
                el.location_name as location_name
        """, warning_threshold)

        if not warned_payments:
            logger.info("SLA warning: no payments to warn")
            return 0

        logger.info(f"SLA warning: {len(warned_payments)} payments marked for warning")

        # Get treasury agent emails
        agent_emails = await self._get_treasury_agent_emails(db)
        if not agent_emails:
            logger.warning("SLA warning: no active treasury agents found")
            return len(warned_payments)

        # Build and send HTML table email to each agent
        html_body = self._build_warning_email_html(warned_payments)
        subject = f"[SLA] {len(warned_payments)} pago(s) pendiente(s) > {SLA_WARNING_HOURS}h - TaxasGE"

        for email in agent_emails:
            await self._send_email_async(email, subject, html_body)

        return len(warned_payments)

    # =========================================================================
    # STEP 2: 5-DAY ESCALATION → SUPERVISORS
    # =========================================================================

    async def _process_escalations(self, db) -> int:
        """
        Find cash payments pending > 5 days that have been warned but not escalated.
        Escalate to supervisor: update workflow_status + send consolidated email.
        """
        escalation_threshold = datetime.now(timezone.utc) - timedelta(days=SLA_ESCALATION_DAYS)

        escalated_payments = await db.fetch("""
            UPDATE service_payments sp
            SET sla_escalated = true,
                workflow_status = 'escalated_supervisor'
            FROM service_requests sr
            JOIN users u ON u.id = sr.user_id
            LEFT JOIN entity_locations el ON el.id = sr.entity_location_id
            WHERE sp.service_request_id = sr.id
              AND sp.payment_method IN ('cash', 'check')
              AND sp.status = 'pending'
              AND sp.workflow_status = 'pending_agent_review'
              AND sp.validated_at IS NULL
              AND sp.sla_warning_sent = true
              AND sp.sla_escalated = false
              AND sp.created_at < $1
            RETURNING
                sp.id, sp.payment_reference, sp.total_amount, sp.currency,
                sp.payment_method, sp.created_at,
                sr.reference as sr_reference, sr.workflow_code,
                u.first_name as citizen_first_name, u.last_name as citizen_last_name,
                u.email as citizen_email,
                el.location_name as location_name
        """, escalation_threshold)

        if not escalated_payments:
            logger.info("SLA escalation: no payments to escalate")
            return 0

        logger.info(f"SLA escalation: {len(escalated_payments)} payments escalated")

        # Get supervisor emails (entity TESORO + is_supervisor=true, OR admin users)
        supervisor_emails = await self._get_supervisor_emails(db)
        if not supervisor_emails:
            logger.warning("SLA escalation: no supervisors found, falling back to agents")
            supervisor_emails = await self._get_treasury_agent_emails(db)

        if not supervisor_emails:
            logger.error("SLA escalation: no recipients found at all")
            return len(escalated_payments)

        html_body = self._build_escalation_email_html(escalated_payments)
        subject = f"[URGENTE] {len(escalated_payments)} pago(s) sin validar > {SLA_ESCALATION_DAYS} dias - TaxasGE"

        for email in supervisor_emails:
            await self._send_email_async(email, subject, html_body)

        return len(escalated_payments)

    # =========================================================================
    # STEP 3: 15-DAY EXPIRATION → CITIZENS
    # =========================================================================

    async def _process_expirations(self, db) -> int:
        """
        Find cash payments pending > 15 days. Expire them:
        - payment status → 'cancelled', workflow_status → 'expired'
        - service_request status → 'EXPIRED'
        - P1: Cancel linked appointments (reservations + holds)
        - P2: Schedule Firebase document cleanup (mark for deletion)
        - P3: Insert audit trail in service_request_history
        - P4: Expire even if sla_warning_sent=false (cron may have been down)
        Send individual email to each citizen.
        """
        expiration_threshold = datetime.now(timezone.utc) - timedelta(days=SLA_EXPIRATION_DAYS)

        # P4: Remove sla_warning_sent/sla_escalated preconditions — if payment
        # has been pending > 15 days it must expire regardless of whether
        # the warning/escalation cron ran previously.
        expired_payments = await db.fetch("""
            UPDATE service_payments sp
            SET status = 'cancelled',
                workflow_status = 'expired'
            FROM service_requests sr, users u
            WHERE sp.service_request_id = sr.id
              AND sp.user_id = u.id
              AND sp.payment_method IN ('cash', 'check')
              AND sp.status = 'pending'
              AND sp.workflow_status IN ('pending_agent_review', 'escalated_supervisor')
              AND sp.validated_at IS NULL
              AND sp.created_at < $1
            RETURNING
                sp.id as payment_id, sp.payment_reference, sp.total_amount,
                sp.currency, sp.created_at as payment_created,
                sr.id as request_id, sr.reference as sr_reference,
                sr.workflow_code, sr.status as previous_status,
                u.email as citizen_email, u.first_name, u.last_name,
                u.preferred_language
        """, expiration_threshold)

        if not expired_payments:
            logger.info("SLA expiration: no payments to expire")
            return 0

        logger.info(f"SLA expiration: {len(expired_payments)} payments expired")

        request_ids = [r["request_id"] for r in expired_payments]

        # Batch update service_requests status
        if request_ids:
            await db.execute("""
                UPDATE service_requests
                SET status = 'EXPIRED',
                    updated_at = NOW()
                WHERE id = ANY($1::uuid[])
                  AND status NOT IN ('COMPLETED', 'CANCELLED', 'EXPIRED')
            """, request_ids)

        # P1: Cancel linked appointments (reservations + holds)
        await self._cancel_appointments(db, request_ids)

        # P3: Insert audit trail in service_request_history
        await self._insert_expiration_history(db, expired_payments)

        # P2: Mark documents for cleanup (soft-delete file paths, async Firebase cleanup)
        await self._schedule_document_cleanup(db, request_ids)

        # Send individual email to each citizen
        for payment in expired_payments:
            try:
                lang = payment.get("preferred_language") or "es"
                citizen_name = f"{payment['first_name'] or ''} {payment['last_name'] or ''}".strip()
                await self._send_citizen_expiration_email(
                    email=payment["citizen_email"],
                    citizen_name=citizen_name or "Usuario",
                    reference=payment["sr_reference"],
                    workflow_code=payment["workflow_code"],
                    amount=float(payment["total_amount"]),
                    currency=payment["currency"],
                    language=lang,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send expiration email for {payment['sr_reference']}: {e}"
                )

        return len(expired_payments)

    # =========================================================================
    # P1: Cancel linked appointments
    # =========================================================================

    async def _cancel_appointments(self, db, request_ids: List[str]) -> None:
        """Cancel appointment reservations and release holds for expired requests."""
        if not request_ids:
            return

        # Cancel reservations (scheduled → cancelled)
        cancelled_reservations = await db.fetchval("""
            WITH updated AS (
                UPDATE appointment_reservations
                SET status = 'cancelled',
                    cancelled_at = NOW(),
                    cancellation_reason = 'Payment expired (SLA 15 days)'
                WHERE service_request_id = ANY($1::uuid[])
                  AND status NOT IN ('cancelled', 'completed')
                RETURNING id
            )
            SELECT COUNT(*) FROM updated
        """, request_ids)

        # Release holds (held/confirmed → expired)
        released_holds = await db.fetchval("""
            WITH updated AS (
                UPDATE appointment_holds
                SET status = 'expired'::appointment_hold_status,
                    released_at = NOW()
                WHERE service_request_id = ANY($1::uuid[])
                  AND status NOT IN ('expired', 'released')
                RETURNING id
            )
            SELECT COUNT(*) FROM updated
        """, request_ids)

        if cancelled_reservations or released_holds:
            logger.info(
                f"SLA expiration: cancelled {cancelled_reservations} reservations, "
                f"released {released_holds} holds"
            )

    # =========================================================================
    # P3: Insert audit trail in service_request_history
    # =========================================================================

    async def _insert_expiration_history(self, db, expired_payments: list) -> None:
        """Insert a history entry for each expired request (citizen-visible)."""
        if not expired_payments:
            return

        import json

        rows = []
        for p in expired_payments:
            rows.append((
                p["request_id"],
                "status_change",                          # action
                p.get("previous_status") or "PAYMENT_PENDING",  # previous_status
                "EXPIRED",                                # new_status
                json.dumps({
                    "reason": "payment_sla_expired",
                    "payment_reference": p["payment_reference"],
                    "payment_amount": str(p["total_amount"]),
                    "sla_days": SLA_EXPIRATION_DAYS,
                }),
                f"Pago {p['payment_reference']} expirado tras {SLA_EXPIRATION_DAYS} dias sin validacion. Solicitud cerrada automaticamente.",
            ))

        await db.executemany("""
            INSERT INTO service_request_history
                (id, service_request_id, action, previous_status, new_status, details, comment, performed_at)
            VALUES
                (gen_random_uuid(), $1, $2, $3, $4, $5::jsonb, $6, NOW())
        """, rows)

        logger.info(f"SLA expiration: {len(rows)} history entries inserted")

    # =========================================================================
    # P2: Schedule document cleanup (Firebase Storage)
    # =========================================================================

    async def _schedule_document_cleanup(self, db, request_ids: List[str]) -> None:
        """
        Collect Firebase file paths for expired requests and delete them.
        Documents are in service_request_documents.file_path.
        Deletion is best-effort (non-blocking) — files may already be gone.
        """
        if not request_ids:
            return

        # Fetch file paths
        file_rows = await db.fetch("""
            SELECT id, file_path
            FROM service_request_documents
            WHERE service_request_id = ANY($1::uuid[])
              AND file_path IS NOT NULL
        """, request_ids)

        if not file_rows:
            return

        deleted_count = 0
        failed_count = 0

        try:
            from app.modules.documents.services.storage_service import FirebaseStorageService
            storage = FirebaseStorageService()
            await storage.initialize()

            for row in file_rows:
                try:
                    await storage.delete_file(row["file_path"])
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"SLA cleanup: failed to delete {row['file_path']}: {e}")
                    failed_count += 1
        except Exception as e:
            logger.warning(f"SLA cleanup: StorageService unavailable, skipping: {e}")
            return

        # Mark documents as cleaned in DB (nullify file_path)
        if deleted_count > 0:
            doc_ids = [row["id"] for row in file_rows]
            await db.execute("""
                UPDATE service_request_documents
                SET file_path = NULL,
                    updated_at = NOW()
                WHERE id = ANY($1::uuid[])
            """, doc_ids)

        logger.info(
            f"SLA cleanup: {deleted_count} files deleted, {failed_count} failed "
            f"for {len(request_ids)} expired requests"
        )

    # =========================================================================
    # HELPER: Get treasury agent & supervisor emails
    # =========================================================================

    async def _get_treasury_agent_emails(self, db) -> List[str]:
        """Get email addresses of active treasury agents."""
        rows = await db.fetch("""
            SELECT DISTINCT u.email
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            JOIN entities e ON e.id = ap.entity_id
            WHERE e.code = 'TESORO'
              AND ap.is_active = true
              AND u.email IS NOT NULL
        """)
        return [r["email"] for r in rows]

    async def _get_supervisor_emails(self, db) -> List[str]:
        """Get email addresses of treasury supervisors."""
        rows = await db.fetch("""
            SELECT DISTINCT u.email
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            JOIN entities e ON e.id = ap.entity_id
            WHERE e.code = 'TESORO'
              AND ap.is_active = true
              AND ap.is_supervisor = true
              AND u.email IS NOT NULL
        """)
        return [r["email"] for r in rows]

    # =========================================================================
    # HELPER: Send email via CommunicationService
    # =========================================================================

    async def _send_email_async(self, recipient: str, subject: str, html_body: str) -> bool:
        """Send email via CommunicationService (sync → async via executor)."""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.communication_service.send_communication(
                    channel=CommunicationType.EMAIL,
                    recipient=recipient,
                    subject=subject,
                    content=html_body,
                )
            )
        except Exception as e:
            logger.error(f"Failed to send SLA email to {recipient}: {e}")
            return False

    # =========================================================================
    # HTML BUILDERS: Warning email (HTML table for agents)
    # =========================================================================

    def _build_warning_email_html(self, payments: list) -> str:
        """Build HTML email with table of payments pending > 48h."""
        rows_html = ""
        for p in payments:
            created = p["created_at"].strftime("%d/%m/%Y %H:%M") if p["created_at"] else "-"
            hours_elapsed = self._hours_since(p["created_at"])
            workflow_label = WORKFLOW_LABELS.get(p["workflow_code"], p["workflow_code"])
            citizen_name = f"{p['citizen_first_name'] or ''} {p['citizen_last_name'] or ''}".strip()
            location = p.get("location_name") or "-"
            rows_html += f"""
            <tr>
                <td style="padding:8px;border:1px solid #e5e7eb;">{p['sr_reference']}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{citizen_name}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{workflow_label}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{location}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{p['total_amount']:,.0f} {p['currency']}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{p['payment_method']}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{created}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;color:#dc2626;font-weight:bold;">{hours_elapsed}h</td>
            </tr>"""

        return self._wrap_agent_email(
            title="Pagos pendientes de validacion",
            subtitle=f"{len(payments)} pago(s) en efectivo/cheque pendiente(s) de validacion desde hace mas de {SLA_WARNING_HOURS} horas.",
            intro="Los siguientes pagos requieren su atencion urgente:",
            table_headers=["Referencia", "Ciudadano", "Servicio", "Sede", "Monto", "Metodo", "Fecha", "Espera"],
            table_rows=rows_html,
            action_text="Por favor, valide o rechace estos pagos lo antes posible.",
            color="#f59e0b",  # amber/warning
        )

    # =========================================================================
    # HTML BUILDERS: Escalation email (HTML table for supervisors)
    # =========================================================================

    def _build_escalation_email_html(self, payments: list) -> str:
        """Build HTML email with table of payments escalated > 5 days."""
        rows_html = ""
        for p in payments:
            created = p["created_at"].strftime("%d/%m/%Y %H:%M") if p["created_at"] else "-"
            days_elapsed = self._days_since(p["created_at"])
            workflow_label = WORKFLOW_LABELS.get(p["workflow_code"], p["workflow_code"])
            citizen_name = f"{p['citizen_first_name'] or ''} {p['citizen_last_name'] or ''}".strip()
            location = p.get("location_name") or "-"
            rows_html += f"""
            <tr>
                <td style="padding:8px;border:1px solid #e5e7eb;">{p['sr_reference']}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{citizen_name}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{p['citizen_email']}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{workflow_label}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{location}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{p['total_amount']:,.0f} {p['currency']}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;">{created}</td>
                <td style="padding:8px;border:1px solid #e5e7eb;color:#dc2626;font-weight:bold;">{days_elapsed}j</td>
            </tr>"""

        return self._wrap_agent_email(
            title="ESCALATION: Pagos sin validar",
            subtitle=f"{len(payments)} pago(s) sin validar desde hace mas de {SLA_ESCALATION_DAYS} dias.",
            intro="Los siguientes pagos han superado el plazo maximo de validacion y han sido escalados:",
            table_headers=["Referencia", "Ciudadano", "Email", "Servicio", "Sede", "Monto", "Fecha", "Espera"],
            table_rows=rows_html,
            action_text=f"Si estos pagos no se validan antes de {SLA_EXPIRATION_DAYS} dias, seran expirados automaticamente y el ciudadano sera notificado.",
            color="#dc2626",  # red/critical
        )

    # =========================================================================
    # HTML BUILDERS: Common table email wrapper
    # =========================================================================

    def _wrap_agent_email(
        self,
        title: str,
        subtitle: str,
        intro: str,
        table_headers: List[str],
        table_rows: str,
        action_text: str,
        color: str,
    ) -> str:
        """Wrap table content in professional email layout."""
        headers_html = "".join(
            f'<th style="padding:8px;border:1px solid #e5e7eb;background-color:{color};color:#fff;text-align:left;">{h}</th>'
            for h in table_headers
        )
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#f5f5f5;">
            <div style="padding:20px;">
                <div style="max-width:800px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <div style="background:{color};padding:20px 30px;">
                        <h1 style="color:#fff;margin:0;font-size:22px;">{title}</h1>
                        <p style="color:rgba(255,255,255,0.9);margin:5px 0 0;font-size:14px;">{subtitle}</p>
                    </div>
                    <div style="padding:30px;">
                        <p style="font-size:15px;color:#333;">{intro}</p>
                        <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:13px;">
                            <thead>
                                <tr>{headers_html}</tr>
                            </thead>
                            <tbody>
                                {table_rows}
                            </tbody>
                        </table>
                        <div style="background-color:#fef3cd;border:1px solid #ffc107;border-radius:4px;padding:12px 16px;margin-top:20px;">
                            <strong>Accion requerida:</strong> {action_text}
                        </div>
                    </div>
                    <div style="background:#f9fafb;padding:15px 30px;border-top:1px solid #e5e7eb;text-align:center;">
                        <p style="margin:0;font-size:12px;color:#6b7280;">
                            Mensaje automatico generado el {now} - TaxasGE Platform
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    # =========================================================================
    # HTML BUILDERS: Citizen expiration email
    # =========================================================================

    async def _send_citizen_expiration_email(
        self,
        email: str,
        citizen_name: str,
        reference: str,
        workflow_code: str,
        amount: float,
        currency: str,
        language: str = "es",
    ):
        """Send individual expiration email to citizen."""
        workflow_label = WORKFLOW_LABELS.get(workflow_code, workflow_code)

        bodies = {
            "es": {
                "subject": f"Solicitud {reference} expirada - TaxasGE",
                "greeting": f"Estimado/a {citizen_name},",
                "body": f"""
                    <p>Le informamos que su solicitud <strong>{reference}</strong>
                    ({workflow_label}) ha sido <strong>expirada</strong> debido a que el pago
                    de <strong>{amount:,.0f} {currency}</strong> no fue validado dentro del
                    plazo de {SLA_EXPIRATION_DAYS} dias.</p>
                    <p>Si ya realizo el pago, por favor contacte con nuestro servicio de soporte
                    para resolver la situacion.</p>
                    <p>Si desea continuar con su tramite, debera crear una nueva solicitud.</p>
                """,
                "footer": "Este es un mensaje automatico de TaxasGE.",
            },
            "fr": {
                "subject": f"Demande {reference} expiree - TaxasGE",
                "greeting": f"Cher/Chere {citizen_name},",
                "body": f"""
                    <p>Nous vous informons que votre demande <strong>{reference}</strong>
                    ({workflow_label}) a <strong>expire</strong> car le paiement
                    de <strong>{amount:,.0f} {currency}</strong> n'a pas ete valide dans le
                    delai de {SLA_EXPIRATION_DAYS} jours.</p>
                    <p>Si vous avez deja effectue le paiement, veuillez contacter notre
                    service de support pour resoudre la situation.</p>
                    <p>Si vous souhaitez poursuivre votre demarche, vous devrez creer une nouvelle demande.</p>
                """,
                "footer": "Ceci est un message automatique de TaxasGE.",
            },
            "en": {
                "subject": f"Request {reference} expired - TaxasGE",
                "greeting": f"Dear {citizen_name},",
                "body": f"""
                    <p>We inform you that your request <strong>{reference}</strong>
                    ({workflow_label}) has <strong>expired</strong> because the payment
                    of <strong>{amount:,.0f} {currency}</strong> was not validated within
                    the {SLA_EXPIRATION_DAYS}-day deadline.</p>
                    <p>If you have already made the payment, please contact our support
                    service to resolve the situation.</p>
                    <p>If you wish to continue with your procedure, you will need to create a new request.</p>
                """,
                "footer": "This is an automated message from TaxasGE.",
            },
        }

        tpl = bodies.get(language, bodies["es"])
        now = datetime.now(timezone.utc)

        html = f"""
        <!DOCTYPE html>
        <html lang="{language}">
        <head><meta charset="utf-8"></head>
        <body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#f5f5f5;">
            <div style="padding:20px;">
                <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <div style="background:linear-gradient(135deg,#2563eb 0%,#1e40af 100%);padding:30px 20px;text-align:center;">
                        <h1 style="color:#fff;margin:0;font-size:28px;">TaxasGE</h1>
                    </div>
                    <div style="padding:40px 30px;">
                        <p style="font-size:16px;color:#333;">{tpl['greeting']}</p>
                        <div style="font-size:15px;color:#4b5563;line-height:1.8;">
                            {tpl['body']}
                        </div>
                    </div>
                    <div style="background:#f9fafb;padding:25px 30px;text-align:center;border-top:1px solid #e5e7eb;">
                        <p style="margin:5px 0;font-size:12px;color:#6b7280;">{tpl['footer']}</p>
                        <p style="margin-top:10px;font-size:11px;color:#6b7280;">
                            &copy; {now.year} TaxasGE Platform
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        await self._send_email_async(email, tpl["subject"], html)

    # =========================================================================
    # UTILITY
    # =========================================================================

    @staticmethod
    def _hours_since(dt: Optional[datetime]) -> int:
        """Calculate hours since a datetime."""
        if not dt:
            return 0
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt
        return int(delta.total_seconds() / 3600)

    @staticmethod
    def _days_since(dt: Optional[datetime]) -> int:
        """Calculate days since a datetime."""
        if not dt:
            return 0
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt
        return delta.days
