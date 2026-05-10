"""
Helper Utilities - Common functions for TaxasGE

Provides utility functions for:
- Pagination
- Response formatting
- Data transformation
- String manipulation
- Dictionary operations
"""

from typing import Any, Dict, List, Optional, TypeVar, Generic
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
import json


T = TypeVar('T')


# ========================================================================
# PAGINATION HELPERS
# ========================================================================

class PaginationParams:
    """Standard pagination parameters"""

    def __init__(self, limit: int = 50, offset: int = 0):
        self.limit = max(1, min(limit, 1000))  # Cap at 1000
        self.offset = max(0, offset)

    @property
    def page(self) -> int:
        """Calculate current page number (1-indexed)"""
        return (self.offset // self.limit) + 1

    def to_dict(self) -> Dict[str, int]:
        """Convert to dict for query building"""
        return {"limit": self.limit, "offset": self.offset}


class PaginatedResponse(Generic[T]):
    """Standard paginated response format"""

    def __init__(
        self,
        items: List[T],
        total: int,
        limit: int,
        offset: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.items = items
        self.total = total
        self.limit = limit
        self.offset = offset
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "items": self.items,
            "pagination": {
                "total": self.total,
                "limit": self.limit,
                "offset": self.offset,
                "page": (self.offset // self.limit) + 1,
                "pages": (self.total + self.limit - 1) // self.limit,
                "has_next": self.offset + self.limit < self.total,
                "has_previous": self.offset > 0,
            },
            "metadata": self.metadata,
        }


def paginate_list(
    items: List[T],
    limit: int = 50,
    offset: int = 0
) -> tuple[List[T], int]:
    """
    Paginate a list in memory

    Args:
        items: List to paginate
        limit: Number of items per page
        offset: Number of items to skip

    Returns:
        Tuple of (paginated_items, total_count)
    """
    total = len(items)
    paginated = items[offset:offset + limit]
    return paginated, total


# ========================================================================
# RESPONSE FORMATTING
# ========================================================================

def success_response(
    data: Any,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format success response

    Args:
        data: Response data
        message: Optional success message
        metadata: Optional metadata

    Returns:
        Formatted response dict
    """
    response = {
        "success": True,
        "data": data,
    }

    if message:
        response["message"] = message

    if metadata:
        response["metadata"] = metadata

    return response


def error_response(
    message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format error response

    Args:
        message: Error message
        error_code: Optional error code
        details: Optional error details

    Returns:
        Formatted error response dict
    """
    response = {
        "success": False,
        "error": message,
    }

    if error_code:
        response["error_code"] = error_code

    if details:
        response["details"] = details

    return response


# ========================================================================
# DATA TRANSFORMATION
# ========================================================================

def to_dict_safe(obj: Any) -> Any:
    """
    Safely convert object to dict, handling special types

    Args:
        obj: Object to convert

    Returns:
        Dict or serializable value
    """
    if obj is None:
        return None

    # Handle dict
    if isinstance(obj, dict):
        return {k: to_dict_safe(v) for k, v in obj.items()}

    # Handle list/tuple
    if isinstance(obj, (list, tuple)):
        return [to_dict_safe(item) for item in obj]

    # Handle datetime
    if isinstance(obj, datetime):
        return obj.isoformat()

    # Handle date
    if isinstance(obj, date):
        return obj.isoformat()

    # Handle Decimal
    if isinstance(obj, Decimal):
        return float(obj)

    # Handle UUID
    if isinstance(obj, UUID):
        return str(obj)

    # Handle custom objects with dict()
    if hasattr(obj, '__dict__'):
        return to_dict_safe(obj.__dict__)

    # Return as is for primitives
    return obj


def clean_dict(
    data: Dict[str, Any],
    remove_none: bool = True,
    remove_empty: bool = False
) -> Dict[str, Any]:
    """
    Clean dictionary by removing None and empty values

    Args:
        data: Dictionary to clean
        remove_none: Remove None values (default True)
        remove_empty: Remove empty strings/lists/dicts (default False)

    Returns:
        Cleaned dictionary
    """
    cleaned = {}

    for key, value in data.items():
        # Skip None values
        if remove_none and value is None:
            continue

        # Skip empty values
        if remove_empty:
            if value == "" or value == [] or value == {}:
                continue

        cleaned[key] = value

    return cleaned


def merge_dicts(
    base: Dict[str, Any],
    updates: Dict[str, Any],
    deep: bool = False
) -> Dict[str, Any]:
    """
    Merge two dictionaries

    Args:
        base: Base dictionary
        updates: Dictionary with updates
        deep: Whether to deep merge nested dicts (default False)

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in updates.items():
        if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value, deep=True)
        else:
            result[key] = value

    return result


# ========================================================================
# STRING MANIPULATION
# ========================================================================

def truncate_string(
    text: str,
    max_length: int,
    suffix: str = "..."
) -> str:
    """
    Truncate string to max length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix for truncated text (default "...")

    Returns:
        Truncated string
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def slugify(text: str) -> str:
    """
    Convert text to slug (lowercase, hyphens, alphanumeric)

    Args:
        text: Text to slugify

    Returns:
        Slugified string
    """
    import re

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)

    # Remove non-alphanumeric characters (except hyphens)
    text = re.sub(r'[^a-z0-9\-]', '', text)

    # Remove duplicate hyphens
    text = re.sub(r'-+', '-', text)

    # Remove leading/trailing hyphens
    text = text.strip('-')

    return text


def camel_to_snake(text: str) -> str:
    """
    Convert camelCase to snake_case

    Args:
        text: camelCase string

    Returns:
        snake_case string
    """
    import re

    # Insert underscore before uppercase letters
    text = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    text = re.sub('([a-z0-9])([A-Z])', r'\1_\2', text)

    return text.lower()


def snake_to_camel(text: str, capitalize_first: bool = False) -> str:
    """
    Convert snake_case to camelCase

    Args:
        text: snake_case string
        capitalize_first: Capitalize first letter (PascalCase)

    Returns:
        camelCase or PascalCase string
    """
    components = text.split('_')

    if capitalize_first:
        return ''.join(x.title() for x in components)
    else:
        return components[0] + ''.join(x.title() for x in components[1:])


# ========================================================================
# CALCULATION HELPERS
# ========================================================================

def calculate_percentage(
    part: Decimal,
    total: Decimal,
    precision: int = 2
) -> Decimal:
    """
    Calculate percentage with safe division

    Args:
        part: Part value
        total: Total value
        precision: Decimal places (default 2)

    Returns:
        Percentage value (0-100)
    """
    if total == 0:
        return Decimal("0")

    percentage = (part / total) * 100
    return round(percentage, precision)


def calculate_tax(
    base_amount: Decimal,
    tax_rate: Decimal,
    precision: int = 2
) -> Decimal:
    """
    Calculate tax amount from base and rate

    Args:
        base_amount: Base amount
        tax_rate: Tax rate (as percentage, e.g., 15.5 for 15.5%)
        precision: Decimal places (default 2)

    Returns:
        Tax amount
    """
    tax_amount = (base_amount * tax_rate) / 100
    return round(tax_amount, precision)


def sum_amounts(amounts: List[Decimal]) -> Decimal:
    """
    Sum list of decimal amounts safely

    Args:
        amounts: List of amounts

    Returns:
        Sum of amounts
    """
    return sum(amounts, Decimal("0"))


# ========================================================================
# LIST OPERATIONS
# ========================================================================

def chunk_list(items: List[T], chunk_size: int) -> List[List[T]]:
    """
    Split list into chunks

    Args:
        items: List to chunk
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def deduplicate_list(items: List[T], key_func=None) -> List[T]:
    """
    Remove duplicates from list while preserving order

    Args:
        items: List with potential duplicates
        key_func: Optional function to extract comparison key

    Returns:
        List without duplicates
    """
    if key_func is None:
        # Simple case: hashable items
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    else:
        # Complex case: use key function
        seen = set()
        result = []
        for item in items:
            key = key_func(item)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result


def group_by(items: List[Dict[str, Any]], key: str) -> Dict[Any, List[Dict[str, Any]]]:
    """
    Group list of dicts by key

    Args:
        items: List of dictionaries
        key: Key to group by

    Returns:
        Dictionary with grouped items
    """
    grouped = {}

    for item in items:
        group_key = item.get(key)
        if group_key not in grouped:
            grouped[group_key] = []
        grouped[group_key].append(item)

    return grouped


# ========================================================================
# FORMATTING HELPERS
# ========================================================================

def format_currency(
    amount: Decimal,
    currency: str = "XAF",
    locale: str = "fr_FR"
) -> str:
    """
    Format amount as currency

    Args:
        amount: Amount to format
        currency: Currency code (default XAF - Central African CFA franc)
        locale: Locale for formatting (default fr_FR)

    Returns:
        Formatted currency string
    """
    # Simple formatting (can be enhanced with babel if needed)
    if currency == "XAF":
        return f"{amount:,.0f} FCFA"
    elif currency == "EUR":
        return f"{amount:,.2f} EUR"
    elif currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"
