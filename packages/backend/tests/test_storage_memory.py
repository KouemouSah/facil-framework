"""MemoryStorageProvider — in-process object store for dev/tests (Phase 3a)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers.storage_memory import MemoryStorageProvider  # noqa: E402


@pytest.mark.asyncio
async def test_put_get_delete_roundtrip():
    s = MemoryStorageProvider()
    uri = await s.put("assets/public/x.png", b"\x89PNG data", content_type="image/png")
    assert isinstance(uri, str) and uri
    assert await s.get("assets/public/x.png") == b"\x89PNG data"
    await s.delete("assets/public/x.png")
    with pytest.raises(Exception):
        await s.get("assets/public/x.png")


@pytest.mark.asyncio
async def test_store_is_shared_across_instances():
    # The endpoint resolves a NEW provider per request — state MUST persist so an
    # upload (one instance) is readable by a later GET (another instance).
    a = MemoryStorageProvider()
    await a.put("assets/public/y.gif", b"GIF89a", content_type="image/gif")
    b = MemoryStorageProvider()
    assert await b.get("assets/public/y.gif") == b"GIF89a"
    await b.delete("assets/public/y.gif")  # cleanup (shared store)
