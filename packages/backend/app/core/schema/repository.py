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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field_definition import FieldDefinition
from app.modules.organization.models import Organization

# Same bound as RBAC role inheritance (rbac/service.py:_MAX_INHERITANCE_DEPTH) —
# a cycle or a pathological hierarchy must never hang a request.
MAX_ORG_DEPTH = 20


async def _ancestor_org_ids(session: AsyncSession, organization_id: str) -> list[str]:
    """The org's ancestors, nearest first, bounded. Cycles cannot occur
    (organization service enforces `_assert_no_parent_cycle`), but we bound
    anyway: a guard that relies on another guard is not a guard."""
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
                    indexed_only: bool = False) -> int:
    """Count OWN definitions (caps are per-organisation — an org cannot be
    penalised for what its parent defined)."""
    stmt = select(func.count()).select_from(FieldDefinition).where(
        FieldDefinition.target == target,
        FieldDefinition.organization_id == organization_id,
        FieldDefinition.archived.is_(False))
    if indexed_only:
        stmt = stmt.where(FieldDefinition.indexed.is_(True))
    return (await session.execute(stmt)).scalar_one()
