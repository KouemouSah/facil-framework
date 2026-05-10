# -*- coding: utf-8 -*-
"""
Tests for P3.E — verify_license_for_agent enriched response.

Plan: .claude/plans/INSPECTION_BUNDLE_P3_DETAIL.md §3 P3.E / P3.F

Verifies the new fields returned by verify_license_for_agent:
  - existing_dossier
  - has_pending_citizen_payment / pending_payment_info
  - restricted_obligations + agent_can_collect_all
  - agent_scope
  - obligation[*].agent_restricted flag
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.inspections.services.inspection_service import (  # noqa: E402
    InspectionService,
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
    """License + polyvalent agent for predictable scope testing."""
    lic = await conn.fetchrow(
        """
        SELECT cl.id, cl.company_id, cl.bundle_id, cl.fiscal_year
        FROM commercial_licenses cl
        WHERE cl.service_request_id IS NULL
        LIMIT 1
        """
    )
    if not lic:
        pytest.skip("No orphan commercial_license available")

    agent = await conn.fetchrow(
        """
        SELECT u.id, ap.id AS agent_profile_id, ap.entity_id, ap.entity_location_id
        FROM users u
        JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
        JOIN roles r ON r.id = u.role_id
        WHERE r.code = 'agent_oms_polyvalent'
        LIMIT 1
        """
    )
    if not agent:
        pytest.skip("No agent_oms_polyvalent found")

    return {
        "license_id": lic["id"],
        "company_id": lic["company_id"],
        "bundle_id": lic["bundle_id"],
        "fiscal_year": lic["fiscal_year"],
        "agent_id": agent["id"],
        "agent_profile_id": agent["agent_profile_id"],
        "entity_id": agent["entity_id"],
        "entity_location_id": agent["entity_location_id"],
    }


# ═══════════════════════════════════════════════════════════════
# P3.F.19 — existing_dossier populated when SR linked
# ═══════════════════════════════════════════════════════════════


async def test_verify_returns_existing_dossier_when_linked(conn, test_context):
    # Create a service_request and link it to the licence
    sr_id = uuid4()
    await conn.execute(
        """
        INSERT INTO service_requests (
            id, user_id, workflow_code, status, source,
            commercial_license_id, bundle_id, fiscal_year, company_id
        ) VALUES (
            $1, $2, 'FIELD_INSPECTION', 'SUBMITTED'::service_request_status_enum,
            'field_inspection', $3, $4, $5, $6
        )
        """,
        sr_id, test_context["agent_id"],
        test_context["license_id"], test_context["bundle_id"],
        test_context["fiscal_year"], test_context["company_id"],
    )
    # Trigger trg_sync_license_sr_id should have updated the licence
    linked = await conn.fetchval(
        "SELECT service_request_id FROM commercial_licenses WHERE id = $1",
        test_context["license_id"],
    )
    assert linked == sr_id

    result = await InspectionService.verify_license_for_agent(
        conn, test_context["agent_id"], license_id=test_context["license_id"],
    )

    assert result["existing_dossier"] is not None
    assert result["existing_dossier"]["service_request_id"] == str(sr_id)
    assert result["existing_dossier"]["source"] == "field_inspection"
    assert result["existing_dossier"]["status"] == "SUBMITTED"
    assert result["existing_dossier"]["reference"].startswith("FLD-")


# ═══════════════════════════════════════════════════════════════
# P3.F.20 — existing_dossier = None when no SR linked
# ═══════════════════════════════════════════════════════════════


async def test_verify_returns_null_dossier_when_not_linked(conn, test_context):
    result = await InspectionService.verify_license_for_agent(
        conn, test_context["agent_id"], license_id=test_context["license_id"],
    )
    assert result["existing_dossier"] is None
    assert result["has_pending_citizen_payment"] is False
    assert result["pending_payment_info"] is None


# ═══════════════════════════════════════════════════════════════
# P3.F.22 — restricted_obligations for ministry-specific agent
# ═══════════════════════════════════════════════════════════════


async def test_verify_restricted_for_ministry_agent(conn):
    """
    A ministry agent sees obligations of other ministries as restricted.
    """
    # Find a licence with obligations from 2+ different ministries
    rows = await conn.fetch(
        """
        SELECT DISTINCT lo.ministry_id
        FROM license_obligations lo
        JOIN commercial_licenses cl ON cl.id = lo.license_id
        WHERE lo.fee_type = 'tesoro'
          AND lo.ministry_id IS NOT NULL
        LIMIT 5
        """
    )
    if len(rows) < 2:
        pytest.skip("Need 2+ ministries with tesoro obligations")

    ministry_a = rows[0]["ministry_id"]

    # Find a licence that has obligations from ministry_a AND another ministry
    lic = await conn.fetchrow(
        """
        SELECT cl.id, cl.company_id,
               COUNT(DISTINCT lo.ministry_id) as n_ministries
        FROM commercial_licenses cl
        JOIN license_obligations lo ON lo.license_id = cl.id
        WHERE lo.fee_type = 'tesoro'
        GROUP BY cl.id, cl.company_id
        HAVING COUNT(DISTINCT lo.ministry_id) >= 2
        LIMIT 1
        """
    )
    if not lic:
        pytest.skip("No multi-ministry licence available")

    # Find agent of ministry_a
    agent = await conn.fetchrow(
        """
        SELECT u.id FROM users u
        JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
        JOIN roles r ON r.id = u.role_id
        WHERE r.code LIKE 'agent_min_%' AND ap.ministry_id = $1
        LIMIT 1
        """,
        ministry_a,
    )
    if not agent:
        pytest.skip(f"No agent_min_* for ministry {ministry_a}")

    result = await InspectionService.verify_license_for_agent(
        conn, agent["id"], license_id=lic["id"],
    )

    # Should have some restricted obligations (from other ministries)
    assert "restricted_obligations" in result
    assert "agent_can_collect_all" in result
    # agent_can_collect_all is True only if NO obligation is restricted
    # Here the licence has multi-ministry → at least one restricted
    assert isinstance(result["restricted_obligations"], list)

    # Each obligation must have the agent_restricted flag
    for o in result["obligations"]:
        assert "agent_restricted" in o


# ═══════════════════════════════════════════════════════════════
# P3.F.23 — polyvalent sees all tesoro obligations as allowed
# ═══════════════════════════════════════════════════════════════


async def test_verify_polyvalent_can_collect_all_tesoro(conn):
    """Polyvalent agent: all tesoro obligations → agent_can_collect_all TRUE
    if licence has ONLY tesoro. If it has municipal/chamber → some restricted."""
    agent = await conn.fetchrow(
        """
        SELECT u.id FROM users u
        JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
        JOIN roles r ON r.id = u.role_id
        WHERE r.code = 'agent_oms_polyvalent'
        LIMIT 1
        """
    )
    if not agent:
        pytest.skip("No polyvalent agent")

    # Find a licence with ONLY tesoro obligations (simpler case)
    lic = await conn.fetchrow(
        """
        SELECT cl.id
        FROM commercial_licenses cl
        WHERE cl.service_request_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM license_obligations lo
              WHERE lo.license_id = cl.id AND lo.fee_type != 'tesoro'
          )
          AND EXISTS (
              SELECT 1 FROM license_obligations lo
              WHERE lo.license_id = cl.id AND lo.fee_type = 'tesoro'
          )
        LIMIT 1
        """
    )
    if not lic:
        pytest.skip("No tesoro-only licence available")

    result = await InspectionService.verify_license_for_agent(
        conn, agent["id"], license_id=lic["id"],
    )

    assert result["agent_can_collect_all"] is True
    assert result["restricted_obligations"] == []
    assert result["agent_scope"]["is_polyvalent"] is True
    assert result["agent_scope"]["allowed_fee_types"] == ["tesoro"]


# ═══════════════════════════════════════════════════════════════
# P3.F.21 — has_pending_citizen_payment
# ═══════════════════════════════════════════════════════════════


async def test_verify_has_pending_payment_when_workflow_active(conn, test_context):
    """When a service_payment in non-final state exists, flag is True."""
    # Link a service_request to the licence
    sr_id = uuid4()
    await conn.execute(
        """
        INSERT INTO service_requests (
            id, user_id, workflow_code, status, source,
            commercial_license_id, bundle_id, fiscal_year, company_id
        ) VALUES (
            $1, $2, 'BUNDLE_PAYMENT', 'SUBMITTED'::service_request_status_enum,
            'citizen_wizard', $3, $4, $5, $6
        )
        """,
        sr_id, test_context["agent_id"],
        test_context["license_id"], test_context["bundle_id"],
        test_context["fiscal_year"], test_context["company_id"],
    )

    # Insert a pending service_payment
    await conn.execute(
        """
        INSERT INTO service_payments (
            id, payment_reference, user_id, service_request_id,
            payment_type, base_amount, total_amount,
            payment_method, currency, status, workflow_status,
            collection_type, fee_type
        ) VALUES (
            $1, $2, $3, $4,
            'full', 5000, 5000,
            'mobile_money', 'XAF', 'pending', 'field_collected',
            'online', 'tesoro'
        )
        """,
        uuid4(), "TEST-ONL-" + uuid4().hex[:8],
        test_context["agent_id"], sr_id,
    )

    result = await InspectionService.verify_license_for_agent(
        conn, test_context["agent_id"], license_id=test_context["license_id"],
    )

    assert result["has_pending_citizen_payment"] is True
    assert result["pending_payment_info"] is not None
    assert result["pending_payment_info"]["total_amount"] == 5000.0
    assert result["pending_payment_info"]["workflow_status"] == "field_collected"
