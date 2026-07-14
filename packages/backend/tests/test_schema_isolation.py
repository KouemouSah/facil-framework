"""THE central, permanent test: organisation A's custom fields are invisible,
unwritable and unreadable for organisation B. If this ever fails, the whole
isolation promise of SP1 is dead."""

from __future__ import annotations

import pytest

from app.core.schema.repository import count_for, definitions_for
from app.models.field_definition import FieldDefinition


async def _define(session, org_id, key, **kw):
    attrs = dict(organization_id=org_id, target="site.custom_fields", key=key,
                type="string", widget="plain",
                label_en=key, label_fr=key, label_es=key)
    attrs.update(kw)  # allow callers to override defaults (e.g. label_en)
    fd = FieldDefinition(**attrs)
    session.add(fd)
    await session.flush()
    return fd


@pytest.mark.asyncio
async def test_org_B_never_sees_org_A_definitions(session, org_a, org_b):
    await _define(session, org_a.id, "convention_no")
    a = await definitions_for(session, "site.custom_fields", org_a.id)
    b = await definitions_for(session, "site.custom_fields", org_b.id)
    assert [d.key for d in a] == ["convention_no"]
    assert b == [], "LEAK: org B can see org A's custom field"


@pytest.mark.asyncio
async def test_definition_applies_to_the_orgs_units_and_sites(session, org_a):
    # Units and sites are FK-bound to the org, so the reach is STRUCTURAL.
    for target in ("site.custom_fields", "org_unit.custom_fields"):
        fd = FieldDefinition(organization_id=org_a.id, target=target, key="zone",
                             type="string", widget="plain",
                             label_en="Z", label_fr="Z", label_es="Z")
        session.add(fd)
    await session.flush()
    units = await definitions_for(session, "org_unit.custom_fields", org_a.id)
    assert [d.key for d in units] == ["zone"]


@pytest.mark.asyncio
async def test_inherit_to_suborgs_reaches_a_child_org_only_when_enabled(
        session, org_a, org_child_of_a):
    await _define(session, org_a.id, "inherited", inherit_to_suborgs=True)
    await _define(session, org_a.id, "private", inherit_to_suborgs=False)
    child = await definitions_for(session, "site.custom_fields", org_child_of_a.id)
    keys = {d.key for d in child}
    assert "inherited" in keys
    assert "private" not in keys


@pytest.mark.asyncio
async def test_inheritance_never_leaks_sideways_to_a_sibling_org(
        session, org_a, org_b):
    await _define(session, org_a.id, "inherited", inherit_to_suborgs=True)
    sibling = await definitions_for(session, "site.custom_fields", org_b.id)
    assert sibling == [], "LEAK: inheritance walked sideways instead of down"


@pytest.mark.asyncio
async def test_archived_definitions_are_excluded(session, org_a):
    await _define(session, org_a.id, "old", archived=True)
    assert await definitions_for(session, "site.custom_fields", org_a.id) == []


@pytest.mark.asyncio
async def test_nearer_ancestor_wins_over_a_farther_one_on_the_same_key(
        session, org_a, org_child_of_a):
    """SEC-101: a grandchild querying with a key defined by BOTH its parent AND
    its grandparent (both inherit_to_suborgs=True) must deterministically get
    the NEARER (parent's) definition — not whichever row a DB scan happens to
    return first. Proximity is lineage distance, not `group`/`order` (both
    default to ""/0 and cannot break the tie)."""
    from app.modules.organization.models import Organization
    grandchild = Organization(code="org-a-grandchild", legal_name="Grandchild",
                              parent_id=org_child_of_a.id)
    session.add(grandchild)
    await session.flush()

    await _define(session, org_a.id, "policy", inherit_to_suborgs=True,
                 label_en="grandparent's policy")
    await _define(session, org_child_of_a.id, "policy", inherit_to_suborgs=True,
                 label_en="parent's policy")

    result = await definitions_for(session, "site.custom_fields", grandchild.id)
    assert [d.key for d in result] == ["policy"]
    assert result[0].label_en == "parent's policy", (
        "the farther (grandparent) definition won instead of the nearer "
        "(parent) one — inheritance precedence is not lineage-ordered")


@pytest.mark.asyncio
async def test_count_for_is_per_organization_not_inherited(
        session, org_a, org_b, org_child_of_a):
    """Caps are per-org: a child must not be penalised for its parent's
    definitions, and org B's count must stay at zero regardless of org A."""
    await _define(session, org_a.id, "f1", inherit_to_suborgs=True)
    await _define(session, org_a.id, "f2")
    assert await count_for(session, "site.custom_fields", org_a.id) == 2
    assert await count_for(session, "site.custom_fields", org_child_of_a.id) == 0
    assert await count_for(session, "site.custom_fields", org_b.id) == 0


@pytest.mark.asyncio
async def test_count_for_excludes_archived_and_can_filter_indexed_only(
        session, org_a):
    await _define(session, org_a.id, "old", archived=True)
    await _define(session, org_a.id, "plain")
    await _define(session, org_a.id, "searchable", indexed=True)
    assert await count_for(session, "site.custom_fields", org_a.id) == 2
    assert await count_for(
        session, "site.custom_fields", org_a.id, indexed_only=True) == 1
