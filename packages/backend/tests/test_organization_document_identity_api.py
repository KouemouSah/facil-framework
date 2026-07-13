"""PUT /api/v1/modules/organization/{id} — document_identity is schema-merged
(Task 8), not stored as raw JSON. End-to-end through the real endpoint (not just
`merge_blob` in isolation): the historic-key survival and the strict-input 422
must both hold when going through the HTTP handler, the ORM row and back.

Mirrors `org_client` (test_organization_api.py) — a standalone FastAPI app with
only the organization module mounted — plus the one extra piece of state the
handler now depends on: `app.state.schema_registry`.
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
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'doc.db'}")
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


@pytest.mark.asyncio
async def test_declared_key_is_written_via_the_real_endpoint(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "doc1")
    r = await ac.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": await _etag(ac, org_id)},
                     json={"document_identity": {"legal_name": "Acme SARL"}})
    assert r.status_code == 200, r.text
    assert r.json()["document_identity"]["legal_name"] == "Acme SARL"


@pytest.mark.asyncio
async def test_unknown_key_in_the_request_is_422(doc_client):
    ac, _ = doc_client
    org_id = await _mk_org(ac, "doc2")
    r = await ac.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": await _etag(ac, org_id)},
                     json={"document_identity": {"legal_name": "Acme", "injected": "x"}})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_historic_undeclared_key_survives_a_save(doc_client):
    """An org whose `document_identity` predates this schema carries a key nobody
    ever validated (e.g. `seal_ref` from a manual JSON edit). Saving the form must
    not destroy it — it lives on, untouched, in the DB row after the write."""
    ac, db = doc_client
    org_id = await _mk_org(ac, "doc3")

    from app.modules.organization.models import Organization

    async with db.session_factory() as s:
        org = (await s.scalars(select(Organization).where(Organization.id == org_id))).one()
        org.document_identity = {"legal_name": "Old", "seal_ref": "SEAL-77"}
        await s.commit()

    r = await ac.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": await _etag(ac, org_id)},
                     json={"document_identity": {"legal_name": "Acme SARL"}})
    assert r.status_code == 200, r.text
    assert r.json()["document_identity"] == {"legal_name": "Acme SARL", "seal_ref": "SEAL-77"}

    async with db.session_factory() as s:
        got = (await s.scalars(select(Organization).where(Organization.id == org_id))).one()
        assert got.document_identity == {"legal_name": "Acme SARL", "seal_ref": "SEAL-77"}
