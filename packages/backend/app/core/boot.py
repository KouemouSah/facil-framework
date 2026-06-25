"""Boot-step helper — run idempotent startup steps without silent failures.

The lifespan runs several idempotent seeds (RBAC, reference data, org backfill) and
the config-store DB load. They must not crash the boot — first boot may be
pre-migration — but the previous ``contextlib.suppress(Exception)`` was *totally
silent*: a half-applied RBAC catalog or a missing config table in production passed
unnoticed. This wrapper keeps the never-crash guarantee while logging loudly, so the
benign pre-migration case and a real prod failure are both visible (and triageable).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def run_boot_step(name: str, run: Callable[[], Awaitable[object]]) -> bool:
    """Run ``run()``; return True on success, False on failure (never raises).

    On failure logs a WARNING (benign pre-migration, or a real error in prod —
    either way no longer swallowed in silence).
    """
    try:
        await run()
        return True
    except Exception as exc:  # noqa: BLE001 — boot must survive; failure is logged
        logger.warning(
            "boot step %r skipped/failed — benign pre-migration, or a real error in "
            "production (investigate): %s", name, exc)
        return False
