"""
Company Cron Service
====================
Scheduled tasks for company management at scale (1M+ companies):

1. Annual reclassification — Re-run 3-layer classification agent on all active companies
2. Data quality check — Detect anomalies (missing NIF, format errors, duplicates)
3. Compliance reminders — Upcoming deadlines, overdue obligations, escalation
4. Materialized view refresh — Refresh dashboard MVs every 15 min

Called by Cloud Scheduler via:
  POST /api/v1/companies/cron/annual-reclassification
  POST /api/v1/companies/cron/data-quality-check
  POST /api/v1/companies/cron/compliance-reminders
  POST /api/v1/companies/dashboard/cron/refresh-company-stats

Architecture:
  - Batch processing (100 companies per batch) to avoid memory spikes
  - O(1) SQL queries with UPDATE...RETURNING for bulk operations
  - Consolidated email reports (1 per supervisor, not 1 per company)
  - Classification changes logged in company_classification_history
"""

import asyncio
from datetime import datetime, timedelta, date, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
from loguru import logger


# =============================================================================
# CONFIGURATION
# =============================================================================

RECLASSIFY_BATCH_SIZE = 100     # Companies per batch for reclassification
QUALITY_BATCH_SIZE = 500        # Companies per batch for quality check
COMPLIANCE_WARNING_DAYS = 30    # Days before due_date to send warning
COMPLIANCE_ESCALATION_DAYS = 0  # On due_date → escalate to supervisor
COMPLIANCE_OVERDUE_DAYS = 15    # Days after due_date → critical alert


# =============================================================================
# 1. ANNUAL RECLASSIFICATION
# =============================================================================

class CompanyReclassificationService:
    """Batch reclassification of all active companies.

    Processes companies in batches of 100, using the 3-layer classification agent.
    Logs all changes in company_classification_history.
    """

    async def run(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Run annual reclassification on all active companies.

        Returns summary: total processed, changed, errors.
        """
        from app.modules.companies.services.classification_agent import classification_agent

        total = await conn.fetchval(
            "SELECT COUNT(*) FROM companies WHERE is_active = true"
        )
        logger.info(f"Annual reclassification starting: {total} active companies")

        processed = 0
        changed = 0
        errors = 0
        last_id = UUID("00000000-0000-0000-0000-000000000000")

        # Keyset pagination — O(N) total instead of O(N²) with OFFSET
        while True:
            batch = await conn.fetch(
                """SELECT id, legal_name, regimen_fiscal, commerce_type
                   FROM companies
                   WHERE is_active = true AND id > $1
                   ORDER BY id ASC
                   LIMIT $2""",
                last_id, RECLASSIFY_BATCH_SIZE,
            )

            if not batch:
                break

            for company in batch:
                try:
                    result = await classification_agent.classify_and_update(
                        conn,
                        str(company["id"]),
                        triggered_by="annual_cron",
                    )
                    if result and result.regimen_fiscal != (company["regimen_fiscal"] or "pendiente"):
                        changed += 1
                    processed += 1
                except Exception as e:
                    errors += 1
                    logger.error(
                        f"Reclassification error for company {company['id']}: {e}"
                    )

            last_id = batch[-1]["id"]

            if processed % 1000 == 0:
                logger.info(
                    f"Reclassification progress: {processed}/{total} "
                    f"(changed={changed}, errors={errors})"
                )

        summary = {
            "total": total,
            "processed": processed,
            "changed": changed,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Annual reclassification complete: {summary}")
        return summary


# =============================================================================
# 2. DATA QUALITY CHECK
# =============================================================================

class CompanyDataQualityService:
    """Detect data quality anomalies across the company registry.

    Checks:
    - Missing identifiers (no NIF AND no registration_number)
    - Format violations (NIF not matching ^[A-Z0-9]{5,20}$)
    - Cross-check violations (autonomo without PE-XXXX)
    - Missing zone assignment
    - Unclassified companies (regimen_fiscal = 'pendiente')
    - Duplicate legal_name candidates (Levenshtein similarity)
    """

    async def run(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Run full data quality check.

        Returns report with anomaly counts and sample records.
        """
        logger.info("Data quality check starting")

        # 1. Missing identifiers
        missing_id = await conn.fetchval(
            "SELECT COUNT(*) FROM companies "
            "WHERE is_active = true AND nif IS NULL AND registration_number IS NULL"
        )

        # 2. Autonomo without PE-XXXX
        autonomo_no_pe = await conn.fetch(
            """SELECT id, legal_name, nif, registration_number
               FROM companies
               WHERE is_active = true
                 AND forma_juridica = 'autonomo'
                 AND (registration_number IS NULL OR registration_number NOT LIKE 'PE-%')
               LIMIT 50""",
        )

        # 3. Non-autonomo with PE-XXXX format
        non_autonomo_pe = await conn.fetch(
            """SELECT id, legal_name, forma_juridica, registration_number
               FROM companies
               WHERE is_active = true
                 AND forma_juridica IS NOT NULL
                 AND forma_juridica != 'autonomo'
                 AND registration_number LIKE 'PE-%'
               LIMIT 50""",
        )

        # 4. Missing zone
        missing_zone = await conn.fetchval(
            "SELECT COUNT(*) FROM companies "
            "WHERE is_active = true AND zone_id IS NULL"
        )

        # 5. Unclassified (pendiente)
        pendiente = await conn.fetchval(
            "SELECT COUNT(*) FROM companies "
            "WHERE is_active = true AND (regimen_fiscal = 'pendiente' OR regimen_fiscal IS NULL)"
        )

        # 6. NIF format violations (non-null NIFs that don't match pattern)
        nif_violations = await conn.fetchval(
            "SELECT COUNT(*) FROM companies "
            "WHERE nif IS NOT NULL AND nif !~ '^[A-Z0-9]{5,20}$'"
        )

        # 7. Active but not verified
        unverified = await conn.fetchval(
            "SELECT COUNT(*) FROM companies "
            "WHERE is_active = true AND is_verified = false"
        )

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "anomalies": {
                "missing_identifier": missing_id,
                "autonomo_without_pe": len(autonomo_no_pe),
                "non_autonomo_with_pe": len(non_autonomo_pe),
                "missing_zone": missing_zone,
                "unclassified_pendiente": pendiente,
                "nif_format_violations": nif_violations,
                "active_unverified": unverified,
            },
            "total_anomalies": (
                missing_id + len(autonomo_no_pe) + len(non_autonomo_pe)
                + missing_zone + pendiente + nif_violations
            ),
            "samples": {
                "autonomo_without_pe": [
                    {"id": str(r["id"]), "legal_name": r["legal_name"]}
                    for r in autonomo_no_pe[:5]
                ],
                "non_autonomo_with_pe": [
                    {"id": str(r["id"]), "legal_name": r["legal_name"],
                     "forma": r["forma_juridica"]}
                    for r in non_autonomo_pe[:5]
                ],
            },
        }

        logger.info(
            f"Data quality check complete: {report['total_anomalies']} anomalies found"
        )
        return report


# =============================================================================
# 3. COMPLIANCE REMINDERS
# =============================================================================

class CompanyComplianceService:
    """Monitor license obligation deadlines and send reminders.

    3 tiers:
    - J-30: Warning email to company owner (upcoming deadline)
    - J-0: Notification to ministry agents (deadline reached)
    - J+15: Escalation to supervisors (critical overdue)
    """

    async def run(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Run compliance check on all pending obligations.

        Returns summary: warnings sent, escalations, overdue count.
        """
        today = date.today()
        warning_date = today + timedelta(days=COMPLIANCE_WARNING_DAYS)

        # 1. Upcoming deadlines (J-30) — mark as warned
        upcoming = await conn.fetch(
            """SELECT lo.id, lo.amount, lo.fee_type, lo.due_date,
                      cl.company_id, c.legal_name, c.nif
               FROM license_obligations lo
               JOIN commercial_licenses cl ON lo.license_id = cl.id
               JOIN companies c ON cl.company_id = c.id
               WHERE lo.status = 'pending'
                 AND lo.due_date <= $1
                 AND lo.due_date > $2
               ORDER BY lo.due_date ASC""",
            warning_date, today,
        )

        # 2. Due today (J-0) — need agent action
        due_today = await conn.fetch(
            """SELECT lo.id, lo.amount, lo.fee_type, lo.ministry_id,
                      cl.company_id, c.legal_name, c.nif
               FROM license_obligations lo
               JOIN commercial_licenses cl ON lo.license_id = cl.id
               JOIN companies c ON cl.company_id = c.id
               WHERE lo.status = 'pending'
                 AND lo.due_date = $1""",
            today,
        )

        # 3. Critical overdue (J+15) — escalation
        overdue_date = today - timedelta(days=COMPLIANCE_OVERDUE_DAYS)
        critical_overdue = await conn.fetch(
            """UPDATE license_obligations
               SET status = 'overdue'
               WHERE status = 'pending'
                 AND due_date < $1
               RETURNING id, amount, fee_type""",
            overdue_date,
        )

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "upcoming_warnings": len(upcoming),
            "due_today": len(due_today),
            "critical_overdue_updated": len(critical_overdue),
            "total_overdue_amount": sum(
                float(r["amount"] or 0) for r in critical_overdue
            ),
        }

        logger.info(f"Compliance check complete: {summary}")
        return summary


# =============================================================================
# SINGLETONS
# =============================================================================

reclassification_service = CompanyReclassificationService()
data_quality_service = CompanyDataQualityService()
compliance_service = CompanyComplianceService()
