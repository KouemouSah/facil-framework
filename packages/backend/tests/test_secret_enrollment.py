"""F1 — observable, fail-loud enrollment of the default secrets provider (A1a)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers import secret_enrollment as se  # noqa: E402


@pytest.mark.asyncio
async def test_enrolls_openbao_and_labels_it(client, monkeypatch):
    _, db = client
    monkeypatch.setenv("OPENBAO_ROLE_ID", "rid-1")
    label = await se.enroll_secrets_provider(db, env=dict(__import__("os").environ))
    assert label == "openbao"


@pytest.mark.asyncio
async def test_no_approle_labels_env_fallback(client, monkeypatch):
    _, db = client
    monkeypatch.delenv("OPENBAO_ROLE_ID", raising=False)
    label = await se.enroll_secrets_provider(db, env={})
    assert label == "env-fallback"  # resolve_secret will read the env


@pytest.mark.asyncio
async def test_disabled_by_knob(client):
    _, db = client
    label = await se.enroll_secrets_provider(
        db, env={"SECRETS_PROVIDER_SEED_ON_BOOT": "0", "OPENBAO_ROLE_ID": "rid-1"})
    assert label == "disabled"


@pytest.mark.asyncio
async def test_enroll_failure_with_vault_required_fails_closed(client, monkeypatch):
    _, db = client

    async def _boom(session, *, env=None):
        raise RuntimeError("table provider_settings missing")

    monkeypatch.setattr(se, "seed_default_secrets_provider", _boom)
    with pytest.raises(RuntimeError):
        await se.enroll_secrets_provider(
            db, env={"OPENBAO_ROLE_ID": "rid-1", "SECRETS_VAULT_REQUIRED": "1"})


@pytest.mark.asyncio
async def test_premigration_does_not_fail_closed_even_when_required(client, monkeypatch):
    # B1 regression: a pre-migration boot (config DB not loaded) must NOT crash even
    # when the vault is required — migrations run out-of-band, a replica may start
    # before the schema exists. Fail-closed only once the DB is confirmed ready.
    _, db = client

    async def _boom(session, *, env=None):
        raise RuntimeError('relation "provider_settings" does not exist')

    monkeypatch.setattr(se, "seed_default_secrets_provider", _boom)
    label = await se.enroll_secrets_provider(
        db, env={"OPENBAO_ROLE_ID": "rid-1", "SECRETS_VAULT_REQUIRED": "1"},
        db_ready=False)
    assert label == "env-fallback"  # benign pre-migration, boot survives


@pytest.mark.asyncio
async def test_enroll_failure_in_dev_logs_error_not_silent(client, monkeypatch, caplog):
    _, db = client

    async def _boom(session, *, env=None):
        raise RuntimeError("transient")

    monkeypatch.setattr(se, "seed_default_secrets_provider", _boom)
    with caplog.at_level(logging.ERROR):
        label = await se.enroll_secrets_provider(
            db, env={"OPENBAO_ROLE_ID": "rid-1", "ENVIRONMENT": "development"})
    assert label == "env-fallback"
    assert any("enrollment failed" in r.message for r in caplog.records)
