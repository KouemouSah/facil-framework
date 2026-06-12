"""ProviderRegistry + EnvSecretsProvider (unit, no DB)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers.base import SecretsProvider  # noqa: E402
from app.core.providers.registry import ProviderRegistry, default_registry  # noqa: E402
from app.core.providers.secrets_env import EnvSecretsProvider  # noqa: E402


def test_default_registry_has_env_secrets():
    r = default_registry()
    assert r.is_registered("secrets", "env")
    assert ("secrets", "env") in r.registered


def test_build_returns_instance():
    r = default_registry()
    p = r.build("secrets", "env", {})
    assert isinstance(p, SecretsProvider)
    assert isinstance(p, EnvSecretsProvider)


def test_build_unknown_raises():
    r = default_registry()
    with pytest.raises(KeyError):
        r.build("storage", "minio")


@pytest.mark.asyncio
async def test_env_secrets_provider_reads_env(monkeypatch):
    monkeypatch.setenv("MY_SECRET", "shhh")
    p = EnvSecretsProvider({})
    assert await p.get_secret("MY_SECRET") == "shhh"
    assert await p.get_secret("ABSENT_VAR_XYZ") is None


def test_register_custom_factory():
    r = ProviderRegistry()
    r.register("email", "null", lambda config: object())
    assert r.is_registered("email", "null")
