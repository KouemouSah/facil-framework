"""
Service layer for the dashboard_registrations admin API
(E1 phase 2 + Grafana E1 + mig 323 dynamic metadata).

Centralises:
- Cache strategy (Redis 5 min TTL, single key, invalidated on write)
- Backwards-compat env-var fallback (when the BD row is missing)
- Audit log emission for every write (in the same transaction as the upsert)
- Provider switch: Looker Studio vs Grafana iframe URL build
- Mig 323: BD-driven metadata (no in-code registry). Admin can create/delete
  dashboards via POST/DELETE without code changes.

Memory rule #24: asyncpg expects a string for JSONB columns, not a dict —
hence `json.dumps(...)` before INSERTs into audit_logs.
Memory rule #14: cache invalidation goes through delete(), not TTL=0.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import asyncpg
from fastapi import Request
from loguru import logger

from app.core.cache import get_cache
from app.modules.dashboards.models import (
    DashboardConfigDTO,
    DashboardConfigCreateRequest,
    DashboardConfigUpdateRequest,
    DashboardMetadataPatchRequest,
    DashboardReportEntry,
    GrafanaDiscoverEntry,
    GrafanaDiscoverResponse,
    GrafanaImportRequest,
    GrafanaImportResponse,
)
from app.modules.dashboards.repositories import DashboardConfigRepository
from app.modules.dashboards.services.dashboards_service import DashboardNotFoundError
from app.modules.dashboards.services.grafana_api_client import GrafanaApiClient


class DashboardAlreadyExists(Exception):
    """Raised when POST /admin/configs hits a dashboard_id collision."""


# Grafana embed base URL — comes from env var so staging/prod can point at
# different Grafana workspaces without a code change.
def _grafana_base_url() -> Optional[str]:
    return os.environ.get("GRAFANA_BASE_URL") or None


def _build_grafana_embed_url(
    *,
    uid: str,
    org_id: int,
    slug: Optional[str] = None,
    from_range: str = "now-90d",
    to_range: str = "now",
    theme: str = "light",
    kiosk: bool = True,
    embed_mode: str = "kiosk",
    panel_id: Optional[int] = None,
) -> Optional[str]:
    """Build a Grafana embed URL.

    Modes:
      - kiosk: /d/<uid>/<slug>?...&kiosk=tv  (full dashboard, no chrome)
      - solo:  /d-solo/<uid>/<slug>?...&panelId=<id>  (single panel)
      - panel: /d-solo/<uid>/<slug>?...&panelId=<id>  (alias of solo)

    Returns None if GRAFANA_BASE_URL is unset.
    """
    base = _grafana_base_url()
    if not base:
        return None
    base = base.rstrip("/")
    safe_uid = quote(uid, safe="-_")
    safe_slug = quote(slug or uid, safe="-_")

    parts = [
        f"orgId={org_id}",
        f"theme={theme}",
        f"from={from_range}",
        f"to={to_range}",
    ]

    if embed_mode in ("solo", "panel") and panel_id is not None:
        parts.append(f"panelId={panel_id}")
        path = f"/d-solo/{safe_uid}/{safe_slug}"
    else:
        if kiosk:
            parts.append("kiosk=tv")
        # Full dashboard kiosk uses /d/ (not /d-solo/) so the user sees all panels.
        path = f"/d/{safe_uid}/{safe_slug}"

    qs = "&".join(parts)
    return f"{base}{path}?{qs}"


def _build_looker_embed_url(
    *, report_id: str, page_id: Optional[str] = None
) -> str:
    base = "https://lookerstudio.google.com/embed/reporting"
    if page_id:
        return f"{base}/{report_id}/page/{page_id}"
    return f"{base}/{report_id}"


def _row_to_audit_dict(row: Optional[asyncpg.Record]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif v is None:
            out[k] = None
        else:
            out[k] = str(v) if not isinstance(v, (str, int, float, bool)) else v
    return out


def _env_fallback(dashboard_id: str) -> tuple[Optional[str], Optional[str]]:
    env_prefix = f"LOOKER_REPORTS_{dashboard_id.upper()}"
    report_id = os.environ.get(f"{env_prefix}_REPORT_ID") or None
    page_id = os.environ.get(f"{env_prefix}_PAGE_ID") or None
    return report_id, page_id


def _row_to_dto(row: asyncpg.Record, *, embed_url: Optional[str]) -> DashboardConfigDTO:
    """Map an asyncpg row + computed embed_url → DashboardConfigDTO.

    Mig 323 — backwards-compat: `label` mirrors title_es, `description` mirrors
    description_es so the existing frontend keeps rendering even before it
    migrates to the new i18n triplet fields.
    """
    return DashboardConfigDTO(
        dashboard_id=row["dashboard_id"],
        label=row["title_es"] or row["dashboard_id"],
        description=row["description_es"] or "",
        title_es=row["title_es"] or "",
        title_fr=row["title_fr"] or "",
        title_en=row["title_en"] or "",
        description_es=row["description_es"],
        description_fr=row["description_fr"],
        description_en=row["description_en"],
        rls_mode=row["rls_mode"],
        embed_mode=row["embed_mode"] or "kiosk",
        panel_id=row["panel_id"],
        display_order=row["display_order"] or 0,
        default_time_range=row["default_time_range"] or "now-90d",
        icon_name=row["icon_name"],
        category=row["category"],
        provider=row["provider"],
        looker_report_id=row["looker_report_id"],
        looker_page_id=row["looker_page_id"],
        grafana_dashboard_uid=row["grafana_dashboard_uid"],
        grafana_org_id=row["grafana_org_id"] or 1,
        is_active=row["is_active"],
        source="db",
        embed_url=embed_url,
        updated_by=str(row["updated_by"]) if row["updated_by"] else None,
        updated_at=row["updated_at"],
        created_at=row["created_at"],
    )


def _row_to_report_entry(row: asyncpg.Record, *, embed_url: Optional[str]) -> DashboardReportEntry:
    """Map a BD row → DashboardReportEntry (public listing payload)."""
    return DashboardReportEntry(
        dashboard_id=row["dashboard_id"],
        label=row["title_es"] or row["dashboard_id"],
        description=row["description_es"] or "",
        rls_mode=row["rls_mode"],
        title_es=row["title_es"] or "",
        title_fr=row["title_fr"] or "",
        title_en=row["title_en"] or "",
        description_es=row["description_es"],
        description_fr=row["description_fr"],
        description_en=row["description_en"],
        category=row["category"],
        display_order=row["display_order"] or 0,
        icon_name=row["icon_name"],
        embed_mode=row["embed_mode"] or "kiosk",
        panel_id=row["panel_id"],
        default_time_range=row["default_time_range"] or "now-90d",
        provider=row["provider"],
        looker_report_id=row["looker_report_id"],
        looker_page_id=row["looker_page_id"],
        grafana_dashboard_uid=row["grafana_dashboard_uid"],
        grafana_org_id=row["grafana_org_id"] or 1,
        embed_url=embed_url,
    )


# Roles allowed to see admin_only dashboards on /reports-config.
# Anything else gets the row filtered out (defense-in-depth on top of
# `dashboards.view_business` permission gate).
_ADMIN_RLS_ROLES = {"admin", "super_admin"}


class DashboardConfigService:
    """Coordinates BD reads/writes + Redis cache + audit log + provider switch.

    Mig 323: registry parameter is no longer required (kept Optional for
    transitional callers). All metadata is read from BD.
    """

    CACHE_KEY = "dashboard_configs:reports_v3"   # v3 = BD-driven metadata
    CACHE_TTL_SECONDS = 300

    def __init__(self, pool: asyncpg.Pool, registry: Optional[dict] = None):
        # `registry` kept for backwards-compat callers; ignored in mig 323.
        self._pool = pool
        # Stash for any leftover env-var fallback path (rare).
        self._registry = registry or {}

    # -- Public API --------------------------------------------------------

    async def get_public_reports_config(
        self, *, user_role: Optional[str] = None
    ) -> list[DashboardReportEntry]:
        """Power GET /reports-config — DB-only, RLS-filtered, with embed URLs.

        Cache strategy: 2 keys total, one per RLS variant
        (admin sees admin_only rows, everyone else doesn't).
        """
        is_admin = user_role in _ADMIN_RLS_ROLES
        variant = "admin" if is_admin else "public"
        cache_key = f"{self.CACHE_KEY}:{variant}"

        cache = get_cache()
        cached = await cache.get(cache_key)
        if cached is not None:
            try:
                return [DashboardReportEntry(**r) for r in cached]
            except Exception as exc:
                logger.warning(
                    "dashboard_config: stale cache shape, refilling — err={}", exc
                )

        # rls_mode whitelist: hide admin_only rows from non-admin callers.
        rls_modes = None if is_admin else [
            "public", "authenticated", "entity", "agent_via_join"
        ]

        async with self._pool.acquire() as conn:
            rows = await DashboardConfigRepository.list_active(conn, rls_modes=rls_modes)

        entries = [
            _row_to_report_entry(row, embed_url=self._compute_embed_url(row))
            for row in rows
        ]

        try:
            await cache.set(
                cache_key,
                [e.model_dump(mode="json") for e in entries],
                ttl=self.CACHE_TTL_SECONDS,
            )
        except Exception as cache_exc:
            logger.warning(
                "dashboard_config: cache write failed key={} err={}",
                cache_key, cache_exc,
            )
        return entries

    async def list_admin_configs(self) -> list[DashboardConfigDTO]:
        """Power GET /admin/configs — BD rows + computed embed URL."""
        async with self._pool.acquire() as conn:
            rows = await DashboardConfigRepository.list_all(conn)
        return [_row_to_dto(r, embed_url=self._compute_embed_url(r)) for r in rows]

    async def create_config(
        self,
        body: DashboardConfigCreateRequest,
        *,
        user_id: str,
        request: Optional[Request] = None,
    ) -> DashboardConfigDTO:
        """POST /admin/configs — create a new dashboard (mig 323)."""
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                try:
                    new_row = await DashboardConfigRepository.create(
                        conn,
                        dashboard_id=body.dashboard_id,
                        provider=body.provider,
                        looker_report_id=body.looker_report_id,
                        looker_page_id=body.looker_page_id,
                        grafana_dashboard_uid=body.grafana_dashboard_uid,
                        grafana_org_id=body.grafana_org_id,
                        is_active=body.is_active,
                        title_es=body.title_es,
                        title_fr=body.title_fr,
                        title_en=body.title_en,
                        description_es=body.description_es,
                        description_fr=body.description_fr,
                        description_en=body.description_en,
                        rls_mode=body.rls_mode,
                        embed_mode=body.embed_mode,
                        panel_id=body.panel_id,
                        display_order=body.display_order,
                        default_time_range=body.default_time_range,
                        icon_name=body.icon_name,
                        category=body.category,
                        updated_by=user_id,
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise DashboardAlreadyExists(
                        f"dashboard_id '{body.dashboard_id}' already exists"
                    ) from exc

                await self._audit(
                    conn, user_id=user_id, dashboard_id=body.dashboard_id,
                    action="dashboard.config_create",
                    old=None, new=_row_to_audit_dict(new_row),
                    ip=ip, ua=ua,
                )

        await self._invalidate_caches()
        return _row_to_dto(new_row, embed_url=self._compute_embed_url(new_row))

    async def upsert_config(
        self,
        dashboard_id: str,
        update: DashboardConfigUpdateRequest,
        *,
        user_id: str,
        request: Optional[Request] = None,
    ) -> DashboardConfigDTO:
        """PUT /admin/configs/{id} — update provider/UID/active.

        Mig 323: no longer rejects unknown dashboard_ids based on a hardcoded
        registry. The BD row must exist; if not, returns 404.
        """
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                old_row = await DashboardConfigRepository.get_by_id(conn, dashboard_id)
                if old_row is None:
                    raise DashboardNotFoundError(
                        f"Dashboard '{dashboard_id}' not found in dashboard_registrations. "
                        f"Use POST /admin/configs to create a new one."
                    )
                new_row = await DashboardConfigRepository.upsert(
                    conn,
                    dashboard_id=dashboard_id,
                    provider=update.provider,
                    looker_report_id=update.looker_report_id,
                    looker_page_id=update.looker_page_id,
                    grafana_dashboard_uid=update.grafana_dashboard_uid,
                    grafana_org_id=update.grafana_org_id,
                    is_active=update.is_active,
                    updated_by=user_id,
                )
                await self._audit(
                    conn, user_id=user_id, dashboard_id=dashboard_id,
                    action="dashboard.config_update",
                    old=_row_to_audit_dict(old_row),
                    new=_row_to_audit_dict(new_row),
                    ip=ip, ua=ua,
                )

        await self._invalidate_caches()
        return _row_to_dto(new_row, embed_url=self._compute_embed_url(new_row))

    async def patch_metadata(
        self,
        dashboard_id: str,
        patch: DashboardMetadataPatchRequest,
        *,
        user_id: str,
        request: Optional[Request] = None,
    ) -> DashboardConfigDTO:
        """PATCH /admin/configs/{id}/metadata — i18n + presentation update."""
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                old_row = await DashboardConfigRepository.get_by_id(conn, dashboard_id)
                if old_row is None:
                    raise DashboardNotFoundError(
                        f"Dashboard '{dashboard_id}' not found."
                    )
                new_row = await DashboardConfigRepository.update_metadata(
                    conn,
                    dashboard_id=dashboard_id,
                    title_es=patch.title_es,
                    title_fr=patch.title_fr,
                    title_en=patch.title_en,
                    description_es=patch.description_es,
                    description_fr=patch.description_fr,
                    description_en=patch.description_en,
                    rls_mode=patch.rls_mode,
                    embed_mode=patch.embed_mode,
                    panel_id=patch.panel_id,
                    display_order=patch.display_order,
                    default_time_range=patch.default_time_range,
                    icon_name=patch.icon_name,
                    category=patch.category,
                    updated_by=user_id,
                )
                if new_row is None:
                    raise DashboardNotFoundError(
                        f"Dashboard '{dashboard_id}' not found after patch."
                    )
                await self._audit(
                    conn, user_id=user_id, dashboard_id=dashboard_id,
                    action="dashboard.metadata_patch",
                    old=_row_to_audit_dict(old_row),
                    new=_row_to_audit_dict(new_row),
                    ip=ip, ua=ua,
                )

        await self._invalidate_caches()
        return _row_to_dto(new_row, embed_url=self._compute_embed_url(new_row))

    async def soft_delete_config(
        self,
        dashboard_id: str,
        *,
        user_id: str,
        request: Optional[Request] = None,
    ) -> DashboardConfigDTO:
        """DELETE /admin/configs/{id} — soft-delete (is_active=false)."""
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                old_row = await DashboardConfigRepository.get_by_id(conn, dashboard_id)
                if old_row is None:
                    raise DashboardNotFoundError(
                        f"Dashboard '{dashboard_id}' not found."
                    )
                new_row = await DashboardConfigRepository.soft_delete(
                    conn, dashboard_id=dashboard_id, updated_by=user_id,
                )
                if new_row is None:
                    raise DashboardNotFoundError(
                        f"Dashboard '{dashboard_id}' not found after soft-delete."
                    )
                await self._audit(
                    conn, user_id=user_id, dashboard_id=dashboard_id,
                    action="dashboard.config_delete",
                    old=_row_to_audit_dict(old_row),
                    new=_row_to_audit_dict(new_row),
                    ip=ip, ua=ua,
                )

        await self._invalidate_caches()
        return _row_to_dto(new_row, embed_url=self._compute_embed_url(new_row))

    async def discover_grafana(self) -> GrafanaDiscoverResponse:
        """GET /admin/grafana/discover — list dashboards in the Grafana
        workspace, marking those already imported.
        """
        if not GrafanaApiClient.is_configured():
            return GrafanaDiscoverResponse(
                grafana_base_url=GrafanaApiClient.base_url(),
                sa_token_configured=False,
                error="Grafana not configured (set GRAFANA_BASE_URL and GRAFANA_SA_TOKEN).",
            )

        dashboards, error = await GrafanaApiClient.list_dashboards()
        if error:
            return GrafanaDiscoverResponse(
                grafana_base_url=GrafanaApiClient.base_url(),
                sa_token_configured=True,
                error=error,
            )

        async with self._pool.acquire() as conn:
            already = set(await DashboardConfigRepository.list_grafana_uids(conn))

        entries = [
            GrafanaDiscoverEntry(
                uid=d["uid"],
                title=d["title"],
                slug=d.get("slug"),
                folder_title=d.get("folderTitle"),
                tags=d.get("tags", []),
                already_imported=d["uid"] in already,
            )
            for d in dashboards
            if d.get("uid")
        ]
        # Sort: not-yet-imported first, then alphabetically by title.
        entries.sort(key=lambda e: (e.already_imported, e.title.lower()))

        return GrafanaDiscoverResponse(
            grafana_base_url=GrafanaApiClient.base_url(),
            sa_token_configured=True,
            dashboards=entries,
        )

    async def import_grafana(
        self,
        body: GrafanaImportRequest,
        *,
        user_id: str,
        request: Optional[Request] = None,
    ) -> GrafanaImportResponse:
        """POST /admin/grafana/import — bulk-create rows in BD.

        Per-item failures are isolated: one bad item does NOT roll back
        the others. Each item gets its own savepoint so partial success
        is the normal case.
        """
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None

        result = GrafanaImportResponse()

        async with self._pool.acquire() as conn:
            for item in body.items:
                try:
                    async with conn.transaction():
                        new_row = await DashboardConfigRepository.create(
                            conn,
                            dashboard_id=item.dashboard_id,
                            provider="grafana",
                            looker_report_id=None,
                            looker_page_id=None,
                            grafana_dashboard_uid=item.uid,
                            grafana_org_id=item.grafana_org_id,
                            is_active=True,
                            title_es=item.title_es,
                            title_fr=item.title_fr,
                            title_en=item.title_en,
                            description_es=item.description_es,
                            description_fr=item.description_fr,
                            description_en=item.description_en,
                            rls_mode=item.rls_mode,
                            embed_mode="kiosk",
                            panel_id=None,
                            display_order=item.display_order,
                            default_time_range="now-90d",
                            icon_name=item.icon_name,
                            category=item.category,
                            updated_by=user_id,
                        )
                        await self._audit(
                            conn, user_id=user_id, dashboard_id=item.dashboard_id,
                            action="dashboard.grafana_import",
                            old=None, new=_row_to_audit_dict(new_row),
                            ip=ip, ua=ua,
                        )
                    result.imported.append(item.dashboard_id)
                except asyncpg.UniqueViolationError:
                    result.skipped.append({
                        "dashboard_id": item.dashboard_id,
                        "reason": "already_exists",
                    })
                except Exception as exc:
                    logger.warning(
                        "grafana_import: failed item={} uid={} err={}",
                        item.dashboard_id, item.uid, exc,
                    )
                    result.errors.append({
                        "dashboard_id": item.dashboard_id,
                        "error": str(exc)[:200],
                    })

        if result.imported:
            await self._invalidate_caches()
            await GrafanaApiClient.invalidate_cache()

        return result

    # -- Internals ---------------------------------------------------------

    def _compute_embed_url(self, row: asyncpg.Record) -> Optional[str]:
        provider = row["provider"]
        if provider == "grafana":
            uid = row["grafana_dashboard_uid"]
            if not uid:
                return None
            return _build_grafana_embed_url(
                uid=uid,
                org_id=row["grafana_org_id"] or 1,
                slug=row["dashboard_id"],
                from_range=row["default_time_range"] or "now-90d",
                embed_mode=row["embed_mode"] or "kiosk",
                panel_id=row["panel_id"],
            )
        # Default = looker_studio
        report_id = row["looker_report_id"]
        if not report_id:
            # Last resort: try env fallback (legacy code path).
            report_id, page_id = _env_fallback(row["dashboard_id"])
            if not report_id:
                return None
            return _build_looker_embed_url(report_id=report_id, page_id=page_id)
        return _build_looker_embed_url(
            report_id=report_id, page_id=row["looker_page_id"],
        )

    async def _audit(
        self, conn: asyncpg.Connection, *, user_id: str, dashboard_id: str,
        action: str, old: Optional[dict], new: Optional[dict],
        ip: Optional[str], ua: Optional[str],
    ) -> None:
        await conn.execute(
            """
            INSERT INTO audit_logs (
                user_id, entity_type, entity_id, action,
                old_values, new_values, ip_address, user_agent,
                created_at
            )
            VALUES (
                $1::uuid, 'dashboard_config', $2,
                $3,
                $4::jsonb, $5::jsonb, $6, $7, NOW()
            )
            """,
            user_id, dashboard_id, action,
            json.dumps(old) if old is not None else None,
            json.dumps(new) if new is not None else None,
            ip, ua,
        )

    async def _invalidate_caches(self) -> None:
        """Drop both RLS variants of the public cache key."""
        cache = get_cache()
        for variant in ("admin", "public"):
            try:
                await cache.delete(f"{self.CACHE_KEY}:{variant}")
            except Exception as exc:
                logger.warning(
                    "dashboard_config: cache invalidate failed key={}:{} err={}",
                    self.CACHE_KEY, variant, exc,
                )
        # Also drop legacy keys (v1, v2) just in case.
        for legacy in ("dashboard_configs:reports_v1", "dashboard_configs:reports_v2"):
            try:
                await cache.delete(legacy)
            except Exception:
                pass
