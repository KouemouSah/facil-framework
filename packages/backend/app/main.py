"""Facil backend — minimal foundation app (Phase D / D1).

Hosts the config-store only: SQLAlchemy async engine + the layered resolver +
the token-gated admin settings API + /health. Business modules / full auth /
provider registry land in later D-phases.
"""

from __future__ import annotations

import contextlib
import os

from fastapi import FastAPI, Response, status
from sqlalchemy import text

from app.api import admin_providers, admin_settings
from app.config import get_settings
from app.config_store import repository as repo
from app.config_store.resolver import ConfigResolver
from app.core.providers.registry import default_registry
from app.db.engine import Database

# Code defaults — the lowest layer of the resolver (overridden by file/DB/env).
_DEFAULTS: dict[str, object] = {
    "branding.app_name": "Facil",
}


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

    yield
    await db.dispose()


app = FastAPI(title="Facil Backend", version="0.1.0", lifespan=lifespan)
app.include_router(admin_settings.router)
app.include_router(admin_providers.router)


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
