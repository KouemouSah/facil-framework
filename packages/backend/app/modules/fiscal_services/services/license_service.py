"""License Service — Business logic for commercial licenses (OMS).

Orchestrates: license creation → obligation generation → event logging.
All write operations are transactional.
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import asyncpg

from app.modules.fiscal_services.repositories.license_repository import (
    LicenseRepository,
)
from app.modules.fiscal_services.repositories.bundle_repository import (
    BundleRepository,
)

logger = logging.getLogger(__name__)


class LicenseService:
    """Service layer for commercial licenses and obligations."""

    # ==================================================================
    # License — Read
    # ==================================================================

    @staticmethod
    async def get_license(conn, license_id: UUID) -> Optional[Dict]:
        return await LicenseRepository.get_license(conn, license_id)

    @staticmethod
    async def list_licenses(
        conn,
        company_id: Optional[UUID] = None,
        bundle_id: Optional[UUID] = None,
        fiscal_year: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        # Agent scope filters
        city_id: Optional[UUID] = None,
        fee_type: Optional[str] = None,
        ministry_id: Optional[int] = None,
        processing_mode: Optional[str] = None,
        # Sorting
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ) -> Tuple[List[Dict], int]:
        return await LicenseRepository.list_licenses(
            conn, company_id=company_id, bundle_id=bundle_id,
            fiscal_year=fiscal_year, status=status,
            search=search, page=page, page_size=page_size,
            city_id=city_id, fee_type=fee_type,
            ministry_id=ministry_id, processing_mode=processing_mode,
            sort_by=sort_by, sort_order=sort_order,
        )

    # ==================================================================
    # License — Open (atomic: license + obligations + events)
    # ==================================================================

    @staticmethod
    async def open_license(
        conn, data: Dict, user_id: Optional[UUID] = None
    ) -> Dict:
        """Open a new commercial license dossier.

        MUST be called inside a transaction (route wraps with db.transaction()).

        Steps:
        1. Validate company exists and is active
        2. Verify no duplicate (company × bundle × year) — DB UNIQUE as safety net
        3. Fetch bundle config (processing_mode, deadline)
        4. Fetch items for the zone (pricing)
        5. Compute total_amount, deadline
        6. INSERT license
        7. INSERT obligations (bulk) with penalty/deadline config snapshots
        8. LOG events (license_created + batch obligation_created)
        9. Auto-check previous year compliance (non-blocking, informational)
        """
        company_id = data["company_id"]
        bundle_id = data["bundle_id"]
        zone_id = data["zone_id"]
        fiscal_year = data["fiscal_year"]

        # 1. Validate company exists
        company = await conn.fetchrow(
            "SELECT id, is_active, legal_name FROM companies WHERE id = $1",
            company_id,
        )
        if not company:
            raise ValueError(f"Company {company_id} not found")
        if not company["is_active"]:
            raise ValueError(
                f"Company '{company['legal_name']}' is inactive"
            )

        # 2. Fetch bundle
        bundle = await BundleRepository.get_bundle(conn, bundle_id)
        if not bundle:
            raise ValueError(f"Bundle {bundle_id} not found")
        if not bundle.get("is_active"):
            raise ValueError(f"Bundle {bundle_id} is inactive")

        # 3. Fetch items for the zone
        items = await BundleRepository.get_bundle_items(conn, bundle_id, zone_id)
        if not items:
            raise ValueError(
                f"No items found for bundle {bundle_id} in zone {zone_id}. "
                f"Verify zone has pricing configured."
            )

        # 4. Compute totals
        total_amount = sum(Decimal(str(item["amount"])) for item in items)
        deadline_month = bundle.get("deadline_month", 4)
        deadline_day = bundle.get("deadline_day", 30)
        try:
            deadline = date(fiscal_year, deadline_month, deadline_day)
        except ValueError:
            import calendar
            last_day = calendar.monthrange(fiscal_year, deadline_month)[1]
            deadline = date(fiscal_year, deadline_month, min(deadline_day, last_day))

        processing_mode = bundle.get("processing_mode", "per_line")

        # 5. Create license — DB UNIQUE constraint is the real safety net for races
        try:
            license_data = {
                "company_id": company_id,
                "bundle_id": bundle_id,
                "zone_id": zone_id,
                "city_id": data.get("city_id"),
                "fiscal_year": fiscal_year,
                "service_request_id": data.get("service_request_id"),
                "processing_mode": processing_mode,
                "total_amount": total_amount,
                "obligations_total": len(items),
                "deadline": deadline,
            }
            license_row = await LicenseRepository.create_license(
                conn, license_data, user_id
            )
        except asyncpg.UniqueViolationError:
            raise ValueError(
                f"License already exists for company {company_id}, "
                f"bundle {bundle_id}, fiscal year {fiscal_year}"
            )

        license_id = license_row["id"]

        # 6. Generate obligations from items with config snapshots
        obligation_items = []
        for item in items:
            obligation_items.append({
                "bundle_item_id": item["id"],
                "fiscal_service_id": item["fiscal_service_id"],
                "ministry_id": item.get("ministry_id"),
                "fee_type": item.get("fee_type", "tesoro"),
                "amount": item["amount"],
                "due_date": deadline,
                "penalty_config": item.get("effective_penalty"),
                "deadline_config": item.get("effective_deadline"),
            })

        obligations = await LicenseRepository.create_obligations_batch(
            conn, license_id, obligation_items
        )

        # 7. Log events
        await LicenseRepository.log_event(
            conn, license_id, "license_created",
            event_data={
                "fiscal_year": fiscal_year,
                "total_amount": str(total_amount),
                "obligations_count": len(obligations),
                "processing_mode": processing_mode,
                "zone_id": str(zone_id),
                "company_name": company["legal_name"],
            },
            triggered_by=user_id,
        )

        if obligations:
            await LicenseRepository.log_events_batch(
                conn, license_id, "obligation_created",
                [
                    {
                        "obligation_id": obl["id"],
                        "event_data": {
                            "fee_type": obl["fee_type"],
                            "amount": str(obl["amount"]),
                            "fiscal_service_id": obl["fiscal_service_id"],
                        },
                    }
                    for obl in obligations
                ],
                triggered_by=user_id,
            )

        # 8. Auto-check previous year compliance (non-blocking for new companies)
        try:
            await LicenseService.check_previous_year_compliance(
                conn, license_id
            )
        except Exception as e:
            logger.warning(
                f"Previous year check failed for license {license_id}: {e}"
            )

        logger.info(
            f"License opened: {license_id} — {len(obligations)} obligations, "
            f"total={total_amount} XAF, deadline={deadline}"
        )

        # 9. Collect notification data for caller to emit AFTER transaction commits.
        # IMPORTANT: PDF generation involves sync I/O and must NOT run inside the
        # transaction scope (holds the DB connection open). The caller emits the
        # event after `async with db.transaction()` exits.
        try:
            owner = await conn.fetchrow(
                """SELECT u.id, u.email, u.phone_number, u.first_name, u.last_name
                   FROM users u
                   JOIN user_company_roles ucr ON ucr.user_id = u.id
                   WHERE ucr.company_id = $1
                   ORDER BY ucr.assigned_at ASC LIMIT 1""",
                company_id,
            )

            license_ref = f"LIC-{fiscal_year}-{str(license_id)[:8].upper()}"

            if owner and owner["email"]:
                license_row["_notification"] = {
                    "license_id": str(license_id),
                    "user_id": str(owner["id"]),
                    "user_email": owner["email"],
                    "user_phone": owner["phone_number"],
                    "user_name": f"{owner['first_name'] or ''} {owner['last_name'] or ''}".strip(),
                    "company_name": company["legal_name"],
                    "license_ref": license_ref,
                    "fiscal_year": str(fiscal_year),
                    "nif": data.get("nif") or "",
                    "total_amount": str(total_amount),
                    "status": "Pendiente",
                }
        except Exception as evt_err:
            logger.warning(f"Failed to collect notification data: {evt_err}")

        return license_row

    # ==================================================================
    # License — Admin Update (with event logging)
    # ==================================================================

    @staticmethod
    async def update_license_admin(
        conn, license_id: UUID, new_status: str,
        user_id: Optional[UUID] = None,
    ) -> Optional[Dict]:
        """Admin update: status changes (suspend, close) with audit trail.

        Only allows status changes. Counter fields (amount_paid, obligations_paid)
        are managed exclusively by update_license_counters — never directly.
        """
        existing = await LicenseRepository.get_license(conn, license_id)
        if not existing:
            return None

        # Extract raw string value if enum
        if hasattr(new_status, "value"):
            new_status = new_status.value

        old_status = existing["status"]
        if new_status == old_status:
            return existing

        # Validate admin transitions
        admin_transitions = {
            "open": ["suspended", "closed"],
            "partial": ["suspended", "closed"],
            "complete": ["closed"],
            "overdue": ["suspended", "closed"],
            "suspended": ["open"],  # reactivate
            "closed": [],  # terminal
        }
        allowed = admin_transitions.get(old_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Admin cannot transition {old_status} → {new_status}. "
                f"Allowed: {allowed}"
            )

        update_data = {"status": new_status}
        if new_status == "closed":
            update_data["closed_at"] = datetime.now(timezone.utc)

        result = await LicenseRepository.update_license(
            conn, license_id, update_data
        )

        # Log the admin action with precise event_type
        event_map = {
            "suspended": "license_suspended",
            "closed": "config_changed",
        }
        event_type = event_map.get(new_status, "config_changed")
        await LicenseRepository.log_event(
            conn, license_id, event_type,
            event_data={
                "old_status": old_status,
                "new_status": new_status,
                "admin_action": True,
            },
            triggered_by=user_id,
        )

        return result

    # ==================================================================
    # License — Update Counters (after obligation status changes)
    # ==================================================================

    @staticmethod
    async def update_license_counters(
        conn, license_id: UUID, user_id: Optional[UUID] = None
    ) -> Dict:
        """Recalculate license counters from obligation statuses.

        Called ONLY by internal methods after obligation status changes.
        Never exposed directly via API.
        """
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status IN ('paid','processing','completed')) as paid,
                COUNT(*) FILTER (WHERE status = 'overdue') as overdue,
                COALESCE(SUM(amount) FILTER (WHERE status IN ('paid','processing','completed')), 0) as amount_paid,
                COALESCE(SUM(penalty_amount), 0) as penalty_total
            FROM license_obligations
            WHERE license_id = $1
        """, license_id)

        paid = row["paid"]
        overdue = row["overdue"]
        amount_paid = row["amount_paid"]
        penalty_total = row["penalty_total"]

        license_row = await LicenseRepository.get_license(conn, license_id)
        if not license_row:
            raise ValueError(f"License {license_id} not found")

        old_status = license_row["status"]
        total = license_row["obligations_total"]

        # Keep suspended/closed (admin-controlled, not auto)
        if old_status in ("suspended", "closed"):
            new_status = old_status
        elif paid >= total and total > 0:
            new_status = "complete"
        elif paid > 0:
            new_status = "partial"
        elif overdue > 0:
            new_status = "overdue"
        else:
            new_status = "open"

        update_data = {
            "obligations_paid": paid,
            "obligations_overdue": overdue,
            "amount_paid": amount_paid,
            "penalty_amount": penalty_total,
        }
        if new_status != old_status:
            update_data["status"] = new_status

        if new_status == "complete" and old_status != "complete":
            update_data["completed_at"] = datetime.now(timezone.utc)

        updated = await LicenseRepository.update_license(
            conn, license_id, update_data
        )

        # Log status transition if changed
        if new_status != old_status:
            if new_status == "complete":
                event_type = "license_completed"
            elif new_status == "overdue":
                event_type = "overdue_flagged"
            else:
                event_type = "config_changed"

            await LicenseRepository.log_event(
                conn, license_id, event_type,
                event_data={
                    "old_status": old_status,
                    "new_status": new_status,
                    "paid": paid,
                    "total": total,
                },
                triggered_by=user_id,
            )

            # When license completes, also complete the linked service_request
            if new_status == "complete" and license_row.get("service_request_id"):
                sr_id = license_row["service_request_id"]
                await conn.execute(
                    """UPDATE service_requests
                       SET status = 'COMPLETED', updated_at = NOW(),
                           completed_at = NOW()
                       WHERE id = $1
                         AND status != 'COMPLETED'""",
                    sr_id,
                )
                logger.info(
                    "License %s completed → service_request %s → COMPLETED",
                    license_id,
                    sr_id,
                )

            # When license completes, trigger PDF generation + email notification
            # Runs AFTER the transaction commits (deferred via event).
            if new_status == "complete":
                try:
                    from app.core.events import EventBus, EventType
                    company_id = license_row.get("company_id")
                    owner = await conn.fetchrow("""
                        SELECT u.id, u.email, u.first_name, u.last_name
                        FROM users u
                        JOIN user_company_roles ucr ON ucr.user_id = u.id
                        WHERE ucr.company_id = $1
                        ORDER BY ucr.assigned_at ASC LIMIT 1
                    """, company_id) if company_id else None

                    owner_name = (
                        f"{owner['first_name'] or ''} "
                        f"{owner['last_name'] or ''}".strip()
                    ) if owner else None

                    EventBus.publish_nowait(EventType.LICENSE_COMPLETED, {
                        "license_id": str(license_id),
                        "company_id": str(company_id) if company_id else None,
                        "service_request_id": str(
                            license_row.get("service_request_id") or ""
                        ),
                        # Standard keys for notification_handler (user_email, user_name)
                        "user_email": owner["email"] if owner else None,
                        "user_name": owner_name,
                        "owner_email": owner["email"] if owner else None,
                        "owner_name": owner_name,
                        "total_amount": float(amount_paid),
                        "fiscal_year": license_row.get("fiscal_year"),
                        # Template variables for LICENSE_GENERATED
                        "company_name": license_row.get("company_name", ""),
                        "license_ref": f"LIC-{license_row.get('fiscal_year')}-{str(license_id)[:8].upper()}",
                        "status": "Completada",
                    })
                    logger.info(
                        "LICENSE_COMPLETED event published for license %s "
                        "(PDF + email deferred)",
                        license_id,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to publish LICENSE_COMPLETED event for %s: %s",
                        license_id, e,
                    )

        return updated

    # ==================================================================
    # Obligations — Read
    # ==================================================================

    @staticmethod
    async def list_obligations(
        conn,
        license_id: UUID,
        fee_type: Optional[str] = None,
        ministry_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Tuple[List[Dict], int, Dict]:
        """Returns (items, total, kpis) where kpis are aggregated from ALL
        matching obligations (not just the current page)."""
        return await LicenseRepository.list_obligations(
            conn, license_id, fee_type=fee_type,
            ministry_id=ministry_id, status=status,
            page=page, page_size=page_size,
        )

    @staticmethod
    async def get_obligation(conn, obligation_id: UUID) -> Optional[Dict]:
        return await LicenseRepository.get_obligation(conn, obligation_id)

    @staticmethod
    async def get_obligations_summary(conn, license_id: UUID) -> Dict:
        """Get obligations grouped by fee_type with sub-totals."""
        return await LicenseRepository.get_obligations_grouped_by_fee_type(
            conn, license_id
        )

    # ==================================================================
    # Obligations — Status Update (single)
    # ==================================================================

    @staticmethod
    async def update_obligation_status(
        conn,
        obligation_id: UUID,
        data: Dict,
        user_id: Optional[UUID] = None,
        expected_license_id: Optional[UUID] = None,
        _skip_counter_refresh: bool = False,
    ) -> Optional[Dict]:
        """Update obligation status with event logging and counter refresh.

        Args:
            expected_license_id: If provided, verifies the obligation belongs
                to this license (IDOR protection).
            _skip_counter_refresh: Internal flag for batch operations —
                caller handles counter refresh once at the end.
        """
        existing = await LicenseRepository.get_obligation(conn, obligation_id)
        if not existing:
            return None

        # IDOR protection: verify obligation belongs to the expected license
        if expected_license_id and existing["license_id"] != expected_license_id:
            raise ValueError(
                f"Obligation {obligation_id} does not belong to "
                f"license {expected_license_id}"
            )

        new_status = data.get("status")
        old_status = existing["status"]

        # Validate transition
        valid_transitions = {
            "pending": ["selected", "overdue", "waived", "cancelled", "completed", "processing"],
            "selected": ["pending", "payment_pending", "cancelled"],
            "payment_pending": ["paid", "pending", "cancelled"],
            "paid": ["processing", "completed"],
            "processing": ["completed", "paid"],
            "completed": [],  # terminal
            "overdue": ["pending", "paid", "waived", "cancelled", "completed", "processing"],
            "waived": [],     # terminal
            "cancelled": [],  # terminal
        }

        if new_status and new_status != old_status:
            if hasattr(new_status, "value"):
                new_status = new_status.value
            allowed = valid_transitions.get(old_status, [])
            if new_status not in allowed:
                raise ValueError(
                    f"Invalid transition: {old_status} → {new_status}. "
                    f"Allowed: {allowed}"
                )

        # Update
        updated = await LicenseRepository.update_obligation_status(
            conn, obligation_id, data
        )
        if not updated:
            return None

        # Log event — map status to event_type
        event_map = {
            "selected": "payment_initiated",
            "payment_pending": "payment_initiated",
            "paid": "payment_validated",
            "processing": "obligation_routed",
            "completed": "obligation_completed",
            "overdue": "overdue_flagged",
            "waived": "waived",
            "cancelled": "config_changed",
        }
        event_type = event_map.get(new_status)
        if event_type and new_status != old_status:
            await LicenseRepository.log_event(
                conn, existing["license_id"], event_type,
                event_data={
                    "old_status": old_status,
                    "new_status": new_status,
                    "amount": str(existing["amount"]),
                    "fee_type": existing["fee_type"],
                    "service_code": existing.get("service_code"),
                },
                obligation_id=obligation_id,
                triggered_by=user_id,
            )

        # Refresh parent license counters (unless batch caller handles it)
        if not _skip_counter_refresh:
            await LicenseService.update_license_counters(
                conn, existing["license_id"], user_id
            )

        return updated

    # ==================================================================
    # Obligations — Batch Status Update
    # ==================================================================

    @staticmethod
    async def batch_update_obligation_status(
        conn,
        license_id: UUID,
        obligation_ids: List[UUID],
        data: Dict,
        user_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Update multiple obligations at once (e.g., grouped payment).

        All obligations must belong to the specified license (IDOR protection).
        All must support the same status transition.
        Counter refresh is done once at the end (not per obligation).
        """
        if not obligation_ids:
            raise ValueError("No obligation IDs provided")

        # Verify license exists
        license_row = await LicenseRepository.get_license(conn, license_id)
        if not license_row:
            raise ValueError(f"License {license_id} not found")

        results = []
        for obl_id in obligation_ids:
            result = await LicenseService.update_obligation_status(
                conn, obl_id, data.copy(),
                user_id=user_id,
                expected_license_id=license_id,
                _skip_counter_refresh=True,
            )
            if result:
                results.append(result)

        # Single counter refresh for the whole batch
        if results:
            await LicenseService.update_license_counters(
                conn, license_id, user_id
            )

        logger.info(
            f"Batch update: {len(results)}/{len(obligation_ids)} obligations "
            f"updated for license {license_id}"
        )
        return results

    # ==================================================================
    # Previous Year Compliance Check
    # ==================================================================

    @staticmethod
    async def check_previous_year_compliance(
        conn, license_id: UUID
    ) -> int:
        """Check if same obligations were paid in previous fiscal year.

        Non-blocking, informational only. Never blocks license creation.

        Returns:
          - For new companies: 0 (all obligations marked as checked, NULL paid)
          - For existing companies: count of obligations with data
        """
        license_row = await LicenseRepository.get_license(conn, license_id)
        if not license_row:
            return 0

        prev_year = license_row["fiscal_year"] - 1
        company_id = license_row["company_id"]
        bundle_id = license_row["bundle_id"]

        # Find previous year's license
        prev_license = await LicenseRepository.get_license_by_scope(
            conn, company_id, bundle_id, prev_year
        )

        if not prev_license:
            # New company or first year — mark as checked with NULL (no data)
            rows = await conn.fetch("""
                UPDATE license_obligations
                SET previous_year_checked_at = NOW()
                WHERE license_id = $1 AND previous_year_checked_at IS NULL
                RETURNING id
            """, license_id)
            return len(rows)

        # For each obligation, check if same bundle_item was paid in prev year
        rows = await conn.fetch("""
            UPDATE license_obligations lo
            SET previous_year_paid = (
                SELECT prev.status IN ('paid', 'completed', 'processing')
                FROM license_obligations prev
                WHERE prev.license_id = $2
                  AND prev.bundle_item_id = lo.bundle_item_id
                LIMIT 1
            ),
            previous_year_checked_at = NOW()
            WHERE lo.license_id = $1
              AND lo.previous_year_checked_at IS NULL
            RETURNING id, previous_year_paid
        """, license_id, prev_license["id"])

        paid_count = sum(1 for r in rows if r["previous_year_paid"] is True)
        unpaid_count = sum(1 for r in rows if r["previous_year_paid"] is False)
        new_items = sum(1 for r in rows if r["previous_year_paid"] is None)

        logger.info(
            f"Previous year check for license {license_id}: "
            f"{paid_count} paid, {unpaid_count} unpaid, {new_items} new items"
        )

        return len(rows)

    # ==================================================================
    # License — Renewal
    # ==================================================================

    @staticmethod
    async def renew_license(
        conn,
        prev_license_id: UUID,
        new_fiscal_year: int,
        user_id: Optional[UUID] = None,
    ) -> Dict:
        """Renew a license for a new fiscal year.

        Creates a new dossier from current bundle items (not copied from prev).
        Auto-populates previous_year_paid from the old dossier.
        """
        prev = await LicenseRepository.get_license(conn, prev_license_id)
        if not prev:
            raise ValueError(f"Previous license {prev_license_id} not found")

        if prev["fiscal_year"] >= new_fiscal_year:
            raise ValueError(
                f"New fiscal year ({new_fiscal_year}) must be greater than "
                f"previous ({prev['fiscal_year']})"
            )

        # Create new license via open_license (handles all validation + items)
        data = {
            "company_id": prev["company_id"],
            "bundle_id": prev["bundle_id"],
            "zone_id": prev["zone_id"],
            "city_id": prev.get("city_id"),
            "fiscal_year": new_fiscal_year,
        }

        new_license = await LicenseService.open_license(conn, data, user_id)

        # Log renewal event on the old license
        await LicenseRepository.log_event(
            conn, prev_license_id, "license_renewed",
            event_data={
                "new_license_id": str(new_license["id"]),
                "new_fiscal_year": new_fiscal_year,
            },
            triggered_by=user_id,
        )

        logger.info(
            f"License renewed: {prev_license_id} → {new_license['id']} "
            f"(FY {prev['fiscal_year']} → {new_fiscal_year})"
        )

        return new_license

    # ==================================================================
    # Overdue Detection (cron)
    # ==================================================================

    @staticmethod
    async def flag_overdue_obligations(conn) -> int:
        """Flag obligations past due_date as overdue.

        Called by a daily cron job. Returns count of newly flagged obligations.
        Uses batch event logging (no N+1).
        """
        rows = await conn.fetch("""
            UPDATE license_obligations
            SET status = 'overdue'
            WHERE status = 'pending'
              AND due_date IS NOT NULL
              AND due_date < CURRENT_DATE
            RETURNING id, license_id, amount, fee_type
        """)

        if not rows:
            return 0

        # Group by license for batch event logging
        by_license = defaultdict(list)
        for row in rows:
            by_license[row["license_id"]].append(row)

        # Batch log events + refresh counters per license
        for lic_id, lic_rows in by_license.items():
            await LicenseRepository.log_events_batch(
                conn, lic_id, "overdue_flagged",
                [
                    {
                        "obligation_id": r["id"],
                        "event_data": {
                            "amount": str(r["amount"]),
                            "fee_type": r["fee_type"],
                        },
                    }
                    for r in lic_rows
                ],
            )
            await LicenseService.update_license_counters(conn, lic_id)

        # Notify citizen owners (async, best-effort)
        try:
            from app.core.events import EventBus, EventType
            for lic_id, lic_rows in by_license.items():
                owner = await conn.fetchrow("""
                    SELECT u.email, u.first_name, u.last_name, c.legal_name
                    FROM users u
                    JOIN user_company_roles ucr ON ucr.user_id = u.id
                    JOIN commercial_licenses cl ON cl.company_id = ucr.company_id
                    WHERE cl.id = $1 AND ucr.role = 'company_owner'
                    LIMIT 1
                """, lic_id)
                if owner and owner["email"]:
                    total = sum(float(r["amount"]) for r in lic_rows)
                    EventBus.publish_nowait(EventType.OBLIGATION_OVERDUE, {
                        "license_id": str(lic_id),
                        "user_email": owner["email"],
                        "user_name": f"{owner['first_name'] or ''} {owner['last_name'] or ''}".strip(),
                        "company_name": owner["legal_name"],
                        "obligations_count": len(lic_rows),
                        "total_amount": total,
                    })
        except Exception as e:
            logger.warning(f"Failed to publish OBLIGATION_OVERDUE events: {e}")

        logger.info(
            f"Overdue check: {len(rows)} obligations flagged, "
            f"{len(by_license)} licenses affected"
        )
        return len(rows)

    # ==================================================================
    # Penalty Calculation (cron)
    # ==================================================================

    @staticmethod
    async def apply_penalties(conn) -> int:
        """Calculate and apply penalties on overdue obligations.

        Uses the snapshotted penalty_config on each obligation.
        Called by a periodic cron job (e.g., weekly or monthly).

        Guard: only runs if PENALTIES_ENABLED env var is 'true' (default: false).
        Each obligation's penalty_config must also have rate > 0.
        """
        from app.config import get_settings
        settings = get_settings()
        if not getattr(settings, 'PENALTIES_ENABLED', False):
            logger.info("Penalties cron: DISABLED (PENALTIES_ENABLED != true)")
            return 0
        rows = await conn.fetch("""
            SELECT id, license_id, amount, penalty_amount,
                   penalty_config, due_date, fee_type
            FROM license_obligations
            WHERE status = 'overdue'
              AND penalty_config IS NOT NULL
              AND penalty_config->>'rate' != '0'
              AND due_date IS NOT NULL
        """)

        updated_events = defaultdict(list)  # license_id -> [event items]

        for row in rows:
            config = row["penalty_config"]
            rate = Decimal(str(config.get("rate", 0)))
            if rate <= 0:
                continue

            max_rate = Decimal(str(config.get("max_rate", 100)))
            grace_days = int(config.get("grace_days", 0))

            days_overdue = (date.today() - row["due_date"]).days - grace_days
            if days_overdue <= 0:
                continue

            # Calculate penalty: rate per period (rate = % per month)
            penalty_type = config.get("type", "percentage")
            if penalty_type == "percentage":
                months_overdue = max(1, days_overdue // 30)
                penalty_rate = min(rate * months_overdue, max_rate)
                new_penalty = (row["amount"] * penalty_rate / 100).quantize(
                    Decimal("1")
                )
            else:
                # Fixed penalty per period
                new_penalty = rate * max(1, days_overdue // 30)

            if new_penalty != row["penalty_amount"]:
                await conn.execute("""
                    UPDATE license_obligations
                    SET penalty_amount = $1
                    WHERE id = $2
                """, new_penalty, row["id"])

                updated_events[row["license_id"]].append({
                    "obligation_id": row["id"],
                    "event_data": {
                        "old_penalty": str(row["penalty_amount"]),
                        "new_penalty": str(new_penalty),
                        "days_overdue": days_overdue,
                        "rate": str(rate),
                        "fee_type": row["fee_type"],
                    },
                })

        # Batch log events + refresh counters per license
        for lic_id, events in updated_events.items():
            await LicenseRepository.log_events_batch(
                conn, lic_id, "penalty_applied", events,
            )
            await LicenseService.update_license_counters(conn, lic_id)

        updated_count = sum(len(evts) for evts in updated_events.values())

        # Notify citizen owners about new penalties (async, best-effort)
        if updated_count > 0:
            try:
                from app.core.events import EventBus, EventType
                for lic_id, events in updated_events.items():
                    penalty_total = sum(
                        float(e["event_data"]["new_penalty"]) for e in events
                    )
                    owner = await conn.fetchrow("""
                        SELECT u.email, u.first_name, c.legal_name
                        FROM users u
                        JOIN user_company_roles ucr ON ucr.user_id = u.id
                        JOIN commercial_licenses cl ON cl.company_id = ucr.company_id
                        WHERE cl.id = $1 AND ucr.role = 'company_owner'
                        LIMIT 1
                    """, lic_id)
                    if owner and owner["email"]:
                        EventBus.publish_nowait(EventType.OBLIGATION_PENALTY_APPLIED, {
                            "license_id": str(lic_id),
                            "user_email": owner["email"],
                            "user_name": owner["first_name"] or "",
                            "company_name": owner["legal_name"],
                            "penalty_total": penalty_total,
                            "obligations_affected": len(events),
                        })
            except Exception as e:
                logger.warning(f"Failed to publish PENALTY events: {e}")

            logger.info(
                f"Penalties applied: {updated_count} obligations updated, "
                f"{len(updated_events)} licenses affected"
            )
        return updated_count

    # ==================================================================
    # Renewal Reminders (cron — annual)
    # ==================================================================

    @staticmethod
    async def check_renewal_reminders(conn) -> int:
        """Check for companies that completed last year but haven't renewed.

        Sends OBLIGATION_REMINDER_SENT event for each company that:
        - Had a complete license last year (fiscal_year = current - 1)
        - Does NOT have a license for the current year

        Returns count of reminders sent.
        """
        current_year = datetime.now(timezone.utc).year

        rows = await conn.fetch("""
            SELECT cl.id AS prev_license_id, cl.company_id,
                   c.legal_name, c.representante_legal,
                   u.email, u.first_name, u.last_name,
                   cl.total_amount
            FROM commercial_licenses cl
            JOIN companies c ON c.id = cl.company_id
            LEFT JOIN user_company_roles ucr
                ON ucr.company_id = c.id AND ucr.role = 'company_owner'
            LEFT JOIN users u ON u.id = ucr.user_id
            WHERE cl.fiscal_year = $1
              AND cl.status = 'complete'
              AND NOT EXISTS (
                  SELECT 1 FROM commercial_licenses cl2
                  WHERE cl2.company_id = cl.company_id
                    AND cl2.fiscal_year = $2
              )
              AND u.email IS NOT NULL
        """, current_year - 1, current_year)

        if not rows:
            return 0

        from app.core.events import EventBus, EventType

        sent = 0
        for row in rows:
            try:
                EventBus.publish_nowait(EventType.OBLIGATION_REMINDER_SENT, {
                    "license_id": str(row["prev_license_id"]),
                    "user_email": row["email"],
                    "user_name": f"{row['first_name'] or ''} {row['last_name'] or ''}".strip(),
                    "company_name": row["legal_name"],
                    "fiscal_year": current_year,
                    "message": f"Su licencia comercial {current_year - 1} fue completada. "
                               f"Renueve para el año fiscal {current_year}.",
                })
                sent += 1
            except Exception:
                pass

        logger.info(
            f"Renewal reminders: {sent}/{len(rows)} sent for FY {current_year}"
        )
        return sent

    # ==================================================================
    # Events — Read
    # ==================================================================

    @staticmethod
    async def list_events(
        conn,
        license_id: UUID,
        event_type: Optional[str] = None,
        obligation_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict], int]:
        return await LicenseRepository.list_events(
            conn, license_id, event_type=event_type,
            obligation_id=obligation_id, page=page, page_size=page_size,
        )

    # ==================================================================
    # Stats
    # ==================================================================

    @staticmethod
    async def get_dashboard_stats(
        conn,
        fiscal_year: Optional[int] = None,
        city_id: Optional[UUID] = None,
        fee_type: Optional[str] = None,
        ministry_id: Optional[int] = None,
        processing_mode: Optional[str] = None,
    ) -> Dict:
        return await LicenseRepository.get_dashboard_stats(
            conn, fiscal_year=fiscal_year,
            city_id=city_id, fee_type=fee_type,
            ministry_id=ministry_id, processing_mode=processing_mode,
        )

    # ==================================================================
    # Payment Hook — called when service_payment completes
    # ==================================================================

    @staticmethod
    async def on_payment_completed(
        conn, payment_id, user_id: Optional[UUID] = None
    ) -> int:
        """Hook called when a service_payment reaches workflow_status='completed'.

        1. Check if payment has fee_type (OMS payment) — if not, return 0
        2. Atomically UPDATE payment_pending → paid (RETURNING affected rows)
        3. Batch-fetch all affected licenses in 1 query (no N+1)
        4. Route: tesoro → processing, municipal/chamber → completed
        5. Recalculate license counters

        Idempotent: uses UPDATE...WHERE status='payment_pending' RETURNING —
        concurrent calls on the same payment_id will affect 0 rows on retry.

        Returns: number of obligations processed
        """
        from app.modules.fiscal_services.services.obligation_routing_service import (
            ObligationRoutingService,
        )

        # 1. Check if this is an OMS payment
        payment_row = await conn.fetchrow(
            "SELECT id, fee_type FROM service_payments WHERE id = $1",
            payment_id,
        )
        if not payment_row or not payment_row["fee_type"]:
            return 0

        # 2. Atomic UPDATE with RETURNING — only rows actually transitioned
        #    are returned. Concurrent retries get 0 rows = idempotent.
        paid_at = datetime.now(timezone.utc)
        updated_rows = await conn.fetch("""
            UPDATE license_obligations
            SET status = 'paid', paid_at = $2, updated_at = NOW()
            WHERE payment_id = $1
              AND status = 'payment_pending'
            RETURNING id, license_id, bundle_item_id, fiscal_service_id,
                      ministry_id, fee_type, amount, penalty_amount,
                      due_date, payment_id
        """, payment_id, paid_at)

        if not updated_rows:
            return 0

        obligations = [dict(r) for r in updated_rows]

        # 3. Batch-fetch ALL affected licenses in 1 query (no N+1)
        license_ids = list({o["license_id"] for o in obligations})
        license_rows = await conn.fetch("""
            SELECT cl.id, cl.processing_mode, cl.status,
                   cl.company_id, cl.bundle_id, cl.zone_id,
                   cl.city_id, cl.fiscal_year, cl.obligations_total,
                   cl.service_request_id
            FROM commercial_licenses cl
            WHERE cl.id = ANY($1::uuid[])
        """, license_ids)
        licenses_map: Dict[UUID, Dict] = {
            r["id"]: dict(r) for r in license_rows
        }

        # 4. Route paid obligations grouped by license (batch per license,
        #    not per obligation — avoids N re-instantiations of pre-cache + assignment service)
        from collections import defaultdict
        obls_by_license: defaultdict = defaultdict(list)
        for obl in obligations:
            obl["status"] = "paid"
            obls_by_license[obl["license_id"]].append(obl)

        all_updated = []
        for lic_id, lic_obls in obls_by_license.items():
            license_row = licenses_map.get(lic_id)
            if not license_row:
                logger.error(
                    "OMS: License %s not found for %d obligation(s) "
                    "— data integrity issue",
                    lic_id,
                    len(lic_obls),
                )
                continue

            routed = await ObligationRoutingService.route_paid_obligations(
                conn, lic_obls, license_row, user_id=user_id,
            )
            all_updated.extend(routed)

        logger.info(
            f"OMS on_payment_completed: payment {payment_id} → "
            f"{len(all_updated)}/{len(obligations)} obligations routed"
        )
        return len(all_updated)
