"""Pluggable cache / shared state — in-process or Redis (D4.12).

At 1M+ agents the backend runs many replicas, so security state that must be
GLOBAL (OIDC revocation, rate-limit counters) cannot live in per-process dicts.
This is the pluggable seam: MemoryCache (default, single-process / tests) or
RedisCache (shared across replicas). `build_cache(REDIS_URL)` picks one.

Ops are deliberately minimal: get/set/delete/exists + incr (fixed-window counter).
TTLs are seconds. Values are strings.
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod

from app.core.env_posture import is_required

logger = logging.getLogger(__name__)


class Cache(ABC):
    #: Observable backend label, surfaced in /health ("redis" vs "memory").
    backend: str = "memory"

    async def ping(self) -> None:
        """Active liveness probe (Redis: a real round-trip; Memory: a no-op)."""
        return None

    @abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def incr(self, key: str, ttl: int) -> int:
        """Increment a counter; set the TTL when it is first created. Returns the
        new value (fixed-window rate limiting)."""

    async def close(self) -> None:
        return None


class MemoryCache(Cache):
    """In-process TTL cache (single replica / tests). Lazy expiry on access."""

    backend = "memory"

    def __init__(self) -> None:
        self._kv: dict[str, tuple[str, float]] = {}   # key -> (value, expiry)
        self._ctr: dict[str, tuple[int, float]] = {}   # key -> (count, expiry)

    def _alive(self, store: dict, key: str):
        ent = store.get(key)
        if ent is None:
            return None
        if ent[1] <= time.monotonic():
            store.pop(key, None)
            return None
        return ent

    async def get(self, key: str) -> str | None:
        ent = self._alive(self._kv, key)
        return ent[0] if ent else None

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._kv[key] = (value, time.monotonic() + ttl)

    async def delete(self, key: str) -> None:
        self._kv.pop(key, None)

    async def exists(self, key: str) -> bool:
        return self._alive(self._kv, key) is not None

    async def incr(self, key: str, ttl: int) -> int:
        ent = self._alive(self._ctr, key)
        if ent is None:
            self._ctr[key] = (1, time.monotonic() + ttl)
            return 1
        count = ent[0] + 1
        self._ctr[key] = (count, ent[1])   # keep the original window expiry
        return count


class RedisCache(Cache):
    """Redis-backed shared cache (multi-replica). Lazily connects."""

    backend = "redis"

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis  # local import — optional dependency
        self._r = redis.from_url(url, decode_responses=True)

    async def ping(self) -> None:
        await self._r.ping()  # real round-trip — reconciles the lazy from_url()

    async def get(self, key: str) -> str | None:
        return await self._r.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        await self._r.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._r.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._r.exists(key))

    async def incr(self, key: str, ttl: int) -> int:
        count = await self._r.incr(key)
        if count == 1:
            await self._r.expire(key, ttl)
        return int(count)

    async def close(self) -> None:
        await self._r.aclose()


async def build_cache(redis_url: str | None, *, env=None, redis_factory=None) -> Cache:
    """RedisCache when a URL is given (shared across replicas), else MemoryCache.

    When ``REDIS_URL`` is set the cache is actively probed (``ping``) so a Redis
    that is down at boot is detected here instead of surfacing as runtime 500s
    (``redis.from_url`` connects lazily). If the probe fails:

    - **prod / ``CACHE_REQUIRED=1``** → raise (fail-closed): a per-replica
      MemoryCache would silently break OIDC revocation + shared rate-limiting at
      scale — exactly the divergence we refuse to ship.
    - **dev / ``CACHE_REQUIRED=0``** → degrade to MemoryCache with a loud ERROR
      (never a silent ``pass``).
    """
    env = os.environ if env is None else env
    if not redis_url:
        return MemoryCache()
    factory = redis_factory or RedisCache
    try:
        cache = factory(redis_url)
        await cache.ping()
        return cache
    except Exception as exc:  # noqa: BLE001 — construction or connection failure
        if is_required(env, "CACHE_REQUIRED"):
            raise RuntimeError(
                f"REDIS_URL is set but Redis is unreachable or its client is "
                f"unavailable ({type(exc).__name__}) — refusing to start with a "
                "per-replica MemoryCache (OIDC revocation and rate-limit would not be "
                "shared across replicas). Fix Redis or set CACHE_REQUIRED=0 to "
                "explicitly allow degraded single-replica mode."
            ) from exc
        logger.error(
            "REDIS_URL set but Redis unreachable (%s) — DEGRADING to an in-process "
            "MemoryCache; OIDC revocation + rate-limit are now PER-REPLICA. Set "
            "CACHE_REQUIRED=1 to forbid this in production.", type(exc).__name__)
        return MemoryCache()
