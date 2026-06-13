"""LLMRouter — role resolution, defaults, overrides, secret injection, admin API."""

from __future__ import annotations

import pytest

from app.config_store.resolver import ConfigResolver
from app.core.providers.llm_ollama import OllamaLLMProvider
from app.core.providers.llm_openai_compat import OpenAICompatLLMProvider
from app.core.providers.llm_router import (DEFAULT_ROUTING, ROLES, LLMRouter)
from app.core.providers.registry import default_registry
from app.core.providers.secret_resolver import resolve_secret
from tests.conftest import AUTH


def _router(db_map=None) -> LLMRouter:
    resolver = ConfigResolver(defaults={}, env={})
    if db_map:
        resolver.set_db(db_map)
    return LLMRouter(resolver, default_registry())


@pytest.mark.asyncio
async def test_default_split_routing_resolves_three_roles():
    r = _router()
    assert tuple(DEFAULT_ROUTING) == ROLES
    pub = await r.get_for_role("public_chat", session=None)
    agt = await r.get_for_role("agent_backend", session=None)
    emb = await r.get_for_role("embedding", session=None)
    assert isinstance(pub, OllamaLLMProvider) and pub._model == "gemma4:e4b"
    assert agt._model == "gemma4:12b"
    assert emb._model == "embeddinggemma"


@pytest.mark.asyncio
async def test_unknown_role_raises():
    with pytest.raises(LookupError):
        await _router().get_for_role("nope", session=None)


@pytest.mark.asyncio
async def test_routing_to_undefined_provider_raises():
    r = _router({"ai.routing": {"public_chat": "ghost"}, "ai.providers": {}})
    with pytest.raises(LookupError):
        await r.get_for_role("public_chat", session=None)


@pytest.mark.asyncio
async def test_db_override_selects_openai_compat():
    r = _router({
        "ai.routing": {"agent_backend": "cloud"},
        "ai.providers": {"cloud": {"kind": "openai_compat",
                                   "endpoint": "https://api.example.com",
                                   "model": "big", "api_key_secret": ""}},
    })
    p = await r.get_for_role("agent_backend", session=None)
    assert isinstance(p, OpenAICompatLLMProvider)
    assert p._endpoint == "https://api.example.com" and p._model == "big"


@pytest.mark.asyncio
async def test_secret_injected_from_env_fallback(client, monkeypatch):
    _, db = client
    monkeypatch.setenv("MY_LLM_KEY", "sk-secret-123")
    r = _router({
        "ai.routing": {"agent_backend": "cloud"},
        "ai.providers": {"cloud": {"kind": "openai_compat",
                                   "endpoint": "https://api.example.com",
                                   "model": "big", "api_key_secret": "MY_LLM_KEY"}},
    })
    async with db.session_factory() as session:
        p = await r.get_for_role("agent_backend", session)
    assert p._api_key == "sk-secret-123"


@pytest.mark.asyncio
async def test_resolve_secret_env_fallback(client, monkeypatch):
    _, db = client
    monkeypatch.setenv("FOO", "bar")
    async with db.session_factory() as session:
        assert await resolve_secret("FOO", session, default_registry()) == "bar"
        assert await resolve_secret("", session, default_registry()) is None


# --- admin API -----------------------------------------------------------

@pytest.mark.asyncio
async def test_get_routing_returns_defaults(client):
    ac, _ = client
    r = await ac.get("/api/v1/admin/providers/llm/routing", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["routing"]["public_chat"] == "ollama_public"
    assert body["providers"]["ollama_public"]["model"] == "gemma4:e4b"


@pytest.mark.asyncio
async def test_routing_override_via_settings(client):
    ac, _ = client
    await ac.put("/api/v1/admin/settings/ai.routing", headers=AUTH,
                 json={"value": {"public_chat": "x"}, "value_type": "json"})
    await ac.put("/api/v1/admin/settings/ai.providers", headers=AUTH, json={
        "value": {"x": {"kind": "ollama", "endpoint": "", "model": "gemma4:26b"}},
        "value_type": "json"})
    r = await ac.get("/api/v1/admin/providers/llm/routing", headers=AUTH)
    assert r.json()["routing"] == {"public_chat": "x"}


@pytest.mark.asyncio
async def test_routing_check_aggregates_roles(client, monkeypatch):
    ac, _ = client
    # Point Ollama at a closed port so the probe fails fast (no real backend).
    monkeypatch.setenv("OLLAMA_ENDPOINT", "http://127.0.0.1:1")
    r = await ac.post("/api/v1/admin/providers/llm/routing/check", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == set(ROLES)
    assert body["public_chat"]["ok"] is False
    assert body["public_chat"]["model"] == "gemma4:e4b"
