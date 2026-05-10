"""
TaxasGE Utilities Package

Centralized utilities for validation, helpers, logging, dates, and enums.

Usage:
    from app.utils import validate_nif, format_currency, logger
    from app.utils.date_utils import get_current_fiscal_year
    from app.utils.validators import validate_amount
"""

# ========================================================================
# VALIDATORS
# ========================================================================
from .validators import (
    # Tax ID validation
    validate_nif,
    validate_nie,

    # Amount validation
    validate_amount,
    validate_tax_amount,
    validate_percentage,

    # Fiscal period validation
    validate_fiscal_period,
    validate_fiscal_year,

    # Phone validation
    validate_phone_number,

    # UUID validation
    validate_uuid,

    # Enum validation
    validate_enum_value,
    get_enum_values,

    # Batch validation
    validate_all,
)

# ========================================================================
# HELPERS
# ========================================================================
from .helpers import (
    # Pagination
    PaginationParams,
    PaginatedResponse,
    paginate_list,

    # Response formatting
    success_response,
    error_response,

    # Data transformation
    to_dict_safe,
    clean_dict,
    merge_dicts,

    # String manipulation
    truncate_string,
    slugify,
    camel_to_snake,
    snake_to_camel,

    # Calculations
    calculate_percentage,
    calculate_tax,
    sum_amounts,

    # List operations
    chunk_list,
    deduplicate_list,
    group_by,

    # Formatting
    format_currency,
    format_file_size,
)

# ========================================================================
# LOGGER
# ========================================================================
from .logger import (
    # Logger setup
    setup_logger,
    logger,

    # Context logging
    log_with_context,

    # Request tracing
    RequestLogger,

    # Module logger
    get_module_logger,

    # Performance logging
    log_performance,

    # Database logging
    log_db_query,

    # Error logging
    log_exception,

    # Security logging
    log_security_event,

    # Audit logging
    log_audit,
)

# ========================================================================
# DATE UTILITIES
# ========================================================================
from .date_utils import (
    # Enums
    FiscalPeriodType,
    Quarter,
    Month,

    # Fiscal year functions
    get_current_fiscal_year,
    get_fiscal_year_range,
    is_fiscal_year_complete,
    get_fiscal_year_from_date,

    # Fiscal period functions
    get_quarter_from_month,
    get_quarter_dates,
    get_month_dates,
    get_current_period_dates,
    get_previous_period_dates,

    # Date range functions
    get_days_in_period,
    get_months_in_period,
    is_date_in_period,
    periods_overlap,

    # Deadline functions
    calculate_deadline,
    get_days_until_deadline,
    is_deadline_passed,
    get_deadline_status,

    # Working days
    is_weekend,
    get_next_working_day,
    count_working_days,

    # Date formatting
    format_date_french,
    format_date_iso,
    format_period,

    # Period generation
    generate_monthly_periods,
    generate_quarterly_periods,

    # Date parsing
    parse_date_flexible,
)

# ========================================================================
# ENUM UTILITIES
# ========================================================================
from .enum_utils import (
    # Validation
    is_valid_enum_value,
    is_valid_enum_name,

    # Conversion
    get_enum_by_value,
    get_enum_by_name,
    enum_to_value,

    # Listing
    get_enum_values as enum_get_values,
    get_enum_names,
    get_enum_dict,
    get_enum_choices,

    # Display names
    enum_to_display_name,
    get_enum_display_dict,

    # Comparison
    enum_equals,
    enum_in,

    # Filtering
    filter_enums_by_attribute,

    # Mapping
    create_enum_mapper,
    batch_convert_enum_values,

    # Serialization
    serialize_enum,
    deserialize_enum,

    # Documentation
    get_enum_docstring,
    get_enum_member_info,
    get_enum_summary,

    # Validation with messages
    validate_enum_value_verbose,
)

# ========================================================================
# EMAIL VALIDATOR (existing)
# ========================================================================
try:
    from .email_validator import validate_email, normalize_email
except ImportError:
    # email_validator might not exist yet or might have different exports
    pass


__all__ = [
    # Validators
    "validate_nif",
    "validate_nie",
    "validate_amount",
    "validate_tax_amount",
    "validate_percentage",
    "validate_fiscal_period",
    "validate_fiscal_year",
    "validate_phone_number",
    "validate_uuid",
    "validate_enum_value",
    "get_enum_values",
    "validate_all",

    # Helpers
    "PaginationParams",
    "PaginatedResponse",
    "paginate_list",
    "success_response",
    "error_response",
    "to_dict_safe",
    "clean_dict",
    "merge_dicts",
    "truncate_string",
    "slugify",
    "camel_to_snake",
    "snake_to_camel",
    "calculate_percentage",
    "calculate_tax",
    "sum_amounts",
    "chunk_list",
    "deduplicate_list",
    "group_by",
    "format_currency",
    "format_file_size",

    # Logger
    "setup_logger",
    "logger",
    "log_with_context",
    "RequestLogger",
    "get_module_logger",
    "log_performance",
    "log_db_query",
    "log_exception",
    "log_security_event",
    "log_audit",

    # Date utilities
    "FiscalPeriodType",
    "Quarter",
    "Month",
    "get_current_fiscal_year",
    "get_fiscal_year_range",
    "is_fiscal_year_complete",
    "get_fiscal_year_from_date",
    "get_quarter_from_month",
    "get_quarter_dates",
    "get_month_dates",
    "get_current_period_dates",
    "get_previous_period_dates",
    "get_days_in_period",
    "get_months_in_period",
    "is_date_in_period",
    "periods_overlap",
    "calculate_deadline",
    "get_days_until_deadline",
    "is_deadline_passed",
    "get_deadline_status",
    "is_weekend",
    "get_next_working_day",
    "count_working_days",
    "format_date_french",
    "format_date_iso",
    "format_period",
    "generate_monthly_periods",
    "generate_quarterly_periods",
    "parse_date_flexible",

    # Enum utilities
    "is_valid_enum_value",
    "is_valid_enum_name",
    "get_enum_by_value",
    "get_enum_by_name",
    "enum_to_value",
    "enum_get_values",
    "get_enum_names",
    "get_enum_dict",
    "get_enum_choices",
    "enum_to_display_name",
    "get_enum_display_dict",
    "enum_equals",
    "enum_in",
    "filter_enums_by_attribute",
    "create_enum_mapper",
    "batch_convert_enum_values",
    "serialize_enum",
    "deserialize_enum",
    "get_enum_docstring",
    "get_enum_member_info",
    "get_enum_summary",
    "validate_enum_value_verbose",
]
