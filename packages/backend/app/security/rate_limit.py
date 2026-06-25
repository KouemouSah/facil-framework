"""Ingress rate limiting — fixed-window, per (scope, client-IP) (D4.8 #1).

A first-layer app guard against brute-force / credential-stuffing / abuse on the
public auth endpoints (login, register, password-reset). In-process (per worker)
— a shared Redis-backed limiter is the scale upgrade; the edge (Caddy/WAF) is the
complementary network layer.

The store is the shared cache on `app.state.cache` (Redis at scale → GLOBAL across
replicas; in-process otherwise). When it is ABSENT the limiter is a no-op — so test
fixtures / contexts that don't initialise it are not affected.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status


def rate_limited(scope: str, limit: int, window_seconds: int = 60):
    """Dependency: at most `limit` requests per `window_seconds` per client IP.
    Backed by the shared cache (Redis at scale → GLOBAL across replicas; in-process
    otherwise). No cache configured -> limiter is a no-op."""
    async def dep(request: Request) -> None:
        cache = getattr(request.app.state, "cache", None)
        if cache is None:
            return
        ip = request.client.host if request.client else "unknown"
        count = await cache.incr(f"rl:{scope}:{ip}", int(window_seconds))
        if count > limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "too many requests — slow down")
    return dep
