# -*- coding: utf-8 -*-
"""
Regression test for the bundle-workflow fee_type invariant.

Hotfix P1.1 (2026-04-14):
BundleWorkflowService.initiate_payment assumes every obligation inside a
single entity_group shares the same fee_type. This assumption is not
captured anywhere in the code — it derives from the 1:1 mapping inside
v_obligation_routing where `validates_fee_type` is unique per
`entity_code`. If a future migration introduces an N:M mapping, the
hotfix `entity_fee_type = entity_obligations[0]['fee_type']` would pick
an arbitrary value and the other obligations would end up attached to a
service_payment with a mismatched fee_type.

This test asserts the invariant against the real DB and fails loudly if
the mapping ever drifts.

Also validates that:
- service_payments_fee_type_check still matches the
  license_obligations_fee_type_check domain, so the hotfix stays valid.
"""

import sys
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

pytestmark = pytest.mark.asyncio


def load_database_url() -> str:
    env_path = BACKEND_ROOT / ".env"
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("DATABASE_URL="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("DATABASE_URL not found in backend/.env")


@pytest_asyncio.fixture(scope="function")
async def conn():
    c = await asyncpg.connect(load_database_url())
    yield c
    await c.close()


# ─────────────────────────────────────────────────────────────
# T1 — v_obligation_routing is 1:1 between validates_fee_type and
#      entity_code for payment_validator role
# ─────────────────────────────────────────────────────────────


async def test_v_obligation_routing_is_one_to_one(conn):
    """Invariant: every validates_fee_type maps to exactly one entity_code
    (in the payment_validator routing_role). This is what makes the
    hotfix `entity_fee_type = entity_obligations[0]['fee_type']` safe.
    """
    rows = await conn.fetch(
        """
        SELECT validates_fee_type, COUNT(DISTINCT entity_code) AS distinct_entities
        FROM v_obligation_routing
        WHERE routing_role = 'payment_validator'
        GROUP BY validates_fee_type
        HAVING COUNT(DISTINCT entity_code) > 1
        """
    )
    assert rows == [], (
        "v_obligation_routing has fee_type -> multiple entities mapping; "
        "bundle fee_type assumption broken: " + str([dict(r) for r in rows])
    )


# ─────────────────────────────────────────────────────────────
# T2 — service_payments fee_type domain matches license_obligations
# ─────────────────────────────────────────────────────────────


async def test_service_payments_fee_type_domain_matches_obligations(conn):
    """service_payments.fee_type CHECK must accept every value that
    license_obligations.fee_type accepts, otherwise the hotfix
    (copying the obligation's fee_type to the service_payment) breaks.
    """
    rows = await conn.fetch(
        """
        SELECT conname, pg_get_constraintdef(oid) AS def
        FROM pg_constraint
        WHERE conrelid IN ('service_payments'::regclass,
                           'license_obligations'::regclass)
          AND conname IN ('service_payments_fee_type_check',
                          'license_obligations_fee_type_check')
        ORDER BY conname
        """
    )
    defs = {r["conname"]: r["def"] for r in rows}
    assert "service_payments_fee_type_check" in defs, "missing service_payments check"
    assert "license_obligations_fee_type_check" in defs, "missing license_obligations check"

    # Both constraints must reference the same three values
    for required in ("tesoro", "municipal", "chamber"):
        assert required in defs["service_payments_fee_type_check"], (
            f"service_payments_fee_type_check missing '{required}': "
            + defs["service_payments_fee_type_check"]
        )
        assert required in defs["license_obligations_fee_type_check"], (
            f"license_obligations_fee_type_check missing '{required}': "
            + defs["license_obligations_fee_type_check"]
        )

    # And neither constraint accepts the old placeholder 'bundle'
    assert "'bundle'" not in defs["service_payments_fee_type_check"], (
        "service_payments_fee_type_check mentions 'bundle' — the hotfix "
        "assumption (no 'bundle' literal) is wrong, rethink the code."
    )


# ─────────────────────────────────────────────────────────────
# T3 — All existing license_obligations per license share the fee_type
#      of exactly one entity_code when grouped via v_obligation_routing
# ─────────────────────────────────────────────────────────────


async def test_existing_obligation_groups_are_fee_type_homogeneous(conn):
    """For every license, every entity_group (as computed by the code at
    bundle_workflow_service.py lines 914-916) must contain obligations
    with exactly one distinct fee_type. If this ever fails, the hotfix
    picks an arbitrary fee_type from the group and some obligations
    will be mis-routed.
    """
    rows = await conn.fetch(
        """
        WITH routing AS (
            SELECT DISTINCT validates_fee_type, entity_code
            FROM v_obligation_routing
            WHERE routing_role = 'payment_validator'
        ),
        grouped AS (
            SELECT lo.license_id,
                   COALESCE(r.entity_code, 'TESORO') AS target_entity,
                   COUNT(DISTINCT lo.fee_type) AS distinct_fee_types
            FROM license_obligations lo
            LEFT JOIN routing r ON r.validates_fee_type = lo.fee_type
            GROUP BY lo.license_id, COALESCE(r.entity_code, 'TESORO')
        )
        SELECT license_id, target_entity, distinct_fee_types
        FROM grouped
        WHERE distinct_fee_types > 1
        """
    )
    assert rows == [], (
        "Found entity_groups with heterogeneous fee_type — "
        "bundle_workflow_service fee_type hotfix would pick wrong value: "
        + str([dict(r) for r in rows])
    )
