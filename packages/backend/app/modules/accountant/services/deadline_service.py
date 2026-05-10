"""
Accountant Deadline Service - Business logic for deadline tracking

Provides high-level operations for deadline management with additional
business logic like notifications, summary calculations, and analytics.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from loguru import logger
import asyncpg

from app.modules.accountant.repositories import AccountantDeadlineRepository
from app.modules.accountant.models import (
    DeadlineFilters,
    DeadlinePriority,
    DeadlineSeverity,
)


class AccountantDeadlineService:
    """Service layer for accountant deadline operations"""

    def __init__(self):
        self.repository = AccountantDeadlineRepository()

    async def get_upcoming_deadlines_with_summary(
        self,
        conn: asyncpg.Connection,
        accountant_user_id: str,
        filters: Optional[DeadlineFilters] = None,
        sort_by: str = "due_date",
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get upcoming deadlines with summary statistics

        Args:
            conn: Database connection
            accountant_user_id: Accountant's user ID
            filters: Optional filters
            sort_by: Sort field
            sort_order: Sort direction
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Dict with deadlines, total, pagination, and summary stats
        """
        try:
            offset = (page - 1) * page_size

            deadlines, total = await self.repository.get_upcoming_deadlines(
                conn=conn,
                accountant_user_id=accountant_user_id,
                filters=filters,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=page_size,
                offset=offset,
            )

            # Calculate summary statistics
            summary = self._calculate_upcoming_summary(deadlines)

            # Build filters_applied dict
            filters_applied = {}
            if filters:
                if filters.start_date:
                    filters_applied["start_date"] = str(filters.start_date)
                if filters.end_date:
                    filters_applied["end_date"] = str(filters.end_date)
                if filters.company_ids:
                    filters_applied["company_ids"] = filters.company_ids
                if filters.declaration_types:
                    filters_applied["declaration_types"] = filters.declaration_types
                if filters.priority:
                    filters_applied["priority"] = filters.priority.value
                if filters.status:
                    filters_applied["status"] = filters.status.value

            return {
                "deadlines": deadlines,
                "total": total,
                "page": page,
                "page_size": page_size,
                "filters_applied": filters_applied,
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error in get_upcoming_deadlines_with_summary: {str(e)}")
            raise

    def _calculate_upcoming_summary(self, deadlines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics for upcoming deadlines"""
        if not deadlines:
            return {
                "total_urgent": 0,
                "total_high": 0,
                "total_medium": 0,
                "total_low": 0,
                "avg_days_until_due": 0,
                "total_tax_amount": 0,
                "within_7_days": 0,
                "within_30_days": 0,
            }

        total_urgent = sum(1 for d in deadlines if d["priority"] == DeadlinePriority.URGENT.value)
        total_high = sum(1 for d in deadlines if d["priority"] == DeadlinePriority.HIGH.value)
        total_medium = sum(1 for d in deadlines if d["priority"] == DeadlinePriority.MEDIUM.value)
        total_low = sum(1 for d in deadlines if d["priority"] == DeadlinePriority.LOW.value)

        avg_days = sum(d["days_until_due"] for d in deadlines) / len(deadlines)

        total_tax = sum(
            float(d["declaration"]["calculated_tax"]) if d["declaration"]["calculated_tax"] else 0
            for d in deadlines
        )

        within_7 = sum(1 for d in deadlines if d["days_until_due"] <= 7)
        within_30 = sum(1 for d in deadlines if d["days_until_due"] <= 30)

        return {
            "total_urgent": total_urgent,
            "total_high": total_high,
            "total_medium": total_medium,
            "total_low": total_low,
            "avg_days_until_due": round(avg_days, 1),
            "total_tax_amount": round(total_tax, 2),
            "within_7_days": within_7,
            "within_30_days": within_30,
        }

    async def get_overdue_deadlines_with_summary(
        self,
        conn: asyncpg.Connection,
        accountant_user_id: str,
        filters: Optional[DeadlineFilters] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get overdue deadlines grouped by severity with summary

        Args:
            conn: Database connection
            accountant_user_id: Accountant's user ID
            filters: Optional filters
            page: Page number
            page_size: Items per page

        Returns:
            Dict with deadlines, grouped data, and summary
        """
        try:
            offset = (page - 1) * page_size

            deadlines, grouped, total = await self.repository.get_overdue_deadlines(
                conn=conn,
                accountant_user_id=accountant_user_id,
                filters=filters,
                group_by_severity=True,
                limit=page_size,
                offset=offset,
            )

            # Calculate summary
            summary = self._calculate_overdue_summary(deadlines, grouped)

            return {
                "deadlines": deadlines,
                "grouped_by_severity": grouped,
                "total": total,
                "page": page,
                "page_size": page_size,
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error in get_overdue_deadlines_with_summary: {str(e)}")
            raise

    def _calculate_overdue_summary(
        self,
        deadlines: List[Dict[str, Any]],
        grouped: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Calculate summary statistics for overdue deadlines"""
        if not deadlines:
            return {
                "total_recent": 0,
                "total_moderate": 0,
                "total_critical": 0,
                "avg_days_overdue": 0,
                "total_tax_amount": 0,
                "escalated_count": 0,
            }

        total_recent = len(grouped.get(DeadlineSeverity.RECENT.value, []))
        total_moderate = len(grouped.get(DeadlineSeverity.MODERATE.value, []))
        total_critical = len(grouped.get(DeadlineSeverity.CRITICAL.value, []))

        avg_days = sum(d["days_overdue"] for d in deadlines) / len(deadlines)

        total_tax = sum(
            float(d["declaration"]["calculated_tax"]) if d["declaration"]["calculated_tax"] else 0
            for d in deadlines
        )

        escalated_count = sum(1 for d in deadlines if d.get("escalated", False))

        return {
            "total_recent": total_recent,
            "total_moderate": total_moderate,
            "total_critical": total_critical,
            "avg_days_overdue": round(avg_days, 1),
            "total_tax_amount": round(total_tax, 2),
            "escalated_count": escalated_count,
            "percentage_critical": round((total_critical / len(deadlines) * 100), 1) if deadlines else 0,
        }

    async def get_calendar_view_data(
        self,
        conn: asyncpg.Connection,
        accountant_user_id: str,
        start_date: date,
        end_date: date,
        view_type: str = "month",
    ) -> Dict[str, Any]:
        """
        Get calendar view data with aggregations

        Args:
            conn: Database connection
            accountant_user_id: Accountant's user ID
            start_date: Start of date range
            end_date: End of date range
            view_type: View type (day, week, month)

        Returns:
            Calendar data with aggregations
        """
        try:
            # Validate view_type
            if view_type not in ["day", "week", "month"]:
                view_type = "month"

            # Validate date range
            if start_date > end_date:
                raise ValueError("start_date must be before end_date")

            # Limit date range to prevent excessive queries
            max_days = 365
            if (end_date - start_date).days > max_days:
                logger.warning(f"Date range exceeds {max_days} days, limiting to {max_days} days")
                end_date = start_date + timedelta(days=max_days)

            calendar_data = await self.repository.get_calendar_view(
                conn=conn,
                accountant_user_id=accountant_user_id,
                start_date=start_date,
                end_date=end_date,
                view_type=view_type,
            )

            logger.info(
                f"Retrieved calendar view ({view_type}) for accountant {accountant_user_id} "
                f"from {start_date} to {end_date}"
            )

            return calendar_data

        except Exception as e:
            logger.error(f"Error in get_calendar_view_data: {str(e)}")
            raise

    async def get_deadline_analytics(
        self,
        conn: asyncpg.Connection,
        accountant_user_id: str,
    ) -> Dict[str, Any]:
        """
        Get comprehensive deadline analytics for dashboard

        Returns:
            Dict with various analytics metrics
        """
        try:
            # Get upcoming deadlines (next 30 days)
            today = date.today()
            filters_30 = DeadlineFilters(
                start_date=today,
                end_date=today + timedelta(days=30),
            )

            upcoming_30, _ = await self.repository.get_upcoming_deadlines(
                conn=conn,
                accountant_user_id=accountant_user_id,
                filters=filters_30,
                limit=1000,
                offset=0,
            )

            # Get overdue deadlines
            overdue, overdue_grouped, _ = await self.repository.get_overdue_deadlines(
                conn=conn,
                accountant_user_id=accountant_user_id,
                filters=None,
                group_by_severity=True,
                limit=1000,
                offset=0,
            )

            # Calculate analytics
            analytics = {
                "upcoming_next_30_days": len(upcoming_30),
                "upcoming_urgent": sum(1 for d in upcoming_30 if d["priority"] == DeadlinePriority.URGENT.value),
                "upcoming_high": sum(1 for d in upcoming_30 if d["priority"] == DeadlinePriority.HIGH.value),
                "total_overdue": len(overdue),
                "overdue_recent": len(overdue_grouped.get(DeadlineSeverity.RECENT.value, [])),
                "overdue_moderate": len(overdue_grouped.get(DeadlineSeverity.MODERATE.value, [])),
                "overdue_critical": len(overdue_grouped.get(DeadlineSeverity.CRITICAL.value, [])),
                "total_tax_upcoming": sum(
                    float(d["declaration"]["calculated_tax"]) if d["declaration"]["calculated_tax"] else 0
                    for d in upcoming_30
                ),
                "total_tax_overdue": sum(
                    float(d["declaration"]["calculated_tax"]) if d["declaration"]["calculated_tax"] else 0
                    for d in overdue
                ),
                "health_score": self._calculate_health_score(upcoming_30, overdue),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"Generated deadline analytics for accountant {accountant_user_id}")
            return analytics

        except Exception as e:
            logger.error(f"Error in get_deadline_analytics: {str(e)}")
            raise

    def _calculate_health_score(
        self,
        upcoming: List[Dict[str, Any]],
        overdue: List[Dict[str, Any]],
    ) -> int:
        """
        Calculate overall health score (0-100)

        Scoring logic:
        - Start at 100
        - -2 points per overdue item
        - -1 point per urgent upcoming item
        - Minimum score: 0
        """
        score = 100

        # Penalty for overdue
        score -= len(overdue) * 2

        # Penalty for urgent upcoming
        urgent_count = sum(1 for d in upcoming if d["priority"] == DeadlinePriority.URGENT.value)
        score -= urgent_count * 1

        return max(score, 0)


# Singleton service instance
_deadline_service: Optional[AccountantDeadlineService] = None


def get_deadline_service() -> AccountantDeadlineService:
    """Get or create deadline service singleton"""
    global _deadline_service
    if _deadline_service is None:
        _deadline_service = AccountantDeadlineService()
    return _deadline_service
