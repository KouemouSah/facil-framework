"""Phase 1 — generalize the boot-time default-provider seed to storage/llm/email.

Mirrors the `secrets` keystone (seed_default_secrets_provider): enroll the
config-declared default provider for each capability so `registry.get_default`
resolves on a fresh deploy WITHOUT a manual admin entry — env-driven
(config.yaml -> env via render_env), idempotent, never overriding an admin choice.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers import repository as repo  # noqa: E402
from app.core.providers.seed import seed_default_providers  # noqa: E402


@pytest.mark.asyncio
async def test_enrolls_storage_default_from_env(session):
    seeded = await seed_default_providers(session, env={"STORAGE_PROVIDER": "minio"})
    row = await repo.get_default(session, "storage")
    assert row is not None
    assert row.provider_code == "minio"
    assert row.is_default is True
    assert "storage" in seeded


@pytest.mark.asyncio
async def test_enrolls_email_from_env(session):
    await seed_default_providers(session, env={"EMAIL_PROVIDER": "smtp"})
    email = await repo.get_default(session, "email")
    assert email is not None and email.provider_code == "smtp"


@pytest.mark.asyncio
async def test_llm_is_not_seeded_router_owns_role_routing(session):
    # llm is deliberately NOT a single-default capability: the LLMRouter resolves
    # role -> provider from ai.routing/ai.providers (ADR-0002) with sovereign Ollama
    # defaults baked in, and calls registry.build('llm', ...) directly — get_default
    # ('llm') is never consulted. Seeding provider_settings for 'llm' would be dead
    # data, so LLM_PROVIDER must be ignored here.
    seeded = await seed_default_providers(session, env={"LLM_PROVIDER": "ollama"})
    assert "llm" not in seeded
    assert await repo.get_default(session, "llm") is None


@pytest.mark.asyncio
async def test_skips_capability_when_env_absent(session):
    seeded = await seed_default_providers(session, env={})
    assert seeded == []
    assert await repo.get_default(session, "storage") is None


@pytest.mark.asyncio
async def test_preserves_existing_admin_default(session):
    # An admin already chose s3 for storage. A boot seed must NEVER override it.
    await repo.upsert_provider(session, "storage", "s3", updated_by="admin")
    await repo.set_default(session, "storage", "s3")

    seeded = await seed_default_providers(session, env={"STORAGE_PROVIDER": "minio"})

    row = await repo.get_default(session, "storage")
    assert row.provider_code == "s3"          # admin choice intact
    assert "storage" not in seeded            # nothing seeded for storage


@pytest.mark.asyncio
async def test_ignores_unregistered_code(session):
    # A config typo must not create a broken default (get_default would then raise
    # KeyError at build time). Enroll only registered (capability, code) pairs.
    seeded = await seed_default_providers(session, env={"STORAGE_PROVIDER": "bogus"})
    assert seeded == []
    assert await repo.get_default(session, "storage") is None


@pytest.mark.asyncio
async def test_seeded_rows_are_labelled(session):
    await seed_default_providers(session, env={"STORAGE_PROVIDER": "minio"})
    row = await repo.get_default(session, "storage")
    assert row.updated_by == "seed:boot"      # observable provenance, like secrets seed


@pytest.mark.asyncio
async def test_rerun_is_idempotent(session):
    await seed_default_providers(session, env={"STORAGE_PROVIDER": "minio"})
    seeded = await seed_default_providers(session, env={"STORAGE_PROVIDER": "minio"})
    assert seeded == []                        # already the default, nothing to do
    rows = await repo.list_providers(session, "storage")
    assert len(rows) == 1                      # no duplicate row
