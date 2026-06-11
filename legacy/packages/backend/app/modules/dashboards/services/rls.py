"""
RLS (Row-Level Security) for Looker Studio dashboards (Phase B.2a).

Translates a user identity into a `DashboardAccessContext` that the data
service applies as a SQL WHERE clause. The granularity is **strictly
entity-level** for everyone except admin.

Why entity-only? An agent — even a supervisor — should only see flows
from entities they are explicitly assigned to. Cross-entity visibility
within a ministry is NOT a default privilege; an operator who needs that
gets multiple `agent_profiles` rows (one per entity), or has the admin
role for the same effect. This follows least-privilege.

Resolution rules:
  - Staff (admin): no filter — see everything.
  - Anyone with at least one active `agent_profiles` row: filter by the
    union of `entities.code` values from those rows.
  - Other roles (citizen, business, accountant, …) OR every profile
    deactivated: forbidden — endpoint returns 403, surfaced to the Looker
    connector as an "Access denied" UserError.

Schema verified against live Supabase 2026-05-01:
  agent_profiles(user_id, entity_id, deactivated_at)
  entities(id, code) — joined for entity_code lookup.
  mv_treasury_daily_kpis(entity_code, ...) — filter column is present.

The query is parameterised — no string interpolation of user_id.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import asyncpg
from loguru import logger


# Roles that bypass the per-entity filter. Kept narrow on purpose — adding a
# role here lifts the data wall, so any future addition needs explicit review
# (and probably a separate test in test_dashboards_rls.py).
STAFF_ROLES: frozenset[str] = frozenset({"admin"})


@dataclass(frozen=True)
class DashboardAccessContext:
    """Resolved access shape for a single user request."""

    user_id: str
    user_role: str
    is_staff: bool
    entity_codes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_access(self) -> bool:
        """True if the user is allowed to read dashboard data at all."""
        return self.is_staff or bool(self.entity_codes)

    def describe(self) -> str:
        """Short human-readable form for logs and audit trails."""
        if self.is_staff:
            return f"staff:{self.user_role}"
        if self.entity_codes:
            return f"agent:entities={list(self.entity_codes)}"
        return f"forbidden:{self.user_role}"


class DashboardAccessDenied(Exception):
    """Raised when the user cannot read any dashboard data."""

    def __init__(self, ctx: DashboardAccessContext):
        super().__init__(
            f"User {ctx.user_id} (role={ctx.user_role}) has no agent profile "
            f"with an active entity assignment. Dashboard access denied."
        )
        self.ctx = ctx


async def resolve_user_access(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    user_role: Optional[str],
) -> DashboardAccessContext:
    """Resolve the access shape for a user.

    Pure read — only joins agent_profiles + entities. No side effects.
    Idempotent across retries.
    """
    role = (user_role or "").strip().lower()
    is_staff = role in STAFF_ROLES

    if is_staff:
        # Skip the agent_profiles lookup — staff bypasses the filter.
        return DashboardAccessContext(
            user_id=str(user_id),
            user_role=role,
            is_staff=True,
        )

    async with pool.acquire() as conn:
        # We need entities.code for filtering — agent_profiles only stores
        # entity_id (uuid). LEFT JOIN handles profiles without entity_id;
        # those rows simply contribute no entity_code.
        rows = await conn.fetch(
            """
            SELECT DISTINCT e.code AS entity_code
            FROM agent_profiles ap
            LEFT JOIN entities e ON e.id = ap.entity_id
            WHERE ap.user_id = $1
              AND ap.deactivated_at IS NULL
              AND e.code IS NOT NULL
            """,
            user_id,
        )

    entity_codes = tuple(sorted({r["entity_code"] for r in rows}))
    ctx = DashboardAccessContext(
        user_id=str(user_id),
        user_role=role,
        is_staff=False,
        entity_codes=entity_codes,
    )

    logger.debug(
        "dashboards.rls.resolve user={} access={}",
        ctx.user_id,
        ctx.describe(),
    )
    return ctx


def build_access_filter(
    ctx: DashboardAccessContext,
    *,
    next_param_index: int,
) -> tuple[Optional[str], list[Any]]:
    """Return a `(where_clause, params)` pair to inject into a SQL query.

    `next_param_index` is 1-based: the index that the next $N placeholder
    in the caller's SQL will use.

    Returns:
      - Staff: `(None, [])` — no filter to add (bypass).
      - Agent: `("entity_code = ANY($N::text[])", [list_of_entity_codes])`.
      - Forbidden user: raises DashboardAccessDenied. NEVER returns an
        empty filter for an unauthorised user — that would silently leak
        every row.
    """
    if ctx.is_staff:
        return None, []
    if ctx.entity_codes:
        clause = f"entity_code = ANY(${next_param_index}::text[])"
        return clause, [list(ctx.entity_codes)]
    # Defensive: caller must guard on `ctx.has_access` first.
    raise DashboardAccessDenied(ctx)
