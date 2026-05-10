"""
Redis Cache with In-Memory Fallback

Provides caching mechanism with Upstash Redis (TLS) as primary
and in-memory fallback for local development or when Redis is unavailable.

System-wide cache for:
- Menu configurations (5 min TTL)
- Workflow mappings (30 min TTL)
- Permissions (10 min TTL)
- User sessions (30 min TTL)
- Fiscal services catalog (1 hour TTL)
- Translations (1 hour TTL)
- Rate limiting

Usage Examples:
---------------

1. Basic cache operations:
    ```python
    from app.core.cache import get_cache, CacheKeys

    cache = get_cache()

    # Set a value (auto JSON serialization)
    await cache.set("my_key", {"data": "value"}, ttl=300)

    # Get a value (auto JSON deserialization)
    data = await cache.get("my_key")

    # Delete a key
    await cache.delete("my_key")
    ```

2. Using cache decorators:
    ```python
    from app.core.cache import cached, get_services_cache

    @cached(cache_getter=get_services_cache, ttl=3600)
    async def get_expensive_data(param: str) -> dict:
        # This result will be cached for 1 hour
        return await fetch_from_db(param)
    ```

3. Rate limiting:
    ```python
    from app.core.cache import check_rate_limit

    is_allowed, remaining = await check_rate_limit(
        identifier="user_123",
        endpoint="/api/expensive",
        max_requests=100,
        window_seconds=60
    )
    if not is_allowed:
        raise HTTPException(429, "Rate limit exceeded")
    ```

4. Cache invalidation:
    ```python
    from app.core.cache import invalidate_user_permissions_cache

    # After modifying user permissions
    await invalidate_user_permissions_cache(user_id)
    ```

Author: Claude Code Expert
Date: 2026-01-25
"""
import os
import json
import functools
from typing import Any, Optional, Dict, TypeVar, Generic, Callable, Awaitable, Union
from datetime import datetime, timedelta, timezone
import asyncio
from loguru import logger

T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Awaitable[Any]])


# =============================================================================
# IN-MEMORY CACHE (Fallback)
# =============================================================================

class CacheEntry(Generic[T]):
    """Cache entry with value and expiration"""

    def __init__(self, value: T, ttl_seconds: int):
        self.value = value
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class InMemoryCache:
    """Simple in-memory cache with TTL support (fallback)."""

    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl or self._default_ttl)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def delete_pattern(self, pattern: str) -> int:
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                return False
            return True

    async def ttl(self, key: str) -> int:
        """Get TTL of a key in seconds."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return -2
            if entry.is_expired():
                del self._cache[key]
                return -2
            remaining = (entry.expires_at - datetime.now(timezone.utc)).total_seconds()
            return max(0, int(remaining))

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired():
                self._cache[key] = CacheEntry(amount, self._default_ttl)
                return amount
            new_value = (entry.value or 0) + amount
            entry.value = new_value
            return new_value

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on a key."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            entry.expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
            return True

    async def mget(self, keys: list[str]) -> list[Optional[Any]]:
        """Get multiple keys at once."""
        results = []
        for key in keys:
            results.append(await self.get(key))
        return results

    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple keys at once."""
        async with self._lock:
            for key, value in mapping.items():
                self._cache[key] = CacheEntry(value, ttl or self._default_ttl)
        return True


# =============================================================================
# REDIS CACHE (Primary)
# =============================================================================

class RedisCache:
    """Redis cache with Upstash TLS support."""

    def __init__(self, redis_url: str, default_ttl: int = 300):
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._client = None
        self._connected = False

    async def _get_client(self):
        """Lazy initialization of Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as aioredis

                # Parse URL and connect with TLS
                self._client = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
                # Test connection
                await self._client.ping()
                self._connected = True
                logger.info("Redis cache connected successfully (Upstash TLS)")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._client = None
                self._connected = False
                raise
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value is None:
                return None
            # Deserialize JSON
            return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis GET failed for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            client = await self._get_client()
            # Serialize to JSON
            serialized = json.dumps(value, default=str)
            await client.setex(key, ttl or self._default_ttl, serialized)
        except Exception as e:
            logger.warning(f"Redis SET failed for key {key}: {e}")

    async def delete(self, key: str) -> bool:
        try:
            client = await self._get_client()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Redis DELETE failed for key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern using SCAN + pipeline (1 round-trip per batch)."""
        try:
            client = await self._get_client()
            deleted = 0
            keys_batch = []
            async for key in client.scan_iter(match=f"{pattern}*", count=100):
                keys_batch.append(key)
            if keys_batch:
                pipe = client.pipeline(transaction=False)
                for key in keys_batch:
                    pipe.delete(key)
                results = await pipe.execute()
                deleted = sum(1 for r in results if r)
            return deleted
        except Exception as e:
            logger.warning(f"Redis DELETE_PATTERN failed for pattern {pattern}: {e}")
            return 0

    async def clear(self) -> None:
        """Clear all keys (use with caution in production)."""
        try:
            client = await self._get_client()
            await client.flushdb()
        except Exception as e:
            logger.warning(f"Redis CLEAR failed: {e}")

    def is_connected(self) -> bool:
        return self._connected

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        try:
            client = await self._get_client()
            return await client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Redis EXISTS failed for key {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """Get TTL of a key in seconds. Returns -2 if key doesn't exist, -1 if no expiry."""
        try:
            client = await self._get_client()
            return await client.ttl(key)
        except Exception as e:
            logger.warning(f"Redis TTL failed for key {key}: {e}")
            return -2

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a counter. Creates key with value 0 if it doesn't exist."""
        try:
            client = await self._get_client()
            return await client.incrby(key, amount)
        except Exception as e:
            logger.warning(f"Redis INCR failed for key {key}: {e}")
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on a key."""
        try:
            client = await self._get_client()
            return await client.expire(key, ttl)
        except Exception as e:
            logger.warning(f"Redis EXPIRE failed for key {key}: {e}")
            return False

    async def mget(self, keys: list[str]) -> list[Optional[Any]]:
        """Get multiple keys at once."""
        try:
            client = await self._get_client()
            values = await client.mget(keys)
            return [json.loads(v) if v else None for v in values]
        except Exception as e:
            logger.warning(f"Redis MGET failed: {e}")
            return [None] * len(keys)

    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple keys at once."""
        try:
            client = await self._get_client()
            # Serialize values to JSON
            serialized = {k: json.dumps(v, default=str) for k, v in mapping.items()}
            await client.mset(serialized)
            # Set TTL for each key if specified
            if ttl:
                for key in mapping:
                    await client.expire(key, ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis MSET failed: {e}")
            return False


# =============================================================================
# HYBRID CACHE (Redis + In-Memory Fallback)
# =============================================================================

class HybridCache:
    """
    Hybrid cache that uses Redis as primary and falls back to in-memory.

    - Tries Redis first
    - Falls back to in-memory if Redis fails
    - Automatically switches back to Redis when available
    """

    def __init__(self, redis_url: Optional[str], default_ttl: int = 300):
        self._default_ttl = default_ttl
        self._memory_cache = InMemoryCache(default_ttl)
        self._redis_cache: Optional[RedisCache] = None
        self._use_redis = False

        if redis_url:
            self._redis_cache = RedisCache(redis_url, default_ttl)
            self._use_redis = True
            logger.info("Cache configured with Redis (Upstash)")
        else:
            logger.info("Cache configured with in-memory only (no Redis URL)")

    async def get(self, key: str) -> Optional[Any]:
        if self._use_redis and self._redis_cache:
            try:
                value = await self._redis_cache.get(key)
                if value is not None:
                    return value
            except Exception:
                # Fallback to memory
                pass

        return await self._memory_cache.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        # Always set in memory for fast local access
        await self._memory_cache.set(key, value, ttl)

        # Also set in Redis if available
        if self._use_redis and self._redis_cache:
            try:
                await self._redis_cache.set(key, value, ttl)
            except Exception:
                pass  # Memory cache is still set

    async def delete(self, key: str) -> bool:
        # Delete from both
        memory_deleted = await self._memory_cache.delete(key)
        redis_deleted = False

        if self._use_redis and self._redis_cache:
            try:
                redis_deleted = await self._redis_cache.delete(key)
            except Exception:
                pass

        return memory_deleted or redis_deleted

    async def delete_pattern(self, pattern: str) -> int:
        # Delete from both
        memory_count = await self._memory_cache.delete_pattern(pattern)
        redis_count = 0

        if self._use_redis and self._redis_cache:
            try:
                redis_count = await self._redis_cache.delete_pattern(pattern)
            except Exception:
                pass

        return max(memory_count, redis_count)

    async def clear(self) -> None:
        await self._memory_cache.clear()

        if self._use_redis and self._redis_cache:
            try:
                await self._redis_cache.clear()
            except Exception:
                pass

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if self._use_redis and self._redis_cache:
            try:
                return await self._redis_cache.exists(key)
            except Exception:
                pass
        return await self._memory_cache.exists(key)

    async def ttl(self, key: str) -> int:
        """Get TTL of a key in seconds."""
        if self._use_redis and self._redis_cache:
            try:
                return await self._redis_cache.ttl(key)
            except Exception:
                pass
        return await self._memory_cache.ttl(key)

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a counter (useful for rate limiting)."""
        if self._use_redis and self._redis_cache:
            try:
                return await self._redis_cache.incr(key, amount)
            except Exception:
                pass
        return await self._memory_cache.incr(key, amount)

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on a key."""
        memory_result = await self._memory_cache.expire(key, ttl)
        if self._use_redis and self._redis_cache:
            try:
                await self._redis_cache.expire(key, ttl)
            except Exception:
                pass
        return memory_result

    async def mget(self, keys: list[str]) -> list[Optional[Any]]:
        """Get multiple keys at once."""
        if self._use_redis and self._redis_cache:
            try:
                return await self._redis_cache.mget(keys)
            except Exception:
                pass
        return await self._memory_cache.mget(keys)

    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple keys at once."""
        await self._memory_cache.mset(mapping, ttl)
        if self._use_redis and self._redis_cache:
            try:
                await self._redis_cache.mset(mapping, ttl)
            except Exception:
                pass
        return True

    def is_redis_enabled(self) -> bool:
        """Check if Redis is enabled."""
        return self._use_redis

    async def health_check(self) -> Dict[str, Any]:
        """Check cache health status."""
        status = {
            "memory_cache": "ok",
            "redis_enabled": self._use_redis,
            "redis_status": "disabled",
        }
        if self._use_redis and self._redis_cache:
            try:
                await self._redis_cache._get_client()
                status["redis_status"] = "connected"
            except Exception as e:
                status["redis_status"] = f"error: {str(e)}"
        return status


# =============================================================================
# GLOBAL CACHE INSTANCES
# =============================================================================

_default_cache: Optional[HybridCache] = None
_menu_cache: Optional[HybridCache] = None
_workflow_mappings_cache: Optional[HybridCache] = None
_permissions_cache: Optional[HybridCache] = None
_sessions_cache: Optional[HybridCache] = None
_services_cache: Optional[HybridCache] = None
_translations_cache: Optional[HybridCache] = None


def _get_redis_url() -> Optional[str]:
    """Get Redis URL from environment."""
    return os.getenv("REDIS_URL")


def get_cache() -> HybridCache:
    """Get the default system cache (5 min TTL)."""
    global _default_cache
    if _default_cache is None:
        _default_cache = HybridCache(redis_url=_get_redis_url(), default_ttl=300)
    return _default_cache


def get_menu_cache() -> HybridCache:
    """Get the menu configuration cache (5 min TTL)."""
    global _menu_cache
    if _menu_cache is None:
        _menu_cache = HybridCache(redis_url=_get_redis_url(), default_ttl=300)
    return _menu_cache


def get_workflow_mappings_cache() -> HybridCache:
    """Get the workflow mappings cache (30 min TTL - rarely changes)."""
    global _workflow_mappings_cache
    if _workflow_mappings_cache is None:
        _workflow_mappings_cache = HybridCache(redis_url=_get_redis_url(), default_ttl=1800)
    return _workflow_mappings_cache


def get_permissions_cache() -> HybridCache:
    """Get the permissions cache (10 min TTL)."""
    global _permissions_cache
    if _permissions_cache is None:
        _permissions_cache = HybridCache(redis_url=_get_redis_url(), default_ttl=600)
    return _permissions_cache


def get_sessions_cache() -> HybridCache:
    """Get the sessions cache (30 min TTL - matches JWT expiry)."""
    global _sessions_cache
    if _sessions_cache is None:
        _sessions_cache = HybridCache(redis_url=_get_redis_url(), default_ttl=1800)
    return _sessions_cache


def get_services_cache() -> HybridCache:
    """Get the fiscal services cache (1 hour TTL - rarely changes)."""
    global _services_cache
    if _services_cache is None:
        _services_cache = HybridCache(redis_url=_get_redis_url(), default_ttl=3600)
    return _services_cache


def get_translations_cache() -> HybridCache:
    """Get the translations cache (1 hour TTL - rarely changes)."""
    global _translations_cache
    if _translations_cache is None:
        _translations_cache = HybridCache(redis_url=_get_redis_url(), default_ttl=3600)
    return _translations_cache


# =============================================================================
# CACHE KEYS
# =============================================================================

class CacheKeys:
    """
    Cache key generators for consistent key naming across the system.

    Key format: {domain}:{entity_type}:{identifier}
    Examples:
        - menu:agent:123
        - perm:user:456
        - svc:list:active
    """

    # Menu related keys
    @staticmethod
    def agent_menu_config(agent_profile_id: str) -> str:
        return f"menu:agent:{agent_profile_id}"

    @staticmethod
    def workflow_mappings() -> str:
        return "menu:workflow_mappings"

    @staticmethod
    def role_menu_config(role_id: str) -> str:
        return f"menu:role:{role_id}"

    # Permission related keys
    @staticmethod
    def user_permissions(user_id: str) -> str:
        return f"perm:user:{user_id}"

    @staticmethod
    def role_permissions(role_code: str) -> str:
        return f"perm:role:{role_code}"

    @staticmethod
    def all_permissions() -> str:
        return "perm:all"

    # Session related keys
    @staticmethod
    def user_session(user_id: str) -> str:
        return f"session:user:{user_id}"

    @staticmethod
    def refresh_token(token_hash: str) -> str:
        return f"session:refresh:{token_hash}"

    # Fiscal services related keys
    @staticmethod
    def services_list(status: str = "active") -> str:
        return f"svc:list:{status}"

    @staticmethod
    def service_detail(service_id: Union[str, int]) -> str:
        return f"svc:detail:{service_id}"

    @staticmethod
    def services_by_category(category_id: Union[str, int]) -> str:
        return f"svc:category:{category_id}"

    @staticmethod
    def services_by_ministry(ministry_id: Union[str, int]) -> str:
        return f"svc:ministry:{ministry_id}"

    # Translation related keys
    @staticmethod
    def translations(locale: str, category: str = "all") -> str:
        return f"trans:{locale}:{category}"

    @staticmethod
    def entity_translations(entity_type: str, entity_id: Union[str, int], locale: str) -> str:
        return f"trans:entity:{entity_type}:{entity_id}:{locale}"

    # Display config keys
    @staticmethod
    def display_config(workflow_code: str) -> str:
        return f"menu:display_config:{workflow_code}"

    # Rate limiting keys
    @staticmethod
    def rate_limit(identifier: str, endpoint: str) -> str:
        return f"rate:{endpoint}:{identifier}"

    # User dashboard keys
    @staticmethod
    def user_declarations(user_id: str, status: str = "all", page: int = 1) -> str:
        return f"dash:decl:{user_id}:{status}:{page}"

    @staticmethod
    def user_payments(user_id: str, page: int = 1) -> str:
        return f"dash:pay:{user_id}:{page}"

    @staticmethod
    def user_dashboard_stats(user_id: str) -> str:
        return f"dash:stats:{user_id}"

    @staticmethod
    def user_service_requests(user_id: str, page: int = 1) -> str:
        return f"dash:svcreq:{user_id}:{page}"

    # Admin dashboard keys
    @staticmethod
    def admin_users_list(page: int = 1, filters_hash: str = "") -> str:
        return f"admin:users:{page}:{filters_hash}"

    @staticmethod
    def admin_stats() -> str:
        return "admin:stats"

    @staticmethod
    def admin_audit_logs(page: int = 1, filters_hash: str = "") -> str:
        return f"admin:audit:{page}:{filters_hash}"

    @staticmethod
    def treasury_stats(period: str = "current") -> str:
        return f"treasury:stats:{period}"

    @staticmethod
    def treasury_payments(page: int = 1, filters_hash: str = "") -> str:
        return f"treasury:payments:{page}:{filters_hash}"

    # Generic cache keys
    @staticmethod
    def custom(domain: str, *parts: str) -> str:
        """Build a custom cache key with given domain and parts."""
        return f"{domain}:{':'.join(parts)}"


# =============================================================================
# CACHE INVALIDATION HELPERS
# =============================================================================

async def invalidate_agent_menu_cache(agent_profile_id: str) -> None:
    """Invalidate menu cache for a specific agent."""
    cache = get_menu_cache()
    key = CacheKeys.agent_menu_config(agent_profile_id)
    deleted = await cache.delete(key)
    if deleted:
        logger.debug(f"Invalidated menu cache for agent {agent_profile_id}")


async def invalidate_role_menu_cache(role_id: str) -> None:
    """Invalidate menu cache for all agents with a specific role."""
    cache = get_menu_cache()
    # Clear all agent menu caches when a role changes
    count = await cache.delete_pattern("menu:agent:")
    if count > 0:
        logger.debug(f"Invalidated {count} agent menu caches for role change")


async def invalidate_workflow_mappings_cache() -> None:
    """Invalidate workflow mappings cache."""
    cache = get_workflow_mappings_cache()
    await cache.delete(CacheKeys.workflow_mappings())
    logger.debug("Invalidated workflow mappings cache")


async def invalidate_user_permissions_cache(user_id: str) -> None:
    """Invalidate permissions cache for a specific user."""
    cache = get_permissions_cache()
    await cache.delete(CacheKeys.user_permissions(user_id))
    logger.debug(f"Invalidated permissions cache for user {user_id}")


async def invalidate_role_permissions_cache(role_code: str) -> None:
    """Invalidate permissions cache for all users with a specific role."""
    cache = get_permissions_cache()
    # Clear the specific role cache
    await cache.delete(CacheKeys.role_permissions(role_code))
    # Also clear all user permissions (they may inherit from this role)
    count = await cache.delete_pattern("perm:user:")
    logger.debug(f"Invalidated role permissions cache and {count} user permission caches")


async def invalidate_all_permissions_cache() -> None:
    """Invalidate all permissions caches."""
    cache = get_permissions_cache()
    await cache.delete_pattern("perm:")
    logger.debug("Invalidated all permissions caches")


async def invalidate_services_cache() -> None:
    """Invalidate all fiscal services caches."""
    cache = get_services_cache()
    await cache.delete_pattern("svc:")
    logger.debug("Invalidated all services caches")


async def invalidate_service_cache(service_id: Union[str, int]) -> None:
    """Invalidate cache for a specific service."""
    cache = get_services_cache()
    await cache.delete(CacheKeys.service_detail(service_id))
    # Also invalidate list caches
    await cache.delete_pattern("svc:list:")
    logger.debug(f"Invalidated cache for service {service_id}")


async def invalidate_translations_cache(locale: Optional[str] = None) -> None:
    """Invalidate translations cache. If locale is specified, only that locale."""
    cache = get_translations_cache()
    if locale:
        await cache.delete_pattern(f"trans:{locale}:")
        logger.debug(f"Invalidated translations cache for locale {locale}")
    else:
        await cache.delete_pattern("trans:")
        logger.debug("Invalidated all translations caches")


async def invalidate_user_dashboard_cache(user_id: str) -> None:
    """Invalidate all dashboard caches for a specific user."""
    cache = get_cache()
    await cache.delete_pattern(f"dash:decl:{user_id}:")
    await cache.delete_pattern(f"dash:pay:{user_id}:")
    await cache.delete(CacheKeys.user_dashboard_stats(user_id))
    await cache.delete_pattern(f"dash:svcreq:{user_id}:")
    logger.debug(f"Invalidated dashboard cache for user {user_id}")


async def invalidate_user_declarations_cache(user_id: str) -> None:
    """Invalidate declarations cache for a specific user."""
    cache = get_cache()
    await cache.delete_pattern(f"dash:decl:{user_id}:")
    await cache.delete(CacheKeys.user_dashboard_stats(user_id))
    logger.debug(f"Invalidated declarations cache for user {user_id}")


async def invalidate_user_payments_cache(user_id: str) -> None:
    """Invalidate payments cache for a specific user."""
    cache = get_cache()
    await cache.delete_pattern(f"dash:pay:{user_id}:")
    await cache.delete(CacheKeys.user_dashboard_stats(user_id))
    logger.debug(f"Invalidated payments cache for user {user_id}")


async def invalidate_admin_cache() -> None:
    """Invalidate all admin dashboard caches."""
    cache = get_cache()
    await cache.delete_pattern("admin:")
    logger.debug("Invalidated admin dashboard cache")


async def invalidate_treasury_cache() -> None:
    """Invalidate all treasury dashboard caches."""
    cache = get_cache()
    await cache.delete_pattern("treasury:")
    logger.debug("Invalidated treasury dashboard cache")


# =============================================================================
# CACHE DECORATOR
# =============================================================================

def cached(
    cache_getter: Callable[[], HybridCache] = get_cache,
    key_builder: Optional[Callable[..., str]] = None,
    ttl: Optional[int] = None,
    prefix: str = "fn",
):
    """
    Decorator to cache async function results.

    Args:
        cache_getter: Function that returns the cache instance to use
        key_builder: Function to build the cache key from function args.
                    If None, uses function name + args hash
        ttl: Time to live in seconds (uses cache default if None)
        prefix: Key prefix for auto-generated keys

    Usage:
        @cached(cache_getter=get_services_cache, ttl=3600)
        async def get_service(service_id: int) -> dict:
            ...

        @cached(key_builder=lambda user_id: f"user:{user_id}")
        async def get_user(user_id: str) -> dict:
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache = cache_getter()

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Auto-generate key from function name and arguments
                args_str = ":".join(str(a) for a in args)
                kwargs_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{prefix}:{func.__name__}:{args_str}:{kwargs_str}".rstrip(":")

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT for {cache_key}")
                return cached_value

            # Call function and cache result
            logger.debug(f"Cache MISS for {cache_key}")
            result = await func(*args, **kwargs)

            if result is not None:
                await cache.set(cache_key, result, ttl)

            return result

        return wrapper  # type: ignore
    return decorator


# =============================================================================
# RATE LIMITING
# =============================================================================

async def check_rate_limit(
    identifier: str,
    endpoint: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """
    Check if a request should be rate limited.

    Args:
        identifier: User ID, IP address, or other identifier
        endpoint: API endpoint or action name
        max_requests: Maximum requests allowed in the window
        window_seconds: Time window in seconds

    Returns:
        Tuple of (is_allowed, remaining_requests)
    """
    cache = get_cache()
    key = CacheKeys.rate_limit(identifier, endpoint)

    # Increment counter
    count = await cache.incr(key)

    # Fail-closed: if cache returns 0 (failure), deny the request
    if count == 0:
        logger.warning(f"Rate limit cache failure for {identifier}:{endpoint} — denying request (fail-closed)")
        return False, 0

    # Set expiry on first request
    if count == 1:
        await cache.expire(key, window_seconds)

    is_allowed = count <= max_requests
    remaining = max(0, max_requests - count)

    return is_allowed, remaining


# =============================================================================
# CACHE HEALTH CHECK
# =============================================================================

async def get_cache_health() -> Dict[str, Any]:
    """Get health status of all cache instances."""
    default_cache = get_cache()
    health = await default_cache.health_check()

    return {
        "cache_type": "hybrid" if health["redis_enabled"] else "memory_only",
        "redis_enabled": health["redis_enabled"],
        "redis_status": health["redis_status"],
        "memory_cache": health["memory_cache"],
    }


# =============================================================================
# STARTUP INITIALIZATION
# =============================================================================

async def initialize_cache() -> None:
    """
    Initialize cache connections at application startup.
    Call this from FastAPI lifespan or on_event("startup").
    """
    logger.info("Initializing cache system...")

    # Initialize default cache (triggers Redis connection)
    cache = get_cache()
    health = await cache.health_check()

    if health["redis_enabled"]:
        if health["redis_status"] == "connected":
            logger.info("Redis cache initialized successfully (Upstash TLS)")
        else:
            logger.warning(f"Redis cache failed to connect: {health['redis_status']}")
            logger.info("Falling back to in-memory cache")
    else:
        logger.info("Running with in-memory cache only (no REDIS_URL configured)")


async def shutdown_cache() -> None:
    """
    Cleanup cache connections at application shutdown.
    """
    logger.info("Shutting down cache system...")
    # Redis connections are cleaned up automatically
    # Clear globals to allow re-initialization if needed
    global _default_cache, _menu_cache, _workflow_mappings_cache
    global _permissions_cache, _sessions_cache, _services_cache, _translations_cache
    _default_cache = None
    _menu_cache = None
    _workflow_mappings_cache = None
    _permissions_cache = None
    _sessions_cache = None
    _services_cache = None
    _translations_cache = None
