"""LLM providers — chat / embed / healthcheck via httpx MockTransport (no net)."""

from __future__ import annotations

import httpx
import pytest

from app.core.providers.llm_ollama import OllamaLLMProvider
from app.core.providers.llm_openai_compat import OpenAICompatLLMProvider


def _ollama_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/chat":
        return httpx.Response(200, json={"message": {"content": "hi from gemma"}})
    if path == "/api/embed":
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
    if path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": "gemma4:e4b"},
                                                    {"name": "embeddinggemma"}]})
    return httpx.Response(404)


def _ollama(model: str = "gemma4:e4b", handler=_ollama_handler) -> OllamaLLMProvider:
    return OllamaLLMProvider({"endpoint": "http://ollama:11434", "model": model,
                              "transport": httpx.MockTransport(handler)})


@pytest.mark.asyncio
async def test_ollama_chat():
    out = await _ollama().chat([{"role": "user", "content": "hello"}])
    assert out == "hi from gemma"


@pytest.mark.asyncio
async def test_ollama_embed():
    vecs = await _ollama("embeddinggemma").embed(["a", "b"])
    assert vecs == [[0.1, 0.2, 0.3]]


@pytest.mark.asyncio
async def test_ollama_healthcheck_model_present():
    res = await _ollama("gemma4:e4b").healthcheck()
    assert res["ok"] is True and "present" in res["detail"]


@pytest.mark.asyncio
async def test_ollama_healthcheck_model_missing():
    res = await _ollama("llama3:70b").healthcheck()
    assert res["ok"] is True and "NOT pulled" in res["detail"]


@pytest.mark.asyncio
async def test_ollama_healthcheck_unreachable_is_false():
    def boom(request):
        raise httpx.ConnectError("refused")
    res = await _ollama(handler=boom).healthcheck()
    assert res["ok"] is False


@pytest.mark.asyncio
async def test_ollama_chat_forwards_options():
    seen = {}

    def handler(request):
        import json
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "ok"}})

    await _ollama(handler=handler).chat([{"role": "user", "content": "x"}],
                                        temperature=0.1, top_p=0.5)
    assert seen["options"] == {"temperature": 0.1, "top_p": 0.5}
    assert seen["stream"] is False


# --- openai_compat -------------------------------------------------------

def _oai_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/v1/chat/completions":
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})
    if path == "/v1/embeddings":
        return httpx.Response(200, json={"data": [{"embedding": [0.4, 0.5]}]})
    if path == "/v1/models":
        return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})
    return httpx.Response(404)


def _oai(handler=_oai_handler, **cfg) -> OpenAICompatLLMProvider:
    base = {"endpoint": "https://api.example.com", "model": "m1",
            "api_key": "sk-test", "transport": httpx.MockTransport(handler)}
    base.update(cfg)
    return OpenAICompatLLMProvider(base)


@pytest.mark.asyncio
async def test_openai_chat():
    assert await _oai().chat([{"role": "user", "content": "hi"}]) == "hi"


@pytest.mark.asyncio
async def test_openai_embed():
    assert await _oai().embed(["x"]) == [[0.4, 0.5]]


@pytest.mark.asyncio
async def test_openai_sends_bearer_auth():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    await _oai(handler=handler).chat([{"role": "user", "content": "x"}])
    assert captured["auth"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_openai_healthcheck():
    res = await _oai().healthcheck()
    assert res["ok"] is True and "2 model(s)" in res["detail"]


@pytest.mark.asyncio
async def test_embed_not_implemented_default():
    from app.core.providers.base import LLMProvider

    class ChatOnly(LLMProvider):
        code = "chatonly"

        async def chat(self, messages, **kw):
            return ""

    with pytest.raises(NotImplementedError):
        await ChatOnly().embed(["x"])
