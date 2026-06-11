"""
Homepage Module - Dynamic Statistics and Category Directory

Provides optimized endpoints for homepage data with intelligent caching

Architecture: 3-tier
- models/: Pydantic models for requests/responses
- services/: Business logic with cache orchestration
- repositories/: Optimized SQL queries (single query vs multiple)
- api/: FastAPI routes (thin layer)

Features:
- Optimized queries: 70-80% faster than legacy (1 query vs 4)
- Multilingual support: ES/FR/EN via entity_translations
- Redis caching: Intelligent TTL with auto-invalidation
- Graceful fallback: Works without Redis

Migrated from: app/api/v1/homepage.py
"""

from app.modules.homepage.api import homepage_router

__all__ = ["homepage_router"]
