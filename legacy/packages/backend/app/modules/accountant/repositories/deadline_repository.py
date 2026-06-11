"""
Accountant Deadline Repository - Data access layer for deadline tracking

Optimized queries for accountants to track deadlines across all client companies.
Uses PostgreSQL date functions, CTEs, and window functions for efficient aggregation.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from loguru import logger
import asyncpg

from app.modules.accountant.models import (
    DeadlinePriority,
    DeadlineSeverity,
    DeadlineFilters,
)


class AccountantDeadlineRepository:
    """Repository for accountant deadline tracking with optimized queries"""

    @staticmethod
    def _calculate_priority_score(
        days_until_due: int,
        amount: Optional[Decimal],
        declaration_type: str,
        escalated: bool = False,
    ) -> Tuple[int, DeadlinePriority]:
        """
        Calculate priority score (0-100) based on multiple factors

        Scoring logic:
        - Base: 0 points
        - +40 if days_until_due <= 3 (urgent deadline)
        - +30 if days_until_due <= 7 (warning)
        - +20 if amount > 1,000,000 XAF (large tax payment)
        - +15 if declaration_type is high-volume (iva_real, iva_destajo)
        - +20 if escalated

        Priority levels:
        - URGENT: 80-100
        - HIGH: 60-79
        - MEDIUM: 30-59
        - LOW: 0-29
        """
        score = 0

        # Time-based scoring
        if days_until_due <= 0:
            score += 50  # Overdue gets highest base score
        elif days_until_due <= 3:
            score += 40
        elif days_until_due <= 7:
            score += 30
        elif days_until_due <= 14:
            score += 15

        # Amount-based scoring
        if amount:
            if amount > 5_000_000:  # 5M XAF
                score += 25
            elif amount > 1_000_000:  # 1M XAF
                score += 20
            elif amount > 500_000:  # 500K XAF
                score += 10

        # Declaration type scoring (high-volume types)
        high_volume_types = ["iva_real", "iva_destajo", "vat_declaration", "income_tax"]
        if declaration_type in high_volume_types:
            score += 15

        # Escalation bonus
        if escalated:
            score += 20

        # Determine priority level
        if score >= 80:
            priority = DeadlinePriority.URGENT
        elif score >= 60:
            priority = DeadlinePriority.HIGH
        elif score >= 30:
            priority = DeadlinePriority.MEDIUM
        else:
            priority = DeadlinePriority.LOW

        return min(score, 100), priority

    @staticmethod
    def _build_filter_conditions(filters: Optional[DeadlineFilters]) -> Tuple[str, List[Any]]:
        """Build SQL WHERE conditions from filters"""
        conditions = []
        params = []
        param_count = 0

        if not filters:
            return "", params

        if filters.start_date:
            param_count += 1
            conditions.append(f"d.fiscal_period_end >= ${param_count}")
            params.append(filters.start_date)

        if filters.end_date:
            param_count += 1
            conditions.append(f"d.fiscal_period_end <= ${param_count}")
            params.append(filters.end_date)

        if filters.company_ids:
            param_count += 1
            conditions.append(f"d.company_id = ANY(${param_count})")
            params.append(filters.company_ids)

        if filters.declaration_types:
            param_count += 1
            # Cast enum to text for comparison
            conditions.append(f"d.declaration_type::text = ANY(${param_count}::text[])")
            params.append(filters.declaration_types)

        if filters.status:
            param_count += 1
            conditions.append(f"d.status = ${param_count}")
            params.append(filters.status.value)

        if filters.assigned_agent:
            param_count += 1
            conditions.append(f"cm.user_id = ${param_count}")
            params.append(filters.assigned_agent)

        if filters.min_amount:
            param_count += 1
            conditions.append(f"d.calculated_tax >= ${param_count}")
            params.append(filters.min_amount)

        if filters.max_amount:
            param_count += 1
            conditions.append(f"d.calculated_tax <= ${param_count}")
            params.append(filters.max_amount)

        where_clause = " AND " + " AND ".join(conditions) if conditions else ""
        return where_clause, params

    async def get_upcoming_deadlines(
        self,
        conn: asyncpg.Connection,
        accountant_user_id: str,
        filters: Optional[DeadlineFilters] = None,
        sort_by: str = "due_date",  # due_date, priority, company_name, amount
        sort_order: str = "asc",  # asc, desc
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get upcoming deadlines across all client companies

        Query optimization notes:
        - Uses CTE to calculate days_until_due once
        - JOIN with companies and company_members to filter by accountant
        - Uses GIN index on company_members(user_id) for fast filtering
        - LIMIT/OFFSET for pagination
        - Window function COUNT(*) OVER() to get total without separate query

        Args:
            accountant_user_id: Accountant's user ID (filters to their clients)
            filters: Optional filters for date range, company, type, etc.
            sort_by: Field to sort by
            sort_order: Sort direction
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (deadlines list, total count)
        """
        try:
            # Build filter conditions
            filter_where, filter_params = self._build_filter_conditions(filters)

            # Map sort fields to SQL columns
            sort_field_map = {
                "due_date": "d.fiscal_period_end",
                "priority": "d.calculated_tax",  # Approximate for now
                "company_name": "c.name",
                "amount": "d.calculated_tax",
            }
            sort_field = sort_field_map.get(sort_by, "d.fiscal_period_end")
            sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"

            # Base param count after filters
            param_count = len(filter_params)

            query = f"""
                WITH deadline_calc AS (
                    SELECT
                        d.id,
                        d.company_id,
                        d.declaration_type,
                        d.status,
                        d.fiscal_period_start,
                        d.fiscal_period_end,
                        d.tax_year,
                        d.calculated_tax,
                        d.created_at,
                        d.updated_at,
                        -- Calculate days until due (fiscal_period_end is due date)
                        EXTRACT(DAY FROM (d.fiscal_period_end - CURRENT_DATE))::INTEGER AS days_until_due,
                        -- Check if escalated (join with agent_work_queue if exists)
                        COALESCE(awq.escalated, false) AS escalated,
                        awq.assigned_to AS agent_assigned,
                        c.id AS company_id_full,
                        c.name AS company_name,
                        c.tax_id AS company_tax_id,
                        c.email AS company_email,
                        c.phone AS company_phone,
                        COUNT(*) OVER() AS total_count
                    FROM tax_declarations d
                    INNER JOIN companies c ON d.company_id = c.id
                    INNER JOIN company_members cm ON c.id = cm.company_id
                    LEFT JOIN agent_work_queue awq ON awq.item_id = d.id AND awq.item_type = 'declaration'
                    WHERE
                        -- Filter to accountant's client companies
                        cm.user_id = ${param_count + 1}
                        -- Only active accountant/owner roles
                        AND cm.role IN ('company_accountant', 'company_owner', 'company_admin')
                        -- Only upcoming deadlines (due date in future)
                        AND d.fiscal_period_end > CURRENT_DATE
                        -- Exclude completed/rejected declarations
                        AND d.status NOT IN ('approved', 'rejected')
                        {filter_where}
                )
                SELECT
                    id,
                    company_id,
                    company_name,
                    company_tax_id,
                    company_email,
                    company_phone,
                    declaration_type,
                    status,
                    fiscal_period_start,
                    fiscal_period_end,
                    tax_year,
                    calculated_tax,
                    days_until_due,
                    escalated,
                    agent_assigned,
                    created_at,
                    updated_at,
                    total_count
                FROM deadline_calc
                ORDER BY {sort_field} {sort_direction}
                LIMIT ${param_count + 2}
                OFFSET ${param_count + 3}
            """

            # Combine all params
            all_params = filter_params + [accountant_user_id, limit, offset]

            results = await conn.fetch(query, *all_params)

            if not results:
                return [], 0

            total_count = results[0]["total_count"] if results else 0

            # Calculate priority scores in Python (could be moved to SQL for performance)
            deadlines = []
            for row in results:
                score, priority = self._calculate_priority_score(
                    days_until_due=row["days_until_due"],
                    amount=row["calculated_tax"],
                    declaration_type=row["declaration_type"],
                    escalated=row["escalated"],
                )

                deadline = {
                    "id": str(row["id"]),
                    "company": {
                        "id": str(row["company_id"]),
                        "name": row["company_name"],
                        "tax_id": row["company_tax_id"],
                        "email": row["company_email"],
                        "phone": row["company_phone"],
                    },
                    "declaration": {
                        "id": str(row["id"]),
                        "declaration_type": row["declaration_type"],
                        "status": row["status"],
                        "fiscal_period_start": row["fiscal_period_start"],
                        "fiscal_period_end": row["fiscal_period_end"],
                        "tax_year": row["tax_year"],
                        "calculated_tax": row["calculated_tax"],
                        "reference_number": None,  # TODO: Add reference field
                    },
                    "due_date": row["fiscal_period_end"],
                    "days_until_due": row["days_until_due"],
                    "priority": priority.value,
                    "priority_score": score,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "email_notifications": True,
                    "sms_notifications": False,
                    "agent_assigned": str(row["agent_assigned"]) if row["agent_assigned"] else None,
                    "notes": None,
                }
                deadlines.append(deadline)

            logger.info(
                f"Retrieved {len(deadlines)} upcoming deadlines for accountant {accountant_user_id} "
                f"(total: {total_count})"
            )
            return deadlines, total_count

        except Exception as e:
            logger.error(f"Error fetching upcoming deadlines: {str(e)}")
            raise

    async def get_overdue_deadlines(
        self,
        conn: asyncpg.Connection,
        accountant_user_id: str,
        filters: Optional[DeadlineFilters] = None,
        group_by_severity: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], int]:
        """
        Get overdue deadlines grouped by severity

        Query optimization notes:
        - Uses CASE WHEN for severity classification
        - Single query with grouping done in application layer
        - Index on (status, fiscal_period_end) for fast overdue filtering

        Severity levels:
        - RECENT: 1-7 days overdue
        - MODERATE: 7-30 days overdue
        - CRITICAL: 30+ days overdue

        Returns:
            Tuple of (all_deadlines, grouped_by_severity, total_count)
        """
        try:
            filter_where, filter_params = self._build_filter_conditions(filters)
            param_count = len(filter_params)

            query = f"""
                WITH overdue_calc AS (
                    SELECT
                        d.id,
                        d.company_id,
                        d.declaration_type,
                        d.status,
                        d.fiscal_period_start,
                        d.fiscal_period_end,
                        d.tax_year,
                        d.calculated_tax,
                        d.created_at,
                        d.updated_at,
                        -- Calculate days overdue (negative days_until_due)
                        EXTRACT(DAY FROM (CURRENT_DATE - d.fiscal_period_end))::INTEGER AS days_overdue,
                        -- Severity classification
                        CASE
                            WHEN EXTRACT(DAY FROM (CURRENT_DATE - d.fiscal_period_end)) BETWEEN 1 AND 7 THEN 'recent'
                            WHEN EXTRACT(DAY FROM (CURRENT_DATE - d.fiscal_period_end)) BETWEEN 8 AND 30 THEN 'moderate'
                            WHEN EXTRACT(DAY FROM (CURRENT_DATE - d.fiscal_period_end)) > 30 THEN 'critical'
                            ELSE 'recent'
                        END AS severity,
                        -- Escalation info
                        COALESCE(awq.escalated, false) AS escalated,
                        awq.escalated_at,
                        awq.escalation_reason,
                        awq.assigned_to AS agent_assigned,
                        c.id AS company_id_full,
                        c.name AS company_name,
                        c.tax_id AS company_tax_id,
                        c.email AS company_email,
                        c.phone AS company_phone,
                        COUNT(*) OVER() AS total_count
                    FROM tax_declarations d
                    INNER JOIN companies c ON d.company_id = c.id
                    INNER JOIN company_members cm ON c.id = cm.company_id
                    LEFT JOIN agent_work_queue awq ON awq.item_id = d.id AND awq.item_type = 'declaration'
                    WHERE
                        cm.user_id = ${param_count + 1}
                        AND cm.role IN ('company_accountant', 'company_owner', 'company_admin')
                        -- Only overdue (due date in past)
                        AND d.fiscal_period_end < CURRENT_DATE
                        -- Exclude completed/rejected
                        AND d.status NOT IN ('approved', 'rejected')
                        {filter_where}
                )
                SELECT
                    id,
                    company_id,
                    company_name,
                    company_tax_id,
                    company_email,
                    company_phone,
                    declaration_type,
                    status,
                    fiscal_period_start,
                    fiscal_period_end,
                    tax_year,
                    calculated_tax,
                    days_overdue,
                    severity,
                    escalated,
                    escalated_at,
                    escalation_reason,
                    agent_assigned,
                    created_at,
                    updated_at,
                    total_count
                FROM overdue_calc
                ORDER BY days_overdue DESC, calculated_tax DESC
                LIMIT ${param_count + 2}
                OFFSET ${param_count + 3}
            """

            all_params = filter_params + [accountant_user_id, limit, offset]
            results = await conn.fetch(query, *all_params)

            if not results:
                return [], {}, 0

            total_count = results[0]["total_count"] if results else 0

            # Process results and group by severity
            all_deadlines = []
            grouped = {
                DeadlineSeverity.RECENT.value: [],
                DeadlineSeverity.MODERATE.value: [],
                DeadlineSeverity.CRITICAL.value: [],
            }

            for row in results:
                # Calculate priority with overdue penalty
                score, priority = self._calculate_priority_score(
                    days_until_due=-row["days_overdue"],  # Negative for overdue
                    amount=row["calculated_tax"],
                    declaration_type=row["declaration_type"],
                    escalated=row["escalated"],
                )

                deadline = {
                    "id": str(row["id"]),
                    "company": {
                        "id": str(row["company_id"]),
                        "name": row["company_name"],
                        "tax_id": row["company_tax_id"],
                        "email": row["company_email"],
                        "phone": row["company_phone"],
                    },
                    "declaration": {
                        "id": str(row["id"]),
                        "declaration_type": row["declaration_type"],
                        "status": row["status"],
                        "fiscal_period_start": row["fiscal_period_start"],
                        "fiscal_period_end": row["fiscal_period_end"],
                        "tax_year": row["tax_year"],
                        "calculated_tax": row["calculated_tax"],
                        "reference_number": None,
                    },
                    "due_date": row["fiscal_period_end"],
                    "days_overdue": row["days_overdue"],
                    "severity": row["severity"],
                    "priority_score": score,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "escalated": row["escalated"],
                    "escalated_at": row["escalated_at"],
                    "escalation_reason": row["escalation_reason"],
                    "agent_assigned": str(row["agent_assigned"]) if row["agent_assigned"] else None,
                    "notes": None,
                    "last_contact_date": None,
                }

                all_deadlines.append(deadline)

                # Group by severity
                if group_by_severity:
                    grouped[row["severity"]].append(deadline)

            logger.info(
                f"Retrieved {len(all_deadlines)} overdue deadlines for accountant {accountant_user_id} "
                f"(recent: {len(grouped['recent'])}, moderate: {len(grouped['moderate'])}, "
                f"critical: {len(grouped['critical'])})"
            )

            return all_deadlines, grouped, total_count

        except Exception as e:
            logger.error(f"Error fetching overdue deadlines: {str(e)}")
            raise

    async def get_calendar_view(
        self,
        conn: asyncpg.Connection,
        accountant_user_id: str,
        start_date: date,
        end_date: date,
        view_type: str = "month",  # day, week, month
    ) -> Dict[str, Any]:
        """
        Get calendar view data with deadline aggregations

        Query optimization notes:
        - Uses date_trunc for grouping by day/week/month
        - Aggregates counts and sums in SQL
        - Returns efficient summary data for calendar rendering

        Args:
            accountant_user_id: Accountant's user ID
            start_date: Start of date range
            end_date: End of date range
            view_type: Aggregation level (day, week, month)

        Returns:
            Dict with calendar data grouped by view_type
        """
        try:
            if view_type == "day":
                # Daily view with all deadlines per day
                query = """
                    SELECT
                        DATE(d.fiscal_period_end) AS deadline_date,
                        COUNT(*) AS count,
                        SUM(d.calculated_tax) AS total_amount,
                        json_agg(
                            json_build_object(
                                'id', d.id,
                                'company_name', c.name,
                                'declaration_type', d.declaration_type,
                                'amount', d.calculated_tax
                            )
                        ) AS deadlines
                    FROM tax_declarations d
                    INNER JOIN companies c ON d.company_id = c.id
                    INNER JOIN company_members cm ON c.id = cm.company_id
                    WHERE
                        cm.user_id = $1
                        AND cm.role IN ('company_accountant', 'company_owner', 'company_admin')
                        AND d.fiscal_period_end BETWEEN $2 AND $3
                        AND d.status NOT IN ('approved', 'rejected')
                    GROUP BY DATE(d.fiscal_period_end)
                    ORDER BY deadline_date ASC
                """
                results = await conn.fetch(query, accountant_user_id, start_date, end_date)

                days = []
                for row in results:
                    days.append({
                        "date": row["deadline_date"],
                        "count": row["count"],
                        "total_amount": row["total_amount"],
                        "deadlines": row["deadlines"],
                    })

                return {
                    "view_type": "day",
                    "start_date": start_date,
                    "end_date": end_date,
                    "days": days,
                    "summary": {
                        "total_deadlines": sum(d["count"] for d in days),
                        "total_amount": sum(d["total_amount"] or 0 for d in days),
                        "busiest_day": max(days, key=lambda d: d["count"])["date"] if days else None,
                    },
                }

            elif view_type == "week":
                # Weekly aggregation
                query = """
                    SELECT
                        DATE_TRUNC('week', d.fiscal_period_end)::DATE AS week_start,
                        (DATE_TRUNC('week', d.fiscal_period_end) + INTERVAL '6 days')::DATE AS week_end,
                        EXTRACT(WEEK FROM d.fiscal_period_end)::INTEGER AS week_number,
                        COUNT(*) AS count,
                        SUM(d.calculated_tax) AS total_amount,
                        COUNT(*) FILTER (WHERE d.calculated_tax > 1000000) AS high_priority_count
                    FROM tax_declarations d
                    INNER JOIN companies c ON d.company_id = c.id
                    INNER JOIN company_members cm ON c.id = cm.company_id
                    WHERE
                        cm.user_id = $1
                        AND cm.role IN ('company_accountant', 'company_owner', 'company_admin')
                        AND d.fiscal_period_end BETWEEN $2 AND $3
                        AND d.status NOT IN ('approved', 'rejected')
                    GROUP BY DATE_TRUNC('week', d.fiscal_period_end), EXTRACT(WEEK FROM d.fiscal_period_end)
                    ORDER BY week_start ASC
                """
                results = await conn.fetch(query, accountant_user_id, start_date, end_date)

                weeks = []
                for row in results:
                    weeks.append({
                        "week_start": row["week_start"],
                        "week_end": row["week_end"],
                        "week_number": row["week_number"],
                        "count": row["count"],
                        "total_amount": row["total_amount"],
                        "high_priority_count": row["high_priority_count"],
                    })

                return {
                    "view_type": "week",
                    "start_date": start_date,
                    "end_date": end_date,
                    "weeks": weeks,
                    "summary": {
                        "total_deadlines": sum(w["count"] for w in weeks),
                        "total_amount": sum(w["total_amount"] or 0 for w in weeks),
                    },
                }

            else:  # month view
                # Monthly aggregation
                query = """
                    SELECT
                        TO_CHAR(d.fiscal_period_end, 'YYYY-MM') AS month,
                        TO_CHAR(d.fiscal_period_end, 'Month YYYY') AS month_name,
                        COUNT(*) AS count,
                        SUM(d.calculated_tax) AS total_amount,
                        COUNT(*) FILTER (WHERE d.calculated_tax > 1000000) AS high_priority_count
                    FROM tax_declarations d
                    INNER JOIN companies c ON d.company_id = c.id
                    INNER JOIN company_members cm ON c.id = cm.company_id
                    WHERE
                        cm.user_id = $1
                        AND cm.role IN ('company_accountant', 'company_owner', 'company_admin')
                        AND d.fiscal_period_end BETWEEN $2 AND $3
                        AND d.status NOT IN ('approved', 'rejected')
                    GROUP BY TO_CHAR(d.fiscal_period_end, 'YYYY-MM'), TO_CHAR(d.fiscal_period_end, 'Month YYYY')
                    ORDER BY month ASC
                """
                results = await conn.fetch(query, accountant_user_id, start_date, end_date)

                months = []
                for row in results:
                    months.append({
                        "month": row["month"],
                        "month_name": row["month_name"].strip(),
                        "count": row["count"],
                        "total_amount": row["total_amount"],
                        "high_priority_count": row["high_priority_count"],
                    })

                return {
                    "view_type": "month",
                    "start_date": start_date,
                    "end_date": end_date,
                    "months": months,
                    "summary": {
                        "total_deadlines": sum(m["count"] for m in months),
                        "total_amount": sum(m["total_amount"] or 0 for m in months),
                    },
                }

        except Exception as e:
            logger.error(f"Error fetching calendar view: {str(e)}")
            raise
