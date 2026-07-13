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


def test_default_registry_is_importable_and_empty_at_M0():
    assert isinstance(default_schema_registry(), SchemaRegistry)
