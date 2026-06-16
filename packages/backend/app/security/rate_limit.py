"""Ingress rate limiting — fixed-window, per (scope, client-IP) (D4.8 #1).

A first-layer app guard against brute-force / credential-stuffing / abuse on the
public auth endpoints (login, register, password-reset). In-process (per worker)
— a shared Redis-backed limiter is the scale upgrade; the edge (Caddy/WAF) is the
complementary network layer.

The store lives on `app.state.rate_limiter`. When it is ABSENT the limiter is a
no-op — so test fixtures / contexts that don't initialise it are not affected.
"""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, status


def _allow(store: dict, key: str, limit: int, window: float) -> bool:
    now = time.monotonic()
    entry = store.get(key)
    if entry is None or now - entry[1] >= window:
        store[key] = [1, now]          # new window
        return True
    if entry[0] >= limit:
        return False
    entry[0] += 1
    return True


def rate_limited(scope: str, limit: int, window_seconds: float = 60.0):
    """Dependency: at most `limit` requests per `window_seconds` per client IP."""
    async def dep(request: Request) -> None:
        store = getattr(request.app.state, "rate_limiter", None)
        if store is None:
            return  # limiter disabled in this context
        ip = request.client.host if request.client else "unknown"
        if not _allow(store, f"{scope}:{ip}", limit, window_seconds):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "too many requests — slow down")
    return dep
