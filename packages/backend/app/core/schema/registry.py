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
    def __init__(self) -> None:
        self._schemas: dict[str, list[dict[str, Any]]] = {}

    def register(self, target: str, specs: list[dict[str, Any]]) -> None:
        keys = [s["key"] for s in specs]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ValueError(f"target {target!r} declares duplicate key(s): {sorted(dupes)}")
        self._schemas[target] = specs

    def is_registered(self, target: str) -> bool:
        return target in self._schemas

    def get(self, target: str) -> list[dict[str, Any]]:
        return self._schemas.get(target, [])

    @property
    def targets(self) -> list[str]:
        return sorted(self._schemas)


def default_schema_registry() -> SchemaRegistry:
    """Registry pre-loaded with the built-in product schemas.

    Empty at M0 — `organization.document_identity` lands in M2 and
    `organization.settings` in M3. Custom-field targets carry no code schema by
    design: everything they expose comes from the DB.
    """
    return SchemaRegistry()
