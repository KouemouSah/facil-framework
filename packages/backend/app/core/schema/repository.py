"""Scoped resolution of custom-field definitions.

Three rules (spec §7):
  1. A definition ALWAYS belongs to one organisation (organization_id NOT NULL).
     No global custom field exists — that would be the very cross-tenant
     corruption vector we refuse.
  2. It reaches that org's units and sites (FK-bound => structural reach), and —
     only if `inherit_to_suborgs` — its CHILD organisations. We resolve this by
     walking Organization.parent_id UPWARD from the requesting org to find its
     ancestors, bounded, then keeping only ancestor definitions marked
     `inherit_to_suborgs` — so a definition can only ever flow down a lineage,
     never sideways to a sibling.
  3. We inherit DEFINITIONS, not VALUES. Each row holds its own value.
"""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field_definition import FieldDefinition
from app.modules.organization.models import Organization

# Same bound as RBAC role inheritance (rbac/service.py:_MAX_INHERITANCE_DEPTH) —
# a cycle or a pathological hierarchy must never hang a request.
MAX_ORG_DEPTH = 20


async def _ancestor_org_ids(session: AsyncSession, organization_id: str) -> list[str]:
    """The org's ancestors, nearest first, bounded. Cycles cannot occur
    (organization service enforces `_assert_no_parent_cycle`), but we bound
    anyway: a guard that relies on another guard is not a guard.

    Dialect-guarded (repo rule: Postgres-specific SQL degrades cleanly under
    any other dialect): Postgres walks the whole lineage in ONE round trip via
    a bounded `WITH RECURSIVE` CTE (`_ancestor_org_ids_cte`); every other
    dialect (SQLite, the test suite's default) falls back to the original
    bounded sequential-query loop (`_ancestor_org_ids_loop`) — a textbook N+1,
    but a correct and simple one, and SQLite is never the production path
    100+ concurrent agents actually hit.
    """
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "postgresql":
        return await _ancestor_org_ids_cte(session, organization_id)
    return await _ancestor_org_ids_loop(session, organization_id)


async def _ancestor_org_ids_loop(session: AsyncSession, organization_id: str) -> list[str]:
    """The original N+1: up to `MAX_ORG_DEPTH` sequential round trips, one per
    hop up the lineage. Kept as the non-Postgres fallback — see
    `_ancestor_org_ids`'s docstring."""
    ancestors: list[str] = []
    current = organization_id
    for _ in range(MAX_ORG_DEPTH):
        parent = (await session.execute(
            select(Organization.parent_id).where(Organization.id == current)
        )).scalar_one_or_none()
        if not parent:
            break
        ancestors.append(parent)
        current = parent
    return ancestors


async def _ancestor_org_ids_cte(session: AsyncSession, organization_id: str) -> list[str]:
    """The same result as `_ancestor_org_ids_loop`, in ONE round trip: a
    `WITH RECURSIVE` CTE walks `organization.parent_id` upward, carrying its
    own `depth` counter bounded by `:max_depth` — a guard that relies on
    another guard (only the ORM loop being bounded) is not a guard, so the
    SQL itself must refuse to recurse past `MAX_ORG_DEPTH` even though the
    organization service already forbids cycles (`_assert_no_parent_cycle`).
    `ORDER BY depth` reproduces the loop's nearest-first ordering, which
    `definitions_for`'s precedence walk (`by_org.get(org_id, {})` iterated in
    `(organization_id, *ancestors)` order) depends on.
    """
    rows = (await session.execute(text(
        """
        WITH RECURSIVE ancestors(id, depth) AS (
            SELECT parent_id, 1
            FROM organization
            WHERE id = :org_id AND parent_id IS NOT NULL
          UNION ALL
            SELECT o.parent_id, a.depth + 1
            FROM organization o
            JOIN ancestors a ON o.id = a.id
            WHERE o.parent_id IS NOT NULL AND a.depth < :max_depth
        )
        SELECT id FROM ancestors ORDER BY depth ASC
        """
    ), {"org_id": organization_id, "max_depth": MAX_ORG_DEPTH})).scalars().all()
    return list(rows)


async def definitions_for(session: AsyncSession, target: str,
                          organization_id: str) -> list[FieldDefinition]:
    """Active definitions visible to `organization_id` for `target`.

    Visibility = the org's OWN definitions, plus any ancestor's definitions
    that have `inherit_to_suborgs=True`. Ancestors are walked from
    `organization_id` upward (never sideways to a sibling), bounded, so
    inheritance can only ever flow down a lineage — never leak across it.
    """
    ancestors = await _ancestor_org_ids(session, organization_id)

    own = (FieldDefinition.organization_id == organization_id)
    if ancestors:
        inherited = (FieldDefinition.organization_id.in_(ancestors)
                     & FieldDefinition.inherit_to_suborgs.is_(True))
        scope = own | inherited
    else:
        scope = own

    rows = (await session.execute(
        select(FieldDefinition)
        .where(FieldDefinition.target == target,
               FieldDefinition.archived.is_(False),
               FieldDefinition.is_active.is_(True),
               scope)
    )).scalars().all()

    # Precedence must follow LINEAGE PROXIMITY, not row/scan order: the org's
    # own definition wins over any ancestor's, and a nearer ancestor wins over
    # a farther one redefining the same key (`ORDER BY` alone cannot express
    # this — `group`/`order` are user data, not a proximity rank, and ties on
    # them are the common case since both default to ""/0). Group rows by
    # owning org first, then resolve one key at a time by proximity, nearest
    # first, so the outcome is deterministic rather than "whichever ancestor
    # row the DB happened to return first".
    by_org: dict[str, dict[str, FieldDefinition]] = {}
    for row in rows:
        by_org.setdefault(row.organization_id, {})[row.key] = row

    by_key: dict[str, FieldDefinition] = {}
    for org_id in (organization_id, *ancestors):
        for key, row in by_org.get(org_id, {}).items():
            by_key.setdefault(key, row)
    return sorted(by_key.values(), key=lambda d: (d.group, d.order, d.key))


async def count_for(session: AsyncSession, target: str, organization_id: str, *,
                    indexed_only: bool = False, include_archived: bool = False) -> int:
    """Count OWN definitions (caps are per-organisation — an org cannot be
    penalised for what its parent defined).

    `include_archived` defaults to `False` — the pre-existing meaning of this
    function (see `test_count_for_excludes_archived_and_can_filter_indexed_only`)
    is UNCHANGED for every caller that does not opt in. Pass `True` where the
    caller means "how many rows does this org actually occupy", not "how many
    rows are on the org's form right now" — the two differ precisely because
    archive is a non-destructive flag flip (spec §3 principle 7: "rien n'est
    détruit"), so an archived row still holds storage and the
    `(organization_id, target, key)` unique constraint. `indexed_only` and
    `include_archived` are independent axes; the caller decides both.
    """
    stmt = select(func.count()).select_from(FieldDefinition).where(
        FieldDefinition.target == target,
        FieldDefinition.organization_id == organization_id)
    if not include_archived:
        stmt = stmt.where(FieldDefinition.archived.is_(False))
    if indexed_only:
        stmt = stmt.where(FieldDefinition.indexed.is_(True))
    return (await session.execute(stmt)).scalar_one()
