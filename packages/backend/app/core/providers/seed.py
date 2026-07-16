"""Boot-time enrollment of the default `secrets` provider.

Keystone of the OpenBao integration: without a `provider_settings` row marking
OpenBao as the default `secrets` provider, ``resolve_secret`` silently falls back
to ``EnvSecretsProvider`` and the vault — though provisioned and reachable via the
AppRole — is never read.

This seed enrolls OpenBao as the default **only** when the AppRole creds the deploy
layer renders are present (``OPENBAO_ROLE_ID``), and **only** when no default is
already configured — so an admin's runtime choice (or a prior seed) is never
overridden. Idempotent. Disable with ``SECRETS_PROVIDER_SEED_ON_BOOT=0``.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers import repository as repo

logger = logging.getLogger(__name__)

# Single-default capabilities whose default is declared by the deploy config and
# rendered to env (config.yaml -> render_env). Excluded on purpose:
#   - `secrets`: own keystone seed (seed_default_secrets_provider) — vault AppRole gating;
#   - `llm`: NOT a single default — the LLMRouter resolves role -> provider from
#     ai.routing/ai.providers (ADR-0002) with sovereign defaults; get_default('llm')
#     is never consulted, so a provider_settings 'llm' row would be dead data.
_DEFAULT_PROVIDER_ENV = {
    "storage": "STORAGE_PROVIDER",
    "email": "EMAIL_PROVIDER",
}


async def seed_default_secrets_provider(session: AsyncSession, *, env=None) -> bool:
    """Enroll OpenBao as the default `secrets` provider when applicable.

    Returns True iff it enrolled OpenBao this call (False = skipped: no AppRole
    creds, or a default already exists). Caller commits. ``env`` lets the caller
    pass a single source of truth (defaults to ``os.environ``).
    """
    env = os.environ if env is None else env
    if not env.get("OPENBAO_ROLE_ID"):
        return False  # no vault AppRole rendered → keep the env fallback
    if await repo.get_default(session, "secrets") is not None:
        return False  # already configured (admin or prior seed) — do not override

    await repo.upsert_provider(
        session, "secrets", "openbao",
        config={
            "addr": env.get("OPENBAO_ADDR", "http://openbao:8200"),
            "kv_path": "facil",
            "paths": ["boot", "runtime"],
        },
        updated_by="seed:boot",
    )
    await repo.set_default(session, "secrets", "openbao")
    return True


async def seed_default_providers(session: AsyncSession, *, env=None,
                                 registry=None) -> list[str]:
    """Enroll the config-declared default for storage/email when applicable (`llm` is
    excluded on purpose — see `_DEFAULT_PROVIDER_ENV`; the LLMRouter owns role routing).

    For each capability, the provider **code** comes from env (rendered from
    config.yaml). Enrollment happens **only** when the code is registered (a typo
    must not create a broken default that `get_default` fails to build) and **only**
    when no default already exists (an admin's runtime choice — or a prior seed — is
    never overridden). Config is left empty: every provider self-configures from the
    env the deploy layer renders (endpoint/bucket/host/creds). Idempotent. Caller
    commits. Returns the capabilities enrolled this call.
    """
    env = os.environ if env is None else env
    if registry is None:
        from app.core.providers.registry import default_registry
        registry = default_registry()

    seeded: list[str] = []
    for capability, env_var in _DEFAULT_PROVIDER_ENV.items():
        code = (env.get(env_var) or "").strip()
        if not code:
            continue  # capability not declared by the deploy config → skip
        if not registry.is_registered(capability, code):
            logger.warning(
                "%s=%r is not a registered '%s' provider — skipping seed "
                "(check deploy config).", env_var, code, capability)
            continue
        if await repo.get_default(session, capability) is not None:
            continue  # already configured (admin or prior seed) — do not override
        await repo.upsert_provider(session, capability, code, config={},
                                   updated_by="seed:boot")
        await repo.set_default(session, capability, code)
        seeded.append(capability)
    return seeded
