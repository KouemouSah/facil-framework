"""run_boot_step — idempotent boot steps log loudly on failure (B/C, A1a)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.boot import run_boot_step  # noqa: E402


@pytest.mark.asyncio
async def test_success_returns_true_and_is_quiet(caplog):
    ran = {"n": 0}

    async def _ok():
        ran["n"] += 1

    with caplog.at_level(logging.WARNING):
        ok = await run_boot_step("demo", _ok)
    assert ok is True and ran["n"] == 1
    assert not caplog.records  # success is silent


@pytest.mark.asyncio
async def test_failure_returns_false_and_warns_loud(caplog):
    async def _boom():
        raise RuntimeError("table missing")

    with caplog.at_level(logging.WARNING):
        ok = await run_boot_step("rbac-seed", _boom)
    assert ok is False                      # never crashes the boot
    assert any("rbac-seed" in r.message for r in caplog.records)  # not silent
