"""resolve_secret — turn a `*_secret` reference into its value at call time.

Providers store the *name* of a secret (e.g. ai.providers[*].api_key_secret),
never the value. This helper resolves it through the DB-configured default
SecretsProvider (OpenBao in prod), falling back to the process env in dev when
no secrets provider is configured. Used by the LLMRouter / email providers so
concrete providers stay free of session/registry coupling.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


async def resolve_secret(name: str, session: AsyncSession,
                         registry: ProviderRegistry) -> str | None:
    if not name:
        return None
    try:
        provider = await registry.get_default("secrets", session)
    except LookupError:
        from app.core.providers.secrets_env import EnvSecretsProvider
        # The env fallback is normal in dev (no vault). But when an AppRole IS
        # present, no enrolled provider means OpenBao is provisioned yet unused —
        # warn so it is not a silent misconfiguration (see F1 / secret_enrollment).
        if os.environ.get("OPENBAO_ROLE_ID"):
            logger.warning(
                "resolve_secret(%s): no default secrets provider enrolled — falling "
                "back to env although a vault AppRole is present (OpenBao not enrolled?).",
                name)
        provider = EnvSecretsProvider()
    return await provider.get_secret(name)
