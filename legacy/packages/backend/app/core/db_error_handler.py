"""
Database error handler — maps asyncpg exceptions to structured API responses.

Plan: .claude/plans/BUNDLE_DEBUG_PHASE4_PLAN.md

Any asyncpg error that isn't caught locally by a service/repository flows
into :func:`build_db_error_response` which returns a FastAPI JSONResponse
with:

- a stable metier code the frontend can branch on
  (format compatible with ``packages/web/src/core/api/errors.ts::extractApiError``)
- trilingual messages (es/fr/en) that DO NOT leak PostgreSQL internals
  (constraint/table names, SQL fragments) — OWASP A01/A05 compliance
- a structured server-side log with SQLSTATE + constraint + table so
  ops can correlate errors in Cloud Logging / Sentry.

The handler is wired in ``app/main.py`` as a top-level exception handler
for :class:`asyncpg.exceptions.PostgresError` **and** for the non-
PostgresError-but-still-asyncpg :class:`asyncpg.InterfaceError` (which
covers lost connections).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import asyncpg
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import ERROR_CATALOG, ErrorCode
from loguru import logger

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Mapping asyncpg exceptions → (ErrorCode, HTTP status)
# ---------------------------------------------------------------------------

# Order matters: more specific subclasses first. We iterate this list and
# pick the first match via isinstance(), so ``IntegrityConstraintViolationError``
# never shadows ``UniqueViolationError`` because the latter is a subclass
# and listed first.
_DB_ERROR_MAPPING: list[Tuple[type, ErrorCode, int]] = [
    (asyncpg.UniqueViolationError, ErrorCode.DB_UNIQUE_VIOLATION, 409),
    (asyncpg.CheckViolationError, ErrorCode.DB_CHECK_VIOLATION, 422),
    (asyncpg.ForeignKeyViolationError, ErrorCode.DB_FK_VIOLATION, 422),
    (asyncpg.NotNullViolationError, ErrorCode.DB_NOT_NULL_VIOLATION, 422),
    (asyncpg.SerializationError, ErrorCode.DB_SERIALIZATION_FAILURE, 409),
    (asyncpg.DeadlockDetectedError, ErrorCode.DB_DEADLOCK, 409),
    (asyncpg.LockNotAvailableError, ErrorCode.DB_LOCK_TIMEOUT, 409),
    (asyncpg.QueryCanceledError, ErrorCode.DB_STATEMENT_TIMEOUT, 504),
]


def _classify(exc: BaseException) -> Tuple[ErrorCode, int]:
    """Return the (ErrorCode, HTTP status) for an asyncpg exception.

    Falls back to ``SERVER_ERROR`` / 500 for uncharted PostgresError
    subclasses and to ``DB_CONNECTION_ERROR`` / 503 for :class:`asyncpg.
    InterfaceError` (which does not inherit from ``PostgresError``).
    """
    if isinstance(exc, asyncpg.InterfaceError):
        return ErrorCode.DB_CONNECTION_ERROR, 503
    for exc_type, code, status in _DB_ERROR_MAPPING:
        if isinstance(exc, exc_type):
            return code, status
    return ErrorCode.SERVER_ERROR, 500


def _detect_language(request: Request) -> str:
    """Resolve the request language without triggering a cascade error."""
    try:
        if hasattr(request, "state") and hasattr(request.state, "language"):
            value = request.state.language
            if hasattr(value, "value"):
                return value.value
        accept = request.headers.get("Accept-Language", "es")
        return accept[:2] if accept[:2] in ("es", "fr", "en") else "es"
    except Exception:  # defensive: language resolution must never raise
        return "es"


def _get_cors_headers(request: Request) -> dict:
    """Bridge to main.get_cors_headers without creating an import cycle.

    main.py imports this module; we import main at call time so the
    dependency is one-way. The cost (function-local import) is negligible
    because exceptions are rare by definition.
    """
    try:
        from app.main import get_cors_headers  # noqa: WPS433 runtime import
        return get_cors_headers(request)
    except Exception:
        return {}


def _safe_constraint_name(exc: BaseException) -> str | None:
    """Extract the constraint name if asyncpg exposed it — for SERVER LOGS only."""
    for attr in ("constraint_name", "constraint"):
        value = getattr(exc, attr, None)
        if value:
            return str(value)
    return None


def _safe_table_name(exc: BaseException) -> str | None:
    for attr in ("table_name", "table"):
        value = getattr(exc, attr, None)
        if value:
            return str(value)
    return None


def build_db_error_response(request: Request, exc: BaseException) -> JSONResponse:
    """Map an asyncpg exception to a structured, sanitized FastAPI response.

    This is the central DB error sanitizer. All catch-free asyncpg errors
    hit this function via the global exception handler registered in main.py.

    The response body matches the contract expected by the frontend helper
    ``core/api/errors.ts::extractApiError`` — ``detail`` is a dict with a
    metier ``code`` and ``message_es/message_fr/message_en`` fields.

    The raw PostgreSQL error text is **never** surfaced to the client; we
    only log it server-side for ops correlation.
    """
    code, status = _classify(exc)
    lang = _detect_language(request)
    catalog_entry = ERROR_CATALOG.get(code, ERROR_CATALOG[ErrorCode.SERVER_ERROR])

    # Server-side log (rich): SQLSTATE + constraint + table + raw message
    logger.opt(exception=exc).error(
        "Unhandled DB error: code={code} sqlstate={sqlstate} "
        "constraint={constraint} table={table} path={path} method={method}",
        code=code.value,
        sqlstate=getattr(exc, "sqlstate", None),
        constraint=_safe_constraint_name(exc),
        table=_safe_table_name(exc),
        path=request.url.path,
        method=request.method,
    )

    content = {
        "detail": {
            "code": code.value,
            "message_es": catalog_entry.get("es", ""),
            "message_fr": catalog_entry.get("fr", ""),
            "message_en": catalog_entry.get("en", ""),
            # Convenience field for callers that expect a single "message"
            "message": catalog_entry.get(lang, catalog_entry.get("en", "")),
        },
        "error_code": code.value,
    }

    return JSONResponse(
        status_code=status,
        content=content,
        headers=_get_cors_headers(request),
    )
