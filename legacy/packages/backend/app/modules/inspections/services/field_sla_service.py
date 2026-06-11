"""Field SLA Service — Automated checks for field inspection operations.

Pattern: Same as PaymentSLAService.
- Batch UPDATE...WHERE...RETURNING for O(1) idempotent queries (cash checks)
- Redis dedup keys for SELECT-based checks (MED, inactive agents)
- Consolidated emails per supervisor (1 email, not N)
- CommunicationService via run_in_executor (sync service)
- All thresholds from system_rules (dynamic, no hardcoded values)
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html import escape as html_escape
from typing import Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


async def _dedup_check(key: str, ttl_seconds: int = 86400) -> bool:
    """Redis-based deduplication for idempotent scheduler checks.

    Returns True if this key has NOT been seen within TTL (proceed with check).
    Returns False if already processed (skip to avoid duplicate emails).

    Uses get-then-set pattern with HybridCache. On multi-instance, a small
    race window exists but is acceptable (worst case: 1 duplicate email).
    Falls back to True (allow) if cache unavailable.
    """
    try:
        from app.core.cache import get_cache
        cache = get_cache()
        existing = await cache.get(key)
        if existing is not None:
            return False  # Already processed
        await cache.set(key, "1", ttl=ttl_seconds)
        return True  # First time — proceed
    except Exception as e:
        logger.warning(f"Dedup check failed for {key}, allowing execution: {e}")
        return True  # Fail-open: allow execution if cache is down


class FieldSLAService:
    """Automated SLA checks for field inspection operations."""

    def __init__(self):
        from app.modules.communications.services.communication_service import CommunicationService
        self.communication_service = CommunicationService()

    async def run_all_checks(self, db) -> Dict:
        """Main entry point — run all 4 SLA checks.

        Returns dict with counts for each check type.
        Called by InternalScheduler._field_sla_check().
        """
        results = {
            "cash_warnings_sent": 0,
            "cash_escalations_sent": 0,
            "med_expired_alerts": 0,
            "inactive_agent_alerts": 0,
            "stale_zone_count": 0,
            "errors": [],
        }

        # Each check is independent — one failure doesn't block others
        for check_name, check_fn in [
            ("cash_warnings", self._check_unreconciled_cash),
            ("cash_escalations", self._check_cash_escalations),
            ("med_expired", self._check_expired_med),
            ("inactive_agents", self._check_inactive_agents),
        ]:
            try:
                check_result = await check_fn(db)
                results.update(check_result)
            except Exception as e:
                logger.error(f"Field SLA check '{check_name}' failed: {e}")
                results["errors"].append(f"{check_name}: {str(e)}")

        return results

    # =========================================================================
    # CHECK 1: Cash >48h warning — unreconciled field collections
    # =========================================================================

    async def _check_unreconciled_cash(self, db) -> Dict:
        """Find field cash collections that exceeded SLA and haven't been warned yet.

        Batch UPDATE...WHERE...RETURNING: mark field_sla_warning_sent = true
        and return all rows in one atomic query. Group by entity, send
        consolidated email per supervisor.
        """
        warning_hours = await self._get_system_rule_int(
            db, "FIELD_CASH_SLA_WARNING_HOURS", 48
        )
        threshold = datetime.now(timezone.utc) - timedelta(hours=warning_hours)

        warned_rows = await db.fetch("""
            UPDATE service_payments sp
            SET field_sla_warning_sent = true
            FROM (
                SELECT sp2.id, sp2.payment_reference, sp2.total_amount, sp2.created_at,
                       fi.entity_id, fi.company_id,
                       u.full_name AS agent_name,
                       c.legal_name AS company_name,
                       COALESCE(c.nif, c.registration_number) AS company_nif
                FROM service_payments sp2
                JOIN field_inspections fi ON fi.id = sp2.field_inspection_id
                JOIN users u ON u.id = sp2.collected_by
                JOIN companies c ON c.id = fi.company_id
                WHERE sp2.collection_type = 'field'
                  AND sp2.workflow_status = 'field_collected'
                  AND sp2.field_sla_warning_sent = false
                  AND sp2.created_at < $1
            ) sub
            WHERE sp.id = sub.id
            RETURNING sub.id, sub.payment_reference, sub.total_amount, sub.created_at,
                      sub.entity_id, sub.company_id,
                      sub.agent_name, sub.company_name, sub.company_nif
        """, threshold)

        if not warned_rows:
            logger.info("Field SLA cash warning: no payments to warn")
            return {"cash_warnings_sent": 0}

        logger.info(
            f"Field SLA cash warning: {len(warned_rows)} payments marked for warning"
        )

        # Group by entity_id
        by_entity: Dict[UUID, list] = {}
        for row in warned_rows:
            eid = row["entity_id"]
            by_entity.setdefault(eid, []).append(row)

        emails_sent = 0
        for entity_id, payments in by_entity.items():
            supervisors = await self._get_entity_supervisors(db, entity_id)
            if not supervisors:
                logger.warning(
                    f"Field SLA cash warning: no supervisors for entity {entity_id}"
                )
                continue

            entity_code = supervisors[0].get("entity_code", "N/A")

            # Build table rows
            rows_html = ""
            for p in payments:
                created = (
                    p["created_at"].strftime("%d/%m/%Y %H:%M")
                    if p["created_at"]
                    else "-"
                )
                hours_elapsed = self._hours_since(p["created_at"])
                rows_html += f"""
                <tr>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(p['payment_reference'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(p['agent_name'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(p['company_name'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(p['company_nif'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;text-align:right;">{p['total_amount']:,.0f} XAF</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{created}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;color:#dc2626;font-weight:bold;">{hours_elapsed}h</td>
                </tr>"""

            subject = (
                f"[SLA] {len(payments)} cobro(s) de campo pendiente(s) "
                f">{warning_hours}h - {html_escape(entity_code)}"
            )
            html_body = self._build_table_email(
                title="Alerta SLA - Cobros de Campo sin Reconciliar",
                subtitle=(
                    f"{len(payments)} cobro(s) de campo pendiente(s) de reconciliacion "
                    f"desde hace mas de {warning_hours} horas."
                ),
                color="#f59e0b",
                headers=["Referencia", "Agente", "Empresa", "NIF", "Monto", "Fecha Cobro", "Espera"],
                rows_html=rows_html,
                action_text="Reconciliar estos cobros en el panel de supervision.",
            )

            for sup in supervisors:
                sent = await self._send_email_async(sup["email"], subject, html_body)
                if sent:
                    emails_sent += 1

        return {"cash_warnings_sent": emails_sent}

    # =========================================================================
    # CHECK 2: Cash >5 days escalation
    # =========================================================================

    async def _check_cash_escalations(self, db) -> Dict:
        """Find field cash collections warned but still unreconciled after escalation threshold.

        Same batch UPDATE pattern — mark field_sla_escalated = true. Only
        processes rows where field_sla_warning_sent = true (already warned).
        """
        escalation_days = await self._get_system_rule_int(
            db, "FIELD_CASH_SLA_ESCALATION_DAYS", 5
        )
        threshold = datetime.now(timezone.utc) - timedelta(days=escalation_days)

        escalated_rows = await db.fetch("""
            UPDATE service_payments sp
            SET field_sla_escalated = true
            FROM (
                SELECT sp2.id, sp2.payment_reference, sp2.total_amount, sp2.created_at,
                       fi.entity_id,
                       u.full_name AS agent_name,
                       c.legal_name AS company_name,
                       COALESCE(c.nif, c.registration_number) AS company_nif
                FROM service_payments sp2
                JOIN field_inspections fi ON fi.id = sp2.field_inspection_id
                JOIN users u ON u.id = sp2.collected_by
                JOIN companies c ON c.id = fi.company_id
                WHERE sp2.collection_type = 'field'
                  AND sp2.workflow_status = 'field_collected'
                  AND sp2.field_sla_warning_sent = true
                  AND sp2.field_sla_escalated = false
                  AND sp2.created_at < $1
            ) sub
            WHERE sp.id = sub.id
            RETURNING sub.id, sub.payment_reference, sub.total_amount, sub.created_at,
                      sub.entity_id, sub.agent_name, sub.company_name, sub.company_nif
        """, threshold)

        if not escalated_rows:
            logger.info("Field SLA cash escalation: no payments to escalate")
            return {"cash_escalations_sent": 0}

        logger.info(
            f"Field SLA cash escalation: {len(escalated_rows)} payments escalated"
        )

        # Group by entity_id
        by_entity: Dict[UUID, list] = {}
        for row in escalated_rows:
            eid = row["entity_id"]
            by_entity.setdefault(eid, []).append(row)

        emails_sent = 0
        for entity_id, payments in by_entity.items():
            supervisors = await self._get_entity_supervisors(db, entity_id)
            if not supervisors:
                logger.warning(
                    f"Field SLA cash escalation: no supervisors for entity {entity_id}"
                )
                continue

            entity_code = supervisors[0].get("entity_code", "N/A")

            rows_html = ""
            for p in payments:
                created = (
                    p["created_at"].strftime("%d/%m/%Y %H:%M")
                    if p["created_at"]
                    else "-"
                )
                days_elapsed = self._days_since(p["created_at"])
                rows_html += f"""
                <tr>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(p['payment_reference'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(p['agent_name'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(p['company_name'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(p['company_nif'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;text-align:right;">{p['total_amount']:,.0f} XAF</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{created}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;color:#dc2626;font-weight:bold;">{days_elapsed}j</td>
                </tr>"""

            subject = (
                f"[URGENTE] {len(payments)} cobro(s) de campo sin reconciliar "
                f">{escalation_days} dias - {html_escape(entity_code)}"
            )
            html_body = self._build_table_email(
                title="ESCALACION: Cobros de Campo sin Reconciliar",
                subtitle=(
                    f"{len(payments)} cobro(s) de campo sin reconciliar "
                    f"desde hace mas de {escalation_days} dias."
                ),
                color="#dc2626",
                headers=["Referencia", "Agente", "Empresa", "NIF", "Monto", "Fecha Cobro", "Espera"],
                rows_html=rows_html,
                action_text=(
                    "Estos cobros requieren atencion inmediata del supervisor. "
                    "Reconciliar en el panel de supervision o contactar al agente responsable."
                ),
            )

            for sup in supervisors:
                sent = await self._send_email_async(sup["email"], subject, html_body)
                if sent:
                    emails_sent += 1

        return {"cash_escalations_sent": emails_sent}

    # =========================================================================
    # CHECK 3: MED deadline passed — mise en demeure expired
    # =========================================================================

    async def _check_expired_med(self, db) -> Dict:
        """Find inspections where mise en demeure deadline has passed.

        This is a SELECT (not UPDATE) because we don't auto-change inspection status —
        the supervisor decides whether to propose a seal. Idempotency is achieved by
        Redis dedup key per inspection ID (TTL 7 days — won't re-alert for same MED).
        """
        grace_days = await self._get_system_rule_int(
            db, "FIELD_MED_EXPIRY_GRACE_DAYS", 0
        )
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=grace_days)

        expired_rows = await db.fetch("""
            SELECT fi.id, fi.entity_id, fi.mise_en_demeure_deadline,
                   fi.unpaid_obligations_amount,
                   c.legal_name AS company_name,
                   COALESCE(c.nif, c.registration_number) AS company_nif,
                   u.full_name AS agent_name
            FROM field_inspections fi
            JOIN companies c ON c.id = fi.company_id
            JOIN users u ON u.id = fi.agent_id
            WHERE fi.mise_en_demeure_issued = true
              AND fi.status = 'mise_en_demeure'
              AND fi.mise_en_demeure_deadline < $1
        """, threshold)

        # Filter out already-alerted MEDs via Redis dedup (7-day TTL)
        new_expired = []
        for row in expired_rows:
            dedup_key = f"sla:med_expired:{row['id']}"
            if await _dedup_check(dedup_key, ttl_seconds=604800):  # 7 days
                new_expired.append(row)
        expired_rows = new_expired

        if not expired_rows:
            logger.info("Field SLA MED expiry: no expired MEDs in window")
            return {"med_expired_alerts": 0}

        logger.info(
            f"Field SLA MED expiry: {len(expired_rows)} MEDs expired in last 24h window"
        )

        # Group by entity_id
        by_entity: Dict[UUID, list] = {}
        for row in expired_rows:
            eid = row["entity_id"]
            by_entity.setdefault(eid, []).append(row)

        emails_sent = 0
        for entity_id, inspections in by_entity.items():
            supervisors = await self._get_entity_supervisors(db, entity_id)
            if not supervisors:
                logger.warning(
                    f"Field SLA MED expiry: no supervisors for entity {entity_id}"
                )
                continue

            entity_code = supervisors[0].get("entity_code", "N/A")

            rows_html = ""
            for insp in inspections:
                deadline = (
                    insp["mise_en_demeure_deadline"].strftime("%d/%m/%Y")
                    if insp["mise_en_demeure_deadline"]
                    else "-"
                )
                amount = insp["unpaid_obligations_amount"] or Decimal("0")
                rows_html += f"""
                <tr>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(insp['company_name'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(insp['company_nif'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;text-align:right;color:#dc2626;font-weight:bold;">{amount:,.0f} XAF</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{deadline}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(insp['agent_name'] or '-'))}</td>
                </tr>"""

            subject = (
                f"[CRITICO] {len(inspections)} mise(s) en demeure expirada(s) "
                f"- {html_escape(entity_code)}"
            )
            html_body = self._build_table_email(
                title="Mise en Demeure Expirada(s)",
                subtitle=(
                    f"{len(inspections)} mise(s) en demeure han expirado sin "
                    f"regularizacion por parte de la empresa."
                ),
                color="#dc2626",
                headers=["Empresa", "NIF", "Monto Impago", "Fecha Limite", "Agente"],
                rows_html=rows_html,
                action_text=(
                    "Evaluar cada caso para iniciar procedimiento de scelle "
                    "o nueva notificacion."
                ),
            )

            for sup in supervisors:
                sent = await self._send_email_async(sup["email"], subject, html_body)
                if sent:
                    emails_sent += 1

        return {"med_expired_alerts": emails_sent}

    # =========================================================================
    # CHECK 4: Agent inactive >N working days
    # =========================================================================

    async def _check_inactive_agents(self, db) -> Dict:
        """Find agents with inspection permissions but no recent inspections.

        Identifies agents who have not performed any inspection in the last N days
        (configurable via INSPECTION_AGENT_INACTIVE_DAYS system rule, default 3).
        Results are grouped by entity and included in supervisor daily summary.
        """
        inactive_days = await self._get_system_rule_int(
            db, "INSPECTION_AGENT_INACTIVE_DAYS", 3
        )

        inactive_rows = await db.fetch("""
            SELECT ap.user_id, u.full_name AS agent_name, u.email,
                   ap.entity_id, e.code AS entity_code,
                   MAX(fi.inspection_date) AS last_inspection_date,
                   CURRENT_DATE - MAX(fi.inspection_date) AS days_since_last
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            JOIN entities e ON e.id = ap.entity_id
            LEFT JOIN field_inspections fi ON fi.agent_id = ap.user_id AND fi.status != 'cancelled'
            WHERE ap.is_active = true
              AND ap.is_supervisor = false
              AND u.status = 'active'
              AND EXISTS (
                  SELECT 1 FROM role_permissions rp
                  JOIN permissions p ON p.id = rp.permission_id
                  JOIN roles r ON r.id = rp.role_id
                  WHERE r.id = u.role_id AND p.name = 'inspection.create'
              )
            GROUP BY ap.user_id, u.full_name, u.email, ap.entity_id, e.code
            HAVING MAX(fi.inspection_date) IS NULL
               OR MAX(fi.inspection_date) < CURRENT_DATE - $1::int
        """, inactive_days)

        if not inactive_rows:
            logger.info("Field SLA inactive agents: no inactive agents found")
            return {"inactive_agent_alerts": 0, "stale_zone_count": 0}

        logger.info(
            f"Field SLA inactive agents: {len(inactive_rows)} agents inactive "
            f">{inactive_days} days"
        )

        # Group by entity_id
        by_entity: Dict[UUID, list] = {}
        for row in inactive_rows:
            eid = row["entity_id"]
            by_entity.setdefault(eid, []).append(row)

        # Also check stale zones (zones with no inspection in 30+ days)
        stale_zones = await db.fetch("""
            SELECT el.id, el.location_name, e.code AS entity_code, e.id AS entity_id,
                   MAX(fi.inspection_date) AS last_inspection_date,
                   CURRENT_DATE - MAX(fi.inspection_date) AS days_since_last
            FROM entity_locations el
            JOIN entities e ON e.id = el.entity_id
            LEFT JOIN field_inspections fi ON fi.entity_location_id = el.id
                AND fi.status != 'cancelled'
            WHERE el.is_active = true
            GROUP BY el.id, el.location_name, e.code, e.id
            HAVING MAX(fi.inspection_date) IS NULL
               OR MAX(fi.inspection_date) < CURRENT_DATE - 30
        """)
        stale_count = len(stale_zones) if stale_zones else 0

        emails_sent = 0
        for entity_id, agents in by_entity.items():
            supervisors = await self._get_entity_supervisors(db, entity_id)
            if not supervisors:
                logger.warning(
                    f"Field SLA inactive agents: no supervisors for entity {entity_id}"
                )
                continue

            entity_code = agents[0].get("entity_code", "N/A")

            # Build inactive agents table
            rows_html = ""
            for ag in agents:
                last_date = (
                    ag["last_inspection_date"].strftime("%d/%m/%Y")
                    if ag["last_inspection_date"]
                    else "Nunca"
                )
                days_since = ag["days_since_last"] if ag["days_since_last"] is not None else "-"
                rows_html += f"""
                <tr>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(ag['agent_name'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{html_escape(str(ag['email'] or '-'))}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;">{last_date}</td>
                    <td style="padding:8px;border:1px solid #e5e7eb;color:#dc2626;font-weight:bold;">{days_since}</td>
                </tr>"""

            # Build stale zones section for this entity
            entity_stale = [
                z for z in (stale_zones or []) if z["entity_id"] == entity_id
            ]
            stale_html = ""
            if entity_stale:
                stale_rows = ""
                for z in entity_stale:
                    z_last = (
                        z["last_inspection_date"].strftime("%d/%m/%Y")
                        if z["last_inspection_date"]
                        else "Nunca"
                    )
                    z_days = z["days_since_last"] if z["days_since_last"] is not None else "-"
                    stale_rows += f"""
                    <tr>
                        <td style="padding:6px;border:1px solid #e5e7eb;">{html_escape(str(z['location_name'] or '-'))}</td>
                        <td style="padding:6px;border:1px solid #e5e7eb;">{z_last}</td>
                        <td style="padding:6px;border:1px solid #e5e7eb;color:#dc2626;">{z_days} dias</td>
                    </tr>"""
                stale_html = f"""
                <div style="margin-top:20px;">
                    <h3 style="color:#dc2626;font-size:14px;">Zonas sin inspeccion reciente (>30 dias)</h3>
                    <table style="width:100%;border-collapse:collapse;font-size:13px;">
                        <thead>
                            <tr>
                                <th style="padding:6px;border:1px solid #e5e7eb;background:#fef2f2;text-align:left;">Zona</th>
                                <th style="padding:6px;border:1px solid #e5e7eb;background:#fef2f2;text-align:left;">Ultima Inspeccion</th>
                                <th style="padding:6px;border:1px solid #e5e7eb;background:#fef2f2;text-align:left;">Inactividad</th>
                            </tr>
                        </thead>
                        <tbody>{stale_rows}</tbody>
                    </table>
                </div>"""

            subject = (
                f"[INFO] {len(agents)} agente(s) inactivo(s) "
                f">{inactive_days} dias - {html_escape(entity_code)}"
            )
            html_body = self._build_table_email(
                title="Agentes de Inspeccion Inactivos",
                subtitle=(
                    f"{len(agents)} agente(s) sin actividad de inspeccion "
                    f"en los ultimos {inactive_days} dias."
                ),
                color="#2d5a03",
                headers=["Agente", "Email", "Ultima Inspeccion", "Dias Inactivo"],
                rows_html=rows_html,
                action_text=(
                    "Verificar la disponibilidad de estos agentes y reasignar "
                    "zonas si es necesario."
                ),
                extra_html=stale_html,
            )

            for sup in supervisors:
                sent = await self._send_email_async(sup["email"], subject, html_body)
                if sent:
                    emails_sent += 1

        return {
            "inactive_agent_alerts": emails_sent,
            "stale_zone_count": stale_count,
        }

    # =========================================================================
    # HELPER: Get system rule value (int)
    # =========================================================================

    @staticmethod
    async def _get_system_rule_int(db, rule_code: str, default: int) -> int:
        """Fetch a system_rules integer value by code. Falls back to default.

        rule_value is JSONB, so int() cast works since JSONB numbers are
        deserialized as Python int/float by asyncpg.
        """
        row = await db.fetchrow(
            "SELECT rule_value FROM system_rules WHERE rule_code = $1 AND is_active = true",
            rule_code,
        )
        if row and row["rule_value"] is not None:
            try:
                return int(row["rule_value"])
            except (ValueError, TypeError):
                logger.warning(
                    f"system_rules '{rule_code}' has non-integer value: "
                    f"{row['rule_value']}, using default {default}"
                )
                return default
        return default

    # =========================================================================
    # HELPER: Get entity supervisors
    # =========================================================================

    @staticmethod
    async def _get_entity_supervisors(db, entity_id: UUID) -> List[Dict]:
        """Fetch active supervisors for an entity with their email and entity code."""
        rows = await db.fetch("""
            SELECT u.email, u.full_name, e.code AS entity_code
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            JOIN entities e ON e.id = ap.entity_id
            WHERE ap.entity_id = $1
              AND ap.is_supervisor = true
              AND ap.is_active = true
              AND u.status = 'active'
        """, entity_id)
        return [dict(r) for r in rows]

    # =========================================================================
    # HELPER: Send email via CommunicationService (sync → async via executor)
    # =========================================================================

    async def _send_email_async(
        self, recipient: str, subject: str, html_body: str
    ) -> bool:
        """Send email via CommunicationService. Same pattern as PaymentSLAService."""
        try:
            from app.modules.communications.models.communication import CommunicationType

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.communication_service.send_communication(
                    channel=CommunicationType.EMAIL,
                    recipient=recipient,
                    subject=subject,
                    content=html_body,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to send field SLA email to {recipient}: {e}")
            return False

    # =========================================================================
    # HTML BUILDER: Generic table email
    # =========================================================================

    def _build_table_email(
        self,
        title: str,
        subtitle: str,
        color: str,
        headers: List[str],
        rows_html: str,
        action_text: str,
        extra_html: str = "",
    ) -> str:
        """Generic email builder that wraps table rows in a styled template.

        Same design as PaymentSLAService._wrap_agent_email.
        Colors: #2d5a03 (info/green), #f59e0b (warning/amber), #dc2626 (critical/red).
        """
        headers_html = "".join(
            f'<th style="padding:8px;border:1px solid #e5e7eb;background-color:{html_escape(color)};'
            f'color:#fff;text-align:left;">{html_escape(h)}</th>'
            for h in headers
        )
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#f5f5f5;">
    <div style="padding:20px;">
        <div style="max-width:800px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <div style="background:{html_escape(color)};padding:20px 30px;">
                <h1 style="color:#fff;margin:0;font-size:22px;">{html_escape(title)}</h1>
                <p style="color:rgba(255,255,255,0.9);margin:5px 0 0;font-size:14px;">{html_escape(subtitle)}</p>
            </div>
            <div style="padding:30px;">
                <p style="font-size:15px;color:#333;">Los siguientes elementos requieren su atencion:</p>
                <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:13px;">
                    <thead>
                        <tr>{headers_html}</tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
                {extra_html}
                <div style="background-color:#fef3cd;border:1px solid #ffc107;border-radius:4px;padding:12px 16px;margin-top:20px;">
                    <strong>Accion requerida:</strong> {html_escape(action_text)}
                </div>
            </div>
            <div style="background:#f9fafb;padding:15px 30px;border-top:1px solid #e5e7eb;text-align:center;">
                <p style="margin:0;font-size:12px;color:#6b7280;">
                    Mensaje automatico generado el {now} - Facil Platform
                </p>
            </div>
        </div>
    </div>
</body>
</html>"""

    # =========================================================================
    # UTILITY: Time calculations
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
