"""
Preview Cache Service - Abstraction for document preview caching.

Supports:
- In-memory cache (development/single instance)
- Redis cache (production/multi-instance)

Usage:
    preview_cache = PreviewCache()  # Uses config to select backend
    await preview_cache.set(preview_id, data, ttl_seconds=1800)
    data = await preview_cache.get(preview_id)
    await preview_cache.delete(preview_id)
"""
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> bool:
        """Set value in cache with TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        pass


class InMemoryCache(CacheBackend):
    """
    In-memory cache implementation.

    WARNING: Not suitable for production with multiple instances.
    Data is lost on restart.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value if exists and not expired."""
        entry = self._store.get(key)
        if not entry:
            return None

        expires_at = entry.get("_expires_at")
        if expires_at and datetime.now(timezone.utc) > expires_at:
            # Expired - remove and return None
            del self._store[key]
            return None

        # Return without internal fields
        result = {k: v for k, v in entry.items() if not k.startswith("_")}
        return result

    async def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> bool:
        """Set value with expiration."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._store[key] = {
            **value,
            "_expires_at": expires_at
        }
        return True

    async def delete(self, key: str) -> bool:
        """Delete key if exists."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        now = datetime.now(timezone.utc)
        expired_keys = [
            k for k, v in self._store.items()
            if v.get("_expires_at") and now > v["_expires_at"]
        ]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)


class RedisCache(CacheBackend):
    """
    Redis cache implementation.

    Suitable for production with multiple instances.
    Requires redis-py[async] package.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url
        self._client = None
        self._prefix = "preview:"

    async def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            try:
                from redis import asyncio as aioredis
                self._client = await aioredis.from_url(
                    self._redis_url or "redis://localhost:6379",
                    encoding="utf-8",
                    decode_responses=True
                )
            except ImportError:
                logger.error("redis package not installed. Install with: pip install redis")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._client

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from Redis."""
        try:
            client = await self._get_client()
            data = await client.get(f"{self._prefix}{key}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    async def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> bool:
        """Set value in Redis with expiration."""
        try:
            client = await self._get_client()
            await client.setex(
                f"{self._prefix}{key}",
                ttl_seconds,
                json.dumps(value, default=str)
            )
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            client = await self._get_client()
            result = await client.delete(f"{self._prefix}{key}")
            return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False

    async def cleanup_expired(self) -> int:
        """Redis handles expiration automatically."""
        return 0


class PreviewCache:
    """
    Preview cache with automatic backend selection.

    Uses Redis if REDIS_URL is configured, otherwise falls back to in-memory.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url
        self._backend: Optional[CacheBackend] = None

    def _get_backend(self) -> CacheBackend:
        """Get or create the appropriate cache backend."""
        if self._backend is None:
            if self._redis_url:
                try:
                    self._backend = RedisCache(self._redis_url)
                    logger.info("Using Redis cache for previews")
                except Exception as e:
                    logger.warning(f"Redis unavailable, falling back to in-memory: {e}")
                    self._backend = InMemoryCache()
            else:
                logger.warning("No REDIS_URL configured, using in-memory cache (not suitable for production)")
                self._backend = InMemoryCache()
        return self._backend

    async def get(self, preview_id: str) -> Optional[Dict[str, Any]]:
        """Get preview data by ID."""
        return await self._get_backend().get(preview_id)

    async def set(self, preview_id: str, data: Dict[str, Any], ttl_seconds: int = 1800) -> bool:
        """Store preview data with 30-minute default TTL."""
        return await self._get_backend().set(preview_id, data, ttl_seconds)

    async def delete(self, preview_id: str) -> bool:
        """Delete preview after validation."""
        return await self._get_backend().delete(preview_id)

    async def cleanup_expired(self) -> int:
        """Remove expired previews."""
        return await self._get_backend().cleanup_expired()


# Singleton instance - will be configured based on app settings
def get_preview_cache() -> PreviewCache:
    """Get the preview cache singleton."""
    try:
        from app.config import settings
        redis_url = getattr(settings, 'REDIS_URL', None)
        if redis_url:
            # Mask password in log for security
            masked_url = redis_url.split('@')[-1] if '@' in redis_url else 'configured'
            logger.info(f"REDIS_URL detected: ...@{masked_url}")
        else:
            logger.warning("REDIS_URL not configured - preview cache will use in-memory (not suitable for multi-instance)")
    except Exception as e:
        logger.error(f"Error loading REDIS_URL from settings: {e}")
        redis_url = None
    return PreviewCache(redis_url)


# Create singleton
preview_cache = get_preview_cache()
