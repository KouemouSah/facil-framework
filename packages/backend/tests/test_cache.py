"""MemoryCache (shared-state abstraction, D4.12) + build_cache fail-secure (F3/A1a)."""

from __future__ import annotations

import logging

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


@pytest.mark.asyncio
async def test_build_cache_defaults_to_memory():
    for url in (None, ""):
        c = await build_cache(url, env={})
        assert isinstance(c, MemoryCache) and c.backend == "memory"


class _FakeRedis:
    """Stand-in cache whose ping() can be made to fail (Redis down at boot)."""

    backend = "redis"

    def __init__(self, url, *, ping_error=None):
        self.url = url
        self._ping_error = ping_error
        self.pinged = False

    async def ping(self) -> None:
        self.pinged = True
        if self._ping_error is not None:
            raise self._ping_error


@pytest.mark.asyncio
async def test_build_cache_uses_redis_when_reachable():
    made = {}

    def factory(url):
        made["c"] = _FakeRedis(url)
        return made["c"]

    c = await build_cache("redis://x", env={}, redis_factory=factory)
    assert c is made["c"] and c.backend == "redis"
    assert c.pinged is True  # active probe ran (reconciles lazy from_url)


@pytest.mark.asyncio
async def test_build_cache_fails_closed_in_prod_when_redis_down():
    def factory(url):
        return _FakeRedis(url, ping_error=ConnectionError("refused"))

    with pytest.raises(RuntimeError, match="CACHE_REQUIRED"):
        await build_cache("redis://x", env={"ENVIRONMENT": "production"},
                          redis_factory=factory)


@pytest.mark.asyncio
async def test_build_cache_degrades_loudly_in_dev_when_redis_down(caplog):
    def factory(url):
        return _FakeRedis(url, ping_error=ConnectionError("refused"))

    with caplog.at_level(logging.ERROR):
        c = await build_cache("redis://x", env={"ENVIRONMENT": "development"},
                              redis_factory=factory)
    assert isinstance(c, MemoryCache) and c.backend == "memory"
    assert any("DEGRADING" in r.message for r in caplog.records)  # not silent


@pytest.mark.asyncio
async def test_build_cache_construction_failure_treated_as_unreachable():
    def factory(url):
        raise ImportError("redis package not installed")  # construction failure

    # Dev posture degrades; prod posture would raise (covered above).
    c = await build_cache("redis://x", env={"ENVIRONMENT": "dev"}, redis_factory=factory)
    assert isinstance(c, MemoryCache)


@pytest.mark.asyncio
async def test_build_cache_explicit_required_overrides_dev():
    def factory(url):
        return _FakeRedis(url, ping_error=ConnectionError("refused"))

    with pytest.raises(RuntimeError):
        await build_cache("redis://x", env={"ENVIRONMENT": "dev", "CACHE_REQUIRED": "1"},
                          redis_factory=factory)


@pytest.mark.asyncio
async def test_memory_cache_ping_is_noop():
    await MemoryCache().ping()  # must not raise
