"""S0 — boot enrollment of OpenBao as the default `secrets` provider."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers import repository as repo  # noqa: E402
from app.core.providers.seed import seed_default_secrets_provider  # noqa: E402


@pytest.mark.asyncio
async def test_enrolls_openbao_when_role_id_present(client, monkeypatch):
    _, db = client
    monkeypatch.setenv("OPENBAO_ROLE_ID", "rid-123")
    monkeypatch.setenv("OPENBAO_ADDR", "http://openbao:8200")
    async with db.session_factory() as s:
        assert await seed_default_secrets_provider(s) is True
        await s.commit()
    async with db.session_factory() as s:
        d = await repo.get_default(s, "secrets")
    assert d is not None and d.provider_code == "openbao" and d.is_default
    assert d.config["kv_path"] == "facil" and "runtime" in d.config["paths"]


@pytest.mark.asyncio
async def test_skips_when_no_role_id(client, monkeypatch):
    _, db = client
    monkeypatch.delenv("OPENBAO_ROLE_ID", raising=False)
    async with db.session_factory() as s:
        assert await seed_default_secrets_provider(s) is False
        await s.commit()
    async with db.session_factory() as s:
        assert await repo.get_default(s, "secrets") is None  # keeps env fallback


@pytest.mark.asyncio
async def test_idempotent_and_respects_existing_default(client, monkeypatch):
    _, db = client
    monkeypatch.setenv("OPENBAO_ROLE_ID", "rid-123")
    # An admin already chose a different default secrets provider.
    async with db.session_factory() as s:
        await repo.upsert_provider(s, "secrets", "env", config={})
        await repo.set_default(s, "secrets", "env")
        await s.commit()
    async with db.session_factory() as s:
        assert await seed_default_secrets_provider(s) is False  # must not override
        await s.commit()
    async with db.session_factory() as s:
        d = await repo.get_default(s, "secrets")
    assert d.provider_code == "env"  # admin choice preserved


@pytest.mark.asyncio
async def test_second_run_is_noop(client, monkeypatch):
    _, db = client
    monkeypatch.setenv("OPENBAO_ROLE_ID", "rid-123")
    async with db.session_factory() as s:
        assert await seed_default_secrets_provider(s) is True
        await s.commit()
    async with db.session_factory() as s:
        assert await seed_default_secrets_provider(s) is False  # already default
        await s.commit()
    async with db.session_factory() as s:
        rows = await repo.list_providers(s, "secrets")
    assert len([r for r in rows if r.provider_code == "openbao"]) == 1
