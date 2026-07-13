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
