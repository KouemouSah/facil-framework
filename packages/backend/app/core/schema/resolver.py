"""Merge product schemas (code) with custom-field definitions (DB).

Scoping and inheritance of the DB half live in `repository.py` (Task 12); this
module only merges and orders. Keeping them apart means the merge logic is
testable with zero database.
"""

from __future__ import annotations

from typing import Any

from app.core.schema.registry import SchemaRegistry


def resolve(registry: SchemaRegistry, target: str,
            db_specs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Product specs + custom specs, ordered by (group, order, key).

    A DB field may never shadow a product field: a tenant redefining a
    product-owned key would silently change its meaning for the whole product.
    """
    code_specs = registry.get(target)
    code_keys = {s["key"] for s in code_specs}
    db_specs = db_specs or []

    clashes = sorted({s["key"] for s in db_specs} & code_keys)
    if clashes:
        raise ValueError(
            f"custom field(s) {clashes} shadows a product field on target {target!r}")

    merged = [*code_specs, *db_specs]
    return sorted(merged, key=lambda s: (s.get("group") or "", s.get("order") or 0, s["key"]))
