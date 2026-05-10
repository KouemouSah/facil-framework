"""OMS Obligation Reminders — Automated email/SMS alerts for license compliance.

3-tier SLA monitoring (follows PaymentSLAService pattern):
  - J-15 before due_date: reminder to company owners (email)
  - J+1 after due_date: overdue notice to company + agent (email + SMS)
  - J+30 after due_date: escalation to supervisors (email consolidated)

Only targets obligations in status 'pending' or 'overdue' (not paid/completed/processing).
Idempotent: uses reminder_sent_at to avoid duplicate sends.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# SLA thresholds (days)
REMINDER_BEFORE_DUE = 15  # J-15: reminder before due date
OVERDUE_NOTICE_AFTER = 1  # J+1: overdue notice
ESCALATION_AFTER = 30     # J+30: escalation to supervisor


class OmsReminderService:
    """Monitors license obligation deadlines and sends tiered reminders."""

    def __init__(self):
        self._comm_service = None

    def _get_comm_service(self):
        """Lazy-load CommunicationService to avoid import cycles."""
        if self._comm_service is None:
            try:
                from app.modules.communications.services.communication_service import (
                    CommunicationService,
                )
                self._comm_service = CommunicationService()
            except Exception as e:
                logger.error("CommunicationService unavailable: %s", e)
        return self._comm_service

    async def run_reminder_check(self, db) -> Dict[str, Any]:
        """Run all 3 reminder tiers. Called by Cloud Scheduler daily."""
        results = {
            "reminders_sent": 0,
            "overdue_notices_sent": 0,
            "escalations_sent": 0,
            "weekly_reports_sent": 0,
            "errors": [],
        }

        try:
            results["reminders_sent"] = await self._process_upcoming_reminders(db)
        except Exception as e:
            logger.error("OMS reminder: upcoming reminders failed: %s", e, exc_info=True)
            results["errors"].append(f"upcoming: {e}")

        try:
            results["overdue_notices_sent"] = await self._process_overdue_notices(db)
        except Exception as e:
            logger.error("OMS reminder: overdue notices failed: %s", e, exc_info=True)
            results["errors"].append(f"overdue: {e}")

        try:
            results["escalations_sent"] = await self._process_escalations(db)
        except Exception as e:
            logger.error("OMS reminder: escalations failed: %s", e, exc_info=True)
            results["errors"].append(f"escalation: {e}")

        # Weekly compliance report — runs only on Mondays
        if date.today().weekday() == 0:  # Monday
            try:
                results["weekly_reports_sent"] = await self._send_weekly_compliance_report(db)
            except Exception as e:
                logger.error("OMS reminder: weekly report failed: %s", e, exc_info=True)
                results["errors"].append(f"weekly_report: {e}")

        logger.info("OMS reminder check complete: %s", results)
        return results

    # ------------------------------------------------------------------
    # Tier 1: J-15 — Reminder to company owners
    # ------------------------------------------------------------------

    async def _process_upcoming_reminders(self, db) -> int:
        """Send reminders for obligations due within REMINDER_BEFORE_DUE days.

        Only obligations in 'pending' status that haven't been reminded yet.
        SELECT first, send email, then UPDATE only successfully sent IDs.
        """
        target_date = date.today() + timedelta(days=REMINDER_BEFORE_DUE)

        # Step 1: SELECT candidates (no mutation yet)
        rows = await db.fetch("""
            SELECT
                lo.id, lo.fee_type, lo.amount, lo.due_date,
                co.legal_name as company_name, co.nif as company_nif,
                cl.id as license_id, cl.fiscal_year
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            JOIN companies co ON co.id = cl.company_id
            WHERE lo.status = 'pending'
              AND lo.due_date <= $1
              AND lo.reminder_sent_at IS NULL
            ORDER BY lo.due_date ASC, lo.amount DESC
            LIMIT 500
        """, target_date)

        if not rows:
            return 0

        # Step 2: Group by company, send emails
        company_obligations: Dict[str, List[Dict]] = {}
        for r in rows:
            key = r["company_name"] or "unknown"
            company_obligations.setdefault(key, []).append(dict(r))

        sent_ids: List = []
        sent = 0
        for company_name, obligations in company_obligations.items():
            try:
                license_id = obligations[0]["license_id"]
                owner_email = await self._get_company_owner_email(db, license_id)
                if not owner_email:
                    continue

                total_amount = sum(o["amount"] for o in obligations)
                subject = (
                    f"Recordatorio: {len(obligations)} obligaciones fiscales "
                    f"próximas a vencer — {company_name}"
                )
                html = self._build_reminder_html(
                    company_name, obligations, total_amount, "upcoming"
                )
                success = await self._send_email(owner_email, subject, html)
                if success:
                    sent += 1
                    sent_ids.extend(o["id"] for o in obligations)
            except Exception as e:
                logger.warning("Reminder email failed for %s: %s", company_name, e)

        # Step 3: Mark ONLY successfully sent obligations
        if sent_ids:
            await db.execute("""
                UPDATE license_obligations
                SET reminder_sent_at = NOW()
                WHERE id = ANY($1::uuid[])
            """, sent_ids)

            # Log events (batch)
            import json
            event_data = json.dumps({"tier": "upcoming", "days_before": REMINDER_BEFORE_DUE})
            for r in rows:
                if r["id"] in sent_ids:
                    await db.execute("""
                        INSERT INTO license_compliance_events
                            (license_id, obligation_id, event_type, event_data, created_at)
                        VALUES ($1, $2, 'reminder_sent', $3::jsonb, NOW())
                    """, r["license_id"], r["id"], event_data)

        return sent

    # ------------------------------------------------------------------
    # Tier 2: J+1 — Overdue notice to company + agent
    # ------------------------------------------------------------------

    async def _process_overdue_notices(self, db) -> int:
        """Send overdue notices for obligations past due_date by OVERDUE_NOTICE_AFTER days.

        Only obligations in 'overdue' status with overdue_notice_sent_at IS NULL.
        Uses dedicated column instead of event table scan.
        """
        cutoff = date.today() - timedelta(days=OVERDUE_NOTICE_AFTER)

        rows = await db.fetch("""
            SELECT
                lo.id, lo.fee_type, lo.amount, lo.penalty_amount,
                lo.due_date, lo.ministry_id, lo.license_id,
                co.legal_name as company_name, co.nif as company_nif,
                cl.fiscal_year,
                m.name_es as ministry_name
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            JOIN companies co ON co.id = cl.company_id
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            WHERE lo.status = 'overdue'
              AND lo.due_date <= $1
              AND lo.overdue_notice_sent_at IS NULL
            ORDER BY lo.amount DESC
            LIMIT 500
        """, cutoff)

        if not rows:
            return 0

        # Group by ministry for agent notifications
        by_ministry: Dict[Optional[int], List[Dict]] = {}
        for r in rows:
            by_ministry.setdefault(r["ministry_id"], []).append(dict(r))

        sent = 0

        # Notify company owners (consolidated per company)
        company_map: Dict[str, List[Dict]] = {}
        for r in rows:
            company_map.setdefault(r["company_name"] or "unknown", []).append(dict(r))

        for company_name, obligations in company_map.items():
            try:
                owner_email = await self._get_company_owner_email(
                    db, obligations[0]["license_id"]
                )
                if not owner_email:
                    continue
                total = sum(o["amount"] + (o["penalty_amount"] or 0) for o in obligations)
                subject = (
                    f"[URGENTE] {len(obligations)} obligaciones vencidas — {company_name}"
                )
                html = self._build_reminder_html(
                    company_name, obligations, total, "overdue"
                )
                await self._send_email(owner_email, subject, html)
                sent += 1
            except Exception as e:
                logger.warning("Overdue notice to %s failed: %s", company_name, e)

        # Notify agents (consolidated per ministry)
        for ministry_id, obligations in by_ministry.items():
            try:
                agent_emails = await self._get_ministry_agent_emails(db, ministry_id)
                if not agent_emails:
                    continue
                total = sum(o["amount"] for o in obligations)
                subject = (
                    f"OMS: {len(obligations)} obligaciones vencidas en tu ministerio"
                )
                html = self._build_agent_overdue_html(obligations, total)
                for email in agent_emails:
                    await self._send_email(email, subject, html)
                    sent += 1
            except Exception as e:
                logger.warning("Agent overdue notice failed (ministry %s): %s", ministry_id, e)

        # Mark sent + log events
        all_ids = [r["id"] for r in rows]
        if all_ids:
            await db.execute("""
                UPDATE license_obligations
                SET overdue_notice_sent_at = NOW()
                WHERE id = ANY($1::uuid[])
            """, all_ids)

            import json
            event_data = json.dumps({"tier": "overdue_notice"})
            for r in rows:
                await db.execute("""
                    INSERT INTO license_compliance_events
                        (license_id, obligation_id, event_type, event_data, created_at)
                    VALUES ($1, $2, 'reminder_sent', $3::jsonb, NOW())
                """, r["license_id"], r["id"], event_data)

        return sent

    # ------------------------------------------------------------------
    # Tier 3: J+30 — Escalation to supervisors
    # ------------------------------------------------------------------

    async def _process_escalations(self, db) -> int:
        """Escalate obligations overdue by ESCALATION_AFTER days to supervisors.

        Uses dedicated escalation_sent_at column for idempotency.
        """
        cutoff = date.today() - timedelta(days=ESCALATION_AFTER)

        rows = await db.fetch("""
            SELECT
                lo.id, lo.fee_type, lo.amount, lo.penalty_amount,
                lo.due_date, lo.ministry_id, lo.license_id,
                co.legal_name as company_name, co.nif,
                cl.fiscal_year,
                m.name_es as ministry_name
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            JOIN companies co ON co.id = cl.company_id
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            WHERE lo.status = 'overdue'
              AND lo.due_date <= $1
              AND lo.escalation_sent_at IS NULL
            ORDER BY lo.amount DESC
            LIMIT 500
        """, cutoff)

        if not rows:
            return 0

        # Group by ministry for supervisor email
        by_ministry: Dict[Optional[int], List[Dict]] = {}
        for r in rows:
            by_ministry.setdefault(r["ministry_id"], []).append(dict(r))

        sent = 0
        for ministry_id, obligations in by_ministry.items():
            try:
                sup_emails = await self._get_supervisor_emails(db, ministry_id)
                if not sup_emails:
                    continue
                total = sum(o["amount"] + (o["penalty_amount"] or 0) for o in obligations)
                ministry_name = obligations[0].get("ministry_name", "—")
                subject = (
                    f"[ESCALATION] {len(obligations)} obligaciones >30 días vencidas "
                    f"— {ministry_name}"
                )
                html = self._build_escalation_html(
                    obligations, total, ministry_name
                )
                for email in sup_emails:
                    await self._send_email(email, subject, html)
                    sent += 1
            except Exception as e:
                logger.warning("Escalation failed (ministry %s): %s", ministry_id, e)

        # Mark sent + log events
        all_ids = [r["id"] for r in rows]
        if all_ids:
            await db.execute("""
                UPDATE license_obligations
                SET escalation_sent_at = NOW()
                WHERE id = ANY($1::uuid[])
            """, all_ids)

            import json
            event_data = json.dumps({"tier": "escalation"})
            for r in rows:
                await db.execute("""
                    INSERT INTO license_compliance_events
                        (license_id, obligation_id, event_type, event_data, created_at)
                    VALUES ($1, $2, 'reminder_sent', $3::jsonb, NOW())
            """, r["license_id"], r["id"])

        return sent

    # ------------------------------------------------------------------
    # Helper: email senders
    # ------------------------------------------------------------------

    async def _send_email(self, recipient: str, subject: str, html: str) -> bool:
        """Async wrapper for sync CommunicationService."""
        comm = self._get_comm_service()
        if not comm:
            logger.warning("CommunicationService unavailable, skipping email to %s", recipient)
            return False
        try:
            from app.modules.communications.models.communication import CommunicationType
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: comm.send_communication(
                    channel=CommunicationType.EMAIL,
                    recipient=recipient,
                    subject=subject,
                    content=html,
                ),
            )
        except Exception as e:
            logger.error("Email send failed to %s: %s", recipient, e)
            return False

    # ------------------------------------------------------------------
    # Helper: recipient resolution
    # ------------------------------------------------------------------

    async def _get_company_owner_email(self, db, license_id) -> Optional[str]:
        """Get the company owner's email for a license."""
        row = await db.fetchrow("""
            SELECT u.email
            FROM commercial_licenses cl
            JOIN companies co ON co.id = cl.company_id
            JOIN user_company_roles ucr ON ucr.company_id = co.id
                AND ucr.role = 'company_owner'
            JOIN users u ON u.id = ucr.user_id AND u.status = 'active'
            WHERE cl.id = $1
            LIMIT 1
        """, license_id)
        return row["email"] if row else None

    async def _get_ministry_agent_emails(self, db, ministry_id: Optional[int]) -> List[str]:
        """Get active agent emails for a ministry."""
        if ministry_id is None:
            return []
        rows = await db.fetch("""
            SELECT DISTINCT u.email
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id AND u.status = 'active'
            WHERE ap.ministry_id = $1
              AND ap.is_active = true
              AND ap.is_supervisor = false
        """, ministry_id)
        return [r["email"] for r in rows if r["email"]]

    async def _get_supervisor_emails(self, db, ministry_id: Optional[int]) -> List[str]:
        """Get supervisor emails for a ministry."""
        if ministry_id is None:
            return []
        rows = await db.fetch("""
            SELECT DISTINCT u.email
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id AND u.status = 'active'
            WHERE ap.ministry_id = $1
              AND ap.is_active = true
              AND ap.is_supervisor = true
        """, ministry_id)
        return [r["email"] for r in rows if r["email"]]

    # ------------------------------------------------------------------
    # Helper: HTML builders
    # ------------------------------------------------------------------

    def _build_reminder_html(
        self, company_name: str, obligations: List[Dict],
        total: float, tier: str,
    ) -> str:
        """Build HTML email for company reminders (upcoming or overdue)."""
        is_overdue = tier == "overdue"
        color = "#dc2626" if is_overdue else "#d97706"
        title = "Obligaciones Vencidas" if is_overdue else "Recordatorio de Obligaciones"

        rows_html = ""
        for o in obligations:
            penalty = o.get("penalty_amount") or 0
            penalty_cell = f"<td style='color:#dc2626'>{penalty:,.0f} XAF</td>" if penalty else "<td>—</td>"
            rows_html += f"""
            <tr>
                <td>{o['fee_type']}</td>
                <td style='text-align:right'>{o['amount']:,.0f} XAF</td>
                {penalty_cell}
                <td>{o['due_date']}</td>
            </tr>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
            <div style="background:{color};color:white;padding:16px 24px;border-radius:8px 8px 0 0">
                <h2 style="margin:0">{title}</h2>
                <p style="margin:4px 0 0;opacity:0.9">{company_name}</p>
            </div>
            <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 8px 8px">
                <p>Estimado contribuyente,</p>
                <p>{'Sus obligaciones fiscales están vencidas.' if is_overdue else 'Le recordamos que las siguientes obligaciones están próximas a vencer.'}</p>
                <table style="width:100%;border-collapse:collapse;margin:16px 0" cellpadding="8">
                    <thead>
                        <tr style="background:#f3f4f6">
                            <th style="text-align:left">Tipo</th>
                            <th style="text-align:right">Monto</th>
                            <th>Penalidad</th>
                            <th>Vencimiento</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                    <tfoot>
                        <tr style="font-weight:bold;border-top:2px solid #d1d5db">
                            <td>Total</td>
                            <td style="text-align:right">{total:,.0f} XAF</td>
                            <td colspan="2"></td>
                        </tr>
                    </tfoot>
                </table>
                <p>Por favor, regularice su situación fiscal lo antes posible.</p>
                <p style="color:#6b7280;font-size:12px">
                    Plataforma Facil — República de Guinea Ecuatorial
                </p>
            </div>
        </div>"""

    def _build_agent_overdue_html(self, obligations: List[Dict], total: float) -> str:
        """Build HTML email for agent overdue notification."""
        rows_html = ""
        for o in obligations:
            rows_html += f"""
            <tr>
                <td>{o.get('company_name', '—')}</td>
                <td>{o.get('company_nif') or '—'}</td>
                <td>{o['fee_type']}</td>
                <td style='text-align:right'>{o['amount']:,.0f} XAF</td>
                <td>{o['due_date']}</td>
            </tr>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto">
            <h2 style="color:#dc2626">OMS — Obligaciones Vencidas</h2>
            <p>{len(obligations)} obligaciones vencidas requieren atención en tu cola.</p>
            <table style="width:100%;border-collapse:collapse;font-size:13px" cellpadding="6" border="1" bordercolor="#e5e7eb">
                <thead style="background:#fef2f2">
                    <tr><th>Empresa</th><th>NIF</th><th>Tipo</th><th>Monto</th><th>Vencimiento</th></tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
            <p style="font-weight:bold">Total: {total:,.0f} XAF</p>
        </div>"""

    def _build_escalation_html(
        self, obligations: List[Dict], total: float, ministry_name: str,
    ) -> str:
        """Build HTML email for supervisor escalation."""
        rows_html = ""
        for o in obligations:
            days_late = (date.today() - o["due_date"]).days if o.get("due_date") else 0
            rows_html += f"""
            <tr>
                <td>{o.get('company_name', '—')}</td>
                <td>{o['fee_type']}</td>
                <td style='text-align:right'>{o['amount']:,.0f} XAF</td>
                <td style='text-align:right;color:#dc2626'>{(o.get('penalty_amount') or 0):,.0f}</td>
                <td style='text-align:center;font-weight:bold;color:#dc2626'>{days_late}j</td>
            </tr>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto">
            <div style="background:#7f1d1d;color:white;padding:16px 24px;border-radius:8px 8px 0 0">
                <h2 style="margin:0">⚠ ESCALATION — {ministry_name}</h2>
                <p style="margin:4px 0 0;opacity:0.9">
                    {len(obligations)} obligaciones vencidas >30 días
                </p>
            </div>
            <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 8px 8px">
                <table style="width:100%;border-collapse:collapse;font-size:13px" cellpadding="6" border="1" bordercolor="#e5e7eb">
                    <thead style="background:#fef2f2">
                        <tr><th>Empresa</th><th>Tipo</th><th>Monto</th><th>Penalidad</th><th>Días</th></tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
                <p style="font-weight:bold;font-size:16px;color:#dc2626;margin-top:16px">
                    Total: {total:,.0f} XAF
                </p>
                <p>Acción requerida: verificar el estado de cobro y contactar empresas.</p>
            </div>
        </div>"""

    # ------------------------------------------------------------------
    # Weekly compliance report — Runs on Mondays
    # ------------------------------------------------------------------

    async def _send_weekly_compliance_report(self, db) -> int:
        """Send weekly compliance summary to all ministry supervisors.

        Aggregates per ministry: total obligations, paid, overdue, recovery %,
        top 5 debtors, penalties accumulated. One email per supervisor.
        """
        current_year = date.today().year

        # Get per-ministry stats in a single query
        rows = await db.fetch("""
            SELECT
                lo.ministry_id,
                m.name_es as ministry_name,
                COUNT(*) as total_obligations,
                COUNT(*) FILTER (
                    WHERE lo.status IN ('paid', 'completed', 'processing')
                ) as paid,
                COUNT(*) FILTER (WHERE lo.status = 'overdue') as overdue,
                COUNT(*) FILTER (
                    WHERE lo.status IN ('pending', 'selected', 'payment_pending')
                ) as pending,
                COALESCE(SUM(lo.amount), 0) as total_amount,
                COALESCE(SUM(lo.amount) FILTER (
                    WHERE lo.status IN ('paid', 'completed', 'processing')
                ), 0) as paid_amount,
                COALESCE(SUM(lo.amount) FILTER (
                    WHERE lo.status = 'overdue'
                ), 0) as overdue_amount,
                COALESCE(SUM(lo.penalty_amount), 0) as total_penalties,
                -- Completed this week
                COUNT(*) FILTER (
                    WHERE lo.status = 'completed'
                    AND lo.updated_at >= CURRENT_DATE - INTERVAL '7 days'
                ) as completed_this_week
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            WHERE cl.fiscal_year = $1
            GROUP BY lo.ministry_id, m.name_es
            ORDER BY overdue_amount DESC
        """, current_year)

        if not rows:
            return 0

        sent = 0
        for r in rows:
            ministry_id = r["ministry_id"]
            if not ministry_id:
                continue

            sup_emails = await self._get_supervisor_emails(db, ministry_id)
            if not sup_emails:
                continue

            total = float(r["total_amount"]) if r["total_amount"] else 0
            paid = float(r["paid_amount"]) if r["paid_amount"] else 0
            recovery = round((paid / total) * 100) if total > 0 else 0

            # Top 5 debtors for this ministry
            debtors = await db.fetch("""
                SELECT
                    co.legal_name as company_name,
                    co.nif,
                    SUM(lo.amount) as debt_amount,
                    COUNT(*) as overdue_count
                FROM license_obligations lo
                JOIN commercial_licenses cl ON cl.id = lo.license_id
                JOIN companies co ON co.id = cl.company_id
                WHERE lo.status = 'overdue'
                  AND lo.ministry_id = $1
                  AND cl.fiscal_year = $2
                GROUP BY co.legal_name, co.nif
                ORDER BY debt_amount DESC
                LIMIT 5
            """, ministry_id, current_year)

            ministry_name = r["ministry_name"] or f"Ministry #{ministry_id}"
            subject = (
                f"Informe Semanal OMS — {ministry_name} "
                f"({recovery}% recuperación)"
            )
            html = self._build_weekly_report_html(dict(r), debtors, recovery)

            for email in sup_emails:
                try:
                    success = await self._send_email(email, subject, html)
                    if success:
                        sent += 1
                except Exception as e:
                    logger.warning("Weekly report to %s failed: %s", email, e)

        return sent

    def _build_weekly_report_html(
        self, stats: Dict, debtors: List, recovery: int,
    ) -> str:
        """Build HTML for weekly compliance report."""
        ministry_name = stats.get("ministry_name", "—")
        recovery_color = (
            "#22c55e" if recovery >= 70
            else "#eab308" if recovery >= 40
            else "#ef4444"
        )

        debtors_rows = ""
        for d in debtors:
            debtors_rows += f"""
            <tr>
                <td style="padding:6px 8px">{d['company_name']}</td>
                <td style="padding:6px 8px;font-family:monospace">{d['nif'] or '—'}</td>
                <td style="padding:6px 8px;text-align:right;color:#dc2626;font-weight:bold">
                    {float(d['debt_amount']):,.0f} XAF
                </td>
                <td style="padding:6px 8px;text-align:center">{d['overdue_count']}</td>
            </tr>"""

        debtors_section = ""
        if debtors:
            debtors_section = f"""
            <h3 style="margin-top:20px;color:#991b1b">Top 5 deudores</h3>
            <table style="width:100%;border-collapse:collapse;font-size:13px" border="1" bordercolor="#e5e7eb" cellpadding="0">
                <thead style="background:#fef2f2">
                    <tr>
                        <th style="padding:6px 8px;text-align:left">Empresa</th>
                        <th style="padding:6px 8px;text-align:left">NIF</th>
                        <th style="padding:6px 8px;text-align:right">Deuda</th>
                        <th style="padding:6px 8px;text-align:center">Oblig.</th>
                    </tr>
                </thead>
                <tbody>{debtors_rows}</tbody>
            </table>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:650px;margin:0 auto">
            <div style="background:#1e3a5f;color:white;padding:16px 24px;border-radius:8px 8px 0 0">
                <h2 style="margin:0">Informe Semanal OMS</h2>
                <p style="margin:4px 0 0;opacity:0.8">{ministry_name} — Semana del {date.today().strftime('%d/%m/%Y')}</p>
            </div>
            <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 8px 8px">

                <!-- KPIs -->
                <div style="display:flex;gap:12px;margin-bottom:20px">
                    <div style="flex:1;background:#f0fdf4;padding:12px;border-radius:6px;text-align:center">
                        <div style="font-size:24px;font-weight:bold;color:{recovery_color}">{recovery}%</div>
                        <div style="font-size:11px;color:#6b7280">Recuperación</div>
                    </div>
                    <div style="flex:1;background:#f0f9ff;padding:12px;border-radius:6px;text-align:center">
                        <div style="font-size:24px;font-weight:bold">{stats['total_obligations']}</div>
                        <div style="font-size:11px;color:#6b7280">Obligaciones</div>
                    </div>
                    <div style="flex:1;background:#fef2f2;padding:12px;border-radius:6px;text-align:center">
                        <div style="font-size:24px;font-weight:bold;color:#dc2626">{stats['overdue']}</div>
                        <div style="font-size:11px;color:#6b7280">Vencidas</div>
                    </div>
                    <div style="flex:1;background:#fffbeb;padding:12px;border-radius:6px;text-align:center">
                        <div style="font-size:24px;font-weight:bold;color:#d97706">{stats['completed_this_week']}</div>
                        <div style="font-size:11px;color:#6b7280">Completadas esta semana</div>
                    </div>
                </div>

                <!-- Summary -->
                <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px" cellpadding="8">
                    <tr style="background:#f3f4f6">
                        <td>Total</td>
                        <td style="text-align:right;font-weight:bold">{float(stats['total_amount']):,.0f} XAF</td>
                    </tr>
                    <tr>
                        <td>Cobrado</td>
                        <td style="text-align:right;color:#16a34a;font-weight:bold">{float(stats['paid_amount']):,.0f} XAF</td>
                    </tr>
                    <tr style="background:#f3f4f6">
                        <td>Vencido</td>
                        <td style="text-align:right;color:#dc2626;font-weight:bold">{float(stats['overdue_amount']):,.0f} XAF</td>
                    </tr>
                    <tr>
                        <td>Penalidades acumuladas</td>
                        <td style="text-align:right;color:#d97706">{float(stats['total_penalties']):,.0f} XAF</td>
                    </tr>
                </table>

                {debtors_section}

                <p style="margin-top:20px;color:#6b7280;font-size:12px">
                    Plataforma Facil — Generado automáticamente cada lunes
                </p>
            </div>
        </div>"""


# Singleton
oms_reminder_service = OmsReminderService()
