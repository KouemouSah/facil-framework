"""Module-resource reconciliation (Phase 1bis).

When a module is enabled, its declared resources are reconciled at boot against the
**system** providers (ADR-0010: the module declares, the system provider provisions):

  - `config_defaults`      -> seeded into the config-store IF ABSENT (never overrides
                              an admin/runtime value; idempotent);
  - `required_secret_keys` -> VALIDATED via the active secrets provider — a runtime
                              cannot forge a secret, so a missing key is *reported*
                              (loud, surfaced), not created;
  - `required_buckets`     -> ensured via the active storage provider's `ensure_bucket`
                              (best-effort: the least-privilege runtime SA may lack
                              CreateBucket, so a failure is captured, never fatal — the
                              deploy/bootstrap layer is the privileged fallback).

Everything is non-fatal: a module may be enabled before its infra is fully ready. The
returned report is meant to surface in /health.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config_store import repository as settings_repo
from app.core.module_registry import ModuleManifest
from app.core.providers.registry import ProviderRegistry
from app.core.providers.secret_resolver import resolve_secret

logger = logging.getLogger(__name__)


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, (dict, list)):
        return "json"
    return "string"


async def reconcile_module_resources(
    manifest: ModuleManifest, module_name: str, *,
    session: AsyncSession, registry: ProviderRegistry, storage=None,
) -> dict[str, list]:
    """Reconcile one module's declared resources. Caller commits. Non-fatal."""
    report: dict[str, list] = {
        "config_seeded": [], "secrets_missing": [],
        "buckets_ensured": [], "bucket_errors": [],
    }

    # 1. config defaults — seed only if the key is absent (never override).
    for key, value in (manifest.config_defaults or {}).items():
        if await settings_repo.get_setting(session, key) is not None:
            continue
        await settings_repo.upsert_setting(
            session, key, value, value_type=_value_type(value),
            updated_by=f"module:{module_name}")
        report["config_seeded"].append(key)

    # 2. required secret keys — validate, never forge. `is None` (pas `not`) : une
    # valeur vide "" est presente-mais-vide, un cas distinct d'un secret absent.
    for name in (manifest.required_secret_keys or []):
        if await resolve_secret(name, session, registry) is None:
            report["secrets_missing"].append(name)
            logger.warning(
                "module '%s' requires secret '%s' but it is not resolvable — provision "
                "it in the vault / env.", module_name, name)

    # 3. required buckets — ensure via the active storage provider (best-effort).
    buckets = manifest.required_buckets or []
    if buckets and storage is None:
        try:
            storage = await registry.get_default("storage", session)
        except LookupError:
            storage = None
    for bucket in buckets:
        if storage is None:
            report["bucket_errors"].append([bucket, "no active storage provider"])
            continue
        try:
            await storage.ensure_bucket(bucket)
            report["buckets_ensured"].append(bucket)
        except Exception as e:  # noqa: BLE001 — non-fatal; deploy layer is the fallback
            report["bucket_errors"].append([bucket, f"{type(e).__name__}: {e}"])
            logger.warning(
                "module '%s' bucket '%s' not ensured at runtime (%s) — the deploy "
                "bootstrap should provision it.", module_name, bucket, e)

    return report
