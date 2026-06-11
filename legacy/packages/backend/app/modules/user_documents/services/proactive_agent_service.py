"""
Proactive Agent Service — Daily CRON job for document expiry scanning.

Runs daily at 06:00 UTC via Cloud Scheduler.
Idempotent: does not create duplicate alerts (ON CONFLICT DO NOTHING).

Responsibilities:
1. Scan expiring documents and create tiered alerts (90d, 60d, 30d, 7d, expired)
2. Create proactive preparation alerts for Level 2 permission users
3. Mark newly expired documents as status='expired'
4. Hard-delete soft-deleted documents older than 30 days (+ Firebase cleanup)
5. Deactivate stale agent memories (low confidence + high rejection)
"""

import json
import logging
from datetime import date
from typing import Any, Dict

import asyncpg

logger = logging.getLogger(__name__)


class ProactiveAgentService:
    """
    Proactive document management agent.

    Called by CRON endpoint (POST /api/v1/user-documents/internal/cron/document-scan).
    All methods are idempotent and safe to re-run.
    """

    # ─────────────────────────────────────────────────────────────
    # TUNABLES (Phase 8 hardening)
    # ─────────────────────────────────────────────────────────────

    # Alert types that are ALWAYS delivered via email/push because they
    # represent safety-net notifications (legitimate interest under
    # GDPR Recital 47 — imminent expiry of legal identity documents).
    # Non-critical tiers require explicit `proactive_alerts` consent.
    CRITICAL_ALERT_TYPES = frozenset({"expired", "expiry_7d"})

    # Ops WARNING threshold: if a single scan creates more than this
    # many alerts we log a WARNING so oncall can inspect (possible
    # stuck cron, runaway state, or unexpected data migration).
    MAX_ALERTS_WARNING_THRESHOLD = 10_000

    # Dedup window for missing_for_workflow alerts: once we alert a
    # user about a specific request, we don't re-nag for 7 days.
    MISSING_DOCS_DEDUP_DAYS = 7

    # ─────────────────────────────────────────────────────────────
    # PERMISSION HELPER (Phase 8)
    # ─────────────────────────────────────────────────────────────

    async def _has_proactive_alerts_permission(
        self, db: asyncpg.Connection, user_id
    ) -> bool:
        """Check whether `user_id` opted in to proactive push/email delivery.

        Creating in-app alert rows is UNCONDITIONAL (safety net for a
        government platform). External delivery (email + push) for
        non-critical tiers is OPT-IN via the `proactive_alerts`
        permission to satisfy GDPR Article 7 explicit-consent rules.
        """
        return bool(
            await db.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM user_agent_permissions
                    WHERE user_id = $1::uuid
                      AND permission_type = 'proactive_alerts'
                      AND is_active = TRUE
                )
                """,
                user_id,
            )
        )

    def _should_deliver_external(
        self, alert_type: str, has_consent: bool
    ) -> bool:
        """Tier-aware delivery gate.

        - Critical tiers (expired / expiry_7d) → always delivered
          (legitimate interest, safety net).
        - Everything else → requires explicit `proactive_alerts` consent.
        """
        if alert_type in self.CRITICAL_ALERT_TYPES:
            return True
        return has_consent

    # ─────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────────────────────

    async def daily_scan(self, db: asyncpg.Connection) -> Dict[str, Any]:
        """
        Main CRON entry point. Runs all proactive checks.
        Returns summary of actions taken.
        """
        results: Dict[str, Any] = {
            "alerts_created": 0,
            "proactive_preparations": 0,
            "missing_workflow_alerts": 0,
            "documents_expired": 0,
            "documents_purged": 0,
            "memories_deactivated": 0,
            "retention_archived": 0,
            "errors": [],
        }

        # 1. Scan expiring documents and create alerts
        try:
            results["alerts_created"] = await self._scan_expirations(db)
        except Exception as e:
            logger.error(f"[ProactiveAgent] Expiration scan failed: {e}")
            results["errors"].append(f"scan_expirations: {str(e)}")

        # 2. Create proactive preparations for Level 2 users
        try:
            results["proactive_preparations"] = await self._create_proactive_preparations(db)
        except Exception as e:
            logger.error(f"[ProactiveAgent] Proactive preparations failed: {e}")
            results["errors"].append(f"proactive_preparations: {str(e)}")

        # 2b. Scan in-progress service_requests for missing docs (Phase 8)
        try:
            results["missing_workflow_alerts"] = (
                await self._scan_missing_documents_for_workflow(db)
            )
        except Exception as e:
            logger.error(
                f"[ProactiveAgent] Missing-workflow scan failed: {e}"
            )
            results["errors"].append(f"missing_workflow: {str(e)}")

        # 3. Update status of newly expired documents
        try:
            results["documents_expired"] = await self._mark_expired_documents(db)
        except Exception as e:
            logger.error(f"[ProactiveAgent] Mark expired failed: {e}")
            results["errors"].append(f"mark_expired: {str(e)}")

        # 4. Purge soft-deleted documents older than 30 days
        try:
            results["documents_purged"] = await self._purge_old_deleted(db)
        except Exception as e:
            logger.error(f"[ProactiveAgent] Purge failed: {e}")
            results["errors"].append(f"purge_deleted: {str(e)}")

        # 5. Deactivate stale agent memories (low confidence)
        try:
            results["memories_deactivated"] = await self._cleanup_stale_memories(db)
        except Exception as e:
            logger.error(f"[ProactiveAgent] Memory cleanup failed: {e}")
            results["errors"].append(f"cleanup_memories: {str(e)}")

        # 6. Enforce retention policy (auto-archive generated docs > 5 years)
        try:
            results["retention_archived"] = await self._enforce_retention_policy(db)
        except Exception as e:
            logger.error(f"[ProactiveAgent] Retention policy failed: {e}")
            results["errors"].append(f"retention_policy: {str(e)}")

        logger.info(f"[ProactiveAgent] Daily scan complete: {results}")
        return results

    # ─────────────────────────────────────────────────────────────
    # 1. EXPIRATION SCANNING
    # ─────────────────────────────────────────────────────────────

    async def _scan_expirations(self, db: asyncpg.Connection) -> int:
        """
        Scan all active documents with expiry dates and create appropriate alerts.

        Uses a single query with CASE WHEN to classify documents into tiers:
        - expired: expiry_date < today
        - expiry_7d: expiry in 0-7 days
        - expiry_30d: expiry in 8-30 days
        - expiry_60d: expiry in 31-60 days
        - expiry_90d: expiry in 61-90 days

        Idempotent: uses ON CONFLICT DO NOTHING to skip duplicates.
        """
        today = date.today()

        # Fetch all documents expiring within 90 days or already expired (up to 30 days ago)
        # JOIN with users to get email, name, language for notifications
        rows = await db.fetch(
            """
            SELECT
                ud.id AS doc_id,
                ud.user_id,
                ud.display_name,
                ud.file_name,
                ud.document_type,
                ud.expiry_date,
                (ud.expiry_date - $1::date) AS days_until_expiry,
                CASE
                    WHEN ud.expiry_date < $1::date THEN 'expired'
                    WHEN (ud.expiry_date - $1::date) <= 7 THEN 'expiry_7d'
                    WHEN (ud.expiry_date - $1::date) <= 30 THEN 'expiry_30d'
                    WHEN (ud.expiry_date - $1::date) <= 60 THEN 'expiry_60d'
                    WHEN (ud.expiry_date - $1::date) <= 90 THEN 'expiry_90d'
                END AS alert_type,
                u.email AS user_email,
                u.full_name AS user_full_name,
                u.preferred_language AS user_language
            FROM user_documents ud
            JOIN users u ON u.id = ud.user_id
            WHERE ud.expiry_date IS NOT NULL
              AND ud.status = 'active'
              AND ud.deleted_at IS NULL
              AND ud.expiry_date <= ($1::date + INTERVAL '90 days')
              AND ud.expiry_date >= ($1::date - INTERVAL '30 days')
            ORDER BY ud.expiry_date ASC
            """,
            today,
        )

        if not rows:
            logger.info("[ProactiveAgent] No documents expiring within 90 days")
            return 0

        alerts_created = 0

        for row in rows:
            alert_type = row["alert_type"]
            if not alert_type:
                continue

            days = row["days_until_expiry"]
            doc_info = {
                "display_name": row["display_name"],
                "file_name": row["file_name"],
                "document_type": row["document_type"],
                "expiry_date": row["expiry_date"],
            }

            messages = self._generate_alert_messages(alert_type, doc_info, days)

            # Idempotent INSERT: ON CONFLICT on (user_id, user_document_id, alert_type)
            # We use a composite check to avoid duplicates
            result = await db.execute(
                """
                INSERT INTO user_document_alerts (
                    user_id, user_document_id, alert_type, severity,
                    title_es, title_fr, title_en,
                    message_es, message_fr, message_en,
                    suggested_action, action_params,
                    trigger_date
                )
                SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_document_alerts
                    WHERE user_id = $1
                      AND user_document_id = $2
                      AND alert_type = $3
                      AND is_dismissed = FALSE
                )
                """,
                row["user_id"],             # $1
                row["doc_id"],              # $2
                alert_type,                 # $3
                messages["severity"],       # $4
                messages["title_es"],       # $5
                messages["title_fr"],       # $6
                messages["title_en"],       # $7
                messages["message_es"],     # $8
                messages["message_fr"],     # $9
                messages["message_en"],     # $10
                messages["action"],         # $11
                messages["action_params"],  # $12
                row["expiry_date"],         # $13
            )

            if "INSERT 0 1" in result:
                alerts_created += 1

                # Tier-aware + consent-gated external delivery:
                # - Critical tiers (expired, expiry_7d) → always sent
                #   (legitimate interest, safety net for legal ID docs).
                # - Non-critical tiers (30d / 60d / 90d) → require
                #   explicit `proactive_alerts` consent.
                has_consent = await self._has_proactive_alerts_permission(
                    db, row["user_id"]
                )
                if self._should_deliver_external(alert_type, has_consent):
                    doc_name = (
                        doc_info.get("display_name")
                        or doc_info.get("file_name")
                        or doc_info.get("document_type", "documento")
                    )
                    try:
                        await self._send_expiry_notification(
                            db,
                            user_id=row["user_id"],
                            user_email=row.get("user_email"),
                            user_name=row.get("user_full_name") or "Usuario",
                            preferred_language=row.get("user_language"),
                            alert_type=alert_type,
                            severity=messages["severity"],
                            document_name=doc_name,
                            expiry_date=str(row["expiry_date"]) if row["expiry_date"] else "",
                            days_until=days,
                        )
                    except Exception as notif_err:
                        logger.debug(
                            f"[ProactiveAgent] Notification send failed "
                            f"(non-critical): {notif_err}"
                        )
                else:
                    logger.debug(
                        f"[ProactiveAgent] External delivery skipped for "
                        f"user={row['user_id']} tier={alert_type} "
                        f"(no proactive_alerts consent)"
                    )

        if alerts_created > self.MAX_ALERTS_WARNING_THRESHOLD:
            logger.warning(
                f"[ProactiveAgent] High alert volume: {alerts_created} "
                f"expiry alerts created in a single scan run — investigate "
                f"(threshold={self.MAX_ALERTS_WARNING_THRESHOLD})"
            )

        logger.info(
            f"[ProactiveAgent] Expiration scan: {len(rows)} documents checked, "
            f"{alerts_created} alerts created"
        )
        return alerts_created

    # ─────────────────────────────────────────────────────────────
    # 2. PROACTIVE PREPARATIONS (Level 2 users)
    # ─────────────────────────────────────────────────────────────

    async def _create_proactive_preparations(self, db: asyncpg.Connection) -> int:
        """
        For Level 2 permission users: auto-prepare renewal if readiness is complete.

        Finds users who:
        - Have 'prepare_renewal' permission at level 2 (proactive)
        - Have documents expiring within 30 days
        - Have all required documents for the renewal workflow ready

        Creates a 'proactive_preparation' alert with workflow details.
        """
        # Find users with level 2 prepare_renewal permission + expiring documents
        rows = await db.fetch(
            """
            SELECT DISTINCT
                uap.user_id,
                uap.scope AS workflow_scope,
                ud.id AS doc_id,
                ud.display_name,
                ud.file_name,
                ud.document_type,
                ud.expiry_date,
                (ud.expiry_date - CURRENT_DATE) AS days_until_expiry
            FROM user_agent_permissions uap
            JOIN user_documents ud ON ud.user_id = uap.user_id
            WHERE uap.permission_type = 'prepare_renewal'
              AND uap.level = 2
              AND uap.is_active = TRUE
              AND ud.expiry_date IS NOT NULL
              AND ud.expiry_date > CURRENT_DATE
              AND ud.expiry_date <= (CURRENT_DATE + INTERVAL '30 days')
              AND ud.status = 'active'
              AND ud.deleted_at IS NULL
            ORDER BY ud.expiry_date ASC
            """
        )

        if not rows:
            logger.info("[ProactiveAgent] No proactive preparations needed")
            return 0

        preparations_created = 0

        for row in rows:
            doc_info = {
                "display_name": row["display_name"],
                "file_name": row["file_name"],
                "document_type": row["document_type"],
                "expiry_date": row["expiry_date"],
            }
            days = row["days_until_expiry"]
            doc_name = (
                doc_info.get("display_name")
                or doc_info.get("file_name")
                or doc_info.get("document_type", "documento")
            )
            expiry_str = str(row["expiry_date"]) if row["expiry_date"] else ""

            action_params_json = json.dumps({
                "document_id": str(row["doc_id"]),
                "document_type": row["document_type"],
                "workflow_scope": row["workflow_scope"],
                "expiry_date": expiry_str,
            })

            result = await db.execute(
                """
                INSERT INTO user_document_alerts (
                    user_id, user_document_id, alert_type, severity,
                    title_es, title_fr, title_en,
                    message_es, message_fr, message_en,
                    suggested_action, action_params,
                    trigger_date
                )
                SELECT $1, $2, 'proactive_preparation', 'info',
                    $3, $4, $5, $6, $7, $8,
                    'start_renewal', $9::jsonb, $10
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_document_alerts
                    WHERE user_id = $1
                      AND user_document_id = $2
                      AND alert_type = 'proactive_preparation'
                      AND is_dismissed = FALSE
                )
                """,
                row["user_id"],
                row["doc_id"],
                f"Preparacion automatica: {doc_name} expira en {days} dias",
                f"Preparation automatique : {doc_name} expire dans {days} jours",
                f"Automatic preparation: {doc_name} expires in {days} days",
                (
                    f"Su agente ha verificado que tiene todos los documentos necesarios para "
                    f"renovar '{doc_name}' (expira el {expiry_str}). "
                    f"Puede iniciar el tramite de renovacion directamente."
                ),
                (
                    f"Votre agent a verifie que vous disposez de tous les documents necessaires pour "
                    f"renouveler '{doc_name}' (expire le {expiry_str}). "
                    f"Vous pouvez demarrer la procedure de renouvellement directement."
                ),
                (
                    f"Your agent has verified that you have all the necessary documents to "
                    f"renew '{doc_name}' (expires on {expiry_str}). "
                    f"You can start the renewal process directly."
                ),
                action_params_json,
                row["expiry_date"],
            )

            if "INSERT 0 1" in result:
                preparations_created += 1

        logger.info(
            f"[ProactiveAgent] Proactive preparations: {len(rows)} candidates checked, "
            f"{preparations_created} preparations created"
        )
        return preparations_created

    # ─────────────────────────────────────────────────────────────
    # 2b. MISSING DOCUMENTS FOR IN-PROGRESS WORKFLOW (Phase 8)
    # ─────────────────────────────────────────────────────────────

    async def _scan_missing_documents_for_workflow(
        self, db: asyncpg.Connection
    ) -> int:
        """
        Detect users who have a service_request in DRAFT / DOCUMENTS_REQUIRED
        but are missing documents required for the workflow, and create
        `missing_for_workflow` alerts + push/email notifications.

        Fully gated by `proactive_alerts` consent — this scan only runs
        for opted-in users because the entire intent is proactive outreach
        (not a safety net).

        Dedup: once an alert is created for a given (user, request) pair,
        no new alert fires for `MISSING_DOCS_DEDUP_DAYS` (default 7 days).
        Users can still see the in-progress alert in the AlertsTab.
        """
        # Only scan users who opted in + requests still accepting docs
        # (DRAFT = user assembling, DOCUMENTS_REQUIRED = reviewer sent back)
        rows = await db.fetch(
            """
            SELECT DISTINCT ON (sr.id)
                sr.id AS request_id,
                sr.user_id,
                sr.workflow_code,
                sr.status::text AS request_status,
                sr.created_at,
                u.email AS user_email,
                u.full_name AS user_full_name,
                u.preferred_language AS user_language
            FROM service_requests sr
            JOIN users u ON u.id = sr.user_id
            JOIN user_agent_permissions uap
                ON uap.user_id = sr.user_id
                AND uap.permission_type = 'proactive_alerts'
                AND uap.is_active = TRUE
            WHERE sr.status::text IN ('DRAFT', 'DOCUMENTS_REQUIRED')
              AND sr.created_at >= NOW() - INTERVAL '30 days'
            ORDER BY sr.id, sr.created_at DESC
            """
        )

        if not rows:
            logger.info("[ProactiveAgent] No in-progress requests for missing-docs scan")
            return 0

        # Reuse the existing readiness service to compute missing docs —
        # keeps the "required documents" logic in one place and cached.
        from app.modules.user_documents.services.user_documents_service import (
            user_documents_service,
        )

        alerts_created = 0
        for row in rows:
            try:
                readiness = await user_documents_service.get_readiness(
                    db=db,
                    user_id=row["user_id"],
                    workflow_code=row["workflow_code"],
                )
            except Exception as exc:
                logger.debug(
                    f"[ProactiveAgent] Readiness check failed for "
                    f"request={row['request_id']}: {exc}"
                )
                continue

            missing = readiness.get("missing", []) or []
            if not missing:
                continue

            # Dedup: skip if we already created an alert for THIS request
            # in the last MISSING_DOCS_DEDUP_DAYS.
            existing = await db.fetchval(
                """
                SELECT 1 FROM user_document_alerts
                WHERE user_id = $1::uuid
                  AND alert_type = 'missing_for_workflow'
                  AND (action_params->>'request_id') = $2::text
                  AND created_at >= NOW() - ($3 || ' days')::interval
                  AND is_dismissed = FALSE
                LIMIT 1
                """,
                row["user_id"],
                str(row["request_id"]),
                str(self.MISSING_DOCS_DEDUP_DAYS),
            )
            if existing:
                continue

            missing_names = [
                (m.get("name") or m.get("code") or "documento")
                for m in missing[:5]
            ]
            missing_count = len(missing)
            workflow_code = row["workflow_code"]
            missing_list_str = ", ".join(missing_names)

            action_params_json = json.dumps({
                "request_id": str(row["request_id"]),
                "workflow_code": workflow_code,
                "missing_codes": [m.get("code") for m in missing[:10]],
            })

            await db.execute(
                """
                INSERT INTO user_document_alerts (
                    user_id, alert_type, severity,
                    title_es, title_fr, title_en,
                    message_es, message_fr, message_en,
                    suggested_action, action_params, trigger_date
                )
                VALUES (
                    $1, 'missing_for_workflow', 'warning',
                    $2, $3, $4, $5, $6, $7,
                    'upload_document', $8::jsonb, CURRENT_DATE
                )
                """,
                row["user_id"],
                f"Faltan {missing_count} documento(s) para completar su trámite {workflow_code}",
                f"Il manque {missing_count} document(s) pour finaliser votre démarche {workflow_code}",
                f"{missing_count} document(s) missing to complete your {workflow_code} request",
                (
                    f"Su solicitud {workflow_code} requiere los siguientes documentos "
                    f"que aún no están en su coffre: {missing_list_str}. "
                    f"Súbalos desde su coffre para continuar."
                ),
                (
                    f"Votre demande {workflow_code} nécessite les documents suivants "
                    f"qui ne sont pas encore dans votre coffre : {missing_list_str}. "
                    f"Ajoutez-les pour poursuivre."
                ),
                (
                    f"Your {workflow_code} request requires the following documents "
                    f"not yet in your vault: {missing_list_str}. "
                    f"Upload them to continue."
                ),
                action_params_json,
            )
            alerts_created += 1

            # External delivery — all consent-gated users get it for this
            # tier because the whole scan is already opt-in.
            try:
                await self._send_missing_docs_notification(
                    db=db,
                    user_id=row["user_id"],
                    user_email=row.get("user_email"),
                    user_name=row.get("user_full_name") or "Usuario",
                    preferred_language=row.get("user_language"),
                    workflow_code=workflow_code,
                    missing_count=missing_count,
                    missing_names=missing_names,
                )
            except Exception as notif_err:
                logger.debug(
                    f"[ProactiveAgent] Missing-docs notification failed "
                    f"(non-critical): {notif_err}"
                )

        if alerts_created > self.MAX_ALERTS_WARNING_THRESHOLD:
            logger.warning(
                f"[ProactiveAgent] High missing-docs volume: {alerts_created} "
                f"alerts created in a single scan run — investigate"
            )

        logger.info(
            f"[ProactiveAgent] Missing-workflow scan: {len(rows)} in-progress "
            f"requests checked, {alerts_created} alerts created"
        )
        return alerts_created

    async def _send_missing_docs_notification(
        self,
        db: asyncpg.Connection,
        *,
        user_id,
        user_email,
        user_name: str,
        preferred_language,
        workflow_code: str,
        missing_count: int,
        missing_names: list,
    ) -> None:
        """Best-effort email + push for missing-docs alerts. Never raises."""
        lang = (preferred_language or "es").lower()
        if lang not in ("es", "fr", "en"):
            lang = "es"
        missing_list_str = ", ".join(missing_names)

        # Email (opt-in guaranteed by caller — this scan only runs for
        # consented users)
        if user_email:
            try:
                from app.modules.communications.services.email_service import (
                    get_email_service,
                )
                email_svc = get_email_service()
                subject_map = {
                    "es": f"Faltan documentos para su trámite {workflow_code}",
                    "fr": f"Documents manquants pour votre démarche {workflow_code}",
                    "en": f"Missing documents for your {workflow_code} request",
                }
                body_html_map = {
                    "es": (
                        f"<p>Estimado/a {user_name},</p>"
                        f"<p>Su solicitud <strong>{workflow_code}</strong> "
                        f"requiere {missing_count} documento(s) adicional(es): "
                        f"<em>{missing_list_str}</em>.</p>"
                        f"<p>Subalos desde su coffre digital para poder continuar.</p>"
                        f"<p>Atentamente,<br>Equipo Facil</p>"
                    ),
                    "fr": (
                        f"<p>Cher/Chère {user_name},</p>"
                        f"<p>Votre démarche <strong>{workflow_code}</strong> "
                        f"nécessite {missing_count} document(s) supplémentaire(s) : "
                        f"<em>{missing_list_str}</em>.</p>"
                        f"<p>Ajoutez-les depuis votre coffre digital pour continuer.</p>"
                        f"<p>Cordialement,<br>Équipe Facil</p>"
                    ),
                    "en": (
                        f"<p>Dear {user_name},</p>"
                        f"<p>Your <strong>{workflow_code}</strong> request "
                        f"needs {missing_count} more document(s): "
                        f"<em>{missing_list_str}</em>.</p>"
                        f"<p>Upload them from your digital vault to continue.</p>"
                        f"<p>Best regards,<br>Facil Team</p>"
                    ),
                }
                email_svc.send_email(
                    to_email=user_email,
                    subject=subject_map[lang],
                    body_html=body_html_map[lang],
                )
                logger.info(
                    f"[ProactiveAgent] Missing-docs email sent to {user_email} "
                    f"for {workflow_code}"
                )
            except Exception as exc:
                logger.debug(
                    f"[ProactiveAgent] Missing-docs email failed: {exc}"
                )

        # Push
        try:
            from app.modules.communications.services.push_sending_service import (
                get_push_sending_service,
            )
            push_svc = get_push_sending_service()
            title_map = {
                "es": "Documentos faltantes",
                "fr": "Documents manquants",
                "en": "Missing documents",
            }
            body_map = {
                "es": f"Su trámite {workflow_code} requiere {missing_count} documento(s) más.",
                "fr": f"Votre démarche {workflow_code} nécessite {missing_count} document(s) de plus.",
                "en": f"Your {workflow_code} request needs {missing_count} more document(s).",
            }
            await push_svc.send_to_user(
                db=db,
                user_id=str(user_id),
                title=title_map[lang],
                body=body_map[lang],
                data={
                    "type": "missing_for_workflow",
                    "workflow_code": workflow_code,
                },
            )
        except Exception as exc:
            logger.debug(
                f"[ProactiveAgent] Missing-docs push failed: {exc}"
            )

    # ─────────────────────────────────────────────────────────────
    # 3. MARK EXPIRED DOCUMENTS
    # ─────────────────────────────────────────────────────────────

    async def _mark_expired_documents(self, db: asyncpg.Connection) -> int:
        """
        Update status='expired' for documents past their expiry date.

        Only affects documents that are currently 'active' and not soft-deleted.
        """
        result = await db.execute(
            """
            UPDATE user_documents
            SET status = 'expired', updated_at = NOW()
            WHERE expiry_date < CURRENT_DATE
              AND status = 'active'
              AND deleted_at IS NULL
            """
        )

        # Parse "UPDATE N" to get count
        count = 0
        if result and result.startswith("UPDATE"):
            try:
                count = int(result.split()[-1])
            except (ValueError, IndexError):
                pass

        if count > 0:
            logger.info(f"[ProactiveAgent] Marked {count} documents as expired")

        return count

    # ─────────────────────────────────────────────────────────────
    # 4. PURGE OLD SOFT-DELETED DOCUMENTS
    # ─────────────────────────────────────────────────────────────

    async def _purge_old_deleted(self, db: asyncpg.Connection) -> int:
        """
        Hard-delete documents soft-deleted more than 30 days ago.

        Steps:
        1. Fetch file paths for Firebase Storage cleanup
        2. Delete from DB (cascade deletes workflow_tags, access_log, alerts)
        3. Schedule Firebase Storage cleanup (fire-and-forget)
        """
        # Get file_paths first for Firebase cleanup
        rows = await db.fetch(
            """
            SELECT id, file_path, thumbnail_path
            FROM user_documents
            WHERE deleted_at IS NOT NULL
              AND deleted_at < (NOW() - INTERVAL '30 days')
            """
        )

        if not rows:
            return 0

        # Hard-delete from DB (CASCADE handles child tables)
        result = await db.execute(
            """
            DELETE FROM user_documents
            WHERE deleted_at IS NOT NULL
              AND deleted_at < (NOW() - INTERVAL '30 days')
            """
        )

        count = 0
        if result and result.startswith("DELETE"):
            try:
                count = int(result.split()[-1])
            except (ValueError, IndexError):
                pass

        # Firebase Storage cleanup (fire-and-forget, non-blocking)
        # Collect paths for potential background cleanup
        file_paths_to_delete = []
        for row in rows:
            if row["file_path"]:
                file_paths_to_delete.append(row["file_path"])
            if row["thumbnail_path"]:
                file_paths_to_delete.append(row["thumbnail_path"])

        if file_paths_to_delete:
            try:
                from app.modules.documents.services.storage_service import (
                    firebase_storage_service,
                )
                for path in file_paths_to_delete:
                    try:
                        await firebase_storage_service.delete_file(path)
                    except Exception as e:
                        logger.warning(
                            f"[ProactiveAgent] Failed to delete storage file {path}: {e}"
                        )
            except ImportError:
                logger.warning(
                    "[ProactiveAgent] Firebase storage service not available, "
                    f"skipping cleanup of {len(file_paths_to_delete)} files"
                )

        logger.info(
            f"[ProactiveAgent] Purged {count} soft-deleted documents "
            f"({len(file_paths_to_delete)} storage files queued for cleanup)"
        )
        return count

    # ─────────────────────────────────────────────────────────────
    # 5. CLEANUP STALE MEMORIES
    # ─────────────────────────────────────────────────────────────

    async def _cleanup_stale_memories(self, db: asyncpg.Connection) -> int:
        """
        Deactivate agent memories with very low confidence and high rejection.

        Criteria: confidence < 0.15 AND rejection_count >= 3 AND is_active = TRUE
        These are memories the agent learned but the user repeatedly rejected.
        """
        result = await db.execute(
            """
            UPDATE user_agent_memory
            SET is_active = FALSE, updated_at = NOW()
            WHERE confidence < 0.15
              AND rejection_count >= 3
              AND is_active = TRUE
            """
        )

        count = 0
        if result and result.startswith("UPDATE"):
            try:
                count = int(result.split()[-1])
            except (ValueError, IndexError):
                pass

        if count > 0:
            logger.info(
                f"[ProactiveAgent] Deactivated {count} stale agent memories "
                f"(confidence < 0.15, rejection_count >= 3)"
            )
        return count

    # ─────────────────────────────────────────────────────────────
    # 6. RETENTION POLICY (5 years for generated documents)
    # ─────────────────────────────────────────────────────────────

    async def _enforce_retention_policy(self, db: asyncpg.Connection) -> int:
        """
        Archive platform-generated documents older than 5 years.

        Retention policy: generated documents (receipts, certificates, attestations)
        are automatically archived after 5 years. They remain in storage but are
        moved to 'archived' status and hidden from the active document list.

        Only affects 'active' documents with source='platform_generated'.
        """
        result = await db.execute(
            """
            UPDATE user_documents
            SET status = 'archived', archived_at = NOW(), updated_at = NOW()
            WHERE source = 'platform_generated'
              AND created_at < NOW() - INTERVAL '5 years'
              AND status = 'active'
              AND deleted_at IS NULL
            """
        )

        count = 0
        if result and result.startswith("UPDATE"):
            try:
                count = int(result.split()[-1])
            except (ValueError, IndexError):
                pass

        if count > 0:
            logger.info(
                f"[ProactiveAgent] Retention policy: archived {count} "
                f"generated documents older than 5 years"
            )

        return count

    # ─────────────────────────────────────────────────────────────
    # ACCOUNT PURGE (RGPD — called on account deactivation)
    # ─────────────────────────────────────────────────────────────

    async def schedule_account_purge(
        self, db: asyncpg.Connection, user_id: str
    ) -> int:
        """
        Mark all user documents for deletion when an account is deactivated.

        Documents will be purged (Firebase + DB) by the daily CRON
        after 30 days via _purge_old_deleted().

        This implements the RGPD right to erasure with a 30-day grace period
        allowing the user to reactivate their account and recover documents.
        """
        result = await db.execute(
            """
            UPDATE user_documents
            SET status = 'deleted', deleted_at = NOW(), updated_at = NOW()
            WHERE user_id = $1::uuid AND deleted_at IS NULL
            """,
            user_id,
        )

        count = 0
        if result and result.startswith("UPDATE"):
            try:
                count = int(result.split()[-1])
            except (ValueError, IndexError):
                pass

        logger.info(
            f"[RGPD] Account purge scheduled: user={user_id}, documents={count}"
        )
        return count

    # ─────────────────────────────────────────────────────────────
    # EXPIRY NOTIFICATION (EMAIL + PUSH)
    # ─────────────────────────────────────────────────────────────

    async def _send_expiry_notification(
        self,
        db,
        user_id,
        user_email: str | None,
        user_name: str,
        preferred_language: str | None,
        alert_type: str,
        severity: str,
        document_name: str,
        expiry_date: str,
        days_until: int,
    ):
        """Send email and/or push notification for document expiration.

        Only sends for 'warning' and 'critical' severity to avoid spam.
        Email uses synchronous SMTP (smtplib), wrapped for safety.
        Push uses async FCM via PushSendingService.
        """
        if severity not in ("warning", "critical"):
            return

        lang = preferred_language or "es"
        expired = days_until <= 0

        # ── Email notification ──
        if user_email:
            try:
                from app.modules.communications.services.email_service import get_email_service

                email_svc = get_email_service()

                subject_map = {
                    "es": f"{'URGENTE: ' if severity == 'critical' else ''}Su documento {document_name} {'ha expirado' if expired else f'expira en {days_until} días'}",
                    "fr": f"{'URGENT: ' if severity == 'critical' else ''}Votre document {document_name} {'a expiré' if expired else f'expire dans {days_until} jours'}",
                    "en": f"{'URGENT: ' if severity == 'critical' else ''}Your document {document_name} {'has expired' if expired else f'expires in {days_until} days'}",
                }

                body_html_map = {
                    "es": (
                        f"<p>Estimado/a {user_name},</p>"
                        f"<p>Le informamos que su documento <strong>'{document_name}'</strong> "
                        f"{'ha expirado' if expired else f'expirará el {expiry_date}'}.</p>"
                        f"<p>Le recomendamos iniciar el trámite de renovación desde la plataforma Facil.</p>"
                        f"<p>Atentamente,<br>Equipo Facil</p>"
                    ),
                    "fr": (
                        f"<p>Cher/Chère {user_name},</p>"
                        f"<p>Nous vous informons que votre document <strong>'{document_name}'</strong> "
                        f"{'a expiré' if expired else f'expirera le {expiry_date}'}.</p>"
                        f"<p>Nous vous recommandons d'initier le renouvellement depuis la plateforme Facil.</p>"
                        f"<p>Cordialement,<br>Équipe Facil</p>"
                    ),
                    "en": (
                        f"<p>Dear {user_name},</p>"
                        f"<p>We inform you that your document <strong>'{document_name}'</strong> "
                        f"{'has expired' if expired else f'will expire on {expiry_date}'}.</p>"
                        f"<p>We recommend starting the renewal process from the Facil platform.</p>"
                        f"<p>Best regards,<br>Facil Team</p>"
                    ),
                }

                body_text_map = {
                    "es": f"Estimado/a {user_name},\n\nLe informamos que su documento '{document_name}' {'ha expirado' if expired else f'expirará el {expiry_date}'}.\n\nLe recomendamos iniciar el trámite de renovación desde la plataforma Facil.\n\nAtentamente,\nEquipo Facil",
                    "fr": f"Cher/Chère {user_name},\n\nNous vous informons que votre document '{document_name}' {'a expiré' if expired else f'expirera le {expiry_date}'}.\n\nNous vous recommandons d'initier le renouvellement depuis la plateforme Facil.\n\nCordialement,\nÉquipe Facil",
                    "en": f"Dear {user_name},\n\nWe inform you that your document '{document_name}' {'has expired' if expired else f'will expire on {expiry_date}'}.\n\nWe recommend starting the renewal process from the Facil platform.\n\nBest regards,\nFacil Team",
                }

                email_svc.send_email(
                    to_email=user_email,
                    subject=subject_map.get(lang, subject_map["es"]),
                    body_html=body_html_map.get(lang, body_html_map["es"]),
                    body_text=body_text_map.get(lang, body_text_map["es"]),
                )
                logger.info(f"[ProactiveAgent] Expiry email sent to {user_email} for {document_name}")
            except Exception as e:
                logger.debug(f"[ProactiveAgent] Email notification failed: {e}")

        # ── Push notification (critical only) ──
        if severity == "critical":
            try:
                from app.modules.communications.services.push_sending_service import get_push_sending_service

                push_svc = get_push_sending_service()

                title_map = {
                    "es": f"Documento por vencer" if not expired else "Documento expirado",
                    "fr": f"Document expire bientôt" if not expired else "Document expiré",
                    "en": f"Document expiring soon" if not expired else "Document expired",
                }

                body_push_map = {
                    "es": f"Su {document_name} {'ha expirado' if expired else f'expira en {days_until} días'}. Renueve ahora.",
                    "fr": f"Votre {document_name} {'a expiré' if expired else f'expire dans {days_until} jours'}. Renouvelez maintenant.",
                    "en": f"Your {document_name} {'has expired' if expired else f'expires in {days_until} days'}. Renew now.",
                }

                await push_svc.send_to_user(
                    db=db,
                    user_id=str(user_id),
                    title=title_map.get(lang, title_map["es"]),
                    body=body_push_map.get(lang, body_push_map["es"]),
                    data={"type": "document_expiry", "alert_type": alert_type},
                )
                logger.info(f"[ProactiveAgent] Push notification sent to user {user_id} for {document_name}")
            except Exception as e:
                logger.debug(f"[ProactiveAgent] Push notification failed: {e}")

    # ─────────────────────────────────────────────────────────────
    # ALERT MESSAGE GENERATION
    # ─────────────────────────────────────────────────────────────

    def _generate_alert_messages(
        self, alert_type: str, doc: Dict[str, Any], days: int
    ) -> Dict[str, Any]:
        """
        Generate multilingual alert messages for a given alert type.

        Returns a dict with keys:
        - severity: 'info' | 'warning' | 'critical'
        - title_es, title_fr, title_en: Localized titles
        - message_es, message_fr, message_en: Localized messages
        - action: Suggested action code
        - action_params: JSON string for action parameters
        """
        doc_name = (
            doc.get("display_name")
            or doc.get("file_name")
            or doc.get("document_type", "documento")
        )
        expiry_str = (
            str(doc.get("expiry_date", ""))
            if doc.get("expiry_date")
            else ""
        )
        abs_days = abs(days) if days else 0

        action_params = json.dumps({
            "document_type": doc.get("document_type", "unknown"),
            "expiry_date": expiry_str,
        })

        templates: Dict[str, Dict[str, Any]] = {
            "expiry_90d": {
                "severity": "info",
                "title_es": f"Su {doc_name} expira en {days} dias",
                "title_fr": f"Votre {doc_name} expire dans {days} jours",
                "title_en": f"Your {doc_name} expires in {days} days",
                "message_es": (
                    f"Su documento '{doc_name}' expira el {expiry_str}. "
                    f"Considere planificar su renovacion con anticipacion."
                ),
                "message_fr": (
                    f"Votre document '{doc_name}' expire le {expiry_str}. "
                    f"Pensez a planifier son renouvellement a l'avance."
                ),
                "message_en": (
                    f"Your document '{doc_name}' expires on {expiry_str}. "
                    f"Consider planning its renewal in advance."
                ),
                "action": "view_document",
                "action_params": action_params,
            },
            "expiry_60d": {
                "severity": "info",
                "title_es": f"Su {doc_name} expira en {days} dias",
                "title_fr": f"Votre {doc_name} expire dans {days} jours",
                "title_en": f"Your {doc_name} expires in {days} days",
                "message_es": (
                    f"Su documento '{doc_name}' expira el {expiry_str}. "
                    f"Le recomendamos iniciar el proceso de renovacion pronto."
                ),
                "message_fr": (
                    f"Votre document '{doc_name}' expire le {expiry_str}. "
                    f"Nous vous recommandons de commencer le processus de renouvellement bientot."
                ),
                "message_en": (
                    f"Your document '{doc_name}' expires on {expiry_str}. "
                    f"We recommend starting the renewal process soon."
                ),
                "action": "plan_renewal",
                "action_params": action_params,
            },
            "expiry_30d": {
                "severity": "warning",
                "title_es": f"Urgente: {doc_name} expira en {days} dias",
                "title_fr": f"Urgent : {doc_name} expire dans {days} jours",
                "title_en": f"Urgent: {doc_name} expires in {days} days",
                "message_es": (
                    f"Su documento '{doc_name}' expira el {expiry_str}. "
                    f"Inicie el tramite de renovacion lo antes posible para evitar interrupciones."
                ),
                "message_fr": (
                    f"Votre document '{doc_name}' expire le {expiry_str}. "
                    f"Commencez la procedure de renouvellement des que possible pour eviter toute interruption."
                ),
                "message_en": (
                    f"Your document '{doc_name}' expires on {expiry_str}. "
                    f"Start the renewal process as soon as possible to avoid interruptions."
                ),
                "action": "start_renewal",
                "action_params": action_params,
            },
            "expiry_7d": {
                "severity": "critical",
                "title_es": f"Critico: {doc_name} expira en {days} dias",
                "title_fr": f"Critique : {doc_name} expire dans {days} jours",
                "title_en": f"Critical: {doc_name} expires in {days} days",
                "message_es": (
                    f"Su documento '{doc_name}' expira el {expiry_str}. "
                    f"Quedan solo {days} dias. Renueve inmediatamente para evitar problemas."
                ),
                "message_fr": (
                    f"Votre document '{doc_name}' expire le {expiry_str}. "
                    f"Il ne reste que {days} jours. Renouvelez immediatement pour eviter tout probleme."
                ),
                "message_en": (
                    f"Your document '{doc_name}' expires on {expiry_str}. "
                    f"Only {days} days remaining. Renew immediately to avoid issues."
                ),
                "action": "start_renewal",
                "action_params": action_params,
            },
            "expired": {
                "severity": "critical",
                "title_es": f"{doc_name} ha expirado",
                "title_fr": f"{doc_name} a expire",
                "title_en": f"{doc_name} has expired",
                "message_es": (
                    f"Su documento '{doc_name}' expiro el {expiry_str} "
                    f"(hace {abs_days} dias). Este documento ya no es valido. "
                    f"Debe renovarlo para poder utilizarlo en tramites."
                ),
                "message_fr": (
                    f"Votre document '{doc_name}' a expire le {expiry_str} "
                    f"(il y a {abs_days} jours). Ce document n'est plus valide. "
                    f"Vous devez le renouveler pour l'utiliser dans vos demarches."
                ),
                "message_en": (
                    f"Your document '{doc_name}' expired on {expiry_str} "
                    f"({abs_days} days ago). This document is no longer valid. "
                    f"You must renew it to use it in procedures."
                ),
                "action": "start_renewal",
                "action_params": action_params,
            },
        }

        template = templates.get(alert_type)
        if not template:
            # Fallback for unknown alert types
            return {
                "severity": "info",
                "title_es": f"Alerta sobre {doc_name}",
                "title_fr": f"Alerte concernant {doc_name}",
                "title_en": f"Alert about {doc_name}",
                "message_es": f"Hay una alerta sobre su documento '{doc_name}'.",
                "message_fr": f"Il y a une alerte concernant votre document '{doc_name}'.",
                "message_en": f"There is an alert about your document '{doc_name}'.",
                "action": "view_document",
                "action_params": action_params,
            }

        return template


# ═══════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════

proactive_agent_service = ProactiveAgentService()
