"""F1 — observable, fail-loud enrollment of the default `secrets` provider.

The keystone seed (``seed_default_secrets_provider``) is silent: if it fails, the
backend keeps booting and ``resolve_secret`` quietly falls back to env — the vault
is provisioned and reachable, yet never read, with no health signal. This wrapper:

- returns an **observable label** (surfaced in /health, distinct from the
  hydration ``secrets_source``) so an env fallback is visible, not buried in logs;
- escalates a failed enrollment to **ERROR** when the AppRole is present (the
  vault was expected) instead of a buried WARNING;
- **fails closed** (re-raises) when the vault is required, so a prod replica never
  silently serves secrets from a possibly-stale env.
"""

from __future__ import annotations

import logging

from app.core.env_posture import is_required
from app.core.providers import repository as repo
from app.core.providers.seed import seed_default_secrets_provider

logger = logging.getLogger(__name__)


async def enroll_secrets_provider(db, *, env, db_ready: bool = True) -> str:
    """Enroll OpenBao as default and return an observable label.

    Label ∈ {"disabled", "env-fallback", or the enrolled/admin provider_code
    ("openbao", "env", …)}. ``db`` is the Database (own session). ``db_ready`` (the
    config-store DB load result) guards the fail-closed path: a pre-migration boot
    (DB not yet ready) must never crash even when the vault is required — migrations
    run out-of-band and a replica may start before the schema exists.
    """
    if env.get("SECRETS_PROVIDER_SEED_ON_BOOT", "1") == "0":
        return "disabled"
    try:
        async with db.session_factory() as session:
            await seed_default_secrets_provider(session, env=env)
            await session.commit()
            row = await repo.get_default(session, "secrets")
    except Exception as exc:  # noqa: BLE001 — pre-migration first boot may fail
        vault_expected = bool(env.get("OPENBAO_ROLE_ID"))
        if vault_expected and db_ready:
            # DB is migrated and the vault was expected, yet enrollment failed — a
            # real error: resolve_secret would silently serve env secrets.
            logger.error(
                "secrets provider enrollment failed (%s) — resolve_secret will fall "
                "back to env; the vault is NOT the secrets source. Investigate.", exc)
            if is_required(env, "SECRETS_VAULT_REQUIRED"):
                raise  # fail closed: refuse to run a prod replica off env secrets
        elif vault_expected:
            # Pre-migration / DB not ready — benign; a later boot retries. Never crash.
            logger.warning("secrets provider enrollment deferred (DB not ready): %s", exc)
        else:
            logger.warning("secrets provider seed skipped/failed: %s", exc)
        return "env-fallback"
    return row.provider_code if row is not None else "env-fallback"
