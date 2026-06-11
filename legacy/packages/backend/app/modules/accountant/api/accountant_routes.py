"""
Accountant Routes - Deadline Tracking API for Accountants

Provides comprehensive deadline tracking across all client companies.
Accountants can view upcoming deadlines, overdue declarations, and calendar views.

Endpoints:
- GET /api/v1/accountant/deadlines/upcoming - Upcoming deadlines with filters
- GET /api/v1/accountant/deadlines/overdue - Overdue deadlines grouped by severity
- GET /api/v1/accountant/calendar - Calendar view with aggregations
- GET /api/v1/accountant/analytics - Dashboard analytics
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
from datetime import date, timedelta
from decimal import Decimal
from loguru import logger

from app.modules.accountant.models import (
    UpcomingDeadlinesResponse,
    OverdueDeadlinesResponse,
    CalendarViewResponse,
    DeadlineFilters,
    DeadlinePriority,
    DeclarationStatus,
)
from app.modules.accountant.services import get_deadline_service
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.database.connection import get_database

# Create router
router = APIRouter(tags=["Accountant - Deadline Tracking"])
security = HTTPBearer()

# Initialize service
deadline_service = get_deadline_service()


@router.get("/")
async def get_accountant_api_info():
    """
    Get accountant API information

    Returns API metadata and available endpoints.
    """
    return {
        "message": "TaxasGE Accountant Deadline Tracking API",
        "version": "1.0.0",
        "description": "Comprehensive deadline tracking across all client companies",
        "endpoints": {
            "upcoming": "GET /deadlines/upcoming - View upcoming deadlines with filters and sorting",
            "overdue": "GET /deadlines/overdue - View overdue declarations grouped by severity",
            "calendar": "GET /calendar - Calendar view with day/week/month aggregations",
            "analytics": "GET /analytics - Dashboard analytics and health score",
        },
        "features": [
            "Multi-client deadline tracking",
            "Priority scoring (0-100)",
            "Severity classification (recent, moderate, critical)",
            "Calendar aggregations (day, week, month)",
            "Advanced filtering and sorting",
            "Summary statistics and analytics",
        ],
        "filters_available": [
            "date_range",
            "company_id",
            "declaration_type",
            "priority",
            "status",
            "assigned_agent",
            "amount_range",
        ],
        "note": "Authentication required - Accountant role only",
    }


@router.get("/deadlines/upcoming", response_model=UpcomingDeadlinesResponse)
async def get_upcoming_deadlines(
    # Filters
    start_date: Optional[date] = Query(
        None,
        description="Filter deadlines starting from this date (default: today)",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Filter deadlines until this date (default: 90 days from now)",
    ),
    company_ids: Optional[List[str]] = Query(
        None,
        description="Filter by specific company IDs (comma-separated)",
    ),
    declaration_types: Optional[List[str]] = Query(
        None,
        description="Filter by declaration types (e.g., iva_real, income_tax)",
    ),
    priority: Optional[DeadlinePriority] = Query(
        None,
        description="Filter by priority level (urgent, high, medium, low)",
    ),
    status: Optional[DeclarationStatus] = Query(
        None,
        description="Filter by declaration status",
    ),
    min_amount: Optional[Decimal] = Query(
        None,
        ge=0,
        description="Minimum tax amount filter",
    ),
    max_amount: Optional[Decimal] = Query(
        None,
        ge=0,
        description="Maximum tax amount filter",
    ),
    # Sorting
    sort_by: str = Query(
        "due_date",
        description="Sort field: due_date, priority, company_name, amount",
    ),
    sort_order: str = Query(
        "asc",
        description="Sort direction: asc or desc",
    ),
    # Pagination
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    # Auth
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get upcoming deadlines across all client companies

    Returns a paginated list of upcoming deadlines with:
    - Company information
    - Declaration details
    - Days until due
    - Priority score (0-100)
    - Summary statistics

    **Filters:**
    - Date range (start_date, end_date)
    - Company IDs
    - Declaration types
    - Priority level
    - Status
    - Amount range

    **Sorting:**
    - By due date, priority, company name, or amount
    - Ascending or descending

    **Query Optimization:**
    - Uses CTE for efficient date calculations
    - GIN index on company_members(user_id)
    - Composite index on (status, fiscal_period_end)
    - Single query with window function for total count

    **Authentication:** Required (Accountant role)
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Set defaults for date range
        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = start_date + timedelta(days=90)

        # Build filters object
        filters = DeadlineFilters(
            start_date=start_date,
            end_date=end_date,
            company_ids=company_ids,
            declaration_types=declaration_types,
            priority=priority,
            status=status,
            min_amount=min_amount,
            max_amount=max_amount,
        )

        # Get deadlines with summary
        result = await deadline_service.get_upcoming_deadlines_with_summary(
            conn=db,
            accountant_user_id=user_id,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

        logger.info(
            f"Accountant {user_id} retrieved {len(result['deadlines'])} upcoming deadlines "
            f"(page {page}, total: {result['total']})"
        )

        return UpcomingDeadlinesResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in get_upcoming_deadlines: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve upcoming deadlines",
        )


@router.get("/deadlines/overdue", response_model=OverdueDeadlinesResponse)
async def get_overdue_deadlines(
    # Filters
    company_ids: Optional[List[str]] = Query(
        None,
        description="Filter by specific company IDs",
    ),
    declaration_types: Optional[List[str]] = Query(
        None,
        description="Filter by declaration types",
    ),
    status: Optional[DeclarationStatus] = Query(
        None,
        description="Filter by declaration status",
    ),
    min_amount: Optional[Decimal] = Query(
        None,
        ge=0,
        description="Minimum tax amount filter",
    ),
    max_amount: Optional[Decimal] = Query(
        None,
        ge=0,
        description="Maximum tax amount filter",
    ),
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    # Auth
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get overdue declarations grouped by severity

    Returns overdue deadlines with:
    - Severity classification:
      - RECENT: 1-7 days overdue
      - MODERATE: 7-30 days overdue
      - CRITICAL: 30+ days overdue
    - Days overdue
    - Priority score with overdue penalty
    - Escalation information
    - Summary statistics by severity

    **Grouping:**
    - Deadlines are grouped by severity level
    - Each group includes count and total amount

    **Priority Scoring:**
    - Overdue items get higher priority scores
    - Escalated items get +20 bonus
    - Large amounts get higher scores

    **Query Optimization:**
    - Single query with CASE WHEN for severity
    - Index on (status, fiscal_period_end) for fast filtering
    - Aggregation done in application layer

    **Authentication:** Required (Accountant role)
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Build filters
        filters = DeadlineFilters(
            company_ids=company_ids,
            declaration_types=declaration_types,
            status=status,
            min_amount=min_amount,
            max_amount=max_amount,
        )

        # Get overdue deadlines with grouping
        result = await deadline_service.get_overdue_deadlines_with_summary(
            conn=db,
            accountant_user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size,
        )

        logger.info(
            f"Accountant {user_id} retrieved {len(result['deadlines'])} overdue deadlines "
            f"(recent: {result['summary']['total_recent']}, "
            f"moderate: {result['summary']['total_moderate']}, "
            f"critical: {result['summary']['total_critical']})"
        )

        return OverdueDeadlinesResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in get_overdue_deadlines: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve overdue deadlines",
        )


@router.get("/calendar", response_model=CalendarViewResponse)
async def get_calendar_view(
    # Date range
    start_date: date = Query(
        ...,
        description="Start date for calendar view",
    ),
    end_date: date = Query(
        ...,
        description="End date for calendar view",
    ),
    view_type: str = Query(
        "month",
        description="View type: day, week, or month",
    ),
    # Auth
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get calendar view data with deadline aggregations

    Returns calendar data aggregated by:
    - **Day view:** All deadlines per day with details
    - **Week view:** Weekly aggregations with counts and amounts
    - **Month view:** Monthly aggregations with high-priority counts

    **View Types:**
    - `day`: Detailed view with all deadlines per day
    - `week`: Weekly summary with totals
    - `month`: Monthly overview with week breakdown

    **Aggregations:**
    - Count of deadlines per period
    - Total tax amount per period
    - High-priority count (amount > 1M XAF)
    - Busiest day/week identification

    **Query Optimization:**
    - Uses DATE_TRUNC for efficient grouping
    - Single query per view type
    - Aggregates in PostgreSQL (COUNT, SUM, json_agg)
    - Date range limited to 365 days max

    **Example Use Cases:**
    - Display calendar widget on dashboard
    - Weekly planning for accountants
    - Monthly reporting and forecasting

    **Authentication:** Required (Accountant role)
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Validate view_type
        if view_type not in ["day", "week", "month"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="view_type must be 'day', 'week', or 'month'",
            )

        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before end_date",
            )

        # Get calendar data
        result = await deadline_service.get_calendar_view_data(
            conn=db,
            accountant_user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            view_type=view_type,
        )

        logger.info(
            f"Accountant {user_id} retrieved calendar view ({view_type}) "
            f"from {start_date} to {end_date}"
        )

        return CalendarViewResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in get_calendar_view: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve calendar view",
        )


@router.get("/analytics")
async def get_analytics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get comprehensive deadline analytics for dashboard

    Returns analytics including:
    - Upcoming deadlines count (next 30 days)
    - Overdue deadlines by severity
    - Priority breakdowns
    - Total tax amounts
    - Health score (0-100)

    **Health Score Calculation:**
    - Starts at 100
    - -2 points per overdue item
    - -1 point per urgent upcoming item
    - Minimum: 0

    **Use Case:**
    - Dashboard overview widget
    - Email/SMS alerts
    - Performance monitoring

    **Authentication:** Required (Accountant role)
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        analytics = await deadline_service.get_deadline_analytics(
            conn=db,
            accountant_user_id=user_id,
        )

        logger.info(f"Accountant {user_id} retrieved deadline analytics (health: {analytics['health_score']})")

        return {
            "analytics": analytics,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Error in get_analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics",
        )
