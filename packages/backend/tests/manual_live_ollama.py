"""Manual LIVE check — OllamaLLMProvider against a real Ollama daemon.

Not part of the pytest suite (needs a running Ollama + a pulled model).
Run after: docker compose --profile ai up -d ollama && ollama pull <model>.

    cd packages/backend
    PYTHONPATH=. python tests/manual_live_ollama.py <chat_model> <embed_model>

Validated live 2026-06-13 against ollama/ollama:latest (qwen2:0.5b + all-minilm):
healthcheck ok, real chat completion, real 384-dim batch embeddings.
"""

from __future__ import annotations

import asyncio
import sys

from app.core.providers.llm_ollama import OllamaLLMProvider

ENDPOINT = "http://localhost:11434"


async def main(chat_model: str, embed_model: str) -> None:
    chat = OllamaLLMProvider({"endpoint": ENDPOINT, "model": chat_model})
    print("healthcheck:", await chat.healthcheck())
    reply = await chat.chat([{"role": "user",
                              "content": "Reply with exactly one word: ping"}])
    print(f"chat({chat_model}):", repr(reply[:120]))

    emb = OllamaLLMProvider({"endpoint": ENDPOINT, "model": embed_model})
    vecs = await emb.embed(["hola", "bonjour"])
    print(f"embed({embed_model}): {len(vecs)} vectors, dim={len(vecs[0])}")


if __name__ == "__main__":
    chat_m = sys.argv[1] if len(sys.argv) > 1 else "qwen2:0.5b"
    embed_m = sys.argv[2] if len(sys.argv) > 2 else "all-minilm"
    asyncio.run(main(chat_m, embed_m))
