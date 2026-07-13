"""Product schemas — declared in CODE, versioned with it, never editable.

Mirrors `app.core.providers.registry.default_registry()`: one place where every
built-in schema is registered. An administrator FILLS `document_identity`; they
do not REDEFINE its shape. Only DB-backed custom fields are user-defined.
"""

from __future__ import annotations

from typing import Any

# Opt-in allowlist: which (entity, json column) pairs may carry USER-DEFINED
# fields. Deliberately excludes RBAC, settings, accounts and audit — a tenant
# must never be able to bolt fields onto security tables.
EXTENSIBLE_TARGETS: dict[str, str] = {
    "organization.custom_fields": "organization",
    "org_unit.custom_fields": "org_unit",
    "site.custom_fields": "site",
    "party.custom_fields": "party",
}


class SchemaRegistry:
    """Registry of product schemas (code-versioned, non-editable).

    This is a process-wide source of truth for what fields are defined for each
    entity. Any mutation of schemas through get() or register() would silently
    corrupt what every caller sees, with no exception or audit trail.

    To prevent accidental mutations:
    - register() stores a defensive copy of the input list
    - get() returns a defensive copy of the internal list
    """

    def __init__(self) -> None:
        self._schemas: dict[str, list[dict[str, Any]]] = {}

    def register(self, target: str, specs: list[dict[str, Any]]) -> None:
        keys = [s["key"] for s in specs]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ValueError(f"target {target!r} declares duplicate key(s): {sorted(dupes)}")
        # Defensive copy: prevent caller mutations to specs from corrupting registry state
        self._schemas[target] = list(specs)

    def is_registered(self, target: str) -> bool:
        return target in self._schemas

    def get(self, target: str) -> list[dict[str, Any]]:
        # Defensive copy: prevent caller mutations to returned list from corrupting registry state
        return list(self._schemas.get(target, []))

    @property
    def targets(self) -> list[str]:
        return sorted(self._schemas)


def default_schema_registry() -> SchemaRegistry:
    """Registry pre-loaded with the built-in product schemas.

    `organization.document_identity` lands in M2; `organization.settings` lands
    in M3. Custom-field targets carry no code schema by design: everything they
    expose comes from the DB.
    """
    from app.core.schema.product_schemas import DOCUMENT_IDENTITY

    r = SchemaRegistry()
    r.register("organization.document_identity", DOCUMENT_IDENTITY)
    return r
