"""End-to-end test of the generic CRUD router factory (build_crud_router).

A throwaway `Widget` model + a minimal app mounting the factory, exercised with
the break-glass admin token (so RBAC scope/enforce pass without seeding grants).
Proves the standardized contract: list (items/total/sort/search), get (+etag),
create, update (If-Match -> 409), delete, and the sort whitelist (422).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDAuditBase

ADMIN = {"X-Admin-Token": "test-token"}
BASE = "/api/v1/widgets"


# Module-level (registers the table once; redefining per-test would clash).
class Widget(UUIDAuditBase):
    __tablename__ = "widget_test"
    name: Mapped[str] = mapped_column(String(80))
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name,
                "organization_id": self.organization_id, "is_active": self.is_active}


class WCreate(BaseModel):
    name: str
    organization_id: str | None = None


class WUpdate(BaseModel):
    name: str | None = None


@pytest_asyncio.fixture
async def crud_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-0123456789abcdef0123456789")
    import app.config as cfg
    cfg._settings = None
    from app.api.crud import build_crud_router
    from app.auth import models as _c  # noqa: F401 (register tables for create_all)
    from app.db.base import Base
    from app.db.engine import Database
    from app.identity import models as _a  # noqa: F401
    from app.rbac import models as _r  # noqa: F401

    db = Database(f"sqlite+aiosqlite:///{tmp_path/'crud.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app = FastAPI()
    app.state.db = db
    app.include_router(build_crud_router(
        prefix=BASE, tags=["widgets"], model=Widget, resource="widget",
        create_schema=WCreate, update_schema=WUpdate,
        sortable={"name": Widget.name, "created_at": Widget.created_at},
        default_sort="name", search_fields=[Widget.name],
        scope_col=Widget.organization_id))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await db.dispose()
    cfg._settings = None


@pytest.mark.asyncio
async def test_crud_factory_full_contract(crud_client):
    ac = crud_client
    # Auth required.
    assert (await ac.get(BASE)).status_code == 401

    # Create (break-glass) -> 201.
    a = await ac.post(BASE, headers=ADMIN, json={"name": "beta"})
    b = await ac.post(BASE, headers=ADMIN, json={"name": "alpha"})
    assert a.status_code == 201 and b.status_code == 201
    bid = b.json()["id"]

    # List: {items,total}, default sort by name asc.
    lst = (await ac.get(BASE, headers=ADMIN)).json()
    assert lst["total"] == 2
    assert [w["name"] for w in lst["items"]] == ["alpha", "beta"]

    # Search.
    hit = (await ac.get(f"{BASE}?q=alph", headers=ADMIN)).json()
    assert hit["total"] == 1 and hit["items"][0]["id"] == bid

    # Unknown sort -> 422.
    assert (await ac.get(f"{BASE}?sort=evil", headers=ADMIN)).status_code == 422

    # Get + etag.
    g = (await ac.get(f"{BASE}/{bid}", headers=ADMIN)).json()
    etag = g["etag"]
    assert etag and g["name"] == "alpha"

    # Update with correct etag -> 200, etag rotates (content changed).
    ok = await ac.put(f"{BASE}/{bid}", headers={**ADMIN, "If-Match": etag},
                      json={"name": "alpha2"})
    assert ok.status_code == 200 and ok.json()["name"] == "alpha2"
    new_etag = (await ac.get(f"{BASE}/{bid}", headers=ADMIN)).json()["etag"]
    assert new_etag != etag
    # Stale etag -> 409.
    assert (await ac.put(f"{BASE}/{bid}", headers={**ADMIN, "If-Match": etag},
                         json={"name": "race"})).status_code == 409

    # Delete -> 200, then 404.
    assert (await ac.delete(f"{BASE}/{bid}", headers=ADMIN)).status_code == 200
    assert (await ac.get(f"{BASE}/{bid}", headers=ADMIN)).status_code == 404
