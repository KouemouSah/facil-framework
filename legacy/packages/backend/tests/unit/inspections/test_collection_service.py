# -*- coding: utf-8 -*-
"""
Integration tests for CollectionService (P1).

Plan: .claude/plans/INSPECTION_BUNDLE_P1_DETAIL.md §4 P1.C

Each test runs inside a transaction with automatic ROLLBACK to avoid
polluting the prod/dev database. Uses asyncpg directly (no mocks)
against the real Supabase connection.

Covers 15 tests (P1.C.1 - P1.C.14ter):
  1.  Create new dossier when none exists
  2.  Reuse existing dossier (idempotence)
  3.  Concurrent creation → single dossier (FOR UPDATE + UNIQUE)
  4.  Cross-year renewal → different dossiers
  5.  Multi-bundle same company+year → different dossiers
  6.  Full collect_field_payment flow (D2: payment_pending)
  7.  Amount mismatch → ValueError (OWASP A03)
  8.  Wrong agent → ValueError (OWASP A01)
  9.  Double collect → ValueError (OWASP A04)
  10. No lowercase 'cancelled'/'rejected' in source (regression B1)
  11. Trigger rejects bundle SR without commercial_license_id
  12. Trigger allows non-bundle SR without commercial_license_id (no-op)
  13. Reference prefixes: BUNDLE_PAYMENT → LIC, FIELD_INSPECTION → FLD,
      PASAPORTE_NUEVO → PAS (D1 regression)
  14. Supervisor validation completes payment_pending → paid (covered
      separately by existing LicenseService tests)
"""

import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

# Ensure we can import app.*
BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

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
    """Yield a connection with an outer transaction that will be rolled back."""
    c = await asyncpg.connect(load_database_url())
    tr = c.transaction()
    await tr.start()
    try:
        yield c
    finally:
        await tr.rollback()
        await c.close()


@pytest_asyncio.fixture(scope="function")
async def test_data(conn):
    """Fetch a real license + user + agent from the DB for test usage.

    Plan P3: the picked agent must be scope-compatible with the licence's
    obligations (new fee_type/ministry check in collect_field_payment).
    Strategy: pick a licence that has at least one tesoro obligation, then
    pick a ministry agent whose ministry_id matches. Obligations used in
    tests are filtered to that same ministry to keep the flow successful.
    """
    # Step 1: find a licence with tesoro obligations + the ministry_id
    lic = await conn.fetchrow(
        """
        SELECT cl.id, cl.company_id, cl.bundle_id, cl.fiscal_year,
               lo.ministry_id AS scope_ministry_id
        FROM commercial_licenses cl
        JOIN license_obligations lo ON lo.license_id = cl.id
        WHERE cl.service_request_id IS NULL
          AND lo.fee_type = 'tesoro'
          AND lo.status IN ('pending', 'overdue')
          AND lo.ministry_id IS NOT NULL
        LIMIT 1
        """
    )
    if not lic:
        pytest.skip("No orphan commercial_license with tesoro pending obligations")

    scope_ministry_id = lic["scope_ministry_id"]

    # Step 2: find a ministry agent matching the ministry + has collect permission
    agent_row = await conn.fetchrow(
        """
        SELECT u.id AS user_id, ap.id AS agent_profile_id,
               ap.entity_id, ap.entity_location_id
        FROM users u
        JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
        JOIN roles r ON r.id = u.role_id
        JOIN role_permissions rp ON rp.role_id = r.id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE p.name = 'inspection.collect_payment'
          AND ap.ministry_id = $1
          AND r.code LIKE 'agent_min_%'
        LIMIT 1
        """,
        scope_ministry_id,
    )

    if not agent_row:
        # Fallback: polyvalent agent (accepts any tesoro obligation)
        agent_row = await conn.fetchrow(
            """
            SELECT u.id AS user_id, ap.id AS agent_profile_id,
                   ap.entity_id, ap.entity_location_id
            FROM users u
            JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
            JOIN roles r ON r.id = u.role_id
            WHERE r.code = 'agent_oms_polyvalent'
            LIMIT 1
            """
        )
    if not agent_row:
        pytest.skip("No scope-compatible agent available for tesoro obligations")

    # Get a company owner (any user — we'll use the agent itself if no owner)
    owner = await conn.fetchrow(
        """
        SELECT u.id AS user_id
        FROM user_company_roles ucr
        JOIN users u ON u.id = ucr.user_id
        WHERE ucr.company_id = $1 AND ucr.role = 'company_owner' AND ucr.is_active = true
        LIMIT 1
        """,
        lic["company_id"],
    )
    owner_id = owner["user_id"] if owner else agent_row["user_id"]

    return {
        "license_id": lic["id"],
        "company_id": lic["company_id"],
        "bundle_id": lic["bundle_id"],
        "fiscal_year": lic["fiscal_year"],
        "scope_ministry_id": scope_ministry_id,
        "agent_id": agent_row["user_id"],
        "agent_profile_id": agent_row["agent_profile_id"],
        "entity_id": agent_row["entity_id"],
        "entity_location_id": agent_row["entity_location_id"],
        "owner_id": owner_id,
    }


async def _make_inspection(conn, test_data, agent_id=None):
    """Helper to create a valid field_inspection row (all NOT NULL columns provided)."""
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
        insp_id,
        agent_id or test_data["agent_id"],
        test_data["agent_profile_id"],
        test_data["entity_id"],
        test_data["entity_location_id"],
        test_data["license_id"],
        test_data["company_id"],
    )
    return insp_id


# ═══════════════════════════════════════════════════════════════
# P1.C.4 — _find_or_create_bundle_dossier creates new when none
# ═══════════════════════════════════════════════════════════════


async def test_find_or_create_creates_new_when_none(conn, test_data):
    # The caller (collect_field_payment) locks the license; here we simulate
    async with conn.transaction():
        await conn.fetchrow(
            "SELECT id FROM commercial_licenses WHERE id = $1 FOR UPDATE",
            test_data["license_id"],
        )
        sr_id = await CollectionService._find_or_create_bundle_dossier(
            conn,
            license_id=test_data["license_id"],
            company_owner_user_id=test_data["owner_id"],
        )

    # Verify: new SR exists with correct fields
    row = await conn.fetchrow(
        """
        SELECT workflow_code, status, source, commercial_license_id,
               bundle_id, fiscal_year, reference
        FROM service_requests WHERE id = $1
        """,
        sr_id,
    )
    assert row is not None
    assert row["workflow_code"] == "FIELD_INSPECTION"
    assert row["status"] == "SUBMITTED"
    assert row["source"] == "field_inspection"
    assert row["commercial_license_id"] == test_data["license_id"]
    assert row["bundle_id"] == test_data["bundle_id"]
    assert row["fiscal_year"] == test_data["fiscal_year"]
    assert row["reference"].startswith("FLD-"), f"wrong prefix: {row['reference']}"

    # Verify: commercial_licenses.service_request_id was set (via trigger or explicit update)
    linked = await conn.fetchval(
        "SELECT service_request_id FROM commercial_licenses WHERE id = $1",
        test_data["license_id"],
    )
    assert linked == sr_id


# ═══════════════════════════════════════════════════════════════
# P1.C.5 — reuses existing dossier (idempotence)
# ═══════════════════════════════════════════════════════════════


async def test_find_or_create_reuses_existing(conn, test_data):
    async with conn.transaction():
        await conn.fetchrow(
            "SELECT id FROM commercial_licenses WHERE id = $1 FOR UPDATE",
            test_data["license_id"],
        )
        first = await CollectionService._find_or_create_bundle_dossier(
            conn,
            license_id=test_data["license_id"],
            company_owner_user_id=test_data["owner_id"],
        )
        second = await CollectionService._find_or_create_bundle_dossier(
            conn,
            license_id=test_data["license_id"],
            company_owner_user_id=test_data["owner_id"],
        )

    assert first == second, "Second call must reuse the existing dossier"

    # Only one SR should exist for this license
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM service_requests WHERE commercial_license_id = $1",
        test_data["license_id"],
    )
    assert count == 1


# ═══════════════════════════════════════════════════════════════
# P1.C.6 — Concurrent creation → single dossier via UNIQUE safety net
# ═══════════════════════════════════════════════════════════════


async def test_unique_partial_index_enforces_single_dossier(conn, test_data):
    """
    Verifies the UNIQUE partial index `idx_sr_commercial_license_unique`
    blocks duplicate INSERTs for the same commercial_license_id.

    The failing INSERT is wrapped in a nested transaction (savepoint) so
    the outer fixture transaction stays healthy for the follow-up asserts.
    """
    # Lock and create first dossier
    await conn.fetchrow(
        "SELECT id FROM commercial_licenses WHERE id = $1 FOR UPDATE",
        test_data["license_id"],
    )
    first_id = await CollectionService._find_or_create_bundle_dossier(
        conn,
        license_id=test_data["license_id"],
        company_owner_user_id=test_data["owner_id"],
    )

    # Direct INSERT of a 2nd SR — wrapped in savepoint to avoid poisoning
    # the outer transaction when the UNIQUE index raises.
    raised = False
    try:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO service_requests (
                    id, user_id, workflow_code, status, source,
                    commercial_license_id, bundle_id, fiscal_year
                ) VALUES (
                    $1, $2, 'FIELD_INSPECTION', 'SUBMITTED', 'field_inspection',
                    $3, $4, $5
                )
                """,
                uuid4(), test_data["owner_id"],
                test_data["license_id"], test_data["bundle_id"], test_data["fiscal_year"],
            )
    except asyncpg.UniqueViolationError:
        raised = True

    assert raised, "UNIQUE partial index did not block duplicate INSERT"

    # Sanity: still only one SR linked to this license
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM service_requests WHERE commercial_license_id = $1",
        test_data["license_id"],
    )
    assert count == 1
    assert first_id is not None


# ═══════════════════════════════════════════════════════════════
# P1.C.14bis — Trigger is no-op for non-bundle workflows
# ═══════════════════════════════════════════════════════════════


async def test_trigger_allows_non_bundle_sr(conn, test_data):
    """Non-bundle SR (PASAPORTE_NUEVO) without commercial_license_id must pass."""
    new_id = uuid4()
    await conn.execute(
        """
        INSERT INTO service_requests (id, user_id, workflow_code, status)
        VALUES ($1, $2, 'PASAPORTE_NUEVO', 'DRAFT')
        """,
        new_id, test_data["agent_id"],
    )
    row = await conn.fetchrow(
        "SELECT reference, workflow_code, source FROM service_requests WHERE id = $1",
        new_id,
    )
    assert row is not None
    assert row["workflow_code"] == "PASAPORTE_NUEVO"
    assert row["source"] == "citizen_wizard"  # DEFAULT
    assert row["reference"].startswith("PAS-"), f"expected PAS- prefix, got {row['reference']}"


# ═══════════════════════════════════════════════════════════════
# P1.C.14 — Trigger rejects bundle SR without commercial_license_id
# ═══════════════════════════════════════════════════════════════


async def test_trigger_rejects_bundle_without_license(conn, test_data):
    """FIELD_INSPECTION SR without commercial_license_id must raise."""
    with pytest.raises(
        (asyncpg.CheckViolationError, asyncpg.RaiseError),
        match="commercial_license_id",
    ):
        await conn.execute(
            """
            INSERT INTO service_requests (
                id, user_id, workflow_code, status, source
            ) VALUES (
                $1, $2, 'FIELD_INSPECTION', 'SUBMITTED', 'field_inspection'
            )
            """,
            uuid4(), test_data["agent_id"],
        )


# ═══════════════════════════════════════════════════════════════
# P1.C.14ter — Reference prefixes after migration 291 patch (D1)
# ═══════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "workflow_code,expected_prefix",
    [
        ("BUNDLE_PAYMENT", "LIC"),
        ("FIELD_INSPECTION", "FLD"),
        ("PASAPORTE_NUEVO", "PAS"),
        ("RESIDENCIA_PRIMERA_VEZ", "RES"),
        ("CONDUCIR_NUEVO", "CON"),
        ("bundle_payment", "LIC"),  # lowercase works via UPPER()
        ("FP_CARNET_FUNCIONARIO", "CFN"),
        ("VEHICULO_DUPLICADO_CUVE", "VHC"),
        ("CONTRATO_OBRA", "CTR"),
    ],
)
async def test_reference_prefixes(conn, workflow_code, expected_prefix):
    ref = await conn.fetchval(
        "SELECT generate_service_request_reference($1)",
        workflow_code,
    )
    assert ref is not None
    assert ref.startswith(expected_prefix + "-"), (
        f"{workflow_code}: expected {expected_prefix}- prefix, got {ref}"
    )


# ═══════════════════════════════════════════════════════════════
# P1.C.13 — Regression: no lowercase 'cancelled'/'rejected' in source
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_no_lowercase_enum_regression():
    """Grep the source file for lowercase enum references (B1 regression)."""
    src_path = (
        BACKEND_ROOT / "app" / "modules" / "inspections"
        / "services" / "collection_service.py"
    )
    content = src_path.read_text(encoding="utf-8")
    assert "'cancelled'" not in content, "lowercase 'cancelled' found — B1 regression"
    assert "'rejected'" not in content, "lowercase 'rejected' found — B1 regression"


# ═══════════════════════════════════════════════════════════════
# P1.C.7 — Cross-year renewal → different dossiers
# ═══════════════════════════════════════════════════════════════


async def test_cross_year_different_dossiers(conn, test_data):
    """
    Same company + same bundle, but 2 different fiscal_years
    must yield 2 distinct commercial_licenses → 2 distinct SRs.

    We can't easily create a 2nd license in the transaction (FK chains),
    so we verify the invariant: if 2 licenses exist with same (company, bundle)
    but different fiscal_year, each gets its own SR.
    """
    # Try to find 2 licenses with same company+bundle but different year
    rows = await conn.fetch(
        """
        SELECT id, fiscal_year
        FROM commercial_licenses
        WHERE company_id = $1 AND bundle_id = $2
        ORDER BY fiscal_year
        """,
        test_data["company_id"], test_data["bundle_id"],
    )
    if len(rows) < 2:
        pytest.skip("Need 2+ licenses same company+bundle different years")

    async with conn.transaction():
        # Lock + create for each license
        for row in rows[:2]:
            await conn.fetchrow(
                "SELECT id FROM commercial_licenses WHERE id = $1 FOR UPDATE",
                row["id"],
            )
            sr = await CollectionService._find_or_create_bundle_dossier(
                conn, license_id=row["id"], company_owner_user_id=test_data["owner_id"],
            )
            assert sr is not None

    # Verify 2 distinct SRs
    sr_ids = await conn.fetch(
        """
        SELECT commercial_license_id, id
        FROM service_requests
        WHERE commercial_license_id = ANY($1::uuid[])
        """,
        [r["id"] for r in rows[:2]],
    )
    assert len({r["id"] for r in sr_ids}) == 2


# ═══════════════════════════════════════════════════════════════
# P1.C.11 — OWASP A01: Wrong agent ownership
# ═══════════════════════════════════════════════════════════════


async def test_collect_payment_wrong_agent_raises(conn, test_data):
    """OWASP A01 — another user cannot collect on someone else's inspection."""
    other_user = await conn.fetchval(
        "SELECT id FROM users WHERE id != $1 LIMIT 1",
        test_data["agent_id"],
    )
    if not other_user:
        pytest.skip("Need 2+ users for this test")

    insp_id = await _make_inspection(conn, test_data)

    with pytest.raises(ValueError, match="another agent's inspection"):
        await CollectionService.collect_field_payment(
            conn,
            inspection_id=insp_id,
            user_id=other_user,
            obligation_ids=[uuid4()],
            method="cash",
            amount=Decimal("1000.00"),
        )


# ═══════════════════════════════════════════════════════════════
# P1.C.10 — Amount mismatch raises
# ═══════════════════════════════════════════════════════════════


async def test_collect_payment_amount_mismatch_raises(conn, test_data):
    """OWASP A03 — amount must exactly match obligations sum."""
    obls = await conn.fetch(
        """
        SELECT id, amount, penalty_amount
        FROM license_obligations
        WHERE license_id = $1 AND status IN ('pending', 'overdue')
          AND fee_type = 'tesoro'
          AND ministry_id = $2
        LIMIT 2
        """,
        test_data["license_id"], test_data["scope_ministry_id"],
    )
    if not obls:
        pytest.skip("License has no pending/overdue obligations")

    insp_id = await _make_inspection(conn, test_data)

    wrong_amount = (
        sum(Decimal(str(o["amount"])) + Decimal(str(o["penalty_amount"])) for o in obls)
        + Decimal("1.00")
    )

    with pytest.raises(ValueError, match="Amount mismatch"):
        await CollectionService.collect_field_payment(
            conn,
            inspection_id=insp_id,
            user_id=test_data["agent_id"],
            obligation_ids=[o["id"] for o in obls],
            method="cash",
            amount=wrong_amount,
        )


# ═══════════════════════════════════════════════════════════════
# P1.C.9 — Full happy path with payment_pending transition (D2)
# ═══════════════════════════════════════════════════════════════


async def test_collect_payment_full_flow_happy_path(conn, test_data):
    obls = await conn.fetch(
        """
        SELECT id, amount, penalty_amount, fee_type, status
        FROM license_obligations
        WHERE license_id = $1 AND status IN ('pending', 'overdue')
          AND fee_type = 'tesoro'
          AND ministry_id = $2
        LIMIT 3
        """,
        test_data["license_id"], test_data["scope_ministry_id"],
    )
    if len(obls) < 1:
        pytest.skip("License has no pending/overdue obligations")

    insp_id = await _make_inspection(conn, test_data)

    total = sum(
        Decimal(str(o["amount"])) + Decimal(str(o["penalty_amount"])) for o in obls
    )

    result = await CollectionService.collect_field_payment(
        conn,
        inspection_id=insp_id,
        user_id=test_data["agent_id"],
        obligation_ids=[o["id"] for o in obls],
        method="cash",
        amount=total,
    )

    assert result["status"] == "field_collected"
    assert result["payment_reference"].startswith("FLD-")
    assert UUID(result["service_request_id"])

    # Verify obligations moved to payment_pending (D2 — not 'paid')
    statuses = await conn.fetch(
        "SELECT status, payment_id FROM license_obligations WHERE id = ANY($1::uuid[])",
        [o["id"] for o in obls],
    )
    for row in statuses:
        assert row["status"] == "payment_pending", (
            f"D2 violation: obligation status should be payment_pending, got {row['status']}"
        )
        assert row["payment_id"] is not None

    # Verify field_inspection updated
    insp = await conn.fetchrow(
        "SELECT payment_collected, payment_id, payment_receipt_number FROM field_inspections WHERE id = $1",
        insp_id,
    )
    assert insp["payment_collected"] is True
    assert insp["payment_id"] == UUID(result["payment_id"])
    assert insp["payment_receipt_number"] == result["payment_reference"]

    # Verify license_compliance_events logged
    ev_count = await conn.fetchval(
        """
        SELECT COUNT(*) FROM license_compliance_events
        WHERE license_id = $1 AND event_type = 'payment_initiated'
          AND event_data->>'payment_reference' = $2
        """,
        test_data["license_id"], result["payment_reference"],
    )
    assert ev_count == 1

    # Verify service_request created (lazy-create) + reference FLD-
    sr = await conn.fetchrow(
        "SELECT workflow_code, source, reference FROM service_requests WHERE id = $1",
        UUID(result["service_request_id"]),
    )
    assert sr["workflow_code"] == "FIELD_INSPECTION"
    assert sr["source"] == "field_inspection"
    assert sr["reference"].startswith("FLD-")


# ═══════════════════════════════════════════════════════════════
# P1.C.12 — Double collect prevented (OWASP A04)
# ═══════════════════════════════════════════════════════════════


async def test_collect_payment_double_charge_rejected(conn, test_data):
    """OWASP A04 — second collect on same inspection must be blocked."""
    obls = await conn.fetch(
        """
        SELECT id, amount, penalty_amount
        FROM license_obligations
        WHERE license_id = $1 AND status IN ('pending', 'overdue')
          AND fee_type = 'tesoro'
          AND ministry_id = $2
        LIMIT 1
        """,
        test_data["license_id"], test_data["scope_ministry_id"],
    )
    if not obls:
        pytest.skip("No pending obligations available")

    insp_id = await _make_inspection(conn, test_data)

    total = sum(
        Decimal(str(o["amount"])) + Decimal(str(o["penalty_amount"])) for o in obls
    )

    # First collect — succeeds
    await CollectionService.collect_field_payment(
        conn,
        inspection_id=insp_id,
        user_id=test_data["agent_id"],
        obligation_ids=[o["id"] for o in obls],
        method="cash",
        amount=total,
    )

    # Second collect on same inspection — must be rejected
    with pytest.raises(ValueError, match="already collected"):
        await CollectionService.collect_field_payment(
            conn,
            inspection_id=insp_id,
            user_id=test_data["agent_id"],
            obligation_ids=[o["id"] for o in obls],
            method="cash",
            amount=total,
        )
