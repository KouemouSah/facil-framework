"""
Cron Routes for Scheduled Tasks.

Internal endpoints called by Cloud Scheduler (GCP) for:
- Appointment reminders (J-1)
- Expired hold cleanup
- SLA monitoring

Security: These endpoints should be protected by internal authentication
or called only from Cloud Scheduler with proper IAM.
"""
from fastapi import APIRouter, Depends
from datetime import date, timedelta
from html import escape as html_escape
import asyncpg
from loguru import logger

from app.database.connection import get_database
from app.core.events import EventBus, EventType
from app.config import get_settings
from app.modules.payments.services.payment_sla_service import PaymentSLAService
from app.modules.service_requests.services.escalation_sla_service import EscalationSLAService

router = APIRouter(prefix="/cron", tags=["Cron Jobs (Internal)"])

settings = get_settings()


# Centralized cron authentication (fail-closed)
from app.core.cron_auth import verify_cron_auth  # noqa: F401 — used as Depends()


@router.post(
    "/appointment-reminders",
    summary="Send appointment reminders",
    description="""
    Called daily by Cloud Scheduler to send appointment reminders.

    Sends reminders for appointments scheduled for tomorrow (J-1).
    Publishes APPOINTMENT_REMINDER events for each appointment.
    """
)
async def send_appointment_reminders(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth)
):
    """Send reminder notifications for tomorrow's appointments."""
    tomorrow = date.today() + timedelta(days=1)

    # Get all confirmed appointments for tomorrow
    appointments = await db.fetch("""
        SELECT
            sr.id as request_id,
            sr.user_id,
            sr.workflow_code,
            sr.reference,
            sr.cita_date as appointment_date,
            sr.cita_time as appointment_time,
            sr.cita_location as location,
            u.email,
            u.phone_number as phone,
            u.first_name,
            u.last_name,
            u.preferred_language
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.cita_date = $1
        AND sr.status IN ('SUBMITTED', 'UNDER_REVIEW', 'DOSSIER_VALIDE', 'PAID')
        AND sr.appointment_status IS NULL  -- Not yet arrived or no-show
        AND sr.reminder_sent_at IS NULL    -- Reminder not already sent
    """, tomorrow)

    sent_count = 0
    failed_count = 0

    for appt in appointments:
        try:
            # Publish APPOINTMENT_REMINDER event
            EventBus.publish_nowait(
                EventType.APPOINTMENT_REMINDER,
                {
                    "request_id": str(appt["request_id"]),
                    "user_id": str(appt["user_id"]),
                    "user_email": appt["email"],
                    "user_phone": appt["phone"],
                    "user_name": f"{appt['first_name'] or ''} {appt['last_name'] or ''}".strip(),
                    "preferred_language": appt.get("preferred_language", "es"),
                    "workflow_code": appt["workflow_code"],
                    "service": appt["workflow_code"],  # For SMS template compatibility
                    "reference": appt["reference"],
                    "appointment_date": str(appt["appointment_date"]) if appt.get("appointment_date") else None,
                    "date": str(appt["appointment_date"]) if appt.get("appointment_date") else None,  # SMS template
                    "appointment_time": str(appt["appointment_time"]) if appt.get("appointment_time") else None,
                    "time": str(appt["appointment_time"]) if appt.get("appointment_time") else None,  # SMS template
                    "location": appt.get("location"),
                }
            )

            # Mark reminder as sent
            await db.execute("""
                UPDATE service_requests
                SET reminder_sent_at = NOW()
                WHERE id = $1
            """, appt["request_id"])

            sent_count += 1

        except Exception as e:
            logger.error(f"Failed to send reminder for request {appt['request_id']}: {e}")
            failed_count += 1

    logger.info(f"Appointment reminders: {sent_count} sent, {failed_count} failed")

    return {
        "message": "Appointment reminders processed",
        "date": str(tomorrow),
        "total_appointments": len(appointments),
        "sent": sent_count,
        "failed": failed_count
    }


@router.post(
    "/cleanup-expired-holds",
    summary="Cleanup expired appointment holds",
    description="""
    Called periodically to release expired appointment holds.

    Holds that have expired (past 15 min without payment) are released
    to make slots available for other users.
    """
)
async def cleanup_expired_holds(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth)
):
    """Release expired appointment holds."""
    result = await db.execute("""
        UPDATE appointment_holds
        SET status = 'expired',
            released_at = NOW()
        WHERE status = 'held'
        AND expires_at < NOW()
    """)

    # Extract count from result string
    count = 0
    if result:
        try:
            count = int(result.split()[-1])
        except (ValueError, IndexError):
            pass

    logger.info(f"Expired appointment holds released: {count}")

    return {
        "message": "Expired holds cleaned up",
        "released_count": count
    }


@router.post(
    "/cleanup-abandoned-requests",
    summary="Cleanup abandoned DRAFT service requests (bundle excluded)",
    description="""
    Called hourly by Cloud Scheduler to delete abandoned DRAFT service requests.

    **Always EXCLUDED from deletion (bundle dossiers):**
    - `workflow_code IN ('BUNDLE_PAYMENT', 'FIELD_INSPECTION')`
    - `source IN ('field_inspection', 'admin_import')`
    - `commercial_license_id IS NOT NULL`

    These are commercial licence dossiers that must remain active until
    explicitly closed (plan P2 — INSPECTION_BUNDLE_P2_DETAIL.md).

    Uses `settings.DRAFT_CLEANUP_MAX_HOURS` (default 2h, env-configurable).

    **Anomaly signal**: if `skipped_bundle > 0`, some bundle DRAFTs are
    accumulating — this should never happen with the P1 CollectionService
    which inserts bundle SRs directly in SUBMITTED status.
    """
)
async def cron_cleanup_abandoned_requests(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Delete abandoned DRAFT service_requests older than configured threshold."""
    from app.modules.service_requests.services.service_request_service import (
        service_request_service,
    )

    stats = await service_request_service.cleanup_abandoned_requests(db=db)

    logger.info(
        "Cron cleanup_abandoned_requests: deleted={} docs={} files={} "
        "skipped_bundle={} max_age_hours={} errors={}",
        stats["deleted_requests"],
        stats["deleted_documents"],
        stats["deleted_files"],
        stats["skipped_bundle"],
        stats["max_age_hours"],
        len(stats["errors"]),
    )

    # Anomaly alert: bundle DRAFTs should never accumulate
    if stats["skipped_bundle"] > 0:
        logger.warning(
            "ANOMALY: {} bundle DRAFT requests found during cleanup (should be 0 — "
            "bundles should always be in SUBMITTED/other non-DRAFT status). "
            "Investigate CollectionService flow or manual DRAFT inserts.",
            stats["skipped_bundle"],
        )

    return {
        "message": "Cleanup completed",
        **stats,
    }


@router.post(
    "/payment-sla-check",
    summary="Check payment SLA and send notifications",
    description="""
    Called daily by Cloud Scheduler to monitor cash/check payments
    pending treasury agent validation.

    Three actions:
    1. 48h warning: Email treasury agents with table of pending payments
    2. 5-day escalation: Email supervisors with table of overdue payments
    3. 15-day expiration: Expire payment + request, email citizen
    """
)
async def payment_sla_check(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth)
):
    """Run payment SLA checks: warning, escalation, expiration."""
    sla_service = PaymentSLAService()
    results = await sla_service.run_sla_check(db)

    logger.info(
        f"Payment SLA check: {results['warnings_sent']} warnings, "
        f"{results['escalations_sent']} escalations, "
        f"{results['expirations_processed']} expirations"
    )

    return {
        "message": "Payment SLA check completed",
        **results
    }


@router.post(
    "/escalation-sla-check",
    summary="Check escalation SLA and send notifications",
    description="""
    Called every 2 hours by Cloud Scheduler to monitor open escalations
    pending supervisor resolution.

    Three tiers:
    1. 4h warning: Email entity supervisors with table of pending escalations
    2. 24h escalation: Email admins, boost priority to URGENT
    3. 72h expiration: Auto-resolve escalation, email admin notification
    """
)
async def escalation_sla_check(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth)
):
    """Run escalation SLA checks: warning, escalation, expiration."""
    sla_service = EscalationSLAService()
    results = await sla_service.run_sla_check(db)

    logger.info(
        f"Escalation SLA check: {results['warnings_sent']} warnings, "
        f"{results['escalations_sent']} escalations, "
        f"{results['expirations_processed']} expirations"
    )

    return {
        "message": "Escalation SLA check completed",
        **results
    }


@router.post(
    "/workload-rebalance",
    summary="Auto-rebalance agent workload",
    description="""
    Called daily by Cloud Scheduler to automatically rebalance workload
    across all entities. Moves assignments from overloaded agents to
    underloaded agents using mobility scoring (priority/SLA weighting).
    """
)
async def workload_rebalance(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth)
):
    """Auto-rebalance workload across all active entities."""
    from app.modules.assignment.services.workload_rebalance_service import rebalance_entity_workload

    # Get all entities with active non-supervisor agents
    entities = await db.fetch("""
        SELECT DISTINCT e.id, e.code
        FROM entities e
        JOIN agent_profiles ap ON ap.entity_id = e.id
        WHERE ap.is_active = true AND ap.is_supervisor = false
        AND e.is_active = true
    """)

    total_reassigned = 0
    entity_results = []

    for entity in entities:
        try:
            result = await rebalance_entity_workload(
                entity_id=entity['id'],
                db=db,
                performed_by=None,
            )
            total_reassigned += result['reassignments_made']
            entity_results.append({
                "entity": entity['code'],
                "reassignments": result['reassignments_made'],
            })
        except Exception as e:
            logger.error(f"Rebalance failed for entity {entity['code']}: {e}")
            entity_results.append({
                "entity": entity['code'],
                "error": str(e),
            })

    logger.info(f"Workload rebalance: {total_reassigned} total reassignments across {len(entities)} entities")

    return {
        "message": "Workload rebalance completed",
        "total_reassigned": total_reassigned,
        "entities_processed": len(entities),
        "details": entity_results,
    }


@router.post(
    "/supervisor-weekly-report",
    summary="Send weekly performance report to supervisors",
    description="""
    Called weekly (Monday 8:00 AM) by Cloud Scheduler.
    Sends HTML email report with key metrics to all active supervisors.
    """
)
async def supervisor_weekly_report(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth)
):
    """Send weekly performance report email to all active supervisors."""
    import asyncio
    from app.modules.communications.services.communication_service import CommunicationService
    from app.modules.communications.models.communication import CommunicationType

    comm_service = CommunicationService()

    supervisors = await db.fetch("""
        SELECT ap.user_id, u.email, u.full_name, ap.entity_id,
               e.code as entity_code, e.name as entity_name
        FROM agent_profiles ap
        JOIN users u ON u.id = ap.user_id
        JOIN entities e ON e.id = ap.entity_id
        WHERE ap.is_supervisor = true AND ap.is_active = true
        AND u.status = 'active'
    """)

    emails_sent = 0
    emails_failed = 0

    for sup in supervisors:
        try:
            # Gather weekly stats scoped to entity
            wf_codes = await db.fetchval(
                "SELECT workflow_codes FROM entities WHERE id = $1", sup['entity_id']
            )
            if isinstance(wf_codes, str):
                import json
                wf_codes = json.loads(wf_codes)

            if not wf_codes:
                continue

            stats = await db.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE sr.created_at >= NOW() - INTERVAL '7 days') as new_requests,
                    COUNT(*) FILTER (
                        WHERE sr.status IN ('completed', 'approved')
                        AND sr.updated_at >= NOW() - INTERVAL '7 days'
                    ) as completed,
                    COUNT(*) FILTER (WHERE sr.escalated = true) as pending_escalations,
                    COALESCE(AVG(
                        CASE WHEN sr.status IN ('completed', 'approved')
                        THEN EXTRACT(EPOCH FROM (sr.updated_at - sr.created_at)) / 3600.0
                        ELSE NULL END
                    ), 0) as avg_processing_hours,
                    COUNT(*) FILTER (
                        WHERE sr.status NOT IN ('completed', 'approved', 'rejected', 'cancelled', 'expired')
                    ) as active_requests
                FROM service_requests sr
                WHERE sr.workflow_code = ANY($1)
            """, wf_codes)

            # Build HTML email (escape user-provided strings to prevent XSS)
            entity_name = html_escape(sup['entity_name'] or sup['entity_code'] or '')
            sup_name = html_escape(sup['full_name'] or 'Supervisor')
            avg_hours = round(float(stats['avg_processing_hours'] or 0), 1)
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #1a56db;">Reporte Semanal — {entity_name}</h2>
                <p>Hola {sup_name},</p>
                <p>Resumen de la actividad de tu equipo esta semana:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">Nuevas solicitudes</td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb; text-align: right;">{stats['new_requests'] or 0}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">Completadas</td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb; text-align: right;">{stats['completed'] or 0}</td>
                    </tr>
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">Solicitudes activas</td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb; text-align: right;">{stats['active_requests'] or 0}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">Escalaciones pendientes</td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb; text-align: right; color: {'#dc2626' if (stats['pending_escalations'] or 0) > 0 else '#059669'};">{stats['pending_escalations'] or 0}</td>
                    </tr>
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">Tiempo promedio de tramitación</td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb; text-align: right;">{avg_hours}h</td>
                    </tr>
                </table>
                <p style="font-size: 12px; color: #6b7280;">
                    Este reporte se genera automáticamente cada lunes.
                    Accede al <a href="{getattr(settings, 'FRONTEND_URL', 'https://taxasge.web.app')}/dashboard/supervisor">panel de supervisión</a> para más detalles.
                </p>
            </div>
            """

            subject = f"Reporte Semanal — {entity_name}"

            loop = asyncio.get_running_loop()
            sent = await loop.run_in_executor(
                None,
                lambda: comm_service.send_communication(
                    channel=CommunicationType.EMAIL,
                    recipient=sup['email'],
                    subject=subject,
                    content=html_body,
                )
            )

            if sent:
                emails_sent += 1
            else:
                emails_failed += 1

        except Exception as e:
            logger.error(f"Failed to send weekly report to {sup.get('email')}: {e}")
            emails_failed += 1

    logger.info(f"Supervisor weekly reports: {emails_sent} sent, {emails_failed} failed")

    return {
        "message": "Supervisor weekly reports sent",
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
        "total_supervisors": len(supervisors),
    }


# ============================================================
# Queue Priority Management
# ============================================================


@router.post(
    "/queue-priority-recalculate",
    summary="Recalculate queue priorities based on item age",
    description="""
    Called every 6 hours by Cloud Scheduler.

    Applies age-based priority boosts to pending queue items:
    - Items >24h: +QUEUE_AGE_BOOST_24H (default 10)
    - Items >48h: +QUEUE_AGE_BOOST_48H (default 15)
    - Items >72h: +QUEUE_AGE_BOOST_72H (default 25)

    Prevents items from languishing in the queue when static
    priority alone (from workflows.priority_weight) is equal.
    """,
)
async def queue_priority_recalculate(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Recalculate priorities for aging queue items."""
    from app.modules.service_requests.services.agent_queue_service import agent_queue_service

    updated_count = await agent_queue_service.recalculate_pending_priorities(db)

    if updated_count > 0:
        logger.info(f"Queue priority recalculation: {updated_count} items boosted")

    return {
        "message": "Queue priority recalculation completed",
        "items_updated": updated_count,
    }


# ============================================================
# Assignment Outbox Cron Jobs
# ============================================================


@router.post(
    "/process-assignment-outbox",
    summary="Process pending assignment outbox items",
    description="""
    Called every 1 minute by Cloud Scheduler.

    Processes pending outbox items using FOR UPDATE SKIP LOCKED:
    - Multiple Cloud Run instances can run simultaneously (no overlap)
    - Each item triggers: add_to_queue + auto_assign + PAID→SUBMITTED
    - Failed items retry with exponential backoff (30s→10min)
    - Dead letter after 5 retries
    """,
)
async def process_assignment_outbox(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Process pending assignment outbox items."""
    from app.modules.service_requests.services.assignment_outbox_service import (
        assignment_outbox_service,
    )

    results = await assignment_outbox_service.process_pending_items(db)

    total_work = results["processed"] + results["failed"] + results["dead_letter"]
    if total_work > 0:
        logger.info(
            f"Assignment outbox: {results['processed']} processed, "
            f"{results['failed']} retrying, {results['dead_letter']} dead-lettered"
        )

    return {"message": "Assignment outbox processed", **results}


@router.post(
    "/assignment-health-check",
    summary="Assignment pipeline health check",
    description="""
    Called every 5 minutes by Cloud Scheduler.

    Detects:
    - PAID requests >10 min without assignment or outbox entry (orphans)
    - Dead letter outbox items (>5 retries, need supervisor attention)
    - Stale 'processing' items from crashed instances

    Actions:
    - Re-enqueue orphans into outbox
    - Reset stale processing items to pending
    - Report dead letters for supervisor attention
    """,
)
async def assignment_health_check(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Run assignment pipeline health check."""
    from app.modules.service_requests.services.assignment_outbox_service import (
        assignment_outbox_service,
    )

    results = await assignment_outbox_service.run_health_check(db)

    if results["orphans_found"] > 0 or results["dead_letters"] > 0:
        logger.warning(
            f"Assignment health: {results['orphans_found']} orphans "
            f"({results['orphans_requeued']} requeued), "
            f"{results['dead_letters']} dead letters, "
            f"{results['stale_processing_reset']} stale resets"
        )

    return {"message": "Assignment health check completed", **results}


# ============================================================
# Treasury Materialized Views Refresh
# ============================================================


@router.post(
    "/treasury-refresh-views",
    summary="Refresh treasury materialized views",
    description="""
    Called every 4 hours by Cloud Scheduler.

    Refreshes materialized views used by treasury dashboard:
    - mv_treasury_daily_kpis: daily payment KPIs (365 days window)
    - mv_reconciliation_stats: bank reconciliation stats (90 days window)

    Uses CONCURRENTLY to avoid locking reads during refresh.
    Requires unique indexes on the views (already created).
    """,
)
async def treasury_refresh_views(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Refresh treasury materialized views concurrently."""
    refreshed = []
    errors = []

    views = ["mv_treasury_daily_kpis", "mv_reconciliation_stats", "mv_agent_daily_workload", "mv_services_translated"]

    # Override statement_timeout: REFRESH can exceed 60s at 1M+ rows
    await db.execute("SET LOCAL statement_timeout = '300000'")

    for view in views:
        try:
            await db.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
            refreshed.append(view)
            logger.info(f"Refreshed materialized view: {view}")
        except Exception as e:
            logger.error(f"Failed to refresh {view}: {e}")
            errors.append({"view": view, "error": str(e)})

    return {
        "message": "Treasury views refresh completed",
        "refreshed": refreshed,
        "errors": errors,
    }


# ============================================================================
# LOCK HEALTH CHECK (every 15 min)
# ============================================================================

@router.post(
    "/lock-health-check",
    summary="Monitor PostgreSQL locks and stuck transactions",
    description="""
    Called by Cloud Scheduler every 15 minutes.
    Checks for: waiting locks, long-running transactions (>60s),
    stale payment locks (>4h in locked_by_agent status).
    """
)
async def lock_health_check(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth)
):
    """Monitor database locks and stuck transactions for alerting."""

    # 1. Waiting locks (blocked queries)
    waiting_locks = await db.fetch("""
        SELECT blocked.pid AS blocked_pid,
               LEFT(blocked_activity.query, 200) AS blocked_query,
               blocking.pid AS blocking_pid,
               LEFT(blocking_activity.query, 200) AS blocking_query,
               ROUND(EXTRACT(EPOCH FROM (NOW() - blocked_activity.query_start))::numeric, 1) AS wait_seconds
        FROM pg_locks blocked
        JOIN pg_stat_activity blocked_activity ON blocked.pid = blocked_activity.pid
        JOIN pg_locks blocking
            ON blocked.transactionid = blocking.transactionid
            AND blocked.pid != blocking.pid
        JOIN pg_stat_activity blocking_activity ON blocking.pid = blocking_activity.pid
        WHERE NOT blocked.granted
    """)

    # 2. Long-running transactions (>60s)
    long_txns = await db.fetch("""
        SELECT pid,
               LEFT(query, 200) AS query,
               state,
               ROUND(EXTRACT(EPOCH FROM (NOW() - xact_start))::numeric, 1) AS txn_seconds
        FROM pg_stat_activity
        WHERE state != 'idle'
          AND xact_start < NOW() - INTERVAL '60 seconds'
          AND query NOT LIKE '%pg_stat%'
          AND query NOT LIKE '%cron%'
    """)

    # 3. Stale payment locks (agent_reviewing > 4h)
    stale_payment_locks = await db.fetch("""
        SELECT sp.id AS payment_id,
               sp.payment_reference,
               sp.assigned_agent_id,
               u.full_name AS agent_name,
               sp.assigned_at AS locked_at,
               ROUND(EXTRACT(EPOCH FROM (NOW() - sp.assigned_at))::numeric / 3600, 1) AS locked_hours
        FROM service_payments sp
        LEFT JOIN agent_profiles ap ON ap.id = sp.assigned_agent_id
        LEFT JOIN users u ON u.id = ap.user_id
        WHERE sp.assigned_agent_id IS NOT NULL
          AND sp.assigned_at < NOW() - INTERVAL '4 hours'
          AND sp.workflow_status = 'agent_reviewing'
    """)

    # Log warnings for alerting via Cloud Logging
    if waiting_locks:
        logger.warning(f"LOCK_HEALTH: {len(waiting_locks)} waiting locks detected")
    if long_txns:
        logger.warning(f"LOCK_HEALTH: {len(long_txns)} long-running transactions (>60s)")
    if stale_payment_locks:
        logger.warning(f"LOCK_HEALTH: {len(stale_payment_locks)} stale payment locks (>4h)")

    return {
        "waiting_locks": len(waiting_locks),
        "long_transactions": len(long_txns),
        "stale_payment_locks": len(stale_payment_locks),
        "details": {
            "waiting": [dict(r) for r in waiting_locks],
            "long_txns": [dict(r) for r in long_txns],
            "stale_payments": [dict(r) for r in stale_payment_locks],
        }
    }


# ============================================================================
# SLOW QUERY SNAPSHOT (every 6h)
# ============================================================================

@router.post(
    "/slow-query-snapshot",
    summary="Capture periodic snapshot of slow queries",
    description="""
    Called by Cloud Scheduler every 6 hours.
    Captures top 10 slowest queries from pg_stat_statements for trend analysis.
    Logs to structured logging for Cloud Logging indexing.
    """
)
async def slow_query_snapshot(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth)
):
    """Capture slow query snapshot from pg_stat_statements."""
    try:
        slow_queries = await db.fetch("""
            SELECT queryid,
                   LEFT(query, 300) AS query_preview,
                   calls,
                   ROUND(mean_exec_time::numeric, 2) AS mean_ms,
                   ROUND(max_exec_time::numeric, 2) AS max_ms,
                   ROUND(total_exec_time::numeric, 2) AS total_ms,
                   rows AS total_rows
            FROM pg_stat_statements
            WHERE calls >= 10
              AND mean_exec_time > 100
              AND query NOT LIKE '%pg_stat%'
            ORDER BY mean_exec_time DESC
            LIMIT 10
        """)

        for row in slow_queries:
            logger.warning(
                f"SLOW_QUERY_SNAPSHOT queryid={row['queryid']} "
                f"calls={row['calls']} mean_ms={row['mean_ms']} "
                f"max_ms={row['max_ms']} query={row['query_preview'][:100]}"
            )

        return {
            "snapshot_count": len(slow_queries),
            "queries": [dict(r) for r in slow_queries],
        }
    except Exception as e:
        logger.error(f"Failed to capture slow query snapshot: {e}")
        return {"snapshot_count": 0, "error": str(e)}


# ============================================================================
# PAYMENT ANOMALY DETECTION (daily)
# ============================================================================

@router.post(
    "/payment-anomaly-detection",
    summary="Run automatic payment anomaly detection",
    description="""
    Called by Cloud Scheduler once daily (e.g. 02:00 UTC).

    Detects payment anomalies:
    - SLA breaches: payments pending beyond SLA threshold
    - Amount mismatches: declared vs expected amount discrepancies
    - Duplicate payments: same user+amount+service within window
    - Suspicious patterns: users with 5+ payments in 24 hours

    Results are stored in payment_anomalies table for supervisor review.
    """,
)
async def payment_anomaly_detection_cron(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Run scheduled payment anomaly detection."""
    from app.modules.service_requests.services.treasury_anomaly_service import treasury_anomaly_service

    try:
        results = await treasury_anomaly_service.run_detection(db=db)
        logger.info(
            f"ANOMALY_DETECTION: found {results['anomalies_found']} anomalies "
            f"({results.get('by_type', {})})"
        )
        return {
            "message": "Payment anomaly detection completed",
            "anomalies_found": results["anomalies_found"],
            "by_type": results.get("by_type", {}),
            "detected_at": results["detected_at"],
        }
    except Exception as e:
        logger.error(f"Payment anomaly detection failed: {e}")
        return {"message": "Payment anomaly detection failed", "error": str(e)}


# ============================================================================
# NLP INTENT CLASSIFIER RETRAIN (weekly, Sunday 02:00 UTC)
# ============================================================================

@router.post(
    "/retrain-nlp-classifier",
    summary="Retrain NLP intent classifier from real query data",
    description="""
    Called weekly by Cloud Scheduler (Sunday 02:00 UTC).

    Pipeline:
    1. Fetch last 90 days of agent_query_logs with ground_truth_intent
    2. Cold start: < 50 samples → skip (seed model sufficient)
    3. Retrain TF-IDF + LogisticRegression on seeds + real data (3× weight)
    4. Evaluate on 20% held-out split → report accuracy
    5. Save retrained model to Redis (7-day TTL)
    6. All Cloud Run instances pick up new model on next request

    Distant supervision: Gemini's function calls = free ground truth labels.
    """,
)
async def retrain_nlp_classifier(
    _auth: bool = Depends(verify_cron_auth),
):
    """Retrain NLP intent classifier from accumulated query logs."""
    from app.modules.shared.services.nlp_retrain_service import retrain_nlp_classifier

    report = await retrain_nlp_classifier()

    level = "info" if report["status"] in ("retrained", "skipped_cold_start") else "warning"
    getattr(logger, level)(f"NLP retrain: {report.get('message', report['status'])}")

    return report


# ============================================================================
# INDEX HEALTH AUDIT (monthly, 1st of month 03:00 UTC)
# ============================================================================


def _format_bytes(n: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ("B", "kB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


@router.post(
    "/index-health-audit",
    summary="Audit unused and redundant database indexes",
    description="""
    Called monthly by Cloud Scheduler (1st of month, 03:00 UTC).

    Analyzes pg_stat_user_indexes on high-write tables for:
    - Unused indexes (0 scans since last stats reset)
    - Index/table size ratio (bloat detection)
    - Duplicate/overlapping index candidates (same leading column)

    Read-only — does NOT modify or drop any indexes.
    Results are logged to Cloud Logging for admin review.

    Reliability: stats counters are cumulative since last DB restart
    or pg_stat_reset(). The 'stats_days_since_reset' field indicates
    how long the data has been accumulating. Values > 90 days are
    considered reliable for identifying truly unused indexes.
    """,
)
async def index_health_audit(
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Audit database indexes for unused and redundant entries."""

    MONITORED_TABLES = (
        "service_requests", "service_payments", "service_bundle_items",
        "agent_work_queue", "workflow_transitions", "uploaded_files",
        "payment_validation_audit", "audit_logs",
    )

    # 1. Stats reset time — indicates reliability of 0-scan data
    stats_info = await db.fetchrow("""
        SELECT stats_reset,
               EXTRACT(EPOCH FROM (NOW() - stats_reset)) / 86400.0 AS days_since_reset
        FROM pg_stat_bgwriter
    """)
    days_since_reset = round(
        float(stats_info["days_since_reset"] or 0), 1
    ) if stats_info and stats_info["stats_reset"] else 0

    # 2. Unused indexes (0 scans, excluding PKs and UNIQUE constraints)
    unused_indexes = await db.fetch("""
        SELECT
            i.relname AS table_name,
            i.indexrelname AS index_name,
            pg_size_pretty(pg_relation_size(i.indexrelid)) AS index_size,
            pg_relation_size(i.indexrelid) AS size_bytes,
            LEFT(pg_get_indexdef(i.indexrelid), 250) AS definition
        FROM pg_stat_user_indexes i
        JOIN pg_index pi ON pi.indexrelid = i.indexrelid
        WHERE i.relname = ANY($1::text[])
          AND i.idx_scan = 0
          AND NOT pi.indisunique
          AND NOT pi.indisprimary
        ORDER BY pg_relation_size(i.indexrelid) DESC
    """, list(MONITORED_TABLES))

    # 3. Duplicate candidates (same table + same leading column)
    duplicate_candidates = await db.fetch("""
        WITH idx_leading AS (
            SELECT
                i.relname AS table_name,
                i.indexrelname AS index_name,
                i.idx_scan,
                (SELECT a.attname FROM pg_attribute a
                 WHERE a.attrelid = ix.indrelid AND a.attnum = ix.indkey[0]
                   AND a.attnum > 0) AS leading_col,
                (SELECT string_agg(a.attname, ',' ORDER BY ord)
                 FROM unnest(ix.indkey) WITH ORDINALITY AS u(attnum, ord)
                 JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = u.attnum
                 WHERE a.attnum > 0) AS all_cols
            FROM pg_stat_user_indexes i
            JOIN pg_index ix ON ix.indexrelid = i.indexrelid
            WHERE i.relname = ANY($1::text[])
        )
        SELECT
            a.table_name,
            a.index_name AS idx_a, a.all_cols AS cols_a, a.idx_scan AS scans_a,
            b.index_name AS idx_b, b.all_cols AS cols_b, b.idx_scan AS scans_b
        FROM idx_leading a
        JOIN idx_leading b
          ON a.table_name = b.table_name
         AND a.leading_col = b.leading_col
         AND a.index_name < b.index_name
        ORDER BY a.table_name, a.leading_col
    """, list(MONITORED_TABLES))

    # 4. Index-to-table size ratios
    size_ratios = await db.fetch("""
        SELECT
            relname AS table_name,
            pg_size_pretty(pg_relation_size(relid)) AS table_size,
            pg_size_pretty(pg_indexes_size(relid)) AS indexes_size,
            (SELECT count(*) FROM pg_index WHERE indrelid = c.relid) AS index_count,
            CASE WHEN pg_relation_size(relid) > 0
                 THEN ROUND(pg_indexes_size(relid)::numeric /
                            pg_relation_size(relid)::numeric, 1)
                 ELSE 0 END AS idx_table_ratio
        FROM pg_stat_user_tables c
        WHERE relname = ANY($1::text[])
        ORDER BY pg_indexes_size(relid) DESC
    """, list(MONITORED_TABLES))

    # 5. Aggregate waste
    total_waste = sum(r["size_bytes"] for r in unused_indexes)

    # 6. Structured logging for Cloud Logging alerting
    for idx in unused_indexes:
        logger.warning(
            f"INDEX_HEALTH_UNUSED: {idx['index_name']} on {idx['table_name']} "
            f"({idx['index_size']}, 0 scans in {days_since_reset} days) "
            f"— candidate for removal"
        )

    for dup in duplicate_candidates:
        logger.info(
            f"INDEX_HEALTH_OVERLAP: {dup['idx_a']}({dup['cols_a']}) "
            f"vs {dup['idx_b']}({dup['cols_b']}) on {dup['table_name']} "
            f"(scans: {dup['scans_a']} vs {dup['scans_b']})"
        )

    for ratio in size_ratios:
        if float(ratio["idx_table_ratio"]) > 5:
            logger.warning(
                f"INDEX_HEALTH_BLOAT: {ratio['table_name']} index/table ratio = "
                f"{ratio['idx_table_ratio']}x ({ratio['indexes_size']} indexes "
                f"vs {ratio['table_size']} data, {ratio['index_count']} indexes)"
            )

    logger.info(
        f"INDEX_HEALTH_AUDIT: {len(unused_indexes)} unused indexes "
        f"({_format_bytes(total_waste)} waste), "
        f"{len(duplicate_candidates)} overlap candidates, "
        f"stats reliability: {days_since_reset} days"
    )

    return {
        "message": "Index health audit completed",
        "stats_days_since_reset": days_since_reset,
        "reliable": days_since_reset >= 90,
        "unused_indexes": [
            {
                "table": r["table_name"],
                "index": r["index_name"],
                "size": r["index_size"],
                "definition": r["definition"],
            }
            for r in unused_indexes
        ],
        "unused_count": len(unused_indexes),
        "total_waste": _format_bytes(total_waste),
        "duplicate_candidates": [
            {
                "table": r["table_name"],
                "idx_a": r["idx_a"], "cols_a": r["cols_a"], "scans_a": r["scans_a"],
                "idx_b": r["idx_b"], "cols_b": r["cols_b"], "scans_b": r["scans_b"],
            }
            for r in duplicate_candidates
        ],
        "overlap_count": len(duplicate_candidates),
        "size_ratios": [
            {
                "table": r["table_name"],
                "table_size": r["table_size"],
                "indexes_size": r["indexes_size"],
                "index_count": r["index_count"],
                "ratio": float(r["idx_table_ratio"]),
            }
            for r in size_ratios
        ],
    }


# ---------------------------------------------------------------------------
# Cron: Permission Audit Log Cleanup
# ---------------------------------------------------------------------------

@router.post(
    "/cleanup-permission-audit-log",
    summary="Archive old permission audit entries",
    description="""
    Called daily by Cloud Scheduler.

    Archives permission_audit_log entries older than retention_days (default 90)
    into permission_audit_log_archive table, then removes them from the main table.
    This prevents unbounded growth from startup sync triggers.
    """
)
async def cleanup_permission_audit_log(
    retention_days: int = 90,
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Archive old permission audit entries and return stats."""
    try:
        row = await db.fetchrow(
            "SELECT * FROM cleanup_permission_audit_log($1)",
            retention_days,
        )
        archived = row["archived_count"] if row else 0
        remaining = row["remaining_count"] if row else 0

        logger.info(
            f"Permission audit cleanup: archived={archived}, "
            f"remaining={remaining}, retention={retention_days}d"
        )

        return {
            "message": f"Archived {archived} entries older than {retention_days} days",
            "archived_count": archived,
            "remaining_count": remaining,
            "retention_days": retention_days,
        }

    except Exception as e:
        logger.error(f"Permission audit cleanup failed: {e}")
        return {
            "message": f"Cleanup failed: {str(e)}",
            "archived_count": 0,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Cron: Re-index Legislative PDFs for RAG Chatbot
# ---------------------------------------------------------------------------

@router.post(
    "/reindex-legislacion-pdfs",
    summary="Re-index legislative PDFs for RAG chatbot",
    description="""
    Called weekly by Cloud Scheduler (or manually).

    Scans all PDFs in the legislacion folder, chunks them, generates embeddings
    with Vertex AI, and upserts into legislacion_documents table.
    Runs on Cloud Run which has GCP service account credentials.
    Idempotent: existing chunks are skipped unless force=true.
    """
)
async def reindex_legislacion_pdfs(
    force: bool = False,
    doc: str = "",
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Re-index legislative PDFs for RAG chatbot semantic search."""
    import glob
    import os
    import time as time_module

    try:
        from app.modules.chatbot.services.embedding_service import embedding_service

        if not embedding_service.enabled:
            return {"message": "Embedding service disabled (Vertex AI not available)", "error": True}

        # Find PDFs — check backend data/legislacion/ first (deployed with backend image),
        # then fallback to web/public (local dev), then absolute Cloud Run path
        pdf_folder = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'legislacion')
        if not os.path.isdir(pdf_folder):
            pdf_folder = os.path.join(os.getcwd(), 'data', 'legislacion')
        if not os.path.isdir(pdf_folder):
            # Cloud Run: absolute path in backend image
            pdf_folder = '/app/data/legislacion'
        if not os.path.isdir(pdf_folder):
            # Fallback: web public (local dev only)
            pdf_folder = os.path.join(os.getcwd(), '..', 'web', 'public', 'documents', 'legislacion')

        # Find PDFs AND markdown files (for scanned documents converted to text)
        all_files = []
        if os.path.isdir(pdf_folder):
            all_files = sorted(
                glob.glob(os.path.join(pdf_folder, '*.pdf'))
                + glob.glob(os.path.join(pdf_folder, '*.md'))
            )
        if not all_files:
            return {"message": f"No files found in {pdf_folder}", "pdf_count": 0}

        # Filter by specific document if requested (avoids timeout on large batches)
        if doc:
            all_files = [f for f in all_files if doc.lower() in os.path.basename(f).lower()]
            if not all_files:
                return {"message": f"Document '{doc}' not found in {pdf_folder}", "pdf_count": 0}

        logger.info(f"Found {len(all_files)} file(s) to index (PDF + MD)")

        # Import pdfplumber (available in requirements.txt)
        try:
            import pdfplumber
        except ImportError:
            return {"message": "pdfplumber not installed", "error": True}

        chunk_size = settings.PDF_CHUNK_SIZE
        chunk_overlap = settings.PDF_CHUNK_OVERLAP
        start_time = time_module.time()

        total_stats = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0, "pdfs_processed": 0}

        for file_path in all_files:
            filename = os.path.basename(file_path)
            doc_name = os.path.splitext(filename)[0]
            is_markdown = filename.endswith('.md')

            # Check existing chunks BEFORE parsing
            existing = set()
            if not force:
                rows = await db.fetch(
                    "SELECT chunk_id FROM legislacion_documents WHERE document_name = $1",
                    doc_name,
                )
                existing = {r['chunk_id'] for r in rows}

            page_count = 0
            chunks_this_file = 0
            try:
                if is_markdown:
                    # Markdown: read as plain text, chunk directly
                    with open(file_path, 'r', encoding='utf-8') as f:
                        full_text = f.read()
                    if not full_text.strip():
                        continue
                    page_count = 1
                    step = max(1, chunk_size - chunk_overlap)
                    for i in range(0, len(full_text), step):
                        chunk_text = full_text[i:i + chunk_size]
                        if len(chunk_text.strip()) < 50:
                            continue
                        chunk_idx = i // step
                        page_num = chunk_idx // 3 + 1  # Approximate pages (3 chunks per "page")
                        chunk_id = f'{doc_name.lower()}_p{page_num}_c{chunk_idx % 3}'

                        if chunk_id in existing and not force:
                            total_stats['skipped'] += 1
                            continue

                        embedding = await embedding_service.generate_embedding(
                            chunk_text.strip(),
                            task_type='RETRIEVAL_DOCUMENT',
                            title=f"{doc_name} - Section {chunk_idx + 1}",
                        )
                        if not embedding:
                            total_stats['failed'] += 1
                            continue

                        embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
                        await db.execute(
                            """
                            INSERT INTO legislacion_documents
                                (document_name, page_number, chunk_id, content,
                                 embedding, embedding_model, embedding_generated_at)
                            VALUES ($1, $2, $3, $4, $5::vector, $6, NOW())
                            ON CONFLICT (document_name, chunk_id) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding,
                                embedding_model = EXCLUDED.embedding_model,
                                embedding_generated_at = NOW(),
                                updated_at = NOW()
                            """,
                            doc_name, page_num, chunk_id, chunk_text.strip(),
                            embedding_str, settings.GEMINI_EMBEDDING_MODEL,
                        )

                        if chunk_id in existing:
                            total_stats['updated'] += 1
                        else:
                            total_stats['inserted'] += 1
                        chunks_this_file += 1

                else:
                    # PDF: parse page by page with pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        page_count = len(pdf.pages)
                        for page_num, page in enumerate(pdf.pages, 1):
                            text = page.extract_text() or ''
                            if not text.strip():
                                continue

                            step = max(1, chunk_size - chunk_overlap)
                            for i in range(0, len(text), step):
                                chunk_text = text[i:i + chunk_size]
                                if len(chunk_text.strip()) < 50:
                                    continue
                                chunk_idx = i // step
                                chunk_id = f'{doc_name.lower()}_p{page_num}_c{chunk_idx}'

                            # Skip if already indexed
                            if chunk_id in existing and not force:
                                total_stats['skipped'] += 1
                                continue

                            # Embed immediately (don't accumulate in memory)
                            embedding = await embedding_service.generate_embedding(
                                chunk_text.strip(),
                                task_type='RETRIEVAL_DOCUMENT',
                                title=f"{doc_name} - Página {page_num}",
                            )
                            if not embedding:
                                total_stats['failed'] += 1
                                continue

                            embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
                            await db.execute(
                                """
                                INSERT INTO legislacion_documents
                                    (document_name, page_number, chunk_id, content,
                                     embedding, embedding_model, embedding_generated_at)
                                VALUES ($1, $2, $3, $4, $5::vector, $6, NOW())
                                ON CONFLICT (document_name, chunk_id) DO UPDATE SET
                                    content = EXCLUDED.content,
                                    embedding = EXCLUDED.embedding,
                                    embedding_model = EXCLUDED.embedding_model,
                                    embedding_generated_at = NOW(),
                                    updated_at = NOW()
                                """,
                                doc_name,
                                page_num,
                                chunk_id,
                                chunk_text.strip(),
                                embedding_str,
                                settings.GEMINI_EMBEDDING_MODEL,
                            )

                            if chunk_id in existing:
                                total_stats['updated'] += 1
                            else:
                                total_stats['inserted'] += 1
                            chunks_this_file += 1

                        # Page memory freed when loop moves to next page

            except Exception as e:
                logger.error(f"Failed to parse {filename}: {e}")
                continue

            if chunks_this_file == 0 and not existing:
                logger.info(f"  {filename}: no text extracted (possibly scanned PDF)")
                continue

            total_stats['pdfs_processed'] += 1
            logger.info(f"  {filename}: {page_count} pages/sections, {chunks_this_file} new chunks indexed")

        elapsed = time_module.time() - start_time
        total_stats['elapsed_seconds'] = round(elapsed, 1)
        total_stats['message'] = (
            f"Indexed {total_stats['pdfs_processed']}/{len(all_files)} files: "
            f"+{total_stats['inserted']} new, ~{total_stats['updated']} updated, "
            f"={total_stats['skipped']} skipped, x{total_stats['failed']} failed "
            f"in {elapsed:.1f}s"
        )

        logger.info(total_stats['message'])
        return total_stats

    except Exception as e:
        logger.error(f"PDF re-indexing failed: {e}")
        return {"message": f"Re-indexing failed: {str(e)}", "error": str(e)}


# ---------------------------------------------------------------------------
# Cron: Re-embed Fiscal Services (after embedding model migration)
# ---------------------------------------------------------------------------

@router.post(
    "/reembed-fiscal-services",
    summary="Re-generate embeddings for all fiscal services",
    description="""
    Called after embedding model migration (e.g., text-embedding-004 → 005).

    Regenerates embeddings for all active fiscal services using the current
    GEMINI_EMBEDDING_MODEL. Processes in batches to avoid Vertex AI rate limits.
    Idempotent: safe to run multiple times. Marks needs_embedding_update=false.

    Run this ONCE after deploying a new embedding model version.
    """
)
async def reembed_fiscal_services(
    batch_size: int = 50,
    force: bool = False,
    db: asyncpg.Connection = Depends(get_database),
    _auth: bool = Depends(verify_cron_auth),
):
    """Re-generate embeddings for fiscal services with current model."""
    import time as time_module

    try:
        from app.modules.chatbot.services.embedding_service import embedding_service

        if not embedding_service.enabled:
            return {"message": "Embedding service disabled (Vertex AI not available)", "error": True}

        start_time = time_module.time()
        current_model = settings.GEMINI_EMBEDDING_MODEL

        # Find services that need re-embedding
        if force:
            rows = await db.fetch("""
                SELECT id, service_code, name_es, description_es,
                       embedding_model, needs_embedding_update
                FROM fiscal_services
                WHERE status = 'active'
                ORDER BY service_code
            """)
        else:
            rows = await db.fetch("""
                SELECT id, service_code, name_es, description_es,
                       embedding_model, needs_embedding_update
                FROM fiscal_services
                WHERE status = 'active'
                  AND (embedding IS NULL
                       OR needs_embedding_update = true
                       OR embedding_model IS DISTINCT FROM $1)
                ORDER BY service_code
            """, current_model)

        if not rows:
            return {
                "message": f"All services already use {current_model}",
                "updated": 0,
                "model": current_model,
            }

        logger.info(f"Re-embedding {len(rows)} services with {current_model}")

        updated = 0
        failed = 0
        skipped = 0

        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]

            for row in batch:
                try:
                    # Build embedding text (same pattern as populate_embeddings.py)
                    name = row["name_es"] or ""
                    desc = (row["description_es"] or "")[:500]
                    text = f"{name}. {desc}".strip()

                    if len(text) < 10:
                        skipped += 1
                        continue

                    embedding = await embedding_service.generate_embedding(
                        text,
                        task_type='RETRIEVAL_DOCUMENT',
                        title=name[:100],
                    )

                    if not embedding:
                        failed += 1
                        continue

                    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
                    await db.execute("""
                        UPDATE fiscal_services
                        SET embedding = $1::vector,
                            embedding_model = $2,
                            embedding_generated_at = NOW(),
                            embedding_version = COALESCE(embedding_version, 0) + 1,
                            needs_embedding_update = false
                        WHERE id = $3
                    """, embedding_str, current_model, row["id"])
                    updated += 1

                except Exception as e:
                    logger.error(f"Re-embed {row['service_code']} failed: {e}")
                    failed += 1

            logger.info(f"  Batch {i // batch_size + 1}: {updated}/{len(rows)} updated")

            # Small delay between batches to avoid rate limiting
            if i + batch_size < len(rows):
                import asyncio
                await asyncio.sleep(1)

        elapsed = time_module.time() - start_time
        result = {
            "message": f"Re-embedded {updated}/{len(rows)} services with {current_model} in {elapsed:.1f}s",
            "updated": updated,
            "failed": failed,
            "skipped": skipped,
            "total": len(rows),
            "model": current_model,
            "elapsed_seconds": round(elapsed, 1),
        }
        logger.info(result["message"])
        return result

    except Exception as e:
        logger.error(f"Re-embedding failed: {e}")
        return {"message": f"Re-embedding failed: {str(e)}", "error": str(e)}
