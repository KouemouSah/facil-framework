"""
FastAPI rate limit dependency — user + IP Redis-backed counters.

Plan: .claude/plans/BUNDLE_DEBUG_PHASE5_PLAN.md §2.4

Wraps :func:`app.core.cache.check_rate_limit` (Upstash Redis + in-memory
fallback, fail-closed on cache failure) as a reusable dependency.

Usage:
    from app.core.rate_limit import rate_limit_dep

    @router.post(
        "/my-expensive-endpoint",
        dependencies=[rate_limit_dep(
            endpoint="my_endpoint",
            user_max=10, user_window=60,
            ip_max=30, ip_window=60,
        )],
    )
    async def handler(...): ...

Design choices:
- **Dual-key check** (user_id + IP) so a single user behind multiple
  IPs cannot evade the limit, and a NAT-shared IP with many users
  still gets a higher ceiling.
- **Fail-closed** inherited from check_rate_limit: if Redis is down
  the helper denies requests, preventing a rate-limit bypass during
  cache outages.
- Anonymous calls (no ``get_current_user`` in the dependency chain)
  fall through to the IP-only path — useful for unauthenticated
  routes but still protects against DoS.
"""

from __future__ import annotations

from typing import Callable, Optional

import jwt
from fastapi import Depends, HTTPException, Request

from app.core.cache import check_rate_limit
from app.core.errors import ErrorCode, get_error_message
from loguru import logger


def _client_ip(request: Request) -> str:
    """Best-effort extraction of the client IP behind proxies."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # First hop is the real client IP
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    client = request.client
    return client.host if client else "unknown"


def _detect_language(request: Request) -> str:
    try:
        if hasattr(request, "state") and hasattr(request.state, "language"):
            value = request.state.language
            if hasattr(value, "value"):
                return value.value
        accept = request.headers.get("Accept-Language", "es")
        return accept[:2] if accept[:2] in ("es", "fr", "en") else "es"
    except Exception:
        return "es"


def _extract_user_id(request: Request) -> Optional[str]:
    """Read the JWT ``sub`` claim directly from the Authorization header
    without hitting the user repository. Skips signature verification
    because the auth middleware (``get_current_user``) will verify it
    properly for any route that actually needs authentication — this
    helper runs *before* that dependency and only needs a stable
    identifier for the Redis counter.

    Returns ``None`` for anonymous requests (missing / malformed header).
    """
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(None, 1)[1].strip()
    try:
        # We intentionally disable signature verification — the real
        # verification happens in get_current_user. Tampering with the
        # token to get a different rate-limit bucket is pointless
        # because the request will still be rejected by auth.
        claims = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
        )
    except Exception:
        return None
    sub = claims.get("sub") if isinstance(claims, dict) else None
    return str(sub) if sub else None


def rate_limit_dep(
    endpoint: str,
    user_max: int,
    user_window: int,
    ip_max: Optional[int] = None,
    ip_window: Optional[int] = None,
) -> Callable:
    """Build a FastAPI dependency that enforces user + IP rate limits.

    :param endpoint: Stable identifier used as the Redis key namespace.
    :param user_max: Max requests per authenticated user in the window.
    :param user_window: User window in seconds.
    :param ip_max: Max requests per IP in ``ip_window`` seconds.
        Defaults to ``user_max * 3`` so shared NATs aren't penalized.
    :param ip_window: IP window in seconds. Defaults to ``user_window``.
    """
    resolved_ip_max = ip_max if ip_max is not None else user_max * 3
    resolved_ip_window = ip_window if ip_window is not None else user_window

    async def dependency(request: Request) -> None:
        ip = _client_ip(request)

        # IP-level check first — the cheapest way to shed load from
        # an attacker who isn't even authenticated.
        ip_allowed, _ip_remaining = await check_rate_limit(
            identifier=f"ip:{ip}",
            endpoint=endpoint,
            max_requests=resolved_ip_max,
            window_seconds=resolved_ip_window,
        )
        if not ip_allowed:
            logger.warning(
                "Rate limit (IP) exceeded: ip=%s endpoint=%s", ip, endpoint,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMITED",
                    "message_es": get_error_message(ErrorCode.RATE_LIMITED, "es"),
                    "message_fr": get_error_message(ErrorCode.RATE_LIMITED, "fr"),
                    "message_en": get_error_message(ErrorCode.RATE_LIMITED, "en"),
                    "message": get_error_message(
                        ErrorCode.RATE_LIMITED, _detect_language(request),
                    ),
                },
            )

        # User-level check: decode the JWT sub claim without signature
        # verification (cheap, no DB hit) so this dependency composes
        # cleanly with get_current_user which will perform the real
        # auth later in the dependency chain.
        user_id = _extract_user_id(request)

        if user_id:
            user_allowed, _user_remaining = await check_rate_limit(
                identifier=f"user:{user_id}",
                endpoint=endpoint,
                max_requests=user_max,
                window_seconds=user_window,
            )
            if not user_allowed:
                logger.warning(
                    "Rate limit (user) exceeded: user=%s endpoint=%s",
                    user_id, endpoint,
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "RATE_LIMITED",
                        "message_es": get_error_message(ErrorCode.RATE_LIMITED, "es"),
                        "message_fr": get_error_message(ErrorCode.RATE_LIMITED, "fr"),
                        "message_en": get_error_message(ErrorCode.RATE_LIMITED, "en"),
                        "message": get_error_message(
                            ErrorCode.RATE_LIMITED, _detect_language(request),
                        ),
                    },
                )

    return Depends(dependency)
