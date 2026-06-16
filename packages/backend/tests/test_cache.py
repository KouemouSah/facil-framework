"""MemoryCache (shared-state abstraction, D4.12)."""

from __future__ import annotations

import pytest

from app.core.cache import MemoryCache, build_cache


@pytest.mark.asyncio
async def test_get_set_delete_exists():
    c = MemoryCache()
    assert await c.get("k") is None and await c.exists("k") is False
    await c.set("k", "v", ttl=60)
    assert await c.get("k") == "v" and await c.exists("k") is True
    await c.delete("k")
    assert await c.get("k") is None


@pytest.mark.asyncio
async def test_ttl_expiry(monkeypatch):
    import app.core.cache as cache_mod
    t = {"now": 1000.0}
    monkeypatch.setattr(cache_mod.time, "monotonic", lambda: t["now"])
    c = MemoryCache()
    await c.set("k", "v", ttl=30)
    assert await c.get("k") == "v"
    t["now"] += 31
    assert await c.get("k") is None        # expired


@pytest.mark.asyncio
async def test_incr_fixed_window(monkeypatch):
    import app.core.cache as cache_mod
    t = {"now": 0.0}
    monkeypatch.setattr(cache_mod.time, "monotonic", lambda: t["now"])
    c = MemoryCache()
    assert [await c.incr("rl", 10) for _ in range(3)] == [1, 2, 3]
    t["now"] += 11                          # window rolls over
    assert await c.incr("rl", 10) == 1


def test_build_cache_defaults_to_memory():
    assert isinstance(build_cache(None), MemoryCache)
    assert isinstance(build_cache(""), MemoryCache)
