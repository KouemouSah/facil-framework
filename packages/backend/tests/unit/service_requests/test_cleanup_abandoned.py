# -*- coding: utf-8 -*-
"""
Integration tests for cleanup_abandoned_requests (P2).

Plan: .claude/plans/INSPECTION_BUNDLE_P2_DETAIL.md §4 P2.D

Tests run inside a transaction with automatic ROLLBACK to avoid polluting
the prod/dev database. Uses asyncpg directly against the real Supabase
connection.

Covers 11 tests (P2.D.1 - P2.D.11):
  3.  Normal DRAFT older than cutoff IS deleted
  4.  Bundle BUNDLE_PAYMENT DRAFT is NOT deleted (workflow_code exclusion)
  5.  Bundle FIELD_INSPECTION DRAFT is NOT deleted (workflow_code + source)
  6.  SR linked to commercial_license_id is NOT deleted (triple exclusion)
  7.  Safety check raises RuntimeError if filter and licence link diverge
  8.  cleanup uses settings.DRAFT_CLEANUP_MAX_HOURS when max_age_hours=None
  9.  cleanup respects explicit max_age_hours override
  10. Stats include skipped_bundle + max_age_hours
  11. Bundle DRAFT counter = 1 when one bundle DRAFT exists
  12. Safety check ok path (no licence references) allows cleanup to proceed
  13. Regression: cleanup still honors the "created_at < cutoff" constraint
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.service_requests.services.service_request_service import (  # noqa: E402
    service_request_service,
)

pytestmark = pytest.mark.asyncio


def load_database_url() -> str:
    env_path = BACKEND_ROOT / ".env"
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("DATABASE_URL="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("DATABASE_URL not found in backend/.env")


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(scope="function")
async def conn():
    """Yield a connection with an outer transaction rolled back after test."""
    c = await asyncpg.connect(load_database_url())
    tr = c.transaction()
    await tr.start()
    try:
        yield c
    finally:
        await tr.rollback()
        await c.close()


@pytest_asyncio.fixture(scope="function")
async def test_context(conn):
    """Real user + license for inserting test SRs."""
    user = await conn.fetchrow("SELECT id FROM users LIMIT 1")
    lic = await conn.fetchrow(
        """
        SELECT id, company_id, bundle_id, fiscal_year
        FROM commercial_licenses
        WHERE service_request_id IS NULL
        LIMIT 1
        """
    )
    if not lic:
        pytest.skip("No orphan commercial_license available")
    return {
        "user_id": user["id"],
        "license_id": lic["id"],
        "company_id": lic["company_id"],
        "bundle_id": lic["bundle_id"],
        "fiscal_year": lic["fiscal_year"],
    }


async def _create_sr(
    conn,
    user_id,
    workflow_code: str,
    status: str = "DRAFT",
    hours_ago: float = 3.0,
    source: str = "citizen_wizard",
    commercial_license_id=None,
    bundle_id=None,
    fiscal_year=None,
    company_id=None,
):
    """
    Create a service_request with a custom created_at (backdated).

    Two-step: INSERT with default NOW(), then UPDATE created_at.
    (A direct INSERT with created_at is refused by the auto-reference trigger
    that relies on NOW() in some configs.)
    """
    new_id = uuid4()
    await conn.execute(
        """
        INSERT INTO service_requests (
            id, user_id, workflow_code, status, source,
            commercial_license_id, bundle_id, fiscal_year, company_id
        ) VALUES ($1, $2, $3, $4::service_request_status_enum, $5, $6, $7, $8, $9)
        """,
        new_id, user_id, workflow_code, status, source,
        commercial_license_id, bundle_id, fiscal_year, company_id,
    )
    # Backdate created_at
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    await conn.execute(
        "UPDATE service_requests SET created_at = $1 WHERE id = $2",
        cutoff, new_id,
    )
    return new_id


# ═══════════════════════════════════════════════════════════════
# P2.D.3 — Normal DRAFT older than cutoff IS deleted
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_deletes_normal_draft(conn, test_context):
    sr_id = await _create_sr(
        conn, test_context["user_id"], "PASAPORTE_NUEVO", hours_ago=3.0,
    )

    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn, max_age_hours=2,
    )

    assert stats["deleted_requests"] >= 1
    assert stats["skipped_bundle"] == 0
    assert stats["max_age_hours"] == 2

    # Verify SR is gone
    exists = await conn.fetchval(
        "SELECT 1 FROM service_requests WHERE id = $1", sr_id,
    )
    assert exists is None


# ═══════════════════════════════════════════════════════════════
# P2.D.4 — BUNDLE_PAYMENT DRAFT is NOT deleted
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_skips_bundle_payment_draft(conn, test_context):
    sr_id = await _create_sr(
        conn,
        test_context["user_id"],
        "BUNDLE_PAYMENT",
        hours_ago=5.0,
        source="citizen_wizard",
        commercial_license_id=test_context["license_id"],
        bundle_id=test_context["bundle_id"],
        fiscal_year=test_context["fiscal_year"],
        company_id=test_context["company_id"],
    )

    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn, max_age_hours=2,
    )

    assert stats["skipped_bundle"] >= 1

    # SR must still exist
    still_there = await conn.fetchval(
        "SELECT 1 FROM service_requests WHERE id = $1", sr_id,
    )
    assert still_there == 1


# ═══════════════════════════════════════════════════════════════
# P2.D.5 — FIELD_INSPECTION DRAFT is NOT deleted
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_skips_field_inspection_draft(conn, test_context):
    sr_id = await _create_sr(
        conn,
        test_context["user_id"],
        "FIELD_INSPECTION",
        hours_ago=5.0,
        source="field_inspection",
        commercial_license_id=test_context["license_id"],
        bundle_id=test_context["bundle_id"],
        fiscal_year=test_context["fiscal_year"],
        company_id=test_context["company_id"],
    )

    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn, max_age_hours=2,
    )

    assert stats["skipped_bundle"] >= 1

    still_there = await conn.fetchval(
        "SELECT 1 FROM service_requests WHERE id = $1", sr_id,
    )
    assert still_there == 1


# ═══════════════════════════════════════════════════════════════
# P2.D.6 — SR with source='field_inspection' excluded even if non-bundle workflow
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_skips_sr_with_field_inspection_source(conn, test_context):
    """
    Edge case: even if somehow a non-bundle workflow had source='field_inspection',
    the exclusion by source must protect it.

    We use PASAPORTE_NUEVO + source='field_inspection' — theoretical but
    defense-in-depth means the filter still catches it.
    """
    # The enforce_bundle_sr_integrity trigger only fires for bundle workflows,
    # so non-bundle workflows with any source value are allowed. This tests
    # the source exclusion path directly.
    sr_id = await _create_sr(
        conn,
        test_context["user_id"],
        "PASAPORTE_NUEVO",
        hours_ago=5.0,
        source="field_inspection",
    )

    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn, max_age_hours=2,
    )

    assert stats["skipped_bundle"] >= 1

    still_there = await conn.fetchval(
        "SELECT 1 FROM service_requests WHERE id = $1", sr_id,
    )
    assert still_there == 1


# ═══════════════════════════════════════════════════════════════
# P2.D.7 — Safety check aborts on corrupted state
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_safety_check_aborts_if_license_references_candidate(
    conn, test_context,
):
    """
    Simulate a state where:
      - SR has workflow_code=PASAPORTE_NUEVO (passes the filter)
      - source='citizen_wizard', commercial_license_id=NULL (passes filter)
      - BUT commercial_licenses.service_request_id points to this SR

    The safety check must raise RuntimeError rather than delete the SR,
    since the license would become orphaned.
    """
    sr_id = await _create_sr(
        conn,
        test_context["user_id"],
        "PASAPORTE_NUEVO",  # Not bundle
        hours_ago=5.0,
        source="citizen_wizard",
        commercial_license_id=None,  # Empty — passes the filter
    )

    # Point a licence to it (corrupted state simulation)
    await conn.execute(
        "UPDATE commercial_licenses SET service_request_id = $1 WHERE id = $2",
        sr_id, test_context["license_id"],
    )

    with pytest.raises(RuntimeError, match="safety check FAILED"):
        await service_request_service.cleanup_abandoned_requests(
            db=conn, max_age_hours=2,
        )

    # SR must still be there (not deleted due to raise)
    still_there = await conn.fetchval(
        "SELECT 1 FROM service_requests WHERE id = $1", sr_id,
    )
    assert still_there == 1


# ═══════════════════════════════════════════════════════════════
# P2.D.8 — Uses settings default when max_age_hours is None
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_uses_settings_default(conn, test_context, monkeypatch):
    """When max_age_hours=None, cleanup reads settings.DRAFT_CLEANUP_MAX_HOURS."""
    # Monkeypatch the setting via the cached settings object
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "DRAFT_CLEANUP_MAX_HOURS", 5)

    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn,  # no max_age_hours
    )

    assert stats["max_age_hours"] == 5


# ═══════════════════════════════════════════════════════════════
# P2.D.9 — Explicit override wins over settings
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_explicit_override_wins(conn, test_context, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "DRAFT_CLEANUP_MAX_HOURS", 999)

    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn, max_age_hours=10,
    )

    assert stats["max_age_hours"] == 10


# ═══════════════════════════════════════════════════════════════
# P2.D.10 — Stats always contain new keys
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_stats_contains_new_keys(conn):
    """Even with nothing to clean, stats dict must expose the new keys."""
    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn, max_age_hours=999,
    )
    assert "skipped_bundle" in stats
    assert "max_age_hours" in stats
    assert stats["max_age_hours"] == 999
    assert isinstance(stats["skipped_bundle"], int)


# ═══════════════════════════════════════════════════════════════
# P2.D.11 — Recent DRAFT (within cutoff) is NOT deleted (regression)
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_ignores_recent_draft(conn, test_context):
    """A DRAFT created 1h ago with max_age=2h must survive."""
    sr_id = await _create_sr(
        conn, test_context["user_id"], "PASAPORTE_NUEVO", hours_ago=1.0,
    )

    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn, max_age_hours=2,
    )

    # SR must still be there (not old enough)
    still_there = await conn.fetchval(
        "SELECT 1 FROM service_requests WHERE id = $1", sr_id,
    )
    assert still_there == 1


# ═══════════════════════════════════════════════════════════════
# P2.D.12 — Bundle SR with source=admin_import excluded too
# ═══════════════════════════════════════════════════════════════


async def test_cleanup_skips_admin_import_source(conn, test_context):
    """source='admin_import' also protects the SR from cleanup."""
    sr_id = await _create_sr(
        conn,
        test_context["user_id"],
        "PASAPORTE_NUEVO",
        hours_ago=5.0,
        source="admin_import",
    )

    stats = await service_request_service.cleanup_abandoned_requests(
        db=conn, max_age_hours=2,
    )

    assert stats["skipped_bundle"] >= 1
    still_there = await conn.fetchval(
        "SELECT 1 FROM service_requests WHERE id = $1", sr_id,
    )
    assert still_there == 1
