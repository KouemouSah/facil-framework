"""
Validation Utilities - Reusable validators for TaxasGE

Provides validation functions for:
- Tax IDs (NIF/NIE for Equatorial Guinea)
- Amounts and financial values
- Fiscal periods and years
- Phone numbers (GQ format)
- UUIDs
- Enum values
"""

import re
from typing import Optional, List, Any
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


# ========================================================================
# TAX ID VALIDATION (NIF/NIE - Equatorial Guinea)
# ========================================================================

def validate_nif(nif: str) -> tuple[bool, Optional[str]]:
    """
    Validate Equatorial Guinea NIF (Numero de Identificacion Fiscal)

    Format: 9 digits (can have letter suffix)
    Example: 123456789A

    Args:
        nif: Tax identification number

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not nif or not isinstance(nif, str):
        return False, "NIF is required"

    # Remove whitespace
    nif = nif.strip().upper()

    # Basic format check: 8-9 digits optionally followed by a letter
    pattern = r'^[0-9]{8,9}[A-Z]?$'
    if not re.match(pattern, nif):
        return False, "NIF must be 8-9 digits optionally followed by a letter"

    return True, None


def validate_nie(nie: str) -> tuple[bool, Optional[str]]:
    """
    Validate NIE (Numero de Identificacion de Extranjero)

    Format: Similar to NIF but for foreign entities

    Args:
        nie: Foreign identification number

    Returns:
        Tuple of (is_valid, error_message)
    """
    # For now, use same validation as NIF
    # Can be extended with specific NIE rules if needed
    return validate_nif(nie)


# ========================================================================
# AMOUNT VALIDATION
# ========================================================================

def validate_amount(
    amount: Any,
    min_value: Optional[Decimal] = None,
    max_value: Optional[Decimal] = None,
    allow_zero: bool = True,
    allow_negative: bool = False,
    field_name: str = "Amount"
) -> tuple[bool, Optional[str]]:
    """
    Validate monetary amount

    Args:
        amount: Amount to validate (Decimal, int, float, or str)
        min_value: Optional minimum value
        max_value: Optional maximum value
        allow_zero: Whether zero is allowed (default True)
        allow_negative: Whether negative values are allowed (default False)
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    if amount is None:
        return False, f"{field_name} is required"

    # Convert to Decimal for precise comparison
    try:
        if isinstance(amount, str):
            amount_decimal = Decimal(amount)
        elif isinstance(amount, (int, float)):
            amount_decimal = Decimal(str(amount))
        elif isinstance(amount, Decimal):
            amount_decimal = amount
        else:
            return False, f"{field_name} must be a number"
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number"

    # Check zero
    if amount_decimal == 0 and not allow_zero:
        return False, f"{field_name} cannot be zero"

    # Check negative
    if amount_decimal < 0 and not allow_negative:
        return False, f"{field_name} cannot be negative"

    # Check min value
    if min_value is not None and amount_decimal < min_value:
        return False, f"{field_name} must be at least {min_value}"

    # Check max value
    if max_value is not None and amount_decimal > max_value:
        return False, f"{field_name} must be at most {max_value}"

    return True, None


def validate_tax_amount(amount: Any, field_name: str = "Tax amount") -> tuple[bool, Optional[str]]:
    """
    Validate tax amount (must be non-negative)

    Args:
        amount: Tax amount to validate
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    return validate_amount(
        amount,
        min_value=Decimal("0"),
        allow_zero=True,
        allow_negative=False,
        field_name=field_name
    )


# ========================================================================
# FISCAL PERIOD VALIDATION
# ========================================================================

def validate_fiscal_period(
    start_date: date,
    end_date: date,
    allow_future: bool = True
) -> tuple[bool, Optional[str]]:
    """
    Validate fiscal period dates

    Args:
        start_date: Period start date
        end_date: Period end date
        allow_future: Whether future periods are allowed

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not start_date or not end_date:
        return False, "Both start and end dates are required"

    # End date must be after start date
    if end_date <= start_date:
        return False, "End date must be after start date"

    # Period should not exceed 1 year
    days_diff = (end_date - start_date).days
    if days_diff > 366:  # Allow for leap years
        return False, "Fiscal period cannot exceed 1 year"

    # Check if future period
    if not allow_future and start_date > date.today():
        return False, "Fiscal period cannot be in the future"

    return True, None


def validate_fiscal_year(year: int, allow_future: bool = True) -> tuple[bool, Optional[str]]:
    """
    Validate fiscal year

    Args:
        year: Fiscal year (e.g., 2024)
        allow_future: Whether future years are allowed

    Returns:
        Tuple of (is_valid, error_message)
    """
    current_year = datetime.now().year

    # Minimum year: 2024 (project start)
    if year < 2024:
        return False, "Fiscal year must be 2024 or later"

    # Check future years
    if not allow_future and year > current_year:
        return False, f"Fiscal year cannot be later than {current_year}"

    # Maximum: current year + 1 (allow next year declarations)
    if year > current_year + 1:
        return False, f"Fiscal year cannot be later than {current_year + 1}"

    return True, None


# ========================================================================
# PHONE NUMBER VALIDATION
# ========================================================================

def validate_phone_number(phone: str) -> tuple[bool, Optional[str]]:
    """
    Validate Equatorial Guinea phone number

    Format: +240 XXX XXX XXX (9 digits after country code)
    Also accepts: 240XXXXXXXXX or XXXXXXXXX

    Args:
        phone: Phone number to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone or not isinstance(phone, str):
        return False, "Phone number is required"

    # Remove whitespace and common separators
    phone_clean = re.sub(r'[\s\-\(\)]', '', phone)

    # Check formats
    # Format 1: +240XXXXXXXXX (9 digits)
    # Format 2: 240XXXXXXXXX (9 digits)
    # Format 3: XXXXXXXXX (9 digits)
    patterns = [
        r'^\+240[0-9]{9}$',  # +240XXXXXXXXX
        r'^240[0-9]{9}$',    # 240XXXXXXXXX
        r'^[0-9]{9}$',       # XXXXXXXXX
    ]

    for pattern in patterns:
        if re.match(pattern, phone_clean):
            return True, None

    return False, "Phone number must be in format +240 XXX XXX XXX (9 digits)"


# ========================================================================
# UUID VALIDATION
# ========================================================================

def validate_uuid(uuid_string: str, field_name: str = "UUID") -> tuple[bool, Optional[str]]:
    """
    Validate UUID format

    Args:
        uuid_string: UUID string to validate
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not uuid_string:
        return False, f"{field_name} is required"

    try:
        UUID(str(uuid_string))
        return True, None
    except (ValueError, AttributeError):
        return False, f"{field_name} must be a valid UUID"


# ========================================================================
# ENUM VALIDATION
# ========================================================================

def validate_enum_value(
    value: Any,
    allowed_values: List[str],
    field_name: str = "Value",
    case_sensitive: bool = False
) -> tuple[bool, Optional[str]]:
    """
    Validate enum value against allowed values

    Args:
        value: Value to validate
        allowed_values: List of allowed values
        field_name: Name of field for error messages
        case_sensitive: Whether comparison is case-sensitive

    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return False, f"{field_name} is required"

    # Convert to string
    value_str = str(value)

    # Check against allowed values
    if case_sensitive:
        if value_str not in allowed_values:
            return False, f"{field_name} must be one of: {', '.join(allowed_values)}"
    else:
        value_lower = value_str.lower()
        allowed_lower = [v.lower() for v in allowed_values]
        if value_lower not in allowed_lower:
            return False, f"{field_name} must be one of: {', '.join(allowed_values)}"

    return True, None


def get_enum_values(enum_class) -> List[str]:
    """
    Get list of values from Python enum

    Args:
        enum_class: Python enum class

    Returns:
        List of enum values
    """
    return [e.value for e in enum_class]


# ========================================================================
# PERCENTAGE VALIDATION
# ========================================================================

def validate_percentage(
    value: Any,
    min_value: Decimal = Decimal("0"),
    max_value: Decimal = Decimal("100"),
    field_name: str = "Percentage"
) -> tuple[bool, Optional[str]]:
    """
    Validate percentage value (0-100)

    Args:
        value: Percentage value to validate
        min_value: Minimum allowed value (default 0)
        max_value: Maximum allowed value (default 100)
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    return validate_amount(
        value,
        min_value=min_value,
        max_value=max_value,
        allow_zero=True,
        allow_negative=False,
        field_name=field_name
    )


# ========================================================================
# BATCH VALIDATION HELPER
# ========================================================================

def validate_all(validations: List[tuple[bool, Optional[str]]]) -> tuple[bool, List[str]]:
    """
    Run multiple validations and collect all errors

    Args:
        validations: List of (is_valid, error_message) tuples

    Returns:
        Tuple of (all_valid, list_of_errors)
    """
    errors = []

    for is_valid, error_msg in validations:
        if not is_valid and error_msg:
            errors.append(error_msg)

    return len(errors) == 0, errors
