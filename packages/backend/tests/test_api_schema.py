"""GET /api/v1/schema/{target} — the single endpoint every generated form reads."""

from __future__ import annotations

import pytest

from app.core.schema.spec import field
from tests.conftest import AUTH

L = {"en": "Legal name", "fr": "Raison sociale", "es": "Razón social"}


@pytest.mark.asyncio
async def test_returns_the_registered_product_schema(client):
    ac, _ = client
    from app.main import app
    app.state.schema_registry.register(
        "organization.document_identity", [field("legal_name", L, required=True)])
    r = await ac.get("/api/v1/schema/organization.document_identity", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == "organization.document_identity"
    assert body["fields"][0]["key"] == "legal_name"
    assert body["fields"][0]["label"]["fr"] == "Raison sociale"
    assert body["fields"][0]["widget"] == "plain"


@pytest.mark.asyncio
async def test_unknown_target_is_404_not_an_empty_list(client):
    ac, _ = client
    # An empty list would let a typo'd target silently render an empty form.
    r = await ac.get("/api/v1/schema/nope.nope", headers=AUTH)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_extensible_target_with_zero_code_fields_is_200_not_404(client):
    ac, _ = client
    # organization.custom_fields is DB-backed by design (EXTENSIBLE_TARGETS):
    # it legitimately carries zero CODE schema. That must not 404 — pins the
    # guard that separates "known, DB-only target" from "genuinely unknown".
    r = await ac.get("/api/v1/schema/organization.custom_fields", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["fields"] == []


@pytest.mark.asyncio
async def test_requires_authentication(client):
    ac, _ = client
    r = await ac.get("/api/v1/schema/organization.document_identity")
    assert r.status_code == 401


# --- Task 12 carry-forward: DB-scoped resolution wired into the endpoint ----

@pytest.mark.asyncio
async def test_db_field_shadowing_a_product_field_is_422_not_500(client):
    """A tenant custom field reusing a product key must never reach the
    resolver's ValueError as a bare 500 — it is a bad definition (422)."""
    ac, db = client
    from app.main import app
    from app.models.field_definition import FieldDefinition
    app.state.schema_registry.register(
        "organization.custom_fields", [field("legal_name", L, required=True)])
    async with db.session_factory() as s:
        s.add(FieldDefinition(
            organization_id="org-x", target="organization.custom_fields",
            key="legal_name", type="string", widget="plain",
            label_en="x", label_fr="x", label_es="x"))
        await s.commit()
    r = await ac.get(
        "/api/v1/schema/organization.custom_fields?organization_id=org-x",
        headers=AUTH)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_organization_id_not_visible_to_caller_is_404_not_leaked(client):
    """The caller may only read schemas for an org they can see. A real org
    the caller has no grant for is 404 — never 403 — so its existence is not
    revealed to an unauthorized caller."""
    ac, db = client
    from app.modules.organization.models import Organization
    async with db.session_factory() as s:
        org = Organization(code="hidden-org", legal_name="Hidden Org")
        s.add(org)
        await s.commit()
        org_id = org.id

    await ac.post("/api/v1/auth/register",
                  json={"password": "Sup3rStr0ng!pw", "email": "noone@x.com"})
    login = await ac.post(
        "/api/v1/auth/login",
        json={"identifier": "noone@x.com", "password": "Sup3rStr0ng!pw"})
    assert login.status_code == 200, login.text
    hdr = {"Authorization": f"Bearer {login.json()['access']}"}

    r = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=hdr)
    assert r.status_code == 404
