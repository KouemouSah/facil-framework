"""
Homepage Cache Service
Manages Redis caching with intelligent invalidation
"""

from typing import Optional, Dict, Any, List
import json
from datetime import datetime
import redis.asyncio as redis
from loguru import logger


# Cache configuration
STATS_CACHE_KEY = "homepage:stats:v2"  # v2 to avoid conflicts with old cache
STATS_TTL = 1800  # 30 minutes

CATEGORIES_CACHE_KEY_PREFIX = "homepage:categories:v2"  # One key per language
CATEGORIES_TTL = 3600  # 1 hour


class HomepageCacheService:
    """
    Cache service for homepage data with invalidation support

    Handles:
    - Get/Set cached stats and categories
    - Cache invalidation on data changes
    - Graceful fallback when Redis unavailable
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client

    # ========================================================================
    # STATS CACHING
    # ========================================================================

    async def get_cached_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get cached homepage stats

        Returns:
            Stats dict if cached, None otherwise
        """
        if not self.redis:
            return None

        try:
            cached_data = await self.redis.get(STATS_CACHE_KEY)
            if cached_data:
                logger.debug("✅ Homepage stats served from cache")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Redis get failed (graceful fallback): {e}")

        return None

    async def cache_stats(self, stats: Dict[str, Any]) -> bool:
        """
        Cache homepage stats

        Args:
            stats: Stats data to cache

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.redis:
            return False

        try:
            await self.redis.setex(
                STATS_CACHE_KEY,
                STATS_TTL,
                json.dumps(stats)
            )
            logger.debug(f"✅ Homepage stats cached for {STATS_TTL}s")
            return True
        except Exception as e:
            logger.warning(f"Redis setex failed (non-critical): {e}")
            return False

    # ========================================================================
    # CATEGORIES CACHING (per language)
    # ========================================================================

    def _get_categories_cache_key(self, language: str) -> str:
        """Get cache key for categories by language"""
        return f"{CATEGORIES_CACHE_KEY_PREFIX}:{language}"

    async def get_cached_categories(self, language: str = "es") -> Optional[Dict[str, Any]]:
        """
        Get cached category directory for specific language

        Args:
            language: Language code (es, fr, en)

        Returns:
            Category directory dict if cached, None otherwise
        """
        if not self.redis:
            return None

        try:
            cache_key = self._get_categories_cache_key(language)
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                logger.debug(f"✅ Category directory ({language}) served from cache")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Redis get failed (graceful fallback): {e}")

        return None

    async def cache_categories(self, categories_data: Dict[str, Any], language: str = "es") -> bool:
        """
        Cache category directory for specific language

        Args:
            categories_data: Category directory data to cache
            language: Language code (es, fr, en)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.redis:
            return False

        try:
            cache_key = self._get_categories_cache_key(language)
            await self.redis.setex(
                cache_key,
                CATEGORIES_TTL,
                json.dumps(categories_data)
            )
            logger.debug(f"✅ Category directory ({language}) cached for {CATEGORIES_TTL}s")
            return True
        except Exception as e:
            logger.warning(f"Redis setex failed (non-critical): {e}")
            return False

    # ========================================================================
    # CACHE INVALIDATION
    # ========================================================================

    async def invalidate_stats_cache(self) -> bool:
        """
        Invalidate homepage stats cache

        Call this when:
        - A fiscal service is created/updated/deleted
        - A ministry/category/sector is created/deleted
        - Any change that affects counts

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self.redis:
            return False

        try:
            deleted = await self.redis.delete(STATS_CACHE_KEY)
            if deleted:
                logger.info("🔄 Homepage stats cache invalidated")
            return deleted > 0
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return False

    async def invalidate_categories_cache(self, language: Optional[str] = None) -> bool:
        """
        Invalidate category directory cache

        Args:
            language: Specific language to invalidate, or None for all languages

        Call this when:
        - A fiscal service is created/deleted (changes service_count)
        - A category is created/updated/deleted
        - Translations are updated

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self.redis:
            return False

        try:
            if language:
                # Invalidate specific language
                cache_key = self._get_categories_cache_key(language)
                deleted = await self.redis.delete(cache_key)
                if deleted:
                    logger.info(f"🔄 Category cache ({language}) invalidated")
                return deleted > 0
            else:
                # Invalidate all languages
                pattern = f"{CATEGORIES_CACHE_KEY_PREFIX}:*"
                keys = await self.redis.keys(pattern)
                if keys:
                    deleted = await self.redis.delete(*keys)
                    logger.info(f"🔄 Category cache invalidated ({deleted} languages)")
                    return deleted > 0
                return False
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return False

    async def invalidate_all_homepage_cache(self) -> bool:
        """
        Invalidate ALL homepage cache (stats + categories for all languages)

        Use this for major changes that affect everything

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self.redis:
            return False

        try:
            # Get all homepage cache keys
            pattern = "homepage:*:v2*"
            keys = await self.redis.keys(pattern)

            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"🔄 All homepage cache invalidated ({deleted} keys)")
                return deleted > 0
            return False
        except Exception as e:
            logger.warning(f"Full cache invalidation failed: {e}")
            return False
