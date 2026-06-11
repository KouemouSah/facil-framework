"""
Logger Configuration - Standardized loguru setup for TaxasGE

Provides centralized logging configuration with:
- Structured logging with context
- Log rotation and retention
- Different log levels for different environments
- Request tracing support
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
import os


# ========================================================================
# LOG CONFIGURATION
# ========================================================================

# Environment
ENV = os.getenv("ENVIRONMENT", "development")

# Log directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Log format with colors for development
DEV_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

# Log format for production (JSON-compatible)
PROD_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} | "
    "{message}"
)

# Log levels by environment
LOG_LEVELS = {
    "development": "DEBUG",
    "staging": "INFO",
    "production": "INFO",
}


# ========================================================================
# LOGGER SETUP
# ========================================================================

def setup_logger(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    rotation: str = "100 MB",
    retention: str = "30 days",
    include_context: bool = True
) -> None:
    """
    Setup loguru logger with standard configuration

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   If None, uses environment default
        log_file: Optional log file name (defaults to app.log)
        rotation: Log rotation policy (default "100 MB")
        retention: Log retention policy (default "30 days")
        include_context: Whether to include request context in logs
    """
    # Remove default handler
    logger.remove()

    # Determine log level
    if log_level is None:
        log_level = LOG_LEVELS.get(ENV, "INFO")

    # Choose format based on environment
    log_format = DEV_FORMAT if ENV == "development" else PROD_FORMAT

    # Console handler (stderr)
    logger.add(
        sys.stderr,
        format=log_format,
        level=log_level,
        colorize=(ENV == "development"),
        backtrace=True,
        diagnose=(ENV == "development"),
    )

    # File handler for all logs
    if log_file is None:
        log_file = "app.log"

    logger.add(
        LOG_DIR / log_file,
        format=PROD_FORMAT,  # Always use plain format for files
        level=log_level,
        rotation=rotation,
        retention=retention,
        compression="zip",  # Compress rotated logs
        backtrace=True,
        diagnose=True,
    )

    # Separate error log file
    logger.add(
        LOG_DIR / "error.log",
        format=PROD_FORMAT,
        level="ERROR",
        rotation=rotation,
        retention=retention,
        compression="zip",
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"Logger initialized - Environment: {ENV}, Level: {log_level}")


# ========================================================================
# CONTEXT LOGGING
# ========================================================================

def log_with_context(
    level: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    Log message with additional context

    Args:
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        context: Additional context dictionary
        **kwargs: Additional key-value pairs to log
    """
    # Merge context and kwargs
    extra = {}
    if context:
        extra.update(context)
    if kwargs:
        extra.update(kwargs)

    # Format message with context
    if extra:
        context_str = " | ".join(f"{k}={v}" for k, v in extra.items())
        full_message = f"{message} | {context_str}"
    else:
        full_message = message

    # Log at appropriate level
    log_func = getattr(logger, level.lower())
    log_func(full_message)


# ========================================================================
# REQUEST TRACING
# ========================================================================

class RequestLogger:
    """Context manager for request logging with tracing"""

    def __init__(
        self,
        request_id: str,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.endpoint = endpoint
        self.method = method
        self.context = logger.contextualize(
            request_id=request_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method,
        )

    def __enter__(self):
        """Start request logging"""
        logger.info(
            f"Request started | "
            f"request_id={self.request_id} | "
            f"method={self.method} | "
            f"endpoint={self.endpoint} | "
            f"user_id={self.user_id}"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End request logging"""
        if exc_type is None:
            logger.info(
                f"Request completed | "
                f"request_id={self.request_id}"
            )
        else:
            logger.error(
                f"Request failed | "
                f"request_id={self.request_id} | "
                f"error={exc_type.__name__}: {exc_val}"
            )
        return False


# ========================================================================
# MODULE-SPECIFIC LOGGERS
# ========================================================================

def get_module_logger(module_name: str):
    """
    Get logger with module name context

    Args:
        module_name: Name of the module

    Returns:
        Logger with bound module name
    """
    return logger.bind(module=module_name)


# ========================================================================
# PERFORMANCE LOGGING
# ========================================================================

def log_performance(
    operation: str,
    duration_ms: float,
    threshold_ms: float = 1000.0,
    **context
) -> None:
    """
    Log performance metrics

    Args:
        operation: Operation name
        duration_ms: Duration in milliseconds
        threshold_ms: Warning threshold (default 1000ms)
        **context: Additional context
    """
    context_str = " | ".join(f"{k}={v}" for k, v in context.items()) if context else ""
    message = f"Performance | operation={operation} | duration={duration_ms:.2f}ms"

    if context_str:
        message += f" | {context_str}"

    if duration_ms > threshold_ms:
        logger.warning(f"{message} | SLOW_OPERATION")
    else:
        logger.debug(message)


# ========================================================================
# DATABASE LOGGING
# ========================================================================

def log_db_query(
    query: str,
    params: Optional[tuple] = None,
    duration_ms: Optional[float] = None,
    rows_affected: Optional[int] = None,
) -> None:
    """
    Log database query

    Args:
        query: SQL query
        params: Query parameters
        duration_ms: Query duration in milliseconds
        rows_affected: Number of rows affected
    """
    # Truncate long queries
    max_query_length = 200
    truncated_query = query[:max_query_length] + "..." if len(query) > max_query_length else query

    message = f"DB Query | query={truncated_query}"

    if params:
        message += f" | params={params}"

    if duration_ms is not None:
        message += f" | duration={duration_ms:.2f}ms"

    if rows_affected is not None:
        message += f" | rows={rows_affected}"

    # Warn on slow queries (>1 second)
    if duration_ms and duration_ms > 1000:
        logger.warning(f"{message} | SLOW_QUERY")
    else:
        logger.debug(message)


# ========================================================================
# ERROR LOGGING
# ========================================================================

def log_exception(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """
    Log exception with full context

    Args:
        error: Exception to log
        context: Additional context
        user_id: Optional user ID
        request_id: Optional request ID
    """
    extra_info = []

    if user_id:
        extra_info.append(f"user_id={user_id}")

    if request_id:
        extra_info.append(f"request_id={request_id}")

    if context:
        for key, value in context.items():
            extra_info.append(f"{key}={value}")

    extra_str = " | ".join(extra_info) if extra_info else ""
    message = f"Exception: {type(error).__name__}: {str(error)}"

    if extra_str:
        message += f" | {extra_str}"

    logger.exception(message)


# ========================================================================
# SECURITY LOGGING
# ========================================================================

def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None,
    severity: str = "INFO",
) -> None:
    """
    Log security-related event

    Args:
        event_type: Type of security event (LOGIN, LOGOUT, PERMISSION_DENIED, etc.)
        user_id: Optional user ID
        ip_address: Optional IP address
        details: Optional additional details
        severity: Severity level (INFO, WARNING, ERROR, CRITICAL)
    """
    message = f"SECURITY | event={event_type}"

    if user_id:
        message += f" | user_id={user_id}"

    if ip_address:
        message += f" | ip={ip_address}"

    if details:
        message += f" | details={details}"

    log_func = getattr(logger, severity.lower())
    log_func(message)


# ========================================================================
# AUDIT LOGGING
# ========================================================================

def log_audit(
    action: str,
    user_id: str,
    resource_type: str,
    resource_id: str,
    changes: Optional[Dict[str, Any]] = None,
    result: str = "SUCCESS",
) -> None:
    """
    Log audit trail for important actions

    Args:
        action: Action performed (CREATE, UPDATE, DELETE, etc.)
        user_id: User who performed the action
        resource_type: Type of resource (declaration, payment, etc.)
        resource_id: ID of the resource
        changes: Optional dictionary of changes made
        result: Result of the action (SUCCESS, FAILED)
    """
    message = (
        f"AUDIT | action={action} | "
        f"user_id={user_id} | "
        f"resource={resource_type}/{resource_id} | "
        f"result={result}"
    )

    if changes:
        message += f" | changes={changes}"

    logger.info(message)


# ========================================================================
# INITIALIZATION
# ========================================================================

# Auto-setup logger on import with defaults
setup_logger()
