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
    import_module_models()  # register module tables before create_all
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'test.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.db = db
    resolver = ConfigResolver(defaults={"branding.app_name": "Facil"}, env={})
    async with db.session_factory() as s:
        resolver.set_db(await repo.active_map(s))
    app.state.resolver = resolver
    app.state.registry = default_registry()
    app.state.llm_router = LLMRouter(resolver, app.state.registry)
    app.state.auth = app.state.registry.build("auth", "native", {"issuer": "facil"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db
    await db.dispose()
    cfg._settings = None


AUTH = {"X-Admin-Token": "test-token"}
