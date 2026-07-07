"""OllamaLLMProvider — sovereign local inference via the Ollama HTTP API.

Dev / small on-prem default (ADR-0002). The Ollama engine is a SEPARATE
profile-gated service (`ai`), weights live in a volume and are pulled at
bootstrap — never baked into the backend image. The backend talks to it over
HTTP, so swapping the model is a config change + `ollama pull`, zero rebuild.

Endpoint/model come from the DB config (ai.providers) or the rendered env
(OLLAMA_ENDPOINT). Sovereign default model = the role's gemma4 variant.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.providers.base import LLMProvider, cfg


class OllamaLLMProvider(LLMProvider):
    code = "ollama"

    # Ollama option keys we forward from chat(**kw) when present.
    _OPTION_KEYS = ("temperature", "top_p", "top_k", "num_predict", "num_ctx", "seed")

    @classmethod
    def config_schema(cls):
        return [
            cfg("endpoint", "Endpoint", hint="http://ollama:11434"),
            cfg("model", "Model", default="gemma4:e4b"),
            cfg("timeout_seconds", "Timeout (s)", type="number", default=120),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._endpoint = (self.config.get("endpoint")
                          or os.environ.get("OLLAMA_ENDPOINT",
                                            "http://ollama:11434")).rstrip("/")
        self._model = self.config.get("model") or "gemma4:e4b"
        self._timeout = float(self.config.get("timeout_seconds") or 120)
        # Test seam only: an httpx.MockTransport injected by tests. Never set in
        # prod (absent from the W6 ai.providers schema).
        self._transport = self.config.get("transport")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def chat(self, messages: list[dict], **kw: Any) -> str:
        payload: dict[str, Any] = {
            "model": self._model, "messages": messages, "stream": False}
        options = dict(kw.get("options") or {})
        for k in self._OPTION_KEYS:
            if kw.get(k) is not None:
                options[k] = kw[k]
        if options:
            payload["options"] = options
        async with self._client() as client:
            r = await client.post(f"{self._endpoint}/api/chat", json=payload)
            r.raise_for_status()
            return r.json()["message"]["content"]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with self._client() as client:
            r = await client.post(f"{self._endpoint}/api/embed",
                                  json={"model": self._model, "input": texts})
            r.raise_for_status()
            return r.json()["embeddings"]

    async def healthcheck(self) -> dict:
        try:
            async with self._client() as client:
                r = await client.get(f"{self._endpoint}/api/tags")
                r.raise_for_status()
                models = [m.get("name", "") for m in r.json().get("models", [])]
            stem = self._model.split(":")[0]
            present = any(m.split(":")[0] == stem for m in models)
            note = "present" if present else "NOT pulled (run `ollama pull`)"
            return {"ok": True,
                    "detail": f"{len(models)} model(s) served; '{self._model}' {note}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
