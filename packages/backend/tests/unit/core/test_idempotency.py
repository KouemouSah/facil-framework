# -*- coding: utf-8 -*-
"""
Unit tests for app/core/idempotency.py (Plan P3).

Tests the Stripe-style idempotency helpers:
  - check_idempotency_or_replay
  - store_idempotency_result
  - _validate_idempotency_key

Uses a mocked Request object (headers only) + the real HybridCache
(in-memory fallback when Redis URL not set).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import HTTPException  # noqa: E402

from app.core.idempotency import (  # noqa: E402
    MAX_KEY_LENGTH,
    MIN_KEY_LENGTH,
    check_idempotency_or_replay,
    store_idempotency_result,
)

pytestmark = pytest.mark.asyncio


def _mock_request(headers: dict) -> MagicMock:
    """Create a minimal mock of fastapi.Request with headers dict."""
    req = MagicMock()
    req.headers = headers
    return req


# ═══════════════════════════════════════════════════════════════
# P3.F.13 — No header returns None (pass-through)
# ═══════════════════════════════════════════════════════════════


async def test_check_idempotency_no_header_returns_none():
    request = _mock_request({})
    result = await check_idempotency_or_replay(
        request, uuid4(), endpoint_key="collect_payment",
    )
    assert result is None


# ═══════════════════════════════════════════════════════════════
# P3.F.14 — Store then replay returns the cached value
# ═══════════════════════════════════════════════════════════════


async def test_store_then_replay_returns_cached():
    key = "test-idem-" + uuid4().hex[:16]
    user_id = uuid4()
    request = _mock_request({"Idempotency-Key": key})

    # First call: nothing cached → returns None
    cached = await check_idempotency_or_replay(
        request, user_id, "collect_payment",
    )
    assert cached is None

    # Store a result
    payload = {"payment_id": str(uuid4()), "amount": 15000.0, "status": "ok"}
    await store_idempotency_result(
        request, user_id, "collect_payment", payload,
    )

    # Second call: must return the cached payload
    cached = await check_idempotency_or_replay(
        request, user_id, "collect_payment",
    )
    assert cached == payload


# ═══════════════════════════════════════════════════════════════
# P3.F.15 — Different users don't collide on the same key
# ═══════════════════════════════════════════════════════════════


async def test_different_users_dont_collide():
    key = "shared-idem-" + uuid4().hex[:16]
    user_a = uuid4()
    user_b = uuid4()
    request = _mock_request({"Idempotency-Key": key})

    await store_idempotency_result(
        request, user_a, "collect_payment", {"owner": "A"},
    )
    # User B reads the same key → must be cache miss
    cached = await check_idempotency_or_replay(
        request, user_b, "collect_payment",
    )
    assert cached is None

    # User A still sees their payload
    cached_a = await check_idempotency_or_replay(
        request, user_a, "collect_payment",
    )
    assert cached_a == {"owner": "A"}


# ═══════════════════════════════════════════════════════════════
# P3.F.16 — Different endpoints don't collide
# ═══════════════════════════════════════════════════════════════


async def test_different_endpoints_dont_collide():
    key = "endpoint-idem-" + uuid4().hex[:16]
    user_id = uuid4()
    request = _mock_request({"Idempotency-Key": key})

    await store_idempotency_result(
        request, user_id, "collect_payment", {"endpoint": "collect"},
    )
    # Same key + same user but different endpoint → miss
    cached = await check_idempotency_or_replay(
        request, user_id, "create_inspection",
    )
    assert cached is None


# ═══════════════════════════════════════════════════════════════
# P3.F.17 — Key too short raises 400
# ═══════════════════════════════════════════════════════════════


async def test_key_too_short_raises_400():
    request = _mock_request({"Idempotency-Key": "abc"})  # 3 chars < 8
    with pytest.raises(HTTPException) as exc_info:
        await check_idempotency_or_replay(
            request, uuid4(), "collect_payment",
        )
    assert exc_info.value.status_code == 400
    assert "length" in exc_info.value.detail.lower()


# ═══════════════════════════════════════════════════════════════
# P3.F.18 — Key too long raises 400
# ═══════════════════════════════════════════════════════════════


async def test_key_too_long_raises_400():
    request = _mock_request({"Idempotency-Key": "a" * (MAX_KEY_LENGTH + 1)})
    with pytest.raises(HTTPException) as exc_info:
        await check_idempotency_or_replay(
            request, uuid4(), "collect_payment",
        )
    assert exc_info.value.status_code == 400


# ═══════════════════════════════════════════════════════════════
# P3.F.19 — Empty string header treated as absent
# ═══════════════════════════════════════════════════════════════


async def test_empty_key_treated_as_absent():
    request = _mock_request({"Idempotency-Key": ""})
    result = await check_idempotency_or_replay(
        request, uuid4(), "collect_payment",
    )
    assert result is None


# ═══════════════════════════════════════════════════════════════
# P3.F.20 — Key at exact min/max boundaries accepted
# ═══════════════════════════════════════════════════════════════


async def test_key_exact_min_length_accepted():
    request = _mock_request({"Idempotency-Key": "a" * MIN_KEY_LENGTH})
    # Should not raise — just cache miss returning None
    result = await check_idempotency_or_replay(
        request, uuid4(), "test",
    )
    assert result is None


async def test_key_exact_max_length_accepted():
    request = _mock_request({"Idempotency-Key": "a" * MAX_KEY_LENGTH})
    result = await check_idempotency_or_replay(
        request, uuid4(), "test",
    )
    assert result is None
