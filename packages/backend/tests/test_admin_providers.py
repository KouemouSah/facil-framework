"""Admin providers API — CRUD, set-default, registered, token gate."""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_requires_token(client):
    ac, _ = client
    assert (await ac.get("/api/v1/admin/providers/")).status_code == 401


@pytest.mark.asyncio
async def test_registered_lists_builtin(client):
    ac, _ = client
    r = await ac.get("/api/v1/admin/providers/registered", headers=AUTH)
    assert r.status_code == 200
    assert {"capability": "secrets", "provider_code": "env"} in r.json()


@pytest.mark.asyncio
async def test_crud_and_default(client):
    ac, _ = client
    # upsert two storage providers
    await ac.put("/api/v1/admin/providers/storage/minio", headers=AUTH,
                 json={"config": {"endpoint": "http://minio:9000", "bucket": "facil-documents"},
                       "secret_ref": "minio_sa"})
    await ac.put("/api/v1/admin/providers/storage/s3", headers=AUTH,
                 json={"config": {"region": "eu-west-1"}})
    # list
    r = await ac.get("/api/v1/admin/providers/?capability=storage", headers=AUTH)
    assert {p["provider_code"] for p in r.json()} == {"minio", "s3"}
    # set default -> minio
    assert (await ac.post("/api/v1/admin/providers/storage/minio/default",
                          headers=AUTH)).status_code == 200
    r = await ac.get("/api/v1/admin/providers/storage/minio", headers=AUTH)
    assert r.json()["is_default"] is True
    # switching default to s3 unsets minio
    await ac.post("/api/v1/admin/providers/storage/s3/default", headers=AUTH)
    assert (await ac.get("/api/v1/admin/providers/storage/minio",
                         headers=AUTH)).json()["is_default"] is False
    # delete
    assert (await ac.delete("/api/v1/admin/providers/storage/s3",
                            headers=AUTH)).status_code == 200


@pytest.mark.asyncio
async def test_invalid_capability_rejected(client):
    ac, _ = client
    r = await ac.put("/api/v1/admin/providers/teleport/warp", headers=AUTH, json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_set_default_missing_404(client):
    ac, _ = client
    assert (await ac.post("/api/v1/admin/providers/llm/ghost/default",
                          headers=AUTH)).status_code == 404
