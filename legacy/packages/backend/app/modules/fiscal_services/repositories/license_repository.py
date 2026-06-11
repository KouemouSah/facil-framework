"""License Repository — Data access for commercial_licenses, license_obligations, license_compliance_events."""

import json as _json
import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


def _license_sort_clause(sort_by: Optional[str], sort_order: str = "desc") -> str:
    """Build ORDER BY clause from whitelisted sort column (SQL injection safe)."""
    ALLOWED = {
        "company_name": "co.legal_name",
        "fiscal_year": "cl.fiscal_year",
        "status": "cl.status",
        "total_amount": "cl.total_amount",
        "amount_paid": "cl.amount_paid",
        "compliance_score": "cl.compliance_score",
        "deadline": "cl.deadline",
        "created_at": "cl.created_at",
        "zone_code": "cz.zone_code",
    }
    direction = "ASC" if sort_order.lower() == "asc" else "DESC"
    col = ALLOWED.get(sort_by or "", "cl.fiscal_year")
    return f"{col} {direction}, cl.created_at DESC"


class LicenseRepository:
    """Repository for the OMS (Obligation Management System) tables."""

    # ==================================================================
    # Licenses — Read
    # ==================================================================

    @staticmethod
    async def get_license(conn, license_id: UUID) -> Optional[Dict]:
        """Get a single license with enriched JOINs."""
        row = await conn.fetchrow("""
            SELECT cl.*,
                   co.legal_name as company_name,
                   COALESCE(co.nif, co.registration_number) as company_nif,
                   co.registration_number as company_registration_number,
                   sb.name_es as bundle_name,
                   cz.zone_code
            FROM commercial_licenses cl
            LEFT JOIN companies co ON cl.company_id = co.id
            LEFT JOIN service_bundles sb ON cl.bundle_id = sb.id
            LEFT JOIN commerce_zones cz ON cl.zone_id = cz.id
            WHERE cl.id = $1
        """, license_id)
        return dict(row) if row else None

    @staticmethod
    async def get_license_by_scope(
        conn, company_id: UUID, bundle_id: UUID, fiscal_year: int
    ) -> Optional[Dict]:
        """Lookup by UNIQUE(company, bundle, year)."""
        row = await conn.fetchrow("""
            SELECT cl.*,
                   co.legal_name as company_name,
                   sb.name_es as bundle_name,
                   cz.zone_code
            FROM commercial_licenses cl
            LEFT JOIN companies co ON cl.company_id = co.id
            LEFT JOIN service_bundles sb ON cl.bundle_id = sb.id
            LEFT JOIN commerce_zones cz ON cl.zone_id = cz.id
            WHERE cl.company_id = $1 AND cl.bundle_id = $2 AND cl.fiscal_year = $3
        """, company_id, bundle_id, fiscal_year)
        return dict(row) if row else None

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
        # Agent scope filters (from OmsAgentService.resolve_agent_context)
        city_id: Optional[UUID] = None,
        fee_type: Optional[str] = None,
        ministry_id: Optional[int] = None,
        processing_mode: Optional[str] = None,
        # Sorting
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ) -> Tuple[List[Dict], int]:
        """List licenses with filters, paginated, sortable.

        Agent scope: city_id filters by license city, fee_type/ministry_id
        filters by having at least one matching obligation (EXISTS subquery).
        search: ILIKE on company legal_name or bundle name_es.
        sort_by: whitelisted column name. sort_order: asc|desc.
        """
        conditions = []
        params = []
        idx = 1

        if company_id:
            conditions.append(f"cl.company_id = ${idx}")
            params.append(company_id)
            idx += 1

        if bundle_id:
            conditions.append(f"cl.bundle_id = ${idx}")
            params.append(bundle_id)
            idx += 1

        if fiscal_year:
            conditions.append(f"cl.fiscal_year = ${idx}")
            params.append(fiscal_year)
            idx += 1

        if status:
            conditions.append(f"cl.status = ${idx}")
            params.append(status)
            idx += 1

        if search:
            conditions.append(
                f"(co.legal_name ILIKE ${idx} OR sb.name_es ILIKE ${idx})"
            )
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
            idx += 1

        # --- Agent scope filters ---
        if city_id is not None:
            conditions.append(f"cl.city_id = ${idx}")
            params.append(city_id)
            idx += 1

        if processing_mode:
            conditions.append(f"cl.processing_mode = ${idx}")
            params.append(processing_mode)
            idx += 1

        # fee_type / ministry_id: license must have at least one matching obligation
        if fee_type:
            conditions.append(f"""EXISTS (
                SELECT 1 FROM license_obligations lo_scope
                WHERE lo_scope.license_id = cl.id AND lo_scope.fee_type = ${idx}
            )""")
            params.append(fee_type)
            idx += 1

        if ministry_id is not None:
            conditions.append(f"""EXISTS (
                SELECT 1 FROM license_obligations lo_scope
                WHERE lo_scope.license_id = cl.id AND lo_scope.ministry_id = ${idx}
            )""")
            params.append(ministry_id)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # JOINs needed for both count (when search/scope active) and data
        joins = """
            LEFT JOIN companies co ON cl.company_id = co.id
            LEFT JOIN service_bundles sb ON cl.bundle_id = sb.id
            LEFT JOIN commerce_zones cz ON cl.zone_id = cz.id
        """

        # Count — always include JOINs (needed for search and scope filters)
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM commercial_licenses cl {joins} {where}",
            *params,
        )
        total = count_row["total"]

        # Data
        offset = (page - 1) * page_size
        params_data = params + [page_size, offset]
        rows = await conn.fetch(f"""
            SELECT cl.*,
                   co.legal_name as company_name,
                   co.nif as company_nif,
                   co.registration_number as company_registration_number,
                   sb.name_es as bundle_name,
                   cz.zone_code
            FROM commercial_licenses cl
            {joins}
            {where}
            ORDER BY {_license_sort_clause(sort_by, sort_order)}
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params_data)

        return [dict(r) for r in rows], total

    # ==================================================================
    # Licenses — Write
    # ==================================================================

    @staticmethod
    async def create_license(conn, data: Dict, user_id: Optional[UUID] = None) -> Dict:
        """Create a commercial license dossier."""
        row = await conn.fetchrow("""
            INSERT INTO commercial_licenses
                (company_id, service_request_id, bundle_id, zone_id, city_id,
                 fiscal_year, processing_mode, total_amount, obligations_total,
                 deadline, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
        """,
            data["company_id"],
            data.get("service_request_id"),
            data["bundle_id"],
            data["zone_id"],
            data.get("city_id"),
            data["fiscal_year"],
            data.get("processing_mode", "per_line"),
            data["total_amount"],
            data["obligations_total"],
            data.get("deadline"),
            user_id,
        )
        return await LicenseRepository.get_license(conn, row["id"])

    @staticmethod
    async def update_license(
        conn, license_id: UUID, data: Dict
    ) -> Optional[Dict]:
        """Partial update of a license."""
        allowed = [
            "status", "amount_paid", "penalty_amount",
            "obligations_paid", "obligations_overdue",
            "completed_at", "closed_at",
        ]
        sets = []
        params = []
        idx = 1

        for field in allowed:
            if field in data:
                sets.append(f"{field} = ${idx}")
                val = data[field]
                if hasattr(val, "value"):
                    val = val.value
                params.append(val)
                idx += 1

        if not sets:
            return await LicenseRepository.get_license(conn, license_id)

        params.append(license_id)
        row = await conn.fetchrow(f"""
            UPDATE commercial_licenses
            SET {', '.join(sets)}
            WHERE id = ${idx}
            RETURNING id
        """, *params)

        if not row:
            return None
        return await LicenseRepository.get_license(conn, license_id)

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
    ) -> Tuple[List[Dict], int]:
        """List obligations for a license with enriched JOINs.

        Agent scope: fee_type filters by obligation fee_type (AYUNTAMIENTO/CAMARA),
        ministry_id filters by obligation ministry (MIN_* agents).
        """
        conditions = ["lo.license_id = $1"]
        params = [license_id]
        idx = 2

        if fee_type:
            conditions.append(f"lo.fee_type = ${idx}")
            params.append(fee_type)
            idx += 1

        if ministry_id is not None:
            conditions.append(f"lo.ministry_id = ${idx}")
            params.append(ministry_id)
            idx += 1

        if status:
            conditions.append(f"lo.status = ${idx}")
            params.append(status)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        # Single query for count + KPIs (no page_size limit)
        agg_row = await conn.fetchrow(f"""
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(lo.amount), 0) as total_amount,
                COALESCE(SUM(CASE WHEN lo.status IN ('paid', 'processing', 'completed')
                    THEN lo.amount ELSE 0 END), 0) as paid_amount,
                COALESCE(SUM(lo.penalty_amount), 0) as penalty_amount,
                COUNT(*) FILTER (WHERE lo.status IN ('paid', 'processing', 'completed')) as paid_count,
                COUNT(*) FILTER (WHERE lo.status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE lo.status = 'overdue') as overdue_count
            FROM license_obligations lo
            {where}
        """, *params)
        total = agg_row["total"]
        kpis = {
            "total_amount": agg_row["total_amount"],
            "paid_amount": agg_row["paid_amount"],
            "penalty_amount": agg_row["penalty_amount"],
            "paid_count": agg_row["paid_count"],
            "pending_count": agg_row["pending_count"],
            "overdue_count": agg_row["overdue_count"],
        }

        # Paginated data
        offset = (page - 1) * page_size
        params_data = params + [page_size, offset]
        rows = await conn.fetch(f"""
            SELECT lo.*,
                   fs.name_es as service_name,
                   fs.service_code,
                   m.name_es as ministry_name
            FROM license_obligations lo
            LEFT JOIN fiscal_services fs ON lo.fiscal_service_id = fs.id
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            {where}
            ORDER BY lo.fee_type, fs.service_code
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params_data)

        return [dict(r) for r in rows], total, kpis

    @staticmethod
    async def get_obligation(conn, obligation_id: UUID) -> Optional[Dict]:
        """Get a single obligation with JOINs."""
        row = await conn.fetchrow("""
            SELECT lo.*,
                   fs.name_es as service_name,
                   fs.service_code,
                   m.name_es as ministry_name
            FROM license_obligations lo
            LEFT JOIN fiscal_services fs ON lo.fiscal_service_id = fs.id
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            WHERE lo.id = $1
        """, obligation_id)
        return dict(row) if row else None

    @staticmethod
    async def get_obligations_grouped_by_fee_type(
        conn, license_id: UUID
    ) -> Dict:
        """Group obligations by fee_type with sub-totals."""
        rows = await conn.fetch("""
            SELECT fee_type,
                   COUNT(*) as count,
                   SUM(amount) as subtotal,
                   SUM(penalty_amount) as penalty_subtotal,
                   COUNT(*) FILTER (WHERE status = 'paid') as paid_count,
                   COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                   COUNT(*) FILTER (WHERE status = 'overdue') as overdue_count
            FROM license_obligations
            WHERE license_id = $1
            GROUP BY fee_type
            ORDER BY fee_type
        """, license_id)
        return {r["fee_type"]: dict(r) for r in rows}

    @staticmethod
    async def count_by_status(conn, license_id: UUID) -> Dict:
        """Count obligations by status for a license."""
        rows = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM license_obligations
            WHERE license_id = $1
            GROUP BY status
        """, license_id)
        return {r["status"]: r["count"] for r in rows}

    # ==================================================================
    # Obligations — Write
    # ==================================================================

    @staticmethod
    async def create_obligations_batch(
        conn, license_id: UUID, items: List[Dict]
    ) -> List[Dict]:
        """Bulk insert obligations from bundle items.

        Uses a single INSERT with multiple VALUES rows (no N+1).
        """
        import json as _json

        if not items:
            return []

        # Build VALUES clause with dynamic parameters
        values_parts = []
        params = []
        idx = 1
        for item in items:
            values_parts.append(
                f"(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, ${idx+4}, "
                f"${idx+5}, ${idx+6}, ${idx+7}, ${idx+8})"
            )
            params.extend([
                license_id,
                item["bundle_item_id"],
                item["fiscal_service_id"],
                item.get("ministry_id"),
                item["fee_type"],
                item["amount"],
                item.get("due_date"),
                _json.dumps(item["penalty_config"]) if isinstance(item.get("penalty_config"), dict) else item.get("penalty_config"),
                _json.dumps(item["deadline_config"]) if isinstance(item.get("deadline_config"), dict) else item.get("deadline_config"),
            ])
            idx += 9

        values_sql = ", ".join(values_parts)
        rows = await conn.fetch(f"""
            INSERT INTO license_obligations
                (license_id, bundle_item_id, fiscal_service_id, ministry_id,
                 fee_type, amount, due_date, penalty_config, deadline_config)
            VALUES {values_sql}
            RETURNING *
        """, *params)

        return [dict(r) for r in rows]

    @staticmethod
    async def update_obligation_status(
        conn, obligation_id: UUID, data: Dict
    ) -> Optional[Dict]:
        """Update obligation status and related fields."""
        sets = []
        params = []
        idx = 1

        for field in ["status", "payment_id", "paid_at", "penalty_amount",
                       "issued_document_id", "user_document_id"]:
            if field in data:
                sets.append(f"{field} = ${idx}")
                val = data[field]
                if hasattr(val, "value"):
                    val = val.value
                params.append(val)
                idx += 1

        if not sets:
            return await LicenseRepository.get_obligation(conn, obligation_id)

        params.append(obligation_id)
        row = await conn.fetchrow(f"""
            UPDATE license_obligations
            SET {', '.join(sets)}
            WHERE id = ${idx}
            RETURNING id
        """, *params)

        if not row:
            return None
        return await LicenseRepository.get_obligation(conn, obligation_id)

    # ==================================================================
    # Events — Append-only
    # ==================================================================

    @staticmethod
    async def log_event(
        conn,
        license_id: UUID,
        event_type: str,
        event_data: Optional[Dict] = None,
        obligation_id: Optional[UUID] = None,
        triggered_by: Optional[UUID] = None,
    ) -> Dict:
        """Insert a compliance event (append-only)."""
        import json as _json
        row = await conn.fetchrow("""
            INSERT INTO license_compliance_events
                (license_id, obligation_id, event_type, event_data, triggered_by)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            RETURNING *
        """,
            license_id,
            obligation_id,
            event_type,
            _json.dumps(event_data or {}),
            triggered_by,
        )
        return dict(row)

    @staticmethod
    async def log_events_batch(
        conn,
        license_id: UUID,
        event_type: str,
        items: List[Dict],
        triggered_by: Optional[UUID] = None,
    ) -> List[Dict]:
        """Bulk insert compliance events (single INSERT, no N+1).

        Each item must have:
          - obligation_id: UUID
          - event_data: Dict
        """
        import json as _json

        if not items:
            return []

        values_parts = []
        params = []
        idx = 1
        for item in items:
            values_parts.append(
                f"(${idx}, ${idx+1}, ${idx+2}, ${idx+3}::jsonb, ${idx+4})"
            )
            ed = item.get("event_data", {})
            params.extend([
                license_id,
                item.get("obligation_id"),
                event_type,
                _json.dumps(ed) if isinstance(ed, dict) else (ed or "{}"),
                triggered_by,
            ])
            idx += 5

        values_sql = ", ".join(values_parts)
        rows = await conn.fetch(f"""
            INSERT INTO license_compliance_events
                (license_id, obligation_id, event_type, event_data, triggered_by)
            VALUES {values_sql}
            RETURNING *
        """, *params)

        return [dict(r) for r in rows]

    @staticmethod
    async def list_events(
        conn,
        license_id: UUID,
        event_type: Optional[str] = None,
        obligation_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict], int]:
        """List compliance events for a license (timeline)."""
        conditions = ["lce.license_id = $1"]
        params = [license_id]
        idx = 2

        if event_type:
            conditions.append(f"lce.event_type = ${idx}")
            params.append(event_type)
            idx += 1

        if obligation_id:
            conditions.append(f"lce.obligation_id = ${idx}")
            params.append(obligation_id)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM license_compliance_events lce {where}",
            *params,
        )
        total = count_row["total"]

        offset = (page - 1) * page_size
        params_data = params + [page_size, offset]
        rows = await conn.fetch(f"""
            SELECT lce.*
            FROM license_compliance_events lce
            {where}
            ORDER BY lce.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params_data)

        results = []
        for r in rows:
            d = dict(r)
            # asyncpg returns JSONB as str (no global codec) — parse to dict
            ed = d.get("event_data")
            if isinstance(ed, str):
                d["event_data"] = _json.loads(ed)
            results.append(d)
        return results, total

    # ==================================================================
    # Agent Queue (OMS Post-Payment Processing)
    # ==================================================================

    @staticmethod
    async def get_agent_queue(
        conn,
        ministry_id: Optional[int] = None,
        processing_mode: Optional[str] = None,
        status_filter: Optional[List[str]] = None,
        fee_type: Optional[str] = None,
        search: Optional[str] = None,
        agent_profile_id: Optional[UUID] = None,
        city_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict], int]:
        """Get obligation queue for OMS post-payment agents.

        Ministry agent (Mode A): filter by ministry_id + processing_mode='per_line'
        Polyvalent agent (Mode B): filter by processing_mode='consolidated'

        When agent_profile_id is provided, only obligations assigned to this agent
        are returned (via JOIN assignments). Supervisors pass agent_profile_id=None
        to see all obligations in their scope.
        """
        if status_filter is None:
            status_filter = ["paid", "processing"]

        conditions = []
        params = []
        idx = 1
        assignment_join = ""

        # Status filter
        placeholders = ", ".join(f"${idx + i}" for i in range(len(status_filter)))
        conditions.append(f"lo.status IN ({placeholders})")
        params.extend(status_filter)
        idx += len(status_filter)

        # Ministry filter (Mode A agents)
        if ministry_id is not None:
            conditions.append(f"lo.ministry_id = ${idx}")
            params.append(ministry_id)
            idx += 1

        # Processing mode filter (Mode A vs Mode B)
        if processing_mode:
            conditions.append(f"cl.processing_mode = ${idx}")
            params.append(processing_mode)
            idx += 1

        # Fee type filter
        if fee_type:
            conditions.append(f"lo.fee_type = ${idx}")
            params.append(fee_type)
            idx += 1

        # Search filter (company name, NIF, registration_number, service name)
        if search:
            conditions.append(f"""(
                co.legal_name ILIKE ${idx}
                OR co.nif ILIKE ${idx}
                OR co.registration_number ILIKE ${idx}
                OR fs.name_es ILIKE ${idx}
            )""")
            params.append(f"%{search}%")
            idx += 1

        # City filter (entity_location scope — non-polyvalent agents/supervisors)
        if city_id is not None:
            conditions.append(f"cl.city_id = ${idx}")
            params.append(city_id)
            idx += 1

        # Assignment filter (non-supervisors only see their assigned obligations)
        if agent_profile_id is not None:
            assignment_join = f"""
            JOIN assignments a ON a.item_id = lo.id
                AND a.item_type = 'obligation_processing'
                AND a.agent_profile_id = ${idx}
                AND a.status IN ('assigned', 'in_progress')
            """
            params.append(agent_profile_id)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        count_row = await conn.fetchrow(f"""
            SELECT COUNT(*) as total
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            LEFT JOIN companies co ON cl.company_id = co.id
            LEFT JOIN fiscal_services fs ON lo.fiscal_service_id = fs.id
            {assignment_join}
            {where}
        """, *params)
        total = count_row["total"]

        offset = (page - 1) * page_size
        params_data = params + [page_size, offset]
        rows = await conn.fetch(f"""
            SELECT lo.*,
                   fs.name_es as service_name,
                   fs.service_code,
                   m.name_es as ministry_name,
                   cl.fiscal_year,
                   cl.processing_mode,
                   co.legal_name as company_name,
                   co.nif as company_nif,
                   co.registration_number as company_registration_number,
                   cz.zone_code
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            LEFT JOIN fiscal_services fs ON lo.fiscal_service_id = fs.id
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            LEFT JOIN companies co ON cl.company_id = co.id
            LEFT JOIN commerce_zones cz ON cl.zone_id = cz.id
            {assignment_join}
            {where}
            ORDER BY lo.due_date ASC NULLS LAST, lo.amount DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params_data)

        return [dict(r) for r in rows], total

    @staticmethod
    async def get_agent_queue_stats(
        conn,
        ministry_id: Optional[int] = None,
        processing_mode: Optional[str] = None,
        fee_type: Optional[str] = None,
        agent_profile_id: Optional[UUID] = None,
        city_id: Optional[UUID] = None,
    ) -> Dict:
        """Aggregated stats for agent OMS dashboard.

        When agent_profile_id is provided, stats are scoped to assigned obligations.
        fee_type is used for independent agents (ayuntamiento=municipal, camara=chamber).
        """
        conditions = []
        params = []
        idx = 1
        assignment_join = ""

        if ministry_id is not None:
            conditions.append(f"lo.ministry_id = ${idx}")
            params.append(ministry_id)
            idx += 1

        if processing_mode:
            conditions.append(f"cl.processing_mode = ${idx}")
            params.append(processing_mode)
            idx += 1

        if fee_type:
            conditions.append(f"lo.fee_type = ${idx}")
            params.append(fee_type)
            idx += 1

        if city_id is not None:
            conditions.append(f"cl.city_id = ${idx}")
            params.append(city_id)
            idx += 1

        if agent_profile_id is not None:
            assignment_join = f"""
            JOIN assignments a ON a.item_id = lo.id
                AND a.item_type = 'obligation_processing'
                AND a.agent_profile_id = ${idx}
                AND a.status IN ('assigned', 'in_progress', 'completed')
            """
            params.append(agent_profile_id)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # When agent_profile_id is set the assignment JOIN is present,
        # so a.started_at is available for the not_started metric.
        has_assignment_join = agent_profile_id is not None

        row = await conn.fetchrow(f"""
            SELECT
                COUNT(*) FILTER (WHERE lo.status IN ('paid', 'processing')) as pending_count,
                COUNT(*) FILTER (
                    WHERE lo.status = 'completed'
                    AND lo.updated_at::date = CURRENT_DATE
                ) as completed_today,
                COALESCE(SUM(lo.amount) FILTER (
                    WHERE lo.status IN ('paid', 'processing')
                ), 0) as total_amount_pending,
                COALESCE(SUM(lo.amount) FILTER (
                    WHERE lo.status = 'completed'
                    AND lo.updated_at::date = CURRENT_DATE
                ), 0) as total_amount_completed_today,
                COUNT(*) FILTER (
                    WHERE lo.status = 'processing'
                    AND lo.issued_document_id IS NULL
                ) as awaiting_document,
                {"COUNT(*) FILTER (WHERE a.started_at IS NULL AND a.status = 'assigned') as not_started"
                 if has_assignment_join else "0 as not_started"}
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            {assignment_join}
            {where}
        """, *params)
        return dict(row)

    @staticmethod
    async def get_compliance_summary(
        conn,
        fiscal_year: int,
        ministry_id: Optional[int] = None,
        city_id: Optional[UUID] = None,
        fee_type: Optional[str] = None,
    ) -> List[Dict]:
        """Aggregated compliance summary by fee_type for a fiscal year.

        Agent scope: city_id filters licenses by city, fee_type limits to agent's scope.
        Single query using LATERAL JOIN for overdue companies — no N+1.
        Returns 1 row per fee_type with: counts, amounts, recovery %, overdue companies.
        """
        import json as _json

        conditions = ["cl.fiscal_year = $1"]
        params: list = [fiscal_year]
        idx = 2

        if ministry_id is not None:
            conditions.append(f"lo.ministry_id = ${idx}")
            params.append(ministry_id)
            idx += 1

        if city_id is not None:
            conditions.append(f"cl.city_id = ${idx}")
            params.append(city_id)
            idx += 1

        if fee_type:
            conditions.append(f"lo.fee_type = ${idx}")
            params.append(fee_type)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)
        ministry_clause = f"AND lo2.ministry_id = $2" if ministry_id is not None else ""

        # Single query: aggregation + overdue companies via LATERAL subquery
        rows = await conn.fetch(f"""
            WITH fee_stats AS (
                SELECT
                    lo.fee_type,
                    COUNT(*) as total_obligations,
                    COUNT(*) FILTER (
                        WHERE lo.status IN ('paid', 'completed', 'processing')
                    ) as paid,
                    COUNT(*) FILTER (
                        WHERE lo.status IN ('pending', 'selected', 'payment_pending')
                    ) as pending,
                    COUNT(*) FILTER (WHERE lo.status = 'overdue') as overdue,
                    COALESCE(SUM(lo.amount), 0) as total_amount,
                    COALESCE(SUM(lo.amount) FILTER (
                        WHERE lo.status IN ('paid', 'completed', 'processing')
                    ), 0) as paid_amount,
                    COALESCE(SUM(lo.amount) FILTER (
                        WHERE lo.status = 'overdue'
                    ), 0) as overdue_amount,
                    COALESCE(SUM(lo.penalty_amount) FILTER (
                        WHERE lo.status = 'overdue'
                    ), 0) as overdue_penalty
                FROM license_obligations lo
                JOIN commercial_licenses cl ON cl.id = lo.license_id
                {where}
                GROUP BY lo.fee_type
            ),
            overdue_companies AS (
                SELECT
                    lo2.fee_type,
                    co.legal_name as company_name,
                    co.nif as company_nif,
                    cz.zone_code,
                    cl2.id as license_id,
                    SUM(lo2.amount) as amount,
                    COALESCE(SUM(lo2.penalty_amount), 0) as penalty,
                    ROW_NUMBER() OVER (
                        PARTITION BY lo2.fee_type
                        ORDER BY SUM(lo2.amount) DESC
                    ) as rn
                FROM license_obligations lo2
                JOIN commercial_licenses cl2 ON cl2.id = lo2.license_id
                LEFT JOIN companies co ON cl2.company_id = co.id
                LEFT JOIN commerce_zones cz ON cl2.zone_id = cz.id
                WHERE lo2.status = 'overdue'
                  AND cl2.fiscal_year = $1
                  {ministry_clause}
                GROUP BY lo2.fee_type, co.legal_name, co.nif,
                         cz.zone_code, cl2.id
            )
            SELECT
                fs.*,
                COALESCE(
                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'company_name', oc.company_name,
                            'company_nif', oc.company_nif,
                            'zone', oc.zone_code,
                            'license_id', oc.license_id::text,
                            'amount', oc.amount,
                            'penalty', oc.penalty
                        ) ORDER BY oc.amount DESC
                    ) FILTER (WHERE oc.company_name IS NOT NULL AND oc.rn <= 50),
                    '[]'::json
                ) as overdue_companies_json
            FROM fee_stats fs
            LEFT JOIN overdue_companies oc ON oc.fee_type = fs.fee_type
            GROUP BY fs.fee_type, fs.total_obligations, fs.paid,
                     fs.pending, fs.overdue, fs.total_amount,
                     fs.paid_amount, fs.overdue_amount, fs.overdue_penalty
            ORDER BY fs.overdue_amount DESC
        """, *params)

        result = []
        for r in rows:
            total = float(r["total_amount"]) if r["total_amount"] else 0
            paid = float(r["paid_amount"]) if r["paid_amount"] else 0
            recovery_pct = round((paid / total) * 100) if total > 0 else 0

            # Parse JSON-aggregated overdue companies (already sorted, limited)
            raw_companies = r["overdue_companies_json"]
            if isinstance(raw_companies, str):
                overdue_companies = _json.loads(raw_companies)
            elif isinstance(raw_companies, list):
                overdue_companies = raw_companies
            else:
                overdue_companies = []

            result.append({
                "fee_type": r["fee_type"],
                "total_obligations": r["total_obligations"],
                "paid": r["paid"],
                "pending": r["pending"],
                "overdue": r["overdue"],
                "total_amount": float(r["total_amount"]),
                "paid_amount": float(r["paid_amount"]),
                "overdue_amount": float(r["overdue_amount"]),
                "overdue_penalty": float(r["overdue_penalty"]),
                "recovery_pct": recovery_pct,
                "overdue_companies": [
                    {
                        "company_name": c.get("company_name") or "—",
                        "company_nif": c.get("company_nif"),
                        "zone": c.get("zone") or c.get("zone_code"),
                        "license_id": str(c.get("license_id", "")),
                        "amount": float(c.get("amount", 0)),
                        "penalty": float(c.get("penalty", 0)),
                    }
                    for c in overdue_companies
                ],
            })

        return result

    # ==================================================================
    # Stats
    # ==================================================================

    @staticmethod
    async def get_dashboard_stats(
        conn,
        fiscal_year: Optional[int] = None,
        # Agent scope filters
        city_id: Optional[UUID] = None,
        fee_type: Optional[str] = None,
        ministry_id: Optional[int] = None,
        processing_mode: Optional[str] = None,
    ) -> Dict:
        """Aggregate stats scoped by agent context.

        When agent scope filters are provided, stats reflect only the
        licenses/obligations visible to that agent. Uses obligation-level
        aggregation for fee_type/ministry scoping to show accurate amounts.
        """
        conditions = []
        params: list = []
        idx = 1

        if fiscal_year:
            conditions.append(f"cl.fiscal_year = ${idx}")
            params.append(fiscal_year)
            idx += 1

        if city_id is not None:
            conditions.append(f"cl.city_id = ${idx}")
            params.append(city_id)
            idx += 1

        if processing_mode:
            conditions.append(f"cl.processing_mode = ${idx}")
            params.append(processing_mode)
            idx += 1

        # fee_type/ministry scoping: only count licenses that have matching obligations
        if fee_type:
            conditions.append(f"""EXISTS (
                SELECT 1 FROM license_obligations lo_s
                WHERE lo_s.license_id = cl.id AND lo_s.fee_type = ${idx}
            )""")
            params.append(fee_type)
            idx += 1

        if ministry_id is not None:
            conditions.append(f"""EXISTS (
                SELECT 1 FROM license_obligations lo_s
                WHERE lo_s.license_id = cl.id AND lo_s.ministry_id = ${idx}
            )""")
            params.append(ministry_id)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # When scoped by fee_type or ministry_id, we aggregate from obligations
        # to show accurate amounts for the agent's scope (not full license totals)
        if fee_type or ministry_id is not None:
            # Obligation-level aggregation — parameterized (no string interpolation)
            ob_conditions = []
            ob_params = list(params)  # copy existing params
            ob_idx = idx

            if fee_type:
                ob_conditions.append(f"lo.fee_type = ${ob_idx}")
                ob_params.append(fee_type)
                ob_idx += 1
            if ministry_id is not None:
                ob_conditions.append(f"lo.ministry_id = ${ob_idx}")
                ob_params.append(ministry_id)
                ob_idx += 1

            ob_filter = " AND " + " AND ".join(ob_conditions) if ob_conditions else ""

            row = await conn.fetchrow(f"""
                WITH scoped_licenses AS (
                    SELECT cl.id, cl.status
                    FROM commercial_licenses cl
                    {where}
                ),
                scoped_amounts AS (
                    SELECT
                        lo.license_id,
                        SUM(lo.amount) as total_amount,
                        SUM(CASE WHEN lo.status IN ('paid', 'processing', 'completed') THEN lo.amount ELSE 0 END) as amount_paid,
                        SUM(COALESCE(lo.penalty_amount, 0)) as penalty_amount
                    FROM license_obligations lo
                    JOIN scoped_licenses sl ON sl.id = lo.license_id
                    WHERE 1=1 {ob_filter}
                    GROUP BY lo.license_id
                )
                SELECT
                    (SELECT COUNT(*) FROM scoped_licenses) as total_licenses,
                    (SELECT COUNT(*) FROM scoped_licenses WHERE status IN ('open', 'partial')) as active_licenses,
                    (SELECT COUNT(*) FROM scoped_licenses WHERE status = 'open') as open_licenses,
                    (SELECT COUNT(*) FROM scoped_licenses WHERE status = 'partial') as partial_licenses,
                    (SELECT COUNT(*) FROM scoped_licenses WHERE status = 'complete') as complete_licenses,
                    (SELECT COUNT(*) FROM scoped_licenses WHERE status = 'overdue') as overdue_licenses,
                    COALESCE((SELECT SUM(total_amount) FROM scoped_amounts), 0) as total_amount,
                    COALESCE((SELECT SUM(amount_paid) FROM scoped_amounts), 0) as amount_paid,
                    COALESCE((SELECT SUM(amount_paid) FROM scoped_amounts), 0) as total_paid,
                    COALESCE((SELECT SUM(total_amount) FROM scoped_amounts)
                           - (SELECT SUM(amount_paid) FROM scoped_amounts), 0) as total_debt,
                    COALESCE((SELECT SUM(penalty_amount) FROM scoped_amounts), 0) as penalty_amount,
                    CASE WHEN COALESCE((SELECT SUM(total_amount) FROM scoped_amounts), 0) > 0
                         THEN ROUND(
                            (SELECT SUM(amount_paid) FROM scoped_amounts) * 100.0
                            / (SELECT SUM(total_amount) FROM scoped_amounts), 1)
                         ELSE 0 END as recovery_rate,
                    0 as avg_compliance_score
            """, *ob_params)
        else:
            # No obligation scoping — use license-level totals (faster)
            row = await conn.fetchrow(f"""
                SELECT
                    COUNT(*) as total_licenses,
                    COUNT(*) FILTER (WHERE cl.status IN ('open', 'partial')) as active_licenses,
                    COUNT(*) FILTER (WHERE cl.status = 'open') as open_licenses,
                    COUNT(*) FILTER (WHERE cl.status = 'partial') as partial_licenses,
                    COUNT(*) FILTER (WHERE cl.status = 'complete') as complete_licenses,
                    COUNT(*) FILTER (WHERE cl.status = 'overdue') as overdue_licenses,
                    COALESCE(SUM(cl.total_amount), 0) as total_amount,
                    COALESCE(SUM(cl.amount_paid), 0) as amount_paid,
                    COALESCE(SUM(cl.amount_paid), 0) as total_paid,
                    COALESCE(SUM(cl.total_amount) - SUM(cl.amount_paid), 0) as total_debt,
                    COALESCE(SUM(cl.penalty_amount), 0) as penalty_amount,
                    CASE WHEN COALESCE(SUM(cl.total_amount), 0) > 0
                         THEN ROUND(SUM(cl.amount_paid) * 100.0 / SUM(cl.total_amount), 1)
                         ELSE 0 END as recovery_rate,
                    COALESCE(AVG(cl.compliance_score), 0) as avg_compliance_score
                FROM commercial_licenses cl
                {where}
            """, *params)
        return dict(row)

    # ==================================================================
    # Supervisor — Team performance
    # ==================================================================

    @staticmethod
    async def get_team_performance(
        conn,
        ministry_id: Optional[int] = None,
        processing_mode: Optional[str] = None,
        fee_type: Optional[str] = None,
        city_id: Optional[UUID] = None,
        period_days: int = 30,
        fiscal_year: int = 2026,
    ) -> Dict:
        """Per-agent OMS obligation processing metrics.

        Single query joining assignments + obligations + events + agent profiles.
        Scoped by supervisor's ministry/mode/fee_type.
        """
        from datetime import datetime, timedelta, timezone

        conditions = ["a.item_type = 'obligation_processing'"]
        params: list = []
        idx = 1

        # Period filter
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        conditions.append(f"a.created_at >= ${idx}")
        params.append(cutoff)
        idx += 1

        # Fiscal year filter
        conditions.append(f"cl.fiscal_year = ${idx}")
        params.append(fiscal_year)
        idx += 1

        # Scope filters (same as queue)
        if ministry_id is not None:
            conditions.append(f"lo.ministry_id = ${idx}")
            params.append(ministry_id)
            idx += 1

        if processing_mode:
            conditions.append(f"cl.processing_mode = ${idx}")
            params.append(processing_mode)
            idx += 1

        if fee_type:
            conditions.append(f"lo.fee_type = ${idx}")
            params.append(fee_type)
            idx += 1

        if city_id is not None:
            conditions.append(f"cl.city_id = ${idx}")
            params.append(city_id)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        rows = await conn.fetch(f"""
            SELECT
                ap.id as agent_profile_id,
                u.first_name || ' ' || u.last_name as agent_name,
                r.code as role_code,
                e.code as entity_code,
                COALESCE(aw.availability, 'available') as availability,
                COUNT(a.id) as obligations_assigned,
                COUNT(a.id) FILTER (
                    WHERE a.status = 'completed'
                ) as obligations_completed,
                COUNT(a.id) FILTER (
                    WHERE a.status IN ('assigned', 'in_progress')
                ) as obligations_pending,
                COALESCE(SUM(lo.amount) FILTER (
                    WHERE a.status = 'completed'
                ), 0) as amount_processed,
                ROUND(
                    AVG(
                        EXTRACT(EPOCH FROM (a.completed_at - a.created_at)) / 60
                    ) FILTER (WHERE a.status = 'completed' AND a.completed_at IS NOT NULL),
                    1
                ) as avg_processing_minutes
            FROM assignments a
            JOIN license_obligations lo ON lo.id = a.item_id
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            JOIN agent_profiles ap ON ap.id = a.agent_profile_id
            LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
            JOIN users u ON u.id = ap.user_id AND u.status = 'active'
            JOIN roles r ON r.id = u.role_id
            JOIN entities e ON e.id = ap.entity_id
            {where}
            GROUP BY ap.id, u.first_name, u.last_name, r.code,
                     e.code, aw.availability
            ORDER BY obligations_completed DESC
        """, *params)

        # Count rejections separately (from compliance events)
        rejection_counts: Dict = {}
        if rows:
            agent_ids = [r["agent_profile_id"] for r in rows]
            rejections = await conn.fetch(f"""
                SELECT
                    ap.id as agent_profile_id,
                    COUNT(lce.id) as rejection_count
                FROM license_compliance_events lce
                JOIN agent_profiles ap ON lce.triggered_by = ap.user_id
                WHERE lce.event_type = 'agent_rejected'
                  AND lce.created_at >= $1
                  AND ap.id = ANY($2::uuid[])
                GROUP BY ap.id
            """, cutoff, agent_ids)
            rejection_counts = {r["agent_profile_id"]: r["rejection_count"] for r in rejections}

        agents = []
        total_assigned = 0
        total_completed = 0
        total_pending = 0
        total_amount = 0

        for r in rows:
            assigned = r["obligations_assigned"]
            completed = r["obligations_completed"]
            pending = r["obligations_pending"]
            rejected = rejection_counts.get(r["agent_profile_id"], 0)
            amount = float(r["amount_processed"]) if r["amount_processed"] else 0
            completion_rate = round((completed / assigned) * 100, 1) if assigned > 0 else 0
            rejection_rate = round((rejected / assigned) * 100, 1) if assigned > 0 else 0

            total_assigned += assigned
            total_completed += completed
            total_pending += pending
            total_amount += amount

            agents.append({
                "agent_profile_id": str(r["agent_profile_id"]),
                "agent_name": r["agent_name"],
                "role_code": r["role_code"],
                "entity_code": r["entity_code"],
                "availability": r["availability"],
                "obligations_assigned": assigned,
                "obligations_completed": completed,
                "obligations_pending": pending,
                "obligations_rejected": rejected,
                "amount_processed": amount,
                "avg_processing_minutes": float(r["avg_processing_minutes"] or 0),
                "completion_rate": completion_rate,
                "rejection_rate": rejection_rate,
            })

        avg_rate = round((total_completed / total_assigned) * 100, 1) if total_assigned > 0 else 0

        return {
            "agents": agents,
            "team_totals": {
                "total_agents": len(agents),
                "total_assigned": total_assigned,
                "total_completed": total_completed,
                "total_pending": total_pending,
                "total_amount_processed": total_amount,
                "avg_completion_rate": avg_rate,
            },
            "period_days": period_days,
            "fiscal_year": fiscal_year,
        }
