"""
Accountant Deadline Models - Deadline tracking for accountants
Provides comprehensive deadline tracking across all client companies
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class DeadlineSeverity(str, Enum):
    """Severity classification for overdue items"""
    RECENT = "recent"          # 1-7 days overdue
    MODERATE = "moderate"      # 7-30 days overdue
    CRITICAL = "critical"      # 30+ days overdue


class DeadlinePriority(str, Enum):
    """Priority levels for deadlines"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class DeclarationStatus(str, Enum):
    """Declaration status for filtering"""
    DRAFT = "draft"
    PENDING_SUBMISSION = "pending_submission"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERDUE = "overdue"


class CompanyInfo(BaseModel):
    """Company information for deadline view"""
    id: str
    name: str
    tax_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class DeclarationInfo(BaseModel):
    """Declaration information for deadline view"""
    id: str
    declaration_type: str
    status: str
    fiscal_period_start: Optional[date] = None
    fiscal_period_end: Optional[date] = None
    tax_year: Optional[int] = None
    calculated_tax: Optional[Decimal] = None
    reference_number: Optional[str] = None


class UpcomingDeadlineItem(BaseModel):
    """Single upcoming deadline item"""
    id: str
    company: CompanyInfo
    declaration: DeclarationInfo
    due_date: datetime
    days_until_due: int
    priority: DeadlinePriority
    priority_score: int = Field(..., description="Calculated priority score 0-100")
    created_at: datetime
    updated_at: datetime

    # Notification preferences
    email_notifications: bool = True
    sms_notifications: bool = False

    # Additional context
    agent_assigned: Optional[str] = None
    notes: Optional[str] = None


class UpcomingDeadlinesResponse(BaseModel):
    """Response for upcoming deadlines endpoint"""
    deadlines: List[UpcomingDeadlineItem]
    total: int
    page: int
    page_size: int
    filters_applied: Dict[str, Any]
    summary: Dict[str, Any] = Field(
        default={},
        description="Summary stats: total_urgent, total_high, avg_days_until_due"
    )


class OverdueDeadlineItem(BaseModel):
    """Single overdue deadline item"""
    id: str
    company: CompanyInfo
    declaration: DeclarationInfo
    due_date: datetime
    days_overdue: int
    severity: DeadlineSeverity
    priority_score: int = Field(..., description="Calculated priority score with overdue penalty")
    created_at: datetime
    updated_at: datetime

    # Escalation info
    escalated: bool = False
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = None

    # Additional context
    agent_assigned: Optional[str] = None
    notes: Optional[str] = None
    last_contact_date: Optional[datetime] = None


class OverdueDeadlinesResponse(BaseModel):
    """Response for overdue deadlines endpoint"""
    deadlines: List[OverdueDeadlineItem]
    grouped_by_severity: Dict[DeadlineSeverity, List[OverdueDeadlineItem]]
    total: int
    page: int
    page_size: int
    summary: Dict[str, Any] = Field(
        default={},
        description="Summary: total_recent, total_moderate, total_critical, avg_days_overdue"
    )


class CalendarDayItem(BaseModel):
    """Deadlines for a single day"""
    date: date
    count: int
    deadlines: List[Dict[str, Any]] = Field(
        default=[],
        description="Simplified deadline info: id, company_name, declaration_type, priority"
    )
    total_amount: Optional[Decimal] = Field(None, description="Sum of all tax amounts due this day")


class CalendarWeekItem(BaseModel):
    """Weekly aggregation of deadlines"""
    week_start: date
    week_end: date
    week_number: int
    count: int
    high_priority_count: int
    total_amount: Optional[Decimal] = None


class CalendarMonthItem(BaseModel):
    """Monthly aggregation of deadlines"""
    month: str  # Format: "2025-01"
    month_name: str  # Format: "January 2025"
    count: int
    high_priority_count: int
    total_amount: Optional[Decimal] = None
    weeks: List[CalendarWeekItem] = []


class CalendarViewResponse(BaseModel):
    """Response for calendar view endpoint"""
    view_type: str = Field(..., description="day, week, or month")
    start_date: date
    end_date: date

    # Different views
    days: Optional[List[CalendarDayItem]] = None
    weeks: Optional[List[CalendarWeekItem]] = None
    months: Optional[List[CalendarMonthItem]] = None

    summary: Dict[str, Any] = Field(
        default={},
        description="Summary: total_deadlines, total_amount, busiest_day"
    )


class NotificationPreferences(BaseModel):
    """Notification preferences for deadline alerts"""
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = True

    # Timing
    days_before_deadline: List[int] = Field(
        default=[7, 3, 1],
        description="Send notifications X days before deadline"
    )

    # Filters
    only_high_priority: bool = False
    only_specific_companies: Optional[List[str]] = Field(
        None,
        description="Filter to specific company IDs"
    )

    # Schedule
    daily_digest_enabled: bool = True
    daily_digest_time: str = Field(default="08:00", description="Time in HH:MM format")
    weekly_summary_enabled: bool = True
    weekly_summary_day: str = Field(default="monday", description="Day of week")


class DeadlineFilters(BaseModel):
    """Common filters for deadline queries"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    company_ids: Optional[List[str]] = None
    declaration_types: Optional[List[str]] = None
    priority: Optional[DeadlinePriority] = None
    status: Optional[DeclarationStatus] = None
    assigned_agent: Optional[str] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
