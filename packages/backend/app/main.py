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

from app.api import (
    admin_accounts,
    admin_branding,
    admin_federation,
    admin_providers,
    admin_settings,
    auth,
    rbac,
    saved_views,
    system,
)
from app.scim import api as scim_api
from app.modules.reference.api import router as reference_router
from app.modules.party.api import router as party_router
from app.branding import resolver_defaults as branding_defaults
from app.config import get_settings
from app.config_store import repository as repo
from app.config_store.resolver import ConfigResolver
from app.core.boot import run_boot_step
from app.core.module_registry import enabled_from_env, load_modules
from app.core.providers.llm_router import LLMRouter
from app.core.providers.registry import default_registry
from app.db.engine import Database

# Code defaults — the lowest layer of the resolver (overridden by file/DB/env).
# Branding = app-shell theming/identity (distinct from the organization module's
# business identity); admin-editable at runtime via /admin/branding. The branding
# defaults live in app.branding (single source of truth, reused here).
_DEFAULTS: dict[str, object] = {
    **branding_defaults(),
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
        audience = resolver.resolve("auth.oidc.audience", "") or None
        # Fail-secure: without an audience the verifier disables `verify_aud` and
        # would accept ANY token signed by the realm (e.g. minted for another
        # client) — refuse to build it rather than degrade authentication.
        if (issuer or jwks_uri) and not audience:
            logger.error("auth.methods includes keycloak_oidc but auth.oidc.audience "
                         "is empty — refusing the OIDC verifier (would skip audience "
                         "validation). Set auth.oidc.audience to the client id.")
        elif issuer or jwks_uri:
            verifiers.append(app.state.registry.build("auth", "keycloak_oidc", {
                "issuer": issuer,
                "jwks_uri": jwks_uri,
                "discovery_url": resolver.resolve("auth.oidc.discovery_url", "") or None,
                "audience": audience,
                # RFC 7662 introspection (near-instant IdP offboarding) — opt-in,
                # needs a confidential client (id + secret from secrets store).
                "introspection": bool(resolver.resolve("auth.oidc.introspection", False)),
                "introspection_fail_closed": bool(
                    resolver.resolve("auth.oidc.introspection_fail_closed", False)),
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
    # S2: in secrets=openbao mode, pull the infra creds (DATABASE_URL + MinIO SA)
    # from the vault BEFORE settings/DB are built — the vault is the fresher source
    # (survives a password rotation that left the env stale). No-op in env_file mode
    # or when SECRETS_VAULT_HYDRATE=0; hard-fails only if SECRETS_VAULT_REQUIRED=1.
    import app.config as _config
    from app.core.secrets_bootstrap import hydrate_secrets_from_vault
    report = await hydrate_secrets_from_vault()
    app.state.secrets_report = report  # observable post-boot (surfaced in /health)
    if report.get("mutated"):
        _config._settings = None  # re-read settings from the hydrated env
        logger.info("secrets hydrated from vault: %s", ", ".join(report["keys"]))

    settings = get_settings()
    db = Database(settings.async_database_url)
    app.state.db = db

    resolver = ConfigResolver(defaults=_DEFAULTS, file_cfg={}, env=os.environ)

    # Load the DB layer if the schema is present (first boot may be pre-migration).
    # A silent failure here would disable OIDC (issuer/audience come from the DB
    # config) without any signal — so it is logged loud and surfaced in /health.
    async def _load_config_db():
        async with db.session_factory() as session:
            resolver.set_db(await repo.active_map(session))
    app.state.config_db_loaded = await run_boot_step("config-store-db-load", _load_config_db)
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
    app.state.cache = await build_cache(os.environ.get("REDIS_URL"))

    # Secrets provider enrollment — make OpenBao the default `secrets` provider when
    # its AppRole creds are present, so resolve_secret reads the vault instead of
    # silently falling back to env. The label is observable in /health; a failed
    # enrollment is loud (and fail-closed when the vault is required). Idempotent;
    # SECRETS_PROVIDER_SEED_ON_BOOT=0 disables it.
    from app.core.providers.secret_enrollment import enroll_secrets_provider
    app.state.secrets_provider = await enroll_secrets_provider(
        db, env=os.environ, db_ready=app.state.config_db_loaded)

    # RBAC seeding — sync the permission catalog + the active profile's global
    # roles (idempotent). Loud on failure (benign pre-migration vs real prod error);
    # RBAC_SEED_ON_BOOT=0 disables it for operators who seed out-of-band.
    if os.environ.get("RBAC_SEED_ON_BOOT", "1") != "0":
        from app.rbac.seed import seed_roles

        async def _seed_rbac():
            async with db.session_factory() as session:
                await seed_roles(session, profile=resolver.resolve("profile", "empty"))
                await session.commit()
        await run_boot_step("rbac-seed", _seed_rbac)

    # Reference master data (countries/currencies/regions) — idempotent upsert by
    # ISO code. Same guard as RBAC; REFERENCE_SEED_ON_BOOT=0 disables it.
    if os.environ.get("REFERENCE_SEED_ON_BOOT", "1") != "0":
        from app.modules.reference.seed import seed_reference

        async def _seed_reference():
            async with db.session_factory() as session:
                await seed_reference(session)
        await run_boot_step("reference-seed", _seed_reference)

    # F.3 backfill: link each Company to a Party + Address (legacy text -> pillar).
    # Runs AFTER the reference seed so country/currency codes resolve; idempotent
    # (only orgs without party_id). ORG_BACKFILL_ON_BOOT=0 disables it.
    if os.environ.get("ORG_BACKFILL_ON_BOOT", "1") != "0":
        from app.modules.organization.backfill import backfill_org_party

        async def _backfill_org():
            async with db.session_factory() as session:
                await backfill_org_party(session)
        await run_boot_step("org-party-backfill", _backfill_org)

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
app.include_router(admin_accounts.router)
app.include_router(admin_federation.router)
app.include_router(admin_branding.router)
app.include_router(auth.router)
app.include_router(rbac.router)
app.include_router(saved_views.router)
app.include_router(scim_api.router)
app.include_router(system.router)
# Reference master data (countries/currencies/regions) is foundational — org/site
# depend on it — so it is a CORE router, always mounted (not a MODULES_ENABLED module).
app.include_router(reference_router)
# Party directory (Odoo res.partner) — foundational pillar, also core.
app.include_router(party_router)
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
    # Surface the secrets posture so a vault fallback is observable post-boot, not
    # just a one-shot startup log (no secret values — only the source label).
    secrets_source = getattr(app.state, "secrets_report", {}).get("source", "unknown")
    # secrets_provider = which provider resolve_secret actually uses (enrollment),
    # distinct from secrets_source (infra-cred hydration). "env-fallback" with a
    # vault expected = a silent misconfiguration made visible. cache = redis|memory
    # (memory while REDIS_URL is set + >1 replica ⇒ revocation/rate-limit per-replica).
    cache = getattr(getattr(app.state, "cache", None), "backend", "unknown")
    return {"status": "ok" if db_ok else "degraded",
            "database": db_ok, "secrets_source": secrets_source,
            "secrets_provider": getattr(app.state, "secrets_provider", "unknown"),
            "config_db": getattr(app.state, "config_db_loaded", None),
            "cache": cache, "service": "facil-backend"}
