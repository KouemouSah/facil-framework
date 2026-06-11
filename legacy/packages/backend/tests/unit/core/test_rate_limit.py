# -*- coding: utf-8 -*-
"""
Unit tests for app.core.rate_limit.rate_limit_dep dependency.

Plan: .claude/plans/BUNDLE_DEBUG_PHASE5_PLAN.md §3.4

These tests exercise the helper in isolation by monkey-patching
check_rate_limit so Redis is never touched. They validate:
  - IP-only path (anonymous)
  - User + IP dual-check path (JWT Bearer)
  - 429 raised when IP limit hit
  - 429 raised when user limit hit (IP path passed)
  - Malformed Authorization header falls back to IP-only
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, List, Tuple

import pytest
from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core import rate_limit as rl  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _make_jwt(sub: str) -> str:
    """Build an unsigned JWT-looking token with the given sub claim.

    rate_limit_dep decodes with verify_signature=False, but PyJWT still
    requires the signature segment to be valid base64 (it runs the
    structural parse before deciding to skip crypto). We use an empty
    base64 blob so the decoder is happy.
    """
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode(),
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": sub}).encode(),
    ).rstrip(b"=").decode()
    fake_sig = base64.urlsafe_b64encode(b"\x00" * 32).rstrip(b"=").decode()
    return f"{header}.{payload}.{fake_sig}"


def _make_request(
    *, authorization: str | None = None, ip: str = "1.2.3.4",
) -> SimpleNamespace:
    headers = {"accept-language": "es"}
    if authorization:
        headers["authorization"] = authorization
    return SimpleNamespace(
        headers=headers,
        client=SimpleNamespace(host=ip),
        state=SimpleNamespace(),
    )


def _patch_check_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    sequence: List[Tuple[bool, int]],
) -> Callable:
    """Replace check_rate_limit with a stub that returns sequence in order."""
    calls = []

    async def fake(identifier, endpoint, max_requests, window_seconds):
        calls.append({
            "identifier": identifier,
            "endpoint": endpoint,
            "max": max_requests,
            "window": window_seconds,
        })
        idx = len(calls) - 1
        return sequence[idx] if idx < len(sequence) else sequence[-1]

    monkeypatch.setattr(rl, "check_rate_limit", fake)
    return lambda: calls


async def _run_dep(
    dep_factory,
    request,
) -> None:
    """Extract and await the dependency callable from a Depends(...) wrapper."""
    # rate_limit_dep returns ``Depends(...)``; the actual coroutine is
    # available under ``.dependency``.
    coro = dep_factory.dependency(request)
    await coro


# ─────────────────────────────────────────────────────────────
# T1 — Anonymous IP-only allowed
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anonymous_ip_only_allowed(monkeypatch):
    _patch_check_rate_limit(monkeypatch, [(True, 9)])
    dep = rl.rate_limit_dep(
        endpoint="test_ep", user_max=10, user_window=60,
        ip_max=30, ip_window=60,
    )
    req = _make_request()  # no Authorization

    await _run_dep(dep, req)  # must not raise


# ─────────────────────────────────────────────────────────────
# T2 — Anonymous IP-only rejected 429
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anonymous_ip_only_rejected_429(monkeypatch):
    _patch_check_rate_limit(monkeypatch, [(False, 0)])
    dep = rl.rate_limit_dep(
        endpoint="test_ep", user_max=10, user_window=60,
    )
    req = _make_request()

    with pytest.raises(HTTPException) as exc:
        await _run_dep(dep, req)
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "RATE_LIMITED"
    assert "message_es" in exc.value.detail


# ─────────────────────────────────────────────────────────────
# T3 — Authenticated: IP OK, user OK → allowed
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authenticated_dual_check_allowed(monkeypatch):
    get_calls = _patch_check_rate_limit(monkeypatch, [(True, 29), (True, 9)])
    dep = rl.rate_limit_dep(
        endpoint="test_ep", user_max=10, user_window=60,
    )
    req = _make_request(authorization=f"Bearer {_make_jwt('user-abc')}")

    await _run_dep(dep, req)

    calls = get_calls()
    assert len(calls) == 2
    assert calls[0]["identifier"].startswith("ip:")
    assert calls[1]["identifier"] == "user:user-abc"


# ─────────────────────────────────────────────────────────────
# T4 — Authenticated: IP OK, user over → 429
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authenticated_user_limit_rejected(monkeypatch):
    _patch_check_rate_limit(monkeypatch, [(True, 29), (False, 0)])
    dep = rl.rate_limit_dep(
        endpoint="test_ep", user_max=10, user_window=60,
    )
    req = _make_request(authorization=f"Bearer {_make_jwt('user-abc')}")

    with pytest.raises(HTTPException) as exc:
        await _run_dep(dep, req)
    assert exc.value.status_code == 429


# ─────────────────────────────────────────────────────────────
# T5 — Authenticated: IP over → 429 (user never checked)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ip_limit_short_circuits(monkeypatch):
    get_calls = _patch_check_rate_limit(monkeypatch, [(False, 0), (True, 9)])
    dep = rl.rate_limit_dep(
        endpoint="test_ep", user_max=10, user_window=60,
    )
    req = _make_request(authorization=f"Bearer {_make_jwt('user-abc')}")

    with pytest.raises(HTTPException) as exc:
        await _run_dep(dep, req)
    assert exc.value.status_code == 429
    # Only the IP check ran — user check short-circuited
    assert len(get_calls()) == 1


# ─────────────────────────────────────────────────────────────
# T6 — Malformed Authorization header → IP-only fallback
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_malformed_auth_header_falls_back_to_ip(monkeypatch):
    get_calls = _patch_check_rate_limit(monkeypatch, [(True, 29)])
    dep = rl.rate_limit_dep(
        endpoint="test_ep", user_max=10, user_window=60,
    )
    req = _make_request(authorization="NotBearer garbage")

    await _run_dep(dep, req)

    calls = get_calls()
    assert len(calls) == 1
    assert calls[0]["identifier"].startswith("ip:")


# ─────────────────────────────────────────────────────────────
# T7 — X-Forwarded-For is honored for the IP bucket
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_x_forwarded_for_is_honored(monkeypatch):
    get_calls = _patch_check_rate_limit(monkeypatch, [(True, 29)])
    dep = rl.rate_limit_dep(
        endpoint="test_ep", user_max=10, user_window=60,
    )
    req = SimpleNamespace(
        headers={
            "x-forwarded-for": "203.0.113.7, 10.0.0.1",
            "accept-language": "es",
        },
        client=SimpleNamespace(host="10.0.0.1"),
        state=SimpleNamespace(),
    )

    await _run_dep(dep, req)

    calls = get_calls()
    assert calls[0]["identifier"] == "ip:203.0.113.7"
