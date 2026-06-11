"""
Dashboards API routes — Looker Studio Community Connector backend.

Phase B.1 skeleton:
- Auth: standard Bearer JWT (the connector posts JWT in X-Facil-Api-Key header,
  we accept it as Bearer token transparently). B.2 will switch to OAUTH2.
- Endpoints:
    GET /api/v1/dashboards/_ping              — connector health check
    GET /api/v1/dashboards/{id}/schema        — Looker schema for dashboard
    GET /api/v1/dashboards/{id}/data          — Looker data rows for dashboard

NO RLS in this phase. B.2 will add `WHERE ministry_id = user.ministry_id`
when the JWT subject is not admin / treasury_supervisor.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger

import json
import time

from app.core.cache import check_rate_limit, get_cache
from app.database.connection import get_db_pool
from app.modules.auth.dependencies import get_current_user

# Sentry — soft import so the module loads even when sentry-sdk is not
# installed (e.g. test environments). All set_tag/set_user calls become
# no-ops.
try:
    import sentry_sdk
    _SENTRY_AVAILABLE = True
except Exception:
    sentry_sdk = None  # type: ignore[assignment]
    _SENTRY_AVAILABLE = False
from app.modules.dashboards.models import (
    DashboardConfigCreateRequest,
    DashboardConfigDTO,
    DashboardConfigUpdateRequest,
    DashboardConfigsListResponse,
    DashboardDataResponse,
    DashboardMetadataPatchRequest,
    DashboardPingResponse,
    DashboardReportEntry,
    DashboardReportsConfigResponse,
    DashboardSchemaResponse,
    GrafanaDiscoverResponse,
    GrafanaImportRequest,
    GrafanaImportResponse,
)
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.dashboards.services import (
    DashboardAccessDenied,
    DashboardAlreadyExists,
    DashboardConfigService,
    DashboardNotFoundError,
    DashboardsService,
    resolve_user_access,
)

router = APIRouter()

# Server-side TTL for /dashboards/{id}/data responses. Combined with the
# 5-min user-scoped cache in the Apps Script connector (Q5 default), this
# bounds backend load to ~1 query per user per dashboard per minute even
# under aggressive Looker refresh. Cache key includes user_id so two
# distinct ministry agents do NOT share entries.
_DATA_CACHE_TTL_SECONDS = 60

# Rate limit: 60 read requests per minute per user across all dashboard
# endpoints. With the 5-min connector-side cache + 60s server-side cache,
# real traffic should never approach this — but we cap so a misbehaving
# script can't drown the backend. 429 surfaced to the connector with a
# Retry-After header.
_RATE_LIMIT_REQUESTS = 60
_RATE_LIMIT_WINDOW_SECONDS = 60


def _set_sentry_context(user, dashboard_id: Optional[str], access_label: Optional[str]):
    """Tag every Sentry event raised inside a dashboard request with
    enough context to debug RLS / dashboard issues without grepping logs.
    No-op when sentry-sdk is not installed.
    """
    if not _SENTRY_AVAILABLE:
        return
    try:
        sentry_sdk.set_user({
            "id": str(getattr(user, "id", "unknown")),
            "role": getattr(user, "role", None) or "unknown",
        })
        if dashboard_id:
            sentry_sdk.set_tag("dashboard_id", dashboard_id)
        if access_label:
            sentry_sdk.set_tag("dashboard_access", access_label)
    except Exception:
        # Sentry init can be partial in CI / forks — never let a tag call
        # crash the request.
        pass


async def _record_audit(
    pool,
    *,
    user_id: str,
    dashboard_id: str,
    access_describe: str,
    row_count: int,
    filters_applied: list,
    request: Request,
    latency_ms: int,
) -> None:
    """Insert one row into audit_logs for traceability. Best-effort —
    a failure here is logged but does NOT break the response.
    """
    payload = {
        "row_count": row_count,
        "filters_applied": filters_applied,
        "access": access_describe,
        "latency_ms": latency_ms,
    }
    ip = request.client.host if request and request.client else None
    ua = request.headers.get("user-agent") if request else None
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs (
                    user_id, entity_type, entity_id, action,
                    old_values, new_values, ip_address, user_agent,
                    created_at
                )
                VALUES ($1, 'dashboard', $2, 'dashboard.read',
                        NULL, $3::jsonb, $4, $5, NOW())
                """,
                user_id,
                dashboard_id,
                json.dumps(payload),     # asyncpg expects str for JSONB (Memory rule #24)
                ip,
                ua,
            )
    except Exception as exc:
        logger.warning(
            "dashboards.audit_log write failed user={} dashboard={} err={}",
            user_id, dashboard_id, exc,
        )


# ---------------------------------------------------------------------------
# Routes
#
# Auth: standard Bearer JWT via app.modules.auth.dependencies.get_current_user.
# The Apps Script connector posts the JWT as the Bearer token (its USER_PASS
# `password` field is filled with the JWT). B.2 will switch the connector
# to OAUTH2, the backend dependency stays the same.
# ---------------------------------------------------------------------------


# Mig 323 (2026-05-05): the `_REPORTS_METADATA` in-code dict was removed.
# All metadata (label/description/rls_mode/category/etc.) now lives in the
# `dashboard_registrations` BD table. Admins create/edit/delete dashboards
# via POST/PATCH/DELETE — no redeploy needed.

_RATE_LIMIT_WRITE_REQ = 10  # POST/PUT/PATCH/DELETE per minute per user


async def _enforce_write_rate_limit(user_id: str, endpoint: str) -> None:
    is_allowed, _remaining = await check_rate_limit(
        identifier=user_id, endpoint=endpoint,
        max_requests=_RATE_LIMIT_WRITE_REQ, window_seconds=60,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {_RATE_LIMIT_WRITE_REQ} write requests / 60s.",
            headers={"Retry-After": "60"},
        )


@router.get(
    "/reports-config",
    response_model=DashboardReportsConfigResponse,
    summary="List of embeddable dashboards the caller is authorised to see",
)
async def get_reports_config(
    user=Depends(get_current_user),
    _perm: None = Depends(permission_required("dashboards.view_business")),
):
    """Power the Next.js /admin/dashboards landing page.

    The route gates on the `dashboards.view_business` permission seeded
    by migration 316. Anyone without it gets 403 from the dependency
    BEFORE we touch the BD.

    Mig 323 — fully BD-driven. Each row's metadata (i18n title/description,
    category, embed mode, panel id, default time range) comes from
    dashboard_registrations. Non-admin callers don't see admin_only rows.

    Hot path: cached server-side 5 min via DashboardConfigService.
    """
    pool = await get_db_pool()
    svc = DashboardConfigService(pool)
    entries = await svc.get_public_reports_config(
        user_role=getattr(user, "role", None),
    )
    return DashboardReportsConfigResponse(reports=entries)


@router.get(
    "/admin/configs",
    response_model=DashboardConfigsListResponse,
    summary="Admin-only list of dashboard configs (BD row + computed embed)",
)
async def list_admin_dashboard_configs(
    user=Depends(get_current_user),
    _perm: None = Depends(permission_required("dashboards.manage")),
):
    """Power the admin /admin/dashboards/config page.

    Returns one entry per dashboard_registrations row, including
    inactive rows. `source` is always "db" since mig 323.
    """
    pool = await get_db_pool()
    svc = DashboardConfigService(pool)
    configs = await svc.list_admin_configs()
    return DashboardConfigsListResponse(configs=configs)


@router.post(
    "/admin/configs",
    response_model=DashboardConfigDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Admin-only create a new dashboard (mig 323)",
)
async def create_admin_dashboard_config(
    request: Request,
    body: DashboardConfigCreateRequest,
    user=Depends(get_current_user),
    _perm: None = Depends(permission_required("dashboards.manage")),
):
    """Create a new dashboard row from scratch — replaces the old in-code
    registry. Validates regex on dashboard_id, provider fields, and
    metadata at the Pydantic layer (422) before any BD round-trip.

    409 returned if dashboard_id already exists.
    """
    user_id = str(getattr(user, "id", ""))
    await _enforce_write_rate_limit(user_id, "/dashboards/admin/configs:POST")

    pool = await get_db_pool()
    svc = DashboardConfigService(pool)
    try:
        return await svc.create_config(body, user_id=user_id, request=request)
    except DashboardAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.put(
    "/admin/configs/{dashboard_id}",
    response_model=DashboardConfigDTO,
    summary="Admin-only update of one dashboard's provider/UID/active state",
)
async def upsert_admin_dashboard_config(
    request: Request,
    dashboard_id: str,
    update: DashboardConfigUpdateRequest,
    user=Depends(get_current_user),
    _perm: None = Depends(permission_required("dashboards.manage")),
):
    """Update provider/Looker IDs/Grafana UID/is_active. Mig 323: requires
    the row to exist already (use POST to create new). Metadata fields
    (title/description/category/etc.) are patched separately via PATCH.

    OWASP / 1M+ guards:
    - permission_required('dashboards.manage')      → admin/super_admin only
    - rate limit 10 PUT/min/user                     → vs 60 read/min
    - Pydantic regex on provider/UID fields          → 422 on invalid input
    - 404 when dashboard_id not in BD
    - audit_logs row emitted in the same transaction as the UPSERT
    """
    user_id = str(getattr(user, "id", ""))
    await _enforce_write_rate_limit(user_id, "/dashboards/admin/configs:PUT")

    pool = await get_db_pool()
    svc = DashboardConfigService(pool)
    try:
        return await svc.upsert_config(
            dashboard_id, update, user_id=user_id, request=request,
        )
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch(
    "/admin/configs/{dashboard_id}/metadata",
    response_model=DashboardConfigDTO,
    summary="Admin-only patch of i18n + presentation metadata (mig 323)",
)
async def patch_admin_dashboard_metadata(
    request: Request,
    dashboard_id: str,
    patch: DashboardMetadataPatchRequest,
    user=Depends(get_current_user),
    _perm: None = Depends(permission_required("dashboards.manage")),
):
    """Partial update of title_*, description_*, rls_mode, embed_mode, panel_id,
    display_order, default_time_range, icon_name, category. NULL fields
    are left unchanged.
    """
    user_id = str(getattr(user, "id", ""))
    await _enforce_write_rate_limit(user_id, "/dashboards/admin/configs:PATCH")

    pool = await get_db_pool()
    svc = DashboardConfigService(pool)
    try:
        return await svc.patch_metadata(
            dashboard_id, patch, user_id=user_id, request=request,
        )
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/admin/configs/{dashboard_id}",
    response_model=DashboardConfigDTO,
    summary="Admin-only soft-delete of a dashboard (sets is_active=false)",
)
async def soft_delete_admin_dashboard_config(
    request: Request,
    dashboard_id: str,
    user=Depends(get_current_user),
    _perm: None = Depends(permission_required("dashboards.manage")),
):
    """Soft-delete: keeps the row + audit trail; just hides it from
    /reports-config. Re-enable via PUT with is_active=true.
    """
    user_id = str(getattr(user, "id", ""))
    await _enforce_write_rate_limit(user_id, "/dashboards/admin/configs:DELETE")

    pool = await get_db_pool()
    svc = DashboardConfigService(pool)
    try:
        return await svc.soft_delete_config(
            dashboard_id, user_id=user_id, request=request,
        )
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/admin/grafana/discover",
    response_model=GrafanaDiscoverResponse,
    summary="List dashboards available in the Grafana workspace (mig 323)",
)
async def discover_grafana_dashboards(
    user=Depends(get_current_user),
    _perm: None = Depends(permission_required("dashboards.manage")),
):
    """Read-only call to Grafana /api/search. Tags each dashboard with
    `already_imported=true` when its UID is already in dashboard_registrations.

    Returns a structured payload with `error` populated when GRAFANA_BASE_URL /
    GRAFANA_SA_TOKEN are missing or the token is rejected — UI surfaces a
    friendly hint instead of a 500.
    """
    pool = await get_db_pool()
    svc = DashboardConfigService(pool)
    return await svc.discover_grafana()


@router.post(
    "/admin/grafana/import",
    response_model=GrafanaImportResponse,
    summary="Bulk import multiple Grafana dashboards into the registry (mig 323)",
)
async def import_grafana_dashboards(
    request: Request,
    body: GrafanaImportRequest,
    user=Depends(get_current_user),
    _perm: None = Depends(permission_required("dashboards.manage")),
):
    """Per-item transaction: one bad item does NOT roll back the others.
    Response splits results into imported / skipped (already_exists) / errors.
    """
    user_id = str(getattr(user, "id", ""))
    await _enforce_write_rate_limit(user_id, "/dashboards/admin/grafana:import")

    pool = await get_db_pool()
    svc = DashboardConfigService(pool)
    return await svc.import_grafana(body, user_id=user_id, request=request)


@router.get(
    "/_ping",
    response_model=DashboardPingResponse,
    summary="Connector health-check — returns the authenticated user identity",
)
async def ping(user=Depends(get_current_user)):
    pool = await get_db_pool()
    ctx = await resolve_user_access(
        pool,
        user_id=str(getattr(user, "id", "")),
        user_role=getattr(user, "role", None),
    )
    _set_sentry_context(user, None, ctx.describe())
    # If the user can read 0 ministries AND isn't staff → connector should
    # surface auth failure, not silent zero-row dashboards.
    if not ctx.has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your account is authenticated but has no agent profile with "
                "an active ministry assignment. Dashboard access is reserved "
                "to staff (admin) and ministry agents."
            ),
        )
    # Expose the first ministry id as a hint when present; otherwise None.
    # The connector mainly checks the response is 200; the precise scope
    # (entity vs ministry) lives in the audit log (loguru info on get_data).
    primary_ministry = ctx.ministry_ids[0] if ctx.ministry_ids else None
    return DashboardPingResponse(
        user_email=getattr(user, "email", "unknown"),
        user_id=ctx.user_id,
        role=ctx.user_role or None,
        ministry_id=primary_ministry,
    )


@router.get(
    "/{dashboard_id}/schema",
    response_model=DashboardSchemaResponse,
    summary="Looker Studio schema for the requested dashboard",
)
async def get_schema(
    dashboard_id: str,
    user=Depends(get_current_user),
):
    pool = await get_db_pool()
    svc = DashboardsService(pool)
    try:
        return svc.get_schema(dashboard_id)
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/{dashboard_id}/data",
    response_model=DashboardDataResponse,
    summary="Looker Studio data rows for the requested dashboard",
)
async def get_data(
    request: Request,
    dashboard_id: str,
    fields: Optional[str] = Query(
        None,
        description="CSV list of field names to return. Defaults to all schema fields.",
    ),
    start_date: Optional[date] = Query(None, description="Inclusive lower bound on the date column."),
    end_date: Optional[date] = Query(None, description="Inclusive upper bound on the date column."),
    user=Depends(get_current_user),
):
    started_at = time.monotonic()
    pool = await get_db_pool()
    user_id = str(getattr(user, "id", ""))

    # B.3 — rate limit BEFORE any DB call. 60 req/min/user/all-dashboards.
    is_allowed, _remaining = await check_rate_limit(
        identifier=user_id,
        endpoint="/dashboards/data",
        max_requests=_RATE_LIMIT_REQUESTS,
        window_seconds=_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {_RATE_LIMIT_REQUESTS} requests / {_RATE_LIMIT_WINDOW_SECONDS}s.",
            headers={"Retry-After": str(_RATE_LIMIT_WINDOW_SECONDS)},
        )

    # B.2a — resolve user → access context BEFORE touching the data MV. Two
    # benefits: (1) 403 on forbidden roles before any SQL load, (2) the WHERE
    # clause built downstream is always anchored to a verified entity list.
    access = await resolve_user_access(
        pool,
        user_id=user_id,
        user_role=getattr(user, "role", None),
    )
    _set_sentry_context(user, dashboard_id, access.describe())

    # Per-dashboard RLS modes (entity / agent_via_join / admin_only / public)
    # are enforced inside svc.get_data via DashboardsService._enforce_rls_gate.
    # We do NOT raise an early 403 here because some dashboards (rls_mode=
    # public) accept any authenticated user — checking has_access too early
    # would reject citizens from a legitimate public catalog read.

    svc = DashboardsService(pool)
    try:
        field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

        # B.2a — server-side cache (60s) keyed by user_id so RLS results never
        # leak across users. Connector also caches 5 min user-scoped (Code.gs).
        # Combined upper bound: 1 backend query / user / dashboard / minute.
        cache = get_cache()
        cache_key = "dashboards:{0}:{1}:{2}:{3}:{4}".format(
            access.user_id,
            dashboard_id,
            start_date.isoformat() if start_date else "_",
            end_date.isoformat() if end_date else "_",
            ",".join(field_list) if field_list else "*",
        )
        cached_payload = await cache.get(cache_key)
        if cached_payload is not None:
            logger.debug(
                "dashboards.get_data cache_hit dashboard={} user={}",
                dashboard_id, access.user_id,
            )
            return DashboardDataResponse.model_validate(cached_payload)

        result = await svc.get_data(
            dashboard_id,
            access=access,
            fields=field_list,
            start_date=start_date,
            end_date=end_date,
        )
        # Cache the dict form (model_dump with by_alias=True so the cached
        # payload reads back identically through model_validate on the next
        # hit). model_dump's exclude_none=False to keep deterministic shape.
        try:
            await cache.set(
                cache_key,
                result.model_dump(by_alias=True, mode="json"),
                ttl=_DATA_CACHE_TTL_SECONDS,
            )
        except Exception as cache_exc:
            logger.warning(
                "dashboards.get_data cache_write_failed key={} err={}",
                cache_key, cache_exc,
            )
        # B.3 — proper audit_logs row (queryable, JSONB metadata) replacing
        # the prior loguru.info breadcrumb. Best-effort: a write failure
        # logs a warning but never breaks the response.
        latency_ms = int((time.monotonic() - started_at) * 1000)
        await _record_audit(
            pool,
            user_id=user_id,
            dashboard_id=dashboard_id,
            access_describe=access.describe(),
            row_count=result.row_count,
            filters_applied=result.filters_applied,
            request=request,
            latency_ms=latency_ms,
        )
        logger.info(
            "dashboards.get_data ok dashboard={} user={} access={} rows={} latency={}ms",
            dashboard_id,
            getattr(user, "email", "unknown"),
            access.describe(),
            result.row_count,
            latency_ms,
        )
        return result
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DashboardAccessDenied as exc:
        # Should be caught by the early has_access check above, but if a
        # downstream guard re-raises (e.g. multi-ministry user lost access
        # mid-request), surface as 403 not 500.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
