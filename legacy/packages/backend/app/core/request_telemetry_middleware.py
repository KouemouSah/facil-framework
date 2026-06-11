"""
Request telemetry middleware (Phase C.2 / mig 329).

Pure ASGI middleware (NOT BaseHTTPMiddleware — too heavy, consumes the body).
Captures every HTTP request that enters facil-backend with:
- method, path, status_code, latency_ms, request/response bytes
- ip_address (X-Forwarded-For first hop, fallback request.client.host)
- user_agent / referer (truncated)
- trace_id (from active OTEL span — Phase A.4 + B)
- user_id / user_role (from request.scope state set by upstream auth)
- device_type / browser / os (Phase C.3 user_agents lib — TBD)
- geo_country / geo_city (Phase C.4 GeoLite2 — TBD)

Sampling decision tree (decision §1.D of plan):
1. Errors (status >= 400) → ALWAYS sample
2. New IP / new user_id in last 1h (Redis SET TTL 1h) → ALWAYS sample
3. Bots (is_bot=true) → 1% sample
4. Else (steady-state success) → 10% sample

Persistence is fire-and-forget (asyncio.create_task); the middleware itself
never blocks the response. Excluded paths (healthz, static, metrics) bypass
entirely so they cost ~200ns extra per request.

Design memory:
- #23: cron retention registered in app/core/scheduler.py
- #24: text[] passed directly (asyncpg native; not JSONB so no json.dumps)
- #40: GeoLite2 license key via Secret Manager
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Awaitable, Callable

from loguru import logger
from starlette.types import ASGIApp, Receive, Scope, Send


# Paths that should bypass telemetry entirely (Cloud Run health checks fire
# every second; static assets are noise; metrics endpoint is a self-poll).
_EXCLUDED_PREFIXES: tuple[str, ...] = (
    "/healthz", "/health", "/_ah/", "/metrics", "/static/",
    "/favicon.ico", "/docs", "/redoc", "/openapi.json",
)

# Sampling configuration
_SAMPLE_SUCCESS_PCT = float(os.environ.get("REQUEST_TELEMETRY_SAMPLE_SUCCESS_PCT", "10"))
_SAMPLE_BOT_PCT = float(os.environ.get("REQUEST_TELEMETRY_SAMPLE_BOT_PCT", "1"))

# Bounded raw fields
_MAX_PATH_LEN = 256
_MAX_UA_LEN = 512
_MAX_REFERER_LEN = 256

# Track recently seen IPs / users (in-memory LRU-like; for cross-worker
# accuracy we'd use Redis but per-worker is good enough for sampling).
_RECENT_IPS: dict[str, float] = {}
_RECENT_USERS: dict[str, float] = {}
_RECENT_TTL = 3600.0  # 1 hour
_RECENT_MAX = 10_000  # cap memory


def _is_excluded(path: str) -> bool:
    return any(path.startswith(p) for p in _EXCLUDED_PREFIXES)


def _get_client_ip(scope: Scope) -> str | None:
    """Extract client IP from headers (X-Forwarded-For) or scope.client."""
    headers = dict(scope.get("headers") or [])
    xff = headers.get(b"x-forwarded-for") or headers.get(b"X-Forwarded-For")
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2 — take first (real client)
        return xff.decode("ascii", errors="ignore").split(",")[0].strip() or None
    real_ip = headers.get(b"x-real-ip")
    if real_ip:
        return real_ip.decode("ascii", errors="ignore").strip() or None
    client = scope.get("client")
    if client and isinstance(client, (tuple, list)) and len(client) >= 1:
        return str(client[0])
    return None


def _truncate(s: str | None, n: int) -> str | None:
    if s is None:
        return None
    return s[:n] if len(s) > n else s


def _is_recent(d: dict[str, float], key: str, now: float) -> bool:
    """LRU-bounded recency check. Returns True if `key` was seen in TTL window.

    Side effects: updates `key` timestamp; evicts oldest if cap reached.
    """
    last = d.get(key)
    if last is not None and (now - last) < _RECENT_TTL:
        d[key] = now
        return True
    # Evict if at cap (drop the oldest 1k by re-creating dict)
    if len(d) >= _RECENT_MAX:
        cutoff = now - _RECENT_TTL
        for k in [kk for kk, v in d.items() if v < cutoff][:1000]:
            d.pop(k, None)
    d[key] = now
    return False


def _decide_sample(
    *,
    status_code: int | None,
    ip: str | None,
    user_id: str | None,
    is_bot: bool,
    now: float,
) -> tuple[bool, float]:
    """Return (should_persist, sampled_pct). Sampling decision tree per §1.D."""
    # Rule 1: errors always sampled
    if status_code is not None and status_code >= 400:
        return (True, 100.0)
    # Rule 2: new IP / user → always sampled
    if ip and not _is_recent(_RECENT_IPS, ip, now):
        return (True, 100.0)
    if user_id and not _is_recent(_RECENT_USERS, user_id, now):
        return (True, 100.0)
    # Rule 3: bots — heavy sampling
    if is_bot:
        if random.random() * 100 < _SAMPLE_BOT_PCT:
            return (True, _SAMPLE_BOT_PCT)
        return (False, _SAMPLE_BOT_PCT)
    # Rule 4: steady-state successes
    if random.random() * 100 < _SAMPLE_SUCCESS_PCT:
        return (True, _SAMPLE_SUCCESS_PCT)
    return (False, _SAMPLE_SUCCESS_PCT)


async def _persist_request(pool, **kw: Any) -> None:
    """Fire-and-forget INSERT. Never raises into the caller."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO request_telemetry (
                    trace_id, user_id, user_role, session_id,
                    method, path, status_code, latency_ms,
                    request_bytes, response_bytes,
                    ip_address,
                    device_type, browser_name, browser_version,
                    os_name, os_version, is_bot,
                    geo_country, geo_country_name, geo_city,
                    geo_lat, geo_lon, geo_subdivision,
                    user_agent, referer,
                    sampled_pct, is_suspicious, suspicious_reasons
                ) VALUES (
                    $1, $2::uuid, $3, $4,
                    $5, $6, $7, $8,
                    $9, $10,
                    $11::inet,
                    $12, $13, $14,
                    $15, $16, $17,
                    $18, $19, $20,
                    $21, $22, $23,
                    $24, $25,
                    $26, $27, $28::text[]
                )
                """,
                kw.get("trace_id"),
                kw.get("user_id"), kw.get("user_role"), kw.get("session_id"),
                kw["method"], kw["path"], kw.get("status_code"), kw.get("latency_ms"),
                int(kw.get("request_bytes") or 0),
                int(kw.get("response_bytes") or 0),
                kw.get("ip_address"),
                kw.get("device_type"), kw.get("browser_name"), kw.get("browser_version"),
                kw.get("os_name"), kw.get("os_version"), bool(kw.get("is_bot") or False),
                kw.get("geo_country"), kw.get("geo_country_name"), kw.get("geo_city"),
                kw.get("geo_lat"), kw.get("geo_lon"), kw.get("geo_subdivision"),
                kw.get("user_agent"), kw.get("referer"),
                float(kw.get("sampled_pct") or 100.0),
                bool(kw.get("is_suspicious") or False),
                kw.get("suspicious_reasons"),
            )
    except Exception as exc:
        logger.warning(
            "request_telemetry: persist failed (non-blocking) path={} err={}",
            kw.get("path"), exc,
        )


_pending_persists: set[asyncio.Task] = set()


def _track(task: asyncio.Task) -> None:
    _pending_persists.add(task)
    task.add_done_callback(_pending_persists.discard)


async def flush_pending_persists(timeout: float = 5.0) -> None:
    """Await pending persists at shutdown."""
    if not _pending_persists:
        return
    pending = list(_pending_persists)
    try:
        await asyncio.wait_for(
            asyncio.gather(*pending, return_exceptions=True),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "request_telemetry: shutdown flush timed out ({} pending)",
            len(_pending_persists),
        )


def _enrich_ua(ua: str | None) -> dict:
    """Phase C.3 — UA parsing. Falls back to all-NULL when lib unavailable."""
    try:
        from app.core.user_agent_parser import parse_ua
        return parse_ua(ua or "")
    except Exception:
        return {
            "device_type": None, "is_bot": False,
            "browser_name": None, "browser_version": None,
            "os_name": None, "os_version": None,
        }


def _enrich_geo(ip: str | None) -> dict:
    """Phase C.4 — GeoIP enrichment. Falls back to all-NULL when DB unavailable."""
    try:
        from app.core.geoip import lookup_ip
        return lookup_ip(ip or "")
    except Exception:
        return {
            "geo_country": None, "geo_country_name": None,
            "geo_city": None, "geo_lat": None, "geo_lon": None,
            "geo_subdivision": None,
        }


class RequestTelemetryMiddleware:
    """Pure ASGI middleware. Captures + persists per-request HTTP telemetry."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if _is_excluded(path):
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_code: int | None = None
        response_bytes = 0

        # Track response for size + status
        async def send_wrapper(message: dict) -> None:
            nonlocal status_code, response_bytes
            if message["type"] == "http.response.start":
                status_code = message.get("status")
            elif message["type"] == "http.response.body":
                body = message.get("body") or b""
                if body:
                    response_bytes += len(body)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            try:
                await self._capture(scope, status_code, response_bytes, start)
            except Exception as exc:
                logger.debug("request_telemetry: capture skipped ({})", exc)

    async def _capture(
        self,
        scope: Scope,
        status_code: int | None,
        response_bytes: int,
        start: float,
    ) -> None:
        """Build + persist the row. Best-effort, fire-and-forget."""
        latency_ms = int((time.monotonic() - start) * 1000)
        path = _truncate(scope.get("path", ""), _MAX_PATH_LEN) or "/"
        method = scope.get("method", "GET")
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            method = "GET"

        # Headers
        headers = {
            k.decode("ascii", errors="ignore").lower(): v.decode("utf-8", errors="ignore")
            for k, v in (scope.get("headers") or [])
        }
        ua = _truncate(headers.get("user-agent"), _MAX_UA_LEN)
        referer = _truncate(headers.get("referer") or headers.get("referrer"), _MAX_REFERER_LEN)

        ip = _get_client_ip(scope)

        # Trace ID from active OTEL span
        trace_id: str | None = None
        try:
            from opentelemetry import trace as _otel_trace
            span = _otel_trace.get_current_span()
            if span is not None:
                ctx = span.get_span_context()
                if ctx and ctx.trace_id:
                    trace_id = format(ctx.trace_id, "032x")
        except Exception:
            pass

        # User from scope state (set by upstream auth dependency / middleware)
        user = None
        try:
            user = scope.get("state", {}).get("user") if isinstance(scope.get("state"), dict) else None
        except Exception:
            pass
        user_id: str | None = None
        user_role: str | None = None
        if user is not None:
            uid = getattr(user, "id", None)
            if uid is not None:
                user_id = str(uid)
            urole = getattr(user, "role", None)
            if urole is not None:
                user_role = str(urole)

        # Enrichments (no-op until C.3 / C.4 modules exist)
        ua_info = _enrich_ua(ua)
        geo_info = _enrich_geo(ip)
        is_bot = bool(ua_info.get("is_bot"))

        # Sampling decision
        now = time.monotonic()
        should_persist, sampled_pct = _decide_sample(
            status_code=status_code, ip=ip, user_id=user_id,
            is_bot=is_bot, now=now,
        )
        if not should_persist:
            return

        # Request bytes from Content-Length header (best-effort)
        try:
            request_bytes = int(headers.get("content-length") or 0)
        except (TypeError, ValueError):
            request_bytes = 0

        # Resolve pool lazily
        try:
            from app.database.connection import get_db_pool
            pool = await get_db_pool()
        except Exception:
            return

        task = asyncio.create_task(_persist_request(
            pool,
            trace_id=trace_id,
            user_id=user_id, user_role=user_role,
            session_id=None,  # frontend session token not threaded yet
            method=method, path=path,
            status_code=status_code, latency_ms=latency_ms,
            request_bytes=request_bytes, response_bytes=response_bytes,
            ip_address=ip,
            device_type=ua_info.get("device_type"),
            browser_name=ua_info.get("browser_name"),
            browser_version=ua_info.get("browser_version"),
            os_name=ua_info.get("os_name"),
            os_version=ua_info.get("os_version"),
            is_bot=is_bot,
            geo_country=geo_info.get("geo_country"),
            geo_country_name=geo_info.get("geo_country_name"),
            geo_city=geo_info.get("geo_city"),
            geo_lat=geo_info.get("geo_lat"),
            geo_lon=geo_info.get("geo_lon"),
            geo_subdivision=geo_info.get("geo_subdivision"),
            user_agent=ua, referer=referer,
            sampled_pct=sampled_pct,
        ))
        _track(task)


__all__ = ["RequestTelemetryMiddleware", "flush_pending_persists"]
