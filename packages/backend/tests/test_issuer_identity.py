"""`core.schema.issuer.resolve_issuer_identity` — SP1 debt D1.

Pure resolver tests against the `session` fixture (SQLite, full schema, no
HTTP layer) — isolation across the RBAC boundary is a separate, API-level
concern covered by `test_issuer_identity_api.py`.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.core.schema.issuer import ALL_KEYS, resolve_issuer_identity
from app.modules.location.models import Site
from app.modules.organization.models import OrgUnit, Organization


def _child_path(parent: OrgUnit | None, unit_id: str) -> tuple[str, int]:
    base = parent.path if parent else "/"
    return f"{base}{unit_id}/", (parent.depth + 1 if parent else 0)


async def _mk_unit(session, org: Organization, *, code: str, parent: OrgUnit | None = None,
                   document_identity: dict | None = None) -> OrgUnit:
    unit = OrgUnit(organization_id=org.id, code=code, name=code,
                   parent_id=parent.id if parent else None,
                   document_identity=document_identity or {})
    session.add(unit)
    await session.flush()
    unit.path, unit.depth = _child_path(parent, unit.id)
    await session.flush()
    return unit


async def _mk_site(session, org: Organization, *, code: str,
                   org_unit: OrgUnit | None = None,
                   document_identity: dict | None = None) -> Site:
    site = Site(organization_id=org.id, org_unit_id=org_unit.id if org_unit else None,
               code=code, name=code, document_identity=document_identity or {})
    session.add(site)
    await session.flush()
    return site


@pytest_asyncio.fixture
async def org(session):
    o = Organization(code="issuer-org", legal_name="Org SA", tax_id="TAX-1",
                     registration_number="REG-1", logo_url="https://x/org-logo.png",
                     document_identity={"short_code": "ORG-SC", "seal_url": "https://x/seal.png",
                                        "header_note": "Org header", "footer_note": "Org footer",
                                        "legal_mentions": "<p>Org mentions</p>",
                                        "contact_line": "org@x.com"})
    session.add(o)
    await session.flush()
    return o


@pytest.mark.asyncio
async def test_organization_only_every_key_resolves_from_organization(session, org):
    result = await resolve_issuer_identity(session, organization=org)
    assert set(result) == set(ALL_KEYS)
    assert result["legal_name"] == {"value": "Org SA", "from": "organization"}
    assert result["tax_id"] == {"value": "TAX-1", "from": "organization"}
    assert result["registration_number"] == {"value": "REG-1", "from": "organization"}
    assert result["logo_url"] == {"value": "https://x/org-logo.png", "from": "organization"}
    assert result["short_code"] == {"value": "ORG-SC", "from": "organization"}
    assert result["seal_url"]["from"] == "organization"
    assert result["contact_line"] == {"value": "org@x.com", "from": "organization"}


@pytest.mark.asyncio
async def test_key_set_nowhere_reports_none_not_a_bare_absence(session):
    # A minimal org — only the NOT NULL legal_name is set. Every other key
    # must report {"value": None, "from": None}: absent is never confused
    # with "inherited from a level that happens to hold an empty string".
    o = Organization(code="bare-org", legal_name="Bare SA")
    session.add(o)
    await session.flush()
    result = await resolve_issuer_identity(session, organization=o)
    assert result["tax_id"] == {"value": None, "from": None}
    assert result["short_code"] == {"value": None, "from": None}
    assert result["seal_url"] == {"value": None, "from": None}
    assert result["legal_name"] == {"value": "Bare SA", "from": "organization"}


@pytest.mark.asyncio
async def test_org_unit_override_beats_organization(session, org):
    unit = await _mk_unit(session, org, code="dept", document_identity={"short_code": "UNIT-SC"})
    result = await resolve_issuer_identity(session, org_unit=unit)
    assert result["short_code"] == {"value": "UNIT-SC", "from": "org_unit"}
    # legal_name is untouched by the unit -> still falls back to the org.
    assert result["legal_name"] == {"value": "Org SA", "from": "organization"}


@pytest.mark.asyncio
async def test_site_override_beats_org_unit_beats_organization(session, org):
    unit = await _mk_unit(session, org, code="dept", document_identity={"legal_name": "Unit Ltd"})
    site = await _mk_site(session, org, code="branch-1", org_unit=unit,
                          document_identity={"legal_name": "Site LLC"})
    result = await resolve_issuer_identity(session, site=site)
    assert result["legal_name"] == {"value": "Site LLC", "from": "site"}

    # Drop the site's own override -> falls through to the org_unit's.
    site.document_identity = {}
    await session.flush()
    result2 = await resolve_issuer_identity(session, site=site)
    assert result2["legal_name"] == {"value": "Unit Ltd", "from": "org_unit"}


@pytest.mark.asyncio
async def test_empty_override_does_not_shadow_the_parent_value(session, org):
    # A literal "" (or missing key) at a nearer level must NOT win over a
    # farther level's real value — an empty override means "inherit", not
    # "print nothing".
    unit = await _mk_unit(session, org, code="dept")
    site = await _mk_site(session, org, code="branch-1", org_unit=unit,
                          document_identity={"legal_name": "", "short_code": None})
    result = await resolve_issuer_identity(session, site=site)
    assert result["legal_name"] == {"value": "Org SA", "from": "organization"}
    assert result["short_code"] == {"value": "ORG-SC", "from": "organization"}


@pytest.mark.asyncio
async def test_nearest_ancestor_wins_over_a_farther_one(session, org):
    root = await _mk_unit(session, org, code="root", document_identity={"short_code": "ROOT-SC"})
    mid = await _mk_unit(session, org, code="mid", parent=root,
                         document_identity={"short_code": "MID-SC"})
    leaf = await _mk_unit(session, org, code="leaf", parent=mid)  # no override of its own
    result = await resolve_issuer_identity(session, org_unit=leaf)
    assert result["short_code"] == {"value": "MID-SC", "from": "org_unit"}

    # Even the leaf's own override (nearest) beats mid and root.
    leaf.document_identity = {"short_code": "LEAF-SC"}
    await session.flush()
    result2 = await resolve_issuer_identity(session, org_unit=leaf)
    assert result2["short_code"] == {"value": "LEAF-SC", "from": "org_unit"}


@pytest.mark.asyncio
async def test_non_overridable_keys_ignore_child_blobs_even_if_present(session, org):
    # `tax_id` is organization-only (no override schema declares it) — even if
    # a unit's raw blob somehow carries a "tax_id" key (bypassing the API's
    # allowlist, e.g. a direct DB edit), the resolver must never read it: the
    # candidate list for a non-overridable key is ALWAYS just the organization.
    unit = await _mk_unit(session, org, code="dept",
                          document_identity={"tax_id": "SHOULD-NOT-COUNT"})
    result = await resolve_issuer_identity(session, org_unit=unit)
    assert result["tax_id"] == {"value": "TAX-1", "from": "organization"}


@pytest.mark.asyncio
async def test_site_without_org_unit_walks_straight_to_organization(session, org):
    site = await _mk_site(session, org, code="hq")  # no org_unit_id
    result = await resolve_issuer_identity(session, site=site)
    assert result["legal_name"] == {"value": "Org SA", "from": "organization"}


@pytest.mark.asyncio
async def test_requires_at_least_one_entry_point(session):
    with pytest.raises(ValueError):
        await resolve_issuer_identity(session)
