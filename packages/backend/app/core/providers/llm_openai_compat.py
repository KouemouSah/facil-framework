"""OpenAICompatLLMProvider — any OpenAI-compatible inference endpoint.

One provider covers vLLM, Docker Model Runner (dev), a managed API (Claude/
OpenAI/Mistral/Together), or any `/v1/chat/completions` server — that is the
whole point of the abstraction (ADR-0002). Sovereign prod-at-scale = vLLM+GPU
behind this provider; the managed-API fallback for hard agent tasks is just
another `ai.providers` entry routed here.

Credentials NEVER live in provider_settings.config: the LLMRouter resolves the
named `api_key_secret` via the SecretsProvider and injects the value as
config['api_key']. A bare env fallback (OPENAI_API_KEY) covers the dev path.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.providers.base import LLMProvider, cfg


class OpenAICompatLLMProvider(LLMProvider):
    code = "openai_compat"

    @classmethod
    def config_schema(cls):
        # api_key travels via secret_ref/env (OPENAI_API_KEY), never in config.
        return [
            cfg("endpoint", "Endpoint (OpenAI-compatible)", hint="https://api.openai.com/v1"),
            cfg("model", "Model", hint="gpt-4o / mistral-large / …"),
            cfg("timeout_seconds", "Timeout (s)", type="number", default=120),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._endpoint = (self.config.get("endpoint")
                          or os.environ.get("OPENAI_BASE_URL", "")).rstrip("/")
        self._model = self.config.get("model") or ""
        # Resolved value injected by the router; env is the dev fallback only.
        self._api_key = (self.config.get("api_key")
                         or os.environ.get("OPENAI_API_KEY", ""))
        self._timeout = float(self.config.get("timeout_seconds") or 120)
        self._transport = self.config.get("transport")  # test seam only

    def _client(self) -> httpx.AsyncClient:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport,
                                 headers=headers)

    async def chat(self, messages: list[dict], **kw: Any) -> str:
        payload: dict[str, Any] = {"model": self._model, "messages": messages}
        for k in ("temperature", "top_p", "max_tokens", "seed"):
            if kw.get(k) is not None:
                payload[k] = kw[k]
        async with self._client() as client:
            r = await client.post(f"{self._endpoint}/v1/chat/completions",
                                  json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with self._client() as client:
            r = await client.post(f"{self._endpoint}/v1/embeddings",
                                  json={"model": self._model, "input": texts})
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]]

    async def healthcheck(self) -> dict:
        try:
            async with self._client() as client:
                r = await client.get(f"{self._endpoint}/v1/models")
                r.raise_for_status()
                models = [m.get("id", "") for m in r.json().get("data", [])]
            return {"ok": True,
                    "detail": f"endpoint reachable, {len(models)} model(s) listed"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
