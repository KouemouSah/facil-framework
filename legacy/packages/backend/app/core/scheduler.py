"""
Internal cron scheduler for TaxasGE backend.

Replaces Cloud Scheduler by running periodic tasks inside the FastAPI process.
Uses asyncio tasks with configurable intervals.

Safe for multi-instance: outbox uses FOR UPDATE SKIP LOCKED,
other jobs are idempotent.

HTTP cron endpoints remain available as manual triggers.
"""

import asyncio
from datetime import date, timedelta, datetime
from html import escape as html_escape
from loguru import logger


class InternalScheduler:
    """Lightweight asyncio-based cron scheduler."""

    def __init__(self):
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self):
        """Start all scheduled jobs after app initialization."""
        if self._running:
            return

        from app.config import get_settings
        settings = get_settings()

        if not settings.SCHEDULER_ENABLED:
            logger.info("Internal scheduler DISABLED (SCHEDULER_ENABLED=false)")
            return

        self._running = True

        jobs = [
            # (name, handler, interval_seconds)
            (
                "process-assignment-outbox",
                self._process_assignment_outbox,
                settings.SCHEDULER_OUTBOX_INTERVAL,
            ),
            (
                "assignment-health-check",
                self._assignment_health_check,
                settings.SCHEDULER_HEALTH_CHECK_INTERVAL,
            ),
            (
                "cleanup-expired-holds",
                self._cleanup_expired_holds,
                settings.SCHEDULER_EXPIRED_HOLDS_INTERVAL,
            ),
            (
                "escalation-sla-check",
                self._escalation_sla_check,
                settings.SCHEDULER_ESCALATION_SLA_INTERVAL,
            ),
            (
                "queue-priority-recalculate",
                self._queue_priority_recalculate,
                settings.SCHEDULER_QUEUE_PRIORITY_INTERVAL,
            ),
            (
                "appointment-reminders",
                self._appointment_reminders,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "payment-sla-check",
                self._payment_sla_check,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "workload-rebalance",
                self._workload_rebalance,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "proficiency-30d-rollup",
                self._proficiency_30d_rollup,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "anomaly-detection",
                self._anomaly_detection,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "refresh-treasury-views",
                self._refresh_treasury_views,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "refresh-inspection-zone-analytics",
                self._refresh_inspection_zone_analytics,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "field-sla-check",
                self._field_sla_check,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "mission-daily-reminder",
                self._mission_daily_reminder,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "mission-start-alert",
                self._mission_start_alert,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "mission-progress-alert",
                self._mission_progress_alert,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "inspection-daily-summary",
                self._inspection_daily_summary,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "supervisor-weekly-report",
                self._supervisor_weekly_report,
                settings.SCHEDULER_WEEKLY_INTERVAL,
            ),
            (
                "mission-stale-cleanup",
                self._mission_stale_cleanup,
                settings.SCHEDULER_WEEKLY_INTERVAL,
            ),
            (
                "mission-auto-create",
                self._mission_auto_create,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "inspection-weekly-digest",
                self._inspection_weekly_digest,
                settings.SCHEDULER_WEEKLY_INTERVAL,
            ),
            (
                "refresh-effective-permissions",
                self._refresh_effective_permissions,
                60,  # Every 60 seconds — lightweight CONCURRENTLY refresh
            ),
            # ── Module crons (HTTP endpoint equivalents run internally) ──
            (
                "refresh-company-stats",
                self._refresh_company_stats,
                900,  # Every 15 min — refresh company dashboard MVs
            ),
            (
                "license-flag-overdue",
                self._license_flag_overdue,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "license-apply-penalties",
                self._license_apply_penalties,
                settings.SCHEDULER_WEEKLY_INTERVAL,
            ),
            (
                "license-obligation-reminders",
                self._license_obligation_reminders,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "license-renewal-reminders",
                self._license_renewal_reminders,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "auth-cleanup",
                self._auth_cleanup,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "cleanup-abandoned-requests",
                self._cleanup_abandoned_requests,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "inspection-auto-approve-seals",
                self._inspection_auto_approve_seals,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                "document-intelligence-scan",
                self._document_intelligence_scan,
                settings.SCHEDULER_DAILY_INTERVAL,
            ),
            (
                # Phase C.2 — request_telemetry retention + MV refresh
                # Runs every 6 hours: drops raw rows > 30d, refreshes hourly MV
                "request-telemetry-cleanup",
                self._request_telemetry_cleanup,
                21600,  # 6 hours
            ),
            (
                # Phase C.4 — refresh MaxMind GeoLite2-City.mmdb monthly.
                # No-op when MAXMIND_LICENSE_KEY is not set.
                "geolite-refresh",
                self._geolite_refresh,
                2592000,  # 30 days
            ),
        ]

        for name, handler, interval in jobs:
            task = asyncio.create_task(
                self._run_periodic(name, handler, interval)
            )
            self._tasks.append(task)

        logger.info(
            f"Internal scheduler started: {len(self._tasks)} jobs "
            f"(outbox={settings.SCHEDULER_OUTBOX_INTERVAL}s, "
            f"health={settings.SCHEDULER_HEALTH_CHECK_INTERVAL}s)"
        )

    async def stop(self):
        """Cancel all running tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Internal scheduler stopped")

    _stagger_counter: int = 0

    async def _run_periodic(self, name: str, handler, interval_seconds: int):
        """Execute handler on a fixed interval with error isolation."""
        # Stagger initial delay: 30s base + 5s per job to avoid pool saturation
        # (17 jobs × 5s = 85s spread — prevents all jobs hitting the pool simultaneously)
        InternalScheduler._stagger_counter += 1
        initial_delay = 30 + (InternalScheduler._stagger_counter * 5)
        await asyncio.sleep(initial_delay)

        while self._running:
            try:
                result = await handler()
                if result:
                    logger.debug(f"Scheduler [{name}]: {result}")
            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                logger.warning(f"Scheduler [{name}] timed out (pool exhaustion?), will retry next cycle")
            except Exception as e:
                logger.error(f"Scheduler [{name}] failed: {type(e).__name__}: {e}", exc_info=True)

            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break

    # ------------------------------------------------------------------
    # Job handlers — each acquires its own DB connection from the pool
    # ------------------------------------------------------------------

    async def _process_assignment_outbox(self):
        from app.database.connection import db_manager
        from app.modules.service_requests.services.assignment_outbox_service import (
            assignment_outbox_service,
        )

        async with db_manager.get_connection() as db:
            results = await assignment_outbox_service.process_pending_items(db)
            total = results["processed"] + results["failed"] + results["dead_letter"]
            if total > 0:
                logger.info(
                    f"Outbox cron: {results['processed']} processed, "
                    f"{results['failed']} retrying, "
                    f"{results['dead_letter']} dead-lettered"
                )
                return results
        return None

    async def _assignment_health_check(self):
        from app.database.connection import db_manager
        from app.modules.service_requests.services.assignment_outbox_service import (
            assignment_outbox_service,
        )

        async with db_manager.get_connection() as db:
            results = await assignment_outbox_service.run_health_check(db)
            if results["orphans_found"] > 0 or results["dead_letters"] > 0:
                logger.warning(
                    f"Health check: {results['orphans_found']} orphans "
                    f"({results['orphans_requeued']} requeued), "
                    f"{results['dead_letters']} dead letters, "
                    f"{results['stale_processing_reset']} stale resets"
                )
                return results
        return None

    async def _cleanup_expired_holds(self):
        from app.database.connection import db_manager

        async with db_manager.get_connection() as db:
            result = await db.execute("""
                UPDATE appointment_holds
                SET status = 'expired', released_at = NOW()
                WHERE status = 'held' AND expires_at < NOW()
            """)
            count = 0
            if result:
                try:
                    count = int(result.split()[-1])
                except (ValueError, IndexError):
                    pass
            if count > 0:
                logger.info(f"Expired appointment holds released: {count}")
                return {"released_count": count}
        return None

    async def _escalation_sla_check(self):
        from app.database.connection import db_manager
        from app.modules.service_requests.services.escalation_sla_service import (
            EscalationSLAService,
        )

        async with db_manager.get_connection() as db:
            sla_service = EscalationSLAService()
            results = await sla_service.run_sla_check(db)
            total = (
                results["warnings_sent"]
                + results["escalations_sent"]
                + results["expirations_processed"]
            )
            if total > 0:
                logger.info(
                    f"Escalation SLA: {results['warnings_sent']} warnings, "
                    f"{results['escalations_sent']} escalations, "
                    f"{results['expirations_processed']} expirations"
                )
                return results
        return None

    async def _queue_priority_recalculate(self):
        from app.database.connection import db_manager
        from app.modules.service_requests.services.agent_queue_service import (
            agent_queue_service,
        )

        async with db_manager.get_connection() as db:
            updated = await agent_queue_service.recalculate_pending_priorities(db)
            if updated > 0:
                logger.info(f"Queue priority recalculation: {updated} items boosted")
                return {"items_updated": updated}
        return None

    async def _appointment_reminders(self):
        from app.database.connection import db_manager
        from app.core.events import EventBus, EventType

        tomorrow = date.today() + timedelta(days=1)

        async with db_manager.get_connection() as db:
            appointments = await db.fetch("""
                SELECT
                    sr.id as request_id, sr.user_id, sr.workflow_code,
                    sr.reference, sr.cita_date as appointment_date,
                    sr.cita_time as appointment_time,
                    sr.cita_location as location,
                    u.email, u.phone_number as phone,
                    u.first_name, u.last_name, u.preferred_language,
                    ar.id as reservation_id
                FROM service_requests sr
                JOIN users u ON u.id = sr.user_id
                LEFT JOIN appointment_reservations ar
                    ON ar.service_request_id = sr.id
                WHERE sr.cita_date = $1
                AND sr.status IN ('SUBMITTED', 'UNDER_REVIEW', 'DOSSIER_VALIDE', 'COMPLETED', 'PAID')
                AND (ar.reminder_sent_at IS NULL OR ar.id IS NULL)
            """, tomorrow)

            if not appointments:
                return None

            sent = 0
            failed = 0
            for appt in appointments:
                try:
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
                            "service": appt["workflow_code"],
                            "reference": appt["reference"],
                            "appointment_date": str(appt["appointment_date"]) if appt.get("appointment_date") else None,
                            "date": str(appt["appointment_date"]) if appt.get("appointment_date") else None,
                            "appointment_time": str(appt["appointment_time"]) if appt.get("appointment_time") else None,
                            "time": str(appt["appointment_time"]) if appt.get("appointment_time") else None,
                            "location": appt.get("location"),
                        },
                    )
                    if appt.get("reservation_id"):
                        await db.execute(
                            "UPDATE appointment_reservations SET reminder_sent_at = NOW() WHERE id = $1",
                            appt["reservation_id"],
                        )
                    sent += 1
                except Exception as e:
                    logger.error(f"Reminder failed for {appt['request_id']}: {e}")
                    failed += 1

            logger.info(f"Appointment reminders: {sent} sent, {failed} failed")
            return {"sent": sent, "failed": failed}

    async def _payment_sla_check(self):
        from app.database.connection import db_manager
        from app.modules.payments.services.payment_sla_service import PaymentSLAService

        async with db_manager.get_connection() as db:
            sla_service = PaymentSLAService()
            results = await sla_service.run_sla_check(db)
            total = (
                results["warnings_sent"]
                + results["escalations_sent"]
                + results["expirations_processed"]
            )
            if total > 0:
                logger.info(
                    f"Payment SLA: {results['warnings_sent']} warnings, "
                    f"{results['escalations_sent']} escalations, "
                    f"{results['expirations_processed']} expirations"
                )
                return results
        return None

    async def _workload_rebalance(self):
        from app.database.connection import db_manager
        from app.modules.assignment.services.workload_rebalance_service import (
            rebalance_entity_workload,
        )

        async with db_manager.get_connection() as db:
            entities = await db.fetch("""
                SELECT DISTINCT e.id, e.code
                FROM entities e
                JOIN agent_profiles ap ON ap.entity_id = e.id
                WHERE ap.is_active = true AND ap.is_supervisor = false
                AND e.is_active = true
            """)

            if not entities:
                return None

            total = 0
            for entity in entities:
                try:
                    result = await rebalance_entity_workload(
                        entity_id=entity["id"],
                        db=db,
                        performed_by=None,
                    )
                    total += result["reassignments_made"]
                except Exception as e:
                    logger.error(f"Rebalance failed for {entity['code']}: {e}")

            if total > 0:
                logger.info(
                    f"Workload rebalance: {total} reassignments "
                    f"across {len(entities)} entities"
                )
                return {"total_reassigned": total}
        return None

    async def _proficiency_30d_rollup(self):
        """Recalculate 30-day rolling counters in agent_workflow_proficiency."""
        from app.database.connection import db_manager

        async with db_manager.get_connection() as db:
            # Step 1: Reset ALL 30d counters to 0 first (avoids stale data bug)
            await db.execute("""
                UPDATE agent_workflow_proficiency
                SET completions_30d = 0, escalations_30d = 0
                WHERE completions_30d > 0 OR escalations_30d > 0
            """)

            # Step 2: Set actual 30d completions from agent_work_queue
            await db.execute("""
                UPDATE agent_workflow_proficiency awp SET
                    completions_30d = sub.cnt
                FROM (
                    SELECT ap.id AS agent_profile_id, q.declaration_type AS workflow_code,
                           COUNT(*) AS cnt
                    FROM agent_work_queue q
                    JOIN agent_profiles ap ON ap.user_id = q.completed_by
                    WHERE q.status = 'completed'
                      AND q.completed_at >= NOW() - INTERVAL '30 days'
                    GROUP BY ap.id, q.declaration_type
                ) sub
                WHERE awp.agent_profile_id = sub.agent_profile_id
                  AND awp.workflow_code = sub.workflow_code
            """)

            # Step 3: Set actual 30d escalations from agent_work_queue
            await db.execute("""
                UPDATE agent_workflow_proficiency awp SET
                    escalations_30d = sub.cnt
                FROM (
                    SELECT ap.id AS agent_profile_id, q.declaration_type AS workflow_code,
                           COUNT(*) AS cnt
                    FROM agent_work_queue q
                    JOIN agent_profiles ap ON ap.user_id = q.escalated_by
                    WHERE q.escalated = true
                      AND q.escalated_at >= NOW() - INTERVAL '30 days'
                    GROUP BY ap.id, q.declaration_type
                ) sub
                WHERE awp.agent_profile_id = sub.agent_profile_id
                  AND awp.workflow_code = sub.workflow_code
            """)

            logger.info("Proficiency 30d rollup completed")
            return {"status": "ok"}

    async def _refresh_treasury_views(self):
        """Refresh materialized views used by treasury analytics dashboard."""
        from app.database.connection import db_manager

        async with db_manager.get_connection() as db:
            # Override statement_timeout: REFRESH can exceed 60s at 1M+ rows
            await db.execute("SET LOCAL statement_timeout = '300000'")
            refreshed = []
            for view in ("mv_treasury_daily_kpis", "mv_reconciliation_stats", "mv_agent_daily_workload"):
                try:
                    await db.execute(
                        f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"
                    )
                    refreshed.append(view)
                except Exception as e:
                    # CONCURRENTLY requires a unique index; fall back to blocking refresh
                    try:
                        await db.execute(f"REFRESH MATERIALIZED VIEW {view}")
                        refreshed.append(view)
                    except Exception as e2:
                        logger.error(f"Failed to refresh {view}: {e2}")

            if refreshed:
                logger.info(f"Treasury views refreshed: {', '.join(refreshed)}")
                return {"refreshed": refreshed}
        return None

    async def _refresh_inspection_zone_analytics(self):
        """Refresh materialized view for inspection zone analytics (daily)."""
        from app.database.connection import db_manager

        view = "mv_inspection_zone_analytics"
        async with db_manager.get_connection() as db:
            await db.execute("SET LOCAL statement_timeout = '300000'")
            try:
                await db.execute(
                    f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"
                )
                logger.info(f"Inspection zone analytics view refreshed (CONCURRENTLY)")
                return {"refreshed": view}
            except Exception:
                try:
                    await db.execute(f"REFRESH MATERIALIZED VIEW {view}")
                    logger.info(f"Inspection zone analytics view refreshed (blocking)")
                    return {"refreshed": view}
                except Exception as e2:
                    if "does not exist" in str(e2):
                        return None  # Migration not yet applied
                    logger.error(f"Failed to refresh {view}: {e2}")
        return None

    async def _field_sla_check(self):
        """Run all field inspection SLA checks (cash, MED, inactive agents)."""
        from app.database.connection import db_manager

        try:
            async with db_manager.get_connection() as db:
                from app.modules.inspections.services.field_sla_service import (
                    FieldSLAService,
                )
                sla_service = FieldSLAService()
                results = await sla_service.run_all_checks(db)

                total = (
                    results.get("cash_warnings_sent", 0)
                    + results.get("cash_escalations_sent", 0)
                    + results.get("med_expired_alerts", 0)
                    + results.get("inactive_agent_alerts", 0)
                )
                if total > 0 or results.get("errors"):
                    logger.info(f"Field SLA check: {results}")
                    return results
        except Exception as e:
            if "does not exist" in str(e):
                return None  # Migration not yet applied
            logger.error(f"Field SLA check failed: {e}")
        return None

    async def _mission_daily_reminder(self):
        """Send reminder to agents assigned to tomorrow's planned missions."""
        from app.database.connection import db_manager
        from app.core.events.event_bus import EventBus
        from app.core.events.event_types import EventType

        tomorrow = date.today() + timedelta(days=1)
        dedup_key = f"scheduler:mission_reminder:{tomorrow.isoformat()}"
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            if await cache.get(dedup_key):
                return None
            await cache.set(dedup_key, "1", ttl=72000)
        except Exception:
            pass

        try:
            async with db_manager.get_connection() as db:
                rows = await db.fetch("""
                    SELECT fm.id AS mission_id, fm.mission_date, fm.title, fm.zone_ids,
                           fma.agent_id, fma.target_inspections,
                           u.first_name, u.last_name, u.email, u.phone_number,
                           u.preferred_language
                    FROM field_missions fm
                    JOIN field_mission_agents fma ON fma.mission_id = fm.id
                    JOIN users u ON u.id = fma.agent_id
                    WHERE fm.mission_date = $1
                      AND fm.status = 'planned'
                      AND fma.status = 'assigned'
                      AND u.status = 'active'
                """, tomorrow)

                if not rows:
                    return None

                # Resolve zone names once per mission
                zone_cache: dict = {}
                sent = 0
                for row in rows:
                    mid = str(row["mission_id"])
                    if mid not in zone_cache:
                        zones = await db.fetch(
                            "SELECT name_es FROM commerce_zones WHERE id = ANY($1::uuid[])",
                            row["zone_ids"] or [],
                        )
                        zone_cache[mid] = ", ".join(z["name_es"] for z in zones)

                    EventBus.publish_nowait(EventType.MISSION_REMINDER, {
                        "user_id": str(row["agent_id"]),
                        "user_email": row["email"],
                        "user_phone": row["phone_number"],
                        "preferred_language": row["preferred_language"] or "es",
                        "agent_name": f"{row['first_name']} {row['last_name']}".strip(),
                        "mission_id": mid,
                        "mission_date": str(row["mission_date"]),
                        "mission_title": row["title"] or str(row["mission_date"]),
                        "zone_names": zone_cache[mid],
                        "target_inspections": str(row["target_inspections"] or 10),
                    })
                    sent += 1

                if sent:
                    logger.info(f"Mission reminders sent: {sent} agents for {tomorrow}")
                return {"reminders_sent": sent, "mission_date": str(tomorrow)}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Mission daily reminder failed: {e}")
        return None

    async def _mission_start_alert(self):
        """Alert supervisors about today's missions that haven't started yet.

        Runs daily. Sends push notification if a mission scheduled for today
        is still in 'planned' status (not yet transitioned to in_progress).
        """
        from app.database.connection import db_manager
        from app.core.events.event_bus import EventBus
        from app.core.events.event_types import EventType

        today = date.today()
        dedup_key = f"scheduler:mission_start_alert:{today.isoformat()}"
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            if await cache.get(dedup_key):
                return None
            await cache.set(dedup_key, "1", ttl=72000)
        except Exception:
            pass

        try:
            async with db_manager.get_connection() as db:
                rows = await db.fetch("""
                    SELECT fm.id, fm.title, fm.mission_date, fm.supervisor_id,
                           u.email, u.first_name, u.last_name, u.preferred_language,
                           (SELECT COUNT(*) FROM field_mission_agents
                            WHERE mission_id = fm.id) AS agent_count
                    FROM field_missions fm
                    JOIN users u ON u.id = fm.supervisor_id
                    WHERE fm.mission_date = $1
                      AND fm.status = 'planned'
                """, today)

                sent = 0
                for row in rows:
                    EventBus.publish_nowait(EventType.MISSION_REMINDER, {
                        "user_id": str(row["supervisor_id"]),
                        "user_email": row["email"],
                        "preferred_language": row["preferred_language"] or "es",
                        "agent_name": f"{row['first_name']} {row['last_name']}".strip(),
                        "mission_id": str(row["id"]),
                        "mission_date": str(today),
                        "mission_title": row["title"] or str(today),
                        "zone_names": "",
                        "target_inspections": str(row["agent_count"]),
                    })
                    sent += 1

                if sent:
                    logger.info(f"Mission start alerts: {sent} missions not started today")
                return {"alerts_sent": sent}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Mission start alert failed: {e}")
        return None

    async def _mission_progress_alert(self):
        """Alert supervisors about in-progress missions below 50% target.

        Runs daily (afternoon). Checks missions in_progress today where
        actual inspections < 50% of target.
        """
        from app.database.connection import db_manager
        from app.core.events.event_bus import EventBus
        from app.core.events.event_types import EventType

        today = date.today()
        dedup_key = f"scheduler:mission_progress_alert:{today.isoformat()}"
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            if await cache.get(dedup_key):
                return None
            await cache.set(dedup_key, "1", ttl=72000)
        except Exception:
            pass

        try:
            async with db_manager.get_connection() as db:
                rows = await db.fetch("""
                    SELECT fm.id, fm.title, fm.mission_date, fm.supervisor_id,
                           u.email, u.first_name, u.last_name, u.preferred_language,
                           COALESCE(agg.actual, 0) AS actual,
                           COALESCE(agg.target, 0) AS target
                    FROM field_missions fm
                    JOIN users u ON u.id = fm.supervisor_id
                    LEFT JOIN LATERAL (
                        SELECT SUM(actual_inspections)::int AS actual,
                               SUM(target_inspections)::int AS target
                        FROM field_mission_agents WHERE mission_id = fm.id
                    ) agg ON true
                    WHERE fm.mission_date = $1
                      AND fm.status = 'in_progress'
                      AND COALESCE(agg.target, 0) > 0
                      AND COALESCE(agg.actual, 0)::float / NULLIF(COALESCE(agg.target, 0), 0) < 0.5
                """, today)

                sent = 0
                for row in rows:
                    pct = round(row["actual"] / row["target"] * 100) if row["target"] > 0 else 0
                    EventBus.publish_nowait(EventType.MISSION_REMINDER, {
                        "user_id": str(row["supervisor_id"]),
                        "user_email": row["email"],
                        "preferred_language": row["preferred_language"] or "es",
                        "agent_name": f"{row['first_name']} {row['last_name']}".strip(),
                        "mission_id": str(row["id"]),
                        "mission_date": str(today),
                        "mission_title": f"{row['title'] or today} ({pct}%)",
                        "zone_names": f"{row['actual']}/{row['target']}",
                        "target_inspections": str(row["target"]),
                    })
                    sent += 1

                if sent:
                    logger.info(f"Mission progress alerts: {sent} missions below 50%")
                return {"alerts_sent": sent}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Mission progress alert failed: {e}")
        return None

    async def _mission_stale_cleanup(self):
        """Auto-cancel missions that were planned but never started.

        Runs weekly. Cancels missions where:
        - status = 'planned'
        - mission_date < today - 7 days
        Notifies supervisors of cancelled missions.
        """
        from app.database.connection import db_manager
        from app.core.events.event_bus import EventBus
        from app.core.events.event_types import EventType

        cutoff = date.today() - timedelta(days=7)

        try:
            async with db_manager.get_connection() as db:
                # Find stale missions
                stale = await db.fetch("""
                    SELECT fm.id, fm.title, fm.mission_date, fm.supervisor_id,
                           u.email, u.first_name, u.last_name, u.preferred_language
                    FROM field_missions fm
                    JOIN users u ON u.id = fm.supervisor_id
                    WHERE fm.status = 'planned'
                      AND fm.mission_date < $1
                """, cutoff)

                if not stale:
                    return {"cancelled": 0}

                ids = [row["id"] for row in stale]

                # Cancel them
                await db.execute("""
                    UPDATE field_missions
                    SET status = 'cancelled', updated_at = NOW()
                    WHERE id = ANY($1::uuid[])
                      AND status = 'planned'
                """, ids)

                # Notify supervisors
                for row in stale:
                    EventBus.publish_nowait(EventType.MISSION_CANCELLED, {
                        "user_id": str(row["supervisor_id"]),
                        "user_email": row["email"],
                        "preferred_language": row["preferred_language"] or "es",
                        "agent_name": f"{row['first_name']} {row['last_name']}".strip(),
                        "mission_id": str(row["id"]),
                        "mission_date": str(row["mission_date"]),
                        "mission_title": row["title"] or str(row["mission_date"]),
                        "cancellation_reason": "Auto-cancelled: mission date passed 7+ days ago",
                        "zone_names": "",
                        "target_inspections": "",
                        "agent_count": "",
                    })

                logger.info(f"Mission stale cleanup: {len(stale)} missions auto-cancelled")
                return {"cancelled": len(stale)}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Mission stale cleanup failed: {e}")
        return None

    async def _mission_auto_create(self):
        """Auto-create missions from recurring templates.

        Checks all active templates and creates missions for today if:
        - daily: always
        - weekly: today matches day_of_week
        - biweekly: today matches day_of_week AND week is even
        - monthly: today matches day_of_month

        Skips if mission already exists for that template+date (dedup via last_created_at).
        After creation, auto-assigns default agents if configured.
        """
        from app.database.connection import db_manager
        from app.core.events.event_bus import EventBus
        from app.core.events.event_types import EventType

        today = date.today()
        weekday = today.weekday()  # 0=Monday
        week_number = today.isocalendar()[1]
        day_of_month = today.day

        try:
            async with db_manager.get_connection() as db:
                templates = await db.fetch("""
                    SELECT * FROM mission_templates
                    WHERE is_active = true
                """)

                if not templates:
                    return {"created": 0}

                created = 0
                for tpl in templates:
                    rec = tpl["recurrence"]

                    # Check if today matches the recurrence pattern
                    should_create = False
                    if rec == "daily":
                        should_create = True
                    elif rec == "weekly":
                        should_create = (tpl["day_of_week"] == weekday)
                    elif rec == "biweekly":
                        should_create = (tpl["day_of_week"] == weekday and week_number % 2 == 0)
                    elif rec == "monthly":
                        should_create = (tpl["day_of_month"] == day_of_month)

                    if not should_create:
                        continue

                    # Dedup: skip if already created today
                    if tpl["last_created_at"] and tpl["last_created_at"].date() == today:
                        continue

                    # Validation: check agent availability
                    default_agents = tpl["default_agent_ids"] or []
                    if not default_agents:
                        # No default agents configured — check if any agents available
                        avail_count = await db.fetchval("""
                            SELECT COUNT(*) FROM agent_profiles
                            WHERE entity_id = $1 AND entity_location_id = $2
                              AND is_active = true AND is_supervisor = false
                        """, tpl["entity_id"], tpl["entity_location_id"])
                        if not avail_count or avail_count == 0:
                            logger.warning(
                                f"Template '{tpl['name']}': skipped — no agents available "
                                f"at location {tpl['entity_location_id']}"
                            )
                            continue

                    # Validation: check last mission completion rate
                    if tpl["last_created_mission_id"]:
                        last_stats = await db.fetchrow("""
                            SELECT COALESCE(SUM(actual_inspections), 0) AS actual,
                                   COALESCE(SUM(target_inspections), 0) AS target
                            FROM field_mission_agents
                            WHERE mission_id = $1
                        """, tpl["last_created_mission_id"])
                        if last_stats and last_stats["target"] > 0:
                            last_rate = last_stats["actual"] / last_stats["target"]
                            if last_rate < 0.3:
                                logger.warning(
                                    f"Template '{tpl['name']}': last mission had "
                                    f"{int(last_rate*100)}% completion — creating anyway"
                                )

                    # Check UNIQUE constraint (entity_id, entity_location_id, mission_date)
                    existing = await db.fetchval("""
                        SELECT id FROM field_missions
                        WHERE entity_id = $1 AND entity_location_id = $2 AND mission_date = $3
                    """, tpl["entity_id"], tpl["entity_location_id"], today)

                    if existing:
                        continue

                    # Create mission
                    try:
                        async with db.transaction():
                            mission = await db.fetchrow("""
                                INSERT INTO field_missions (
                                    entity_id, entity_location_id, supervisor_id,
                                    mission_date, title, notes, zone_ids, status
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'planned')
                                ON CONFLICT (entity_id, entity_location_id, mission_date) DO NOTHING
                                RETURNING id
                            """,
                                tpl["entity_id"],
                                tpl["entity_location_id"],
                                tpl["created_by"],
                                today,
                                f"{tpl['name']} ({today.isoformat()})",
                                tpl["notes"],
                                tpl["zone_ids"],
                            )

                            if not mission:
                                # UNIQUE conflict — mission already exists
                                continue

                            mission_id = mission["id"]

                            # Auto-assign default agents
                            agent_ids = tpl["default_agent_ids"] or []
                            for agent_id in agent_ids:
                                # Verify agent is active and available
                                profile = await db.fetchrow("""
                                    SELECT id FROM agent_profiles
                                    WHERE user_id = $1 AND entity_id = $2
                                      AND is_active = true AND is_supervisor = false
                                """, agent_id, tpl["entity_id"])

                                if profile:
                                    # Check no conflict
                                    conflict = await db.fetchval("""
                                        SELECT 1 FROM field_mission_agents fma
                                        JOIN field_missions fm ON fm.id = fma.mission_id
                                        WHERE fma.agent_id = $1 AND fm.mission_date = $2
                                          AND fm.status IN ('planned', 'in_progress')
                                    """, agent_id, today)

                                    if not conflict:
                                        await db.execute("""
                                            INSERT INTO field_mission_agents (
                                                mission_id, agent_id, agent_profile_id,
                                                target_inspections, status
                                            ) VALUES ($1, $2, $3, $4, 'assigned')
                                        """, mission_id, agent_id, profile["id"],
                                            tpl["target_inspections_per_agent"])

                            # Update template last_created
                            await db.execute("""
                                UPDATE mission_templates
                                SET last_created_at = NOW(), last_created_mission_id = $1
                                WHERE id = $2
                            """, mission_id, tpl["id"])

                            created += 1
                            logger.info(
                                f"Auto-created mission from template '{tpl['name']}' "
                                f"({tpl['recurrence']}) for {today}"
                            )

                    except Exception as e:
                        logger.warning(f"Failed to create mission from template {tpl['id']}: {e}")
                        continue

                if created:
                    logger.info(f"Mission auto-create: {created} missions from templates")
                return {"created": created, "templates_checked": len(templates)}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Mission auto-create failed: {e}")
        return None

    async def _inspection_daily_summary(self):
        """Send daily inspection summary email to supervisors (end of day)."""
        from app.database.connection import db_manager

        # Dedup: only send once per day (Redis key with 20h TTL)
        # If Redis is unavailable, SKIP (don't send without dedup guarantee)
        dedup_key = f"scheduler:daily_summary:{date.today().isoformat()}"
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            if await cache.get(dedup_key):
                return None  # Already sent today
            await cache.set(dedup_key, "1", ttl=72000)  # 20h TTL
        except Exception:
            logger.warning("Daily summary: Redis unavailable — SKIPPING to prevent duplicate sends")
            return None

        async with db_manager.get_connection() as db:
            # Get all active supervisors with inspection permissions
            supervisors = await db.fetch("""
                SELECT ap.user_id, u.email, u.full_name,
                       ap.entity_id, e.code AS entity_code
                FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                JOIN entities e ON e.id = ap.entity_id
                WHERE ap.is_supervisor = true AND ap.is_active = true
                  AND u.status = 'active'
                  AND EXISTS (
                      SELECT 1 FROM role_permissions rp
                      JOIN permissions p ON p.id = rp.permission_id
                      WHERE rp.role_id = u.role_id
                        AND p.name = 'inspection.view_entity'
                  )
            """)

            if not supervisors:
                return None

            from app.modules.communications.services.communication_service import (
                CommunicationService,
            )
            from app.modules.communications.models.communication import CommunicationType
            import asyncio as _asyncio

            comm = CommunicationService()
            sent = 0
            today = date.today()

            for sup in supervisors:
                try:
                    # Daily stats for this entity
                    stats = await db.fetchrow("""
                        SELECT
                            COUNT(*)::int AS total_inspections,
                            COUNT(*) FILTER (WHERE result = 'conforme')::int AS conforme,
                            COUNT(*) FILTER (WHERE result = 'non_conforme')::int AS non_conforme,
                            COALESCE(SUM(payment_amount) FILTER (WHERE payment_collected), 0) AS collected,
                            COUNT(*) FILTER (WHERE mise_en_demeure_issued)::int AS med_count,
                            COUNT(*) FILTER (WHERE seal_applied OR status = 'seal_proposed')::int AS seal_count,
                            COUNT(DISTINCT agent_id)::int AS agents_active
                        FROM field_inspections
                        WHERE entity_id = $1 AND inspection_date = $2
                          AND status != 'cancelled'
                    """, sup["entity_id"], today)

                    total = stats["total_inspections"] or 0
                    if total == 0:
                        continue  # No inspections today, skip

                    conf = stats["conforme"] or 0
                    rate = f"{conf * 100 / total:.1f}" if total > 0 else "0"
                    collected = float(stats["collected"] or 0)

                    # Build alerts section
                    alerts_parts = []

                    # Stale zones
                    stale_days = await db.fetchval(
                        "SELECT COALESCE(rule_value::int, 30) FROM system_rules "
                        "WHERE rule_code = 'INSPECTION_ZONE_STALE_DAYS' AND is_active = true"
                    ) or 30
                    stale_zones = await db.fetch("""
                        SELECT cz.zone_code, cz.name_es
                        FROM commerce_zones cz
                        WHERE NOT EXISTS (
                            SELECT 1 FROM field_inspections fi
                            WHERE fi.zone_id = cz.id
                              AND fi.entity_id = $1
                              AND fi.inspection_date > CURRENT_DATE - $2
                              AND fi.status != 'cancelled'
                        )
                    """, sup["entity_id"], stale_days)
                    if stale_zones:
                        zones_list = ", ".join(
                            html_escape(z["zone_code"]) for z in stale_zones[:5]
                        )
                        extra = f" (+{len(stale_zones) - 5} más)" if len(stale_zones) > 5 else ""
                        alerts_parts.append(
                            f"Zonas sin inspección >{stale_days}d: {zones_list}{extra}"
                        )

                    alerts_html = "<br>".join(alerts_parts) if alerts_parts else ""

                    # Fetch template
                    template = await db.fetchrow(
                        "SELECT subject_es, html_content FROM email_templates "
                        "WHERE template_code = 'inspection_daily_summary' AND is_active = true"
                    )
                    if not template:
                        continue

                    # Render template
                    replacements = {
                        "supervisor_name": html_escape(sup["full_name"] or "Supervisor"),
                        "entity_code": html_escape(sup["entity_code"] or ""),
                        "date": today.isoformat(),
                        "total_inspections": str(total),
                        "conforme": str(conf),
                        "non_conforme": str(stats["non_conforme"] or 0),
                        "conformity_rate": rate,
                        "collected_amount": f"{collected:,.0f}",
                        "med_count": str(stats["med_count"] or 0),
                        "seal_count": str(stats["seal_count"] or 0),
                        "agents_active": str(stats["agents_active"] or 0),
                        "alerts": alerts_html,
                    }

                    html = template["html_content"]
                    subject = template["subject_es"]
                    for k, v in replacements.items():
                        html = html.replace("{{" + k + "}}", v)
                        subject = subject.replace("{{" + k + "}}", v)

                    # Handle conditional sections {{#alerts}}...{{/alerts}}
                    if alerts_html:
                        html = html.replace("{{#alerts}}", "").replace("{{/alerts}}", "")
                    else:
                        # Remove the entire alerts block
                        import re
                        html = re.sub(r"\{\{#alerts\}\}.*?\{\{/alerts\}\}", "", html, flags=re.DOTALL)

                    loop = _asyncio.get_running_loop()
                    ok = await loop.run_in_executor(
                        None,
                        lambda: comm.send_communication(
                            channel=CommunicationType.EMAIL,
                            recipient=sup["email"],
                            subject=subject,
                            content=html,
                        ),
                    )
                    if ok:
                        sent += 1

                except Exception as e:
                    logger.error(f"Daily summary failed for {sup.get('email')}: {e}")

            if sent > 0:
                logger.info(f"Inspection daily summaries sent: {sent}")
                return {"daily_summaries_sent": sent}
        return None

    async def _inspection_weekly_digest(self):
        """Send weekly performance digest comparing this week vs last week."""
        from app.database.connection import db_manager

        # Dedup: only send once per week (Redis key with 6-day TTL)
        # If Redis is unavailable, SKIP the job (don't send without dedup guarantee)
        week_key = f"{date.today().isocalendar()[0]}-W{date.today().isocalendar()[1]:02d}"
        dedup_key = f"scheduler:weekly_digest:{week_key}"
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            if await cache.get(dedup_key):
                return None  # Already sent this week
            await cache.set(dedup_key, "1", ttl=518400)  # 6 days TTL
        except Exception:
            logger.warning("Weekly digest: Redis unavailable — SKIPPING to prevent duplicate sends")
            return None  # SKIP instead of proceeding without dedup

        async with db_manager.get_connection() as db:
            supervisors = await db.fetch("""
                SELECT ap.user_id, u.email, u.full_name,
                       ap.entity_id, e.code AS entity_code
                FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                JOIN entities e ON e.id = ap.entity_id
                WHERE ap.is_supervisor = true AND ap.is_active = true
                  AND u.status = 'active'
                  AND EXISTS (
                      SELECT 1 FROM role_permissions rp
                      JOIN permissions p ON p.id = rp.permission_id
                      WHERE rp.role_id = u.role_id
                        AND p.name = 'inspection.view_entity'
                  )
            """)

            if not supervisors:
                return None

            from app.modules.communications.services.communication_service import (
                CommunicationService,
            )
            from app.modules.communications.models.communication import CommunicationType
            import asyncio as _asyncio

            comm = CommunicationService()
            sent = 0
            today = date.today()
            # ISO week number
            week_num = today.isocalendar()[1]
            this_week_start = today - timedelta(days=today.weekday())
            last_week_start = this_week_start - timedelta(days=7)

            for sup in supervisors:
                try:
                    # Compare this week vs last week
                    comparison = await db.fetch("""
                        SELECT
                            CASE
                                WHEN inspection_date >= $2 THEN 'this_week'
                                ELSE 'last_week'
                            END AS period,
                            COUNT(*)::int AS inspections,
                            COUNT(*) FILTER (WHERE result = 'conforme')::int AS conforme,
                            COUNT(*) FILTER (WHERE result = 'non_conforme')::int AS non_conforme,
                            COALESCE(SUM(payment_amount) FILTER (WHERE payment_collected), 0) AS collected,
                            COUNT(*) FILTER (WHERE mise_en_demeure_issued)::int AS med,
                            COUNT(*) FILTER (WHERE seal_applied)::int AS seals,
                            COUNT(DISTINCT agent_id)::int AS agents
                        FROM field_inspections
                        WHERE entity_id = $1
                          AND inspection_date >= $3
                          AND status != 'cancelled'
                        GROUP BY CASE
                            WHEN inspection_date >= $2 THEN 'this_week'
                            ELSE 'last_week'
                        END
                    """, sup["entity_id"], this_week_start, last_week_start)

                    this_w = {"inspections": 0, "conforme": 0, "non_conforme": 0,
                              "collected": 0, "med": 0, "seals": 0, "agents": 0}
                    last_w = dict(this_w)
                    for row in comparison:
                        target = this_w if row["period"] == "this_week" else last_w
                        for k in target:
                            target[k] = row.get(k, 0) or 0

                    if this_w["inspections"] == 0 and last_w["inspections"] == 0:
                        continue

                    # Build comparison rows HTML
                    # Metrics with semantic direction: True = higher is better
                    metrics = [
                        ("Inspecciones", "inspections", True),
                        ("Conformes", "conforme", True),
                        ("No conformes", "non_conforme", False),  # higher = worse
                        ("Monto recaudado (XAF)", "collected", True),
                        ("MED emitidas", "med", False),  # higher = worse
                        ("Scellés", "seals", False),  # higher = worse
                        ("Agentes activos", "agents", True),
                    ]
                    rows_html = ""
                    for label, key, higher_is_good in metrics:
                        tw = this_w[key]
                        lw = last_w[key]
                        if key == "collected":
                            tw_str = f"{float(tw):,.0f}"
                            lw_str = f"{float(lw):,.0f}"
                        else:
                            tw_str = str(int(tw))
                            lw_str = str(int(lw))

                        if lw > 0:
                            pct = ((float(tw) - float(lw)) / float(lw)) * 100
                            arrow = "↑" if pct >= 0 else "↓"
                            # Semantic colors: green = good, red = bad
                            is_positive = (pct >= 0) == higher_is_good
                            color = "#155724" if is_positive else "#b33a3a"
                            var_str = f'<span style="color:{color}">{arrow} {abs(pct):.0f}%</span>'
                        elif tw > 0:
                            is_positive = higher_is_good
                            color = "#155724" if is_positive else "#b33a3a"
                            var_str = f'<span style="color:{color}">↑ new</span>'
                        else:
                            var_str = "—"

                        rows_html += (
                            f'<tr>'
                            f'<td style="padding:8px 12px;border:1px solid #e5e7eb;">'
                            f'{html_escape(label)}</td>'
                            f'<td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;font-weight:bold;">'
                            f'{tw_str}</td>'
                            f'<td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">'
                            f'{lw_str}</td>'
                            f'<td style="padding:8px 12px;border:1px solid #e5e7eb;text-align:right;">'
                            f'{var_str}</td>'
                            f'</tr>'
                        )

                    # Top agents this week
                    top_agents = await db.fetch("""
                        SELECT u.full_name, COUNT(*)::int AS cnt
                        FROM field_inspections fi
                        JOIN users u ON u.id = fi.agent_id
                        WHERE fi.entity_id = $1
                          AND fi.inspection_date >= $2
                          AND fi.status != 'cancelled'
                        GROUP BY u.full_name
                        ORDER BY cnt DESC LIMIT 3
                    """, sup["entity_id"], this_week_start)
                    top_html = ""
                    if top_agents:
                        top_html = ", ".join(
                            f"{html_escape(a['full_name'])} ({a['cnt']})"
                            for a in top_agents
                        )

                    # Stale zones
                    stale_days = await db.fetchval(
                        "SELECT COALESCE(rule_value::int, 30) FROM system_rules "
                        "WHERE rule_code = 'INSPECTION_ZONE_STALE_DAYS' AND is_active = true"
                    ) or 30
                    stale = await db.fetch("""
                        SELECT cz.zone_code FROM commerce_zones cz
                        WHERE NOT EXISTS (
                            SELECT 1 FROM field_inspections fi
                            WHERE fi.zone_id = cz.id AND fi.entity_id = $1
                              AND fi.inspection_date > CURRENT_DATE - $2
                              AND fi.status != 'cancelled'
                        )
                    """, sup["entity_id"], stale_days)
                    stale_html = ", ".join(html_escape(s["zone_code"]) for s in stale[:8]) if stale else ""

                    # Render template
                    template = await db.fetchrow(
                        "SELECT subject_es, html_content FROM email_templates "
                        "WHERE template_code = 'inspection_weekly_digest' AND is_active = true"
                    )
                    if not template:
                        continue

                    replacements = {
                        "supervisor_name": html_escape(sup["full_name"] or "Supervisor"),
                        "entity_code": html_escape(sup["entity_code"] or ""),
                        "week_number": str(week_num),
                        "comparison_rows": rows_html,
                        "top_agents": top_html,
                        "stale_zones": stale_html,
                    }

                    html = template["html_content"]
                    subject = template["subject_es"]
                    for k, v in replacements.items():
                        html = html.replace("{{" + k + "}}", v)
                        subject = subject.replace("{{" + k + "}}", v)

                    # Handle conditional blocks
                    import re
                    for block_key in ("top_agents", "stale_zones"):
                        if replacements.get(block_key):
                            html = html.replace("{{#" + block_key + "}}", "").replace(
                                "{{/" + block_key + "}}", ""
                            )
                        else:
                            html = re.sub(
                                r"\{\{#" + block_key + r"\}\}.*?\{\{/" + block_key + r"\}\}",
                                "", html, flags=re.DOTALL,
                            )

                    loop = _asyncio.get_running_loop()
                    ok = await loop.run_in_executor(
                        None,
                        lambda: comm.send_communication(
                            channel=CommunicationType.EMAIL,
                            recipient=sup["email"],
                            subject=subject,
                            content=html,
                        ),
                    )
                    if ok:
                        sent += 1

                except Exception as e:
                    logger.error(f"Weekly digest failed for {sup.get('email')}: {e}")

            if sent > 0:
                logger.info(f"Inspection weekly digests sent: {sent}")
                return {"weekly_digests_sent": sent}
        return None

    async def _anomaly_detection(self):
        """Detect assignment anomalies: queue spikes, underperformers, imbalances."""
        from app.database.connection import db_manager
        from app.config import get_settings

        settings = get_settings()
        anomalies = []
        actions_taken = []

        async with db_manager.get_connection() as db:
            # 1. Queue spike detection: pending items much higher than normal
            daily_avg = 1.0  # Default for corrective actions
            queue_stats = await db.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE status = 'assigned') AS assigned,
                    COUNT(*) FILTER (WHERE status = 'completed'
                        AND completed_at >= NOW() - INTERVAL '7 days') AS completed_7d
                FROM agent_work_queue
            """)
            if queue_stats:
                pending = queue_stats["pending"] or 0
                completed_7d = queue_stats["completed_7d"] or 0
                daily_avg = completed_7d / 7.0 if completed_7d > 0 else 1.0
                if pending > daily_avg * settings.ANOMALY_QUEUE_SPIKE_MULTIPLIER:
                    anomalies.append(
                        f"QUEUE_SPIKE: {pending} pending vs "
                        f"{daily_avg:.0f}/day avg (>{settings.ANOMALY_QUEUE_SPIKE_MULTIPLIER}x)"
                    )

            # 2. Underperforming agents: success_rate below threshold with enough data
            underperformers = await db.fetch("""
                SELECT awp.agent_profile_id, awp.workflow_code,
                       awp.success_rate, awp.completions_total, awp.escalations_total
                FROM agent_workflow_proficiency awp
                WHERE awp.completions_total + awp.escalations_total >= $1
                  AND awp.success_rate < $2
            """, settings.ESCALATION_PREDICTIVE_MIN_COMPLETIONS,
                settings.ANOMALY_UNDERPERFORMER_THRESHOLD)
            for row in underperformers:
                anomalies.append(
                    f"UNDERPERFORMER: agent {row['agent_profile_id']} "
                    f"workflow={row['workflow_code']} "
                    f"success_rate={row['success_rate']}% "
                    f"({row['completions_total']}C/{row['escalations_total']}E)"
                )

            # 3. Processing time spike: avg much higher than expected
            slow_workflows = await db.fetch("""
                SELECT workflow_code,
                       AVG(avg_processing_hours) AS avg_hours,
                       COUNT(*) AS agent_count
                FROM agent_workflow_proficiency
                WHERE completions_total > 0
                GROUP BY workflow_code
                HAVING AVG(avg_processing_hours) > $1
            """, settings.ANOMALY_PROCESSING_TIME_SPIKE_HOURS)
            for row in slow_workflows:
                anomalies.append(
                    f"SLOW_WORKFLOW: {row['workflow_code']} "
                    f"avg={row['avg_hours']:.1f}h across {row['agent_count']} agents"
                )

            # 4. Rejection patterns: agents with high rejection rate
            rejection_patterns = await db.fetch("""
                SELECT
                    a.agent_profile_id,
                    u.full_name AS agent_name,
                    COUNT(*) FILTER (
                        WHERE srh.new_status::text = 'REJECTED'
                    ) AS rejections,
                    COUNT(*) AS total_actions
                FROM service_request_history srh
                JOIN assignments a ON a.item_id = srh.service_request_id
                    AND a.agent_profile_id IS NOT NULL
                JOIN agent_profiles ap ON ap.id = a.agent_profile_id
                JOIN users u ON u.id = ap.user_id
                WHERE srh.action = 'status_change'
                  AND srh.performed_at >= NOW() - MAKE_INTERVAL(days => $1)
                GROUP BY a.agent_profile_id, u.full_name
                HAVING COUNT(*) >= $2
                   AND COUNT(*) FILTER (
                       WHERE srh.new_status::text = 'REJECTED'
                   ) * 1.0 / COUNT(*) > $3
            """, settings.ANOMALY_REJECTION_LOOKBACK_DAYS,
                settings.ANOMALY_REJECTION_MIN_ACTIONS,
                settings.ANOMALY_REJECTION_RATE_THRESHOLD)
            for row in rejection_patterns:
                anomalies.append(
                    f"REJECTION_PATTERN: {row['agent_name']} "
                    f"{row['rejections']}/{row['total_actions']} rejections in 7 days"
                )

            # 5. Site imbalance: some entities have much more pending than others
            site_imbalance = await db.fetch("""
                SELECT entity_code, COUNT(*) AS pending_count
                FROM agent_work_queue
                WHERE status = 'pending' AND entity_code IS NOT NULL
                GROUP BY entity_code
                ORDER BY pending_count DESC
            """)
            if len(site_imbalance) >= 2:
                max_pending = site_imbalance[0]["pending_count"]
                min_pending = site_imbalance[-1]["pending_count"]
                if max_pending > 0 and min_pending >= 0 and max_pending > min_pending * settings.ANOMALY_SITE_IMBALANCE_MULTIPLIER:
                    anomalies.append(
                        f"SITE_IMBALANCE: {site_imbalance[0]['entity_code']}="
                        f"{max_pending} vs {site_imbalance[-1]['entity_code']}="
                        f"{min_pending}"
                    )

            # 6. Dead-letter items: failed all retries, need manual attention
            dead_count = await db.fetchval(
                "SELECT COUNT(*) FROM assignment_outbox WHERE status = 'dead_letter'"
            )
            if dead_count and dead_count > 0:
                anomalies.append(
                    f"DEAD_LETTER: {dead_count} items failed all retries "
                    f"and need manual attention"
                )

            # === CORRECTIVE ACTIONS ===
            actions_taken = []

            # Action 1: SITE_IMBALANCE → trigger rebalance for overloaded entities
            from app.modules.assignment.services.workload_rebalance_service import (
                rebalance_entity_workload,
            )
            for row in site_imbalance:
                if row["pending_count"] > daily_avg * settings.ANOMALY_QUEUE_SPIKE_MULTIPLIER:
                    try:
                        entity = await db.fetchrow(
                            "SELECT id FROM entities WHERE code = $1",
                            row["entity_code"],
                        )
                        if entity:
                            result = await rebalance_entity_workload(
                                entity_id=entity["id"], db=db, performed_by=None,
                            )
                            if result["reassignments_made"] > 0:
                                actions_taken.append(
                                    f"REBALANCE: {row['entity_code']} "
                                    f"→ {result['reassignments_made']} moved"
                                )
                    except Exception as e:
                        logger.error(
                            f"Auto-rebalance failed for {row['entity_code']}: {e}"
                        )

            # Action 2: UNDERPERFORMER → reduce max_concurrent_assignments
            for row in underperformers:
                try:
                    current_max = await db.fetchval(
                        "SELECT max_concurrent_assignments FROM agent_workloads "
                        "WHERE agent_profile_id = $1",
                        row["agent_profile_id"],
                    )
                    if current_max and current_max > settings.ANOMALY_CAPACITY_MIN_FLOOR:
                        new_max = max(settings.ANOMALY_CAPACITY_MIN_FLOOR, current_max - settings.ANOMALY_CAPACITY_REDUCTION_STEP)
                        await db.execute(
                            "UPDATE agent_workloads "
                            "SET max_concurrent_assignments = $2, last_updated_at = NOW() "
                            "WHERE agent_profile_id = $1",
                            row["agent_profile_id"], new_max,
                        )
                        actions_taken.append(
                            f"CAPACITY_REDUCED: agent {row['agent_profile_id']} "
                            f"max_assignments {current_max} → {new_max}"
                        )
                except Exception as e:
                    logger.error(f"Capacity reduction failed: {e}")

            if actions_taken:
                for act in actions_taken:
                    logger.info(f"Anomaly action: {act}")

        # Store results in Redis cache for supervisor dashboard consumption
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            anomaly_data = {
                "detected_at": datetime.now().isoformat(),
                "anomalies": [
                    {
                        "type": a.split(":")[0].strip(),
                        "message": a,
                        "severity": "critical" if "UNDERPERFORMER" in a or "QUEUE_SPIKE" in a else "warning",
                    }
                    for a in anomalies
                ],
                "count": len(anomalies),
                "actions_taken": actions_taken,
            }
            await cache.set("supervisor:anomalies:latest", anomaly_data, ttl=86400)
        except Exception as e:
            logger.warning(f"Failed to cache anomaly results: {e}")

        if anomalies:
            for a in anomalies:
                logger.warning(f"Anomaly detected: {a}")
            return {"anomalies": anomalies, "count": len(anomalies)}

        # Clear cache when no anomalies
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            await cache.set("supervisor:anomalies:latest", {
                "detected_at": datetime.now().isoformat(),
                "anomalies": [],
                "count": 0,
            }, ttl=86400)
        except Exception:
            pass

        return None

    async def _supervisor_weekly_report(self):
        """Send weekly performance report email to all active supervisors."""
        import asyncio
        import json as json_mod
        from app.database.connection import db_manager
        from app.config import get_settings

        # Dedup: only send once per week (Redis key with 6-day TTL)
        # If Redis unavailable, SKIP to prevent duplicate sends on cold starts
        week_key = f"{date.today().isocalendar()[0]}-W{date.today().isocalendar()[1]:02d}"
        dedup_key = f"scheduler:supervisor_weekly:{week_key}"
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            if await cache.get(dedup_key):
                return None
            await cache.set(dedup_key, "1", ttl=518400)
        except Exception:
            logger.warning("Supervisor weekly: Redis unavailable — SKIPPING")
            return None

        settings = get_settings()

        async with db_manager.get_connection() as db:
            supervisors = await db.fetch("""
                SELECT ap.user_id, u.email, u.full_name, ap.entity_id,
                       e.code as entity_code, e.name as entity_name
                FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                JOIN entities e ON e.id = ap.entity_id
                WHERE ap.is_supervisor = true AND ap.is_active = true
                AND u.status = 'active'
            """)

            if not supervisors:
                return None

            from app.modules.communications.services.communication_service import CommunicationService
            from app.modules.communications.models.communication import CommunicationType

            comm_service = CommunicationService()
            emails_sent = 0
            emails_failed = 0

            for sup in supervisors:
                try:
                    wf_codes = await db.fetchval(
                        "SELECT workflow_codes FROM entities WHERE id = $1", sup['entity_id']
                    )
                    if isinstance(wf_codes, str):
                        wf_codes = json_mod.loads(wf_codes)
                    if not wf_codes:
                        continue

                    stats = await db.fetchrow("""
                        SELECT
                            COUNT(*) FILTER (WHERE sr.created_at >= NOW() - INTERVAL '7 days') as new_requests,
                            COUNT(*) FILTER (
                                WHERE sr.status = 'COMPLETED'
                                AND sr.updated_at >= NOW() - INTERVAL '7 days'
                            ) as completed,
                            COUNT(*) FILTER (WHERE sr.escalated = true) as pending_escalations,
                            COALESCE(AVG(
                                CASE WHEN sr.status = 'COMPLETED'
                                THEN EXTRACT(EPOCH FROM (sr.updated_at - sr.created_at)) / 3600.0
                                ELSE NULL END
                            ), 0) as avg_processing_hours,
                            COUNT(*) FILTER (
                                WHERE sr.status NOT IN ('COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED')
                            ) as active_requests
                        FROM service_requests sr
                        WHERE sr.workflow_code = ANY($1)
                    """, wf_codes)

                    entity_name = html_escape(sup['entity_name'] or sup['entity_code'] or '')
                    sup_name = html_escape(sup['full_name'] or 'Supervisor')
                    avg_hours = round(float(stats['avg_processing_hours'] or 0), 1)
                    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://taxasge.web.app')
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
                                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">Tiempo promedio</td>
                                <td style="padding: 10px; border: 1px solid #e5e7eb; text-align: right;">{avg_hours}h</td>
                            </tr>
                        </table>
                        <p style="font-size: 12px; color: #6b7280;">
                            Este reporte se genera automáticamente cada lunes.
                            <a href="{frontend_url}/dashboard/supervisor">Panel de supervisión</a>
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

            if emails_sent > 0 or emails_failed > 0:
                logger.info(f"Supervisor weekly reports: {emails_sent} sent, {emails_failed} failed")
                return {"emails_sent": emails_sent, "emails_failed": emails_failed}
        return None

    async def _refresh_effective_permissions(self):
        """Refresh the effective_permissions_mv materialized view (CONCURRENTLY)."""
        from app.database.connection import db_manager

        try:
            async with db_manager.get_connection() as db:
                await db.execute("SELECT refresh_effective_permissions()")
            return "refreshed"
        except Exception as e:
            # View may not exist yet (migration not applied)
            if "does not exist" in str(e):
                return None
            raise


    # ================================================================
    # Module crons — call the same logic as HTTP endpoints internally
    # ================================================================

    async def _refresh_company_stats(self):
        """Refresh company dashboard materialized views (every 15 min)."""
        from app.database.connection import db_manager

        views = [
            "mv_company_stats_by_zone",
            "mv_obligation_stats_by_ministry",
            "mv_company_global_stats",
            "mv_company_analytics",
        ]
        refreshed = []
        async with db_manager.get_connection() as db:
            for view in views:
                try:
                    exists = await db.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM pg_matviews WHERE matviewname = $1)",
                        view,
                    )
                    if not exists:
                        continue
                    try:
                        await db.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
                    except Exception:
                        await db.execute(f"REFRESH MATERIALIZED VIEW {view}")
                    refreshed.append(view)
                except Exception as e:
                    if "does not exist" not in str(e):
                        logger.warning(f"Failed to refresh {view}: {e}")
        if refreshed:
            logger.info(f"Company stats MVs refreshed: {', '.join(refreshed)}")
        return {"refreshed": refreshed}

    async def _license_flag_overdue(self):
        """Flag overdue obligations past due_date (daily)."""
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                async with db.transaction():
                    from app.modules.fiscal_services.services.license_service import LicenseService
                    count = await LicenseService.flag_overdue_obligations(db)
                    if count:
                        logger.info(f"License flag-overdue: {count} flagged")
                    return {"flagged": count}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"License flag-overdue failed: {e}")
        return None

    async def _license_apply_penalties(self):
        """Apply penalties on overdue obligations (weekly)."""
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                async with db.transaction():
                    from app.modules.fiscal_services.services.license_service import LicenseService
                    count = await LicenseService.apply_penalties(db)
                    if count:
                        logger.info(f"License penalties applied: {count}")
                    return {"updated": count}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"License apply-penalties failed: {e}")
        return None

    async def _license_obligation_reminders(self):
        """Send tiered obligation reminders (daily)."""
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                from app.modules.fiscal_services.services.oms_reminder_service import OmsReminderService
                svc = OmsReminderService()
                result = await svc.run_reminder_check(db)
                if result and result.get("total_sent"):
                    logger.info(f"Obligation reminders: {result}")
                return result
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Obligation reminders failed: {e}")
        return None

    async def _license_renewal_reminders(self):
        """Send renewal reminders for completed licenses from previous year (daily)."""
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                from app.modules.fiscal_services.services.license_service import LicenseService
                count = await LicenseService.check_renewal_reminders(db)
                if count:
                    logger.info(f"Renewal reminders sent: {count}")
                return {"reminders_sent": count}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Renewal reminders failed: {e}")
        return None

    async def _auth_cleanup(self):
        """Cleanup expired sessions, tokens, and pending registrations (daily)."""
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                r1 = await db.execute("DELETE FROM sessions WHERE expires_at < NOW()")
                r2 = await db.execute("DELETE FROM refresh_tokens WHERE expires_at < NOW()")
                r3 = await db.execute("DELETE FROM pending_registrations WHERE expires_at < NOW()")
                sessions = int(r1.split()[-1]) if r1 else 0
                tokens = int(r2.split()[-1]) if r2 else 0
                regs = int(r3.split()[-1]) if r3 else 0
                total = sessions + tokens + regs
                if total > 0:
                    logger.info(f"Auth cleanup: {sessions} sessions, {tokens} tokens, {regs} registrations")
                return {"sessions": sessions, "tokens": tokens, "registrations": regs}
        except Exception as e:
            logger.error(f"Auth cleanup failed: {e}")
        return None

    async def _cleanup_abandoned_requests(self):
        """Cleanup abandoned DRAFT service requests (daily)."""
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                from app.modules.service_requests.services.service_request_service import ServiceRequestService
                result = await ServiceRequestService.cleanup_abandoned_requests(db)
                if result and result.get("deleted", 0) > 0:
                    logger.info(f"Abandoned requests cleanup: {result}")
                return result
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Abandoned requests cleanup failed: {e}")
        return None

    async def _inspection_auto_approve_seals(self):
        """Auto-approve seal proposals after timeout (daily)."""
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                from app.modules.inspections.services.inspection_service import InspectionService
                svc = InspectionService()
                count = await svc.auto_approve_expired_seals(db)
                if count:
                    logger.info(f"Auto-approved seals: {count}")
                return {"auto_approved": count}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Auto-approve seals failed: {e}")
        return None


    async def _document_intelligence_scan(self):
        """Document Intelligence daily scan — proactive agent (daily).

        Runs 7 operations:
        1. Scan expirations → create tiered alerts (90d, 60d, 30d, 7d, expired)
        2. Create proactive preparations for Level 2 users
        3. Scan missing documents for in-progress service requests
        4. Mark expired documents (status → 'expired')
        5. Purge soft-deleted documents > 30 days (RGPD)
        6. Cleanup stale agent memories
        7. Enforce retention policy (archive > 5 years)
        """
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                from app.modules.user_documents.services.proactive_agent_service import (
                    ProactiveAgentService,
                )
                agent = ProactiveAgentService()
                result = await agent.daily_scan(db)
                if result:
                    total = sum(
                        v for k, v in result.items()
                        if isinstance(v, int) and k != "errors"
                    )
                    if total > 0:
                        logger.info(f"Document intelligence scan: {result}")
                return result
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"Document intelligence scan failed: {e}")
        return None

    async def _request_telemetry_cleanup(self):
        """Phase C.2 — request_telemetry retention + MV refresh.

        Runs every 6h:
        1. Delete raw rows older than 30 days (GDPR/storage)
        2. Refresh mv_request_telemetry_hourly CONCURRENTLY (90-day rollup
           preserved beyond raw retention)
        """
        from app.database.connection import db_manager
        try:
            async with db_manager.get_connection() as db:
                # 1. Drop > 30 days
                deleted = await db.fetchval(
                    "WITH d AS (DELETE FROM request_telemetry "
                    "WHERE \"timestamp\" < now() - interval '30 days' "
                    "RETURNING 1) SELECT count(*) FROM d"
                )
                # 2. Refresh MV (CONCURRENTLY requires unique index — present)
                await db.execute(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_request_telemetry_hourly"
                )
                if deleted and deleted > 0:
                    logger.info(
                        f"request_telemetry cleanup: deleted {deleted} rows >30d, "
                        f"refreshed hourly MV"
                    )
                return {"deleted_rows": deleted}
        except Exception as e:
            if "does not exist" in str(e):
                return None
            logger.error(f"request_telemetry cleanup failed: {e}")
        return None

    async def _geolite_refresh(self):
        """Phase C.4 — refresh GeoLite2-City.mmdb (~80 MB) monthly.

        No-op when MAXMIND_LICENSE_KEY is unset. Runs in a thread to avoid
        blocking the event loop on the ~10s download. After success, the
        next geoip lookup miss will pick up the fresher file (the open
        reader keeps using its mmap'd snapshot until the process restarts —
        acceptable since Cloud Run instances rotate frequently).
        """
        import os
        if not os.environ.get("MAXMIND_LICENSE_KEY"):
            return None
        try:
            from app.core.geoip import _try_auto_download, init_geoip
            target = os.environ.get("GEOIP_DB_PATH") or "/tmp/GeoLite2-City.mmdb"
            ok = await asyncio.to_thread(_try_auto_download, target)
            if ok:
                # Force re-init so a subsequent process restart picks up the fresh DB
                # (current reader keeps the old snapshot mmap'd; benign).
                logger.info("geolite-refresh: refreshed {} successfully", target)
                init_geoip(target)
                return {"refreshed": True, "path": target}
            logger.warning("geolite-refresh: download failed (license key invalid?)")
            return {"refreshed": False}
        except Exception as e:
            logger.error(f"geolite-refresh failed: {e}")
        return None


# Singleton
internal_scheduler = InternalScheduler()
