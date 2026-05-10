# -*- coding: utf-8 -*-
"""
Unit tests for the Looker dashboards RLS layer (Phase B.2a).

Verifies the row-level security primitives across the three scenarios:
  1. admin (staff) — bypass filter, see all rows.
  2. agent (any role except admin) — filter strictly by entity_code.
  3. citizen / no agent profile — forbidden, raises DashboardAccessDenied.

Granularity rationale: an agent at AYUNTAMIENTO and an agent at DGT
should not see each other's flows, even within the same ministry. The
entity is the operational scope; cross-entity visibility requires either
multiple `agent_profiles` rows OR the admin role. Supervisors get the
exact same entity-level filter as anyone else (no privileged
ministry-wide visibility by default — that was a B.2a design rejection).

Tests do NOT touch the database — `resolve_user_access` is exercised
in integration tests against a real pool. These unit tests focus on the
pure logic primitives `DashboardAccessContext.has_access` and
`build_access_filter`, which is where the security guarantee lives.
"""
import sys
from pathlib import Path

import pytest

# Backend root on sys.path so `app...` imports resolve.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.dashboards.services.rls import (
    STAFF_ROLES,
    DashboardAccessContext,
    DashboardAccessDenied,
    build_access_filter,
)


# ---------------------------------------------------------------------------
# DashboardAccessContext shape
# ---------------------------------------------------------------------------


def test_staff_has_access_without_scope():
    ctx = DashboardAccessContext(
        user_id="u-1", user_role="admin", is_staff=True
    )
    assert ctx.has_access is True
    assert "staff:admin" in ctx.describe()


def test_agent_single_entity_has_access():
    ctx = DashboardAccessContext(
        user_id="u-2",
        user_role="agent",
        is_staff=False,
        entity_codes=("AYUNTAMIENTO",),
    )
    assert ctx.has_access is True
    assert "agent:entities=['AYUNTAMIENTO']" in ctx.describe()


def test_agent_multi_entity_has_access():
    ctx = DashboardAccessContext(
        user_id="u-3",
        user_role="agent",
        is_staff=False,
        entity_codes=("AYUNTAMIENTO", "CAMARA_COMERCIO"),
    )
    assert ctx.has_access is True
    assert "AYUNTAMIENTO" in ctx.describe()
    assert "CAMARA_COMERCIO" in ctx.describe()


def test_citizen_no_access():
    ctx = DashboardAccessContext(
        user_id="u-9", user_role="citizen", is_staff=False
    )
    assert ctx.has_access is False
    assert "forbidden:citizen" in ctx.describe()


def test_agent_with_no_assignment_no_access():
    """Edge: agent role but every agent_profiles row is deactivated → no scope → 403."""
    ctx = DashboardAccessContext(
        user_id="u-10", user_role="agent", is_staff=False
    )
    assert ctx.has_access is False


def test_staff_roles_is_narrow():
    """Only `admin` is in STAFF_ROLES today. Adding more lifts the data wall —
    this test exists so any future change to STAFF_ROLES forces a review."""
    assert STAFF_ROLES == frozenset({"admin"})


# ---------------------------------------------------------------------------
# build_access_filter — the SQL-shaped output
# ---------------------------------------------------------------------------


def test_filter_for_staff_returns_none():
    """Staff bypasses RLS — clause is None, nothing to inject in WHERE."""
    ctx = DashboardAccessContext(
        user_id="u-1", user_role="admin", is_staff=True
    )
    clause, params = build_access_filter(ctx, next_param_index=1)
    assert clause is None
    assert params == []


def test_filter_for_single_entity():
    """Critical: every non-admin = entity-level filter, even supervisors."""
    ctx = DashboardAccessContext(
        user_id="u-2",
        user_role="agent",
        is_staff=False,
        entity_codes=("AYUNTAMIENTO",),
    )
    clause, params = build_access_filter(ctx, next_param_index=2)
    assert clause == "entity_code = ANY($2::text[])"
    assert params == [["AYUNTAMIENTO"]]


def test_filter_for_multi_entity_keeps_full_list():
    ctx = DashboardAccessContext(
        user_id="u-3",
        user_role="agent",
        is_staff=False,
        entity_codes=("AYUNTAMIENTO", "CAMARA_COMERCIO", "DGT"),
    )
    clause, params = build_access_filter(ctx, next_param_index=5)
    assert clause == "entity_code = ANY($5::text[])"
    assert params == [["AYUNTAMIENTO", "CAMARA_COMERCIO", "DGT"]]


def test_filter_for_forbidden_user_raises_not_silent_empty_filter():
    """The critical security property: a forbidden user must NOT silently
    get an empty filter (which would expose all data). Caller must guard
    on `ctx.has_access` first; if that guard is bypassed, build_access_filter
    raises rather than returning a clause that lets data through."""
    ctx = DashboardAccessContext(
        user_id="u-9", user_role="citizen", is_staff=False
    )
    with pytest.raises(DashboardAccessDenied):
        build_access_filter(ctx, next_param_index=1)


def test_filter_param_index_threading():
    """The clause text references the index we said the next param uses.
    Important: the caller's existing params (date filters etc.) come first,
    the access param appends after them."""
    ctx = DashboardAccessContext(
        user_id="u-2",
        user_role="agent",
        is_staff=False,
        entity_codes=("AYUNTAMIENTO",),
    )
    # Suppose caller already used $1, $2 for start_date, end_date.
    clause, params = build_access_filter(ctx, next_param_index=3)
    assert "$3" in clause


def test_supervisor_gets_same_entity_filter_as_regular_agent():
    """B.2a design property: supervisors are NOT privileged to see entire
    ministries by default. They get the exact same entity-level filter
    as any agent. Cross-entity visibility requires either multiple
    agent_profiles rows or the admin role."""
    # A supervisor is recognised at the agent_profiles level (is_supervisor
    # column exists) but the dashboard layer ignores it. Two contexts with
    # the same entity_codes must produce the same clause regardless of any
    # supervisor metadata that might be added in a future regression.
    ctx_regular = DashboardAccessContext(
        user_id="u-7", user_role="agent", is_staff=False,
        entity_codes=("AYUNTAMIENTO",),
    )
    ctx_supervisor = DashboardAccessContext(
        user_id="u-8", user_role="agent", is_staff=False,
        entity_codes=("AYUNTAMIENTO",),
    )
    c1, p1 = build_access_filter(ctx_regular, next_param_index=1)
    c2, p2 = build_access_filter(ctx_supervisor, next_param_index=1)
    assert c1 == c2
    assert p1 == p2


# ---------------------------------------------------------------------------
# DashboardAccessDenied error shape
# ---------------------------------------------------------------------------


def test_access_denied_carries_context():
    ctx = DashboardAccessContext(
        user_id="u-9", user_role="business", is_staff=False
    )
    err = DashboardAccessDenied(ctx)
    assert err.ctx is ctx
    assert "u-9" in str(err)
    assert "business" in str(err)
