"""Product schemas live in CODE (versioned, non-editable). Custom fields live in
the DB. The resolver merges them; only opted-in targets may be extended."""

import pytest

from app.core.schema.registry import (
    EXTENSIBLE_TARGETS, SchemaRegistry, default_schema_registry,
)
from app.core.schema.resolver import resolve
from app.core.schema.spec import field

L = {"en": "X", "fr": "X", "es": "X"}


def test_registry_registers_and_returns_specs():
    r = SchemaRegistry()
    r.register("organization.document_identity", [field("legal_name", L)])
    assert r.is_registered("organization.document_identity")
    assert [s["key"] for s in r.get("organization.document_identity")] == ["legal_name"]


def test_unknown_target_returns_empty_not_an_error():
    assert SchemaRegistry().get("nope.nope") == []


def test_registering_a_duplicate_key_is_refused():
    r = SchemaRegistry()
    with pytest.raises(ValueError, match="duplicate key"):
        r.register("t.x", [field("a", L), field("a", L)])


def test_extensible_targets_are_an_explicit_opt_in_allowlist():
    # Not every table may carry custom fields. RBAC, settings and audit tables
    # must never be user-extensible.
    assert EXTENSIBLE_TARGETS == {
        "organization.custom_fields": "organization",
        "org_unit.custom_fields": "org_unit",
        "site.custom_fields": "site",
        "party.custom_fields": "party",
    }
    assert not any(t.startswith(("role.", "permission.", "settings.", "account."))
                   for t in EXTENSIBLE_TARGETS)


def test_resolve_merges_code_specs_and_db_specs_sorted_by_group_order_key():
    r = SchemaRegistry()
    r.register("site.custom_fields", [field("code_ref", L, group="a", order=2)])
    db = [field("zone", L, group="a", order=1), field("floor", L, group="b", order=1)]
    out = resolve(r, "site.custom_fields", db_specs=db)
    assert [s["key"] for s in out] == ["zone", "code_ref", "floor"]


def test_a_db_field_cannot_shadow_a_code_field():
    # A tenant must never be able to redefine a product-owned field.
    r = SchemaRegistry()
    r.register("site.custom_fields", [field("code_ref", L)])
    with pytest.raises(ValueError, match="shadows a product field"):
        resolve(r, "site.custom_fields", db_specs=[field("code_ref", L)])


def test_default_registry_carries_exactly_the_shipped_product_schemas():
    # M0 shipped this registry empty (product schemas land in M2/M3). M2 wires
    # `organization.document_identity` in — this test now pins the exact set of
    # targets so a stray `register()` call is caught immediately instead of
    # silently colliding with a later one.
    r = default_schema_registry()
    assert isinstance(r, SchemaRegistry)
    assert r.targets == ["organization.document_identity"]


def test_registry_state_cannot_be_mutated_through_get_or_register():
    # The registry is a process-wide source of truth for product schemas.
    # Handing out the live list would let any caller silently corrupt what
    # every other caller sees — no exception, no trace.
    specs = [field("a", L)]
    r = SchemaRegistry()
    r.register("t.x", specs)

    specs.append(field("injected_via_register", L))   # mutate the caller's list
    assert [s["key"] for s in r.get("t.x")] == ["a"]

    r.get("t.x").append(field("injected_via_get", L))  # mutate the returned list
    assert [s["key"] for s in r.get("t.x")] == ["a"]
