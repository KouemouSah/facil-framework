"""Hydrate the backend's infra secrets from OpenBao at startup (S2).

In ``secrets=openbao`` mode the vault (``facil/{boot,runtime,infra}``) is the
source of truth for the creds the backend consumes — ``DATABASE_URL`` and the
MinIO service account. The deploy layer also renders them into the env as a
fallback, but the vault is *fresher*: after a password rotation the env file can
be stale while the vault already holds the new value. So when the vault is
reachable we **override** the env with the vault values **before** settings / the
DB engine are built; when it is not, we fall back to the env with a loud warning —
or hard-fail when ``SECRETS_VAULT_REQUIRED=1`` (the production posture: refuse to
start on possibly-stale secrets).

Design notes
------------
- Runs *before* ``get_settings()`` / ``Database(...)`` because ``DATABASE_URL`` is
  consumed first and the registry (which would otherwise resolve secrets) does not
  exist yet — a chicken-and-egg the AppRole env creds (OPENBAO_ROLE_ID/SECRET_ID)
  break cleanly.
- Reuses ``OpenBaoSecretsProvider`` (same AppRole login + kv-v2 read) — no second
  vault client.
- Retries **connection** transients only; an auth/permission error (HTTP 4xx) is
  not retried (it will not self-heal).
- Never logs secret *values* — only the names of the keys applied.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import MutableMapping

import httpx

from app.core.env_posture import is_dev, is_required
from app.core.providers.secrets_openbao import OpenBaoSecretsProvider

logger = logging.getLogger(__name__)

# Infra creds the backend consumes that the vault mirrors (facil/runtime + infra).
INFRA_KEYS = (
    "DATABASE_URL",
    "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET",
)


def _safe_detail(exc: Exception) -> str:
    """A log-safe summary of a vault error — never the body/URL (may echo creds)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code} from OpenBao"
    if isinstance(exc, httpx.RequestError):
        return f"{type(exc).__name__} contacting OpenBao"
    return type(exc).__name__


async def _load_with_retry(provider, *, attempts: int, delay: float, sleep) -> dict:
    """Load all vault secrets, retrying connection transients (not auth errors).

    Only ``httpx`` errors are caught here: an auth/permission error
    (``HTTPStatusError``) is re-raised at once (a retry will not help), connection
    transients (``RequestError``) are retried. Any NON-httpx exception (KeyError on
    a malformed response, a programming bug, …) propagates untouched so the caller
    never mistakes a code defect for "the vault is down".
    """
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await provider.load_all()
        except httpx.HTTPStatusError:
            raise  # auth / permission / path error — a retry will not help
        except httpx.RequestError as exc:  # connect/read/timeout — transient
            last = exc
            if i + 1 < attempts:
                await sleep(delay)
    assert last is not None
    raise last


async def hydrate_secrets_from_vault(
    *,
    env: MutableMapping[str, str] | None = None,
    sleep=asyncio.sleep,
    attempts: int = 5,
    delay: float = 1.0,
    provider_factory=OpenBaoSecretsProvider,
) -> dict:
    """Override infra creds in ``env`` with the vault's, when applicable.

    Returns a small report ``{"source", "keys", ...}`` (no secret values) for
    logging/observability. ``source`` ∈ {disabled, env-only, vault, env-fallback}.
    """
    env = os.environ if env is None else env

    if env.get("SECRETS_VAULT_HYDRATE", "1") == "0":
        return {"source": "disabled", "keys": [], "mutated": False}
    if not env.get("OPENBAO_ROLE_ID"):
        return {"source": "env-only", "keys": [], "mutated": False}

    # Fail-secure default: when the AppRole is present the vault is REQUIRED unless
    # the operator explicitly relaxes it (SECRETS_VAULT_REQUIRED=0) or we are in a
    # dev/test env. A prod deploy that forgets the knob fails closed, not open.
    required = is_required(env, "SECRETS_VAULT_REQUIRED")

    addr = env.get("OPENBAO_ADDR", "http://openbao:8200")
    # SEC-006: in production the AppRole login + every secret (DATABASE_URL, MinIO SA)
    # would transit in clear over http:// — refuse it (TLS is P7/P8). An operator can
    # opt out explicitly with OPENBAO_ALLOW_HTTP=1 (e.g. a trusted local network).
    if addr.startswith("http://") and not is_dev(env):
        if env.get("OPENBAO_ALLOW_HTTP") != "1":
            raise RuntimeError(
                "OpenBao address is plaintext http:// in production — refusing (the "
                "AppRole login and all secrets would transit in clear). Enable TLS "
                "(P7/P8) or set OPENBAO_ALLOW_HTTP=1 to override explicitly.")
        # Override used in prod — leave an audit trail of the deliberate downgrade.
        logger.warning("OPENBAO_ALLOW_HTTP=1: contacting OpenBao over plaintext http:// "
                       "in a non-dev environment — secrets transit in clear.")
    if required and addr.startswith("http://"):
        logger.warning("OpenBao address is plaintext http:// under a required "
                       "posture — enable TLS (P7/P8) before production exposure.")
    provider = provider_factory({
        "addr": addr, "kv_path": "facil", "paths": ["boot", "runtime", "infra"],
    })

    try:
        secrets = await _load_with_retry(
            provider, attempts=attempts, delay=delay, sleep=sleep)
    except httpx.HTTPError as exc:  # vault unreachable/refused — NOT a code bug
        detail = _safe_detail(exc)
        if required:
            raise RuntimeError(
                f"OpenBao hydration failed ({detail}) — refusing to start on "
                f"possibly-stale env secrets (SECRETS_VAULT_REQUIRED)."
            ) from exc
        logger.error(
            "OpenBao unreachable (%s) — FALLING BACK to env secrets, which may be "
            "stale after a rotation. Set SECRETS_VAULT_REQUIRED=1 to forbid this.",
            detail)
        return {"source": "env-fallback", "keys": [], "mutated": False,
                "error": detail}

    applied = []
    for key in INFRA_KEYS:
        val = secrets.get(key)
        if val and env.get(key) != val:
            env[key] = val
            applied.append(key)
    # Vault reachable but the infra path is empty => the bootstrap mirror did not
    # run or the policy lacks it. Surface it (don't fall back to env in silence).
    if "DATABASE_URL" not in secrets:
        logger.warning("OpenBao reachable but facil/infra has no DATABASE_URL — the "
                       "bootstrap infra mirror may not have run (or the facil-backend "
                       "policy lacks it). Backend uses the env DATABASE_URL fallback.")
    logger.info("hydrated %d infra secret(s) from OpenBao: %s",
                len(applied), ", ".join(applied) or "(none changed)")
    return {"source": "vault", "keys": applied, "mutated": bool(applied)}
