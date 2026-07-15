"""Reserved key names — DERIVED from the real columns, never hardcoded.

A hardcoded denylist drifts the moment someone adds a column. Introspecting the
mapped model (via `sqlalchemy.inspect`) means the guard can never fall out of
sync with the schema: a custom field can never shadow a real column, including
one added by a future migration nobody remembered to also update here.
"""

from __future__ import annotations

from sqlalchemy import inspect

from app.core.schema.registry import EXTENSIBLE_TARGETS

_MODELS: dict[str, type] = {}


def _model_for(target: str) -> type:
    if target not in EXTENSIBLE_TARGETS:
        raise ValueError(
            f"target {target!r} is not extensible; one of {sorted(EXTENSIBLE_TARGETS)}")
    if not _MODELS:
        from app.modules.location.models import Site
        from app.modules.organization.models import Organization, OrgUnit
        # `party.custom_fields` deliberately absent — Party is no longer an
        # extensible target (see `registry.EXTENSIBLE_TARGETS`'s docstring).
        _MODELS.update({
            "organization.custom_fields": Organization,
            "org_unit.custom_fields": OrgUnit,
            "site.custom_fields": Site,
        })
    return _MODELS[target]


def reserved_keys(target: str) -> set[str]:
    """Every real column name on the mapped model for `target`, introspected —
    never a maintained list. `id`/`etag` are added defensively in case a base
    class exposes them as properties rather than mapped columns."""
    return {c.key for c in inspect(_model_for(target)).columns} | {"id", "etag"}


def assert_key_allowed(target: str, key: str) -> None:
    if key in reserved_keys(target):
        raise ValueError(
            f"key {key!r} is reserved on {target!r} (it shadows a real column)")


# The ONLY resources a `relation` field may target. A free-form string would be
# interpolated into a request path by the client picker — an allowlist, not a
# denylist, is the only safe shape here. Verified against the actual reference
# module routes (`app/modules/reference/api/__init__.py`: /countries, /currencies,
# /regions) and the frontend `RefSelect`/`RecordForm` `resource` union
# (`packages/web/src/components/ui/ref-select.tsx`) — these three are the entire
# set of resources the picker knows how to render.
RELATION_RESOURCES: frozenset[str] = frozenset({"countries", "currencies", "regions"})


def assert_relation_resource_allowed(resource: str) -> None:
    if resource not in RELATION_RESOURCES:
        raise ValueError(
            f"relation resource {resource!r} is not allowed; must be one of "
            f"{sorted(RELATION_RESOURCES)}")
