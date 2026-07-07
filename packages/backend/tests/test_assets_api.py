"""Asset upload + public serving API (Phase 3a) — backed by MemoryStorage in tests.

Upload is RBAC-gated (branding.manage; break-glass AUTH bypasses). Serving is
public but structurally prefix-locked to assets/public/ via a strict name regex
(anti-traversal; can never reach a future private/scoped key).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.conftest import AUTH  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # valid PNG magic + filler


async def _seed_memory_storage(db):
    from app.core.providers import repository as prepo
    async with db.session_factory() as s:
        await prepo.upsert_provider(s, "storage", "memory", config={})
        await prepo.set_default(s, "storage", "memory")
        await s.commit()


@pytest.mark.asyncio
async def test_upload_then_serve_roundtrip(client):
    ac, db = client
    await _seed_memory_storage(db)
    r = await ac.post("/api/v1/assets", headers=AUTH,
                      files={"file": ("logo.png", PNG, "image/png")})
    assert r.status_code == 201
    body = r.json()
    assert body["url"].startswith("/api/v1/assets/") and body["asset_id"]
    # Public GET returns the exact bytes with the sniffed content-type.
    got = await ac.get(body["url"])
    assert got.status_code == 200
    assert got.headers["content-type"].startswith("image/png")
    assert got.headers["x-content-type-options"] == "nosniff"  # anti-MIME-sniffing
    assert got.content == PNG


@pytest.mark.asyncio
async def test_upload_requires_permission(client):
    ac, db = client
    await _seed_memory_storage(db)
    r = await ac.post("/api/v1/assets",  # no AUTH header
                      files={"file": ("logo.png", PNG, "image/png")})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_upload_rejects_non_image(client):
    ac, db = client
    await _seed_memory_storage(db)
    r = await ac.post("/api/v1/assets", headers=AUTH,
                      files={"file": ("x.png", b"<svg>not really</svg>", "image/png")})
    assert r.status_code == 422  # magic-bytes sniff fails (declared type ignored)


@pytest.mark.asyncio
async def test_serve_unknown_is_404(client):
    ac, db = client
    await _seed_memory_storage(db)
    r = await ac.get("/api/v1/assets/" + ("a" * 32) + ".png")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_serve_rejects_traversal_and_bad_name(client):
    ac, _ = client
    for bad in ("../secret.png", "not-a-uuid.png", ("a" * 32) + ".svg",
                ("a" * 32) + ".exe"):
        r = await ac.get(f"/api/v1/assets/{bad}")
        assert r.status_code == 404  # strict name regex = prefix-lock + anti-traversal
