"""/health surfaces the cache backend + secrets provider (F1/F3 observability)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.mark.asyncio
async def test_health_surfaces_cache_and_secrets_provider(client):
    ac, _ = client
    r = await ac.get("/health")
    assert r.status_code == 200
    body = r.json()
    # cache backend is observable (memory in tests; "memory" while REDIS_URL set + >1
    # replica is the alarm signal in prod).
    assert body["cache"] == "memory"
    # secrets_provider key present so an env fallback is visible post-boot.
    assert "secrets_provider" in body
    assert "secrets_source" in body
