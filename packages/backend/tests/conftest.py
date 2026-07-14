"""Test fixtures — the app wired to a throwaway SQLite DB (no live Postgres)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    """Yield (AsyncClient, Database) with a fresh SQLite schema + admin token."""
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-0123456789abcdef0123456789")
    import app.config as cfg
    cfg._settings = None  # reset cached settings so ADMIN_TOKEN is read

    from app.config_store import repository as repo
    from app.config_store.resolver import ConfigResolver
    from app.core.module_registry import import_module_models
    from app.core.providers.llm_router import LLMRouter
    from app.core.providers.registry import default_registry
    from app.db.base import Base
    from app.db.engine import Database
    from app.main import app

    from app.identity import models as _account_models  # noqa: F401 (register Account)
    from app.auth import models as _cred_models  # noqa: F401 (register Credential)
    from app.rbac import models as _rbac_models  # noqa: F401 (register RBAC tables)
    import_module_models()  # register module tables before create_all
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'test.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.db = db
    # Self-registration is off by default in prod (opt-in); the test harness is an
    # opted-in tenant so the many suites that seed accounts via POST /auth/register
    # keep working. The default-off gating is covered explicitly in test_system_api.
    resolver = ConfigResolver(
        defaults={"branding.app_name": "Facil", "auth.self_registration_enabled": True},
        env={})
    async with db.session_factory() as s:
        resolver.set_db(await repo.active_map(s))
    app.state.resolver = resolver
    app.state.registry = default_registry()
    from app.core.schema.registry import default_schema_registry
    app.state.schema_registry = default_schema_registry()
    app.state.llm_router = LLMRouter(resolver, app.state.registry)
    app.state.auth = app.state.registry.build("auth", "native", {"issuer": "facil"})
    from app.core.cache import MemoryCache
    app.state.cache = MemoryCache()  # fresh per test (rate-limit/revocation/fed cache)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db
    await db.dispose()
    cfg._settings = None


AUTH = {"X-Admin-Token": "test-token"}


@pytest_asyncio.fixture
async def session(tmp_path):
    """Bare AsyncSession against a throwaway SQLite DB with the FULL schema
    (all module tables registered) — for tests that exercise repository/service
    functions directly, without going through the HTTP layer or `client`'s app
    wiring (config resolver, providers, auth, ...) that those tests don't need."""
    from app.core.module_registry import import_module_models
    from app.db.base import Base
    from app.db.engine import Database

    from app.identity import models as _account_models  # noqa: F401 (register Account)
    from app.auth import models as _cred_models  # noqa: F401 (register Credential)
    from app.rbac import models as _rbac_models  # noqa: F401 (register RBAC tables)
    import_module_models()  # register module tables (organization, location, ...)

    db = Database(f"sqlite+aiosqlite:///{tmp_path/'session_test.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with db.session_factory() as s:
        yield s
    await db.dispose()


@pytest_asyncio.fixture
async def org_a(session):
    """A root organisation (no parent), unrelated to org_b."""
    from app.modules.organization.models import Organization
    org = Organization(code="org-a", legal_name="Organisation A")
    session.add(org)
    await session.flush()
    return org


@pytest_asyncio.fixture
async def org_b(session):
    """A second root organisation, unrelated to org_a — the isolation target."""
    from app.modules.organization.models import Organization
    org = Organization(code="org-b", legal_name="Organisation B")
    session.add(org)
    await session.flush()
    return org


@pytest_asyncio.fixture
async def org_child_of_a(session, org_a):
    """A child organisation of org_a (parent_id = org_a.id) — for inheritance."""
    from app.modules.organization.models import Organization
    org = Organization(code="org-a-child", legal_name="Organisation A Child",
                       parent_id=org_a.id)
    session.add(org)
    await session.flush()
    return org
