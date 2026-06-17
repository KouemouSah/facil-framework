"""API tests for per-user saved views (backlog ERP item 4)."""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_saved_views_requires_auth(client):
    ac, _ = client
    assert (await ac.get("/api/v1/me/views")).status_code == 401


@pytest.mark.asyncio
async def test_save_list_overwrite_delete(client):
    ac, _ = client
    created = await ac.post("/api/v1/me/views", headers=AUTH,
                            json={"resource": "accounts", "name": "Suspended",
                                  "config": {"status": "suspended", "sort": "email"}})
    assert created.status_code == 201
    vid = created.json()["id"]

    rows = (await ac.get("/api/v1/me/views?resource=accounts", headers=AUTH)).json()
    assert any(v["id"] == vid and v["config"]["status"] == "suspended" for v in rows)
    # Other resource -> not listed.
    assert (await ac.get("/api/v1/me/views?resource=roles", headers=AUTH)).json() == []

    # Re-saving the same name overwrites the config (upsert, no duplicate).
    again = await ac.post("/api/v1/me/views", headers=AUTH,
                          json={"resource": "accounts", "name": "Suspended",
                                "config": {"status": "active"}})
    assert again.status_code == 201 and again.json()["id"] == vid
    rows2 = (await ac.get("/api/v1/me/views?resource=accounts", headers=AUTH)).json()
    assert len(rows2) == 1 and rows2[0]["config"]["status"] == "active"

    # Delete; then gone.
    assert (await ac.delete(f"/api/v1/me/views/{vid}", headers=AUTH)).status_code == 200
    assert (await ac.get("/api/v1/me/views?resource=accounts", headers=AUTH)).json() == []
    assert (await ac.delete(f"/api/v1/me/views/{vid}", headers=AUTH)).status_code == 404
