"""Idempotency-Key helpers for safe retry of mutating endpoints.

Plan P3 — INSPECTION_BUNDLE_P3_DETAIL.md §2 D1 / §3 P3.B

Pattern: Stripe-style idempotency-key with 2 explicit helpers called at the
beginning and end of the handler. Avoids FastAPI decorator magic which
would conflict with Pydantic request parsing.

Usage in a route:

    @router.post("/collect")
    async def collect_payment(
        request: Request,
        payload: CollectRequest,
        current_user=Depends(get_current_user),
    ):
        # 1. Replay check
        cached = await check_idempotency_or_replay(
            request, UUID(current_user.id), "collect_payment"
        )
        if cached is not None:
            return JSONResponse(
                content=cached,
                headers={"Idempotency-Replay": "true"},
            )

        # 2. Normal handler
        result = await do_the_work(payload)

        # 3. Store for future replay
        await store_idempotency_result(
            request, UUID(current_user.id), "collect_payment", result
        )
        return result

Properties:
  - Cache key: idem:{endpoint_key}:{user_id}:{idempotency_key_header}
    → scope is (endpoint, user, client-provided key) — 2 users using the
    same key don't collide.
  - TTL default 24h: covers mobile offline sync retries.
  - Fail-open: if the cache is down, requests proceed normally (no lock).
  - Header validation: 8-128 chars, raise 400 otherwise (anti-abuse).

OWASP: A04 (insecure design) — protects /collect from retry-induced
double-charge on unstable field networks.
"""

from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, Request
from loguru import logger

from app.core.cache import get_cache

# Idempotency-Key constraints (Stripe-compatible, len 8-128)
IDEMPOTENCY_HEADER = "Idempotency-Key"
MIN_KEY_LENGTH = 8
MAX_KEY_LENGTH = 128
DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h


def _build_cache_key(endpoint_key: str, user_id: UUID, idempotency_key: str) -> str:
    """Compose the Redis cache key for an idempotency entry."""
    return f"idem:{endpoint_key}:{user_id}:{idempotency_key}"


def _validate_idempotency_key(key: Optional[str]) -> Optional[str]:
    """
    Validate the header value.

    Returns the key if valid, None if absent (header not provided).
    Raises HTTPException(400) if present but invalid (wrong length).
    """
    if key is None or key == "":
        return None
    if len(key) < MIN_KEY_LENGTH or len(key) > MAX_KEY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid Idempotency-Key: length must be "
                f"{MIN_KEY_LENGTH}-{MAX_KEY_LENGTH} chars"
            ),
        )
    return key


async def check_idempotency_or_replay(
    request: Request,
    user_id: UUID,
    endpoint_key: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,  # noqa: ARG001 — kept for symmetry
) -> Optional[Any]:
    """
    Check if this request is a replay of a previous one.

    Returns:
        - None if no Idempotency-Key header (proceed with normal handler)
        - None if key is present but no cached response (proceed + store later)
        - The cached result dict if a previous response exists (short-circuit)

    Raises:
        HTTPException(400) if the Idempotency-Key header length is invalid.
    """
    raw_key = request.headers.get(IDEMPOTENCY_HEADER)
    key = _validate_idempotency_key(raw_key)
    if key is None:
        return None

    cache_key = _build_cache_key(endpoint_key, user_id, key)

    try:
        cache = get_cache()
        cached = await cache.get(cache_key)
    except Exception as e:
        # Fail-open: cache problem → don't block the request
        logger.warning(
            "Idempotency cache GET failed (fail-open) — endpoint={} key={} err={}",
            endpoint_key, key, e,
        )
        return None

    if cached is not None:
        logger.info(
            "Idempotency REPLAY — endpoint={} user={} key={}",
            endpoint_key, user_id, key,
        )
    return cached


async def store_idempotency_result(
    request: Request,
    user_id: UUID,
    endpoint_key: str,
    result: Any,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """
    Store the handler result for future replay within ttl_seconds.

    Called at the end of the handler, AFTER the request succeeded.
    No-op if Idempotency-Key header absent.

    Fail-open: if cache set fails, the response is still returned to the
    client but future retries will hit the backend again (non-idempotent
    fallback).
    """
    raw_key = request.headers.get(IDEMPOTENCY_HEADER)
    # Don't re-validate (check_idempotency_or_replay already did at request start)
    if not raw_key or len(raw_key) < MIN_KEY_LENGTH or len(raw_key) > MAX_KEY_LENGTH:
        return

    cache_key = _build_cache_key(endpoint_key, user_id, raw_key)
    try:
        cache = get_cache()
        await cache.set(cache_key, result, ttl_seconds)
        logger.debug(
            "Idempotency STORE — endpoint={} user={} key={} ttl={}s",
            endpoint_key, user_id, raw_key, ttl_seconds,
        )
    except Exception as e:
        logger.warning(
            "Idempotency cache SET failed (fail-open) — endpoint={} key={} err={}",
            endpoint_key, raw_key, e,
        )
