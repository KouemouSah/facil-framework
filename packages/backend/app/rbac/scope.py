"""Scope model + coverage semantics for RBAC (D4.3).

A scope is a point (or region) in the org -> unit -> site hierarchy:
{organization_id?, org_unit_id? (+ its materialized path), site_id?}. NULLs widen
it (no org = global; no unit = whole org; no site = whole unit subtree).

`covers(assignment, request)` answers: does an account_role granted at
`assignment` authorize an operation requested at `request`? An assignment covers
a request when it is an ANCESTOR-OR-EQUAL region of it:

- org:  assignment global (None) OR same organization;
- unit: assignment has no unit OR the request's unit lies in the assignment unit's
        subtree (materialized-path prefix);
- site: assignment has no site OR the same site.

The path lookups themselves are DB-backed and live in repository.resolve_scope;
this module stays pure (dataclass + the coverage predicate) so it is trivially
unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class Scope:
    organization_id: str | None = None
    org_unit_id: str | None = None
    unit_path: str | None = None      # materialized path of org_unit_id ("/a/b/")
    site_id: str | None = None

    @property
    def is_global(self) -> bool:
        return (self.organization_id is None and self.org_unit_id is None
                and self.site_id is None)


def covers(assignment: Scope, request: Scope) -> bool:
    """True if a grant at `assignment` authorizes an operation at `request`."""
    if assignment.organization_id is not None:
        if request.organization_id != assignment.organization_id:
            return False
    if assignment.org_unit_id is not None:
        # The request must target something inside the assignment unit's subtree.
        if not request.unit_path or not assignment.unit_path:
            return False
        if not request.unit_path.startswith(assignment.unit_path):
            return False
    if assignment.site_id is not None:
        if request.site_id != assignment.site_id:
            return False
    return True


def _pick(request: Request, *keys: str) -> str | None:
    """First non-empty value among the request's path then query params."""
    for key in keys:
        val = request.path_params.get(key)
        if val:
            return str(val)
    for key in keys:
        val = request.query_params.get(key)
        if val:
            return val
    return None


def raw_scope_ids(request: Request) -> dict[str, str | None]:
    """Extract the scope-bearing ids from the request (path + query), no DB hit.

    Maps the route conventions used across the API:
    org_id|organization_id -> org; unit_id|org_unit_id -> unit; site_id -> site.
    """
    return {
        "organization_id": _pick(request, "org_id", "organization_id"),
        "org_unit_id": _pick(request, "unit_id", "org_unit_id"),
        "site_id": _pick(request, "site_id"),
    }
