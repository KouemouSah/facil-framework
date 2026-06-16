"""Facil backend — minimal foundation app (Phase D / D1).

Hosts the config-store only: SQLAlchemy async engine + the layered resolver +
the token-gated admin settings API + /health. Business modules / full auth /
provider registry land in later D-phases.
"""

from __future__ import annotations

import contextlib
import logging
import os

from fastapi import FastAPI, Response, status
from sqlalchemy import text

from app.api import admin_providers, admin_settings, auth, rbac
from app.config import get_settings
from app.config_store import repository as repo
from app.config_store.resolver import ConfigResolver
from app.core.module_registry import enabled_from_env, load_modules
from app.core.providers.llm_router import LLMRouter
from app.core.providers.registry import default_registry
from app.db.engine import Database

# Code defaults — the lowest layer of the resolver (overridden by file/DB/env).
# Branding = app-shell theming/identity (distinct from the organization module's
# business identity); admin-editable at runtime via /admin/settings.
_DEFAULTS: dict[str, object] = {
    "branding.app_name": "Facil",
    "branding.tagline": "",
    "branding.logo_url": "",
    "branding.logo_dark_url": "",
    "branding.favicon_url": "",
    "branding.login_background_url": "",
    "branding.primary_color": "#2563eb",
    "branding.secondary_color": "#7c3aed",
    "branding.theme_mode": "light",
    "branding.default_locale": "en",
    "branding.supported_locales": ["en", "fr", "es"],
    "branding.support_email": "",
    "branding.support_url": "",
    # Auth methods the backend will VERIFY (CSV). Native is always present for
    # self-service issuance; add `keycloak_oidc` (with auth.oidc.* set) to also
    # accept IdP-issued tokens. Issuance for OIDC happens at the IdP (auth-code).
    "auth.methods": "native",
    "auth.oidc.issuer": "",
    "auth.oidc.jwks_uri": "",
    "auth.oidc.audience": "",
}

logger = logging.getLogger(__name__)


def _build_verifiers(app: FastAPI, resolver) -> list:
    """The token-verifier chain: native + any configured OIDC verifiers."""
    verifiers = [app.state.auth]
    methods = resolver.resolve("auth.methods", "native")
    if isinstance(methods, str):
        methods = [m.strip() for m in methods.split(",") if m.strip()]
    if "keycloak_oidc" in (methods or []):
        issuer = resolver.resolve("auth.oidc.issuer", "")
        jwks_uri = resolver.resolve("auth.oidc.jwks_uri", "")
        # Discovery: the issuer alone is enough (jwks_uri auto-derived from
        # .well-known/openid-configuration). jwks_uri stays an optional override.
        if issuer or jwks_uri:
            verifiers.append(app.state.registry.build("auth", "keycloak_oidc", {
                "issuer": issuer,
                "jwks_uri": jwks_uri,
                "discovery_url": resolver.resolve("auth.oidc.discovery_url", "") or None,
                "audience": resolver.resolve("auth.oidc.audience", "") or None,
                # RFC 7662 introspection (near-instant IdP offboarding) — opt-in,
                # needs a confidential client (id + secret from secrets store).
                "introspection": bool(resolver.resolve("auth.oidc.introspection", False)),
                "client_id": resolver.resolve("auth.oidc.client_id", "") or None,
                "client_secret": resolver.resolve("auth.oidc.client_secret", "") or None,
            }))
        else:
            logger.warning("auth.methods includes keycloak_oidc but neither "
                           "auth.oidc.issuer nor auth.oidc.jwks_uri is set — "
                           "OIDC verify disabled.")
    return verifiers


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = Database(settings.async_database_url)
    app.state.db = db

    resolver = ConfigResolver(defaults=_DEFAULTS, file_cfg={}, env=os.environ)
    # Load the DB layer if the schema is present (first boot may be pre-migration).
    with contextlib.suppress(Exception):
        async with db.session_factory() as session:
            resolver.set_db(await repo.active_map(session))
    app.state.resolver = resolver
    app.state.registry = default_registry()
    app.state.llm_router = LLMRouter(resolver, app.state.registry)
    # Native JWT auth provider (secret from JWT_SECRET env; issuer = app name).
    app.state.auth = app.state.registry.build(
        "auth", "native",
        {"issuer": resolver.resolve("branding.app_name", "Facil")})
    # Token-verifier chain (native + optional OIDC IdPs) consumed by require_auth.
    app.state.auth_verifiers = _build_verifiers(app, resolver)
    # Shared cache / state (D4.12): Redis when REDIS_URL is set (global across
    # replicas — required at scale for rate-limit + OIDC revocation correctness),
    # else in-process. Backs the federation cache, rate-limiter and revocation set.
    from app.core.cache import build_cache
    app.state.cache = build_cache(os.environ.get("REDIS_URL"))

    # RBAC seeding — sync the permission catalog + the active profile's global
    # roles (idempotent). Suppressed pre-migration (schema may be absent on first
    # boot); RBAC_SEED_ON_BOOT=0 disables it for operators who seed out-of-band.
    if os.environ.get("RBAC_SEED_ON_BOOT", "1") != "0":
        from app.rbac.seed import seed_roles
        with contextlib.suppress(Exception):
            async with db.session_factory() as session:
                await seed_roles(session, profile=resolver.resolve("profile", "empty"))
                await session.commit()

    yield
    with contextlib.suppress(Exception):
        await app.state.cache.close()
    await db.dispose()


app = FastAPI(title="Facil Backend", version="0.1.0", lifespan=lifespan)

# Reject oversized request bodies early (DoS / resource consumption — API4).
_MAX_BODY_BYTES = int(os.environ.get("MAX_REQUEST_BYTES", str(1024 * 1024)))


@app.middleware("http")
async def _limit_body_size(request, call_next):
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > _MAX_BODY_BYTES:
                return Response(status_code=413)  # Content Too Large
        except ValueError:
            pass
    return await call_next(request)

# Core (always-on) routers — config-store + provider registry admin.
app.include_router(admin_settings.router)
app.include_router(admin_providers.router)
app.include_router(auth.router)
app.include_router(rbac.router)
# Business modules — included only if listed in MODULES_ENABLED (Phase A.5).
# Not-yet-ported modules are skipped (warned); present-but-broken ones fail closed.
load_modules(app, enabled=enabled_from_env())


@app.get("/health")
async def health(response: Response) -> dict:
    db_ok = False
    with contextlib.suppress(Exception):
        async with app.state.db.session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if db_ok else "degraded",
            "database": db_ok, "service": "facil-backend"}
