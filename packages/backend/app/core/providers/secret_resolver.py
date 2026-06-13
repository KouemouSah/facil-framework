"""resolve_secret — turn a `*_secret` reference into its value at call time.

Providers store the *name* of a secret (e.g. ai.providers[*].api_key_secret),
never the value. This helper resolves it through the DB-configured default
SecretsProvider (OpenBao in prod), falling back to the process env in dev when
no secrets provider is configured. Used by the LLMRouter / email providers so
concrete providers stay free of session/registry coupling.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers.registry import ProviderRegistry


async def resolve_secret(name: str, session: AsyncSession,
                         registry: ProviderRegistry) -> str | None:
    if not name:
        return None
    try:
        provider = await registry.get_default("secrets", session)
    except LookupError:
        from app.core.providers.secrets_env import EnvSecretsProvider
        provider = EnvSecretsProvider()
    return await provider.get_secret(name)
