"""PUT/POST /api/v1/modules/organization — `settings` is schema-merged
(Task 9), same as `document_identity` (Task 8). End-to-end through the real
endpoint (not just `merge_blob`/`validate_blob` in isolation): the
historic-key survival and the strict-input 422 must both hold going through
the HTTP handler, the ORM row and back — on BOTH the create and the update
path, since the allowlist is unconditional.

Mirrors `doc_client` (test_organization_document_identity_api.py).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

AUTH = {"X-Admin-Token": "test-token"}
BASE = "/api/v1/modules/organization"


@pytest_asyncio.fixture
async def settings_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    import app.config as cfg
    cfg._settings = None
    from app.core.module_registry import import_module_models, load_modules
    from app.core.schema.registry import default_schema_registry
    from app.db.base import Base
    from app.db.engine import Database

    from app.identity import models as _account_models  # noqa: F401
    from app.auth import models as _cred_models  # noqa: F401
    from app.rbac import models as _rbac_models  # noqa: F401
    import_module_models()
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'settings.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application = FastAPI()
    application.state.db = db
    application.state.schema_registry = default_schema_registry()
    load_modules(application, enabled=["organization"])
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db
    await db.dispose()
    cfg._settings = None


async def _mk_org(ac, code="acme"):
    r = await ac.post(f"{BASE}/", headers=AUTH,
                      json={"code": code, "legal_name": "Acme Corp"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _etag(ac, org_id):
    return (await ac.get(f"{BASE}/{org_id}", headers=AUTH)).json()["etag"]


# --- update (PUT) ----------------------------------------------------------

@pytest.mark.asyncio
async def test_declared_key_is_written_via_the_real_endpoint(settings_client):
    ac, _ = settings_client
    org_id = await _mk_org(ac, "set1")
    r = await ac.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": await _etag(ac, org_id)},
                     json={"settings": {"fiscal_year_start_month": 4}})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["fiscal_year_start_month"] == 4


@pytest.mark.asyncio
async def test_unknown_key_in_the_update_request_is_422(settings_client):
    ac, _ = settings_client
    org_id = await _mk_org(ac, "set2")
    r = await ac.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": await _etag(ac, org_id)},
                     json={"settings": {"fiscal_year_start_month": 1, "injected": "x"}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_historic_undeclared_key_survives_a_save(settings_client):
    """An org whose `settings` predates this schema carries a key nobody ever
    validated (e.g. a manual JSON edit). Saving the form must not destroy it —
    it lives on, untouched, in the DB row after the write."""
    ac, db = settings_client
    org_id = await _mk_org(ac, "set3")

    from app.modules.organization.models import Organization

    async with db.session_factory() as s:
        org = (await s.scalars(select(Organization).where(Organization.id == org_id))).one()
        org.settings = {"fiscal_year_start_month": 1, "legacy_flag": True}
        await s.commit()

    r = await ac.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": await _etag(ac, org_id)},
                     json={"settings": {"fiscal_year_start_month": 7}})
    assert r.status_code == 200, r.text
    assert r.json()["settings"] == {"fiscal_year_start_month": 7, "legacy_flag": True}

    async with db.session_factory() as s:
        got = (await s.scalars(select(Organization).where(Organization.id == org_id))).one()
        assert got.settings == {"fiscal_year_start_month": 7, "legacy_flag": True}


@pytest.mark.asyncio
async def test_update_validates_declared_rules(settings_client):
    ac, _ = settings_client
    org_id = await _mk_org(ac, "set4")
    r = await ac.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": await _etag(ac, org_id)},
                     json={"settings": {"fiscal_year_start_month": 13}})
    assert r.status_code == 422, r.text


# --- create (POST) — the allowlist is unconditional -------------------------

@pytest.mark.asyncio
async def test_create_rejects_an_undeclared_settings_key(settings_client):
    # A key seeded here would be preserved forever by merge_blob on every PUT.
    ac, _ = settings_client
    r = await ac.post(f"{BASE}/", headers=AUTH,
                      json={"code": "set5", "legal_name": "Acme Corp",
                            "settings": {"injected": "x"}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_create_with_empty_settings_is_allowed(settings_client):
    # An empty blob means "not configured yet", not "invalid".
    ac, _ = settings_client
    r = await ac.post(f"{BASE}/", headers=AUTH,
                      json={"code": "set6", "legal_name": "Acme Corp"})
    assert r.status_code == 201, r.text
    assert r.json()["settings"] == {}

    r2 = await ac.post(f"{BASE}/", headers=AUTH,
                       json={"code": "set6b", "legal_name": "Acme Corp", "settings": {}})
    assert r2.status_code == 201, r2.text
    assert r2.json()["settings"] == {}


@pytest.mark.asyncio
async def test_create_validates_declared_rules(settings_client):
    ac, _ = settings_client
    r = await ac.post(f"{BASE}/", headers=AUTH,
                      json={"code": "set7", "legal_name": "Acme Corp",
                            "settings": {"fiscal_year_start_month": 0}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_create_writes_declared_settings(settings_client):
    ac, _ = settings_client
    r = await ac.post(f"{BASE}/", headers=AUTH,
                      json={"code": "set8", "legal_name": "Acme Corp",
                            "settings": {"default_document_locale": "fr",
                                         "document_number_prefix": "GQ-"}})
    assert r.status_code == 201, r.text
    assert r.json()["settings"] == {"default_document_locale": "fr",
                                    "document_number_prefix": "GQ-"}
