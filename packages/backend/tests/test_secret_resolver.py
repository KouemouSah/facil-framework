"""F1 — resolve_secret warns (not silent) when it falls back to env with a vault expected."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers.secret_resolver import resolve_secret  # noqa: E402


class _RegistryNoDefault:
    async def get_default(self, capability, session):
        raise LookupError("no default secrets provider")


@pytest.mark.asyncio
async def test_env_fallback_warns_when_vault_expected(monkeypatch, caplog):
    monkeypatch.setenv("OPENBAO_ROLE_ID", "rid-1")  # vault expected
    monkeypatch.setenv("MY_API_KEY", "from-env")
    with caplog.at_level(logging.WARNING):
        val = await resolve_secret("MY_API_KEY", None, _RegistryNoDefault())
    assert val == "from-env"
    assert any("falling back to env" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_env_fallback_quiet_in_dev_without_vault(monkeypatch, caplog):
    monkeypatch.delenv("OPENBAO_ROLE_ID", raising=False)  # no vault → quiet
    monkeypatch.setenv("MY_API_KEY", "from-env")
    with caplog.at_level(logging.WARNING):
        val = await resolve_secret("MY_API_KEY", None, _RegistryNoDefault())
    assert val == "from-env"
    assert not any("falling back to env" in r.message.lower() for r in caplog.records)
