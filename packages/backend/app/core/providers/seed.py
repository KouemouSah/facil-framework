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

import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers import repository as repo


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
