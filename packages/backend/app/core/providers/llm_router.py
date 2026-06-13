"""LLMRouter — maps an application role to a concrete LLM provider+model.

Source of truth = the config-store settings `ai.routing` (role -> provider name)
and `ai.providers` (name -> {kind, endpoint, model, api_key_secret}), the W6
schema. The split is encoded in DEFAULT_ROUTING from the base (decision
2026-06-13, see memory `reference_ai_model_stack`):

  public_chat   -> gemma4:e4b      (high-volume citizen chatbot, light)
  agent_backend -> gemma4:12b      (+ managed-API fallback, default not proven)
  embedding     -> embeddinggemma  (dim freezes the pgvector column — lock early)

"Config split" != "two services 24/7": the routing is the source of truth; the
physical topology is a knob (prod = two services; constrained dev = both chat
roles point at one service). Defaults leave `endpoint` empty so providers fall
back to the rendered env (OLLAMA_ENDPOINT) — one Ollama service in dev.

NOTE — design: this is a dedicated router, not `ProviderRegistry.get_for_role`,
because routing needs the config resolver which the registry (pure factory map)
must not depend on. Wired as `app.state.llm_router`.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config_store.resolver import ConfigResolver
from app.core.providers.base import LLMProvider
from app.core.providers.registry import ProviderRegistry
from app.core.providers.secret_resolver import resolve_secret

ROLES = ("public_chat", "agent_backend", "embedding")

# Sovereign split defaults (overridable per deploy via ai.providers / ai.routing
# settings). Empty endpoint => provider uses env OLLAMA_ENDPOINT.
DEFAULT_PROVIDERS: dict[str, dict] = {
    "ollama_public": {"kind": "ollama", "endpoint": "", "model": "gemma4:e4b",
                      "api_key_secret": ""},
    "ollama_agents": {"kind": "ollama", "endpoint": "", "model": "gemma4:12b",
                      "api_key_secret": ""},
    "ollama_embed": {"kind": "ollama", "endpoint": "", "model": "embeddinggemma",
                     "api_key_secret": ""},
}
DEFAULT_ROUTING: dict[str, str] = {
    "public_chat": "ollama_public",
    "agent_backend": "ollama_agents",
    "embedding": "ollama_embed",
}


class LLMRouter:
    def __init__(self, resolver: ConfigResolver, registry: ProviderRegistry) -> None:
        self._resolver = resolver
        self._registry = registry

    def routing(self) -> dict[str, str]:
        return self._resolver.resolve("ai.routing", None) or DEFAULT_ROUTING

    def providers(self) -> dict[str, dict]:
        return self._resolver.resolve("ai.providers", None) or DEFAULT_PROVIDERS

    async def get_for_role(self, role: str, session: AsyncSession) -> LLMProvider:
        routing, providers = self.routing(), self.providers()
        name = routing.get(role)
        if name is None:
            raise LookupError(f"ai.routing has no provider for role '{role}'")
        pdef = providers.get(name)
        if pdef is None:
            raise LookupError(
                f"ai.routing role '{role}' -> unknown provider '{name}' "
                f"(define it in ai.providers)")
        cfg: dict = {"endpoint": pdef.get("endpoint", ""),
                     "model": pdef.get("model", "")}
        secret_name = pdef.get("api_key_secret", "")
        if secret_name:
            cfg["api_key"] = await resolve_secret(secret_name, session, self._registry)
        return self._registry.build("llm", pdef["kind"], cfg)

    async def healthcheck(self, session: AsyncSession) -> dict:
        """Resolve every routed role and probe it — for the admin /check."""
        routing = self.routing()
        out: dict = {}
        for role in ROLES:
            try:
                provider = await self.get_for_role(role, session)
                result = await provider.healthcheck()
                out[role] = {"provider": routing.get(role),
                             "model": getattr(provider, "_model", ""), **result}
            except Exception as e:  # noqa: BLE001
                out[role] = {"ok": False, "detail": f"{type(e).__name__}: {e}"}
        return out
