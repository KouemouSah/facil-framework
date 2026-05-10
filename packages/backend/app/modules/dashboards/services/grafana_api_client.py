"""
Thin client for the Grafana HTTP API.

Used by the /admin/grafana/discover endpoint to list dashboards available in
the configured Grafana workspace so the admin can pick which ones to import
into dashboard_registrations without manually copying UIDs from URLs.

Configuration via env:
- GRAFANA_BASE_URL  (e.g. https://kouemousah.grafana.net)
- GRAFANA_SA_TOKEN  (Grafana service account token, scope: dashboards:read)

If either is unset, the discover endpoint returns an empty list with
sa_token_configured=false so the frontend can render a clear hint.

Cache: results are cached server-side for 5 min via the Redis layer to avoid
hammering the Grafana API on every modal open.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from loguru import logger

from app.core.cache import get_cache


CACHE_KEY = "dashboards:grafana_discover_v1"
CACHE_TTL_SECONDS = 300


def _grafana_base_url() -> Optional[str]:
    return (os.environ.get("GRAFANA_BASE_URL") or "").rstrip("/") or None


def _grafana_sa_token() -> Optional[str]:
    return os.environ.get("GRAFANA_SA_TOKEN") or None


class GrafanaApiClient:
    """Stateless wrapper around Grafana /api/search.

    Errors (network, 4xx/5xx) are caught and converted to a structured
    response so the admin UI can surface a friendly message instead of a 500.
    """

    @staticmethod
    def is_configured() -> bool:
        return bool(_grafana_base_url() and _grafana_sa_token())

    @staticmethod
    def base_url() -> Optional[str]:
        return _grafana_base_url()

    @classmethod
    async def list_dashboards(
        cls, *, use_cache: bool = True
    ) -> tuple[list[dict], Optional[str]]:
        """Return (dashboards, error_message_or_None).

        Each dashboard is a dict: {uid, title, slug, folderTitle, tags}.
        On error, returns ([], error_message).
        """
        base = _grafana_base_url()
        token = _grafana_sa_token()
        if not base or not token:
            return [], "GRAFANA_BASE_URL or GRAFANA_SA_TOKEN not configured"

        if use_cache:
            cache = get_cache()
            cached = await cache.get(CACHE_KEY)
            if cached is not None:
                return cached, None

        url = f"{base}/api/search"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        params = {"type": "dash-db", "limit": "1000"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers, params=params)
        except httpx.RequestError as exc:
            logger.warning("grafana_api: network error during list — {}", exc)
            return [], f"Grafana API unreachable: {exc.__class__.__name__}"

        if resp.status_code == 401:
            return [], "GRAFANA_SA_TOKEN rejected (401) — rotate the token"
        if resp.status_code == 403:
            return [], "GRAFANA_SA_TOKEN lacks dashboards:read scope (403)"
        if resp.status_code >= 400:
            return [], f"Grafana API returned {resp.status_code}"

        try:
            payload = resp.json()
        except ValueError:
            return [], "Grafana API returned non-JSON body"

        dashboards = []
        for item in payload:
            if not isinstance(item, dict) or item.get("type") != "dash-db":
                continue
            dashboards.append({
                "uid": item.get("uid", ""),
                "title": item.get("title", ""),
                "slug": item.get("slug"),
                "folderTitle": item.get("folderTitle"),
                "tags": item.get("tags", []) or [],
            })

        if use_cache:
            try:
                await get_cache().set(CACHE_KEY, dashboards, ttl=CACHE_TTL_SECONDS)
            except Exception as cache_exc:
                logger.warning(
                    "grafana_api: cache write failed key={} err={}",
                    CACHE_KEY, cache_exc,
                )

        return dashboards, None

    @classmethod
    async def invalidate_cache(cls) -> None:
        try:
            await get_cache().delete(CACHE_KEY)
        except Exception as cache_exc:
            logger.warning("grafana_api: cache invalidate failed: {}", cache_exc)
