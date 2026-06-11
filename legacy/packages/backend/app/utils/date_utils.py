"""
Date and Fiscal Period Utilities - Date manipulation for TaxasGE

Provides utilities for:
- Fiscal year calculations
- Fiscal period management
- Date range operations
- Period comparisons
"""

from datetime import date, datetime, timedelta
from typing import Tuple, Optional, List
from enum import Enum


# ========================================================================
# FISCAL PERIOD TYPES
# ========================================================================

class FiscalPeriodType(str, Enum):
    """Types of fiscal periods"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class Quarter(int, Enum):
    """Quarters of the year"""
    Q1 = 1
    Q2 = 2
    Q3 = 3
    Q4 = 4


class Month(int, Enum):
    """Months of the year"""
    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12


# ========================================================================
# FISCAL YEAR FUNCTIONS
# ========================================================================

def get_current_fiscal_year() -> int:
    """
    Get current fiscal year

    Returns:
        Current fiscal year (YYYY)
    """
    return datetime.now().year


def get_fiscal_year_range(fiscal_year: int) -> Tuple[date, date]:
    """
    Get start and end dates for a fiscal year

    For Equatorial Guinea: January 1 to December 31

    Args:
        fiscal_year: Fiscal year (YYYY)

    Returns:
        Tuple of (start_date, end_date)
    """
    start_date = date(fiscal_year, 1, 1)
    end_date = date(fiscal_year, 12, 31)
    return start_date, end_date


def is_fiscal_year_complete(fiscal_year: int) -> bool:
    """
    Check if fiscal year is complete (past)

    Args:
        fiscal_year: Fiscal year to check

    Returns:
        True if fiscal year is complete
    """
    current_year = get_current_fiscal_year()
    return fiscal_year < current_year


def get_fiscal_year_from_date(date_value: date) -> int:
    """
    Get fiscal year from a date

    Args:
        date_value: Date to extract fiscal year from

    Returns:
        Fiscal year (YYYY)
    """
    return date_value.year


# ========================================================================
# FISCAL PERIOD FUNCTIONS
# ========================================================================

def get_quarter_from_month(month: int) -> Quarter:
    """
    Get quarter from month number

    Args:
        month: Month number (1-12)

    Returns:
        Quarter enum value
    """
    if month in [1, 2, 3]:
        return Quarter.Q1
    elif month in [4, 5, 6]:
        return Quarter.Q2
    elif month in [7, 8, 9]:
        return Quarter.Q3
    else:
        return Quarter.Q4


def get_quarter_dates(fiscal_year: int, quarter: Quarter) -> Tuple[date, date]:
    """
    Get start and end dates for a quarter

    Args:
        fiscal_year: Fiscal year
        quarter: Quarter enum value

    Returns:
        Tuple of (start_date, end_date)
    """
    quarter_months = {
        Quarter.Q1: (1, 3),
        Quarter.Q2: (4, 6),
        Quarter.Q3: (7, 9),
        Quarter.Q4: (10, 12),
    }

    start_month, end_month = quarter_months[quarter]
    start_date = date(fiscal_year, start_month, 1)

    # Last day of end month
    if end_month == 12:
        end_date = date(fiscal_year, 12, 31)
    else:
        # First day of next month - 1 day
        end_date = date(fiscal_year, end_month + 1, 1) - timedelta(days=1)

    return start_date, end_date


def get_month_dates(fiscal_year: int, month: int) -> Tuple[date, date]:
    """
    Get start and end dates for a month

    Args:
        fiscal_year: Fiscal year
        month: Month number (1-12)

    Returns:
        Tuple of (start_date, end_date)
    """
    start_date = date(fiscal_year, month, 1)

    # Last day of month
    if month == 12:
        end_date = date(fiscal_year, 12, 31)
    else:
        end_date = date(fiscal_year, month + 1, 1) - timedelta(days=1)

    return start_date, end_date


def get_current_period_dates(period_type: FiscalPeriodType) -> Tuple[date, date]:
    """
    Get start and end dates for current fiscal period

    Args:
        period_type: Type of fiscal period

    Returns:
        Tuple of (start_date, end_date)
    """
    today = date.today()
    year = today.year
    month = today.month

    if period_type == FiscalPeriodType.MONTHLY:
        return get_month_dates(year, month)

    elif period_type == FiscalPeriodType.QUARTERLY:
        quarter = get_quarter_from_month(month)
        return get_quarter_dates(year, quarter)

    elif period_type == FiscalPeriodType.SEMI_ANNUAL:
        if month <= 6:
            return date(year, 1, 1), date(year, 6, 30)
        else:
            return date(year, 7, 1), date(year, 12, 31)

    else:  # ANNUAL
        return get_fiscal_year_range(year)


def get_previous_period_dates(
    period_type: FiscalPeriodType,
    reference_date: Optional[date] = None
) -> Tuple[date, date]:
    """
    Get start and end dates for previous fiscal period

    Args:
        period_type: Type of fiscal period
        reference_date: Reference date (defaults to today)

    Returns:
        Tuple of (start_date, end_date)
    """
    if reference_date is None:
        reference_date = date.today()

    year = reference_date.year
    month = reference_date.month

    if period_type == FiscalPeriodType.MONTHLY:
        # Previous month
        if month == 1:
            return get_month_dates(year - 1, 12)
        else:
            return get_month_dates(year, month - 1)

    elif period_type == FiscalPeriodType.QUARTERLY:
        quarter = get_quarter_from_month(month)
        if quarter == Quarter.Q1:
            return get_quarter_dates(year - 1, Quarter.Q4)
        else:
            return get_quarter_dates(year, Quarter(quarter.value - 1))

    elif period_type == FiscalPeriodType.SEMI_ANNUAL:
        if month <= 6:
            return date(year - 1, 7, 1), date(year - 1, 12, 31)
        else:
            return date(year, 1, 1), date(year, 6, 30)

    else:  # ANNUAL
        return get_fiscal_year_range(year - 1)


# ========================================================================
# DATE RANGE FUNCTIONS
# ========================================================================

def get_days_in_period(start_date: date, end_date: date) -> int:
    """
    Get number of days in a period

    Args:
        start_date: Period start date
        end_date: Period end date

    Returns:
        Number of days (inclusive)
    """
    return (end_date - start_date).days + 1


def get_months_in_period(start_date: date, end_date: date) -> int:
    """
    Get approximate number of months in a period

    Args:
        start_date: Period start date
        end_date: Period end date

    Returns:
        Number of months (approximate)
    """
    years_diff = end_date.year - start_date.year
    months_diff = end_date.month - start_date.month
    return years_diff * 12 + months_diff + 1


def is_date_in_period(date_value: date, start_date: date, end_date: date) -> bool:
    """
    Check if date is within a period

    Args:
        date_value: Date to check
        start_date: Period start date
        end_date: Period end date

    Returns:
        True if date is in period
    """
    return start_date <= date_value <= end_date


def periods_overlap(
    start1: date,
    end1: date,
    start2: date,
    end2: date
) -> bool:
    """
    Check if two periods overlap

    Args:
        start1: First period start date
        end1: First period end date
        start2: Second period start date
        end2: Second period end date

    Returns:
        True if periods overlap
    """
    return start1 <= end2 and start2 <= end1


# ========================================================================
# DEADLINE FUNCTIONS
# ========================================================================

def calculate_deadline(
    start_date: date,
    days_offset: int
) -> date:
    """
    Calculate deadline from start date

    Args:
        start_date: Start date
        days_offset: Number of days to add

    Returns:
        Deadline date
    """
    return start_date + timedelta(days=days_offset)


def get_days_until_deadline(deadline: date) -> int:
    """
    Get number of days until deadline

    Args:
        deadline: Deadline date

    Returns:
        Days until deadline (negative if past due)
    """
    return (deadline - date.today()).days


def is_deadline_passed(deadline: date) -> bool:
    """
    Check if deadline has passed

    Args:
        deadline: Deadline date

    Returns:
        True if deadline has passed
    """
    return date.today() > deadline


def get_deadline_status(deadline: date, warning_days: int = 7) -> str:
    """
    Get deadline status

    Args:
        deadline: Deadline date
        warning_days: Days before deadline to warn (default 7)

    Returns:
        Status string: OVERDUE, WARNING, OK
    """
    days_until = get_days_until_deadline(deadline)

    if days_until < 0:
        return "OVERDUE"
    elif days_until <= warning_days:
        return "WARNING"
    else:
        return "OK"


# ========================================================================
# WORKING DAYS FUNCTIONS (Equatorial Guinea)
# ========================================================================

def is_weekend(date_value: date) -> bool:
    """
    Check if date is a weekend

    Args:
        date_value: Date to check

    Returns:
        True if Saturday or Sunday
    """
    return date_value.weekday() in [5, 6]  # Saturday=5, Sunday=6


def get_next_working_day(date_value: date) -> date:
    """
    Get next working day (skip weekends)

    Args:
        date_value: Starting date

    Returns:
        Next working day
    """
    next_day = date_value + timedelta(days=1)

    while is_weekend(next_day):
        next_day += timedelta(days=1)

    return next_day


def count_working_days(start_date: date, end_date: date) -> int:
    """
    Count working days between two dates (excluding weekends)

    Args:
        start_date: Period start date
        end_date: Period end date

    Returns:
        Number of working days
    """
    working_days = 0
    current_date = start_date

    while current_date <= end_date:
        if not is_weekend(current_date):
            working_days += 1
        current_date += timedelta(days=1)

    return working_days


# ========================================================================
# DATE FORMATTING
# ========================================================================

def format_date_french(date_value: date) -> str:
    """
    Format date in French format (DD/MM/YYYY)

    Args:
        date_value: Date to format

    Returns:
        Formatted date string
    """
    return date_value.strftime("%d/%m/%Y")


def format_date_iso(date_value: date) -> str:
    """
    Format date in ISO format (YYYY-MM-DD)

    Args:
        date_value: Date to format

    Returns:
        Formatted date string
    """
    return date_value.isoformat()


def format_period(start_date: date, end_date: date, locale: str = "fr") -> str:
    """
    Format fiscal period as string

    Args:
        start_date: Period start date
        end_date: Period end date
        locale: Locale for formatting (default "fr")

    Returns:
        Formatted period string
    """
    if locale == "fr":
        return f"{format_date_french(start_date)} - {format_date_french(end_date)}"
    else:
        return f"{format_date_iso(start_date)} - {format_date_iso(end_date)}"


# ========================================================================
# PERIOD GENERATION
# ========================================================================

def generate_monthly_periods(fiscal_year: int) -> List[Tuple[date, date]]:
    """
    Generate all monthly periods for a fiscal year

    Args:
        fiscal_year: Fiscal year

    Returns:
        List of (start_date, end_date) tuples
    """
    return [get_month_dates(fiscal_year, month) for month in range(1, 13)]


def generate_quarterly_periods(fiscal_year: int) -> List[Tuple[date, date]]:
    """
    Generate all quarterly periods for a fiscal year

    Args:
        fiscal_year: Fiscal year

    Returns:
        List of (start_date, end_date) tuples
    """
    return [get_quarter_dates(fiscal_year, quarter) for quarter in Quarter]


# ========================================================================
# DATE PARSING
# ========================================================================

def parse_date_flexible(date_string: str) -> Optional[date]:
    """
    Parse date from various string formats

    Supports:
    - YYYY-MM-DD (ISO)
    - DD/MM/YYYY (French)
    - DD-MM-YYYY
    - YYYY/MM/DD

    Args:
        date_string: Date string to parse

    Returns:
        Parsed date or None if invalid
    """
    formats = [
        "%Y-%m-%d",  # ISO format
        "%d/%m/%Y",  # French format
        "%d-%m-%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt).date()
        except ValueError:
            continue

    return None
