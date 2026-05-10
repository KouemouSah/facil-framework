"""
🚀 TaxasGE Backend - Production FastAPI Application
Optimized for Firebase Functions + Direct FastAPI deployment
"""

import os
import sys
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import uvicorn
# Note: functions_framework removed in v1.1.8 - Cloud Run uses uvicorn directly
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from pydantic import ValidationError
from loguru import logger
import asyncpg
import redis.asyncio as redis
import json

# Single source of truth for backend settings — see app/config.py.
# main.py used to define a duplicate local Settings(BaseSettings) class with
# 8 fields that diverged from the canonical one (notably missing SENTRY_DSN,
# which crashed the container at import time after the Sentry init block was
# added). Removed 2026-05-02. All `settings.XXX` references in this file
# now read from the canonical class — UPPERCASE attribute names per its
# convention. The `api_version` property on the canonical class is preserved
# as a backward-compat alias for the lowercase reads in this file.
from app.config import get_settings
settings = get_settings()
security = HTTPBearer()

# Global connections
from app.database.connection import db_manager  # Use centralized DB manager
redis_client = None

# Lifespan management for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global redis_client

    try:
        # Initialize database connection pool (using centralized db_manager)
        await db_manager.connect()
        logger.info("✅ Database connection pool initialized")

        # ----------------------------------------------------------------
        # Phase C.4 — GeoIP DB initialization (best-effort, non-blocking).
        # ----------------------------------------------------------------
        # Looks for /tmp/GeoLite2-City.mmdb (or GEOIP_DB_PATH env var). If
        # absent, geo enrichment in request_telemetry is silently disabled
        # — middleware persists NULL for geo_country/city/lat/lon columns.
        try:
            from app.core.geoip import init_geoip
            init_geoip()
        except Exception as exc:
            logger.warning(f"⚠️ GeoIP init failed (non-blocking): {exc}")

        # ----------------------------------------------------------------
        # OpenTelemetry tracing (AI Observability — Phase A.2 / mig 325)
        # ----------------------------------------------------------------
        # Conditional: only configures the OTLP exporter when both
        # OTEL_EXPORTER_OTLP_ENDPOINT and the package are available. Without
        # the endpoint env var, ai_telemetry.py runs in BD-only mode (spans
        # become no-ops).
        otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otel_endpoint:
            try:
                from opentelemetry import trace as _otel_trace
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
                from opentelemetry.sdk.resources import Resource

                resource = Resource.create({
                    "service.name": os.environ.get("OTEL_SERVICE_NAME", "facil-backend"),
                    "service.version": os.environ.get("GIT_COMMIT_SHA", "unknown")[:12],
                    "deployment.environment": os.environ.get(
                        "ENVIRONMENT", os.environ.get("ENV", "dev")
                    ),
                })
                # Phase B.9 — drop noise spans before they hit Tempo:
                # /healthz, /ready, /metrics, /static/*, OPTIONS preflight.
                # Optional ratio sampler on the long tail via env var
                # OTEL_TRACES_RATIO=0.25 (off by default = 100% kept).
                from app.core.otel_sampler import build_sampler
                ratio_env = os.environ.get("OTEL_TRACES_RATIO")
                ratio = float(ratio_env) if ratio_env else None
                sampler = build_sampler(ratio=ratio)
                provider = (
                    TracerProvider(resource=resource, sampler=sampler)
                    if sampler is not None
                    else TracerProvider(resource=resource)
                )
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
                _otel_trace.set_tracer_provider(provider)
                logger.info(
                    "✅ OTEL tracing enabled — exporting to {} (sampler={})",
                    otel_endpoint.split("/")[2] if "/" in otel_endpoint else otel_endpoint,
                    sampler.get_description() if sampler else "default",
                )

                # ----------------------------------------------------
                # Phase B — Backend APM auto-instrumentation.
                # User decision 2026-05-05: 100% sampling, instrument
                # everything (FastAPI HTTP routes + asyncpg queries +
                # httpx external calls + redis ops). Powers Grafana
                # Cloud Application Observability service map (RED
                # metrics auto-derived from spans).
                # Each library is wrapped soft-importingly: missing
                # packages don't break the boot.
                # ----------------------------------------------------
                try:
                    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
                    AsyncPGInstrumentor().instrument()
                    logger.info("✅ OTEL asyncpg instrumented (DB queries)")
                except Exception as exc:
                    logger.warning("⚠️ OTEL asyncpg instrumentation failed: {}", exc)

                try:
                    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
                    HTTPXClientInstrumentor().instrument()
                    logger.info("✅ OTEL httpx instrumented (external HTTP calls)")
                except Exception as exc:
                    logger.warning("⚠️ OTEL httpx instrumentation failed: {}", exc)

                try:
                    from opentelemetry.instrumentation.redis import RedisInstrumentor
                    RedisInstrumentor().instrument()
                    logger.info("✅ OTEL redis instrumented (cache ops)")
                except Exception as exc:
                    logger.warning("⚠️ OTEL redis instrumentation failed: {}", exc)

                # FastAPI auto-instrumentation is hooked AFTER the FastAPI
                # app instance is created (see _instrument_fastapi_app
                # call further down once `app` exists).

            except Exception as exc:
                logger.warning(
                    "⚠️ OTEL setup failed (non-blocking, BD metrics still work): {}",
                    exc,
                )
        else:
            logger.info(
                "⚠️ OTEL_EXPORTER_OTLP_ENDPOINT unset — AI telemetry runs in BD-only mode"
            )

        # Initialize permissions system (RBAC)
        try:
            # Import permissions module - triggers auto-discovery of all module_permissions
            # This import chain:
            #   1. permissions/__init__.py imports module_permissions
            #   2. module_permissions/__init__.py runs discover_and_register_permissions()
            #   3. All *_permissions.py files are loaded and registered
            from app.modules.permissions import initialize_permissions

            # Sync permissions and role_permissions — NON-DESTRUCTIVE.
            #
            # cleanup_obsolete=False (changed 2026-05-04 from True): the
            # boot now UPSERTs but never DELETEs. New permissions added by
            # SQL migrations (e.g. dashboards.view_business / .manage from
            # mig 316/317) automatically SURVIVE the next boot even if no
            # *_permissions.py mirror exists yet. The drift is reported as
            # a warning in the logs (report_obsolete=True default) so the
            # team has visibility without anything being wiped.
            #
            # To actually delete obsolete permissions, run the explicit
            # CLI: scripts/cleanup_obsolete_permissions.py --apply
            #
            # Why: prior behaviour caused mig 316 / 317 grants to be wiped
            # at every boot because their permissions weren't mirrored in
            # the code registry — see project_looker_e1_2026_05_04.md.
            async with db_manager.get_connection() as conn:
                sync_result = await initialize_permissions(
                    conn,
                    sync_role_permissions=True,
                    cleanup_obsolete=False,
                )
                logger.info(
                    f"✅ Permissions initialized: {sync_result['created_count']} new, "
                    f"{sync_result['skipped_count']} existing, "
                    f"{sync_result['total_count']} total"
                )
                # Log role_permissions sync if available
                if 'role_permissions' in sync_result:
                    rp = sync_result['role_permissions']
                    if 'error' not in rp:
                        logger.info(
                            f"✅ Role permissions synced: {rp.get('roles_updated', 0)} roles, "
                            f"{rp.get('permissions_assigned', 0)} assignments"
                        )
                # Log cleanup results if any obsolete permissions were removed
                if 'cleanup' in sync_result:
                    cleanup = sync_result['cleanup']
                    if 'error' not in cleanup and cleanup.get('deleted_count', 0) > 0:
                        logger.info(
                            f"🧹 Cleanup: {cleanup['deleted_count']} obsolete permissions removed"
                        )
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize permissions (non-blocking): {e}")

        # Auto-sync Looker view wrappers above MVs.
        #
        # Why: Looker Studio JDBC picker filters out MATERIALIZED VIEWS
        # (relkind='m'). Without a plain VIEW wrapper above each MV, drag-
        # drop in Looker shows only relkind='v' / 'r' relations.
        #
        # This is called at every boot so a new MV granted to looker_readonly
        # in a future migration AUTOMATICALLY gets its wrapper here — no
        # manual migration needed for the wrapper. The dev only writes the
        # GRANT in the MV migration; the boot does the rest.
        #
        # Idempotent (CREATE OR REPLACE VIEW). Non-destructive: orphan
        # wrappers are logged but never dropped. See looker_wrappers_sync.py.
        try:
            from app.modules.dashboards.services import sync_looker_view_wrappers
            async with db_manager.get_connection() as conn:
                wrap_result = await sync_looker_view_wrappers(conn)
            logger.info(
                f"✅ Looker wrappers synced: {len(wrap_result['synced'])} active, "
                f"{len(wrap_result['skipped'])} failed, "
                f"{len(wrap_result['orphans'])} orphans"
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to sync Looker view wrappers (non-blocking): {e}")

        # Sync all workflow data from Python classes → DB (single call)
        try:
            from app.modules.service_requests.services.workflow_sync_service import sync_all_workflows
            async with db_manager.get_connection() as conn:
                r = await sync_all_workflows(conn)
                logger.info(
                    f"✅ Workflows synced: {r.workflows_synced} "
                    f"({r.workflows_created} new, {r.workflows_updated} updated, "
                    f"{r.workflows_deactivated} orphans deleted), "
                    f"{r.tariffs_synced} tariffs, {r.documents_synced} docs, "
                    f"{r.menu_mappings_synced} menus, {r.display_configs_synced} display configs"
                )
                if r.errors:
                    logger.warning(f"⚠️ Workflow sync errors: {r.errors}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to sync workflows (non-blocking): {e}")

        # Initialize Event Bus and register handlers
        try:
            from app.core.events import EventBus
            from app.modules.communications.handlers import register_notification_handlers
            from app.modules.admin.handlers import register_audit_handlers
            from app.modules.service_requests.handlers import register_agent_queue_handlers
            from app.modules.payments.handlers import register_payment_assignment_handlers

            # Initialize the EventBus
            EventBus.initialize()

            # Register event handlers
            notification_handler = register_notification_handlers()
            audit_handler = register_audit_handlers()
            agent_queue_handler = register_agent_queue_handlers()
            logger.info("✅ Agent queue event handlers registered")

            # Register payment assignment handler (auto-assign manual payments to Treasury)
            payment_assignment_handler = register_payment_assignment_handlers()
            logger.info("✅ Payment assignment event handlers registered")

            # Register license counter refresh handler (async post-commit)
            from app.core.events import EventType

            async def _handle_counter_refresh(payload):
                """Async counter refresh — runs on separate connection post-commit."""
                from uuid import UUID
                from app.modules.fiscal_services.services.license_service import LicenseService
                license_id = payload.get("license_id")
                user_id = payload.get("user_id")
                if not license_id:
                    return
                try:
                    async with db_manager.acquire() as conn:
                        await LicenseService.update_license_counters(
                            conn, UUID(license_id),
                            UUID(user_id) if user_id else None,
                        )
                    logger.debug(f"Counter refresh completed for license {license_id}")
                except Exception as e:
                    logger.warning(f"Counter refresh failed for license {license_id}: {e}")

            EventBus.subscribe(EventType.LICENSE_COUNTER_REFRESH, _handle_counter_refresh)

            # Bundle PDF handler — generates proforma (at payment) and final license (at completion)
            async def _handle_bundle_pdf(payload):
                """Generate + store bundle PDF (proforma or final) post-commit."""
                from uuid import UUID
                event_type = payload.get("event_type", "")
                license_id = payload.get("license_id")
                workflow_code = payload.get("workflow_code")
                user_email = payload.get("user_email")

                # Only handle bundle payments
                if not license_id:
                    return
                if event_type == "payment.cash_pending" and workflow_code != "BUNDLE_PAYMENT":
                    return

                try:
                    from app.modules.fiscal_services.services.license_pdf_service import license_pdf_service

                    async with db_manager.acquire() as conn:
                        if event_type == "payment.cash_pending":
                            pdf_bytes = await license_pdf_service.generate_proforma_pdf(
                                conn, license_id,
                                payment_reference=payload.get("payment_reference"),
                            )
                            doc_type = "proforma"
                        else:
                            pdf_bytes = await license_pdf_service.generate_license_certificate(
                                conn, license_id,
                            )
                            doc_type = "certificate"

                    # Store in Firebase (best-effort)
                    stored_url = None
                    try:
                        from app.modules.documents.services.storage_service import storage_service
                        ref = f"LIC-{str(license_id)[:8].upper()}"
                        filename = f"{doc_type}_{ref}.pdf"
                        stored_url = await storage_service.upload_bytes(
                            pdf_bytes, f"licenses/{license_id}/{filename}",
                            content_type="application/pdf",
                        )
                        logger.info(f"Bundle {doc_type} PDF stored: {stored_url}")
                    except Exception as store_err:
                        logger.warning(f"PDF storage failed (non-blocking): {store_err}")

                    # Persist certificate URL + number in BD (best-effort)
                    if doc_type == "certificate" and stored_url:
                        try:
                            from app.modules.fiscal_services.services.license_pdf_service import license_pdf_service
                            cert_number = license_pdf_service._generate_certificate_number(
                                payload.get("fiscal_year", 2026),
                                "", "", license_id,
                            )
                            async with db_manager.acquire() as conn2:
                                await conn2.execute("""
                                    UPDATE commercial_licenses
                                    SET certificate_url = $1,
                                        certificate_number = $2,
                                        certificate_generated_at = NOW()
                                    WHERE id = $3::uuid
                                """, stored_url, cert_number, license_id)
                            logger.info(f"Certificate {cert_number} persisted for license {license_id}")
                        except Exception as persist_err:
                            logger.warning(f"Certificate persist failed: {persist_err}")

                    # Register in user's vault (Mes Documents)
                    if stored_url:
                        try:
                            from uuid import UUID as _UUID
                            from app.modules.user_documents.services.vault_registry import register_document_in_vault
                            from datetime import date as _date

                            # Find company owner(s) for vault registration
                            async with db_manager.acquire() as conn3:
                                owners = await conn3.fetch("""
                                    SELECT u.id, c.representante_legal, c.legal_name, cl.fiscal_year
                                    FROM users u
                                    JOIN user_company_roles ucr ON ucr.user_id = u.id
                                    JOIN commercial_licenses cl ON cl.company_id = ucr.company_id
                                    WHERE cl.id = $1::uuid AND ucr.role = 'company_owner'
                                """, license_id)

                                vault_doc_type = {
                                    "proforma": "PROFORMA_INVOICE",
                                    "certificate": "LICENSE_CERTIFICATE",
                                }.get(doc_type, "LICENSE_DOSSIER")

                                sr_id = payload.get("service_request_id")

                                for owner in owners:
                                    fy = owner["fiscal_year"] or 2026
                                    await register_document_in_vault(
                                        conn3,
                                        user_id=owner["id"],
                                        file_path=stored_url,
                                        file_name=f"{doc_type}_{ref}.pdf",
                                        document_type=vault_doc_type,
                                        document_category="fiscal",
                                        source_request_id=_UUID(sr_id) if sr_id else None,
                                        document_number=cert_number if doc_type == "certificate" else None,
                                        holder_name=owner["representante_legal"] or owner["legal_name"],
                                        expiry_date=_date(fy, 12, 31),
                                    )
                        except Exception as vault_err:
                            logger.warning(f"Vault registration failed: {vault_err}")

                    # Send email with attachment (best-effort)
                    if user_email and pdf_bytes:
                        try:
                            from app.modules.communications.services.email_service import get_email_service
                            email_svc = get_email_service()
                            ref = f"LIC-{str(license_id)[:8].upper()}"
                            subject = (
                                f"Factura Proforma — {ref}"
                                if doc_type == "proforma"
                                else f"Licencia Comercial Completada — {ref}"
                            )
                            body = (
                                f"<p>Adjunto encontrará su {doc_type.replace('_', ' ')}.</p>"
                                f"<p>Referencia: <strong>{ref}</strong></p>"
                            )
                            email_svc.send_email(
                                to_email=user_email,
                                subject=subject,
                                body_html=body,
                                body_text=f"Referencia: {ref}",
                                attachments=[
                                    (f"{doc_type}_{ref}.pdf", pdf_bytes, "application/pdf")
                                ],
                            )
                            logger.info(f"Bundle {doc_type} PDF emailed to {user_email}")
                        except Exception as email_err:
                            logger.warning(f"PDF email failed (non-blocking): {email_err}")

                except Exception as e:
                    logger.error(f"Bundle PDF generation failed: {e}", exc_info=True)

            EventBus.subscribe(EventType.PAYMENT_CASH_PENDING, _handle_bundle_pdf)
            EventBus.subscribe(EventType.LICENSE_COMPLETED, _handle_bundle_pdf)
            logger.info("✅ Bundle PDF + counter refresh handlers registered")

            # Register verification event handlers (external document verification)
            try:
                from app.modules.verified_identifiers.handlers import setup_verification_handlers
                await setup_verification_handlers()
                logger.info("✅ Verification event handlers registered")
            except Exception as ve:
                logger.warning(f"⚠️ Failed to register verification handlers: {ve}")

            logger.info(
                f"✅ EventBus initialized with {EventBus.handler_count()} handlers "
                f"for {len(EventBus.get_subscribed_events())} event types"
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize EventBus (non-blocking): {e}")

        # Self-healing: repair orphaned PAID requests (never assigned to entity agents)
        # Must run AFTER EventBus handlers are registered (publishes PAYMENT_COMPLETED)
        try:
            from app.modules.service_requests.handlers.agent_queue_handler import (
                repair_orphaned_paid_requests,
            )
            repaired = await repair_orphaned_paid_requests()
            if repaired > 0:
                logger.info(f"✅ Startup repair: {repaired} orphaned PAID requests re-queued")
        except Exception as e:
            logger.warning(f"⚠️ Startup repair failed (non-fatal): {e}")

        # Initialize Cache System (Upstash Redis with in-memory fallback)
        try:
            from app.core.cache import initialize_cache, get_cache_health
            await initialize_cache()
            cache_health = await get_cache_health()
            if cache_health["redis_enabled"] and cache_health["redis_status"] == "connected":
                logger.info("✅ Cache system initialized (Upstash Redis)")
            else:
                logger.info("ℹ️ Cache system initialized (in-memory fallback)")
        except Exception as cache_error:
            logger.warning(f"⚠️ Cache initialization failed (continuing without cache): {cache_error}")

        # Initialize legacy Redis connection (for backwards compatibility)
        if settings.REDIS_URL and settings.REDIS_URL != "redis://localhost:6379":
            try:
                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                await redis_client.ping()
                logger.info("✅ Legacy Redis client connected")
            except Exception as redis_error:
                logger.warning(f"⚠️ Legacy Redis unavailable: {redis_error}")
                redis_client = None
        else:
            logger.info("ℹ️ Legacy Redis client not configured")

    except Exception as e:
        logger.error(f"❌ Failed to initialize connections: {e}")
        # For development, continue without external dependencies
        if settings.ENVIRONMENT == "development":
            logger.warning("🔄 Continuing in development mode without external dependencies")
        else:
            raise

    # Start RBAC cache invalidation listener (PostgreSQL NOTIFY → Redis)
    try:
        from app.core.rbac_listener import rbac_listener
        if db_manager.pool:
            await rbac_listener.start(db_manager.pool)
            logger.info("✅ RBAC cache listener started (real-time invalidation)")
    except Exception as e:
        logger.warning(f"⚠️ RBAC listener failed (cache TTL fallback): {e}")

    # Start internal cron scheduler (replaces Cloud Scheduler)
    try:
        from app.core.scheduler import internal_scheduler
        await internal_scheduler.start()
    except Exception as e:
        logger.warning(f"⚠️ Internal scheduler failed to start (non-blocking): {e}")

    yield

    # Shutdown
    try:
        from app.core.scheduler import internal_scheduler
        await internal_scheduler.stop()
    except Exception:
        pass
    # Flush pending AI telemetry persists (Phase A.2 — mig 325)
    try:
        from app.core.ai_telemetry import flush_pending_persists
        await flush_pending_persists(timeout=5.0)
    except Exception as exc:
        logger.warning(f"⚠️ ai_telemetry flush failed (non-blocking): {exc}")
    # Phase C.2 — flush request_telemetry persists
    try:
        from app.core.request_telemetry_middleware import flush_pending_persists as flush_rt
        await flush_rt(timeout=5.0)
    except Exception as exc:
        logger.warning(f"⚠️ request_telemetry flush failed (non-blocking): {exc}")
    try:
        # Stop RBAC listener
        from app.core.rbac_listener import rbac_listener
        await rbac_listener.stop(db_manager.pool)

        # Shutdown cache system
        from app.core.cache import shutdown_cache
        await shutdown_cache()
        logger.info("🔄 Cache system shutdown")

        await db_manager.disconnect()
        logger.info("🔄 Database pool closed")
        if redis_client:
            await redis_client.close()
            logger.info("🔄 Legacy Redis connection closed")
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")

# =============================================================================
# Sentry — error tracking + performance traces (must init BEFORE app = FastAPI)
# =============================================================================
# Gating mirrors the mobile/web wrappers:
#   - Skipped when SENTRY_DSN is empty (forks / local dev without secrets)
#   - Skipped in DEBUG mode (NODE_ENV=development equivalent)
# Once init'd, every uncaught exception in any route is auto-captured
# with full stack trace + breadcrumbs (the 60s of activity before the crash).
# Performance: 5% transaction sampling — calibrated for the Free Developer
# plan (5K errors + 10K transactions / month / project).
if settings.SENTRY_DSN and not settings.DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    from sentry_sdk.integrations.asyncpg import AsyncPGIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    _sentry_environment = (
        "staging"
        if "staging" in (settings.api_version or "")
        or "staging" in os.environ.get("K_SERVICE", "")
        else "production"
    )

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            AsyncPGIntegration(),
            RedisIntegration(),
        ],
        environment=_sentry_environment,
        release=os.environ.get("GIT_COMMIT_SHA") or settings.api_version,
        traces_sample_rate=0.05,
        profiles_sample_rate=0.0,  # Profiling not needed yet; off to save quota
        send_default_pii=False,    # Never send IP / cookies / headers by default
        # Strip authorization headers + auth bodies before any event leaves
        # the server — defense in depth on top of FastAPI's own scrubbing.
        before_send=lambda event, _hint: _scrub_sentry_event(event),
    )
    sentry_sdk.set_tag("service", "taxasge-backend")
    # Use the value we computed above instead of reading it back from the SDK.
    # `sentry_sdk.Hub.current.client.options['environment']` is deprecated in
    # sentry-sdk 2.x and would crash here if init silently failed (client=None).
    logger.info(f"✅ Sentry initialised — env={_sentry_environment}")


def _attach_otel_trace_id(event: dict) -> dict:
    """Phase B.4 — Sentry-OTEL bridge.

    When OTEL tracing is configured (Phase A.4 + B), every Sentry event gets
    the active OTEL trace_id and span_id as tags. Lets the on-call engineer
    click from a Sentry error → Grafana Tempo trace in 1 jump (search by
    trace_id) instead of trying to correlate timestamps manually.

    Soft-import: when opentelemetry isn't loaded, this is a no-op.
    """
    try:
        from opentelemetry import trace as _otel_trace
        span = _otel_trace.get_current_span()
        if span is None:
            return event
        ctx = span.get_span_context()
        if not ctx or not ctx.trace_id:
            return event
        tags = event.setdefault("tags", {})
        tags["otel.trace_id"] = format(ctx.trace_id, "032x")
        if ctx.span_id:
            tags["otel.span_id"] = format(ctx.span_id, "016x")
    except Exception:
        pass  # never break event delivery
    return event


def _scrub_sentry_event(event):
    """Remove Authorization / Cookie headers + attach OTEL trace_id."""
    request = event.get("request", {})
    headers = request.get("headers", {})
    for key in list(headers.keys()):
        if key.lower() in ("authorization", "cookie", "x-api-key"):
            headers[key] = "[REDACTED]"
    # Drop request bodies on auth-issuing routes
    url = request.get("url", "") or ""
    if any(seg in url for seg in ("/auth/login", "/auth/register", "/auth/2fa", "/auth/refresh")):
        request.pop("data", None)
    # Phase B.4: attach OTEL trace_id so on-call jumps Sentry → Tempo
    event = _attach_otel_trace_id(event)
    return event


# FastAPI application
app = FastAPI(
    title="TaxasGE API",
    description="Production-ready fiscal services platform for Guinea",
    version=settings.api_version,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Phase B — FastAPI auto-instrumentation (Backend APM).
# Hooks the FastAPI middleware that creates a parent span for every HTTP
# request. Combined with asyncpg/httpx/redis instrumentation in lifespan(),
# powers Grafana Cloud Application Observability service map.
# Soft-import: missing package doesn't break the app.
if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        # excluded_urls keeps the trace volume sane on health/metrics endpoints
        # that fire every second from Cloud Run's load balancer.
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="^(/healthz|/health|/_ah/.*|/metrics|/static/.*)$",
        )
        logger.info("✅ OTEL FastAPI instrumented (HTTP request spans)")
    except Exception as exc:
        logger.warning(f"⚠️ OTEL FastAPI instrumentation failed: {exc}")

# Security middleware - Based on Cloud Run + Firebase Hosting configuration
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else [
        "taxasge-backend-staging-xrlbgdr5eq-uc.a.run.app",  # Cloud Run backend staging
        "taxasge-backend-staging-392159428433.us-central1.run.app",  # Cloud Run backend alt
        "taxasge.emacsah.com",          # Custom domain frontend
        "taxasge-dev.web.app",          # Firebase Hosting dev
        "taxasge-pro.web.app",          # Firebase Hosting prod
        "taxasge-dev.firebaseapp.com",  # Firebase domain dev
        "taxasge-pro.firebaseapp.com",  # Firebase domain prod
        "localhost",                     # Local development
        "127.0.0.1"                     # Local IP
    ]
)

# Security headers middleware — pure ASGI (not BaseHTTPMiddleware) to avoid
# conflict with CORSMiddleware on OPTIONS preflight requests
class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                extra_headers = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    # Note: CSP is set by the frontend middleware.ts (Next.js).
                    # Backend API responses (JSON) don't need CSP headers.
                    # Duplicate CSP headers can cause the browser to apply
                    # the intersection (most restrictive), breaking the frontend.
                ]
                if not settings.DEBUG:
                    extra_headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = list(message.get("headers", [])) + extra_headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

app.add_middleware(SecurityHeadersMiddleware)

# Phase B.3 — OTEL user attribute enricher.
# Tags every request span with user.id / user.role when authenticated.
# Soft no-op when OTEL not configured.
try:
    from app.core.otel_user_middleware import OtelUserAttributeMiddleware
    app.add_middleware(OtelUserAttributeMiddleware)
    logger.debug("✅ OTEL user attribute middleware registered")
except Exception as exc:
    logger.warning(f"⚠️ OTEL user middleware setup failed: {exc}")

# Phase C.2 — request_telemetry middleware.
# Captures every HTTP request (method/path/status/latency/IP/UA/geo) into
# the request_telemetry table (mig 329) for the Security Monitoring
# dashboard. Pure ASGI, fire-and-forget persist, sampled. Bypasses health
# checks + static + docs paths.
try:
    from app.core.request_telemetry_middleware import RequestTelemetryMiddleware
    app.add_middleware(RequestTelemetryMiddleware)
    logger.debug("✅ Request telemetry middleware registered")
except Exception as exc:
    logger.warning(f"⚠️ Request telemetry middleware setup failed: {exc}")

# Compress JSON / text responses ≥ 1 KiB. The fiscal-services catalog
# endpoints (ministries, categories, search) routinely return 30-80 KiB of
# UTF-8 JSON; gzipping shrinks that 5-7x on the wire which is the single
# biggest leverage point for users on patchy 3G in Equatorial Guinea
# (cf. user feedback on slow Services tab loading on cellular).
# Threshold 1024 avoids the CPU overhead on tiny health-check responses.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# CORS middleware - Aligned with Cloud Run deployments
# Note: Firebase Hosting staging channels use pattern: https://PROJECT--CHANNEL-ID.web.app
_PROD_ORIGINS = [
    "https://taxasge.emacsah.com",           # Custom domain (Cloud Run frontend)
    "https://taxasge-frontend-staging-xrlbgdr5eq-uc.a.run.app",  # Cloud Run direct URL
    "https://taxasge-dev.web.app",
    "https://taxasge-pro.web.app",
    "https://taxasge-dev.firebaseapp.com",
    "https://taxasge-pro.firebaseapp.com",
]
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    # In debug/staging: allow both localhost AND production origins
    # In production: production origins only
    allow_origins=(_DEV_ORIGINS + _PROD_ORIGINS) if settings.DEBUG else _PROD_ORIGINS,
    allow_origin_regex=r"https://taxasge-(dev|frontend-staging)--[\w-]+\.(web\.app|run\.app)",  # Allow staging channels
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language", "X-Cron-Secret"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
)

# Global exception handlers to ensure CORS headers are set on all error responses
# Import TreasuryError for specific handling
try:
    from app.modules.treasury.errors import TreasuryError
except ImportError:
    TreasuryError = None

def get_cors_headers(request: Request) -> dict:
    """Get CORS headers based on request origin."""
    origin = request.headers.get("origin", "")
    allowed_origins = (_DEV_ORIGINS + _PROD_ORIGINS) if settings.DEBUG else _PROD_ORIGINS
    # Check if origin is allowed or matches staging pattern
    import re
    if origin in allowed_origins or re.match(r"https://taxasge-(dev|frontend-staging)--[\w-]+\.(web\.app|run\.app)", origin):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
        }
    return {}

import asyncpg as _asyncpg  # noqa: E402 — used by DB error handlers below
from app.core.db_error_handler import build_db_error_response  # noqa: E402


@app.exception_handler(_asyncpg.exceptions.PostgresError)
async def asyncpg_postgres_error_handler(
    request: Request, exc: _asyncpg.exceptions.PostgresError,
):
    """Map asyncpg PostgresError subclasses (23505, 23514, 40001, ...) to
    structured API responses with trilingual messages and metier codes.
    See app/core/db_error_handler.py for the full mapping table.
    """
    return build_db_error_response(request, exc)


@app.exception_handler(_asyncpg.exceptions.InterfaceError)
async def asyncpg_interface_error_handler(
    request: Request, exc: _asyncpg.exceptions.InterfaceError,
):
    """asyncpg InterfaceError is NOT a PostgresError subclass but still
    represents a database-layer failure (connection lost, pool exhausted,
    protocol mismatch). Route it through the same sanitizer.
    """
    return build_db_error_response(request, exc)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions with i18n and CORS headers."""
    from app.core.errors import get_error_message, ErrorCode
    logger.opt(exception=True).error("Unhandled exception: {}", str(exc))
    lang = "es"
    try:
        accept = request.headers.get("Accept-Language", "es")
        lang = accept[:2] if accept[:2] in ("es", "fr", "en") else "es"
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={
            "detail": get_error_message(ErrorCode.SERVER_ERROR, lang),
            "error_code": ErrorCode.SERVER_ERROR.value,
        },
        headers=get_cors_headers(request)
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with auto-translation and CORS headers.

    Translation priority:
    1. TranslatedException with error_code → already translated at raise site
    2. Legacy HTTPException → auto-translate via pattern matching
    3. Unknown messages → pass through as-is with HTTP_xxx code

    SECURITY: For 5xx errors, sanitize the detail to prevent leaking internal
    exception messages (str(e)) to clients. Full details are logged server-side.
    """
    from app.core.errors import TranslatedException, translate_error_detail, get_error_message, ErrorCode

    # Detect language from request
    lang = "es"
    try:
        if hasattr(request, "state") and hasattr(request.state, "language"):
            lang = request.state.language.value
        else:
            accept = request.headers.get("Accept-Language", "es")
            lang = accept[:2] if accept[:2] in ("es", "fr", "en") else "es"
    except Exception:
        pass

    # For 5xx: log the real detail but return generic translated message
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
        error_code = getattr(exc, "error_code", ErrorCode.SERVER_ERROR).value if hasattr(exc, "error_code") else "ERR_SERVER_ERROR"
        content = {
            "detail": get_error_message(ErrorCode.SERVER_ERROR, lang),
            "error_code": error_code,
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=get_cors_headers(request)
        )

    # For TranslatedException: already has error_code
    if isinstance(exc, TranslatedException):
        content = {
            "detail": exc.detail,
            "error_code": exc.error_code.value,
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=get_cors_headers(request)
        )

    # For 4xx and below: auto-translate known patterns
    if isinstance(exc.detail, dict):
        content = exc.detail
        if "error_code" not in content:
            content["error_code"] = f"HTTP_{exc.status_code}"
    else:
        translated, code = translate_error_detail(exc.detail or "", lang)
        content = {
            "detail": translated,
            "error_code": code or f"HTTP_{exc.status_code}",
        }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=get_cors_headers(request)
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with CORS headers."""
    logger.warning(f"Request validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "error_code": "VALIDATION_ERROR",
            "message_es": "Error de validación en los datos enviados."
        },
        headers=get_cors_headers(request)
    )


@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    """Handle response validation errors with CORS headers."""
    logger.error(f"Response validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Response validation error",
            "error_code": "RESPONSE_VALIDATION_ERROR",
            "message_es": "Error de validación en la respuesta del servidor.",
            "validation_errors": str(exc.errors())[:500]  # Truncate for safety
        },
        headers=get_cors_headers(request)
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors with CORS headers."""
    logger.error(f"Pydantic validation error: {exc.errors()}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Data validation error",
            "error_code": "PYDANTIC_VALIDATION_ERROR",
            "message_es": "Error de validación de datos.",
            "validation_errors": str(exc.errors())[:500]
        },
        headers=get_cors_headers(request)
    )


# Language detection middleware - Detects user language from headers/query
try:
    from app.modules.translations.middleware.language_middleware import language_middleware
    app.middleware("http")(language_middleware)
    logger.info("✅ Language detection middleware configured")
except ImportError as e:
    logger.warning(f"⚠️ Language detection middleware not available: {e}")

# Dependency to get database connection
async def get_db():
    if db_manager.pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available"
        )
    async with db_manager.pool.acquire() as connection:
        yield connection

# Dependency to get Redis connection
async def get_redis():
    if redis_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis connection not available"
        )
    return redis_client

# Health check endpoint
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    health_status = {
        "status": "healthy",
        "service": "taxasge-backend",
        "environment": settings.ENVIRONMENT,
        "version": settings.api_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": "FastAPI + Cloud Run",
        "checks": {
            "api": "ok",
            "database": "unknown",
            "redis": "unknown",
            "firebase": "ok"
        }
    }

    # Test database connection
    try:
        if db_manager.pool:
            async with db_manager.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Test Cache System (Upstash Redis)
    try:
        from app.core.cache import get_cache_health
        cache_health = await get_cache_health()
        health_status["checks"]["cache"] = cache_health
        if cache_health["redis_enabled"]:
            if cache_health["redis_status"] == "connected":
                health_status["checks"]["redis"] = "ok (Upstash)"
            else:
                health_status["checks"]["redis"] = cache_health["redis_status"]
                health_status["status"] = "degraded"
        else:
            health_status["checks"]["redis"] = "disabled (in-memory fallback)"
    except Exception as e:
        health_status["checks"]["cache"] = f"error: {str(e)}"
        health_status["checks"]["redis"] = f"error: {str(e)}"

    return health_status

# Feature flags endpoint (public, cached)
@app.get("/api/v1/feature-flags")
async def get_feature_flags():
    """
    Public endpoint returning dynamic feature flags from system_rules.
    Used by frontend to toggle features without redeploy.
    Cached in-memory for 5 minutes.
    """
    try:
        from app.core.cache import get_cache
        cache = get_cache()
        cached = await cache.get("feature_flags")
        if cached:
            return cached

        async with db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT rule_code, rule_value
                FROM system_rules
                WHERE rule_category = 'feature_flag' AND is_active = true
            """)
            flags = {}
            for row in rows:
                code = row["rule_code"].replace("FEATURE_", "").lower()
                val = row["rule_value"]
                if isinstance(val, str):
                    import json as _json
                    val = _json.loads(val)
                flags[code] = val.get("enabled", False) if isinstance(val, dict) else bool(val)

            result = {"flags": flags, "source": "database"}
            await cache.set("feature_flags", result, ttl=300)
            return result
    except Exception as e:
        logger.warning(f"Feature flags fallback to defaults: {e}")
        return {
            "flags": {
                "dynamic_menus": True,
                "dynamic_widgets": False,
                "dynamic_form": True,
                "cache_first_wizard": True,
                "redis_cache": False,
                "declarations": False,
            },
            "source": "defaults"
        }


# Root endpoint
@app.get("/")
async def root():
    """API root information"""
    return {
        "message": "🚀 TaxasGE API",
        "environment": settings.ENVIRONMENT,
        "version": settings.api_version,
        "status": "operational",
        "description": "Production-ready fiscal services platform",
        "endpoints": {
            "health": "/health",
            "docs": "/docs" if settings.DEBUG else "restricted",
            "api": "/api/v1/"
        },
        "features": {
            "fiscal_services": "850+ services available",
            "multi_language": "Spanish, French, English",
            "ai_assistant": "Conversational AI support",
            "mobile_payments": "BANGE integration",
            "enterprise_support": "B2B declarations"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": "FastAPI + Cloud Run"
    }

# Debug endpoints — hidden in production, require auth header in staging
def _check_debug_access(request: Request):
    """Guard: 404 in production, 401 without auth in staging."""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not found")
    if not request.headers.get("authorization"):
        raise HTTPException(status_code=401, detail="Authentication required")

@app.get("/api/v1/debug/routers")
async def debug_routers(request: Request):
    """Debug endpoint to check which routers are loaded"""
    _check_debug_access(request)
    return {
        "status": "diagnostic",
        "routers_loaded": routers_loaded,
        "routers_count": len(routers_loaded),
        "auth_loaded": "auth" in routers_loaded,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.ENVIRONMENT
    }


@app.get("/api/v1/debug/communications-import")
async def debug_communications_import(request: Request):
    """Debug endpoint to diagnose communications router import errors"""
    _check_debug_access(request)
    import_errors = []
    import_success = []

    # Test each import in the communications chain
    try:
        from app.modules.communications.models.communication import EmailTemplate
        import_success.append("models.communication.EmailTemplate")
    except Exception as e:
        import_errors.append({"module": "models.communication", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.communications.services.template_service import get_template_service
        import_success.append("services.template_service")
    except Exception as e:
        import_errors.append({"module": "services.template_service", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.communications.services.email_service import EmailService
        import_success.append("services.email_service.EmailService")
    except Exception as e:
        import_errors.append({"module": "services.email_service", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.communications.services.communication_service import CommunicationService
        import_success.append("services.communication_service.CommunicationService")
    except Exception as e:
        import_errors.append({"module": "services.communication_service", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.communications.api.communication_routes import router
        import_success.append("api.communication_routes.router")
    except Exception as e:
        import_errors.append({"module": "api.communication_routes", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.communications.api import router as main_router
        import_success.append("api.router (main)")
    except Exception as e:
        import_errors.append({"module": "api (main router)", "error": str(e), "type": type(e).__name__})

    return {
        "status": "diagnostic",
        "communications_loaded": "communications" in routers_loaded,
        "import_success": import_success,
        "import_errors": import_errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/debug/enum-import")
async def debug_enum_import(request: Request):
    """Debug endpoint to diagnose enum router import errors"""
    _check_debug_access(request)
    import_errors = []
    import_success = []

    # Test each import in the chain
    try:
        from app.modules.translations.repositories.translation_repository import TranslationRepository
        import_success.append("translation_repository.TranslationRepository")
    except Exception as e:
        import_errors.append({"module": "translation_repository.TranslationRepository", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.translations.repositories.enum_repository import EnumRepository, MODIFIABLE_ENUMS
        import_success.append("enum_repository.EnumRepository")
        import_success.append(f"MODIFIABLE_ENUMS: {MODIFIABLE_ENUMS}")
    except Exception as e:
        import_errors.append({"module": "enum_repository.EnumRepository", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.translations.services.enum_service import EnumService
        import_success.append("enum_service.EnumService")
    except Exception as e:
        import_errors.append({"module": "enum_service.EnumService", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.auth.middleware.auth_middleware import get_current_user, get_current_admin_user
        import_success.append("auth_middleware.get_current_user")
        import_success.append("auth_middleware.get_current_admin_user")
    except Exception as e:
        import_errors.append({"module": "auth_middleware", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.translations.api.enum_routes import router as enum_router
        import_success.append("enum_routes.router")
    except Exception as e:
        import_errors.append({"module": "enum_routes.router", "error": str(e), "type": type(e).__name__})

    return {
        "status": "diagnostic",
        "enum_router_loaded": "enums" in routers_loaded,
        "import_success": import_success,
        "import_errors": import_errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/debug/support-import")
async def debug_support_import(request: Request):
    """Debug endpoint to diagnose support router import errors"""
    _check_debug_access(request)
    import_errors = []
    import_success = []

    # Test each import in the support module chain
    try:
        from app.modules.support.models.support import SupportCategoryCreate
        import_success.append("models.support.SupportCategoryCreate")
    except Exception as e:
        import_errors.append({"module": "models.support.SupportCategoryCreate", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.support.repositories.support_repository import SupportRepository
        import_success.append("repositories.support_repository.SupportRepository")
    except Exception as e:
        import_errors.append({"module": "repositories.support_repository", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.support.services.support_service import SupportService
        import_success.append("services.support_service.SupportService")
    except Exception as e:
        import_errors.append({"module": "services.support_service", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.support.api.support_routes import router as support_router
        import_success.append("api.support_routes.router")
    except Exception as e:
        import_errors.append({"module": "api.support_routes.router", "error": str(e), "type": type(e).__name__})

    try:
        from app.modules.support.api import router
        import_success.append("api.__init__.router")
    except Exception as e:
        import_errors.append({"module": "api.__init__.router", "error": str(e), "type": type(e).__name__})

    return {
        "status": "diagnostic",
        "support_router_loaded": "support" in routers_loaded,
        "import_success": import_success,
        "import_errors": import_errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/debug/service-requests-import")
async def debug_service_requests_import(request: Request):
    """Debug endpoint to diagnose service_requests router import errors"""
    _check_debug_access(request)
    import_errors = []
    import_success = []

    # Test each import in the service_requests module chain
    try:
        from app.modules.service_requests.models.enums import WorkflowCode, WorkflowCategory, EntityCode
        import_success.append("models.enums (WorkflowCode, WorkflowCategory, EntityCode)")
    except Exception as e:
        import traceback
        import_errors.append({"module": "models.enums", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.service_requests.workflows.workflow_interface import PredefinedWorkflow
        import_success.append("workflows.workflow_interface.PredefinedWorkflow")
    except Exception as e:
        import traceback
        import_errors.append({"module": "workflows.workflow_interface", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.service_requests.workflows.generic_workflow import GenericWorkflowStandard
        import_success.append("workflows.generic_workflow.GenericWorkflowStandard")
    except Exception as e:
        import traceback
        import_errors.append({"module": "workflows.generic_workflow", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.service_requests.services.workflow_engine import WorkflowEngine
        import_success.append("services.workflow_engine.WorkflowEngine")
    except Exception as e:
        import traceback
        import_errors.append({"module": "services.workflow_engine", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.service_requests.services.service_request_service import service_request_service
        import_success.append("services.service_request_service")
    except Exception as e:
        import traceback
        import_errors.append({"module": "services.service_request_service", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.service_requests.api.admin_routes import router as admin_router
        import_success.append("api.admin_routes.router")
    except Exception as e:
        import traceback
        import_errors.append({"module": "api.admin_routes", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.service_requests.api import router, agent_router, admin_router
        import_success.append("api.__init__ (router, agent_router, admin_router)")
    except Exception as e:
        import traceback
        import_errors.append({"module": "api.__init__", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    return {
        "status": "diagnostic",
        "service_requests_loaded": "service_requests" in routers_loaded,
        "documents_loaded": "documents" in routers_loaded,
        "import_success": import_success,
        "import_errors": import_errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/debug/entity-locations-import")
async def debug_entity_locations_import(request: Request):
    """Debug endpoint to diagnose entity_locations router import errors"""
    _check_debug_access(request)
    import_errors = []
    import_success = []

    # Test each import in the entity_locations module chain
    try:
        from app.modules.entity_locations.models.entity_location import (
            EntityLocationCreate,
            EntityLocationResponse,
            VALID_ENTITY_CODES,
            VALID_CITIES,
        )
        import_success.append(f"models.entity_location (VALID_ENTITY_CODES={VALID_ENTITY_CODES})")
    except Exception as e:
        import traceback
        import_errors.append({"module": "models.entity_location", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.entity_locations.repositories.entity_location_repository import EntityLocationRepository
        import_success.append("repositories.entity_location_repository.EntityLocationRepository")
    except Exception as e:
        import traceback
        import_errors.append({"module": "repositories.entity_location_repository", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.entity_locations.services.entity_location_service import EntityLocationService
        import_success.append("services.entity_location_service.EntityLocationService")
    except Exception as e:
        import traceback
        import_errors.append({"module": "services.entity_location_service", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.entity_locations.api.entity_location_routes import router
        import_success.append("api.entity_location_routes.router")
    except Exception as e:
        import traceback
        import_errors.append({"module": "api.entity_location_routes", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.entity_locations.api import router as entity_locations_router
        import_success.append("api.__init__.router")
    except Exception as e:
        import traceback
        import_errors.append({"module": "api.__init__", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    return {
        "status": "diagnostic",
        "entity_locations_loaded": "entity-locations" in routers_loaded,
        "import_success": import_success,
        "import_errors": import_errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/debug/funcionario-import")
async def debug_funcionario_import(request: Request):
    """Debug endpoint to diagnose funcionario router import errors"""
    _check_debug_access(request)
    import_errors = []
    import_success = []

    # Test each import in the funcionario module chain
    try:
        from app.modules.auth.dependencies import get_current_user
        import_success.append("auth.dependencies.get_current_user")
    except Exception as e:
        import traceback
        import_errors.append({"module": "auth.dependencies.get_current_user", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.auth.dependencies import require_permissions
        import_success.append("auth.dependencies.require_permissions")
    except Exception as e:
        import traceback
        import_errors.append({"module": "auth.dependencies.require_permissions", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.funcionario.models.verificacion import VerificacionCreate
        import_success.append("funcionario.models.verificacion.VerificacionCreate")
    except Exception as e:
        import traceback
        import_errors.append({"module": "funcionario.models.verificacion", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.funcionario.services.verificacion_service import verificacion_service
        import_success.append("funcionario.services.verificacion_service")
    except Exception as e:
        import traceback
        import_errors.append({"module": "funcionario.services.verificacion_service", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.funcionario.api.verificacion_routes import router
        import_success.append("funcionario.api.verificacion_routes.router")
    except Exception as e:
        import traceback
        import_errors.append({"module": "funcionario.api.verificacion_routes", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    try:
        from app.modules.funcionario.api import router as funcionario_router
        import_success.append("funcionario.api.__init__.router")
    except Exception as e:
        import traceback
        import_errors.append({"module": "funcionario.api.__init__", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()})

    return {
        "status": "diagnostic",
        "funcionario_loaded": "funcionario" in routers_loaded,
        "import_success": import_success,
        "import_errors": import_errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# API v1 info endpoint
@app.get("/api/v1/")
async def api_v1_info():
    """API v1 information and available endpoints"""
    return {
        "message": "TaxasGE API v1",
        "version": settings.api_version,
        "environment": settings.ENVIRONMENT,
        "available_endpoints": {
            "auth": "/api/v1/auth/ - Authentication and authorization",
            "fiscal_services": "/api/v1/fiscal-services/ - 850+ fiscal services catalog",
            "users": "/api/v1/users/ - User profile management (self-service)",
            "admin": "/api/v1/admin/ - Admin diagnostics and migrations (RESTRICTED)",
            "admin_users": "/api/v1/admin/users/ - Admin user management (CRUD, RESTRICTED)",
            "documents": "/api/v1/documents/ - Document upload, OCR, extraction, validation",
            "taxes": "/api/v1/taxes/ - Tax service management (administrative)",
            "declarations": "/api/v1/declarations/ - Tax declarations workflow",
            "payments": "/api/v1/payments/ - BANGE mobile payments integration",
            "translations": "/api/v1/translations/ - System translations (ENUMs, UI, Forms, Messages)",
            "communications": "/api/v1/communications/ - Email, SMS, Push notification services",
            "ai": "/api/v1/ai/ - AI assistant conversations",
            "notifications": "/api/v1/notifications/ - Multi-channel notifications",
            "accountant": "/api/v1/accountant/ - Accountant deadline tracking across client companies"
        },
        "documentation": "/docs" if settings.DEBUG else "Contact admin for API documentation",
        "support": {
            "languages": ["es", "fr", "en"],
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "authentication": "JWT Bearer token",
            "rate_limiting": "1000 requests/hour per user"
        }
    }

# Include API routers - Import individually to handle partial failures
routers_loaded = []
import traceback

# Try to load auth router (Module 1 - Critical)
try:
    logger.debug("🔄 Loading auth router...")
    from app.modules.auth.api import auth_router, _auth_import_error
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])

    # Check if we got the real router or the fallback dummy router
    if _auth_import_error:
        logger.error(f"⚠️ WARNING: Auth router loaded but with FALLBACK endpoints!")
        logger.error(f"⚠️ Original import error: {_auth_import_error}")
        logger.error("⚠️ Login/Register will return 503 instead of 404, but still NOT functional!")
        routers_loaded.append("auth_FALLBACK")
    else:
        # Verify the router has the expected routes
        route_count = len(auth_router.routes)
        if route_count < 5:
            logger.warning(f"⚠️ Auth router has only {route_count} routes - may be incomplete")
            routers_loaded.append("auth_PARTIAL")
        else:
            routers_loaded.append("auth")
            logger.info(f"✅ Auth router loaded successfully ({route_count} routes)")
except Exception as e:
    logger.error(f"❌ CRITICAL: Failed to load auth router: {e}")
    logger.error(f"❌ Auth router traceback:\n{traceback.format_exc()}")
    logger.error("❌ Login/Register endpoints will NOT be available!")

# Try to load fiscal_services router (Module - Fiscal Services - Phase 3)
try:
    from app.modules.fiscal_services.api import fiscal_service_router
    app.include_router(fiscal_service_router, prefix="/api/v1/fiscal-services", tags=["fiscal-services"])
    routers_loaded.append("fiscal_services")
    logger.info("✅ Fiscal services router loaded (850 services catalog)")
except Exception as e:
    logger.error(f"❌ Fiscal services router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load service bundles router (Module - Service Bundles - Phase 3)
try:
    from app.modules.fiscal_services.api.bundle_routes import router as bundle_router
    app.include_router(bundle_router, prefix="/api/v1", tags=["service-bundles"])
    routers_loaded.append("service_bundles")
    logger.info("✅ Service bundles router loaded (zone-based pricing)")
except Exception as e:
    logger.error(f"❌ Service bundles router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load config rules router (Module - Fiscal Config Rules Engine)
try:
    from app.modules.fiscal_services.api.config_rules_routes import router as config_rules_router
    app.include_router(config_rules_router, prefix="/api/v1", tags=["config-rules"])
    routers_loaded.append("config_rules")
    logger.info("✅ Config rules router loaded (specificity-based config engine)")
except Exception as e:
    logger.error(f"❌ Config rules router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load commercial licenses router (Module - OMS)
try:
    from app.modules.fiscal_services.api.license_routes import router as license_router
    app.include_router(license_router, prefix="/api/v1", tags=["commercial-licenses"])
    routers_loaded.append("commercial_licenses")
    logger.info("✅ Commercial licenses router loaded (OMS)")
except Exception as e:
    logger.error(f"❌ Commercial licenses router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load OMS agent processing router (Module - OMS Post-Payment)
try:
    from app.modules.fiscal_services.api.oms_agent_routes import router as oms_agent_router
    app.include_router(oms_agent_router, prefix="/api/v1", tags=["oms-agent-processing"])
    routers_loaded.append("oms_agent")
    logger.info("✅ OMS agent processing router loaded (post-payment queue)")
except Exception as e:
    logger.error(f"❌ OMS agent processing router failed: {e}")
    logger.error(traceback.format_exc())

# Bundle workflow routes (OMS citizen-facing — BUNDLE_PAYMENT)
try:
    from app.modules.fiscal_services.api.bundle_workflow_routes import router as bundle_workflow_router
    app.include_router(bundle_workflow_router, prefix="/api/v1", tags=["bundle-workflow"])
    routers_loaded.append("bundle_workflow")
    logger.info("✅ Bundle workflow router loaded (OMS citizen payments)")
except Exception as e:
    logger.error(f"❌ Bundle workflow router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load users router (Module - Users System)
try:
    from app.modules.users.api import user_routes
    app.include_router(user_routes, prefix="/api/v1/users", tags=["users"])
    routers_loaded.append("users")
    logger.info("✅ Users router loaded (profile management)")
except Exception as e:
    logger.error(f"❌ Users router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load admin routers (Module - Admin System)
try:
    from app.modules.admin.api import admin_router, user_management_router, monitoring_router
    app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin-diagnostics"])
    app.include_router(user_management_router, prefix="/api/v1/admin/users", tags=["admin-user-management"])
    app.include_router(monitoring_router, prefix="/api/v1/admin/monitoring", tags=["admin-monitoring"])
    routers_loaded.extend(["admin", "admin_users", "admin_monitoring"])
    logger.info("✅ Admin routers loaded (diagnostics + user management + monitoring)")
except Exception as e:
    logger.error(f"❌ Admin routers failed: {e}")
    logger.error(traceback.format_exc())

# Try to load two_factor router (TASK-M01-011)
try:
    from app.modules.auth.api import two_factor_router
    app.include_router(two_factor_router, prefix="/api/v1/auth", tags=["two-factor-authentication"])
    routers_loaded.append("two_factor")
    logger.info("✅ Two-Factor Authentication router loaded")
except Exception as e:
    logger.error(f"❌ Two-Factor router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load homepage router (Module - Homepage Statistics & Category Directory)
try:
    from app.modules.homepage import homepage_router
    app.include_router(homepage_router, prefix="/api/v1/homepage", tags=["homepage"])
    routers_loaded.append("homepage")
    logger.info("✅ Homepage router loaded (v2.0 - optimized 3-tier architecture)")
except Exception as e:
    logger.error(f"❌ Homepage router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load dashboards router (Module - Looker Studio Community Connector backend)
# Phase B.1 skeleton — exposes mv_treasury_daily_kpis as 'recaudacion' dashboard.
# Plan: .claude/plans/LOOKER_STUDIO_COMMUNITY_CONNECTOR_PLAN.md
try:
    from app.modules.dashboards import dashboards_router
    app.include_router(dashboards_router, prefix="/api/v1/dashboards", tags=["dashboards"])
    routers_loaded.append("dashboards")
    logger.info("✅ Dashboards router loaded (B.1 — Looker Studio connector backend)")
except Exception as e:
    logger.error(f"❌ Dashboards router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load permissions routers (Module 04 - RBAC Permissions System)
try:
    from app.modules.permissions import permission_router, role_router, user_permission_router
    app.include_router(permission_router, prefix="/api/v1", tags=["permissions"])
    app.include_router(role_router, prefix="/api/v1", tags=["roles"])
    app.include_router(user_permission_router, prefix="/api/v1", tags=["user-permissions"])
    routers_loaded.extend(["permissions", "roles", "user_permissions"])
    logger.info("✅ Permissions routers loaded (RBAC system)")
except Exception as e:
    logger.error(f"❌ Permissions routers failed: {e}")
    logger.error(traceback.format_exc())

# Try to load assignment router (Module - Assignment System)
logger.info("🔄 Loading assignment router...")
try:
    from app.modules.assignment.api.assignment_routes import router as assignment_router
    logger.info(f"📦 Assignment router imported, routes: {len(assignment_router.routes)}")
    # Note: assignment_routes already has prefix="/api/v1/assignments" defined in the router
    app.include_router(assignment_router, tags=["assignments"])
    routers_loaded.append("assignments")
    logger.info("✅ Assignment router loaded successfully")
except Exception as e:
    logger.error(f"❌ Assignment router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load supervisor router (Module - Supervisor Dashboard & Team Management)
try:
    from app.modules.assignment.api.supervisor_routes import router as supervisor_router
    # Note: supervisor_routes already has prefix="/api/v1/supervisor" defined
    app.include_router(supervisor_router, tags=["supervisor"])
    routers_loaded.append("supervisor")
    logger.info("✅ Supervisor router loaded (dashboard, team management, rules)")
except Exception as e:
    logger.error(f"❌ Supervisor router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load statistics router (Module - Analytics & Reporting)
try:
    from app.modules.assignment.api.statistics_routes import router as statistics_router
    # Note: statistics_routes already has prefix="/api/v1/statistics" defined
    app.include_router(statistics_router, tags=["statistics"])
    routers_loaded.append("statistics")
    logger.info("✅ Statistics router loaded (analytics, performance metrics)")
except Exception as e:
    logger.error(f"❌ Statistics router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load agent profile router (Module - Agent Profiles v2)
try:
    from app.modules.agents.api.profile_routes import router as agent_profile_router
    app.include_router(agent_profile_router, prefix="/api/v1/agents", tags=["agent-profiles"])
    routers_loaded.append("agent-profiles")
    logger.info("✅ Agent profile router loaded")
except Exception as e:
    logger.error(f"❌ Agent profile router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load unified analyst router (Dynamic Agent Architecture - Phase 3)
try:
    from app.modules.agents.api.analyst_routes import router as analyst_router
    app.include_router(analyst_router, prefix="/api/v1/agents", tags=["analyst"])
    routers_loaded.append("analyst")
    logger.info("✅ Unified analyst router loaded (POST /agents/analyst/ask)")
except Exception as e:
    logger.error(f"❌ Unified analyst router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load documents router (Module - Documents System)
try:
    from app.modules.documents.api import document_routes
    app.include_router(document_routes, prefix="/api/v1/documents", tags=["documents"])
    routers_loaded.append("documents")
    logger.info("✅ Documents router loaded (OCR, extraction, validation)")
except Exception as e:
    logger.error(f"❌ Documents router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load service requests router (Module - Service Requests Workflow)
try:
    from app.modules.service_requests.api import router as service_requests_router
    from app.modules.service_requests.api import agent_router as service_requests_agent_router
    from app.modules.service_requests.api import admin_router as service_requests_admin_router
    from app.modules.service_requests.api import wizard_session_router as service_requests_wizard_router
    from app.modules.service_requests.api.appointment_routes import router as service_requests_appointment_router
    from app.modules.service_requests.api.cron_routes import router as service_requests_cron_router
    app.include_router(service_requests_router, prefix="/api/v1", tags=["service-requests"])
    app.include_router(service_requests_agent_router, prefix="/api/v1", tags=["service-requests-agent"])
    app.include_router(service_requests_admin_router, prefix="/api/v1", tags=["service-requests-admin"])
    app.include_router(service_requests_wizard_router, prefix="/api/v1", tags=["wizard-sessions"])
    app.include_router(service_requests_appointment_router, prefix="/api/v1", tags=["service-requests-appointments"])
    app.include_router(service_requests_cron_router, prefix="/api/v1/internal", tags=["cron-jobs"])
    routers_loaded.append("service_requests")
    routers_loaded.append("service_requests_agent")
    routers_loaded.append("service_requests_admin")
    routers_loaded.append("wizard_sessions")
    routers_loaded.append("service_requests_appointments")
    routers_loaded.append("service_requests_cron")
    logger.info("✅ Service Requests router loaded (citizen, agent, admin, wizard, appointments, cron)")
except Exception as e:
    logger.error(f"❌ Service Requests router failed: {e}")
    logger.error(traceback.format_exc())

# --- Enrichment (Gemini auto-enrichment) ---
try:
    from app.modules.enrichment.api.enrichment_routes import router as enrichment_router
    app.include_router(enrichment_router, prefix="/api/v1", tags=["enrichment"])
    routers_loaded.append("enrichment")
    logger.info("✅ Enrichment router loaded")
except Exception as e:
    logger.error(f"❌ Enrichment router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load batch requests router (Module - Batch Service Requests)
try:
    from app.modules.batch_requests.api import router as batch_requests_router
    app.include_router(batch_requests_router, prefix="/api/v1", tags=["batch-requests"])
    routers_loaded.append("batch_requests")
    logger.info("✅ Batch Requests router loaded (bulk submission of N requests)")
except Exception as e:
    logger.error(f"❌ Batch Requests router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load verified identifiers router (Module - External Document Verification)
try:
    from app.modules.verified_identifiers.api import router as verified_identifiers_router
    app.include_router(verified_identifiers_router, prefix="/api/v1", tags=["verified-identifiers"])
    routers_loaded.append("verified_identifiers")
    logger.info("✅ Verified Identifiers router loaded (external document verification)")
except Exception as e:
    logger.error(f"❌ Verified Identifiers router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load declarations router (Module - Declarations System - Phase 3)
try:
    from app.modules.declarations.api import declaration_router
    app.include_router(declaration_router, prefix="/api/v1/declarations", tags=["declarations"])
    routers_loaded.append("declarations")
    logger.info("✅ Declarations router loaded (28 types, MVP Phase 3.1)")
except Exception as e:
    logger.error(f"❌ Declarations router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load accountant batch operations router (Module - Batch Operations)
try:
    from app.modules.declarations.api.accountant_batch_routes import router as accountant_batch_router
    app.include_router(accountant_batch_router, prefix="/api/v1/accountant", tags=["accountant-batch"])
    routers_loaded.append("accountant_batch")
    logger.info("✅ Accountant batch operations router loaded (batch create, submit, reports)")
except Exception as e:
    logger.error(f"❌ Accountant batch operations router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load companies router (Module - Companies System - Phase 3)
try:
    from app.modules.companies.api import company_router
    app.include_router(company_router, prefix="/api/v1/companies", tags=["companies"])
    routers_loaded.append("companies")
    logger.info("✅ Companies router loaded (business management + classification + dashboard + ministry)")
except Exception as e:
    logger.error(f"❌ Companies router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load public companies directory (no auth required)
try:
    from app.modules.companies.api import public_router as company_public_router
    app.include_router(company_public_router, prefix="/api/v1/public/companies", tags=["public-directory"])
    routers_loaded.append("companies_public")
    logger.info("✅ Public company directory router loaded (annuaire)")
except Exception as e:
    logger.error(f"❌ Public company directory router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load payments router (Module - Payments System - Phase 3 - BANGE Integration)
try:
    from app.modules.payments.api import payment_router
    app.include_router(payment_router, prefix="/api/v1/payments", tags=["payments"])
    routers_loaded.append("payments")
    logger.info("✅ Payments router loaded (BANGE mobile payments)")
except Exception as e:
    logger.error(f"❌ Payments router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load receipt verification router (PUBLIC - no auth required)
try:
    from app.modules.payments.api import verify_router
    app.include_router(verify_router, prefix="/api/v1/verify", tags=["verification"])
    routers_loaded.append("verify")
    logger.info("✅ Verification router loaded (receipt authenticity)")
except Exception as e:
    logger.error(f"❌ Verification router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load webhooks router (Module - Webhooks System - Phase 3 - BANGE Callbacks)
try:
    from app.modules.webhooks.api import webhook_router
    app.include_router(webhook_router, prefix="/api/v1/webhooks", tags=["webhooks"])
    routers_loaded.append("webhooks")
    logger.info("✅ Webhooks router loaded (BANGE callbacks + reconciliation)")
except Exception as e:
    logger.error(f"❌ Webhooks router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load entity translations router FIRST (Admin CRUD for ministry/sector/category translations)
# IMPORTANT: Must be loaded BEFORE translation_router to avoid /{translation_id} route conflict
try:
    from app.modules.translations.api.entity_translation_routes import router as entity_translation_router
    app.include_router(entity_translation_router, prefix="/api/v1", tags=["entity-translations"])
    routers_loaded.append("entity-translations")
    logger.info("✅ Entity translations router loaded (Ministries, Sectors, Categories)")
except Exception as e:
    logger.error(f"❌ Entity translations router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load frontend translations router SECOND (Admin CRUD for frontend UI JSON translations)
# IMPORTANT: Must be loaded BEFORE translation_router to avoid /{translation_id} route conflict
try:
    from app.modules.translations.api.frontend_translation_routes import router as frontend_translation_router
    app.include_router(frontend_translation_router, prefix="/api/v1", tags=["frontend-translations"])
    routers_loaded.append("frontend-translations")
    logger.info("✅ Frontend translations router loaded (UI JSON sync)")
except Exception as e:
    logger.error(f"❌ Frontend translations router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load translations router LAST (Module - Translations System - System translations)
# IMPORTANT: Must be loaded AFTER entity/frontend routers because it has /{translation_id} route
try:
    from app.modules.translations.api.translation_routes import router as translation_router
    app.include_router(translation_router, prefix="/api/v1", tags=["translations"])
    routers_loaded.append("translations")
    logger.info("✅ Translations router loaded (ENUMs, UI, Forms, Messages)")
except Exception as e:
    logger.error(f"❌ Translations router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load ENUM management router (Module - Translations System - ENUM value management)
try:
    from app.modules.translations.api.enum_routes import router as enum_router
    app.include_router(enum_router, prefix="/api/v1", tags=["enum-management"])
    routers_loaded.append("enums")
    logger.info("✅ ENUM management router loaded (add/modify/archive ENUM values)")
except Exception as e:
    logger.error(f"❌ ENUM management router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load communications router (Module - Communications System - Email/SMS/Push)
try:
    from app.modules.communications.api import router as communication_router, email_templates_router, push_templates_router
    app.include_router(communication_router, prefix="/api/v1", tags=["communications"])
    app.include_router(email_templates_router, prefix="/api/v1", tags=["email-templates"])
    app.include_router(push_templates_router, prefix="/api/v1", tags=["push-templates"])
    routers_loaded.append("communications")
    routers_loaded.append("email_templates")
    routers_loaded.append("push_templates")
    logger.info("✅ Communications router loaded (Email, SMS, Push notifications)")
    logger.info("✅ Email Templates router loaded (Template management)")
    logger.info("✅ Push Templates router loaded (Push notification template management)")
except Exception as e:
    logger.error(f"❌ Communications router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load chatbot router (Module - AI-powered assistance)
try:
    from app.modules.chatbot import chatbot_router
    app.include_router(chatbot_router, prefix="/api/v1/chatbot", tags=["chatbot"])
    routers_loaded.append("chatbot")
    logger.info("✅ Chatbot router loaded (AI assistance, search, recommendations)")
except Exception as e:
    logger.error(f"❌ Chatbot router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load user documents router (Module - Document Vault / Mes Documents)
try:
    from app.modules.user_documents import user_documents_router
    app.include_router(user_documents_router, prefix="/api/v1/user-documents", tags=["user-documents"])
    routers_loaded.append("user_documents")
    logger.info("✅ User Documents router loaded (document vault, AI classification, alerts)")
except Exception as e:
    logger.error(f"❌ User Documents router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load template routers (Document and Procedure Templates)
try:
    from app.modules.fiscal_services.api.template_routes import (
        document_template_router,
        procedure_template_router,
    )
    app.include_router(document_template_router, prefix="/api/v1/document-templates", tags=["document-templates"])
    app.include_router(procedure_template_router, prefix="/api/v1/procedure-templates", tags=["procedure-templates"])
    routers_loaded.extend(["document_templates", "procedure_templates"])
    logger.info("✅ Template routers loaded (document + procedure templates)")
except Exception as e:
    logger.error(f"❌ Template routers failed: {e}")
    logger.error(traceback.format_exc())

# Try to load audit logs router (Admin - Audit Trail)
try:
    from app.modules.admin.api.audit_routes import router as audit_router, user_audit_router
    app.include_router(audit_router, prefix="/api/v1/audit-logs", tags=["audit-logs"])
    app.include_router(user_audit_router, prefix="/api/v1/users", tags=["user-audit-logs"])
    routers_loaded.append("audit_logs")
    logger.info("✅ Audit logs router loaded (audit trail)")
except Exception as e:
    logger.error(f"❌ Audit logs router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load accountant router (Accountant - Deadline Tracking)
try:
    from app.modules.accountant import accountant_router
    app.include_router(accountant_router, prefix="/api/v1/accountant", tags=["accountant-deadline-tracking"])
    routers_loaded.append("accountant")
    logger.info("✅ Accountant router loaded (deadline tracking for client companies)")
except Exception as e:
    logger.error(f"❌ Accountant router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load support router (Module - Support Ticketing System)
try:
    from app.modules.support.api import router as support_router
    app.include_router(support_router, prefix="/api/v1", tags=["support"])
    routers_loaded.append("support")
    logger.info("✅ Support router loaded (ticketing system)")
except Exception as e:
    logger.error(f"❌ Support router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load entity locations router (Module - Entity Locations Management)
try:
    from app.modules.entity_locations.api import router as entity_locations_router
    app.include_router(entity_locations_router, prefix="/api/v1", tags=["entity-locations"])
    routers_loaded.append("entity-locations")
    logger.info("✅ Entity locations router loaded")
except Exception as e:
    logger.error(f"❌ Entity locations router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load cities router (Module - Cities and Entities Management)
try:
    from app.modules.cities.api import router as cities_router
    app.include_router(cities_router, prefix="/api/v1", tags=["cities"])
    routers_loaded.append("cities")
    logger.info("✅ Cities router loaded")
except Exception as e:
    logger.error(f"❌ Cities router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load funcionario verification router (Module - Civil Servant Verification)
try:
    from app.modules.funcionario.api import router as funcionario_router
    app.include_router(funcionario_router, prefix="/api/v1", tags=["funcionario-verification"])
    routers_loaded.append("funcionario")
    logger.info("✅ Funcionario verification router loaded")
except Exception as e:
    logger.error(f"❌ Funcionario verification router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load field inspections router (Module - Field Inspections)
try:
    # CRITICAL: Import mission_routes DIRECTLY (not via __init__) to avoid
    # circular import that causes empty router registration.
    from app.modules.inspections.api.mission_routes import router as inspection_mission_router
    from app.modules.inspections.api.analytics_routes import router as inspection_analytics_router
    from app.modules.inspections.api.filter_export_routes import router as inspection_filter_export_router
    from app.modules.inspections.api.inspection_routes import router as inspections_router

    # CRITICAL ORDER: mission_router FIRST — its prefix /inspections/missions
    # must be matched before inspections_router's /inspections/{inspection_id}
    app.include_router(inspection_mission_router, prefix="/api/v1", tags=["inspection-missions"])
    app.include_router(inspection_analytics_router, prefix="/api/v1", tags=["inspection-analytics"])
    app.include_router(inspection_filter_export_router, prefix="/api/v1", tags=["inspection-filters-export"])
    app.include_router(inspections_router, prefix="/api/v1", tags=["field-inspections"])
    routers_loaded.append("field_inspections")
    logger.info("✅ Field inspections router loaded (22 + 9 + 6 + 7 = 44 endpoints)")
except Exception as e:
    logger.error(f"❌ Field inspections router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load menu config router (Module - Dynamic Menu Configuration)
try:
    from app.modules.menu_config.api import router as menu_config_router
    app.include_router(menu_config_router, prefix="/api/v1", tags=["menu-configuration"])
    routers_loaded.append("menu-config")
    logger.info("✅ Menu configuration router loaded")
except Exception as e:
    logger.error(f"❌ Menu configuration router failed: {e}")
    logger.error(traceback.format_exc())

# Try to load legal router (Phase 10/B — Privacy Policy + Terms versions + acceptance)
try:
    from app.modules.legal.api.legal_routes import router as legal_router
    app.include_router(legal_router, prefix="/api/v1", tags=["legal"])
    routers_loaded.append("legal")
    logger.info("✅ Legal router loaded (versions + acceptance)")
except Exception as e:
    logger.error(f"❌ Legal router failed: {e}")
    logger.error(traceback.format_exc())

if routers_loaded:
    logger.info(f"✅ {len(routers_loaded)} API routers loaded: {', '.join(routers_loaded)}")
else:
    logger.error("❌ No API routers could be loaded!")

# WebSocket routes (no /api/v1 prefix — direct path /ws/admin)
try:
    from app.core.ws_routes import router as ws_router
    app.include_router(ws_router)
    logger.info("✅ WebSocket admin endpoint registered (/ws/admin)")
except Exception as e:
    logger.warning(f"⚠️ WebSocket routes failed (non-blocking): {e}")

# NOTE: functions_framework wrapper removed in v1.1.8
# Cloud Run uses uvicorn directly with app.main:app
# The functions_framework decorator was causing 422 errors (expecting 'func' query param)

# Direct FastAPI server (for local development)
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        access_log=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )