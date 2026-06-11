"""Inspection Repository — Data access layer for field inspections."""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class InspectionRepository:
    """Data access for field_inspections table."""

    # ============================================================
    # CREATE
    # ============================================================

    @staticmethod
    async def create(conn, data: Dict) -> Dict:
        """Insert a new inspection."""
        row = await conn.fetchrow("""
            INSERT INTO field_inspections (
                agent_id, agent_profile_id, entity_id, entity_location_id,
                license_id, company_id, inspection_date, status, result,
                notes, unpaid_obligations_count, unpaid_obligations_amount,
                total_obligations_count
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
        """,
            data["agent_id"], data["agent_profile_id"],
            data["entity_id"], data["entity_location_id"],
            data["license_id"], data["company_id"],
            data.get("inspection_date", date.today()),
            "in_progress", "pending",
            data.get("notes"),
            data.get("unpaid_obligations_count", 0),
            data.get("unpaid_obligations_amount", Decimal("0")),
            data.get("total_obligations_count", 0),
        )
        return dict(row) if row else None

    # ============================================================
    # READ
    # ============================================================

    @staticmethod
    async def get_by_id(conn, inspection_id: UUID) -> Optional[Dict]:
        """Get inspection with enriched company/agent data.

        company_nif returns COALESCE(nif, registration_number) since
        autonomes have PE-xxxxxx (registration_number) instead of GE NIF.
        """
        row = await conn.fetchrow("""
            SELECT fi.*,
                   c.legal_name AS company_name,
                   COALESCE(c.nif, c.registration_number) AS company_nif,
                   u.full_name AS agent_name,
                   e.code AS entity_code
            FROM field_inspections fi
            JOIN companies c ON c.id = fi.company_id
            JOIN users u ON u.id = fi.agent_id
            JOIN entities e ON e.id = fi.entity_id
            WHERE fi.id = $1
        """, inspection_id)
        return dict(row) if row else None

    @staticmethod
    async def list_by_agent(
        conn, agent_id: UUID,
        inspection_date: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status: Optional[str] = None,
        result: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1, page_size: int = 20,
    ) -> Tuple[List[Dict], int]:
        """List inspections for an agent with filters."""
        conditions = ["fi.agent_id = $1"]
        params = [agent_id]
        idx = 2

        if inspection_date:
            conditions.append(f"fi.inspection_date = ${idx}")
            params.append(inspection_date)
            idx += 1
        else:
            # Date range (when no single date specified)
            if date_from:
                conditions.append(f"fi.inspection_date >= ${idx}")
                params.append(date_from)
                idx += 1
            if date_to:
                conditions.append(f"fi.inspection_date <= ${idx}")
                params.append(date_to)
                idx += 1

        if status:
            conditions.append(f"fi.status = ${idx}")
            params.append(status)
            idx += 1

        if result:
            conditions.append(f"fi.result = ${idx}")
            params.append(result)
            idx += 1

        if search:
            conditions.append(f"(c.legal_name ILIKE ${idx} OR COALESCE(c.nif, c.registration_number) ILIKE ${idx})")
            params.append(f"%{search}%")
            idx += 1

        where = " AND ".join(conditions)

        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) FROM field_inspections fi WHERE {where}", *params
        )
        total = count_row["count"]

        rows = await conn.fetch(f"""
            SELECT fi.id, fi.agent_id, fi.inspection_date, fi.status, fi.result,
                   c.legal_name AS company_name, COALESCE(c.nif, c.registration_number) AS company_nif,
                   fi.unpaid_obligations_count, fi.unpaid_obligations_amount,
                   fi.seal_applied, fi.mise_en_demeure_issued,
                   fi.payment_collected, fi.payment_amount,
                   u.full_name AS agent_name,
                   e.code AS entity_code,
                   fi.created_at
            FROM field_inspections fi
            JOIN companies c ON c.id = fi.company_id
            JOIN users u ON u.id = fi.agent_id
            JOIN entities e ON e.id = fi.entity_id
            WHERE {where}
            ORDER BY fi.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params, page_size, (page - 1) * page_size)

        return [dict(r) for r in rows], total

    # Allowed sort columns (whitelist to prevent SQL injection)
    SORT_COLUMNS = frozenset({
        "inspection_date", "created_at", "payment_amount",
        "company_name", "status", "result",
    })
    SORT_COLUMN_MAP = {
        "inspection_date": "fi.inspection_date",
        "created_at": "fi.created_at",
        "payment_amount": "fi.payment_amount",
        "company_name": "c.legal_name",
        "status": "fi.status",
        "result": "fi.result",
    }

    @staticmethod
    async def list_by_entity(
        conn, entity_id: UUID,
        inspection_date: Optional[date] = None,
        status: Optional[str] = None,
        agent_id: Optional[UUID] = None,
        zone_code: Optional[str] = None,
        result: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None,
        has_payment: Optional[bool] = None,
        has_med: Optional[bool] = None,
        has_seal: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_dir: Optional[str] = "desc",
        page: int = 1, page_size: int = 20,
    ) -> Tuple[List[Dict], int]:
        """List inspections for an entity with advanced filters (supervisor view)."""
        conditions = ["fi.entity_id = $1"]
        params: list = [entity_id]
        idx = 2
        needs_zone_join = False

        if inspection_date:
            conditions.append(f"fi.inspection_date = ${idx}")
            params.append(inspection_date)
            idx += 1

        if status:
            conditions.append(f"fi.status = ${idx}")
            params.append(status)
            idx += 1

        if agent_id:
            conditions.append(f"fi.agent_id = ${idx}")
            params.append(agent_id)
            idx += 1

        if zone_code:
            conditions.append(f"cz.zone_code = ${idx}")
            params.append(zone_code)
            idx += 1
            needs_zone_join = True

        if result:
            conditions.append(f"fi.result = ${idx}")
            params.append(result)
            idx += 1

        if date_from:
            conditions.append(f"fi.inspection_date >= ${idx}")
            params.append(date_from)
            idx += 1

        if date_to:
            conditions.append(f"fi.inspection_date <= ${idx}")
            params.append(date_to)
            idx += 1

        if search:
            conditions.append(f"(c.legal_name ILIKE ${idx} OR COALESCE(c.nif, c.registration_number) ILIKE ${idx})")
            params.append(f"%{search}%")
            idx += 1

        if has_payment is not None:
            conditions.append(f"fi.payment_collected = ${idx}")
            params.append(has_payment)
            idx += 1

        if has_med is not None:
            conditions.append(f"fi.mise_en_demeure_issued = ${idx}")
            params.append(has_med)
            idx += 1

        if has_seal is not None:
            conditions.append(f"fi.seal_applied = ${idx}")
            params.append(has_seal)
            idx += 1

        where = " AND ".join(conditions)
        zone_join = "LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id" if needs_zone_join else ""

        # Sort with whitelist
        order_col = InspectionRepository.SORT_COLUMN_MAP.get(sort_by, "fi.created_at")
        order_dir = "ASC" if sort_dir == "asc" else "DESC"
        order_clause = f"{order_col} {order_dir}"

        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) FROM field_inspections fi JOIN companies c ON c.id = fi.company_id {zone_join} WHERE {where}",
            *params
        )
        total = count_row["count"]

        rows = await conn.fetch(f"""
            SELECT fi.id, fi.agent_id, fi.inspection_date, fi.status, fi.result,
                   c.legal_name AS company_name,
                   COALESCE(c.nif, c.registration_number) AS company_nif,
                   fi.unpaid_obligations_count, fi.unpaid_obligations_amount,
                   fi.seal_applied, fi.mise_en_demeure_issued,
                   fi.payment_collected, fi.payment_amount,
                   fi.duration_minutes, fi.zone_id,
                   u.full_name AS agent_name,
                   e.code AS entity_code,
                   fi.created_at
            FROM field_inspections fi
            JOIN companies c ON c.id = fi.company_id
            JOIN users u ON u.id = fi.agent_id
            JOIN entities e ON e.id = fi.entity_id
            {zone_join}
            WHERE {where}
            ORDER BY {order_clause}
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params, page_size, (page - 1) * page_size)

        return [dict(r) for r in rows], total

    # ============================================================
    # UPDATE
    # ============================================================

    # Fix C5: Whitelist of allowed columns to prevent SQL injection
    UPDATABLE_COLUMNS = frozenset({
        "status", "result",
        "activity_conforme", "activity_declared", "activity_observed",
        "photos", "gps_latitude", "gps_longitude", "gps_accuracy", "notes",
        "mise_en_demeure_issued", "mise_en_demeure_deadline",
        "mise_en_demeure_obligations",
        "seal_applied", "seal_reason", "seal_notes", "seal_photo",
        "seal_proposed_at", "seal_approved_by", "seal_approved_at",
        "seal_rejection_reason",
        "payment_collected", "payment_id", "payment_receipt_number",
        "payment_amount",
        "unpaid_obligations_count", "unpaid_obligations_amount",
        "total_obligations_count",
        "agent_signature",
    })

    @staticmethod
    async def update(conn, inspection_id: UUID, data: Dict) -> Optional[Dict]:
        """Update inspection fields (whitelist-protected against injection)."""
        if not data:
            return await InspectionRepository.get_by_id(conn, inspection_id)

        # Fix C5: Reject any key not in the whitelist
        invalid_keys = set(data.keys()) - InspectionRepository.UPDATABLE_COLUMNS
        if invalid_keys:
            raise ValueError(
                f"Invalid update columns: {invalid_keys}. "
                f"Allowed: {InspectionRepository.UPDATABLE_COLUMNS}"
            )

        # JSONB columns must be serialized to JSON string for asyncpg
        JSONB_COLUMNS = {"photos", "mise_en_demeure_obligations"}

        set_clauses = []
        params = []
        idx = 1

        for key, value in data.items():
            # Serialize lists/dicts to JSON for JSONB columns
            if key in JSONB_COLUMNS and isinstance(value, (list, dict)):
                import json
                value = json.dumps(value)
            set_clauses.append(f"{key} = ${idx}")
            params.append(value)
            idx += 1

        set_clauses.append("updated_at = NOW()")
        params.append(inspection_id)

        row = await conn.fetchrow(f"""
            UPDATE field_inspections
            SET {', '.join(set_clauses)}
            WHERE id = ${idx}
            RETURNING *
        """, *params)

        if not row:
            return None

        # Re-fetch with JOINs for enriched response
        return await InspectionRepository.get_by_id(conn, inspection_id)

    # ============================================================
    # STATS
    # ============================================================

    @staticmethod
    async def get_stats(
        conn, agent_id: Optional[UUID] = None,
        entity_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict:
        """Get inspection stats for agent or entity."""
        conditions = []
        params = []
        idx = 1

        if agent_id:
            conditions.append(f"agent_id = ${idx}")
            params.append(agent_id)
            idx += 1

        if entity_id:
            conditions.append(f"entity_id = ${idx}")
            params.append(entity_id)
            idx += 1

        if date_from:
            conditions.append(f"inspection_date >= ${idx}")
            params.append(date_from)
            idx += 1

        if date_to:
            conditions.append(f"inspection_date <= ${idx}")
            params.append(date_to)
            idx += 1

        where = " AND ".join(conditions) if conditions else "TRUE"

        row = await conn.fetchrow(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE result = 'conforme') AS conforme,
                COUNT(*) FILTER (WHERE result = 'non_conforme') AS non_conforme,
                COUNT(*) FILTER (WHERE mise_en_demeure_issued = true) AS mise_en_demeure,
                COUNT(*) FILTER (WHERE status = 'seal_proposed') AS seals_proposed,
                COUNT(*) FILTER (WHERE status = 'seal_approved') AS seals_approved,
                COUNT(*) FILTER (WHERE payment_collected = true) AS payments_collected,
                COALESCE(SUM(payment_amount) FILTER (WHERE payment_collected = true), 0) AS total_collected_amount
            FROM field_inspections
            WHERE {where}
        """, *params)

        return dict(row) if row else {}

    # ============================================================
    # SEAL QUERIES
    # ============================================================

    @staticmethod
    async def get_pending_seals(conn, entity_id: UUID) -> List[Dict]:
        """Get seal proposals pending supervisor approval."""
        rows = await conn.fetch("""
            SELECT fi.id, fi.inspection_date,
                   c.legal_name AS company_name, COALESCE(c.nif, c.registration_number) AS company_nif,
                   fi.seal_reason, fi.seal_notes, fi.seal_photo,
                   fi.seal_proposed_at,
                   u.full_name AS agent_name,
                   fi.photos,
                   fi.gps_latitude, fi.gps_longitude,
                   fi.unpaid_obligations_amount,
                   fi.unpaid_obligations_count
            FROM field_inspections fi
            JOIN companies c ON c.id = fi.company_id
            JOIN users u ON u.id = fi.agent_id
            WHERE fi.entity_id = $1
              AND fi.status = 'seal_proposed'
            ORDER BY fi.seal_proposed_at ASC
        """, entity_id)
        return [dict(r) for r in rows]

    @staticmethod
    async def get_overdue_med_count(conn, entity_id: UUID) -> int:
        """Count MED with expired deadlines and no seal yet."""
        row = await conn.fetchrow("""
            SELECT COUNT(*) AS cnt
            FROM field_inspections
            WHERE entity_id = $1
              AND mise_en_demeure_issued = true
              AND mise_en_demeure_deadline < NOW()
              AND status = 'mise_en_demeure'
        """, entity_id)
        return row["cnt"] if row else 0

    @staticmethod
    async def get_auto_approve_seals(conn, hours: int = 24) -> List[Dict]:
        """Get seal proposals that exceeded auto-approve deadline."""
        rows = await conn.fetch("""
            SELECT fi.id, fi.company_id, fi.license_id, fi.entity_id,
                   fi.seal_reason, fi.agent_id
            FROM field_inspections fi
            WHERE fi.status = 'seal_proposed'
              AND fi.seal_proposed_at < NOW() - $1::interval
        """, timedelta(hours=hours))
        return [dict(r) for r in rows]

    @staticmethod
    async def batch_auto_approve_seals(conn, hours: int = 24) -> int:
        """Fix m8: Batch auto-approve all expired seals in O(1) queries."""
        # 1. Batch update inspections
        result = await conn.fetch("""
            UPDATE field_inspections
            SET status = 'seal_approved',
                seal_approved_at = NOW(),
                seal_notes = COALESCE(seal_notes, '') ||
                    E'\n[AUTO] Aprobado automáticamente tras 24h sin respuesta',
                updated_at = NOW()
            WHERE status = 'seal_proposed'
              AND seal_proposed_at < NOW() - $1::interval
            RETURNING id, company_id, license_id
        """, timedelta(hours=hours))

        if not result:
            return 0

        # 2. Batch deactivate companies
        company_ids = list({r["company_id"] for r in result})
        await conn.execute("""
            UPDATE companies SET is_active = false, updated_at = NOW()
            WHERE id = ANY($1::uuid[])
        """, company_ids)

        # 3. Batch suspend licenses
        license_ids = list({r["license_id"] for r in result})
        await conn.execute("""
            UPDATE commercial_licenses
            SET status = 'suspended', updated_at = NOW()
            WHERE id = ANY($1::uuid[]) AND status != 'closed'
        """, license_ids)

        return len(result)

    # ============================================================
    # RECONCILIATION
    # ============================================================

    @staticmethod
    async def get_unreconciled_cash(
        conn, agent_id: UUID,
        target_date: Optional[date] = None,
    ) -> Tuple[List[Dict], Decimal]:
        """Get agent's cash collections for reconciliation."""
        d = target_date or date.today()

        rows = await conn.fetch("""
            SELECT fi.id, fi.inspection_date,
                   c.legal_name AS company_name, COALESCE(c.nif, c.registration_number) AS company_nif,
                   fi.payment_amount, fi.payment_receipt_number,
                   fi.created_at
            FROM field_inspections fi
            JOIN companies c ON c.id = fi.company_id
            WHERE fi.agent_id = $1
              AND fi.payment_collected = true
              AND fi.inspection_date = $2
            ORDER BY fi.created_at ASC
        """, agent_id, d)

        items = [dict(r) for r in rows]
        total = sum(r.get("payment_amount") or Decimal("0") for r in items)
        return items, total

    @staticmethod
    async def get_unreconciled_cash_by_entity(conn, entity_id: UUID) -> Dict:
        """Get total unreconciled cash for entity (supervisor view)."""
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) AS cnt,
                COALESCE(SUM(payment_amount), 0) AS total
            FROM field_inspections
            WHERE entity_id = $1
              AND payment_collected = true
              AND inspection_date >= CURRENT_DATE - INTERVAL '7 days'
        """, entity_id)
        return {
            "count": row["cnt"] if row else 0,
            "amount": row["total"] if row else Decimal("0"),
        }

    @staticmethod
    async def get_supervisor_dashboard_cte(
        conn, entity_id: UUID,
        entity_location_id: Optional[UUID] = None,
    ) -> Dict:
        """CTE-based supervisor dashboard — single query instead of 5.

        Returns today_stats, week_stats, pending_seals_count, overdue_med,
        unreconciled_cash in one round-trip.

        If entity_location_id is provided, scopes all stats to that location.
        """
        loc_filter = ""
        params: list = [entity_id]
        if entity_location_id:
            loc_filter = "AND entity_location_id = $2"
            params.append(entity_location_id)

        row = await conn.fetchrow(f"""
            WITH today_stats AS (
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE result = 'conforme') AS conforme,
                    COUNT(*) FILTER (WHERE result = 'non_conforme') AS non_conforme,
                    COUNT(*) FILTER (WHERE mise_en_demeure_issued) AS mise_en_demeure,
                    COUNT(*) FILTER (WHERE status = 'seal_proposed') AS seals_proposed,
                    COUNT(*) FILTER (WHERE status = 'seal_approved') AS seals_approved,
                    COUNT(*) FILTER (WHERE payment_collected) AS payments_collected,
                    COALESCE(SUM(payment_amount) FILTER (WHERE payment_collected), 0) AS total_collected
                FROM field_inspections
                WHERE entity_id = $1 {loc_filter} AND inspection_date = CURRENT_DATE
            ),
            week_stats AS (
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE result = 'conforme') AS conforme,
                    COUNT(*) FILTER (WHERE result = 'non_conforme') AS non_conforme,
                    COUNT(*) FILTER (WHERE mise_en_demeure_issued) AS mise_en_demeure,
                    COUNT(*) FILTER (WHERE status = 'seal_proposed') AS seals_proposed,
                    COUNT(*) FILTER (WHERE status = 'seal_approved') AS seals_approved,
                    COUNT(*) FILTER (WHERE payment_collected) AS payments_collected,
                    COALESCE(SUM(payment_amount) FILTER (WHERE payment_collected), 0) AS total_collected
                FROM field_inspections
                WHERE entity_id = $1 {loc_filter} AND inspection_date >= CURRENT_DATE - 7
            ),
            pending AS (
                SELECT COUNT(*) AS cnt FROM field_inspections
                WHERE entity_id = $1 {loc_filter} AND status = 'seal_proposed'
            ),
            overdue AS (
                SELECT COUNT(*) AS cnt FROM field_inspections
                WHERE entity_id = $1 {loc_filter} AND mise_en_demeure_issued
                  AND mise_en_demeure_deadline < NOW() AND status = 'mise_en_demeure'
            ),
            cash AS (
                SELECT COUNT(*) AS cnt, COALESCE(SUM(payment_amount), 0) AS total
                FROM field_inspections
                WHERE entity_id = $1 {loc_filter} AND payment_collected
                  AND inspection_date >= CURRENT_DATE - 7
            )
            SELECT
                (SELECT row_to_json(today_stats) FROM today_stats) AS today,
                (SELECT row_to_json(week_stats) FROM week_stats) AS week,
                (SELECT cnt FROM pending) AS pending_seals_count,
                (SELECT cnt FROM overdue) AS overdue_med,
                (SELECT cnt FROM cash) AS cash_count,
                (SELECT total FROM cash) AS cash_amount
        """, *params)

        if not row:
            return {}

        import json
        return {
            "today": json.loads(row["today"]) if row["today"] else {},
            "week": json.loads(row["week"]) if row["week"] else {},
            "pending_seals_count": row["pending_seals_count"] or 0,
            "overdue_med": row["overdue_med"] or 0,
            "cash_count": row["cash_count"] or 0,
            "cash_amount": row["cash_amount"] or Decimal("0"),
        }

    # ============================================================
    # LICENSE VERIFICATION (Agent Mode)
    # ============================================================

    @staticmethod
    async def get_license_for_verification(
        conn, license_id: UUID, entity_id: UUID,
        fee_type: Optional[str] = None,
    ) -> Optional[Dict]:
        """Get enriched license data for agent verification."""
        row = await conn.fetchrow("""
            SELECT cl.id AS license_id, cl.company_id,
                   c.legal_name AS company_name, COALESCE(c.nif, c.registration_number) AS company_nif,
                   c.registration_number AS company_registration_number,
                   c.forma_juridica, c.commerce_type,
                   cz.zone_code,
                   ci.name AS city_name,
                   cl.fiscal_year, cl.status AS license_status,
                   cl.total_amount, cl.amount_paid, cl.compliance_score
            FROM commercial_licenses cl
            JOIN companies c ON c.id = cl.company_id
            LEFT JOIN commerce_zones cz ON cz.id = cl.zone_id
            LEFT JOIN cities ci ON ci.id = cl.city_id
            WHERE cl.id = $1
        """, license_id)

        if not row:
            return None

        result = dict(row)
        company_id = result["company_id"]

        async def _get_obligations():
            fee_filter = ""
            params = [license_id]
            if fee_type:
                fee_filter = "AND lo.fee_type = $2"
                params.append(fee_type)
            rows = await conn.fetch(f"""
                SELECT lo.id, lo.fee_type, lo.amount, lo.penalty_amount,
                       lo.due_date, lo.status,
                       lo.ministry_id,
                       fs.name_es AS service_name,
                       m.name_es AS ministry_name
                FROM license_obligations lo
                LEFT JOIN fiscal_services fs ON fs.id = lo.fiscal_service_id
                LEFT JOIN ministries m ON m.id = lo.ministry_id
                WHERE lo.license_id = $1 {fee_filter}
                ORDER BY lo.fee_type, lo.due_date
            """, *params)
            return [dict(o) for o in rows]

        async def _get_prev_inspections():
            rows = await conn.fetch("""
                SELECT fi.id, fi.inspection_date, fi.status, fi.result,
                       fi.unpaid_obligations_count, fi.unpaid_obligations_amount,
                       fi.seal_applied, fi.mise_en_demeure_issued,
                       fi.payment_collected,
                       u.full_name AS agent_name,
                       e.code AS entity_code,
                       fi.created_at
                FROM field_inspections fi
                JOIN users u ON u.id = fi.agent_id
                JOIN entities e ON e.id = fi.entity_id
                WHERE fi.company_id = $1
                ORDER BY fi.inspection_date DESC
                LIMIT 10
            """, company_id)
            return [dict(p) for p in rows]

        async def _get_active_med():
            med = await conn.fetchrow("""
                SELECT id, mise_en_demeure_deadline, mise_en_demeure_obligations,
                       inspection_date, agent_id
                FROM field_inspections
                WHERE company_id = $1
                  AND mise_en_demeure_issued = true
                  AND status = 'mise_en_demeure'
                  AND mise_en_demeure_deadline > NOW()
                ORDER BY mise_en_demeure_deadline DESC
                LIMIT 1
            """, company_id)
            return dict(med) if med else None

        async def _get_seal_history():
            rows = await conn.fetch("""
                SELECT id, inspection_date, seal_reason, status,
                       seal_approved_at, seal_approved_by
                FROM field_inspections
                WHERE company_id = $1
                  AND seal_applied = true
                ORDER BY seal_proposed_at DESC
                LIMIT 5
            """, company_id)
            return [dict(s) for s in rows]

        # Sequential execution — asyncpg does NOT support concurrent queries
        # on a single connection (InterfaceError: another operation in progress)
        obligations = await _get_obligations()
        prev_inspections = await _get_prev_inspections()
        active_med = await _get_active_med()
        seal_history = await _get_seal_history()

        result["obligations"] = obligations
        result["previous_inspections"] = prev_inspections
        result["active_mise_en_demeure"] = active_med
        result["seal_history"] = seal_history

        return result

    @staticmethod
    async def find_license_by_identifier(conn, identifier: str) -> Optional[Dict]:
        """Find the current year license by NIF, registration_number, or company name.

        Search strategy (in priority order):
        1. Exact NIF match (GExxxxxX)
        2. Exact registration_number match (PE-xxxxxx)
        3. Company name search (ILIKE for partial match)
        """
        # First: try exact NIF/registration_number match
        row = await conn.fetchrow("""
            SELECT cl.id AS license_id, cl.company_id
            FROM commercial_licenses cl
            JOIN companies c ON c.id = cl.company_id
            WHERE (c.nif = $1 OR c.registration_number = $1)
              AND cl.fiscal_year = EXTRACT(YEAR FROM CURRENT_DATE)::int
              AND cl.status NOT IN ('closed', 'cancelled')
            ORDER BY cl.created_at DESC
            LIMIT 1
        """, identifier)
        if row:
            return dict(row)

        # Fallback: search by company name (case-insensitive, partial match)
        row = await conn.fetchrow("""
            SELECT cl.id AS license_id, cl.company_id
            FROM commercial_licenses cl
            JOIN companies c ON c.id = cl.company_id
            WHERE c.legal_name ILIKE $1
              AND cl.fiscal_year = EXTRACT(YEAR FROM CURRENT_DATE)::int
              AND cl.status NOT IN ('closed', 'cancelled')
            ORDER BY cl.created_at DESC
            LIMIT 1
        """, f"%{identifier}%")
        return dict(row) if row else None
