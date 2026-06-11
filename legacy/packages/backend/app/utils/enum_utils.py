"""
Enum Utilities - Helper functions for Python Enums

Provides utilities for:
- Enum validation and conversion
- Enum to list/dict transformation
- Safe enum access
- Display name mapping
"""

from enum import Enum
from typing import Type, List, Dict, Optional, Any, TypeVar


E = TypeVar('E', bound=Enum)


# ========================================================================
# ENUM VALIDATION
# ========================================================================

def is_valid_enum_value(enum_class: Type[E], value: Any) -> bool:
    """
    Check if value is a valid enum value

    Args:
        enum_class: Enum class
        value: Value to check

    Returns:
        True if value is valid for enum
    """
    try:
        enum_class(value)
        return True
    except (ValueError, KeyError):
        return False


def is_valid_enum_name(enum_class: Type[E], name: str) -> bool:
    """
    Check if name is a valid enum member name

    Args:
        enum_class: Enum class
        name: Name to check

    Returns:
        True if name is valid enum member
    """
    return name.upper() in enum_class.__members__


# ========================================================================
# ENUM CONVERSION
# ========================================================================

def get_enum_by_value(enum_class: Type[E], value: Any, default: Optional[E] = None) -> Optional[E]:
    """
    Get enum member by value, with optional default

    Args:
        enum_class: Enum class
        value: Value to look up
        default: Default value if not found

    Returns:
        Enum member or default
    """
    try:
        return enum_class(value)
    except (ValueError, KeyError):
        return default


def get_enum_by_name(enum_class: Type[E], name: str, default: Optional[E] = None) -> Optional[E]:
    """
    Get enum member by name, with optional default

    Args:
        enum_class: Enum class
        name: Name to look up (case-insensitive)
        default: Default value if not found

    Returns:
        Enum member or default
    """
    try:
        return enum_class[name.upper()]
    except KeyError:
        return default


def enum_to_value(enum_member: Optional[E]) -> Optional[Any]:
    """
    Convert enum member to its value (None-safe)

    Args:
        enum_member: Enum member or None

    Returns:
        Enum value or None
    """
    return enum_member.value if enum_member is not None else None


# ========================================================================
# ENUM LISTING
# ========================================================================

def get_enum_values(enum_class: Type[E]) -> List[Any]:
    """
    Get list of all enum values

    Args:
        enum_class: Enum class

    Returns:
        List of enum values
    """
    return [member.value for member in enum_class]


def get_enum_names(enum_class: Type[E]) -> List[str]:
    """
    Get list of all enum member names

    Args:
        enum_class: Enum class

    Returns:
        List of enum names
    """
    return [member.name for member in enum_class]


def get_enum_dict(enum_class: Type[E]) -> Dict[str, Any]:
    """
    Convert enum to dictionary {name: value}

    Args:
        enum_class: Enum class

    Returns:
        Dictionary mapping names to values
    """
    return {member.name: member.value for member in enum_class}


def get_enum_choices(enum_class: Type[E]) -> List[tuple[Any, str]]:
    """
    Get enum choices for form/API (value, name) tuples

    Args:
        enum_class: Enum class

    Returns:
        List of (value, name) tuples
    """
    return [(member.value, member.name) for member in enum_class]


# ========================================================================
# ENUM DISPLAY NAMES
# ========================================================================

def enum_to_display_name(
    enum_member: E,
    display_names: Optional[Dict[E, str]] = None
) -> str:
    """
    Convert enum to human-readable display name

    Args:
        enum_member: Enum member
        display_names: Optional custom display name mapping

    Returns:
        Display name (defaults to name with underscores replaced by spaces)
    """
    if display_names and enum_member in display_names:
        return display_names[enum_member]

    # Default: replace underscores with spaces and title case
    return enum_member.name.replace('_', ' ').title()


def get_enum_display_dict(
    enum_class: Type[E],
    display_names: Optional[Dict[E, str]] = None
) -> Dict[Any, str]:
    """
    Get dictionary mapping enum values to display names

    Args:
        enum_class: Enum class
        display_names: Optional custom display name mapping

    Returns:
        Dictionary {value: display_name}
    """
    return {
        member.value: enum_to_display_name(member, display_names)
        for member in enum_class
    }


# ========================================================================
# ENUM COMPARISON
# ========================================================================

def enum_equals(enum_member: Optional[E], value: Any) -> bool:
    """
    Compare enum member with a value (None-safe)

    Args:
        enum_member: Enum member or None
        value: Value to compare

    Returns:
        True if enum value equals comparison value
    """
    if enum_member is None:
        return value is None

    return enum_member.value == value


def enum_in(enum_member: Optional[E], values: List[Any]) -> bool:
    """
    Check if enum value is in list of values (None-safe)

    Args:
        enum_member: Enum member or None
        values: List of values to check

    Returns:
        True if enum value is in list
    """
    if enum_member is None:
        return None in values

    return enum_member.value in values


# ========================================================================
# ENUM FILTERING
# ========================================================================

def filter_enums_by_attribute(
    enum_class: Type[E],
    attribute_name: str,
    attribute_value: Any
) -> List[E]:
    """
    Filter enum members by custom attribute

    Args:
        enum_class: Enum class
        attribute_name: Attribute name to filter by
        attribute_value: Value to match

    Returns:
        List of matching enum members
    """
    return [
        member for member in enum_class
        if hasattr(member, attribute_name) and getattr(member, attribute_name) == attribute_value
    ]


# ========================================================================
# ENUM MAPPING HELPERS
# ========================================================================

def create_enum_mapper(
    source_enum: Type[E],
    target_enum: Type[E],
    mapping: Dict[E, E]
) -> callable:
    """
    Create a function to map between two enums

    Args:
        source_enum: Source enum class
        target_enum: Target enum class
        mapping: Dictionary mapping source to target members

    Returns:
        Mapper function
    """
    def mapper(source_value: Optional[E]) -> Optional[E]:
        if source_value is None:
            return None

        return mapping.get(source_value, None)

    return mapper


def batch_convert_enum_values(
    enum_class: Type[E],
    values: List[Any],
    skip_invalid: bool = True
) -> List[E]:
    """
    Convert list of values to enum members

    Args:
        enum_class: Enum class
        values: List of values to convert
        skip_invalid: If True, skip invalid values; if False, raise error

    Returns:
        List of enum members
    """
    result = []

    for value in values:
        try:
            result.append(enum_class(value))
        except (ValueError, KeyError):
            if not skip_invalid:
                raise

    return result


# ========================================================================
# ENUM SERIALIZATION
# ========================================================================

def serialize_enum(enum_member: Optional[E]) -> Optional[Any]:
    """
    Serialize enum for JSON (convert to value)

    Args:
        enum_member: Enum member or None

    Returns:
        Enum value (JSON-serializable) or None
    """
    return enum_member.value if enum_member is not None else None


def deserialize_enum(
    enum_class: Type[E],
    value: Any,
    raise_on_invalid: bool = False
) -> Optional[E]:
    """
    Deserialize value to enum member

    Args:
        enum_class: Enum class
        value: Value to deserialize
        raise_on_invalid: If True, raise error on invalid value

    Returns:
        Enum member or None
    """
    if value is None:
        return None

    try:
        return enum_class(value)
    except (ValueError, KeyError):
        if raise_on_invalid:
            raise ValueError(f"Invalid {enum_class.__name__} value: {value}")
        return None


# ========================================================================
# ENUM DOCUMENTATION
# ========================================================================

def get_enum_docstring(enum_class: Type[E]) -> Optional[str]:
    """
    Get enum class docstring

    Args:
        enum_class: Enum class

    Returns:
        Docstring or None
    """
    return enum_class.__doc__


def get_enum_member_info(enum_member: E) -> Dict[str, Any]:
    """
    Get comprehensive info about enum member

    Args:
        enum_member: Enum member

    Returns:
        Dictionary with member information
    """
    return {
        "name": enum_member.name,
        "value": enum_member.value,
        "type": type(enum_member.value).__name__,
        "class": enum_member.__class__.__name__,
    }


def get_enum_summary(enum_class: Type[E]) -> Dict[str, Any]:
    """
    Get summary information about an enum

    Args:
        enum_class: Enum class

    Returns:
        Dictionary with enum summary
    """
    members = list(enum_class)

    return {
        "name": enum_class.__name__,
        "docstring": get_enum_docstring(enum_class),
        "member_count": len(members),
        "members": [
            {
                "name": member.name,
                "value": member.value,
            }
            for member in members
        ],
        "values": get_enum_values(enum_class),
        "names": get_enum_names(enum_class),
    }


# ========================================================================
# ENUM VALIDATION WITH ERROR MESSAGES
# ========================================================================

def validate_enum_value_verbose(
    enum_class: Type[E],
    value: Any,
    field_name: str = "Value"
) -> tuple[bool, Optional[str], Optional[E]]:
    """
    Validate enum value with detailed error message

    Args:
        enum_class: Enum class
        value: Value to validate
        field_name: Name of field for error message

    Returns:
        Tuple of (is_valid, error_message, enum_member)
    """
    if value is None:
        return False, f"{field_name} is required", None

    try:
        enum_member = enum_class(value)
        return True, None, enum_member
    except (ValueError, KeyError):
        valid_values = get_enum_values(enum_class)
        return (
            False,
            f"{field_name} must be one of: {', '.join(str(v) for v in valid_values)}",
            None
        )
