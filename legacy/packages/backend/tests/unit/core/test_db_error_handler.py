# -*- coding: utf-8 -*-
"""
Unit tests for app.core.db_error_handler.build_db_error_response.

Plan: .claude/plans/BUNDLE_DEBUG_PHASE4_PLAN.md §3.4

Validates that every asyncpg exception subclass we care about is mapped
to the right (ErrorCode, HTTP status) pair, with a sanitized trilingual
body that never leaks constraint/table names to the client.

No database is touched — we build fake asyncpg exceptions in-memory.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.db_error_handler import build_db_error_response  # noqa: E402
from app.core.errors import ErrorCode  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def make_request(path: str = "/api/v1/bundle-workflow/initiate-payment", lang: str = "es"):
    """Build the minimal Request-like object build_db_error_response needs."""
    return SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path=path),
        headers={"Accept-Language": lang},
        state=SimpleNamespace(),
    )


def body_of(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


# ─────────────────────────────────────────────────────────────
# T1 — UniqueViolation → 409 + DB_UNIQUE_VIOLATION
# ─────────────────────────────────────────────────────────────


def test_unique_violation_maps_to_409():
    exc = asyncpg.exceptions.UniqueViolationError("duplicate key on test_pkey")
    response = build_db_error_response(make_request(lang="es"), exc)
    body = body_of(response)

    assert response.status_code == 409
    assert body["detail"]["code"] == ErrorCode.DB_UNIQUE_VIOLATION.value
    assert body["error_code"] == ErrorCode.DB_UNIQUE_VIOLATION.value
    assert "ya existe" in body["detail"]["message_es"].lower()
    assert "message_fr" in body["detail"]
    assert "message_en" in body["detail"]
    # Must NOT leak the raw PG message
    assert "test_pkey" not in json.dumps(body)


# ─────────────────────────────────────────────────────────────
# T2 — CheckViolation → 422 + DB_CHECK_VIOLATION + locale pick
# ─────────────────────────────────────────────────────────────


def test_check_violation_maps_to_422_fr():
    exc = asyncpg.exceptions.CheckViolationError("violates bundle_integrity")
    response = build_db_error_response(make_request(lang="fr"), exc)
    body = body_of(response)

    assert response.status_code == 422
    assert body["detail"]["code"] == ErrorCode.DB_CHECK_VIOLATION.value
    # The convenience "message" is locale-selected
    assert "validation" in body["detail"]["message"].lower()
    assert "bundle_integrity" not in json.dumps(body)


# ─────────────────────────────────────────────────────────────
# T3 — FK violation → 422
# ─────────────────────────────────────────────────────────────


def test_fk_violation_maps_to_422():
    exc = asyncpg.exceptions.ForeignKeyViolationError("fk missing")
    response = build_db_error_response(make_request(), exc)
    body = body_of(response)

    assert response.status_code == 422
    assert body["detail"]["code"] == ErrorCode.DB_FK_VIOLATION.value


# ─────────────────────────────────────────────────────────────
# T4 — NotNull violation → 422
# ─────────────────────────────────────────────────────────────


def test_not_null_violation_maps_to_422():
    exc = asyncpg.exceptions.NotNullViolationError("null for required column")
    response = build_db_error_response(make_request(), exc)
    body = body_of(response)

    assert response.status_code == 422
    assert body["detail"]["code"] == ErrorCode.DB_NOT_NULL_VIOLATION.value


# ─────────────────────────────────────────────────────────────
# T5 — SerializationError → 409 (retryable)
# ─────────────────────────────────────────────────────────────


def test_serialization_failure_maps_to_409():
    exc = asyncpg.exceptions.SerializationError("serialization failure")
    response = build_db_error_response(make_request(), exc)
    body = body_of(response)

    assert response.status_code == 409
    assert body["detail"]["code"] == ErrorCode.DB_SERIALIZATION_FAILURE.value


# ─────────────────────────────────────────────────────────────
# T6 — DeadlockDetected → 409
# ─────────────────────────────────────────────────────────────


def test_deadlock_maps_to_409():
    exc = asyncpg.exceptions.DeadlockDetectedError("deadlock detected")
    response = build_db_error_response(make_request(), exc)
    body = body_of(response)

    assert response.status_code == 409
    assert body["detail"]["code"] == ErrorCode.DB_DEADLOCK.value


# ─────────────────────────────────────────────────────────────
# T7 — LockNotAvailable → 409 (lock_timeout)
# ─────────────────────────────────────────────────────────────


def test_lock_not_available_maps_to_409():
    exc = asyncpg.exceptions.LockNotAvailableError("could not obtain lock")
    response = build_db_error_response(make_request(), exc)
    body = body_of(response)

    assert response.status_code == 409
    assert body["detail"]["code"] == ErrorCode.DB_LOCK_TIMEOUT.value


# ─────────────────────────────────────────────────────────────
# T8 — QueryCanceled (statement_timeout) → 504
# ─────────────────────────────────────────────────────────────


def test_query_canceled_maps_to_504():
    exc = asyncpg.exceptions.QueryCanceledError("query canceled due to statement timeout")
    response = build_db_error_response(make_request(), exc)
    body = body_of(response)

    assert response.status_code == 504
    assert body["detail"]["code"] == ErrorCode.DB_STATEMENT_TIMEOUT.value


# ─────────────────────────────────────────────────────────────
# T9 — InterfaceError (connection-layer) → 503
# ─────────────────────────────────────────────────────────────


def test_interface_error_maps_to_503():
    exc = asyncpg.exceptions.InterfaceError("connection lost")
    response = build_db_error_response(make_request(), exc)
    body = body_of(response)

    assert response.status_code == 503
    assert body["detail"]["code"] == ErrorCode.DB_CONNECTION_ERROR.value


# ─────────────────────────────────────────────────────────────
# T10 — Unknown PostgresError subclass → 500 generic
# ─────────────────────────────────────────────────────────────


def test_unknown_postgres_error_falls_back_to_500():
    # Generic PostgresError not in our mapping list
    exc = asyncpg.exceptions.PostgresError("some unknown pg error")
    response = build_db_error_response(make_request(), exc)
    body = body_of(response)

    assert response.status_code == 500
    assert body["detail"]["code"] == ErrorCode.SERVER_ERROR.value


# ─────────────────────────────────────────────────────────────
# T11 — Locale fallback chain (unsupported locale → es)
# ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("lang", ["es", "fr", "en", "pt", "de"])
def test_all_locales_render_localized_message(lang):
    exc = asyncpg.exceptions.UniqueViolationError("x")
    response = build_db_error_response(make_request(lang=lang), exc)
    body = body_of(response)
    assert body["detail"]["message"]  # never empty
    assert body["detail"]["message_es"]
    assert body["detail"]["message_fr"]
    assert body["detail"]["message_en"]
