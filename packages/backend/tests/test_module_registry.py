"""Module Loader — discovery, conditional load, order, fail-closed, env parse."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.core.module_registry import (ModuleLoadError, discover,
                                      enabled_from_env, load_modules)

PKG = "tests.sample_modules"


def _paths(app: FastAPI) -> list[str]:
    return [r.path for r in app.routes]


def test_discover_lists_subpackages():
    found = discover(PKG)
    assert {"alpha", "beta", "noapi", "norouter"} <= set(found)
    assert found == sorted(found)


def test_discover_unknown_package_is_empty():
    assert discover("app.does_not_exist") == []


def test_enabled_from_env_parses_csv():
    assert enabled_from_env({"MODULES_ENABLED": "alpha, beta ,, "}) == ["alpha", "beta"]
    assert enabled_from_env({}) == []


def test_load_only_enabled_module():
    app = FastAPI()
    loaded = load_modules(app, enabled=["alpha"], package=PKG)
    assert loaded == ["alpha"]
    paths = _paths(app)
    assert "/api/v1/modules/alpha/ping" in paths
    assert "/api/v1/modules/beta/ping" not in paths


def test_load_preserves_order():
    app = FastAPI()
    assert load_modules(app, enabled=["beta", "alpha"], package=PKG) == ["beta", "alpha"]


def test_empty_enabled_loads_nothing():
    app = FastAPI()
    assert load_modules(app, enabled=[], package=PKG) == []


def test_missing_module_skipped_with_warning(caplog):
    app = FastAPI()
    with caplog.at_level("WARNING"):
        assert load_modules(app, enabled=["ghost"], package=PKG) == []
    assert "ghost" in caplog.text and "not present" in caplog.text


def test_missing_module_does_not_block_present_ones():
    app = FastAPI()
    loaded = load_modules(app, enabled=["alpha", "ghost", "beta"], package=PKG)
    assert loaded == ["alpha", "beta"]


def test_module_without_api_fails_closed():
    app = FastAPI()
    with pytest.raises(ModuleLoadError):
        load_modules(app, enabled=["noapi"], package=PKG)


def test_module_without_router_fails_closed():
    app = FastAPI()
    with pytest.raises(ModuleLoadError):
        load_modules(app, enabled=["norouter"], package=PKG)


@pytest.mark.asyncio
async def test_enabled_module_serves_requests():
    app = FastAPI()
    load_modules(app, enabled=["alpha"], package=PKG)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/modules/alpha/ping")
    assert r.status_code == 200 and r.json() == {"module": "alpha", "pong": True}


# --- Real structure: the shipped `system` module via the real app.modules ----

def test_system_module_is_discoverable():
    assert "system" in discover()  # default package = app.modules


@pytest.mark.asyncio
async def test_real_system_module_loads_and_serves():
    """Validates the PRODUCTION path: real app.modules.system.api:router."""
    app = FastAPI(version="0.1.0")
    assert load_modules(app, enabled=["system"]) == ["system"]  # default package
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/modules/system/info")
    assert r.status_code == 200
    body = r.json()
    assert body["app_name"] == "Facil" and body["version"] == "0.1.0"
    assert "system" in body["modules"]["available"]
