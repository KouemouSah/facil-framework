"""Pluggable cache / shared state — in-process or Redis (D4.12).

At 1M+ agents the backend runs many replicas, so security state that must be
GLOBAL (OIDC revocation, rate-limit counters) cannot live in per-process dicts.
This is the pluggable seam: MemoryCache (default, single-process / tests) or
RedisCache (shared across replicas). `build_cache(REDIS_URL)` picks one.

Ops are deliberately minimal: get/set/delete/exists + incr (fixed-window counter).
TTLs are seconds. Values are strings.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod


class Cache(ABC):
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

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis  # local import — optional dependency
        self._r = redis.from_url(url, decode_responses=True)

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


def build_cache(redis_url: str | None) -> Cache:
    """RedisCache when a URL is given (shared across replicas), else MemoryCache."""
    if redis_url:
        try:
            return RedisCache(redis_url)
        except Exception:  # noqa: BLE001 — redis missing/unreachable -> degrade
            pass
    return MemoryCache()
