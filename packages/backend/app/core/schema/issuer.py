"""Resolve the issuer identity a DOCUMENT actually prints (SP1 debt D1).

`Organization` is the single source of truth for legal identity (real
columns: `legal_name`, `tax_id`, `registration_number`, `logo_url`).
`organization.document_identity` carries the document-specific extras
(`short_code`/`seal_url`/`header_note`/`footer_note`/`legal_mentions`/
`contact_line`). A child `OrgUnit`/`Site` may OPTIONALLY override a narrow
subset of both (`org_unit.document_identity`/`site.document_identity` —
`product_schemas.DOCUMENT_IDENTITY_OVERRIDE`): `legal_name`, `short_code`,
`logo_url`, `contact_line`, `footer_note`.

`resolve_issuer_identity` walks Site -> OrgUnit (nearest ancestor first, via
the materialized `path` — never an N-query loop) -> Organization, and takes
the FIRST NON-EMPTY value per key. It returns, for EVERY key, both the
resolved value AND where it came from (`"site"` / `"org_unit"` /
`"organization"` / `None`) — a bare value would leave the caller unable to
tell "absent" from "inherited", which the SP1 spec names as the classic bug
of this kind of system. The UI needs this to say "Hérité : Facil SA" instead
of silently showing an org-wide value with no indication it isn't the site's
own.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.location.models import Site
from app.modules.organization.models import OrgUnit, Organization

# Keys that live as REAL COLUMNS on Organization — read via getattr, never via
# any document_identity blob (that duplication is exactly the SP1 D1 bug).
_ORG_COLUMN_KEYS = ("legal_name", "tax_id", "registration_number", "logo_url")

# The full set this resolver returns: the four column keys above, plus the six
# keys `product_schemas.DOCUMENT_IDENTITY` declares on `organization.document_identity`.
_DOCUMENT_IDENTITY_KEYS = (
    "short_code", "seal_url", "header_note", "footer_note", "legal_mentions", "contact_line")
ALL_KEYS: tuple[str, ...] = _ORG_COLUMN_KEYS + _DOCUMENT_IDENTITY_KEYS

# Of those ten, only these may be overridden by a child OrgUnit/Site — must
# match `product_schemas.DOCUMENT_IDENTITY_OVERRIDE` exactly (pinned by
# `test_document_identity_schema.py`). `tax_id`/`registration_number`
# (fiscal identifiers) and `seal_url`/`header_note`/`legal_mentions`
# (organisation-wide legal text) are ORGANIZATION-ONLY: no override schema
# declares them, so a child entity cannot even submit them (422 if it tried).
_OVERRIDABLE_KEYS = ("legal_name", "short_code", "logo_url", "contact_line", "footer_note")


def _chain_ids(path: str) -> list[str]:
    """OrgUnit ids from a materialized path (`/root_id/.../leaf_id/`),
    NEAREST first (leaf itself, then its parent, ..., up to the root).

    The path already gives every ancestor id directly — this is a bounded
    string split, never an N-query loop up the tree (the walk this resolver
    must avoid, per the SP1 debt brief)."""
    segments = [s for s in path.split("/") if s]
    return list(reversed(segments))


async def _unit_chain(session: AsyncSession, leaf: OrgUnit) -> list[OrgUnit]:
    """`leaf` and its ancestors, nearest first, fetched in ONE query."""
    ids = _chain_ids(leaf.path)
    if not ids:
        return [leaf]
    rows = (await session.execute(
        select(OrgUnit).where(OrgUnit.id.in_(ids)))).scalars().all()
    by_id = {row.id: row for row in rows}
    # Preserve chain ORDER (nearest first) — a plain `IN` result has no
    # guaranteed ordering. A missing id (deleted mid-flight) is skipped, not
    # fatal: the walk simply continues to the next ancestor.
    return [by_id[i] for i in ids if i in by_id]


def _first_non_empty(candidates: list[tuple[str, Any]]) -> dict[str, Any]:
    """First candidate with a truthy value wins. An EMPTY override (missing
    key, "", None) never shadows the next candidate — that is what lets a
    child clear its own override back to "inherit"."""
    for source, value in candidates:
        if value:
            return {"value": value, "from": source}
    return {"value": None, "from": None}


async def resolve_issuer_identity(
    session: AsyncSession, *, site: Site | None = None,
    org_unit: OrgUnit | None = None, organization: Organization | None = None,
) -> dict[str, dict[str, Any]]:
    """Resolve the issuer identity for a document issued by `site` (or, if no
    site, `org_unit`, or, if neither, `organization` directly).

    Exactly one of the three is the caller's entry point — an OrgUnit or the
    row's own Organization is loaded from it as needed. Returns a dict keyed
    by `ALL_KEYS`; each value is `{"value": ..., "from": "site"|"org_unit"|
    "organization"|None}`.
    """
    if site is None and org_unit is None and organization is None:
        raise ValueError("resolve_issuer_identity requires site, org_unit or organization")

    leaf_unit: OrgUnit | None = org_unit
    if site is not None and site.org_unit_id:
        leaf_unit = await session.get(OrgUnit, site.org_unit_id)

    unit_chain = await _unit_chain(session, leaf_unit) if leaf_unit is not None else []

    if organization is None:
        if site is not None:
            org_id = site.organization_id
        elif org_unit is not None:
            org_id = org_unit.organization_id
        else:  # pragma: no cover — unreachable (one of the three is always set)
            org_id = None
        organization = await session.get(Organization, org_id) if org_id else None
    if organization is None:
        raise ValueError("resolve_issuer_identity: could not resolve an organization")

    result: dict[str, dict[str, Any]] = {}
    for key in ALL_KEYS:
        org_value = (getattr(organization, key) if key in _ORG_COLUMN_KEYS
                     else (organization.document_identity or {}).get(key))
        if key not in _OVERRIDABLE_KEYS:
            result[key] = _first_non_empty([("organization", org_value)])
            continue
        candidates: list[tuple[str, Any]] = []
        if site is not None:
            candidates.append(("site", (site.document_identity or {}).get(key)))
        for unit in unit_chain:
            candidates.append(("org_unit", (unit.document_identity or {}).get(key)))
        candidates.append(("organization", org_value))
        result[key] = _first_non_empty(candidates)
    return result
