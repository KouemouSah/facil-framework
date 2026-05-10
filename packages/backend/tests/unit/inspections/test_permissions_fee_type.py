# -*- coding: utf-8 -*-
"""
Tests for P3.D — fee_type / ministry scope enforcement.

Plan: .claude/plans/INSPECTION_BUNDLE_P3_DETAIL.md §3 P3.F

Tests:
  - compute_collection_scope returns correct tuples for each role
  - check_obligations_in_scope flags wrong fee_type / ministry
  - collect_field_payment raises PermissionError for out-of-scope obligations
  - Happy paths for polyvalent + independent + ministry agents
"""

import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.fiscal_services.services.oms_agent_service import (  # noqa: E402
    OmsAgentService,
)
from app.modules.inspections.services.collection_service import (  # noqa: E402
    CollectionService,
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


# ═══════════════════════════════════════════════════════════════
# P3.F.2 - P3.F.5 — compute_collection_scope per role
# ═══════════════════════════════════════════════════════════════


def test_compute_scope_polyvalent():
    ctx = {
        "is_polyvalent": True,
        "is_independent": False,
        "queue_fee_type": None,
        "ministry_id": None,
    }
    allowed, ministry = OmsAgentService.compute_collection_scope(ctx)
    # Addendum 3 correctly applied: polyvalent = tesoro only
    assert allowed == {"tesoro"}
    assert ministry is None


def test_compute_scope_ayuntamiento():
    ctx = {
        "is_polyvalent": False,
        "is_independent": True,
        "queue_fee_type": "municipal",
        "ministry_id": None,
    }
    allowed, ministry = OmsAgentService.compute_collection_scope(ctx)
    assert allowed == {"municipal"}
    assert ministry is None


def test_compute_scope_camara():
    ctx = {
        "is_polyvalent": False,
        "is_independent": True,
        "queue_fee_type": "chamber",
        "ministry_id": None,
    }
    allowed, ministry = OmsAgentService.compute_collection_scope(ctx)
    assert allowed == {"chamber"}
    assert ministry is None


def test_compute_scope_ministry_agricultura():
    ctx = {
        "is_polyvalent": False,
        "is_independent": False,
        "queue_fee_type": None,
        "ministry_id": 104,  # MIN_AGRICULTURA
    }
    allowed, ministry = OmsAgentService.compute_collection_scope(ctx)
    assert allowed == {"tesoro"}
    assert ministry == 104


def test_compute_scope_independent_without_fee_type_defensive():
    """Defensive: independent role without fee_type mapping returns empty set."""
    ctx = {
        "is_polyvalent": False,
        "is_independent": True,
        "queue_fee_type": None,  # Bug case
        "ministry_id": None,
    }
    allowed, ministry = OmsAgentService.compute_collection_scope(ctx)
    assert allowed == set()
    assert ministry is None


# ═══════════════════════════════════════════════════════════════
# P3.F.6 - P3.F.8 — check_obligations_in_scope
# ═══════════════════════════════════════════════════════════════


def test_check_obligations_all_allowed_tesoro_ministry_match():
    obls = [
        {"id": uuid4(), "fee_type": "tesoro", "ministry_id": 104},
        {"id": uuid4(), "fee_type": "tesoro", "ministry_id": 104},
    ]
    forbidden = OmsAgentService.check_obligations_in_scope(
        obls, allowed_fee_types={"tesoro"}, required_ministry_id=104,
    )
    assert forbidden == []


def test_check_obligations_wrong_fee_type_flagged():
    obls = [
        {"id": uuid4(), "fee_type": "tesoro", "ministry_id": 104},
        {"id": uuid4(), "fee_type": "municipal", "ministry_id": 107},
    ]
    forbidden = OmsAgentService.check_obligations_in_scope(
        obls, allowed_fee_types={"tesoro"}, required_ministry_id=104,
    )
    assert len(forbidden) == 1
    assert forbidden[0]["fee_type"] == "municipal"
    assert "fee_type" in forbidden[0]["reason"]


def test_check_obligations_wrong_ministry_flagged():
    obls = [
        {"id": uuid4(), "fee_type": "tesoro", "ministry_id": 104},  # OK
        {"id": uuid4(), "fee_type": "tesoro", "ministry_id": 91},   # wrong ministry
    ]
    forbidden = OmsAgentService.check_obligations_in_scope(
        obls, allowed_fee_types={"tesoro"}, required_ministry_id=104,
    )
    assert len(forbidden) == 1
    assert forbidden[0]["ministry_id"] == 91
    assert "ministry_id" in forbidden[0]["reason"]


def test_check_obligations_polyvalent_municipal_blocked():
    """Addendum 3: polyvalent allowed_fee_types={'tesoro'} → municipal blocked."""
    obls = [
        {"id": uuid4(), "fee_type": "tesoro", "ministry_id": 91},  # OK
        {"id": uuid4(), "fee_type": "municipal", "ministry_id": 107},  # blocked
        {"id": uuid4(), "fee_type": "chamber", "ministry_id": 108},  # blocked
    ]
    # Polyvalent scope
    forbidden = OmsAgentService.check_obligations_in_scope(
        obls, allowed_fee_types={"tesoro"}, required_ministry_id=None,
    )
    assert len(forbidden) == 2
    forbidden_fee_types = {f["fee_type"] for f in forbidden}
    assert forbidden_fee_types == {"municipal", "chamber"}


def test_check_obligations_no_fee_type_filter_means_all_allowed():
    """allowed_fee_types=None means any fee_type passes."""
    obls = [
        {"id": uuid4(), "fee_type": "tesoro", "ministry_id": 91},
        {"id": uuid4(), "fee_type": "municipal", "ministry_id": 107},
    ]
    forbidden = OmsAgentService.check_obligations_in_scope(
        obls, allowed_fee_types=None, required_ministry_id=None,
    )
    assert forbidden == []


# ═══════════════════════════════════════════════════════════════
# P3.F.9 — collect_field_payment blocks wrong fee_type (E2E)
# ═══════════════════════════════════════════════════════════════


async def test_collect_field_payment_blocks_wrong_ministry(conn):
    """
    An agent_min_* trying to collect an obligation of another ministry
    must raise PermissionError via CollectionService.collect_field_payment.

    We pick: licence with tesoro obligation ministry X, agent of ministry Y.
    """
    # Find 2 distinct ministries both having tesoro obligations pending
    rows = await conn.fetch(
        """
        SELECT DISTINCT lo.ministry_id
        FROM license_obligations lo
        JOIN commercial_licenses cl ON cl.id = lo.license_id
        WHERE lo.fee_type = 'tesoro'
          AND lo.status IN ('pending', 'overdue')
          AND lo.ministry_id IS NOT NULL
          AND cl.service_request_id IS NULL
        LIMIT 5
        """
    )
    ministries = [r["ministry_id"] for r in rows]
    if len(ministries) < 2:
        pytest.skip("Need 2+ ministries with pending tesoro obligations")

    obligation_ministry = ministries[0]
    agent_ministry = ministries[1]

    # Find licence + obligations for ministry[0]
    lic_row = await conn.fetchrow(
        """
        SELECT cl.id, cl.company_id,
               array_agg(lo.id) as obl_ids,
               sum(lo.amount + lo.penalty_amount) as total
        FROM commercial_licenses cl
        JOIN license_obligations lo ON lo.license_id = cl.id
        WHERE lo.fee_type = 'tesoro'
          AND lo.status IN ('pending', 'overdue')
          AND lo.ministry_id = $1
          AND cl.service_request_id IS NULL
        GROUP BY cl.id, cl.company_id
        LIMIT 1
        """,
        obligation_ministry,
    )
    if not lic_row:
        pytest.skip("No licence with obligations for selected ministry")

    # Find agent of ministry[1] (different from obligations' ministry)
    agent_row = await conn.fetchrow(
        """
        SELECT u.id, ap.id AS agent_profile_id, ap.entity_id, ap.entity_location_id
        FROM users u
        JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
        JOIN roles r ON r.id = u.role_id
        WHERE r.code LIKE 'agent_min_%'
          AND ap.ministry_id = $1
        LIMIT 1
        """,
        agent_ministry,
    )
    if not agent_row:
        pytest.skip(f"No agent_min_* matches ministry {agent_ministry}")

    # Create inspection owned by the wrong-ministry agent
    insp_id = uuid4()
    await conn.execute(
        """
        INSERT INTO field_inspections (
            id, agent_id, agent_profile_id, entity_id, entity_location_id,
            license_id, company_id, status, result, inspection_date
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, 'in_progress', 'pending', CURRENT_DATE
        )
        """,
        insp_id, agent_row["id"], agent_row["agent_profile_id"],
        agent_row["entity_id"], agent_row["entity_location_id"],
        lic_row["id"], lic_row["company_id"],
    )

    # Try to collect obligations of the wrong ministry → must raise PermissionError
    with pytest.raises(PermissionError, match="fee_type/ministry scope"):
        await CollectionService.collect_field_payment(
            conn,
            inspection_id=insp_id,
            user_id=agent_row["id"],
            obligation_ids=lic_row["obl_ids"],
            method="cash",
            amount=Decimal(str(lic_row["total"])),
        )


# ═══════════════════════════════════════════════════════════════
# P3.F.11 — Polyvalent agent collects tesoro obligation — OK
# ═══════════════════════════════════════════════════════════════


async def test_collect_field_payment_polyvalent_tesoro_ok(conn):
    """agent_oms_polyvalent can collect any tesoro obligation regardless of ministry."""
    # Find polyvalent agent
    agent_row = await conn.fetchrow(
        """
        SELECT u.id, ap.id AS agent_profile_id, ap.entity_id, ap.entity_location_id
        FROM users u
        JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
        JOIN roles r ON r.id = u.role_id
        WHERE r.code = 'agent_oms_polyvalent'
          AND ap.is_active = true
        LIMIT 1
        """
    )
    if not agent_row:
        pytest.skip("No agent_oms_polyvalent found")

    # Find licence with tesoro obligation
    lic_row = await conn.fetchrow(
        """
        SELECT cl.id, cl.company_id,
               lo.id as obl_id, (lo.amount + lo.penalty_amount) as total
        FROM commercial_licenses cl
        JOIN license_obligations lo ON lo.license_id = cl.id
        WHERE lo.fee_type = 'tesoro'
          AND lo.status IN ('pending', 'overdue')
          AND cl.service_request_id IS NULL
        LIMIT 1
        """
    )
    if not lic_row:
        pytest.skip("No licence with pending tesoro obligation")

    # Create inspection
    insp_id = uuid4()
    await conn.execute(
        """
        INSERT INTO field_inspections (
            id, agent_id, agent_profile_id, entity_id, entity_location_id,
            license_id, company_id, status, result, inspection_date
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, 'in_progress', 'pending', CURRENT_DATE
        )
        """,
        insp_id, agent_row["id"], agent_row["agent_profile_id"],
        agent_row["entity_id"], agent_row["entity_location_id"],
        lic_row["id"], lic_row["company_id"],
    )

    # Collect tesoro — polyvalent is allowed
    result = await CollectionService.collect_field_payment(
        conn,
        inspection_id=insp_id,
        user_id=agent_row["id"],
        obligation_ids=[lic_row["obl_id"]],
        method="cash",
        amount=Decimal(str(lic_row["total"])),
    )
    assert result["status"] == "field_collected"
    assert result["payment_reference"].startswith("FLD-")


# ═══════════════════════════════════════════════════════════════
# P3.F.12 — Polyvalent blocked on municipal (Addendum 3)
# ═══════════════════════════════════════════════════════════════


async def test_collect_field_payment_polyvalent_municipal_rejected(conn):
    """agent_oms_polyvalent CANNOT collect municipal (Addendum 3)."""
    agent_row = await conn.fetchrow(
        """
        SELECT u.id, ap.id AS agent_profile_id, ap.entity_id, ap.entity_location_id
        FROM users u
        JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
        JOIN roles r ON r.id = u.role_id
        WHERE r.code = 'agent_oms_polyvalent' AND ap.is_active = true
        LIMIT 1
        """
    )
    if not agent_row:
        pytest.skip("No agent_oms_polyvalent found")

    lic_row = await conn.fetchrow(
        """
        SELECT cl.id, cl.company_id, lo.id as obl_id,
               (lo.amount + lo.penalty_amount) as total
        FROM commercial_licenses cl
        JOIN license_obligations lo ON lo.license_id = cl.id
        WHERE lo.fee_type = 'municipal'
          AND lo.status IN ('pending', 'overdue')
          AND cl.service_request_id IS NULL
        LIMIT 1
        """
    )
    if not lic_row:
        pytest.skip("No licence with pending municipal obligation")

    insp_id = uuid4()
    await conn.execute(
        """
        INSERT INTO field_inspections (
            id, agent_id, agent_profile_id, entity_id, entity_location_id,
            license_id, company_id, status, result, inspection_date
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, 'in_progress', 'pending', CURRENT_DATE
        )
        """,
        insp_id, agent_row["id"], agent_row["agent_profile_id"],
        agent_row["entity_id"], agent_row["entity_location_id"],
        lic_row["id"], lic_row["company_id"],
    )

    with pytest.raises(PermissionError, match="fee_type"):
        await CollectionService.collect_field_payment(
            conn,
            inspection_id=insp_id,
            user_id=agent_row["id"],
            obligation_ids=[lic_row["obl_id"]],
            method="cash",
            amount=Decimal(str(lic_row["total"])),
        )
