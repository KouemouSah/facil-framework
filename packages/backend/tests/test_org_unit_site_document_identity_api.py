"""`org_unit.document_identity` / `site.document_identity` — SP1 debt D1.

The allowlist (`org_unit.document_identity`/`site.document_identity`,
`product_schemas.DOCUMENT_IDENTITY_OVERRIDE`) is UNCONDITIONAL — create AND
update — same discipline as `organization.document_identity`
(`test_organization_document_identity_api.py`). A review already caught a
create-path bypass once (see the comment on `create_organization` in
`app/modules/organization/api/__init__.py`); this file pins that both new
targets don't repeat it.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

AUTH = {"X-Admin-Token": "test-token"}
ORG = "/api/v1/modules/organization"
LOC = "/api/v1/modules/location"


@pytest_asyncio.fixture
async def doc_client(tmp_path, monkeypatch):
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
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'unit_site_doc.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application = FastAPI()
    application.state.db = db
    application.state.schema_registry = default_schema_registry()
    load_modules(application, enabled=["organization", "location"])
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db
    await db.dispose()
    cfg._settings = None


async def _mk_org(ac, code="acme"):
    r = await ac.post(f"{ORG}/", headers=AUTH, json={"code": code, "legal_name": "Acme Corp"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mk_unit(ac, org_id, code="dept", **extra):
    r = await ac.post(f"{ORG}/{org_id}/units", headers=AUTH,
                      json={"code": code, "name": code, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_site(ac, org_id, code="branch", **extra):
    r = await ac.post(f"{LOC}/sites", headers=AUTH,
                      json={"organization_id": org_id, "code": code, "name": code, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def _unit_etag(ac, unit_id):
    return (await ac.get(f"{ORG}/units/{unit_id}", headers=AUTH)).json()["etag"]


async def _site_etag(ac, site_id):
    return (await ac.get(f"{LOC}/sites/{site_id}", headers=AUTH)).json()["etag"]


# --- OrgUnit -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_unit_create_with_declared_override_key_succeeds(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "u1")
    unit = await _mk_unit(ac, org_id, "u1-dept",
                          document_identity={"legal_name": "Dept override"})
    assert unit["document_identity"] == {"legal_name": "Dept override"}


@pytest.mark.asyncio
async def test_unit_create_rejects_undeclared_document_identity_key(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "u2")
    r = await ac.post(f"{ORG}/{org_id}/units", headers=AUTH,
                      json={"code": "u2-dept", "name": "u2-dept",
                            "document_identity": {"tax_id": "not-overridable"}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_unit_update_rejects_undeclared_document_identity_key(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "u3")
    unit = await _mk_unit(ac, org_id, "u3-dept")
    r = await ac.put(f"{ORG}/units/{unit['id']}",
                     headers={**AUTH, "If-Match": await _unit_etag(ac, unit["id"])},
                     json={"document_identity": {"seal_url": "not-overridable"}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_unit_update_merges_declared_key(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "u4")
    unit = await _mk_unit(ac, org_id, "u4-dept")
    r = await ac.put(f"{ORG}/units/{unit['id']}",
                     headers={**AUTH, "If-Match": await _unit_etag(ac, unit["id"])},
                     json={"document_identity": {"short_code": "DEPT4"}})
    assert r.status_code == 200, r.text
    assert r.json()["document_identity"] == {"short_code": "DEPT4"}


# --- Site --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_site_create_with_declared_override_key_succeeds(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "s1")
    site = await _mk_site(ac, org_id, "s1-branch",
                          document_identity={"contact_line": "branch@x.com"})
    assert site["document_identity"] == {"contact_line": "branch@x.com"}


@pytest.mark.asyncio
async def test_site_create_rejects_undeclared_document_identity_key(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "s2")
    r = await ac.post(f"{LOC}/sites", headers=AUTH,
                      json={"organization_id": org_id, "code": "s2-branch",
                            "name": "s2-branch",
                            "document_identity": {"registration_number": "not-overridable"}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_site_update_rejects_undeclared_document_identity_key(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "s3")
    site = await _mk_site(ac, org_id, "s3-branch")
    r = await ac.put(f"{LOC}/sites/{site['id']}",
                     headers={**AUTH, "If-Match": await _site_etag(ac, site["id"])},
                     json={"document_identity": {"header_note": "not-overridable"}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_site_update_merges_declared_key(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "s4")
    site = await _mk_site(ac, org_id, "s4-branch")
    r = await ac.put(f"{LOC}/sites/{site['id']}",
                     headers={**AUTH, "If-Match": await _site_etag(ac, site["id"])},
                     json={"document_identity": {"logo_url": "https://x/branch-logo.png"}})
    assert r.status_code == 200, r.text
    assert r.json()["document_identity"] == {"logo_url": "https://x/branch-logo.png"}


@pytest.mark.asyncio
async def test_site_update_historic_undeclared_key_survives_a_save(doc_client):
    """Mirrors `test_historic_undeclared_key_survives_a_save`
    (test_organization_document_identity_api.py): a pre-existing undeclared
    key (predating this schema) is preserved, not silently dropped."""
    ac, db = doc_client
    org_id = await _mk_org(ac, "s5")
    site = await _mk_site(ac, org_id, "s5-branch")

    from app.modules.location.models import Site
    from sqlalchemy import select

    async with db.session_factory() as s:
        row = (await s.scalars(select(Site).where(Site.id == site["id"]))).one()
        row.document_identity = {"logo_url": "https://old", "legacy_ref": "REF-9"}
        await s.commit()

    r = await ac.put(f"{LOC}/sites/{site['id']}",
                     headers={**AUTH, "If-Match": await _site_etag(ac, site["id"])},
                     json={"document_identity": {"logo_url": "https://new"}})
    assert r.status_code == 200, r.text
    assert r.json()["document_identity"] == {"logo_url": "https://new", "legacy_ref": "REF-9"}
